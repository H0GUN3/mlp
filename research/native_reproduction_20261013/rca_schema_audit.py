"""Guarded RCA input feasibility audit; no encoders, fitting or model imports."""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
DATA = BASE / "data/rcaeval"
META = BASE / "research/mlp_prerequisites"
SPLIT_SHA = "1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5"
FAMILIES = ("cpu", "mem", "diskio", "socket", "workload", "error",
            "latency-50", "latency-90")
PROXIES = ("BlackHoleCluster", "PassthroughCluster",
           "InboundPassthroughClusterIpv4", "InboundPassthroughClusterIpv6")
FILES = ("metrics.parquet", "logs.parquet", "traces.parquet", "inject_time.txt")
IDENTIFIERS = {"logs.parquet": ("container_name",),
               "traces.parquet": ("serviceName",)}
TIME_FIELDS = {"metrics.parquet": ("time",), "logs.parquet": ("timestamp",),
               "traces.parquet": ("time", "startTimeMillis", "startTime")}


def digest(body):
    return hashlib.sha256(body).hexdigest()


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def identifier_key(value):
    return (value is not None, "" if value is None else value)


def ordered(values):
    return sorted(values, key=identifier_key)


class Guard:
    def __init__(self):
        self.ledger = {}
        self.rejected = Counter()
        self.rows = self.verify_split()

    def verify_split(self):
        body = (META / "split.json").read_bytes()
        if digest(body) != SPLIT_SHA:
            raise ValueError("Frozen split hash mismatch")
        if json.loads((META / "split.lock.json").read_text())["sha256"] != SPLIT_SHA:
            raise ValueError("Split lock mismatch")
        rows = json.loads(body)["cases"]
        assert len(rows) == len({r["case"] for r in rows}) == 180
        assert Counter(r["partition"] for r in rows) == {
            "train": 108, "validation": 36, "test": 36}
        groups = defaultdict(list)
        for row in rows:
            groups[(row["dataset"], row["root_cause_service"], row["fault"])].append(row)
        assert len(groups) == 60
        for group in groups.values():
            assert len({r["partition"] for r in group}) == 1
            assert {r["repetition"] for r in group} == {1, 2, 3}
        for system in ("RE2-OB", "RE2-TT"):
            assert Counter(r["partition"] for r in rows if r["dataset"] == system) == {
                "train": 54, "validation": 18, "test": 18}
        assert all(not r["previously_developed"] or r["partition"] == "train"
                   for r in rows)
        return {r["case"]: r for r in rows}

    def authorize(self, case, filename, mode, columns=None):
        rows = self.verify_split()
        row = rows.get(case)
        # No path resolution, stat, existence check or open precedes this decision.
        allowed = row is not None and row["partition"] != "test" and filename in FILES
        if allowed and row is not None and row["partition"] == "validation":
            allowed = (mode == "footer" and filename.endswith(".parquet")) or (
                mode == "columns" and bool(columns) and
                set(columns) <= set(IDENTIFIERS.get(filename, ())))
        elif allowed:
            allowed = mode in ("footer", "columns", "text")
        if not allowed:
            self.rejected[f"{'unknown' if row is None else row['partition']}:{mode}"] += 1
            raise PermissionError(f"Protected access rejected: {case}/{filename}/{mode}")
        assert row is not None
        return row

    @contextmanager
    def opened(self, case, filename, mode, columns=None):
        row = self.authorize(case, filename, mode, columns)
        path = DATA / case / filename
        if path.resolve().parent != (DATA / case).resolve() or (
                path.resolve().parent.parent != DATA.resolve()):
            raise PermissionError("Raw path escapes authorized case")
        entry = self.ledger.setdefault((case, filename), {
            "case": case, "partition": row["partition"], "file": filename,
            "opens": 0, "modes": Counter(), "columns": set()})
        entry["opens"] += 1
        entry["modes"][mode] += 1
        entry["columns"].update(columns or ())
        try:
            with path.open("rb") as stream:
                entry["bytes"] = path.stat().st_size
                yield stream
        except FileNotFoundError:
            entry["missing"] = True
            raise

    def footer(self, case, filename):
        with self.opened(case, filename, "footer") as stream:
            pf = pq.ParquetFile(stream)
            train = self.rows[case]["partition"] == "train"
            return footer_summary(pf, filename, train)

    def columns(self, case, filename, columns):
        with self.opened(case, filename, "columns", columns) as stream:
            pf = pq.ParquetFile(stream)
            missing = set(columns) - set(pf.schema_arrow.names)
            if missing:
                raise ValueError(f"{case}/{filename}: absent columns {sorted(missing)}")
            return pf.read(columns=list(columns))

    def injection(self, case):
        with self.opened(case, "inject_time.txt", "text") as stream:
            value = int(stream.read().decode().strip())
        assert value == self.rows[case]["inject_time"], "Injection disagrees with frozen split"
        return value

    def access_ledger(self):
        assert len(self.ledger) <= 144 * 3 + 108
        return [{**value, "modes": dict(value["modes"]),
                 "columns": sorted(value["columns"])}
                for _, value in sorted(self.ledger.items())]


def footer_summary(pf, filename, train):
    fields = {}
    for index, field in enumerate(pf.schema_arrow):
        info = {"type": str(field.type), "nullable": field.nullable}
        if field.metadata:
            info["field_metadata"] = {k.decode(): v.decode() for k, v in field.metadata.items()}
        if train or field.name in TIME_FIELDS[filename]:
            nulls, minima, maxima, unknown, no_minmax = 0, [], [], 0, 0
            represented_rows = 0
            for group in range(pf.metadata.num_row_groups):
                column = pf.metadata.row_group(group).column(index)
                represented_rows += column.num_values
                stat = column.statistics
                if stat is None or not stat.has_null_count:
                    unknown += column.num_values
                else:
                    nulls += stat.null_count
                if stat is not None and stat.has_min_max:
                    minima.append(stat.min)
                    maxima.append(stat.max)
                elif stat is None or not stat.has_null_count or stat.null_count != column.num_values:
                    no_minmax += column.num_values
            assert represented_rows == pf.metadata.num_rows
            assert nulls + unknown <= represented_rows
            info.update(null_count=nulls, null_unknown_rows=unknown,
                        min=min(minima) if minima else None,
                        max=max(maxima) if maxima else None,
                        minmax_unknown_rows=no_minmax)
            info["constant_nonnull"] = (
                info["min"] == info["max"] if minima and no_minmax == 0 else None)
            info["all_null"] = (nulls == pf.metadata.num_rows if unknown == 0 else None)
        fields[field.name] = info
    assert len(fields) == pf.metadata.num_columns
    return {"rows": pf.metadata.num_rows, "row_groups": pf.metadata.num_row_groups,
            "fields": fields, "statistics_scope": "all fields" if train else "time fields only"}


def self_test(guard):
    real_open = Path.open
    raw_attempts = []

    def trap(path, *args, **kwargs):
        if DATA in path.parents:
            raw_attempts.append(str(path))
            raise AssertionError("Rejected access reached disk")
        return real_open(path, *args, **kwargs)

    with patch.object(Path, "open", trap):
        for row in guard.rows.values():
            if row["partition"] != "test":
                continue
            for filename in FILES:
                try:
                    with guard.opened(row["case"], filename, "footer"):
                        raise AssertionError("Final access allowed")
                except PermissionError:
                    pass
        case = next(r["case"] for r in guard.rows.values() if r["partition"] == "validation")
        for filename, columns in (("metrics.parquet", ("time",)),
                                  ("logs.parquet", ("message",)),
                                  ("traces.parquet", ("duration",))):
            try:
                guard.columns(case, filename, columns)
                raise AssertionError("Validation telemetry allowed")
            except PermissionError:
                pass
    assert not raw_attempts and not guard.ledger
    return {"final_open_requests_rejected_before_disk": 144,
            "validation_value_requests_rejected_before_disk": 3}


def probe(guard):
    for system in ("RE2-OB", "RE2-TT"):
        row = next(r for r in guard.rows.values()
                   if r["dataset"] == system and r["partition"] == "train")
        for filename in FILES[:3]:
            info = guard.footer(row["case"], filename)
            print(encoded({"case": row["case"], "file": filename,
                           "rows": info["rows"],
                           "schema": {k: v["type"] for k, v in info["fields"].items()
                                      if filename != "metrics.parquet" or k == "time"},
                           "times": {k: info["fields"][k] for k in TIME_FIELDS[filename]
                                     if k in info["fields"]}}), flush=True)


def canonical_vocabularies():
    """Decode vocabulary metadata only, never the old feature vectors/scores."""
    result = {}
    system = None
    collecting = False
    lines = []
    with (META / "training_results.json").open() as stream:
        for line in stream:
            if line.strip() in ('"RE2-OB": {', '"RE2-TT": {'):
                system = json.loads(line.strip().split(":")[0])
            if system and line.strip() == '"vocabulary": [':
                collecting, lines = True, ["["]
                continue
            if collecting:
                if line.strip() == "],":
                    result[system] = json.loads("".join(lines) + "]")
                    collecting = False
                    if len(result) == 2:
                        break
                else:
                    lines.append(line)
    assert set(result) == {"RE2-OB", "RE2-TT"}
    assert all(names == sorted(set(names)) and not set(names) & set(PROXIES)
               for names in result.values())
    # features.json contains only train/validation; do not decode any case values.
    with (META / "features.json").open() as stream:
        prefix = "".join(next(stream) for _ in range(4))
    feature_metadata = json.loads(prefix.rstrip().rstrip(",") + "\n}")
    assert feature_metadata["split_sha256"] == SPLIT_SHA
    return result, feature_metadata


def metric_inventory(info):
    services = defaultdict(list)
    unrecognized = []
    for name in info["fields"]:
        if name == "time":
            continue
        matches = [family for family in FAMILIES if name.endswith("_" + family)]
        if len(matches) != 1:
            unrecognized.append(name)
            continue
        family = matches[0]
        services[name[:-len(family) - 1]].append(family)
    fields = [f for name, f in info["fields"].items() if name != "time"]
    return {
        "services": {s: sorted(fs) for s, fs in sorted(services.items())},
        "family_columns": {f: sum(f in fs for fs in services.values()) for f in FAMILIES},
        "absent_families_by_metric_service": {
            s: [f for f in FAMILIES if f not in fs] for s, fs in sorted(services.items())},
        "unrecognized_fields": unrecognized,
        "null_cells_footer": sum(f.get("null_count", 0) for f in fields),
        "null_unknown_rows": sum(f.get("null_unknown_rows", info["rows"]) for f in fields),
        "all_null_fields": [n for n, f in info["fields"].items() if f.get("all_null")],
        "constant_nonnull_fields": [
            n for n, f in info["fields"].items() if n != "time" and f.get("constant_nonnull")],
        "constant_unknown_fields": [
            n for n, f in info["fields"].items() if n != "time" and
            f.get("constant_nonnull") is None],
    }


def service_counts(table, field):
    counts = Counter(table[field].to_pylist())
    assert sum(counts.values()) == table.num_rows
    assert all(s is None or isinstance(s, str) for s in counts)
    return [{"service": s, "rows": counts[s]} for s in ordered(counts)]


def placement(timestamp, start, end, injection):
    if timestamp is None:
        return "missing_timestamp"
    if type(timestamp) is not int:
        return "invalid_timestamp"
    if not start <= timestamp <= end:
        return "outside_metric_range"
    return "nominal_normal" if timestamp < injection else "nominal_faulty"


def eligible_starts(start, end, injection):
    # Integer metric samples cover [min(time), max(time)+1); verified on TRAIN.
    return {t: "nominal_normal" if t + 10 <= injection else "nominal_faulty"
            for t in range(start, end - 8, 10)
            if t + 10 <= injection or t >= injection}


def log_rows(table):
    return zip(table["container_name"].to_pylist(), table["timestamp"].to_pylist(),
               table["message"].to_pylist())


def audit_logs(case, table, start, end, injection, stream):
    starts = eligible_starts(start, end, injection)
    groups = defaultdict(lambda: Counter(events=0, string_messages=0, null_messages=0))
    reasons, missing = Counter(), Counter()
    examples = defaultdict(list)
    normal = []
    source_digest = hashlib.sha256()
    for row_number, (service, timestamp, message) in enumerate(log_rows(table)):
        assert service is None or isinstance(service, str)
        assert message is None or isinstance(message, str)
        state = placement(timestamp, start, end, injection)
        reasons[state] += 1
        missing["null_service"] += service is None
        missing["null_message"] += message is None
        if state not in ("nominal_normal", "nominal_faulty"):
            if len(examples[state]) < 8:
                examples[state].append(row_number)
            continue
        if state == "nominal_normal":
            normal.append((service, timestamp, row_number, message))
        window = start + ((timestamp - start) // 10) * 10
        if window in starts:
            group = groups[(service, window)]
            group["events"] += 1
            group["string_messages"] += isinstance(message, str)
            group["null_messages"] += message is None
        else:
            missing["boundary_or_tail_window_events"] += 1
    normal.sort(key=lambda r: (identifier_key(r[0]), r[1], r[2]))
    row_digest = hashlib.sha256()
    for service, timestamp, row_number, message in normal:
        assert start <= timestamp <= end and timestamp < injection
        obj = {"case": case, "service": service, "timestamp": timestamp, "message": message}
        line = (encoded(obj) + "\n").encode("utf-8")
        # Round trip all exported rows: no string cleaning, null replacement or coercion.
        assert json.loads(line) == obj
        stream.write(line)
        source_digest.update(line)
        row_digest.update(f"{row_number}\n".encode())
    assert sum(reasons.values()) == table.num_rows
    assert len(normal) == reasons["nominal_normal"]
    descriptors = []
    for (service, window), counts in groups.items():
        period = starts[window]
        left, right = (start, min(injection, end + 1)) if period == "nominal_normal" else (
            max(injection, start), end + 1)
        descriptors.append({"case": case, "service": service, "start": window,
                            "end": window + 10, "period": period, **counts,
                            "position": (window - left) / max(right - left - 10, 1)})
    descriptors.sort(key=lambda d: (d["case"], identifier_key(d["service"]), d["start"]))
    return {
        "source_rows": table.num_rows, "placement_counts": dict(reasons),
        "missing_counts": dict(missing), "unplaced_source_row_examples": dict(examples),
        "exported_normal_rows": len(normal),
        "exported_source_order_sha256": row_digest.hexdigest(),
        "exported_original_objects_sha256": source_digest.hexdigest(),
        "eligible_windows": dict(Counter(starts.values())),
        "observed_raw_services": ordered(d["service"] for d in service_counts(table, "container_name")),
        "nonempty_window_service_groups": len(groups),
        "string_message_window_service_groups": sum(g["string_messages"] > 0 for g in groups.values()),
        "drain_usable_nonempty_groups": sum(
            service is not None and counts["string_messages"] > 0
            for (service, _), counts in groups.items()),
    }, descriptors


def select_profiles(descriptors):
    chosen = {}
    coverage = {}
    for period in ("nominal_normal", "nominal_faulty"):
        pool = [d for d in descriptors if d["period"] == period]
        coverage[period] = len(pool)
        if not pool:
            continue
        key = lambda d: (d["case"], identifier_key(d["service"]), d["start"])
        choices = [(name, min(pool, key=lambda d: (abs(d["position"] - target), key(d))))
                   for name, target in (("beginning", 0), ("middle", .5), ("end", 1))]
        choices += [("smallest_event_count", min(pool, key=lambda d: (d["events"], key(d)))),
                    ("largest_event_count", min(pool, key=lambda d: (-d["events"], key(d))))]
        for reason, descriptor in choices:
            identity = key(descriptor)
            chosen.setdefault(identity, {**descriptor, "selected_for": []})["selected_for"].append(reason)
    result = [chosen[k] for k in sorted(chosen)]
    assert len(result) <= 12
    return result, coverage


def fill_profiles(guard, selected):
    by_case = defaultdict(list)
    for descriptor in selected:
        by_case[descriptor["case"]].append(descriptor)
    samples = []
    for case, descriptors in sorted(by_case.items()):
        table = guard.columns(case, "logs.parquet", ("container_name", "timestamp", "message"))
        source = defaultdict(list)
        for index, (service, timestamp, message) in enumerate(log_rows(table)):
            for d in descriptors:
                if service == d["service"] and timestamp is not None and d["start"] <= timestamp < d["end"]:
                    source[(service, d["start"])].append((timestamp, index, message))
        for d in descriptors:
            events = sorted(source[(d["service"], d["start"])], key=lambda e: (e[0], e[1]))
            assert len(events) == d["events"] > 0
            sample = {k: v for k, v in d.items() if k not in ("events", "position")}
            sample["events"] = [{"timestamp": t, "message": m} for t, _, m in events]
            sample["source_rows"] = [i for _, i, _ in events]
            assert all(d["start"] <= e["timestamp"] < d["end"] for e in sample["events"])
            assert json.loads(encoded(sample)) == sample
            samples.append(sample)
    return sorted(samples, key=lambda d: (d["case"], identifier_key(d["service"]), d["start"]))


def time_evidence(table, metric_start, metric_end):
    scaled = pc.call_function("multiply", [table["startTimeMillis"], pa.scalar(1000)])
    delta = pc.call_function("subtract", [table["startTime"], scaled])
    lower = pc.call_function("greater_equal", [delta, pa.scalar(0)])
    upper = pc.call_function("less", [delta, pa.scalar(1000)])
    valid = pc.call_function("and", [lower, upper])
    minmax = pc.call_function("min_max", [table["startTime"]]).as_py()
    return {
        "rows": table.num_rows, "paired_null_rows": delta.null_count,
        "microseconds_agree_with_millisecond_floor_rows": pc.call_function(
            "sum", [pc.cast(valid, pa.int64())]).as_py() or 0,
        "microsecond_minus_millisecond_x1000": pc.call_function("min_max", [delta]).as_py(),
        "start_seconds_range_if_microseconds": {
            k: None if v is None else v / 1e6 for k, v in minmax.items()},
        "metric_seconds_range": [metric_start, metric_end],
        "duration_unit": "int64 with no physical unit in schema; microseconds assumption not certified by RCA provenance",
        "native_source_evidence": "native_data.py:290 divides Jaeger duration by 1e6; not a RCA unit certificate",
    }


def estimate_arrays(windows, counts):
    estimates = []
    for label, count in counts.items():
        estimates.append({
            "candidate_basis": label, "N": count, "W": windows,
            "metric_float32_bytes_W_N_10_8": windows * count * 10 * 8 * 4,
            "trace_float32_bytes_W_N_10_2": windows * count * 10 * 2 * 4,
            "log_float64_bytes_per_template_W_N_E": windows * count * 8,
            "presence_bool_bytes_W_N": windows * count,
            "dense_graph_float32_bytes_N_N": count * count * 4,
            "per_hawkes_dense_matrix_float64_bytes_per_E_squared": 8,
        })
    return {"estimates": estimates,
            "E": "unknown until TRAIN nominal-normal Drain profiling; no template/model fitting here",
            "memory_scope": "uncompressed payload, excludes missing masks, Python/solver overhead and graph choice"}


def write_json_new(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def artifact(path, rows=None):
    sha = hashlib.sha256()
    lines = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
            lines += chunk.count(b"\n")
    value = {"path": str(path.relative_to(BASE)), "sha256": sha.hexdigest(),
             "bytes": path.stat().st_size, "lines": lines}
    if rows is not None:
        value["rows"] = rows
    return value


def logic_tests():
    assert [placement(t, 100, 130, 115) for t in (None, 99, 100, 114, 115, 130, 131)] == [
        "missing_timestamp", "outside_metric_range", "nominal_normal", "nominal_normal",
        "nominal_faulty", "nominal_faulty", "outside_metric_range"]
    assert eligible_starts(100, 140, 115) == {
        100: "nominal_normal", 120: "nominal_faulty", 130: "nominal_faulty"}
    import io
    table = pa.table({"container_name": ["x", None, "x", "x", "x", "x"],
                      "timestamp": [114, 100, 115, 99, None, 140],
                      "message": ["  original\nλ", None, "", "outside", "unplaced", "tail"]})
    stream = io.BytesIO()
    info, descriptors = audit_logs("fixture", table, 100, 140, 115, stream)
    exported = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert exported == [
        {"case": "fixture", "service": None, "timestamp": 100, "message": None},
        {"case": "fixture", "service": "x", "timestamp": 114, "message": "  original\nλ"}]
    assert info["source_rows"] == sum(info["placement_counts"].values()) == 6
    assert info["exported_normal_rows"] == 2
    assert all(d["end"] - d["start"] == 10 for d in descriptors)
    assert not any(d["start"] == 110 for d in descriptors)
    sink = pa.BufferOutputStream()
    pq.write_table(pa.table({"time": [100, 101, 102], "x_cpu": [0., None, 0.],
                             "x_mem": pa.array([None, None, None], type=pa.float64())}),
                   sink, row_group_size=2)
    footer = footer_summary(pq.ParquetFile(pa.BufferReader(sink.getvalue())),
                            "metrics.parquet", True)
    inventory = metric_inventory(footer)
    assert footer["rows"] == 3 and len(footer["fields"]) == 3
    assert inventory["null_cells_footer"] == 4
    assert inventory["constant_nonnull_fields"] == ["x_cpu"]
    assert inventory["all_null_fields"] == ["x_mem"]
    assert inventory["family_columns"]["cpu"] == inventory["family_columns"]["mem"] == 1
    assert len(inventory["absent_families_by_metric_service"]["x"]) == 6
    schema_only = footer_summary(pq.ParquetFile(pa.BufferReader(sink.getvalue())),
                                "metrics.parquet", False)
    assert "null_count" not in schema_only["fields"]["x_cpu"]
    assert estimate_arrays(2, {"fixture": 3})["estimates"][0][
        "metric_float32_bytes_W_N_10_8"] == 1920
    trace = pa.table({"startTime": [100000027, None], "startTimeMillis": [100000, None]})
    evidence = time_evidence(trace, 100, 110)
    assert evidence["microseconds_agree_with_millisecond_floor_rows"] == 1
    assert evidence["paired_null_rows"] == 1
    return {"time_boundary_clipping": "pass", "original_null_unicode_message_preservation": "pass",
            "source_row_partition_completeness": "pass", "complete_footer_counts": "pass",
            "validation_stats_not_exposed": "pass", "array_byte_formula": "pass",
            "trace_coordinate_agreement": "pass"}


def verify_outputs():
    with (OUT / "rca_schema_audit.json").open(encoding="utf-8") as stream:
        report = json.load(stream)
    assert report["split_sha256"] == SPLIT_SHA and len(report["cases"]) == 144
    for info in report["outputs"]:
        actual = artifact(BASE / info["path"])
        assert (actual["sha256"], actual["bytes"]) == (info["sha256"], info["bytes"])
    for system, manifest in report["systems"].items():
        counts = Counter()
        hashes = defaultdict(hashlib.sha256)
        last = None
        with (OUT / "rca_audit_inputs" / system / "normal_logs.jsonl").open("rb") as stream:
            for line in stream:
                obj = json.loads(line)
                assert set(obj) == {"case", "service", "timestamp", "message"}
                card = report["cases"][obj["case"]]
                assert card["partition"] == "train" and card["dataset"] == "RE2-" + system
                start, end = card["metric_range_inclusive"]
                assert start <= obj["timestamp"] <= end and obj["timestamp"] < card["inject_time"]
                key = (obj["case"], identifier_key(obj["service"]), obj["timestamp"])
                assert last is None or last <= key
                last = key
                counts[obj["case"]] += 1
                hashes[obj["case"]].update(line)
        assert sum(counts.values()) == manifest["normal_export_rows"]
        for case in manifest["train_cases"]:
            card = report["cases"][case]
            if "log_export" not in card:
                assert card["failures"]
                continue
            assert counts[case] == card["log_export"]["exported_normal_rows"]
            assert hashes[case].hexdigest() == card["log_export"]["exported_original_objects_sha256"]
            assert sum(card["log_export"]["placement_counts"].values()) == card["log_export"]["source_rows"]
        with (OUT / "rca_audit_inputs" / system / "profile_windows.json").open() as stream:
            profiles = json.load(stream)
        samples = profiles["samples"]
        assert len(samples) == manifest["profile_sample_count"] <= 12
        for sample in samples:
            assert sample["end"] == sample["start"] + 10
            card = report["cases"][sample["case"]]
            assert card["partition"] == "train"
            assert sample["start"] >= card["metric_range_inclusive"][0]
            assert sample["end"] <= card["metric_range_inclusive"][1] + 1
            assert sample["end"] <= card["inject_time"] or sample["start"] >= card["inject_time"]
            assert len(sample["events"]) == len(sample["source_rows"]) > 0
            assert all(sample["start"] <= e["timestamp"] < sample["end"] for e in sample["events"])
        assert {s["period"] for s in samples} == {
            p for p, count in profiles["nonempty_groups_by_period"].items() if count}
    print("VERIFY_PASS output_hashes normal_original_row_hashes ordering clipping profiles metadata", flush=True)


def audit(guard, tests):
    vocab, feature_metadata = canonical_vocabularies()
    targets = [OUT / f"rca_schema_audit.{ext}" for ext in ("json", "md")]
    targets += [OUT / "rca_audit_inputs" / system / name
                for system in ("OB", "TT")
                for name in ("normal_logs.jsonl", "profile_windows.json", "manifest.json")]
    if any(p.exists() for p in targets):
        raise FileExistsError("Refusing to overwrite named audit outputs")
    cases, systems, issues, outputs = {}, {}, [], []
    for system in ("OB", "TT"):
        dataset = "RE2-" + system
        directory = OUT / "rca_audit_inputs" / system
        directory.mkdir(parents=True, exist_ok=True)
        services = {part: {modality: set() for modality in ("metrics", "logs", "spans")}
                    for part in ("train", "validation")}
        descriptors, train_cases, validation_cases = [], [], []
        window_counts = Counter()
        normal_count = 0
        jsonl = directory / "normal_logs.jsonl"
        with jsonl.open("xb") as stream:
            rows = sorted((r for r in guard.rows.values() if r["dataset"] == dataset and
                           r["partition"] != "test"), key=lambda r: r["case"])
            for row in rows:
                case, part = row["case"], row["partition"]
                card = {"partition": part, "dataset": dataset,
                        "inject_time": row["inject_time"], "files": {}, "failures": []}
                cases[case] = card
                (train_cases if part == "train" else validation_cases).append(case)
                for filename in FILES[:3]:
                    try:
                        card["files"][filename] = guard.footer(case, filename)
                    except (FileNotFoundError, ValueError, pa.ArrowInvalid) as exc:
                        card["failures"].append(f"{filename}: {type(exc).__name__}: {exc}")
                if "metrics.parquet" not in card["files"]:
                    issues.append({"case": case, "failure": "Missing/unreadable metric footer; no placement/export"})
                    continue
                metrics = card["files"]["metrics.parquet"]
                inventory = metric_inventory(metrics)
                card["metric_inventory"] = inventory
                services[part]["metrics"].update(inventory["services"])
                stamp = metrics["fields"].get("time", {})
                start, end = stamp.get("min"), stamp.get("max")
                if type(start) is not int or type(end) is not int:
                    card["failures"].append("Metric footer does not establish integer time range")
                    continue
                card["metric_range_inclusive"] = [start, end]
                card["metric_range_exclusive"] = [start, end + 1]
                if part == "train":
                    injection = guard.injection(case)
                    times = guard.columns(case, "metrics.parquet", ("time",))["time"].to_pylist()
                    assert len(times) == metrics["rows"]
                    finite_times = [t for t in times if t is not None]
                    assert finite_times and min(finite_times) == start and max(finite_times) == end
                    card["metric_time_observed"] = {
                        "nulls": len(times) - len(finite_times),
                        "unique": len(set(finite_times)),
                        "contiguous_one_second": all(b - a == 1 for a, b in zip(times, times[1:])
                                                     if a is not None and b is not None)}
                    if len(times) != end - start + 1 or len(set(finite_times)) != len(times):
                        card["failures"].append("Metric sequence has gaps/duplicate/null timestamps")
                    starts = eligible_starts(start, end, injection)
                    window_counts.update(starts.values())
                for filename, field, modality in (("logs.parquet", "container_name", "logs"),
                                                   ("traces.parquet", "serviceName", "spans")):
                    if filename not in card["files"]:
                        continue
                    columns = (field,)
                    if part == "train":
                        columns = (("container_name", "timestamp", "message") if modality == "logs" else
                                   ("serviceName", "startTime", "startTimeMillis"))
                    try:
                        table = guard.columns(case, filename, columns)
                        assert table.num_rows == card["files"][filename]["rows"]
                        counts = service_counts(table, field)
                        card[modality + "_service_counts"] = counts
                        services[part][modality].update(c["service"] for c in counts)
                        if part == "train" and modality == "logs":
                            log_info, groups = audit_logs(case, table, start, end, row["inject_time"], stream)
                            card["log_export"] = log_info
                            descriptors.extend(groups)
                            normal_count += log_info["exported_normal_rows"]
                        elif part == "train":
                            card["trace_time_evidence"] = time_evidence(table, start, end)
                    except (FileNotFoundError, ValueError, pa.ArrowInvalid) as exc:
                        card["failures"].append(f"{filename}: {type(exc).__name__}: {exc}")
        selected, coverage = select_profiles(descriptors)
        samples = fill_profiles(guard, selected)
        assert len(samples) <= 12
        write_json_new(directory / "profile_windows.json", {
            "system": system, "split_sha256": SPLIT_SHA, "seconds": 10, "stride": 10,
            "bounds": "[start,end)", "selection": "per nominal period: nearest beginning/middle/end recording position plus minimum/maximum raw event count; deterministic ties case/raw-service/start",
            "selection_inputs": ["event_count", "window_time", "case/service identity for ties",
                                 "publisher inject_time for period coverage only"],
            "nonempty_groups_by_period": coverage, "samples": samples})
        observed_train = set().union(*services["train"].values())
        observed_validation = set().union(*services["validation"].values())
        unknown_train = observed_train - set(vocab[dataset]) - set(PROXIES) - {None}
        unknown_validation = observed_validation - set(vocab[dataset]) - set(PROXIES) - {None}
        raw_all = observed_train | observed_validation
        aliases = []
        for raw in ordered(raw_all - {None}):
            possible = [name for name in vocab[dataset] if raw != name and (
                raw.startswith(name + "-") or name.startswith(raw + "-") or
                raw + "service" == name or raw == name + "service")]
            if possible:
                aliases.append({"raw": raw, "possible_canonical": possible,
                                "status": "name-similarity hypothesis only; not merged"})
        train_windows = sum(window_counts.values())
        val_windows = sum(len(eligible_starts(cases[c]["metric_range_inclusive"][0],
                                             cases[c]["metric_range_inclusive"][1],
                                             cases[c]["inject_time"])) for c in validation_cases
                          if "metric_range_inclusive" in cases[c])
        candidate_counts = {
            "current_canonical": len(vocab[dataset]),
            "TRAIN_observed_nonproxy_nonnull_audit_not_adopted":
                len(observed_train - set(PROXIES) - {None}),
            "TRAIN_plus_VALIDATION_observed_nonproxy_nonnull_validation_derived_not_adopted":
                len(raw_all - set(PROXIES) - {None})}
        jsonl_info = artifact(jsonl, normal_count)
        assert jsonl_info["lines"] == normal_count
        profile_info = artifact(directory / "profile_windows.json", len(samples))
        manifest = {
            "system": system, "split_sha256": SPLIT_SHA,
            "status": "cost/input audit only; candidate boundary not adopted",
            "nominal_labels": "publisher <inject_time normal, >=inject_time faulty; not verified physical fault durations",
            "canonical_vocabulary": vocab[dataset], "exact_proxy_exclusions": list(PROXIES),
            "proxy_policy": "reported, not removed from cost-audit logs/profile/raw identifier inventory",
            "raw_service_identifiers": ordered(raw_all),
            "raw_identifiers_by_partition_modality": {
                part: {mod: ordered(names) for mod, names in modalities.items()}
                for part, modalities in services.items()},
            "real_unknowns_train": ordered(unknown_train),
            "real_unknowns_validation": ordered(unknown_validation),
            "possible_aliases": aliases,
            "logs_only_train": ordered(services["train"]["logs"] -
                                       services["train"]["metrics"] - services["train"]["spans"]),
            "candidate_counts": candidate_counts,
            "train_cases": train_cases, "validation_schema_cases": validation_cases,
            "normal_export_order": "case lexicographic, raw service (null first), timestamp, zero-based original parquet source row; duplicates retained",
            "normal_export_rows": normal_count, "profile_sample_count": len(samples),
            "train_eligible_windows_by_period": dict(window_counts),
            "train_full_stride10_window_count": train_windows,
            "train_nonempty_window_raw_service_fit_count": len(descriptors),
            "train_string_message_group_count": sum(d["string_messages"] > 0 for d in descriptors),
            "train_drain_usable_nonempty_fit_count": sum(
                d["service"] is not None and d["string_messages"] > 0 for d in descriptors),
            "train_nonempty_fit_counts_by_period": dict(Counter(d["period"] for d in descriptors)),
            "empty_groups": "no Hawkes fit; all raw nonempty groups counted separately from identifiable/string-usable groups",
            "TRAIN_array_estimates": estimate_arrays(train_windows, candidate_counts),
            "VALIDATION_array_estimates_schema_derived_only": estimate_arrays(val_windows, candidate_counts),
            "unit_policy": "no RCA time shift applied; startTime us/startTimeMillis ms supported by coordinate agreement; duration us remains an explicit assumption",
            "normal_output": jsonl_info, "profile_output": profile_info,
        }
        if unknown_train or unknown_validation:
            issues.append({"system": system, "issue": "Real nonproxy unknown services require reconciliation, not silent dropping",
                           "train": ordered(unknown_train), "validation": ordered(unknown_validation)})
        if any(not coverage[p] for p in ("nominal_normal", "nominal_faulty")):
            issues.append({"system": system, "failure": "No nonempty full log windows for at least one nominal period",
                           "counts": coverage})
        for case in train_cases + validation_cases:
            if cases[case]["failures"]:
                issues.append({"case": case, "failures": cases[case]["failures"]})
        write_json_new(directory / "manifest.json", manifest)
        systems[system] = manifest
        outputs += [jsonl_info, profile_info, artifact(directory / "manifest.json", len(train_cases))]
        print(f"SYSTEM_PASS {system} normal_rows={normal_count} profiles={len(samples)} "
              f"fits={len(descriptors)} candidates={candidate_counts}", flush=True)
    assert len(cases) == 144
    ledger = guard.access_ledger()
    assert not any(entry["partition"] == "test" for entry in ledger)
    assert all(entry["columns"] == [] or set(entry["columns"]) <=
               set(IDENTIFIERS.get(entry["file"], ()))
               for entry in ledger if entry["partition"] == "validation")
    summaries = {}
    for system in ("OB", "TT"):
        summaries[system] = {}
        for part in ("train", "validation"):
            cards = [c for c in cases.values() if c["dataset"] == "RE2-" + system and c["partition"] == part]
            summaries[system][part] = {
                "cases": len(cards),
                "file_rows": {f: sum(c["files"].get(f, {}).get("rows", 0) for c in cards) for f in FILES[:3]},
                "family_columns": {f: sum(c.get("metric_inventory", {}).get("family_columns", {}).get(f, 0)
                                          for c in cards) for f in FAMILIES},
                "absent_metric_service_family_fields": sum(
                    len(fs) for c in cards for fs in c.get("metric_inventory", {}).get(
                        "absent_families_by_metric_service", {}).values()),
                "metric_null_cells_footer": sum(c.get("metric_inventory", {}).get("null_cells_footer", 0) for c in cards),
                "metric_null_unknown_rows": sum(c.get("metric_inventory", {}).get("null_unknown_rows", 0) for c in cards),
                "metric_constant_nonnull_fields": sum(len(c.get("metric_inventory", {}).get(
                    "constant_nonnull_fields", [])) for c in cards),
                "metric_constant_unknown_fields": sum(len(c.get("metric_inventory", {}).get(
                    "constant_unknown_fields", [])) for c in cards),
            }
    code_info = artifact(Path(__file__))
    outputs.insert(0, code_info)
    report = {
        "scope": "TRAIN input feasibility/native port cost audit, no feature/model training",
        "split_sha256": SPLIT_SHA, "versions": {"python": sys.version, "pyarrow": pa.__version__},
        "label_contract": "Publisher nominal labels preserved; actual activation/end/recovery not independently verified",
        "validation_scope": "schemas, footer time ranges, service identifier columns only; no metric values, log messages, durations, features or predictions",
        "final_test_raw_accesses": 0, "tests": tests, "summaries": summaries,
        "systems": systems, "cases": cases, "issues": issues,
        "access_ledger": ledger, "rejected_requests": dict(guard.rejected),
        "preimplementation_probe_access": {
            "partition": "train", "mode": "footer",
            "cases": ["re2ob_checkoutservice_delay_1", "re2tt_ts-auth-service_delay_1"],
            "files_per_case": list(FILES[:3]), "raw_opens": 6,
            "self_test_rejections_separate_run": 147},
        "preparatory_read_disclosure": "An initial bounded read of features.json exposed first 2000 lines of old train/validation vectors. They were not used for sampling or any audit decision; features contains no final-test cases. Exporter reads only the four-line feature metadata header.",
        "old_feature_metadata_only": feature_metadata,
        "graph": "not built; no imported Eadro27/static deployment graph",
        "outputs": outputs,
        "self_hash_policy": "JSON self hash printed as OUTPUT_HASH at exit; cannot embed its own hash",
    }
    md = markdown_report(report)
    assert len(md.split()) <= 900
    with (OUT / "rca_schema_audit.md").open("x", encoding="utf-8") as stream:
        stream.write(md)
    report["outputs"].append(artifact(OUT / "rca_schema_audit.md"))
    write_json_new(OUT / "rca_schema_audit.json", report)
    for info in report["outputs"] + [artifact(OUT / "rca_schema_audit.json", len(cases))]:
        print("OUTPUT_HASH " + encoded(info), flush=True)
    guard.verify_split()
    print("AUDIT_PASS train=108 validation_schema=36 final_raw=0 metadata_cases=144", flush=True)


def markdown_report(report):
    lines = [
        "# RCA guarded schema/input cost audit",
        "",
        f"Frozen split SHA256 `{SPLIT_SHA}`; Python3.10/PyArrow19.",
        "TRAIN108 telemetry; validation36 schema/footer-time/service IDs only. Final36 case files not opened.",
        "Input feasibility only: no templates, Hawkes extraction, feature/model training, new candidates or graph adoption.",
        "**Labels:** publisher nominal normal `<inject_time`, faulty `>=inject_time`; not verified physical activation or fault duration.",
        "",
        "## Export and cost coverage",
        "|System|normal original rows|profile samples|TRAIN windows|nonempty raw service fits|canonical N|observed TRAIN N|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for system, m in report["systems"].items():
        counts = m["candidate_counts"]
        lines.append(f"|{system}|{m['normal_export_rows']}|{m['profile_sample_count']}|"
                     f"{m['train_full_stride10_window_count']}|{m['train_nonempty_window_raw_service_fit_count']}|"
                     f"{counts['current_canonical']}|{counts['TRAIN_observed_nonproxy_nonnull_audit_not_adopted']}|")
    lines += [
        "",
        "JSONL order: case, raw service (null first), timestamp, original source row; no deduplication/string cleaning/null replacement.",
        "Clipping uses own inclusive metric range and strictly pre-injection timestamps. Missing/outside rows and boundary/tail-window events are counted per case.",
        "Profiles retain every source event, fixed10s half-open bounds, both nominal periods, beginning/middle/end and smallest/largest counts. Selection uses counts/time only.",
        "",
        "## Evidence-backed schema issues",
    ]
    for system, m in report["systems"].items():
        s = report["summaries"][system]["train"]
        cards = [c for c in report["cases"].values() if c["dataset"] == "RE2-" + system and c["partition"] == "train"]
        placement_counts = Counter()
        for c in cards:
            placement_counts.update(c.get("log_export", {}).get("placement_counts", {}))
        lines.append(f"- **{system} TRAIN:** metric rows {s['file_rows']['metrics.parquet']}; "
                     f"family-column counts `{s['family_columns']}`; "
                     f"absent fields {s['absent_metric_service_family_fields']}, "
                     f"null cells {s['metric_null_cells_footer']} (unknown rows {s['metric_null_unknown_rows']}), "
                     f"constant fields {s['metric_constant_nonnull_fields']}. Missing error fields are unknown, never zero errors.")
        lines.append(f"- **{system} services:** real unknown TRAIN `{m['real_unknowns_train']}`, "
                     f"validation `{m['real_unknowns_validation']}`; logs-only TRAIN `{m['logs_only_train']}`. "
                     "All raw IDs, proxy sightings and unmerged alias hypotheses are retained in manifests.")
        lines.append(f"- **{system} log placement:** `{dict(placement_counts)}`.")
    lines += [
        "- Exact exclusions remain BlackHoleCluster, PassthroughCluster, InboundPassthroughClusterIpv4/Ipv6. Cost exports do not drop these or unknown IDs.",
        "- TRAIN startTime/startTimeMillis rowwise coordinate agreement is recorded; us/ms start coordinates are supported by scale/epoch comparison. RCA duration is int64 without unit metadata: microseconds remains an assumption, not certified provenance. Native Jaeger conversion is evidence for native data only.",
        "- Arrays use W×N×10×8 metric float32, W×N×10×2 trace float32, W×N×E log float64. Exact byte coefficients for current/observed N and explicitly validation-derived estimates are in manifests; E/solver cost remain unknown until later TRAIN-only profiling.",
        "",
        "## Verification and provenance",
        "144 final-open and 3 validation-value requests rejected before disk access; clipping, Unicode/null preservation and row-completeness self-checks passed. All exported rows round-trip unchanged; per-case source-row/order hashes, full footer fields and bounded case/partition/file ledger are in JSON.",
        "Preimplementation probe: six TRAIN footer opens recorded separately. Initial bounded old-features read exposed TRAIN/validation vectors; none influenced sampling or decisions, and no final features existed there. Exporter uses metadata header only.",
        "Outputs below record SHA256 and bytes; JSON self hash is recorded in successful monitor OUTPUT_HASH output.",
        "",
    ]
    for item in report["outputs"]:
        lines.append(f"- `{Path(item['path']).name}` ({item['bytes']} bytes): `{item['sha256']}`")
    if report["issues"]:
        lines += ["", "Contract/data failures needing reconciliation are listed verbatim in JSON; no raw-access widening or automatic adapter adoption was attempted."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Guarded training footer discovery")
    parser.add_argument("--self-test", action="store_true", help="Test guards/clipping without opening raw files")
    parser.add_argument("--verify", action="store_true", help="Verify generated hashes/rows, no raw files")
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 10), "Use .venv-mlp Python3.10"
    assert pa.__version__.split(".")[0] == "19", "Use PyArrow19"
    guard = Guard()
    tests = {**self_test(guard), **logic_tests()}
    print(encoded({"self_test": tests}), flush=True)
    if args.verify:
        verify_outputs()
    elif args.self_test:
        pass
    elif args.probe:
        probe(guard)
    else:
        audit(guard, tests)
