"""Matched local/relative root rankers; development partitions only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import tempfile
import time

import numpy as np
import torch
from torch.nn import functional as F

from ranker import Ranker

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
SEEDS = (11, 23, 37)
SETTINGS = {"epochs": 200, "patience": 30, "batch_size": 32,
            "learning_rate": 1e-3, "weight_decay": 1e-4, "threads": 2}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def source_hashes():
    return {name: sha(HERE / name) for name in ("PROTOCOL.md", "train.py", "ranker.py", "features.py")}


def load_data(system):
    path = HERE / "features" / (system + ".npz")
    with np.load(path, allow_pickle=False) as saved:
        data = {key: saved[key] for key in saved.files}
    expected = {"x", "mask", "coverage", "labels", "indices", "event_ids", "partition"}
    if set(data) != expected:
        raise ValueError("Feature archive keys differ from the frozen contract")
    split_path = NATIVE / "calibration200" / system / "diagmlp/seed_11/split.json"
    split = json.loads(split_path.read_text())["indices"]
    meta_path = NATIVE / "native_inputs" / system / "metadata.json"
    meta = json.loads(meta_path.read_text())
    rows, nodes, features = data["x"].shape
    if nodes != len(meta["services"]) or features != 18 or rows == 0:
        raise ValueError("Candidate/feature count mismatch")
    if data["x"].dtype != np.float32 or not np.isfinite(data["x"]).all():
        raise ValueError("Invalid feature values")
    if data["mask"].dtype != np.bool_ or data["mask"].shape != data["x"].shape:
        raise ValueError("Invalid observation masks")
    if np.any(data["x"][~data["mask"]] != 0):
        raise ValueError("Missing feature slots must be zero with a separate mask")
    q = data["coverage"]
    if q.shape != data["x"].shape or not np.isfinite(q).all() or np.any((q < 0) | (q > 1)):
        raise ValueError("Invalid observed-second coverage")
    for key in ("labels", "indices", "event_ids", "partition"):
        if data[key].shape != (rows,):
            raise ValueError("Invalid row metadata: " + key)
    if data["labels"].dtype != np.int64 or data["indices"].dtype != np.int64:
        raise ValueError("Labels/indices must be int64")
    ids = data["indices"]
    if len(set(ids.tolist())) != rows or set(data["partition"].tolist()) != {"train", "validation"}:
        raise ValueError("Duplicate indices or forbidden partition")
    for part in ("train", "validation"):
        if set(ids[data["partition"] == part].tolist()) != set(split[part]):
            raise ValueError("Frozen " + part + " partition changed")
    if set(ids.tolist()) & set(split["test"] + split["unassigned"]):
        raise ValueError("Held-out indices entered development")
    with np.load(NATIVE / "native_inputs" / system / "raw.npz", allow_pickle=False) as native:
        if not np.array_equal(data["labels"], native["labels"][ids]):
            raise ValueError("Native root labels changed")
    events = np.asarray([meta["windows"][int(i)]["event_id"] or "" for i in ids])
    if not np.array_equal(data["event_ids"], events):
        raise ValueError("Incident provenance changed")
    if np.any((data["labels"] < -1) | (data["labels"] >= nodes)):
        raise ValueError("Root labels outside candidate inventory")
    if np.any((data["labels"] >= 0) & (data["event_ids"] == "")):
        raise ValueError("Fault window without an incident")
    provenance = {"features": sha(path), "split": sha(split_path), "metadata": sha(meta_path)}
    return data, meta, provenance


def fit_standardizer(x, mask, training):
    values = x[training].astype(np.float64)
    valid = mask[training]
    counts = valid.sum(axis=(0, 1))
    mean = np.where(valid, values, 0).sum(axis=(0, 1)) / np.maximum(counts, 1)
    variance = np.where(valid, (values - mean) ** 2, 0).sum(axis=(0, 1)) / np.maximum(counts, 1)
    std = np.sqrt(variance)
    std[std <= 1e-12] = 1
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise ValueError("Nonfinite training-only standardizer")
    return {"mean": mean, "std": std, "counts": counts}


def transform(x, mask, stats):
    normalized = np.where(mask, (x.astype(np.float64) - stats["mean"]) / stats["std"], 0)
    result = normalized.astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite standardized input")
    return result


def event_weights(event_ids):
    if len(event_ids) == 0 or any(not event for event in event_ids):
        raise ValueError("Expected nonempty labelled incident identities")
    counts = Counter(event_ids.tolist())
    return np.asarray([len(event_ids) / (len(counts) * counts[event]) for event in event_ids],
                      dtype=np.float32)


def score(logits, labels, events):
    if logits.ndim != 2 or len(logits) != len(labels) or not np.isfinite(logits).all():
        raise ValueError("Invalid prediction matrix")
    target = logits[np.arange(len(labels)), labels]
    greater = (logits > target[:, None]).sum(axis=1)
    ties = (logits == target[:, None]).sum(axis=1)
    credit = np.where(greater == 0, 1 / ties, 0)
    unique = (greater == 0) & (ties == 1)
    groups = {str(event): float(credit[events == event].mean()) for event in np.unique(events)}
    return {"window_top1": float(credit.mean()),
            "event_balanced_top1": float(np.mean(list(groups.values()))),
            "unique_window_top1": float(unique.mean()),
            "windows": len(labels), "incidents": len(groups),
            "correct_root_tied_at_top": int(((greater == 0) & (ties > 1)).sum()),
            "by_incident": groups}


def fit_model(model, tensors, labels, train_rows, val_rows, train_weights, val_weights,
              seed, settings):
    train_rows = torch.as_tensor(train_rows, dtype=torch.long)
    val_rows = torch.as_tensor(val_rows, dtype=torch.long)
    optimizer = torch.optim.Adam(model.parameters(), lr=settings["learning_rate"],
                                 weight_decay=settings["weight_decay"])
    order_rng = np.random.RandomState(seed)
    best_loss, best_epoch, best_state = float("inf"), 0, None
    history = []
    for epoch in range(1, settings["epochs"] + 1):
        model.train()
        weighted_sum = 0.0
        order = order_rng.permutation(len(train_rows))
        for start in range(0, len(order), settings["batch_size"]):
            local = torch.as_tensor(order[start:start + settings["batch_size"]], dtype=torch.long)
            rows = train_rows[local]
            optimizer.zero_grad()
            losses = F.cross_entropy(model(*(value[rows] for value in tensors)), labels[rows],
                                     reduction="none")
            loss = (losses * train_weights[local]).mean()
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite training loss")
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise ValueError("Nonfinite model gradient")
            optimizer.step()
            weighted_sum += float(loss.detach()) * len(local)
        model.eval()
        with torch.no_grad():
            predictions = model(*(value[val_rows] for value in tensors))
            loss = (F.cross_entropy(predictions, labels[val_rows], reduction="none") * val_weights).mean()
        validation_loss = float(loss)
        if not np.isfinite(validation_loss):
            raise ValueError("Nonfinite validation loss")
        history.append({"epoch": epoch, "train_event_ce": weighted_sum / len(train_rows),
                        "validation_event_ce": validation_loss})
        if validation_loss < best_loss:
            best_loss, best_epoch = validation_loss, epoch
            best_state = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
        if epoch == 1 or epoch % 25 == 0:
            print("EPOCH", epoch, "validation_event_ce", validation_loss, flush=True)
        if epoch - best_epoch >= settings["patience"]:
            break
    if best_state is None:
        raise AssertionError("No finite checkpoint selected")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        predictions = model(*(value[val_rows] for value in tensors)).numpy()
    return predictions, history, best_epoch, best_loss


def run(system, mode, seed, bundle=None):
    start = time.perf_counter()
    data, metadata, provenance = load_data(system) if bundle is None else bundle
    sources = source_hashes()
    target = HERE / "runs" / system / mode / ("seed_" + str(seed))
    if target.exists():
        raise FileExistsError("Never overwrite an existing experiment: " + str(target))
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    train_all = np.flatnonzero(data["partition"] == "train")
    train_rows = np.flatnonzero((data["partition"] == "train") & (data["labels"] >= 0))
    val_rows = np.flatnonzero((data["partition"] == "validation") & (data["labels"] >= 0))
    stats = fit_standardizer(data["x"], data["mask"], train_all)
    tensors = (torch.from_numpy(transform(data["x"], data["mask"], stats)),
               torch.from_numpy(data["mask"]), torch.from_numpy(data["coverage"]))
    labels = torch.from_numpy(data["labels"])
    train_weights = torch.from_numpy(event_weights(data["event_ids"][train_rows]))
    val_weights = torch.from_numpy(event_weights(data["event_ids"][val_rows]))
    model = Ranker(data["x"].shape[-1], relative=(mode == "relative"))
    initial = {name: value.detach().clone() for name, value in model.state_dict().items()}
    predictions, history, best_epoch, best_loss = fit_model(
        model, tensors, labels, train_rows, val_rows, train_weights, val_weights, seed, SETTINGS)
    config = {"system": system, "mode": mode, "seed": seed, "settings": SETTINGS,
              "feature_dim": data["x"].shape[-1], "services": metadata["services"],
              "parameter_count": sum(p.numel() for p in model.parameters()),
              "input_hashes": provenance, "source_hashes": sources,
              "train_indices": data["indices"][train_rows].tolist(),
              "validation_indices": data["indices"][val_rows].tolist(),
              "normalization_train_indices": data["indices"][train_all].tolist(),
              "test_evaluated": False, "rcaeval_access": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(tempfile.mkdtemp(prefix="." + target.name + ".partial_", dir=str(target.parent)))
    dump(partial / "config.json", config)
    dump(partial / "history.json", history)
    np.savez_compressed(partial / "standardizer.npz", **stats)
    torch.save({"state_dict": model.state_dict(), "initial_state_dict": initial,
                "config_sha256": sha(partial / "config.json")}, partial / "checkpoint.pt")
    checkpoint = torch.load(partial / "checkpoint.pt", map_location="cpu")
    replay = Ranker(config["feature_dim"], relative=(mode == "relative"))
    replay.load_state_dict(checkpoint["state_dict"])
    replay.eval()
    with torch.no_grad():
        replayed = replay(*(value[torch.from_numpy(val_rows)] for value in tensors)).numpy()
    if not np.array_equal(predictions, replayed):
        raise AssertionError("Saved checkpoint replay mismatch")
    np.savez_compressed(partial / "predictions.npz", logits=predictions,
                        labels=data["labels"][val_rows], indices=data["indices"][val_rows],
                        event_ids=data["event_ids"][val_rows])
    if sources != source_hashes() or provenance["features"] != sha(HERE / "features" / (system + ".npz")):
        raise ValueError("Code or input changed during training; partial output retained")
    report = {"status": "complete", "system": system, "mode": mode, "seed": seed,
              "best_epoch": best_epoch, "epochs_run": len(history), "best_event_ce": best_loss,
              "seconds": time.perf_counter() - start, "parameter_count": config["parameter_count"],
              "train_windows": len(train_rows), "train_incidents": len(set(data["event_ids"][train_rows])),
              "metrics": score(predictions, data["labels"][val_rows], data["event_ids"][val_rows]),
              "checkpoint_replay_equal": True,
              "artifact_hashes": {name: sha(partial / name) for name in
                                 ("config.json", "history.json", "standardizer.npz",
                                  "checkpoint.pt", "predictions.npz")}}
    dump(partial / "report.json", report)
    partial.rename(target)
    print("METHOD_RUN_COMPLETE", system, mode, seed, json.dumps(report["metrics"]), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-all", action="store_true")
    parser.add_argument("--system", choices=("SN", "TT"))
    parser.add_argument("--mode", choices=("local", "relative"))
    parser.add_argument("--seed", type=int, choices=SEEDS)
    args = parser.parse_args()
    gate = json.loads((HERE / "implementation_gate.json").read_text())
    if gate.get("status") != "PASS":
        raise ValueError("Real feature/model integration gate has not passed")
    torch.set_num_threads(SETTINGS["threads"])
    torch.set_num_interop_threads(1)
    if args.run_all:
        if any(value is not None for value in (args.system, args.mode, args.seed)):
            parser.error("--run-all cannot be mixed with single-run arguments")
        for system in ("SN", "TT"):
            bundle = load_data(system)
            for seed in SEEDS:
                for mode in ("local", "relative"):
                    run(system, mode, seed, bundle)
        print("METHOD_MATRIX_COMPLETE", flush=True)
    elif None not in (args.system, args.mode, args.seed):
        run(args.system, args.mode, args.seed)
    else:
        parser.error("Choose --run-all or all of --system/--mode/--seed")


if __name__ == "__main__":
    main()
