"""Read-only native Eadro profile; emit a bounded compressed JSON summary.

Reads only the two authorized extracted dataset roots. Never extracts archives,
normalizes telemetry, creates windows, selects splits, or invokes model code.
The caller applies the emitted summary to native_data_profile.json via apply_patch.
"""
import argparse
import base64
from collections import Counter
import codecs
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys

import numpy as np
import pandas as pd
import tarfile


BASE = Path("/home/gnho1236/r2/data/eadro_native")
ROOTS = {
    "SN": BASE / "SN_Dataset/SN Dataset",
    "TT": BASE / "TT_Dataset/TT Dataset",
}
METRICS = [
    "cpu_usage_system", "cpu_usage_total", "cpu_usage_user", "memory_usage",
    "memory_working_set", "rx_bytes", "tx_bytes",
]
SERVICES = {
    "SN": [
        "social-graph-service", "compose-post-service", "post-storage-service",
        "user-timeline-service", "url-shorten-service", "user-service",
        "media-service", "text-service", "unique-id-service",
        "user-mention-service", "home-timeline-service", "nginx-web-server",
    ],
    "TT": ["ts-{}-service".format(s) for s in (
        "assurance auth basic cancel config contacts food-map food inside-payment "
        "notification order-other order payment preserve price route-plan route "
        "seat security station ticketinfo train travel-plan travel travel2 user "
        "verification-code").split()],
}
SESSION_RE = re.compile(r"(?:SN|TT)\.(\d{4}-\d{2}-\d{2}T\d{6})D"
                        r"(\d{4}-\d{2}-\d{2}T\d{6})")
LOG_RE = re.compile(r"\d{4}-(?:[A-Za-z]{3}|\d{2})-\d{2} "
                    r"\d{2}:\d{2}:\d{2}\.\d+")


def utc_seconds(text, fmt):
    return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp()


def filename_range(name):
    match = SESSION_RE.fullmatch(name)
    if match is None:
        raise ValueError("Unexpected session name: " + name)
    return [utc_seconds(s, "%Y-%m-%dT%H%M%S") for s in match.groups()]


def safe_member(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe member: " + name)
    return str(path)


def bounds(values):
    finite = [float(v) for v in values if np.isfinite(v)]
    return [min(finite), max(finite)] if finite else None


def range_delta(actual, reference, shift=0):
    if actual is None:
        return None
    return [round(actual[i] + shift - reference[i], 6) for i in (0, 1)]


def schema_update(schema, obj):
    for key, value in obj.items():
        schema.setdefault(key, set()).add(type(value).__name__)


def json_array(stream, digest):
    """Stream top-level JSON objects with bounded memory and strict delimiters."""
    decoder = json.JSONDecoder()
    utf8 = codecs.getincrementaldecoder("utf-8")()
    buffer, eof = "", False

    def more():
        nonlocal buffer, eof
        chunk = stream.read(65536)
        digest.update(chunk)
        eof = not chunk
        buffer += utf8.decode(chunk, final=eof)
        if len(buffer) > 32 * 1024 * 1024:
            raise ValueError("Single JSON element exceeds bounded 32 MiB buffer")

    def trim():
        nonlocal buffer
        buffer = buffer.lstrip()
        while not buffer and not eof:
            more()
            buffer = buffer.lstrip()

    trim()
    if not buffer.startswith("["):
        raise ValueError("Expected top-level Jaeger trace array")
    buffer = buffer[1:]
    trim()
    first = True
    while not buffer.startswith("]"):
        if not first:
            if not buffer.startswith(","):
                raise ValueError("Missing JSON array separator")
            buffer = buffer[1:]
            trim()
        while True:
            try:
                obj, end = decoder.raw_decode(buffer)
                break
            except json.JSONDecodeError:
                if eof:
                    raise
                more()
        if not isinstance(obj, dict):
            raise ValueError("Expected trace object")
        buffer = buffer[end:]
        yield obj
        first = False
        trim()
    buffer = buffer[1:]
    while not eof:
        more()
    if buffer.strip():
        raise ValueError("Trailing JSON data")


def profile_spans(stream, schemas):
    digest = hashlib.sha256()
    counts = Counter()
    services = Counter()
    field_types = {"startTime": Counter(), "duration": Counter()}
    low, high, sample_count = float("inf"), -float("inf"), 0
    for trace in json_array(stream, digest):
        counts["traces"] += 1
        if counts["traces"] <= 64:
            schema_update(schemas["trace"], trace)
        processes = trace["processes"]
        for process in processes.values():
            if counts["traces"] <= 64:
                schema_update(schemas["process"], process)
        for span in trace["spans"]:
            counts["spans"] += 1
            if sample_count < 64:
                schema_update(schemas["span"], span)
                sample_count += 1
            for field in field_types:
                field_types[field][type(span.get(field)).__name__] += 1
            start, duration = span.get("startTime"), span.get("duration")
            if type(start) in (int, float) and np.isfinite(start):
                low, high = min(low, start / 1e6), max(high, start / 1e6)
            else:
                counts["invalid_startTime"] += 1
            if type(duration) not in (int, float) or not np.isfinite(duration):
                counts["invalid_duration"] += 1
            elif duration < 0:
                counts["negative_duration"] += 1
            process = processes.get(span.get("processID"))
            if process is None:
                counts["unresolved_processID"] += 1
            else:
                services[process["serviceName"]] += 1
    result: dict = dict(counts)
    result.update({
        "services": sorted(services), "span_field_types": field_types,
        "raw_start_seconds": [low, high] if np.isfinite(low) else None,
        "schema_span_sample_count": sample_count,
    })
    return result, digest.hexdigest()


def profile_logs(body):
    obj = json.loads(body)
    if not isinstance(obj, dict):
        raise ValueError("Expected service-to-log-lines JSON object")
    counts, service_counts, line_types = Counter(), {}, Counter()
    low, high = float("inf"), -float("inf")
    for service, lines in obj.items():
        if not isinstance(lines, list):
            raise ValueError("Expected per-service log list")
        service_counts[service] = len(lines)
        for line in lines:
            counts["lines"] += 1
            line_types[type(line).__name__] += 1
            match = LOG_RE.search(line) if isinstance(line, str) else None
            if match is None:
                counts["source_timestamp_regex_unmatched"] += 1
                continue
            stamp = None
            for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"):
                try:
                    stamp = utc_seconds(match.group(), fmt)
                    break
                except ValueError:
                    pass
            if stamp is None:
                counts["unparseable_matched_timestamp"] += 1
            else:
                counts["parsed_timestamps"] += 1
                low, high = min(low, stamp), max(high, stamp)
    return {
        "top_type": type(obj).__name__, "value_type": "list",
        "line_types": line_types, "counts": counts, "service_counts": service_counts,
        "raw_text_wallclock_as_UTC": [low, high] if np.isfinite(low) else None,
    }


def profile_metric(body, service):
    frame = pd.read_csv(io.BytesIO(body))
    missing = sorted(set(["timestamp"] + METRICS) - set(frame.columns))
    result = {
        "service": service, "rows": len(frame), "columns": list(frame.columns),
        "dtypes": {k: str(v) for k, v in frame.dtypes.items()},
        "missing_columns": missing,
        "extra_columns": sorted(set(frame.columns) - set(["timestamp"] + METRICS)),
    }
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    result["nan_cells"] = {k: int(v) for k, v in frame.isna().sum().items() if v}
    result["nonnumeric_cells"] = {
        k: int(v) for k, v in (numeric.isna() & ~frame.isna()).sum().items() if v
    }
    result["inf_cells"] = int(np.isinf(np.asarray(numeric)).sum())
    result["constant_metrics"] = [
        k for k in METRICS if k in frame and frame[k].nunique(dropna=True) <= 1
    ]
    if "timestamp" in numeric:
        times = np.asarray(numeric["timestamp"])
        finite = times[np.isfinite(times)]
        diffs = np.diff(finite)
        result.update({
            "raw_timestamp_seconds": bounds(finite),
            "nan_timestamp": int(np.isnan(times).sum()),
            "nonintegral_timestamp": int((finite != np.floor(finite)).sum()),
            "duplicate_timestamp": int(pd.Series(finite).duplicated().sum()),
            "backward_steps": int((diffs < 0).sum()),
            "non_1s_steps": int((diffs != 1).sum()),
            "max_step_seconds": float(diffs.max()) if len(diffs) else None,
        })
    return result


def summarize_metrics(files):
    if not files:
        return None
    ranges = [f["raw_timestamp_seconds"] for f in files
              if f.get("raw_timestamp_seconds") is not None]
    summary = {
        "service_count": len(files), "services": sorted(f["service"] for f in files),
        "row_count_range": bounds([f["rows"] for f in files]),
        "raw_timestamp_seconds": bounds([v for r in ranges for v in r]),
        "all_service_time_ranges_equal": len(set(tuple(r) for r in ranges)) == 1,
        "column_variants": sorted(set(tuple(f["columns"]) for f in files)),
        "dtype_variants": [dict(pairs) for pairs in sorted(set(
            tuple(sorted(f["dtypes"].items())) for f in files))],
        "nan_cells": dict(sum((Counter(f["nan_cells"]) for f in files), Counter())),
        "nonnumeric_cells": dict(sum((Counter(f["nonnumeric_cells"])
                                    for f in files), Counter())),
        "constant_metric_service_counts": dict(Counter(
            k for f in files for k in f["constant_metrics"])),
    }
    for key in ("inf_cells", "nan_timestamp", "nonintegral_timestamp",
                "duplicate_timestamp", "backward_steps", "non_1s_steps"):
        summary[key] = sum(f.get(key, 0) for f in files)
    bad = [f for f in files if f["missing_columns"] or f["extra_columns"]
           or f["nan_cells"] or f["nonnumeric_cells"] or f["inf_cells"]
           or f.get("non_1s_steps", 0)]
    summary["quality_mismatch_file_count"] = len(bad)
    summary["quality_mismatch_examples"] = bad[:3]
    return summary


def finish_session(row, metric_files, expected):
    row["metrics"] = summarize_metrics(metric_files)
    row["modalities_present"] = {
        "metrics": bool(metric_files), "logs": "logs" in row, "spans": "spans" in row,
    }
    row["missing_metric_services"] = sorted(set(expected) - {
        f["service"] for f in metric_files})
    row["missing_log_service_keys"] = sorted(
        set(expected) - set(row.get("logs", {}).get("service_counts", {})))
    row["missing_span_services"] = sorted(
        set(expected) - set(row.get("spans", {}).get("services", [])))
    row["unknown_services"] = sorted(
        (set(f["service"] for f in metric_files)
         | set(row.get("logs", {}).get("service_counts", {}))
         | set(row.get("spans", {}).get("services", []))) - set(expected))
    ref = filename_range(row["session"])
    metrics = row["metrics"]
    row["alignment_seconds_against_filename"] = {
        "filename_wallclock_as_UTC": ref,
        "metric_raw": range_delta(metrics["raw_timestamp_seconds"], ref)
        if metrics else None,
        "metric_source_plus16h": range_delta(
            metrics["raw_timestamp_seconds"], ref, 16 * 3600) if metrics else None,
        "span_source_plus8h": range_delta(
            row.get("spans", {}).get("raw_start_seconds"), ref, 8 * 3600),
        "log_source_no_shift": range_delta(
            row.get("logs", {}).get("raw_text_wallclock_as_UTC"), ref),
        "log_plus8h_observation_only": range_delta(
            row.get("logs", {}).get("raw_text_wallclock_as_UTC"), ref, 8 * 3600),
    }
    if row.get("record") is not None:
        record = row["record"]
        raw = [record["start"], record["end"]]
        row["alignment_seconds_against_filename"].update({
            "record_raw": range_delta(raw, ref),
            "record_source_int_then_plus16h": range_delta(
                [int(v) for v in raw], ref, 16 * 3600),
        })


def fault_service(name, dataset):
    if dataset == "TT":
        return name.split("_")[1]
    if name == "socialnetwork-nginx-thrift-1":
        return "nginx-web-server"
    if name.startswith("socialnetwork-") and name.endswith("-1"):
        return name[len("socialnetwork-"):-2]
    raise ValueError("Unrecognized injected service: " + name)


def profile_dataset(dataset, root):
    schemas = {"trace": {}, "process": {}, "span": {}}
    records, record_objects, sessions, loose_hashes = [], {}, {}, {}
    conditions, roots, kinds, durations = Counter(), Counter(), Counter(), Counter()
    data_records = sorted((root / "data").glob("*.json"))
    data_folders = sorted(p for p in (root / "data").iterdir() if p.is_dir())
    for path in data_records + sorted((root / "no fault").glob("*.json")):
        body = path.read_bytes()
        obj = json.loads(body)
        session = path.name[:-5].replace(".fault-", ".")
        record_objects[session] = obj
        record = {
            "source": str(path.relative_to(root)), "session": session,
            "source_types": {k: type(v).__name__ for k, v in obj.items()},
            "fault_count": len(obj["faults"]),
            "start": obj["start"], "end": obj["end"],
            "recording_duration_seconds": obj["end"] - obj["start"],
            "fault_fields_types": {},
        }
        fault_types = {}
        for fault in obj["faults"]:
            schema_update(fault_types, fault)
            service = fault_service(fault["name"], dataset)
            conditions[(service, fault["fault"])] += 1
            roots[service] += 1
            kinds[fault["fault"]] += 1
            durations[str(fault["duration"])] += 1
        record["fault_fields_types"] = {k: sorted(v) for k, v in fault_types.items()}
        records.append(record)
        loose_hashes[str(path.relative_to(root))] = hashlib.sha256(body).hexdigest()
    record_by_session = {r["session"]: r for r in records}

    for folder in data_folders:
        name = folder.name
        row = {
            "session": name, "collection": "data", "source_folder": str(
                folder.relative_to(root)), "record": record_by_session.get(name),
            "source_paths": {
                "logs": str((folder / "logs.json").relative_to(root)),
                "spans": str((folder / "spans.json").relative_to(root)),
                "metrics": str((folder / "metrics").relative_to(root)) + "/{service}.csv",
            },
        }
        metric_files = []
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            relative = str(path.relative_to(root))
            if path.name == "spans.json":
                with path.open("rb") as stream:
                    row["spans"], loose_hashes[relative] = profile_spans(stream, schemas)
            else:
                body = path.read_bytes()
                loose_hashes[relative] = hashlib.sha256(body).hexdigest()
                if path.name == "logs.json":
                    row["logs"] = profile_logs(body)
                elif path.suffix == ".csv" and path.parent.name == "metrics":
                    metric_files.append(profile_metric(body, path.stem))
        finish_session(row, metric_files, SERVICES[dataset])
        sessions[name] = row
        print("PROFILE_SESSION {} {} faults={}".format(
            dataset, name, row["record"]["fault_count"] if row["record"] else "unknown"),
              flush=True)

    archives = []
    archive_paths = sorted(p for p in root.rglob("*") if p.is_file()
                           and p.name.endswith((".tgz", ".txz", ".tar.xz")))
    for path in archive_paths:
        catalog = {
            "source": str(path.relative_to(root)), "compressed_bytes": path.stat().st_size,
            "members": 0, "regular_files": 0, "uncompressed_bytes": 0,
            "content_identical_loose_files": 0, "different_loose_files": [],
            "nonduplicate_member_count": 0, "sessions": [],
            "fault_metadata": [], "member_kinds": Counter(),
        }
        archive_sessions, metrics_by_session = {}, {}
        with tarfile.open(str(path), "r|*") as archive:
            for member in archive:
                catalog["members"] += 1
                name = safe_member(member.name)
                if not member.isfile():
                    if not member.isdir():
                        raise ValueError("Unsupported archive member: " + name)
                    continue
                catalog["regular_files"] += 1
                catalog["uncompressed_bytes"] += member.size
                parts = PurePosixPath(name).parts
                session = next((s for s in parts if SESSION_RE.fullmatch(s)), None)
                if session:
                    catalog["sessions"].append(session)
                source = str(path.relative_to(root)) + "!" + name
                stream = archive.extractfile(member)  # Read member, never extract to disk.
                if stream is None:
                    raise ValueError("Regular member has no readable stream: " + name)
                if path.parent.name == "no fault" and session:
                    row = archive_sessions.setdefault(session, {
                        "session": session, "collection": "no fault",
                        "source_folder": str(path.relative_to(root)) + "!" + session,
                        "record": record_by_session.get(session), "source_paths": {},
                    })
                    if parts[-1] == "spans.json":
                        row["spans"], digest = profile_spans(stream, schemas)
                        row["source_paths"]["spans"] = source
                    else:
                        body = stream.read()
                        digest = hashlib.sha256(body).hexdigest()
                        if parts[-1] == "logs.json":
                            row["logs"] = profile_logs(body)
                            row["source_paths"]["logs"] = source
                        elif parts[-1].endswith(".csv") and parts[-2] == "metrics":
                            metrics_by_session.setdefault(session, []).append(
                                profile_metric(body, PurePosixPath(name).stem))
                            row["source_paths"]["metrics"] = source.rsplit("/", 1)[0] + "/{service}.csv"
                else:
                    sha = hashlib.sha256()
                    body = bytearray() if ".fault-" in name and name.endswith(".json") else None
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        sha.update(chunk)
                        if body is not None:
                            body.extend(chunk)
                    digest = sha.hexdigest()
                    if body is not None:
                        obj = json.loads(body)
                        catalog["fault_metadata"].append({
                            "member": name, "fault_count": len(obj["faults"]),
                            "start": obj["start"], "end": obj["end"],
                        })
                if name in loose_hashes:
                    if loose_hashes[name] == digest:
                        catalog["content_identical_loose_files"] += 1
                    else:
                        catalog["different_loose_files"].append(name)
                else:
                    catalog["nonduplicate_member_count"] += 1
                kind = ("fault_metadata" if ".fault-" in name else
                        "metric_csv" if name.endswith(".csv") else
                        "logs" if name.endswith("/logs.json") else
                        "spans" if name.endswith("/spans.json") else "other")
                catalog["member_kinds"][kind] += 1
        catalog["sessions"] = sorted(set(catalog["sessions"]))
        catalog["adds_sessions_not_in_data"] = sorted(
            set(catalog["sessions"]) - {p.name for p in data_folders})
        for name, row in archive_sessions.items():
            if name in sessions:
                raise ValueError("Duplicate no-fault session requires explicit resolution")
            finish_session(row, metrics_by_session.get(name, []), SERVICES[dataset])
            sessions[name] = row
        archives.append(catalog)
        print("PROFILE_ARCHIVE {} {} identical={} additional_sessions={}".format(
            dataset, path.name, catalog["content_identical_loose_files"],
            len(catalog["adds_sessions_not_in_data"])), flush=True)

    correspondence = []
    for index, path in enumerate(data_records):
        session = path.name[:-5].replace(".fault-", ".")
        correspondence.append({
            "source_parser_index": index, "record_json": str(path.relative_to(root)),
            "matching_data_folder": "data/" + session,
            "folder_exists": session in sessions,
            "independent_sorted_folder_index_agrees": (
                index < len(data_folders) and data_folders[index].name == session),
        })
    return {
        "root": str(root), "expected_services_in_source_order": SERVICES[dataset],
        "data_record_count": len(data_records), "data_folder_count": len(data_folders),
        "annotated_fault_events": sum(r["fault_count"] for r in records),
        "unique_fault_roots": len(roots), "root_event_counts": roots,
        "fault_type_event_counts": kinds, "fault_duration_seconds_counts": durations,
        "unique_root_fault_conditions": len(conditions),
        "condition_event_counts": [
            {"service": s, "fault_type": f, "events": n}
            for (s, f), n in sorted(conditions.items())],
        "condition_repeat_count_distribution": dict(Counter(conditions.values())),
        "record_count_including_no_fault_metadata": len(records),
        "actual_distinct_recording_sessions": len(sessions),
        "no_fault_archive_sessions": sum(r["collection"] == "no fault" for r in sessions.values()),
        "sessions_without_fault_metadata": sorted(
            n for n, r in sessions.items() if r["record"] is None),
        "records_without_recording_session": sorted(set(record_objects) - set(sessions)),
        "record_to_folder_correspondence": correspondence, "archives": archives,
        "schemas": {kind: {k: sorted(v) for k, v in fields.items()}
                    for kind, fields in schemas.items()},
        "sessions": [sessions[n] for n in sorted(sessions)],
    }


def self_check():
    for body, count in ((b"[]", 0), (b'[{"a":1},{"b":[2]}]', 2)):
        digest = hashlib.sha256()
        assert len(list(json_array(io.BytesIO(body), digest))) == count
        assert digest.hexdigest() == hashlib.sha256(body).hexdigest()
    for body in (b'[{"a":1},]', b'[{"a":1} {"b":2}]', b"[]junk"):
        try:
            list(json_array(io.BytesIO(body), hashlib.sha256()))
        except (ValueError, json.JSONDecodeError):
            pass
        else:
            raise AssertionError("Invalid JSON accepted")
    assert filename_range("SN.2022-04-17T181245D2022-04-17T183616")[1] > 0
    assert fault_service("dockercomposemanifests_ts-food-service_1", "TT") == "ts-food-service"
    log = profile_logs(b'{"s":["2022-Apr-17 10:12:50.490796","untimed"]}')
    assert log["counts"]["parsed_timestamps"] == 1
    assert log["counts"]["source_timestamp_regex_unmatched"] == 1
    assert range_delta([0, 1], [10, 11], 10) == [0, 0]
    print("PROFILE_SELF_CHECK_PASS", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check-only", action="store_true")
    args = parser.parse_args()
    self_check()
    if args.self_check_only:
        return
    assert sys.version_info[:2] == (3, 8), "Use parent-managed .venv-eadro"
    assert np.__version__ == "1.21.5" and pd.__version__ == "1.4.2"
    result = {
        "scope": "Native Eadro profile only; no RCAEval data access",
        "environment": {
            "python": sys.version.split()[0],
            **{name: importlib.metadata.version(name)
               for name in ("numpy", "pandas", "tick", "torch", "dgl")},
        },
        "policy": {
            "raw_data_read_roots": [str(p) for p in ROOTS.values()],
            "archive_extraction": False, "data_mutation": False,
            "model_preprocessing_training_split_selection": False,
            "metrics": "All CSV rows and cells scanned",
            "logs": "All lines counted and source regex timestamps checked; no log text retained",
            "spans": "Streaming full time/service counts; schema first 64 traces/spans per session",
            "archive_duplicates": "Every regular member SHA256 compared with corresponding loose file",
            "timestamp_reference": "Filename and text wallclocks interpreted as UTC coordinates, not timezone assertions",
        },
        "datasets": {name: profile_dataset(name, root) for name, root in ROOTS.items()},
    }
    payload = json.dumps(result, sort_keys=True, allow_nan=False).encode()
    assert len(payload) <= 300000, "Summary exceeded bounded JSON contract"
    print("PROFILE_PAYLOAD " + base64.b64encode(gzip.compress(payload)).decode(), flush=True)
    print("PROFILE_COMPLETE bytes={} SN_faults={} TT_faults={}".format(
        len(payload), result["datasets"]["SN"]["annotated_fault_events"],
        result["datasets"]["TT"]["annotated_fault_events"]), flush=True)


if __name__ == "__main__":
    main()
