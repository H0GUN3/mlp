"""Independent checks of the preserved 257-cost artifacts; never fits a model."""
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
REPO = HERE.parents[2]
ART = PROJECT / "artifacts"
MATCHED = ART / "matched"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def check(value, message):
    if not value:
        raise AssertionError(message)


def rank(text):
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    split = load(PROJECT / "split.json")
    pre = load(ART / "preflight.json")
    templates = load(ART / "templates.json")
    mapping = load(HERE / "mapping.json")
    selection = load(HERE / "selection.json")
    coverage = load(HERE / "coverage.json")
    completion = load(HERE / "mapping_evidence/completion.json")
    upstream_check = load(HERE / "mapping_evidence/verification.json")
    benchmark = load(HERE / "benchmark.json")
    producer = load(HERE / "fits/producer-exit.json")
    checks = load(HERE / "fits/checks.json")
    runtime = load(HERE / "fits/runtime.json")
    benchmark_check = load(HERE / "fits/verification.json")

    rows = {r["case"]: r for r in split["cases"]}
    train = {case for case, row in rows.items() if row["partition"] == "train"}
    validation = {case for case, row in rows.items()
                  if row["partition"] == "validation"}
    check((len(train), len(validation), len(split["protected_cases"])) == (48, 24, 18),
          "split/protected counts changed")
    services = pre["services"]
    check(len(services) == len(set(services)) == 14, "service allowlist")
    check(completion["status"] == upstream_check["status"] == "PASS",
          "mapping producer evidence status")

    # Recount frozen TRAIN pre-injection events independently from matched arrays.
    old_feature_to_cluster = {
        int(feature): int(cluster)
        for cluster, feature in templates["cluster_id_to_feature"].items()
    }
    check(set(old_feature_to_cluster) == set(range(1, 1025)), "frozen feature map")
    counts = np.zeros(1025, dtype=np.int64)
    source_hashes = {}
    intervals = {x["case"]: x for x in pre["intervals"]}
    for case in sorted(train):
        meta_path, data_path = MATCHED / (case + ".json"), MATCHED / (case + ".npz")
        meta = load(meta_path)
        check(meta["case"] == case and meta["partition"] == "train",
              "TRAIN cache metadata allowlist")
        check(digest(data_path) == meta["sha256"], "TRAIN cache content hash")
        with np.load(data_path, allow_pickle=False) as archive:
            check(set(archive.files) == {"times", "nodes", "events"}, "TRAIN cache schema")
            times, nodes, events = (archive[k] for k in ("times", "nodes", "events"))
        check(all(a.dtype == np.int64 and a.ndim == 1 for a in (times, nodes, events))
              and len(times) == len(nodes) == len(events) == meta["rows"],
              "TRAIN cache shape")
        check(np.all((times >= intervals[case]["start"]) &
                     (times < intervals[case]["end_exclusive"])) and
              np.all((nodes >= 0) & (nodes < 14)) and
              np.all((events >= 0) & (events <= 1024)), "TRAIN cache bounds")
        before = events[(times < rows[case]["inject_time"]) & (events > 0)]
        counts += np.bincount(before, minlength=1025)
        source_hashes["matched/" + case + ".json"] = digest(meta_path)
        source_hashes["matched/" + case + ".npz"] = digest(data_path)

    cluster_counts = {str(old_feature_to_cluster[f]): int(counts[f])
                      for f in range(1, 1025)}
    check(cluster_counts == mapping["counts"], "independent TRAIN counts mismatch")
    check(sum(cluster_counts.values()) == mapping["strictly_preinject_occurrences"],
          "TRAIN occurrence total mismatch")
    all_ids = sorted(map(int, cluster_counts))
    ranked = sorted(all_ids, key=lambda i: (-cluster_counts[str(i)], i))[:256]
    selected = sorted(ranked)
    check(selected == mapping["selected_cluster_ids"], "top-256/tie rule mismatch")
    check(mapping["dimensions"] == 257 and mapping["retained"] == 256 and
          mapping["frequency_source_cases"] == 48 and
          mapping["frequency_validation_reads"] == 0 and
          len(mapping["unselected_cluster_ids"]) == 768 and
          set(map(int, mapping["cluster_id_to_feature"].keys())) == set(selected) and
          set(mapping["cluster_id_to_feature"].values()) == set(range(1, 257)) and
          mapping["unknown_cluster_id"] == mapping["unknown_feature_id"] == 0,
          "mapping shape/unknown contract")

    # Recompute the five roots and ten window choices from the frozen hash rule.
    case_rows = list(rows.values())
    expected_selection = []
    for root in sorted({r["root_cause_service"] for r in case_rows
                        if r["partition"] == "train"}):
        candidates = [r for r in case_rows if r["partition"] == "train"
                      and r["root_cause_service"] == root]
        chosen_case = min(candidates, key=lambda r: (
            rank("re2-ob-257-cost-v1|case|" + r["case"]), r["case"]))
        iv = intervals[chosen_case["case"]]
        starts = range(iv["start"], iv["end_exclusive"], 10)
        for fault in (False, True):
            eligible = [s for s in starts
                        if (s + 9 >= chosen_case["inject_time"]) == fault]
            check(bool(eligible), "missing required window layer")
            start = min(eligible, key=lambda s: (
                rank("re2-ob-257-cost-v1|window|" + chosen_case["case"] + "|" +
                     str(s)), s))
            expected_selection.append({
                "case": chosen_case["case"], "partition": "train", "root": root,
                "fault": fault, "start": start,
                "window_index": (start - iv["start"]) // 10, "services": services,
            })
    check(expected_selection == selection["records"] and
          selection["missing"] == [] and selection["cases"] == 5 and
          selection["windows"] == 10 and selection["mapping_sha256"] == digest(
              HERE / "mapping.json"), "selection/hash-rule mismatch")

    # Independently recount all TRAIN/validation × pre/post × service cells.
    new_lookup = np.zeros(1025, dtype=np.int64)
    for old_feature, cluster in old_feature_to_cluster.items():
        new_lookup[old_feature] = mapping["cluster_id_to_feature"].get(str(cluster), 0)
    expected: Dict[Tuple[str, str, str], Dict[str, Any]] = {
        (part, phase, service): dict(total=0, kept=0, newly_pooled=0, old_unknown=0,
                                     distinct_pooled_templates=set(), pooled_counts={})
        for part in ("train", "validation") for phase in ("pre", "post")
        for service in services
    }
    for part, cases in (("train", train), ("validation", validation)):
        for case in sorted(cases):
            meta_path, data_path = MATCHED / (case + ".json"), MATCHED / (case + ".npz")
            meta = load(meta_path)
            check(meta["case"] == case and meta["partition"] == part,
                  "cache partition mismatch")
            check(digest(data_path) == meta["sha256"], "cache hash mismatch")
            source_hashes["matched/" + case + ".json"] = digest(meta_path)
            source_hashes["matched/" + case + ".npz"] = digest(data_path)
            with np.load(data_path, allow_pickle=False) as archive:
                times, nodes, events = (archive[k] for k in ("times", "nodes", "events"))
            check(all(a.dtype == np.int64 and a.ndim == 1 for a in (times, nodes, events))
                  and len(times) == len(nodes) == len(events) == meta["rows"] and
                  np.all((times >= intervals[case]["start"]) &
                         (times < intervals[case]["end_exclusive"])) and
                  np.all((nodes >= 0) & (nodes < 14)) and
                  np.all((events >= 0) & (events <= 1024)), "cache integrity")
            for phase, phase_mask in (
                    ("pre", times < rows[case]["inject_time"]),
                    ("post", times >= rows[case]["inject_time"])):
                for node, service in enumerate(services):
                    mask = phase_mask & (nodes == node)
                    ev = events[mask]
                    bucket = expected[(part, phase, service)]
                    bucket["total"] += len(ev)
                    bucket["kept"] += int(np.count_nonzero(new_lookup[ev] > 0))
                    pooled = ev[(ev > 0) & (new_lookup[ev] == 0)]
                    bucket["newly_pooled"] += len(pooled)
                    bucket["old_unknown"] += int(np.count_nonzero(ev == 0))
                    if len(pooled):
                        ids, nums = np.unique(pooled, return_counts=True)
                        for feature, num in zip(ids.tolist(), nums.tolist()):
                            cid = old_feature_to_cluster[feature]
                            bucket["distinct_pooled_templates"].add(cid)
                            bucket["pooled_counts"][cid] = (
                                bucket["pooled_counts"].get(cid, 0) + num)

    check(len(coverage["records"]) == 56 and coverage["cases"] == 72 and
          coverage["row_conservation"] is True, "coverage dimensions")
    covered = {}
    for record in coverage["records"]:
        key = (record["partition"], record["phase"], record["service"])
        check(key not in covered, "duplicate coverage row")
        covered[key] = record
        actual = expected[key]
        for field in ("total", "kept", "newly_pooled", "old_unknown"):
            check(record[field] == actual[field], "independent coverage mismatch " + str(key))
        check(record["other"] == record["newly_pooled"] + record["old_unknown"] and
              record["total"] == record["kept"] + record["other"],
              "coverage row conservation")
        ratio = record["other"] / record["total"] if record["total"] else None
        check(record["other_ratio"] == ratio, "coverage ratio")
        check(record["distinct_pooled_templates"] ==
              len(actual["distinct_pooled_templates"]), "pooled template count")
        tops = sorted(actual["pooled_counts"].items(), key=lambda x: (-x[1], x[0]))[:10]
        check([(x["cluster_id"], x["rows"]) for x in record["top_pooled_templates"]] ==
              tops, "top pooled-template counts")
    check(len(covered) == 56 and
          sum(r["total"] for r in coverage["records"]) == 11991116,
          "coverage records/total")

    # Confirm the saved boundary record, hashes, and fit absence; never launch fits.
    cache_phases = [x.split(":", 1)[0] for x in coverage["cache_reads"]]
    check(len(cache_phases) == 120 and cache_phases[:48] == ["train"] * 48 and
          cache_phases[48:] == ["coverage"] * 72 and
          coverage["validation_opened_after_mapping_sha256"] == digest(HERE / "mapping.json"),
          "freeze-before-validation evidence order")
    check(benchmark["status"] == "STOP_HANDOFF_HASH_MISMATCH" and
          benchmark["measurement_complete"] is False and
          producer["exit_code"] == 1 and benchmark["actual_producer"]["exit_code"] == 1 and
          benchmark["successful_fits"] == 0 and len(benchmark["positions"]) == 140 and
          all(p["status"] == "unrun_boundary" for p in benchmark["positions"]),
          "benchmark must remain classified as pre-fit failure")
    check(checks["passed"] and
          [x["exit_code"] for x in checks["checks"]] == [0, 0, 0] and
          benchmark_check["actual_producer_exit"] == 1 and
          benchmark_check["fit_artifact_count"] == 0,
          "preserved benchmark check/exit evidence")
    fit_files = {p.name for p in (HERE / "fits").iterdir() if p.is_file()}
    check(not any(name.startswith(("result-", "baseline-", "launch-", "completion-",
                                  "input-")) for name in fit_files) and
          "manifest.json" not in fit_files, "unexpected fit artifact")

    # Reconcile current immutable inputs with the producer's saved SHA-256 ledger.
    for rel, expected_hash in completion["source_hashes"].items():
        source_paths = {
            "split": PROJECT / "split.json",
            "preflight": ART / "preflight.json",
            "templates": ART / "templates.json",
            "snapshot": ART / "drain.snapshot",
        }
        path = (MATCHED / rel[len("matched/"):] if rel.startswith("matched/")
                else source_paths[rel])
        check(digest(path) == expected_hash, "source hash mismatch " + rel)
    for path, expected_hash in runtime["runtime_hashes"].items():
        check(digest(path) == expected_hash, "installed runtime hash mismatch")
    check(digest(REPO / "research/native_reproduction_20261013/native_data.py") ==
          "05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986",
          "native source hash")

    totals = {}
    for part in ("train", "validation"):
        for phase in ("pre", "post"):
            subset = [r for r in coverage["records"]
                      if r["partition"] == part and r["phase"] == phase]
            totals[part + "_" + phase] = {
                field: sum(r[field] for r in subset)
                for field in ("total", "kept", "newly_pooled", "old_unknown", "other")
            }
    service_summary = []
    for service in services:
        entry = {"service": service}
        for part in ("train", "validation"):
            entry[part] = {}
            for phase in ("pre", "post"):
                r = covered[(part, phase, service)]
                entry[part][phase] = {
                    "total": r["total"], "kept": r["kept"],
                    "newly_pooled": r["newly_pooled"], "old_unknown": r["old_unknown"],
                    "other_ratio": r["other_ratio"],
                    "distinct_pooled_templates": r["distinct_pooled_templates"],
                }
        service_summary.append(entry)

    result = {
        "status": "PASS_ARTIFACTS_VERIFIED_BENCHMARK_NOT_MEASURED",
        "method": "Independent NumPy/stdlib recount; no fit or prediction invoked",
        "checks": {
            "train_only_frequency_and_top256": "PASS",
            "freeze_before_validation_evidence": "PASS; explicit cache guard, not OS audit",
            "mapping_and_unknown": "PASS",
            "selection_hash_rule": "PASS",
            "coverage_72_cases_14_services_56_cells": "PASS",
            "fit_artifacts": "NONE; producer stopped before aggregation/fit",
            "producer_exit": 1,
            "protected_observations_or_predictions_opened": 0,
            "neural_training_or_inference": 0,
        },
        "counts": {
            "train_cases": 48, "validation_cases": 24, "protected_cases": 18,
            "frozen_templates": 1024, "selected_templates": 256,
            "pooled_templates": 768, "dimensions": 257,
            "selection_cases": 5, "selection_windows": 10,
            "positions": 140, "coverage_rows": 56,
            "accounted_log_rows": 11991116, "phase_totals": totals,
        },
        "service_coverage": service_summary,
        "hashes": {
            "mapping_py": digest(HERE / "mapping.py"),
            "benchmark_py": digest(HERE / "benchmark.py"),
            "mapping": digest(HERE / "mapping.json"),
            "selection": digest(HERE / "selection.json"),
            "coverage": digest(HERE / "coverage.json"),
            "benchmark": digest(HERE / "benchmark.json"),
            "native_source": digest(REPO /
                "research/native_reproduction_20261013/native_data.py"),
        },
        "fit_cost": {
            "real_fit_count": 0,
            "solver_seconds": None,
            "sample_wall_seconds": None,
            "full_cost_scenario_seconds": None,
            "reason": "Producer exit 1 at handoff hash; no sample fit distribution exists",
        },
        "historical": {
            "first_mapping_attempt": "read one validation cache JSON metadata before freeze; stopped without outputs",
            "recovered_run": "deterministic TRAIN-only counts and selection; saved mapping hash before validation cache aggregation",
            "benchmark_attempt": "MAPPING.md handoff hash mismatch; 140 positions unrun, 0 fits",
        },
    }
    out = HERE / "verification.json"
    with out.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print("INDEPENDENT_ARTIFACT_CHECK_PASS; BENCHMARK_UNMEASURED")


def recovery_main():
    """Verify saved recovery fits only; reuse prior mapping/coverage recounts."""
    fits_dir = HERE / "fits_recovery"
    report = load(HERE / "benchmark_recovery.json")
    manifest = load(fits_dir / "manifest.json")
    fit_verification = load(fits_dir / "verification.json")
    producer_exit = load(fits_dir / "producer-exit.json")
    verifier_exit = load(fits_dir / "verification-exit.json")
    cost = load(fits_dir / "cost-summary.json")
    prior = load(HERE / "verification.json")
    mapping_evidence = load(HERE / "mapping_evidence/verification.json")
    coverage = load(HERE / "coverage.json")
    selection = load(HERE / "selection.json")

    check(prior["status"] == "PASS_ARTIFACTS_VERIFIED_BENCHMARK_NOT_MEASURED",
          "Preserved first verification")
    check(mapping_evidence["status"] == "PASS" and
          mapping_evidence["checks"]["independent_artifact_assertions"]["exit"] == 0,
          "Reuse earlier independent mapping/selection/coverage check")
    check(report["status"] == "BOUNDED_BENCHMARK_ENDED" and
          producer_exit["exit_code"] == verifier_exit["exit_code"] == 0 and
          fit_verification["status"] == cost["status"] == "PASS",
          "Actual recovery producer/verifier exits")
    for name, expected in (
            ("mapping.json", "a9bf14fd115d55c040c1d7a30b376411f722ef6ef12f3fa3eaf7f12d4f9b006a"),
            ("selection.json", "6b7be4278e61e6752aa8c65b15b7d58b76f227ee7738e4be33788b4e9af399e9"),
            ("coverage.json", "78a76b05fa54cd9b9a3cc92e15adb8e7d86f7ef39dd8a33ff1a1d10d35fd7181"),
            ("MAPPING.md", "711c3e41334efa1c798ee47ef6606afd9aae670841db59b7ff156ef32ff41b46")):
        check(digest(HERE / name) == expected, "Pinned upstream changed: " + name)
    check(selection["mapping_sha256"] == digest(HERE / "mapping.json") and
          coverage["selection_sha256"] == digest(HERE / "selection.json") and
          coverage["mapping_sha256"] == digest(HERE / "mapping.json"),
          "Frozen mapping/selection/coverage bindings")
    check(report["manifest_sha256"] == digest(fits_dir / "manifest.json") and
          manifest["mapping_sha256"] == digest(HERE / "mapping.json") and
          manifest["selection_sha256"] == digest(HERE / "selection.json"),
          "Selected manifest bindings")
    check(report["limits"] == dict(workers=4, threads=1, positions=140,
          per_fit_seconds=60, batch_seconds=900,
          aggregation_and_benchmark_seconds=1800), "Declared limits")
    check(report["contract"]["event_count"] == 257 and
          report["contract"]["solver"] == "installed original HawkesADM4" and
          report["contract"]["decay"] == 3 and report["contract"]["seed"] == 42 and
          report["contract"]["max_iter"] == 50 and report["contract"]["tol"] == 1e-5 and
          report["contract"]["n_threads"] == 1, "Original solver contract")
    check(not any(report[k] for k in ("validation_fits", "original_1025_fits",
          "old54_state_reads", "protected_observation_opens")), "Scope boundary")
    check(len(selection["records"]) == 10 and selection["cases"] == 5 and
          selection["missing"] == [] and
          all(row["partition"] == "train" for row in selection["records"]),
          "Fixed TRAIN-only selection")
    check(len(report["positions"]) == 140 and report["empty_positions"] == 58 and
          report["reused_positions"] == 1 and report["knot_failures"] == 0 and
          report["unrun_keys"] == [], "Position accounting")

    keys, iterations, solver_seconds, process_seconds = set(), [], [], []
    baseline_hashes, cache_hashes = {}, {}
    warnings, capped, timeouts = 0, 0, 0
    for path, expected in report["immutable_before"].items():
        check(digest(path) == expected, "Immutable input changed: " + path)
        if "/matched/" in path:
            cache_hashes[str(Path(path).relative_to(PROJECT / "artifacts"))] = expected
    check(report["immutable_before"] == report["immutable_after"] and
          report["immutable_unchanged"], "Producer immutability ledger")
    check(report["source_hashes"] == manifest["source_hashes"], "Source ledger mismatch")
    for path, expected in report["source_hashes"].items():
        check(digest(path) == expected, "Source hash changed: " + path)
    check("svd" not in (HERE / "benchmark.py").read_text().lower(),
          "Unexpected compact-SVD path")

    for fit in report["fits"]:
        key = fit["key"]
        check(key not in keys, "Duplicate fit key")
        keys.add(key)
        check(fit["status"] == "ok" and fit["exit_code"] == 0 and
              not fit["timed_out"] and not fit["hard_killed"] and
              fit["exception"] is None, "Fit failed or timed out: " + key)
        check(fit["iterations"] in (11, 21, 31, 41, 50) and
              fit["cap50_reached"] == (fit["iterations"] == 50),
              "Fit iteration/cap state: " + key)
        check(fit["solver_seconds"] >= 0 and 0 < fit["process_seconds"] < 60,
              "Fit timing bound: " + key)
        warnings += len(fit["warnings"])
        capped += int(fit["cap50_reached"])
        timeouts += int(fit["timed_out"])
        iterations.append(fit["iterations"])
        solver_seconds.append(fit["solver_seconds"])
        process_seconds.append(fit["process_seconds"])

        input_path = fits_dir / ("input-" + key + ".json")
        result_path = fits_dir / ("result-" + key + ".json")
        baseline_path = fits_dir / ("baseline-" + key + ".npz")
        check(digest(input_path) == manifest["input_hashes"][key],
              "Knot input hash: " + key)
        check(digest(result_path) == fit["result_sha256"], "Fit result hash: " + key)
        saved_input = load(input_path)
        knots = saved_input["knots"]
        check(len(knots) == 257, "Knot width: " + key)
        knot_hash = hashlib.sha256(b"RE2-native-relative10-seed42-v1")
        for knot in knots:
            values = np.asarray(knot, dtype="<f8")
            check(np.isfinite(values).all() and np.all(np.diff(values) >= 0),
                  "Knot values/order: " + key)
            knot_hash.update(np.asarray([len(values)], dtype="<i8").tobytes())
            knot_hash.update(values.tobytes())
        check(saved_input["key"] == knot_hash.hexdigest() == key, "Knot key: " + key)

        result = load(result_path)
        completion = load(fits_dir / ("completion-" + key + ".json"))
        check(completion["exit_code"] == 0 and completion["status"] == "ok" and
              completion["result_sha256"] == digest(result_path),
              "Per-fit completion evidence: " + key)
        check(result["key"] == key and result["contract"] == report["contract"] and
              result["native_source_sha256"] == report["source_hashes"][
                  str(REPO / "research/native_reproduction_20261013/native_data.py")],
              "Fit source/parameter evidence: " + key)
        check(result["input_sha256"] == manifest["input_hashes"][key] and
              result["read_guard"]["denied"] == [] and
              result["direct_pandas_operations"] == 0 and
              all(value == "1" for value in result["threads"].values()),
              "Fit boundary/thread evidence: " + key)
        check(result["baseline_shape"] == [257] and result["baseline_finite"] and
              result["baseline_nonnegative"] and
              digest(baseline_path) == result["baseline_sha256"],
              "Baseline metadata/hash: " + key)
        with np.load(baseline_path, allow_pickle=False) as archive:
            check(archive.files == ["baseline"], "Baseline schema: " + key)
            baseline = archive["baseline"]
        check(baseline.shape == (257,) and baseline.dtype == np.float64 and
              np.isfinite(baseline).all() and np.all(baseline >= 0),
              "Baseline values: " + key)
        baseline_hashes[key] = result["baseline_sha256"]
        for path, expected in result["runtime_hashes"].items():
            check(digest(path) == expected, "Fit runtime hash: " + path)

    check(len(keys) == 81 and len(iterations) == 81 and capped == 36 and
          warnings == timeouts == 0, "Fit totals/warnings/timeouts")
    check(collections.Counter(iterations) ==
          {11: 23, 21: 14, 31: 6, 41: 2, 50: 36}, "Fit iteration distribution")
    check(sum(p["empty"] for p in report["positions"]) == 58 and
          sum(not p["empty"] for p in report["positions"]) == 82,
          "Selected position population")
    for position in report["positions"]:
        check(position["partition"] == "train" and
              position["raw_count"] == position["kept_count"] +
              position["pooled_count"] + position["unknown_count"],
              "Position row conservation")
        if position["empty"]:
            check(position["fit_status"] == "empty_zero" and
                  len(position["zero_baseline"]) == 257 and
                  all(value == 0 for value in position["zero_baseline"]),
                  "Empty position zero vector")
        else:
            check(position["fit_status"] == "ok" and position["key"] in keys,
                  "Nonempty position fit link")

    output_hashes = fit_verification["outputs_sha256"]
    for path, expected in output_hashes.items():
        check(digest(path) == expected, "Saved recovery output hash: " + path)
    allowed_unledgered = {"cost-summary.json", "final-verification.json",
                          "verification-exit.json", "verification.json"}
    actual_files = {path.name for path in fits_dir.iterdir() if path.is_file()}
    recorded_files = {Path(path).name for path in output_hashes}
    check(actual_files - recorded_files == allowed_unledgered,
          "Unexpected recovery artifacts outside output ledger")
    checks = load(fits_dir / "checks.json")
    check(checks["passed"] and
          [entry["exit_code"] for entry in checks["checks"]] == [0, 0, 0],
          "Reused test/type/runtime exits")

    throughput = len(keys) / report["batch_wall_seconds"]
    no_dedup_scenario = 91060 / throughput
    check(report["batch_wall_seconds"] <= 900 and
          report["aggregation_and_benchmark_seconds"] +
          report["inherited_coverage_aggregation_seconds"] <= 1800 and
          math.isclose(report["scenario_no_dedup_seconds"], no_dedup_scenario,
                       rel_tol=1e-12), "Wall budgets/cost scenario")
    result = {
        "status": "PASS_INDEPENDENT_RECOVERED_FITS",
        "method": "Saved artifacts only; reuse prior independent 72-cache recount",
        "checks": {
            "upstream_mapping_selection_coverage": "PASS at pinned hashes",
            "fit_inputs_knot_hashes_and_arrays": "PASS; 81",
            "fit_results_and_257_float64_baselines": "PASS; finite/nonnegative",
            "original_solver_contract_native_source": "PASS; compact-SVD absent",
            "per_fit_exits_timeouts_warnings_iterations": "PASS; cap reached by 36/81",
            "140_positions_58_empty_row_conservation": "PASS",
            "immutable_input_source_runtime_hashes": "PASS",
            "saved_fit_output_hash_ledger": "PASS",
            "selection_scope": "5 TRAIN roots × 2 fixed windows; 14 services",
            "validation_fit_neural_fit_protected_observation": 0,
        },
        "counts": {
            "positions": 140, "empty": 58, "nonempty": 82,
            "unique_fits": 81, "exact_reused_positions": 1,
            "iterations": dict(sorted(collections.Counter(iterations).items())),
            "cap50": capped, "warnings": warnings, "timeouts_or_failures": timeouts,
            "immutable_paths": len(report["immutable_before"]),
            "fit_runtime_paths": len({path for fit in report["fits"]
                                      for path in load(fits_dir / (
                                          "result-" + fit["key"] + ".json"))["runtime_hashes"]}),
            "verified_fit_output_hashes": len(output_hashes),
        },
        "cost": {
            "solver_seconds": {
                "min": min(solver_seconds), "median": statistics.median(solver_seconds),
                "mean": statistics.mean(solver_seconds), "max": max(solver_seconds),
                "sum": sum(solver_seconds),
            },
            "process_seconds": {
                "min": min(process_seconds), "median": statistics.median(process_seconds),
                "mean": statistics.mean(process_seconds), "max": max(process_seconds),
                "sum": sum(process_seconds),
            },
            "batch_wall_seconds": report["batch_wall_seconds"],
            "throughput_fits_per_second": throughput,
            "nonempty_position_no_dedup_scenario_seconds": no_dedup_scenario,
            "global_257_unique_count": None,
            "no_global_confidence_interval": True,
        },
        "exits": {
            "first_benchmark_attempt": 1,
            "recovery_producer": producer_exit["exit_code"],
            "recovery_preserved_output_verifier": verifier_exit["exit_code"],
            "independent_recovery_checker": 0,
            "reused_tests_pyright_runtime": [entry["exit_code"]
                                             for entry in checks["checks"]],
        },
        "hashes": {
            "verify_py": digest(HERE / "verify.py"),
            "benchmark_py": digest(HERE / "benchmark.py"),
            "test_benchmark_py": digest(HERE / "test_benchmark.py"),
            "mapping_py": digest(HERE / "mapping.py"),
            "test_mapping_py": digest(HERE / "test_mapping.py"),
            "mapping": digest(HERE / "mapping.json"),
            "selection": digest(HERE / "selection.json"),
            "coverage": digest(HERE / "coverage.json"),
            "mapping_doc": digest(HERE / "MAPPING.md"),
            "benchmark_recovery": digest(HERE / "benchmark_recovery.json"),
            "fit_manifest": digest(fits_dir / "manifest.json"),
            "native_solver_source": digest(REPO /
                "research/native_reproduction_20261013/native_data.py"),
            "selected_train_cache_sources": cache_hashes,
        },
        "historical": {
            "first_mapping_attempt": "Read one validation matched-cache JSON metadata before freeze; stopped with no output.",
            "old_benchmark_attempt": "Exit 1 on MAPPING.md handoff hash; 140 unrun, zero fits; preserved.",
            "recovery_boundary": "Selection and TRAIN-only frequency rule unchanged; validation aggregation followed saved mapping hash.",
            "prior_verification_json": "Preserved; earlier mapping/selection/coverage recount reused at identical hashes.",
        },
    }
    out = HERE / "verification_recovery.json"
    with out.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print("INDEPENDENT_RECOVERY_ARTIFACT_CHECK_PASS; 81_FITS; COST_RECOMPUTED")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "recovery":
        recovery_main()
    else:
        main()
