"""One bounded TRAIN-only benchmark of the installed, unchanged HawkesADM4."""
import ast
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from typing import Any, Dict, List, Tuple
import warnings

sys.dont_write_bytecode = True
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")
for variable in THREADS:
    os.environ[variable] = "1"

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = HERE.parents[2]
ART = PROJECT / "artifacts"
FITS = HERE / "fits_recovery"
REPORT = HERE / "benchmark_recovery.json"
tempfile.tempdir = str(FITS)  # Avoid dill's temporary-directory write probes outside owned output.
PYTHON = REPO / ".venv-eadro/bin/python"
NATIVE = REPO / "research/native_reproduction_20261013/native_data.py"
RUNTIME_EXAMPLE = PROJECT / "cost_preservation/probes/native_runtime.py"
TICK = REPO / ".venv-eadro/lib/python3.8/site-packages/tick"
NATIVE_SHA = "05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986"
PINS = {
    HERE / "mapping.json": "a9bf14fd115d55c040c1d7a30b376411f722ef6ef12f3fa3eaf7f12d4f9b006a",
    HERE / "selection.json": "6b7be4278e61e6752aa8c65b15b7d58b76f227ee7738e4be33788b4e9af399e9",
    HERE / "coverage.json": "78a76b05fa54cd9b9a3cc92e15adb8e7d86f7ef39dd8a33ff1a1d10d35fd7181",
    HERE / "MAPPING.md": "711c3e41334efa1c798ee47ef6606afd9aae670841db59b7ff156ef32ff41b46",
    PROJECT / "split.json": "3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2",
    ART / "preflight.json": "264f5ca84c1fefa1855773478e97a71a4e314d4f71aad04af0ec68cde6caf101",
    ART / "templates.json": "8fbdd0cf419679294fe645cea1d3c66f81484ff1be7d59f6deb330d73b2b6b53",
    ART / "drain.snapshot": "70c77a932c150cf47488a7fd3b1a0efc9abfde11856c30090c7584e1925b3072",
    NATIVE: NATIVE_SHA,
    RUNTIME_EXAMPLE: "3e0c6056ffc131adf9cd39afb582c0ccb0859f4a9d27597d432bc1014e38ab87",
    TICK / "hawkes/inference/hawkes_adm4.py":
        "0546b62509c79736e570b4caee78c4766daead25020001bdf13ae963eb0b9ecb",
    TICK / "prox/prox_nuclear.py":
        "6ac610883ef0d06c759433fdbfb365e9106d8cd3cb906211fa4c0dc8f6de6da4",
}
CONTRACT = dict(event_count=257, seed=42, decay=3, end_times=10,
                baseline_start=0.2, adjacency_start="native uniform(0.5,0.9), 257x257",
                C=1000, lasso_nuclear_ratio=0.5, max_iter=50, tol=1e-5,
                n_threads=1, verbose=False, print_every=10, record_every=10,
                rho=0.1, approx=0, em_max_iter=30, em_tol=None,
                admm_start="native zeros", solver="installed original HawkesADM4")
LIMITS = dict(workers=4, threads=1, positions=140, per_fit_seconds=60,
              batch_seconds=900, aggregation_and_benchmark_seconds=1800)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    require(path == REPORT or FITS in path.parents,
            "Output outside declared artifacts")
    require(not path.is_symlink(), "Symlink output")
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def save_arrays(path, **arrays):
    require(FITS in path.parents and not path.is_symlink(), "Unsafe array output")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return digest(path)


def code_hashes():
    return {str(HERE / name): digest(HERE / name)
            for name in ("benchmark.py", "test_benchmark.py")}


def native_functions(solver=None):
    """Compile the two pinned function ASTs unchanged, without module main/imports."""
    require(digest(NATIVE) == NATIVE_SHA, "Native source pin changed")
    tree = ast.parse(NATIVE.read_text(), filename=str(NATIVE))
    names = {"make_knots", "fit_hawkes"}
    nodes: List[ast.stmt] = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    require({n.name for n in nodes if isinstance(n, ast.FunctionDef)} == names,
            "Native functions missing")
    namespace: Dict[str, Any] = dict(np=np, time=time, warnings=warnings,
                                    LENGTH=10, HawkesADM4=solver,
                                    Any=Any, Dict=Dict, List=List, Tuple=Tuple)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(NATIVE), "exec"), namespace)
    return namespace


def original_solver():
    """Reuse read-only import routing, not its pandas/main guards or any solver copy."""
    require(digest(RUNTIME_EXAMPLE) == PINS[RUNTIME_EXAMPLE], "Runtime loader changed")
    tree = ast.parse(RUNTIME_EXAMPLE.read_text(), filename=str(RUNTIME_EXAMPLE))
    nodes = [n for n in tree.body if not isinstance(n, ast.If)]
    namespace: Dict[str, Any] = {"__name__": "bounded_native_imports"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(RUNTIME_EXAMPLE), "exec"),
         namespace)
    return namespace["HawkesADM4"]


def knot_key(knots):
    value = hashlib.sha256(b"RE2-native-relative10-seed42-v1")
    for knot in knots:
        value.update(np.asarray([len(knot)], dtype="<i8").tobytes())
        value.update(np.asarray(knot, dtype="<f8").tobytes())
    return value.hexdigest()


def event_lookup(templates, mapping):
    old = templates["cluster_id_to_feature"]
    new = mapping["cluster_id_to_feature"]
    require(len(old) == 1024 and set(map(int, old.values())) == set(range(1, 1025)),
            "Frozen template feature map")
    require(len(new) == 256 and set(new.values()) == set(range(1, 257)),
            "Frozen reduced feature map")
    lookup = np.zeros(1025, dtype=np.int64)
    for cluster, feature in old.items():
        lookup[int(feature)] = new.get(cluster, 0)
    return lookup


def group(times, events, start, lookup, make_knots) -> Tuple[Dict[str, Any], Any]:
    remapped = lookup[events]
    counts = dict(raw_count=len(events), kept_count=int(np.count_nonzero(remapped)),
                  pooled_count=int(np.count_nonzero((events != 0) & (remapped == 0))),
                  unknown_count=int(np.count_nonzero(events == 0)))
    require(counts["raw_count"] == sum(counts[k] for k in (
        "kept_count", "pooled_count", "unknown_count")), "Group conservation")
    if not len(events):
        return dict(counts, empty=True, key=None, knot_error=None), None
    try:
        knots = make_knots(times, remapped, float(start), 257)
    except ValueError as error:
        return dict(counts, empty=False, key=None, knot_error=str(error)), None
    return dict(counts, empty=False, key=knot_key(knots), knot_error=None), knots


def install_guard(allowed):
    allowed = {Path(p).resolve() for p in allowed}
    stats = dict(denied=[], input_opens=[], writes=[])
    runtime_roots = [REPO / ".venv-eadro", Path(sys.base_prefix), REPO / ".python-native"]

    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        if path == Path("/dev/null"):
            return  # dill probes stream types on this nonpersistent device during tick import.
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+")) or
                   (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)))
        output = FITS in path.parents or path == REPORT
        runtime = (any(root == path or root in path.parents for root in runtime_roots) or
                   Path("/usr/share/zoneinfo") in path.parents or
                   path == Path("/etc/localtime").resolve())
        permitted = output if writing else (
            output or runtime or path in allowed or path == Path("/dev/null"))
        if writing:
            permitted = permitted and isinstance(flags, int) and bool(flags & os.O_EXCL)
        if not permitted:
            stats["denied"].append(str(path))
            raise PermissionError("Outside bounded benchmark allowlist: " + str(path))
        if path in allowed and not writing:
            stats["input_opens"].append(str(path))
        if writing:
            stats["writes"].append(str(path))
    sys.addaudithook(audit)
    return stats


def handoff():
    for path, expected in PINS.items():
        require(digest(path) == expected, "Frozen handoff/source hash: " + str(path))
    mapping, selection, coverage = [load(HERE / name) for name in (
        "mapping.json", "selection.json", "coverage.json")]
    completion = load(HERE / "mapping_evidence/completion.json")
    verification = load(HERE / "mapping_evidence/verification.json")
    require(completion["status"] == verification["status"] == "PASS" and
            completion["exits"]["aggregation"] == 0 and
            completion["validation_read_boundary_enforced"], "Failed mapping boundary")
    for name in ("mapping", "selection", "coverage"):
        require(completion[name + "_sha256"] == digest(HERE / (name + ".json")) and
                verification["artifact_hashes"][name + ".json"] == digest(
                    HERE / (name + ".json")), "Mapping evidence hash")
    require(selection["mapping_sha256"] == coverage["mapping_sha256"] ==
            digest(HERE / "mapping.json") and coverage["selection_sha256"] ==
            digest(HERE / "selection.json"), "Frozen dependency hashes")
    require(mapping["dimensions"] == 257 and mapping["frequency_source_cases"] == 48 and
            mapping["frequency_validation_reads"] == 0 and coverage["row_conservation"],
            "Mapping/coverage boundary")
    split, pre, templates = [load(path) for path in (
        PROJECT / "split.json", ART / "preflight.json", ART / "templates.json")]
    rows = {r["case"]: r for r in split["cases"]}
    require(len(rows) == 72 and len(split["protected_cases"]) == 18 and
            sum(r["partition"] == "train" for r in rows.values()) == 48 and
            sum(r["partition"] == "validation" for r in rows.values()) == 24 and
            pre["status"] == "PREFLIGHT_PASS" and
            pre["case_counts"] == {"train": 48, "validation": 24}, "48/24/protected boundary")
    services = pre["services"]
    require(len(services) == 14 and services == selection["services"] == coverage["services"]
            and selection["missing"] == [] and selection["windows"] == 10 and
            len(selection["records"]) == 10 and selection["cases"] == 5,
            "Incomplete selected windows/services")
    intervals = {r["case"]: r for r in pre["intervals"]}
    selected_cases = {r["case"] for r in selection["records"]}
    require(len(selected_cases) == 5 and all(rows[c]["partition"] == "train"
            for c in selected_cases), "Non-TRAIN selected case")
    rank = lambda text: hashlib.sha256(text.encode()).hexdigest()
    roots = sorted({r["root_cause_service"] for r in rows.values() if r["partition"] == "train"})
    expected = []
    for root in roots:
        candidates = [c for c in rows if rows[c]["partition"] == "train" and
                      rows[c]["root_cause_service"] == root]
        case = min(candidates, key=lambda c: (rank("re2-ob-257-cost-v1|case|" + c), c))
        iv = intervals[case]
        starts = range(iv["start"], iv["end_exclusive"], 10)
        for fault in (False, True):
            eligible = [s for s in starts if (s + 9 >= rows[case]["inject_time"]) == fault]
            require(eligible, "Missing selection layer")
            start = min(eligible, key=lambda s: (
                rank("re2-ob-257-cost-v1|window|" + case + "|" + str(s)), s))
            expected.append(dict(case=case, partition="train", root=root, fault=fault,
                                 start=start, window_index=(start - iv["start"]) // 10,
                                 services=services))
    require(expected == selection["records"], "Preselection changed; no resampling")
    for row in coverage["records"]:
        require(row["total"] == row["kept"] + row["newly_pooled"] + row["old_unknown"],
                "Coverage conservation failed")
    return mapping, selection, coverage, pre, templates


def aggregate(mapping, selection, pre, templates, hashes):
    lookup = event_lookup(templates, mapping)
    make_knots = native_functions()["make_knots"]
    positions, unique = [], {}
    intervals = {r["case"]: r for r in pre["intervals"]}
    for case in sorted({r["case"] for r in selection["records"]}):
        path = ART / "matched" / (case + ".npz")
        meta = load(path.with_suffix(".json"))
        require(meta["case"] == case and meta["partition"] == "train", "TRAIN cache boundary")
        for field in ("split_sha256", "snapshot_sha256", "policy_sha256", "input_binding_sha256"):
            require(meta[field] == mapping[field], "Cache provenance " + field)
        require(meta["sha256"] == digest(path) == hashes[str(path)], "Selected cache hash")
        provenance = next(r for r in pre["verified_cases"] if r["case"] == case)
        require(meta["stage1_log_sha256"] == provenance["stage1_member_hashes"]["logs.jsonl.gz"],
                "Selected cache source")
        with np.load(path, allow_pickle=False) as archive:
            require(set(archive.files) == {"times", "nodes", "events"}, "Cache schema")
            times, nodes, events = [archive[k] for k in ("times", "nodes", "events")]
        require(all(x.ndim == 1 and x.dtype == np.int64 for x in (times, nodes, events))
                and len(times) == len(nodes) == len(events) == meta["rows"], "Cache row shape")
        iv = intervals[case]
        require(bool(np.all((times >= iv["start"]) & (times < iv["end_exclusive"]))) and
                bool(np.all((nodes >= 0) & (nodes < 14))) and
                bool(np.all((events >= 0) & (events <= 1024))), "Cache data bounds")
        for window in [r for r in selection["records"] if r["case"] == case]:
            for node, service in enumerate(selection["services"]):
                mask = (times >= window["start"]) & (times < window["start"] + 10) & (nodes == node)
                stamps, ids = times[mask], events[mask]
                record, knots = group(stamps, ids, window["start"], lookup, make_knots)
                record.update(case=case, partition="train", window_index=window["window_index"],
                              start=window["start"], fault=window["fault"], node=node,
                              service=service, reused=False)
                if knots is not None:
                    key = record["key"]
                    record["reused"] = key in unique
                    if key in unique:
                        require(all(np.array_equal(a, b) for a, b in
                                    zip(knots, unique[key])), "Knot hash collision")
                    else:
                        unique[key] = knots
                        save(FITS / ("input-" + key + ".json"),
                             dict(key=key, knots=[k.tolist() for k in knots]))
                if record["empty"]:
                    record["zero_baseline"] = [0.0] * 257
                record["mapped_rows_sha256"] = hashlib.sha256(
                    np.column_stack((stamps, lookup[ids])).astype("<i8").tobytes()).hexdigest()
                positions.append(record)
    require(len(positions) == 140 and len(unique) <= 140, "Position/fit cap")
    return positions, list(unique)


def fit_accounting(iterations, timed_out=False):
    return dict(iterations=iterations, cap50_reached=iterations >= 50 if iterations is not None else None,
                timed_out=timed_out,
                convergence="not asserted; native recorded iteration only")


def worker(key):
    started = time.perf_counter()
    manifest = load(FITS / "manifest.json")
    require(key in manifest["keys"], "Worker input not preselected")
    guard = install_guard(manifest["immutable_before"])
    for path, expected in manifest["source_hashes"].items():
        require(digest(path) == expected, "Worker source changed")
    input_path = FITS / ("input-" + key + ".json")
    require(digest(input_path) == manifest["input_hashes"][key], "Worker input digest")
    knots = [np.asarray(k, dtype=np.float64) for k in load(input_path)["knots"]]
    require(len(knots) == 257 and knot_key(knots) == key, "Worker knot dimension/key")
    record: Dict[str, Any] = dict(
        key=key, pid=os.getpid(), status="exception", baseline_sha256=None,
        baseline_finite=None, baseline_nonnegative=None, warnings=[],
        exception=None, solver_seconds=None, **fit_accounting(None))
    solver_started = None

    def terminate(signum, frame):
        raise TimeoutError("Per-fit or batch wall deadline")

    signal.signal(signal.SIGTERM, terminate)
    try:
        HawkesADM4 = original_solver()
        require(HawkesADM4.__module__ == "tick.hawkes.inference.hawkes_adm4",
                "Original installed solver required")
        native = native_functions(HawkesADM4)
        solver_started = time.perf_counter()
        result = native["fit_hawkes"]((0, 0, knots, 42))
        baseline = result.pop("baseline")
        record.update(status="ok", solver_seconds=result["seconds"], warnings=result["warnings"],
                      baseline_finite=bool(np.isfinite(baseline).all()),
                      baseline_nonnegative=bool(np.all(baseline >= 0)),
                      baseline_shape=list(baseline.shape), **fit_accounting(result["iterations"]))
        record["baseline_sha256"] = save_arrays(FITS / ("baseline-" + key + ".npz"),
                                                baseline=baseline)
    except Exception as error:
        record.update(exception=type(error).__name__ + ": " + str(error),
                      traceback=traceback.format_exc(),
                      status="timeout" if isinstance(error, TimeoutError) else "exception",
                      **fit_accounting(None, isinstance(error, TimeoutError)))
        if solver_started is not None:
            record["solver_seconds"] = time.perf_counter() - solver_started
        tb = error.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_name == "fit_hawkes":
                local = tb.tb_frame.f_locals
                record["warnings"] = [str(w.message) for w in local.get("caught", [])]
                model = local.get("model")
                if model is not None:
                    record["last_recorded_iteration"] = model.history.last_values.get("n_iter")
            tb = tb.tb_next
    runtime = runtime_hashes()
    record.update(contract=CONTRACT, native_source_sha256=NATIVE_SHA,
                  source_hashes=manifest["source_hashes"], input_sha256=manifest["input_hashes"][key],
                  runtime_hashes=runtime, python=sys.version, numpy=np.__version__,
                  threads={v: os.environ[v] for v in THREADS},
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  worker_seconds=time.perf_counter() - started, read_guard=guard,
                  transitive_pandas_loaded="pandas" in sys.modules, direct_pandas_operations=0)
    save(FITS / ("result-" + key + ".json"), record)
    return 0 if record["status"] == "ok" else 2


def runtime_hashes():
    runtime = {}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if name.startswith(("tick", "numpy", "scipy")) and isinstance(filename, str):
            path = Path(filename).resolve()
            if path.is_file():
                runtime[str(path)] = digest(path)
    return runtime


def runtime_check():
    """Check installed defaults and hash loaded modules; never call fit."""
    guard = install_guard(list(PINS) + [
        HERE / "benchmark.py", HERE / "test_benchmark.py",
        HERE / "mapping_evidence/completion.json", HERE / "mapping_evidence/verification.json"])
    solver = original_solver()
    require(solver.__module__ == "tick.hawkes.inference.hawkes_adm4", "Installed ADM4")
    model = solver(3)
    actual = {name: getattr(model, name) for name in (
        "decay", "C", "lasso_nuclear_ratio", "max_iter", "tol", "n_threads",
        "verbose", "print_every", "record_every", "rho", "approx", "em_max_iter", "em_tol")}
    require(all(actual[k] == CONTRACT[k] for k in actual), "Original default parameters changed")
    require(sys.version_info[:2] == (3, 8) and np.__version__ == "1.21.5", "Pinned runtime")
    handoff()
    save(FITS / "runtime.json", dict(defaults=actual, runtime_hashes=runtime_hashes(),
                                   source_hashes=code_hashes(), read_guard=guard,
                                   handoff_preflight="PASS",
                                   transitive_pandas_loaded="pandas" in sys.modules,
                                   real_fits=0, direct_pandas_operations=0))
    print("ORIGINAL_RUNTIME_DEFAULTS_PASS real_fits=0", flush=True)
    return 0


def available_timeout(now, deadline):
    return max(0.0, min(60.0, deadline - now - 2.0))


def launch(key, deadline):
    started = time.perf_counter()
    limit = available_timeout(started, deadline)
    if limit <= 0:
        return dict(key=key, status="unrun_budget", exit_code=None, process_seconds=0.0)
    command = [str(PYTHON), "-B", str(HERE / "benchmark.py"), "worker", key]
    save(FITS / ("launch-" + key + ".json"),
         dict(key=key, command=command, hard_process_seconds=limit, started_unix=time.time()))
    soft = threading.Event()
    hard = threading.Event()
    with (FITS / ("stdout-" + key + ".log")).open("xb") as out, (
            FITS / ("stderr-" + key + ".log")).open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)

        def stop(sig, event):
            try:
                os.killpg(proc.pid, sig)
                event.set()
            except ProcessLookupError:
                pass

        remaining = max(0.001, started + limit - time.perf_counter())
        soft_timer = threading.Timer(max(0.001, remaining - 0.5), stop, (signal.SIGTERM, soft))
        hard_timer = threading.Timer(remaining, stop, (signal.SIGKILL, hard))
        soft_timer.start()
        hard_timer.start()
        try:
            _, status, usage = os.wait4(proc.pid, 0)
            proc.returncode = (os.WEXITSTATUS(status) if os.WIFEXITED(status)
                               else -os.WTERMSIG(status))
        finally:
            soft_timer.cancel()
            hard_timer.cancel()
            soft_timer.join()
            hard_timer.join()
    elapsed = time.perf_counter() - started
    result_path = FITS / ("result-" + key + ".json")
    result = load(result_path) if result_path.exists() else {}
    timed_out = soft.is_set() or hard.is_set() or result.get("timed_out", False)
    status = ("timeout" if timed_out else
              "ok" if proc.returncode == 0 and result.get("status") == "ok" else "exception")
    record = dict(key=key, status=status, pid=proc.pid, exit_code=proc.returncode,
                  process_seconds=elapsed, hard_process_seconds=limit, timed_out=timed_out,
                  hard_killed=hard.is_set(), peak_rss_kib=usage.ru_maxrss,
                  user_seconds=usage.ru_utime, system_seconds=usage.ru_stime,
                  result_sha256=digest(result_path) if result else None,
                  solver_seconds=result.get("solver_seconds"),
                  iterations=result.get("iterations"), cap50_reached=result.get("cap50_reached"),
                  warnings=result.get("warnings"), exception=result.get("exception"),
                  iterations_note=("unknown after hard kill" if not result else
                                   "native history; null when fit did not return"))
    save(FITS / ("completion-" + key + ".json"), record)
    return record


def run():
    started = time.perf_counter()
    FITS.mkdir(exist_ok=True)
    save(FITS / "RUN_ONCE.json", dict(pid=os.getpid(), started_unix=time.time(),
                                    source_hashes=code_hashes(), limits=LIMITS))
    require(sys.version_info[:2] == (3, 8) and np.__version__ == "1.21.5",
            "Existing pinned Python/NumPy runtime required")
    checks = load(FITS / "checks.json")
    require(checks["passed"] and checks["source_hashes"] == code_hashes(),
            "Tests and explicit Pyright must pass on this source before run")
    mapping, selection, coverage, pre, templates = handoff()
    allowed = dict(PINS)
    for path, expected in load(FITS / "runtime.json")["runtime_hashes"].items():
        require(digest(path) == expected, "Installed runtime changed after checks")
        allowed[Path(path)] = expected
    for name in ("BRIEF.md", "mapping_evidence/completion.json",
                 "mapping_evidence/verification.json", "benchmark.py", "test_benchmark.py"):
        allowed[HERE / name] = digest(HERE / name)
    for case in sorted({r["case"] for r in selection["records"]}):
        for suffix in (".json", ".npz"):
            rel = "matched/" + case + suffix
            path = ART / rel
            require(mapping["source_hashes"][rel] == coverage["source_hashes"][rel] ==
                    digest(path), "Frozen selected cache pair changed")
            allowed[path] = mapping["source_hashes"][rel]
    guard = install_guard(allowed)
    before = {str(p): digest(p) for p in allowed}
    positions, keys = aggregate(mapping, selection, pre, templates, before)
    aggregation_seconds = time.perf_counter() - started
    previous_aggregation = coverage["aggregation_seconds"]
    require(aggregation_seconds + previous_aggregation < 1800 - 900,
            "Aggregation leaves insufficient fixed benchmark budget")
    source_hashes = {str(p): digest(p) for p in (NATIVE, RUNTIME_EXAMPLE, HERE / "benchmark.py",
                     HERE / "test_benchmark.py", TICK / "hawkes/inference/hawkes_adm4.py",
                     TICK / "prox/prox_nuclear.py")}
    manifest = dict(contract=CONTRACT, limits=LIMITS, positions=positions, keys=keys,
                    immutable_before=before, source_hashes=source_hashes,
                    mapping_sha256=digest(HERE / "mapping.json"),
                    selection_sha256=digest(HERE / "selection.json"),
                    input_hashes={key: digest(FITS / ("input-" + key + ".json")) for key in keys},
                    aggregation_seconds=aggregation_seconds)
    save(FITS / "manifest.json", manifest)
    batch_start = time.perf_counter()
    deadline = batch_start + 900
    completed, unrun = [], []
    pending_keys = iter(keys)
    with ThreadPoolExecutor(max_workers=4) as pool:
        active = {}
        exhausted = False
        while active or not exhausted:
            while len(active) < 4 and not exhausted:
                key = next(pending_keys, None)
                if key is None:
                    exhausted = True
                elif available_timeout(time.perf_counter(), deadline) <= 0:
                    unrun.append(key)
                else:
                    active[pool.submit(launch, key, deadline)] = key
            if active:
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    key = active.pop(future)
                    try:
                        result = future.result()
                    except Exception as error:
                        result = dict(key=key, status="launcher_exception", exit_code=None,
                                      exception=repr(error), process_seconds=None)
                    completed.append(result)
                    print("FIT_DONE {}/{} {}".format(
                        len(completed), len(keys), result["status"]), flush=True)
    batch_seconds = time.perf_counter() - batch_start
    by_key = {r["key"]: r for r in completed}
    for position in positions:
        position["fit_status"] = ("empty_zero" if position["empty"] else
                                  "knot_failure" if position["knot_error"] else
                                  by_key.get(position["key"], {}).get("status", "unrun_budget"))
    after = {p: digest(p) for p in before}
    successful = [r for r in completed if r["status"] == "ok"]
    elapsed = time.perf_counter() - started
    result = dict(schema="re2-ob-257-cost-v1", status="BOUNDED_BENCHMARK_ENDED",
                  contract=CONTRACT, limits=LIMITS, positions=positions, fits=completed,
                  unrun_keys=unrun, unique_nonempty_knots=len(keys),
                  empty_positions=sum(p["empty"] for p in positions),
                  reused_positions=sum(p["reused"] for p in positions),
                  knot_failures=sum(p["knot_error"] is not None for p in positions),
                  successful_fits=len(successful), batch_wall_seconds=batch_seconds,
                  batch_successful_fits_per_second=len(successful) / batch_seconds,
                  batch_attempted_fits_per_second=len(completed) / batch_seconds,
                  aggregation_seconds=aggregation_seconds,
                  aggregation_and_benchmark_seconds=elapsed,
                  inherited_coverage_aggregation_seconds=previous_aggregation,
                  combined_incremental_seconds=elapsed + previous_aggregation,
                  peak_parent_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  immutable_before=before, immutable_after=after, immutable_unchanged=before == after,
                  read_guard=guard, source_hashes=source_hashes,
                  manifest_sha256=digest(FITS / "manifest.json"),
                  scenario_workcount_upper=91060, global_new_unique_count=None,
                  scenario_no_dedup_seconds=(91060 * batch_seconds / len(successful)
                                            if successful else None),
                  scenario_scope="sample throughput, startup included; not a global CI or guarantee",
                  all_workers_reaped=True, original_1025_fits=0, validation_fits=0,
                  protected_observation_opens=0, old54_state_reads=0,
                  previous_duplicate_producer_spend="unresolved; not included as zero",
                  actual_producer_exit_artifact="fits_recovery/producer-exit.json")
    save(REPORT, result)
    require(before == after, "Original/source/input hashes changed")
    require(batch_seconds <= 900 and elapsed + previous_aggregation <= 1800,
            "Hard wall budget exceeded")
    print("BENCHMARK_ENDED successful={} unique={} batch_seconds={:.6f}".format(
        len(successful), len(keys), batch_seconds), flush=True)
    return 0


def check():
    FITS.mkdir(exist_ok=True)
    commands = [
        [str(PYTHON), "-B", str(HERE / "test_benchmark.py")],
        ["/home/gnho1236/.local/bin/pyright", "--project",
         str(PROJECT / "pyrightconfig.json"), str(HERE / "benchmark.py"),
         str(HERE / "test_benchmark.py")],
        [str(PYTHON), "-B", str(HERE / "benchmark.py"), "runtime-check"],
    ]
    records = []
    for command in commands:
        begin = time.perf_counter()
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120, cwd=str(REPO))
        records.append(dict(command=command, exit_code=proc.returncode, stdout=proc.stdout,
                            stderr=proc.stderr, wall_seconds=time.perf_counter() - begin))
        print(proc.stdout + proc.stderr, end="", flush=True)
    result = dict(passed=all(r["exit_code"] == 0 for r in records),
                  source_hashes=code_hashes(), checks=records)
    path = FITS / "checks.json" if result["passed"] else FITS / (
        "checks-failed-" + str(time.time_ns()) + ".json")
    save(path, result)
    return 0 if result["passed"] else 1


def execute():
    require(not (FITS / "RUN_ONCE.json").exists(), "Producer already attempted; no duplicate fits")
    save(FITS / "invocation.json", dict(command=[str(PYTHON), "-B", str(HERE / "benchmark.py"), "run"],
                                      source_hashes=code_hashes(), started_unix=time.time()))
    begin = time.perf_counter()
    command = [str(PYTHON), "-B", str(HERE / "benchmark.py"), "run"]
    proc = subprocess.run(command, timeout=1800, cwd=str(REPO))
    save(FITS / "producer-exit.json", dict(command=command, exit_code=proc.returncode,
                                         wall_seconds=time.perf_counter() - begin,
                                         source_hashes=code_hashes()))
    print("ACTUAL_PRODUCER_EXIT", proc.returncode, flush=True)
    return proc.returncode


def verify():
    report = load(REPORT)
    manifest = load(FITS / "manifest.json")
    require(load(FITS / "producer-exit.json")["exit_code"] == 0, "Producer exit")
    require(report["immutable_unchanged"] and report["all_workers_reaped"] and
            report["read_guard"]["denied"] == [] and
            len(report["positions"]) == 140 and report["batch_wall_seconds"] <= 900 and
            report["combined_incremental_seconds"] <= 1800, "Report boundaries")
    for path, expected in report["immutable_before"].items():
        require(digest(path) == expected, "Read-only input changed: " + path)
    require(report["manifest_sha256"] == digest(FITS / "manifest.json"), "Manifest changed")
    outputs = {str(REPORT): digest(REPORT)}
    seen = set()
    for key in manifest["keys"]:
        input_path = FITS / ("input-" + key + ".json")
        require(digest(input_path) == manifest["input_hashes"][key], "Saved input changed")
        knots = [np.asarray(k, dtype=np.float64) for k in load(input_path)["knots"]]
        require(len(knots) == 257 and knot_key(knots) == key, "Saved input key")
        if key in report["unrun_keys"]:
            require(not (FITS / ("launch-" + key + ".json")).exists(), "Unrun key launched")
            continue
        completion = load(FITS / ("completion-" + key + ".json"))
        require(key not in seen and completion["pid"] > 0, "Duplicate fit")
        seen.add(key)
        result_path = FITS / ("result-" + key + ".json")
        if completion["result_sha256"]:
            require(digest(result_path) == completion["result_sha256"], "Fit result changed")
        if completion["status"] == "ok":
            result = load(result_path)
            baseline_path = FITS / ("baseline-" + key + ".npz")
            require(completion["exit_code"] == 0 and
                    digest(baseline_path) == result["baseline_sha256"], "Baseline/exit")
            with np.load(baseline_path, allow_pickle=False) as archive:
                require(archive.files == ["baseline"], "Baseline schema")
                baseline = archive["baseline"]
            require(baseline.shape == (257,) and baseline.dtype == np.float64 and
                    np.isfinite(baseline).all() and np.all(baseline >= 0), "Baseline values")
            require(result["iterations"] <= 50 and result["cap50_reached"] ==
                    (result["iterations"] >= 50), "Iteration accounting")
            require(result["read_guard"]["denied"] == [], "Worker boundary")
            for path, expected in result["runtime_hashes"].items():
                require(digest(path) == expected, "Installed runtime mutated")
    for path in FITS.iterdir():
        if path.is_file():
            outputs[str(path)] = digest(path)
    require(len(seen) + len(report["unrun_keys"]) == len(manifest["keys"]), "Unaccounted fit")
    require(sum(p["raw_count"] for p in report["positions"]) ==
            sum(p["kept_count"] + p["pooled_count"] + p["unknown_count"]
                for p in report["positions"]), "Position conservation")
    save(FITS / "verification.json", dict(status="PASS", checked_fits=len(seen),
                                        outputs_sha256=outputs, actual_verifier_exit_artifact=
                                        "fits_recovery/verification-exit.json"))
    print("PRESERVED_OUTPUTS_PASS positions=140 fits={}".format(len(seen)), flush=True)
    return 0


def verify_once():
    command = [str(PYTHON), "-B", str(HERE / "benchmark.py"), "verify"]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120, cwd=str(REPO))
    save(FITS / "verification-exit.json", dict(command=command, exit_code=proc.returncode,
                                              stdout=proc.stdout, stderr=proc.stderr))
    print(proc.stdout + proc.stderr, end="", flush=True)
    return proc.returncode


def main():
    command = sys.argv[1]
    if command == "worker":
        return worker(sys.argv[2])
    if command == "runtime-check":
        return runtime_check()
    if command == "check":
        return check()
    if command == "execute":
        return execute()
    if command == "run":
        return run()
    if command == "verify":
        return verify()
    if command == "verify-once":
        return verify_once()
    raise ValueError("Expected check/execute/run/worker/verify-once")


if __name__ == "__main__":
    sys.exit(main())
