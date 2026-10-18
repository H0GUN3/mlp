"""Recompute evidence checks from completed artifacts only; never fit a solver."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark import ART, HERE, PROBES, compare, digest, guard, load, require, save
import numpy as np


def main():
    selection = load(PROBES / "selection.json")
    guard_stats = guard(selection["immutable_before"])
    summary = load(HERE / "benchmark.json")
    require(digest(PROBES / "selection.json") == summary["selection_sha256"], "Selection changed")
    require({p: digest(p) for p in selection["immutable_before"]} ==
            selection["immutable_before"] == summary["immutable_after"], "Original hash changed")
    for name, sha in summary["implementation_sha256"].items():
        require(digest(HERE / name) == sha, "Implementation changed after benchmark")
    completions = [load(p) for p in sorted(PROBES.glob("completion-*.json"))]
    require(len(completions) == 8, "Fit count differs")
    require(sum(r["mode"] != "candidate" for r in completions) == 3, "Original fit cap")
    require(sum(r["mode"] == "candidate" for r in completions) == 5, "Candidate fit cap")
    require(sum(r["process_wall_seconds"] for r in completions) < 900, "Total wall budget")
    require(all(r["process_wall_seconds"] < 180 and not r["timed_out"] for r in completions),
            "Per-process deadline")
    failures = [r for r in completions if r["exit_code"] != 0 or not r["sentinel_present"]]
    require(len(failures) == 1 and failures[0]["mode"] == "profile" and failures[0]["index"] == 0,
            "Unexpected completion failure")
    checks, structures = [], []
    initial_value = load(PROBES / "reference-3.json")["records"][0]["value"]
    for entry in selection["inputs"]:
        i = entry["index"]
        candidate = load(PROBES / ("candidate-{}.json".format(i)))
        if i < 3:
            with np.load(ART / "hawkes" / (entry["key"] + ".npz"), allow_pickle=False) as z:
                reference = dict(entry["cached_reference"], baseline=z["baseline"].tolist())
        else:
            reference = load(PROBES / ("reference-{}.json".format(i)))
        check = compare(reference, candidate)
        require(all(summary["checks"][i][k] == v for k, v in check.items()), "Comparison changed")
        require(check["qualified"], "Representative exact equivalence failed")
        require(candidate["key"] == entry["key"] and candidate["contract"] == selection["contract"],
                "Input/contract changed")
        require(digest(entry["knot_file"]) == entry["knot_file_sha256"], "Knots changed")
        require(not candidate["transitive_pandas_loaded_by_tick"], "Candidate imported pandas")
        require(all(v == "1" for v in candidate["thread_environment"].values()), "Thread count")
        require(candidate["runtime_files_before"] == candidate["runtime_files_after"],
                "Installed numerical runtime changed")
        require(all(digest(p) == sha for p, sha in candidate["runtime_files_before"].items()),
                "Installed numerical runtime changed after fit")
        # -B disables writes, not Python's speculative read of a nonexistent .pyc.
        denied_pyc = HERE / "__pycache__/equivalent_backend.cpython-38.pyc"
        require(candidate["read_guard"]["denied"] == [str(denied_pyc)] and
                not denied_pyc.exists(), "Unexpected denied path; raw/protected reads forbidden")
        first_value = candidate["records"][0]
        require(first_value["kind"] == "value" and first_value["after_iteration"] == 0 and
                first_value["nonzero_rows"] == first_value["nonzero_columns"] == 1025 and
                not first_value["fastpath"] and first_value["value"] == initial_value,
                "Initial dense objective was altered")
        checks.append(dict(index=i, key=entry["key"], **check))
        counts = {}
        for kind in ("prox", "value"):
            records = [r for r in candidate["records"] if r["kind"] == kind]
            counts[kind] = dict(calls=len(records), fastpath_hits=sum(r["fastpath"] for r in records),
                                min_nonzero_rows=min(r["nonzero_rows"] for r in records),
                                max_nonzero_rows=max(r["nonzero_rows"] for r in records),
                                min_nonzero_columns=min(r["nonzero_columns"] for r in records),
                                max_nonzero_columns=max(r["nonzero_columns"] for r in records))
        structures.append(dict(index=i, **counts))
    tests = load(PROBES / "unit-tests-final.json")
    require(tests["success"] and tests["tests_run"] == 10 and not tests["pandas_loaded"],
            "Focused tests not green")
    save(PROBES / "verification.json", dict(
        status="REPRESENTATIVE_CHECKS_PASS_NOT_FULL_PROTOCOL_PASS",
        no_new_fits=True, original_hashes_unchanged=True, read_guard=guard_stats,
        recomputed_checks=checks, fastpath_counts=structures,
        actual_completions=[{k: r[k] for k in ("mode", "index", "pid", "exit_code",
                                             "sentinel_present", "process_wall_seconds")}
                            for r in completions],
        total_process_wall_seconds=sum(r["process_wall_seconds"] for r in completions),
        original_fits=3, candidate_fits=5, failed_first_profile_preserved=True,
        denied_nonexistent_pyc_reads_per_candidate=1,
        benchmark_sha256=digest(HERE / "benchmark.json")))
    print("NUMERICS_ARTIFACT_CHECK_PASS", flush=True)


if __name__ == "__main__":
    main()
