"""Allowed-case Parquet -> unscaled temporal arrays and timed log messages."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from inspect_re2_schema import DATA, HERE, MANIFEST, REPO, allow_case, digest

sys.path.insert(0, str(REPO / "scripts"))
from audit import observed_calls

FAMILIES = ("cpu", "diskio", "error", "latency-50", "latency-90", "mem", "socket", "workload")
PROXIES = frozenset(("BlackHoleCluster", "PassthroughCluster",
                     "InboundPassthroughClusterIpv4", "InboundPassthroughClusterIpv6"))
OUT = HERE / "re2_stage1"
MARKER = re.compile(r"chaos[-_ ]?(mesh|daemon)|stress-ng|chaosblade|fault.?inject", re.I)


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def save_json(path, value):
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with path.open("x") as stream:
        stream.write(payload)


def metric_grid(times, columns, services):
    times = np.asarray(times)
    assert times.dtype.kind in "iu" and times.ndim == 1 and len(times) >= 10
    assert np.all(np.diff(times) > 0), "Metric times must be unique and increasing"
    start, end = int(times[0]), int(times[-1])
    assert end - start < 10800, "Unexpected case duration; review before allocating"
    seconds = ((end - start + 1) // 10) * 10
    assert seconds >= 10
    raw = np.full((seconds, len(services), len(FAMILIES)), np.nan, dtype=np.float64)
    rows = times - start
    keep = rows < seconds
    for name, values in columns.items():
        service, separator, family = name.partition("_")
        assert separator and family in FAMILIES, name
        if service in PROXIES:
            continue
        assert service in services
        values = np.asarray(values, dtype=np.float64)
        assert values.shape == times.shape
        raw[rows[keep], services.index(service), FAMILIES.index(family)] = values[keep]
    raw[~np.isfinite(raw)] = np.nan
    values = raw.reshape(-1, 10, len(services), len(FAMILIES)).transpose(0, 2, 1, 3).copy()
    return np.arange(start, start + seconds, 10, dtype=np.int64), values


def trace_grid(start_us, duration_us, names, starts, services):
    start_us, duration_us = np.asarray(start_us), np.asarray(duration_us)
    assert start_us.dtype.kind in "iu" and duration_us.dtype.kind in "iu"
    assert start_us.shape == duration_us.shape == (len(names),) and np.all(duration_us >= 0)
    seconds = len(starts) * 10
    sums = np.zeros((seconds, len(services)), dtype=np.float64)
    counts = np.zeros((seconds, len(services)), dtype=np.int64)
    origin = int(starts[0])
    relative = start_us // 1000000 - origin
    retained = (relative >= 0) & (relative < seconds)
    names = np.asarray(names, dtype=str)
    for service in sorted(set(names)):
        assert service
        if service in PROXIES:
            continue
        assert service in services
        selected = retained & (names == service)
        index = services.index(service)
        np.add.at(sums[:, index], relative[selected], duration_us[selected] / 1e6)
        np.add.at(counts[:, index], relative[selected], 1)
    mean = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    values = np.zeros((len(starts), len(services), 10, 2), dtype=np.float64)
    values[..., 0] = mean.reshape(-1, 10, len(services)).transpose(0, 2, 1)
    return values, counts.reshape(-1, 10, len(services)).transpose(0, 2, 1), retained


def convert_case(row):
    allow_case(row)
    started = time.perf_counter()
    folder, target = DATA / row["case"], OUT / row["case"]
    if target.exists():
        raise FileExistsError("Never overwrite an existing case conversion: " + str(target))
    paths = {kind: folder / (kind + ".parquet") for kind in ("metrics", "logs", "traces")}
    available = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    assert sum(path.stat().st_size for path in paths.values()) * 30 < available / 4
    hashes = {kind: file_hash(path) for kind, path in paths.items()}
    metrics = pq.read_table(paths["metrics"])
    logs = pq.read_table(paths["logs"], columns=["timestamp", "container_name", "message"])
    traces = pq.read_table(paths["traces"], columns=[
        "traceID", "spanID", "parentSpanID", "serviceName", "startTime",
        "startTimeMillis", "duration"])
    log_names, trace_names = logs["container_name"].to_pylist(), traces["serviceName"].to_pylist()
    assert all(isinstance(name, str) and name for name in log_names + trace_names)
    metric_names = {name.partition("_")[0] for name in metrics.column_names if name != "time"}
    services = sorted((metric_names | set(log_names) | set(trace_names)) - PROXIES)
    assert row["root_cause_service"] in services
    starts, values = metric_grid(
        metrics["time"].to_numpy(), {name: metrics[name].to_numpy()
                                    for name in metrics.column_names if name != "time"}, services)
    start_us, start_ms = traces["startTime"].to_numpy(), traces["startTimeMillis"].to_numpy()
    assert np.all(start_us // 1000 == start_ms), "Trace coordinates disagree"
    latency, counts, retained = trace_grid(start_us, traces["duration"].to_numpy(),
                                           trace_names, starts, services)
    root = services.index(row["root_cause_service"])
    labels = np.where(starts + 9 < row["inject_time"], -1, root).astype(np.int64)
    assert (labels == -1).any() and (labels == root).any()
    call_table = traces.filter(pa.array(retained)).select(
        ["traceID", "spanID", "parentSpanID", "serviceName"]).rename_columns(
            ["trace_id", "span_id", "parent_span_id", "service_name"])
    calls, missing_parent, duplicates, conflicts = observed_calls([call_table])
    edges = sorted([list(pair) for pair in calls if pair[0] not in PROXIES and pair[1] not in PROXIES])
    log_times, messages = logs["timestamp"].to_numpy(), logs["message"].to_pylist()
    assert log_times.dtype.kind in "iu" and all(isinstance(message, str) for message in messages)
    marker_hits = sum(bool(MARKER.search(message)) for message in messages)
    if marker_hits:
        raise ValueError("Injection-tool log markers need review before feature extraction: " + row["case"])
    target.mkdir(parents=True, exist_ok=False)
    with (target / "temporal.npz").open("xb") as stream:
        np.savez_compressed(stream, metrics=values, metric_observed=np.isfinite(values),
                            traces=latency, retained_count=counts, starts=starts, labels=labels)
    kept_logs, excluded_logs = 0, Counter()
    with gzip.open(target / "logs.jsonl.gz", "xt", encoding="utf8") as stream:
        for stamp, name, message in zip(log_times, log_names, messages):
            if name in PROXIES:
                excluded_logs["declared_proxy"] += 1
            elif not (starts[0] <= stamp < starts[-1] + 10):
                excluded_logs["outside_complete_windows"] += 1
            else:
                stream.write(json.dumps([int(stamp), name, message], ensure_ascii=False) + "\n")
                kept_logs += 1
    assert hashes == {kind: file_hash(path) for kind, path in paths.items()}
    with np.load(target / "temporal.npz", allow_pickle=False) as saved:
        np.testing.assert_equal(saved["metrics"], values)
        np.testing.assert_array_equal(saved["traces"], latency)
        np.testing.assert_array_equal(saved["retained_count"], counts)
        np.testing.assert_array_equal(saved["labels"], labels)
    report = {
        "status": "PASS_UNSCALED_CASE", "case": row["case"], "partition": row["partition"],
        "root_service": row["root_cause_service"], "inject_time": row["inject_time"],
        "services": services, "families": list(FAMILIES), "observed_edges": edges,
        "windows": len(starts), "nominal_normal_windows": int((labels < 0).sum()),
        "nominal_fault_windows": int((labels >= 0).sum()),
        "metric_missing_cells": int((~np.isfinite(values)).sum()),
        "metric_observed_cells": int(np.isfinite(values).sum()),
        "logs_retained": kept_logs, "logs_excluded": dict(excluded_logs),
        "trace_rows": len(start_us), "trace_rows_in_complete_windows": int(retained.sum()),
        "trace_parent_missing": missing_parent, "trace_duplicate_id_rows": duplicates,
        "trace_conflicting_identities": conflicts, "raw_hashes": hashes,
        "source_sha256": digest(Path(__file__)),
        "split_sha256": digest(MANIFEST), "seconds": time.perf_counter() - started,
        "output_hashes": {name: file_hash(target / name)
                          for name in ("temporal.npz", "logs.jsonl.gz")},
        "physical_service_aliases_merged": False,
        "frontend_identity_note": "frontendservice and frontend retained separately; mapping not certified",
        "label_convention": "window intersects post-injection period; not verified physical fault persistence",
        "metric_imputation_fitted": False, "templates_or_scalers_fitted": False,
        "protected_case_files_opened": 0,
    }
    save_json(target / "metadata.json", report)
    print("RE2_CASE_PASS", row["case"], len(starts), kept_logs, flush=True)
    return report


if __name__ == "__main__":
    assert __debug__
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    lock = json.loads(MANIFEST.with_name("split.lock.json").read_text())
    assert digest(MANIFEST) == lock["sha256"]
    manifest = json.loads(MANIFEST.read_text())
    record = next(row for row in manifest["cases"] if row["case"] == args.case)
    convert_case(record)
