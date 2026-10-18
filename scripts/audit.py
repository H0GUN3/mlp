"""Direct, read-only telemetry audit. Generated findings never modify source data."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import time

import pyarrow as pa
import pyarrow.compute as pc
from pyarrow.compute import call_function as compute
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parents[1]
EVIDENCE = BASE / "evidence"


def load(path):
    return json.loads(path.read_text())


def save(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def seconds(column):
    dtype = column.type
    if pa.types.is_timestamp(dtype):
        # Whole-second range diagnostics; avoid lossy int64-nanosecond -> double conversion.
        return compute("divide", [pc.cast(column, pa.int64()), {"s": 1, "ms": 1000, "us": 1000000, "ns": 1000000000}[dtype.unit]])
    return column


def scan(path, findings):
    table = pq.read_table(path)
    table.validate(full=True)
    item = {"path": str(path.relative_to(BASE)), "rows": table.num_rows,
            "columns": {name: str(dtype) for name, dtype in zip(table.column_names, table.schema.types)},
            "nulls": {name: table[name].null_count for name in table.column_names}}
    item["nonfinite"] = {
        name: compute("sum", [compute("invert", [compute("is_finite", [table[name]])])]).as_py()
        for name in table.column_names if pa.types.is_floating(table[name].type)}
    time_column = next((name for name in ("startTime", "timestamp", "time")
                        if name in table.column_names and
                        (pa.types.is_integer(table[name].type) or pa.types.is_timestamp(table[name].type))), None)
    if time_column:
        values = seconds(table[time_column])
        item["time_column"] = time_column
        item["time_range"] = compute("min_max", [values]).as_py()
    if "message" in table.column_names:
        # A hit is a review flag, not proof of label leakage.
        mask = compute("match_substring_regex", [table["message"]],
                       options=pc.MatchSubstringOptions("(?i)chaos[-_ ]?(mesh|daemon)|stress-ng|chaosblade|fault.?inject"))
        item["injection_tool_log_hits"] = compute("sum", [mask]).as_py() or 0
        item["injection_tool_examples"] = table["message"].filter(pc.fill_null(mask, False)).slice(0, 3).to_pylist()
    findings.append(item)
    return table


def observed_calls(tables):
    calls, missing, duplicates, conflicts = set(), 0, 0, 0
    for table in tables:
        rows = list(zip(*(table[name].to_pylist()
                          for name in ("trace_id", "span_id", "parent_span_id", "service_name"))))
        lookup, ambiguous = {}, set()
        for trace, span, parent, service in rows:
            key = (trace, span)
            duplicates += key in lookup
            if key in lookup and lookup[key] != (service, parent):
                ambiguous.add(key)
            lookup[key] = (service, parent)
        conflicts += len(ambiguous)
        for trace, span, parent, child_service in rows:
            if not parent or set(parent) == {"0"}:
                continue
            if (trace, span) in ambiguous or (trace, parent) in ambiguous:
                continue
            parent_service = lookup.get((trace, parent), (None, None))[0]
            if parent_service is None:
                missing += 1
            elif child_service and parent_service != child_service:
                calls.add((parent_service, child_service))
    return calls, missing, duplicates, conflicts


def self_check():
    table = pa.table({"trace_id": ["t", "t", "u"], "span_id": ["a", "b", "b"],
                      "parent_span_id": ["", "a", "x"], "service_name": ["caller", "callee", "other"]})
    assert observed_calls([table]) == ({("caller", "callee")}, 1, 0, 0)
    conflicting = pa.table({"trace_id": ["t", "t", "t"], "span_id": ["a", "a", "b"],
                           "parent_span_id": ["", "", "a"], "service_name": ["x", "y", "child"]})
    assert observed_calls([conflicting]) == (set(), 0, 1, 1)
    assert seconds(pa.array([1_000_000], type=pa.timestamp("us")))[0].as_py() == 1
    assert seconds(pa.array([1777651009453396461], type=pa.timestamp("ns")))[0].as_py() == 1777651009


def rcaeval(findings) -> dict[str, object]:
    root = BASE / "data" / "rcaeval"
    index = scan(root / "cases.parquet", findings).to_pylist()
    selected = [record for record in index if record["dataset"] in ("RE2-OB", "RE2-TT")]
    assert len(selected) == 180
    results = []
    for n, record in enumerate(selected, 1):
        case = root / record["case"]
        result = {key: record[key] for key in ("case", "dataset", "root_cause_service", "fault", "repetition")}
        result["split_group"] = f"{record['dataset']}|{record['root_cause_service']}|{record['fault']}"
        injection = int((case / "inject_time.txt").read_text().strip())
        result["index_mismatches"] = []
        if injection != record["inject_time"]:
            result["index_mismatches"].append("inject_time")
        metrics = scan(case / "metrics.parquet", findings)
        result["normal_rows"] = compute("sum", [compute("less", [metrics["time"], injection])]).as_py()
        result["fault_rows"] = compute("sum", [compute("greater_equal", [metrics["time"], injection])]).as_py()
        result["root_in_metrics"] = any(name.startswith(record["root_cause_service"] + "_")
                                         for name in metrics.column_names)
        result["duplicate_metric_times"] = metrics.num_rows - len(compute("unique", [metrics["time"]]))
        result["all_null_metric_columns"] = [name for name in metrics.column_names
                                              if metrics[name].null_count == metrics.num_rows]
        for field, actual in (("n_timesteps", metrics.num_rows),
                              ("normal_timesteps", result["normal_rows"]),
                              ("faulty_timesteps", result["fault_rows"]),
                              ("n_metrics", metrics.num_columns - 1)):
            if record[field] != actual:
                result["index_mismatches"].append(field)
        del metrics
        for kind, service_column, timestamp, scale in (
                ("logs", "container_name", "timestamp", 1),
                ("traces", "serviceName", "startTime", 1e6)):
            path = case / f"{kind}.parquet"
            result[f"{kind}_rows"] = 0
            result[f"root_in_{kind}"] = False
            if path.exists():
                table = scan(path, findings)
                result[f"{kind}_rows"] = table.num_rows
                services = compute("unique", [table[service_column]]).to_pylist()
                result[f"{kind}_services"] = services
                result[f"root_in_{kind}"] = record["root_cause_service"] in services
                ts = compute("divide", [table[timestamp], scale])
                result[f"{kind}_normal_rows"] = compute("sum", [compute("less", [ts, injection])]).as_py()
                result[f"{kind}_fault_rows"] = compute("sum", [compute("greater_equal", [ts, injection])]).as_py()
                del table
            if result[f"{kind}_rows"] != record[f"n_{kind}"]:
                result["index_mismatches"].append(f"n_{kind}")
        result["paired_metrics_usable"] = bool(result["normal_rows"] and result["fault_rows"] and result["root_in_metrics"])
        result["all_modalities_paired"] = bool(result["paired_metrics_usable"] and
            result.get("logs_normal_rows") and result.get("logs_fault_rows") and
            result.get("traces_normal_rows") and result.get("traces_fault_rows"))
        results.append(result)
        if n % 30 == 0:
            print(f"AUDIT RCAEval {n}/180", flush=True)
    save("rcaeval-cases.json", results)
    fields = ["case", "dataset", "root_cause_service", "fault", "repetition", "split_group",
              "normal_rows", "fault_rows", "logs_rows", "traces_rows",
              "logs_normal_rows", "logs_fault_rows", "traces_normal_rows", "traces_fault_rows",
              "root_in_metrics", "root_in_logs", "root_in_traces", "paired_metrics_usable",
              "all_modalities_paired", "all_null_metric_columns"]
    with (EVIDENCE / "rcaeval-readiness.csv").open("w") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    return {"cases": len(results), "by_system": dict(Counter(r["dataset"] for r in results)),
            "paired_metrics_usable": sum(r["paired_metrics_usable"] for r in results),
            "all_modalities_paired": sum(r["all_modalities_paired"] for r in results),
            "incomplete_modalities": [r["case"] for r in results if not r["all_modalities_paired"]],
            "cases_with_all_null_metric_columns": sum(bool(r["all_null_metric_columns"]) for r in results),
            "missing_logs": [r["case"] for r in results if not r["logs_rows"]],
            "root_absent_traces": [r["case"] for r in results if not r["root_in_traces"]],
            "no_normal_or_fault": [r["case"] for r in results if not r["normal_rows"] or not r["fault_rows"]],
            "index_mismatches": [r["case"] for r in results if r["index_mismatches"]],
            "repeat_groups": len({r["split_group"] for r in results})}


def ops_lite(findings) -> dict[str, object]:
    root = BASE / "data" / "ops-lite"
    manifest = [json.loads(line) for line in (root / "manifest.jsonl").read_text().splitlines()]
    label_results, structural_issues, roles = [], [], Counter()
    for record in manifest:
        case = root / "cases" / record["name"]
        label, graph = load(case / "label.json"), load(case / "causal_graph.json")
        injection, env = load(case / "injection.json"), load(case / "env.json")
        assert isinstance(injection, dict) and isinstance(env, dict)
        mapping = graph["component_to_service"]
        projected = {(mapping.get(edge["source"]), mapping.get(edge["target"])) for edge in graph["edges"]}
        projected = {(a, b) for a, b in projected if a and b and a != b}
        edges = {tuple(edge) for edge in label["service_edges"]}
        required = {fault["service"] for fault in label["faults"] if fault["role"] == "required"}
        node_ids = {node["component"] for node in graph["nodes"]}
        issues = []
        if projected != edges:
            issues.append("projection_mismatch")
        if required != set(record["root_services"]):
            issues.append("required_manifest_mismatch")
        if len(edges) != record["n_service_edges"] or bool(edges) != record["process_applicable"]:
            issues.append("edge_manifest_mismatch")
        if label["case"] != record["name"]:
            issues.append("case_name_mismatch")
        dangling = [edge for edge in graph["edges"]
                    if edge["source"] not in node_ids or edge["target"] not in node_ids]
        if dangling:
            issues.append("edge_endpoint_absent_from_nodes")
        roles.update(fault["role"] for fault in label["faults"])
        label_results.append({"case": record["name"], "system": record["system"],
                              "required": sorted(required), "edges": sorted(edges),
                              "issues": issues})
        if issues:
            structural_issues.append({"case": record["name"], "issues": issues})
    save("ops-lite-labels.json", label_results)
    sample = load(EVIDENCE / "ops-lite-sample.json")["cases"]
    results = []
    for n, name in enumerate(sample, 1):
        case = root / "cases" / name
        label = load(case / "label.json")
        traces = []
        result = {"case": name, "system": label["system"], "rows": {}, "root_visibility": {}}
        roots = {fault["service"] for fault in label["faults"] if fault["role"] == "required"}
        for path in sorted(case.glob("*.parquet")):
            table = scan(path, findings)
            result["rows"][path.name] = table.num_rows
            if "service_name" in table.column_names:
                services = set(compute("unique", [table["service_name"]]).to_pylist())
                result["root_visibility"][path.name] = sorted(roots & services)
            if path.name.endswith("_logs.parquet"):
                result[path.stem + "_populated_templates"] = (
                    table.num_rows - table["attr.log_template"].null_count
                    if "attr.log_template" in table.column_names else 0)
            if path.name.endswith("_traces.parquet"):
                traces.append(table.select(["trace_id", "span_id", "parent_span_id", "service_name"]))
            del table
        assert len(result["rows"]) == 10, name
        calls, missing, duplicates, conflicts = observed_calls(traces)
        candidates = {(b, a) for a, b in calls}
        gold = {tuple(edge) for edge in label["service_edges"]}
        result.update({"gold_edges": len(gold), "reverse_call_candidates": len(candidates),
                       "covered_gold": len(gold & candidates),
                       "gold_with_either_call_direction": sum((a,b) in calls or (b,a) in calls for a,b in gold),
                       "missing_gold_edges": sorted(gold - candidates),
                       "missing_parent_spans": missing, "duplicate_span_keys": duplicates,
                       "conflicting_span_keys_excluded": conflicts})
        results.append(result)
        print(f"AUDIT ops-lite sample {n}/30", flush=True)
    save("ops-lite-sample-audit.json", results)
    totals = {key: sum(r[key] for r in results)
              for key in ("gold_edges", "reverse_call_candidates", "covered_gold", "gold_with_either_call_direction")}
    return {**totals, "all_labels": len(label_results), "label_issues": structural_issues,
                   "roles": dict(roles), "process_cases": sum(bool(r["edges"]) for r in label_results),
                   "by_system": dict(Counter(r["system"] for r in label_results)),
                   "sample_cases": len(results), "sample_by_system": dict(Counter(r["system"] for r in results)),
                   "empty_normal_logs": sum(not r["rows"]["normal_logs.parquet"] for r in results),
                   "empty_abnormal_logs": sum(not r["rows"]["abnormal_logs.parquet"] for r in results)}


def duplicates(key):
    download = load(EVIDENCE / f"{key}-downloads.json")
    groups = defaultdict(list)
    case_digests = defaultdict(list)
    for record in download["files"]:
        if record["path"].endswith(".parquet") and not record["path"].endswith("cases.parquet"):
            groups[record["sha256"]].append(record["path"])
            path = Path(record["path"])
            case_digests[str(path.parent)].append((path.name, record["sha256"]))
    cases = defaultdict(list)
    for name, files in case_digests.items():
        digest = hashlib.sha256(json.dumps(sorted(files)).encode()).hexdigest()
        cases[digest].append(name)
    return {"identical_files": [paths for paths in groups.values() if len(paths) > 1],
            "identical_acquired_telemetry_cases": [names for names in cases.values() if len(names) > 1]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["rcaeval", "ops-lite"])
    key = parser.parse_args().dataset
    self_check()
    downloads = load(EVIDENCE / f"{key}-downloads.json")
    assert not downloads["failed"], "Download failures must be resolved before auditing"
    findings = []
    started = time.monotonic()
    result = rcaeval(findings) if key == "rcaeval" else ops_lite(findings)
    result["duplicates"] = duplicates(key)
    result["parquet_files_fully_decoded"] = len(findings)
    result["rows_fully_decoded"] = sum(f["rows"] for f in findings)
    result["log_leakage_flags"] = [{"path": f["path"], "hits": f["injection_tool_log_hits"],
                                   "examples": f["injection_tool_examples"]}
                                  for f in findings if f.get("injection_tool_log_hits")]
    result["seconds"] = time.monotonic() - started
    save(f"{key}-file-audit.json", findings)
    save(f"{key}-summary.json", result)
    print("COMPLETE " + json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
