#!/usr/bin/env python3
"""Read-only six-window native SN evidence; prints JSON, writes no files."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

REPO = Path("/home/gnho1236/r2")
NATIVE = REPO / "research/native_reproduction_20261013"
HORIZON = REPO / "research/sn_hawkes_horizon_contrast_20261017"
ROOT = REPO / "data/eadro_native/SN_Dataset/SN Dataset"
RUN = "SN.2022-04-17T181245D2022-04-17T183616"
WANTED = (112, 115, 120, 129, 133, 136)
FOCUS = ("media-service", "text-service", "compose-post-service")
sys.path.insert(0, str(NATIVE))
sys.path.insert(0, str(HORIZON))
profile = importlib.import_module("native_data_profile")
loader = importlib.import_module("selective_loader")
LOG_RE, json_array, utc_seconds = profile.LOG_RE, profile.json_array, profile.utc_seconds
file_hash, read_rows = loader.file_hash, loader.read_rows


def load_json(path):
    with path.open() as stream:
        return json.load(stream)


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def log_stamp(line):
    match = LOG_RE.search(line)
    if match is None:
        raise ValueError("Missing routing timestamp")
    for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return utc_seconds(match.group(), fmt) + 28800
        except ValueError:
            pass
    raise ValueError("Invalid routing timestamp")


def diagnose():
    meta_path = NATIVE / "native_inputs/SN/metadata.json"
    meta = load_json(meta_path)
    services, channels = meta["services"], meta["metrics"]
    run = next(r for r in meta["runs"] if r["run_id"] == RUN)
    windows = [meta["windows"][w] for w in WANTED]
    lookup = {w["start"]: i for i, w in enumerate(windows)}

    def route(stamp):
        if not run["record_start"] <= stamp < run["record_end_exclusive"]:
            return None
        start = run["record_start"] + int((stamp - run["record_start"]) // 10) * 10
        row = lookup.get(start)
        return None if row is None else (row, start)

    # Boundary checks include excluded adjacent windows but no observations.
    for row, window in enumerate(windows):
        assert window["run_id"] == RUN and window["end"] == window["start"] + 9
        assert route(window["start"]) == (row, window["start"])
        assert route(window["start"] + 9.999) == (row, window["start"])
        assert route(window["start"] - .001) is None
        assert route(window["start"] + 10) is None
        assert window["event_id"].endswith("fault07" if row < 3 else "fault08")
    split = load_json(NATIVE / "calibration200/SN/diagmlp/seed_11/split.json")
    assert set(WANTED) <= set(split["indices"]["validation"])

    safe = HORIZON / "inputs/selected.npz"
    preparation = load_json(HORIZON / "inputs/preparation.json")
    expected_safe_hash = preparation["output_hashes"]["selected.npz"]
    assert file_hash(safe) == expected_safe_hash
    with np.load(safe, allow_pickle=False) as archive:
        indices = archive["indices"]  # Structural metadata only.
    assert len(indices) == 394 and len(set(indices.tolist())) == 394
    assert set(indices.tolist()) == set(split["indices"]["train"] + split["indices"]["validation"])
    positions = [int(np.flatnonzero(indices == w)[0]) for w in WANTED]
    audit = []
    arrays = {
        key: read_rows(safe, key, positions, shape, kind, audit)
        for key, shape, kind in (
            ("metrics", (394, 12, 10, 7), "f"),
            ("traces", (394, 12, 10, 2), "f"),
            ("logs", (394, 12, 7), "f"),
            ("labels", (394,), "iu"),
        )
    }
    assert np.all(arrays["labels"] == services.index("media-service"))
    scaler_path = NATIVE / "calibration200/SN/diagmlp/seed_11/scaler.npz"
    scaler_hash = file_hash(scaler_path)
    assert scaler_hash == load_json(scaler_path.parent / "summary.json")["artifact_hashes"]["scaler.npz"]
    assert all(file_hash(scaler_path.parent.parent / ("seed_%d" % seed) / "scaler.npz") == scaler_hash
               for seed in (23, 37))
    with np.load(scaler_path, allow_pickle=False) as archive:
        stats = {k: archive[k] for k in ("metrics_mean", "metrics_std", "traces_mean", "traces_std")}

    hashes = {}

    def checked_bytes(path):
        body = path.read_bytes()
        relative = str(path.relative_to(ROOT))
        actual = hashlib.sha256(body).hexdigest()
        assert actual == meta["input_sha256"][relative], relative
        hashes[relative] = actual
        return body

    # CSV structure/string fields pass through the parser for the shared file;
    # only timestamp-selected rows undergo metric numeric interpretation.
    raw_metrics = np.empty((6, 12, 10, 7), dtype=np.float64)
    metric_rows = 0
    for node, service in enumerate(services):
        body = checked_bytes(ROOT / "data" / RUN / "metrics" / (service + ".csv"))
        rows = csv.reader(io.StringIO(body.decode()))
        assert next(rows) == ["timestamp"] + channels
        retained = []
        coordinates = []
        for fields in rows:
            stamp = int(fields[0]) + 57600
            routed = route(stamp)
            if routed is None:
                continue
            row, start = routed
            retained.append(fields)
            coordinates.append((row, stamp - start))
        assert len(coordinates) == len(set(coordinates)) == 60
        selected_text = io.StringIO()
        writer = csv.writer(selected_text)
        writer.writerow(["timestamp"] + channels)
        writer.writerows(retained)
        frame = pd.read_csv(io.StringIO(selected_text.getvalue()))
        values = np.asarray(frame, dtype=np.float64)[:, 1:]
        assert np.isfinite(values).all()
        for (row, second), value in zip(coordinates, values):
            raw_metrics[row, node, second] = value
        metric_rows += len(coordinates)
    assert np.array_equal(raw_metrics, arrays["metrics"]), "Metric exact match failed"
    z = (raw_metrics - stats["metrics_mean"][None, :, None, :]) / (
        stats["metrics_std"][None, :, None, :] + 1e-8)

    # Whole shared JSON object is parsed; nonselected line content is not
    # template-matched, summarized, retained or emitted after timestamp routing.
    logs = json.loads(checked_bytes(ROOT / "data" / RUN / "logs.json"))
    assert set(logs) == set(services)
    log_groups = defaultdict(list)
    log_routed = 0
    for service, lines in logs.items():
        for line in lines:
            stamp = log_stamp(line)
            log_routed += 1
            routed = route(stamp)
            if routed is not None:
                row, start = routed
                # Frozen SN templates contain no Drain wildcards. This tests
                # exact masked text equality, not a new Drain training/match.
                masked = re.sub(r"\[(" + LOG_RE.pattern + r")\]", "<:DATATIME:>", line)
                template_id = meta["templates"].index(masked) + 1 if masked in meta["templates"] else None
                log_groups[(row, service)].append({
                    "timestamp": stamp, "offset": stamp - start,
                    "template_id_exact_masked_text": template_id,
                    "masked_text": masked, "raw_line": line,
                })
    del logs

    # Existing bounded JSON-array parser decodes every shared trace object.
    # Only startTime is interpreted before the six-window selection boundary.
    sums = np.zeros((6, 12, 10), dtype=np.float64)
    counts = np.zeros((6, 12, 10), dtype=np.int64)
    durations = defaultdict(list)
    identities = defaultdict(set)
    signatures = {}
    conflicts = 0
    operations = defaultdict(Counter)
    operation_durations = defaultdict(list)
    selected_span_examples = {}
    routed_occurrences = 0
    digest = hashlib.sha256()
    span_path = ROOT / "data" / RUN / "spans.json"
    with span_path.open("rb") as stream:
        for trace in json_array(stream, digest):
            for span in trace["spans"]:
                stamp_us = span.get("startTime")
                assert type(stamp_us) is int
                routed_occurrences += 1
                stamp = stamp_us // 1000000 + 28800
                routed = route(stamp)
                if routed is None:
                    continue
                row, start = routed
                service = trace["processes"][span["processID"]]["serviceName"]
                node, second = services.index(service), stamp - start
                duration = span["duration"]
                identity = (span["traceID"], span["spanID"])
                assert type(duration) is int and duration >= 0
                assert identity[0] == trace["traceID"] and all(identity)
                signature = (row, node, stamp_us, duration)
                if identity in signatures and signatures[identity] != signature:
                    conflicts += 1
                signatures[identity] = signature
                identities[(row, node)].add(identity)
                sums[row, node, second] += duration / 1e6
                counts[row, node, second] += 1
                durations[(row, node)].append(duration)
                operations[(row, node)][span["operationName"]] += 1
                operation_durations[(row, node, span["operationName"])].append(duration)
                selected_span_examples.setdefault((row, node), {
                    "traceID": identity[0], "spanID": identity[1],
                    "startTime": stamp_us, "duration_us": duration,
                    "operationName": span["operationName"],
                })
    relative = str(span_path.relative_to(ROOT))
    assert digest.hexdigest() == meta["input_sha256"][relative]
    hashes[relative] = digest.hexdigest()
    latency = np.divide(sums, counts, out=np.zeros_like(sums), where=counts > 0)
    assert np.array_equal(latency, arrays["traces"][..., 0]), "Occurrence-weighted latency exact match failed"
    assert np.all(arrays["traces"][..., 1] == 0)

    result = {
        "scope": {"run": RUN, "original_indices": WANTED, "protected_model_input_rows_decoded": 0,
                  "selected_npz_observation_rows_decoded": 6},
        "disclosure": (
            "All 14 shared source files are read for hashes. CSV records/string fields and timestamps "
            "are routed for whole files; metric numerics retained/analyzed only for six windows. "
            "logs.json is wholly JSON-parsed, all log timestamps routed; only six-window content is analyzed. "
            "spans.json is wholly byte-read and every trace object JSON-decoded; only span startTime "
            "is interpreted before routing. Nonselected durations/services/operations/identities are not analyzed. "
            "Safe394 NPZ members are sequentially decompressed but only six observation rows decoded. "
            "No original raw.npz or protected numeric model-input rows/model outputs are opened. "
            "Shared raw JSON records outside the six windows are structurally decoded as disclosed above. "
            "No other-window distributions, training, inference, "
            "Drain fitting or Hawkes fitting are used."
        ),
        "checks": {"metric_exact_equal": True, "latency_exact_equal": True,
                   "trace_channel1_zero": True, "source_hashes_verified": len(hashes),
                   "metric_selected_rows": metric_rows, "log_timestamp_routed_lines": log_routed,
                   "selected_log_lines": sum(map(len, log_groups.values())),
                   "span_timestamp_routed_occurrences": routed_occurrences,
                   "selected_span_occurrences": int(counts.sum()),
                   "selected_unique_identities": len(signatures), "selected_identity_conflicts": conflicts},
        "provenance": {"metadata": str(meta_path), "metadata_sha256": file_hash(meta_path),
                       "selected": str(safe), "selected_sha256": expected_safe_hash,
                       "scaler": str(scaler_path), "scaler_sha256": scaler_hash,
                       "same_scaler_seeds": [11, 23, 37], "source_sha256": hashes},
        "npz_access": audit, "templates_one_based": dict(enumerate(meta["templates"], 1)),
        "windows": [],
    }
    for row, (index, window) in enumerate(zip(WANTED, windows)):
        strongest = int(np.argmax(np.abs(z[row]).mean(axis=(1, 2))))
        detail_nodes = sorted({services.index(s) for s in FOCUS} | {strongest})
        item = {"index": index, **window, "start_iso_utc": iso(window["start"]),
                "end_exclusive_iso_utc": iso(window["start"] + 10),
                "raw_metric_start": window["start"] - 57600,
                "raw_span_start_us": (window["start"] - 28800) * 1000000,
                "raw_log_start_wallclock": iso(window["start"] - 28800),
                "services": {}, "logs_nonempty": {}, "latency_all_services": {}}
        for node, service in enumerate(services):
            count = int(counts[row, node].sum())
            ds = np.asarray(durations[(row, node)], dtype=np.int64)
            ls = latency[row, node]
            trace_summary = {
                "occurrences": count, "unique_identities": len(identities[(row, node)]),
                "duplicate_occurrences": count - len(identities[(row, node)]),
                "observed_bins": int(np.count_nonzero(counts[row, node])),
                "zero_filled_bin_mean_seconds": float(ls.mean()),
                "observed_bin_mean_seconds": float(ls[counts[row, node] > 0].mean()) if count else None,
                "occurrence_weighted_duration_mean_us": float(ds.mean()) if count else None,
                "duration_min_us": int(ds.min()) if count else None,
                "duration_max_us": int(ds.max()) if count else None,
                "mean_abs_metric_z": float(np.abs(z[row, node]).mean()),
            }
            item["latency_all_services"][service] = trace_summary
            if node in detail_nodes:
                metrics = {
                    channel: {"raw": raw_metrics[row, node, :, c].tolist(),
                              "fixed_train_mean": float(stats["metrics_mean"][node, c]),
                              "fixed_train_std": float(stats["metrics_std"][node, c]),
                              "z_mean": float(z[row, node, :, c].mean()),
                              "z_min": float(z[row, node, :, c].min()),
                              "z_max": float(z[row, node, :, c].max())}
                    for c, channel in enumerate(channels)
                }
                item["services"][service] = {
                    "metrics": metrics, "trace": trace_summary,
                    "trace_bin_counts": counts[row, node].tolist(),
                    "trace_bin_latency_seconds": ls.tolist(),
                    "trace_operations_occurrence_weighted": dict(operations[(row, node)]),
                    "trace_operation_duration_us": {
                        operation: {"occurrences": len(values), "min": min(values),
                                    "max": max(values), "mean": float(np.mean(values))}
                        for (r, n, operation), values in operation_durations.items()
                        if r == row and n == node
                    },
                    "trace_example": selected_span_examples.get((row, node)),
                    "baseline_raw_hawkes_log_feature": arrays["logs"][row, node].tolist(),
                }
            entries = log_groups.get((row, service), [])
            if entries:
                item["logs_nonempty"][service] = {
                    "count": len(entries),
                    "template_counts": dict(Counter(str(e["template_id_exact_masked_text"]) for e in entries)),
                    "masked_content_counts": dict(Counter(e["masked_text"] for e in entries)),
                    "timestamp_min": min(e["timestamp"] for e in entries),
                    "timestamp_max": max(e["timestamp"] for e in entries),
                    "bin_counts": np.histogram([e["offset"] for e in entries], bins=np.arange(11))[0].tolist(),
                    "first_raw_line": entries[0]["raw_line"],
                }
        result["windows"].append(item)
    return result


if __name__ == "__main__":
    print(json.dumps(diagnose(), sort_keys=True, indent=2, allow_nan=False))
