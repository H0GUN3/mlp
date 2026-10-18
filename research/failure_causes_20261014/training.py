"""Lane B: fixed-checkpoint diagnostics, with no fitting or raw-data loaders."""
from __future__ import annotations

from collections import defaultdict
import json
from math import ceil
from pathlib import Path
import platform
import sys

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "method_mlp_20261013"))
from research.relationship_diagnosis_20261014 import errors
from research.method_mlp_20261013 import features, train
from research.relationship_smoke_20261013.relation_model import RelationRanker

METRICS = errors.METRICS + ("ce",)
STAT_MEMBERS = (
    "reference_median", "reference_scale", "reference_count", "reference_mask",
    "standardizer_mean", "standardizer_std", "standardizer_counts",
    "train_indices", "normal_train_indices", "validation_indices",
)
SETTINGS = {"epochs": 5, "patience": 5, "batch_size": 32,
            "learning_rate": 1e-3, "weight_decay": 1e-4, "threads": 2}


def window_scores(logits, labels):
    scores, _, target_ties, maximum_ties = errors.ranking(logits, labels)
    shifted = logits.astype(np.float64) - logits.max(axis=1, keepdims=True)
    scores["ce"] = np.log(np.exp(shifted).sum(axis=1)) - shifted[np.arange(len(labels)), labels]
    errors.require(np.isfinite(scores["ce"]).all(), "Nonfinite inference CE")
    return scores, target_ties, maximum_ties


def collapse_evaluations(rows):
    """Windows already averaged; folds/seeds averaged inside each event."""
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        identity = (row["event_id"], row["fold"], row["seed"])
        errors.require(identity not in identities, "Duplicate event evaluation")
        identities.add(identity)
        errors.require(row["window_count"] > 0
                       and all(np.isfinite(row["metrics"][m]) for m in METRICS),
                       "Invalid event evaluation")
        groups[row["event_id"]].append(row)
    result = {}
    for event, evaluations in sorted(groups.items()):
        counts = {r["window_count"] for r in evaluations}
        errors.require(len(counts) == 1, "Event window coverage differs between evaluations")
        result[event] = {
            "unique_windows": evaluations[0]["window_count"],
            "evaluation_count": len(evaluations),
            "metrics": {m: float(np.mean([r["metrics"][m] for r in evaluations])) for m in METRICS},
            "evaluations": evaluations,
        }
    return result


def group_mean(events):
    errors.require(bool(events), "Empty incident group")
    return {
        "independent_event_count": len(events),
        "unique_windows": sum(e["unique_windows"] for e in events),
        "metrics": {m: float(np.mean([e["metrics"][m] for e in events])) for m in METRICS},
        "zero_top1_events": sum(e["metrics"]["top1"] == 0 for e in events),
        "perfect_top1_events": sum(e["metrics"]["top1"] == 1 for e in events),
    }


def history_summary(rows):
    keys = ("epoch1_ce", "epoch4_ce", "epoch5_ce", "delta_1_to_5", "delta_4_to_5",
            "fractional_drop_1_to_5", "fractional_drop_4_to_5")
    return {
        "run_count": len(rows),
        "decreasing_1_to_5": sum(r["delta_1_to_5"] < 0 for r in rows),
        "decreasing_4_to_5": sum(r["delta_4_to_5"] < 0 for r in rows),
        "statistics": {k: {"mean": float(np.mean([r[k] for r in rows])),
                            "min": float(min(r[k] for r in rows)),
                            "max": float(max(r[k] for r in rows))} for k in keys},
        "total_optimizer_steps": sorted({r["optimizer_steps"] for r in rows}),
    }


def support_records(bundle, manifest, fold):
    faults = bundle["labels"] >= 0
    result = []
    for service in sorted({f["service"] for f in manifest["faults"].values()}):
        by_split = {}
        for split in ("train", "validation"):
            selected = (bundle["fold_ids"] != fold if split == "train"
                        else bundle["fold_ids"] == fold) & faults
            event_ids = sorted({str(e) for e in bundle["event_ids"][selected]
                                if manifest["faults"][str(e)]["service"] == service})
            types = sorted({manifest["faults"][e]["fault_type"] for e in event_ids})
            by_split[split] = {
                fault_type: {
                    "event_ids": [e for e in event_ids if manifest["faults"][e]["fault_type"] == fault_type],
                    "events": sum(manifest["faults"][e]["fault_type"] == fault_type for e in event_ids),
                    "windows": int(sum(np.count_nonzero(bundle["event_ids"] == e) for e in event_ids
                                       if manifest["faults"][e]["fault_type"] == fault_type)),
                } for fault_type in types
            }
        train_types, val_types = set(by_split["train"]), set(by_split["validation"])
        errors.require(len(train_types) == 2 and len(val_types) == 1 and not train_types & val_types,
                       "Expected root-specific two-type TRAIN / one-type validation")
        result.append({"fold": fold, "service": service, "support": by_split})
    return result


def build_diagnostic():
    inputs = errors.Inputs()
    runs = inputs.json(errors.CV / "runs.json", errors.SNAPSHOT_HASHES["runs.json"], "frozen snapshot")
    analysis = inputs.json(errors.CV / "analysis.json", errors.SNAPSHOT_HASHES["analysis.json"],
                           "immutable prior analysis snapshot")
    errors.require(runs["status"] == "PASS" and runs["run_count"] == 54
                   and analysis["input_hashes"]["runs.json"] == errors.SNAPSHOT_HASHES["runs.json"],
                   "Invalid completed CV provenance")
    reports = errors.validate_reports(runs["reports"])
    for path, digest in runs["source_hashes"].items():
        errors.require(ROOT / "research" in Path(path).resolve().parents,
                       "Unexpected source path")
        inputs.record(path, digest, "runs.json/source_hashes; source bytes only", ())
    helper_file = errors.__file__
    if helper_file is None:
        raise RuntimeError("Missing diagnostic helper source")
    helper_path = Path(helper_file).resolve()
    inputs.record(helper_path, errors.file_hash(helper_path), "diagnostic helper snapshot at start", ())
    software = {str(HERE / name): errors.file_hash(HERE / name)
                for name in ("training.py", "test_training.py")}
    evaluations = defaultdict(list)
    histories, replays, supports, coverage = [], [], {}, {}
    per_run_event_checks = 0
    for system in errors.SYSTEMS:
        manifest_path = errors.BUNDLES / (system + ".json")
        manifest = inputs.json(manifest_path, runs["input_hashes"][str(manifest_path)],
                               "runs.json/input_hashes")
        bundle_path = errors.BUNDLES / (system + ".npz")
        errors.require(manifest["npz_sha256"] == runs["input_hashes"][str(bundle_path)],
                       "Manifest/bundle binding mismatch")
        bundle = inputs.npz(bundle_path, manifest["npz_sha256"], "runs.json/input_hashes",
                            ("values",) + errors.BUNDLE_MEMBERS)
        errors.validate_bundle(bundle, manifest, system)
        errors.require(manifest["faults"] == runs["systems"][system]["faults"],
                       "Fault metadata differs from saved CV")
        faults = bundle["labels"] >= 0
        errors.require(len(manifest["faults"]) == (36 if system == "SN" else 81),
                       "Unexpected independent incident count")
        coverage[system] = {
            "events": len(manifest["faults"]), "fault_windows": int(faults.sum()),
            "normal_windows": int((~faults).sum()), "services": len(manifest["services"]),
        }
        supports[system] = []
        for fold in errors.FOLDS:
            stats_path = errors.CV / system / ("fold_" + str(fold)) / "statistics.npz"
            stats = inputs.npz(stats_path, runs["artifact_hashes"][str(stats_path.relative_to(errors.CV))],
                               "runs.json/artifact_hashes", STAT_MEMBERS)
            partition = bundle["fold_ids"] == fold
            for name, mask in (("train_indices", ~partition),
                               ("normal_train_indices", ~partition & ~faults),
                               ("validation_indices", partition)):
                errors.require(np.array_equal(stats[name], bundle["indices"][mask]),
                               "Saved statistics partition mismatch: " + name)
            reference = {k: stats["reference_" + k] for k in ("median", "scale", "count", "mask")}
            standardizer = {k: stats["standardizer_" + k] for k in ("mean", "std", "counts")}
            errors.require(np.all(reference["scale"] > 0) and np.all(standardizer["std"] > 0),
                           "Invalid saved scales")
            x, mask, coverage_array = features.window_features(bundle["values"], bundle["observed"], reference)
            tensors = (torch.from_numpy(train.transform(x, mask, standardizer)),
                       torch.from_numpy(mask), torch.from_numpy(coverage_array),
                       torch.from_numpy(bundle["adjacency"]))
            train_rows = np.flatnonzero(~partition & faults)
            val_rows = np.flatnonzero(partition & faults)
            train_tensor_rows = torch.as_tensor(train_rows, dtype=torch.long)
            val_tensor_rows = torch.as_tensor(val_rows, dtype=torch.long)
            fold_report = runs["systems"][system]["folds"][fold]
            errors.require(len(train_rows) == fold_report["train_fault_windows"]
                           and len(val_rows) == fold_report["validation_fault_windows"],
                           "Exact training/validation window count mismatch")
            supports[system].extend(support_records(bundle, manifest, fold))
            for seed in errors.SEEDS:
                for mode in errors.MODES:
                    identity = {"system": system, "fold": fold, "seed": seed, "mode": mode}
                    report = reports[system, fold, seed, mode]
                    folder = stats_path.parent / ("seed_" + str(seed)) / mode

                    def artifact_hash(name):
                        digest = runs["artifact_hashes"][str((folder / name).relative_to(errors.CV))]
                        errors.require(digest == report["artifact_hashes"][name],
                                       "Run artifact hash binding mismatch")
                        return digest

                    config = inputs.json(folder / "config.json", artifact_hash("config.json"),
                                         "runs.json and report/artifact_hashes")
                    expected_inputs = {str(p): runs["input_hashes"][str(p)]
                                       for p in (manifest_path, bundle_path)}
                    expected_config = dict(identity, settings=SETTINGS, checkpoint_policy="fixed_final_epoch_5",
                                           source_hashes=runs["source_hashes"], input_hashes=expected_inputs,
                                           parameter_count=3361,
                                           train_indices=bundle["indices"][train_rows].tolist(),
                                           validation_indices=bundle["indices"][val_rows].tolist())
                    errors.require(config == expected_config, "Run config differs from fixed contract")
                    history = inputs.json(folder / "history.json", artifact_hash("history.json"),
                                          "runs.json and report/artifact_hashes")
                    errors.require(len(history) == 5 and [r["epoch"] for r in history] == list(range(1, 6))
                                   and report["epochs_run"] == 5
                                   and all(np.isfinite(r["train_event_ce"]) and r["train_event_ce"] > 0
                                           for r in history), "Invalid five-epoch history")
                    first, fourth, fifth = (float(history[i]["train_event_ce"]) for i in (0, 3, 4))
                    steps = ceil(len(train_rows) / config["settings"]["batch_size"])
                    histories.append(dict(identity, training_fault_windows=len(train_rows),
                                          training_events=len(set(bundle["event_ids"][train_rows])),
                                          batch_size=32, steps_per_epoch=steps, optimizer_steps=5 * steps,
                                          history=history, epoch1_ce=first, epoch4_ce=fourth, epoch5_ce=fifth,
                                          delta_1_to_5=fifth - first, delta_4_to_5=fifth - fourth,
                                          fractional_drop_1_to_5=(first - fifth) / first,
                                          fractional_drop_4_to_5=(fourth - fifth) / fourth))
                    saved = inputs.npz(folder / "predictions.npz", artifact_hash("predictions.npz"),
                                       "runs.json and report/artifact_hashes", errors.PREDICTION_MEMBERS)
                    errors.require(np.array_equal(errors.validate_prediction(saved, bundle, fold), val_rows),
                                   "Validation row ordering differs")
                    checkpoint_path = folder / "checkpoint.pt"
                    inputs.record(checkpoint_path, artifact_hash("checkpoint.pt"),
                                  "runs.json and report/artifact_hashes", ("state_dict", "config_sha256"))
                    checkpoint = torch.load(checkpoint_path, map_location="cpu")
                    errors.check_hash(checkpoint_path, artifact_hash("checkpoint.pt"))
                    errors.require(checkpoint["config_sha256"] == artifact_hash("config.json"),
                                   "Checkpoint/config mismatch")
                    model = RelationRanker(18, mode)
                    model.load_state_dict(checkpoint["state_dict"], strict=True)
                    model.eval()
                    with torch.no_grad():
                        # Same whole validation batch as cv.predict; exact equality, no tolerance fallback.
                        val_logits = model(*(t[val_tensor_rows] for t in tensors)).numpy()
                        errors.require(np.array_equal(val_logits, saved["logits"]),
                                       "STOP: fixed checkpoint validation logits are not exact")
                        train_logits = model(*(t[train_tensor_rows] for t in tensors)).numpy()
                    tie_counts = {}
                    for split, rows, logits in (("train", train_rows, train_logits),
                                                ("validation", val_rows, val_logits)):
                        scores, target_ties, maximum_ties = window_scores(logits, bundle["labels"][rows])
                        tie_counts[split] = {"target_tie_windows": target_ties,
                                             "maximum_tie_windows": maximum_ties}
                        event_ids = bundle["event_ids"][rows]
                        per_event = {}
                        for event in sorted(set(event_ids)):
                            selected = event_ids == event
                            metric = {m: float(v[selected].mean()) for m, v in scores.items()}
                            evaluations[system, mode, split].append({
                                "event_id": str(event), "fold": fold, "seed": seed,
                                "window_count": int(selected.sum()), "metrics": metric,
                            })
                            per_event[str(event)] = metric
                            if split == "validation":
                                errors.compare(metric, report["metrics"]["by_incident"][str(event)],
                                               str((system, fold, seed, mode, event)))
                                per_run_event_checks += 1
                        if split == "validation":
                            errors.require(set(per_event) == set(report["metrics"]["by_incident"])
                                           and report["metrics"]["target_score_tie_windows"] == target_ties,
                                           "Saved validation event coverage/ties differ")
                            errors.compare({m: float(np.mean([r[m] for r in per_event.values()]))
                                            for m in errors.METRICS}, report["metrics"]["event_balanced"],
                                           "run event-balanced")
                    replays.append(dict(identity, exact_logits=True,
                                        validation_batch_shape=list(val_logits.shape),
                                        train_batch_shape=list(train_logits.shape), ties=tie_counts))
                    print("TRAINING_REPLAY_OK", system, fold, seed, mode, flush=True)
        inputs.recheck()
    events, summaries = {}, {}
    summary_checks = 0
    for system in errors.SYSTEMS:
        manifest_path = errors.BUNDLES / (system + ".json")
        manifest = inputs.json(manifest_path, runs["input_hashes"][str(manifest_path)], "runs.json/input_hashes")
        events[system], summaries[system] = {}, {}
        for mode in errors.MODES:
            events[system][mode], summaries[system][mode] = {}, {}
            for split in ("train", "validation"):
                collapsed = collapse_evaluations(evaluations[system, mode, split])
                errors.require(set(collapsed) == set(manifest["faults"]), "Missing independent event coverage")
                for event, entry in collapsed.items():
                    expected_folds = (set(errors.FOLDS) - {manifest["event_folds"][event]}
                                      if split == "train" else {manifest["event_folds"][event]})
                    expected_pairs = {(f, s) for f in expected_folds for s in errors.SEEDS}
                    errors.require({(r["fold"], r["seed"]) for r in entry["evaluations"]} == expected_pairs
                                   and entry["evaluation_count"] == (6 if split == "train" else 3),
                                   "Missing fold/seed event evaluation")
                    entry["fault"] = manifest["faults"][event]
                    if split == "validation":
                        errors.compare(entry["metrics"],
                                       analysis["summary"]["systems"][system]["modes"][mode]["by_incident"][event],
                                       "prior analysis event")
                        summary_checks += 1
                events[system][mode][split] = collapsed
                fault_types = sorted({f["fault_type"] for f in manifest["faults"].values()})
                grouped = {
                    "all": group_mean(list(collapsed.values())),
                    "fault_type": {fault: group_mean([e for e in collapsed.values()
                                                      if e["fault"]["fault_type"] == fault])
                                   for fault in fault_types},
                    "network": group_mean([e for e in collapsed.values()
                                           if e["fault"]["fault_type"].startswith("network")]),
                }
                summaries[system][mode][split] = grouped
                if split == "validation":
                    errors.compare(grouped["all"]["metrics"],
                                   analysis["summary"]["systems"][system]["modes"][mode]["aggregate"],
                                   "prior analysis aggregate")
            summaries[system][mode]["validation_minus_train"] = {
                group: {m: summaries[system][mode]["validation"][group]["metrics"][m]
                        - summaries[system][mode]["train"][group]["metrics"][m] for m in METRICS}
                for group in ("all", "network")
            }
    errors.require(len(replays) == len(histories) == 54 and per_run_event_checks == 1053
                   and summary_checks == 351, "Incomplete replay/reconciliation")
    inputs.recheck()
    for path, digest in software.items():
        errors.check_hash(path, digest)
    return {
        "status": "PASS", "run_count": 54, "replays": replays,
        "reconciliation": {"exact_validation_replays": len(replays), "run_event_checks": per_run_event_checks,
                           "prior_analysis_event_checks": summary_checks, "hashes_unchanged": True},
        "coverage": coverage, "support": supports, "histories": histories,
        "history_summary": {system: {mode: history_summary([r for r in histories
                                                           if r["system"] == system and r["mode"] == mode])
                                     for mode in errors.MODES} for system in errors.SYSTEMS},
        "events": events, "summary": summaries, "input_hashes": inputs.provenance,
        "software_hashes": software,
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "torch": torch.__version__, "threads": torch.get_num_threads(), "device": "cpu"},
        "method": {
            "aggregation": "Windows within event/evaluation; seeds and TRAIN's two folds within event; independent events equally.",
            "steps": "Exact loop-implied count: ceil(saved TRAIN fault windows / batch_size) * saved epochs; no optimizer counter saved.",
            "history_ce": "Event-weighted online CE while parameters change within each epoch, not final fixed-checkpoint CE.",
            "inference_ce": "Stable float64 logsumexp of unchanged final float32 logits; unweighted windows inside each incident.",
            "reference": "Saved statistics.npz reference and standardizer; pure window_features and transform, never fit.",
            "ties": "Uniform rank credit over exact score ties, including expected reciprocal rank.",
            "replay": "Whole validation batch, pinned environment, np.array_equal; any discrepancy aborts without output.",
        },
        "limitations": [
            "Development incidents only; TRAIN appears twice across CV folds but is counted once independently.",
            "Each root has two fault types in TRAIN, its third in validation; not unseen-root evaluation.",
            "TRAIN and validation use different models/support for the same incidents; not a paired same-model generalization gap.",
            "Shared recordings and overlapping CV TRAIN sets limit statistical independence; no confidence/p-value claims.",
            "Small update count and falling online CE suggest possible incomplete optimization, not demonstrated underfitting cause.",
            "Final TRAIN errors cannot separate optimization, representation, missing information, or label/measurement issues.",
            "No new model, epoch choice, fitting, backward, optimizer, perturbation, native loader or held-out observation access.",
        ],
    }


def main():
    output = HERE / "training.json"
    if output.exists():
        raise FileExistsError("Refusing to overwrite diagnostic: " + str(output))
    if (sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5"
            or torch.__version__ != "1.12.1+cpu"):
        raise RuntimeError("Use pinned .venv-eadro Python3.8 / NumPy1.21.5 / torch1.12.1+cpu")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    result = build_diagnostic()
    errors.write_result(output, result)
    print("TRAINING_COMPLETE 54 EXACT_REPLAYS HASHES_UNCHANGED", flush=True)


if __name__ == "__main__":
    main()
