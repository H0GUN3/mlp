"""Fresh incident-split features and within-window relations; frozen inputs are read-only."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import numpy as np

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "method_mlp_20261013"
OUT = HERE / "artifacts"
sys.path.insert(0, str(HERE.parents[1]))
from research.method_mlp_20261013 import features as base_features


def source_hashes():
    return {str(path): base_features.file_hash(path) for path in (
        Path(__file__), HERE / "PROTOCOL.md", OLD / "features.py",
        base_features.NATIVE / "native_data_profile.py",
    )}


def event_partition(meta, indices, labels, fold=0):
    if fold not in (0, 1, 2) or len(indices) != len(labels):
        raise ValueError("Invalid fold or row metadata")
    parts = base_features.original_split(meta["window_count"])
    allowed = set(parts["train"]) | set(parts["validation"])
    if len(set(indices.tolist())) != len(indices) or not set(indices.tolist()) <= allowed:
        raise ValueError("Repeated or protected original index")
    faults = {}
    for run in meta["runs"]:
        for fault in run["faults"]:
            event = fault["event_id"]
            if event in faults or ";" in event:
                raise ValueError("Duplicate or compound incident identity")
            if meta["services"][fault["root"]] != fault["service"]:
                raise ValueError("Root service mapping mismatch")
            faults[event] = dict(fault, run_id=run["run_id"])
    types = sorted({fault["fault_type"] for fault in faults.values()})
    services = sorted(meta["services"], key=lambda s: hashlib.sha256(
        ("20261013:" + s).encode()).hexdigest())
    combinations = [(f["service"], f["fault_type"]) for f in faults.values()]
    if len(types) != 3 or len(set(combinations)) != len(services) * 3 or len(combinations) != len(set(combinations)):
        raise ValueError("Expected exactly one incident per service/type combination")
    event_folds = {event: (services.index(f["service"]) + types.index(f["fault_type"])) % 3
                   for event, f in faults.items()}
    windows = [meta["windows"][int(index)] for index in indices]
    episodes, event_ids = [], []
    for window, label in zip(windows, labels):
        event = window["event_id"] or ""
        if window["end"] != window["start"] + 9:
            raise ValueError("Window length changed")
        candidates = [f for f in faults.values() if f["run_id"] == window["run_id"]]
        if not candidates:
            raise ValueError("Recording without an incident")
        if label >= 0:
            if event not in faults or faults[event]["root"] != int(label):
                raise ValueError("Incident/root mismatch")
            if faults[event]["run_id"] != window["run_id"]:
                raise ValueError("Incident recording mismatch")
            chosen = faults[event]
        else:
            if label != -1 or event:
                raise ValueError("Invalid normal row")
            chosen = min(candidates, key=lambda f: (
                max(f["start"] - window["end"], window["start"] - f["end_inclusive"], 0),
                f["start"], f["event_id"]))
            if max(chosen["start"] - window["end"], window["start"] - chosen["end_inclusive"], 0) == 0:
                raise ValueError("Normal window overlaps annotated fault")
        event_ids.append(event)
        episodes.append(chosen["event_id"])
    if {event for event in event_ids if event} != set(faults):
        raise ValueError("An incident has no permitted development fault window")
    folds = np.asarray([event_folds[event] for event in episodes], dtype=np.int64)
    partition = np.where(folds == fold, "validation", "train")
    if set(np.asarray(episodes)[partition == "train"]) & set(np.asarray(episodes)[partition == "validation"]):
        raise ValueError("Incident leakage")
    for part, per_service in (("train", 2), ("validation", 1)):
        ids = {event for event, part_name in zip(event_ids, partition) if event and part_name == part}
        counts = Counter(faults[event]["service"] for event in ids)
        if counts != Counter({service: per_service for service in services}):
            raise ValueError("Root service support differs from contract")
    few = {}
    for name, delta in (("A", 1), ("B", 2)):
        selected_events = {
            event for event, f in faults.items()
            if types.index(f["fault_type"]) == ((fold - services.index(f["service"])) % 3 + delta) % 3
        }
        few[name] = {
            "event_ids": sorted(selected_events),
            "original_indices": [int(index) for index, event in zip(indices, event_ids) if event in selected_events],
        }
    return {
        "windows": windows, "faults": faults, "event_folds": event_folds,
        "episode_ids": np.asarray(episodes), "event_ids": np.asarray(event_ids),
        "fold_ids": folds, "partition": partition, "few_shot": few,
    }


def adjacency_from_records(records, rows, nodes):
    adjacency = np.zeros((rows, nodes, nodes), dtype=np.bool_)
    counts = Counter()
    for identity, (row, node, stamp, duration, references) in records.items():
        for ref_type, trace_id, span_id in references:
            if ref_type != "CHILD_OF":
                counts["non_child_of_references_ignored"] += 1
                continue
            if trace_id != identity[0]:
                counts["cross_trace_references_ignored"] += 1
                continue
            parent = records.get((trace_id, span_id))
            if parent is None:
                counts["parent_unresolved_or_unselected"] += 1
                continue
            parent_row, parent_node, parent_stamp, parent_duration, _ = parent
            if parent_row != row:
                counts["cross_window_parents_ignored"] += 1
                continue
            if parent_node == node:
                counts["same_service_edges_ignored"] += 1
                continue
            adjacency[row, parent_node, node] = True
            counts["unique_span_parent_links"] += 1
            counts["child_interval_exceeds_parent"] += int(
                stamp < parent_stamp or stamp + duration > parent_stamp + parent_duration)
    counts["binary_service_edges"] = int(adjacency.sum())
    counts["windows_with_edges"] = int(adjacency.any(axis=(1, 2)).sum())
    return adjacency, dict(counts)


def read_adjacency(path, services, run, selected_starts, expected_hash):
    lookup = {int(start): row for row, start in enumerate(selected_starts)}
    if len(lookup) != len(selected_starts):
        raise ValueError("Duplicate selected window start")
    node_map = {service: index for index, service in enumerate(services)}
    records, audit = {}, Counter()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for trace in base_features.json_array(stream, digest):
            for span in trace["spans"]:
                stamp, duration = span["startTime"], span["duration"]
                if type(stamp) is not int or type(duration) is not int or duration < 0:
                    raise ValueError("Invalid span time")
                second = stamp // 1_000_000 + 28800
                if not run["record_start"] <= second < run["record_end_exclusive"]:
                    continue
                start = run["record_start"] + (second - run["record_start"]) // 10 * 10
                row = lookup.get(start)
                if row is None:
                    continue
                identity = (span["traceID"], span["spanID"])
                if not all(isinstance(value, str) and value for value in identity) or identity[0] != trace["traceID"]:
                    raise ValueError("Invalid selected span identity")
                service = trace["processes"][span["processID"]]["serviceName"]
                if service not in node_map:
                    raise ValueError("Unknown selected service")
                references = span.get("references", [])
                if references is None:
                    references = []
                if not isinstance(references, list) or any(
                    not isinstance(ref, dict) or not all(isinstance(ref.get(key), str)
                    for key in ("refType", "traceID", "spanID")) for ref in references
                ):
                    raise ValueError("Invalid span references")
                signature = (row, node_map[service], stamp, duration, tuple(sorted(
                    (ref["refType"], ref["traceID"], ref["spanID"]) for ref in references)))
                audit["selected_occurrences"] += 1
                audit["selected_occurrences_ending_after_window"] += int(
                    stamp + duration + 28800 * 1000000 > (start + 10) * 1000000)
                if identity in records:
                    if records[identity] != signature:
                        raise ValueError("Conflicting duplicate selected span identity")
                    audit["duplicate_occurrences"] += 1
                else:
                    records[identity] = signature
    if digest.hexdigest() != expected_hash:
        raise ValueError("Trace source changed")
    adjacency, relations = adjacency_from_records(records, len(selected_starts), len(services))
    audit["distinct_selected_spans"] = len(records)
    audit.update(relations)
    return adjacency, dict(audit)


def validate_bundle(arrays, manifest):
    base_features.validate_output({key: arrays[key] for key in base_features.KEYS}, len(manifest["services"]))
    rows, nodes = arrays["x"].shape[:2]
    if arrays["adjacency"].shape != (rows, nodes, nodes) or arrays["adjacency"].dtype != np.bool_:
        raise ValueError("Invalid adjacency array")
    if np.diagonal(arrays["adjacency"], axis1=1, axis2=2).any():
        raise ValueError("Self edges entered input")
    if arrays["values"].shape != (rows, nodes, 10, 9) or arrays["observed"].shape != arrays["values"].shape:
        raise ValueError("Invalid reusable raw observations")
    if arrays["observed"].dtype != np.bool_ or not np.isfinite(arrays["values"]).all():
        raise ValueError("Invalid raw observation values")
    if (arrays["fold_ids"].shape != (rows,) or arrays["episode_ids"].shape != (rows,)
            or not np.isin(arrays["fold_ids"], [0, 1, 2]).all()
            or not np.array_equal(arrays["partition"],
                                  np.where(arrays["fold_ids"] == manifest.get("fold", 0), "validation", "train"))):
        raise ValueError("Fold assignment mismatch")
    parts = base_features.original_split(manifest["native_window_count"])
    if set(arrays["indices"]) & (set(parts["test"]) | set(parts["unassigned"])):
        raise ValueError("Protected windows entered bundle")
    if set(arrays["indices"]) != set(parts["train"]) | set(parts["validation"]):
        raise ValueError("Permitted row inventory changed")
    training = arrays["partition"] == "train"
    if set(arrays["episode_ids"][training]) & set(arrays["episode_ids"][~training]):
        raise ValueError("Episode leakage")
    reference = base_features.fit_reference(
        arrays["values"], arrays["observed"], arrays["labels"], arrays["partition"])
    for key, value in reference.items():
        if not np.array_equal(value, np.asarray(manifest["normal_reference"][key])):
            raise ValueError("Normal TRAIN reference mismatch")
    changed = arrays["values"].copy()
    changed[~training] = 1234567.0
    changed_reference = base_features.fit_reference(
        changed, arrays["observed"], arrays["labels"], arrays["partition"])
    if any(not np.array_equal(value, changed_reference[key]) for key, value in reference.items()):
        raise ValueError("Validation values affect normal TRAIN reference")
    expected = base_features.window_features(arrays["values"], arrays["observed"], reference)
    if any(not np.array_equal(arrays[key], value) for key, value in zip(("x", "mask", "coverage"), expected)):
        raise ValueError("Saved feature reconstruction mismatch")


def prepare_system(system):
    started = time.perf_counter()
    sources = source_hashes()
    native, meta, indices, _, provenance = base_features.load_selected(system)
    split = event_partition(meta, indices, native["labels"])
    raw_hashes = base_features.check_metric_evidence(system, meta)
    rows, nodes = len(indices), len(meta["services"])
    values = np.zeros((rows, nodes, 10, 9), dtype=np.float64)
    values[..., :7] = native["metrics"]
    observed = np.ones(values.shape, dtype=np.bool_)
    observed[..., 7] = False
    adjacency = np.zeros((rows, nodes, nodes), dtype=np.bool_)
    audits = {}
    for run in meta["runs"]:
        selected = np.asarray([i for i, w in enumerate(split["windows"])
                               if w["run_id"] == run["run_id"]], dtype=np.int64)
        starts = [split["windows"][int(i)]["start"] for i in selected]
        path = base_features.ROOTS[system] / "data" / run["run_id"] / "spans.json"
        name = str(path.relative_to(base_features.ROOTS[system]))
        latency, counts, trace_audit, digest = base_features.reconstruct_trace(
            path, meta["services"], run, starts, meta["input_sha256"][name])
        base_features.require_trace_equal(latency, native["traces"][selected, :, :, 0])
        graph, graph_audit = read_adjacency(path, meta["services"], run, starts, meta["input_sha256"][name])
        values[selected, :, :, 7], values[selected, :, :, 8] = latency, counts
        observed[selected, :, :, 7] = counts > 0
        adjacency[selected] = graph
        raw_hashes[name] = digest
        audits[run["run_id"]] = {"trace": trace_audit, "graph": graph_audit}
        print("RELATION_STREAM", system, run["run_id"], graph_audit, flush=True)
    reference = base_features.fit_reference(values, observed, native["labels"], split["partition"])
    if not np.any((native["labels"] == -1) & (split["partition"] == "train")):
        raise ValueError("No normal TRAIN windows")
    x, mask, coverage = base_features.window_features(values, observed, reference)
    arrays = {
        "values": values, "observed": observed, "x": x, "mask": mask, "coverage": coverage,
        "adjacency": adjacency, "indices": indices, "labels": native["labels"],
        "event_ids": split["event_ids"], "episode_ids": split["episode_ids"],
        "fold_ids": split["fold_ids"], "partition": split["partition"],
    }
    stats = {}
    for part in ("train", "validation"):
        chosen = split["partition"] == part
        fault_rows = chosen & (native["labels"] >= 0)
        stats[part] = {
            "windows": int(chosen.sum()), "fault_windows": int(fault_rows.sum()),
            "normal_windows": int((chosen & (native["labels"] == -1)).sum()),
            "incidents": len(set(split["event_ids"][fault_rows])),
            "fault_windows_with_edges": int(adjacency[fault_rows].any(axis=(1, 2)).sum()),
        }
    manifest = {
        "system": system, "fold": 0, "services": meta["services"], "feature_names": base_features.FEATURE_NAMES,
        "native_window_count": meta["window_count"], "provenance": provenance, "raw_input_hashes": raw_hashes,
        "source_hashes": sources, "normal_reference": {key: value.tolist() for key, value in reference.items()},
        "normal_train_indices": indices[(split["partition"] == "train") & (native["labels"] == -1)].tolist(),
        "event_folds": split["event_folds"], "faults": split["faults"], "windows": split["windows"],
        "few_shot": split["few_shot"], "counts": stats, "trace_graph_audit": audits,
        "graph_policy": "Binary CHILD_OF caller->callee; unique identities; both starts in same permitted 10s window",
        "test_evaluated": False, "rcaeval_access": False,
        "checks": {"incident_disjoint": True, "native_test_excluded": True,
                   "normal_train_only": True, "validation_reference_invariant": True,
                   "exact_native_trace_latency": True, "frozen_sources_unchanged": True},
        "limitations": [
            "Previously used incidents; not a pristine final evaluation or recording-disjoint split.",
            "Frozen NPZ members decode whole before selecting allowed rows; no held-out values fitted/evaluated/exported.",
            "Original streams are scanned twice for hash and trace/graph reconstruction; only permitted windows accumulate.",
            "Latency/count retain duplicate weights; relations deduplicate IDs. Count0 is not collector-health evidence.",
            "Observed CHILD_OF edges are not complete topology or proven causal dependencies.",
            "Same-window parent/child rule discards cross-window calls; absence of an edge is not evidence of no call.",
            "Native latency assigns complete durations by span start; spans ending after a window are counted, not online-availability verified.",
        ],
        "prepare_seconds": time.perf_counter() - started,
    }
    validate_bundle(arrays, manifest)
    if source_hashes() != sources:
        raise ValueError("Reused or new source changed during preparation")
    for key in ("metadata", "raw_npz"):
        base_features.require_hash(Path(provenance[key]["path"]), provenance[key]["sha256"])
    print("RELATION_PREPARED", system, stats, flush=True)
    return arrays, manifest


def load_bundle(system):
    path = OUT / (system + ".npz")
    manifest = json.loads((OUT / (system + ".json")).read_text())
    base_features.require_hash(path, manifest["npz_sha256"])
    for source, digest in manifest["source_hashes"].items():
        base_features.require_hash(Path(source), digest)
    with np.load(path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in archive.files}
    validate_bundle(arrays, manifest)
    return arrays, manifest


def prepare_both():
    OUT.mkdir(exist_ok=True)
    destinations = [OUT / (system + suffix) for system in ("SN", "TT") for suffix in (".npz", ".json")]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise FileExistsError("Refusing to overwrite development artifacts")
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=str(OUT)) as temporary:
        stage = Path(temporary)
        for system in ("SN", "TT"):
            arrays, manifest = prepare_system(system)
            archive_path = stage / (system + ".npz")
            with archive_path.open("xb") as stream:
                np.savez_compressed(stream, **arrays)
            with np.load(archive_path, allow_pickle=False) as saved:
                if set(saved.files) != set(arrays) or any(not np.array_equal(saved[key], value)
                                                        for key, value in arrays.items()):
                    raise ValueError("Serialized bundle differs")
            manifest["npz_sha256"] = base_features.file_hash(archive_path)
            manifest["npz_bytes"] = archive_path.stat().st_size
            with (stage / (system + ".json")).open("x", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        published = []
        try:
            for destination in destinations:
                os.link(str(stage / destination.name), str(destination))
                published.append(destination)
        except BaseException:
            for destination in published:
                destination.unlink()
            raise
    print("RELATION_PREPARE_COMPLETE", flush=True)


if __name__ == "__main__":
    if sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5":
        raise RuntimeError("Use the pinned .venv-eadro Python3.8 / NumPy1.21.5")
    prepare_both()
