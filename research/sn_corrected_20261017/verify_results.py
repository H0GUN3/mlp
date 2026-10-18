#!/usr/bin/env python3
"""Read-only independent audit and checkpoint replay for locked SN predictions."""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = ROOT / "research/native_reproduction_20261013"
sys.path.insert(0, str(NATIVE))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def check_alignment(prediction, expected, filename):
    require(np.array_equal(prediction["labels"], expected["labels"]),
            "labels mismatch " + filename)
    require(np.array_equal(prediction["indices"], expected["indices"]),
            "indices mismatch " + filename)
    require(np.array_equal(prediction["event_ids"], expected["event_ids"]),
            "event IDs mismatch " + filename)


def independent_events(logits, labels, event_ids):
    """Float64 log-softmax, window log-mean-exp, uniform exact-tie credit."""
    x = np.asarray(logits, dtype=np.float64)
    y, ids = np.asarray(labels), np.asarray(event_ids)
    require(x.ndim == 2 and x.shape[1] == 12, "expected 12 root logits")
    require(y.shape == ids.shape == (len(x),), "prediction metadata shape mismatch")
    groups = {}
    for i, (root, event) in enumerate(zip(y.tolist(), ids.tolist())):
        if root == -1:
            require(event == "", "normal event ID must be empty")
            continue
        require(0 <= root < 12 and bool(event), "invalid fault label/event")
        groups.setdefault(event, [root, []])
        require(groups[event][0] == root, "inconsistent event root")
        groups[event][1].append(i)
    require(bool(groups), "no fault events")
    row_max = np.max(x, axis=1)
    shifted = x - row_max[:, None]
    logp = shifted - np.log(np.sum(np.exp(shifted), axis=1))[:, None]
    output, losses = [], []
    for event in sorted(groups):
        root, rows = groups[event]
        lp = logp[rows]
        m = np.max(lp, axis=0)
        pooled = m + np.log(np.sum(np.exp(lp - m), axis=0)) - math.log(len(rows))
        truth = pooled[root]
        greater = int(np.count_nonzero(pooled > truth))
        ties = int(np.count_nonzero(pooled == truth))
        output.append({"event_id": event, "root": root, "windows": len(rows),
                       "log_probabilities": pooled.tolist(),
                       "top1": min(max(1 - greater, 0), ties) / ties,
                       "top3": min(max(3 - greater, 0), ties) / ties})
        losses.append(-float(truth))
    return {"event_nll": float(np.mean(losses)),
            "top1": float(np.mean([e["top1"] for e in output])),
            "top3": float(np.mean([e["top3"] for e in output])), "events": output}


def main():
    import torch
    import dgl
    from input_bundle import load_inputs, split_indices
    from native_models import NativeReference
    from native_train import fit_scaler, scaled_partition, graph_batch
    from runner import setup, sources

    require(sys.flags.optimize == 0, "assertions must remain enabled")
    selection = json.loads((HERE / "selection.lock.json").read_text())
    manifest = json.loads((HERE / "input_manifest.json").read_text())
    result = json.loads((HERE / "evaluation.json").read_text())
    require(selection["status"] == "LOCKED", "selection lock missing")
    require(selection["input_npz_sha256"] == digest(HERE / "inputs.npz"), "input hash changed")
    require(result["selection_sha256"] == digest(HERE / "selection.lock.json"), "selection hash changed")
    require(selection["source_hashes"] == sources() == result["source_hashes"],
            "frozen source hash mismatch")
    arrays, meta = load_inputs()
    require(len(selection["runs"]) == 18 and len(result["runs"]) == 18, "expected 18 runs")
    require(len({(r["rotation"], r["kind"], r["seed"]) for r in selection["runs"]}) == 18,
            "duplicate run key")
    require(meta["services"] == manifest["services"] and len(meta["services"]) == 12,
            "service order mismatch")
    protection = manifest["protection"]
    require(protection["permitted_rows"] == 394
            and protection["protected_rows_decoded"] == 0
            and protection["raw_streams_scanned"] is False,
            "input protection audit failed")
    reused = manifest["reused_verification"]
    require(reused["audit_path"] == "research/diagnostic_observability_20261016/sn_tt_audit.json"
            and all(reused["checks"].values()), "existing protection/identity audit failed")
    reports = {(r["rotation"], r["kind"], r["seed"]): r for r in result["runs"]}
    require(len(reports) == 18, "duplicate evaluation run records")
    max_diff = 0.0
    files = 0
    oof_events = {(kind, seed): set() for kind in ("eadro", "diagmlp")
                  for seed in (11, 23, 37)}
    for entry in selection["runs"]:
        rotation, kind, seed = entry["rotation"], entry["kind"], entry["seed"]
        key = rotation, kind, seed
        record = reports[key]
        folder = HERE / entry["path"]
        require(digest(folder / "best.pt") == entry["best_sha256"], "checkpoint hash mismatch: " + str(key))
        config = json.loads((folder / "config.json").read_text())
        require(digest(folder / "config.json") == entry["config_sha256"]
                and config["input_npz_sha256"] == digest(HERE / "inputs.npz")
                and config["source_hashes"] == sources(),
                "frozen run config/input/source hash mismatch " + str(key))
        checkpoint = torch.load(folder / "best.pt", map_location="cpu")
        require(checkpoint["epoch"] == entry["best_epoch"]
                and checkpoint["config_sha256"] == entry["config_sha256"], "checkpoint selection mismatch")
        splits = split_indices(arrays, rotation)
        stats = fit_scaler(arrays, splits["train"])
        with np.load(folder / "scaler.npz", allow_pickle=False) as saved:
            for name, value in stats.items():
                require(np.array_equal(saved[name], value), "TRAIN-only scaler mismatch " + name)
        model = NativeReference(kind, 12, 7)
        model.load_state_dict(checkpoint["model"])
        model.eval()
        setup(seed)
        part_events = 0
        for part in ("train", "validation", "evaluation"):
            pos = splits[part]
            data = scaled_partition(arrays, pos, stats)
            data["event_ids"] = arrays["event_ids"][pos]
            data["indices"] = arrays["indices"][pos]
            filename = "r{}_{}_s{}_{}.npz".format(rotation, kind, seed, part)
            path = HERE / "evaluation" / filename
            require(filename in record["prediction_sha256"]
                    and digest(path) == record["prediction_sha256"][filename],
                    "prediction hash mismatch: " + filename)
            with np.load(path, allow_pickle=False) as pred:
                check_alignment(pred, data, filename)
                require(np.array_equal(pred["indices"], arrays["indices"][pos]),
                        "original indices do not match split positions " + filename)
                roots, detects = [], []
                with torch.no_grad():
                    for start in range(0, len(pos), 32):
                        batch = np.arange(start, min(start + 32, len(pos)))
                        graph, _ = graph_batch(data, batch, meta)
                        root, detect = model(graph)
                        roots.append(root.cpu().numpy())
                        detects.append(detect.cpu().numpy())
                root, detect = np.concatenate(roots), np.concatenate(detects)
                require(np.array_equal(root, pred["root_logits"]), "root replay differs " + filename)
                require(np.array_equal(detect, pred["detection_logits"]), "detection replay differs " + filename)
                require(root.shape[1] == 12 and np.isfinite(root).all() and np.isfinite(detect).all(),
                        "invalid logits " + filename)
                metrics = independent_events(root, data["labels"], data["event_ids"])
                stored = record["parts"][part]
                stored_events = stored["events"]
                require(len(stored_events) == len(metrics["events"]), "stored event count differs")
                for a, b in zip(metrics["events"], stored_events):
                    require((a["event_id"], a["root"], a["windows"]) ==
                            (b["event_id"], b["root"], b["windows"]), "event ordering/content differs")
                    d = float(np.max(np.abs(np.asarray(a["log_probabilities"]) -
                                            np.asarray(b["log_probabilities"]))))
                    max_diff = max(max_diff, d)
                    require(d <= 1e-12, "independent pooled log probability mismatch")
                    require(a["top1"] == b["top1"] and a["top3"] == b["top3"],
                            "exact tie credit mismatch")
                require(abs(metrics["event_nll"] - stored["event_nll"]) <= 1e-12,
                        "independent NLL mismatch")
                if part == "evaluation":
                    require(len(metrics["events"]) == 12, "each OOF partition must contain 12 events")
                    for event in metrics["events"]:
                        fault = manifest["faults"][event["event_id"]]
                        require(event["root"] == fault["root"]
                                and fault["service"] == manifest["services"][event["root"]],
                                "event root/service order mismatch " + event["event_id"])
                        oof_events[(kind, seed)].add(event["event_id"])
                    part_events += len(metrics["events"])
            files += 1
        require(part_events == 12, "evaluation event count mismatch")
    require(files == 54, "expected 54 replayed prediction artifacts")
    for key, events in oof_events.items():
        require(len(events) == 36, "out-of-fold event coverage/duplicates mismatch " + str(key))
    print("VERIFY_PASS 18 54")
    return {"verdict": "PASS", "runs": 18, "prediction_files_replayed": files,
            "max_pooled_log_probability_abs_diff": max_diff}


if __name__ == "__main__":
    import json
    print("VERIFY_SUMMARY " + json.dumps(main(), sort_keys=True, allow_nan=False))
