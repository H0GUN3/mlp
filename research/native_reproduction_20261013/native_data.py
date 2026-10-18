"""Native Eadro input extraction only: no normalization, splits, or models."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tarfile
import time
from typing import Any, Dict, List, Tuple
import warnings

import numpy as np
import pandas as pd
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from tick.hawkes import HawkesADM4

from native_data_profile import (
    LOG_RE, METRICS, ROOTS, SERVICES, fault_service, json_array, safe_member,
    utc_seconds,
)


OUT = Path(__file__).resolve().parent
INPUTS = OUT / "native_inputs"
COMMIT = "7d69281a80adce60067aa858729746fc6a362f53"
LENGTH = 10
RECORD_SHIFT = 16 * 3600
TRACE_SHIFT = LOG_SHIFT = 8 * 3600
SEED = 42
SN_EDGES = {
    "compose-post-service": ["compose-post-service", "home-timeline-service",
                            "media-service", "post-storage-service", "text-service",
                            "unique-id-service", "user-service", "user-timeline-service"],
    "home-timeline-service": ["home-timeline-service", "post-storage-service", "social-graph-service"],
    "post-storage-service": ["post-storage-service"],
    "social-graph-service": ["social-graph-service", "user-service"],
    "text-service": ["text-service", "url-shorten-service", "user-mention-service"],
    "user-service": ["user-service"],
    "user-timeline-service": ["user-timeline-service"],
    "nginx-web-server": ["compose-post-service", "home-timeline-service",
                        "nginx-web-server", "social-graph-service", "user-service"],
}
TT_EDGES = {
    "preserve": ["preserve", "seat", "security", "food", "order", "ticketinfo",
                 "travel", "contacts", "notification", "user", "station"],
    "seat": ["seat", "order", "config", "travel"],
    "cancel": ["inside-payment", "order-other", "order"],
    "security": ["security", "order-other", "order"],
    "food": ["travel", "food-map", "station"],
    "travel": ["travel", "order", "ticketinfo", "train", "route"],
    "inside-payment": ["payment", "order"],
    "ticketinfo": ["ticketinfo", "basic"],
    "basic": ["basic", "route", "price", "train", "station"],
    "order-other": ["station"],
    "order": ["order", "station", "assurance"],
    "auth": ["auth", "verification-code"],
}


def edges(dataset: str) -> List[List[int]]:
    names = SERVICES[dataset]
    mapping = {s: i for i, s in enumerate(names)}
    pairs = SN_EDGES if dataset == "SN" else {
        "ts-{}-service".format(k): ["ts-{}-service".format(v) for v in values]
        for k, values in TT_EDGES.items()
    }
    return [
        [mapping[s] for s, targets in pairs.items() for _ in targets],
        [mapping[t] for targets in pairs.values() for t in targets],
    ]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_raw(path: Path, root: Path, hashes: Dict[str, str]) -> bytes:
    if root.resolve() not in path.resolve().parents:
        raise ValueError("Raw path escapes authorized root: " + str(path))
    body = path.read_bytes()
    hashes[str(path.relative_to(root))] = hashlib.sha256(body).hexdigest()
    return body


def write_json(path: Path, obj: Any) -> None:
    text = json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x") as stream:
        stream.write(text)


def save_arrays(path: Path, arrays: Dict[str, np.ndarray]) -> str:
    if path.exists():
        raise FileExistsError("Refusing to overwrite input artifact: " + str(path))
    temporary = path.with_suffix(".npz.partial")
    with temporary.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    temporary.rename(path)
    return file_hash(path)


def window_starts(start: int, end: int) -> np.ndarray:
    if type(start) is not int or type(end) is not int or end - start < LENGTH:
        raise ValueError("Recording needs integer endpoints and a full 10s window")
    return np.arange(start, end - LENGTH + 1, LENGTH, dtype=np.int64)


def rounded_faults(record: Dict[str, Any], dataset: str, run: str) -> List[Dict[str, Any]]:
    result = []
    for index, fault in enumerate(record["faults"]):
        service = fault_service(fault["name"], dataset)
        if service not in SERVICES[dataset]:
            raise ValueError("Unknown root service: " + service)
        if not np.isfinite(fault["start"]) or not np.isfinite(fault["duration"]) or fault["duration"] <= 0:
            raise ValueError("Invalid fault time or duration")
        result.append({
            "event_id": "{}:fault{:02d}".format(run, index),
            "root": SERVICES[dataset].index(service),
            "service": service, "fault_type": fault["fault"],
            "root_fault_group": service + "|" + fault["fault"],
            "start": int(fault["start"]) + RECORD_SHIFT,
            "end_inclusive": int(fault["start"] + fault["duration"]) + RECORD_SHIFT,
        })
    return result


def window_labels(starts: np.ndarray, faults: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels, event_ids, groups = [], [], []
    for start in starts:
        hits = [f for f in faults if f["start"] < int(start) + LENGTH
                and f["end_inclusive"] >= int(start)]
        roots = {f["root"] for f in hits}
        if len(roots) > 1:
            raise ValueError("Ambiguous roots in window {}: {}".format(start, hits))
        labels.append(next(iter(roots)) if roots else -1)
        event_ids.append(";".join(f["event_id"] for f in hits))
        groups.append(";".join(sorted({f["root_fault_group"] for f in hits})))
    return np.array(labels, dtype=np.int64), np.array(event_ids, dtype=str), np.array(groups, dtype=str)


def log_timestamp(line: str) -> float:
    if not isinstance(line, str):
        raise ValueError("Log line must be a string")
    match = LOG_RE.search(line)
    if match is None:
        raise ValueError("Log lacks source-format timestamp")
    for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return utc_seconds(match.group(), fmt) + LOG_SHIFT
        except ValueError:
            pass
    raise ValueError("Invalid log timestamp: " + match.group())


def auxiliary_logs(root: Path, hashes: Dict[str, str]) -> List[Tuple[str, Dict[str, List[str]]]]:
    result = []
    archives = sorted(p for p in (root / "no fault").iterdir()
                      if p.name.endswith((".txz", ".tgz", ".tar.xz")))
    for path in archives:
        found = 0
        # Streaming skips large span members without extracting anything.
        with tarfile.open(str(path), "r|*") as archive:
            for member in archive:
                name = safe_member(member.name)
                if not member.isfile():
                    if not member.isdir():
                        raise ValueError("Nonregular auxiliary archive member")
                    continue
                if not name.endswith("/logs.json"):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("Unreadable archive log member")
                body = stream.read()
                source = str(path.relative_to(root)) + "!" + name
                hashes[source] = hashlib.sha256(body).hexdigest()
                obj = json.loads(body)
                if not isinstance(obj, dict) or any(
                    not isinstance(v, list) or any(not isinstance(s, str) for s in v)
                    for v in obj.values()
                ):
                    raise ValueError("Invalid auxiliary service/log schema")
                result.append((source, obj))
                found += 1
        if found != 1:
            raise ValueError("Expected one log member per auxiliary archive")
    if len(result) != 3:
        raise ValueError("Expected exactly three designated auxiliary normal log sessions")
    return result


def train_templates(root: Path, hashes: Dict[str, str]) -> Tuple[Any, List[str], Dict[str, Any]]:
    config_path = INPUTS / "drain3.ini"
    raw = config_path.read_bytes()
    # apply_patch adds a final LF; the pinned INI has none. Parameter bytes match.
    source_raw = raw[:-1] if raw.endswith(b"\n") else raw
    blob = hashlib.sha1(("blob {}\0".format(len(source_raw))).encode() + source_raw).hexdigest()
    if blob != "a391102e3e8c66ac125fad082e619a2b180e0dcf":
        raise ValueError("Pinned Drain configuration changed")
    config = TemplateMinerConfig()
    config.load(str(config_path))
    miner = TemplateMiner(config=config)
    sources, count = [], 0
    for source, logs in auxiliary_logs(root, hashes):
        sources.append(source)
        # Deterministic archive ordering; retain JSON service order and line order.
        for lines in logs.values():
            for line in lines:
                miner.add_log_message(line)
                count += 1
    templates = [cluster.get_template() for cluster in miner.drain.clusters]
    return miner, templates, {
        "sources": sources, "lines": count, "config_sha256": hashlib.sha256(raw).hexdigest(),
        "config_source_sha256": hashlib.sha256(source_raw).hexdigest(),
        "config_terminal_lf_added": raw != source_raw,
        "config_git_blob_sha1": blob, "archive_order": "sorted filename",
        "template_order": "source Drain cluster enumeration; duplicate texts not removed",
    }


class SpanAudit:
    def __init__(self) -> None:
        self.seen: Dict[Tuple[str, str], Tuple[str, Tuple[str, int, int], str]] = {}
        self.counts: Counter = Counter()
        self.examples: List[Dict[str, Any]] = []

    def observe(self, trace: Dict[str, Any], span: Dict[str, Any], service: str,
                run: str, inside: bool) -> None:
        key = (span["traceID"], span["spanID"])
        if not all(isinstance(k, str) and k for k in key) or key[0] != trace["traceID"]:
            raise ValueError("Invalid trace/span identity")
        canonical = {"span": span, "service": service}
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        feature = (service, span["startTime"], span["duration"])
        previous = self.seen.get(key)
        self.counts["raw_span_occurrences"] += 1
        self.counts["kept_occurrences" if inside else "record_clipped_occurrences"] += 1
        if previous is None:
            self.seen[key] = (digest, feature, run)
        else:
            self.counts["duplicate_identity_occurrences"] += 1
            if inside:
                self.counts["duplicate_identity_kept_occurrences"] += 1
            if previous[0] != digest:
                self.counts["conflicting_content_occurrences"] += 1
                changed = previous[1] != feature
                self.counts["conflicting_feature_occurrences"] += int(changed)
                if len(self.examples) < 8:
                    self.examples.append({
                        "trace_id": key[0], "span_id": key[1], "run": run,
                        "first_run": previous[2], "feature_changed": changed,
                    })

    def summary(self) -> Dict[str, Any]:
        return {
            "counts": dict(self.counts), "unique_identities": len(self.seen),
            "conflict_examples": self.examples,
            "weighting": "Keep every occurrence inside its recording, including duplicate identities; no deduplication",
        }


def trace_series(path: Path, names: List[str], start: int, end: int,
                 audit: SpanAudit, hashes: Dict[str, str], root: Path) -> np.ndarray:
    node_map = {s: i for i, s in enumerate(names)}
    sums = np.zeros((len(names), end - start), dtype=np.float64)
    counts = np.zeros_like(sums, dtype=np.int64)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for trace in json_array(stream, digest):
            for span in trace["spans"]:
                if type(span.get("startTime")) is not int or type(span.get("duration")) is not int or span["duration"] < 0:
                    raise ValueError("Invalid native span timestamp/duration")
                process = trace["processes"].get(span["processID"])
                if process is None or process["serviceName"] not in node_map:
                    raise ValueError("Unresolved or unknown span service")
                service = process["serviceName"]
                stamp = span["startTime"] // 1000000 + TRACE_SHIFT
                inside = start <= stamp < end
                audit.observe(trace, span, service, path.parent.name, inside)
                if inside:
                    nid, slot = node_map[service], stamp - start
                    sums[nid, slot] += span["duration"] / 1000000.0
                    counts[nid, slot] += 1
    hashes[str(path.relative_to(root))] = digest.hexdigest()
    latency = np.zeros((len(names), end - start, 2), dtype=np.float64)
    np.divide(sums, counts, out=latency[:, :, 0], where=counts > 0)
    return latency


def metric_series(folder: Path, names: List[str], start: int, end: int,
                  hashes: Dict[str, str], root: Path) -> np.ndarray:
    if sorted(p.stem for p in folder.glob("*.csv")) != sorted(names):
        raise ValueError("Missing/extra metric service files")
    result = np.empty((len(names), end - start, len(METRICS)), dtype=np.float64)
    for nid, service in enumerate(names):
        path = folder / (service + ".csv")
        body = read_raw(path, root, hashes)
        import io
        frame = pd.read_csv(io.BytesIO(body))
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("Expected a complete metric DataFrame")
        if list(frame.columns) != ["timestamp"] + METRICS:
            raise ValueError("Metric column order/schema mismatch")
        values = np.asarray(frame, dtype=np.float64)
        if not np.isfinite(values).all() or not np.array_equal(values[:, 0], np.floor(values[:, 0])):
            raise ValueError("Invalid metric numeric values/timestamps")
        stamps = values[:, 0].astype(np.int64) + RECORD_SHIFT
        if len(stamps) != len(set(stamps)) or np.any(np.diff(stamps) != 1):
            raise ValueError("Metric timestamps not unique contiguous seconds")
        keep = (stamps >= start) & (stamps < end)
        if not np.array_equal(stamps[keep], np.arange(start, end)):
            raise ValueError("Recording metric coverage mismatch")
        result[nid] = values[keep, 1:]
    return result


def log_rows(body: bytes, miner: Any, templates: List[str], names: List[str],
             start: int, end: int, first_window: int) -> Tuple[List[Tuple[int, int, int, float]], Dict[str, int]]:
    obj = json.loads(body)
    if not isinstance(obj, dict) or set(obj) != set(names):
        raise ValueError("Missing/extra log service keys")
    mapping = {template: index + 1 for index, template in enumerate(templates)}
    mapping["Unseen"] = 0
    rows: List[Tuple[int, int, int, float]] = []
    counts: Counter = Counter()
    full_end = start + ((end - start) // LENGTH) * LENGTH
    for service, lines in obj.items():
        if not isinstance(lines, list):
            raise ValueError("Invalid service log list")
        for line in lines:
            stamp = log_timestamp(line)
            counts["raw_lines"] += 1
            if not start <= stamp < end:
                counts["record_clipped_lines"] += 1
                continue
            if stamp >= full_end:
                counts["trailing_partial_window_lines"] += 1
                continue
            match = miner.match(line)
            template = match.get_template() if match is not None else "Unseen"
            event = mapping.get(template, 0)
            counts["unseen_lines"] += int(event == 0)
            counts["used_lines"] += 1
            rows.append((first_window + int((stamp - start) // LENGTH),
                         names.index(service), event, stamp))
    return rows, dict(counts)


def prepare(dataset: str) -> Dict[str, Any]:
    root, names = ROOTS[dataset], SERVICES[dataset]
    hashes: Dict[str, str] = {}
    miner, templates, training = train_templates(root, hashes)
    audit = SpanAudit()
    pieces: Dict[str, List[np.ndarray]] = {
        k: [] for k in ("metrics", "traces", "labels", "run_id", "window_start", "event_id", "root_fault_group")
    }
    logs, runs = [], []
    first_window = 0
    for record_path in sorted((root / "data").glob("*.json")):
        record = json.loads(read_raw(record_path, root, hashes))
        run = record_path.name[:-5].replace(".fault-", ".")
        folder = root / "data" / run
        if not np.isfinite(record["start"]) or not np.isfinite(record["end"]):
            raise ValueError("Nonfinite recording endpoints")
        start, end = int(record["start"]) + RECORD_SHIFT, int(record["end"]) + RECORD_SHIFT
        starts = window_starts(start, end)
        faults = rounded_faults(record, dataset, run)
        if any(f["start"] < start or f["end_inclusive"] > end for f in faults):
            raise ValueError("Fault outside recording")
        metrics = metric_series(folder / "metrics", names, start, end, hashes, root)
        traces = trace_series(folder / "spans.json", names, start, end, audit, hashes, root)
        count = len(starts)
        used_seconds = count * LENGTH
        pieces["metrics"].append(metrics[:, :used_seconds].reshape(len(names), count, LENGTH, 7).transpose(1, 0, 2, 3))
        pieces["traces"].append(traces[:, :used_seconds].reshape(len(names), count, LENGTH, 2).transpose(1, 0, 2, 3))
        labels, event_ids, groups = window_labels(starts, faults)
        for key, value in (
            ("labels", labels), ("event_id", event_ids), ("root_fault_group", groups),
            ("window_start", starts), ("run_id", np.full(count, run)),
        ):
            pieces[key].append(value)
        rows, log_counts = log_rows(
            read_raw(folder / "logs.json", root, hashes), miner, templates,
            names, start, end, first_window)
        logs.extend(rows)
        runs.append({
            "run_id": run, "record_json": str(record_path.relative_to(root)),
            "record_start": start, "record_end_exclusive": end,
            "windows": count, "trailing_seconds": end - start - used_seconds,
            "faults": faults, "log_counts": log_counts,
        })
        first_window += count
        print("NATIVE_PREPARED_RUN {} {} windows={} used_logs={}".format(dataset, run, count, len(rows)), flush=True)
    if len(runs) != (4 if dataset == "SN" else 9):
        raise ValueError("Native recording count changed")
    arrays = {key: np.concatenate(values) for key, values in pieces.items()}
    table = np.asarray(logs, dtype=np.float64).reshape(-1, 4)
    order = np.lexsort((table[:, 3], table[:, 2], table[:, 1], table[:, 0]))
    table = table[order]
    arrays.update({
        "log_window": table[:, 0].astype(np.int64), "log_node": table[:, 1].astype(np.int64),
        "log_template": table[:, 2].astype(np.int64), "log_timestamp": table[:, 3],
    })
    metadata = {
        "dataset": dataset, "services": names, "edges": edges(dataset), "metrics": METRICS,
        "window_length": LENGTH, "stride": LENGTH, "windows": first_window,
        "templates": templates, "event_num": len(templates) + 1, "unseen_index": 0,
        "template_training": training, "runs": runs, "span_audit": audit.summary(),
        "input_sha256": hashes,
        "source": {
            "repository": "FeiGSSS/Eadro", "commit": COMMIT,
            "functions": ["Info.__get_edges", "parse_raw_logs.extract_log_template",
                          "parse_raw_traces.parse_spans", "single_process.logHaw",
                          "single_process.deal_traces", "align.get_basic"],
            "protocol_sha256": file_hash(OUT / "CALIBRATION_PROTOCOL.md"),
            "native_data_source_sha256": file_hash(Path(__file__)),
            "reused_profile_helpers_sha256": file_hash(OUT / "native_data_profile.py"),
        },
        "repairs": {
            "clock_shifts_seconds": {"records_metrics": RECORD_SHIFT, "spans": TRACE_SHIFT, "logs": LOG_SHIFT},
            "recording_clip": "[int(start)+16h,int(end)+16h)",
            "windows": "full length10 stride10; trailing seconds recorded, not selected by labels",
            "logs": "half-open window bounds; source matching, unseen bin, per-bin 1e-5 jitter, absent bins [0]",
            "trace": "source per-second mean duration seconds, channel1 zero; all duplicate occurrences retained",
            "labels": "any overlap with source int-rounded inclusive fault endpoints; ambiguous roots rejected",
            "normalization": "NONE; parent fits training-only scalers",
            "hawkes": "native HawkesADM4 defaults, relative horizon10, decay3, baseline_start=.2",
            "solver_rng": "default random uniform adjacency; NumPy seed42+window*N+node per fit",
            "memoization": "disabled",
        },
    }
    metadata["prepared_npz_sha256"] = save_arrays(INPUTS / (dataset + "_prepared.npz"), arrays)
    write_json(INPUTS / (dataset + "_metadata.json"), metadata)
    print("NATIVE_PREPARE_COMPLETE {} W={} N={} E={}".format(dataset, first_window, len(names), len(templates) + 1), flush=True)
    return metadata


def load_prepared(dataset: str) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    metadata = json.loads((INPUTS / (dataset + "_metadata.json")).read_text())
    path = INPUTS / (dataset + "_prepared.npz")
    if file_hash(path) != metadata["prepared_npz_sha256"]:
        raise ValueError("Prepared artifact hash mismatch")
    with np.load(path, allow_pickle=False) as source:
        arrays = {key: source[key] for key in source.files}
    return arrays, metadata


def make_knots(times: np.ndarray, ids: np.ndarray, start: float, event_num: int) -> List[np.ndarray]:
    if event_num < 1 or not np.isfinite(start) or len(times) != len(ids) or len(times) == 0:
        raise ValueError("Invalid or empty Hawkes event group")
    if not np.isfinite(times).all() or ids.dtype.kind not in "iu" or np.any(ids < 0) or np.any(ids >= event_num):
        raise ValueError("Invalid Hawkes timestamps/template indices")
    if np.any(times < start) or np.any(times >= start + LENGTH):
        raise ValueError("Hawkes events violate half-open window")
    knots = [np.array([0.0], dtype=np.float64) for _ in range(event_num)]
    for event in np.unique(ids):
        relative = np.sort(times[ids == event]) - start
        relative += np.arange(len(relative), dtype=np.float64) * 1e-5
        if np.any(relative >= LENGTH):
            raise ValueError("Source tie jitter exceeds relative horizon; no clipping applied")
        knots[int(event)] = relative
    return knots


def fit_hawkes(task: Tuple[int, int, List[np.ndarray], int]) -> Dict[str, Any]:
    window, node, knots, seed = task
    for knot in knots:
        if knot.ndim != 1 or len(knot) == 0 or not np.isfinite(knot).all() or np.any(knot < 0) or np.any(knot >= LENGTH) or np.any(np.diff(knot) <= 0):
            raise ValueError("Invalid relative Hawkes knots/horizon")
    np.random.seed(seed)
    begin = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = HawkesADM4(3)
        model.fit(knots, end_times=float(LENGTH), baseline_start=np.ones(len(knots)) * .2)
        baseline = np.asarray(model.baseline, dtype=np.float64)
    if baseline.shape != (len(knots),) or not np.isfinite(baseline).all() or np.any(baseline < 0):
        raise ValueError("Invalid native Hawkes baseline")
    return {
        "window": window, "node": node, "baseline": baseline,
        "seconds": time.perf_counter() - begin,
        "warnings": [str(w.message) for w in caught],
        "iterations": int(model.history.last_values["n_iter"]),
    }


def event_tasks(arrays: Dict[str, np.ndarray], node_num: int, event_num: int) -> List[Tuple[int, int, List[np.ndarray], int]]:
    windows, nodes = arrays["log_window"], arrays["log_node"]
    boundaries = np.r_[0, np.flatnonzero((np.diff(windows) != 0) | (np.diff(nodes) != 0)) + 1, len(windows)]
    tasks = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        if left == right:
            continue
        window, node = int(windows[left]), int(nodes[left])
        knots = make_knots(arrays["log_timestamp"][left:right], arrays["log_template"][left:right],
                           float(arrays["window_start"][window]), event_num)
        tasks.append((window, node, knots, SEED + window * node_num + node))
    return tasks


def calibrate(workers: int, sample_count: int) -> Dict[str, Any]:
    reports = {}
    for dataset in ("SN", "TT"):
        arrays, metadata = load_prepared(dataset)
        tasks = event_tasks(arrays, len(metadata["services"]), metadata["event_num"])
        event_counts = np.array([sum(len(k) for k in t[2]) for t in tasks])
        selected = sorted(set(np.linspace(0, len(tasks) - 1, sample_count, dtype=int).tolist()
                              + [int(event_counts.argmin()), int(event_counts.argmax())]))
        samples = []
        for index in selected:
            result = fit_hawkes(tasks[index])
            samples.append({k: v for k, v in result.items() if k != "baseline"})
            print("NATIVE_TIMING {} task={} E={} seconds={:.4f}".format(
                dataset, index, metadata["event_num"], result["seconds"]), flush=True)
        first = fit_hawkes(tasks[selected[0]])
        second = fit_hawkes(tasks[selected[0]])
        deterministic = np.array_equal(first["baseline"], second["baseline"])
        times = np.array([s["seconds"] for s in samples])
        reports[dataset] = {
            "windows": len(arrays["labels"]), "nodes": len(metadata["services"]),
            "event_num": metadata["event_num"], "required_fits": len(tasks),
            "sample_count": len(samples), "samples": samples,
            "mean_fit_seconds": float(times.mean()), "max_fit_seconds": float(times.max()),
            "estimated_serial_seconds": float(times.mean() * len(tasks)),
            "conservative_worker_seconds": float(times.max() * len(tasks) / workers * 1.5),
            "same_seed_exact_determinism": deterministic,
            "memoization": "disabled even after seed-controlled check",
            "native_defaults": {
                "decay": 3, "baseline_start": .2, "end_times": LENGTH,
                "C": 1000, "lasso_nuclear_ratio": .5, "max_iter": 50, "tol": 1e-5,
                "n_threads": 1, "rho": .1, "approx": 0, "em_max_iter": 30, "em_tol": None,
            },
        }
    conservative = sum(r["conservative_worker_seconds"] for r in reports.values())
    result = {
        "datasets": reports, "workers": workers,
        "thread_environment": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
        "conservative_full_build_seconds": conservative, "full_build_feasible": conservative < 1800,
    }
    write_json(INPUTS / "calibration.json", result)
    print("NATIVE_COST_ESTIMATE workers={} conservative_seconds={:.2f} feasible={}".format(
        workers, conservative, result["full_build_feasible"]), flush=True)
    return result


def build(dataset: str, workers: int) -> Dict[str, Any]:
    calibration = json.loads((INPUTS / "calibration.json").read_text())
    if not calibration["full_build_feasible"] or workers != calibration["workers"]:
        raise ValueError("Full build requires feasible measured budget and calibrated worker count")
    arrays, metadata = load_prepared(dataset)
    node_num, event_num = len(metadata["services"]), metadata["event_num"]
    tasks = event_tasks(arrays, node_num, event_num)
    log_features = np.zeros((len(arrays["labels"]), node_num, event_num), dtype=np.float64)
    counts: Counter = Counter()
    warning_counts: Counter = Counter()
    begin = time.perf_counter()
    context = __import__("multiprocessing").get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
        for index, result in enumerate(executor.map(fit_hawkes, tasks, chunksize=8)):
            log_features[result["window"], result["node"]] = result["baseline"]
            counts[str(result["iterations"])] += 1
            warning_counts.update(result["warnings"])
            if index % 500 == 0:
                print("NATIVE_BUILD_PROGRESS {} fits={}/{}".format(dataset, index + 1, len(tasks)), flush=True)
    final = {k: v for k, v in arrays.items() if not k.startswith("log_")}
    final["logs"] = log_features
    validate_arrays(final, node_num, event_num)
    dataset_dir = INPUTS / dataset
    dataset_dir.mkdir(exist_ok=True)
    path = dataset_dir / "raw.npz"
    raw = {k: final[k] for k in ("metrics", "traces", "logs", "labels")}
    contract_metadata = raw_metadata(final, metadata)
    contract_metadata["source"] = dict(
        metadata["source"], feature_build_source_sha256=file_hash(Path(__file__)))
    summary = {
        "status": "complete", "dataset": dataset, "fit_count": len(tasks),
        "workers": workers, "build_seconds": time.perf_counter() - begin,
        "warnings": dict(warning_counts), "solver_iteration_counts": dict(counts),
        "array_shapes": {k: list(v.shape) for k, v in raw.items()},
        "array_dtypes": {k: str(v.dtype) for k, v in raw.items()},
        "nonzero_cells": {k: int(np.count_nonzero(final[k])) for k in ("metrics", "traces", "logs")},
        "output_npz": dataset + "/raw.npz", "output_sha256": save_arrays(path, raw),
        "metadata_json": dataset + "/metadata.json",
    }
    contract_metadata["raw_npz_sha256"] = summary["output_sha256"]
    write_json(dataset_dir / "metadata.json", contract_metadata)
    summary["metadata_sha256"] = file_hash(dataset_dir / "metadata.json")
    write_json(INPUTS / (dataset + "_build.json"), summary)
    print("NATIVE_BUILD_COMPLETE {} seconds={:.2f} fits={}".format(
        dataset, summary["build_seconds"], len(tasks)), flush=True)
    return summary


def raw_metadata(arrays: Dict[str, np.ndarray], metadata: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(metadata)
    result.update({
        "system": metadata["dataset"],
        "edges": [[int(s), int(t)] for s, t in zip(*metadata["edges"])],
        "event_count": metadata["event_num"],
        "end_convention": "inclusive end=start+9 for integer samples; logs use [start,start+10)",
        "normalized": False,
        "window_count": len(arrays["labels"]),
        "windows": [{
            "run_id": str(arrays["run_id"][i]),
            "start": int(arrays["window_start"][i]),
            "end": int(arrays["window_start"][i]) + LENGTH - 1,
            "event_id": str(arrays["event_id"][i]) or None,
            "root_fault_group": str(arrays["root_fault_group"][i]) or None,
        } for i in range(len(arrays["labels"]))],
    })
    for i, row in enumerate(result["windows"]):
        if (arrays["labels"][i] == -1) != (row["event_id"] is None):
            raise ValueError("Normal/event provenance mismatch")
    return result


def validate_arrays(arrays: Dict[str, np.ndarray], nodes: int, events: int) -> None:
    labels = arrays["labels"]
    windows = len(labels)
    if labels.dtype.kind not in "iu" or np.any(labels < -1) or np.any(labels >= nodes):
        raise ValueError("Invalid root labels")
    for key, shape in (
        ("metrics", (windows, nodes, LENGTH, 7)),
        ("traces", (windows, nodes, LENGTH, 2)),
        ("logs", (windows, nodes, events)),
    ):
        if arrays[key].shape != shape or arrays[key].dtype.kind != "f" or not np.isfinite(arrays[key]).all():
            raise ValueError("Invalid " + key + " numeric contract")
    if np.count_nonzero(arrays["traces"][:, :, :, 1]):
        raise ValueError("Original second trace channel must stay zero")
    for key in ("run_id", "window_start", "event_id", "root_fault_group"):
        if arrays[key].shape != (windows,):
            raise ValueError("Invalid provenance shape: " + key)
    if arrays["window_start"].dtype.kind not in "iu":
        raise ValueError("Window start must be integer seconds")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "calibrate", "build"))
    parser.add_argument("--dataset", choices=("SN", "TT", "both"), default="both")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or not 2 <= args.samples <= 16:
        raise ValueError("Use modest 1..4 workers and bounded 2..16 sample positions")
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        if os.environ.get(key) != "1":
            raise ValueError("Set " + key + "=1 before process startup")
    if sys.version_info[:2] != (3, 8) or any(
        importlib.metadata.version(name) != version for name, version in
        (("numpy", "1.21.5"), ("pandas", "1.4.2"), ("tick", "0.7.0.1"), ("drain3", "0.9.11"))
    ):
        raise ValueError("Use exact parent-installed .venv-eadro environment")
    if args.stage == "calibrate":
        calibrate(args.workers, args.samples)
    else:
        for dataset in ("SN", "TT") if args.dataset == "both" else (args.dataset,):
            if args.stage == "prepare":
                prepare(dataset)
            else:
                build(dataset, args.workers)


if __name__ == "__main__":
    main()
