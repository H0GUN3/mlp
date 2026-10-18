"""Trace only three selected TT development events back to one source recording."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.tt_trace_origin_20261014 import labels
from research.relationship_diagnosis_20261014 import errors
from research.method_mlp_20261013 import features

LOG_TIME = re.compile(r"\d{4}-(?:[A-Za-z]{3}|\d{2})-\d{2} \d{2}:\d{2}:\d{2}\.\d+")


def log_second(line):
    match = LOG_TIME.search(line)
    if match is None:
        return None
    for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return int(datetime.strptime(match.group(), fmt).replace(tzinfo=timezone.utc).timestamp() + 28800)
        except ValueError:
            continue
    raise ValueError("Invalid timestamp")


def second_lookup(windows):
    lookup = {}
    for row, window in enumerate(windows):
        for second in range(window["start"], window["end_exclusive"]):
            errors.require(second not in lookup, "Overlapping selected windows")
            lookup[second] = (row, second - window["start"])
    return lookup


def collect_traces(traces, windows, services):
    lookup = second_lookup(windows)
    node_map = {name: index for index, name in enumerate(services)}
    sums = np.zeros((len(windows), len(services), 10))
    counts = np.zeros(sums.shape, dtype=np.int64)
    unique = [set() for _ in windows]
    root_unique = [set() for _ in windows]
    endpoint_mentions = {event: [] for event in labels.EVENTS}
    mention_counts = Counter()
    for trace in traces:
        for span in trace["spans"]:
            stamp = span["startTime"]
            errors.require(type(stamp) is int, "Noninteger span routing timestamp")
            chosen = lookup.get(stamp // 1000000 + 28800)
            if chosen is None:
                continue
            row, second = chosen
            duration = span["duration"]
            service = trace["processes"][span["processID"]]["serviceName"]
            errors.require(type(duration) is int and duration >= 0 and service in node_map,
                           "Invalid selected span")
            errors.require(span["traceID"] == trace["traceID"], "Cross-trace identity")
            node = node_map[service]
            sums[row, node, second] += duration / 1000000.
            counts[row, node, second] += 1
            identity = (span["traceID"], span["spanID"])
            unique[row].add(identity)
            target = windows[row]["root"]
            if node == target:
                root_unique[row].add(identity)
            # Endpoint mentions are diagnostic leads, not inferred calls or successful requests.
            tags = {tag["key"]: tag.get("value") for tag in span.get("tags", [])
                    if tag.get("key") in ("http.url", "http.method", "http.status_code", "error")}
            operation = span.get("operationName", "")
            target_name = services[target]
            stem = target_name[3:-8] if target_name.startswith("ts-") and target_name.endswith("-service") else target_name
            text = (str(operation) + " " + str(tags.get("http.url", ""))).lower()
            if target_name in text or stem.replace("-", "") + "service" in text:
                event = windows[row]["event_id"]
                mention_counts[event] += 1
                if len(endpoint_mentions[event]) < 5:
                    endpoint_mentions[event].append({
                        "original_index": windows[row]["original_index"], "service": service,
                        "trace_id": identity[0], "span_id": identity[1],
                        "operation": operation, "tags": tags,
                    })
    latency = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    return counts, latency, unique, root_unique, endpoint_mentions, mention_counts


def collect_logs(logs, windows, services):
    lookup = second_lookup(windows)
    selected_counts = np.zeros((len(windows), len(services)), dtype=np.int64)
    examples = {event: [] for event in labels.EVENTS}
    unparsed = Counter()
    for node, service in enumerate(services):
        errors.require(service in logs and isinstance(logs[service], list), "Missing log service")
        for line in logs[service]:
            second = log_second(line)
            if second is None:
                unparsed[service] += 1
                continue
            chosen = lookup.get(second)
            if chosen is None:
                continue
            row, _ = chosen
            selected_counts[row, node] += 1
            event = windows[row]["event_id"]
            if node == windows[row]["root"] and len(examples[event]) < 5:
                examples[event].append({"original_index": windows[row]["original_index"],
                                        "second": second, "line": line[:700]})
    return selected_counts, examples, dict(unparsed)


def execute():
    metadata_path = HERE / "metadata.json"
    metadata_hash = errors.file_hash(metadata_path)
    metadata = json.loads(metadata_path.read_text())
    errors.require(metadata["status"] == "PASS" and metadata["selected_events"] == labels.EVENTS,
                   "Metadata gate not passed")
    inputs, manifest, bundle = labels.load_bundle(("indices", "labels", "event_ids", "values", "observed"))
    inputs.record(metadata_path, metadata_hash, "successful metadata gate snapshot", ())
    for path, binding in metadata["input_hashes"].items():
        errors.check_hash(path, binding["sha256"])
    windows = metadata["selected_windows"]
    rows = np.asarray([w["bundle_row"] for w in windows], dtype=np.int64)
    services = manifest["services"]
    errors.require(all(int(bundle["indices"][row]) == w["original_index"]
                       and int(bundle["labels"][row]) == w["root"]
                       and str(bundle["event_ids"][row]) == w["event_id"]
                       for row, w in zip(rows, windows)), "Selected rows changed")
    span_relative = "data/" + labels.RUN + "/spans.json"
    span_path = labels.RAW / span_relative
    inputs.record(span_path, manifest["raw_input_hashes"][span_relative],
                  "existing selected source span pin; only allowed timestamps analyzed", ())
    digest = hashlib.sha256()
    with span_path.open("rb") as stream:
        outputs = collect_traces(features.json_array(stream, digest), windows, services)
    errors.require(digest.hexdigest() == manifest["raw_input_hashes"][span_relative], "Source stream hash mismatch")
    counts, latency, unique, root_unique, mentions, mention_counts = outputs
    errors.require(np.array_equal(counts, bundle["values"][rows, :, :, 8]), "Span count changed during preprocessing")
    errors.require(np.array_equal(latency, bundle["values"][rows, :, :, 7]), "Latency changed during preprocessing")
    errors.require(np.array_equal(counts > 0, bundle["observed"][rows, :, :, 7]), "Observation mask mismatch")

    root_absent = any(not counts[i, w["root"]].any() for i, w in enumerate(windows))
    log_counts = np.zeros(counts.shape[:2], dtype=np.int64)
    log_examples, unparsed = {}, {}
    if root_absent:
        log_path = labels.RAW / "data" / labels.RUN / "logs.json"
        log_hash = errors.file_hash(log_path)
        logs = inputs.json(log_path, log_hash, "local start/end snapshot; not historical distribution pin")
        log_counts, log_examples, unparsed = collect_logs(logs, windows, services)
    cases = []
    for event in labels.EVENTS:
        selected = [i for i, w in enumerate(windows) if w["event_id"] == event]
        root = windows[selected[0]]["root"]
        interior = [i for i in selected if windows[i]["fully_inside_fault"]]
        root_span_windows = [i for i in selected if counts[i, root].any()]
        root_log_windows = [i for i in selected if log_counts[i, root] > 0]
        root_log_without_span = [i for i in root_log_windows if not counts[i, root].any()]
        service_counts = counts[selected].sum(axis=(0, 2))
        cases.append({
            "event_id": event, "service": services[root], "fault_type": manifest["faults"][event]["fault_type"],
            "windows": len(selected), "fully_inside_windows": len(interior),
            "root_span_windows": len(root_span_windows),
            "fully_inside_root_span_windows": sum(counts[i, root].any().item() for i in interior),
            "root_span_occurrences": int(counts[selected, root].sum()),
            "root_unique_spans": len(set().union(*(root_unique[i] for i in selected))),
            "any_service_span_windows": sum(counts[i].any().item() for i in selected),
            "total_span_occurrences": int(counts[selected].sum()),
            "total_unique_spans": len(set().union(*(unique[i] for i in selected))),
            "source_service_occurrences": {name: int(value) for name, value in zip(services, service_counts) if value},
            "root_log_lines": int(log_counts[selected, root].sum()),
            "root_log_windows": len(root_log_windows),
            "root_log_without_root_span_windows": len(root_log_without_span),
            "any_service_log_lines": int(log_counts[selected].sum()),
            "root_log_examples": log_examples.get(event, []),
            "root_endpoint_mention_occurrences": int(mention_counts[event]),
            "root_endpoint_mention_examples": mentions[event],
            "window_indices": [windows[i]["original_index"] for i in selected],
        })
    inputs.recheck()
    return {
        "status": "PASS", "recording": labels.RUN, "selected_windows": len(windows),
        "metadata_gate_hash": metadata_hash, "cases": cases,
        "checks": {"exact_raw_count": True, "exact_raw_latency": True, "exact_raw_observation_mask": True},
        "raw_channel_cells_checked": int(counts.size), "unparseable_log_lines_by_service": unparsed,
        "input_hashes": inputs.provenance,
        "source_hashes": {name: errors.file_hash(HERE / name)
                          for name in ("labels.py", "trace.py", "test_labels.py", "test_trace.py", "PROTOCOL.md")},
        "limits": [
            "Three selected development events in one recording; no TT-wide generalization.",
            "Published spans absent does not distinguish no call, failed export, missing instrumentation or sampling.",
            "Logs and endpoint mentions require semantic inspection; a text match is not causal proof.",
            "Metadata alignment is not independently verified physical injection or clock synchronization.",
            "Source JSON parsed for timestamp routing; nonselected telemetry not analyzed/exported.",
        ],
    }


if __name__ == "__main__":
    result = execute()
    with (HERE / "trace.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    for case in result["cases"]:
        print("TRACE_CASE", case["event_id"], "windows", case["windows"],
              "root_spans", case["root_span_occurrences"], "root_logs", case["root_log_lines"], flush=True)
    print("TRACE_ORIGIN_PASS", result["selected_windows"], flush=True)
