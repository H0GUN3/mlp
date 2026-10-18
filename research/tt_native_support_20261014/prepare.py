"""Selected-only TT preparation under the frozen local PROTOCOL.md."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import sys
import time
import traceback
from typing import Any, Dict

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NATIVE = HERE.parent / "native_reproduction_20261013"
ALLOWED = HERE.parent / "relationship_smoke_20261013" / "artifacts"
OUT = HERE / "artifacts"
# Frozen modules use sibling imports; fix resolution here, never in their source.
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(NATIVE))
import native_data as native
from research.method_mlp_20261013.features import original_split

ROW_KEYS = ("labels", "indices", "fold_ids", "event_ids", "episode_ids")
ARRAY_KEYS = set(ROW_KEYS) | {"metrics", "traces", "logs", "unique_count"}
THREAD_KEYS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def check_mask(indices, original_count):
    parts = original_split(original_count)
    allowed = set(parts["train"].tolist()) | set(parts["validation"].tolist())
    selected = set(indices.tolist())
    if indices.dtype != np.int64 or len(indices) != len(selected) or selected != allowed:
        raise ValueError("Selected indices must exactly cover original TRAIN+validation")
    protected = set(parts["test"].tolist()) | set(parts["unassigned"].tolist())
    if selected & protected:
        raise ValueError("Protected original index entered preparation")
    return {key: len(value) for key, value in parts.items()}


def check_selection(arrays, manifest, metadata):
    if manifest["system"] != "TT" or manifest["services"] != native.SERVICES["TT"]:
        raise ValueError("TT service order changed")
    rows = len(arrays["indices"])
    if rows != 4069 or len(manifest["windows"]) != rows:
        raise ValueError("Expected exactly 4069 selected rows")
    if arrays["values"].shape != (rows, 27, 10, 9) or arrays["values"].dtype != np.float64:
        raise ValueError("Allowed values schema changed")
    if not np.isfinite(arrays["values"]).all():
        raise ValueError("Nonfinite allowed values")
    for key in ROW_KEYS:
        expected = np.int64 if key in ROW_KEYS[:3] else np.dtype(str)
        if arrays[key].shape != (rows,):
            raise ValueError("Row metadata shape changed: " + key)
        if key in ROW_KEYS[:3] and arrays[key].dtype != expected:
            raise ValueError("Row integer dtype changed: " + key)
        if key in ROW_KEYS[3:] and arrays[key].dtype.kind != "U":
            raise ValueError("Row identity must be Unicode: " + key)
    original_count = sum(run["windows"] for run in metadata["runs"])
    if original_count != manifest["native_window_count"]:
        raise ValueError("Original metadata window count changed")
    split = check_mask(arrays["indices"], original_count)
    original_windows = [
        (run["run_id"], start)
        for run in metadata["runs"]
        for start in range(run["record_start"],
                           run["record_start"] + run["windows"] * 10, 10)
    ]
    faults = manifest["faults"]
    if len(faults) != 81 or set(arrays["event_ids"]) - {""} != set(faults):
        raise ValueError("Expected all 81 incident identities")
    support = {}
    for fold in range(3):
        events = {e for e, f in manifest["event_folds"].items() if f == fold}
        counts = Counter(faults[e]["service"] for e in events)
        if len(events) != 27 or counts != Counter({s: 1 for s in manifest["services"]}):
            raise ValueError("Incident fold support changed")
        mask = arrays["fold_ids"] == fold
        if set(arrays["event_ids"][mask]) - {""} != events:
            raise ValueError("Selected fold incident coverage changed")
        if set(arrays["episode_ids"][mask]) != events:
            raise ValueError("Selected episode fold coverage changed")
        support[str(fold)] = {
            "validation_incidents": 27, "train_incidents": 54,
            "validation_windows": int(mask.sum()), "train_windows": int((~mask).sum()),
            "validation_normal": int((mask & (arrays["labels"] == -1)).sum()),
        }
    for row, window in enumerate(manifest["windows"]):
        if (window["run_id"], window["start"]) != original_windows[int(arrays["indices"][row])]:
            raise ValueError("Original index/window alignment changed")
        if window["end"] != window["start"] + 9:
            raise ValueError("Window horizon changed")
        event, episode = str(arrays["event_ids"][row]), str(arrays["episode_ids"][row])
        if event != (window["event_id"] or "") or episode not in faults:
            raise ValueError("Selected identity metadata mismatch")
        if arrays["fold_ids"][row] != manifest["event_folds"][episode]:
            raise ValueError("Episode fold mismatch")
        label = int(arrays["labels"][row])
        if label != (faults[event]["root"] if event else -1):
            raise ValueError("Selected root label changed")
    if int((arrays["labels"] >= 0).sum()) != 3451:
        raise ValueError("Expected 3451 fault and 618 normal rows")
    return {"original_split": split, "fold_support": support,
            "protected_selected_rows": 0, "windows": rows, "incidents": 81}


class Router:
    """Map timestamps to selected manifest rows, without reading observation content."""
    def __init__(self, run, windows, rows):
        self.start = run["record_start"]
        self.end = run["record_end_exclusive"]
        self.lookup = {}
        for row in rows:
            window = windows[row]
            start = window["start"]
            if (window["run_id"] != run["run_id"] or start < self.start
                    or start + 10 > self.end or (start - self.start) % 10):
                raise ValueError("Selected window outside recording grid")
            if start in self.lookup:
                raise ValueError("Duplicate selected window")
            self.lookup[start] = row

    def route(self, stamp):
        if not np.isfinite(stamp):
            raise ValueError("Nonfinite timestamp")
        if not self.start <= stamp < self.end:
            return None
        start = self.start + int((stamp - self.start) // 10) * 10
        row = self.lookup.get(start)
        return None if row is None else (row, start)


def selected_logs(body, miner, templates, services, router):
    obj = json.loads(body)
    if not isinstance(obj, dict) or set(obj) != set(services):
        raise ValueError("Missing/extra log services")
    mapping = {template: index + 1 for index, template in enumerate(templates)}
    mapping["Unseen"] = 0
    groups = defaultdict(list)
    audit = Counter()
    for service, lines in obj.items():
        if not isinstance(lines, list):
            raise ValueError("Invalid log list")
        for line in lines:
            stamp = native.log_timestamp(line)
            audit["timestamp_routed_lines"] += 1
            routed = router.route(stamp)
            if routed is None:
                audit["unselected_lines_content_not_used"] += 1
                continue
            row, _ = routed
            match = miner.match(line)
            template = match.get_template() if match is not None else "Unseen"
            event = mapping.get(template, 0)
            groups[(row, services.index(service))].append((stamp, event))
            audit["selected_lines"] += 1
            audit["selected_unseen_lines"] += int(event == 0)
    return groups, dict(audit)


def selected_spans(traces, services, router, sums, counts, unique, identities):
    node_map = {service: node for node, service in enumerate(services)}
    audit = Counter()
    for trace in traces:
        for span in trace["spans"]:
            stamp_us = span.get("startTime")
            if type(stamp_us) is not int:
                raise ValueError("Invalid span routing timestamp")
            audit["timestamp_routed_occurrences"] += 1
            stamp = stamp_us // 1000000 + native.TRACE_SHIFT
            routed = router.route(stamp)
            if routed is None:
                audit["unselected_occurrences_content_not_used"] += 1
                continue
            row, start = routed
            identity = (span.get("traceID"), span.get("spanID"))
            if (not all(isinstance(value, str) and value for value in identity)
                    or identity[0] != trace.get("traceID")):
                raise ValueError("Invalid selected trace/span identity")
            duration = span.get("duration")
            if type(duration) is not int or duration < 0:
                raise ValueError("Invalid selected duration")
            process = trace["processes"].get(span.get("processID"))
            if process is None or process.get("serviceName") not in node_map:
                raise ValueError("Unknown selected span service")
            node = node_map[process["serviceName"]]
            signature = (row, node, stamp_us, duration)
            previous = identities.get(identity)
            if previous is not None:
                if previous != signature:
                    raise ValueError("Conflicting selected identity/service/time/duration")
                audit["duplicate_selected_occurrences"] += 1
            else:
                identities[identity] = signature
                unique[row, node] += 1
                audit["unique_selected_identities"] += 1
            # Native latency averages occurrences, not unique span identities.
            sums[row, node, stamp - start] += duration / 1000000.0
            counts[row, node, stamp - start] += 1
            audit["selected_occurrences"] += 1
    return dict(audit)


def hawkes_task(row, node, observations, arrays, windows, event_count):
    values = sorted(observations)
    times = np.asarray([value[0] for value in values], dtype=np.float64)
    ids = np.asarray([value[1] for value in values], dtype=np.int64)
    knots = native.make_knots(times, ids, float(windows[row]["start"]), event_count)
    return (row, node, knots, 42 + int(arrays["indices"][row]) * 27 + node)


def validate_output(arrays, metadata, allowed, manifest):
    rows, nodes, events = len(allowed["indices"]), 27, metadata["event_count"]
    if set(arrays) != ARRAY_KEYS:
        raise ValueError("Output keys differ from frozen schema")
    for key, shape in (("metrics", (rows, nodes, 10, 7)),
                       ("traces", (rows, nodes, 10, 2)),
                       ("logs", (rows, nodes, events))):
        value = arrays[key]
        if value.shape != shape or value.dtype != np.float64 or not np.isfinite(value).all():
            raise ValueError("Invalid output float array: " + key)
    if np.any(arrays["logs"] < 0) or np.any(arrays["traces"][..., 1] != 0):
        raise ValueError("Invalid logs or nonzero native trace channel1")
    if not np.array_equal(arrays["metrics"], allowed["values"][..., :7]):
        raise ValueError("Metric reuse changed")
    if not np.array_equal(arrays["traces"][..., 0], allowed["values"][..., 7]):
        raise ValueError("Native occurrence-weighted latency changed")
    unique = arrays["unique_count"]
    if unique.dtype != np.int64 or unique.shape != (rows, nodes) or np.any(unique < 0):
        raise ValueError("Invalid unique count")
    if np.any(unique > allowed["values"][..., 8].sum(axis=2)):
        raise ValueError("Unique count exceeds retained occurrences")
    for key in ROW_KEYS:
        if not np.array_equal(arrays[key], allowed[key]) or arrays[key].dtype != allowed[key].dtype:
            raise ValueError("Selected row order/identity changed: " + key)
    if (metadata["windows"] != manifest["windows"] or metadata["faults"] != manifest["faults"]
            or metadata["event_folds"] != manifest["event_folds"]
            or metadata["services"] != manifest["services"]):
        raise ValueError("Manifest metadata changed")
    if metadata["edges"] != [list(pair) for pair in zip(*native.edges("TT"))]:
        raise ValueError("Author graph pair schema changed")
    check_mask(arrays["indices"], manifest["native_window_count"])


def publish_npz(path, arrays, diagnostic):
    """An exclusive hard link publishes complete bytes and cannot replace a file."""
    partial = diagnostic / "TT.npz.partial"
    with partial.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    os.link(str(partial), str(path))
    return file_hash(path)


def prepare(workers=4):
    if workers not in range(1, 5):
        raise ValueError("Hawkes workers must be between one and four")
    if any(os.environ.get(key) != "1" for key in THREAD_KEYS) or not sys.dont_write_bytecode:
        raise ValueError("Require -B and OMP/MKL/OPENBLAS thread limits=1")
    OUT.mkdir(exist_ok=True)
    for name in ("TT.npz", "TT.json"):
        if (OUT / name).exists():
            raise FileExistsError("Refusing to overwrite final artifact: " + name)
    attempt = OUT / ("preparation_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    attempt.mkdir()
    started = time.perf_counter()
    log_stream = (attempt / "progress.log").open("x", buffering=1)

    def report(message):
        print(message, flush=True)
        log_stream.write(message + "\n")

    report("PREPARE_START workers={} utc={}".format(workers, datetime.now(timezone.utc).isoformat()))
    try:
        frozen_paths = [HERE / "PROTOCOL.md", ALLOWED / "TT.npz", ALLOWED / "TT.json",
                        NATIVE / "native_inputs" / "TT_metadata.json",
                        NATIVE / "native_data.py", NATIVE / "native_data_profile.py",
                        HERE.parent / "method_mlp_20261013" / "features.py",
                        NATIVE / "native_inputs" / "drain3.ini", Path(__file__)]
        before = {str(path): file_hash(path) for path in frozen_paths}
        manifest = json.loads((ALLOWED / "TT.json").read_text())
        prior = json.loads((NATIVE / "native_inputs" / "TT_metadata.json").read_text())
        if before[str(ALLOWED / "TT.npz")] != manifest["npz_sha256"]:
            raise ValueError("Allowed NPZ hash changed")
        if (before[str(NATIVE / "native_data.py")] != manifest["provenance"]["native_source"]["feature_build_source_sha256"]
                or before[str(NATIVE / "native_data_profile.py")] != prior["source"]["reused_profile_helpers_sha256"]):
            raise ValueError("Native pure-function sources changed")
        # Only the explicitly permitted selected bundle is loaded.
        with np.load(ALLOWED / "TT.npz", allow_pickle=False) as source:
            allowed = {key: source[key] for key in ("values",) + ROW_KEYS}
        selection = check_selection(allowed, manifest, prior)
        rows, nodes = 4069, 27
        metrics = allowed["values"][..., :7].copy()
        traces = np.zeros((rows, nodes, 10, 2), dtype=np.float64)
        traces[..., 0] = allowed["values"][..., 7]
        unique = np.zeros((rows, nodes), dtype=np.int64)
        sums = np.zeros((rows, nodes, 10), dtype=np.float64)
        counts = np.zeros((rows, nodes, 10), dtype=np.int64)
        hashes: Dict[str, str] = {}
        phase_started = time.perf_counter()
        miner, templates, training = native.train_templates(native.ROOTS["TT"], hashes)
        template_seconds = time.perf_counter() - phase_started
        if templates != prior["templates"] or training != prior["template_training"]:
            raise ValueError("Source-designated TRAIN reference/template provenance changed")
        for path, digest in hashes.items():
            if prior["input_sha256"].get(path) != digest:
                raise ValueError("Auxiliary normal TRAIN reference changed: " + path)
        event_count = len(templates) + 1
        report("TEMPLATE_TRAIN seconds={:.6f} reference_lines={} templates={} E={}".format(
            template_seconds, training["lines"], len(templates), event_count))
        identities, groups, run_audits = {}, {}, {}
        span_seconds = log_seconds = 0.0
        for run in prior["runs"]:
            selected = [row for row, window in enumerate(manifest["windows"])
                        if window["run_id"] == run["run_id"]]
            router = Router(run, manifest["windows"], selected)
            root = native.ROOTS["TT"]
            relative = "data/" + run["run_id"]
            log_path = root / relative / "logs.json"
            span_path = root / relative / "spans.json"
            phase_started = time.perf_counter()
            body = log_path.read_bytes()
            log_hash = hashlib.sha256(body).hexdigest()
            if log_hash != prior["input_sha256"][relative + "/logs.json"]:
                raise ValueError("Raw log hash changed")
            log_groups, log_audit = selected_logs(body, miner, templates, manifest["services"], router)
            groups.update(log_groups)
            hashes[relative + "/logs.json"] = log_hash
            elapsed_log = time.perf_counter() - phase_started
            log_seconds += elapsed_log
            phase_started = time.perf_counter()
            digest = hashlib.sha256()
            with span_path.open("rb") as stream:
                span_audit = selected_spans(native.json_array(stream, digest),
                                           manifest["services"], router, sums, counts, unique, identities)
            span_hash = digest.hexdigest()
            if (span_hash != prior["input_sha256"][relative + "/spans.json"]
                    or span_hash != manifest["raw_input_hashes"][relative + "/spans.json"]):
                raise ValueError("Raw span hash changed")
            hashes[relative + "/spans.json"] = span_hash
            elapsed_span = time.perf_counter() - phase_started
            span_seconds += elapsed_span
            reconstructed = np.zeros_like(sums[selected])
            np.divide(sums[selected], counts[selected], out=reconstructed, where=counts[selected] > 0)
            if (not np.array_equal(reconstructed, allowed["values"][selected, :, :, 7])
                    or not np.array_equal(counts[selected], allowed["values"][selected, :, :, 8])):
                raise ValueError("Selected duplicate-weighted latency/retained count mismatch")
            run_audits[run["run_id"]] = {
                "selected_windows": len(selected), "logs": log_audit, "spans": span_audit,
                "log_seconds": elapsed_log, "span_seconds": elapsed_span,
                "exact_retained_count_equality": True, "exact_latency_equality": True,
            }
            report("SELECTED_RUN {} windows={} logs={} spans={} unique={} log_seconds={:.4f} span_seconds={:.4f}".format(
                run["run_id"], len(selected), log_audit.get("selected_lines", 0),
                span_audit.get("selected_occurrences", 0), span_audit.get("unique_selected_identities", 0),
                elapsed_log, elapsed_span))
        logs = np.zeros((rows, nodes, event_count), dtype=np.float64)
        tasks = [hawkes_task(row, node, observations, allowed, manifest["windows"], event_count)
                 for (row, node), observations in sorted(groups.items())]
        iteration_counts, warning_counts = Counter(), Counter()
        fit_seconds = 0.0
        phase_started = time.perf_counter()
        report("HAWKES_START tasks={} workers={} max_iter=50 nonempty_only=true".format(len(tasks), workers))
        with (attempt / "solver.jsonl").open("x", buffering=1) as solver_stream:
            with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as executor:
                for number, result in enumerate(executor.map(native.fit_hawkes, tasks, chunksize=8), 1):
                    row, node = result["window"], result["node"]
                    logs[row, node] = result["baseline"]
                    fit_seconds += result["seconds"]
                    iteration_counts[str(result["iterations"])] += 1
                    warning_counts.update(result["warnings"])
                    audit: Dict[str, Any] = {k: v for k, v in result.items() if k != "baseline"}
                    audit["original_index"] = int(allowed["indices"][row])
                    audit["seed"] = 42 + audit["original_index"] * 27 + node
                    audit["finite_nonnegative"] = True
                    solver_stream.write(json.dumps(audit, allow_nan=False) + "\n")
                    if result["warnings"]:
                        report("HAWKES_WARNING row={} node={} warnings={}".format(row, node, result["warnings"]))
                    if number == 1 or number % 250 == 0 or number == len(tasks):
                        report("HAWKES_PROGRESS fits={}/{} wall_seconds={:.4f} iteration_counts={}".format(
                            number, len(tasks), time.perf_counter() - phase_started, dict(iteration_counts)))
        hawkes_seconds = time.perf_counter() - phase_started
        arrays = {key: allowed[key].copy() for key in ROW_KEYS}
        arrays.update(metrics=metrics, traces=traces, logs=logs, unique_count=unique)
        metadata = {
            "system": "TT", "services": manifest["services"], "event_count": event_count,
            "edges": [list(pair) for pair in zip(*native.edges("TT"))],
            "windows": manifest["windows"], "faults": manifest["faults"],
            "event_folds": manifest["event_folds"], "templates": templates,
            "input_hashes": dict(hashes, **{str(ALLOWED / "TT.npz"): before[str(ALLOWED / "TT.npz")],
                                         str(ALLOWED / "TT.json"): before[str(ALLOWED / "TT.json")]}),
            "source_hashes": {path: digest for path, digest in before.items()
                              if path not in (str(ALLOWED / "TT.npz"), str(ALLOWED / "TT.json"))},
            "normal_reference": dict(training, role="source-designated shared auxiliary normal TRAIN reference",
                                     evaluation_template_fit=False, sources_sha256={
                                         path: hashes[path] for path in training["sources"]}),
            "hawkes": {
                "function": "native_data.fit_hawkes", "decay": 3, "horizon": 10,
                "baseline_start": 0.2, "tie_jitter": 1e-5, "absent_bin": [0.0],
                "seed": "42+original_index*27+node", "max_iter": 50,
                "fit_count": len(tasks), "workers": workers,
                "zero_log_groups": rows * nodes - len(tasks),
                "iteration_counts": dict(iteration_counts), "warnings": dict(warning_counts),
                "cap_reached_count": sum(count for iteration, count in iteration_counts.items()
                                         if int(iteration) >= 50),
                "finite_nonnegative": True, "nonfinite_count": 0,
                "convergence_claimed": False, "solver_diagnostics": str(attempt / "solver.jsonl"),
            },
            "unique_count_audit": {
                "identity": "(traceID,spanID) per service/window",
                "conflicts": "identity/service/startTime/duration conflicts rejected within selected observations",
                "latency_weighting": "original duplicate occurrences retained",
                "unique_total": int(unique.sum()), "retained_occurrences": int(counts.sum()),
                "exact_retained_count_equality": True, "exact_latency_equality": True,
                "runs": run_audits,
            },
            "selection_validation": selection,
            "cost": {
                "template_train_seconds": template_seconds, "selected_log_seconds": log_seconds,
                "selected_span_seconds": span_seconds, "hawkes_wall_seconds": hawkes_seconds,
                "hawkes_summed_fit_seconds": fit_seconds,
                "parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "max_child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                "thread_environment": {key: os.environ[key] for key in THREAD_KEYS},
                "started_utc": (attempt.name.split("_", 1)[1]),
            },
            "test_evaluated": False, "native_observation_npz_loaded": False,
        }
        validate_output(arrays, metadata, allowed, manifest)
        if any(file_hash(Path(path)) != digest for path, digest in before.items()):
            raise ValueError("Input/source hash changed during preparation")
        output_hash = publish_npz(OUT / "TT.npz", arrays, attempt)
        with np.load(OUT / "TT.npz", allow_pickle=False) as saved:
            reopened = {key: saved[key] for key in saved.files}
        validate_output(reopened, metadata, allowed, manifest)
        if any(not np.array_equal(reopened[key], arrays[key]) for key in ARRAY_KEYS):
            raise ValueError("Published artifact round-trip mismatch")
        metadata["npz_sha256"] = output_hash
        metadata["cost"]["total_prepare_seconds"] = time.perf_counter() - started
        write_json(OUT / "TT.json", metadata)
        summary = {
            "status": "complete", "seconds": time.perf_counter() - started,
            "npz_sha256": output_hash, "json_sha256": file_hash(OUT / "TT.json"),
            "shapes": {key: list(value.shape) for key, value in arrays.items()},
            "dtypes": {key: str(value.dtype) for key, value in arrays.items()},
            "input_source_hashes_unchanged": True, "publication_round_trip_exact": True,
        }
        write_json(attempt / "success.json", summary)
        report("PREPARE_COMPLETE seconds={:.6f} sha256={} solver_caps={} warnings={}".format(
            summary["seconds"], output_hash, metadata["hawkes"]["cap_reached_count"], dict(warning_counts)))
        return summary
    except BaseException:
        write_json(attempt / "failure.json", {
            "status": "failed", "seconds": time.perf_counter() - started,
            "traceback": traceback.format_exc(),
        })
        report("PREPARE_FAILED seconds={:.6f}".format(time.perf_counter() - started))
        raise
    finally:
        log_stream.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    prepare(parser.parse_args().workers)
