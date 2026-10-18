"""RE2-OB staged native inputs; no raw readers, imputation, scaling or models."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict

sys.dont_write_bytecode = True
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
from drain3 import TemplateMiner
from drain3.file_persistence import FilePersistence
from drain3.template_miner_config import TemplateMinerConfig

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "re2_stage2"
STAGE1 = HERE / "re2_stage1"
NATIVE = HERE.parent / "native_reproduction_20261013"
SPLIT = REPO / "research/mlp_prerequisites/split.json"
MANIFEST = HERE / "RE2_STAGE1_MANIFEST.json"
CONFIG = NATIVE / "native_inputs/drain3.ini"
SPLIT_HASH = "1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5"
FAMILIES = ["cpu", "diskio", "error", "latency-50", "latency-90", "mem", "socket", "workload"]
PROXIES = {"BlackHoleCluster", "PassthroughCluster",
           "InboundPassthroughClusterIpv4", "InboundPassthroughClusterIpv6"}
PINNED = {
    "native_data.py": "05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986",
    "native_data_profile.py": "86d323810f70e732d945e25358d8488df619f0d9a445697f1b77b82fbfbaaa00",
    "native_models.py": "7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632",
    "native_train.py": "48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7",
    "native_inputs/drain3.ini": "d106ce127611fc0607871a08e7825edae7c24651b8e4c3dbafe836550f40c86c",
}
sys.path.insert(0, str(NATIVE))
from native_data import make_knots, fit_hawkes


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def load_json(path):
    return json.loads(path.read_text())


def save_json(path, value):
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x") as stream:
        stream.write(text)


def save_npz(path, arrays):
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    with np.load(path, allow_pickle=False) as saved:
        assert set(saved.files) == set(arrays)
        for key, value in arrays.items():
            np.testing.assert_equal(saved[key], value)
            assert saved[key].dtype == value.dtype
    return digest(path)


def install_guard(allowed):
    """Refuse raw/protected input reads and writes outside this task's output."""
    stats = {"raw_case_files_opened": 0, "protected_case_files_opened": 0,
             "denied": [], "writes_outside_stage2": 0}

    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1], args[2]
        writing = (isinstance(mode, str) and any(x in mode for x in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
        forbidden = REPO / "data" == path or REPO / "data" in path.parents
        if STAGE1 in path.parents:
            relative = path.relative_to(STAGE1)
            forbidden |= len(relative.parts) != 2 or relative.parts[0] not in allowed or (
                relative.parts[-1] not in {"temporal.npz", "logs.jsonl.gz", "metadata.json"})
        if writing and OUT not in path.parents:
            stats["writes_outside_stage2"] += 1
            forbidden = True
        if forbidden:
            stats["denied"].append(str(path))
            raise PermissionError("Outside authorized Stage2 boundary: " + str(path))

    sys.addaudithook(audit)
    return stats


def interval_overlaps(intervals, cross_partition=True):
    result = []
    for i, left in enumerate(intervals):
        for right in intervals[i + 1:]:
            if cross_partition and left["partition"] == right["partition"]:
                continue
            lo = max(left["start"], right["start"])
            hi = min(left["end_exclusive"], right["end_exclusive"])
            if lo < hi:
                result.append({"left": left["case"], "right": right["case"],
                               "start": lo, "end_exclusive": hi})
    return result


def global_labels(starts, injection, root):
    return np.where(starts + 9 < injection, -1, root).astype(np.int64)


def indexed_edge_pairs(services, edges):
    node = {service: index for index, service in enumerate(services)}
    return [[node[source], node[target]] for source, target in sorted(edges)]


def preflight():
    assert sys.version_info[:2] == (3, 8), "Use existing .venv-eadro Python3.8"
    assert digest(SPLIT) == SPLIT_HASH == load_json(SPLIT.with_name("split.lock.json"))["sha256"]
    manifest = load_json(MANIFEST)
    assert manifest["status"] == "PASS_UNSCALED_ONLY"
    assert manifest["split_sha256"] == SPLIT_HASH
    assert digest(HERE / "re2_stage1.py") == manifest["stage_source_sha256"]
    for name, expected in PINNED.items():
        assert digest(NATIVE / name) == expected, name
    rows = sorted((r for r in load_json(SPLIT)["cases"] if r["dataset"] == "RE2-OB"
                   and r["partition"] in ("train", "validation")), key=lambda r: r["case"])
    assert Counter(r["partition"] for r in rows) == {"train": 54, "validation": 18}
    assert len({r["case"] for r in rows}) == 72
    guard = install_guard({r["case"] for r in rows})
    expected = {r["case"]: r for r in manifest["cases"]}
    assert set(expected) == {r["case"] for r in rows}
    metadata, intervals = {}, []
    for row in rows:
        case = row["case"]
        folder = STAGE1 / case
        assert digest(folder / "metadata.json") == expected[case]["metadata_sha256"]
        meta = load_json(folder / "metadata.json")
        assert meta["case"] == case and meta["partition"] == row["partition"]
        assert meta["root_service"] == row["root_cause_service"]
        assert meta["inject_time"] == row["inject_time"]
        assert meta["split_sha256"] == SPLIT_HASH
        assert meta["source_sha256"] == manifest["stage_source_sha256"]
        assert meta["status"] == "PASS_UNSCALED_CASE" and meta["families"] == FAMILIES
        assert not set(meta["services"]) & PROXIES
        assert meta["protected_case_files_opened"] == 0
        assert not meta["templates_or_scalers_fitted"] and not meta["metric_imputation_fitted"]
        for name in ("temporal.npz", "logs.jsonl.gz"):
            assert digest(folder / name) == meta["output_hashes"][name], (case, name)
        with np.load(folder / "temporal.npz", allow_pickle=False) as z:
            starts = z["starts"]
            assert starts.dtype == np.int64 and len(starts) == meta["windows"]
            assert np.all(np.diff(starts) == 10)
            assert z["metrics"].shape == (len(starts), len(meta["services"]), 10, 8)
            assert z["metrics"].dtype == np.float64 and not np.isinf(z["metrics"]).any()
            np.testing.assert_array_equal(z["metric_observed"], np.isfinite(z["metrics"]))
            assert np.isfinite(z["traces"]).all() and np.all(z["traces"][..., 1] == 0)
            np.testing.assert_array_equal(z["labels"], global_labels(
                starts, row["inject_time"], meta["services"].index(row["root_cause_service"])))
            interval = {"case": case, "partition": row["partition"], "start": int(starts[0]),
                        "end_exclusive": int(starts[-1]) + 10, "windows": len(starts)}
        intervals.append(interval)
        metadata[case] = meta
    overlaps = interval_overlaps(intervals)
    report = {"status": "STOP_OVERLAP_IDENTITY_REVIEW" if overlaps else "PASS",
              "intervals": intervals, "cross_partition_overlaps": overlaps,
              "all_case_overlaps": interval_overlaps(intervals, False),
              "split_sha256": SPLIT_HASH, "stage1_manifest_sha256": digest(MANIFEST),
              "native_source_hashes": PINNED, "protection": guard}
    if not (OUT / "preflight.json").exists():
        save_json(OUT / "preflight.json", report)
    else:
        old = load_json(OUT / "preflight.json")
        assert old == report, "Inputs changed since preflight"
    if overlaps:
        raise ValueError("Cross-partition temporal overlap requires identity review BEFORE any fitting")
    services = sorted({s for r in rows if r["partition"] == "train"
                       for s in metadata[r["case"]]["services"]})
    for row in rows:
        assert set(metadata[row["case"]]["services"]) <= set(services), "Unseen validation identifiers"
        assert row["root_cause_service"] in services
    edges = {(s, s) for s in services}
    for row in rows:
        if row["partition"] == "train":
            edges.update(tuple(e) for e in metadata[row["case"]]["observed_edges"])
    edge_pairs = indexed_edge_pairs(services, edges)
    print("PREFLIGHT_PASS cases=72 cross_partition_overlaps=0 nodes={}".format(len(services)), flush=True)
    return rows, metadata, services, edge_pairs, report


def new_miner(snapshot=None):
    config = TemplateMinerConfig()
    config.load(str(CONFIG))
    if snapshot is None:
        return TemplateMiner(config=config)
    return TemplateMiner(config=config, persistence_handler=FilePersistence(str(snapshot)))


def cluster_records(miner):
    return [{"cluster_id": int(c.cluster_id), "template": c.get_template(), "size": int(c.size)}
            for c in sorted(miner.drain.clusters, key=lambda c: c.cluster_id)]


def log_records(case, meta):
    count = 0
    with gzip.open(STAGE1 / case / "logs.jsonl.gz", "rt", encoding="utf8") as stream:
        for line in stream:
            stamp, name, message = json.loads(line)
            assert type(stamp) is int and name in meta["services"] and isinstance(message, str)
            count += 1
            yield stamp, name, message
    assert count == meta["logs_retained"]


def fit_nominal(miner, records, injection):
    count = 0
    for stamp, _, message in records:
        if stamp < injection:
            miner.add_log_message(message)
            count += 1
    return count


def templates(rows, metadata):
    path = OUT / "templates.json"
    snapshot = OUT / "drain.snapshot"
    if path.exists():
        report = load_json(path)
        assert digest(snapshot) == report["snapshot_sha256"]
        miner = new_miner(snapshot)
        assert cluster_records(miner) == report["clusters"]
        return miner, report
    assert not snapshot.exists(), "Preserve incomplete snapshot; do not overwrite"
    begin = time.perf_counter()
    miner = new_miner()
    fitted = []
    for row in rows:
        if row["partition"] != "train":
            continue
        case = row["case"]
        count = fit_nominal(miner, log_records(case, metadata[case]), row["inject_time"])
        fitted.append({
            "case": case, "partition": "train", "strictly_preinject_lines": count,
            "clusters_retained_after_case": len(miner.drain.clusters),
            "clusters_created_after_case": int(miner.drain.clusters_counter),
        })
        print("TEMPLATE_CASE {} lines={} clusters={} created={}".format(
            case, count, len(miner.drain.clusters), miner.drain.clusters_counter), flush=True)
    clusters = cluster_records(miner)
    miner.persistence_handler = FilePersistence(str(snapshot))
    miner.save_state("TRAIN54 strictly preinject frozen final")
    restored = new_miner(snapshot)
    assert cluster_records(restored) == clusters
    assert miner.config.drain_max_clusters is not None
    report = {
        "clusters": clusters, "event_count": len(clusters) + 1, "unknown_bin": 0,
        "cluster_id_to_feature": {str(c["cluster_id"]): i + 1 for i, c in enumerate(clusters)},
        "sources": fitted, "lines": sum(r["strictly_preinject_lines"] for r in fitted),
        "order": "sorted TRAIN case ID, then original staged row order; timestamp strictly < inject_time",
        "config_sha256": digest(CONFIG), "snapshot_sha256": digest(snapshot),
        "snapshot_API": "TemplateMiner.save_state + FilePersistence; restored with TemplateMiner constructor",
        "matching": "TemplateMiner.match default full_search_strategy=never; no add_log_message",
        "clusters_created": int(miner.drain.clusters_counter),
        "clusters_retained": len(clusters), "max_clusters": int(miner.config.drain_max_clusters),
        "evicted_clusters": int(miner.drain.clusters_counter) - len(clusters),
        "first_case_at_cluster_cap": next(
            (r["case"] for r in fitted
             if r["clusters_retained_after_case"] >= int(miner.config.drain_max_clusters)),
            None),
        "seconds": time.perf_counter() - begin,
        "validation_fit_lines": 0,
    }
    save_json(path, report)
    print("TEMPLATES_FROZEN E={} seconds={:.3f} evicted={}".format(
        report["event_count"], report["seconds"], report["evicted_clusters"]), flush=True)
    return restored, report


def match_event(miner, mapping, message):
    cluster = miner.match(message)
    return 0 if cluster is None else mapping[str(cluster.cluster_id)]


def matched_case(row, meta, services, miner, template):
    folder = OUT / "matched"
    folder.mkdir(exist_ok=True)
    path = folder / (row["case"] + ".npz")
    if path.exists():
        record = load_json(path.with_suffix(".json"))
        assert digest(path) == record["sha256"]
        assert record["snapshot_sha256"] == template["snapshot_sha256"]
        assert record["stage1_log_sha256"] == meta["output_hashes"]["logs.jsonl.gz"]
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    begin = time.perf_counter()
    with np.load(STAGE1 / row["case"] / "temporal.npz", allow_pickle=False) as z:
        start, count = int(z["starts"][0]), len(z["starts"])
    times, nodes, events = [], [], []
    mapping = template["cluster_id_to_feature"]
    node_map = {s: i for i, s in enumerate(services)}
    before = cluster_records(miner)
    for stamp, name, message in log_records(row["case"], meta):
        assert start <= stamp < start + count * 10, "Staged log outside full windows"
        times.append(stamp)
        nodes.append(node_map[name])
        events.append(match_event(miner, mapping, message))
    assert cluster_records(miner) == before == template["clusters"], "Template mutation"
    arrays = {"times": np.asarray(times, dtype=np.int64), "nodes": np.asarray(nodes, dtype=np.int64),
              "events": np.asarray(events, dtype=np.int64)}
    sha = save_npz(path, arrays)
    save_json(path.with_suffix(".json"), {
        "case": row["case"], "sha256": sha, "rows": len(times), "unknown_rows": events.count(0),
        "seconds": time.perf_counter() - begin, "snapshot_sha256": template["snapshot_sha256"],
        "stage1_log_sha256": meta["output_hashes"]["logs.jsonl.gz"]})
    print("MATCHED {} rows={} seconds={:.3f}".format(
        row["case"], len(times), time.perf_counter() - begin), flush=True)
    return arrays


def knot_key(knots):
    value = hashlib.sha256(b"RE2-native-relative10-seed42-v1")
    for knot in knots:
        value.update(np.asarray([len(knot)], dtype="<i8").tobytes())
        value.update(np.asarray(knot, dtype="<f8").tobytes())
    return value.hexdigest()


def case_groups(matched, start, event_count):
    windows = (matched["times"] - start) // 10
    nodes = matched["nodes"]
    order = np.lexsort((nodes, windows))
    w, n = windows[order], nodes[order]
    times, ids = matched["times"][order], matched["events"][order]
    boundaries = np.r_[0, np.flatnonzero((np.diff(w) != 0) | (np.diff(n) != 0)) + 1, len(w)]
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if left == right:
            continue
        window, node = int(w[left]), int(n[left])
        knots = make_knots(times[left:right], ids[left:right], float(start + window * 10), event_count)
        yield window, node, knot_key(knots), knots


def cached_fit(key, knots):
    folder = OUT / "hawkes"
    path = folder / (key + ".npz")
    record = folder / (key + ".json")
    if path.exists() or record.exists():
        assert path.exists() and record.exists(), "Incomplete cache must not be overwritten"
        meta = load_json(record)
        assert digest(path) == meta["sha256"]
        with np.load(path, allow_pickle=False) as z:
            baseline = z["baseline"]
        assert np.isfinite(baseline).all() and np.all(baseline >= 0)
        return baseline, meta
    result = fit_hawkes((0, 0, knots, 42))
    baseline = result.pop("baseline")
    result.update({"key": key, "seed": 42, "event_count": len(knots),
                   "iteration_cap": 50, "cap_reached": result["iterations"] >= 50})
    result["sha256"] = save_npz(path, {"baseline": baseline})
    save_json(record, result)
    return baseline, result


def worker_fit(task):
    key, knots = task
    _, meta = cached_fit(key, knots)
    return meta


def profile(rows, metadata, services, miner, template):
    path = OUT / "profile.json"
    if path.exists():
        return load_json(path)
    (OUT / "hawkes").mkdir(exist_ok=True)
    row = next(r for r in rows if r["partition"] == "train")
    matched = matched_case(row, metadata[row["case"]], services, miner, template)
    with np.load(STAGE1 / row["case"] / "temporal.npz", allow_pickle=False) as z:
        start = int(z["starts"][0])
    groups = list(case_groups(matched, start, template["event_count"]))
    unique = {key: knots for _, _, key, knots in groups}
    ordered = sorted(unique, key=lambda key: sum(map(len, unique[key])))
    chosen = list(dict.fromkeys(ordered[i] for i in (
        0, len(ordered) // 4, len(ordered) // 2, 3 * len(ordered) // 4, len(ordered) - 1)))
    results = []
    begin = time.perf_counter()
    total_windows = sum(metadata[r["case"]]["windows"] for r in rows)
    estimate_unique = len(unique) * total_windows / metadata[row["case"]]["windows"]
    for key in chosen:
        _, result = cached_fit(key, unique[key])
        results.append(result)
        print("HAWKES_PROBE E={} seconds={:.6f} iterations={} warnings={}".format(
            template["event_count"], result["seconds"], result["iterations"], len(result["warnings"])), flush=True)
        if estimate_unique * float(np.mean([r["seconds"] for r in results])) / 8 > 1500:
            break
    seconds = [r["seconds"] for r in results]
    estimate_wall = estimate_unique * float(np.mean(seconds)) / 8
    report = {
        "case": row["case"], "event_count": template["event_count"],
        "nonempty_groups": len(groups), "unique_knots": len(unique), "actual_fits": results,
        "planned_probe_fits": len(chosen), "completed_probe_fits": len(results),
        "probe_stopped_on_cost_gate": len(results) < len(chosen),
        "probe_wall_seconds": time.perf_counter() - begin, "fit_seconds_mean": float(np.mean(seconds)),
        "fit_seconds_max": max(seconds), "total_windows": total_windows,
        "estimated_unique_full": estimate_unique, "estimated_8worker_fit_seconds": estimate_wall,
        "dense_hawkes_coefficients": template["event_count"] ** 2,
        "template_cap_reached": template["clusters_retained"] >= template["max_clusters"],
        "estimate_note": (
            "First sorted TRAIN case event-count quantiles; stop after the first measured fit "
            "whose extrapolation exceeds the bounded full-fit budget"),
        "probe_cache_reused_in_full": True, "maximum_full_fit_budget_seconds": 1500,
        "affordable": estimate_wall <= 1500,
    }
    save_json(path, report)
    return report


def aligned_case(row, meta, services):
    with np.load(STAGE1 / row["case"] / "temporal.npz", allow_pickle=False) as z:
        count = len(z["starts"])
        values = np.full((count, len(services), 10, 8), np.nan, dtype=np.float64)
        observed = np.zeros(values.shape, dtype=bool)
        traces = np.zeros((count, len(services), 10, 2), dtype=np.float64)
        local = [services.index(s) for s in meta["services"]]
        values[:, local] = z["metrics"]
        observed[:, local] = z["metric_observed"]
        traces[:, local] = z["traces"]
        starts = z["starts"]
        labels = global_labels(starts, row["inject_time"], services.index(row["root_cause_service"]))
        return {
            "metrics": values, "metric_observed": observed, "traces": traces, "starts": starts,
            "labels": labels, "partition": np.full(count, row["partition"]),
            "case_ids": np.full(count, row["case"]),
            "event_ids": np.where(labels >= 0, row["case"], ""),
        }


def validate_bundle(arrays, services, event_count):
    assert set(arrays) == {"metrics", "metric_observed", "traces", "logs", "labels", "partition",
                           "case_ids", "event_ids", "starts", "indices"}
    count = len(arrays["labels"])
    assert arrays["metrics"].shape == (count, len(services), 10, 8)
    assert arrays["metric_observed"].shape == arrays["metrics"].shape
    assert arrays["traces"].shape == (count, len(services), 10, 2)
    assert arrays["logs"].shape == (count, len(services), event_count)
    for key in ("metrics", "traces", "logs"):
        assert arrays[key].dtype == np.float64
    assert not np.isinf(arrays["metrics"]).any()
    assert arrays["metric_observed"].dtype == np.bool_
    np.testing.assert_array_equal(arrays["metric_observed"], np.isfinite(arrays["metrics"]))
    assert np.isfinite(arrays["traces"]).all() and np.all(arrays["traces"] >= 0)
    assert np.all(arrays["traces"][..., 1] == 0)
    assert np.isfinite(arrays["logs"]).all() and np.all(arrays["logs"] >= 0)
    for key in ("labels", "starts", "indices"):
        assert arrays[key].dtype == np.int64 and arrays[key].shape == (count,)
    assert np.all((arrays["labels"] >= -1) & (arrays["labels"] < len(services)))
    for key in ("partition", "case_ids", "event_ids"):
        assert arrays[key].dtype.kind == "U" and arrays[key].shape == (count,)
    assert set(arrays["partition"]) == {"train", "validation"}
    np.testing.assert_array_equal(arrays["indices"], np.arange(count, dtype=np.int64))
    np.testing.assert_array_equal(arrays["event_ids"], np.where(
        arrays["labels"] >= 0, arrays["case_ids"], ""))


def prepare(rows, metadata, services, edges, miner, template, precheck, cost, workers):
    assert 1 <= workers <= 8
    assert not (OUT / "inputs.npz").exists() and not (OUT / "metadata.json").exists()
    assert cost["affordable"], "Measured native cost exceeds bounded preparation budget"
    begin = time.perf_counter()
    pieces: Dict[str, Any] = {}
    fitted, cache_hits, nonempty, empty = {}, 0, 0, 0
    case_reports = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in rows:
            case = row["case"]
            meta = metadata[case]
            arrays = aligned_case(row, meta, services)
            matched = matched_case(row, meta, services, miner, template)
            groups = list(case_groups(matched, int(arrays["starts"][0]), template["event_count"]))
            tasks = {}
            for _, _, key, knots in groups:
                tasks[key] = knots
            missing = [(k, knots) for k, knots in tasks.items()
                       if not (OUT / "hawkes" / (k + ".json")).exists()]
            for record in pool.map(worker_fit, missing, chunksize=1):
                fitted[record["key"]] = record
            logs = np.zeros((len(arrays["starts"]), len(services), template["event_count"]),
                            dtype=np.float64)
            for window, node, key, knots in groups:
                baseline, record = cached_fit(key, knots)
                logs[window, node] = baseline
                fitted[key] = record
            cache_hits += len(groups) - len(missing)
            nonempty += len(groups)
            empty += logs.shape[0] * logs.shape[1] - len(groups)
            arrays["logs"] = logs
            for key, value in arrays.items():
                pieces.setdefault(key, []).append(value)
            case_reports.append({
                "case": case, "root": row["root_cause_service"],
                "global_root": services.index(row["root_cause_service"]),
                "fault": row["fault"], "injection": row["inject_time"],
                "originalpartition": row["partition"], "windows": len(arrays["starts"]),
                "start": int(arrays["starts"][0]), "end_exclusive": int(arrays["starts"][-1]) + 10,
                "logs_excluded": meta["logs_excluded"],
                "trace_rows": meta["trace_rows"],
                "trace_rows_excluded_from_complete_windows": (
                    meta["trace_rows"] - meta["trace_rows_in_complete_windows"]),
                "trailing_partial_window_seconds": "not retained in Stage1 metadata; not inferred",
                "stage1_metadata_sha256": digest(STAGE1 / case / "metadata.json"),
                "stage1_missing_metric_cells": meta["metric_missing_cells"],
                "bundle_missing_metric_cells": int((~arrays["metric_observed"]).sum()),
                "metric_mask_sha256": hashlib.sha256(arrays["metric_observed"].tobytes()).hexdigest(),
                "absent_global_nodes": sorted(set(services) - set(meta["services"])),
            })
            print("FEATURE_CASE {} groups={} new_fits={}".format(case, len(groups), len(missing)), flush=True)
    bundle = {key: np.concatenate(values) for key, values in pieces.items()}
    bundle["indices"] = np.arange(len(bundle["labels"]), dtype=np.int64)
    validate_bundle(bundle, services, template["event_count"])
    input_hash = save_npz(OUT / "inputs.npz", bundle)
    for name, expected in PINNED.items():
        assert digest(NATIVE / name) == expected
    assert digest(OUT / "drain.snapshot") == template["snapshot_sha256"]
    assert cluster_records(miner) == template["clusters"]
    assert digest(SPLIT) == SPLIT_HASH and digest(MANIFEST) == precheck["stage1_manifest_sha256"]
    records = list(fitted.values())
    result = {
        "status": "PASS_UNNORMALIZED_NATIVE_FEATURES", "system": "RE2-OB", "services": services,
        "candidates": {
            "services": services, "source": "sorted TRAIN observed raw-identifier union",
            "excluded_proxies": sorted(PROXIES), "validation_fit": False,
            "physical_aliases_merged": False,
        },
        "edges": edges, "edges_layout": "Kx2 source/destination pairs",
        "graph_source": "TRAIN observed edge union plus every candidate self-loop; validation excluded",
        "event_count": template["event_count"], "input_npz_sha256": input_hash,
        "split_sha256": SPLIT_HASH, "stage1_manifest_sha256": digest(MANIFEST),
        "cases": case_reports, "windows": len(bundle["labels"]), "families": FAMILIES,
        "templates": template, "protection": precheck["protection"],
        "sources": {"native": PINNED, "stage2": digest(Path(__file__)),
                    "protocol": digest(HERE / "RE2_FEATURE_PROTOCOL.md")},
        "normalization": {"imputer_fitted": False, "scaler_fitted": False, "metric_nan_preserved": True},
        "cost": {"preparation_wall_seconds": time.perf_counter() - begin, "workers": workers,
                 "threads_per_worker": 1, "unique_fits": len(records), "cache_hits": cache_hits,
                 "fit_cpu_seconds": sum(r["seconds"] for r in records),
                 "cap_reached": sum(r["cap_reached"] for r in records),
                 "warning_fits": sum(bool(r["warnings"]) for r in records),
                 "warnings": dict(Counter(w for r in records for w in r["warnings"])),
                 "nonempty_groups": nonempty, "true_empty_groups_zero": empty, "profile": cost},
        "checks": {"roundtrip": True, "nonfinite_logs": 0, "negative_logs": 0,
                   "cross_partition_overlaps": 0, "trace_channel1_nonzero": 0},
        "limits": [
            "Observed raw identifiers, not certified physical service fusion; frontend aliases preserved",
            "Nominal injection labels do not prove physical active/recovery intervals",
            "Existing root x fault repeats remain in same partition; not same-combination repeat evaluation",
            "Not a claim of exact paper input reproduction; parent TRAIN-only normalization still required"],
        "versions": {p: importlib.metadata.version(p) for p in ("numpy", "tick", "drain3")},
    }
    save_json(OUT / "metadata.json", result)
    print("RE2_STAGE2_PASS cases={} W={} N={} E={} PROTECTED_OPENED_0".format(
        len(rows), len(bundle["labels"]), len(services), template["event_count"]), flush=True)


def main():
    assert __debug__
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "profile", "prepare"), required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    rows, metadata, services, edges, precheck = preflight()
    if args.mode == "preflight":
        return
    blocker = OUT / "template_partial_progress.json"
    if blocker.exists():
        raise RuntimeError(
            "Unresolved RE2 log-format/template-cap review: " + str(blocker)
        )
    miner, template = templates(rows, metadata)
    cost = profile(rows, metadata, services, miner, template)
    print("COST_GATE affordable={} estimated_8worker_seconds={:.3f}".format(
        cost["affordable"], cost["estimated_8worker_fit_seconds"]), flush=True)
    if args.mode == "prepare":
        prepare(rows, metadata, services, edges, miner, template, precheck, cost, args.workers)


if __name__ == "__main__":
    main()
