"""Independent NumPy scoring and receipt verification for the six TT baselines."""
import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from tt_runner import HERE, HASHES, KINDS, SEEDS, digest, dump, sources


def independent_scores(roots, detects, labels):
    roots = np.asarray(roots, dtype=np.float64)
    detects = np.asarray(detects, dtype=np.float64)
    labels = np.asarray(labels)
    assert roots.ndim == detects.ndim == 2
    assert roots.shape[0] == detects.shape[0] == len(labels) and detects.shape[1] == 2
    assert np.isfinite(roots).all() and np.isfinite(detects).all()
    faulty = labels >= 0
    predicted = detects.argmax(axis=1) == 1
    counts = {"tp": int((faulty & predicted).sum()),
              "fp": int((~faulty & predicted).sum()),
              "fn": int((faulty & ~predicted).sum()),
              "tn": int((~faulty & ~predicted).sum())}
    results: Dict[str, Optional[float]] = dict(
        counts, windows=len(labels), fault_windows=int(faulty.sum()))
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    results["precision"] = tp / (tp + fp) if tp + fp else 0.
    results["recall"] = tp / (tp + fn) if tp + fn else 0.
    results["f1"] = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.
    loss = []
    for k in (1, 3, 5):
        credits, gated = [], []
        for i in np.flatnonzero(faulty):
            row = roots[i]
            assert 0 <= labels[i] < len(row)
            above = sum(value > row[labels[i]] for value in row)
            tied = sum(value == row[labels[i]] for value in row)
            credit = max(0, min(k - above, tied)) / tied
            credits.append(credit)
            gated.append(credit if predicted[i] else 0.)
            if k == 1:
                shifted = row - row.max()
                loss.append(float(np.log(np.exp(shifted).sum()) - shifted[labels[i]]))
        results["conditional_top" + str(k)] = float(np.mean(credits)) if credits else None
        results["end_to_end_top" + str(k)] = float(np.mean(gated)) if gated else None
    results["root_window_nll"] = float(np.mean(loss)) if loss else None
    return results


def main():
    assert __debug__
    fixture = independent_scores(np.zeros((3, 27)),
                                 [[0, 1], [1, 0], [1, 0]], [0, 1, -1])
    assert fixture["conditional_top3"] == 3 / 27
    assert fixture["end_to_end_top1"] == 1 / 54
    assert fixture["fault_windows"] == 2 and fixture["tn"] == 1
    all_runs, paired = [], {}
    for kind in KINDS:
        for seed in SEEDS:
            folder = HERE / "tt_runs" / kind / ("seed_" + str(seed))
            config = json.loads((folder / "config.json").read_text())
            summary = json.loads((folder / "summary.json").read_text())
            history = json.loads((folder / "history.json").read_text())
            assert config["sources"] == sources() and config["inputs"] == HASHES
            assert config["kind"] == summary["kind"] == kind
            assert config["seed"] == summary["seed"] == seed
            assert summary["status"] == "PASS" and summary["epochs"] == len(history) == 50
            assert summary["updates"] == sum(r["updates"] for r in history) == 650
            assert [r["epoch"] for r in history] == list(range(1, 51))
            for name, expected in summary["hashes"].items():
                assert digest(folder / name) == expected
            assert digest(folder / "scaler.npz") == config["scaler_sha256"]
            best = min(history, key=lambda r: (r["validation_joint_loss"], r["epoch"]))
            assert best["epoch"] == summary["best_epoch"]
            assert best["epoch"] == summary["metrics"]["best"]["epoch"]
            assert summary["checkpoint_replay"] == "all four predictions bitwise equal"
            assert not summary["protected_observations_opened"]
            interrupted = HERE / "interrupted_attempts" / kind / folder.name
            if interrupted.exists():
                assert digest(interrupted / "config.json") == digest(folder / "config.json")
                for epoch_file in sorted(interrupted.glob("epoch_*.json")):
                    previous = json.loads(epoch_file.read_text())
                    current = history[previous["epoch"] - 1]
                    assert {k: v for k, v in previous.items() if k != "seconds"} == {
                        k: v for k, v in current.items() if k != "seconds"}
            key = str(seed)
            if key in paired:
                assert paired[key] == config["common_initial"]
            paired[key] = config["common_initial"]
            for tag in ("best", "last"):
                for part in ("train", "validation"):
                    with np.load(folder / (tag + "_" + part + ".npz"),
                                 allow_pickle=False) as saved:
                        np.testing.assert_array_equal(saved["indices"], config["original_indices"][part])
                        assert len(set(saved["indices"])) == len(saved["indices"])
                        assert np.all(saved["event_ids"][saved["labels"] < 0] == "")
                        metrics = independent_scores(saved["root_logits"], saved["detection_logits"],
                                                     saved["labels"])
                    actual = summary["metrics"][tag][part]
                    for metric, expected in metrics.items():
                        if expected is None:
                            assert actual[metric] is None
                        else:
                            assert np.isclose(actual[metric], expected, rtol=1e-12, atol=1e-12), metric
            assert not set(config["original_indices"]["train"]) & set(config["original_indices"]["validation"])
            all_runs.append({"kind": kind, "seed": seed, "best_epoch": summary["best_epoch"],
                             "first_train_loss": history[0]["train_joint_loss"],
                             "last_train_loss": history[-1]["train_joint_loss"],
                             "first_validation_loss": history[0]["validation_joint_loss"],
                             "last_validation_loss": history[-1]["validation_joint_loss"],
                             "seconds": summary["training_validation_seconds"],
                             "metrics": summary["metrics"],
                             "summary_sha256": digest(folder / "summary.json")})
    result = {"status": "PASS", "runs": all_runs, "predictions_independently_scored": 24,
              "protected_observations_opened": False, "sources": sources(),
              "interrupted_attempts": "original configs and completed epoch prefixes exactly reproduced",
              "verifier_sha256": digest(Path(__file__))}
    dump(HERE / "TT_RESULTS.json", result)
    for kind in KINDS:
        rows = [r for r in all_runs if r["kind"] == kind]
        print("TT_RESULT", kind, json.dumps({
            "selected_epochs": [r["best_epoch"] for r in rows],
            "validation_conditional_top1": [r["metrics"]["best"]["validation"]["conditional_top1"] for r in rows],
            "validation_conditional_top3": [r["metrics"]["best"]["validation"]["conditional_top3"] for r in rows],
            "train_conditional_top1": [r["metrics"]["best"]["train"]["conditional_top1"] for r in rows]}))
    print("TT_VERIFIED 6 24", flush=True)


if __name__ == "__main__":
    main()
