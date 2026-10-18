"""Training-export-only native Drain/Hawkes cost measurement; never a feature build."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple
from unittest.mock import Mock, patch


OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
INPUTS = OUT / "rca_audit_inputs"
CONFIG = OUT / "native_inputs/drain3.ini"
SPLIT_SHA = "1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5"
THREADS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
DEADLINE = 120
READS: Counter = Counter()
REJECTED: Counter = Counter()
MISSING = object()


class InputsPending(RuntimeError):
    pass


def guarded_open(event: str, args: Tuple[Any, ...]) -> None:
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
        isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR |
                                                os.O_CREAT | os.O_TRUNC)))
    allowed_outputs = {OUT / ("rca_native_cost." + ext) for ext in ("json", "md")}
    allowed_outputs.update(INPUTS / s / "native_templates.json" for s in ("OB", "TT"))
    if writing:
        if path == Path(os.devnull):
            return  # dill probes file types on import; no persistent artifact.
        if path not in allowed_outputs:
            REJECTED[str(path)] += 1
            raise PermissionError("Write outside named cost/template outputs: " + str(path))
        return
    if path == BASE / "data" or BASE / "data" in path.parents:
        REJECTED[str(path)] += 1
        raise PermissionError("Protected raw read blocked: " + str(path))
    if OUT in path.parents:
        allowed = {
            OUT / name for name in (
                "rca_native_cost.py", "rca_schema_audit.py", "rca_schema_audit.json",
                "rca_schema_audit.md", "native_data.py", "native_data_profile.py",
                "native_data_test.py", "native_data_build.md",
            )
        } | allowed_outputs | {CONFIG}
        allowed.update(INPUTS / s / name for s in ("OB", "TT") for name in (
            "manifest.json", "normal_logs.jsonl", "profile_windows.json"))
        if path not in allowed:
            REJECTED[str(path)] += 1
            raise PermissionError("Unapproved research input read: " + str(path))
        READS[str(path.relative_to(BASE))] += 1


sys.addaudithook(guarded_open)
# dill queries the temp directory on import; avoid its create/unlink probe.
tempfile.tempdir = "/tmp"

import numpy as np
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import native_data as native


def artifact_digest(path: Path) -> Dict[str, Any]:
    digest = hashlib.sha256()
    lines = size = 0
    before = path.stat()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b"\n")
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns), "Artifact changed while hashing"
    return {"sha256": digest.hexdigest(), "bytes": size, "lines": lines}


def sha(path: Path) -> str:
    return artifact_digest(path)["sha256"]


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def save(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def environment() -> Dict[str, Any]:
    versions = {n: importlib.metadata.version(n) for n in (
        "numpy", "pandas", "tick", "drain3")}
    assert sys.version_info[:2] == (3, 8)
    assert Path(sys.prefix).resolve() == (BASE / ".venv-eadro").resolve()
    assert versions == {"numpy": "1.21.5", "pandas": "1.4.2",
                        "tick": "0.7.0.1", "drain3": "0.9.11"}
    assert all(os.environ.get(k) == "1" for k in THREADS)
    assert not os.environ.get("PYTHONPATH"), "No mixed Python paths"
    defaults = {
        k: v.default for k, v in inspect.signature(native.HawkesADM4).parameters.items()
        if v.default is not inspect.Parameter.empty
    }
    assert defaults == {
        "C": 1000.0, "lasso_nuclear_ratio": .5, "max_iter": 50, "tol": 1e-5,
        "n_threads": 1, "verbose": False, "print_every": 10, "record_every": 10,
        "rho": .1, "approx": 0, "em_max_iter": 30, "em_tol": None,
    }
    paths = {n: str(Path(inspect.getfile(c)).resolve()) for n, c in (
        ("HawkesADM4", native.HawkesADM4), ("TemplateMiner", TemplateMiner))}
    assert all((BASE / ".venv-eadro").resolve() in Path(p).parents for p in paths.values())
    return {"python": sys.version, "prefix": sys.prefix, "versions": versions,
            "estimator_paths": paths, "solver_defaults": defaults,
            "decay": 3, "baseline_start": .2, "end_times": 10,
            "threads": {k: os.environ[k] for k in THREADS}}


def new_miner() -> Tuple[Any, Dict[str, Any]]:
    body = CONFIG.read_bytes()
    original = body[:-1] if body.endswith(b"\n") else body
    blob = hashlib.sha1(("blob {}\0".format(len(original))).encode() + original).hexdigest()
    assert blob == "a391102e3e8c66ac125fad082e619a2b180e0dcf"
    config = TemplateMinerConfig()
    config.load(str(CONFIG))
    assert (config.drain_sim_th, config.drain_depth, config.drain_max_children,
            config.drain_max_clusters) == (.9, 4, 100, 1024)
    return TemplateMiner(config=config), {
        "sha256": hashlib.sha256(body).hexdigest(), "upstream_git_blob_sha1": blob,
        "sim_th": .9, "depth": 4, "max_children": 100, "max_clusters": 1024,
        "max_clusters_policy": "unchanged pinned Drain LRU; no post-mining truncation",
        "masking": "unchanged INI; TemplateMiner.add_log_message and match",
    }


def message_status(obj: Dict[str, Any]) -> Tuple[Optional[str], str]:
    value = obj.get("message", MISSING)
    if value is MISSING:
        return None, "missing_message"
    if value is None:
        return None, "null_message"
    if not isinstance(value, str):
        raise ValueError("Non-string, non-null message; no coercion permitted")
    return value, "observed_string"


def identifier(value: Any) -> Tuple[bool, str]:
    if value is not None and not isinstance(value, str):
        raise ValueError("Invalid raw service identifier")
    return value is not None, "" if value is None else value


def eligible(card: Dict[str, Any]) -> Iterator[int]:
    start, end = card["metric_range_inclusive"]
    injection = card["inject_time"]
    return (t for t in range(start, end - 8, 10)
            if t + 10 <= injection or t >= injection)


def closed_exports() -> Dict[str, Any]:
    paths = [INPUTS / s / name for s in ("OB", "TT") for name in (
        "manifest.json", "normal_logs.jsonl", "profile_windows.json")]
    paths += [OUT / "rca_schema_audit.json", OUT / "rca_schema_audit.md"]
    absent = [str(p.relative_to(BASE)) for p in paths if not p.is_file()]
    if absent:
        raise InputsPending("Both final manifests/audit/exports required: " + repr(absent))
    targets = {str(p.resolve()) for p in paths}
    checked = 0
    writers = []
    # Process descriptor metadata only; never open a descriptor's data target.
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            if not (proc / "comm").read_text().strip().startswith("python"):
                continue
            command = (proc / "cmdline").read_bytes().split(b"\0")
            if not any(b"rca_schema_audit" in arg for arg in command):
                continue
            descriptors = list((proc / "fd").iterdir())
            checked += 1
            for fd in descriptors:
                target = os.readlink(str(fd))
                if target not in targets:
                    continue
                info = (proc / "fdinfo" / fd.name).read_text()
                flag_line = next(line for line in info.splitlines() if line.startswith("flags:"))
                flags = int(flag_line.split()[1], 8)
                if (flags & os.O_ACCMODE) in (os.O_WRONLY, os.O_RDWR):
                    writers.append({"pid": int(proc.name), "artifact": target})
        except FileNotFoundError:
            continue  # Process/descriptor exited during inspection.
        except PermissionError as exc:
            raise InputsPending("Cannot certify exporter descriptor closure: " + str(exc))
    if writers:
        raise InputsPending("Exporter still has writable artifacts: " + repr(writers))
    return {
        "both_final_manifests_present": True, "writable_export_descriptors": writers,
        "exporter_python_processes_checked": checked,
        "closure_evidence": "same-user exporter Python /proc fd/fdinfo metadata before and after hashing; "
                            "exporter closes logs/profiles/manifests before final audit JSON",
        "paths": [str(p.relative_to(BASE)) for p in paths],
    }


def verify_exports() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    before_closed = closed_exports()
    audit = load(OUT / "rca_schema_audit.json")
    assert audit["split_sha256"] == SPLIT_SHA
    verified = {}
    measured_artifacts = {}
    for item in audit["outputs"]:
        path = BASE / item["path"]
        assert path.resolve() in {
            OUT / "rca_schema_audit.py", OUT / "rca_schema_audit.md",
            *(INPUTS / s / name for s in ("OB", "TT") for name in
              ("manifest.json", "normal_logs.jsonl", "profile_windows.json")),
        }
        actual = artifact_digest(path)
        assert all(actual[k] == item[k] for k in ("sha256", "bytes", "lines"))
        verified[item["path"]] = item["sha256"]
        measured_artifacts[item["path"]] = actual
    manifests = {}
    for system in ("OB", "TT"):
        manifest = load(INPUTS / system / "manifest.json")
        assert manifest == audit["systems"][system]
        assert len(manifest["train_cases"]) == 54
        normal = measured_artifacts[manifest["normal_output"]["path"]]
        assert normal["lines"] == manifest["normal_export_rows"] == manifest["normal_output"]["rows"]
        for case in manifest["train_cases"]:
            card = audit["cases"][case]
            assert card["partition"] == "train" and card["dataset"] == "RE2-" + system
        profiles = load(INPUTS / system / "profile_windows.json")
        assert profiles["split_sha256"] == SPLIT_SHA
        assert profiles["seconds"] == profiles["stride"] == 10
        assert len(profiles["samples"]) == manifest["profile_sample_count"] <= 12
        for sample in profiles["samples"]:
            card = audit["cases"][sample["case"]]
            assert sample["case"] in manifest["train_cases"] and card["partition"] == "train"
            assert sample["end"] == sample["start"] + 10
            assert sample["start"] in eligible(card)
            period = "nominal_normal" if sample["end"] <= card["inject_time"] else "nominal_faulty"
            assert sample["period"] == period
            assert len(sample["events"]) == len(sample["source_rows"]) > 0
            assert all(type(e["timestamp"]) is int and
                       sample["start"] <= e["timestamp"] < sample["end"]
                       for e in sample["events"])
            statuses = Counter(message_status(e)[1] for e in sample["events"])
            assert statuses["observed_string"] == sample["string_messages"]
            assert statuses["null_message"] == sample["null_messages"]
        manifests[system] = manifest
    verified["audit_json_sha256"] = sha(OUT / "rca_schema_audit.json")
    after_closed = closed_exports()
    print("EXPORT_HASHES_PASS", flush=True)
    return audit, {"input_hashes": verified, "manifests": manifests,
                   "measured_export_hash_bytes_line_counts": measured_artifacts,
                   "closed_exports_before_hashing": before_closed,
                   "closed_exports_after_hashing": after_closed}


def mine(system: str, audit: Dict[str, Any], manifest: Dict[str, Any]) -> Tuple[Any, List[str], Dict[str, Any]]:
    miner, config = new_miner()
    count: Counter = Counter()
    case_counts: Counter = Counter()
    case_hashes: Any = defaultdict(hashlib.sha256)
    last = None
    begin = time.perf_counter()
    with (INPUTS / system / "normal_logs.jsonl").open("rb") as stream:
        for line in stream:
            row = json.loads(line)
            assert set(row) <= {"case", "service", "timestamp", "message"}
            assert {"case", "service", "timestamp"} <= set(row)
            card = audit["cases"][row["case"]]
            assert row["case"] in manifest["train_cases"] and card["partition"] == "train"
            assert card["dataset"] == "RE2-" + system and type(row["timestamp"]) is int
            start, end = card["metric_range_inclusive"]
            assert start <= row["timestamp"] <= end and row["timestamp"] < card["inject_time"]
            key = row["case"], identifier(row["service"]), row["timestamp"]
            assert last is None or last <= key
            last = key
            case_counts[row["case"]] += 1
            case_hashes[row["case"]].update(line)
            message, status = message_status(row)
            count["rows"] += 1
            count[status] += 1
            count["null_service_rows"] += row["service"] is None
            if message is not None:
                miner.add_log_message(message)
            if count["rows"] % 100000 == 0:
                print("MINING {} rows={} clusters={} seconds={:.1f}".format(
                    system, count["rows"], len(miner.drain.clusters),
                    time.perf_counter() - begin), flush=True)
    seconds = time.perf_counter() - begin
    assert count["rows"] == manifest["normal_export_rows"]
    for case in manifest["train_cases"]:
        card = audit["cases"][case]
        if "log_export" in card:
            assert case_counts[case] == card["log_export"]["exported_normal_rows"]
            assert case_hashes[case].hexdigest() == card["log_export"]["exported_original_objects_sha256"]
        else:
            assert card["failures"] and case_counts[case] == 0
    clusters = list(miner.drain.clusters)
    templates = [c.get_template() for c in clusters]
    metadata = {
        "system": system, "split_sha256": SPLIT_SHA, "counts": dict(count),
        "mining_wall_seconds_including_export_decode_validation": seconds,
        "supervisor_peak_rss_bytes_after_mining": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "config": config, "training_order": manifest["normal_export_order"],
        "all_available_normal_train_messages_mined": count["observed_string"],
        "unavailable_policy": "null/missing message never mined or matched; no invented strings",
        "null_service_policy": "observed strings mined; unidentified service fits unavailable",
        "template_order": "native Drain final cluster enumeration; duplicate texts retained",
        "templates": templates, "E": len(templates) + 1, "unseen_index": 0,
        "clusters": [{"cluster_id": c.cluster_id, "size": c.size,
                      "template": c.get_template()} for c in clusters],
        "clusters_created": miner.drain.clusters_counter,
        "intrinsic_pinned_lru_evictions": miner.drain.clusters_counter - len(clusters),
        "normal_export_sha256": manifest["normal_output"]["sha256"],
    }
    return miner, templates, metadata


def memory_estimates(manifest: Dict[str, Any], events: int) -> Dict[str, Any]:
    matrix = 8 * events * events
    return {
        "E": events, "single_dense_float64_E_squared_bytes": matrix,
        "seven_source_simultaneous_dense_matrices_bytes": 7 * matrix,
        "two_fits_seven_matrix_payload_bytes": 14 * matrix,
        "solver_scope": "matrix payload lower bounds, not RSS ceilings; excludes C++ event buffers, "
                        "SVD/LAPACK workspace, temporaries, Python, worker imports and miner",
        "array_estimates": [
            {"scope": scope, **entry,
             "log_float64_bytes_W_N_E": entry["log_float64_bytes_per_template_W_N_E"] * events}
            for scope, key in (("TRAIN", "TRAIN_array_estimates"),
                               ("VALIDATION_schema_only", "VALIDATION_array_estimates_schema_derived_only"))
            for entry in manifest[key]["estimates"]
        ],
        "final36_memory": "unknown; no final-case inputs or dimensions consulted",
    }


def bridge(sample: Dict[str, Any], miner: Any, templates: List[str]) -> Tuple[Optional[List[np.ndarray]], Dict[str, Any]]:
    mapping = {template: index + 1 for index, template in enumerate(templates)}
    mapping["Unseen"] = 0
    times, ids = [], []
    counts: Counter = Counter()
    for event in sample["events"]:
        message, status = message_status(event)
        counts[status] += 1
        if message is None:
            continue
        match = miner.match(message)
        template = match.get_template() if match is not None else "Unseen"
        event_id = mapping.get(template, 0)
        times.append(event["timestamp"])
        ids.append(event_id)
        counts["unseen_observed_strings"] += event_id == 0
    info: Dict[str, Any] = {
        "source_events": len(sample["events"]), "message_counts": dict(counts),
        "E": len(templates) + 1, "start": sample["start"], "end": sample["end"],
    }
    if counts["null_message"] or counts["missing_message"] or sample["service"] is None or not times:
        info["status"] = "unavailable"
        info["reason"] = "missing message or unidentified service; no partial observed-group fit"
        return None, info
    knots = native.make_knots(np.asarray(times, dtype=np.float64),
                              np.asarray(ids, dtype=np.int64),
                              float(sample["start"]), len(templates) + 1)
    info.update({
        "status": "ready", "occupied_observed_bins": len(set(ids)),
        "dummy_zero_bins": len(templates) + 1 - len(set(ids)),
        "total_solver_knots_including_dummy_bins": sum(len(k) for k in knots),
        "relative_knot_min": min(float(k.min()) for k in knots),
        "relative_knot_max": max(float(k.max()) for k in knots),
        "native_jitter": 1e-5, "relative_horizon": 10,
    })
    return knots, info


def coordinates(system: str, audit: Dict[str, Any], manifest: Dict[str, Any],
                sample: Dict[str, Any]) -> Dict[str, Any]:
    nodes = manifest["canonical_vocabulary"]
    window = 0
    found = False
    for case in manifest["train_cases"]:
        card = audit["cases"][case]
        if "metric_range_inclusive" not in card:
            continue
        for start in eligible(card):
            if case == sample["case"] and start == sample["start"]:
                found = True
                break
            window += 1
        if found:
            break
    assert found and sample["service"] in nodes
    node = nodes.index(sample["service"])
    return {"window": window, "node": node, "node_num": len(nodes),
            "seed": native.SEED + window * len(nodes) + node,
            "policy": "native 42+window*N+node; TRAIN case/eligible-window order, "
                      "unchanged audited canonical vocabulary/order; no candidate changes",
            "system": system}


def worker() -> None:
    environment()
    payload = json.load(sys.stdin)
    knots = [np.asarray(k, dtype=np.float64) for k in payload["knots"]]
    c = payload["coordinates"]
    print("FIT_STARTED " + json.dumps({"E": len(knots), "seed": c["seed"]}), flush=True)
    result = native.fit_hawkes((c["window"], c["node"], knots, c["seed"]))
    baseline = result.pop("baseline")
    result.update({
        "baseline_shape": list(baseline.shape), "finite_baseline": bool(np.isfinite(baseline).all()),
        "baseline_min": float(baseline.min()), "baseline_max": float(baseline.max()),
        "baseline_sha256": hashlib.sha256(baseline.tobytes()).hexdigest(),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "solver_limit_reached": result["iterations"] == 50,
    })
    print("FIT_RESULT " + json.dumps(result, allow_nan=False), flush=True)


def bounded_fit(knots: List[np.ndarray], coords: Dict[str, Any]) -> Dict[str, Any]:
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker"]
    payload = json.dumps({"knots": [k.tolist() for k in knots], "coordinates": coords}, allow_nan=False)
    begin = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(payload, timeout=DEADLINE)
        elapsed = time.perf_counter() - begin
        result: Dict[str, Any] = {"status": "completed" if process.returncode == 0 else "failed",
                                 "returncode": process.returncode,
                                 "process_wall_seconds": elapsed, "deadline_seconds": DEADLINE,
                                 "stderr": stderr, "stdout": stdout}
        if process.returncode == 0:
            lines = [line[len("FIT_RESULT "):] for line in stdout.splitlines()
                     if line.startswith("FIT_RESULT ")]
            assert len(lines) == 1
            result["fit"] = json.loads(lines[0])
            assert result["fit"]["finite_baseline"]
            assert result["fit"]["baseline_shape"] == [len(knots)]
        return result
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        elapsed = time.perf_counter() - begin
        return {
            "status": "timeout", "returncode": process.returncode,
            "deadline_seconds": DEADLINE, "process_wall_seconds": elapsed,
            "censored_process_wall_lower_bound_seconds": DEADLINE,
            "completed_fit_seconds": None, "stdout": stdout, "stderr": stderr,
            "warnings_limit": "stderr preserved; native catch_warnings buffer unavailable "
                              "when killed before fit_hawkes returns",
            "censor_scope": "120s subprocess wall includes imports/initialization; not 120s pure solver CPU",
        }


def measure(system: str, audit: Dict[str, Any], manifest: Dict[str, Any],
            miner: Any, templates: List[str]) -> List[Dict[str, Any]]:
    samples = load(INPUTS / system / "profile_windows.json")["samples"]
    results = []
    attempted = 0
    first_two = []
    stop = False
    for index, sample in enumerate(samples):
        identity = {k: sample[k] for k in ("case", "service", "start", "end", "period", "selected_for")}
        statuses = Counter(message_status(e)[1] for e in sample["events"])
        if statuses["null_message"] or statuses["missing_message"] or sample["service"] is None:
            results.append({
                "sample_index": index, **identity, "E": len(templates) + 1,
                "source_events": len(sample["events"]), "message_counts": dict(statuses),
                "status": "unavailable",
                "reason": "missing message or unidentified service; no partial observed-group fit",
            })
            print("SAMPLE {} index={} E={} status=unavailable".format(
                system, index, len(templates) + 1), flush=True)
            continue
        if stop:
            results.append({"sample_index": index, **identity,
                            "status": "not_run_first_two_timeouts", "deadline_seconds": DEADLINE})
            continue
        knots, info = bridge(sample, miner, templates)
        entry: Dict[str, Any] = {"sample_index": index, **identity, **info}
        if knots is not None:
            coords = coordinates(system, audit, manifest, sample)
            entry.update(bounded_fit(knots, coords))
            entry["coordinates"] = coords
            attempted += 1
            if attempted <= 2:
                first_two.append(entry["status"])
            stop = attempted == 2 and first_two == ["timeout", "timeout"]
        results.append(entry)
        print("SAMPLE {} index={} E={} status={} wall={}".format(
            system, index, len(templates) + 1, entry["status"],
            entry.get("process_wall_seconds")), flush=True)
    return results


def projections(manifest: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    complete = [r["fit"]["seconds"] for r in results if r["status"] == "completed"]
    timed_out = [r for r in results if r["status"] == "timeout"]
    usable = manifest["train_drain_usable_nonempty_fit_count"]
    raw = manifest["train_nonempty_window_raw_service_fit_count"]
    result: Dict[str, Any] = {
        "audited_TRAIN_nonempty_raw_service_fit_count": raw,
        "audited_TRAIN_identifiable_at_least_one_string_fit_count": usable,
        "unavailable_or_partially_observed_group_limit":
            "audit string-usable count may include partially null groups; full native count "
            "cannot be certified without all-group message completeness",
        "completed_samples": len(complete), "timeout_samples": len(timed_out),
        "unavailable_samples": sum(r["status"] == "unavailable" for r in results),
        "not_run_samples": sum(r["status"] == "not_run_first_two_timeouts" for r in results),
        "projection_scope": "TRAIN stride10 only; selected profiles are purposive, "
                            "not a random sample; no statistical confidence interval or final36 projection",
    }
    if complete:
        mean = sum(complete) / len(complete)
        result.update({
            "completed_mean_fit_seconds": mean, "completed_max_fit_seconds": max(complete),
            "TRAIN_mean_serial_seconds_estimate": mean * usable,
            "TRAIN_mean_two_worker_ideal_seconds_estimate": mean * usable / 2,
            "TRAIN_max_sample_serial_scenario_seconds": max(complete) * usable,
            "TRAIN_max_sample_two_worker_ideal_scenario_seconds": max(complete) * usable / 2,
            "completed_only_bias": "excludes censored samples; not an upper bound, promise or all-data estimate",
        })
    if timed_out:
        result.update({
            "measured_censored_process_lower_bound_each_seconds": DEADLINE,
            "TRAIN_all_groups_at_deadline_serial_scenario_seconds": usable * DEADLINE,
            "TRAIN_all_groups_at_deadline_two_worker_ideal_scenario_seconds": usable * DEADLINE / 2,
            "deadline_scenario_limit": "conditional scenario, NOT a lower bound for all TRAIN groups; "
                                       "only timed-out samples have measured lower bounds",
        })
    return result


def report_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# RCA native Drain/Hawkes feasibility",
        "",
        "Only hash-verified guarded TRAIN exports were read. No RCA raw files, validation "
        "messages, final36 files, full feature arrays or models were read/built. Frozen split "
        "SHA256: `" + SPLIT_SHA + "`.",
        "",
        "## Actual dimensions and measurements",
        "|System|normal rows / observed strings|templates / E|Drain wall seconds|sample completed / timeout / unavailable / stopped|",
        "|---|---:|---:|---:|---:|",
    ]
    for s, value in report["systems"].items():
        m, p = value["templates"], value["projection"]
        lines.append("|{}|{} / {}|{} / {}|{:.3f}|{} / {} / {} / {}|".format(
            s, m["counts"]["rows"], m["counts"].get("observed_string", 0),
            len(m["templates"]), m["E"], m["mining_wall_seconds_including_export_decode_validation"],
            p["completed_samples"], p["timeout_samples"], p["unavailable_samples"], p["not_run_samples"]))
    lines += [
        "",
        "Every available nominal-normal TRAIN string was mined in exported case/service/time/source-row "
        "order; empty strings are observed messages, not missing. Null/missing messages are unavailable, "
        "never invented or assigned unseen events; partially missing profile groups are not fitted. "
        "Unidentified services remain unavailable for fits. Native final cluster enumeration and duplicate "
        "template texts are retained. The pinned INI's intrinsic 1024-cluster LRU is unchanged; no extra "
        "truncation, subsampling, rate/count surrogate or configuration change.",
    ]
    for s, value in report["systems"].items():
        m, mem, p = value["templates"], value["memory"], value["projection"]
        lines.append("- **{}:** {} clusters created, {} intrinsic evictions; missing/null normal messages "
                     "{} / {}. Single E×E float64 matrix {:.2f} MiB; seven simultaneous source matrix "
                     "payloads {:.2f} MiB/fit ({:.2f} MiB for two), excluding SVD/C++/Python overhead. "
                     "Supervisor cumulative peak RSS after mining {:.2f} MiB.".format(
                         s, m["clusters_created"], m["intrinsic_pinned_lru_evictions"],
                         m["counts"].get("missing_message", 0), m["counts"].get("null_message", 0),
                         mem["single_dense_float64_E_squared_bytes"] / 2**20,
                         mem["seven_source_simultaneous_dense_matrices_bytes"] / 2**20,
                         mem["two_fits_seven_matrix_payload_bytes"] / 2**20,
                         m["supervisor_peak_rss_bytes_after_mining"] / 2**20))
        if p["completed_samples"]:
            lines.append("- **{} completed fits:** mean {:.6f}s, max {:.6f}s; measured iteration counts {}; "
                         "peak worker RSS {:.2f} MiB. TRAIN {} string-usable groups imply {:.2f}h serial / "
                         "{:.2f}h ideal two-worker mean-fit estimate; max-sample scenario {:.2f}h serial. "
                         "These are completed-only projections, not upper bounds.".format(
                             s, p["completed_mean_fit_seconds"], p["completed_max_fit_seconds"],
                             [r["fit"]["iterations"] for r in value["samples"] if r["status"] == "completed"],
                             max(r["fit"]["peak_rss_bytes"] for r in value["samples"]
                                 if r["status"] == "completed") / 2**20,
                             p["audited_TRAIN_identifiable_at_least_one_string_fit_count"],
                             p["TRAIN_mean_serial_seconds_estimate"] / 3600,
                             p["TRAIN_mean_two_worker_ideal_seconds_estimate"] / 3600,
                             p["TRAIN_max_sample_serial_scenario_seconds"] / 3600))
        if p["timeout_samples"]:
            lines.append("- **{} timeouts:** each attempt exceeded the exact 120s subprocess wall deadline; "
                         "censored lower bounds, not completed fit timings or 120s solver CPU. "
                         "First two timeouts stop remaining system fits. Conditional all-groups-at-deadline "
                         "scenario: {:.2f}h serial / {:.2f}h ideal two-worker, NOT a measured bound on every "
                         "group.".format(s, p["TRAIN_all_groups_at_deadline_serial_scenario_seconds"] / 3600,
                                         p["TRAIN_all_groups_at_deadline_two_worker_ideal_scenario_seconds"] / 3600))
        arrays = [a for a in mem["array_estimates"] if a["scope"] == "TRAIN" and
                  a["candidate_basis"] == "current_canonical"]
        for a in arrays:
            lines.append("- **{} canonical audit footprint:** W={}, N={}, E={}: dense log payload {:.3f} GiB; "
                         "metric float32 {:.3f} GiB; trace float32 {:.3f} GiB. Exact TRAIN/validation-schema "
                         "array estimates for all audit candidate bases are in JSON; none is adopted.".format(
                             s, a["W"], a["N"], m["E"], a["log_float64_bytes_W_N_E"] / 2**30,
                             a["metric_float32_bytes_W_N_10_8"] / 2**30,
                             a["trace_float32_bytes_W_N_10_2"] / 2**30))
    lines += [
        "",
        "## Estimator, limits and verification",
        "Python3.8, tick0.7.0.1, drain3==0.9.11, NumPy1.21.5; one unmixed `.venv-eadro`. "
        "Pinned INI upstream blob `a391102e3e8c66ac125fad082e619a2b180e0dcf` verified. "
        "Native `make_knots`/`fit_hawkes` reused: source match/unseen index0, absent-bin [0], "
        "per-bin 1e−5 jitter, relative horizon10, HawkesADM4(decay3), baseline initialization.2. "
        "Defaults: C1000, lasso/nuclear.5, max_iter50, tol1e−5, rho.1, em_max_iter30, "
        "em_tol=None, approx0, n_threads1. NumPy seed42+window*N+node uses deterministic TRAIN "
        "case/window and unchanged audited canonical service coordinates. "
        "OMP/MKL/OPENBLAS=1; measurement is sequential (≤2 concurrent fits).",
        "Dimensions/memory were written before any actual sample fit. Completed baselines are finite, "
        "nonnegative and E-dimensional; knot bounds are relative [0,10). Reaching iteration50 does not "
        "establish convergence. Warnings, failures, worker output and timeout censoring remain in JSON; "
        "native in-flight captured warnings cannot be recovered after SIGKILL.",
        "Confidence is limited by purposive ≤12 exported profiles, intrinsic LRU, dummy-bin overhead, "
        "unknown/partially null groups, host contention and solver convergence. Full TRAIN cost uses "
        "audited actual nonempty/string-usable group counts; no statistical confidence interval, "
        "full matching/I/O timing or final36 time/memory claim. Mining wall includes JSON decoding "
        "and row verification; matrix payloads are not peak-memory ceilings. Input resolution, labels, "
        "candidates and scientific mechanism remain unchanged.",
    ]
    text = "\n".join(lines) + "\n"
    assert len(text.split()) <= 900
    return text


def self_test() -> Dict[str, str]:
    assert message_status({}) == (None, "missing_message")
    assert message_status({"message": None}) == (None, "null_message")
    assert message_status({"message": ""}) == ("", "observed_string")
    try:
        message_status({"message": 17})
        raise AssertionError("Numeric message accepted")
    except ValueError:
        pass
    miner, _ = new_miner()
    miner.add_log_message("observed alpha")
    templates = [c.get_template() for c in miner.drain.clusters]
    sample: Dict[str, Any] = {"service": "s", "start": 100, "end": 110,
                             "events": [{"timestamp": 100, "message": "observed alpha"},
                                        {"timestamp": 100, "message": "unseen distinct beta"}]}
    knots, info = bridge(sample, miner, templates)
    assert knots is not None and info["message_counts"]["unseen_observed_strings"] == 1
    np.testing.assert_array_equal(knots[0], [0])
    np.testing.assert_array_equal(knots[1], [0])
    for unavailable in ({}, {"message": None}):
        partial = dict(sample, events=sample["events"] + [{"timestamp": 101, **unavailable}])
        assert bridge(partial, miner, templates)[0] is None
    assert bridge(dict(sample, service=None), miner, templates)[0] is None
    assert len(miner.drain.clusters) == len(templates)
    repeated = dict(sample, events=[sample["events"][0], sample["events"][0]])
    repeat_knots, _ = bridge(repeated, miner, templates)
    assert repeat_knots is not None
    np.testing.assert_array_equal(repeat_knots[1], [0, 1e-5])
    before = sum(READS.values())
    try:
        (BASE / "data/rcaeval/forbidden/logs.parquet").open("rb")
        raise AssertionError("Raw boundary accepted")
    except PermissionError:
        pass
    assert sum(READS.values()) == before
    with patch.object(Path, "is_file", return_value=False):
        try:
            closed_exports()
            raise AssertionError("Incomplete artifacts considered ready")
        except InputsPending:
            pass
    assert sum(READS.values()) == before
    card = {"metric_range_inclusive": [100, 129], "inject_time": 120}
    coords = coordinates("fixture", {"cases": {"case": card}}, {
        "train_cases": ["case"], "canonical_vocabulary": ["a", "s", "z"]},
        {"case": "case", "service": "s", "start": 110})
    assert coords["window"] == 1 and coords["node"] == 1 and coords["seed"] == 46
    fake = Mock(pid=123, returncode=-9)
    fake.communicate.side_effect = [subprocess.TimeoutExpired("fixture", 120),
                                    ("FIT_STARTED fixture\n", "fixture warning\n")]
    with patch.object(subprocess, "Popen", return_value=fake), patch.object(os, "killpg") as kill:
        limited = bounded_fit(knots, coords)
        kill.assert_called_once_with(123, signal.SIGKILL)
        assert fake.communicate.call_args_list[0].kwargs["timeout"] == 120
        assert limited["status"] == "timeout" and limited["completed_fit_seconds"] is None
        assert limited["stderr"] == "fixture warning\n"
    profile = dict(sample, case="case", period="nominal_normal", selected_for=["fixture"])
    nullable = dict(profile, events=[{"timestamp": 100, "message": None}])
    with patch.dict(globals(), load=Mock(return_value={"samples": [profile, profile, nullable, profile]})):
        with patch.dict(globals(), bounded_fit=Mock(return_value={"status": "timeout"})) as patched:
            stopped = measure("fixture", {"cases": {"case": card}}, {
                "train_cases": ["case"], "canonical_vocabulary": ["a", "s", "z"]},
                miner, templates)
            assert patched["bounded_fit"].call_count == 2
            assert [r["status"] for r in stopped] == [
                "timeout", "timeout", "unavailable", "not_run_first_two_timeouts"]
    return {"nullable_missing_empty_numeric_messages": "pass",
            "native_mask_match_unseen_no_miner_updates": "pass",
            "partial_group_unavailable_and_null_service": "pass",
            "native_relative_origin_dummy_bins_jitter": "pass",
            "protected_raw_denied_before_open": "pass",
            "unchanged_canonical_seed_coordinates": "pass",
            "mocked_deadline_kill_reap_stderr_censoring": "pass",
            "nullable_unavailability_after_first_two_timeouts": "pass",
            "both_manifest_pending_gate_no_partial_file_reads": "pass"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--ready", action="store_true")
    args = parser.parse_args()
    env = environment()
    if args.worker:
        worker()
        return
    if args.self_test:
        print("SELF_TEST_PASS " + json.dumps(self_test()), flush=True)
        return
    if args.ready:
        _, provenance = verify_exports()
        print("ARTIFACT_READY " + json.dumps({
            s: {"normal_rows": m["normal_export_rows"], "profiles": m["profile_sample_count"]}
            for s, m in provenance["manifests"].items()}), flush=True)
        return
    if args.verify:
        audit, provenance = verify_exports()
        report = load(OUT / "rca_native_cost.json")
        assert provenance["input_hashes"] == report["provenance"]["input_hashes"]
        for system, value in report["systems"].items():
            templates = load(INPUTS / system / "native_templates.json")
            assert templates["E"] == len(templates["templates"]) + 1
            assert templates["normal_export_sha256"] == audit["systems"][system]["normal_output"]["sha256"]
            for sample in value["samples"]:
                if sample["status"] == "completed":
                    assert sample["fit"]["finite_baseline"] and sample["fit"]["baseline_min"] >= 0
                    assert sample["fit"]["baseline_shape"] == [templates["E"]]
                    assert sample["relative_horizon"] == 10
                    assert 0 <= sample["relative_knot_min"] <= sample["relative_knot_max"] < 10
                elif sample["status"] == "timeout":
                    assert sample["deadline_seconds"] == 120 and sample["completed_fit_seconds"] is None
            assert sha(INPUTS / system / "native_templates.json") == value["template_artifact_sha256"]
        assert report["verification"]["protected_raw_successful_reads"] == 0
        assert len((OUT / "rca_native_cost.md").read_text().split()) <= 900
        print("COST_VERIFY_PASS hashes versions dimensions finite horizons timeouts", flush=True)
        return
    if any((OUT / ("rca_native_cost." + ext)).exists() for ext in ("json", "md")):
        raise FileExistsError("Cost outputs already exist; verify rather than silently refit")
    tests = self_test()
    audit, provenance = verify_exports()
    report: Dict[str, Any] = {
        "status": "mining", "environment": env, "systems": {},
        "provenance": provenance,
        "native_source_sha256": sha(OUT / "native_data.py"),
        "cost_source_sha256": sha(Path(__file__)),
        "verification": {"tests": tests, "protected_raw_successful_reads": 0,
                         "validation_message_reads": 0, "final36_reads": 0,
                         "prior_check_failures": [
                             "Initial environment probe failed from shell quoting; corrected probe passed.",
                             "Initial root LSP used non-native environment and could not resolve drain3; "
                             "explicit native Python3.8 Pyright passed with zero diagnostics.",
                             "Initial bridge test blocked dill's /dev/null import probe; "
                             "non-persistent /dev/null exception added; no raw access occurred.",
                             "Second bridge import hit tempfile's create/unlink directory probe; "
                             "tempfile.tempdir fixed to /tmp to avoid any temporary file writes.",
                             "First partial mining run cancelled before artifacts or sample fits "
                             "to classify nullable profiles as unavailable even after the timeout stop.",
                             "Second partial mining run stopped on parent readiness correction; "
                             "both closed-manifest gates and independent pre-mining line counts added. "
                             "Node launch/completion statuses are never used as readiness evidence.",
                             "Descriptor readiness initially blocked an unrelated protected sd-pam; "
                             "closure checks scoped to same-user exporter Python processes, "
                             "without changing accounts or permissions.",
                         ]},
    }
    # Persist both systems' dimensions before launching any actual Hawkes sample.
    learned = {}
    for system in ("OB", "TT"):
        manifest = provenance["manifests"][system]
        miner, templates, metadata = mine(system, audit, manifest)
        memory = memory_estimates(manifest, len(templates) + 1)
        metadata["memory_before_fits"] = memory
        save(INPUTS / system / "native_templates.json", metadata)
        learned[system] = miner, templates
        report["systems"][system] = {
            "templates": metadata, "memory": memory, "samples": [],
            "template_artifact_sha256": sha(INPUTS / system / "native_templates.json"),
        }
        save(OUT / "rca_native_cost.json", report)
        print("DIMENSIONS_BEFORE_FITS {} E={} matrix_bytes={}".format(
            system, len(templates) + 1, memory["single_dense_float64_E_squared_bytes"]), flush=True)
    report["status"] = "sampling"
    for system in ("OB", "TT"):
        manifest = provenance["manifests"][system]
        miner, templates = learned[system]
        results = measure(system, audit, manifest, miner, templates)
        report["systems"][system]["samples"] = results
        report["systems"][system]["projection"] = projections(manifest, results)
        save(OUT / "rca_native_cost.json", report)
    report["status"] = "measured_or_bounded"
    report["verification"]["allowed_research_open_ledger"] = dict(READS)
    report["verification"]["rejected_open_requests"] = dict(REJECTED)
    report["verification"]["full_feature_builds"] = report["verification"]["model_runs"] = 0
    markdown = report_markdown(report)
    with (OUT / "rca_native_cost.md").open("w", encoding="utf-8") as stream:
        stream.write(markdown)
    report["report_sha256"] = sha(OUT / "rca_native_cost.md")
    report["report_words"] = len(markdown.split())
    save(OUT / "rca_native_cost.json", report)
    print("COST_PASS report_words={} json_sha256={}".format(
        report["report_words"], sha(OUT / "rca_native_cost.json")), flush=True)


if __name__ == "__main__":
    try:
        main()
    except InputsPending as pending:
        print("INPUTS_PENDING " + str(pending), file=sys.stderr, flush=True)
        sys.exit(75)
