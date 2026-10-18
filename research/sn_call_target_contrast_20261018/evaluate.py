"""Independent NumPy scoring of both frozen budgets; no model imports."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
SEEDS = (11, 23, 37)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lp(logits):
    shifted = logits.astype(np.float64) - logits.max(axis=1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))


def credits(logits, labels, k):
    correct = logits[np.arange(len(labels)), labels, None]
    greater = (logits > correct).sum(axis=1)
    tied = (logits == correct).sum(axis=1)
    return np.minimum(np.maximum(k - greater, 0), tied) / tied


def metrics(pred):
    labels = pred["labels"]
    faulty = labels >= 0
    root = pred["root_logits"]
    det = pred["detection_logits"]
    detected = det.argmax(axis=1).astype(bool)
    top1 = credits(root[faulty], labels[faulty], 1)
    top3 = credits(root[faulty], labels[faulty], 3)
    root_nll = -lp(root)[np.flatnonzero(faulty), labels[faulty]]
    det_nll = -lp(det)[np.arange(len(labels)), faulty.astype(int)]
    tp, fp, fn, tn = (int(np.sum(detected & faulty)), int(np.sum(detected & ~faulty)),
                      int(np.sum(~detected & faulty)), int(np.sum(~detected & ~faulty)))
    return {
        "fault_windows": int(faulty.sum()), "normal_windows": int((~faulty).sum()),
        "top1": float(top1.mean()), "top3": float(top3.mean()),
        "gated_top1": float(np.mean(top1 * detected[faulty])),
        "gated_top3": float(np.mean(top3 * detected[faulty])),
        "root_nll": float(root_nll.mean()), "detection_nll": float(det_nll.mean()),
        "joint_loss": float(.5 * root_nll.mean() + .5 * det_nll.mean()),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "detection_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
    }


def transition(before, after):
    if before == after == 1:
        return "both_correct"
    if before == after == 0:
        return "both_wrong"
    if before == 0 and after == 1:
        return "new_correct"
    if before == 1 and after == 0:
        return "new_wrong"
    return "partial_credit_change"


def analyze():
    hashes = {}

    def document(path):
        hashes[str(path)] = digest(path)
        return json.loads(path.read_text())

    def archive(path):
        hashes[str(path)] = digest(path)
        with np.load(path, allow_pickle=False) as data:
            return {k: data[k] for k in data.files}

    baseline = document(HERE / "BASELINE.json")
    for run in baseline["runs"]:
        for path, expected in run["hashes"].items():
            assert digest(path) == expected
    prep = document(HERE / "inputs/preparation.json")
    meta = document(HERE / "inputs/metadata.json")
    assert prep["status"] == "PASS"
    assert digest(HERE / "inputs/metadata.json") == prep["output_hashes"]["metadata.json"]
    windows = dict(zip(meta["original_indices"], meta["windows"]))
    seed_scores, paired, timing = [], [], []
    for seed in SEEDS:
        folder = HERE / "runs" / ("seed_%d" % seed)
        summary, config, history = [document(folder / (n + ".json"))
                                    for n in ("summary", "config", "history")]
        assert summary["status"] == "PASS" and summary["epochs_completed"] == 200
        assert len(history) == 200 and sum(r["optimizer_updates"] for r in history) == 400
        log_path = folder / "epochs.jsonl"
        hashes[str(log_path)] = digest(log_path)
        assert [json.loads(line) for line in log_path.read_text().splitlines()] == history
        for name, expected in summary["artifact_hashes"].items():
            assert digest(folder / name) == expected, name
        for path, expected in config["source_hashes"].items():
            assert digest(path) == expected, path
        timing.append({
            "seed": seed, "candidate50_seconds": summary["training_validation_seconds50"],
            "candidate200_seconds": summary["training_validation_seconds200"],
            "replay_seconds": summary["replay_seconds"], "total_seconds": summary["total_seconds"],
            "started_at": config["started_at_unix"], "finished_at": summary["finished_at_unix"],
            "baseline50_seconds": next(r["training_validation_seconds"] for r in baseline["runs"]
                                       if r["seed"] == seed and r["budget"] == 50),
            "baseline200_seconds": next(r["training_validation_seconds"] for r in baseline["runs"]
                                        if r["seed"] == seed and r["budget"] == 200),
        })
        for budget in (50, 200):
            old_folder = NATIVE / ("calibration%d/SN/diagmlp/seed_%d" % (budget, seed))
            old = archive(old_folder / "validation_predictions.npz")
            new = archive(folder / ("predictions_%d.npz" % budget))
            old_summary = document(old_folder / "summary.json")
            for key in ("indices", "labels"):
                np.testing.assert_array_equal(old[key], new[key])
            np.testing.assert_array_equal(new["indices"], config["validation_original_indices"])
            old_metrics, new_metrics = metrics(old), metrics(new)
            selected = summary["selected"][str(budget)]
            best = min(history[:budget], key=lambda r: r["validation_joint_loss"])
            assert selected["selected_epoch"] == best["epoch"]
            assert selected["selected_updates"] == 2 * best["epoch"]
            assert new_metrics["fault_windows"] == 65 and new_metrics["normal_windows"] == 13
            np.testing.assert_allclose(new_metrics["joint_loss"], selected["joint_loss"],
                                       rtol=1e-6, atol=1e-7)
            assert new_metrics["top1"] == selected["scores"]["conditional_top1"]
            assert new_metrics["gated_top1"] == selected["scores"]["end_to_end_top1"]
            np.testing.assert_allclose(old_metrics["joint_loss"], old_summary["best_validation_joint_loss"],
                                       rtol=1e-6, atol=1e-7)
            seed_scores.append({
                "budget": budget, "seed": seed, "baseline": old_metrics, "candidate": new_metrics,
                "baseline_selected_epoch": old_summary["best_epoch"],
                "candidate_selected_epoch": best["epoch"],
            })
            faulty = new["labels"] >= 0
            old1 = credits(old["root_logits"][faulty], old["labels"][faulty], 1)
            new1 = credits(new["root_logits"][faulty], new["labels"][faulty], 1)
            old3 = credits(old["root_logits"][faulty], old["labels"][faulty], 3)
            new3 = credits(new["root_logits"][faulty], new["labels"][faulty], 3)
            for j, pos in enumerate(np.flatnonzero(faulty)):
                index = int(new["indices"][pos])
                window = windows[index]
                paired.append({
                    "budget": budget, "seed": seed, "index": index,
                    "event": window["event_id"], "recording": window["run_id"],
                    "fault_type": window["root_fault_group"].split("|")[1],
                    "root": int(new["labels"][pos]),
                    "baseline_prediction": int(old["root_logits"][pos].argmax()),
                    "candidate_prediction": int(new["root_logits"][pos].argmax()),
                    "baseline_top1": float(old1[j]), "candidate_top1": float(new1[j]),
                    "baseline_top3": float(old3[j]), "candidate_top3": float(new3[j]),
                    "transition": transition(old1[j], new1[j]),
                })
    aggregates, event_rows = {}, []
    for budget in (50, 200):
        rows = [r for r in paired if r["budget"] == budget]
        assert len(rows) == 195 and len({r["index"] for r in rows}) == 65
        assert len({r["event"] for r in rows}) == 28
        by_type = {}
        for typ in ("all", "cpu_load", "network_delay", "network_loss"):
            subset = [r for r in rows if typ == "all" or r["fault_type"] == typ]
            by_type[typ] = {
                "seed_window_evaluations": len(subset),
                "unique_windows": len({r["index"] for r in subset}),
                "unique_events": len({r["event"] for r in subset}),
                "baseline_top1": float(np.mean([r["baseline_top1"] for r in subset])),
                "candidate_top1": float(np.mean([r["candidate_top1"] for r in subset])),
                "baseline_top3": float(np.mean([r["baseline_top3"] for r in subset])),
                "candidate_top3": float(np.mean([r["candidate_top3"] for r in subset])),
            }
        transitions = {}
        for name in ("both_correct", "both_wrong", "new_correct", "new_wrong", "partial_credit_change"):
            subset = [r for r in rows if r["transition"] == name]
            transitions[name] = {
                "seed_window_evaluations": len(subset),
                "unique_windows": len({r["index"] for r in subset}),
                "unique_events": len({r["event"] for r in subset}),
                "unique_recordings": len({r["recording"] for r in subset}),
                "types": dict(Counter(r["fault_type"] for r in subset)),
            }
        events = defaultdict(list)
        for row in rows:
            events[row["event"]].append(row)
        for event, subset in sorted(events.items()):
            assert {r["seed"] for r in subset} == set(SEEDS)
            per_seed = [{
                "seed": seed, "baseline": float(np.mean([r["baseline_top1"] for r in subset if r["seed"] == seed])),
                "candidate": float(np.mean([r["candidate_top1"] for r in subset if r["seed"] == seed])),
            } for seed in SEEDS]
            event_rows.append({
                "budget": budget, "event": event, "recording": subset[0]["recording"],
                "fault_type": subset[0]["fault_type"],
                "windows": len({r["index"] for r in subset}), "per_seed_window_hit_means": per_seed,
                "delta_top1": float(np.mean([r["candidate"] - r["baseline"] for r in per_seed])),
            })
        differences = [r["delta_top1"] for r in event_rows if r["budget"] == budget]
        aggregates[str(budget)] = {
            "by_type": by_type, "transitions": transitions,
            "event_window_hit_mean_win_tie_loss": {
                "win": sum(d > 0 for d in differences), "tie": sum(d == 0 for d in differences),
                "loss": sum(d < 0 for d in differences)},
        }
    for path, expected in hashes.items():
        assert digest(path) == expected
    return {
        "status": "PASS", "scope": "SN fixed-window development contrast; no independent final test",
        "seed_scores": seed_scores, "aggregates": aggregates, "paired": paired,
        "event_window_hit_means": event_rows, "timing": timing, "preparation_cost": prep["cost"],
        "concurrent_candidate_wall_seconds": max(t["finished_at"] for t in timing) - min(t["started_at"] for t in timing),
        "source_sha256": hashes,
    }


if __name__ == "__main__":
    result = analyze()
    expected = json.loads((HERE / "RESULTS.json").read_text())
    assert result == expected
    print("CALL_TARGET_EVALUATION_PASS", len(result["paired"]), flush=True)
