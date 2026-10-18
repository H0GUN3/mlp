"""Audit RCABench labels, timing, SLI summaries and already-verified row support."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "rcabench_assessment_20261013"
# Pinned upstream rcabench.py FAULT_TYPES, not inferred from filenames.
FAULT_TYPES = [
    "PodKill", "PodFailure", "ContainerKill", "MemoryStress", "CPUStress",
    "HTTPRequestAbort", "HTTPResponseAbort", "HTTPRequestDelay", "HTTPResponseDelay",
    "HTTPResponseReplaceBody", "HTTPResponsePatchBody", "HTTPRequestReplacePath",
    "HTTPRequestReplaceMethod", "HTTPResponseReplaceCode", "DNSError", "DNSRandom",
    "TimeSkew", "NetworkDelay", "NetworkLoss", "NetworkDuplicate", "NetworkCorrupt",
    "NetworkBandwidth", "NetworkPartition", "JVMLatency", "JVMReturn", "JVMException",
    "JVMGarbageCollector", "JVMCPUStress", "JVMMemoryStress", "JVMMySQLLatency",
    "JVMMySQLException"]
TYPE_SOURCE = ("https://github.com/OperationsPAI/rcabench-platform/blob/"
               "5a463bd2bfaecda1b26aed9fe3f018859196bb0e/"
               "src/rcabench_platform/v2/datasets/rcabench.py")
CORE = ["normal_metrics.parquet", "abnormal_metrics.parquet",
        "normal_traces.parquet", "abnormal_traces.parquet"]


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def describe(values):
    values = sorted(float(v) for v in values if finite(v))
    if not values:
        return {"n": 0}
    def q(p):
        at = (len(values) - 1) * p
        left = int(at)
        right = min(left + 1, len(values) - 1)
        return values[left] + (at - left) * (values[right] - values[left])
    return {"n": len(values), "min": values[0], "p25": q(.25), "median": q(.5),
            "p75": q(.75), "p95": q(.95), "max": values[-1]}


def timestamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def scope(point):
    if "source_service" in point and "target_service" in point:
        return "network_pair", point["source_service"], [
            point["source_service"], point["target_service"]]
    if "server_address" in point and "app_name" in point:
        return "http_endpoint", point["app_name"], [point["app_name"], point["server_address"]]
    if "domain" in point and "app_name" in point:
        return "dns_endpoint", point["app_name"], [point["app_name"], point["domain"]]
    if "db_name" in point and "app_name" in point:
        return "database_operation", point["app_name"], [point["app_name"], "mysql"]
    anchor = point.get("app_name", point.get("app_label"))
    return ("single_application", anchor, [anchor]) if anchor else ("unknown", None, [])


def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def interval_audit(rows):
    by_namespace = defaultdict(list)
    for row in rows:
        by_namespace[row["namespace"]].append(row)
    data_pairs, abnormal_pairs, normal_fault_pairs, touching_pairs = [], [], [], []
    components = []
    for namespace, values in by_namespace.items():
        values.sort(key=lambda r: (r["normal_start"], r["case"]))
        parent = list(range(len(values)))
        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        for i, a in enumerate(values):
            for j in range(i + 1, len(values)):
                b = values[j]
                if b["normal_start"] > a["abnormal_end"]:
                    break
                seconds = overlap(a["normal_start"], a["abnormal_end"],
                                  b["normal_start"], b["abnormal_end"])
                if seconds:
                    data_pairs.append({"a": a["case"], "b": b["case"], "seconds": seconds})
                    parent[find(j)] = find(i)
                elif b["normal_start"] == a["abnormal_end"]:
                    touching_pairs.append([a["case"], b["case"]])
                ab = overlap(a["abnormal_start"], a["abnormal_end"],
                             b["abnormal_start"], b["abnormal_end"])
                if ab:
                    abnormal_pairs.append({"a": a["case"], "b": b["case"], "seconds": ab})
                for normal, fault in ((a, b), (b, a)):
                    nf = overlap(normal["normal_start"], normal["normal_end"],
                                 fault["injection_start"], fault["injection_end"])
                    if nf:
                        normal_fault_pairs.append({
                            "normal_case": normal["case"], "fault_case": fault["case"],
                            "seconds": nf})
        groups = defaultdict(list)
        for i, row in enumerate(values):
            groups[find(i)].append(row["case"])
        components.extend({"namespace": namespace, "cases": members} for members in groups.values())
    return {
        "rule": "strict positive half-open overlap within same env.NAMESPACE; not a split assignment",
        "data_overlap_pairs": data_pairs, "abnormal_overlap_pairs": abnormal_pairs,
        "normal_vs_other_injection_pairs": normal_fault_pairs,
        "data_touching_boundary_pairs": touching_pairs,
        "connected_components": components,
        "counts": {"data_overlap_pairs": len(data_pairs),
                   "abnormal_overlap_pairs": len(abnormal_pairs),
                   "normal_vs_other_injection_pairs": len(normal_fault_pairs),
                   "normal_cases_at_risk": len({r["normal_case"] for r in normal_fault_pairs}),
                   "components": len(components),
                   "component_size_histogram": dict(sorted(Counter(
                       len(c["cases"]) for c in components).items()))},
        "limits": [
            "Same namespace does not establish unchanged deployment; separate namespaces may share hosts.",
            "Positive overlap is a risk flag, not proof of shared telemetry or causal contamination.",
            "Configuration repeats and temporal neighbors may remain dependent without positive overlap."]}


def audit(details, inventory, quality):
    previous = {c["case"]: c for c in inventory["cases"]}
    quality_by_case = {c["case"]: c for c in quality["cases"]}
    if set(details["records"]) != set(previous) or set(previous) != set(quality_by_case):
        raise ValueError("Case universe mismatch")
    rows, issues, examples = [], Counter(), {}
    nonfinite_fields = Counter()
    observed_metric_names = set()
    strict_configs, semantic_configs, task_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    sli_rows_total = 0
    for case, record in sorted(details["records"].items()):
        injection = record["injection.json"]
        env = record["env.json"]
        config = json.loads(injection["display_config"])
        engine = json.loads(injection["engine_config"])
        kind = injection["fault_type"]
        if not isinstance(kind, int) or kind not in range(len(FAULT_TYPES)):
            raise ValueError("Unknown fault type")
        roots = injection["ground_truth"]["service"]
        if sorted(roots) != sorted(previous[case]["root_services"]) or kind != previous[case]["fault_type"]:
            raise ValueError("Original inventory label changed")
        if engine["value"] != kind:
            raise ValueError("Engine type mismatch")
        if injection["injection_name"] != case:
            raise ValueError("Case identity mismatch")
        point = config["injection_point"]
        target_scope, anchor, expected = scope(point)
        label_matches = set(expected) == set(roots)
        periods = {key.lower(): int(env[key]) for key in
                   ("NORMAL_START", "NORMAL_END", "ABNORMAL_START", "ABNORMAL_END")}
        if any(periods[key.lower()] != previous[case]["periods_epoch_seconds"][key] for key in
               ("NORMAL_START", "NORMAL_END", "ABNORMAL_START", "ABNORMAL_END")):
            raise ValueError("Time metadata changed")
        start, end = timestamp(injection["start_time"]), timestamp(injection["end_time"])
        if not (periods["normal_start"] < periods["normal_end"] <= periods["abnormal_start"]
                < periods["abnormal_end"]) or end < start:
            raise ValueError("Invalid time ordering")
        summaries = record["conclusion.parquet"]["rows"]
        case_issue_keys, malformed = set(), []
        slo_count, nonempty_issue_rows = 0, 0
        max_drop, max_ratio = None, None
        for n, summary in enumerate(summaries):
            sli_rows_total += 1
            for key, value in summary.items():
                if key not in ("SpanName", "Issues") and not finite(value):
                    nonfinite_fields[key] += 1
            try:
                issue = json.loads(summary["Issues"])
                if not isinstance(issue, dict):
                    raise ValueError("Not an issue object")
            except (ValueError, TypeError) as error:
                malformed.append({"row": n, "error": str(error)})
                continue
            if issue:
                nonempty_issue_rows += 1
            case_issue_keys.update(issue)
            issues.update(issue.keys())
            for info in issue.values():
                if isinstance(info, dict) and info.get("slo_violated") is True:
                    slo_count += 1
            normal, abnormal = summary.get("NormalSuccRate"), summary.get("AbnormalSuccRate")
            if finite(normal) and finite(abnormal):
                drop = normal - abnormal
                max_drop = drop if max_drop is None else max(max_drop, drop)
            normal, abnormal = summary.get("NormalAvgDuration"), summary.get("AbnormalAvgDuration")
            if finite(normal) and normal > 0 and finite(abnormal):
                ratio = abnormal / normal
                max_ratio = ratio if max_ratio is None else max(max_ratio, ratio)
        support = quality_by_case[case]
        min_trace_coverage = {}
        absent_roots = {}
        for filename in CORE:
            file = support["files"][filename]
            absent_roots[filename] = [root for root in roots
                                      if file["roots"][root]["basic_valid_rows"] == 0]
            if "metrics" in filename:
                observed_metric_names.update(file["metric_names"])
            if "traces" in filename:
                fractions = [info["occupied_10s_bins"] / info["expected_10s_bins"]
                             for info in file["roots"].values() if info["expected_10s_bins"] > 0]
                min_trace_coverage[filename] = min(fractions) if fractions else None
        strict_key = canonical({"type": kind, "config": config})
        semantic_config = {k: v for k, v in config.items() if k != "namespace"}
        semantic_point = {k: v for k, v in point.items() if k != "pod_name"}
        semantic_config["injection_point"] = semantic_point
        semantic_key = canonical({"type": kind, "config": semantic_config})
        strict_configs[strict_key].append(case)
        semantic_configs[semantic_key].append(case)
        task_groups[str(injection.get("task_id"))].append(case)
        row = {
            "case": case, "fault_type_id": kind, "fault_type": FAULT_TYPES[kind],
            "namespace": env["NAMESPACE"], "display_namespace": config.get("namespace"),
            "roots": roots, "root_count": len(roots), "target_scope": target_scope,
            "configuration_anchor": anchor, "injection_point": point,
            "label_set_matches_config_rule": label_matches,
            "first_raw_label_matches_anchor": bool(roots) and roots[0] == anchor,
            "direction": config.get("direction"), "duration_parameter": config.get("duration"),
            "pre_duration": injection.get("pre_duration"), "task_id": injection.get("task_id"),
            "status": injection.get("status"), **periods,
            "injection_start": start, "injection_end": end,
            "start_delta_to_abnormal": start - periods["abnormal_start"],
            "end_delta_to_abnormal": end - periods["abnormal_end"],
            "normal_seconds": periods["normal_end"] - periods["normal_start"],
            "abnormal_seconds": periods["abnormal_end"] - periods["abnormal_start"],
            "sli_summary_rows": len(summaries), "sli_nonempty_issue_rows": nonempty_issue_rows,
            "sli_issue_keys": sorted(case_issue_keys), "sli_violation_entries": slo_count,
            "sli_malformed_issues": malformed, "max_endpoint_success_drop": max_drop,
            "max_endpoint_mean_latency_ratio": max_ratio,
            "all_labeled_roots_basic_rows": support["all_labeled_roots_have_basic_rows_in_both_modalities_and_periods"],
            "absent_labeled_roots": absent_roots, "min_labeled_root_trace_coverage": min_trace_coverage,
            "shared_normal_abnormal_boundary_span_ids": support["shared_boundary_trace_span_identities"],
            "invalid_marker": support["invalid_marker"],
            "strict_configuration_sha256": sha(strict_key.encode()),
            "semantic_configuration_sha256": sha(semantic_key.encode())}
        rows.append(row)
        examples.setdefault(target_scope, {"case": case, "injection_point": point,
                                           "raw_ground_truth": injection["ground_truth"],
                                           "config": config, "sli": summaries[:1]})
    type_summary = []
    for kind in sorted({row["fault_type_id"] for row in rows}):
        subset = [r for r in rows if r["fault_type_id"] == kind]
        type_summary.append({
            "id": kind, "name": FAULT_TYPES[kind], "cases": len(subset),
            "root_cardinality": dict(Counter(r["root_count"] for r in subset)),
            "target_scope": dict(Counter(r["target_scope"] for r in subset)),
            "sli_violation_cases": sum(r["sli_violation_entries"] > 0 for r in subset),
            "all_roots_basic_support": sum(r["all_labeled_roots_basic_rows"] for r in subset)})
    def repeated(groups):
        return [members for members in groups.values() if len(members) > 1]
    return {
        "status": "PASS", "cases": len(rows), "fault_type_source": TYPE_SOURCE,
        "observed_fault_types": type_summary,
        "target_scope_counts": dict(Counter(r["target_scope"] for r in rows)),
        "root_cardinality": dict(Counter(r["root_count"] for r in rows)),
        "label_set_rule_mismatches": [r["case"] for r in rows if not r["label_set_matches_config_rule"]],
        "raw_first_label_anchor_matches": sum(r["first_raw_label_matches_anchor"] for r in rows),
        "unique_configuration_anchors": len({r["configuration_anchor"] for r in rows}),
        "root_service_frequency": dict(Counter(root for r in rows for root in r["roots"])),
        "anchor_frequency": dict(Counter(r["configuration_anchor"] for r in rows)),
        "namespace_counts": dict(Counter(r["namespace"] for r in rows)),
        "direction_counts": dict(Counter(str(r["direction"]) for r in rows)),
        "date_range_utc": [datetime.fromtimestamp(min(r["normal_start"] for r in rows), timezone.utc).isoformat(),
                           datetime.fromtimestamp(max(r["abnormal_end"] for r in rows), timezone.utc).isoformat()],
        "normal_seconds": describe([r["normal_seconds"] for r in rows]),
        "abnormal_seconds": describe([r["abnormal_seconds"] for r in rows]),
        "start_offset_seconds": describe([r["start_delta_to_abnormal"] for r in rows]),
        "end_offset_seconds": describe([r["end_delta_to_abnormal"] for r in rows]),
        "sli": {
            "summary_rows": sli_rows_total,
            "cases_with_nonempty_issue": sum(r["sli_nonempty_issue_rows"] > 0 for r in rows),
            "cases_with_slo_flag": sum(r["sli_violation_entries"] > 0 for r in rows),
            "cases_without_slo_flag": [r["case"] for r in rows if r["sli_violation_entries"] == 0],
            "malformed_issue_cases": [r["case"] for r in rows if r["sli_malformed_issues"]],
            "issue_entry_counts": dict(issues), "nonfinite_or_null_summary_values": dict(nonfinite_fields),
            "max_success_drop_per_case": describe([r["max_endpoint_success_drop"] for r in rows]),
            "max_mean_latency_ratio_per_case": describe([r["max_endpoint_mean_latency_ratio"] for r in rows]),
            "limits": "Imported source-generated SLI flags; no raw counts/Z-tests/latency thresholds recomputed."},
        "support": {
            "all_labeled_roots_basic_rows": sum(r["all_labeled_roots_basic_rows"] for r in rows),
            "root_missing_cases_by_file": {f: sum(bool(r["absent_labeled_roots"][f]) for r in rows) for f in CORE},
            "normal_min_trace_bin_fraction": describe([r["min_labeled_root_trace_coverage"]["normal_traces.parquet"] for r in rows]),
            "abnormal_min_trace_bin_fraction": describe([r["min_labeled_root_trace_coverage"]["abnormal_traces.parquet"] for r in rows]),
            "shared_boundary_cases": sum(r["shared_normal_abnormal_boundary_span_ids"] > 0 for r in rows),
            "observed_gauge_metric_names": sorted(observed_metric_names),
            "limits": "Root support means at least one basic valid row, not sufficient diagnostic information."},
        "repeat_candidates": {
            "strict_configuration_groups": len(strict_configs),
            "semantic_configuration_groups": len(semantic_configs),
            "semantic_rule": "Ignore display namespace and ephemeral pod_name only; keep duration and other parameters",
            "strict_repeated_groups": repeated(strict_configs),
            "semantic_repeated_groups": repeated(semantic_configs),
            "task_id_groups": len(task_groups), "repeated_task_ids": repeated(task_groups),
            "limits": "Repeated configurations/task IDs are grouping candidates, not duplicate or independent-event proof."},
        "intervals": interval_audit(rows), "examples": examples, "case_rows": rows,
        "model_training": False, "split_assignment": False}


def self_test():
    assert describe([0, 10])["median"] == 5
    assert overlap(0, 4, 4, 8) == 0 and overlap(0, 5, 4, 8) == 1
    assert scope({"app_name": "a", "server_address": "b"}) == ("http_endpoint", "a", ["a", "b"])
    assert scope({"app_name": "a", "db_name": "db"}) == ("database_operation", "a", ["a", "mysql"])
    def row(name, normal_start, start, end):
        return {"case": name, "namespace": "same", "normal_start": normal_start,
                "normal_end": start, "abnormal_start": start, "abnormal_end": end,
                "injection_start": start, "injection_end": end}
    result = interval_audit([row("a", 0, 4, 8), row("b", 6, 10, 14), row("c", 14, 18, 22)])
    assert result["counts"]["data_overlap_pairs"] == 1
    assert result["counts"]["normal_vs_other_injection_pairs"] == 1
    assert result["counts"]["components"] == 2
    assert len(result["data_touching_boundary_pairs"]) == 1
    print("METADATA_ANALYSIS_SELF_TEST_PASS", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "metadata_analysis.json")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.output.exists():
        raise FileExistsError(args.output)
    started = time.perf_counter()
    paths = [HERE / "metadata_details.json", AUDIT / "metadata_inventory.json", AUDIT / "quality_audit.json"]
    blobs = [path.read_bytes() for path in paths]
    details, inventory, quality = [json.loads(blob) for blob in blobs]
    if details["inventory_sha256"] != sha(blobs[1]) or details["quality_sha256"] != sha(blobs[2]):
        raise ValueError("Input evidence hash mismatch")
    result = audit(details, inventory, quality)
    result.update(input_sha256={str(p): sha(b) for p, b in zip(paths, blobs)},
                  script_sha256=sha(Path(__file__).read_bytes()), seconds=time.perf_counter() - started)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("METADATA_ANALYSIS_PASS", result["cases"], "types", len(result["observed_fault_types"]),
          "SLI flagged", result["sli"]["cases_with_slo_flag"],
          "seconds", result["seconds"], flush=True)


if __name__ == "__main__":
    main()
