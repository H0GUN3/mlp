"""Read-only frozen SN analysis; emit an apply_patch payload or verify its reports.

No model execution, fitting, source-cache loading, or raw-data access occurs here.
Run with the existing Python 3.8 environment and -B. Reports are applied externally
with apply_patch, not written by this program.
"""
import argparse
import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from scores import event_metrics, paired_cluster_bootstrap
from verify_results import check_alignment, independent_events

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT = ROOT / "research/diagnostic_observability_20261016/sn_tt_audit.json"
PYTHON = "/home/gnho1236/r2/.venv-eadro/bin/python"
KINDS = ("eadro", "diagmlp")
SEEDS = (11, 23, 37)
PARTS = ("train", "validation", "evaluation")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sn_audit(path):
    """Decode ONLY the SN section of the existing audit, not its TT section."""
    lines = []
    active = False
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.startswith('    "SN": {'):
                active = True
                lines.append("{\n")
            elif active:
                if line.startswith("    },"):
                    lines.append("}\n")
                    break
                lines.append(line)
    require(active and lines[-1] == "}\n", "missing complete SN audit section")
    return json.loads("".join(lines))


def proof_gate(verify, text):
    require(verify["verdict"] == "PASS" and "Status: **PASS**" in text,
            "VERIFY.json/VERIFY.md must both PASS")
    upstream = verify["upstream_execution_provenance"]
    replay = verify["independent_verification"]
    require(upstream["verdict"] == "PASS" and upstream["runner_exit"] == 0
            and upstream["runner_sentinel"] == "EVALUATION_PASS 18",
            "missing upstream actual exit/sentinel proof")
    require(replay["verdict"] == "PASS" and replay["runs"] == 18
            and replay["prediction_files"] == 54
            and replay["out_of_fold_events_per_model_seed"] == 36
            and replay["test_command_exit"] == replay["replay_command_exit"] == 0
            and replay["replay_sentinel"] == "VERIFY_PASS 18 54"
            and all(v == "PASS" for v in verify["checks"].values()),
            "missing independent replay proof")


def training_prior(labels, event_ids, candidates=12):
    """One count per TRAIN event, not per window; no query argument exists."""
    roots = {}
    for root, event in zip(labels.tolist(), event_ids.tolist()):
        if root == -1:
            require(event == "", "normal event ID")
            continue
        require(0 <= root < candidates and bool(event), "invalid TRAIN root")
        require(event not in roots or roots[event] == root, "inconsistent TRAIN root")
        roots[event] = root
    counts = np.zeros(candidates, dtype=np.int64)
    for root in roots.values():
        counts[root] += 1
    require(len(roots) == candidates and np.array_equal(counts, np.ones(candidates)),
            "TRAIN prior requires exactly one event per root")
    return counts, counts / counts.sum()


def boundary_counts(windows, fault):
    boundary = [w["original_index"] for w in windows
                if w["start"] < fault["start"] or w["end"] > fault["end_inclusive"]]
    return {"boundary_windows": len(boundary),
            "fully_inside_windows": len(windows) - len(boundary),
            "boundary_original_indices": sorted(boundary)}


def join_observability(event, windows, fault, audit_event, contrasts):
    selected = {w["original_index"] for w in windows}
    require(len(selected) == len(windows) > 0, "duplicate/missing event windows")
    require(selected == set(audit_event["original_indices"]), "audit event index mismatch")
    require(audit_event["root"] == fault["root"]
            and audit_event["service"] == fault["service"], "audit root mismatch")
    joined = []
    for w in sorted(windows, key=lambda row: row["original_index"]):
        require(w["event_id"] == event and w["label"] == fault["root"],
                "window root/event mismatch")
        c = contrasts[w["original_index"]]
        require(c["event_id"] == event and c["root_service"] == fault["service"],
                "original-index audit join mismatch")
        bins = c["root_latency_seconds"]
        require(type(bins) is int and 0 <= bins <= 10, "invalid observed one-second bin count")
        joined.append(dict(c, start=w["start"], end_inclusive=w["end"],
                           boundary=(w["start"] < fault["start"]
                                     or w["end"] > fault["end_inclusive"])))
    present = sum(c["root_latency_seconds"] > 0 for c in joined)
    require(present / len(joined) == audit_event["root_latency_present_fraction"],
            "trace coverage differs from SN audit")
    return dict(boundary_counts(windows, fault),
                windows=len(joined), original_indices=sorted(selected),
                root_trace_observed_bins=sum(c["root_latency_seconds"] for c in joined),
                possible_bins=10 * len(joined), root_trace_present_windows=present,
                root_trace_missing_windows=len(joined) - present,
                root_trace_present_fraction=present / len(joined),
                root_any_edge_fraction=audit_event["root_any_edge_fraction"],
                old_QA_root_metric_at_least_nonroot_fraction=
                audit_event["root_metric_at_least_nonroot_fraction"],
                window_records=joined)


def candidates(event, services):
    values = np.asarray(event["log_probabilities"])
    groups = []
    occupied = 0
    for value in sorted(set(values.tolist()), reverse=True):
        tied = np.flatnonzero(values == value)
        groups.append({"first_rank": occupied + 1, "last_rank": occupied + len(tied),
                       "services": [services[n] for n in tied]})
        occupied += len(tied)
        if occupied >= 3:
            break
    truth = values[event["root"]]
    return {"top_rank_groups_through_3": groups,
            "root_rank_first": int(np.sum(values > truth)) + 1,
            "root_rank_last": int(np.sum(values >= truth)),
            "top1": event["top1"], "top3": event["top3"],
            "root_nll": -float(truth)}


def summarize_events(events):
    require(bool(events), "empty event summary")
    return {metric: float(np.mean([e[metric] for e in events])) for metric in ("top1", "top3")}


def variability(values):
    return {"mean": float(np.mean(values)), "sample_sd_ddof1": float(np.std(values, ddof=1)),
            "min": float(min(values)), "max": float(max(values))}


def paired_summary(records):
    return {metric: {"mean_difference": float(np.mean([r["difference"][metric] for r in records])),
                     "wins": sum(r["difference"][metric] > 0 for r in records),
                     "ties": sum(r["difference"][metric] == 0 for r in records),
                     "losses": sum(r["difference"][metric] < 0 for r in records)}
            for metric in ("top1", "top3")}


def breakdown(records):
    return {"events": len(records),
            "methods": {k: {metric: variability(
                [float(np.mean([r[k]["seeds"][str(seed)][metric] for r in records]))
                 for seed in SEEDS]) for metric in ("top1", "top3")} for k in KINDS},
            "paired": paired_summary(records)}


def log_softmax(x):
    x = np.asarray(x, dtype=np.float64)
    require(np.isfinite(x).all(), "nonfinite saved logits")
    x = x - np.max(x, axis=1, keepdims=True)
    return x - np.log(np.exp(x).sum(axis=1, keepdims=True))


def saved_joint(pred):
    y = pred["labels"]
    faulty = y >= 0
    root = log_softmax(pred["root_logits"])
    detect = log_softmax(pred["detection_logits"])
    detection = float(-np.mean(detect[np.arange(len(y)), faulty.astype(int)]))
    location = float(-np.mean(root[np.flatnonzero(faulty), y[faulty]]))
    return {"detection_window_nll": detection, "root_window_nll": location,
            "joint_loss_recomputed_float64": .5 * detection + .5 * location,
            "max_fault_window_root_nll": float(np.max(-root[np.flatnonzero(faulty), y[faulty]]))}


def analyze():
    require(sys.version_info[:2] == (3, 8) and sys.flags.optimize == 0,
            "use existing Python3.8 with assertions enabled")
    require(np.__version__ == "1.21.5", "frozen NumPy version")
    provenance = {}

    def pin(path, expected=None):
        path = Path(path)
        actual = digest(path)
        if expected is not None:
            require(actual == expected, "hash mismatch: " + str(path))
        provenance[str(path)] = actual
        return actual

    def artifact(name):
        path = HERE / name
        pin(path)
        return read_json(path)

    verify = artifact("VERIFY.json")
    pin(HERE / "VERIFY.md")
    proof_gate(verify, (HERE / "VERIFY.md").read_text())
    selection = artifact("selection.lock.json")
    evaluation = artifact("evaluation.json")
    manifest = artifact("input_manifest.json")
    budgets = artifact("budgets.json")
    pin(HERE / "PLAN.md")
    pin(HERE / "ANALYSIS_PROTOCOL.md")
    for name in ("EVAL_EXECUTION.md", "TRAIN_VERIFY.md", "MAIN_TRAIN_EXECUTION.md",
                 "TRAIN_R0.md", "TRAIN_R1.md", "TRAIN_R2.md", "TRAIN_RECOVERY.md",
                 "EXECUTION_STATE.md", "analysis.py", "test_analysis.py", "verify_results.py"):
        pin(HERE / name)
    require(selection["status"] == "LOCKED" and selection["evaluation_opened"] is False,
            "selection not frozen before evaluation")
    require(evaluation["status"] == manifest["status"] == "PASS"
            and evaluation["original_protected_test_opened"] is False, "upstream status")
    pin(HERE / "selection.lock.json", evaluation["selection_sha256"])
    pin(HERE / "budgets.json", selection["budgets_sha256"])
    pin(HERE / "inputs.npz", selection["input_npz_sha256"])
    require(manifest["input_npz_sha256"] == selection["input_npz_sha256"], "input hash mapping")
    require(evaluation["source_hashes"] == selection["source_hashes"], "frozen sources mismatch")
    for path, expected in selection["source_hashes"].items():
        pin(path, expected)
    protection = manifest["protection"]
    require(protection["permitted_rows"] == 394 and protection["protected_rows_decoded"] == 0
            and protection["raw_streams_scanned"] is False, "input protection proof")
    require(all(manifest["checks"].values())
            and all(manifest["reused_verification"]["checks"].values()), "input checks failed")
    pin(AUDIT, manifest["source_hashes"][str(AUDIT.relative_to(ROOT))])
    audit = sn_audit(AUDIT)
    require(all(audit["checks"].values()), "SN audit checks failed")
    # Never call load_inputs(): its source inventory hashes an old mixed raw cache.
    with np.load(HERE / "inputs.npz", allow_pickle=False) as source:
        arrays = {name: source[name] for name in source.files}
    require(set(arrays) == {"metrics", "traces", "logs", "labels", "indices",
                            "event_ids", "episode_ids", "fold_ids"}, "input key contract")
    for name, shape in (("metrics", (394, 12, 10, 7)), ("traces", (394, 12, 10, 2)),
                        ("logs", (394, 12, 7))):
        require(arrays[name].shape == shape and np.isfinite(arrays[name]).all(),
                "permitted input shape/finite contract")
    require(len(manifest["windows"]) == len(set(arrays["indices"].tolist())) == 394,
            "input row count/identity")
    require(int(np.sum(arrays["labels"] >= 0)) == 325
            and int(np.sum(arrays["labels"] == -1)) == 69, "fault/normal support")
    for i, w in enumerate(manifest["windows"]):
        for key, field in (("indices", "original_index"), ("labels", "label"),
                           ("event_ids", "event_id"), ("episode_ids", "episode_id"),
                           ("fold_ids", "fold_id")):
            require(arrays[key][i] == (w[field] or "" if key == "event_ids" else w[field]),
                    "manifest/input alignment " + key)
    services, faults = manifest["services"], manifest["faults"]
    require(len(services) == 12 and len(faults) == 36, "candidate/event count")
    expected_keys = {(r, k, s) for r in range(3) for k in KINDS for s in SEEDS}
    key = lambda r: (r["rotation"], r["kind"], r["seed"])
    reports = {key(r): r for r in evaluation["runs"]}
    require(len(selection["runs"]) == len(reports) == 18
            and {key(r) for r in selection["runs"]} == set(reports) == expected_keys,
            "18 unique run Cartesian set")
    rotations = {}
    for rotation in range(3):
        budget = artifact("rotation_{}.budget.json".format(rotation))
        done = artifact("rotation_{}.done.json".format(rotation))
        started = artifact("rotation_{}.started.json".format(rotation))
        require(budget["rotations"][str(rotation)] == budgets["rotations"][str(rotation)],
                "rotation budget mismatch")
        require(done["status"] == "PASS" and done["rotation_process_exit"] == 0
                and done["rotation"] == rotation and len(done["runs"]) == 6,
                "rotation completion proof")
        pin(HERE / "rotation_{}.started.json".format(rotation), done["started_sha256"])
        pin(HERE / "rotation_{}.budget.json".format(rotation), done["budget_sha256"])
        require(done["source_hashes"] == started["source_hashes"] == selection["source_hashes"]
                and done["input_npz_sha256"] == started["input_npz_sha256"] ==
                selection["input_npz_sha256"], "rotation source/input proof")
        rotations[rotation] = {"budget": budget, "done": done, "started": started}
    prior_rows, learning, fold_rows = [], [], []
    oof = {(kind, seed): {} for kind in KINDS for seed in SEEDS}
    costs = {kind: [] for kind in KINDS}
    for entry in selection["runs"]:
        rotation, kind, seed = key(entry)
        report = reports[key(entry)]
        folder = HERE / entry["path"]
        config = artifact(entry["path"] + "/config.json")
        pin(folder / "config.json", entry["config_sha256"])
        pin(folder / entry["history_path"], entry["history_sha256"])
        pin(folder / "best.pt", entry["best_sha256"])
        pin(folder / "last_{}.pt".format(entry["epochs"]), entry["last_sha256"])
        pin(folder / "scaler.npz", config["scaler_sha256"])
        require(config["source_hashes"] == selection["source_hashes"], "run sources")
        require(config["input_manifest_sha256"] == provenance[str(HERE / "input_manifest.json")]
                and config["input_npz_sha256"] == selection["input_npz_sha256"], "run inputs")
        history = read_json(folder / entry["history_path"])
        epochs_log = folder / "epochs_200.jsonl"
        pin(epochs_log)
        require([json.loads(line) for line in epochs_log.read_text().splitlines()] == history,
                "history/epoch log mismatch")
        require([h["epoch"] for h in history] == list(range(1, entry["epochs"] + 1)),
                "nonconsecutive history")
        require(all(np.isfinite(v) for h in history for v in h.values()), "nonfinite history")
        selected = min(history, key=lambda h: (h["validation_event_nll"], h["epoch"]))
        require(selected["epoch"] == entry["best_epoch"] == report["selected_epoch"]
                and selected["validation_event_nll"] == entry["best_validation_event_nll"],
                "history selection mismatch")
        budget = budgets["rotations"][str(rotation)]
        require(budget["target_epochs"] == (400 if max(budget["initial_best_epochs"]) >= 180 else 200),
                "extension trigger mismatch")
        require(entry["epochs"] == budget["target_epochs"] == 200
                and entry["budget_bound"] is report["budget_bound"] is False,
                "unexpected frozen budget")
        stage = artifact(entry["path"] + "/stage_200.json")
        for field, value in stage.items():
            require(entry[field] == value, "stage/selection mismatch " + field)
        completed = [r for r in rotations[rotation]["done"]["runs"] if key(r) == key(entry)]
        require(len(completed) == 1 and all(completed[0][f] == v for f, v in stage.items()),
                "stage/rotation completion mismatch")
        require(config["common_initial_state"] == entry["common_initial_state"],
                "common initialization receipt mismatch")
        costs[kind].append({"rotation": rotation, "seed": seed,
                            "stage_seconds": stage["stage_seconds"]})
        part_rows = {}
        for part in PARTS:
            group = {"train": (rotation + 2) % 3,
                     "validation": (rotation + 1) % 3, "evaluation": rotation}[part]
            pos = np.flatnonzero(arrays["fold_ids"] == group)
            require(pos.tolist() == config["indices"][part], "split positions changed")
            filename = "r{}_{}_s{}_{}.npz".format(rotation, kind, seed, part)
            path = HERE / "evaluation" / filename
            pin(path, report["prediction_sha256"][filename])
            with np.load(path, allow_pickle=False) as source:
                pred = {name: source[name] for name in source.files}
            check_alignment(pred, {n: arrays[n][pos] for n in ("labels", "indices", "event_ids")},
                            filename)
            m = independent_events(pred["root_logits"], pred["labels"], pred["event_ids"])
            fixed = event_metrics(pred["root_logits"], pred["labels"], pred["event_ids"])
            saved = report["parts"][part]
            require(len(m["events"]) == 12, "part must contain 12 events")
            for metric in ("top1", "top3", "event_nll"):
                require(abs(m[metric] - saved[metric]) <= 1e-12, "saved score mismatch")
            for a, b, c in zip(m["events"], saved["events"], fixed["events"]):
                require((a["event_id"], a["root"], a["windows"]) ==
                        (b["event_id"], b["root"], b["windows"]), "event mapping mismatch")
                require(a["root"] == faults[a["event_id"]]["root"]
                        and manifest["event_folds"][a["event_id"]] == group, "fault mapping")
                np.testing.assert_allclose(a["log_probabilities"], b["log_probabilities"],
                                           rtol=0, atol=1e-12)
                require(a["top1"] == b["top1"] == c["top1"]
                        and a["top3"] == b["top3"] == c["top3"], "exact tie credits changed")
            components = saved_joint(pred)
            require(np.isclose(components["joint_loss_recomputed_float64"], saved["joint_loss"],
                               rtol=3e-7, atol=1e-6), "saved joint loss mismatch")
            part_rows[part] = dict(top1=m["top1"], top3=m["top3"], event_nll=m["event_nll"],
                                   joint_loss=saved["joint_loss"], **components)
            if part == "train":
                counts, prior = training_prior(pred["labels"], pred["event_ids"])
                prior_score = event_metrics(np.tile(np.log(prior), (len(pos), 1)),
                                            pred["labels"], pred["event_ids"])
                require(prior_score["top1"] == 1 / 12 and prior_score["top3"] == 3 / 12,
                        "uniform prior tie credit")
                if kind == "eadro" and seed == 11:
                    prior_rows.append({"rotation": rotation, "train_group": group,
                                       "train_events": 12, "counts": counts.tolist(),
                                       "probabilities": prior.tolist(),
                                       "top1": prior_score["top1"], "top3": prior_score["top3"]})
            elif part == "validation":
                require(saved["event_nll"] == selected["validation_event_nll"]
                        and saved["joint_loss"] == selected["validation_joint_loss"],
                        "selected inference/history alignment")
            else:
                require(not set(oof[(kind, seed)]) & {e["event_id"] for e in m["events"]},
                        "repeated out-of-fold event")
                oof[(kind, seed)].update({e["event_id"]: e for e in m["events"]})
        updates_per_epoch = int(np.ceil(len(config["indices"]["train"]) / 32))
        require(entry["updates"] == sum(h["updates"] for h in history)
                == updates_per_epoch * entry["epochs"]
                and all(h["updates"] == updates_per_epoch for h in history), "update budget")
        learning.append({"rotation": rotation, "kind": kind, "seed": seed,
                         "selected_epoch": selected["epoch"], "epochs": entry["epochs"],
                         "selected_updates": selected["epoch"] * updates_per_epoch,
                         "total_updates": entry["updates"], "extended": False,
                         "budget_bound": entry["budget_bound"],
                         "first": history[0], "selected": selected, "final": history[-1],
                         "train_online_joint_loss_min": min(h["train_online_joint_loss"] for h in history),
                         "validation_nll_max": max(h["validation_event_nll"] for h in history),
                         "selected_checkpoint": part_rows,
                         "parameter_count": config["parameter_count"],
                         "dropout": config["model"]["dropout"]})
        fold_rows.append({"rotation": rotation, "kind": kind, "seed": seed,
                          "events": 12, **part_rows["evaluation"]})
    require(all(set(v) == set(faults) for v in oof.values()), "36 unique OOF events required")
    audit_events = {e["event_id"]: e for e in audit["events"]}
    contrasts = {c["original_index"]: c for c in audit["root_contrasts"]["windows"]}
    require(len(audit_events) == 36 and len(contrasts) ==
            len(audit["root_contrasts"]["windows"]) == 325, "SN audit coverage")
    records = []
    for event, fault in sorted(faults.items()):
        windows = [w for w in manifest["windows"] if w["event_id"] == event]
        observation = join_observability(event, windows, fault, audit_events[event], contrasts)
        record = {"event_id": event, "recording": fault["run_id"], "fault_type": fault["fault_type"],
                  "root": fault["root"], "root_service": fault["service"],
                  "rotation": manifest["event_folds"][event], "observability": observation}
        for kind in KINDS:
            per_seed = {str(seed): candidates(oof[(kind, seed)][event], services) for seed in SEEDS}
            record[kind] = {"seeds": per_seed,
                            **summarize_events(list(per_seed.values())),
                            "top1_seed_sd": float(np.std([e["top1"] for e in per_seed.values()], ddof=1)),
                            "top3_seed_sd": float(np.std([e["top3"] for e in per_seed.values()], ddof=1)),
                            "top1_candidate_groups_differ_across_seeds":
                            len({tuple(e["top_rank_groups_through_3"][0]["services"])
                                 for e in per_seed.values()}) > 1}
        record["difference"] = {metric: record["diagmlp"][metric] - record["eadro"][metric]
                                for metric in ("top1", "top3")}
        records.append(record)
    require(sum(r["observability"]["boundary_windows"] for r in records) ==
            audit["boundary_audit"]["fault_windows_crossing_injection_boundary"] == 37,
            "joined boundary total mismatch")
    require(set(contrasts) == {i for r in records for i in r["observability"]["original_indices"]},
            "unjoined audit rows")
    seeds = []
    for kind in KINDS:
        for seed in SEEDS:
            seeds.append({"kind": kind, "seed": seed, "events": 36,
                          **summarize_events(list(oof[(kind, seed)].values()))})
    overall = {kind: {metric: variability([r[metric] for r in seeds if r["kind"] == kind])
                      for metric in ("top1", "top3")} for kind in KINDS}
    by_type = {t: breakdown([r for r in records if r["fault_type"] == t])
               for t in sorted({r["fault_type"] for r in records})}
    by_recording = {t: breakdown([r for r in records if r["recording"] == t])
                   for t in sorted({r["recording"] for r in records})}
    require(all(v["events"] == 12 for v in by_type.values())
            and len(by_recording) == 4 and all(v["events"] == 9 for v in by_recording.values()),
            "type/recording support")
    bootstrap = {metric: paired_cluster_bootstrap(
        [r["difference"][metric] for r in records], [r["recording"] for r in records],
        samples=5000, seed=20261017) for metric in ("top1", "top3")}
    strata = {}
    for name, predicate in (
            ("no_missing_trace_windows", lambda o: o["root_trace_missing_windows"] == 0),
            ("some_but_not_all_missing_trace_windows",
             lambda o: 0 < o["root_trace_missing_windows"] < o["windows"]),
            ("all_trace_windows_missing", lambda o: o["root_trace_missing_windows"] == o["windows"]),
            ("zero_boundary_windows", lambda o: o["boundary_windows"] == 0),
            ("one_boundary_window", lambda o: o["boundary_windows"] == 1),
            ("two_boundary_windows", lambda o: o["boundary_windows"] == 2)):
        rows = [r for r in records if predicate(r["observability"])]
        strata[name] = dict(breakdown(rows), event_ids=[r["event_id"] for r in rows],
                           both_methods_wrong_all_seeds=sum(
                               all(r[k]["seeds"][str(s)]["top1"] == 0 for k in KINDS for s in SEEDS)
                               for r in rows))
    totals = {"root_trace_observed_bins": sum(r["observability"]["root_trace_observed_bins"] for r in records),
              "possible_root_bins": 3250,
              "root_trace_missing_windows": sum(r["observability"]["root_trace_missing_windows"] for r in records),
              "boundary_windows": 37, "fully_inside_windows": 288,
              "normal_windows_overlapping_injection": audit["boundary_audit"]["normal_windows_overlapping_injection"]}
    interpretation = {
        "observation_absence": "Real root-trace missingness, not zero latency or absence of all modalities. Missingness is confounded with fault type and neither necessary nor sufficient for Top1 errors.",
        "prior_temporal_loss": "The old 18-feature audit is permutation-insensitive; this native sequence/Hawkes frontend does not use those features. No attribution of current errors to that earlier reduction.",
        "optimization_selection": "TRAIN online joint decreases while validation NLL worsens. Early validation minima and budget_bound=false prove neither convergence nor GNN deficiency. Final TRAIN event accuracy was not saved.",
        "backend_structure": "Observed method gap confounds fusion/position/graph/dropout. No pure GNN causal effect or predetermined architecture.",
        "follow_up": {
            "verdict": "ONE_READ_ONLY_DIAGNOSTIC_HYPOTHESIS; architecture evidence insufficient",
            "hypothesis": "TRAIN-scaler out-of-range held observations may contribute to Eadro held-set confidence/loss inflation.",
            "observed_anchor": {
                "rotation": 0, "kind": "eadro", "seed": 23, "selected_epoch": 23,
                "train_event_top1": 1.0, "train_event_nll": 0.3292644154588491,
                "validation_event_top1": 0.0, "validation_event_nll": 6.875896280397247,
                "validation_joint_loss": 1384.1705322265625},
            "next_check_only": "Join channel-wise standardized extremes from permitted 394 rows using frozen TRAIN scalers to large saved-logit window losses by original index; no refit, clipping, model, or tuning.",
            "reject_if": "Large held losses do not co-occur with out-of-range standardized observations.",
            "status": "NOT RUN. Even co-occurrence would not establish causality or authorize a new experiment."},
        "limitations": [
            "36 previously inspected development events, not 108 independent events or a blind final test.",
            "Known roots/types, unseen combinations; no independent repeated root-type incidents or cold-root evidence.",
            "Shared recordings across training/validation/query; only four recording clusters.",
            "Reconstruction, not exact authors' unified code; architecture and dropout differences.",
            "No direct subtraction from old 95% or window metrics.",
            "Fixed-prediction bootstrap exploratory only; costs not controlled efficiency evidence.",
            "Nonroots are not automatically victims. No case exclusions or causal claims."]}
    return {"verdict": "PASS", "follow_up_verdict": "ONE_DIAGNOSTIC_HYPOTHESIS_ONLY",
            "scope": {"events": 36, "seeds": list(SEEDS), "candidates": 12,
                      "permitted_rows": 394, "fault_windows": 325, "normal_windows": 69,
                      "protected_rows_decoded": 0, "native_raw_scans": 0,
                      "difference_direction": "DiagMLP minus Eadro",
                      "seed_variability": "sample standard deviation ddof=1; not a standard error"},
            "upstream_proof": verify, "services": services, "seed_oof": seeds, "overall": overall,
            "folds": fold_rows, "paired": paired_summary(records), "paired_events": records,
            "by_type": by_type, "by_recording": by_recording,
            "bootstrap": {"samples": 5000, "seed": 20261017, "clusters": 4,
                          "percentiles": [2.5, 97.5], "exploratory_only": True,
                          "metrics": bootstrap},
            "train_event_prior": prior_rows, "learning": learning,
            "observability": {"totals": totals, "strata": strata,
                              "older_18_feature_temporal_audit": audit["temporal_loss"]},
            "costs": {k: {"sum_actual_stage_wall_seconds": sum(r["stage_seconds"] for r in costs[k]),
                          "stages": costs[k]} for k in KINDS},
            "cost_conditions": "CPU, 2 torch intra-op threads and 1 inter-op; at most three rotation processes; six fits serial per rotation. Overlapping stage sums are not elapsed makespan or a controlled efficiency comparison.",
            "interpretation": interpretation,
            "provenance_sha256": dict(sorted(provenance.items()))}


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "|" + "|".join("---" for _ in headers) + "|"] +
                     ["| " + " | ".join(str(v).replace("|", "/") for v in row) + " |"
                      for row in rows]) + "\n"


def number(x):
    return "{:.6f}".format(x)


def report_md(a):
    lines = [
        "# SN 동결 사건진단 분석\n",
        "**수치·프로토콜 판정: PASS. 후속 판정: 구조 변경 실험은 아직 정당화되지 않으며, 아래의 단일 진단 가설만 남긴다.**\n",
        "## 문제와 목적\n",
        "이미 장애 관측 구간이 주어진 사후 원인 서비스 진단이다. 12개 후보 중 실제 원인은 하나이며, "
        "정상 창은 root 순위에서 제외한다. 탐지 head로 순위를 차단하지 않는다. "
        "검사했던 개발 사건 36개를 사건 단위로 분리해 복원 기준법의 실패를 확인한다. "
        "각 사건의 창 확률을 평균한 단일 순위이며, 창 정확도나 사건별 창 적중률 평균이 아니다.\n",
        "## 재현과 검증\n",
        "기존 VERIFY.json/VERIFY.md PASS: 원래 평가 exit 0 / `EVALUATION_PASS 18`, "
        "18 checkpoint·54 예측 파일의 독립 재추론 exit 0 / `VERIFY_PASS 18 54`. "
        "중복 실행의 directory guard exit 1은 원래 성공 실행과 별개이며 출력 덮어쓰기가 없다. "
        "이 분석은 체크포인트를 다시 실행하지 않고 그 검증 증거를 요구하며, 저장 logits를 독립 float64 "
        "확률 pooling 및 고정 scores.py와 대조했다. 입력/라벨/원본 인덱스/사건 대응, "
        "모든 18 전체 history·epoch log·stage 영수증, 선택·소스·checkpoint 해시를 검사한다.\n",
        "아래 명령은 작업 디렉터리에서 실행한다. 프로그램은 파일을 쓰지 않는다. "
        "`--emit-chunk N`은 gzip/base64로 압축한 apply_patch payload의 12,000자 조각을 출력한다. "
        "0번의 total을 보고 모든 조각을 순서대로 결합·해제해 apply_patch에 전달하면 두 보고서를 재생성한다. "
        "기본 실행은 저장된 두 보고서를 byte 단위 재계산 대조한 뒤 sentinel을 출력한다.\n",
        "```sh\n" + PYTHON + " -B -m unittest -v test_analysis\n" +
        PYTHON + " -B analysis.py\n```\n",
        "실제 실행·진단 영수증은 마지막 절에 수록한다. JSON의 provenance_sha256은 전체 사용 artifact의 SHA-256이다. "
        "원자료의 과거 hash는 재검사하지 않았고 혼재 raw cache, 보호 170행은 열지 않았다. "
        "배열 디코딩은 허용 inputs.npz 394행과 54개 저장 예측에 한정한다.\n",
        "## 사건 외부평가\n",
        "seed별 분모는 36. seed 평균은 예측확률 ensemble이 아니라 각 seed의 사건 credit 평균이다. "
        "같은 36사건을 세 번 예측했으므로 **108개 독립 사건이 아니다**. "
        "동률은 반올림/임의 ID 정렬 없이 정확히 같은 score의 무작위 순위 기대 credit을 보존한다.\n",
        table(["방법", "seed", "사건", "Top1", "Top3"],
              [[r["kind"], r["seed"], 36, number(r["top1"]), number(r["top3"])] for r in a["seed_oof"]]),
        table(["방법", "지표", "3seed 평균", "표본 SD (ddof=1)", "최소", "최대"],
              [[k, m] + [number(a["overall"][k][m][v]) for v in ("mean", "sample_sd_ddof1", "min", "max")]
               for k in KINDS for m in ("top1", "top3")]),
        "### 순환별 query 12사건\n",
        table(["순환", "방법", "seed", "Top1", "Top3", "root 사건 NLL", "joint loss"],
              [[r["rotation"], r["kind"], r["seed"]] +
               [number(r[m]) for m in ("top1", "top3", "event_nll", "joint_loss")] for r in a["folds"]]),
        "### TRAIN 사건 root 빈도 prior\n",
        "각 순환의 TRAIN 고유 사건을 root당 한 번 센다. 창 수는 세지 않는다. "
        "모든 root 빈도=1 → 모든 점수=1/12 → 12중 동률 기대 Top1=1/12, Top3=3/12. "
        "query 정답은 채점에만 쓰며 prior 입력 점수를 만들지 않는다.\n",
        table(["순환", "TRAIN 그룹", "사건 수", "root 0–11 사건수", "Top1", "Top3"],
              [[r["rotation"], r["train_group"], 12, ",".join(map(str, r["counts"])),
                number(r["top1"]), number(r["top3"])] for r in a["train_event_prior"]]),
        "### 짝지은 차이와 불확실성\n",
        "방향은 **DiagMLP − Eadro**. 각 사건에서 먼저 세 seed의 credit을 평균하고 차이를 계산한다. "
        "win/tie/loss는 그 차이의 양수/정확한 0/음수이다.\n",
        table(["지표", "평균차", "win", "tie", "loss", "cluster 2.5%", "cluster 97.5%"],
              [[m, number(a["paired"][m]["mean_difference"])] +
               [a["paired"][m][v] for v in ("wins", "ties", "losses")] +
               [number(a["bootstrap"]["metrics"][m][v]) for v in ("lower", "upper")]
               for m in ("top1", "top3")]),
        "고정 helper scores.paired_cluster_bootstrap, recording 4개를 복원추출 5,000회, "
        "seed 20261017, np.percentile 2.5/97.5. 모든 seed의 고정 예측을 사건별 평균한 paired 차이에 적용했다. "
        "재학습/seed 재추출은 없다. 4개뿐인 cluster와 공유 학습·환경에 조건부인 탐색적 범위이며, "
        "운영 모집단 독립성·유의성·학습 불확실성의 증거가 아니다.\n",
    ]
    for title, field in (("고장 종류별", "by_type"), ("recording별", "by_recording")):
        lines += ["### " + title + "\n",
                  table(["그룹", "사건", "E Top1", "D Top1", "ΔTop1 W/T/L",
                         "E Top3", "D Top3", "ΔTop3 W/T/L"],
                        [[g, v["events"], number(v["methods"]["eadro"]["top1"]["mean"]),
                          number(v["methods"]["diagmlp"]["top1"]["mean"]),
                          "/".join(str(v["paired"]["top1"][x]) for x in ("wins", "ties", "losses")),
                          number(v["methods"]["eadro"]["top3"]["mean"]),
                          number(v["methods"]["diagmlp"]["top3"]["mean"]),
                          "/".join(str(v["paired"]["top3"][x]) for x in ("wins", "ties", "losses"))]
                         for g, v in a[field].items()])]
    lines += [
        "## 학습·선택 상태: 18개 이력 전체와 정렬\n",
        "TRAIN/validation/query는 **선택 checkpoint**의 eval-mode 사건 Top1/3/NLL 및 추론 joint loss이다. "
        "반면 online TRAIN joint는 학습모드에서 파라미터가 배치마다 바뀌는 창 가중 평균이다. "
        "joint=0.5 탐지 창 CE + 0.5 장애 창 root CE이며 사건 pooled root NLL과 서로 다른 양이다. "
        "저장 logits로 추론 joint를 float64 재계산해 float32 오차 허용범위 내 대조했다. "
        "JSON에는 detection/root 창 NLL과 가장 큰 장애 창 root NLL도 보존했다.\n",
        table(["R/방법/seed", "부분 (12사건)", "Top1", "Top3", "사건 root NLL", "추론 joint"],
              [["{}/{}/{}".format(r["rotation"], r["kind"], r["seed"]), p] +
               [number(r["selected_checkpoint"][p][m]) for m in ("top1", "top3", "event_nll", "joint_loss")]
               for r in a["learning"] for p in PARTS]),
        "first/selected/final은 실제 epoch 1/선택 epoch/200의 기록이다. "
        "모든 순환은200epoch, 연장없음, budget_bound=false. 선택 업데이트는 선택 epoch까지의 실제 누적치다.\n",
        table(["R/방법/seed", "선택 epoch", "선택/전체 updates", "TRAIN joint 1/선택/200",
               "val joint 1/선택/200", "val 사건 NLL 1/선택/200"],
              [["{}/{}/{}".format(r["rotation"], r["kind"], r["seed"]), r["selected_epoch"],
                "{}/{}".format(r["selected_updates"], r["total_updates"])] +
               ["/".join(number(r[t][m]) for t in ("first", "selected", "final"))
                for m in ("train_online_joint_loss", "validation_joint_loss", "validation_event_nll")]
               for r in a["learning"]]),
        "Eadro는 9실행 중 {}개에서 epoch1이 선택됐다. 최종 TRAIN online joint 범위는 {}, "
        "최종 validation 사건 NLL 범위는 {}다. DiagMLP 선택 epoch 범위는 {}다. "
        "이는 학습 손실 감소와 validation 손실 악화/일반화·선택 불일치를 보여 주지만, "
        "최종 TRAIN 사건 정확도는 저장되지 않았으므로 낮은 online joint에서 정확도를 발명하지 않는다. "
        "선택 TRAIN도 잘 못 맞힌 실행과 TRAIN을 모두 맞힌 실행을 구분해야 한다. "
        "이른 validation 최소는 수렴 증명도 GNN 결함 증명도 아니다. "
        "후반 예산 경계에 걸리지 않았다는 것은 연장 규칙이 작동하지 않았다는 뜻일 뿐, 최적화 완료 보장이 아니다.\n".format(
            sum(r["selected_epoch"] == 1 for r in a["learning"] if r["kind"] == "eadro"),
            "/".join(number(f([r["final"]["train_online_joint_loss"] for r in a["learning"] if r["kind"] == "eadro"]))
                     for f in (min, max)),
            "/".join(number(f([r["final"]["validation_event_nll"] for r in a["learning"] if r["kind"] == "eadro"]))
                     for f in (min, max)),
            "/".join(str(f([r["selected_epoch"] for r in a["learning"] if r["kind"] == "diagmlp"]))
                     for f in (min, max))),
        "## 관측·경계창과 오류 동반 여부\n",
        "원본 인덱스로 SN audit의325 장애 창을 모두 연결했다. "
        "`root_latency_seconds`는 **관측된 1초 bin 수**이며 지연시간의 길이/크기가 아니다. "
        "빈 bin은 관측 부재이며 정상 지연 0이라는 뜻이 아니다. "
        "root_metric_magnitude 및 root≥nonroot 비율은 예전 fold0 QA 기준의 설명값일 뿐 "
        "이번 TRAIN scaler의 anomaly 점수나 현재 모델이 본 값으로 해석할 수 없다. "
        "비원인 후보를 자동으로 피해 서비스라 부르지 않는다.\n",
        "총 root trace 관측 bin {}/{}; trace 부재 창 {}/325. "
        "경계창은 각 window start/end와 fault start/end_inclusive를 대조해 사건별 집계했고 "
        "합계37, 완전 내부288과 대조했다. global37을 사건마다 배분하지 않았다.\n".format(
            a["observability"]["totals"]["root_trace_observed_bins"],
            a["observability"]["totals"]["possible_root_bins"],
            a["observability"]["totals"]["root_trace_missing_windows"]),
        table(["관측/경계 층", "사건", "E Top1", "D Top1", "E Top3", "D Top3", "두방법 모든seed Top1오답"],
              [[g, v["events"]] +
               [number(v["methods"][k][m]["mean"]) for m in ("top1", "top3") for k in KINDS] +
               [v["both_methods_wrong_all_seeds"]] for g, v in a["observability"]["strata"].items()]),
        "관측누락 층과 경계 개수 층은 서로 다른 요약이며 서로 겹친다. 모든36사건을 유지했다. "
        "누락 없는12사건은 모두 CPU이고, 누락 있는24사건은 network 장애라 종류와 완전히 얽혀 있다. "
        "누락이 오답의 필요조건도 충분조건도 아니다: CPU text-service fault00은 누락0인데 두방법 모든seed 오답이고, "
        "nginx network_loss는5/11창이 부재인데 DiagMLP 모든seed 정답이다. "
        "전체 trace 부재 home-timeline network_loss도 DiagMLP seed37이 맞힌다. "
        "경계0인 사건에서도 성공/실패가 모두 있어 경계만으로 실패를 설명할 수 없다. "
        "동반 여부를 관찰했을 뿐 통계검정·사례 제외·원인 확정은 하지 않았다.\n",
        "### 정보와 실패를 네 가지로 구분\n",
        "1. **관측 부재:** 감사의 실제 trace 누락은 존재하지만 metric/log 단서 전체의 부재를 뜻하지 않는다. "
        "관측된 caller/callee는 기록된 관계이지 인과 피해 라벨이 아니다.\n"
        "2. **이전 18특징의 시간정보 손실:** 기존 감사의 reverse/shared/채널별 permutation은 "
        "원시 시계열을 바꾸어도 18요약이394/394창에서 동일(1e-6 이내)했다. "
        "90→18 scalar 개수는 정보량 bit나 인과 효과가 아니다. 이번 native frontend는 "
        "10초 metric/trace sequence와 Hawkes logs를 쓰며 그18특징을 쓰지 않는다. "
        "이번 실패를 그 요약의 시간정보 손실로 귀속할 수 없다.\n"
        "3. **최적화·선택:** 낮아지는 TRAIN online joint와 악화되는 validation NLL, "
        "이른 선택 및 선택 TRAIN 오류는 관찰됐지만 충분한 수렴·부족한 epoch·원인을 확정하지 않는다.\n"
        "4. **후단 구조:** 두 복원본의 격차는 관찰됐으나 GNN의 순수 효과가 아니다. "
        "GLU/fusion, 위치, 그래프 처리, dropout(E0/D0.1)도 다르다. "
        "현 frontend의 정보 충분성이나 어떤 후단 구조의 필연적 결함도 입증하지 못한다.\n",
        "## 단일 후속 가설과 반증 조건\n",
        "**가설:** Eadro의 TRAIN 밖 confidence/loss 폭증에 TRAIN 전용 정규화 범위 밖 입력이 "
        "기여할 수 있다. 근거는 R0/seed23의 선택 TRAIN Top1=1.0/NLL=0.329264인데 "
        "validation Top1=0/NLL=6.875896/joint=1384.170532인 구체적인 실패와, "
        "후반 TRAIN 손실 감소에도 validation NLL이 더 커지는 전체 이력이다. "
        "이는 scaling 원인의 증명이 아니며 단지 우선 검사할 단일 설명이다.\n",
        "**후속 범위는 읽기 전용 진단 하나:** 허용394행과 이미 고정된 TRAIN scaler만으로 "
        "TRAIN/validation/query의 채널별 표준화 극단값과 저장 logits의 큰 창 손실이 "
        "같은 original index에 겹치는지 조사한다. 새 적합·clipping·학습·모델선택을 하지 않는다. "
        "큰 손실이 범위 밖 관측과 동반되지 않으면 이 가설을 버린다. "
        "동반돼도 인과로 부르지 않으며 별도 승인 없이 개선 실험으로 넘어가지 않는다. "
        "이 분석은 해당 표준화 극단값 대조를 수행하지 않았다. 따라서 새 아키텍처·특정 모듈 제안은 **근거 부족**이다.\n",
        "## 36개 짝지은 사건·오류 기록\n",
        "R0–R3는 아래 recording 순서이다. 후보는 service 순서의 번호로 표시하며 바로 아래 사전을 따른다. "
        "예측 표의 seed 순서는11,23,37. `a>b>c`는 순위 그룹, `{a,b}`는 정확한 동률이고 "
        "3위 경계에 걸친 동률도 전부 보존한다. Top1/Top3는 각 사건의3seed credit 평균이다. "
        "JSON에는 실제 서비스명, root rank 구간, seed별 정확 credit/NLL·표본 SD·후보 변동과 "
        "모든 원본 인덱스의 관측·경계 기록이 들어 있다.\n",
        table(["번호", "서비스"], enumerate(a["services"])),
        table(["recording", "ID"], [["R" + str(i), r] for i, r in enumerate(a["by_recording"])]),
    ]
    rec_ids = list(a["by_recording"])

    def prediction(row, kind):
        def one(seed):
            groups = row[kind]["seeds"][str(seed)]["top_rank_groups_through_3"]
            return ">".join(("{" + ",".join(str(a["services"].index(s)) for s in g["services"]) + "}")
                            if len(g["services"]) > 1 else str(a["services"].index(g["services"][0]))
                            for g in groups)
        return "; ".join(one(s) for s in SEEDS)

    lines.append(table(
        ["사건", "root", "종류", "E 후보11;23;37", "D 후보11;23;37", "E Top1/3",
         "D Top1/3", "ΔTop1/3", "trace 부재/창", "관측bin/가능", "경계창"],
        [["R{}:{}".format(rec_ids.index(r["recording"]), r["event_id"].split(":")[-1]),
          r["root"], r["fault_type"], prediction(r, "eadro"), prediction(r, "diagmlp"),
          "/".join(number(r["eadro"][m]) for m in ("top1", "top3")),
          "/".join(number(r["diagmlp"][m]) for m in ("top1", "top3")),
          "/".join(number(r["difference"][m]) for m in ("top1", "top3")),
          "{}/{}".format(r["observability"]["root_trace_missing_windows"], r["observability"]["windows"]),
          "{}/{}".format(r["observability"]["root_trace_observed_bins"], r["observability"]["possible_bins"]),
          r["observability"]["boundary_windows"]] for r in a["paired_events"]]))
    lines += [
        "## 비용·적용 한계\n",
        table(["방법", "9실행 stage wall 합(초)"],
              [[k, number(a["costs"][k]["sum_actual_stage_wall_seconds"])] for k in KINDS]),
        a["cost_conditions"] + "\n",
        "stage receipt의 실제 시간 합이며 입력 준비·독립 검증 전체 비용은 아니다. "
        "서로 겹친 CPU 실행이라 통제된 효율 우위나 순차 총경과시간으로 주장하지 않는다.\n",
        "- 이미 연구자가 검사한36개 개발 사건이다. 새 맹검 최종시험이나 보호169 시험창 성능이 아니다.\n"
        "- 알려진 roots/types의 미학습 조합이며 동일 root×종류의 반복 사건, cold-root, 새 시스템 일반화는 미검증이다.\n"
        "- 같은 recording의 다른 사건이 TRAIN/validation/query에 남는다. 독립 수집환경 평가가 아니다.\n"
        "- 공개 수리 포크/수식 기반 재구성이지 정확한 저자 통합 코드가 아니다. 구조·dropout 차이가 섞여 있다.\n"
        "- 옛95%/창 지표와 이번 사건 단일순위를 직접 차감하지 않는다. 새 방법의 개선 결과가 아니다.\n"
        "- post-hoc 관측 연결은 고정 예측의 설명일 뿐 입력 선택·재튜닝·사례 제외에 쓰지 않았다. "
        "새 모델·두번째 실험·fit·패키지 설치·다운로드·commit·구연구 수정은 없다.\n",
        "## 핵심 provenance SHA-256\n",
        table(["파일", "SHA-256"], [[p, h] for p, h in a["provenance_sha256"].items()
                                  if p in {str(HERE / n) for n in (
                                      "analysis.py", "test_analysis.py", "PLAN.md", "ANALYSIS_PROTOCOL.md",
                                      "VERIFY.json", "VERIFY.md", "inputs.npz", "input_manifest.json",
                                      "selection.lock.json", "budgets.json", "evaluation.json", "scores.py")}
                                  or p == str(AUDIT)]),
    ]
    return "\n".join(lines) + "\n"


def render(a):
    return {"ANALYSIS.json": json.dumps(a, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            "ANALYSIS.md": report_md(a)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-chunk", type=int, help="emit 12000-character base64 gzip patch chunk")
    args = parser.parse_args()
    artifacts = render(analyze())
    if args.emit_chunk is not None:
        require(args.emit_chunk >= 0, "negative chunk")
        patch = "*** Begin Patch\n"
        for name, content in artifacts.items():
            path = HERE / name
            if path.exists():
                # Keep the human-added real execution receipt outside the generated body.
                old = path.read_text().split("\n## 실행 영수증\n")[0]
                if name.endswith(".json"):
                    old = path.read_text()
                patch += "*** Update File: {}\n@@\n".format(path)
                patch += "".join("-" + line + "\n" for line in old.splitlines())
                patch += "".join("+" + line + "\n" for line in content.splitlines())
            else:
                patch += "*** Add File: {}\n".format(path)
                patch += "".join("+" + line + "\n" for line in content.splitlines())
        patch += "*** End Patch\n"
        encoded = base64.b64encode(gzip.compress(patch.encode(), mtime=0)).decode()
        chunks = [encoded[i:i + 12000] for i in range(0, len(encoded), 12000)]
        require(args.emit_chunk < len(chunks), "chunk outside patch")
        print(json.dumps({"index": args.emit_chunk, "total": len(chunks),
                          "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
                          "data": chunks[args.emit_chunk]}))
    else:
        for name, content in artifacts.items():
            actual = (HERE / name).read_text()
            if name.endswith(".md"):
                actual = actual.split("\n## 실행 영수증\n")[0].rstrip("\n")
                content = content.rstrip("\n")
            require(actual == content, "report differs from frozen recomputation: " + name)
        print("ANALYSIS_PASS 36", flush=True)


if __name__ == "__main__":
    main()
