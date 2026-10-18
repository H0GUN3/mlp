"""Fixed five-epoch development smoke; no full experiment or protected evaluation."""
import argparse
import json
from pathlib import Path
import random
import resource
import sys
import tempfile
import time

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.relationship_smoke_20261013 import data
from research.relationship_smoke_20261013.relation_model import RelationRanker

sys.path.insert(0, str(data.OLD))
from research.method_mlp_20261013 import train as base_train

SEED = 11
MODES = ("local", "global", "directed")
SETTINGS = {"epochs": 5, "patience": 5, "batch_size": 32,
            "learning_rate": 1e-3, "weight_decay": 1e-4, "threads": 2}


def source_hashes():
    paths = (HERE / "smoke.py", HERE / "relation_model.py", data.OLD / "train.py", data.OLD / "ranker.py")
    return dict(data.source_hashes(), **{str(path): data.base_features.file_hash(path) for path in paths})


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def ranking_metrics(logits, labels, events):
    if (logits.ndim != 2 or not logits.shape[0] or not logits.shape[1]
            or labels.shape != (len(logits),) or events.shape != labels.shape
            or labels.dtype.kind not in "iu" or np.any(labels < 0) or np.any(labels >= logits.shape[1])
            or not np.isfinite(logits).all() or any(not isinstance(e, str) or not e for e in events)):
        raise ValueError("Invalid ranking inputs")
    target = logits[np.arange(len(labels)), labels]
    greater = (logits > target[:, None]).sum(axis=1)
    ties = (logits == target[:, None]).sum(axis=1)
    credit = {
        "top1": np.clip((1 - greater) / ties, 0, 1),
        "top3": np.clip((3 - greater) / ties, 0, 1),
        "mrr": np.asarray([np.mean(1 / np.arange(g + 1, g + t + 1, dtype=np.float64))
                           for g, t in zip(greater, ties)]),
    }
    per_incident = {event: {key: float(values[events == event].mean()) for key, values in credit.items()}
                    for event in sorted(set(events))}
    return {
        "event_balanced": {key: float(np.mean([row[key] for row in per_incident.values()])) for key in credit},
        "window": {key: float(values.mean()) for key, values in credit.items()},
        "by_incident": per_incident, "windows": len(labels), "incidents": len(per_incident),
        "target_score_tie_windows": int((ties > 1).sum()),
    }


def common_inputs(arrays):
    training = np.flatnonzero(arrays["partition"] == "train")
    stats = base_train.fit_standardizer(arrays["x"], arrays["mask"], training)
    changed = arrays["x"].copy()
    changed[arrays["partition"] == "validation"] = 987654.0
    check = base_train.fit_standardizer(changed, arrays["mask"], training)
    if any(not np.array_equal(value, check[key]) for key, value in stats.items()):
        raise ValueError("Validation affects feature standardizer")
    tensors = (
        torch.from_numpy(base_train.transform(arrays["x"], arrays["mask"], stats)),
        torch.from_numpy(arrays["mask"]), torch.from_numpy(arrays["coverage"]),
        torch.from_numpy(arrays["adjacency"]),
    )
    train_rows = np.flatnonzero((arrays["partition"] == "train") & (arrays["labels"] >= 0))
    val_rows = np.flatnonzero((arrays["partition"] == "validation") & (arrays["labels"] >= 0))
    if not len(train_rows) or not len(val_rows):
        raise ValueError("Empty fault split")
    if set(arrays["event_ids"][train_rows]) & set(arrays["event_ids"][val_rows]):
        raise ValueError("Fault incident overlap")
    return stats, tensors, train_rows, val_rows


def verify_run(system, mode, arrays):
    folder = HERE / "runs" / system / mode
    config = json.loads((folder / "config.json").read_text())
    report = json.loads((folder / "report.json").read_text())
    data.base_features.require_hash(data.OUT / (system + ".npz"), config["bundle_sha256"])
    if config["system"] != system or config["mode"] != mode:
        raise ValueError("Run identity mismatch")
    for filename, digest in report["artifact_hashes"].items():
        data.base_features.require_hash(folder / filename, digest)
    if config["source_hashes"] != source_hashes():
        raise ValueError("Source changed since smoke")
    stats, tensors, train_rows, val_rows = common_inputs(arrays)
    if (config["train_indices"] != arrays["indices"][train_rows].tolist()
            or config["validation_indices"] != arrays["indices"][val_rows].tolist()):
        raise ValueError("Run indices differ")
    with np.load(folder / "standardizer.npz", allow_pickle=False) as saved:
        if any(not np.array_equal(value, saved[key]) for key, value in stats.items()):
            raise ValueError("Stored standardizer differs")
    checkpoint = torch.load(folder / "checkpoint.pt", map_location="cpu")
    if checkpoint["config_sha256"] != data.base_features.file_hash(folder / "config.json"):
        raise ValueError("Checkpoint/config mismatch")
    model = RelationRanker(arrays["x"].shape[-1], mode)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    validation_tensor = torch.as_tensor(val_rows, dtype=torch.long)
    with torch.no_grad():
        logits = model(*(tensor[validation_tensor] for tensor in tensors)).numpy()
    with np.load(folder / "predictions.npz", allow_pickle=False) as saved:
        expected = {"logits": logits, "labels": arrays["labels"][val_rows],
                    "indices": arrays["indices"][val_rows], "event_ids": arrays["event_ids"][val_rows]}
        if set(saved.files) != set(expected) or any(not np.array_equal(value, saved[key])
                                                  for key, value in expected.items()):
            raise ValueError("Checkpoint replay/prediction provenance mismatch")
    scored = ranking_metrics(logits, arrays["labels"][val_rows], arrays["event_ids"][val_rows])
    if scored != report["metrics"]:
        raise ValueError("Independent ranking replay mismatch")
    original_score = base_train.score(logits, arrays["labels"][val_rows], arrays["event_ids"][val_rows])
    if not np.isclose(original_score["event_balanced_top1"], scored["event_balanced"]["top1"], rtol=0, atol=1e-12):
        raise ValueError("Independent Top1 differs from established scorer")
    for key in ("build", "metadata", "raw_npz", "split"):
        entry = config["input_provenance"][key]
        data.base_features.require_hash(Path(entry["path"]), entry["sha256"])
    print("RELATION_REPLAY_VERIFIED", system, mode, flush=True)
    return report


def run_system(system, arrays, manifest):
    stats, tensors, train_rows, val_rows = common_inputs(arrays)
    labels = torch.from_numpy(arrays["labels"])
    train_weights = torch.from_numpy(base_train.event_weights(arrays["event_ids"][train_rows]))
    val_weights = torch.from_numpy(base_train.event_weights(arrays["event_ids"][val_rows]))
    sources = source_hashes()
    initial_reference = None
    reports = []
    for mode in MODES:
        target = HERE / "runs" / system / mode
        if target.exists():
            raise FileExistsError("Refusing to overwrite smoke run")
        random.seed(SEED)
        np.random.seed(SEED)
        torch.manual_seed(SEED)
        model = RelationRanker(arrays["x"].shape[-1], mode)
        initial = {key: value.detach().clone() for key, value in model.state_dict().items()}
        if initial_reference is not None and any(not torch.equal(initial_reference[key], value)
                                                 for key, value in initial.items()):
            raise ValueError("Modes have unequal initial weights")
        initial_reference = initial
        parameters = sum(parameter.numel() for parameter in model.parameters())
        if parameters != 3361:
            raise ValueError("Unexpected parameter count")
        started = time.perf_counter()
        logits, history, best_epoch, best_loss = base_train.fit_model(
            model, tensors, labels, train_rows, val_rows, train_weights, val_weights, SEED, SETTINGS)
        fit_seconds = time.perf_counter() - started
        config = {
            "system": system, "mode": mode, "seed": SEED, "fold": 0, "settings": SETTINGS,
            "parameter_count": parameters, "feature_dim": arrays["x"].shape[-1],
            "services": manifest["services"], "source_hashes": sources,
            "input_provenance": manifest["provenance"], "bundle_sha256": manifest["npz_sha256"],
            "train_indices": arrays["indices"][train_rows].tolist(),
            "validation_indices": arrays["indices"][val_rows].tolist(),
            "normalization_train_indices": arrays["indices"][arrays["partition"] == "train"].tolist(),
            "test_evaluated": False, "rcaeval_access": False,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix="." + mode + ".partial-", dir=str(target.parent)))
        write_json(stage / "config.json", config)
        write_json(stage / "history.json", history)
        with (stage / "standardizer.npz").open("xb") as stream:
            np.savez_compressed(stream, **stats)
        torch.save({"state_dict": model.state_dict(), "initial_state_dict": initial,
                    "config_sha256": data.base_features.file_hash(stage / "config.json")},
                   stage / "checkpoint.pt")
        with (stage / "predictions.npz").open("xb") as stream:
            np.savez_compressed(stream, logits=logits, labels=arrays["labels"][val_rows],
                                indices=arrays["indices"][val_rows], event_ids=arrays["event_ids"][val_rows])
        report = {
            "status": "smoke_complete_not_efficacy_evidence", "system": system, "mode": mode,
            "seed": SEED, "fold": 0, "epochs_run": len(history), "best_epoch": best_epoch,
            "best_validation_event_ce": best_loss, "fit_seconds": fit_seconds,
            "parameter_count": parameters, "metrics": ranking_metrics(
                logits, arrays["labels"][val_rows], arrays["event_ids"][val_rows]),
            "artifact_hashes": {name: data.base_features.file_hash(stage / name) for name in
                               ("config.json", "history.json", "standardizer.npz", "checkpoint.pt", "predictions.npz")},
        }
        write_json(stage / "report.json", report)
        if sources != source_hashes():
            raise ValueError("Source changed during smoke; partial run retained")
        if target.exists():
            raise FileExistsError("Run appeared during smoke; partial run retained")
        stage.rename(target)
        reports.append(verify_run(system, mode, arrays))
        print("RELATION_SMOKE_RUN_COMPLETE", system, mode, report["metrics"]["event_balanced"], flush=True)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("run", "verify"))
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5":
        raise RuntimeError("Use pinned .venv-eadro")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    if args.stage == "run" and any((HERE / "runs" / system / mode).exists()
                                   for system in ("SN", "TT") for mode in MODES):
        raise FileExistsError("Completed runs already exist; choose verify")
    started = time.perf_counter()
    reports, bundles = [], {}
    for system in ("SN", "TT"):
        arrays, manifest = data.load_bundle(system)
        bundles[system] = {"counts": manifest["counts"], "bytes": manifest["npz_bytes"],
                           "prepare_seconds": manifest["prepare_seconds"], "sha256": manifest["npz_sha256"]}
        if args.stage == "run":
            reports.extend(run_system(system, arrays, manifest))
        else:
            reports.extend(verify_run(system, mode, arrays) for mode in MODES)
    summary = {
        "status": "PASS", "scope": "six five-epoch development smoke runs only",
        "reports": reports, "bundles": bundles, "seconds": time.perf_counter() - started,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "test_evaluated": False, "rcaeval_access": False, "efficacy_established": False,
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__, "torch": torch.__version__,
                        "threads": 2, "device": "cpu"},
    }
    if args.stage == "run":
        write_json(HERE / "smoke_results.json", summary)
    print("RELATION_SMOKE_" + args.stage.upper() + "_COMPLETE", json.dumps(
        {key: value for key, value in summary.items() if key not in ("reports", "bundles")}), flush=True)


if __name__ == "__main__":
    main()
