#!/usr/bin/env python3
"""Guarded SN absolute-Hawkes-horizon calibration runner."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time

os.environ.setdefault("DGLBACKEND", "pytorch")
import dgl
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parents[1] / "research" / "native_reproduction_20261013"
sys.path.insert(0, str(NATIVE))
from native_models import NativeReference, joint_loss, native_scores  # noqa: E402
from native_train import (  # noqa: E402
    file_hash, fit_scaler, graph_batch, scaled_partition,
    validation_predictions,
)

BASELINE = NATIVE / "calibration200" / "SN" / "diagmlp"
INPUTS = HERE / "inputs"
EXPECTED_SEEDS = (11, 23, 37)


def strict_minimum(history, candidate):
    """Keep the earliest epoch on an exact validation-loss tie."""
    if not history:
        return True
    return candidate["validation_joint_loss"] < min(
        row["validation_joint_loss"] for row in history)


def absolute_horizon_arrays(arrays):
    return dict(arrays, logs=arrays["log_absolute"])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def sha256(path):
    return file_hash(path)


def load_preparation():
    prep_path = INPUTS / "preparation.json"
    metadata_path = INPUTS / "metadata.json"
    selected_path = INPUTS / "selected.npz"
    require(prep_path.is_file() and metadata_path.is_file() and selected_path.is_file(),
            "prepared input manifest, metadata, or selected.npz is missing")
    prep = read_json(prep_path)
    require(prep.get("status") == "PASS", "preparation manifest status is not PASS")
    hashes = prep.get("output_hashes")
    require(isinstance(hashes, dict), "preparation output_hashes missing")
    for name, path in (("metadata.json", metadata_path), ("selected.npz", selected_path)):
        expected = hashes.get(name)
        require(isinstance(expected, str) and len(expected) == 64,
                "missing preparation hash for " + name)
        require(sha256(path) == expected, "prepared input hash mismatch: " + name)
    metadata = read_json(metadata_path)
    require(metadata.get("system") == "SN", "prepared input is not SN")
    require(metadata.get("event_count") == 7 and len(metadata.get("services", [])) == 12,
            "prepared SN model shape differs from frozen configuration")
    require(metadata.get("window_count") == 394 and metadata.get("stride") == 10
            and metadata.get("window_length") == 10,
            "prepared window contract differs from frozen SN contrast")
    require(metadata.get("split_counts") == {
        "train": 316, "validation": 78, "test": 169, "unassigned": 1},
        "prepared original split counts mismatch")
    require(metadata.get("forbidden_observation_rows_materialized") == 0,
            "preparation reports forbidden observations materialized")
    require(isinstance(prep.get("protection"), str) and prep["protection"].strip(),
            "preparation protection/stream-skip disclosure missing")
    raw_indices = metadata.get("original_indices")
    raw_train = metadata.get("train_positions")
    raw_val = metadata.get("validation_positions")
    require(isinstance(raw_indices, list) and all(type(v) is int for v in raw_indices),
            "original_indices missing or invalid")
    require(isinstance(raw_train, list) and all(type(v) is int for v in raw_train),
            "train_positions missing or invalid")
    require(isinstance(raw_val, list) and all(type(v) is int for v in raw_val),
            "validation_positions missing or invalid")
    indices = np.asarray(raw_indices, dtype=np.int64)
    train_pos = np.asarray(raw_train, dtype=np.int64)
    val_pos = np.asarray(raw_val, dtype=np.int64)
    require(indices.shape == (394,) and len(np.unique(indices)) == 394,
            "expected 394 unique allowed original windows")
    require(train_pos.shape == (316,) and val_pos.shape == (78,),
            "expected train/validation positions 316/78")
    require(np.array_equal(np.sort(np.concatenate((train_pos, val_pos))),
                           np.arange(len(indices))), "split positions are not a partition")
    require(np.all((train_pos >= 0) & (train_pos < len(indices)))
            and np.all((val_pos >= 0) & (val_pos < len(indices))),
            "split position outside selected input")
    require(metadata.get("horizon_only") == {
        "relative": 10, "absolute": "original_window_start+10"},
        "prepared horizon contract mismatch")
    with np.load(selected_path, allow_pickle=False) as archive:
        needed = {"indices", "metrics", "traces", "logs", "log_absolute", "labels"}
        require(set(archive.files) == needed, "selected input field set mismatch")
        arrays = {key: archive[key] for key in needed}
    require(np.array_equal(arrays["indices"], indices),
            "selected NPZ original indices differ from metadata order")
    return prep, metadata, indices, train_pos, val_pos, arrays


def compare_baseline_contract(metadata, indices, train_pos, val_pos):
    split_path = BASELINE / "seed_11" / "split.json"
    scaler_path = BASELINE / "seed_11" / "scaler.npz"
    config_path = BASELINE / "seed_11" / "config.json"
    require(all(path.is_file() for path in (split_path, scaler_path, config_path)),
            "baseline split/scaler/config is missing")
    split = read_json(split_path)
    train = np.asarray(split["indices"]["train"], dtype=np.int64)
    validation = np.asarray(split["indices"]["validation"], dtype=np.int64)
    require(np.array_equal(indices[train_pos], train), "original train split/order mismatch")
    require(np.array_equal(indices[val_pos], validation), "original validation split/order mismatch")
    require(metadata.get("original_split_sha256") == sha256(split_path),
            "original split hash mismatch")
    config = read_json(config_path)
    summary_path = BASELINE / "seed_11" / "summary.json"
    summary = read_json(summary_path)
    artifact_hashes = summary.get("artifact_hashes")
    require(isinstance(artifact_hashes, dict), "baseline summary artifact_hashes missing")
    require(artifact_hashes.get("split.json") == sha256(split_path),
            "baseline summary split hash mismatch")
    require(artifact_hashes.get("scaler.npz") == sha256(scaler_path),
            "baseline summary scaler hash mismatch")
    require(metadata.get("original_split_sha256") == sha256(split_path),
            "original split hash mismatch")
    require(config.get("artifact_hashes", {}).get("split.json") == sha256(split_path),
            "baseline config split hash differs")
    return split, scaler_path, config


def check_arrays(arrays, rows):
    require(arrays["indices"].shape == (rows,) and arrays["indices"].dtype == np.int64,
            "original indices shape/dtype mismatch")
    require(np.array_equal(arrays["metrics"].shape, (rows, 12, 10, 7)), "metrics shape mismatch")
    require(arrays["traces"].shape == (rows, 12, 10, 2), "traces shape mismatch")
    require(arrays["logs"].shape == (rows, 12, 7) and
            arrays["log_absolute"].shape == (rows, 12, 7), "logs shape mismatch")
    require(arrays["labels"].shape == (rows,), "labels shape mismatch")
    require(arrays["labels"].dtype.kind in "iu", "labels must be integer typed")
    require(np.all((arrays["labels"] == -1) | ((arrays["labels"] >= 0) & (arrays["labels"] < 12))),
            "invalid labels")
    for key in ("metrics", "traces", "logs", "log_absolute"):
        require(np.isfinite(arrays[key]).all(), "nonfinite " + key)
    require(np.all(arrays["logs"] >= 0) and np.all(arrays["log_absolute"] >= 0),
            "negative Hawkes feature")
    require(np.all(arrays["traces"][..., 1] == 0), "nonzero reserved trace channel")


def check_runtime_versions(actual, expected):
    require(isinstance(expected, dict), "baseline runtime versions missing")
    for name in ("python", "torch", "dgl", "numpy"):
        require(name in expected, "baseline version field missing: " + name)
        require(actual[name] == expected[name], "runtime version mismatch: " + name)


def preflight():
    prep, metadata, indices, train_pos, val_pos, arrays = load_preparation()
    check_arrays(arrays, len(indices))
    split, scaler_path, baseline_config = compare_baseline_contract(
        metadata, indices, train_pos, val_pos)
    stats = fit_scaler(
        {key: arrays[key] for key in ("metrics", "traces", "logs", "labels")},
        train_pos)
    with np.load(scaler_path, allow_pickle=False) as old:
        require(set(stats) == set(old.files), "scaler field set mismatch")
        for key, value in stats.items():
            np.testing.assert_array_equal(value, old[key], err_msg="scaler mismatch: " + key)
    config_path = BASELINE / "seed_11" / "config.json"
    versions = {"python": sys.version, "torch": torch.__version__,
                "dgl": dgl.__version__, "numpy": np.__version__}
    check_runtime_versions(versions, baseline_config.get("versions"))
    for source_name, path in (
            ("native_train.py", NATIVE / "native_train.py"),
            ("native_models.py", NATIVE / "native_models.py")):
        require(baseline_config["source_hashes"].get(source_name) == sha256(path),
                "native helper source hash mismatch: " + source_name)
    # Compare initialized state and one relative-input epoch to baseline history[0].
    seed = 11
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    model = NativeReference("diagmlp", 12, 7)
    expected_shape = baseline_config["model"]
    require(model.config == expected_shape, "native model configuration mismatch")
    train = scaled_partition(arrays, train_pos, stats)
    validation = scaled_partition(arrays, val_pos, stats)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, betas=(.9, .999),
                                 eps=1e-8, weight_decay=0, amsgrad=False)
    order = np.random.RandomState(seed).permutation(len(train["labels"]))
    model.train()
    total, updates = 0., 0
    for start in range(0, len(order), 256):
        batch = order[start:start + 256]
        graph, labels = graph_batch(train, batch, metadata)
        optimizer.zero_grad()
        root, detection = model(graph)
        loss = joint_loss(root, detection, labels)
        require(bool(torch.isfinite(loss)), "nonfinite one-epoch parity loss")
        loss.backward()
        optimizer.step()
        total += float(loss.item()) * len(batch)
        updates += 1
    root, detection, labels, val_loss = validation_predictions(model, validation, metadata, 256)
    history = read_json(BASELINE / "seed_11" / "history.json")
    first = history[0]
    require(updates == first["optimizer_updates"], "one-epoch update count mismatch")
    require(math.isclose(total / len(order), first["train_batch_weighted_joint_loss"],
                         rel_tol=0, abs_tol=1e-7), "relative epoch training loss parity failed")
    require(math.isclose(val_loss, first["validation_joint_loss"], rel_tol=0, abs_tol=1e-7),
            "relative epoch validation loss parity failed")
    np.testing.assert_equal(native_scores(root, detection, labels), first["validation_scores"])
    report = {"status": "PASS", "versions": versions, "preparation_sha256": sha256(INPUTS / "preparation.json"),
              "metadata_sha256": sha256(INPUTS / "metadata.json"),
              "selected_sha256": sha256(INPUTS / "selected.npz"),
              "baseline_config_sha256": sha256(config_path), "split_sha256": sha256(BASELINE / "seed_11" / "split.json"),
              "scaler_sha256": sha256(scaler_path), "allowed_rows": len(indices),
              "train_count": len(train_pos), "validation_count": len(val_pos),
              "runner_script_sha256": sha256(Path(__file__)),
              "pyright_config_sha256": sha256(HERE / "optionalpyright_runner.json"),
              "relative_seed11_epoch1": {"training_loss": total / len(order),
                  "validation_loss": val_loss, "updates": updates},
              "protected_values_materialized": False,
              "stream_skip_disclosure": prep["protection"]}
    (HERE / "preflight.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (HERE / "preflight.status").write_text("PASS\n")
    return report


def fit(seed):
    require(seed in EXPECTED_SEEDS, "seed must be 11, 23, or 37")
    preflight_path = HERE / "preflight.json"
    require(preflight_path.is_file() and read_json(preflight_path).get("status") == "PASS",
            "a passing real-input --preflight is required before fitting")
    output = HERE / "runs" / ("absolute_seed_" + str(seed))
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    prep, metadata, indices, train_pos, val_pos, arrays = load_preparation()
    check_arrays(arrays, len(indices))
    absolute_arrays = absolute_horizon_arrays(arrays)
    stats = fit_scaler(
        {key: absolute_arrays[key] for key in ("metrics", "traces", "logs", "labels")},
        train_pos)
    split, scaler_path, baseline_config = compare_baseline_contract(
        metadata, indices, train_pos, val_pos)
    with np.load(scaler_path, allow_pickle=False) as old:
        for key, value in stats.items():
            np.testing.assert_array_equal(value, old[key])
    train = scaled_partition(absolute_arrays, train_pos, stats)
    validation = scaled_partition(absolute_arrays, val_pos, stats)
    baseline_predictions = BASELINE / ("seed_" + str(seed)) / "validation_predictions.npz"
    require(baseline_predictions.is_file(), "baseline validation predictions missing")
    with np.load(baseline_predictions, allow_pickle=False) as old_predictions:
        np.testing.assert_array_equal(old_predictions["indices"], indices[val_pos])
        np.testing.assert_array_equal(old_predictions["labels"], validation["labels"])
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    model = NativeReference("diagmlp", 12, 7)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, betas=(.9, .999),
                                 eps=1e-8, weight_decay=0, amsgrad=False)
    config = {"seed": seed, "kind": "diagmlp", "horizon": "absolute",
              "effective_epochs": 200, "batch_size": 256, "lr": .001,
              "optimizer": "Adam", "model": model.config, "services": metadata["services"],
              "edges": metadata["edges"], "training_original_indices": indices[train_pos].tolist(),
              "validation_original_indices": indices[val_pos].tolist(),
              "preparation_sha256": sha256(INPUTS / "preparation.json"),
              "selected_sha256": sha256(INPUTS / "selected.npz"),
              "runner_script_sha256": sha256(Path(__file__)),
              "pyright_config_sha256": sha256(HERE / "optionalpyright_runner.json"),
              "native_model_source_sha256": sha256(NATIVE / "native_models.py"),
              "native_train_source_sha256": sha256(NATIVE / "native_train.py"),
              "baseline_artifact_hashes": {
                  "config.json": sha256(BASELINE / ("seed_" + str(seed)) / "config.json"),
                  "summary.json": sha256(BASELINE / ("seed_" + str(seed)) / "summary.json"),
                  "split.json": sha256(BASELINE / ("seed_" + str(seed)) / "split.json"),
                  "scaler.npz": sha256(BASELINE / ("seed_" + str(seed)) / "scaler.npz"),
                  "history.json": sha256(BASELINE / ("seed_" + str(seed)) / "history.json"),
                  "validation_predictions.npz": sha256(baseline_predictions)},
              "versions": {"python": sys.version, "torch": torch.__version__,
                           "dgl": dgl.__version__, "numpy": np.__version__},
              "checkpoint_selection": "strict minimum validation joint loss; earliest tie"}
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    rng = np.random.RandomState(seed)
    history, best = [], float("inf")
    start_train = time.perf_counter()
    for epoch in range(1, 201):
        epoch_start = time.perf_counter()
        model.train()
        order = rng.permutation(len(train["labels"]))
        total, updates = 0., 0
        for start in range(0, len(order), 256):
            batch = order[start:start + 256]
            graph, labels = graph_batch(train, batch, metadata)
            optimizer.zero_grad()
            root, detection = model(graph)
            loss = joint_loss(root, detection, labels)
            require(bool(torch.isfinite(loss)), "nonfinite training loss")
            loss.backward()
            require(all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in model.parameters()),
                    "nonfinite gradient")
            optimizer.step()
            total += float(loss.item()) * len(batch); updates += 1
        root, detection, labels, val_loss = validation_predictions(model, validation, metadata, 256)
        row = {"epoch": epoch, "train_batch_weighted_joint_loss": total / len(order),
               "validation_joint_loss": val_loss, "optimizer_updates": updates,
               "seconds": time.perf_counter() - epoch_start,
               "validation_scores": native_scores(root, detection, labels)}
        history.append(row)
        if strict_minimum(history[:-1], row):
            best = val_loss
            torch.save({"state_dict": model.state_dict(), "model_config": model.config,
                        "epoch": epoch, "validation_joint_loss": best}, output / "checkpoint.pt")
            np.savez(output / "validation_predictions.npz",
                     indices=indices[val_pos], root_logits=root.numpy(),
                     detection_logits=detection.numpy(), labels=labels.numpy())
        (output / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
    training_seconds = time.perf_counter() - start_train
    checkpoint = torch.load(output / "checkpoint.pt", map_location="cpu")
    replay = NativeReference("diagmlp", 12, 7); replay.load_state_dict(checkpoint["state_dict"])
    root, detection, labels, replay_loss = validation_predictions(replay, validation, metadata, 256)
    with np.load(output / "validation_predictions.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["indices"], indices[val_pos])
        np.testing.assert_array_equal(saved["root_logits"], root.numpy())
        np.testing.assert_array_equal(saved["detection_logits"], detection.numpy())
        np.testing.assert_array_equal(saved["labels"], labels.numpy())
    require(replay_loss == checkpoint["validation_joint_loss"], "checkpoint loss replay mismatch")
    summary = {"status": "PASS", "best_epoch": checkpoint["epoch"],
               "best_validation_joint_loss": best, "checkpoint_replay": "bitwise predictions and exact loss",
               "training_validation_seconds": training_seconds, "total_seconds": time.perf_counter() - started,
               "epochs_completed": 200, "optimizer_updates": sum(r["optimizer_updates"] for r in history),
               "test_evaluated": False}
    summary["artifact_hashes"] = {
        path.name: sha256(path) for path in
        (output / "config.json", output / "history.json", output / "checkpoint.pt",
         output / "validation_predictions.npz")
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-check", action="store_true")
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--seed", type=int, choices=EXPECTED_SEEDS)
    args = parser.parse_args(argv)
    if args.self_check:
        from test_run_horizon import self_check
        self_check()
        print("HORIZON_SELF_CHECK PASS")
    elif args.preflight:
        print(json.dumps(preflight(), indent=2))
    else:
        print(json.dumps(fit(args.seed), indent=2))


if __name__ == "__main__":
    main()
