"""Pair only saved SN validation indices/labels/root logits; no model or feature IO."""
import csv
import hashlib
import io
import json
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

import numpy as np

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
NATIVE = RESEARCH / "native_reproduction_20261013"
PRIOR = RESEARCH / "native_learning_diagnosis_20261018"
SEEDS = (11, 23, 37)
MODELS = ("diagmlp", "eadro")
CATEGORIES = ("both_correct", "new_correct", "new_wrong", "both_wrong", "unresolved_tie")
PREFIX_KEYS = ("epoch", "optimizer_updates", "train_batch_weighted_joint_loss",
               "validation_joint_loss", "validation_scores")
SOURCES = (NATIVE / "native_train.py", NATIVE / "native_models.py",
           RESEARCH / "mlp_prerequisites/eadro_corrected_model.py")


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def document(path):
    return json.loads(Path(path).read_text())


def softmax(logits):
    values = np.asarray(logits, dtype=np.float64)
    assert values.ndim == 2 and values.shape[1] > 1
    assert np.isfinite(values).all()
    weights = np.exp(values - values.max(axis=1, keepdims=True))
    return weights / weights.sum(axis=1, keepdims=True)


def decision(values, root):
    values = np.asarray(values)
    assert values.ndim == 1 and np.isfinite(values).all()
    assert 0 <= root < len(values)
    top = np.flatnonzero(values == values.max()).tolist()
    tied = len(top) > 1
    return {
        "top_candidates": top,
        "tie": tied,
        "root_credit": 1.0 / len(top) if root in top else 0.0,
        "root_probability": float(values[root]),
        "status": ("tied_root" if root in top else "tied_wrong") if tied else (
            "correct" if root in top else "wrong"),
    }


def transition(before, after):
    if before["tie"] or after["tie"]:
        return "unresolved_tie"
    a, b = before["root_credit"] == 1, after["root_credit"] == 1
    return ("both_correct" if b else "new_wrong") if a else (
        "new_correct" if b else "both_wrong")


def paired_rows(model, seed, before, after, windows, services):
    """Join by original index, not storage order; retain event/seed nesting."""
    for saved in (before, after):
        indices, labels, logits = (saved[k] for k in ("indices", "labels", "root_logits"))
        assert indices.ndim == labels.ndim == 1
        assert indices.dtype.kind in "iu" and labels.dtype.kind in "iu"
        assert logits.shape == (len(indices), len(services))
        assert len(labels) == len(indices) == len(set(indices.tolist()))
        assert np.isfinite(logits).all()
        assert np.all((labels >= -1) & (labels < len(services)))
    assert len(services) == len(set(services))
    assert set(before["indices"].tolist()) == set(after["indices"].tolist())
    lookups = [{int(i): j for j, i in enumerate(saved["indices"])}
               for saved in (before, after)]
    probabilities = [softmax(saved["root_logits"]) for saved in (before, after)]
    groups, result = defaultdict(list), []
    for index in sorted(lookups[0]):
        j, k = (lookup[index] for lookup in lookups)
        root = int(before["labels"][j])
        assert root == int(after["labels"][k]), (model, seed, index, "label mismatch")
        window = windows[index]
        if root < 0:
            assert not window["event_id"]
            continue
        event, run_id = window["event_id"], window["run_id"]
        assert run_id and event.startswith(run_id + ":") and event != run_id + ":"
        root_service, fault_type = window["root_fault_group"].split("|")
        assert services[root] == root_service, (event, "metadata root mismatch")
        row: Dict[str, Any] = dict(
            model=model, seed=seed, index=index, event_id=event, run_id=run_id,
            root=root, root_service=root_service, fault_type=fault_type)
        judgments = []
        for budget, saved, pos, probs in zip(
                (50, 200), (before, after), (j, k), probabilities):
            # Window ties use exact saved logits; softmax is for event aggregation.
            judgment = decision(saved["root_logits"][pos], root)
            judgment["root_probability"] = float(probs[pos, root])
            judgment["top_services"] = [services[t] for t in judgment["top_candidates"]]
            row[str(budget)] = judgment
            judgments.append(judgment)
        row["category"] = transition(*judgments)
        result.append(row)
        groups[event].append((row, probabilities[0][j], probabilities[1][k]))
    events = []
    for event, members in sorted(groups.items()):
        identities = {(r["root"], r["root_service"], r["fault_type"], r["run_id"])
                      for r, _, _ in members}
        assert len(identities) == 1, (event, "inconsistent event root/type")
        root, root_service, fault_type, run_id = next(iter(identities))
        counts = Counter(r["category"] for r, _, _ in members)
        row = dict(model=model, seed=seed, event_id=event, run_id=run_id, root=root,
                   root_service=root_service, fault_type=fault_type,
                   indices=[r["index"] for r, _, _ in members],
                   fault_windows=len(members),
                   window_categories={c: counts[c] for c in CATEGORIES},
                   mixed_window_outcomes=len(counts) > 1)
        for budget, pos in ((50, 1), (200, 2)):
            mean = np.stack([member[pos] for member in members]).mean(axis=0)
            judgment = decision(mean, root)
            judgment["top_services"] = [services[t] for t in judgment["top_candidates"]]
            judgment["mean_candidate_probabilities"] = mean.tolist()
            row[str(budget)] = judgment
        row["category"] = transition(row["50"], row["200"])
        events.append(row)
    return result, events


def counts(rows):
    values = Counter(r["category"] for r in rows)
    return {c: values[c] for c in CATEGORIES}


def cross_seed(rows, seeds) -> Dict[str, Any]:
    """Sets refer to full event IDs; seed-event rows never increase sample size."""
    by_event = defaultdict(dict)
    for row in rows:
        assert row["seed"] in seeds
        assert row["seed"] not in by_event[row["event_id"]], "duplicate seed-event"
        by_event[row["event_id"]][row["seed"]] = row
    assert all(set(v) == set(seeds) for v in by_event.values())
    vectors = []
    for event, values in sorted(by_event.items()):
        first = values[seeds[0]]
        assert all((r["root"], r["fault_type"], r["root_service"]) ==
                   (first["root"], first["fault_type"], first["root_service"])
                   for r in values.values())
        vectors.append(dict(event_id=event, root=first["root"],
                            root_service=first["root_service"], fault_type=first["fault_type"],
                            status_vector={str(s): values[s]["category"] for s in seeds}))
    sets = {c: {s: {e for e, v in by_event.items() if v[s]["category"] == c}
                for s in seeds} for c in CATEGORIES}
    unions = {c: set.union(*sets[c].values()) for c in CATEGORIES}
    intersections = {c: set.intersection(*sets[c].values()) for c in CATEGORIES}
    return dict(
        unique_events=len(by_event), seed_event_records=len(rows), vectors=vectors,
        category_sets={c: {
            "by_seed": {str(s): sorted(sets[c][s]) for s in seeds},
            "union": sorted(unions[c]), "union_count": len(unions[c]),
            "intersection": sorted(intersections[c]),
            "intersection_count": len(intersections[c])} for c in CATEGORIES},
        union_overlaps=[
            dict(categories=[a, b], event_ids=sorted(unions[a] & unions[b]),
                 count=len(unions[a] & unions[b]))
            for i, a in enumerate(CATEGORIES) for b in CATEGORIES[i + 1:]
            if unions[a] & unions[b]],
    )


def model_summary(windows, events):
    seed_summaries = {}
    for seed in SEEDS:
        ws = [r for r in windows if r["seed"] == seed]
        es = [r for r in events if r["seed"] == seed]
        seed_summaries[str(seed)] = dict(
            fault_windows=len(ws), unique_events=len(es),
            window_transitions=counts(ws), event_transitions=counts(es),
            mixed_window_events=sum(r["mixed_window_outcomes"] for r in es),
            window_root_credit={b: sum(r[b]["root_credit"] for r in ws) for b in ("50", "200")},
            event_root_credit={b: sum(r[b]["root_credit"] for r in es) for b in ("50", "200")},
            same_seed_event_ids={c: [dict(event_id=r["event_id"], root=r["root"],
                                         root_service=r["root_service"], fault_type=r["fault_type"])
                                    for r in es if r["category"] == c] for c in CATEGORIES})
    return dict(per_seed=seed_summaries,
                window_record_transitions=counts(windows),
                event_record_transitions=counts(events),
                window_category_support={
                    c: dict(seed_window_records=sum(r["category"] == c for r in windows),
                            unique_windows=len({r["index"] for r in windows if r["category"] == c}),
                            unique_events=len({r["event_id"] for r in windows if r["category"] == c}),
                            fault_types=dict(Counter(r["fault_type"] for r in windows
                                                     if r["category"] == c)))
                    for c in CATEGORIES},
                unique_validation_fault_windows=len({r["index"] for r in windows}),
                cross_seed=cross_seed(events, SEEDS))


def analyze():
    prior = document(PRIOR / "RESULTS.json")
    metadata_path = NATIVE / "native_inputs/SN/metadata.json"
    metadata = document(metadata_path)
    watched = {metadata_path, PRIOR / "RESULTS.json", PRIOR / "analyze.py", *SOURCES}
    runs = {}
    for model in MODELS:
        for seed in SEEDS:
            for budget in (50, 200):
                folder = NATIVE / f"calibration{budget}/SN/{model}/seed_{seed}"
                watched.update(folder / name for name in (
                    "config.json", "split.json", "history.json", "summary.json",
                    "scaler.npz", "validation_predictions.npz"))
    before_hashes = {str(p): digest(p) for p in sorted(watched)}
    reused_hashes = {p: value for p, value in before_hashes.items()
                     if p in prior["source_sha256"]}
    assert all(value == prior["source_sha256"][p] for p, value in reused_hashes.items())
    for model in MODELS:
        for seed in SEEDS:
            for budget in (50, 200):
                folder = NATIVE / f"calibration{budget}/SN/{model}/seed_{seed}"
                config, split, history, summary = [
                    document(folder / (name + ".json"))
                    for name in ("config", "split", "history", "summary")]
                assert summary["status"] == "passed" and not summary["test_evaluated"]
                for name in ("config.json", "split.json", "history.json", "scaler.npz",
                             "validation_predictions.npz"):
                    assert before_hashes[str(folder / name)] == summary["artifact_hashes"][name]
                for name in ("split.json", "scaler.npz"):
                    assert before_hashes[str(folder / name)] == config["artifact_hashes"][name]
                assert before_hashes[str(metadata_path)] == config["input_hashes"]["metadata.json"]
                # raw.npz is NOT opened: its identity is a recorded manifest claim only.
                assert metadata["raw_npz_sha256"] == config["input_hashes"]["raw.npz"]
                for source in SOURCES:
                    assert before_hashes[str(source)] == config["source_hashes"][source.name]
                assert config["services"] == metadata["services"]
                assert config["effective_options"]["seed"] == seed
                assert config["model"]["kind"] == model
                assert config["effective_epochs"] == len(history) == budget
                assert [r["epoch"] for r in history] == list(range(1, budget + 1))
                best = min(history, key=lambda r: r["validation_joint_loss"])
                assert best["epoch"] == summary["best_epoch"]
                assert best["validation_joint_loss"] == summary["best_validation_joint_loss"]
                with np.load(folder / "validation_predictions.npz", allow_pickle=False) as saved:
                    pred = {k: saved[k] for k in ("indices", "labels", "root_logits")}
                np.testing.assert_array_equal(pred["indices"], split["indices"]["validation"])
                allowed = set(split["indices"]["train"]) | set(split["indices"]["validation"])
                assert not set(split["indices"]["train"]) & set(split["indices"]["validation"])
                # Only TRAIN/validation identities are projected out of metadata.
                windows = {i: {k: metadata["windows"][i][k] for k in (
                    "event_id", "run_id", "root_fault_group")} for i in allowed}
                fault = pred["labels"] >= 0
                credits = [decision(v, int(y))["root_credit"]
                           for v, y in zip(pred["root_logits"][fault], pred["labels"][fault])]
                np.testing.assert_allclose(
                    np.mean(credits), best["validation_scores"]["conditional_top1"], rtol=0, atol=0)
                runs[(model, seed, budget)] = (config, split, history, summary, pred, windows)
    all_windows, all_events, alignment = [], [], []
    for model in MODELS:
        for seed in SEEDS:
            a, b = (runs[(model, seed, budget)] for budget in (50, 200))
            assert a[0]["input_hashes"] == b[0]["input_hashes"]
            assert a[0]["artifact_hashes"] == b[0]["artifact_hashes"]
            assert a[0]["services"] == b[0]["services"]
            assert a[0]["source_hashes"] == b[0]["source_hashes"]
            assert a[0]["model"] == b[0]["model"] and a[0]["optimizer"] == b[0]["optimizer"]
            assert a[1] == b[1] and a[5] == b[5]
            assert all(all(x[k] == y[k] for k in PREFIX_KEYS)
                       for x, y in zip(a[2], b[2][:50]))
            np.testing.assert_array_equal(a[4]["indices"], b[4]["indices"])
            np.testing.assert_array_equal(a[4]["labels"], b[4]["labels"])
            ws, es = paired_rows(model, seed, a[4], b[4], a[5], a[0]["services"])
            assert len(ws) == 65 and len(es) == 28
            train_events = {a[5][i]["event_id"] for i in a[1]["indices"]["train"]
                            if a[5][i]["event_id"]}
            overlap = train_events & {r["event_id"] for r in es}
            assert len(overlap) == a[1]["shared_event_counts"]["train__validation"] == 28
            alignment.append(dict(
                model=model, seed=seed, validation_windows=len(a[4]["indices"]),
                fault_windows=len(ws), unique_validation_events=len(es),
                unique_train_events=len(train_events), train_validation_shared_events=len(overlap),
                selected_epoch50=a[3]["best_epoch"], selected_epoch200=b[3]["best_epoch"],
                candidate_order=a[0]["services"], input_hashes=a[0]["input_hashes"],
                split_scaler_hashes=a[0]["artifact_hashes"],
                exact_indices_labels_candidate_order_event_root=True,
                exact_input_split_scaler_pair=True, exact_first50_numeric_history=True,
                history_fields=list(PREFIX_KEYS)))
            all_windows.extend(ws)
            all_events.extend(es)
    # Independent integer receipts and a full keyed comparison to the old DiagMLP proof.
    current = {(r["seed"], r["index"]): r for r in all_windows if r["model"] == "diagmlp"}
    old = {(r["seed"], r["index"]): r for r in prior["transitions"]}
    assert len(old) == len(prior["transitions"]) == len(current) == 195
    assert set(current) == set(old)
    for key, row in current.items():
        other = old[key]
        assert (row["event_id"], row["root"], row["category"]) == (
            other["event"], other["root"], other["category"])
        for budget in (50, 200):
            assert row[str(budget)]["top_candidates"] == [other[f"prediction{budget}"]]
    expected = dict(both_correct=174, new_correct=12, new_wrong=1, both_wrong=8)
    assert counts(list(current.values())) == {**expected, "unresolved_tie": 0}
    assert expected == {c: v["seed_window_evaluations"]
                        for c, v in prior["transition_summary"].items()}
    models = {}
    for model in MODELS:
        ws = [r for r in all_windows if r["model"] == model]
        es = [r for r in all_events if r["model"] == model]
        assert len(ws) == 195 and len(es) == 84
        assert len({r["index"] for r in ws}) == 65
        assert len({r["event_id"] for r in es}) == 28
        for seed in SEEDS:
            a, b = (runs[(model, seed, budget)] for budget in (50, 200))
            for run, budget in ((a, "50"), (b, "200")):
                indices = {int(i): j for j, i in enumerate(run[4]["indices"])}
                event_ids = {r["event_id"] for r in es if r["seed"] == seed}
                for event in event_ids:
                    rows = [r for r in ws if r["seed"] == seed and r["event_id"] == event]
                    # Recalculate column sums independently of the event group reducer.
                    totals = np.zeros(len(run[0]["services"]), dtype=np.float64)
                    for row in rows:
                        v = run[4]["root_logits"][indices[row["index"]]].astype(np.float64)
                        p = np.exp(v - max(v))
                        totals += p / sum(p)
                    found = next(r for r in es if r["seed"] == seed and r["event_id"] == event)
                    np.testing.assert_allclose(
                        totals / len(rows), found[budget]["mean_candidate_probabilities"],
                        rtol=1e-14, atol=1e-15)
        models[model] = model_summary(ws, es)
    after_hashes = {p: digest(p) for p in before_hashes}
    assert before_hashes == after_hashes, "Readonly numerical/source input changed"
    result = dict(
        status="PASS", primary_model="diagmlp", supplementary_model="eadro",
        definition={
            "window": "saved fault-window conditional root Top1, not detection gated",
            "event": "mean candidate softmax probabilities over the same event's saved validation fault windows",
            "tie": "exact equality; uniform Top1 root credit; any tied top set in either arm is unresolved_tie",
            "event_key": "full run_id-containing event_id, never fault number alone",
            "seeds": list(SEEDS), "category_order": list(CATEGORIES),
            "event_metric_is_new_descriptive_aggregation": True,
            "replaces_native_window_metric_or_checkpoint_selection": False,
            "raw_input_identity": "recorded raw hash matched between configs/metadata; raw bytes not opened",
            "independence": "65 unique fault windows within 28 unique events; 195 seed-window and 84 seed-event records per model are repeated evaluations, not independent samples",
            "union_overlap": "event category unions can overlap across seeds; do not sum them",
            "selection": "saved native strict minimum validation joint loss, earliest tie; no reselection",
        },
        alignment=alignment, models=models,
        windows=all_windows, events=all_events,
        limitations=[
            "All 28 validation events also have TRAIN windows: not unseen-event generalization.",
            "Physical independence of events is not established; no confidence intervals or significance tests.",
            "SN50 and SN200 are separate seeded runs with matching numeric first50 histories, not optimizer-state continuation.",
            "Eadro is supplementary only; model differences are not an effect of our change.",
            "No checkpoints, features, raw.npz, protected predictions/observations, RE2 or corrected rotation experiment opened.",
        ])
    evidence: Dict[str, Any] = dict(
        status="PASS", readonly_sha256_before=before_hashes,
        readonly_sha256_after=after_hashes, readonly_unchanged=True,
        prior_proof=dict(path=str(PRIOR / "RESULTS.json"),
                         sha256=before_hashes[str(PRIOR / "RESULTS.json")],
                         matching_file_count=len(reused_hashes), matching_sha256=reused_hashes,
                         diagmlp_195_keyed_rows_match=True, expected_window_counts=expected,
                         reused_fields=["seed", "index", "event", "root", "category",
                                        "prediction50", "prediction200"],
                         old_probability_fields_compared=False,
                         old_analyze_executed=False),
        checks=dict(actual_counts_per_pair_65_windows_28_events=True,
                    indices_labels_candidates_event_root=True, input_split_scaler_pair=True,
                    first50_numeric_history=True, saved_summary_hashes=True,
                    independent_event_probability_sum_check=True,
                    native_window_history_score_check=True,
                    full_event_keys_and_seed_deduplication=True),
        accessed_prediction_members=["indices", "labels", "root_logits"],
        scaler_access="sha256 bytes only; no deserialization",
        raw_access="none; recorded hash identity only", checkpoint_access="none",
        feature_observation_access="none", re2_access="none",
        document_policy="Prose changes are not numerical input changes; protocol/brief prose is not a numerical hash gate.",
        environment=dict(python=sys.version, numpy=np.__version__, execution="resident Python kernel"),
        receipt={m: dict(window_records=195, unique_fault_windows=65,
                         event_records=84, unique_events=28,
                         window_transitions=models[m]["window_record_transitions"],
                         event_transitions=models[m]["event_record_transitions"]) for m in MODELS})
    return result, evidence


def write_csv(path, rows, event=False):
    flattened = []
    for row in rows:
        flat = {k: v for k, v in row.items() if k not in ("50", "200")}
        if event:
            for category, count in row["window_categories"].items():
                flat["window_" + category] = count
            del flat["window_categories"]
        for budget in ("50", "200"):
            flat.update({k + budget: v for k, v in row[budget].items()})
        flattened.append({k: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
                          if isinstance(v, (dict, list)) else v for k, v in flat.items()})
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flattened[0]))
        writer.writeheader()
        writer.writerows(flattened)


def main():
    sys.dont_write_bytecode = True
    sys.modules["paired"] = sys.modules[__name__]
    suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_paired.py")
    test_names = []

    def names(group):
        for item in group:
            if isinstance(item, unittest.TestSuite):
                names(item)
            else:
                test_names.append(item.id())

    names(suite)
    log = io.StringIO()
    test_result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    print(log.getvalue(), end="")
    assert test_result.wasSuccessful(), "Synthetic pairing tests failed"
    result, evidence = analyze()
    evidence["synthetic_tests"] = dict(
        status="PASS", tests_run=test_result.testsRun, names=test_names,
        failures=len(test_result.failures), errors=len(test_result.errors),
        skipped=len(test_result.skipped), output=log.getvalue())
    for name, value in (("PAIRED.json", result), ("evidence_paired.json", evidence)):
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    write_csv(HERE / "paired_windows.csv", result["windows"])
    write_csv(HERE / "paired_events.csv", result["events"], event=True)
    print(json.dumps(evidence["receipt"], ensure_ascii=False, indent=2))
    return result, evidence


if __name__ == "__main__":
    main()
