"""Prepare only permitted, unnormalized SN rows; never load the mixed raw NPZ."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = "research/native_reproduction_20261013/"
BUNDLE = "research/relationship_smoke_20261013/artifacts/SN"
AUDIT = "research/diagnostic_observability_20261016/sn_tt_audit.json"
PINS = {
    BUNDLE + ".json": "1956804ecec5f191b02ccf52aa189e9529acb6cd256ddde2a24c02caf3e2ae93",
    BUNDLE + ".npz": "1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb",
    NATIVE + "native_inputs/SN/raw.npz": "1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8",
    NATIVE + "native_inputs/SN/metadata.json": "d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4",
    NATIVE + "native_inputs/SN_build.json": "31728994c3aeb41ad9c4dfb401d5d15047a21f055bf81e52c80d8a2acff9e207",
    NATIVE + "native_data_build.json": "30285605c55634ca29912f9855875afc8040c60bae79aff367395067c970b455",
    NATIVE + "native_data_build.md": "d1352bf1b8ec32cae6b970baccfac5a97ba1494daac0a0fda3685ba3974df6b2",
    NATIVE + "native_data.py": "05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986",
    NATIVE + "native_data_profile.py": "86d323810f70e732d945e25358d8488df619f0d9a445697f1b77b82fbfbaaa00",
    "research/relationship_smoke_20261013/data.py": "cb6f035cefaaf8c3c67bde91c733d0d0b234a4857cd6cd88ee80a368bc34ec85",
    "research/resource_study_20261013/trace_preflight.py": "27cff85c74e628aadc518cde48047ad314932aea230f537abd5f9bf79d7a9ab7",
    AUDIT: "503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3",
    "research/sn_corrected_20261017/PLAN.md": "5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470",
}
SERVICES = [
    "social-graph-service", "compose-post-service", "post-storage-service",
    "user-timeline-service", "url-shorten-service", "user-service",
    "media-service", "text-service", "unique-id-service",
    "user-mention-service", "home-timeline-service", "nginx-web-server",
]
EDGES = [
    [1, 1], [1, 10], [1, 6], [1, 2], [1, 7], [1, 8], [1, 5], [1, 3],
    [10, 10], [10, 2], [10, 0], [2, 2], [0, 0], [0, 5], [7, 7], [7, 4],
    [7, 9], [5, 5], [3, 3], [11, 1], [11, 10], [11, 11], [11, 0], [11, 5],
]
METRICS = [
    "cpu_usage_system", "cpu_usage_total", "cpu_usage_user", "memory_usage",
    "memory_working_set", "rx_bytes", "tx_bytes",
]
RAW_SHAPES = {
    "metrics": (564, 12, 10, 7), "traces": (564, 12, 10, 2),
    "logs": (564, 12, 7), "labels": (564,),
}
KEYS = set(RAW_SHAPES) | {"indices", "fold_ids", "episode_ids", "event_ids"}
HAWKES = {
    "C": 1000, "approx": 0, "baseline_start": 0.2, "decay": 3,
    "em_max_iter": 30, "em_tol": None, "end_times": 10,
    "lasso_nuclear_ratio": 0.5, "max_iter": 50, "n_threads": 1,
    "rho": 0.1, "tol": 1e-5,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def verify_hashes(hashes):
    for name, expected in hashes.items():
        require(sha256(ROOT / name) == expected, "Source hash mismatch: " + name)


def validate_indices(indices, rows):
    require(isinstance(indices, np.ndarray) and indices.ndim == 1,
            "Indices must be a one-dimensional array")
    require(indices.dtype.kind in "iu" and indices.size > 0,
            "Indices must be nonempty integers")
    require(bool(np.all(indices >= 0) and np.all(indices < rows)),
            "Out-of-range original index")
    require(len(set(indices.tolist())) == len(indices), "Duplicate original index")


def read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        block = stream.read(min(remaining, 65536))
        require(bool(block), "Truncated NPY payload")
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def selected_npy_rows(stream, indices, shape, expected_dtype):
    """Forward-only ZipExtFile reader: rejected rows stay opaque byte blocks."""
    validate_indices(indices, shape[0])
    version = np.lib.format.read_magic(stream)
    require(version in ((1, 0), (2, 0)), "Unsupported NPY header version")
    reader = (np.lib.format.read_array_header_1_0 if version == (1, 0)
              else np.lib.format.read_array_header_2_0)
    actual_shape, fortran, dtype = reader(stream)
    require(actual_shape == shape, "Unexpected NPY shape")
    require(not fortran, "Fortran-order NPY is unsafe for row selection")
    require(not dtype.hasobject and dtype.fields is None
            and dtype == np.dtype(expected_dtype), "Unsafe or unexpected NPY dtype")
    row_items = math.prod(shape[1:])
    row_bytes = row_items * dtype.itemsize
    output = np.empty((len(indices),) + shape[1:], dtype=dtype)
    positions = {int(original): position for position, original in enumerate(indices)}
    for original in range(shape[0]):
        position = positions.get(original)
        if position is None:
            # Never construct an ndarray, inspect, reduce, or log protected bytes.
            remaining = row_bytes
            while remaining:
                block = stream.read(min(remaining, 65536))
                require(bool(block), "Truncated skipped NPY row")
                remaining -= len(block)
        else:
            payload = read_exact(stream, row_bytes)
            output[position] = np.frombuffer(payload, dtype=dtype).reshape(shape[1:])
    require(stream.read(1) == b"", "Trailing NPY payload")
    return output, {
        "shape": list(shape), "dtype": str(dtype), "order": "C",
        "decoded_rows": len(indices), "opaque_skipped_rows": shape[0] - len(indices),
        "decoded_payload_bytes": len(indices) * row_bytes,
        "opaque_skipped_payload_bytes": (shape[0] - len(indices)) * row_bytes,
    }


def selected_native_rows(path, indices):
    arrays, audits = {}, {}
    with ZipFile(path) as archive:
        expected = {key + ".npy" for key in RAW_SHAPES}
        require(len(archive.namelist()) == len(expected)
                and set(archive.namelist()) == expected, "Unexpected/duplicate NPZ members")
        for key, shape in RAW_SHAPES.items():
            with archive.open(key + ".npy") as stream:
                arrays[key], audits[key] = selected_npy_rows(
                    stream, indices, shape, "<i8" if key == "labels" else "<f8")
    return arrays, audits


def split_indices(arrays, rotation):
    """Return row positions, NOT native indices: train G(f+2), val G(f+1), eval Gf."""
    require(type(rotation) is int and rotation in (0, 1, 2), "Invalid rotation")
    folds, episodes, events = (arrays[key] for key in
                               ("fold_ids", "episode_ids", "event_ids"))
    require(folds.ndim == 1 and folds.size > 0 and folds.dtype.kind in "iu"
            and np.isin(folds, [0, 1, 2]).all(), "Invalid fold IDs")
    require(episodes.shape == events.shape == folds.shape
            and episodes.dtype.kind == events.dtype.kind == "U"
            and np.all(episodes != ""), "Invalid episode/event IDs")
    for identities in (episodes, events):
        assignment = {}
        for identity, fold in zip(identities.tolist(), folds.tolist()):
            if identity:
                require(identity not in assignment or assignment[identity] == fold,
                        "Episode/event crosses fold boundary")
                assignment[identity] = fold
    return {name: np.flatnonzero(folds == group) for name, group in (
        ("train", (rotation + 2) % 3),
        ("validation", (rotation + 1) % 3), ("evaluation", rotation))}


def validate_arrays(arrays):
    require(set(arrays) == KEYS, "Unexpected input keys")
    for key, shape in RAW_SHAPES.items():
        value = arrays[key]
        require(value.shape == (394,) + shape[1:], "Invalid selected shape: " + key)
        require(value.dtype == np.dtype("int64" if key == "labels" else "float64"),
                "Invalid selected dtype: " + key)
        require(bool(np.isfinite(value).all()), "Nonfinite selected values: " + key)
    for key in ("indices", "fold_ids", "episode_ids", "event_ids"):
        require(arrays[key].shape == (394,), "Invalid metadata array: " + key)
    validate_indices(arrays["indices"], 564)
    require(arrays["indices"].dtype == arrays["fold_ids"].dtype == np.dtype("int64"),
            "Metadata integer dtype changed")
    require(np.count_nonzero(arrays["labels"] == -1) == 69
            and np.count_nonzero((arrays["labels"] >= 0) & (arrays["labels"] < 12)) == 325,
            "Expected 325 fault and 69 normal rows")
    require(not np.any(arrays["traces"][..., 1]), "Native second trace channel changed")
    require(np.count_nonzero(arrays["traces"][..., 0]) > 0, "Missing trace signal")
    logs = arrays["logs"]
    require(bool(np.all(logs >= 0) and np.all(np.any(logs > 0, axis=(0, 1)))),
            "Logs must be nonnegative with signal in every event channel")
    require(np.array_equal(arrays["event_ids"] == "", arrays["labels"] == -1),
            "Normal event identity mismatch")
    for rotation in range(3):
        split_indices(arrays, rotation)
    require(len(set(arrays["episode_ids"])) == 36, "Expected 36 episodes")
    for fold, count, normals in ((0, 132, 24), (1, 122, 24), (2, 140, 21)):
        chosen = arrays["fold_ids"] == fold
        require(np.count_nonzero(chosen) == count
                and np.count_nonzero(chosen & (arrays["labels"] == -1)) == normals,
                "Fold row counts changed")


def verify_provenance(bundle, meta, build, report, audit):
    require(meta["normalized"] is False and report["contract"]["normalized"] is False,
            "Cache is not UNNORMALIZED")
    require(meta["services"] == bundle["services"] == SERVICES
            and meta["edges"] == EDGES and meta["metrics"] == METRICS,
            "Native services, static edges or metric order changed")
    require(meta["event_count"] == meta["event_num"] == 7
            and len(meta["templates"]) == 6 and meta["unseen_index"] == 0,
            "Native log event inventory changed")
    require(meta["window_count"] == 564 and meta["window_length"] == meta["stride"] == 10,
            "Native window contract changed")
    require(build == report["datasets"]["SN"]["build"] and build["status"] == "complete",
            "Build report mismatch")
    require(build["output_sha256"] == meta["raw_npz_sha256"]
            == bundle["provenance"]["raw_npz"]["sha256"]
            == PINS[NATIVE + "native_inputs/SN/raw.npz"], "Raw provenance mismatch")
    require(build["metadata_sha256"] == bundle["provenance"]["metadata"]["sha256"]
            == PINS[NATIVE + "native_inputs/SN/metadata.json"], "Metadata provenance mismatch")
    require(bundle["provenance"]["build"]["sha256"]
            == PINS[NATIVE + "native_inputs/SN_build.json"], "Bundle build mismatch")
    require(meta["source"] == bundle["provenance"]["native_source"]
            and meta["source"]["feature_build_source_sha256"]
            == PINS[NATIVE + "native_data.py"], "Producer source mismatch")
    require(meta["prepared_npz_sha256"] == bundle["provenance"]["prepared_npz_sha256"]
            == report["datasets"]["SN"]["prepared_npz_sha256"], "Prepared cache mismatch")
    for key, shape in RAW_SHAPES.items():
        require(build["array_shapes"][key] == list(shape)
                and build["array_dtypes"][key] == ("int64" if key == "labels" else "float64"),
                "Build schema changed")
    training = meta["template_training"]
    require(training == report["datasets"]["SN"]["template_training"]
            and len(training["sources"]) == 3 and training["lines"] == 53522
            and all(name.startswith("no fault/SN.") for name in training["sources"])
            and all(name in meta["input_sha256"] for name in training["sources"]),
            "Drain templates lack external three-normal-recording provenance")
    calibration = report["calibration"]["datasets"]["SN"]
    require(calibration["native_defaults"] == HAWKES
            and calibration["same_seed_exact_determinism"] is True,
            "Native Hawkes configuration changed")
    repairs = meta["repairs"]
    require(repairs["normalization"] == "NONE; parent fits training-only scalers"
            and repairs["hawkes"] == "native HawkesADM4 defaults, relative horizon10, decay3, baseline_start=.2"
            and repairs["solver_rng"] == "default random uniform adjacency; NumPy seed42+window*N+node per fit"
            and repairs["memoization"] == "disabled", "Per-window cache provenance changed")
    require(audit["status"] == "PASS"
            and audit["inputs_sha256"][BUNDLE + ".npz"] == PINS[BUNDLE + ".npz"]
            and audit["inputs_sha256"][BUNDLE + ".json"] == PINS[BUNDLE + ".json"],
            "Audit does not bind permitted bundle")
    evidence = audit["systems"]["SN"]
    require(all(evidence["checks"].values()) and all(bundle["checks"].values())
            and evidence["preflight_existing_evidence"]["distinct_conflicting_selected_identities"] == 0,
            "Existing observation/episode audit failed")
    require(evidence["boundary_audit"]["fault_windows_crossing_injection_boundary"] == 37,
            "Boundary provenance changed")
    return evidence


def verify_windows(arrays, bundle, meta, evidence):
    faults = bundle["faults"]
    native_faults = {
        fault["event_id"]: dict(fault, run_id=run["run_id"])
        for run in meta["runs"] for fault in run["faults"]
    }
    require(faults == native_faults and len(faults) == 36, "Fault map changed")
    require({(f["root"], f["fault_type"]) for f in faults.values()}
            == {(root, kind) for root in range(12)
                for kind in ("cpu_load", "network_delay", "network_loss")},
            "Root/type combinations changed")
    windows = []
    for row, original in enumerate(arrays["indices"]):
        window = meta["windows"][int(original)]
        require(window == bundle["windows"][row] and window["end"] == window["start"] + 9,
                "Permitted window order/provenance changed")
        event, episode = str(arrays["event_ids"][row]), str(arrays["episode_ids"][row])
        label, fold = int(arrays["labels"][row]), int(arrays["fold_ids"][row])
        require(event == (window["event_id"] or "") and episode in faults
                and bundle["event_folds"][episode] == fold, "Event/episode/fold mismatch")
        candidates = [f for f in faults.values() if f["run_id"] == window["run_id"]]
        overlaps = [f for f in candidates if f["start"] <= window["end"]
                    and f["end_inclusive"] >= window["start"]]
        if label >= 0:
            require(len(overlaps) == 1 and overlaps[0]["event_id"] == event == episode
                    and faults[event]["root"] == label
                    and faults[event]["service"] == SERVICES[label]
                    and window["root_fault_group"] == faults[event]["root_fault_group"],
                    "Fault label/overlap mismatch")
        else:
            require(not overlaps and window["root_fault_group"] is None,
                    "Normal row overlaps fault")
            nearest = min(candidates, key=lambda f: (
                max(f["start"] - window["end"], window["start"] - f["end_inclusive"], 0),
                f["start"], f["event_id"]))
            require(nearest["event_id"] == episode, "Normal episode assignment changed")
        windows.append(dict(window, original_index=int(original), label=label,
                            episode_id=episode, fold_id=fold))
    ordered = sorted(windows, key=lambda w: (w["run_id"], w["start"]))
    for left, right in zip(ordered, ordered[1:]):
        require(left["run_id"] != right["run_id"] or left["end"] < right["start"],
                "Selected observation times overlap")
    require(set(arrays["event_ids"]) - {""} == set(faults), "Missing event")
    for fold in range(3):
        events = {event for event, f in bundle["event_folds"].items() if f == fold}
        require(Counter(faults[e]["root"] for e in events) == Counter(range(12))
                and Counter(faults[e]["fault_type"] for e in events)
                == Counter({"cpu_load": 4, "network_delay": 4, "network_loss": 4}),
                "Fold root/type support changed")
    episodes = [{
        "episode": episode, "fold": int(arrays["fold_ids"][arrays["episode_ids"] == episode][0]),
        "windows": int(np.count_nonzero(arrays["episode_ids"] == episode)),
        "normal_windows": int(np.count_nonzero((arrays["episode_ids"] == episode)
                                             & (arrays["labels"] == -1))),
    } for episode in sorted(faults)]
    require(episodes == [{k: v for k, v in item.items() if k != "partition"}
                         for item in evidence["episodes"]], "Existing episode audit differs")
    return windows


def manifest_digest(manifest):
    payload = {key: value for key, value in manifest.items() if key != "manifest_payload_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def load_inputs():
    """Load the eight-key permitted bundle after verifying source and output hashes."""
    manifest = read_json(HERE / "input_manifest.json")
    require(manifest.get("manifest_payload_sha256") == manifest_digest(manifest),
            "Manifest payload hash mismatch")
    expected_sources = dict(PINS)
    for name in ("input_bundle.py", "test_input_bundle.py"):
        path = HERE / name
        expected_sources[str(path.relative_to(ROOT))] = sha256(path)
    require(manifest["source_hashes"] == expected_sources, "Source inventory/hash mismatch")
    verify_hashes(expected_sources)
    path = HERE / "inputs.npz"
    require(sha256(path) == manifest["input_npz_sha256"], "Generated input hash mismatch")
    with np.load(path, allow_pickle=False) as source:
        require(set(source.files) == KEYS and len(source.files) == len(KEYS),
                "Unexpected generated NPZ keys")
        arrays = {key: source[key] for key in source.files}
    validate_arrays(arrays)
    require(manifest["services"] == SERVICES and manifest["edges"] == EDGES
            and manifest["event_count"] == 7 and manifest["normalized"] is False,
            "Generated native contract changed")
    require(len(manifest["windows"]) == 394, "Invalid window manifest")
    for row, window in enumerate(manifest["windows"]):
        require(window["original_index"] == int(arrays["indices"][row])
                and window["label"] == int(arrays["labels"][row])
                and window["fold_id"] == int(arrays["fold_ids"][row])
                and window["episode_id"] == str(arrays["episode_ids"][row])
                and (window["event_id"] or "") == str(arrays["event_ids"][row]),
                "Generated manifest/array order mismatch")
    return arrays, manifest


def prepare():
    require(sys.version_info[:2] == (3, 8) and np.__version__ == "1.21.5",
            "Use existing .venv-eadro Python3.8 / NumPy1.21.5")
    for name in ("inputs.npz", "input_manifest.json"):
        require(not (HERE / name).exists(), "Refusing to overwrite " + name)
    verify_hashes(PINS)
    bundle = read_json(ROOT / (BUNDLE + ".json"))
    meta = read_json(ROOT / (NATIVE + "native_inputs/SN/metadata.json"))
    build = read_json(ROOT / (NATIVE + "native_inputs/SN_build.json"))
    report = read_json(ROOT / (NATIVE + "native_data_build.json"))
    audit = read_json(ROOT / AUDIT)
    evidence = verify_provenance(bundle, meta, build, report, audit)
    with np.load(ROOT / (BUNDLE + ".npz"), allow_pickle=False) as permitted:
        allowed = {key: permitted[key] for key in
                   ("values", "labels", "indices", "fold_ids", "episode_ids", "event_ids")}
    validate_indices(allowed["indices"], 564)
    require(len(allowed["indices"]) == 394, "Permitted inventory is not 394 rows")
    index_payload = json.dumps(allowed["indices"].tolist(), separators=(",", ":")).encode()
    require(hashlib.sha256(index_payload).hexdigest()
            == bundle["provenance"]["split"]["selected_indices_sha256"],
            "Permitted ordered index hash mismatch")
    arrays, loader_audit = selected_native_rows(
        ROOT / (NATIVE + "native_inputs/SN/raw.npz"), allowed["indices"])
    require(np.array_equal(arrays["labels"], allowed["labels"]), "Allowed labels differ")
    require(allowed["values"].shape == (394, 12, 10, 9)
            and np.array_equal(arrays["metrics"], allowed["values"][..., :7]),
            "Selected seven raw metrics differ from allowed values")
    require(np.array_equal(arrays["traces"][..., 0], allowed["values"][..., 7]),
            "Selected native trace mean differs from allowed values")
    arrays.update({key: allowed[key] for key in
                   ("indices", "fold_ids", "episode_ids", "event_ids")})
    validate_arrays(arrays)
    windows = verify_windows(arrays, bundle, meta, evidence)
    sources = dict(PINS)
    sources.update({str((HERE / name).relative_to(ROOT)): sha256(HERE / name)
                    for name in ("input_bundle.py", "test_input_bundle.py")})
    verify_hashes(sources)
    manifest = {
        "status": "PASS", "system": "SN", "normalized": False,
        "services": SERVICES, "edges": EDGES, "event_count": 7, "fault_event_count": 36,
        "metrics": METRICS, "windows": windows, "faults": bundle["faults"],
        "event_folds": bundle["event_folds"], "source_hashes": sources,
        "source": meta["source"], "raw_input_hashes_recorded_not_reopened": meta["input_sha256"],
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__},
        "template_training": dict(meta["template_training"],
                                  role="external normal reference shared by all rotations"),
        "hawkes": dict(HAWKES, per_window=True, tick_version="0.7.0.1",
                       seed="42 + original_window_index*12 + node", memoization=False,
                       log_semantics=meta["repairs"]["logs"]),
        "reused_verification": {
            "audit_path": AUDIT, "checks": evidence["checks"],
            "boundary_audit": evidence["boundary_audit"],
            "selected_identity_audit": evidence["preflight_existing_evidence"],
            "interpretation": "Zero conflicting selected identities include start/duration signatures; "
                              "nonoverlapping selected start windows preserve identity isolation.",
        },
        "protection": {
            "permitted_rows": 394, "excluded_test_rows": 169, "excluded_unassigned_rows": 1,
            "protected_rows_decoded": 0, "raw_streams_scanned": False,
            "source_archive_hashing": "SHA256 of compressed source bytes, not observation interpretation",
            "traversal": "ZipExtFile decompression/CRC may visit all bytes; excluded row payloads "
                         "are discarded as opaque bytes, never ndarrays/reductions/logged values",
            "permission_source": BUNDLE + ".npz, hash pinned before reading original indices",
        },
        "loader_audit": loader_audit,
        "checks": {"labels_exact": True, "metrics7_exact": True, "trace_mean_exact": True,
                   "trace_second_channel_zero": True, "windows_ordered": True,
                   "normal_episode_isolation": True, "all_rotations_disjoint": True,
                   "logs_finite_nonnegative": True},
        "log_nonzero_cells_per_channel": np.count_nonzero(arrays["logs"], axis=(0, 1)).tolist(),
        "splits": {str(f): {name: len(rows) for name, rows in split_indices(arrays, f).items()}
                   for f in range(3)},
        "limitations": [
            "No scaler fitted or training performed; parent must fit each rotation on train rows only.",
            "Drain/Hawkes/raw identity provenance reused by hashes; raw streams not rescanned.",
            "Logs have no independent values in permitted bundle; verified against hash-bound native cache.",
            "Native solver reached max_iter50 on 549 SN fits; no new convergence claim.",
            "Previously analyzed development events, not recording-independent or pristine blind test.",
        ],
    }
    with (HERE / "inputs.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    manifest["input_npz_sha256"] = sha256(HERE / "inputs.npz")
    manifest["manifest_payload_sha256"] = manifest_digest(manifest)
    with (HERE / "input_manifest.json").open("x") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    loaded, _ = load_inputs()
    require(all(np.array_equal(loaded[key], value) for key, value in arrays.items()),
            "Generated reload differs")
    print("PASS INPUT_PREPARATION rows=394 fault=325 normal=69 episodes=36 folds=132/122/140")
    print("PASS PROTECTION decoded=394 opaque_skipped=170 per_member; protected_decoded=0")
    print("PASS INPUT_NPZ_SHA256 " + manifest["input_npz_sha256"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    else:
        loaded_arrays, loaded_manifest = load_inputs()
        print("PASS INPUT_VERIFY rows={} sha256={}".format(
            len(loaded_arrays["indices"]), loaded_manifest["input_npz_sha256"]))
