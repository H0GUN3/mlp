"""Read-only HTTP observation census and declared, non-performance-selected deep sample."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import resource
import tarfile
import time

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from pyarrow.compute import call_function as compute
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "rcabench_assessment_20261013"
META = HERE.parent / "research_reset_review_20261016"
HELPER = OLD / "quality_audit.py"
_spec = importlib.util.spec_from_file_location("previous_rcab_quality", HELPER)
if _spec is None or _spec.loader is None:
    raise ImportError(str(HELPER))
_quality_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_quality_helpers)
nonempty = _quality_helpers.nonempty
CORE = ("normal_metrics.parquet", "abnormal_metrics.parquet",
        "normal_traces.parquet", "abnormal_traces.parquet")
TRACE = ["time", "trace_id", "span_id", "parent_span_id", "span_name",
         "service_name", "duration", "attr.span_kind", "attr.status_code",
         "attr.http.response.status_code", "attr.http.request.method",
         "attr.k8s.pod.name"]
METRIC = ["service_name", "metric", "value", "attr.k8s.pod.name", "attr.k8s.node.name"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def flag(value):
    return pc.fill_null(value, False)


def equals(column, value):
    return flag(compute("equal", [column, pa.scalar(value)]))


def and_all(*columns):
    result = flag(columns[0])
    for column in columns[1:]:
        result = compute("and", [result, flag(column)])
    return result


def sum_flags(table, names, keys):
    return table.group_by(keys, use_threads=False).aggregate([(name, "sum") for name in names]).to_pylist()


def trace_profile(table, start, end):
    ticks = table["time"].cast(pa.int64())
    http = table["attr.http.response.status_code"]
    http_known = and_all(compute("greater_equal", [http, pa.scalar(100)]),
                         compute("less_equal", [http, pa.scalar(599)]))
    http_error = and_all(compute("greater_equal", [http, pa.scalar(400)]),
                         compute("less_equal", [http, pa.scalar(599)]))
    flags = {
        "rows": pa.array(np.ones(len(table), dtype=np.int64)),
        "http_known": http_known,
        "http_error": http_error,
        "span_error": equals(table["attr.status_code"], "Error"),
        "span_unset": equals(table["attr.status_code"], "Unset"),
        "identified": and_all(nonempty(table["trace_id"]), nonempty(table["span_id"])),
        "parent_present": nonempty(table["parent_span_id"]),
        "operation_named": nonempty(table["span_name"]),
        "method_present": nonempty(table["attr.http.request.method"]),
        "pod_present": nonempty(table["attr.k8s.pod.name"]),
        "completion_after_period": compute("greater", [
            compute("add", [ticks, table["duration"].cast(pa.int64())]),
            pa.scalar(end * 1_000_000_000)]),
    }
    for seconds in (10, 30, 60):
        cut = min(start + seconds, end) * 1_000_000_000
        in_prefix = and_all(compute("greater_equal", [ticks, pa.scalar(start * 1_000_000_000)]),
                            compute("less", [ticks, pa.scalar(cut)]))
        flags[f"prefix{seconds}_starts"] = in_prefix
        flags[f"prefix{seconds}_unfinished"] = and_all(
            in_prefix, compute("greater", [
                compute("add", [ticks, table["duration"].cast(pa.int64())]), pa.scalar(cut)]))
    work = table.select(["service_name", "attr.span_kind"])
    for key, values in flags.items():
        work = work.append_column(key, values.cast(pa.int64()))
    grouped = sum_flags(work, list(flags), ["service_name", "attr.span_kind"])
    return grouped


def detailed_trace(table, targets):
    unique, ambiguous = {}, set()
    columns = ["trace_id", "span_id", "parent_span_id", "service_name", "attr.span_kind",
               "attr.http.response.status_code", "attr.status_code", "span_name",
               "time", "duration"]
    work = table.select(columns).set_column(columns.index("time"), "time",
                                           table["time"].cast(pa.int64()))
    duplicate_rows = 0
    for row in zip(*(work[name].to_pylist() for name in columns)):
        key = row[:2]
        if not all(key):
            continue
        if key in unique:
            duplicate_rows += 1
            if unique[key] != row:
                ambiguous.add(key)
        else:
            unique[key] = row
    edge_counts, pair_counts = Counter(), Counter()
    resolved = references = contained_violations = client_server = both_known = 0
    for key, row in unique.items():
        if key in ambiguous or not row[2] or row[2] == "0" * len(row[2]):
            continue
        references += 1
        parent_key = (row[0], row[2])
        if parent_key not in unique or parent_key in ambiguous:
            continue
        resolved += 1
        parent = unique[parent_key]
        edge_counts[(parent[3], row[3])] += 1
        if row[8] < parent[8] or row[8] + row[9] > parent[8] + parent[9]:
            contained_violations += 1
        if parent[4] == "Client" and row[4] == "Server":
            client_server += 1
            valid_codes = all(isinstance(x, int) and 100 <= x <= 599 for x in (parent[5], row[5]))
            both_known += valid_codes
            if set((parent[3], row[3])) == set(targets):
                label = f"{parent[3]} -> {row[3]} | {parent[5]}/{row[5]} | {parent[6]}/{row[6]}"
                pair_counts[label] += 1
    return {
        "rows": len(table), "unique_span_identities": len(unique),
        "repeated_identity_rows": duplicate_rows, "conflicting_identities": len(ambiguous),
        "unambiguous_parent_references": references, "resolved_parent_references": resolved,
        "child_outside_parent_interval": contained_violations,
        "client_server_parent_pairs": client_server, "pairs_with_both_http_codes": both_known,
        "configured_endpoint_pair_outcomes": dict(pair_counts),
        "edges": [{"source": a, "target": b, "count": n} for (a, b), n in edge_counts.items()],
        "_identity_keys": {key for key in unique if key not in ambiguous},
    }


def metric_profile(table):
    valid = and_all(nonempty(table["service_name"]), nonempty(table["metric"]),
                    compute("is_finite", [table["value"]]))
    table = table.filter(valid)
    grouped = table.group_by(["service_name", "metric"], use_threads=False).aggregate([
        ("value", "count"), ("value", "mean")]).to_pylist()
    mapping = table.select(["service_name", "attr.k8s.pod.name", "attr.k8s.node.name"])
    mapping = mapping.group_by(mapping.column_names, use_threads=False).aggregate([]).to_pylist()
    return grouped, mapping


def log_profile(table):
    identified = and_all(nonempty(table["trace_id"]), nonempty(table["span_id"]))
    message = table["message"]
    flags = {
        "rows": pa.array(np.ones(len(table), dtype=bool)),
        "identified": identified,
        "error_level": compute("match_substring_regex", [table["level"]],
                               options=pc.MatchSubstringOptions("(?i)error|fatal|critical")),
        "error_keyword": compute("match_substring_regex", [message],
                                 options=pc.MatchSubstringOptions("(?i)exception|timeout|timed out|failed|failure|error")),
        "injection_marker": compute("match_substring_regex", [message],
                                    options=pc.MatchSubstringOptions("(?i)chaosmesh|chaos-mesh|byteman|rcabench|fault injected")),
    }
    work = table.select(["service_name"])
    for key, values in flags.items():
        work = work.append_column(key, flag(values).cast(pa.int64()))
    ids = table.filter(identified).select(["trace_id", "span_id"])
    return {"per_service": sum_flags(work, list(flags), ["service_name"]),
            "_identity_keys": set(zip(ids["trace_id"].to_pylist(), ids["span_id"].to_pylist()))}


def select_samples(details):
    cases = details["records"]
    result = {min(k for k, v in cases.items() if v["injection.json"]["fault_type"] == kind)
              for kind in range(5, 14)}
    result.update([
        "ts2-ts-ui-dashboard-response-replace-code-qzfj27",
        "ts2-ts-basic-service-request-replace-method-v6gzn8",
        "ts3-ts-basic-service-response-replace-code-ws6vpb",
        "ts5-ts-order-service-stress-svfvxk",
        min(k for k, v in cases.items() if v["injection.json"]["fault_type"] == 17)])
    assert result <= cases.keys()
    return sorted(result)


def self_test():
    table = pa.table({
        "time": pa.array([0, 1, 9], type=pa.timestamp("ns", tz="UTC")),
        "trace_id": ["t", "t", "t"], "span_id": ["a", "b", "b"],
        "parent_span_id": ["", "a", "a"], "span_name": ["GET /", "GET /", "GET /"],
        "service_name": ["a", "b", "b"], "duration": pa.array([3, 1, 1], type=pa.uint64()),
        "attr.span_kind": ["Client", "Server", "Server"],
        "attr.status_code": ["Error", "Ok", "Ok"],
        "attr.http.response.status_code": [500, 200, 200],
        "attr.http.request.method": ["GET"] * 3, "attr.k8s.pod.name": ["p", "q", "q"]})
    conflict = detailed_trace(table, ["a", "b"])
    assert conflict["conflicting_identities"] == 1 and conflict["resolved_parent_references"] == 0
    clean = detailed_trace(table.slice(0, 2), ["a", "b"])
    assert clean["client_server_parent_pairs"] == clean["pairs_with_both_http_codes"] == 1
    assert sum(clean["configured_endpoint_pair_outcomes"].values()) == 1
    profile = trace_profile(table.slice(0, 2), 0, 1)
    assert sum(row["http_error_sum"] for row in profile) == 1
    zero = table.slice(0, 1).set_column(9, "attr.http.response.status_code", pa.array([0]))
    assert trace_profile(zero, 0, 1)[0]["http_known_sum"] == 0
    logs = log_profile(pa.table({"trace_id": ["t", ""], "span_id": ["a", ""],
                                "service_name": ["a", "a"], "level": ["ERROR", "INFO"],
                                "message": ["Timeout", "healthy"]}))
    assert logs["per_service"][0]["rows_sum"] == 2
    assert logs["per_service"][0]["identified_sum"] == 1
    metrics, mapping = metric_profile(pa.table({
        "service_name": ["a", "a"], "metric": ["cpu", "cpu"], "value": [1., float("nan")],
        "attr.k8s.pod.name": ["pod", "pod"], "attr.k8s.node.name": ["node", "node"]}))
    assert metrics[0]["value_count"] == 1 and len(mapping) == 1
    print("OBSERVABILITY_SELF_TEST_PASS", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    output = HERE / "rcab_observability.json"
    manifest_path = HERE / "rcab_sample_manifest.json"
    if output.exists() or manifest_path.exists():
        raise FileExistsError("Audit outputs already exist")
    started = time.perf_counter()
    blobs = {name: path.read_bytes() for name, path in {
        "inventory": OLD / "metadata_inventory.json", "quality": OLD / "quality_audit.json",
        "details": META / "metadata_details.json"}.items()}
    inventory, quality, details = (json.loads(blobs[k]) for k in ("inventory", "quality", "details"))
    assert details["inventory_sha256"] == sha(blobs["inventory"])
    assert details["quality_sha256"] == sha(blobs["quality"])
    source_cases = {c["case"]: c for c in inventory["cases"]}
    http_cases = {k for k, v in details["records"].items() if 5 <= v["injection.json"]["fault_type"] <= 13}
    samples = set(select_samples(details))
    manifest = {
        "http_census_cases": sorted(http_cases), "deep_sample_cases": sorted(samples),
        "selection": "lexicographically first per HTTP type + previously discussed UI example + both known HTTP trace-missing cases + one JVM memory and one network-delay control",
        "selection_uses_model_scores": False, "source_sha256": {k: sha(v) for k, v in blobs.items()}}
    assert len(http_cases) == 796
    with manifest_path.open("x", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    archive_path = OLD / "rcabench-absolute_anomaly.tar.gz"
    before = archive_path.stat()
    assert before.st_size == inventory["source"]["bytes"]
    records, service_metrics, observed_services = {}, defaultdict(Counter), Counter()
    all_schemas, processed_hashes = {}, {}
    visited = files_read = rows_read = 0
    for case in http_cases | samples:
        injection = details["records"][case]["injection.json"]
        point = json.loads(injection["display_config"])["injection_point"]
        anchor = point.get("app_name", point.get("app_label", point.get("source_service")))
        counterpart = point.get("server_address", point.get("target_service", point.get("domain")))
        records[case] = {"fault_type": injection["fault_type"], "anchor": anchor,
                         "counterpart": counterpart, "files": {}}
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            visited += 1
            parts = PurePosixPath(member.name).parts
            if len(parts) != 2 or parts[0] not in source_cases:
                raise ValueError("Unexpected archive member")
            case, filename = parts
            if source_cases[case]["files"].get(filename) != member.size:
                raise ValueError("Member size changed")
            need = (case in http_cases and filename in CORE) or (
                case in samples and filename in (*CORE, "normal_logs.parquet", "abnormal_logs.parquet"))
            if not need:
                continue
            if member.name in processed_hashes or member.size > 16 * 1024 * 1024:
                raise ValueError("Duplicate/oversized selected member")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Unreadable member")
            with source:
                payload = source.read(member.size + 1)
            if len(payload) != member.size or sha(payload) != quality["file_sha256"][case][filename]:
                raise ValueError("Input digest mismatch")
            processed_hashes[member.name] = sha(payload)
            parquet = pq.ParquetFile(pa.BufferReader(payload))
            schema = {f.name: str(f.type) for f in parquet.schema_arrow}
            if schema not in all_schemas.get(filename, []):
                all_schemas.setdefault(filename, []).append(schema)
            trace = filename.endswith("_traces.parquet")
            metric = filename.endswith("_metrics.parquet")
            columns = TRACE if trace else METRIC if metric else [
                "time", "trace_id", "span_id", "service_name", "level", "message"]
            if not set(columns) <= set(schema) or parquet.metadata.num_rows > 2_000_000:
                raise ValueError("Unexpected schema or row budget")
            table = parquet.read(columns=columns, use_threads=False)
            rows_read += len(table)
            files_read += 1
            rec = records[case]
            prefix = "NORMAL" if filename.startswith("normal_") else "ABNORMAL"
            env = details["records"][case]["env.json"]
            if trace:
                grouped = trace_profile(table, int(env[prefix + "_START"]), int(env[prefix + "_END"]))
                services = sorted({r["service_name"] for r in grouped if r["service_name"]})
                total = Counter()
                for row in grouped:
                    total.update({k: v for k, v in row.items() if k.endswith("_sum") and v is not None})
                result = {"rows": len(table), "services": services, "totals": dict(total),
                          "targets": [r for r in grouped if r["service_name"] in (rec["anchor"], rec["counterpart"])]}
                if case in samples:
                    result["detail"] = detailed_trace(table, [rec["anchor"], rec["counterpart"]])
                    result["all_service_kind_profiles"] = grouped
            elif metric:
                grouped, mapping = metric_profile(table)
                services = sorted({r["service_name"] for r in grouped})
                for row in grouped:
                    service_metrics[row["service_name"]][row["metric"]] += 1
                result = {"rows": len(table), "services": services, "mapping": mapping,
                          "targets": [r for r in grouped if r["service_name"] in (rec["anchor"], rec["counterpart"])]}
            else:
                result = log_profile(table)
                result["rows"] = len(table)
                services = sorted({r["service_name"] for r in result["per_service"] if r["service_name"]})
            for service in services:
                observed_services[service] += 1
            rec["files"][filename] = result
            if files_read % 200 == 0:
                print("OBSERVABILITY_PROGRESS", files_read, "rows", rows_read, flush=True)
    after = archive_path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    assert visited == sum(len(c["files"]) for c in source_cases.values())
    for case, rec in records.items():
        expected = set(CORE) | ({"normal_logs.parquet", "abnormal_logs.parquet"} if case in samples else set())
        assert set(rec["files"]) == expected
        if case in samples:
            for period in ("normal", "abnormal"):
                tr = rec["files"][period + "_traces.parquet"]["detail"].pop("_identity_keys")
                lg = rec["files"][period + "_logs.parquet"].pop("_identity_keys")
                rec["files"][period + "_logs.parquet"]["identified_log_span_keys"] = len(lg)
                rec["files"][period + "_logs.parquet"]["keys_joinable_to_trace"] = len(lg & tr)
    result = {
        "status": "PASS", "manifest": manifest, "cases": records,
        "files_read": files_read, "rows_read": rows_read, "visited_members": visited,
        "schemas": all_schemas, "service_metric_file_counts": dict(service_metrics),
        "service_observed_file_counts": dict(observed_services), "file_sha256": processed_hashes,
        "seconds": time.perf_counter() - started, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "reused_helper_sha256": sha(HELPER.read_bytes()),
        "limits": [
            "HTTP census is 796 cases; parent pairing/log inspection is a declared sample, not a corpus claim.",
            "Status>=400 denotes HTTP error, not a unique causal root; Unset/0 are not evidence of success.",
            "Ambiguous duplicate identities are excluded only from diagnostic joins, never removed from data.",
            "Duration uses the previously corroborated ns interpretation; physical clock and arrival time remain unverified.",
            "Metric means pool observed rows, not time-weighted causal estimates; unit/counter semantics not restored.",
            "No model training, split assignment, feature-cache generation or protected final-test observations."]}
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print("OBSERVABILITY_PASS", files_read, rows_read, "seconds", result["seconds"], flush=True)


if __name__ == "__main__":
    main()
