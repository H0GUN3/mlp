"""Preserve timed-out artifacts and finish the already-trained seed37 checkpoint."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

import tt_runner as run


def archive_incomplete(seed):
    assert seed in (11, 23)
    folder = run.HERE / "tt_runs/eadro" / ("seed_" + str(seed))
    config = json.loads((folder / "config.json").read_text())
    assert config["kind"] == "eadro" and config["seed"] == seed
    assert config["sources"] == run.sources()
    assert not (folder / "summary.json").exists()
    assert not (folder / "history.json").exists() and not (folder / "last.pt").exists()
    epochs = sorted(folder.glob("epoch_*.json"))
    assert 0 < len(epochs) < 50
    hashes = {p.name: run.digest(p) for p in folder.iterdir() if p.is_file()}
    target = run.HERE / "interrupted_attempts/eadro" / folder.name
    target.parent.mkdir(parents=True, exist_ok=True)
    assert not target.exists()
    folder.rename(target)
    assert {p.name: run.digest(p) for p in target.iterdir() if p.is_file()} == hashes
    run.dump(target / "INTERRUPTION.json", {
        "reason": "Original monitor timed out; process absent; no optimizer resume state",
        "completed_epochs": len(epochs), "producer_exit": 1,
        "action": "preserved byte-identical artifacts; fresh same-seed retry required",
        "hashes": hashes})
    print("TT_INTERRUPTION_ARCHIVED", seed, len(epochs), flush=True)


def finish37():
    run.setup(37)
    folder = run.HERE / "tt_runs/eadro/seed_37"
    assert not (folder / "summary.json").exists()
    config = json.loads((folder / "config.json").read_text())
    history = json.loads((folder / "history.json").read_text())
    assert config["sources"] == run.sources() and config["inputs"] == run.HASHES
    assert [row["epoch"] for row in history] == list(range(1, 51))
    assert sum(row["updates"] for row in history) == 650
    last = torch.load(folder / "last.pt", map_location="cpu")
    best = torch.load(folder / "best.pt", map_location="cpu")
    assert last["epoch"] == 50
    selected = min(history, key=lambda row: (row["validation_joint_loss"], row["epoch"]))
    assert best["epoch"] == selected["epoch"]
    assert last["validation_joint_loss"] == history[-1]["validation_joint_loss"]
    arrays, meta, parts = run.load_selected()
    stats, data = run.make_data(arrays, parts)
    with np.load(folder / "scaler.npz", allow_pickle=False) as saved:
        for key, value in stats.items():
            np.testing.assert_array_equal(saved[key], value)
    assert run.digest(folder / "scaler.npz") == config["scaler_sha256"]
    # Keep any partial postprocessing outputs; never overwrite their bytes.
    for tag in ("best", "last"):
        for part in parts:
            path = folder / (tag + "_" + part + ".npz")
            if path.exists():
                archived = folder / "interrupted_postprocessing"
                archived.mkdir(exist_ok=True)
                assert not (archived / path.name).exists()
                path.rename(archived / path.name)
    metrics = {}
    for tag, checkpoint in (("best", best), ("last", last)):
        assert checkpoint["config_sha256"] == run.digest(folder / "config.json")
        model = run.NativeReference("eadro", 27, 60)
        model.load_state_dict(checkpoint["model"])
        metrics[tag] = {"epoch": checkpoint["epoch"]}
        for part in parts:
            root, detection, labels, loss = run.validation_predictions(model, data[part], meta, run.BATCH)
            metrics[tag][part] = dict(run.score(root, detection, labels), joint_loss=loss)
            if part == "validation":
                assert loss == checkpoint["validation_joint_loss"]
            with (folder / (tag + "_" + part + ".npz")).open("xb") as stream:
                np.savez(stream, root_logits=root.numpy(), detection_logits=detection.numpy(),
                         labels=labels.numpy(), indices=arrays["indices"][parts[part]],
                         event_ids=arrays["event_ids"][parts[part]])
            replay = run.NativeReference("eadro", 27, 60)
            replay.load_state_dict(checkpoint["model"])
            rr, dd, yy, ll = run.validation_predictions(replay, data[part], meta, run.BATCH)
            assert torch.equal(root, rr) and torch.equal(detection, dd) and torch.equal(labels, yy)
            assert loss == ll
    summary = {"status": "PASS", "kind": "eadro", "seed": 37, "epochs": 50, "updates": 650,
               "best_epoch": best["epoch"], "metrics": metrics,
               "training_validation_seconds": sum(row["seconds"] for row in history),
               "timing_recovery": "sum of recorded epoch durations; excludes checkpoint I/O overhead",
               "checkpoint_replay": "all four predictions bitwise equal",
               "protected_observations_opened": False,
               "recovery": {"original_process_exit": 1, "failure": "monitor timeout after training",
                            "training_repeated": False, "recovery_source": run.digest(Path(__file__))},
               "hashes": {p.name: run.digest(p) for p in folder.iterdir() if p.is_file()}}
    run.dump(folder / "summary.json", summary)
    print("TT_RECOVERED_POSTPROCESS eadro 37 50", flush=True)


if __name__ == "__main__":
    assert __debug__
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("archive", "finish37"))
    parser.add_argument("--seed", type=int, choices=(11, 23))
    args = parser.parse_args()
    if args.action == "archive":
        if args.seed is None:
            parser.error("archive requires --seed")
        archive_incomplete(args.seed)
    else:
        finish37()
