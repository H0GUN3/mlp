"""SN-only selection: decompress skipped bytes, never decode skipped observations."""
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, IO, Iterable, List, Tuple
import zipfile

import numpy as np
from numpy.lib import format as npy


HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
RAW = NATIVE / "native_inputs/SN/raw.npz"
PREPARED = NATIVE / "native_inputs/SN_prepared.npz"
SPLIT = NATIVE / "calibration200/SN/eadro/seed_11/split.json"
DISCLOSURE = (
    "ZIP members are sequentially decompressed, including unselected byte blocks. "
    "Unselected observation bytes are discarded without ndarray construction, "
    "numeric interpretation, validation or retention. log_window alone is decoded "
    "in full as structural indexing metadata. Only selected log_node, "
    "log_template, log_timestamp and window_start values are interpreted."
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    with path.open() as stream:
        return json.load(stream)


def header(archive: zipfile.ZipFile, key: str,
           stream: IO[bytes]) -> Tuple[Tuple[int, ...], np.dtype]:
    if archive.namelist().count(key + ".npy") != 1:
        raise ValueError("Missing/duplicate NPY member: " + key)
    version = npy.read_magic(stream)
    if version == (1, 0):
        shape, fortran, dtype = npy.read_array_header_1_0(stream)
    elif version == (2, 0):
        shape, fortran, dtype = npy.read_array_header_2_0(stream)
    else:
        raise ValueError("Unsupported NPY version: " + str(version))
    if (fortran or dtype.hasobject or dtype.fields is not None
            or dtype.kind not in "fiu" or not shape
            or any(type(n) is not int or n < 0 for n in shape)):
        raise ValueError("Expected C-order plain numeric NPY: " + key)
    expected_size = stream.tell() + math.prod(shape) * dtype.itemsize
    if archive.getinfo(key + ".npy").file_size != expected_size:
        raise ValueError("NPY member byte size mismatch: " + key)
    return shape, dtype


def member_shape(path: Path, key: str) -> Tuple[int, ...]:
    with zipfile.ZipFile(path) as archive:
        with archive.open(key + ".npy") as stream:
            return header(archive, key, stream)[0]


def discard(stream: IO[bytes], size: int) -> None:
    """Bounded byte-only skip; deliberately no seek or numeric conversion."""
    while size:
        block = stream.read(min(size, 65536))
        if not block:
            raise ValueError("Truncated skipped NPY block")
        size -= len(block)


def read_rows(path: Path, key: str, rows: Iterable[Any],
              expected_shape: Tuple[int, ...], kind: str,
              audit: List[Dict[str, Any]]) -> np.ndarray:
    requested = list(rows)
    if (any(not isinstance(i, (int, np.integer)) or isinstance(i, bool)
            or not 0 <= i < expected_shape[0] for i in requested)
            or len(set(requested)) != len(requested)):
        raise ValueError("Invalid/duplicate selected row indices")
    positions = {int(row): position for position, row in enumerate(requested)}
    with zipfile.ZipFile(path) as archive:
        with archive.open(key + ".npy") as stream:
            shape, dtype = header(archive, key, stream)
            if shape != expected_shape or dtype.kind not in kind:
                raise ValueError("Unexpected shape/dtype: " + key)
            width = math.prod(shape[1:])
            row_bytes = width * dtype.itemsize
            result = np.empty((len(requested),) + shape[1:], dtype=dtype)
            cursor = 0
            for row in sorted(positions):
                discard(stream, (row - cursor) * row_bytes)
                block = stream.read(row_bytes)
                if len(block) != row_bytes:
                    raise ValueError("Truncated selected NPY row")
                # This is the sole observation decoding boundary.
                result[positions[row]] = np.frombuffer(
                    block, dtype=dtype, count=width).reshape(shape[1:])
                cursor = row + 1
            discard(stream, (shape[0] - cursor) * row_bytes)
            if stream.read(1):
                raise ValueError("Trailing NPY payload")
    audit.append({
        "path": str(path), "member": key, "shape": list(shape),
        "dtype": str(dtype), "selected_rows": len(requested),
        "skipped_rows": shape[0] - len(requested),
        "decoded_bytes": len(requested) * row_bytes,
        "discarded_decompressed_bytes": (shape[0] - len(requested)) * row_bytes,
        "structural_metadata": key == "log_window",
    })
    return result


def selected_split(split: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, List[int]]]:
    permutation = np.random.RandomState(42).permutation(564)
    if (split["seed"] != 42 or split["counts"] !=
            {"train": 316, "validation": 78, "test": 169, "unassigned": 1}):
        raise ValueError("Frozen SN split contract mismatch")
    train, validation = permutation[:316], permutation[316:394]
    for name, expected in (("train", train), ("validation", validation)):
        if split["indices"][name] != expected.tolist():
            raise ValueError("Frozen split order mismatch: " + name)
    indices = np.sort(permutation[:394]).astype(np.int64)
    mapping = {int(row): position for position, row in enumerate(indices)}
    return indices, {
        "train_positions": [mapping[int(row)] for row in train],
        "validation_positions": [mapping[int(row)] for row in validation],
    }


def load_events(path: Path, indices: np.ndarray, window_count: int,
                nodes: int, events: int,
                audit: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
    shape = member_shape(path, "log_window")
    if len(shape) != 1:
        raise ValueError("Expected flat ragged log_window index")
    windows = read_rows(path, "log_window", range(shape[0]), shape, "iu", audit)
    if np.any(windows < 0) or np.any(windows >= window_count):
        raise ValueError("Structural log_window outside source windows")
    selected = np.flatnonzero(np.isin(windows, indices))
    result = {"log_window": windows[selected]}
    for key, kind in (("log_node", "iu"), ("log_template", "iu"),
                      ("log_timestamp", "f")):
        result[key] = read_rows(path, key, selected, shape, kind, audit)
    result["window_start"] = read_rows(
        path, "window_start", indices, (window_count,), "iu", audit)
    if (np.any(result["log_node"] < 0) or np.any(result["log_node"] >= nodes)
            or np.any(result["log_template"] < 0)
            or np.any(result["log_template"] >= events)
            or not np.isfinite(result["log_timestamp"]).all()):
        raise ValueError("Invalid selected log event value")
    return result


def preflight() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    raw_meta_path = RAW.parent / "metadata.json"
    prepared_meta_path = PREPARED.with_name("SN_metadata.json")
    build_path = PREPARED.with_name("SN_build.json")
    raw_meta, prep_meta = read_json(raw_meta_path), read_json(prepared_meta_path)
    build, split = read_json(build_path), read_json(SPLIT)
    paths = [
        RAW, PREPARED, raw_meta_path, prepared_meta_path, build_path, SPLIT,
        NATIVE / "native_data.py", NATIVE / "native_data_profile.py",
        NATIVE / "native_train.py", HERE.parent / "method_mlp_20261013/features.py",
    ] + [HERE / name for name in (
        "ACCESS.md", "BRIEF.md", "EXECUTION_PROTOCOL.md", "GATE.md")]
    hashes = {str(path): file_hash(path) for path in paths}
    checks = [
        (RAW, raw_meta["raw_npz_sha256"]),
        (RAW, build["output_sha256"]),
        (raw_meta_path, build["metadata_sha256"]),
        (PREPARED, prep_meta["prepared_npz_sha256"]),
        (PREPARED, raw_meta["prepared_npz_sha256"]),
        (NATIVE / "native_data.py", raw_meta["source"]["feature_build_source_sha256"]),
        (NATIVE / "native_data_profile.py",
         prep_meta["source"]["reused_profile_helpers_sha256"]),
    ]
    for path, expected in checks:
        if hashes[str(path)] != expected:
            raise ValueError("Metadata-linked SHA256 mismatch: " + str(path))
    if (raw_meta["system"] != "SN" or prep_meta["dataset"] != "SN"
            or raw_meta["window_count"] != 564 or prep_meta["windows"] != 564
            or len(raw_meta["windows"]) != 564
            or raw_meta["window_length"] != 10 or prep_meta["window_length"] != 10
            or raw_meta["event_count"] != 7 or prep_meta["event_num"] != 7
            or len(raw_meta["services"]) != 12
            or raw_meta["services"] != prep_meta["services"]
            or raw_meta["templates"] != prep_meta["templates"]
            or len(raw_meta["templates"]) != 6
            or raw_meta["source"]["commit"] != prep_meta["source"]["commit"]):
        raise ValueError("SN metadata contract mismatch")
    selected_split(split)
    return raw_meta, prep_meta, split, hashes


def load_selected(raw_meta: Dict[str, Any], split: Dict[str, Any]
                  ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray],
                             Dict[str, Any]]:
    indices, positions = selected_split(split)
    audit: List[Dict[str, Any]] = []
    arrays = {}
    for key, shape, kind in (
        ("metrics", (564, 12, 10, 7), "f"),
        ("traces", (564, 12, 10, 2), "f"),
        ("logs", (564, 12, 7), "f"),
        ("labels", (564,), "iu"),
    ):
        arrays[key] = read_rows(RAW, key, indices, shape, kind, audit)
        if not np.isfinite(arrays[key]).all():
            raise ValueError("Nonfinite selected " + key)
    arrays["indices"] = indices
    if (np.any(arrays["labels"] < -1) or np.any(arrays["labels"] >= 12)
            or np.any(arrays["logs"] < 0)
            or np.any(arrays["traces"][..., 1] != 0)):
        raise ValueError("Invalid selected input values")
    event_arrays = load_events(PREPARED, indices, 564, 12, 7, audit)
    windows = [raw_meta["windows"][int(i)] for i in indices]
    if not np.array_equal(event_arrays["window_start"],
                          np.asarray([row["start"] for row in windows])):
        raise ValueError("Selected window start metadata mismatch")
    return arrays, event_arrays, dict(
        positions, original_indices=indices.tolist(), windows=windows,
        access_disclosure=DISCLOSURE, access_audit=audit,
        forbidden_observation_rows_materialized=0,
        split_counts={"train": 316, "validation": 78, "test": 169, "unassigned": 1},
    )
