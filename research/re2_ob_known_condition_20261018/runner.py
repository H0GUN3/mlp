"""Fixed RE2-OB DiagMLP development runner. Never opens raw/protected telemetry."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import sys
import time

os.environ.setdefault("DGLBACKEND", "pytorch")
import dgl
import numpy as np
import torch

from research.native_reproduction_20261013.native_models import (
    NativeReference, SOURCE, joint_loss,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SEEDS = (11, 23, 37)
EPOCHS, BATCH, EPSILON = 200, 256, 1e-8
RTOL, ATOL = 1e-5, 1e-6
PARTS = ("train", "validation")
FAMILIES = ("cpu", "diskio", "error", "latency-50", "latency-90", "mem",
            "socket", "workload")
ARRAY_KEYS = {"metrics", "metric_observed", "traces", "logs", "labels",
              "case_ids", "starts", "partition", "indices", "edge_pairs"}
PRED_KEYS = {"root_logits", "detection_logits", "labels", "case_ids",
             "starts", "indices", "partition"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    """Reject aliases before opening: lexical absolute paths, no symlink components."""
    require(".." not in Path(path).parts, "Parent traversal is forbidden")
    path = Path(os.path.abspath(str(path)))
    for component in (path,) + tuple(path.parents):
        require(not component.is_symlink(), "Symlink path forbidden: " + str(component))
    return path


class ReadGuard:
    """Exact file allowlist; metadata hashes/paths never grant read authority."""

    def __init__(self, paths):
        self.paths = frozenset(Path(os.path.abspath(str(p))) for p in paths)

    def open(self, path):
        path = safe_path(path)
        require(path in self.paths, "Read outside exact allowlist: " + str(path))
        require(path.is_file() and path.stat().st_nlink == 1,
                "Expected unaliased regular file: " + str(path))
        return path.open("rb")

    def digest(self, path):
        digest = hashlib.sha256()
        with self.open(path) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def json(self, path):
        with self.open(path) as stream:
            return json.load(stream)

    def arrays(self, path):
        with self.open(path) as stream, np.load(stream, allow_pickle=False) as saved:
            return {key: saved[key] for key in saved.files}

    def checkpoint(self, path):
        # Only locally generated, hash-checked checkpoints reach this pickle loader.
        with self.open(path) as stream:
            return torch.load(stream, map_location="cpu")


def write_json(path, value):
    path = safe_path(path)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_arrays(path, values):
    with safe_path(path).open("xb") as stream:
        np.savez_compressed(stream, **values)


def write_checkpoint(path, value):
    with safe_path(path).open("xb") as stream:
        torch.save(value, stream)


def source_hashes():
    native = HERE.parent / "native_reproduction_20261013"
    prior = HERE.parent / "tt_re2_baselines_20261017"
    paths = (HERE / "runner.py", HERE / "test_runner.py", HERE / "RUNNER.md",
             HERE / "PROTOCOL.md", native / "native_models.py",
             native / "native_train.py", native / "native_data.py",
             native / "native_data_profile.py", SOURCE,
             prior / "tt_runner.py", prior / "re2_preprocessing.py")
    guard = ReadGuard(paths)
    return {str(p.relative_to(REPO)): guard.digest(p) for p in paths}


def input_paths():
    return [HERE / "artifacts/bundle.npz", HERE / "artifacts/input.json",
            HERE / "split.json"]


def input_hashes():
    guard = ReadGuard(input_paths())
    return {str(p.relative_to(HERE)): guard.digest(p) for p in input_paths()}


def validate_inputs(arrays, meta, expected_cases=(48, 24)):
    """Validate saved arrays only. Split/provenance audits belong to input-verify."""
    require(set(arrays) == ARRAY_KEYS, "Unexpected bundle keys")
    names = meta.get("services")
    require(isinstance(names, list) and len(names) >= 2 and
            all(isinstance(s, str) and s for s in names) and
            len(names) == len(set(names)), "Invalid ordered service inventory")
    require(tuple(meta.get("families", [])) == FAMILIES, "Metric family order changed")
    events = meta.get("event_count")
    require(type(events) is int and events >= 2, "Invalid event_count")
    nodes = len(names)
    labels = arrays["labels"]
    require(labels.dtype == np.int64 and labels.ndim == 1 and len(labels) > 0 and
            np.all((labels >= -1) & (labels < nodes)), "Invalid labels")
    count = len(labels)
    for key, shape in (("metrics", (count, nodes, 10, 8)),
                       ("traces", (count, nodes, 10, 2)),
                       ("logs", (count, nodes, events))):
        value = arrays[key]
        require(value.dtype == np.float32 and value.shape == shape,
                "Shape/dtype mismatch: " + key)
        if key != "metrics":
            require(np.isfinite(value).all(), "Nonfinite " + key)
    observed = arrays["metric_observed"]
    require(observed.dtype == np.bool_ and observed.shape == arrays["metrics"].shape,
            "Invalid metric_observed")
    require(not np.isinf(arrays["metrics"]).any() and
            np.isfinite(arrays["metrics"][observed]).all(),
            "Observed metrics must be finite; infinity is never allowed")
    require(np.all(arrays["traces"][..., 1] == 0), "Trace second channel changed")
    require(np.all(arrays["logs"] >= 0), "Negative Hawkes input")
    for key in ("case_ids", "partition", "starts", "indices"):
        value = arrays[key]
        require(value.shape == (count,), "Invalid provenance shape: " + key)
        require(value.dtype.kind in "US" if key in ("case_ids", "partition")
                else value.dtype == np.int64, "Invalid provenance dtype: " + key)
    require(arrays["case_ids"].dtype.kind == "U" and
            arrays["partition"].dtype.kind == "U", "Use Unicode provenance arrays")
    require(np.all(arrays["case_ids"] != "") and
            set(arrays["partition"]) == set(PARTS), "Invalid cases/partitions")
    require(len(np.unique(arrays["indices"])) == count and
            np.all(arrays["indices"] >= 0), "Indices must be unique nonnegative rows")
    parts = {p: np.flatnonzero(arrays["partition"] == p) for p in PARTS}
    case_sets = {p: set(arrays["case_ids"][parts[p]]) for p in PARTS}
    require(not case_sets["train"] & case_sets["validation"], "Case crosses partitions")
    require(tuple(len(case_sets[p]) for p in PARTS) == expected_cases,
            "Expected TRAIN48/validation24 cases")
    for case in np.unique(arrays["case_ids"]):
        positions = np.flatnonzero(arrays["case_ids"] == case)
        roots = set(labels[positions]) - {-1}
        require(len(roots) == 1, "Each case must retain one fault root: " + case)
        stamps = np.sort(arrays["starts"][positions])
        require(np.all(np.diff(stamps) >= 10), "Duplicate/overlapping case windows")
    # Absolute time overlap across parts is a stop, not permission to drop cases.
    train_starts = np.sort(arrays["starts"][parts["train"]])
    for stamp in arrays["starts"][parts["validation"]]:
        left = np.searchsorted(train_starts, stamp - 9)
        require(left == len(train_starts) or train_starts[left] > stamp + 9,
                "Cross-part absolute window overlap; input audit required")
    edges = arrays["edge_pairs"]
    require(edges.dtype == np.int64 and edges.ndim == 2 and edges.shape[1] == 2 and
            np.all((edges >= 0) & (edges < nodes)), "Invalid edge_pairs")
    pairs = set(map(tuple, edges.tolist()))
    require(len(pairs) == len(edges) and
            all((n, n) in pairs for n in range(nodes)), "Missing self-loop/duplicate edge")
    return parts


def load_inputs():
    guard = ReadGuard(input_paths())
    hashes = input_hashes()
    meta = guard.json(HERE / "artifacts/input.json")
    require(meta.get("bundle_sha256") == hashes["artifacts/bundle.npz"],
            "bundle_sha256 mismatch")
    require(meta.get("split_sha256") == hashes["split.json"], "split_sha256 mismatch")
    arrays = guard.arrays(HERE / "artifacts/bundle.npz")
    parts = validate_inputs(arrays, meta)
    require(input_hashes() == hashes, "Inputs changed while loading")
    return arrays, meta, parts, hashes


def prepare_partitions(arrays, parts):
    """Minimal float32-contract adapter of re2_preprocessing + native_train scaler."""
    require(set(parts) == set(PARTS) and all(len(v) for v in parts.values()),
            "Need nonempty TRAIN and validation")
    train = np.asarray(parts["train"])
    validation = np.asarray(parts["validation"])
    require(not set(train) & set(validation), "Scaler partition overlap")
    raw = arrays["metrics"].astype(np.float64)
    observed = arrays["metric_observed"]
    seen = observed[train]
    count = seen.sum(axis=(0, 2))
    total = np.where(seen, raw[train], 0.).sum(axis=(0, 2))
    mean = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
    supported = count > 0
    filled = np.where(observed, raw, mean[None, :, None, :])
    filled = np.where(supported[None, :, None, :], filled, 0.)
    prepared = dict(arrays, metrics=filled)
    stats = {"metric_impute_mean": mean, "metric_supported": supported,
             "metric_train_observed_count": count}
    for key in ("metrics", "traces"):
        value = prepared[key][train].astype(np.float64)
        avg, std = value.mean(axis=(0, 2)), value.std(axis=(0, 2), ddof=0)
        constant = np.all(value == value[:1, :, :1, :], axis=(0, 2))
        std[constant] = 0
        avg[constant] = np.broadcast_to(value[0, :, 0, :], avg.shape)[constant]
        stats.update({key + "_mean": avg, key + "_std": std,
                      key + "_constant": constant})
    data = {}
    for part, positions in parts.items():
        result = {k: arrays[k][positions] for k in
                  ("labels", "case_ids", "starts", "indices", "partition", "logs")}
        for key in ("metrics", "traces"):
            value = prepared[key][positions].astype(np.float64)
            result[key] = ((value - stats[key + "_mean"][None, :, None, :]) /
                           (stats[key + "_std"][None, :, None, :] + EPSILON)).astype(np.float32)
        require(all(np.isfinite(result[k]).all() for k in
                    ("metrics", "traces", "logs")), "Nonfinite prepared input")
        require(np.all(result["traces"][..., 1] == 0), "Trace zero channel changed")
        data[part] = result
    require(all(np.isfinite(v).all() for v in stats.values()), "Nonfinite scaler")
    report = {
        "fit_partition": "train", "epsilon": EPSILON, "ddof": 0, "clipping": False,
        "unsupported_train_node_channels": int((~supported).sum()),
        "validation_observed_cells_masked_as_unsupported": int(
            (observed[validation] & ~supported[None, :, None, :]).sum()),
        "missing_metric_cells": {
            p: int((~observed[idx]).sum()) for p, idx in parts.items()},
        "constant_channels": {k: int(stats[k + "_constant"].sum())
                              for k in ("metrics", "traces")},
    }
    return stats, data, report


def setup(seed):
    require(seed in SEEDS, "Seed must be 11, 23 or 37")
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dgl.seed(seed)


def model_for(meta):
    return NativeReference("diagmlp", len(meta["services"]), meta["event_count"],
                           metric_count=8, length=10, dropout=.1)


def graph_batch(data, positions, edges):
    nodes = data["metrics"].shape[1]
    graph = dgl.batch([dgl.graph((edges[:, 0], edges[:, 1]), num_nodes=nodes)
                       for _ in positions])
    for key in ("metrics", "traces", "logs"):
        values = data[key][positions]
        graph.ndata[key] = torch.from_numpy(values.reshape((-1,) + values.shape[2:]))
    return graph, torch.from_numpy(data["labels"][positions])


def predict(model, data, edges):
    model.eval()
    roots, detects = [], []
    with torch.no_grad():
        for start in range(0, len(data["labels"]), BATCH):
            idx = np.arange(start, min(start + BATCH, len(data["labels"])))
            graph, _ = graph_batch(data, idx, edges)
            root, detect = model(graph)
            roots.append(root.cpu())
            detects.append(detect.cpu())
    result = {key: data[key].copy() for key in PRED_KEYS - {"root_logits", "detection_logits"}}
    result.update(root_logits=torch.cat(roots).numpy(),
                  detection_logits=torch.cat(detects).numpy())
    require(np.isfinite(result["root_logits"]).all() and
            np.isfinite(result["detection_logits"]).all(), "Nonfinite predictions")
    return result


def full_losses(prediction):
    """Do not average batch joint losses: their fault denominators can differ."""
    labels = torch.from_numpy(prediction["labels"])
    root = torch.from_numpy(prediction["root_logits"])
    detect = torch.from_numpy(prediction["detection_logits"])
    faulty = labels >= 0
    detection = torch.nn.functional.cross_entropy(detect, faulty.long()).item()
    root_nll = (torch.nn.functional.cross_entropy(root[faulty], labels[faulty]).item()
                if faulty.any() else 0.)
    return {"joint_loss": .5 * detection + .5 * root_nll,
            "root_nll": root_nll if faulty.any() else None,
            "detection_ce": detection}


def expected_ranks(row, label):
    greater = int((row > row[label]).sum())
    ties = int((row == row[label]).sum())
    return [min(max(k - greater, 0), ties) / ties for k in (1, 3)] + [
        float(np.mean(1. / np.arange(greater + 1, greater + ties + 1)))]


def score(prediction, independent=False):
    """Fault-window expected ranks -> per-case mean -> equal-case mean."""
    roots = prediction["root_logits"].astype(np.float64)
    detects = prediction["detection_logits"].astype(np.float64)
    labels, cases = prediction["labels"], prediction["case_ids"]
    require(roots.ndim == 2 and detects.shape == (len(labels), 2) and
            roots.shape[0] == len(labels) and
            np.isfinite(roots).all() and np.isfinite(detects).all(), "Invalid logits")
    require(labels.dtype == np.int64 and np.all((labels >= -1) & (labels < roots.shape[1])),
            "Invalid scoring labels")
    faulty = labels >= 0
    detected = detects.argmax(axis=1) == 1
    positions = np.flatnonzero(faulty)
    credits = []
    for i in positions:
        if independent:
            # Independent enumeration of every possible tied true-label position.
            ordered = sorted(roots[i].tolist(), reverse=True)
            ranks = [r + 1 for r, value in enumerate(ordered) if value == roots[i, labels[i]]]
            credits.append([sum(r <= k for r in ranks) / len(ranks) for k in (1, 3)] +
                           [sum(1. / r for r in ranks) / len(ranks)])
        else:
            credits.append(expected_ranks(roots[i], labels[i]))
    credit = np.asarray(credits, dtype=np.float64).reshape(-1, 3)
    gated = credit * detected[positions, None]
    keys = ("top1", "top3", "mrr")

    def averages(values):
        return {k: float(values[:, j].mean()) if len(values) else None
                for j, k in enumerate(keys)}

    per_case = {}
    conditional_cases, gated_cases = [], []
    for case in sorted(set(cases.tolist())):
        mask = cases[positions] == case
        item = {"windows": int((cases == case).sum()), "fault_windows": int(mask.sum()),
                "conditional": averages(credit[mask]), "gated": averages(gated[mask])}
        per_case[case] = item
        if mask.any():
            conditional_cases.append(credit[mask].mean(axis=0))
            gated_cases.append(gated[mask].mean(axis=0))
    tp = int((faulty & detected).sum())
    fp = int((~faulty & detected).sum())
    fn = int((faulty & ~detected).sum())
    result = {
        "windows": len(labels), "fault_windows": len(positions),
        "fault_cases": len(conditional_cases), "cases": per_case,
        "conditional_case": averages(np.asarray(conditional_cases).reshape(-1, 3)),
        "conditional_window": averages(credit),
        "gated_case": averages(np.asarray(gated_cases).reshape(-1, 3)),
        "gated_window": averages(gated),
        "detection": {"tp": tp, "fp": fp, "fn": fn,
                      "tn": int((~faulty & ~detected).sum()),
                      "precision": tp / (tp + fp) if tp + fp else 0.,
                      "recall": tp / (tp + fn) if tp + fn else 0.,
                      "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.},
    }
    if independent:
        # Stable float64 CE, independent of torch joint_loss/full_losses.
        def ce(values, truth):
            shifted = values - values.max(axis=1, keepdims=True)
            logsum = np.log(np.exp(shifted).sum(axis=1))
            return float((logsum - shifted[np.arange(len(truth)), truth]).mean())
        det_ce = ce(detects, faulty.astype(np.int64))
        root_ce = ce(roots[faulty], labels[faulty]) if faulty.any() else 0.
        result.update(joint_loss=.5 * (det_ce + root_ce), detection_ce=det_ce,
                      root_nll=root_ce if faulty.any() else None)
    else:
        result.update(full_losses(prediction))
    return result


def select_epoch(history):
    require(len(history) > 0 and all(math.isfinite(r["validation_joint_loss"])
                                   for r in history), "Invalid selection history")
    return min(history, key=lambda r: (r["validation_joint_loss"], r["epoch"]))["epoch"]


def state_hash(model):
    h = hashlib.sha256()
    for key, value in sorted(model.state_dict().items()):
        array = value.detach().cpu().numpy()
        h.update(key.encode())
        h.update(str(array.dtype).encode())
        h.update(str(array.shape).encode())
        h.update(array.tobytes())
    return h.hexdigest()


def fixed_config(seed, meta):
    return {"seed": seed, "kind": "diagmlp", "epochs": EPOCHS, "batch_size": BATCH,
            "optimizer": {"name": "Adam", "lr": .001, "weight_decay": 0,
                          "betas": [.9, .999], "eps": 1e-8, "amsgrad": False},
            "alpha": .5, "device": "cpu", "threads": 2, "interop_threads": 1,
            "deterministic": True, "shuffle": "NumPy RandomState(seed), window permutation",
            "model": {"nodes": len(meta["services"]), "events": meta["event_count"],
                      "metric_count": 8, "length": 10, "dropout": .1},
            "selection": "minimum full-validation joint loss; earliest exact tie",
            "services": meta["services"], "tolerance": {"rtol": RTOL, "atol": ATOL}}


def run_folder(seed):
    require(seed in SEEDS, "Invalid seed")
    return safe_path(HERE / "runs" / ("seed_" + str(seed)))


def make_run(seed):
    folder = run_folder(seed)
    safe_path(folder.parent).mkdir(exist_ok=True)
    folder.mkdir(exist_ok=False)
    return folder


def save_model(path, model, epoch, loss, config_hash, updates):
    write_checkpoint(path, {"state_dict": model.state_dict(), "epoch": epoch,
                            "validation_joint_loss": loss, "updates": updates,
                            "state_sha256": state_hash(model),
                            "config_sha256": config_hash})


def fit(seed):
    """Production budget is fixed; no data/epoch/model/output override exists."""
    started = time.perf_counter()
    cpu_started = time.process_time()
    setup(seed)
    require(not run_folder(seed).exists(), "Refusing existing seed folder")
    arrays, meta, parts, hashes = load_inputs()
    sources = source_hashes()
    stats, data, preprocessing = prepare_partitions(arrays, parts)
    model = model_for(meta)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=0)
    folder = make_run(seed)
    try:
        write_json(folder / "sources.json", sources)
        write_json(folder / "inputs.json", {"hashes": hashes, "metadata": meta})
        write_arrays(folder / "scaler.npz", stats)
        config = dict(fixed_config(seed, meta), preprocessing=preprocessing,
                      model_native=model.config, initial_state_sha256=state_hash(model),
                      input_hashes=hashes, source_hashes=sources,
                      parameters=sum(p.numel() for p in model.parameters()),
                      versions={"python": sys.version, "numpy": np.__version__,
                                "torch": torch.__version__, "dgl": dgl.__version__},
                      pid=os.getpid(), protected_observations_opened=False)
        write_json(folder / "config.json", config)
        config_hash = ReadGuard([folder / "config.json"]).digest(folder / "config.json")
        save_model(folder / "initial.pt", model, 0, None, config_hash, 0)
        history, best_state, best = [], None, float("inf")
        shuffle = np.random.RandomState(seed)
        total_updates = 0
        training_started = time.perf_counter()
        for epoch in range(1, EPOCHS + 1):
            epoch_started = time.perf_counter()
            model.train()
            order = shuffle.permutation(len(data["train"]["labels"]))
            online, updates = 0., 0
            for start in range(0, len(order), BATCH):
                idx = order[start:start + BATCH]
                graph, labels = graph_batch(data["train"], idx, arrays["edge_pairs"])
                optimizer.zero_grad()
                root, detect = model(graph)
                loss = joint_loss(root, detect, labels, alpha=.5)
                require(bool(torch.isfinite(loss)), "Nonfinite training loss")
                loss.backward()
                require(all(p.grad is None or bool(torch.isfinite(p.grad).all())
                            for p in model.parameters()), "Nonfinite gradients")
                optimizer.step()
                online += loss.item() * len(idx)
                updates += 1
            prediction = predict(model, data["validation"], arrays["edge_pairs"])
            metrics = score(prediction)
            total_updates += updates
            row = {"epoch": epoch, "train_online_joint": online / len(order),
                   "validation_joint_loss": metrics["joint_loss"],
                   "validation_root_nll": metrics["root_nll"],
                   "validation_detection_ce": metrics["detection_ce"],
                   "validation_detection": metrics["detection"],
                   "validation_case_top1": metrics["conditional_case"]["top1"],
                   "validation_window_top1": metrics["conditional_window"]["top1"],
                   "updates": updates, "cumulative_updates": total_updates,
                   "seconds": time.perf_counter() - epoch_started,
                   "elapsed_seconds": time.perf_counter() - started}
            history.append(row)
            write_json(folder / ("epoch_{:03d}.json".format(epoch)), row)
            if metrics["joint_loss"] < best:
                best = metrics["joint_loss"]
                best_state = copy.deepcopy(model.state_dict())
            print("RE2_OB_EPOCH", seed, epoch, row["validation_joint_loss"], flush=True)
        training_seconds = time.perf_counter() - training_started
        best_epoch = select_epoch(history)
        save_model(folder / "final.pt", model, EPOCHS, history[-1]["validation_joint_loss"],
                   config_hash, total_updates)
        if best_state is None:
            raise ValueError("No finite selected state")
        model.load_state_dict(best_state)
        save_model(folder / "best.pt", model, best_epoch, best, config_hash,
                   history[best_epoch - 1]["cumulative_updates"])
        write_json(folder / "history.json", history)
        metrics = {}
        for tag in ("best", "final"):
            checkpoint = ReadGuard([folder / (tag + ".pt")]).checkpoint(folder / (tag + ".pt"))
            model.load_state_dict(checkpoint["state_dict"])
            metrics[tag] = {}
            for part in PARTS:
                prediction = predict(model, data[part], arrays["edge_pairs"])
                write_arrays(folder / (tag + "_" + part + ".npz"), prediction)
                metrics[tag][part] = score(prediction)
        require(source_hashes() == sources and input_hashes() == hashes,
                "Source/input changed during fit")
        files = [p for p in folder.iterdir() if p.is_file()]
        guard = ReadGuard(files)
        summary = {"status": "FIT_COMPLETE_REPLAY_REQUIRED", "seed": seed,
                   "epochs": EPOCHS, "updates": total_updates, "best_epoch": best_epoch,
                   "best_near_end": best_epoch >= math.ceil(.9 * EPOCHS),
                   "budget_limited": best_epoch >= math.ceil(.9 * EPOCHS),
                   "last20_validation_joint": [r["validation_joint_loss"] for r in history[-20:]],
                   "train_online_minus_validation_final":
                       history[-1]["train_online_joint"] - history[-1]["validation_joint_loss"],
                   "metrics": metrics, "pid": os.getpid(),
                   "seconds": time.perf_counter() - started,
                   "training_validation_seconds": training_seconds,
                   "process_cpu_seconds": time.process_time() - cpu_started,
                   "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "protected_observations_opened": False,
                   "hashes": {p.name: guard.digest(p) for p in files}}
        write_json(folder / "summary.json", summary)
        print("RE2_OB_FIT_COMPLETE", seed, "pid=" + str(os.getpid()), flush=True)
        return summary
    except Exception as error:
        write_json(folder / "failure.json",
                   {"type": type(error).__name__, "message": str(error), "pid": os.getpid(),
                    "recovery": "Keep failed folder; no overwrite/resume/automatic extension. "
                                "Report cause and obtain a new-path decision before retry."})
        raise


def assert_close(actual, expected, label="metrics"):
    """Recursive tolerant numeric comparison; provenance is compared exactly elsewhere."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), label + " keys")
        for key in expected:
            assert_close(actual[key], expected[key], label + "." + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + " length")
        for i, value in enumerate(expected):
            assert_close(actual[i], value, label + "." + str(i))
    elif type(expected) is float:
        require(type(actual) in (float, int) and math.isfinite(actual) and
                math.isclose(actual, expected, rel_tol=RTOL, abs_tol=ATOL), label + " mismatch")
    else:
        require(actual == expected, label + " mismatch")


def run_files():
    return ({"sources.json", "inputs.json", "scaler.npz", "config.json", "initial.pt",
             "best.pt", "final.pt", "history.json"} |
            {"epoch_{:03d}.json".format(e) for e in range(1, EPOCHS + 1)} |
            {tag + "_" + part + ".npz" for tag in ("best", "final") for part in PARTS})


def validate_history(history, train_windows):
    require(len(history) == EPOCHS, "Need exactly 200 history rows")
    updates = math.ceil(train_windows / BATCH)
    previous = 0.
    for epoch, row in enumerate(history, 1):
        require(row["epoch"] == epoch and row["updates"] == updates and
                row["cumulative_updates"] == epoch * updates, "History budget/update mismatch")
        for key in ("train_online_joint", "validation_joint_loss", "validation_root_nll",
                    "validation_detection_ce", "validation_case_top1", "validation_window_top1",
                    "seconds", "elapsed_seconds"):
            require(isinstance(row[key], (float, int)) and math.isfinite(row[key]) and
                    row[key] >= 0, "Invalid history numeric " + key)
        require(row["elapsed_seconds"] >= previous and
                row["elapsed_seconds"] >= row["seconds"], "Invalid elapsed time")
        previous = row["elapsed_seconds"]
        assert_close(row["validation_joint_loss"],
                     .5 * (row["validation_root_nll"] + row["validation_detection_ce"]))
    return select_epoch(history)


def verify(seed):
    """Separate CLI invocation; no optimizer construction or optimization."""
    setup(seed)
    folder = run_folder(seed)
    allowed = [folder / name for name in run_files() | {"summary.json"}]
    guard = ReadGuard(allowed)
    summary_hash = guard.digest(folder / "summary.json")
    summary = guard.json(folder / "summary.json")
    require(summary["status"] == "FIT_COMPLETE_REPLAY_REQUIRED" and summary["seed"] == seed,
            "Not a completed matching fit")
    require(summary["pid"] != os.getpid(), "verify requires a separate process from fit")
    require(set(summary["hashes"]) == run_files(), "Unexpected run hash inventory")
    for name, expected in summary["hashes"].items():
        require(guard.digest(folder / name) == expected, "Run hash mismatch: " + name)
    config = guard.json(folder / "config.json")
    arrays, meta, parts, hashes = load_inputs()
    require(config["input_hashes"] == hashes and config["source_hashes"] == source_hashes(),
            "Source/input hash mismatch")
    require(guard.json(folder / "sources.json") == config["source_hashes"], "Source manifest mismatch")
    require(guard.json(folder / "inputs.json") == {"hashes": hashes, "metadata": meta},
            "Input manifest mismatch")
    for key, value in fixed_config(seed, meta).items():
        require(config[key] == value, "Fixed configuration changed: " + key)
    stats, data, preprocessing = prepare_partitions(arrays, parts)
    saved_stats = guard.arrays(folder / "scaler.npz")
    require(set(stats) == set(saved_stats), "Scaler keys differ")
    for key in stats:
        np.testing.assert_array_equal(stats[key], saved_stats[key])
    require(config["preprocessing"] == preprocessing, "Preprocessing report changed")
    history = guard.json(folder / "history.json")
    best_epoch = validate_history(history, len(parts["train"]))
    require(summary["epochs"] == EPOCHS and summary["best_epoch"] == best_epoch and
            summary["updates"] == history[-1]["cumulative_updates"], "Summary budget mismatch")
    require(summary["budget_limited"] == (best_epoch >= math.ceil(.9 * EPOCHS)) and
            summary["best_near_end"] == summary["budget_limited"], "Budget caveat mismatch")
    for row in history:
        require(guard.json(folder / ("epoch_{:03d}.json".format(row["epoch"]))) == row,
                "Per-epoch history mismatch")
    model = model_for(meta)
    initial = guard.checkpoint(folder / "initial.pt")
    require(initial["epoch"] == 0 and initial["updates"] == 0 and
            initial["validation_joint_loss"] is None and
            state_hash(model) == initial["state_sha256"] == config["initial_state_sha256"],
            "Deterministic initial state mismatch")
    config_hash = guard.digest(folder / "config.json")
    require(initial["config_sha256"] == config_hash, "Initial config hash mismatch")
    model.load_state_dict(initial["state_dict"])
    require(state_hash(model) == initial["state_sha256"], "Initial tensor hash mismatch")
    replay_metrics = {}
    for tag, epoch in (("best", best_epoch), ("final", EPOCHS)):
        checkpoint = guard.checkpoint(folder / (tag + ".pt"))
        row = history[epoch - 1]
        require(checkpoint["config_sha256"] == config_hash and checkpoint["epoch"] == epoch and
                checkpoint["updates"] == row["cumulative_updates"] and
                checkpoint["validation_joint_loss"] == row["validation_joint_loss"],
                "Checkpoint selection/config/history mismatch")
        model.load_state_dict(checkpoint["state_dict"])
        require(state_hash(model) == checkpoint["state_sha256"], "Checkpoint tensor hash mismatch")
        replay_metrics[tag] = {}
        for part in PARTS:
            saved = guard.arrays(folder / (tag + "_" + part + ".npz"))
            require(set(saved) == PRED_KEYS, "Prediction keys changed")
            replay = predict(model, data[part], arrays["edge_pairs"])
            for key in PRED_KEYS:
                if key.endswith("logits"):
                    np.testing.assert_allclose(replay[key], saved[key], rtol=RTOL, atol=ATOL)
                else:
                    np.testing.assert_array_equal(replay[key], saved[key])
            independent = score(replay, independent=True)
            assert_close(independent, summary["metrics"][tag][part])
            replay_metrics[tag][part] = independent
            if part == "validation":
                assert_close(independent["joint_loss"], row["validation_joint_loss"])
                assert_close(independent["root_nll"], row["validation_root_nll"])
                assert_close(independent["detection_ce"], row["validation_detection_ce"])
                assert_close(independent["conditional_case"]["top1"], row["validation_case_top1"])
                assert_close(independent["conditional_window"]["top1"], row["validation_window_top1"])
                require(independent["fault_cases"] == len(set(data[part]["case_ids"])),
                        "Missing validation fault case")
    require(source_hashes() == config["source_hashes"] and input_hashes() == hashes,
            "Source/input mutated during verification")
    for name, expected in summary["hashes"].items():
        require(guard.digest(folder / name) == expected, "Run mutated during verification")
    require(guard.digest(folder / "summary.json") == summary_hash, "Summary mutated")
    report = {"status": "PASS", "seed": seed, "pid": os.getpid(), "fit_pid": summary["pid"],
              "predictions_replayed": 4, "best_epoch": best_epoch,
              "budget_limited": summary["budget_limited"], "metrics": replay_metrics,
              "tolerance": {"rtol": RTOL, "atol": ATOL},
              "protected_observations_opened": False}
    write_json(folder / "verification.json", report)
    print("RE2_OB_VERIFY_PASS", seed, "pid=" + str(os.getpid()), flush=True)
    return report


def check():
    """Optional input-contract check; never creates a model or fits anything."""
    arrays, meta, parts, hashes = load_inputs()
    _, _, report = prepare_partitions(arrays, parts)
    require(input_hashes() == hashes, "Inputs mutated during check")
    return {"status": "PASS_INPUT_CONTRACT_ONLY", "input_hashes": hashes,
            "services": meta["services"], "preprocessing": report,
            "protected_observations_opened": False,
            "limitation": "Not the upstream split/provenance/input-verify approval."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("fit", "verify"):
        sub.add_parser(action).add_argument("--seed", type=int, choices=SEEDS, required=True)
    sub.add_parser("check")
    args = parser.parse_args(argv)
    if args.action == "fit":
        result = fit(args.seed)
    elif args.action == "verify":
        result = verify(args.seed)
    else:
        result = check()
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
