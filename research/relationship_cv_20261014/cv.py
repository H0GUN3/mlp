"""Bounded development CV from already-permitted observations, never native inputs."""
import argparse
import json
from pathlib import Path
import random
import resource
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.relationship_smoke_20261013 import data, smoke
from research.relationship_split_audit_20261013 import audit

SEEDS = (11, 23, 37)
MODES = smoke.MODES
SETTINGS = dict(smoke.SETTINGS)
OUTPUT = HERE / "results"
sha = data.base_features.file_hash
write_json = smoke.write_json


def source_hashes():
    sources = audit.canonical_source_hashes(smoke.source_hashes())
    for path in (HERE / "cv.py", HERE / "PROTOCOL.md", Path(audit.__file__).resolve()):
        sources[str(path)] = sha(path)
    return sources


def require_hashes(hashes):
    for filename, digest in hashes.items():
        data.base_features.require_hash(Path(filename), digest)


def load_development(system):
    if system not in ("SN", "TT"):
        raise ValueError("Only authorized development systems are allowed")
    manifest_path = data.OUT / (system + ".json")
    archive_path = data.OUT / (system + ".npz")
    manifest = json.loads(manifest_path.read_text())
    hashes = {str(manifest_path): sha(manifest_path), str(archive_path): manifest["npz_sha256"]}
    require_hashes(hashes)
    if audit.canonical_source_hashes(manifest["source_hashes"]) != audit.canonical_source_hashes(data.source_hashes()):
        raise ValueError("Frozen preparation sources changed")
    with np.load(archive_path, allow_pickle=False) as saved:
        arrays = {key: saved[key] for key in saved.files}
    data.validate_bundle(arrays, manifest)
    split_audit = audit.inspect_splits(manifest, arrays)
    require_hashes(hashes)
    return arrays, manifest, hashes, split_audit


def prepare_fold(original, manifest, fold):
    if fold not in (0, 1, 2):
        raise ValueError("Invalid development fold")
    arrays = dict(original)
    arrays["partition"] = np.where(original["fold_ids"] == fold, "validation", "train")
    reference = data.base_features.fit_reference(
        arrays["values"], arrays["observed"], arrays["labels"], arrays["partition"])
    if not np.any((arrays["partition"] == "train") & (arrays["labels"] == -1)):
        raise ValueError("No normal TRAIN support")
    arrays["x"], arrays["mask"], arrays["coverage"] = data.base_features.window_features(
        arrays["values"], arrays["observed"], reference)
    fold_manifest = dict(manifest, fold=fold,
                         normal_reference={key: value.tolist() for key, value in reference.items()})
    data.validate_bundle(arrays, fold_manifest)
    stats, tensors, training, validation = smoke.common_inputs(arrays)
    return arrays, reference, stats, tensors, training, validation


def fit_final(model, tensors, labels, events, seed):
    """Only TRAIN tensors enter this function; validation cannot select a checkpoint."""
    if len(labels) == 0 or len(events) != len(labels) or any(len(t) != len(labels) for t in tensors):
        raise ValueError("Invalid TRAIN rows")
    weights = torch.from_numpy(smoke.base_train.event_weights(events))
    optimizer = torch.optim.Adam(model.parameters(), lr=SETTINGS["learning_rate"],
                                 weight_decay=SETTINGS["weight_decay"])
    order_rng = np.random.RandomState(seed)
    history = []
    for epoch in range(1, SETTINGS["epochs"] + 1):
        model.train()
        order = order_rng.permutation(len(labels))
        weighted_sum = 0.
        for start in range(0, len(order), SETTINGS["batch_size"]):
            rows = torch.as_tensor(order[start:start + SETTINGS["batch_size"]], dtype=torch.long)
            optimizer.zero_grad()
            losses = F.cross_entropy(model(*(value[rows] for value in tensors)), labels[rows],
                                     reduction="none")
            loss = (losses * weights[rows]).mean()
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite TRAIN loss")
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise ValueError("Nonfinite gradient")
            optimizer.step()
            weighted_sum += float(loss.detach()) * len(rows)
        history.append({"epoch": epoch, "train_event_ce": weighted_sum / len(labels)})
    model.eval()
    return history


def predict(model, tensors, rows):
    chosen = torch.as_tensor(rows, dtype=torch.long)
    model.eval()
    with torch.no_grad():
        return model(*(value[chosen] for value in tensors)).numpy()


def save_npz(path, **values):
    with path.open("xb") as stream:
        np.savez_compressed(stream, **values)


def assert_npz(path, expected):
    with np.load(path, allow_pickle=False) as saved:
        if set(saved.files) != set(expected) or any(not np.array_equal(value, saved[key])
                                                  for key, value in expected.items()):
            raise ValueError("Saved arrays differ: " + str(path))


def fold_statistics(arrays, reference, stats):
    return dict(
        {"reference_" + key: value for key, value in reference.items()},
        **{"standardizer_" + key: value for key, value in stats.items()},
        train_indices=arrays["indices"][arrays["partition"] == "train"],
        normal_train_indices=arrays["indices"][(arrays["partition"] == "train") & (arrays["labels"] == -1)],
        validation_indices=arrays["indices"][arrays["partition"] == "validation"],
    )


def verify_run(folder, arrays, tensors, training, validation, sources, inputs, identity):
    config = json.loads((folder / "config.json").read_text())
    report = json.loads((folder / "report.json").read_text())
    expected_config = dict(identity, seed=int(identity["seed"]), settings=SETTINGS,
                           checkpoint_policy="fixed_final_epoch_5", source_hashes=sources,
                           input_hashes=inputs, parameter_count=3361,
                           train_indices=arrays["indices"][training].tolist(),
                           validation_indices=arrays["indices"][validation].tolist())
    if config != expected_config:
        raise ValueError("Run config/provenance mismatch")
    for name, digest in report["artifact_hashes"].items():
        data.base_features.require_hash(folder / name, digest)
    saved = torch.load(folder / "checkpoint.pt", map_location="cpu")
    if saved["config_sha256"] != sha(folder / "config.json"):
        raise ValueError("Checkpoint/config mismatch")
    model = smoke.RelationRanker(18, identity["mode"])
    model.load_state_dict(saved["state_dict"])
    logits = predict(model, tensors, validation)
    assert_npz(folder / "predictions.npz", {
        "logits": logits, "labels": arrays["labels"][validation],
        "indices": arrays["indices"][validation], "event_ids": arrays["event_ids"][validation],
    })
    metrics = smoke.ranking_metrics(logits, arrays["labels"][validation], arrays["event_ids"][validation])
    if metrics != report["metrics"] or any(report[key] != value for key, value in identity.items()):
        raise ValueError("Prediction scores or identity differ")
    independent = smoke.base_train.score(logits, arrays["labels"][validation], arrays["event_ids"][validation])
    if not np.isclose(independent["event_balanced_top1"], metrics["event_balanced"]["top1"], atol=1e-12, rtol=0):
        raise ValueError("Independent Top1 scorer mismatch")
    torch.manual_seed(identity["seed"])
    initial_model = smoke.RelationRanker(18, identity["mode"])
    if any(not torch.equal(value, saved["initial_state_dict"][key])
           for key, value in initial_model.state_dict().items()):
        raise ValueError("Initial state differs from fixed seed")
    history = json.loads((folder / "history.json").read_text())
    if len(history) != 5 or [row["epoch"] for row in history] != list(range(1, 6)):
        raise ValueError("Wrong epoch budget")
    print("CV_REPLAY_OK", identity, flush=True)
    return report


def run_fold(system, fold, arrays, tensors, training, validation, sources, inputs, output):
    reports = []
    train_tensors = tuple(tensor[training] for tensor in tensors)
    train_labels = torch.from_numpy(arrays["labels"][training])
    for seed in SEEDS:
        initial_reference = None
        for mode in MODES:
            identity = {"system": system, "fold": fold, "seed": seed, "mode": mode}
            folder = output / system / ("fold_" + str(fold)) / ("seed_" + str(seed)) / mode
            folder.mkdir(parents=True, exist_ok=False)
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            model = smoke.RelationRanker(18, mode)
            initial = {key: value.detach().clone() for key, value in model.state_dict().items()}
            if initial_reference is not None and any(not torch.equal(initial_reference[key], value)
                                                     for key, value in initial.items()):
                raise ValueError("Unequal initial weights across modes")
            initial_reference = initial
            if sum(p.numel() for p in model.parameters()) != 3361:
                raise ValueError("Parameter budget changed")
            started = time.perf_counter()
            history = fit_final(model, train_tensors, train_labels, arrays["event_ids"][training], seed)
            seconds = time.perf_counter() - started
            logits = predict(model, tensors, validation)
            config = dict(identity, settings=SETTINGS, checkpoint_policy="fixed_final_epoch_5",
                          source_hashes=sources, input_hashes=inputs, parameter_count=3361,
                          train_indices=arrays["indices"][training].tolist(),
                          validation_indices=arrays["indices"][validation].tolist())
            write_json(folder / "config.json", config)
            write_json(folder / "history.json", history)
            torch.save({"state_dict": model.state_dict(), "initial_state_dict": initial,
                        "config_sha256": sha(folder / "config.json")}, folder / "checkpoint.pt")
            save_npz(folder / "predictions.npz", logits=logits, labels=arrays["labels"][validation],
                     indices=arrays["indices"][validation], event_ids=arrays["event_ids"][validation])
            metrics = smoke.ranking_metrics(logits, arrays["labels"][validation], arrays["event_ids"][validation])
            report = dict(identity, fit_seconds=seconds, epochs_run=len(history),
                          metrics=metrics,
                          artifact_hashes={name: sha(folder / name) for name in
                                           ("config.json", "history.json", "checkpoint.pt", "predictions.npz")})
            write_json(folder / "report.json", report)
            reports.append(verify_run(folder, arrays, tensors, training, validation, sources, inputs, identity))
            print("CV_FIT_COMPLETE", identity, metrics["event_balanced"], flush=True)
    return reports


def execute(stage, output=OUTPUT):
    started = time.perf_counter()
    sources = source_hashes()
    if stage == "run":
        output.mkdir(exist_ok=False)
        previous = None
    elif stage == "verify":
        previous = json.loads((output / "runs.json").read_text())
        if previous["source_hashes"] != sources:
            raise ValueError("Sources changed since run")
        require_hashes({str(output / name): digest for name, digest in previous["artifact_hashes"].items()})
    else:
        raise ValueError("Invalid stage")
    reports, systems, input_hashes, artifact_hashes = [], {}, {}, {}
    for system in ("SN", "TT"):
        original, manifest, inputs, split_audit = load_development(system)
        input_hashes.update(inputs)
        fold_reports = []
        for fold in range(3):
            preparation_start = time.perf_counter()
            arrays, reference, stats, tensors, training, validation = prepare_fold(original, manifest, fold)
            preparation_seconds = time.perf_counter() - preparation_start
            folder = output / system / ("fold_" + str(fold))
            statistics = fold_statistics(arrays, reference, stats)
            if stage == "run":
                folder.mkdir(parents=True, exist_ok=False)
                save_npz(folder / "statistics.npz", **statistics)
                reports.extend(run_fold(system, fold, arrays, tensors, training, validation, sources, inputs, output))
            else:
                for seed in SEEDS:
                    for mode in MODES:
                        reports.append(verify_run(
                            folder / ("seed_" + str(seed)) / mode, arrays, tensors, training, validation,
                            sources, inputs, {"system": system, "fold": fold, "seed": seed, "mode": mode}))
            assert_npz(folder / "statistics.npz", statistics)
            fold_reports.append({
                "fold": fold, "prepare_and_check_seconds": preparation_seconds,
                "missing_normal_reference_slots": int((~reference["mask"]).sum()),
                "train_fault_windows": len(training), "validation_fault_windows": len(validation),
                "validation_fault_windows_with_edges": int(arrays["adjacency"][validation].any(axis=(1, 2)).sum()),
            })
        systems[system] = {"folds": fold_reports, "split_audit": split_audit, "faults": manifest["faults"]}
        require_hashes(inputs)
    require_hashes(sources)
    require_hashes(input_hashes)
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in ("runs.json", "verification.json", "analysis.json"):
            artifact_hashes[str(path.relative_to(output))] = sha(path)
    summary = {
        "status": "PASS", "run_count": len(reports), "reports": reports, "systems": systems,
        "source_hashes": sources, "input_hashes": input_hashes, "artifact_hashes": artifact_hashes,
        "seconds": time.perf_counter() - started,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "test_evaluated": False, "rcaeval_access": False, "rcabench_access": False,
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__, "torch": torch.__version__,
                        "threads": 2, "device": "cpu"},
    }
    if previous is not None:
        if (reports != previous["reports"] or input_hashes != previous["input_hashes"]
                or artifact_hashes != previous["artifact_hashes"]):
            raise ValueError("Separate-process replay differs")
        write_json(output / "verification.json", {key: value for key, value in summary.items()
                                                 if key not in ("reports", "systems", "artifact_hashes")})
    else:
        write_json(output / "runs.json", summary)
    print("CV_" + stage.upper() + "_COMPLETE", len(reports), summary["seconds"],
          summary["process_peak_rss_kib"], flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("run", "verify"))
    arguments = parser.parse_args()
    if (sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5"
            or torch.__version__ != "1.12.1+cpu"):
        raise RuntimeError("Use pinned .venv-eadro Python3.8 / NumPy1.21.5 / torch1.12.1+cpu")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    execute(arguments.stage)
