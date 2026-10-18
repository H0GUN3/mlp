"""Frozen, development-only metric baselines for the RCAEval smoke split."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pyarrow.parquet as pq


BASE = Path(__file__).resolve().parents[1]
SMOKE = BASE / "research" / "smoke"
DATA = BASE / "data" / "rcaeval"
OUT = BASE / "research" / "baselines" / "results"
METHODS = ("median_change", "baro_signed", "baro_absolute_variant")
REFERENCE_COMMIT = "582d4ead3d3301a34fea4e395bfa3f750fc9a40d"
REFERENCE_URLS = {
    "root_cause_analysis": (
        "https://github.com/phamquiluan/baro/blob/582d4ead3d3301a34fea4e395bfa3f750fc9a40d/baro/root_cause_analysis.py"
    ),
    "utility": (
        "https://github.com/phamquiluan/baro/blob/582d4ead3d3301a34fea4e395bfa3f750fc9a40d/baro/utility.py"
    ),
}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def median_change(normal, fault):
    a = np.asarray(normal, dtype=np.float64)
    b = np.asarray(fault, dtype=np.float64)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 20 or len(b) < 20:
        return None
    am, bm = float(np.median(a)), float(np.median(b))
    q25, q75 = np.quantile(a, [0.25, 0.75])
    denominator = max(float(q75 - q25), abs(am) * 0.05, 1e-9)
    return round(min(100.0, abs(bm - am) / denominator), 3), (
        "up" if bm > am else "down" if bm < am else "flat"
    )


def median_rank(ranking):
    """Score boundary deliberately accepts a ranking, never case labels."""
    return list(ranking)


def baro_preprocess(names, values, normal_mask):
    """Apply the frozen BARO read_data/preprocess window rules in NumPy."""
    names = list(names)
    matrix = np.asarray(values, dtype=np.float64).copy()
    if matrix.ndim != 2 or matrix.shape[1] != len(names):
        raise ValueError("metric names and matrix shape disagree")
    matrix[~np.isfinite(matrix)] = np.nan
    for column in range(matrix.shape[1]):
        last = 0.0
        for row in range(matrix.shape[0]):
            if np.isfinite(matrix[row, column]):
                last = matrix[row, column]
            else:
                matrix[row, column] = last

    keep = []
    renamed = []
    for index, name in enumerate(names):
        if name == "time" or name.endswith("_latency-50"):
            continue
        new_name = name[:-len("_latency-90")] + "_latency" if name.endswith("_latency-90") else name
        if new_name in renamed:
            raise ValueError(f"renamed BARO column collision: {new_name}")
        renamed.append(new_name)
        keep.append(index)
    matrix = matrix[:, keep]
    names = renamed

    normal_mask = np.asarray(normal_mask, dtype=bool)
    if matrix.shape[0] != len(normal_mask) or not np.any(normal_mask) or np.all(normal_mask):
        raise ValueError("BARO requires non-empty normal and fault windows")
    normal, fault = matrix[normal_mask], matrix[~normal_mask]

    normal_constant = np.all(normal == normal[0:1], axis=0)
    fault_constant = np.all(fault == fault[0:1], axis=0)
    shared = ~(normal_constant | fault_constant)
    names = [name for name, accepted in zip(names, shared) if accepted]
    matrix = matrix[:, shared]
    for index, name in enumerate(names):
        if name.endswith("_mem"):
            matrix[:, index] /= 1e6
    return names, matrix


def baro_rank(names, values, normal_mask, variant):
    """Rank metrics and deduplicated services without access to any labels."""
    normal_mask = np.asarray(normal_mask, dtype=bool)
    names, matrix = baro_preprocess(names, values, normal_mask)
    normal, fault = matrix[normal_mask], matrix[~normal_mask]
    records = []
    eps_floor = 10 * np.finfo(np.float64).eps
    for order, (name, a, b) in enumerate(zip(names, normal.T, fault.T)):
        center = float(np.median(a))
        q25, q75 = np.quantile(a, [0.25, 0.75])
        scale = float(q75 - q25)
        if scale < eps_floor:
            scale = 1.0
        changes = (b - center) / scale
        score = float(np.max(changes) if variant == "signed" else np.max(np.abs(changes)))
        records.append({"metric": name, "score": score, "normal_median": center,
                        "normal_iqr": float(q75 - q25), "scale": scale,
                        "order": order})
    records.sort(key=lambda row: -row["score"])
    services = []
    for row in records:
        service = row["metric"].split("_", 1)[0]
        if service not in services:
            services.append(service)
    return services, records, names


def self_check():
    assert median_change(np.ones(20), np.full(20, 2)) == (20.0, "up")
    assert median_change(np.ones(20), np.zeros(20)) == (20.0, "down")
    assert median_change(np.full(19, 1.0), np.ones(20)) is None

    # Exercise the public rank path with two windows and explicit edge cases.
    names, matrix = baro_preprocess(
        ["svc_constant", "svc_latency-50", "svc_latency-90", "memory_mem", "time"],
        np.array([[5, 1, 1, 1e-10, 0], [5, np.nan, 2, 2e-10, 1],
                  [5, 2, np.nan, 3e-10, 2], [5, 3, 3, 2e6, 3],
                  [5, 4, 4, 3e6, 4]], dtype=float),
        np.array([True, True, True, False, False]),
    )
    assert names == ["svc_latency", "memory_mem"]
    assert matrix[2, 0] == 2 and matrix[0, 1] == 1e-16
    signed_services, signed_metrics, _ = baro_rank(
        ["up_value", "down_value"],
        np.array([[0, 0], [0, 0], [0, 0], [0, 0], [1, 1],
                  [2, -1], [2, -1], [3, -2.]]),
        np.array([True, True, True, True, True, False, False, False]), "signed"
    )
    absolute_services, _, _ = baro_rank(
        ["up_value", "down_value"],
        np.array([[0, 0], [0, 0], [0, 0], [0, 0], [1, 1],
                  [2, -1], [2, -1], [3, -2.]]),
        np.array([True, True, True, True, True, False, False, False]), "absolute"
    )
    assert signed_services[0] == "up" and absolute_services[0] == "up"
    assert signed_metrics[0]["score"] > 0 and signed_metrics[0]["scale"] == 1.0
    tied, tie_records, _ = baro_rank(
        ["first_cpu", "second_cpu"],
        np.array([[0, 0], [0, 0], [0, 0], [0, 0], [1, 1], [2, 2], [2, 2], [3, 3.]]),
        np.array([True, True, True, True, True, False, False, False]), "signed"
    )
    assert tied == ["first", "second"] and tie_records[0]["metric"] == "first_cpu"
    deduped, _, _ = baro_rank(
        ["same_cpu", "same_mem", "other_cpu"],
        np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0], [1, 1e6, 1],
                  [2, 2e6, 2], [2, 2e6, 2], [3, 3e6, 3.]]),
        np.array([True, True, True, True, True, False, False, False]), "signed"
    )
    assert deduped == ["same", "other"]
    assert median_rank(["S02", "S01"]) == ["S02", "S01"]


def load_smoke_builder():
    sys.path.insert(0, str(BASE / "scripts"))
    from smoke import build_features
    return build_features


def load_inputs():
    manifest = json.loads((SMOKE / "manifest.json").read_text())
    original = {row["case"]: row for row in manifest["cases"]}
    reserved = {case for row in manifest["cases"] for case in row["reserved_development_cases"]}
    index = pq.read_table(DATA / "cases.parquet").to_pylist()
    selected = [record for record in index if record["case"] in reserved]
    if len(selected) != 36 or {record["case"] for record in selected} != reserved:
        raise AssertionError("manifest reserved union does not resolve to exactly 36 indexed cases")
    return manifest, original, reserved, {row["case"]: row for row in selected}


def metric_feature_records(metrics_path, injection):
    table = pq.read_table(metrics_path)
    times = table["time"].to_numpy()
    before = times < injection
    details = []
    for name in table.column_names:
        if name == "time":
            continue
        service, family = name.split("_", 1)
        values = table[name].to_numpy()
        score = median_change(values[before], values[~before])
        details.append({"metric": name, "service": service, "family": family,
                        "score": score[0] if score else None,
                        "direction": score[1] if score else None,
                        "filter_reason": None if score else "fewer_than_20_finite_values_in_a_window"})
    return details


def rank_median_details(details, feature_ranking):
    """The ranking is the persisted smoke result; scores are diagnostic only."""
    ranking = median_rank(feature_ranking)
    return ranking, details


def case_metrics(case_path, injection):
    table = pq.read_table(case_path / "metrics.parquet")
    times = table["time"].to_numpy()
    if not np.any(times < injection) or not np.any(times >= injection):
        raise ValueError(f"case has an empty injection window: {case_path.name}")
    names = [name for name in table.column_names if name != "time"]
    values = np.column_stack([table[name].to_numpy() for name in names]).astype(np.float64)
    return names, values, times < injection


def evaluate_ranking(ranking, truth, all_services):
    position = ranking.index(truth) + 1 if truth in ranking else None
    return {"top1": position == 1, "top3": position is not None and position <= 3,
            "mrr": 1 / position if position else 0.0, "root_position": position,
            "root_candidate_omitted": truth not in all_services}


def aggregate(rows):
    n = len(rows)
    return {"n": n, "top1_count": sum(row["top1"] for row in rows),
            "top3_count": sum(row["top3"] for row in rows),
            "top1": sum(row["top1"] for row in rows) / n if n else 0,
            "top3": sum(row["top3"] for row in rows) / n if n else 0,
            "mrr": sum(row["mrr"] for row in rows) / n if n else 0}


def summarize(rows):
    result = {"overall": {}, "by_system": {}, "by_fault": {}, "root_candidate_omissions": {},
              "paired_outcomes": {}}
    for method in METHODS:
        method_rows = [row["methods"][method] for row in rows]
        result["overall"][method] = aggregate(method_rows)
        result["root_candidate_omissions"][method] = sum(
            row["root_candidate_omitted"] for row in method_rows
        )
        result["by_system"][method] = {
            system: aggregate([row["methods"][method] for row in rows if row["dataset"] == system])
            for system in sorted({row["dataset"] for row in rows})
        }
        result["by_fault"][method] = {
            fault: aggregate([row["methods"][method] for row in rows if row["fault"] == fault])
            for fault in sorted({row["fault"] for row in rows})
        }
    for left_index, left in enumerate(METHODS):
        for right in METHODS[left_index + 1:]:
            comparison = {}
            for measure in ("top1", "top3", "mrr"):
                pairs = [(row["methods"][left][measure], row["methods"][right][measure])
                         for row in rows]
                comparison[measure] = {
                    "left_wins": sum(a > b for a, b in pairs),
                    "right_wins": sum(b > a for a, b in pairs),
                    "ties": sum(a == b for a, b in pairs),
                }
            result["paired_outcomes"][f"{left}_vs_{right}"] = comparison
    return result


def main():
    started = time.monotonic()
    if OUT.exists() and any(OUT.iterdir()):
        raise FileExistsError(f"Refusing to overwrite first-run results in {OUT}")
    self_check()
    manifest, original, reserved, index = load_inputs()
    build_features = load_smoke_builder()
    new_cases = sorted(reserved - set(original))
    seeds = {case: 20262000 + ordinal for ordinal, case in enumerate(new_cases, 1)}
    results = []
    development_feature_paths = []
    allowed_telemetry = {str((DATA / case).resolve()) for case in reserved}

    for record in sorted(index.values(), key=lambda item: (item["dataset"], item["case"])):
        case = record["case"]
        case_path = (DATA / case).resolve()
        if str(case_path) not in allowed_telemetry:
            raise AssertionError(f"refusing telemetry outside reserved development union: {case}")
        injection = int(record["inject_time"])
        if case in original:
            incident = original[case]
            feature_path = SMOKE / "features" / f"{incident['id']}.json"
            features = json.loads(feature_path.read_text())
            feature_source = str(feature_path.relative_to(BASE))
            feature_seed = manifest["seed"] + int(incident["id"].split("-")[1])
            median_scores = []
            for card in features["cards"]:
                for metric in card["metrics"]:
                    median_scores.append({"service_id": card["id"], "family": metric[0],
                                          "score": metric[1], "direction": metric[2],
                                          "source": "persisted_feature_top3"})
        else:
            feature_seed = seeds[case]
            features = build_features(case_path, injection, feature_seed)
            details = metric_feature_records(case_path / "metrics.parquet", injection)
            feature_path = OUT / "development-features" / f"{case}.json"
            dump(feature_path, {"case": case, "seed": feature_seed, "features": features,
                                "metric_scores": details})
            feature_source = str(feature_path.relative_to(BASE))
            development_feature_paths.append(feature_source)
            median_scores = [
                {"service_id": features["mapping"].get(item["service"]), "metric": item["metric"],
                 "family": item["family"], "score": item["score"], "direction": item["direction"],
                 "filter_reason": item["filter_reason"], "source": "smoke.metric_change"}
                for item in details
            ]

        names, values, normal_mask = case_metrics(case_path, injection)
        median_order, _ = rank_median_details(median_scores, features["anomaly_ranking"])
        all_services = [card["id"] for card in features["cards"]]
        method_rankings = {
            "median_change": (median_order, all_services,
                              {"metric_scores": median_scores, "filter_reasons": []}),
        }
        for method, variant in (("baro_signed", "signed"),
                                ("baro_absolute_variant", "absolute")):
            service_order, metric_records, retained = baro_rank(names, values, normal_mask, variant)
            service_order = [features["mapping"].get(service, service) for service in service_order]
            for item in metric_records:
                item["service_id"] = features["mapping"].get(item["metric"].split("_", 1)[0])
            by_service = defaultdict(list)
            for item in metric_records:
                by_service[item["metric"].split("_", 1)[0]].append(item)
            excluded = []
            retained_set = set(retained)
            for name in names:
                if name not in retained_set:
                    excluded.append({"metric": name, "filter_reason": "constant_in_normal_or_fault_window"})
            for name in names:
                if name.endswith("_latency-50"):
                    excluded.append({"metric": name, "filter_reason": "latency-50_removed_by_read_data"})
            candidates = sorted({features["mapping"].get(name.split("_", 1)[0], name.split("_", 1)[0])
                                 for name in retained})
            method_rankings[method] = (service_order, candidates,
                                       {"metric_scores": metric_records, "filter_reasons": excluded})

        method_rows = {}
        for method, (ranking, candidates, scores) in method_rankings.items():
            # The scorer outputs contain anonymous candidates only; gold is joined afterward.
            method_rows[method] = {"ranking": ranking, "candidate_services": candidates,
                                   "metric_scores": scores["metric_scores"],
                                   "filter_reasons": scores["filter_reasons"]}
            method_rows[method].update(evaluate_ranking(ranking, features["mapping"].get(
                record["root_cause_service"], record["root_cause_service"]), all_services))

        root_id = features["mapping"].get(record["root_cause_service"], record["root_cause_service"])
        for method in METHODS:
            method_rows[method]["root_position"] = (
                method_rows[method]["ranking"].index(root_id) + 1
                if root_id in method_rows[method]["ranking"] else None
            )
            method_rows[method]["root_candidate_omitted"] = root_id not in method_rows[method]["candidate_services"]
            method_rows[method]["top1"] = method_rows[method]["root_position"] == 1
            method_rows[method]["top3"] = (
                method_rows[method]["root_position"] is not None and method_rows[method]["root_position"] <= 3
            )
            method_rows[method]["mrr"] = (
                1 / method_rows[method]["root_position"] if method_rows[method]["root_position"] else 0.0
            )
        result = {
            "case": case, "dataset": record["dataset"], "fault": record["fault"],
            "root_cause_service": record["root_cause_service"], "repetition": record["repetition"],
            "inject_time": injection, "feature_source": feature_source, "feature_seed": feature_seed,
            "original_smoke_case": case in original, "methods": method_rows,
        }
        results.append(result)

    summaries = summarize(results)
    simple_top1 = sum(row["methods"]["median_change"]["top1"] for row in results if row["original_smoke_case"])
    simple_top3 = sum(row["methods"]["median_change"]["top3"] for row in results if row["original_smoke_case"])
    if (simple_top1, simple_top3) != (11, 12):
        raise AssertionError(f"persisted smoke median rankings changed: got {simple_top1}/12 and {simple_top3}/12")

    # Failures retain complete comparator ranks, scores, and preceding non-root candidates.
    failures = []
    for row in results:
        for method in METHODS:
            judged = row["methods"][method]
            if judged["top1"]:
                continue
            root = row["root_cause_service"]
            failures.append({
                "case": row["case"], "dataset": row["dataset"], "fault": row["fault"],
                "method": method, "root_candidate_omitted": judged["root_candidate_omitted"],
                "root_position": judged["root_position"], "ranking": judged["ranking"],
                "metric_scores": judged["metric_scores"],
                "preceding_nonroot_services": judged["ranking"][:(judged["root_position"] - 1)
                    if judged["root_position"] else 3],
                "interpretation": "ranked symptom candidate; causal role is not established",
                "root_service_for_report": root,
            })

    input_hashes = {}
    hashed_paths = [
        BASE / "research" / "BASELINE_PROTOCOL.md",
        BASE / "scripts" / "baseline_dev.py",
        BASE / "scripts" / "smoke.py",
        BASE / "scripts" / "audit.py",
        BASE / "research" / "baselines" / "reference" / "baro-root-cause-analysis.py",
        BASE / "research" / "baselines" / "reference" / "baro-utility.py",
        SMOKE / "manifest.json", SMOKE / "simple-anomaly.json", DATA / "cases.parquet",
    ]
    hashed_paths.extend(SMOKE / "features" / f"{incident['id']}.json" for incident in original.values())
    for case in sorted(reserved):
        hashed_paths.extend((DATA / case / name) for name in
                            ("metrics.parquet", "traces.parquet", "inject_time.txt"))
    for path in hashed_paths:
        if path.name in ("metrics.parquet", "traces.parquet", "inject_time.txt"):
            if str(path.parent.resolve()) not in allowed_telemetry:
                raise AssertionError(f"refusing to hash telemetry outside allowed case union: {path}")
        input_hashes[str(path.relative_to(BASE))] = sha256(path)

    metadata = {
        "artifact_version": 1, "protocol": "research/BASELINE_PROTOCOL.md",
        "protocol_sha256": input_hashes["research/BASELINE_PROTOCOL.md"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development-only reserved union; 36 cases; 12 repeated groups",
        "case_count": len(results), "reserved_development_cases": sorted(reserved),
        "original_smoke_case_ids": sorted(original),
        "methods": list(METHODS), "smoke_feature_seeds_for_new_cases": seeds,
        "runtime": {"python": sys.version, "platform": platform.platform(),
                    "numpy": np.__version__, "pyarrow": __import__("pyarrow").__version__},
        "baro_alignment": {"release": "0.2.0", "commit": REFERENCE_COMMIT,
                           "reference_urls": REFERENCE_URLS,
                           "execution_note": "NumPy code-aligned score path; not original BARO execution or full BOCPD reproduction"},
        "input_sha256": input_hashes,
        "code_sha256": input_hashes["scripts/baseline_dev.py"],
        "telemetry_access": {"allowed_case_count": 36, "protected_144_accessed": False,
                             "access_basis": "strict membership assertion against reserved manifest union"},
        "original_smoke_median_check": {"top1": simple_top1, "top1_n": 12,
                                        "top3": simple_top3, "top3_n": 12},
    }
    dump(OUT / "metadata.json", metadata)
    for row in results:
        dump(OUT / "cases" / f"{row['case']}.json", row)
    dump(OUT / "summary.json", summaries)
    dump(OUT / "failures.json", failures)
    dump(OUT / "development-feature-index.json", {
        "count": len(development_feature_paths), "features": development_feature_paths,
        "original_smoke_features_reused": sorted(
            row["feature_source"] for row in results if row["original_smoke_case"]
        ),
    })
    dump(OUT / "verification.json", {
        "self_checks": {"passed": True, "checks": [
            "median up/down and finite sample threshold", "forward-fill and leading-zero behavior",
            "latency-50 exclusion and latency-90 rename", "per-window constant removal",
            "near-zero IQR scale fallback", "stable metric tie order and service deduplication",
            "median ranking uses persisted rankings without labels",
        ]},
        "case_count": len(results), "unique_case_count": len({row["case"] for row in results}),
        "original_smoke_median_top1": simple_top1, "original_smoke_median_top3": simple_top3,
        "protected_144_telemetry_accessed": False,
        "runtime_seconds": time.monotonic() - started,
        "all_methods_have_per_case_rankings": all(
            set(row["methods"]) == set(METHODS) for row in results
        ),
    })
    print(f"BASELINE_DEV_COMPLETE cases={len(results)} unique={len({row['case'] for row in results})} "
          f"median_original={simple_top1}/12,{simple_top3}/12", flush=True)


if __name__ == "__main__":
    main()
