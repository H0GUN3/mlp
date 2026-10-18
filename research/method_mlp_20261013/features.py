#!/usr/bin/env python3
"""Shared local/relative MLP features; no model imports or held-out evaluation."""
import argparse
from collections import Counter
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict

import numpy as np

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
INPUTS = NATIVE / "native_inputs"
OUTPUT = HERE / "features"
sys.path.insert(0, str(NATIVE))
profile = importlib.import_module("native_data_profile")
METRICS, ROOTS, SERVICES, json_array = (
    profile.METRICS, profile.ROOTS, profile.SERVICES, profile.json_array,
)

BUILD_HASHES = {
    "SN": "31728994c3aeb41ad9c4dfb401d5d15047a21f055bf81e52c80d8a2acff9e207",
    "TT": "00887cae019153e8cee1b842751179be51fdc431139705993db6f60cf0267ba6",
}
SPLIT_HASHES = {
    "SN": "c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d",
    "TT": "bc31c71a30f91f968854cd71d7264716d251c470121e7e363533965086c52a3e",
}
TRAIN_SOURCE_HASH = "48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7"
CHANNELS = METRICS + ["trace_mean_duration_seconds", "retained_span_count"]
FEATURE_NAMES = (
    [c + "__signed_log_z_mean" for c in CHANNELS]
    + [c + "__abs_z_gt_2_fraction" for c in CHANNELS]
)
KEYS = {"x", "mask", "coverage", "labels", "indices", "event_ids", "partition"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> str:
    actual = file_hash(path)
    if actual != expected:
        raise ValueError("Hash mismatch: " + str(path))
    return actual


def digest_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def original_split(count: int) -> Dict[str, np.ndarray]:
    permutation = np.random.RandomState(42).permutation(count)
    trainval, test = math.floor(.7 * count), math.floor(.3 * count)
    validation = math.floor(.2 * trainval)
    training = trainval - validation
    return {
        "train": permutation[:training],
        "validation": permutation[training:trainval],
        "test": permutation[trainval:trainval + test],
        "unassigned": permutation[trainval + test:],
    }


def load_selected(system: str):
    build_path = INPUTS / (system + "_build.json")
    build_hash = require_hash(build_path, BUILD_HASHES[system])
    build = json.loads(build_path.read_text())
    if build["status"] != "complete" or build["dataset"] != system:
        raise ValueError("Incomplete native build")
    meta_path = INPUTS / system / "metadata.json"
    raw_path = INPUTS / system / "raw.npz"
    meta_hash = require_hash(meta_path, build["metadata_sha256"])
    raw_hash = require_hash(raw_path, build["output_sha256"])
    meta = json.loads(meta_path.read_text())
    if (meta["system"] != system or meta["services"] != SERVICES[system]
            or meta["metrics"] != METRICS or meta["normalized"] is not False
            or meta["window_length"] != 10 or meta["stride"] != 10
            or meta["raw_npz_sha256"] != raw_hash):
        raise ValueError("Native input contract changed")
    source = meta["source"]
    source_hashes = {
        "native_data.py": require_hash(NATIVE / "native_data.py", source["feature_build_source_sha256"]),
        "native_data_profile.py": require_hash(
            NATIVE / "native_data_profile.py", source["reused_profile_helpers_sha256"]),
        "native_train.py": require_hash(NATIVE / "native_train.py", TRAIN_SOURCE_HASH),
    }
    prepared_hash = require_hash(
        INPUTS / (system + "_prepared.npz"), meta["prepared_npz_sha256"])
    repairs = meta["repairs"]
    if (repairs["clock_shifts_seconds"] != {
            "records_metrics": 57600, "spans": 28800, "logs": 28800}
            or repairs["trace"] !=
            "source per-second mean duration seconds, channel1 zero; all duplicate occurrences retained"
            or repairs["recording_clip"] != "[int(start)+16h,int(end)+16h)"):
        raise ValueError("Native clock/retention policy changed")
    count = meta["window_count"]
    if count != {"SN": 564, "TT": 5814}[system] or len(meta["windows"]) != count:
        raise ValueError("Native window count mismatch")
    parts = original_split(count)
    split_path = NATIVE / "calibration200" / system / "eadro/seed_11/split.json"
    split_hash = require_hash(split_path, SPLIT_HASHES[system])
    stored = json.loads(split_path.read_text())
    if stored["seed"] != 42 or any(
        stored["indices"][k] != v.tolist() for k, v in parts.items()
    ):
        raise ValueError("Original seed42 split mismatch")
    indices = np.concatenate((parts["train"], parts["validation"])).astype(np.int64)
    partition = np.array(
        ["train"] * len(parts["train"]) + ["validation"] * len(parts["validation"]),
        dtype=str,
    )
    # NPZ members decode whole arrays, but only these selected rows are retained/checked.
    with np.load(raw_path, allow_pickle=False) as archive:
        if set(archive.files) != {"metrics", "traces", "logs", "labels"}:
            raise ValueError("Native NPZ keys changed")
        arrays = {key: archive[key][indices] for key in ("metrics", "traces", "labels")}
    nodes = len(meta["services"])
    for key, shape, dtype in (
        ("metrics", (len(indices), nodes, 10, 7), np.dtype("float64")),
        ("traces", (len(indices), nodes, 10, 2), np.dtype("float64")),
        ("labels", (len(indices),), np.dtype("int64")),
    ):
        if arrays[key].shape != shape or arrays[key].dtype != dtype or not np.isfinite(arrays[key]).all():
            raise ValueError("Invalid selected native " + key)
    if (np.any(arrays["labels"] < -1) or np.any(arrays["labels"] >= nodes)
            or np.any(arrays["traces"][..., 1] != 0)):
        raise ValueError("Selected native labels/trace contract mismatch")
    provenance = {
        "build": {"path": str(build_path), "sha256": build_hash},
        "metadata": {"path": str(meta_path), "sha256": meta_hash},
        "raw_npz": {"path": str(raw_path), "sha256": raw_hash},
        "prepared_npz_sha256": prepared_hash,
        "native_source": source,
        "current_native_source_hashes": source_hashes,
        "split": {"path": str(split_path), "sha256": split_hash, "seed": 42,
                  "counts": {k: len(v) for k, v in parts.items()},
                  "selected_indices_sha256": digest_json(indices.tolist())},
    }
    return arrays, meta, indices, partition, provenance


def check_metric_evidence(system: str, meta: Dict[str, Any]) -> Dict[str, str]:
    """Verify bytes bound to the producer's complete-numeric metric_series gate."""
    root = ROOTS[system]
    hashes = {}
    for run in meta["runs"]:
        folder = root / "data" / run["run_id"] / "metrics"
        if sorted(p.stem for p in folder.glob("*.csv")) != sorted(meta["services"]):
            raise ValueError("Metric service inventory mismatch")
        for service in meta["services"]:
            path = folder / (service + ".csv")
            name = str(path.relative_to(root))
            hashes[name] = require_hash(path, meta["input_sha256"][name])
        record_path = root / run["record_json"]
        name = str(record_path.relative_to(root))
        hashes[name] = require_hash(record_path, meta["input_sha256"][name])
    return hashes


def reconstruct_trace(path: Path, services, run, selected_starts, expected_hash: str):
    """One bounded stream, retaining duplicate occurrences only in selected windows."""
    selected_starts = np.asarray(selected_starts, dtype=np.int64)
    lookup = {int(start): row for row, start in enumerate(selected_starts)}
    if len(lookup) != len(selected_starts):
        raise ValueError("Duplicate selected window start")
    start, end = run["record_start"], run["record_end_exclusive"]
    if (np.any(selected_starts < start) or np.any(selected_starts + 10 > end)
            or np.any((selected_starts - start) % 10 != 0)):
        raise ValueError("Selected window outside native recording grid")
    sums = np.zeros((len(selected_starts), len(services), 10), dtype=np.float64)
    counts = np.zeros(sums.shape, dtype=np.int64)
    node_map = {s: i for i, s in enumerate(services)}
    audit: Counter = Counter()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for trace in json_array(stream, digest):
            for span in trace["spans"]:
                stamp_us, duration = span.get("startTime"), span.get("duration")
                if type(stamp_us) is not int or type(duration) is not int or duration < 0:
                    raise ValueError("Invalid native span timestamp/duration")
                process = trace["processes"].get(span["processID"])
                if process is None or process["serviceName"] not in node_map:
                    raise ValueError("Unresolved or unknown span service")
                if (not isinstance(span.get("traceID"), str) or not span["traceID"]
                        or span["traceID"] != trace["traceID"]
                        or not isinstance(span.get("spanID"), str) or not span["spanID"]):
                    raise ValueError("Invalid trace/span identity")
                stamp = stamp_us // 1000000 + 28800
                audit["raw_span_occurrences"] += 1
                if not start <= stamp < end:
                    audit["record_clipped_occurrences"] += 1
                    continue
                audit["kept_occurrences"] += 1
                offset = stamp - start
                row = lookup.get(start + (offset // 10) * 10)
                if row is None:
                    continue
                node, second = node_map[process["serviceName"]], offset % 10
                sums[row, node, second] += duration / 1000000.0
                counts[row, node, second] += 1
                audit["selected_span_occurrences"] += 1
                audit["selected_zero_duration_occurrences"] += int(duration == 0)
    if digest.hexdigest() != expected_hash:
        raise ValueError("Hash mismatch: " + str(path))
    latency = np.zeros_like(sums)
    np.divide(sums, counts, out=latency, where=counts > 0)
    audit["selected_observed_latency_seconds"] = int(np.count_nonzero(counts))
    audit["selected_observed_zero_latency_seconds"] = int(np.count_nonzero((counts > 0) & (latency == 0)))
    return latency, counts, dict(audit), digest.hexdigest()


def require_trace_equal(reconstructed: np.ndarray, existing: np.ndarray) -> None:
    if not np.array_equal(reconstructed, existing):
        raise ValueError("Reconstructed trace latency differs from existing native array")


def fit_reference(values: np.ndarray, observed: np.ndarray, labels: np.ndarray,
                  partition: np.ndarray) -> Dict[str, np.ndarray]:
    if values.shape != observed.shape or values.ndim != 4 or values.shape[2:] != (10, 9):
        raise ValueError("Expected [rows,nodes,10,9] values/observations")
    if labels.shape != (len(values),) or partition.shape != labels.shape:
        raise ValueError("Reference row metadata mismatch")
    normal = (partition == "train") & (labels == -1)
    shape = (values.shape[1], 9)
    median = np.zeros(shape, dtype=np.float64)
    scale = np.ones(shape, dtype=np.float64)
    count = np.zeros(shape, dtype=np.int64)
    for node in range(shape[0]):
        for channel in range(9):
            sample = values[normal, node, :, channel][observed[normal, node, :, channel]]
            if not np.isfinite(sample).all():
                raise ValueError("Nonfinite observed normal TRAIN input")
            count[node, channel] = len(sample)
            if len(sample):
                q25, center, q75 = np.percentile(sample, [25, 50, 75])
                median[node, channel] = center
                scale[node, channel] = max(q75 - q25, .05 * abs(center), 1e-8)
    return {"median": median, "scale": scale, "count": count, "mask": count > 0}


def window_features(values: np.ndarray, observed: np.ndarray, reference):
    if values.shape != observed.shape or values.ndim != 4 or values.shape[2:] != (10, 9):
        raise ValueError("Expected [rows,nodes,10,9] values/observations")
    if not np.isfinite(values[observed]).all():
        raise ValueError("Nonfinite observed input")
    current_count = observed.sum(axis=2)
    valid = observed & reference["mask"][None, :, None, :]
    safe = np.where(valid, values, reference["median"][None, :, None, :])
    z = (safe - reference["median"][None, :, None, :]) / reference["scale"][None, :, None, :]
    denominator = np.maximum(current_count, 1)
    change = (np.sign(z) * np.log1p(np.abs(z))).sum(axis=2) / denominator
    persistence = (valid & (np.abs(z) > 2)).sum(axis=2) / denominator
    mask = (current_count > 0) & reference["mask"][None, :, :]
    x = np.concatenate((change, persistence), axis=-1).astype(np.float32)
    masks = np.concatenate((mask, mask), axis=-1)
    coverage = np.concatenate((current_count / 10., current_count / 10.), axis=-1).astype(np.float32)
    x[~masks] = 0
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite output features")
    return x, masks, coverage


def validate_output(arrays, nodes: int) -> None:
    if set(arrays) != KEYS:
        raise ValueError("Feature output keys mismatch")
    rows = len(arrays["indices"])
    for key, dtype in (("x", np.float32), ("mask", np.bool_), ("coverage", np.float32)):
        if arrays[key].shape != (rows, nodes, 18) or arrays[key].dtype != np.dtype(dtype):
            raise ValueError("Feature output shape/dtype mismatch: " + key)
    for key in ("labels", "indices"):
        if arrays[key].shape != (rows,) or arrays[key].dtype != np.dtype(np.int64):
            raise ValueError("Invalid integer output: " + key)
    for key in ("event_ids", "partition"):
        if arrays[key].shape != (rows,) or arrays[key].dtype.kind != "U":
            raise ValueError("Invalid Unicode output: " + key)
    if (len(np.unique(arrays["indices"])) != rows
            or not np.isin(arrays["partition"], ["train", "validation"]).all()
            or np.any(arrays["labels"] < -1) or np.any(arrays["labels"] >= nodes)
            or np.any((arrays["labels"] == -1) != (arrays["event_ids"] == ""))
            or not np.isfinite(arrays["x"]).all()
            or not np.isfinite(arrays["coverage"]).all()
            or np.any(arrays["x"][~arrays["mask"]] != 0)
            or np.any(arrays["mask"] & (arrays["coverage"] == 0))
            or np.any(arrays["coverage"] < 0) or np.any(arrays["coverage"] > 1)
            or not np.array_equal(arrays["mask"][..., :9], arrays["mask"][..., 9:])
            or not np.array_equal(arrays["coverage"][..., :9], arrays["coverage"][..., 9:])):
        raise ValueError("Invalid feature output values/provenance")


def prepare_system(system: str):
    started = time.perf_counter()
    native, meta, indices, partition, provenance = load_selected(system)
    raw_hashes = check_metric_evidence(system, meta)
    rows, nodes = len(indices), len(meta["services"])
    values = np.zeros((rows, nodes, 10, 9), dtype=np.float64)
    values[..., :7] = native["metrics"]
    observed = np.ones(values.shape, dtype=np.bool_)
    observed[..., 7] = False
    windows = [meta["windows"][int(i)] for i in indices]
    run_rows = {}
    for row, window in enumerate(windows):
        if window["end"] != window["start"] + 9:
            raise ValueError("Native window interval changed")
        run_rows.setdefault(window["run_id"], []).append(row)
    audits = {}
    for run in meta["runs"]:
        run_id = run["run_id"]
        # Validate the full metadata grid, without examining held-out feature values.
        original = [w["start"] for w in meta["windows"] if w["run_id"] == run_id]
        expected = list(range(run["record_start"], run["record_end_exclusive"] - 9, 10))
        if original != expected or len(expected) != run["windows"]:
            raise ValueError("Native recording/window grid mismatch")
        selected = np.array(run_rows.pop(run_id, []), dtype=np.int64)
        starts = [windows[int(i)]["start"] for i in selected]
        path = ROOTS[system] / "data" / run_id / "spans.json"
        name = str(path.relative_to(ROOTS[system]))
        latency, counts, audit, span_hash = reconstruct_trace(
            path, meta["services"], run, starts, meta["input_sha256"][name])
        require_trace_equal(latency, native["traces"][selected, :, :, 0])
        values[selected, :, :, 7] = latency
        values[selected, :, :, 8] = counts
        observed[selected, :, :, 7] = counts > 0
        audits[run_id] = audit
        raw_hashes[name] = span_hash
        print("FEATURE_STREAM {} {} selected_rows={} retained_spans={}".format(
            system, run_id, len(selected), int(counts.sum())), flush=True)
    if run_rows:
        raise ValueError("Unknown selected recording")
    totals = {key: sum(a.get(key, 0) for a in audits.values())
              for key in set().union(*(a.keys() for a in audits.values()))}
    for key in ("raw_span_occurrences", "kept_occurrences", "record_clipped_occurrences"):
        if totals[key] != meta["span_audit"]["counts"][key]:
            raise ValueError("Native span audit total mismatch: " + key)
    reference = fit_reference(values, observed, native["labels"], partition)
    x, mask, coverage = window_features(values, observed, reference)
    arrays = {
        "x": x, "mask": mask, "coverage": coverage,
        "labels": native["labels"], "indices": indices,
        "event_ids": np.array([w["event_id"] or "" for w in windows], dtype=str),
        "partition": partition,
    }
    validate_output(arrays, nodes)
    require_hash(INPUTS / system / "metadata.json", provenance["metadata"]["sha256"])
    require_hash(INPUTS / system / "raw.npz", provenance["raw_npz"]["sha256"])
    manifest = {
        "system": system, "feature_names": FEATURE_NAMES, "raw_channels": CHANNELS,
        "services": meta["services"], "F": 18, "pre_standardization": True,
        "original_indices": indices.tolist(), "partition": partition.tolist(),
        "windows": [{k: w[k] for k in ("run_id", "start", "end", "event_id")} for w in windows],
        "provenance": provenance, "raw_input_hashes": raw_hashes,
        "code_sha256": file_hash(Path(__file__)),
        "tests_sha256": file_hash(HERE / "features_tests.py"),
        "protocol_sha256": file_hash(HERE / "PROTOCOL.md"),
        "normal_reference": {key: value.tolist() for key, value in reference.items()},
        "normal_train_indices": indices[(partition == "train") & (native["labels"] == -1)].tolist(),
        "reference_quantiles": "NumPy percentile linear interpolation: 25/50/75; scale=max(IQR,.05*abs(median),1e-8)",
        "missing_reference_placeholder": "median=0, scale=1, count=0, mask=false; never used as reference",
        "observation_policy": {
            "metrics": "All seconds observed: pinned metric_series requires finite numeric CSV, unique contiguous seconds and full recording coverage; original CSV hashes rechecked.",
            "latency": "Observed iff retained span count>0, including true zero duration.",
            "count": "Every selected recording second measures retained occurrences, including count0; NOT collector health or actual request count.",
            "mask": "current observations AND normal TRAIN reference availability",
            "coverage": "actual observed seconds/10, repeated for both features, independent of reference",
        },
        "trace_checks": {"exact_selected_native_latency_equality": True,
                         "per_run": audits, "totals": totals},
        "counts": {
            "rows": rows, "nodes": nodes,
            "train": int(np.count_nonzero(partition == "train")),
            "validation": int(np.count_nonzero(partition == "validation")),
            "normal_train": int(np.count_nonzero((partition == "train") & (native["labels"] == -1))),
            "normal_validation": int(np.count_nonzero((partition == "validation") & (native["labels"] == -1))),
            "reference_missing_channels": int(np.count_nonzero(~reference["mask"])),
            "valid_feature_slots": int(np.count_nonzero(mask)),
        },
        "checks": {
            "native_build_metadata_raw_prepared_hashes": True,
            "metric_csv_and_record_hashes": True, "original_split_exact": True,
            "normal_reference_train_only": True, "test_evaluated": False,
            "test_trace_seconds_accumulated": False, "logs_loaded": False,
            "output_contract": True, "zero_invalid_slots": True,
        },
        "limitations": [
            "Window splits share injection events; no unseen-incident or service-identity generalization claim.",
            "Duplicate span weighting retained; count0 does not establish collector health.",
            "Original streams must be scanned/hash-checked across recordings, but only TRAIN/validation seconds accumulate duration/count features.",
            "Compressed native NPZ members decode before row selection; held-out values are not checked, fitted, evaluated or exported.",
            "No logs, Hawkes, feature standardization, model training or protected-test predictions.",
        ],
        "prepare_seconds": time.perf_counter() - started,
    }
    print("FEATURE_PREPARED {} {}".format(system, json.dumps(manifest["counts"])), flush=True)
    return arrays, manifest


def refuse_outputs(directory: Path, systems) -> None:
    for system in systems:
        for suffix in (".npz", ".json"):
            path = directory / (system + suffix)
            if path.exists() or path.is_symlink():
                raise FileExistsError("Refusing to overwrite final feature artifact: " + str(path))


def prepare_both() -> None:
    systems = ("SN", "TT")
    OUTPUT.mkdir(exist_ok=True)
    refuse_outputs(OUTPUT, systems)
    # Stage and reload-check BOTH systems before publishing any final name.
    with tempfile.TemporaryDirectory(prefix=".staging-", dir=str(OUTPUT)) as temporary:
        stage = Path(temporary)
        for system in systems:
            arrays, manifest = prepare_system(system)
            npz_path = stage / (system + ".npz")
            with npz_path.open("xb") as stream:
                np.savez_compressed(stream, **arrays)
            with np.load(npz_path, allow_pickle=False) as archive:
                saved = {key: archive[key] for key in archive.files}
            validate_output(saved, len(manifest["services"]))
            if any(not np.array_equal(saved[key], arrays[key]) for key in KEYS):
                raise ValueError("Saved feature replay mismatch")
            manifest["npz_sha256"] = file_hash(npz_path)
            with (stage / (system + ".json")).open("x") as stream:
                json.dump(manifest, stream, indent=2, allow_nan=False)
                stream.write("\n")
        refuse_outputs(OUTPUT, systems)
        published = []
        try:
            for system in systems:
                for suffix in (".npz", ".json"):
                    destination = OUTPUT / (system + suffix)
                    os.link(str(stage / (system + suffix)), str(destination))
                    published.append(destination)
        except BaseException:
            for path in published:
                path.unlink()
            raise
    print("FEATURE_PREPARE_BOTH_COMPLETE", flush=True)


def verify_artifacts() -> None:
    for system in ("SN", "TT"):
        manifest = json.loads((OUTPUT / (system + ".json")).read_text())
        npz_path = OUTPUT / (system + ".npz")
        require_hash(npz_path, manifest["npz_sha256"])
        require_hash(Path(__file__), manifest["code_sha256"])
        require_hash(HERE / "features_tests.py", manifest["tests_sha256"])
        require_hash(HERE / "PROTOCOL.md", manifest["protocol_sha256"])
        native, meta, indices, partition, provenance = load_selected(system)
        with np.load(npz_path, allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        validate_output(arrays, len(meta["services"]))
        for key, expected in (("indices", indices), ("partition", partition),
                              ("labels", native["labels"]),
                              ("event_ids", np.array([meta["windows"][int(i)]["event_id"] or "" for i in indices]))):
            if not np.array_equal(arrays[key], expected):
                raise ValueError("Saved original provenance mismatch: " + key)
        if manifest["provenance"] != provenance or manifest["services"] != meta["services"]:
            raise ValueError("Saved manifest provenance mismatch")
        print("FEATURE_VERIFIED {} {}".format(system, json.dumps(manifest["counts"])), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "verify"))
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5":
        raise ValueError("Use installed .venv-eadro Python3.8 / NumPy1.21.5")
    if args.stage == "prepare":
        prepare_both()
    else:
        verify_artifacts()


if __name__ == "__main__":
    main()
