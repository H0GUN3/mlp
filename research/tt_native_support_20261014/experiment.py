"""Bounded TT incident-CV with native encoders; only this experiment's allowed cache."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import random
import resource
import sys
import time

os.environ.setdefault("DGLBACKEND", "pytorch")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE.parent / "native_reproduction_20261013"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(NATIVE))
import native_models
import native_train
from research.relationship_diagnosis_20261014 import errors

SEEDS = (11, 23, 37)
FOLDS = (0, 1, 2)
KINDS = ("eadro", "diagmlp", "diagmlp_count", "diagmlp_zero_count")
SETTINGS = {"epochs": 200, "batch_size": 256, "learning_rate": .001,
            "dropout": .1, "threads": 2, "weight_decay": 0}
ARTIFACTS = HERE / "artifacts"


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def save_npz(path, **values):
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, **values)


def save_torch(path, value):
    with Path(path).open("xb") as stream:
        torch.save(value, stream)


def source_hashes():
    if errors.__file__ is None:
        raise RuntimeError("Missing diagnostic helper source")
    paths = (Path(__file__), HERE / "PROTOCOL.md", NATIVE / "native_train.py",
             NATIVE / "native_models.py", native_models.SOURCE, Path(errors.__file__))
    return {str(p): errors.file_hash(p) for p in paths}


def validate_indices(actual, allowed):
    errors.require(np.array_equal(actual, allowed) and len(np.unique(actual)) == len(actual),
                   "Changed or protected development index inventory")


def load_data():
    manifest_path = ARTIFACTS / "TT.json"
    manifest = json.loads(manifest_path.read_text())
    path = ARTIFACTS / "TT.npz"
    inputs = {str(manifest_path): errors.file_hash(manifest_path),
              str(path): manifest["npz_sha256"]}
    for filename, digest in inputs.items():
        errors.check_hash(filename, digest)
    with np.load(path, allow_pickle=False) as saved:
        arrays = {key: saved[key] for key in saved.files}
    old_manifest_path, old_bundle_path = errors.BUNDLES / "TT.json", errors.BUNDLES / "TT.npz"
    errors.check_hash(old_manifest_path, manifest["input_hashes"][str(old_manifest_path)])
    errors.check_hash(old_bundle_path, manifest["input_hashes"][str(old_bundle_path)])
    errors.check_hash(HERE / "PROTOCOL.md", manifest["source_hashes"][str(HERE / "PROTOCOL.md")])
    old_manifest = json.loads(old_manifest_path.read_text())
    errors.require(old_manifest["npz_sha256"] == manifest["input_hashes"][str(old_bundle_path)],
                   "Prepared/allowed bundle provenance differs")
    with np.load(old_bundle_path, allow_pickle=False) as old:
        for key in ("indices", "labels", "event_ids", "episode_ids", "fold_ids"):
            validate_indices(arrays[key], old[key]) if key == "indices" else errors.require(
                np.array_equal(arrays[key], old[key]), "Changed row metadata: " + key)
    errors.require(len(arrays["labels"]) == 4069 and len(manifest["services"]) == 27
                   and manifest["services"] == old_manifest["services"]
                   and manifest["faults"] == old_manifest["faults"],
                   "Changed TT development contract")
    native_train.validate_inputs(
        {key: arrays[key] for key in ("metrics", "traces", "logs", "labels")}, manifest, "TT")
    count = arrays["unique_count"]
    errors.require(count.shape == (4069, 27) and count.dtype.kind in "iu"
                   and np.all(count >= 0), "Invalid unique count")
    for filename, digest in inputs.items():
        errors.check_hash(filename, digest)
    return arrays, manifest, inputs


class SupportEncoder(nn.Module):
    """Same equation-based encoder; one observed-support scalar before modal fusion."""
    def __init__(self, base, zero):
        super().__init__()
        self.node_count = base.node_count
        self.metric_model, self.log_model, self.trace_model = base.metric_model, base.log_model, base.trace_model
        self.position, self.modal, self.node = base.position, base.modal, base.node
        self.feat_out_dim, self.zero = base.feat_out_dim, zero
        old = self.modal[0]
        if not isinstance(old, nn.Linear):
            raise TypeError("Unexpected modal block")
        rng = torch.get_rng_state()
        expanded = nn.Linear(old.in_features + 1, old.out_features)
        torch.set_rng_state(rng)
        with torch.no_grad():
            if expanded.bias is None or old.bias is None:
                raise RuntimeError("Unexpected bias-free modal layer")
            expanded.weight[:, :-1].copy_(old.weight)
            expanded.weight[:, -1].zero_()
            expanded.bias.copy_(old.bias)
        self.modal[0] = expanded

    def forward(self, graph):
        batch = graph.batch_size
        values = torch.cat((self.metric_model(graph.ndata["metrics"]),
                            self.log_model(graph.ndata["logs"]),
                            self.trace_model(graph.ndata["traces"])), dim=-1)
        values = values.reshape(batch, self.node_count, -1)
        position = self.position.weight.unsqueeze(0).expand(batch, -1, -1)
        support = graph.ndata["support"].reshape(batch, self.node_count, 1)
        if not torch.isfinite(support).all() or (support < 0).any():
            raise ValueError("Invalid support input")
        if self.zero:
            support = torch.zeros_like(support)
        return self.node(self.modal(torch.cat((values, position, support), -1)).reshape(batch, -1))


def make_model(kind, event_count, nodes=27):
    if kind not in KINDS:
        raise ValueError("Invalid model kind")
    native_kind = "eadro" if kind == "eadro" else "diagmlp"
    model = native_models.NativeReference(native_kind, nodes, event_count, dropout=SETTINGS["dropout"])
    if kind in ("diagmlp_count", "diagmlp_zero_count"):
        model.core.encoder = SupportEncoder(model.core.encoder, kind == "diagmlp_zero_count")
    model.config.update({"experiment_kind": kind, "support": "log1p(unique_count)" if kind == "diagmlp_count" else "none"})
    return model


def require_matching_initial(base, augmented):
    key = "core.encoder.modal.0.weight"
    errors.require(set(base) == set(augmented), "Initial parameter keys differ")
    for name, value in base.items():
        if name == key:
            errors.require(augmented[name].shape == (value.shape[0], value.shape[1] + 1)
                           and torch.equal(augmented[name][:, :-1], value)
                           and torch.count_nonzero(augmented[name][:, -1]).item() == 0,
                           "Initial support layer differs")
        else:
            errors.require(torch.equal(augmented[name], value), "Initial parameter differs: " + name)


def prepare_fold(arrays, fold):
    if fold not in FOLDS:
        raise ValueError("Invalid fold")
    validation = arrays["fold_ids"] == fold
    parts = {"train": np.flatnonzero(~validation), "validation": np.flatnonzero(validation)}
    errors.require(not set(arrays["episode_ids"][~validation]) & set(arrays["episode_ids"][validation]),
                   "Episode leakage")
    stats = native_train.fit_scaler(arrays, parts["train"])
    transformed = {}
    for name, rows in parts.items():
        transformed[name] = native_train.scaled_partition(arrays, rows, stats)
        transformed[name]["support"] = np.log1p(arrays["unique_count"][rows]).astype(np.float32)[..., None]
    return parts, stats, transformed


def graph_batch(data, rows, metadata):
    graph, labels = native_train.graph_batch(data, rows, metadata)
    graph.ndata["support"] = torch.from_numpy(data["support"][rows].reshape(-1, 1))
    return graph, labels


def predict(model, data, metadata):
    model.eval()
    root_parts, detect_parts = [], []
    with torch.no_grad():
        for start in range(0, len(data["labels"]), SETTINGS["batch_size"]):
            rows = np.arange(start, min(start + SETTINGS["batch_size"], len(data["labels"])))
            graph, _ = graph_batch(data, rows, metadata)
            root, detect = model(graph)
            root_parts.append(root)
            detect_parts.append(detect)
    roots, detection = torch.cat(root_parts), torch.cat(detect_parts)
    labels = torch.from_numpy(data["labels"])
    loss = float(native_models.joint_loss(roots, detection, labels).item())
    return roots.numpy(), detection.numpy(), loss


def incident_metrics(roots, labels, event_ids):
    faulty = labels >= 0
    scores, _, _, _ = errors.ranking(roots[faulty], labels[faulty])
    events = event_ids[faulty]
    by_event = {str(event): {m: float(v[events == event].mean()) for m, v in scores.items()}
                for event in sorted(set(events))}
    return {"event_balanced": {m: float(np.mean([r[m] for r in by_event.values()])) for m in errors.METRICS},
            "by_event": by_event, "fault_windows": int(faulty.sum()),
            "event_count": len(by_event)}


def verify_folder(folder, arrays, metadata, parts, stats, transformed, inputs):
    config = json.loads((folder / "config.json").read_text())
    report = json.loads((folder / "report.json").read_text())
    errors.require(report["status"] == "PASS" and config["settings"] == SETTINGS
                   and config["input_hashes"] == inputs, "Run contract mismatch")
    for path, digest in config["source_hashes"].items():
        errors.check_hash(path, digest)
    for name, digest in report["artifact_hashes"].items():
        errors.check_hash(folder / name, digest)
    with np.load(folder / "scaler.npz", allow_pickle=False) as saved:
        errors.require(set(saved.files) == set(stats)
                       and all(np.array_equal(saved[k], v) for k, v in stats.items()), "Scaler changed")
    model = make_model(config["kind"], metadata["event_count"])
    checkpoint = torch.load(folder / "checkpoint.pt", map_location="cpu")
    errors.require(checkpoint["config_sha256"] == errors.file_hash(folder / "config.json"), "Checkpoint config mismatch")
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    for split in ("train", "validation"):
        roots, detection, loss = predict(model, transformed[split], metadata)
        with np.load(folder / (split + "_predictions.npz"), allow_pickle=False) as saved:
            expected = {"root_logits": roots, "detection_logits": detection,
                        "labels": arrays["labels"][parts[split]],
                        "indices": arrays["indices"][parts[split]],
                        "event_ids": arrays["event_ids"][parts[split]]}
            errors.require(set(saved.files) == set(expected)
                           and all(np.array_equal(saved[k], v) for k, v in expected.items()), "Replay differs")
        errors.require(loss == report[split]["joint_loss"], "Replay loss differs")
        metrics = incident_metrics(roots, transformed[split]["labels"], arrays["event_ids"][parts[split]])
        errors.require(metrics == report[split]["ranking"], "Replay ranking differs")
    for path, digest in inputs.items():
        errors.check_hash(path, digest)
    return report


def run_one(fold, seed, kind):
    started = time.perf_counter()
    torch.set_num_threads(SETTINGS["threads"])
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    arrays, metadata, inputs = load_data()
    parts, stats, transformed = prepare_fold(arrays, fold)
    folder = HERE / "runs" / ("fold_" + str(fold)) / ("seed_" + str(seed)) / kind
    if (folder / "report.json").exists():
        report = verify_folder(folder, arrays, metadata, parts, stats, transformed, inputs)
        print("EXISTING_RUN_VERIFIED", fold, seed, kind, flush=True)
        return report
    folder.mkdir(parents=True, exist_ok=False)
    model = make_model(kind, metadata["event_count"])
    initial_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    baseline_initial_hash = None
    if kind in ("diagmlp_count", "diagmlp_zero_count"):
        baseline_initial = folder.parent / "diagmlp" / "initial.pt"
        baseline_initial_hash = errors.file_hash(baseline_initial)
        require_matching_initial(torch.load(baseline_initial, map_location="cpu"), initial_state)
    save_torch(folder / "initial.pt", initial_state)
    save_npz(folder / "scaler.npz", **stats)
    config = {
        "fold": fold, "seed": seed, "kind": kind, "settings": SETTINGS,
        "model": model.config, "input_hashes": inputs, "source_hashes": source_hashes(),
        "checkpoint_selection": "strict minimum full-validation native joint CE; earliest tie",
        "parameters": sum(p.numel() for p in model.parameters()),
        "paired_baseline_initial_sha256": baseline_initial_hash,
        "train_indices": arrays["indices"][parts["train"]].tolist(),
        "validation_indices": arrays["indices"][parts["validation"]].tolist(),
        "test_evaluated": False,
    }
    write_json(folder / "config.json", config)
    optimizer = torch.optim.Adam(model.parameters(), lr=SETTINGS["learning_rate"], weight_decay=0)
    shuffle = np.random.RandomState(seed)
    best, best_epoch, best_state = float("inf"), 0, None
    history = []
    training = transformed["train"]
    fitting_start = time.perf_counter()
    for epoch in range(1, SETTINGS["epochs"] + 1):
        epoch_start = time.perf_counter()
        model.train()
        order = shuffle.permutation(len(training["labels"]))
        total, updates = 0., 0
        for start in range(0, len(order), SETTINGS["batch_size"]):
            rows = order[start:start + SETTINGS["batch_size"]]
            graph, labels = graph_batch(training, rows, metadata)
            optimizer.zero_grad()
            root, detect = model(graph)
            loss = native_models.joint_loss(root, detect, labels)
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite loss")
            loss.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise ValueError("Nonfinite gradient")
            optimizer.step()
            total += float(loss.detach()) * len(rows)
            updates += 1
        _, _, validation_loss = predict(model, transformed["validation"], metadata)
        if validation_loss < best:
            best, best_epoch = validation_loss, epoch
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        history.append({"epoch": epoch, "train_online_joint_loss": total / len(order),
                        "validation_joint_loss": validation_loss, "updates": updates,
                        "seconds": time.perf_counter() - epoch_start})
        if epoch == 1 or epoch % 25 == 0:
            print("NATIVE_EPOCH", fold, seed, kind, epoch, "seconds", history[-1]["seconds"],
                  "val", validation_loss, "best_epoch", best_epoch, flush=True)
    fitting_seconds = time.perf_counter() - fitting_start
    if best_state is None:
        raise RuntimeError("No checkpoint selected")
    model.load_state_dict(best_state)
    save_torch(folder / "checkpoint.pt", {"state_dict": best_state, "epoch": best_epoch,
                                         "config_sha256": errors.file_hash(folder / "config.json")})
    write_json(folder / "history.json", history)
    splits = {}
    for split in ("train", "validation"):
        inference_start = time.perf_counter()
        roots, detection, loss = predict(model, transformed[split], metadata)
        inference_seconds = time.perf_counter() - inference_start
        rows = parts[split]
        save_npz(folder / (split + "_predictions.npz"), root_logits=roots, detection_logits=detection,
                 labels=arrays["labels"][rows], indices=arrays["indices"][rows], event_ids=arrays["event_ids"][rows])
        splits[split] = {
            "joint_loss": loss, "inference_with_graph_seconds": inference_seconds,
            "ranking": incident_metrics(roots, arrays["labels"][rows], arrays["event_ids"][rows]),
            "detection_and_native_window_scores": native_models.native_scores(
                torch.from_numpy(roots), torch.from_numpy(detection), torch.from_numpy(arrays["labels"][rows])),
        }
    errors.require(splits["validation"]["joint_loss"] == best, "Selected loss changed before save")
    for path, digest in inputs.items():
        errors.check_hash(path, digest)
    report = {
        "status": "PASS", "fold": fold, "seed": seed, "kind": kind, "best_epoch": best_epoch,
        "selected_at_cap": best_epoch == SETTINGS["epochs"], "epochs": SETTINGS["epochs"],
        "optimizer_updates": sum(r["updates"] for r in history),
        "fit_validation_seconds": fitting_seconds, "total_before_replay_seconds": time.perf_counter() - started,
        "peak_process_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "parameters": config["parameters"], **splits,
        "artifact_hashes": {p.name: errors.file_hash(p) for p in folder.iterdir() if p.is_file()},
        "folder": str(folder),
    }
    write_json(folder / "report.json", report)
    verify_folder(folder, arrays, metadata, parts, stats, transformed, inputs)
    print("NATIVE_RUN_PASS", fold, seed, kind, "best", best_epoch,
          "top1", splits["validation"]["ranking"]["event_balanced"]["top1"], flush=True)
    return report


def execute(stage, jobs):
    choices = {"baseline": ("eadro", "diagmlp"), "count": ("diagmlp_count",),
               "zero": ("diagmlp_zero_count",)}
    if stage not in choices or not 1 <= jobs <= 3:
        raise ValueError("Invalid bounded stage/jobs")
    if stage != "baseline":
        gate = json.loads((HERE / ("gate.json" if stage == "count" else "count_gate.json")).read_text())
        errors.require(gate["allow_next_stage"] is True, "Prespecified gate not passed")
        errors.check_hash(HERE / "PROTOCOL.md", gate["protocol_sha256"])
        errors.check_hash(HERE / "baseline_runs.json", gate["baseline_runs_sha256"])
        if stage == "zero":
            errors.check_hash(HERE / "count_runs.json", gate["count_runs_sha256"])
    reports = []
    started = time.perf_counter()
    tasks = [(fold, seed, kind) for fold in FOLDS for seed in SEEDS for kind in choices[stage]]
    # Fresh processes keep each run's RSS high-water mark independent of earlier models.
    for start in range(0, len(tasks), jobs):
        with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(run_one, *task) for task in tasks[start:start + jobs]]
            for future in as_completed(futures):
                reports.append(future.result())
    reports.sort(key=lambda r: (r["fold"], r["seed"], r["kind"]))
    result = {"status": "PASS", "stage": stage, "runs": reports,
              "wall_seconds": time.perf_counter() - started, "jobs": jobs}
    output = HERE / (stage + "_runs.json")
    if output.exists():
        previous = json.loads(output.read_text())
        errors.require(previous["runs"] == reports, "Existing stage differs")
    else:
        write_json(output, result)
    print("NATIVE_STAGE_PASS", stage, len(reports), result["wall_seconds"], flush=True)


def check_cache():
    torch.set_num_threads(SETTINGS["threads"])
    arrays, metadata, inputs = load_data()
    checks = []
    for fold in FOLDS:
        parts, _, transformed = prepare_fold(arrays, fold)
        row = {"fold": fold, "sizes": {k: len(v) for k, v in parts.items()},
               "max_absolute_scaled": {
                   split: {key: float(np.abs(data[key]).max()) for key in ("metrics", "traces")}
                   for split, data in transformed.items()}}
        for kind in ("eadro", "diagmlp"):
            torch.manual_seed(11)
            model = make_model(kind, metadata["event_count"]).eval()
            for split in ("train", "validation"):
                graph, _ = graph_batch(transformed[split], np.arange(2), metadata)
                with torch.no_grad():
                    roots, detection = model(graph)
                ex_shape = (2, len(metadata["services"]))
                errors.require(tuple(roots.shape) == ex_shape and tuple(detection.shape) == (2, 2)
                               and torch.isfinite(roots).all().item()
                               and torch.isfinite(detection).all().item(), "Real-cache model smoke failed")
        checks.append(row)
    for path, digest in inputs.items():
        errors.check_hash(path, digest)
    write_json(HERE / "cache_check.json", {"status": "PASS", "checks": checks, "input_hashes": inputs,
                                        "source_hashes": source_hashes(), "training_performed": False})
    print("NATIVE_CACHE_CHECK_PASS", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("baseline", "count", "zero", "check"))
    parser.add_argument("--jobs", type=int, default=3)
    options = parser.parse_args()
    if options.stage == "check":
        check_cache()
    else:
        execute(options.stage, options.jobs)
