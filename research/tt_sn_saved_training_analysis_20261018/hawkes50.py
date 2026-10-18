"""Compare saved JSON histories only; never open inputs or checkpoints."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
NATIVE = RESEARCH / "native_reproduction_20261013"
HORIZON = RESEARCH / "sn_hawkes_horizon_contrast_20261017"
FIELDS = ("epoch", "optimizer_updates", "train_batch_weighted_joint_loss",
          "validation_joint_loss", "validation_scores")


def earliest_best(rows):
    return min(rows, key=lambda row: row["validation_joint_loss"])


def point(row):
    return {
        "epoch": row["epoch"],
        "train_online_joint_loss": row["train_batch_weighted_joint_loss"],
        "validation_joint_loss": row["validation_joint_loss"],
        "conditional_top1": row["validation_scores"]["conditional_top1"],
        "gated_top1": row["validation_scores"]["end_to_end_top1"],
    }


def analyze():
    hashes = {}

    def load(folder, name):
        if name not in {"history.json", "summary.json", "config.json"}:
            raise ValueError("Only saved training JSON records are permitted")
        path = folder / name
        content = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(content).hexdigest()
        return json.loads(content)

    def run(folder, epochs, expected_status="passed"):
        summary = load(folder, "summary.json")
        history = load(folder, "history.json")
        config = load(folder, "config.json")
        assert summary["status"] == expected_status and not summary["test_evaluated"]
        for name in ("history.json", "config.json"):
            assert hashes[str(folder / name)] == summary["artifact_hashes"][name]
        assert len(history) == epochs
        assert [r["epoch"] for r in history] == list(range(1, epochs + 1))
        assert sum(r["optimizer_updates"] for r in history) == summary["optimizer_updates"]
        assert earliest_best(history)["epoch"] == summary["best_epoch"]
        return history, config

    records = []
    for seed in (11, 23, 37):
        relative, relative_config = run(
            NATIVE / "calibration200/SN/diagmlp" / ("seed_" + str(seed)), 200)
        short, short_config = run(
            NATIVE / "calibration50/SN/diagmlp" / ("seed_" + str(seed)), 50)
        absolute, _ = run(HORIZON / "runs" / ("absolute_seed_" + str(seed)), 200, "PASS")
        assert relative_config["input_hashes"] == short_config["input_hashes"]
        assert relative_config["artifact_hashes"] == short_config["artifact_hashes"]
        assert all({k: a[k] for k in FIELDS} == {k: b[k] for k in FIELDS}
                   for a, b in zip(relative[:50], short))
        record = {"seed": seed, "relative_sn50_prefix_exact": True}
        for arm, history in (("absolute_before", absolute), ("relative_after", relative)):
            first = history[:50]
            selected = earliest_best(first)
            record[arm] = {
                "milestones": [point(history[e - 1]) for e in (1, 10, 25, 50)],
                "selected_within_first50": point(selected),
                "updates_first50_recorded": sum(r["optimizer_updates"] for r in first),
                "updates_to_first50_selected_recorded": sum(
                    r["optimizer_updates"] for r in first[:selected["epoch"]]),
                "selected_within_full200_context_only": point(earliest_best(history)),
                "first50_history": [point(row) for row in first],
                "train_accuracy_history_present": any(
                    "train_scores" in r or "train_accuracy" in r for r in first),
            }
        record["first50_differing_validation_loss_epochs"] = sum(
            a["validation_joint_loss"] != b["validation_joint_loss"]
            for a, b in zip(absolute[:50], relative[:50]))
        record["first50_differing_top1_epochs"] = sum(
            a["validation_scores"]["conditional_top1"] !=
            b["validation_scores"]["conditional_top1"]
            for a, b in zip(absolute[:50], relative[:50]))
        record["selected50_delta_relative_minus_absolute"] = (
            record["relative_after"]["selected_within_first50"]["conditional_top1"] -
            record["absolute_before"]["selected_within_first50"]["conditional_top1"])
        records.append(record)
    for path, expected in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    return {
        "status": "PASS_SAVED_HISTORY_ONLY",
        "direction": "relative_after minus absolute_before",
        "horizons": {"absolute_before": "window_start + 10", "relative_after": 10},
        "records": records,
        "mean_selected50_top1": {
            arm: sum(r[arm]["selected_within_first50"]["conditional_top1"]
                     for r in records) / len(records)
            for arm in ("absolute_before", "relative_after")
        },
        "input_hashes": hashes,
        "new_fits": 0,
        "new_inference": 0,
        "feature_arrays_opened": 0,
        "checkpoint_files_opened": 0,
        "limitations": [
            "Absolute first50 selected predictions are not established by these histories.",
            "Full200 selected predictions cannot substitute for first50 predictions.",
            "TRAIN online loss is not a saved fixed-checkpoint TRAIN accuracy.",
            "Seeds and correlated validation windows are not independent incidents.",
        ],
    }


if __name__ == "__main__":
    assert earliest_best([
        {"epoch": 1, "validation_joint_loss": 1.0},
        {"epoch": 2, "validation_joint_loss": 1.0}])["epoch"] == 1
    result = analyze()
    result["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with (HERE / "HAWKES50.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print("HAWKES50_HISTORY_PASS", result["mean_selected50_top1"], flush=True)
