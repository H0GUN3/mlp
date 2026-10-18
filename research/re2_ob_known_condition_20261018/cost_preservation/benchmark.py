"""Bounded, read-only-input ADM4 experiment; every generated artifact is exclusive JSON."""
import ast
import cProfile
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import pstats
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple
import warnings

sys.dont_write_bytecode = True
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
for variable in THREADS:
    os.environ[variable] = "1"

import numpy as np
from probes.native_runtime import HawkesADM4
from tick.prox import ProxNuclear

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = PROJECT.parents[1]
ART = PROJECT / "artifacts"
PROBES = HERE / "probes"
NATIVE = REPO / "research/native_reproduction_20261013/native_data.py"
PURE = REPO / "research/tt_re2_baselines_20261017/re2_stage2.py"
TICK = REPO / ".venv-eadro/lib/python3.8/site-packages/tick"
SPLIT_SHA = "3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2"
NATIVE_SHA = "05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986"
CONTRACT = dict(seed=42, event_count=1025, decay=3, baseline_start=0.2,
                end_times=10, C=1000, lasso_nuclear_ratio=0.5, max_iter=50,
                tol=1e-5, n_threads=1, rho=0.1, approx=0, em_max_iter=30,
                em_tol=None, record_every=10, print_every=10,
                adjacency_start="native uniform(.5,.9)", admm_start="native zeros")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, obj):
    path = Path(path)
    require(path == HERE / "benchmark.json" or PROBES in path.parents,
            "Output outside owned JSON artifacts")
    require(path.suffix == ".json" and not path.is_symlink(), "Unsafe JSON output")
    with path.open("x") as stream:
        json.dump(obj, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def native_functions():
    """Compile only unchanged pure function ASTs: no pandas/Drain/module side effects."""
    require(digest(NATIVE) == NATIVE_SHA, "Native source pin changed")
    namespace: Dict[str, Any] = dict(np=np, hashlib=hashlib, time=time,
                                     warnings=warnings, HawkesADM4=HawkesADM4,
                                     LENGTH=10, List=List, Tuple=Tuple, Dict=Dict, Any=Any)
    for path, names in ((NATIVE, {"make_knots", "fit_hawkes"}),
                        (PURE, {"knot_key", "case_groups"})):
        tree = ast.parse(path.read_text(), filename=str(path))
        nodes: List[ast.stmt] = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        require({n.name for n in nodes if isinstance(n, ast.FunctionDef)} == names, "Missing frozen function")
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def guard(allowed):
    """Only explicit frozen inputs, installed runtime, and owned probe JSON are openable."""
    allowed = {Path(p).resolve() for p in allowed}
    stats: Dict[str, Any] = {"denied": [], "input_opens": 0}

    def audit(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+")) or
                   (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)))
        owned_json = path.suffix == ".json" and (
            PROBES in path.parents or path == HERE / "benchmark.json")
        runtime = (REPO / ".venv-eadro" in path.parents or
                   Path(sys.base_prefix) / "lib" in path.parents or
                   path == Path("/dev/null"))
        owned_source = (path.parent == HERE and path.name in (
            "benchmark.py", "equivalent_backend.py", "test_equivalent_backend.py")) or (
                path == PROBES / "native_runtime.py")
        permitted = owned_json if writing else (
            runtime or path in allowed or owned_json or owned_source)
        if not permitted:
            stats["denied"].append(str(path))
            raise PermissionError("Outside cost-preservation allowlist: " + str(path))
        if path in allowed and not writing:
            stats["input_opens"] += 1
    sys.addaudithook(audit)
    return stats


def immutable_paths(cases):
    paths = [PROJECT / name for name in (
        "prepare.py", "cost_supplement.py", "split.py", "runner.py", "split.json",
        "pyrightconfig.json", "test_prepare.py", "test_runner.py", "test_split.py")]
    paths += [NATIVE, PURE, TICK / "hawkes/inference/hawkes_adm4.py",
              TICK / "prox/prox_nuclear.py", TICK / "prox/base/prox.py",
              ART / "preflight.json", ART / "profile.json", ART / "cost_supplement.json",
              ART / "templates.json", ART / "drain.snapshot"]
    paths += sorted((ART / "hawkes").glob("*"))
    for case in cases:
        paths += [ART / "matched" / (case + suffix) for suffix in (".npz", ".json")]
    return paths


def select():
    PROBES.mkdir(exist_ok=True)
    require(not (PROBES / "selection.json").exists(), "Selection already frozen")
    initial = [PROJECT / "split.json", ART / "preflight.json", ART / "cost_supplement.json"]
    splitting, preflight, supplement = map(load, initial)
    require(digest(initial[0]) == SPLIT_SHA == preflight["split_sha256"], "Split pin")
    require(preflight["case_counts"] == {"train": 48, "validation": 24}, "48/24 changed")
    require(len(splitting["protected_cases"]) == 18, "Protected18 changed")
    first = supplement["case"]
    rows = {r["case"]: r for r in splitting["cases"]}
    rank = sorted((r for r in rows.values() if r["partition"] == "train"),
                  key=lambda r: hashlib.sha256(
                      ("cost-preserve-20261018:" + r["case"]).encode()).hexdigest())
    used = {(rows[first]["root_cause_service"], rows[first]["fault"])}
    cases = [first]
    for row in rank:
        group = row["root_cause_service"], row["fault"]
        if group not in used:
            cases.append(row["case"])
            used.add(group)
        if len(cases) == 3:
            break
    paths = immutable_paths(cases)
    stats = guard(paths)
    before = {str(p): digest(p) for p in paths}
    template = load(ART / "templates.json")
    require(template["event_count"] == 1025, "Feature dimension changed")
    binding = {k: preflight[k] for k in (
        "split_sha256", "input_binding_sha256", "policy_sha256")}
    binding["snapshot_sha256"] = template["snapshot_sha256"]
    require(digest(ART / "drain.snapshot") == binding["snapshot_sha256"], "Snapshot")
    for k in ("split_sha256", "input_binding_sha256", "policy_sha256"):
        require(template[k] == binding[k], "Template binding " + k)
    require(supplement["original_profile_sha256"] == digest(ART / "profile.json"),
            "Original profile changed")
    for p, sha in preflight["source_hashes"].items():
        if str(REPO / p) in before:
            require(before[str(REPO / p)] == sha, "Frozen source changed " + p)
    ns = native_functions()
    intervals = {r["case"]: r for r in preflight["intervals"]}
    selections = []
    for case in cases:
        path = ART / "matched" / (case + ".npz")
        meta = load(path.with_suffix(".json"))
        require(digest(path) == meta["sha256"], "Matched digest")
        require(meta["partition"] == rows[case]["partition"], "Partition mismatch")
        for k, v in binding.items():
            require(meta[k] == v, "Matched binding " + k)
        expected = next(r for r in preflight["verified_cases"] if r["case"] == case)
        require(meta["stage1_log_sha256"] == expected["stage1_member_hashes"]["logs.jsonl.gz"],
                "Matched log provenance")
        with np.load(path, allow_pickle=False) as z:
            matched = {k: z[k] for k in ("times", "nodes", "events")}
        groups = ns["case_groups"](matched, intervals[case]["start"], 1025)
        if case == first:
            wanted = [r["key"] for r in supplement["probe_fits"]]
            found = {}
            # Only the first historical case is enumerated, never the 72-case census.
            for window, node, key, knots in groups:
                if key in wanted and key not in found:
                    found[key] = (window, node, knots)
                if len(found) == len(wanted):
                    break
            chosen = [(k, *found[k]) for k in wanted]
        else:
            window, node, key, knots = next(groups)
            chosen = [(key, window, node, knots)]
        for key, window, node, knots in chosen:
            index = len(selections)
            knot_path = PROBES / ("input-{}.json".format(index))
            save(knot_path, {"key": key, "knots": [k.tolist() for k in knots]})
            entry = dict(index=index, case=case, partition=rows[case]["partition"],
                         root_fault_group=[rows[case]["root_cause_service"], rows[case]["fault"]],
                         window=window, node=node, service=preflight["services"][node],
                         key=key, knot_file=str(knot_path), knot_file_sha256=digest(knot_path),
                         total_knots=sum(map(len, knots)), **binding)
            if index < 3:
                record = load(ART / "hawkes" / (key + ".json"))
                for k, v in binding.items():
                    require(record[k] == v, "Cache binding " + k)
                require(record["seed"] == 42 and record["event_count"] == 1025 and
                        record["threads"] == 1 and record["iteration_cap"] == 50, "Cache contract")
                require(record["sha256"] == digest(ART / "hawkes" / (key + ".npz")), "Cache hash")
                entry["cached_reference"] = record
            selections.append(entry)
    require(len(selections) == 5, "Expected five frozen inputs")
    require(all(digest(Path(p)) == sha for p, sha in before.items()), "Source mutated")
    save(PROBES / "selection.json", {
        "contract": CONTRACT, "inputs": selections, "immutable_before": before,
        "crosscase_ranking": [dict(case=r["case"], sha256=hashlib.sha256(
            ("cost-preserve-20261018:" + r["case"]).encode()).hexdigest()) for r in rank],
        "selection_rule": "3 historical keys; 2 first distinct TRAIN groups by prefixed SHA256; "
                          "crosscase first lexicographic nonempty (window,node), no labels/errors",
        "limits": {"original_fits": 3, "candidate_fits": 5,
                   "process_deadline_seconds": 180, "solver_wall_seconds": 900},
        "read_guard": stats,
    })
    print("NUMERICS_SELECTION_PASS", cases, flush=True)


def structure(x) -> Dict[str, Any]:
    rows = int(np.count_nonzero(np.any(x != 0, axis=1)))
    cols = int(np.count_nonzero(np.any(x != 0, axis=0)))
    return dict(shape=list(x.shape), nonzero_rows=rows, nonzero_columns=cols,
                zero_rows=x.shape[0] - rows, zero_columns=x.shape[1] - cols,
                nonzero_entries=int(np.count_nonzero(x)))


def worker(mode, index):
    selection = load(PROBES / "selection.json")
    stats = guard(selection["immutable_before"])
    for p, sha in selection["immutable_before"].items():
        require(digest(p) == sha, "Source changed before fit: " + p)
    entry = selection["inputs"][index]
    require(digest(entry["knot_file"]) == entry["knot_file_sha256"], "Frozen knot artifact")
    knots = [np.asarray(k, dtype=np.float64) for k in load(entry["knot_file"])["knots"]]
    ns = native_functions()
    require(ns["knot_key"](knots) == entry["key"] and len(knots) == 1025, "Knot key/dimension")
    require("pandas" not in sys.modules, "No pandas before any further fits")
    runtime_before = {}
    for name, loaded_module in list(sys.modules.items()):
        filename = getattr(loaded_module, "__file__", None)
        if name.startswith("tick.") and isinstance(filename, str) and Path(filename).is_file():
            runtime_before[str(Path(filename).resolve())] = digest(filename)
    module = importlib.import_module("tick.hawkes.inference.hawkes_adm4")
    prox_module = importlib.import_module("tick.prox.prox_nuclear")
    records = []
    svd_records = []
    counter = {"prox": 0, "value": 0}
    active: Dict[str, Any] = {"kind": None}
    original_svd = prox_module.svd
    from equivalent_backend import ZeroStructureProxNuclear

    class ObservedProx(ZeroStructureProxNuclear):
        def _call(self, coeffs, step, out):
            counter["prox"] += 1
            x = self._get_matrix(coeffs)
            rec: Dict[str, Any] = dict(kind="prox", iteration=counter["prox"], **structure(x))
            if mode == "candidate":
                rec["fastpath"] = rec["zero_rows"] > 0 or rec["zero_columns"] > 0
            active["kind"] = "prox"
            started = time.perf_counter()
            if mode == "candidate":
                super()._call(coeffs, step, out)
            else:
                ProxNuclear._call(self, coeffs, step, out)
            rec["seconds"] = time.perf_counter() - started
            active["kind"] = None
            records.append(rec)

        def value(self, coeffs):
            counter["value"] += 1
            x = self._get_matrix(coeffs)
            rec: Dict[str, Any] = dict(kind="value", after_iteration=counter["prox"], **structure(x))
            if mode == "candidate":
                rec["fastpath"] = rec["zero_rows"] > 0 or rec["zero_columns"] > 0
            active["kind"] = "value"
            started = time.perf_counter()
            result = (super().value(coeffs) if mode == "candidate" else
                      ProxNuclear.value(self, coeffs))
            rec["seconds"] = time.perf_counter() - started
            rec["value"] = float(result)
            active["kind"] = None
            records.append(rec)
            return result

    def observed_svd(*args, **kwargs):
        started = time.perf_counter()
        result = original_svd(*args, **kwargs)
        svd_records.append(dict(kind=active["kind"], seconds=time.perf_counter() - started,
                                shape=list(args[0].shape), compute_uv=kwargs.get("compute_uv", True)))
        return result

    # Profile delegates every numerical operation to the unchanged original implementation.
    setattr(module, "ProxNuclear", ObservedProx)
    profiling = mode == "profile" or (mode == "reference" and index == 3)
    if profiling:
        setattr(prox_module, "svd", observed_svd)
    profile = cProfile.Profile() if profiling else None
    if profile:
        profile.enable()
    result = ns["fit_hawkes"]((0, 0, knots, 42))
    if profile:
        profile.disable()
    result["baseline"] = result["baseline"].tolist()
    result.update(mode=mode, index=index, pid=os.getpid(), contract=CONTRACT, key=entry["key"],
                  records=records, svd_records=svd_records, thread_environment={
                      k: os.environ[k] for k in THREADS}, numpy_version=np.__version__,
                  python_version=sys.version, read_guard=stats)
    require(counter["prox"] == result["iterations"], "Iteration counter disagrees with history")
    if profile:
        stream = io.StringIO()
        pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(70)
        result["cprofile"] = stream.getvalue()
    result["immutable_after"] = {p: digest(p) for p in selection["immutable_before"]}
    require(result["immutable_after"] == selection["immutable_before"], "Frozen input/source mutated")
    result["runtime_files_before"] = runtime_before
    result["runtime_files_after"] = {p: digest(p) for p in runtime_before}
    require(result["runtime_files_before"] == result["runtime_files_after"], "Installed runtime changed")
    result["transitive_pandas_loaded_by_tick"] = "pandas" in sys.modules
    result["direct_pandas_operations"] = 0
    save(PROBES / ("{}-{}.json".format(mode, index)), result)
    require("pandas" not in sys.modules, "pandas imported; result retained")
    print("NUMERICS_WORKER_PASS mode={} index={} pid={} seconds={:.6f}".format(
        mode, index, os.getpid(), result["seconds"]), flush=True)


def launch(mode, index):
    selection = load(PROBES / "selection.json")
    for p, sha in selection["immutable_before"].items():
        require(digest(p) == sha, "Frozen input changed before launch")
    launches = sorted(PROBES.glob("launch-*.json"))
    previous = [load(p) for p in launches]
    originals = sum(r["mode"] != "candidate" for r in previous)
    candidates = sum(r["mode"] == "candidate" for r in previous)
    require(originals < 3 if mode != "candidate" else candidates < 5, "Fit count budget exhausted")
    charged = 0.0
    for r in previous:
        completion = PROBES / ("completion-{}-{}.json".format(r["mode"], r["index"]))
        charged += load(completion)["process_wall_seconds"] if completion.exists() else 180
    require(charged + 180 <= 900, "Conservative total wall budget exhausted")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", mode, str(index)]
    save(PROBES / ("launch-{}-{}.json".format(mode, index)), dict(
        command=command, mode=mode, index=index, parent_pid=os.getpid(),
        started_unix=time.time(), deadline_seconds=180, previously_charged_seconds=charged,
        code_sha256={str(p): digest(p) for p in (
            Path(__file__).resolve(), PROBES / "native_runtime.py",
            HERE / "equivalent_backend.py") if p.exists()}))
    started = time.perf_counter()
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate()
    record = dict(command=command, mode=mode, index=index, pid=proc.pid,
                  exit_code=proc.returncode, timed_out=timed_out, stdout=stdout, stderr=stderr,
                  process_wall_seconds=time.perf_counter() - started,
                  sentinel_present="NUMERICS_WORKER_PASS" in stdout)
    save(PROBES / ("completion-{}-{}.json".format(mode, index)), record)
    print(stdout, end="", flush=True)
    if stderr:
        print(stderr, file=sys.stderr, end="", flush=True)
    require(proc.returncode == 0 and record["sentinel_present"], "Worker failed; evidence retained")
    return load(PROBES / ("{}-{}.json".format(mode, index)))


def compare(reference, candidate):
    a, b = (np.asarray(r["baseline"], dtype=np.float64) for r in (reference, candidate))
    require(a.shape == b.shape == (1025,) and np.isfinite(a).all() and np.isfinite(b).all(),
            "Invalid baseline shape/finiteness")
    a32, b32 = a.astype(np.float32), b.astype(np.float32)
    equal = np.array_equal(a32, b32)
    bits = a32.tobytes() == b32.tobytes()
    return dict(float32_array_equal=bool(equal), float32_bitwise_equal=bits,
                float32_mismatch_indices=np.flatnonzero(a32 != b32).tolist(),
                float64_max_abs_diff=float(np.max(np.abs(a - b))),
                float64_array_equal=bool(np.array_equal(a, b)),
                iterations_equal=reference["iterations"] == candidate["iterations"],
                warnings_equal=reference["warnings"] == candidate["warnings"],
                reference_iterations=reference["iterations"], candidate_iterations=candidate["iterations"],
                reference_warnings=reference["warnings"], candidate_warnings=candidate["warnings"],
                qualified=bool(equal and bits and reference["iterations"] == candidate["iterations"] and
                               reference["warnings"] == candidate["warnings"]))


def finish():
    selection = load(PROBES / "selection.json")
    references = []
    for entry in selection["inputs"][:3]:
        with np.load(ART / "hawkes" / (entry["key"] + ".npz"), allow_pickle=False) as z:
            baseline = z["baseline"]
            require(baseline.dtype == np.float64, "Cached dtype changed")
        references.append(dict(entry["cached_reference"], baseline=baseline.tolist()))
    profile_failure = load(PROBES / "completion-profile-0.json")
    require(profile_failure["exit_code"] == 1, "Unexpected first profile outcome")
    profile = load(PROBES / "reference-3.json")
    references += [profile, launch("reference", 4)]
    candidates = [launch("candidate", i) for i in range(5)]
    checks = [dict(index=i, case=selection["inputs"][i]["case"],
                   key=selection["inputs"][i]["key"], **compare(ref, cand),
                   original_seconds=ref["seconds"], candidate_seconds=cand["seconds"],
                   speedup=ref["seconds"] / cand["seconds"])
              for i, (ref, cand) in enumerate(zip(references, candidates))]
    after = {p: digest(p) for p in selection["immutable_before"]}
    require(after == selection["immutable_before"], "Final frozen source/hash guard")
    durations = [load(p)["process_wall_seconds"] for p in PROBES.glob("completion-*.json")]
    first_seconds = [r["seconds"] for r in candidates[:3]]
    cross_seconds = [r["seconds"] for r in candidates[3:]]
    qualified = all(c["qualified"] for c in checks)
    result: Dict[str, Any] = dict(
        status="REPRESENTATIVE_NUMERICS_PASS_PROTOCOL_INCOMPLETE" if qualified else "NOT_QUALIFIED",
        representative_numerics_qualified=qualified,
        checks=checks, first_profile_failure=profile_failure,
        profile_source="reference-3.json; first-case profile lost at post-fit pandas check",
        strict_request_satisfied=False,
        selection_sha256=digest(PROBES / "selection.json"), contract=CONTRACT,
        original_fits=3, candidate_fits=5, total_process_wall_seconds=sum(durations),
        total_solver_seconds_lower_bound=sum(r["seconds"] for r in references[3:] + candidates),
        failed_profile_solver_wall_upper_bound=profile_failure["process_wall_seconds"],
        firstcase_candidate_mean_seconds=float(np.mean(first_seconds)),
        firstcase_candidate_max_seconds=max(first_seconds),
        crosscase_candidate_mean_seconds=float(np.mean(cross_seconds)),
        crosscase_candidate_max_seconds=max(cross_seconds),
        firstcase_mean_speedup=float(np.mean([r["seconds"] for r in references[:3]]) / np.mean(first_seconds)),
        crosscase_mean_speedup=float(np.mean([r["seconds"] for r in references[3:]]) / np.mean(cross_seconds)),
        illustrative_80028_4worker_seconds=80028 * float(np.mean(first_seconds)) / 4,
        original_budget_seconds=7200,
        affordable_firstcase_extrapolation=80028 * float(np.mean(first_seconds)) / 4 <= 7200,
        limits="First-case three plus two fixed crosscases, no global CI/full-corpus bitwise claim; "
               "cached originals are historical timings; profile has instrumentation overhead",
        immutable_after=after, immutable_unchanged=True,
        implementation_sha256={name: digest(HERE / name) for name in (
            "benchmark.py", "equivalent_backend.py", "test_equivalent_backend.py")},
        completed_unix=time.time(),
    )
    save(HERE / "benchmark.json", result)
    print("NUMERICS_BENCHMARK_COMPLETE " + result["status"], flush=True)


def main():
    require(sys.version_info[:2] == (3, 8) and np.__version__ == "1.21.5", "Pinned runtime required")
    require(all(os.environ[k] == "1" for k in THREADS), "Single-thread contract")
    command = sys.argv[1]
    if command == "select":
        select()
    elif command == "profile":
        launch("profile", 0)
        print("NUMERICS_PROFILE_COMPLETE", flush=True)
    elif command == "cross-profile":
        launch("reference", 3)
        print("NUMERICS_CROSS_PROFILE_COMPLETE", flush=True)
    elif command == "worker":
        worker(sys.argv[2], int(sys.argv[3]))
    elif command == "run":
        finish()
    else:
        raise ValueError("Expected select/profile/run/worker")


if __name__ == "__main__":
    main()
