"""One frozen SN destination-only contrast; retain selected50 and selected200."""
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time

os.environ.setdefault("DGLBACKEND", "pytorch")
import dgl
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
SAFE = HERE.parent / "sn_hawkes_horizon_contrast_20261017/inputs"
sys.path.insert(0, str(NATIVE))
models = importlib.import_module("native_models")
native = importlib.import_module("native_train")
SEEDS = (11, 23, 37)


def digest(path):
    return native.file_hash(Path(path))


def document(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def archive(path):
    with np.load(path, allow_pickle=False) as saved:
        return {k: saved[k] for k in saved.files}


def baseline_check():
    manifest = document(HERE / "BASELINE.json")
    for run in manifest["runs"]:
        for path, expected in run["hashes"].items():
            assert digest(path) == expected, path
    return manifest


def frozen_sources():
    paths = [HERE / n for n in ("PROTOCOL.md", "BASELINE.json", "runner.py", "test_runner.py",
                               "prepare.py", "test_prepare.py", "pyrightconfig.json",
                               "inputs/preparation.json", "inputs/metadata.json",
                               "inputs/mapping.json", "inputs/selected.npz")]
    paths += [NATIVE / "native_models.py", NATIVE / "native_train.py", models.SOURCE]
    return {str(p): digest(p) for p in paths}


def setup(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)


def state_hash(model):
    result = hashlib.sha256()
    for key, value in sorted(model.state_dict().items()):
        result.update(key.encode())
        result.update(value.detach().cpu().numpy().tobytes())
    return result.hexdigest()


def validate_arrays(candidate, original):
    assert set(candidate) == {"metrics", "traces", "logs", "labels", "indices"}
    shapes = {"metrics": (394, 12, 10, 7), "traces": (394, 12, 10, 2),
              "logs": (394, 12, 7), "labels": (394,), "indices": (394,)}
    for key, shape in shapes.items():
        assert candidate[key].shape == shape and np.isfinite(candidate[key]).all(), key
        if key != "traces":
            np.testing.assert_array_equal(candidate[key], original[key])
    assert candidate["indices"].dtype == np.int64 and candidate["labels"].dtype == np.int64
    assert np.all(candidate["traces"][..., 1] == 0)
    assert np.all(candidate["traces"][..., 0] >= 0)
    assert np.any(candidate["traces"][..., 0] != original["traces"][..., 0])


def load():
    baseline_check()
    prep = document(HERE / "inputs/preparation.json")
    assert prep["status"] == "PASS" and prep["strategy"] == "train_linked_destination_only"
    assert prep["protocol_sha256"] == digest(HERE / "PROTOCOL.md")
    assert prep["baseline_sha256"] == digest(HERE / "BASELINE.json")
    assert prep["protected_model_rows_materialized"] == 0
    for name in ("selected.npz", "metadata.json", "mapping.json"):
        assert digest(HERE / "inputs" / name) == prep["output_hashes"][name]
    assert digest(SAFE / "selected.npz") == prep["source_selected_sha256"]
    for name in ("baseline_owner_exact", "metrics_exact", "logs_exact", "labels_exact",
                 "indices_exact", "trace_channel1_zero", "occurrence_count_preserved"):
        assert prep["checks"][name] is True, name
    data, original = archive(HERE / "inputs/selected.npz"), archive(SAFE / "selected.npz")
    validate_arrays(data, original)
    meta = document(HERE / "inputs/metadata.json")
    old_meta = document(SAFE / "metadata.json")
    for key in ("services", "edges", "windows", "original_indices", "train_positions", "validation_positions"):
        assert meta[key] == old_meta[key], key
    indices = data["indices"]
    train = np.asarray(meta["train_positions"], dtype=np.int64)
    val = np.asarray(meta["validation_positions"], dtype=np.int64)
    split = document(NATIVE / "calibration200/SN/diagmlp/seed_11/split.json")
    np.testing.assert_array_equal(indices[train], split["indices"]["train"])
    np.testing.assert_array_equal(indices[val], split["indices"]["validation"])
    assert set(indices) == set(split["indices"]["train"] + split["indices"]["validation"])
    assert not set(indices) & set(split["indices"]["test"] + split["indices"]["unassigned"])
    assert len(train) == 316 and len(val) == 78
    assert int(np.sum(data["labels"][val] >= 0)) == 65
    stats = native.fit_scaler(data, train)
    original_stats = native.fit_scaler(original, train)
    old = archive(NATIVE / "calibration200/SN/diagmlp/seed_11/scaler.npz")
    for key in old:
        np.testing.assert_array_equal(original_stats[key], old[key])
        if key.startswith("metrics"):
            np.testing.assert_array_equal(stats[key], old[key])
    parts = {"train": native.scaled_partition(data, train, stats),
             "validation": native.scaled_partition(data, val, stats)}
    return data, meta, train, val, stats, parts


def check_runtime():
    config = document(NATIVE / "calibration200/SN/diagmlp/seed_11/config.json")
    versions = {"python": sys.version, "torch": torch.__version__,
                "dgl": dgl.__version__, "numpy": np.__version__}
    assert versions == config["versions"], (versions, config["versions"])
    for name in ("native_models.py", "native_train.py"):
        assert digest(NATIVE / name) == config["source_hashes"][name]
    return config, versions


def preflight():
    config, versions = check_runtime()
    data, meta, train, val, stats, parts = load()
    setup(11)
    model = models.NativeReference("diagmlp", 12, 7)
    assert model.config == config["model"]
    assert sum(p.numel() for p in model.parameters()) == config["parameters"] == 75810
    initial = state_hash(model)
    model.eval()
    with torch.no_grad():
        graph, labels = native.graph_batch(parts["train"], np.arange(2), meta)
        roots, detection = model(graph)
        assert torch.isfinite(models.joint_loss(roots, detection, labels))
    report = {
        "status": "PASS", "versions": versions, "source_hashes": frozen_sources(),
        "allowed_rows": len(data["labels"]), "train_rows": len(train), "validation_rows": len(val),
        "parameters": 75810, "seed11_initial_state_sha256": initial,
        "trace_changed_cells": int(np.sum(data["traces"] != archive(SAFE / "selected.npz")["traces"])),
        "checks": ["baseline_hashes", "unchanged_other_modalities", "source_owner_exact_receipt",
                   "original_split", "TRAIN_only_scaler", "unchanged_model", "finite_forward"],
    }
    dump(HERE / "preflight.json", report)
    print("CALL_TARGET_PREFLIGHT_PASS", flush=True)


def strict_improvement(loss, best):
    if not math.isfinite(loss):
        raise ValueError("Nonfinite selection loss")
    return loss < best


def replay(folder, budget, parts, meta, original_indices):
    state = torch.load(folder / ("checkpoint_%d.pt" % budget), map_location="cpu")
    model = models.NativeReference("diagmlp", 12, 7)
    model.load_state_dict(state["state_dict"])
    root, detection, labels, loss = native.validation_predictions(model, parts["validation"], meta, 256)
    with np.load(folder / ("predictions_%d.npz" % budget), allow_pickle=False) as saved:
        for key, value in (("root_logits", root.numpy()), ("detection_logits", detection.numpy()),
                           ("labels", labels.numpy()), ("indices", original_indices)):
            np.testing.assert_array_equal(saved[key], value)
    assert loss == state["validation_joint_loss"]
    return {"selected_epoch": state["epoch"], "selected_updates": state["epoch"] * 2,
            "joint_loss": loss, "scores": models.native_scores(root, detection, labels),
            "checkpoint_replay": "bitwise equal logits/labels/indices; exact loss"}


def fit(seed):
    assert seed in SEEDS
    started, wall_started = time.perf_counter(), time.time()
    gate = document(HERE / "preflight.json")
    assert gate["status"] == "PASS" and gate["source_hashes"] == frozen_sources()
    baseline, versions = check_runtime()
    data, meta, train, val, stats, parts = load()
    folder = HERE / "runs" / ("seed_%d" % seed)
    folder.mkdir(parents=True, exist_ok=False)
    setup(seed)
    model = models.NativeReference("diagmlp", 12, 7)
    assert model.config == baseline["model"]
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    shuffle = np.random.RandomState(seed)
    config = {
        "seed": seed, "epochs": 200, "batch_size": 256, "lr": .001,
        "strategy": "train_linked_destination_only", "model": model.config,
        "optimizer": baseline["optimizer"], "versions": versions,
        "initial_state_sha256": state_hash(model), "source_hashes": frozen_sources(),
        "preflight_sha256": digest(HERE / "preflight.json"),
        "train_original_indices": data["indices"][train].tolist(),
        "validation_original_indices": data["indices"][val].tolist(),
        "selection": "strict minimum full-validation joint loss; earliest tie",
        "started_at_unix": wall_started,
    }
    if seed == 11:
        assert config["initial_state_sha256"] == gate["seed11_initial_state_sha256"]
    dump(folder / "config.json", config)
    np.savez(folder / "scaler.npz", **stats)
    history, best, elapsed50 = [], float("inf"), None
    training_started = time.perf_counter()
    with (folder / "epochs.jsonl").open("x") as log:
        for epoch in range(1, 201):
            epoch_started = time.perf_counter()
            model.train()
            order = shuffle.permutation(len(parts["train"]["labels"]))
            total, updates = 0., 0
            for start in range(0, len(order), 256):
                batch = order[start:start + 256]
                graph, labels = native.graph_batch(parts["train"], batch, meta)
                optimizer.zero_grad()
                root, detection = model(graph)
                loss = models.joint_loss(root, detection, labels)
                assert torch.isfinite(loss)
                loss.backward()
                assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
                optimizer.step()
                total += float(loss.item()) * len(batch)
                updates += 1
            root, detection, labels, val_loss = native.validation_predictions(
                model, parts["validation"], meta, 256)
            row = {
                "epoch": epoch, "optimizer_updates": updates,
                "train_batch_weighted_joint_loss": total / len(order),
                "validation_joint_loss": val_loss,
                "validation_scores": models.native_scores(root, detection, labels),
                "seconds": time.perf_counter() - epoch_started,
            }
            assert updates == 2
            history.append(row)
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush()
            if strict_improvement(val_loss, best):
                best = val_loss
                torch.save({"state_dict": model.state_dict(), "epoch": epoch,
                            "validation_joint_loss": best, "config_sha256": digest(folder / "config.json")},
                           folder / "checkpoint_200.pt")
                np.savez(folder / "predictions_200.npz", indices=data["indices"][val],
                         root_logits=root.numpy(), detection_logits=detection.numpy(), labels=labels.numpy())
            if epoch == 50:
                elapsed50 = time.perf_counter() - training_started
                for prefix, suffix in (("checkpoint", "pt"), ("predictions", "npz")):
                    shutil.copyfile(folder / (prefix + "_200." + suffix),
                                    folder / (prefix + "_50." + suffix))
            if epoch % 25 == 0:
                print("CALL_TARGET_EPOCH", seed, epoch, "validation_joint", val_loss, flush=True)
    training_seconds = time.perf_counter() - training_started
    dump(folder / "history.json", history)
    replay_started = time.perf_counter()
    selected = {str(b): replay(folder, b, parts, meta, data["indices"][val]) for b in (50, 200)}
    for budget in (50, 200):
        expected = min(history[:budget], key=lambda r: r["validation_joint_loss"])
        assert selected[str(budget)]["selected_epoch"] == expected["epoch"]
    assert config["source_hashes"] == frozen_sources()
    baseline_check()
    summary = {
        "status": "PASS", "seed": seed, "epochs_completed": 200, "optimizer_updates": 400,
        "selected": selected, "training_validation_seconds50": elapsed50,
        "training_validation_seconds200": training_seconds,
        "replay_seconds": time.perf_counter() - replay_started,
        "total_seconds": time.perf_counter() - started, "finished_at_unix": time.time(),
        "protected_model_rows_materialized": 0,
        "artifact_hashes": {p.name: digest(p) for p in folder.iterdir() if p.is_file()},
    }
    dump(folder / "summary.json", summary)
    print("CALL_TARGET_FIT_PASS", seed, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--seed", type=int, choices=SEEDS)
    args = parser.parse_args()
    preflight() if args.check else fit(args.seed)
