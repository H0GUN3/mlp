"""Single-pass converted-file census, not training or a causal-quality certificate."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import resource
import tarfile
import time

import numpy as np
import pyarrow as pa
from pyarrow.compute import call_function as compute
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
CORE = ("normal_metrics.parquet", "abnormal_metrics.parquet",
        "normal_traces.parquet", "abnormal_traces.parquet")
MAX_PAYLOAD = 16 * 1024 * 1024
MAX_ROWS = 2_000_000


def true_count(values):
    return int(compute("sum", [values]).as_py() or 0)


def nonempty(values):
    return compute("coalesce", [
        compute("not_equal", [values, pa.scalar("", type=values.type)]), pa.scalar(False)])


def profile_table(table, kind, roots, start, end):
    required = ["time", "service_name"] + (
        ["metric", "value"] if kind == "metric"
        else ["trace_id", "span_id", "parent_span_id", "duration"])
    missing = sorted(set(required) - set(table.column_names))
    if missing:
        return {"profile_error": "missing_columns", "missing_columns": missing}
    timestamp = table["time"]
    if not pa.types.is_timestamp(timestamp.type) or timestamp.type.tz != "UTC":
        return {"profile_error": "unsupported_timestamp", "type": str(timestamp.type)}
    factor = {"s": 1, "ms": 1000, "us": 1_000_000, "ns": 1_000_000_000}[timestamp.type.unit]
    if not (pa.types.is_string(table["service_name"].type)
            or pa.types.is_large_string(table["service_name"].type)):
        return {"profile_error": "unsupported_service_type"}
    ticks = timestamp.cast(pa.int64())
    lower, upper = start * factor, end * factor
    inside = compute("and_kleene", [
        compute("greater_equal", [ticks, pa.scalar(lower)]),
        compute("less_equal", [ticks, pa.scalar(upper)])])
    valid = compute("and_kleene", [inside, nonempty(table["service_name"])])
    extremes = compute("min_max", [ticks]).as_py()
    result = {
        "rows": table.num_rows, "timestamp_unit": timestamp.type.unit,
        "time_min_tick": None if extremes["min"] is None else str(extremes["min"]),
        "time_max_tick": None if extremes["max"] is None else str(extremes["max"]),
        "null_counts": {name: table[name].null_count for name in table.column_names},
        "outside_closed_period": table.num_rows - timestamp.null_count - true_count(inside),
        "rows_at_start": true_count(compute("equal", [ticks, pa.scalar(lower)])),
        "rows_at_end": true_count(compute("equal", [ticks, pa.scalar(upper)])),
        "empty_service_rows": true_count(compute("equal", [table["service_name"], pa.scalar("")])),
    }
    if kind == "metric":
        if not (pa.types.is_floating(table["value"].type) or pa.types.is_integer(table["value"].type)):
            return {"profile_error": "unsupported_value_type"}
        finite = compute("is_finite", [table["value"]])
        result["nonfinite_values"] = table.num_rows - table["value"].null_count - true_count(finite)
        valid = compute("and_kleene", [valid, compute("and_kleene", [finite, nonempty(table["metric"])])])
        result["metric_names"] = sorted(v for v in compute("unique", [table["metric"]]).to_pylist() if v)
    else:
        if not pa.types.is_integer(table["duration"].type):
            return {"profile_error": "unsupported_duration_type"}
        duration_valid = compute("greater_equal", [table["duration"], pa.scalar(0, type=table["duration"].type)])
        result["negative_duration_rows"] = table.num_rows - table["duration"].null_count - true_count(duration_valid)
        result["duration_min_max"] = compute("min_max", [table["duration"]]).as_py()
        identities_valid = compute("and_kleene", [nonempty(table["trace_id"]), nonempty(table["span_id"])])
        result["empty_or_null_identity_rows"] = table.num_rows - true_count(identities_valid)
        valid = compute("and_kleene", [valid, compute("and_kleene", [duration_valid, identities_valid])])
        for boundary, endpoint in (("start", lower), ("end", upper)):
            selected = table.filter(compute("equal", [ticks, pa.scalar(endpoint)]))
            result["_boundary_" + boundary] = {
                (trace, span) for trace, span in zip(selected["trace_id"].to_pylist(),
                                                    selected["span_id"].to_pylist()) if trace and span
            }
    valid = compute("coalesce", [valid, pa.scalar(False)])
    result["basic_valid_rows"] = true_count(valid)
    result["roots"] = {}
    for root in roots:
        root_mask = compute("and_kleene", [
            valid, compute("equal", [table["service_name"], pa.scalar(root)])])
        selected = table.filter(root_mask)
        root_ticks = selected["time"].cast(pa.int64()).to_numpy(zero_copy_only=False)
        bins = np.unique((root_ticks[root_ticks < upper] - lower) // (10 * factor))
        root_info = {"basic_valid_rows": selected.num_rows, "occupied_10s_bins": len(bins),
                     "expected_10s_bins": (end - start + 9) // 10}
        if kind == "metric":
            root_info["metric_names"] = sorted(
                v for v in compute("unique", [selected["metric"]]).to_pylist() if v)
        result["roots"][root] = root_info
    for name in ("attr.k8s.namespace.name", "attr.span_kind", "attr.status_code",
                 "attr.http.response.status_code"):
        if name in table.column_names:
            values = compute("unique", [table[name]]).to_pylist()
            result[name + "_values"] = sorted(v for v in values if v is not None)
    return result


def inspect_parquet(payload, filename, case):
    parquet = pq.ParquetFile(pa.BufferReader(payload))
    schema = parquet.schema_arrow
    result = {"rows": parquet.metadata.num_rows, "schema": {f.name: str(f.type) for f in schema}}
    metric = filename.endswith("_metrics.parquet") or filename.endswith("_metrics_sum.parquet")
    trace = filename.endswith("_traces.parquet")
    if not metric and not trace:
        result["inspection"] = "footer_only"
        return result
    if parquet.metadata.num_rows > MAX_ROWS:
        result["profile_error"] = "row_budget_exceeded_not_a_data_verdict"
        return result
    wanted = {"time", "service_name", "metric", "value", "trace_id", "span_id",
              "parent_span_id", "duration", "attr.k8s.namespace.name", "attr.span_kind",
              "attr.status_code", "attr.http.response.status_code"}
    table = parquet.read(columns=[name for name in schema.names if name in wanted], use_threads=False)
    prefix = "NORMAL" if filename.startswith("normal_") else "ABNORMAL"
    periods = case["periods_epoch_seconds"]
    if periods is None:
        result["profile_error"] = "invalid_metadata_periods"
        return result
    result["inspection"] = "projected_rows"
    result.update(profile_table(table, "metric" if metric else "trace", case["root_services"],
                                periods[prefix + "_START"], periods[prefix + "_END"]))
    return result


def summarize_case(case, files):
    readable = all(name in files and not files[name].get("profile_error")
                   and files[name].get("rows", 0) > 0 and "roots" in files[name] for name in CORE)
    root_rows = readable and all(
        files[name]["roots"].get(root, {}).get("basic_valid_rows", 0) > 0
        for name in CORE for root in case["root_services"])
    normal = files.get("normal_traces.parquet", {})
    abnormal = files.get("abnormal_traces.parquet", {})
    shared = normal.get("_boundary_end", set()) & abnormal.get("_boundary_start", set())
    for info in files.values():
        info.pop("_boundary_start", None)
        info.pop("_boundary_end", None)
    return {
        "case": case["case"], "root_services": case["root_services"], "fault_type": case["fault_type"],
        "invalid_marker": ".invalid" in case["files"],
        "core_projected_files_readable_nonempty": readable,
        "all_labeled_roots_have_basic_rows_in_both_modalities_and_periods": bool(root_rows),
        "single_label_basic_row_support": bool(case["metadata_gate_pass"] and readable and root_rows),
        "shared_boundary_trace_span_identities": len(shared),
        "files": files,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise FileExistsError("Refusing to overwrite quality audit")
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    started = time.perf_counter()
    inventory_bytes = (HERE / "metadata_inventory.json").read_bytes()
    inventory = json.loads(inventory_bytes)
    cases = {c["case"]: c for c in inventory["cases"]}
    archive_path = HERE / "rcabench-absolute_anomaly.tar.gz"
    initial = archive_path.stat()
    if initial.st_size != inventory["source"]["bytes"]:
        raise ValueError("Verified archive size changed")
    profiles, hashes, file_groups = defaultdict(dict), defaultdict(dict), defaultdict(list)
    payload_total, file_count, finished = 0, 0, 0
    with tarfile.open(archive_path, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if len(parts) != 2 or parts[0] not in cases:
                raise ValueError("Archive layout differs from verified inventory")
            name, filename = parts
            if filename in hashes[name]:
                raise ValueError("Duplicate archive member")
            if member.size != cases[name]["files"].get(filename) or member.size > MAX_PAYLOAD:
                raise ValueError("Unexpected member size; audit budget must be reconsidered")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Unreadable member")
            with source:
                payload = source.read(member.size + 1)
            if len(payload) != member.size:
                raise ValueError("Truncated member")
            digest = hashlib.sha256(payload).hexdigest()
            hashes[name][filename] = digest
            file_groups[(digest, member.size)].append(name + "/" + filename)
            payload_total += member.size
            file_count += 1
            if filename.endswith(".parquet"):
                try:
                    profiles[name][filename] = inspect_parquet(payload, filename, cases[name])
                except (pa.ArrowException, ValueError, TypeError) as error:
                    profiles[name][filename] = {
                        "profile_error": type(error).__name__ + ": " + str(error),
                        "interpretation": "unverified; inspect parser versus data failure",
                    }
            if len(hashes[name]) == len(cases[name]["files"]):
                finished += 1
                if finished % 100 == 0:
                    print("QUALITY_PROGRESS", finished, "of", len(cases), flush=True)
    if finished != len(cases) or set(hashes) != set(cases):
        raise ValueError("Incomplete corpus scan")
    final = archive_path.stat()
    if (initial.st_ino, initial.st_size, initial.st_mtime_ns) != (
            final.st_ino, final.st_size, final.st_mtime_ns):
        raise ValueError("Archive changed during scan")
    results = [summarize_case(cases[name], profiles[name]) for name in sorted(cases)]
    observation_groups = defaultdict(list)
    for name in cases:
        observation_groups[tuple(hashes[name].get(key) for key in CORE)].append(name)
    errors = Counter(info["profile_error"] for case in results for info in case["files"].values()
                     if "profile_error" in info)
    report = {
        "scope": "converted corpus census; not model-ready or independent-incident certification",
        "source": inventory["source"], "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {"numpy": np.__version__, "pyarrow": pa.__version__},
        "file_count": file_count, "payload_bytes": payload_total,
        "unique_payload_bytes": sum(size for _, size in file_groups),
        "duplicate_nonempty_file_groups": [
            {"sha256": digest, "bytes_each": size, "members": members}
            for (digest, size), members in file_groups.items() if size and len(members) > 1],
        "identical_core_observation_bundles": [v for v in observation_groups.values() if len(v) > 1],
        "counts": {
            "cases": len(results),
            "core_readable_nonempty": sum(c["core_projected_files_readable_nonempty"] for c in results),
            "single_label_basic_row_support": sum(c["single_label_basic_row_support"] for c in results),
            "shared_boundary_trace_identity_cases": sum(c["shared_boundary_trace_span_identities"] > 0
                                                         for c in results),
        },
        "profile_error_counts": dict(errors), "independent_usable_incidents": None,
        "native_nine_channel_equivalence_verified": False, "model_fitting": False,
        "seconds": time.perf_counter() - started,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "file_sha256": dict(hashes), "cases": results,
        "limits": [
            "Basic support requires only at least one finite/nonempty in-period root row per core file.",
            "No coverage threshold, exact native seven-metric mapping, full graph, or self-time certification.",
            "Bounds use inclusive source extraction; 10s-bin counts exclude the exact upper endpoint.",
            "Duplicate file bytes do not by themselves identify duplicate or independent fault injections.",
            "Parent reference resolution, clock causality, duration completion availability unverified.",
            "Logs, histograms and conclusion are footer-only; no code/configuration executed from archive.",
            "No feature construction, splitting, fitting, tuning, final testing or original native/RCAEval access.",
        ],
    }
    with args.report.open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")
    print("QUALITY_AUDIT_COMPLETE", json.dumps(report["counts"]), args.report, flush=True)


if __name__ == "__main__":
    main()
