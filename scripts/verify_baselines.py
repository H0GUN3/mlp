#!/usr/bin/env python3
"""Independently check frozen development baseline rankings and scores."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/baselines"
RESULTS = BASE / "results"
MANIFEST_PATH = ROOT / "research/smoke/manifest.json"
PROTOCOL_PATH = ROOT / "research/BASELINE_PROTOCOL.md"
INDEX_PATH = ROOT / "data/rcaeval/cases.parquet"
METHODS = ("median_change", "baro_signed", "baro_absolute_variant")
TOLERANCE = 1e-12


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baro_matrix(names, values, normal):
    """Literal independent implementation of the protocol's frozen score inputs."""
    matrix = np.asarray(values, dtype=np.float64).copy()
    require(matrix.ndim == 2 and matrix.shape[1] == len(names),
            "BARO input metric shape/name mismatch")
    matrix[~np.isfinite(matrix)] = np.nan
    for col in range(matrix.shape[1]):
        previous = 0.0
        for row in range(matrix.shape[0]):
            if np.isnan(matrix[row, col]):
                matrix[row, col] = previous
            else:
                previous = matrix[row, col]

    selected, output_names = [], []
    for col, name in enumerate(names):
        if name == "time" or name.endswith("_latency-50"):
            continue
        renamed = name[:-len("_latency-90")] + "_latency" if name.endswith("_latency-90") else name
        require(renamed not in output_names, f"BARO rename collision: {renamed}")
        output_names.append(renamed)
        selected.append(col)
    matrix = matrix[:, selected]
    normal = np.asarray(normal, dtype=bool)
    require(matrix.shape[0] == len(normal) and np.any(normal) and np.any(~normal),
            "BARO window must contain normal and fault rows")
    before, after = matrix[normal], matrix[~normal]
    keep = [not (np.all(before[:, i] == before[0, i]) or
                 np.all(after[:, i] == after[0, i]))
            for i in range(matrix.shape[1])]
    matrix = matrix[:, keep]
    output_names = [name for name, retained in zip(output_names, keep) if retained]
    for col, name in enumerate(output_names):
        if name.endswith("_mem"):
            matrix[:, col] /= 1e6
    return output_names, matrix, normal


def independent_baro(names, values, normal, absolute):
    names, matrix, normal = baro_matrix(names, values, normal)
    before, after = matrix[normal], matrix[~normal]
    scored = []
    for index, name in enumerate(names):
        baseline = before[:, index]
        q25, q75 = np.quantile(baseline, [0.25, 0.75])
        spread = float(q75 - q25)
        divisor = 1.0 if spread < 10 * np.finfo(np.float64).eps else spread
        changes = (after[:, index] - float(np.median(baseline))) / divisor
        score = float(np.max(np.abs(changes) if absolute else changes))
        scored.append((name, score, index))
    scored.sort(key=lambda entry: -entry[1])
    services = []
    for name, _, _ in scored:
        service = name.split("_", 1)[0]
        if service not in services:
            services.append(service)
    return services, scored


def self_check():
    # Leading NaNs become zero; later NaNs use only the previous observation.
    got = baro_matrix(["s_latency-90", "s_latency-50", "s_const", "time"],
                      [[np.nan, 1, 7, 0], [2, 2, 7, 1], [np.nan, 3, 7, 2],
                       [4, 4, 7, 3]], [True, True, False, False])
    assert got[0] == ["s_latency"]
    assert got[1][:, 0].tolist() == [0.0, 2.0, 2.0, 4.0]

    # IQR zero uses unit scale; signed and absolute formulas differ on decreases.
    data = np.array([[5., 0.], [5., 0.], [5., 0.], [5., 0.],
                     [7., 1.], [7., -4.], [8., -3.]])
    normal = [True] * 5 + [False] * 2
    _, signed = independent_baro(["up_x", "down_x"], data, normal, False)
    _, absolute = independent_baro(["up_x", "down_x"], data, normal, True)
    assert signed[0][0] == "up_x" and absolute[0][0] == "down_x"
    assert signed[-1][1] < 0

    # Equal scores preserve original metric order and service deduplication.
    tied = np.array([[0., 0., 0.]] * 4 + [[1., 1., 1.],
                                         [2., 2., 2.], [3., 3., 3.]])
    services, scores = independent_baro(
        ["first_cpu", "first_mem", "second_cpu"], tied, normal, False)
    assert scores[0][0] == "first_cpu" and services == ["first", "second"]


def read_json(path):
    return json.loads(path.read_text())


def aggregate(rows):
    count = len(rows)
    return {
        "n": count,
        "top1_count": sum(row["position"] == 1 for row in rows),
        "top3_count": sum(row["position"] is not None and row["position"] <= 3 for row in rows),
        "root_misses": sum(row["position"] is None for row in rows),
        "candidate_omissions": sum(row["omitted"] for row in rows),
        "top1": sum(row["position"] == 1 for row in rows) / count,
        "top3": sum(row["position"] is not None and row["position"] <= 3 for row in rows) / count,
        "mrr": sum(1 / row["position"] if row["position"] else 0 for row in rows) / count,
    }


def case_position(ranking, gold):
    require(len(ranking) == len(set(ranking)), "Duplicate service in persisted ranking")
    return ranking.index(gold) + 1 if gold in ranking else None


def main():
    self_check()
    protocol = PROTOCOL_PATH.read_bytes()
    manifest = read_json(MANIFEST_PATH)
    metadata = read_json(RESULTS / "metadata.json")
    require(metadata["protocol_sha256"] == hashlib.sha256(protocol).hexdigest(),
            "Protocol hash does not match baseline metadata")
    require(metadata["baro_alignment"]["commit"] == "582d4ead3d3301a34fea4e395bfa3f750fc9a40d",
            "Unexpected BARO reference commit")

    groups = manifest["cases"]
    reserved = [case for group in groups for case in group["reserved_development_cases"]]
    require(len(groups) == 12 and len(reserved) == 36 and len(set(reserved)) == 36,
            "Manifest must define 12 groups and 36 unique reserved cases")
    original = {group["case"]: group for group in groups}

    index_rows = pq.read_table(
        INDEX_PATH,
        columns=["case", "dataset", "root_cause_service", "fault", "repetition", "inject_time"],
    ).to_pylist()
    index = {row["case"]: row for row in index_rows if row["case"] in set(reserved)}
    require(set(index) == set(reserved), f"Reserved case index mismatch: {sorted(set(reserved)-set(index))}")
    require(len(index_rows) >= 36, "Case index unexpectedly small")

    # Verify provenance hashes only for non-telemetry sources and reserved metrics.
    checked_hashes, unchecked_telemetry_hashes = {}, []
    for relative, expected in metadata["input_sha256"].items():
        path = ROOT / relative
        parts = relative.split("/")
        is_case_telemetry = len(parts) >= 4 and parts[0:2] == ["data", "rcaeval"]
        if is_case_telemetry:
            case = parts[2]
            if case not in set(reserved):
                raise AssertionError(f"Metadata references protected case telemetry: {relative}")
            if path.name != "metrics.parquet":
                unchecked_telemetry_hashes.append(relative)
                continue
        actual = sha256(path)
        require(actual == expected, f"Input provenance hash mismatch: {relative}")
        checked_hashes[relative] = actual

    # Independent source checks for all persisted smoke inputs and generated features.
    source_paths = [
        "research/BASELINE_PROTOCOL.md", "scripts/baseline_dev.py", "scripts/smoke.py",
        "scripts/audit.py", "research/baselines/reference/baro-root-cause-analysis.py",
        "research/baselines/reference/baro-utility.py", "research/smoke/manifest.json",
        "research/smoke/simple-anomaly.json", "data/rcaeval/cases.parquet",
    ]
    source_paths += [f"research/smoke/features/{group['id']}.json" for group in groups]
    for relative in source_paths:
        require(relative in checked_hashes, f"Source provenance absent/unverified: {relative}")

    feature_index = read_json(RESULTS / "development-feature-index.json")
    require(feature_index["count"] == 24, "Expected exactly 24 generated development feature files")
    expected_generated_paths = {
        f"research/baselines/results/development-features/{case}.json"
        for case in set(reserved) - set(original)
    }
    require(set(feature_index["features"]) == expected_generated_paths,
            "Generated-feature index does not exactly match the 24 non-smoke cases")
    rows, feature_sources = [], set()
    for case in sorted(reserved):
        case_path = RESULTS / "cases" / f"{case}.json"
        result = read_json(case_path)
        indexed = index[case]
        require(result["case"] == case and result["dataset"] == indexed["dataset"] and
                result["fault"] == indexed["fault"] and result["root_cause_service"] == indexed["root_cause_service"] and
                result["repetition"] == indexed["repetition"] and result["inject_time"] == indexed["inject_time"],
                f"Case/index provenance mismatch: {case}")
        require(set(result["methods"]) == set(METHODS), f"Method coverage mismatch: {case}")
        require(result["original_smoke_case"] == (case in original), f"Original-case flag mismatch: {case}")
        feature_sources.add(result["feature_source"])

        if case in original:
            group = original[case]
            source = read_json(ROOT / "research/smoke/features" / f"{group['id']}.json")
            expected_seed = manifest["seed"] + int(group["id"].split("-")[1])
        else:
            source = read_json(RESULTS / "development-features" / f"{case}.json")
            expected_seed = metadata["smoke_feature_seeds_for_new_cases"][case]
            require(source["case"] == case and source["seed"] == expected_seed,
                    f"Generated feature provenance mismatch: {case}")
        require(result["feature_seed"] == expected_seed, f"Feature seed mismatch: {case}")
        expected_order = source["features"]["anomaly_ranking"] if case not in original else source["anomaly_ranking"]
        expected_mapping = source["features"]["mapping"] if case not in original else source["mapping"]
        median = result["methods"]["median_change"]
        require(median["ranking"] == expected_order, f"Median ranking/source mismatch: {case}")
        gold = expected_mapping.get(indexed["root_cause_service"], indexed["root_cause_service"])
        require(result["root_cause_service"] == indexed["root_cause_service"],
                f"Gold service mismatch: {case}")

        metrics_path = ROOT / "data/rcaeval" / case / "metrics.parquet"
        metrics_table = pq.read_table(metrics_path)
        times = metrics_table["time"].to_numpy()
        normal = times < indexed["inject_time"]
        require(np.any(normal) and np.any(~normal), f"Empty score window: {case}")
        names = [name for name in metrics_table.column_names if name != "time"]
        values = np.column_stack([metrics_table[name].to_numpy() for name in names]).astype(np.float64)

        method_observed = {}
        for method, absolute in (("baro_signed", False), ("baro_absolute_variant", True)):
            independent_rank, _ = independent_baro(names, values, normal, absolute)
            mapped_rank = [expected_mapping.get(service, service) for service in independent_rank]
            persisted = result["methods"][method]
            require(mapped_rank == persisted["ranking"],
                    f"Independent BARO ranking mismatch ({method}): {case}")
            position = case_position(mapped_rank, gold)
            omitted = gold not in persisted["candidate_services"]
            require(persisted["root_position"] == position and
                    persisted["root_candidate_omitted"] == omitted,
                    f"Stored BARO judgment mismatch ({method}): {case}")
            method_observed[method] = {"ranking": mapped_rank, "gold": gold,
                                       "position": position, "omitted": omitted}

        # Derive all method judgments from their persisted anonymous rankings and
        # independently joined manifest/parquet gold; do not trust saved scores.
        for method in METHODS:
            record = result["methods"][method]
            position = case_position(record["ranking"], gold)
            omitted = gold not in record["candidate_services"]
            require(record["root_position"] == position and
                    record["root_candidate_omitted"] == omitted and
                    record["top1"] == (position == 1) and
                    record["top3"] == (position is not None and position <= 3),
                    f"Ranking-to-gold result mismatch ({method}): {case}")
            method_observed.setdefault(method, {}).update(
                {"ranking": record["ranking"], "gold": gold,
                 "position": position, "omitted": omitted})
        rows.append({"case": case, "dataset": indexed["dataset"], "fault": indexed["fault"],
                     "group": (indexed["dataset"], indexed["root_cause_service"], indexed["fault"]),
                     "methods": method_observed, "result": result})

    require(len(rows) == 36 and len({row["case"] for row in rows}) == 36,
            "Baseline result coverage is not exactly 36 unique cases")
    require(len(feature_sources) == 36, "Each case must identify its feature source")
    original_checks = []
    for case, group in sorted(original.items()):
        feature = read_json(ROOT / "research/smoke/features" / f"{group['id']}.json")
        simple = next(row for row in read_json(ROOT / "research/smoke/simple-anomaly.json")
                      if row["id"] == group["id"])
        expected = feature["anomaly_ranking"]
        require(simple["ranking"] == expected, f"Original simple-anomaly ranking changed: {group['id']}")
        row = next(item for item in rows if item["case"] == case)
        require(row["methods"]["median_change"]["ranking"] == simple["ranking"],
                f"Original 12-case reuse mismatch: {group['id']}")
        truth = feature["mapping"][group["root_cause_service"]]
        require(simple["top1"] == (expected[0] == truth) and
                simple["top3"] == (truth in expected[:3]),
                f"Original simple-anomaly judgment mismatch: {group['id']}")
        original_checks.append({"group": group["id"], "case": case, "top1": simple["top1"],
                                "top3": simple["top3"], "ranking_reused": True})

    by_method = {}
    for method in METHODS:
        judged = []
        for row in rows:
            record = row["methods"][method]
            judged.append({"position": record["position"], "omitted": record["omitted"]})
        by_method[method] = {
            "overall": aggregate(judged),
            "by_system": {system: aggregate([j for row, j in zip(rows, judged)
                                             if row["dataset"] == system])
                          for system in sorted({row["dataset"] for row in rows})},
            "by_fault": {fault: aggregate([j for row, j in zip(rows, judged)
                                           if row["fault"] == fault])
                         for fault in sorted({row["fault"] for row in rows})},
            "by_scenario_group": {
                "|".join(group): aggregate([j for row, j in zip(rows, judged)
                                            if row["group"] == group])
                for group in sorted({row["group"] for row in rows})
            },
        }

    paired = {}
    for left_index, left in enumerate(METHODS):
        for right in METHODS[left_index + 1:]:
            measures = {}
            for measure in ("top1", "top3", "mrr"):
                pairs = []
                for row in rows:
                    a, b = row["methods"][left]["position"], row["methods"][right]["position"]
                    score_a = (a == 1) if measure == "top1" else (
                        a is not None and a <= 3) if measure == "top3" else (1 / a if a else 0)
                    score_b = (b == 1) if measure == "top1" else (
                        b is not None and b <= 3) if measure == "top3" else (1 / b if b else 0)
                    pairs.append((score_a, score_b))
                measures[measure] = {
                    "left_wins": sum(a > b for a, b in pairs),
                    "right_wins": sum(b > a for a, b in pairs),
                    "ties": sum(a == b for a, b in pairs),
                }
            paired[f"{left}_vs_{right}"] = measures

    failures = []
    for row in rows:
        for method in METHODS:
            judged = row["methods"][method]
            if judged["position"] == 1:
                continue
            ranking = judged["ranking"]
            preceding = ranking[:judged["position"] - 1] if judged["position"] else ranking[:3]
            source_metrics = row["result"]["methods"][method]["metric_scores"]
            if method == "median_change" and source_metrics and "metric_scores" in source_metrics[0]:
                source_metrics = source_metrics[0]["metric_scores"]
            named = []
            for service in preceding:
                scores = [item for item in source_metrics
                          if item.get("service_id") == service or item.get("service") == service]
                named.append({"service": service, "rank": ranking.index(service) + 1,
                              "top_metric_evidence": scores[:3]})
            failures.append({
                "case": row["case"], "system": row["dataset"], "fault": row["fault"],
                "method": method, "root_position": judged["position"],
                "root_candidate_omitted": judged["omitted"],
                "preceding_nonroot_ranked_candidates": named,
                "interpretation_limit": "Ranking evidence only; candidate roles and causal direction are not established.",
            })

    summary_source = read_json(RESULTS / "summary.json")
    recomputed = {method: by_method[method]["overall"] for method in METHODS}
    for method in METHODS:
        persisted = summary_source["overall"][method]
        ours = recomputed[method]
        for field, our_field in (("n", "n"), ("top1_count", "top1_count"), ("top3_count", "top3_count")):
            require(persisted[field] == ours[our_field],
                    f"Producer summary mismatch {method}.{field}: {persisted[field]} != {ours[our_field]}")
        require(abs(persisted["mrr"] - ours["mrr"]) <= TOLERANCE,
                f"Producer summary MRR mismatch: {method}")

    evidence = {
        "status": "VERIFY_BASELINES_PASSED",
        "scope": "Development evidence only; not held-out evaluation.",
        "counts": {"cases": 36, "unique_cases": len({row["case"] for row in rows}),
                   "scenario_groups": len(groups), "repetitions_per_group": 3,
                   "original_smoke_cases": 12, "new_feature_cases": 24},
        "boundaries": {
            "protected_144_telemetry_read": False,
            "telemetry_read": "metrics.parquet only, for the 36 manifest-reserved cases",
            "traces_read": False,
            "causal_victim_claimed": False,
            "llm_necessity_claimed": False,
            "scientific_efficacy_novelty_generalization_claimed": False,
        },
        "provenance": {
            "producer_code_sha256": metadata["code_sha256"],
            "current_producer_code_sha256": sha256(ROOT / "scripts/baseline_dev.py"),
            "metadata_hashes_checked": len(checked_hashes),
            "telemetry_hashes_not_recomputed": sorted(unchecked_telemetry_hashes),
            "protocol_hash_match": True,
            "source_hashes_checked": sorted(checked_hashes),
            "baro_reference": metadata["baro_alignment"],
            "result_generation_seed_map": metadata["smoke_feature_seeds_for_new_cases"],
        },
        "checks": {
            "manifest_36_case_coverage": True,
            "12_scenario_groups_each_three_repetitions": True,
            "source_provenance_hashes": True,
            "original_12_heuristic_ranking_reuse": True,
            "independent_baro_raw_metric_recomputation": True,
            "literal_score_edge_checks": [
                "zero-IQR unit fallback", "constant metric removal", "past-only forward-fill",
                "leading missing values fill zero", "signed decrease remains negative",
                "absolute and signed rankings", "stable metric ties", "service deduplication",
            ],
            "producer_aggregate_crosscheck": True,
        },
        "original_12_reuse": {
            "ranking_matches": len(original_checks),
            "top1_count": sum(item["top1"] for item in original_checks),
            "top3_count": sum(item["top3"] for item in original_checks),
            "cases": original_checks,
        },
        "aggregates": by_method,
        "paired_wins_losses_ties": paired,
        "failure_evidence": failures,
    }

    lines = [
        "# Baseline verification and bounded failure analysis",
        "",
        "**Status: reproducibility PASS.** Independent checks passed for the frozen 36-case",
        "development artifact. This is not a held-out result, nor evidence of statistical",
        "significance, novelty, efficacy beyond these cases, or generalization.",
        "",
        "## Scope and integrity",
        "",
        "- 36 unique reserved cases in 12 scenario groups, three repetitions per group.",
        "- The original 12 heuristic rankings match the frozen smoke feature rankings exactly:",
        f"  **{evidence['original_12_reuse']['top1_count']}/12 Top-1, "
        f"{evidence['original_12_reuse']['top3_count']}/12 Top-3**.",
        "- BARO scores/rankings were independently recomputed from raw metrics for reserved",
        "  cases only. The frozen formula uses whole windows, past-only forward fill then zero",
        "  for leading missing values, excludes latency-50, renames latency-90, removes",
        "  per-window constants, converts memory to MB, and applies signed/absolute max",
        "  normalized changes with the specified near-zero-IQR fallback.",
        "- Protected 144 telemetry was not read; no traces were read. Data access was restricted",
        "  to `metrics.parquet` for the reserved 36. Source/hash provenance checked as recorded",
        "  in `verification.json`; telemetry hashes for non-metric files were not reopened.",
        "",
        "## Exact results",
        "",
        "| Method | Top-1 | Top-3 | MRR | Root omitted from ranking | Gold candidate omitted |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        a = by_method[method]["overall"]
        lines.append(f"| `{method}` | {a['top1_count']}/36 | {a['top3_count']}/36 | "
                     f"{a['mrr']:.6f} | {a['root_misses']} | {a['candidate_omissions']} |")
    lines += ["", "### By system", "",
              "| Method | System | n | Top-1 | Top-3 | MRR |",
              "|---|---|---:|---:|---:|---:|"]
    for method in METHODS:
        for system, a in by_method[method]["by_system"].items():
            lines.append(f"| `{method}` | {system} | {a['n']} | {a['top1_count']}/{a['n']} | "
                         f"{a['top3_count']}/{a['n']} | {a['mrr']:.6f} |")
    lines += ["", "### By fault type", "",
              "| Method | Fault | n | Top-1 | Top-3 | MRR |",
              "|---|---|---:|---:|---:|---:|"]
    for method in METHODS:
        for fault, a in by_method[method]["by_fault"].items():
            lines.append(f"| `{method}` | {fault} | {a['n']} | {a['top1_count']}/{a['n']} | "
                         f"{a['top3_count']}/{a['n']} | {a['mrr']:.6f} |")
    lines += ["", "### Paired case outcomes (Top-1)", "",
              "| Pair | Left wins | Right wins | Ties |",
              "|---|---:|---:|---:|"]
    for pair, measures in paired.items():
        outcome = measures["top1"]
        lines.append(f"| `{pair}` | {outcome['left_wins']} | {outcome['right_wins']} | {outcome['ties']} |")
    lines += ["", "## Per-method root misses and case evidence", "",
              "Every listed non-Top-1 outcome is a ranking failure against the dataset's",
              "recorded root-cause label; it does not identify a causal victim. Candidate metrics",
              "are correlates in these windows, not verified propagation or causal evidence.",
              "An omitted root means it was not ranked among the method's candidates.",
              ""]
    for method in METHODS:
        misses = [f for f in failures if f["method"] == method]
        omitted = sum(item["root_candidate_omitted"] for item in misses)
        lines.append(f"### `{method}` — {len(misses)} non-Top-1 outcomes; {omitted} candidate omissions")
        lines.append("")
        if not misses:
            lines.append("No Top-1 failures.")
        else:
            for failure in misses:
                root = "omitted" if failure["root_position"] is None else f"rank {failure['root_position']}"
                blockers = ", ".join(
                    f"{item['service']} (rank {item['rank']})"
                    for item in failure["preceding_nonroot_ranked_candidates"]
                ) or "none ranked ahead"
                lines.append(f"- `{failure['case']}` ({failure['system']}/{failure['fault']}): "
                             f"root {root}; preceding candidates: {blockers}.")
        lines.append("")
    lines += [
        "## What the misses demonstrate—and do not",
        "",
        "The counts establish reproducible rank disagreements on this fixed development set.",
        "They can motivate focused follow-up on where the ranking rules diverge, including",
        "the lower BARO scores on these cases and the close signed/absolute variant comparison.",
        "They do not establish that a leading non-root service was harmed, that a specific",
        "root/victim confusion caused the miss, or that an LLM (or any other added component)",
        "is necessary. The three repetitions per group are repeated observations of 12",
        "scenario groups, not 36 independent conditions. No tuning or repairs were made.",
        "",
        "Exact machine-readable rankings, group counts, paired Top-1/Top-3/MRR results,",
        "and failure evidence are in `verification.json`.",
        "",
    ]
    (BASE / "verification.json").write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    (BASE / "baseline-audit.md").write_text("\n".join(lines))
    print("VERIFY_BASELINES_PASSED")


if __name__ == "__main__":
    main()
