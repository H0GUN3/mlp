#!/usr/bin/env python3
"""CPU-only native baseline calibration; test partitions are never evaluated."""
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any, Dict

os.environ.setdefault("DGLBACKEND", "pytorch")
import dgl
import numpy as np
import torch

from native_models import NativeReference, SOURCE, joint_loss, native_scores

HERE = Path(__file__).resolve().parent
SPLIT_SEED = 42
EPSILON = 1e-8
SCALER_SOURCE = (
    "https://github.com/FeiGSSS/Eadro/blob/"
    "7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py"
)


def dump_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def load_inputs(directory, system):
    raw, meta_path = directory / "raw.npz", directory / "metadata.json"
    hashes = {"raw.npz": file_hash(raw), "metadata.json": file_hash(meta_path)}
    with np.load(raw, allow_pickle=False) as archive:
        if set(archive.files) != {"metrics", "traces", "logs", "labels"}:
            raise ValueError("raw.npz must contain exactly the four numeric contract keys")
        arrays = {key: archive[key] for key in archive.files}
    metadata = json.loads(meta_path.read_text())
    validate_inputs(arrays, metadata, system)
    if hashes != {"raw.npz": file_hash(raw), "metadata.json": file_hash(meta_path)}:
        raise ValueError("Producer inputs changed while loading")
    return arrays, metadata, hashes


def validate_inputs(arrays, metadata, system):
    if not isinstance(metadata, dict) or metadata.get("system") != system:
        raise ValueError("Metadata system mismatch")
    services = metadata.get("services")
    if (not isinstance(services, list) or len(services) != {"SN": 12, "TT": 27}[system]
            or any(not isinstance(s, str) or not s for s in services)
            or len(set(services)) != len(services)):
        raise ValueError("Invalid ordered native service inventory")
    nodes = len(services)
    events = metadata.get("event_count")
    if not isinstance(events, int) or not integer(events) or events < 2:
        raise ValueError("Invalid event_count")
    labels = arrays["labels"]
    if (labels.ndim != 1 or labels.dtype.kind not in "iu" or not len(labels)
            or np.any(labels < -1) or np.any(labels >= nodes)):
        raise ValueError("Invalid native labels")
    count = len(labels)
    for key, shape in (("metrics", (count, nodes, 10, 7)),
                       ("traces", (count, nodes, 10, 2)),
                       ("logs", (count, nodes, events))):
        value = arrays[key]
        if value.shape != shape or value.dtype.kind not in "fiu" or not np.isfinite(value).all():
            raise ValueError("Invalid/nonfinite native " + key)
    if np.any(arrays["traces"][..., 1] != 0):
        raise ValueError("Second native trace channel must remain zero")
    if np.any(arrays["logs"] < 0):
        raise ValueError("Hawkes baselines must be nonnegative")
    edges = metadata.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ValueError("Missing static author edges")
    for edge in edges:
        if (not isinstance(edge, list) or len(edge) != 2
                or any(not integer(v) or not 0 <= v < nodes for v in edge)):
            raise ValueError("Invalid static edge")
    windows = metadata.get("windows")
    if not isinstance(windows, list) or len(windows) != count:
        raise ValueError("Window provenance count mismatch")
    intervals: Dict[str, Any] = {}
    for index, row in enumerate(windows):
        if not isinstance(row, dict):
            raise ValueError("Invalid window provenance")
        run = row.get("run_id")
        start, end = row.get("start"), row.get("end")
        if (not isinstance(run, str) or not run or not isinstance(start, int)
                or not isinstance(end, int) or not integer(start)
                or not integer(end) or end != start + 9):
            raise ValueError("Expected full ten-second windows with inclusive integer end")
        intervals.setdefault(run, []).append((start, end))
        for key in ("event_id", "root_fault_group"):
            if key not in row:
                raise ValueError("Missing " + key)
            value = row[key]
            if labels[index] == -1:
                if value is not None:
                    raise ValueError("Normal windows must have null fault provenance")
            elif not isinstance(value, str) or not value:
                raise ValueError("Fault windows must carry fault provenance")
    for rows in intervals.values():
        ordered = sorted(rows)
        if any(right[0] <= left[1] for left, right in zip(ordered, ordered[1:])):
            raise ValueError("Overlapping windows within a recording")


def make_split(count, windows):
    permutation = np.random.RandomState(SPLIT_SEED).permutation(count)
    trainval, test = math.floor(.7 * count), math.floor(.3 * count)
    validation = math.floor(.2 * trainval)
    training = trainval - validation
    if not training or not validation or not test:
        raise ValueError("Too few windows for nonempty train/validation/test")
    parts = {"train": permutation[:training],
             "validation": permutation[training:trainval],
             "test": permutation[trainval:trainval + test],
             "unassigned": permutation[trainval + test:]}
    flat = np.concatenate(list(parts.values()))
    if len(np.unique(flat)) != count or not np.array_equal(np.sort(flat), np.arange(count)):
        raise AssertionError("Split partition accounting failed")
    event_sets = {}
    for name, indices in parts.items():
        event_sets[name] = {
            (windows[int(i)]["run_id"], event)
            for i in indices if windows[int(i)]["event_id"] is not None
            for event in windows[int(i)]["event_id"].split(";")
        }
    shared = {a + "__" + b: len(event_sets[a] & event_sets[b])
              for a, b in itertools.combinations(parts, 2)}
    report = {"seed": SPLIT_SEED, "rng": "NumPy RandomState/MT19937",
              "validation_rule": "last floor(.2*trainval) of the seed42 trainval permutation",
              "counts": {k: len(v) for k, v in parts.items()},
              "indices": {k: v.tolist() for k, v in parts.items()},
              "permutation": permutation.tolist(), "disjoint_indices": True,
              "shared_event_counts": shared,
              "event_counts": {k: len(v) for k, v in event_sets.items()},
              "limitation": "Window split can share injections; not incident generalization."}
    return parts, report


def fit_scaler(arrays, train_indices):
    stats = {}
    for key in ("metrics", "traces"):
        train = arrays[key][train_indices].astype(np.float64)
        mean = train.mean(axis=(0, 2))
        std = train.std(axis=(0, 2), ddof=0)
        constant = np.all(train == train[:1, :, :1, :], axis=(0, 2))
        # Explicitly zero constant training channels; held-out shifts still use source epsilon.
        std[constant] = 0
        mean[constant] = np.broadcast_to(train[0, :, 0, :], mean.shape)[constant]
        if not np.isfinite(mean).all() or not np.isfinite(std).all():
            raise ValueError("Nonfinite scaler statistics")
        stats[key + "_mean"] = mean
        stats[key + "_std"] = std
        stats[key + "_constant"] = constant
    return stats


def scaled_partition(arrays, indices, stats):
    result = {"labels": arrays["labels"][indices].astype(np.int64)}
    for key in ("metrics", "traces"):
        value = arrays[key][indices].astype(np.float64)
        mean, std = stats[key + "_mean"], stats[key + "_std"]
        normalized = (value - mean[None, :, None, :]) / (std[None, :, None, :] + EPSILON)
        result[key] = normalized.astype(np.float32)
    result["logs"] = arrays["logs"][indices].astype(np.float32)
    if any(not np.isfinite(v).all() for v in result.values()):
        raise ValueError("Nonfinite scaled/native float32 input")
    if np.any(result["traces"][..., 1] != 0):
        raise AssertionError("Scaling altered the zero trace channel")
    return result


def graph_batch(data, indices, metadata):
    nodes = len(metadata["services"])
    src, dst = zip(*metadata["edges"])
    graph = dgl.batch([dgl.graph((src, dst), num_nodes=nodes) for _ in indices])
    for key in ("metrics", "traces", "logs"):
        values = data[key][indices]
        graph.ndata[key] = torch.from_numpy(values.reshape((-1,) + values.shape[2:]))
    return graph, torch.from_numpy(data["labels"][indices])


def validation_predictions(model, data, metadata, batch_size):
    model.eval()
    roots, detects, labels = [], [], []
    with torch.no_grad():
        for start in range(0, len(data["labels"]), batch_size):
            indices = np.arange(start, min(start + batch_size, len(data["labels"])))
            graph, truth = graph_batch(data, indices, metadata)
            root, detect = model(graph)
            roots.append(root)
            detects.append(detect)
            labels.append(truth)
    root, detect, truth = torch.cat(roots), torch.cat(detects), torch.cat(labels)
    loss = joint_loss(root, detect, truth)
    return root, detect, truth, float(loss.item())


def run_training(options):
    started = time.perf_counter()
    torch.set_num_threads(options.threads)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(options.seed)
    np.random.seed(options.seed)
    torch.manual_seed(options.seed)
    arrays, metadata, input_hashes = load_inputs(options.input_dir, options.system)
    parts, split = make_split(len(arrays["labels"]), metadata["windows"])
    expected = {"SN": {"train": 316, "validation": 78, "test": 169},
                "TT": {"train": 3256, "validation": 813, "test": 1744}}[options.system]
    split["protocol_expected_counts"] = expected
    split["protocol_count_match"] = all(split["counts"][k] == v for k, v in expected.items())
    if not split["protocol_count_match"]:
        print("WARNING: protocol count mismatch; inspect split.json before calibration.", flush=True)
    stats = fit_scaler(arrays, parts["train"])
    train = scaled_partition(arrays, parts["train"], stats)
    validation = scaled_partition(arrays, parts["validation"], stats)
    model = NativeReference(options.kind, len(metadata["services"]), metadata["event_count"])
    optimizer = torch.optim.Adam(model.parameters(), lr=options.lr)
    output = options.output_dir
    output.mkdir(parents=True, exist_ok=False)
    dump_json(output / "split.json", split)
    np.savez(output / "scaler.npz", **stats)
    config: Dict[str, Any] = {
        "effective_options": {k: str(v) if isinstance(v, Path) else v for k, v in vars(options).items()},
        "effective_epochs": 1 if options.profile_one_epoch else options.epochs,
        "split_seed": SPLIT_SEED, "model": model.config, "device": "cpu",
        "optimizer": {"name": "Adam", "betas": [.9, .999], "eps": 1e-8,
                      "weight_decay": 0, "amsgrad": False},
        "num_threads": torch.get_num_threads(), "num_interop_threads": torch.get_num_interop_threads(),
        "shuffle": "seeded NumPy RandomState(model seed), each epoch",
        "dgl_backend": os.environ.get("DGLBACKEND"),
        "deterministic_algorithms": True, "dtype": "float32",
        "checkpoint_selection": "strict minimum full-validation joint loss; earliest tie",
        "test_evaluated": False, "services": metadata["services"], "edges": metadata["edges"],
        "parameters": sum(p.numel() for p in model.parameters()),
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "input_hashes": input_hashes,
        "artifact_hashes": {"split.json": file_hash(output / "split.json"),
                            "scaler.npz": file_hash(output / "scaler.npz")},
        "source_hashes": {p.name: file_hash(p) for p in
                          (Path(__file__), HERE / "native_models.py", SOURCE,
                           HERE / "CALIBRATION_PROTOCOL.md")},
        "scaler": {"fit_partition": "train", "axes": "window,time per node/channel",
                   "ddof": 0, "epsilon": EPSILON, "source": SCALER_SOURCE,
                   "constant_policy": "std=0; denominator=source epsilon; no clipping",
                   "constant_channels": {k: np.argwhere(stats[k + "_constant"]).tolist()
                                         for k in ("metrics", "traces")},
                   "logs": "unchanged native Hawkes features"},
        "versions": {"python": sys.version, "torch": torch.__version__,
                     "dgl": dgl.__version__, "numpy": np.__version__},
        "claim": "Native reference calibration only; not paper reproduction.",
    }
    dump_json(output / "config.json", config)
    shuffle = np.random.RandomState(options.seed)
    history = []
    best = float("inf")
    training_started = time.perf_counter()
    for epoch in range(1, config["effective_epochs"] + 1):
        epoch_started = time.perf_counter()
        model.train()
        order = shuffle.permutation(len(train["labels"]))
        total_loss, updates = 0.0, 0
        for start in range(0, len(order), options.batch_size):
            indices = order[start:start + options.batch_size]
            graph, labels = graph_batch(train, indices, metadata)
            optimizer.zero_grad()
            root, detect = model(graph)
            loss = joint_loss(root, detect, labels)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise ValueError("Nonfinite gradient")
            optimizer.step()
            total_loss += float(loss.item()) * len(indices)
            updates += 1
        root, detect, labels, val_loss = validation_predictions(
            model, validation, metadata, options.batch_size)
        row = {"epoch": epoch, "train_batch_weighted_joint_loss": total_loss / len(order),
               "validation_joint_loss": val_loss, "optimizer_updates": updates,
               "seconds": time.perf_counter() - epoch_started,
               "validation_scores": native_scores(root, detect, labels)}
        history.append(row)
        if val_loss < best:
            best = val_loss
            torch.save({"state_dict": model.state_dict(), "model_config": model.config,
                        "epoch": epoch, "validation_joint_loss": best,
                        "config_sha256": file_hash(output / "config.json"),
                        "input_hashes": input_hashes, "artifact_hashes": config["artifact_hashes"]},
                       output / "checkpoint.pt")
            np.savez(output / "validation_predictions.npz", indices=parts["validation"],
                     root_logits=root.numpy(), detection_logits=detect.numpy(), labels=labels.numpy())
        dump_json(output / "history.json", history)
        print("EPOCH", json.dumps(row, allow_nan=False), flush=True)
    training_seconds = time.perf_counter() - training_started
    checkpoint = torch.load(output / "checkpoint.pt", map_location="cpu")
    replay = NativeReference(options.kind, len(metadata["services"]), metadata["event_count"])
    replay.load_state_dict(checkpoint["state_dict"])
    root, detect, labels, replay_loss = validation_predictions(
        replay, validation, metadata, options.batch_size)
    with np.load(output / "validation_predictions.npz", allow_pickle=False) as saved:
        for key, value in (("root_logits", root.numpy()), ("detection_logits", detect.numpy()),
                           ("labels", labels.numpy()), ("indices", parts["validation"])):
            np.testing.assert_array_equal(saved[key], value)
    if replay_loss != checkpoint["validation_joint_loss"]:
        raise AssertionError("Checkpoint validation loss replay mismatch")
    summary = {"status": "passed", "mode": "one_epoch_profile" if options.profile_one_epoch else "training",
               "best_epoch": checkpoint["epoch"], "best_validation_joint_loss": best,
               "checkpoint_replay": "bitwise equal validation logits, labels, indices and loss",
               "test_evaluated": False, "parameters": config["parameters"],
               "training_validation_seconds": training_seconds,
               "total_seconds": time.perf_counter() - started,
               "epochs_completed": len(history),
               "optimizer_updates": sum(row["optimizer_updates"] for row in history),
               "artifact_hashes": {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}}
    dump_json(output / "summary.json", summary)
    return summary


def parse_options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--system", choices=("SN", "TT"))
    parser.add_argument("--kind", choices=("eadro", "diagmlp"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=.001)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--profile-one-epoch", action="store_true",
                        help="Run exactly one training+validation epoch, save timing and replay.")
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    options = parser.parse_args(argv)
    if (options.epochs < 1 or options.batch_size < 1 or options.threads < 1
            or not math.isfinite(options.lr) or options.lr <= 0
            or not 0 <= options.seed < 2 ** 32):
        parser.error("Require positive epochs/batch-size/threads/lr and uint32 seed")
    if not options.self_check and (options.system is None or options.kind is None):
        parser.error("--system and --kind are required outside --self-check")
    if options.self_check:
        if options.input_dir is not None or options.output_dir is not None:
            parser.error("--self-check uses only its own generated fixtures/artifacts")
        return options
    options.input_dir = (options.input_dir or HERE / "native_inputs" / options.system).resolve()
    options.output_dir = (options.output_dir or HERE / "trainer_runs" /
                          "{}-{}-seed{}-{}".format(options.system, options.kind, options.seed,
                                                  time.time_ns())).resolve()
    if HERE not in options.output_dir.parents or (HERE / "native_inputs") in options.output_dir.parents:
        parser.error("--output-dir must be below the trainer directory, outside native_inputs")
    return options


def main():
    options = parse_options()
    if options.self_check:
        from native_train_test import self_check
        self_check(options)
        print("NATIVE_TRAIN_SELF_CHECK PASSED", flush=True)
    else:
        print(json.dumps(run_training(options), indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
