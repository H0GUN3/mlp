"""Read-only native TT50/SN50/SN200 and Hawkes early-history diagnosis."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
HAWKES = HERE.parent / "sn_hawkes_horizon_contrast_20261017"
SEEDS = (11, 23, 37)
TYPES = ("cpu_load", "network_delay", "network_loss")


def logp(values):
    shifted = values.astype(np.float64) - values.max(axis=1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))


def score(values, labels):
    fault = labels >= 0
    selected = values[fault]
    truth = selected[np.arange(len(selected)), labels[fault], None]
    above = (selected > truth).sum(axis=1)
    ties = (selected == truth).sum(axis=1)
    return np.minimum(np.maximum(1 - above, 0), ties) / ties


def category(before, after):
    return ("both_correct" if after else "new_wrong") if before else (
        "new_correct" if after else "both_wrong")


def self_check():
    np.testing.assert_array_equal(
        score(np.array([[1., 1.], [0., 1.], [9., 0.]]), np.array([0, 0, -1])),
        [.5, 0.])
    assert [category(a, b) for a, b in [(1, 1), (1, 0), (0, 1), (0, 0)]] == [
        "both_correct", "new_wrong", "new_correct", "both_wrong"]
    np.testing.assert_allclose(
        np.exp(logp(np.array([[10000., 10000.], [0., 0.]]))), .5)


def differences(actual, expected, path=""):
    if isinstance(actual, dict) and isinstance(expected, dict) and actual.keys() == expected.keys():
        return [item for key in actual
                for item in differences(actual[key], expected[key], path + "/" + str(key))]
    if isinstance(actual, list) and isinstance(expected, list) and len(actual) == len(expected):
        return [item for i, (a, b) in enumerate(zip(actual, expected))
                for item in differences(a, b, path + "/" + str(i))]
    return [] if actual == expected else [(path, actual, expected)]


def analyze():
    hashes = {}

    def digest(path):
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[str(path)] = value
        return value

    def doc(path):
        digest(path)
        return json.loads(path.read_text())

    def arrays(path, keys=None):
        digest(path)
        with np.load(path, allow_pickle=False) as saved:
            return {key: saved[key] for key in (keys or saved.files)}

    metadata = {s: doc(NATIVE / f"native_inputs/{s}/metadata.json") for s in ("SN", "TT")}
    histories, predictions, configs, splits = {}, {}, {}, {}
    run_rows, trajectories, type_scores, loss_parts = [], {}, {}, []
    for system, budget in (("SN", 50), ("SN", 200), ("TT", 50)):
        types = {t: [] for t in TYPES}
        for seed in SEEDS:
            key = (system, budget, seed)
            folder = NATIVE / f"calibration{budget}/{system}/diagmlp/seed_{seed}"
            config, history, split, summary = [
                doc(folder / (name + ".json")) for name in ("config", "history", "split", "summary")]
            for name in ("config.json", "history.json", "split.json", "scaler.npz",
                         "validation_predictions.npz"):
                assert digest(folder / name) == summary["artifact_hashes"][name]
            pred = arrays(folder / "validation_predictions.npz")
            assert summary["status"] == "passed" and not summary["test_evaluated"]
            assert len(history) == budget
            assert [r["epoch"] for r in history] == list(range(1, budget + 1))
            assert config["effective_options"]["batch_size"] == 256
            expected_updates = (split["counts"]["train"] + 255) // 256
            assert all(r["optimizer_updates"] == expected_updates for r in history)
            total_updates = sum(r["optimizer_updates"] for r in history)
            assert total_updates == summary["optimizer_updates"]
            best = min(history, key=lambda r: r["validation_joint_loss"])
            assert best["epoch"] == summary["best_epoch"]
            assert best["validation_joint_loss"] == summary["best_validation_joint_loss"]
            np.testing.assert_array_equal(pred["indices"], split["indices"]["validation"])
            np.testing.assert_allclose(score(pred["root_logits"], pred["labels"]).mean(),
                                       best["validation_scores"]["conditional_top1"], atol=0, rtol=0)
            # The transition table uses unique argmax only after explicitly excluding ties.
            fault = pred["labels"] >= 0
            roots = pred["root_logits"][fault]
            assert np.all((roots == roots.max(axis=1, keepdims=True)).sum(axis=1) == 1)
            root_lp, detect_lp = logp(pred["root_logits"]), logp(pred["detection_logits"])
            root_ce = float(-root_lp[np.flatnonzero(fault), pred["labels"][fault]].mean())
            detection_ce = float(-detect_lp[np.arange(len(fault)), fault.astype(int)].mean())
            np.testing.assert_allclose((root_ce + detection_ce) / 2,
                                       best["validation_joint_loss"], rtol=1e-6, atol=1e-7)
            loss_parts.append(dict(system=system, budget=budget, seed=seed,
                                   root_ce=root_ce, detection_ce=detection_ce))
            peak = max(history, key=lambda r: r["validation_scores"]["conditional_top1"])
            run_rows.append({
                "system": system, "budget": budget, "seed": seed,
                "train_windows": split["counts"]["train"], "updates_per_epoch": expected_updates,
                "total_updates": total_updates, "selected_epoch": best["epoch"],
                "selected_updates": sum(r["optimizer_updates"] for r in history[:best["epoch"]]),
                "selected_joint_loss": best["validation_joint_loss"],
                "selected_top1": best["validation_scores"]["conditional_top1"],
                "last_top1": history[-1]["validation_scores"]["conditional_top1"],
                "earliest_peak_top1_epoch": peak["epoch"],
                "peak_top1": peak["validation_scores"]["conditional_top1"],
                "first90_epoch": next((r["epoch"] for r in history
                                       if r["validation_scores"]["conditional_top1"] >= .9), None),
                "first95_epoch": next((r["epoch"] for r in history
                                       if r["validation_scores"]["conditional_top1"] >= .95), None),
                "parameters": config["parameters"],
            })
            for j in np.flatnonzero(fault):
                window = metadata[system]["windows"][int(pred["indices"][j])]
                typ = window["root_fault_group"].split("|")[1]
                types[typ].append(int(pred["root_logits"][j].argmax()) == pred["labels"][j])
            histories[key], predictions[key], configs[key], splits[key] = history, pred, config, split
        name = f"{system}{budget}"
        type_scores[name] = {
            t: {"seed_window_evaluations": len(values), "correct": int(sum(values)),
                "top1": float(np.mean(values))} for t, values in types.items()}
        sample_epochs = [1, 5, 7, 8, 10, 25, 50] if budget == 50 else [50, 75, 100, 150, 200]
        trajectories[name] = [
            {"epoch": e, "updates": sum(r["optimizer_updates"] for r in histories[(system, budget, 11)][:e]),
             "train_joint": float(np.mean([histories[(system, budget, s)][e - 1]["train_batch_weighted_joint_loss"] for s in SEEDS])),
             "validation_joint": float(np.mean([histories[(system, budget, s)][e - 1]["validation_joint_loss"] for s in SEEDS])),
             "top1": float(np.mean([histories[(system, budget, s)][e - 1]["validation_scores"]["conditional_top1"] for s in SEEDS]))}
            for e in sample_epochs]
    prefix_keys = ("epoch", "optimizer_updates", "train_batch_weighted_joint_loss",
                   "validation_joint_loss", "validation_scores")
    transitions = []
    for seed in SEEDS:
        a, b = ("SN", 50, seed), ("SN", 200, seed)
        assert configs[a]["input_hashes"] == configs[b]["input_hashes"]
        assert configs[a]["artifact_hashes"] == configs[b]["artifact_hashes"]
        assert splits[a] == splits[b]
        assert all(all(x[k] == y[k] for k in prefix_keys)
                   for x, y in zip(histories[a], histories[b][:50]))
        before, after = predictions[a], predictions[b]
        for key in ("indices", "labels"):
            np.testing.assert_array_equal(before[key], after[key])
        bp, ap = logp(before["root_logits"]), logp(after["root_logits"])
        for j, root in enumerate(before["labels"]):
            if root < 0:
                continue
            index = int(before["indices"][j])
            window = metadata["SN"]["windows"][index]
            old, new = int(bp[j].argmax()), int(ap[j].argmax())
            transitions.append({
                "seed": seed, "index": index, "event": window["event_id"],
                "root_fault_group": window["root_fault_group"], "root": int(root),
                "prediction50": old, "prediction200": new,
                "category": category(old == root, new == root),
                "root_probability50": float(np.exp(bp[j, root])),
                "root_probability200": float(np.exp(ap[j, root])),
                "margin50": float(bp[j, root] - np.delete(bp[j], root).max()),
                "margin200": float(ap[j, root] - np.delete(ap[j], root).max()),
            })
    assert len(transitions) == 195
    transition_summary = {}
    for cat in ("both_correct", "new_correct", "new_wrong", "both_wrong"):
        rows = [r for r in transitions if r["category"] == cat]
        transition_summary[cat] = {
            "seed_window_evaluations": len(rows), "unique_windows": len({r["index"] for r in rows}),
            "unique_events": len({r["event"] for r in rows}),
            "types": dict(Counter(r["root_fault_group"].split("|")[1] for r in rows)),
        }
    support = {}
    for system in ("SN", "TT"):
        split = splits[(system, 50, 11)]
        support[system] = {}
        for part in ("train", "validation"):
            windows = [metadata[system]["windows"][i] for i in split["indices"][part]
                       if metadata[system]["windows"][i]["event_id"]]
            counts = Counter(w["event_id"] for w in windows)
            support[system][part] = {
                "fault_windows": len(windows), "unique_events": len(counts),
                "event_window_min": min(counts.values()),
                "event_window_median": float(np.median(list(counts.values()))),
                "event_window_max": max(counts.values()),
            }
        support[system]["shared_train_validation_events"] = split["shared_event_counts"]["train__validation"]
    sn_meta = doc(HAWKES / "inputs/metadata.json")
    sn_input = arrays(HAWKES / "inputs/selected.npz", ["metrics", "traces", "logs", "labels", "indices"])
    assert digest(HAWKES / "inputs/selected.npz") == sn_meta["selected_npz_sha256"]
    preparation = doc(HAWKES / "inputs/preparation.json")
    assert preparation["source_immutable"] and all(preparation["unchanged_arrays"].values())
    assert sn_meta["forbidden_observation_rows_materialized"] == 0
    tt_root = HERE.parent / "tt_native_support_20261014/artifacts"
    tt_meta = doc(tt_root / "TT.json")
    tt_input = arrays(tt_root / "TT.npz", ["metrics", "traces", "labels", "indices"])
    assert digest(tt_root / "TT.npz") == tt_meta["npz_sha256"]
    missing_trace, input_checks = {}, {}
    for system, data in (("SN", sn_input), ("TT", tt_input)):
        lookup = {int(i): j for j, i in enumerate(data["indices"])}
        split = splits[(system, 50, 11)]
        assert set(lookup) == set(split["indices"]["train"] + split["indices"]["validation"])
        assert not set(lookup) & set(split["indices"]["test"] + split["indices"]["unassigned"])
        scaler = arrays(NATIVE / f"calibration50/{system}/diagmlp/seed_11/scaler.npz")
        train_positions = [lookup[i] for i in split["indices"]["train"]]
        for mod in ("metrics", "traces"):
            train = data[mod][train_positions].astype(np.float64)
            mean, std = train.mean(axis=(0, 2)), train.std(axis=(0, 2))
            constant = np.all(train == train[:1, :, :1, :], axis=(0, 2))
            std[constant] = 0
            mean[constant] = train[0, :, 0, :][constant]
            np.testing.assert_array_equal(mean, scaler[mod + "_mean"])
            np.testing.assert_array_equal(std, scaler[mod + "_std"])
        input_checks[system] = {"allowed_rows": len(lookup), "original_scaler_exact": True}
        pred = predictions[(system, 50, 11)]
        absent = [j for j, idx in enumerate(pred["indices"]) if pred["labels"][j] >= 0
                  and not np.any(data["traces"][lookup[int(idx)], pred["labels"][j], :, 0])]
        missing_trace[system] = {
            "unique_absent_fault_windows": len(absent),
            "fault_windows": int(np.sum(pred["labels"] >= 0)),
            "correct_by_seed": {
                str(seed): sum(int(predictions[(system, 50, seed)]["root_logits"][j].argmax()) ==
                               int(predictions[(system, 50, seed)]["labels"][j]) for j in absent)
                for seed in SEEDS}}
    sn_lookup = {int(i): j for j, i in enumerate(sn_input["indices"])}
    scaler = arrays(NATIVE / "calibration50/SN/diagmlp/seed_11/scaler.npz")
    changed_input = []
    for index in sorted({r["index"] for r in transitions if r["category"] != "both_correct"}):
        j = sn_lookup[index]
        root = int(sn_input["labels"][j])
        z = (sn_input["metrics"][j] - scaler["metrics_mean"][:, None, :]) / (
            scaler["metrics_std"][:, None, :] + 1e-8)
        latency = sn_input["traces"][j, root, :, 0]
        changed_input.append({
            "index": index, "root": root,
            "root_observed_latency_bins": int(np.sum(latency > 0)),
            "root_latency_observed_mean_seconds": float(latency[latency > 0].mean()) if np.any(latency > 0) else None,
            "root_log_l1": float(sn_input["logs"][j, root].sum()),
            "largest_node_log_l1": float(sn_input["logs"][j].sum(axis=1).max()),
            "root_metric_max_abs_z": float(np.abs(z[root]).max()),
        })
    hawkes = []
    for seed in SEEDS:
        folder = HAWKES / f"runs/absolute_seed_{seed}"
        history, config, summary = [doc(folder / (n + ".json")) for n in ("history", "config", "summary")]
        for name in ("history.json", "config.json"):
            assert digest(folder / name) == summary["artifact_hashes"][name]
        assert len(history) == 200 and sum(r["optimizer_updates"] for r in history) == 400
        relative = histories[("SN", 200, seed)]
        row: dict[str, object] = {"seed": seed}
        for arm, h in (("absolute", history), ("relative", relative)):
            for bound in (50, 200):
                best = min(h[:bound], key=lambda r: r["validation_joint_loss"])
                row[f"{arm}{bound}"] = {
                    "epoch": best["epoch"], "joint_loss": best["validation_joint_loss"],
                    "top1": best["validation_scores"]["conditional_top1"],
                    "selected_updates": sum(r["optimizer_updates"] for r in h[:best["epoch"]]),
                }
        row["first50_different_top1_epochs"] = sum(
            a["validation_scores"]["conditional_top1"] != b["validation_scores"]["conditional_top1"]
            for a, b in zip(history[:50], relative[:50]))
        row["first50_different_joint_loss_epochs"] = sum(
            a["validation_joint_loss"] != b["validation_joint_loss"]
            for a, b in zip(history[:50], relative[:50]))
        hawkes.append(row)
    for path, expected in list(hashes.items()):
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    return {
        "status": "PASS", "scope": "native fixed window splits; not corrected SN event split",
        "runs": run_rows, "trajectories": trajectories, "type_scores": type_scores,
        "selected_loss_components": loss_parts, "sn_prefix50_exact": True,
        "transition_summary": transition_summary, "transitions": transitions,
        "dataset_support": support, "cache_checks": input_checks,
        "root_trace_absence": missing_trace, "changed_window_inputs": changed_input,
        "hawkes_first50": hawkes, "source_sha256": hashes,
        "limitations": [
            "No new training, neural inference, or Hawkes fitting.",
            "No protected observation rows or checkpoints decoded.",
            "Per-epoch logits are not retained; window-specific first-correct epochs and learned modalities are not identifiable.",
            "Absolute Hawkes first50 selected predictions unavailable; relative SN50 predictions are available.",
            "Approximate equal-update and cross-system comparisons do not isolate update-count effects.",
        ],
    }


if __name__ == "__main__":
    self_check()
    result = analyze()
    mismatches = differences(result, json.loads((HERE / "RESULTS.json").read_text()))
    if mismatches:
        print("RESULT_DIFFERENCES", len(mismatches), mismatches[:10], flush=True)
    assert not mismatches
    print("NATIVE_LEARNING_CHECK_PASS", len(result["runs"]), result["transition_summary"])
