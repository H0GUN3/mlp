"""Read-only, selected-development-window Jaeger graph/field feasibility audit."""
import argparse
import ast
import codecs
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
ROOT = HERE.parents[1] / "data/eadro_native"
OUTCOME_KEYS = {"error", "http.status_code", "http.response.status_code",
                "rpc.grpc.status_code", "grpc.status_code", "otel.status_code",
                "status.code", "status_code", "error.type", "error.message"}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def union_covered(start, duration, intervals):
    end = start + duration
    clipped = sorted((max(start, a), min(end, b)) for a, b in intervals
                     if max(start, a) < min(end, b))
    total, right = 0, start
    for left, stop in clipped:
        total += max(0, stop - max(left, right))
        right = max(right, stop)
    assert 0 <= total <= duration
    return total, sum(b - a for a, b in clipped)


def tags_of(span):
    values = span.get("tags", [])
    if not isinstance(values, list):
        raise ValueError("Unexpected tag container")
    result = defaultdict(list)
    for tag in values:
        if not isinstance(tag, dict) or not isinstance(tag.get("key"), str):
            raise ValueError("Unexpected tag schema")
        result[tag["key"]].append(tag.get("value"))
    return dict(result)


def refs_of(span):
    refs = span.get("references", [])
    if refs is None:
        return []
    if not isinstance(refs, list):
        raise ValueError("Unexpected reference container")
    for ref in refs:
        if not isinstance(ref, dict) or not all(isinstance(ref.get(k), str)
                                               for k in ("refType", "traceID", "spanID")):
            raise ValueError("Unexpected reference schema")
    return refs


def pinned_parser(meta):
    path = NATIVE / "native_data_profile.py"
    assert sha(path) == meta["source"]["reused_profile_helpers_sha256"]
    # Reuse the pinned streaming parser without importing its pandas/numpy modules.
    tree = ast.parse(path.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "json_array")
    namespace: Dict[str, Any] = {"json": json, "codecs": codecs}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["json_array"]


def audit(system):
    started = time.perf_counter()
    meta_path = NATIVE / "native_inputs" / system / "metadata.json"
    meta = json.loads(meta_path.read_text())
    split_path = NATIVE / "calibration200" / system / "eadro/seed_11/split.json"
    split = json.loads(split_path.read_text())["indices"]
    selected = set(split["train"] + split["validation"])
    assert not selected.intersection(split["test"] + split["unassigned"])
    windows = defaultdict(dict)
    for index in selected:
        window = meta["windows"][index]
        windows[window["run_id"]][window["start"]] = index
    parse_array = pinned_parser(meta)
    root = ROOT / (system + "_Dataset") / (system + " Dataset")
    counts, tag_keys, ref_types, kinds, status_values = Counter(), Counter(), Counter(), Counter(), Counter()
    cell_counts, unique_cell_counts = Counter(), Counter()
    seen_cells, seen_identity, conflict_ids = set(), {}, set()
    residual_sum = residual_count = 0
    runs, hashes = [], {}
    for run in meta["runs"]:
        path = root / "data" / run["run_id"] / "spans.json"
        digest = hashlib.sha256()
        before = counts.copy()
        with path.open("rb") as stream:
            for trace in parse_array(stream, digest):
                processes = trace["processes"]
                spans = trace["spans"]
                index_map = defaultdict(list)
                for position, span in enumerate(spans):
                    index_map[(span["traceID"], span["spanID"])].append(position)
                chosen = {}
                for position, span in enumerate(spans):
                    stamp, duration = span["startTime"], span["duration"]
                    if type(stamp) is not int or type(duration) is not int or duration < 0:
                        raise ValueError("Invalid span timing")
                    second = stamp // 1000000 + 28800
                    if not run["record_start"] <= second < run["record_end_exclusive"]:
                        continue
                    window_start = run["record_start"] + ((second - run["record_start"]) // 10) * 10
                    original_index = windows[run["run_id"]].get(window_start)
                    if original_index is not None:
                        chosen[position] = original_index
                if not chosen:
                    continue
                counts["trace_objects_with_selected_spans"] += 1
                children = defaultdict(list)
                boundary_children = Counter()
                for position, span in enumerate(spans):
                    for ref in refs_of(span):
                        if ref["refType"] != "CHILD_OF":
                            continue
                        parent_positions = index_map.get((ref["traceID"], ref["spanID"]), [])
                        for parent in parent_positions:
                            if parent in chosen:
                                if position in chosen:
                                    children[parent].append(position)
                                else:
                                    boundary_children[parent] += 1
                for position, original_index in chosen.items():
                    span = spans[position]
                    service = processes[span["processID"]]["serviceName"]
                    if service not in meta["services"]:
                        raise ValueError("Unknown service")
                    refs, tags = refs_of(span), tags_of(span)
                    identity = (span["traceID"], span["spanID"])
                    counts["selected_span_occurrences"] += 1
                    counts["zero_duration_occurrences"] += int(span["duration"] == 0)
                    counts["references_field_present"] += int("references" in span)
                    counts["selected_spans_with_any_reference"] += int(bool(refs))
                    counts["selected_spans_with_error_or_status_tag"] += int(bool(set(tags) & OUTCOME_KEYS))
                    counts["selected_spans_with_explicit_error_tag"] += int("error" in tags)
                    counts["selected_spans_with_multiple_child_of_parents"] += int(
                        sum(r["refType"] == "CHILD_OF" for r in refs) > 1)
                    counts["duplicate_identity_inside_trace_occurrences"] += int(len(index_map[identity]) > 1)
                    tag_keys.update(tags.keys())
                    for kind in tags.get("span.kind", []):
                        kinds[str(kind)] += 1
                    for key in OUTCOME_KEYS & set(tags):
                        if key in ("error.type", "error.message"):
                            continue
                        for value in tags[key]:
                            if type(value) in (bool, int) or (isinstance(value, str) and len(value) <= 16):
                                status_values[key + "=" + str(value)] += 1
                    for ref in refs:
                        ref_types[ref["refType"]] += 1
                        if ref["refType"] == "CHILD_OF":
                            candidates = index_map.get((ref["traceID"], ref["spanID"]), [])
                            counts["child_of_edges"] += 1
                            counts["child_of_parent_present_in_trace"] += int(bool(candidates))
                            counts["child_of_parent_unique_in_trace"] += int(len(candidates) == 1)
                            counts["child_of_parent_also_selected"] += int(len(candidates) == 1 and candidates[0] in chosen)
                            counts["self_parent_edges"] += int((ref["traceID"], ref["spanID"]) == identity)
                    graph_signature = (service, span["startTime"], span["duration"],
                                       tuple(sorted((r["refType"], r["traceID"], r["spanID"]) for r in refs)))
                    outcome_signature = json.dumps({k: tags[k] for k in sorted(set(tags) & OUTCOME_KEYS)},
                                                   sort_keys=True)
                    signature = (graph_signature, outcome_signature)
                    if identity in seen_identity:
                        counts["repeated_selected_identity_occurrences"] += 1
                        old = seen_identity[identity]
                        if old != signature:
                            conflict_ids.add(identity)
                            counts["repeated_identity_graph_timing_conflicts"] += int(old[0] != graph_signature)
                            counts["repeated_identity_outcome_conflicts"] += int(old[1] != outcome_signature)
                    else:
                        seen_identity[identity] = signature
                    cell = (original_index, service)
                    cell_counts[cell] += 1
                    cell_identity = (cell, identity)
                    if cell_identity not in seen_cells:
                        unique_cell_counts[cell] += 1
                        seen_cells.add(cell_identity)
                    child_positions = sorted(set(children[position]))
                    counts["parents_with_children_outside_selected_windows"] += int(boundary_children[position] > 0)
                    if not child_positions:
                        counts["selected_spans_without_observed_selected_children"] += 1
                        continue
                    counts["selected_spans_with_observed_selected_children"] += 1
                    counts["parents_with_ambiguous_child_identity"] += int(any(
                        len(index_map[(spans[p]["traceID"], spans[p]["spanID"])]) != 1 for p in child_positions))
                    intervals = []
                    start, duration = span["startTime"], span["duration"]
                    for child_position in child_positions:
                        child = spans[child_position]
                        child_service = processes[child["processID"]]["serviceName"]
                        counts["selected_direct_child_edges"] += 1
                        counts["selected_cross_service_child_edges"] += int(child_service != service)
                        left, right = child["startTime"], child["startTime"] + child["duration"]
                        counts["child_interval_exceeds_parent"] += int(left < start or right > start + duration)
                        intervals.append((left, right))
                    covered, summed = union_covered(start, duration, intervals)
                    counts["parents_with_overlapping_child_intervals"] += int(summed > covered)
                    counts["naive_unclipped_subtraction_negative"] += int(
                        sum(b - a for a, b in intervals) > duration)
                    if (not boundary_children[position] and len(index_map[identity]) == 1
                            and position not in child_positions and all(
                                len(index_map[(spans[p]["traceID"], spans[p]["spanID"])]) == 1
                                for p in child_positions)):
                        residual_sum += duration - covered
                        residual_count += 1
        name = str(path.relative_to(root))
        hashes[name] = digest.hexdigest()
        if hashes[name] != meta["input_sha256"][name]:
            raise ValueError("Raw source hash changed: " + name)
        runs.append({"run_id": run["run_id"], "source_bytes": path.stat().st_size,
                     "counts": dict(counts - before)})
        print("TRACE_PREFLIGHT_RUN", system, run["run_id"], flush=True)
    total_cells = len(selected) * len(meta["services"])

    def histogram(cells):
        result = {"0": total_cells - len(cells), "1": 0, "2-9": 0, "10-19": 0, "20-99": 0, "100+": 0}
        for n in cells.values():
            key = "1" if n == 1 else "2-9" if n < 10 else "10-19" if n < 20 else "20-99" if n < 100 else "100+"
            result[key] += 1
        assert sum(result.values()) == total_cells
        return result

    return {"system": system, "seconds": time.perf_counter() - started,
            "metadata_sha256": sha(meta_path), "split_sha256": sha(split_path),
            "raw_source_hashes": hashes, "selected_windows": len(selected),
            "candidate_services": len(meta["services"]), "test_windows_accumulated": 0,
            "counts": dict(counts), "reference_types": dict(ref_types),
            "span_kind_values": dict(kinds), "outcome_tag_values": dict(status_values),
            "span_tag_key_occurrences": dict(tag_keys),
            "distinct_selected_span_identities": len(seen_identity),
            "distinct_conflicting_selected_identities": len(conflict_ids),
            "window_service_retained_span_count_histogram": histogram(cell_counts),
            "window_service_distinct_span_identity_histogram": histogram(unique_cell_counts),
            "observed_residual_candidate_parent_occurrences": residual_count,
            "observed_residual_candidate_mean_microseconds": residual_sum / residual_count if residual_count else None,
            "runs": runs}


def self_check():
    assert union_covered(0, 10, [(1, 6), (4, 8)]) == (7, 9)
    assert union_covered(0, 10, [(-1, 3), (9, 15)]) == (4, 4)
    assert union_covered(0, 0, [(0, 5)]) == (0, 0)
    assert union_covered(0, 10, []) == (0, 0)
    assert tags_of({"tags": [{"key": "error", "value": False}]}) == {"error": [False]}
    assert refs_of({}) == [] and refs_of({"references": None}) == []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check()
    if args.self_check:
        print("TRACE_PREFLIGHT_SELF_CHECK_OK")
        return
    target = HERE / "trace_preflight.json"
    if target.exists():
        raise FileExistsError("Preserve existing audit: " + str(target))
    report = {"scope": "Read-only selected native TRAIN/validation window statistics; no model/features/split output.",
              "systems": [audit("SN"), audit("TT")], "source_sha256": sha(Path(__file__)),
              "limitations": [
                  "Parent presence within one trace object is not proof of complete instrumentation.",
                  "Unselected/test-window children are excluded from timing calculations; boundary parents are marked.",
                  "Observed residual uses clipped direct-child interval union, not CPU time or proven causal depropagation.",
                  "Missing error/status tags are unknown, not observed successes.",
                  "Repeated span IDs and conflicting observations are reported, not silently repaired.",
                  "Span-count bins describe support, not a certified reliability threshold for p95/p99.",
              ]}
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("TRACE_PREFLIGHT_READY", json.dumps({r["system"]: r["counts"] for r in report["systems"]}), flush=True)


if __name__ == "__main__":
    main()
