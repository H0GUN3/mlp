#!/usr/bin/env python3
"""Score the frozen SN horizon predictions; this module never fits a model."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
BASELINE = Path("/home/gnho1236/r2/research/native_reproduction_20261013/calibration200/SN/diagmlp")
SEEDS = (11, 23, 37)
OUT = ROOT / "analysis_v2"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tied_topk_credit(row, label, k):
    """Expected correct membership under uniform random ordering of exact ties."""
    greater = int(np.sum(row > row[label]))
    tied = int(np.sum(row == row[label]))
    return float(min(1.0, max(0.0, (k - greater) / tied)))


def detection_scores(logits):
    # Detection class 1 is fault; class 0 is normal, with exact ties fractional.
    diff = logits[:, 1] - logits[:, 0]
    pred_fault = diff > 0
    tie = diff == 0
    return pred_fault, tie


def validate_order(indices_a, labels_a, indices_b, labels_b):
    require(np.array_equal(indices_a, indices_b), "validation index order mismatch")
    require(np.array_equal(labels_a, labels_b), "validation label order mismatch")


def metrics(root_logits, detection_logits, labels):
    fault = labels >= 0
    normal = ~fault
    require(int(fault.sum()) == 65 and int(normal.sum()) == 13, "expected 65 faults and 13 normals")
    pred_fault, det_tie = detection_scores(detection_logits)
    tp = float(np.sum(pred_fault & fault) + .5 * np.sum(det_tie & fault))
    fp = float(np.sum(pred_fault & normal) + .5 * np.sum(det_tie & normal))
    fn = int(fault.sum()) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / int(fault.sum())
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    root_credit = np.asarray([tied_topk_credit(root_logits[i], int(labels[i]), 1)
                              for i in np.flatnonzero(fault)])
    root3 = np.asarray([tied_topk_credit(root_logits[i], int(labels[i]), 3)
                        for i in np.flatnonzero(fault)])
    gated = root_credit * pred_fault[fault] + root_credit * .5 * det_tie[fault]
    gated3 = root3 * pred_fault[fault] + root3 * .5 * det_tie[fault]
    return {
        "windows": 78, "fault_denominator": 65, "normal_denominator": 13,
        "conditional_top1": float(root_credit.mean()),
        "conditional_top3": float(root3.mean()),
        "gated_top1": float(gated.mean()), "gated_top3": float(gated3.mean()),
        "detection_precision": precision, "detection_recall": recall,
        "detection_f1": f1, "tp": tp, "fp": fp, "fn": fn,
        "tn": float(normal.sum()) - fp,
        "root_nll_fault_only": float(np.mean([
            np.logaddexp.reduce(root_logits[i].astype(np.float64)) -
            root_logits[i, int(labels[i])] for i in np.flatnonzero(fault)])),
    }


def load_prediction(path):
    with np.load(str(path), allow_pickle=False) as z:
        require(set(z.files) == {"indices", "root_logits", "detection_logits", "labels"},
                "unexpected prediction archive members: " + str(path))
        return {k: np.array(z[k], copy=True) for k in z.files}


def checked_arm(path, summary_path, expected_hash):
    require(path.is_file() and summary_path.is_file(), "missing allowed prediction or summary: " + str(path))
    observed = sha(path)
    require(observed == expected_hash,
            "prediction SHA-256 mismatch {} expected={} observed={}".format(path, expected_hash, observed))
    d = load_prediction(path)
    require(d["indices"].shape == (78,) and d["labels"].shape == (78,), "expected 78 indices and labels")
    require(d["root_logits"].shape == (78, 12) and d["detection_logits"].shape == (78, 2),
            "unexpected prediction tensor shape")
    require(np.isfinite(d["root_logits"]).all() and np.isfinite(d["detection_logits"]).all(),
            "nonfinite predictions")
    require(int(np.sum(d["labels"] >= 0)) == 65 and int(np.sum(d["labels"] == -1)) == 13,
            "expected 65 fault labels and 13 normal labels")
    return d


def write_csv(path, rows):
    if not rows:
        return
    with open(str(path), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run():
    metadata = json.loads((ROOT / "inputs/metadata.json").read_text())
    prep = json.loads((ROOT / "inputs/preparation.json").read_text())
    windows = metadata["windows"]
    original_indices = metadata["original_indices"]
    require(len(windows) == len(original_indices), "metadata windows/original_indices length mismatch")
    absolute, relative, histories, configs, summaries = {}, {}, {}, {}, {}
    input_audit = []
    expected_common = None
    for seed in SEEDS:
        ap = ROOT / "runs" / ("absolute_seed_{}".format(seed))
        rp = BASELINE / ("seed_{}".format(seed))
        ac = json.loads((ap / "config.json").read_text())
        rc = json.loads((rp / "config.json").read_text())
        asum = json.loads((ap / "summary.json").read_text())
        rsum = json.loads((rp / "summary.json").read_text())
        require(ac["seed"] == seed and ac["horizon"] == "absolute", "absolute config identity mismatch")
        require(rc.get("effective_options", {}).get("seed") == seed,
                "relative config effective_options.seed mismatch")
        require(rc.get("effective_options", {}).get("epochs") == 200 and
                rc.get("effective_options", {}).get("batch_size") == 256,
                "relative config training budget mismatch")
        for label, cfg, summary, directory in (
                ("absolute", ac, asum, ap),
                ("relative", rc, json.loads((rp / "summary.json").read_text()), rp)):
            hashes = summary.get("artifact_hashes", {})
            for name in ("config.json", "history.json", "validation_predictions.npz"):
                actual = sha(directory / name)
                require(actual == hashes.get(name), "{} seed {} {} hash mismatch expected={} observed={}".format(
                    label, seed, name, hashes.get(name), actual))
        common = {k: ac.get(k) for k in ("seed", "kind", "effective_epochs", "batch_size", "lr", "optimizer", "model", "services", "edges")}
        require(common["seed"] == seed, "seed mismatch")
        if expected_common is None:
            expected_common = {k: v for k, v in common.items() if k != "seed"}
        else:
            require({k: v for k, v in common.items() if k != "seed"} == expected_common,
                    "absolute common settings differ across seeds")
        absolute[seed] = checked_arm(ap / "validation_predictions.npz", ap / "summary.json",
                                     asum["artifact_hashes"]["validation_predictions.npz"])
        relative[seed] = checked_arm(rp / "validation_predictions.npz", rp / "summary.json",
                                     rsum["artifact_hashes"]["validation_predictions.npz"])
        for arm, directory, summary in (("before_absolute", ap, asum), ("after_relative", rp, rsum)):
            prediction = directory / "validation_predictions.npz"
            input_audit.append({"seed": seed, "arm": arm, "path": str(prediction),
                "expected_sha256": summary["artifact_hashes"]["validation_predictions.npz"],
                "observed_sha256": sha(prediction), "matched": True})
        validate_order(absolute[seed]["indices"], absolute[seed]["labels"],
                       relative[seed]["indices"], relative[seed]["labels"])
        histories[seed] = (json.loads((ap / "history.json").read_text()),
                           json.loads((rp / "history.json").read_text()))
        configs[seed] = (ac, rc)
        summaries[seed] = (asum, rsum)
    reference = absolute[SEEDS[0]]
    for seed in SEEDS:
        require(np.array_equal(reference["indices"], absolute[seed]["indices"]) and
                np.array_equal(reference["labels"], absolute[seed]["labels"]),
                "cross-seed validation order/labels differ")
    # Original indices address metadata.windows directly.
    idx = reference["indices"].astype(int)
    metadata_rows = {int(original): pos for pos, original in enumerate(original_indices)}
    require(all(int(i) in metadata_rows for i in idx), "validation index absent from metadata")
    val_positions = [int(x) for x in metadata["validation_positions"]]
    require(len(val_positions) == 78 and
            np.array_equal(np.asarray(original_indices)[val_positions], idx),
            "prediction indices do not match metadata validation order")
    results, cases = {}, []
    changed = {name: [] for name in ("root_new_correct", "root_new_wrong",
                                      "root_improved", "root_degraded",
                                      "joint_new_correct", "joint_new_wrong",
                                      "joint_improved", "joint_degraded")}
    normal_changes = []
    for seed in SEEDS:
        a, r = absolute[seed], relative[seed]
        ma, mr = metrics(a["root_logits"], a["detection_logits"], a["labels"]), metrics(
            r["root_logits"], r["detection_logits"], r["labels"])
        results[str(seed)] = {"before_absolute": ma, "after_relative": mr,
                              "delta_relative_minus_absolute": {
                                  k: mr[k] - ma[k] for k in ma if isinstance(ma[k], (int, float))}}
        for pos, original in enumerate(idx):
            label = int(a["labels"][pos])
            meta = windows[metadata_rows[int(original)]]
            if label < 0:
                ad = float(a["detection_logits"][pos, 1] > a["detection_logits"][pos, 0]) + .5 * float(
                    a["detection_logits"][pos, 1] == a["detection_logits"][pos, 0])
                rd = float(r["detection_logits"][pos, 1] > r["detection_logits"][pos, 0]) + .5 * float(
                    r["detection_logits"][pos, 1] == r["detection_logits"][pos, 0])
                if ad != rd:
                    normal_changes.append({"seed": seed, "original_index": int(original),
                        "event_id": meta["event_id"], "start": meta["start"],
                        "before_false_positive_credit": ad, "after_false_positive_credit": rd,
                        "change": "degraded" if rd > ad else "improved"})
                continue
            ac = tied_topk_credit(a["root_logits"][pos], label, 1)
            rc = tied_topk_credit(r["root_logits"][pos], label, 1)
            ad = float(a["detection_logits"][pos, 1] > a["detection_logits"][pos, 0]) + .5 * float(
                a["detection_logits"][pos, 1] == a["detection_logits"][pos, 0])
            rd = float(r["detection_logits"][pos, 1] > r["detection_logits"][pos, 0]) + .5 * float(
                r["detection_logits"][pos, 1] == r["detection_logits"][pos, 0])
            j0, j1 = ac * ad, rc * rd
            row = {"seed": seed, "validation_position": pos, "original_index": int(original),
                   "event_id": meta["event_id"], "start": meta["start"],
                   "root_fault_group": meta["root_fault_group"],
                   "true_root_label": label, "true_root_name": configs[seed][0]["services"][label],
                   "before_root_top1_credit": ac, "after_root_top1_credit": rc,
                   "before_detection_credit": ad, "after_detection_credit": rd,
                   "before_joint_credit": j0, "after_joint_credit": j1,
                   "joint_change": ("improved" if j1 > j0 else "degraded" if j1 < j0 else "unchanged"),
                   "root_top1_change": ("improved" if rc > ac else "degraded" if rc < ac else "unchanged"),
                   "before_root_top3_credit": tied_topk_credit(a["root_logits"][pos], label, 3),
                   "after_root_top3_credit": tied_topk_credit(r["root_logits"][pos], label, 3)}
            cases.append(row)
            for metric, before, after in (("root", ac, rc), ("joint", j0, j1)):
                if after > before:
                    changed[metric + "_improved"].append(row)
                elif after < before:
                    changed[metric + "_degraded"].append(row)
                if before < 1 and after == 1:
                    changed[metric + "_new_correct"].append(row)
                elif before == 1 and after < 1:
                    changed[metric + "_new_wrong"].append(row)
    OUT.mkdir(exist_ok=True)
    (OUT / "input_audit.json").write_text(json.dumps(input_audit, indent=2, sort_keys=True) + "\n")
    (OUT / "scores.json").write_text(json.dumps({"direction": "after_relative - before_absolute",
        "seeds": results, "seed_mean": {key: {m: float(np.mean([results[str(s)][key][m] for s in SEEDS]))
          for m in results[str(SEEDS[0])][key]} for key in ("before_absolute", "after_relative")},
        "settings": expected_common, "scope_note": "SN validation only; no ensemble; ties are fractional."},
        indent=2, sort_keys=True) + "\n")
    write_csv(OUT / "paired_fault_windows.csv", cases)
    for name, rows in changed.items():
        write_csv(OUT / (name + ".csv"), rows)
    write_csv(OUT / "normal_detection_changes.csv", normal_changes)
    def distinct(rows, key):
        return len(set(row[key] for row in rows))
    root_combos, joint_combos = {}, {}
    for row in cases:
        for metric, before, after, target in (
                ("root", row["before_root_top1_credit"], row["after_root_top1_credit"], root_combos),
                ("joint", row["before_joint_credit"], row["after_joint_credit"], joint_combos)):
            key = "both_correct" if before == after == 1 else "both_wrong" if before == after == 0 else (
                "new_correct" if before < 1 and after == 1 else "new_wrong" if before == 1 and after < 1 else "fractional")
            target[key] = target.get(key, 0) + 1
    require(sum(root_combos.values()) == 195 and sum(joint_combos.values()) == 195,
            "paired root/joint partitions do not sum to 195")
    partition = lambda metric: {
        "records": sum(1 for row in cases),
        "counts": root_combos if metric == "conditional_root_top1" else joint_combos,
        "new_correct_records": len(changed[metric_prefix[metric] + "_new_correct"]),
        "new_wrong_records": len(changed[metric_prefix[metric] + "_new_wrong"]),
        "improved_records": len(changed[metric_prefix[metric] + "_improved"]),
        "degraded_records": len(changed[metric_prefix[metric] + "_degraded"]),
        "improved_distinct_windows": distinct(changed[metric_prefix[metric] + "_improved"], "original_index"),
        "improved_distinct_events": distinct(changed[metric_prefix[metric] + "_improved"], "event_id"),
        "improved_seed_records": len(changed[metric_prefix[metric] + "_improved"]),
        "degraded_distinct_windows": distinct(changed[metric_prefix[metric] + "_degraded"], "original_index"),
        "degraded_distinct_events": distinct(changed[metric_prefix[metric] + "_degraded"], "event_id"),
        "degraded_seed_records": len(changed[metric_prefix[metric] + "_degraded"]),
    }
    metric_prefix = {"conditional_root_top1": "root", "gated_joint_top1": "joint"}
    (OUT / "paired_summary.json").write_text(json.dumps({
       "records": len(cases), "primary_metric": "conditional_root_top1",
       "conditional_root_partition": partition("conditional_root_top1"),
       "gated_joint_partition": partition("gated_joint_top1"),
       "normal_detection_changes": len(normal_changes),
       "independent_unit_warning": "195 window-seed records are not independent events."},
       indent=2, sort_keys=True) + "\n")
    input_report = prep["input_difference"]
    (OUT / "input_difference.json").write_text(json.dumps(input_report, indent=2, sort_keys=True) + "\n")
    settings = [{"seed": s, "arm": arm, "config_sha256": sha(ROOT / ("runs/absolute_seed_{}/config.json".format(s) if arm == "before_absolute" else "../native_reproduction_20261013/calibration200/SN/diagmlp/seed_{}/config.json".format(s))),
                 "horizon": "absolute" if arm == "before_absolute" else "relative",
                 "epochs": cfg.get("effective_epochs", cfg.get("effective_options", {}).get("epochs")),
                 "batch_size": cfg.get("batch_size", cfg.get("effective_options", {}).get("batch_size")),
                 "lr": cfg.get("lr", cfg.get("effective_options", {}).get("lr")),
                 "optimizer": cfg.get("optimizer", cfg.get("effective_options", {}).get("optimizer", {}).get("name")),
                 "model": cfg.get("model"), "services": cfg.get("services")}
                for s in SEEDS for arm, cfg in zip(("before_absolute", "after_relative"), configs[s])]
    write_csv(OUT / "settings.csv", settings)
    hist_rows = []
    for s in SEEDS:
        for arm, hist in zip(("before_absolute", "after_relative"), histories[s]):
            summary = summaries[s][0 if arm == "before_absolute" else 1]
            best = min(hist, key=lambda x: x["validation_joint_loss"])
            require(best["epoch"] == summary["best_epoch"] and
                    best["validation_joint_loss"] == summary["best_validation_joint_loss"],
                    "{} seed {} selected history/summary mismatch".format(arm, s))
            for epoch in (1, 50, 200):
                item = next((x for x in hist if x["epoch"] == epoch), None)
                if item is not None:
                    hist_rows.append({"seed": s, "arm": arm, "epoch": epoch,
                        "selected_epoch": summary["best_epoch"],
                        "train_batch_weighted_joint_loss": item["train_batch_weighted_joint_loss"],
                        "validation_joint_loss": item["validation_joint_loss"],
                        "validation_scores": json.dumps(item.get("validation_scores", {}), sort_keys=True)})
            hist_rows.append({"seed": s, "arm": arm, "epoch": "selected",
                "selected_epoch": summary["best_epoch"],
                "train_batch_weighted_joint_loss": best["train_batch_weighted_joint_loss"],
                "validation_joint_loss": best["validation_joint_loss"],
                "validation_scores": json.dumps(best.get("validation_scores", {}), sort_keys=True)})
    write_csv(OUT / "history_metrics.csv", hist_rows)
    print("ANALYSIS_PASS seeds=3 archives=6 fault_window_seed_records=195 root_partition={} joint_partition={}".format(
        sum(root_combos.values()), sum(joint_combos.values())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="run synthetic scoring assertions only")
    args = parser.parse_args()
    if args.self_check:
        from test_analyze_horizon import self_check
        self_check()
        print("SELF_CHECK_PASS")
        return 0
    try:
        run()
    except Exception as exc:
        print("ANALYSIS_FAIL: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
