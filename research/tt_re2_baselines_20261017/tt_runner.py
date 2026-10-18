"""Fixed TT window baseline; only preselected TRAIN/validation arrays are opened."""
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
REPO = HERE.parents[1]
NATIVE = HERE.parent / "native_reproduction_20261013"
INPUT = HERE.parent / "tt_native_support_20261014/artifacts"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(NATIVE))
from native_models import NativeReference, SOURCE, joint_loss, native_scores
from native_train import fit_scaler, scaled_partition, graph_batch, validation_predictions
from native_train import validate_inputs
from research.method_mlp_20261013.features import original_split

HASHES = {
    "TT.npz": "2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597",
    "TT.json": "07c3ad8ae9331dc4d48b0e4a728e34a9d5bf2c87c985d8792d9d50220f355948",
}
SEEDS = (11, 23, 37)
KINDS = ("eadro", "diagmlp")
EPOCHS, BATCH = 50, 256


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf8") as stream:
        stream.write(payload)


def sources():
    paths = [Path(__file__), HERE / "test_tt_runner.py", HERE / "TT_PROTOCOL.md",
             NATIVE / "native_models.py", NATIVE / "native_train.py", SOURCE,
             REPO / "research/method_mlp_20261013/features.py"]
    return {str(path): digest(path) for path in paths}


def selected_positions(indices):
    original = original_split(5814)
    assert indices.dtype == np.int64 and len(indices) == len(set(indices.tolist())) == 4069
    lookup = {int(value): pos for pos, value in enumerate(indices)}
    allowed = set(original["train"]) | set(original["validation"])
    assert set(lookup) == allowed
    assert not set(lookup) & (set(original["test"]) | set(original["unassigned"]))
    return {name: np.array([lookup[int(i)] for i in original[name]], dtype=np.int64)
            for name in ("train", "validation")}


def load_selected():
    assert {name: digest(INPUT / name) for name in HASHES} == HASHES
    meta = json.loads((INPUT / "TT.json").read_text())
    with np.load(INPUT / "TT.npz", allow_pickle=False) as saved:
        arrays = {key: saved[key] for key in
                  ("metrics", "traces", "logs", "labels", "indices", "event_ids")}
    validate_inputs(arrays, meta, "TT")
    parts = selected_positions(arrays["indices"])
    assert {key: len(value) for key, value in parts.items()} == {"train": 3256, "validation": 813}
    for index, window in enumerate(meta["windows"]):
        event = window["event_id"] or ""
        assert event == arrays["event_ids"][index]
        assert arrays["labels"][index] == (meta["faults"][event]["root"] if event else -1)
    assert {name: digest(INPUT / name) for name in HASHES} == HASHES
    return arrays, meta, parts


def setup(seed):
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dgl.seed(seed)


def common_initial_hash(model):
    h = hashlib.sha256()
    prefixes = ("core.encoder.metric_model.", "core.encoder.trace_model.",
                "core.encoder.log_model.", "core.locator.", "core.detector.")
    tensors = 0
    for key, value in sorted(model.state_dict().items()):
        if key.startswith(prefixes):
            h.update(key.encode())
            h.update(value.detach().cpu().numpy().tobytes())
            tensors += 1
    assert tensors > 10
    return {"sha256": h.hexdigest(), "tensors": tensors}


def score(root, detection, labels):
    result = native_scores(root, detection, labels)
    result["precision"] = result["tp"] / (result["tp"] + result["fp"]) if result["tp"] + result["fp"] else 0.0
    result["recall"] = result["tp"] / (result["tp"] + result["fn"]) if result["tp"] + result["fn"] else 0.0
    x, y = root.detach().cpu().numpy().astype(np.float64), labels.cpu().numpy()
    d = detection.detach().argmax(dim=1).cpu().numpy()
    fault = y >= 0
    if not fault.any():
        for k in (1, 3, 5):
            result["conditional_top" + str(k)] = None
            result["end_to_end_top" + str(k)] = None
        result["root_window_nll"] = None
        return result
    x, y, d = x[fault], y[fault], d[fault]
    truth = x[np.arange(len(y)), y, None]
    greater, ties = (x > truth).sum(axis=1), (x == truth).sum(axis=1)
    for k in (1, 3, 5):
        credit = np.minimum(np.maximum(k - greater, 0), ties) / ties
        result["conditional_top" + str(k)] = float(credit.mean())
        result["end_to_end_top" + str(k)] = float((credit * d).mean())
    shifted = x - x.max(axis=1, keepdims=True)
    lp = shifted - np.logaddexp.reduce(shifted, axis=1, keepdims=True)
    result["root_window_nll"] = float(-lp[np.arange(len(y)), y].mean())
    assert all(v is None or np.isfinite(v) for v in result.values())
    return result


def make_data(arrays, parts):
    stats = fit_scaler(arrays, parts["train"])
    return stats, {name: scaled_partition(arrays, idx, stats) for name, idx in parts.items()}


def fit(kind, seed):
    setup(seed)
    arrays, meta, parts = load_selected()
    stats, data = make_data(arrays, parts)
    model = NativeReference(kind, 27, 60)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    folder = HERE / "tt_runs" / kind / ("seed_" + str(seed))
    folder.mkdir(parents=True, exist_ok=False)
    np.savez(folder / "scaler.npz", **stats)
    config = {
        "kind": kind, "seed": seed, "epochs": EPOCHS, "batch": BATCH, "lr": .001,
        "model": model.config, "inputs": HASHES, "sources": sources(),
        "positions": {k: v.tolist() for k, v in parts.items()},
        "original_indices": {k: arrays["indices"][v].tolist() for k, v in parts.items()},
        "common_initial": common_initial_hash(model),
        "scaler_sha256": digest(folder / "scaler.npz"),
        "selection": "minimum validation joint loss, earliest tie",
        "protected_observations_opened": False,
        "versions": {"python": sys.version, "numpy": np.__version__,
                     "torch": torch.__version__, "dgl": dgl.__version__},
    }
    dump(folder / "config.json", config)
    config_hash, source_hashes = digest(folder / "config.json"), sources()
    history, best, best_epoch = [], float("inf"), None
    shuffle = np.random.RandomState(seed)
    started = time.perf_counter()
    for epoch in range(1, EPOCHS + 1):
        epoch_start = time.perf_counter()
        model.train()
        order = shuffle.permutation(len(parts["train"]))
        total, updates = 0.0, 0
        for start in range(0, len(order), BATCH):
            batch = order[start:start + BATCH]
            graph, labels = graph_batch(data["train"], batch, meta)
            optimizer.zero_grad()
            root, detection = model(graph)
            loss = joint_loss(root, detection, labels)
            assert torch.isfinite(loss)
            loss.backward()
            assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
            optimizer.step()
            total += loss.item() * len(batch)
            updates += 1
        root, detection, labels, validation_loss = validation_predictions(
            model, data["validation"], meta, BATCH)
        assert math.isfinite(validation_loss) and updates == 13
        row = {"epoch": epoch, "train_joint_loss": total / len(order),
               "validation_joint_loss": validation_loss, "updates": updates,
               "validation": score(root, detection, labels),
               "seconds": time.perf_counter() - epoch_start}
        history.append(row)
        dump(folder / ("epoch_{:03d}.json".format(epoch)), row)
        if validation_loss < best:
            best, best_epoch = validation_loss, epoch
            torch.save({"model": model.state_dict(), "epoch": epoch,
                        "validation_joint_loss": best, "config_sha256": config_hash},
                       folder / "best.pt")
        print("TT_EPOCH", kind, seed, epoch, validation_loss, flush=True)
    training_seconds = time.perf_counter() - started
    torch.save({"model": model.state_dict(), "epoch": EPOCHS,
                "validation_joint_loss": history[-1]["validation_joint_loss"],
                "config_sha256": config_hash},
               folder / "last.pt")
    dump(folder / "history.json", history)
    metrics = {}
    for tag in ("best", "last"):
        checkpoint = torch.load(folder / (tag + ".pt"), map_location="cpu")
        model.load_state_dict(checkpoint["model"])
        metrics[tag] = {"epoch": checkpoint["epoch"]}
        for part in parts:
            root, detection, labels, loss = validation_predictions(model, data[part], meta, BATCH)
            metrics[tag][part] = dict(score(root, detection, labels), joint_loss=loss)
            if part == "validation":
                assert loss == checkpoint["validation_joint_loss"]
            path = folder / (tag + "_" + part + ".npz")
            with path.open("xb") as stream:
                np.savez(stream, root_logits=root.numpy(), detection_logits=detection.numpy(),
                         labels=labels.numpy(), indices=arrays["indices"][parts[part]],
                         event_ids=arrays["event_ids"][parts[part]])
            # Recreate the model; predictions must not depend on training-mode state.
            replay = NativeReference(kind, 27, 60)
            replay.load_state_dict(checkpoint["model"])
            rr, dd, yy, ll = validation_predictions(replay, data[part], meta, BATCH)
            assert torch.equal(root, rr) and torch.equal(detection, dd) and torch.equal(labels, yy)
            assert loss == ll
    assert source_hashes == sources()
    assert best_epoch == min(history, key=lambda r: (r["validation_joint_loss"], r["epoch"]))["epoch"]
    summary = {"status": "PASS", "kind": kind, "seed": seed, "epochs": len(history),
               "updates": sum(r["updates"] for r in history), "best_epoch": best_epoch,
               "training_validation_seconds": training_seconds, "metrics": metrics,
               "checkpoint_replay": "all four predictions bitwise equal",
               "protected_observations_opened": False,
               "hashes": {p.name: digest(p) for p in folder.iterdir() if p.is_file()}}
    dump(folder / "summary.json", summary)
    print("TT_FIT_PASS", kind, seed, EPOCHS, flush=True)


def check():
    arrays, meta, parts = load_selected()
    stats, data = make_data(arrays, parts)
    report = {"status": "PASS", "inputs": HASHES, "sources": sources(),
              "parts": {}, "protected_observations_opened": False}
    for name, positions in parts.items():
        events = set(arrays["event_ids"][positions]) - {""}
        report["parts"][name] = {"windows": len(positions),
                                "fault_windows": int((data[name]["labels"] >= 0).sum()),
                                "events": len(events),
                                "root_support": sorted(set(arrays["labels"][positions].tolist()) - {-1})}
    report["shared_events"] = len(
        (set(arrays["event_ids"][parts["train"]]) - {""}) &
        (set(arrays["event_ids"][parts["validation"]]) - {""}))
    report["scaler_constants"] = {key: int(stats[key + "_constant"].sum())
                                  for key in ("metrics", "traces")}
    dump(HERE / "TT_INPUT_CHECK.json", report)
    print("TT_INPUT_PASS", len(arrays["labels"]), len(meta["services"]), flush=True)


if __name__ == "__main__":
    assert __debug__, "Assertions must remain enabled"
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "fit"))
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--seed", choices=SEEDS, type=int)
    args = parser.parse_args()
    if args.action == "check":
        check()
    else:
        if args.kind is None or args.seed is None:
            parser.error("fit requires --kind and --seed")
        fit(args.kind, args.seed)
