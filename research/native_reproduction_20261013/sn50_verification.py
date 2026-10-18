#!/usr/bin/env python3
"""Independent integrity and validation-score check for the six SN50 runs."""
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE / "calibration50" / "SN"
SEEDS = (11, 23, 37)
KINDS = ("eadro", "diagmlp")
HASHED = ("scaler.npz", "validation_predictions.npz", "history.json",
          "config.json", "split.json", "checkpoint.pt")
EXPECTED_COUNTS = {"train": 316, "validation": 78, "test": 169, "unassigned": 1}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def independently_score(root_logits, detection_logits, labels):
    """Neutral expected credit for exact root-score ties; binary fault F1."""
    faulty = labels >= 0
    predicted_fault = np.argmax(detection_logits, axis=1) == 1
    tp = int(np.count_nonzero(predicted_fault & faulty))
    fp = int(np.count_nonzero(predicted_fault & ~faulty))
    fn = int(np.count_nonzero(~predicted_fault & faulty))
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    if not faulty.any():
        return {"conditional_top1": None, "end_to_end_top1": None, "f1": f1}
    expected_hits = []
    for row, truth in zip(root_logits[faulty], labels[faulty]):
        true_score = row[int(truth)]
        above = np.count_nonzero(row > true_score)
        tied = np.count_nonzero(row == true_score)
        expected_hits.append(1.0 / tied if above == 0 else 0.0)
    conditional = float(np.mean(expected_hits))
    gated = float(np.mean(np.asarray(expected_hits) * predicted_fault[faulty]))
    return {"conditional_top1": conditional, "end_to_end_top1": gated, "f1": f1}


def close_exact(actual, expected):
    # JSON and NumPy use binary float values; do not round before comparing.
    return actual == expected


def check_run(kind, seed, failures, runs, common):
    directory = ROOT / kind / f"seed_{seed}"
    run = {"kind": kind, "seed": seed, "path": str(directory.relative_to(HERE)),
           "checks": [], "score_recomputations": []}
    runs.append(run)

    def require(condition, label, detail=None):
        item = {"check": label, "passed": bool(condition)}
        if detail is not None:
            item["detail"] = detail
        run["checks"].append(item)
        if not condition:
            failures.append(f"{kind}/seed_{seed}: {label}" +
                            (f" ({detail})" if detail is not None else ""))

    try:
        summary = json.loads((directory / "summary.json").read_text())
        config = json.loads((directory / "config.json").read_text())
        history = json.loads((directory / "history.json").read_text())
        split = json.loads((directory / "split.json").read_text())
    except Exception as error:
        failures.append(f"{kind}/seed_{seed}: unable to read required JSON: {error}")
        return run

    require(summary.get("status") == "passed", "summary status passed", summary.get("status"))
    require(summary.get("epochs_completed") == 50 and config.get("effective_epochs") == 50,
            "exactly 50 epochs", [summary.get("epochs_completed"), config.get("effective_epochs")])
    require(summary.get("test_evaluated") is False and config.get("test_evaluated") is False,
            "test_evaluated false", [summary.get("test_evaluated"), config.get("test_evaluated")])
    require(summary.get("checkpoint_replay") ==
            "bitwise equal validation logits, labels, indices and loss",
            "bitwise checkpoint replay evidence", summary.get("checkpoint_replay"))
    actual_hashes = {name: sha256(directory / name) for name in HASHED
                     if (directory / name).is_file()}
    expected_hashes = summary.get("artifact_hashes", {})
    for name in HASHED:
        require(name in actual_hashes, f"{name} exists")
        require(expected_hashes.get(name) == actual_hashes.get(name),
                f"{name} SHA256 matches summary",
                {"summary": expected_hashes.get(name), "actual": actual_hashes.get(name)})

    counts = split.get("counts")
    require(counts == EXPECTED_COUNTS, "train/validation/test/unassigned counts", counts)
    require(config.get("services") is not None and len(config["services"]) == 12,
            "12-service inventory present", config.get("services"))
    if config.get("services") is not None:
        services = config["services"]
        require(len(set(services)) == 12, "service inventory has 12 unique entries")
        fingerprint = json.dumps(services, separators=(",", ":"))
        if common.get("services") is None:
            common["services"] = fingerprint
        require(common["services"] == fingerprint, "candidate/service order identical across runs")
    hashes = config.get("input_hashes")
    require(isinstance(hashes, dict) and set(hashes) == {"raw.npz", "metadata.json"},
            "input hashes present", hashes)
    split_hash = actual_hashes.get("split.json")
    scaler_hash = actual_hashes.get("scaler.npz")
    current = {"input_hashes": hashes, "split_hash": split_hash, "scaler_hash": scaler_hash}
    if common.get("manifest") is None:
        common["manifest"] = current
    require(current == common["manifest"], "input, split and scaler hashes identical",
            current)
    require(config.get("artifact_hashes", {}).get("split.json") == split_hash and
            config.get("artifact_hashes", {}).get("scaler.npz") == scaler_hash,
            "config split/scaler hashes match files")

    best_epoch = summary.get("best_epoch")
    run["best_epoch"] = best_epoch
    if isinstance(best_epoch, int):
        run["late_epoch_trigger"] = best_epoch >= 45
    require(len(history) == 50 and all(row.get("epoch") == i for i, row in enumerate(history, 1)),
            "50 sequential history epochs", len(history))
    if not isinstance(best_epoch, int) or not 1 <= best_epoch <= len(history):
        require(False, "best epoch exists in history", best_epoch)
        return run
    selected = history[best_epoch - 1]
    run["train_loss"] = selected.get("train_batch_weighted_joint_loss")
    run["validation_loss"] = selected.get("validation_joint_loss")
    require(selected.get("validation_joint_loss") == summary.get("best_validation_joint_loss"),
            "selected validation loss matches summary")
    if not all(row.get("validation_joint_loss", float("inf")) >=
               selected.get("validation_joint_loss", float("-inf")) for row in history):
        require(False, "selected epoch is minimum validation joint loss")
    else:
        require(True, "selected epoch is minimum validation joint loss")

    try:
        with np.load(directory / "validation_predictions.npz", allow_pickle=False) as saved:
            indices = saved["indices"]
            roots = saved["root_logits"]
            detects = saved["detection_logits"]
            labels = saved["labels"]
        scores = independently_score(roots, detects, labels)
        run["fault_windows"] = int(np.count_nonzero(labels >= 0))
        for metric, value in scores.items():
            recorded = selected.get("validation_scores", {}).get(metric)
            passed = close_exact(recorded, value)
            detail = {"history": recorded, "independent": value}
            run["score_recomputations"].append({"metric": metric, **detail, "passed": passed})
            require(passed, f"independent {metric} exactly matches selected history", detail)
        require(len(indices) == 78 and roots.shape == (78, 12) and
                detects.shape == (78, 2) and labels.shape == (78,),
                "saved validation prediction dimensions",
                [indices.shape, roots.shape, detects.shape, labels.shape])
        require(np.array_equal(indices, np.asarray(split["indices"]["validation"])),
                "prediction validation indices match split")
    except Exception as error:
        failures.append(f"{kind}/seed_{seed}: validation prediction check failed: {error}")

    run["parameters"] = summary.get("parameters")
    run["checkpoint_sha256"] = actual_hashes.get("checkpoint.pt")
    return run


def main():
    failures, runs, common = [], [], {}
    for kind in KINDS:
        for seed in SEEDS:
            check_run(kind, seed, failures, runs, common)
    groups = {}
    for kind in KINDS:
        selected = [run for run in runs if run["kind"] == kind and
                    isinstance(run.get("validation_loss"), (int, float))]
        groups[kind] = {}
        for field in ("conditional_top1", "end_to_end_top1", "f1",
                      "train_loss", "validation_loss", "parameters"):
            values = []
            for run in selected:
                if field in ("train_loss", "validation_loss", "parameters"):
                    value = run.get(field)
                else:
                    score = next((s for s in run["score_recomputations"]
                                  if s["metric"] == field), None)
                    value = score["independent"] if score else None
                if isinstance(value, (int, float)):
                    values.append(value)
            groups[kind][field] = {
                "per_seed": values,
                "mean": float(np.mean(values)) if values else None,
                "range": [min(values), max(values)] if values else None,
            }
        groups[kind]["best_epochs"] = [run.get("best_epoch") for run in selected]
        groups[kind]["parameter_count"] = [run.get("parameters") for run in selected]
    late = [run for run in runs if run.get("late_epoch_trigger")]
    result = {
        "status": "PASS" if not failures else "FAIL",
        "system": "SN",
        "runs_expected": 6,
        "runs_checked": len(runs),
        "fault_windows_per_validation_run": [run.get("fault_windows") for run in runs],
        "fault_windows_are_correlated_windows_not_independent_incidents": True,
        "corrected_calibration_is_not_exact_original_score": True,
        "original_score_comparison": (
            "These corrected conditional/gated fault-only Top1 and positive-class detection F1 "
            "are not asserted equal to the source evaluator's HR@1/F1; exact original "
            "DiagMLP experiment scoring is unavailable."),
        "kind_summaries": groups,
        "late_epoch_diagnostic": {
            "condition": "any seed best_epoch >= 45",
            "triggered": bool(late),
            "triggering_runs": [f"{r['kind']}/seed_{r['seed']} (epoch {r.get('best_epoch')})"
                                for r in late],
            "required_followup": "separate 200-epoch diagnostic for both methods and all three seeds"
                                if late else None,
            "executed": False,
        },
        "common_manifest": common.get("manifest"),
        "failures": failures,
        "runs": runs,
    }
    (HERE / "sn50_verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    write_summary(result)
    print("SN50_VERIFIED" if result["status"] == "PASS" else "SN50_FAILED")
    print(json.dumps({"status": result["status"], "failures": failures,
                      "late_epoch_diagnostic": result["late_epoch_diagnostic"]}, allow_nan=False))
    return 0 if result["status"] == "PASS" else 1


def fmt(stat):
    if stat["mean"] is None:
        return "n/a"
    lo, hi = stat["range"]
    return f"{stat['mean']:.6g} [{lo:.6g}, {hi:.6g}]"


def write_summary(result):
    lines = ["# SN50 native calibration verification", "",
             f"**Verification: {result['status']}** — checked {result['runs_checked']}/6 runs.",
             "Validation scores below were recomputed directly from saved logits and labels "
             "using NumPy, including neutral expected credit for exact root-score ties.", "",
             f"Validation fault windows per run: {result['fault_windows_per_validation_run']}. "
             "These are correlated windows, not independent incidents; the three seeds are "
             "not three incident replications.", "",
             "| Kind | Conditional Top1 mean [range] | Gated Top1 mean [range] | Detection F1 mean [range] | "
             "Best epochs | Train loss mean [range] | Validation loss mean [range] | Parameters |",
             "|---|---:|---:|---:|---|---:|---:|---:|"]
    for kind in KINDS:
        summary = result["kind_summaries"][kind]
        lines.append("| " + " | ".join([
            kind, fmt(summary["conditional_top1"]), fmt(summary["end_to_end_top1"]),
            fmt(summary["f1"]), ", ".join(map(str, summary["best_epochs"])),
            fmt(summary["train_loss"]), fmt(summary["validation_loss"]),
            ", ".join(map(str, summary["parameter_count"]))]) + " |")
    gate = result["late_epoch_diagnostic"]
    lines += ["", f"Predeclared ≥45 best-epoch trigger: **{'TRIGGERED' if gate['triggered'] else 'not triggered'}**."
              + (f" Runs: {', '.join(gate['triggering_runs'])}." if gate["triggered"] else ""),
              "No 200-epoch diagnostic was run. " +
              ("Protocol calls for a separate 200-epoch diagnostic of both methods × three seeds."
               if gate["triggered"] else "The frozen protocol does not call for that diagnostic."),
              "", "This is corrected native calibration, not exact reproduction of original paper "
              "scores. The historical source evaluator used different HR@1/F1 denominators, and "
              "the exact original DiagMLP experiment implementation is unavailable. No test "
              "partition was evaluated.", ""]
    if result["failures"]:
        lines += ["## Failed checks", ""] + [f"- {failure}" for failure in result["failures"]] + [""]
    text = "\n".join(lines)
    (HERE / "sn50_summary.md").write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
