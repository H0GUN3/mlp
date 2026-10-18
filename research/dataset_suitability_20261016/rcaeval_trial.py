"""Metadata-only RCAEval full-scope feasibility trial."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


ROOT = Path("/home/gnho1236/r2")
OUT = ROOT / "research/dataset_suitability_20261016"
INDEX = ROOT / "data/rcaeval/cases.parquet"
README = ROOT / "data/rcaeval/README.md"
TREE = ROOT / "evidence/rcaeval-tree.json"
DOWNLOADS = ROOT / "evidence/rcaeval-downloads.json"
AUDIT = ROOT / "evidence/rcaeval-file-audit.json"
READINESS = ROOT / "evidence/rcaeval-readiness.csv"
PREFIX = "suitability-20261016:"
RELEVANT = {"RE2-OB", "RE2-TT", "RE3-OB", "RE3-TT"}
INDEX_COLUMNS = [
    "case", "dataset", "system", "root_cause_service", "fault", "repetition",
    "has_logs", "n_logs", "has_traces", "n_traces",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    values = (row["system"], row["root_cause_service"], row["fault"])
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"missing group metadata in case {row.get('case')!r}")
    return values


def group_fold(group: tuple[str, str, str]) -> int:
    canonical = json.dumps(group, ensure_ascii=False, separators=(",", ":"))
    return int(hashlib.sha256((PREFIX + canonical).encode()).hexdigest(), 16) % 3


def case_fold(case: str) -> int:
    return int(hashlib.sha256((PREFIX + "case:" + case).encode()).hexdigest(), 16) % 3


def scope_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("dataset") in RELEVANT]


def repetition_histogram(rows: list[dict[str, Any]], dataset: str) -> dict[int, int]:
    conditions = Counter(
        (row["root_cause_service"], row["fault"])
        for row in rows if row["dataset"] == dataset
    )
    return dict(sorted(Counter(conditions.values()).items()))


def validate_rows(rows: list[dict[str, Any]]) -> None:
    required = set(INDEX_COLUMNS)
    seen: set[str] = set()
    for row in rows:
        if not required.issubset(row):
            raise ValueError("metadata row is missing required columns")
        case = row["case"]
        if not isinstance(case, str) or not case or case in seen:
            raise ValueError(f"invalid or duplicate case identifier: {case!r}")
        seen.add(case)
        _key(row)
        if row["dataset"] not in RELEVANT | {"RE1-OB", "RE1-SS", "RE1-TT", "RE2-SS", "RE3-SS"}:
            raise ValueError(f"invalid dataset in {case}: {row['dataset']!r}")
        if not isinstance(row["repetition"], int) or row["repetition"] < 1:
            raise ValueError(f"invalid repetition in {case}")
        for flag in ("has_logs", "has_traces"):
            if not isinstance(row[flag], bool):
                raise ValueError(f"invalid {flag} in {case}")
        for count, flag in (("n_logs", "has_logs"), ("n_traces", "has_traces")):
            value = row[count]
            if not isinstance(value, int) or value < 0 or row[flag] != (value > 0):
                raise ValueError(f"inconsistent {count}/{flag} in {case}")


def partition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_key(row)].append(row)
    assignments = {group: group_fold(group) for group in grouped}
    folds = []
    for fold in range(3):
        held = [row for group, group_rows in grouped.items()
                if assignments[group] == fold for row in group_rows]
        train = [row for group, group_rows in grouped.items()
                 if assignments[group] != fold for row in group_rows]
        folds.append({
            "fold": fold,
            "train_cases": len(train),
            "heldout_cases": len(held),
            "train_groups": len({group for group, assigned in assignments.items() if assigned != fold}),
            "heldout_groups": sum(assigned == fold for assigned in assignments.values()),
            "train_root_support": sorted({row["root_cause_service"] for row in train}),
            "heldout_root_support": sorted({row["root_cause_service"] for row in held}),
            "train_fault_support": sorted({row["fault"] for row in train}),
            "heldout_fault_support": sorted({row["fault"] for row in held}),
            "train_condition_support": sorted(
                f"{system}|{root}|{fault}" for system, root, fault in grouped
                if assignments[(system, root, fault)] != fold
            ),
            "heldout_condition_support": sorted(
                f"{system}|{root}|{fault}" for system, root, fault in grouped
                if assignments[(system, root, fault)] == fold
            ),
        })
    case_assignments: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    condition_counts: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        key = _key(row)
        case_assignments[key].add(case_fold(row["case"]))
        condition_counts[key] += 1
    repeated = {key: assigned for key, assigned in case_assignments.items()
                if condition_counts[key] > 1}
    split_repeated = sum(len(assigned) > 1 for assigned in repeated.values())
    return {
        "grouping": ["system", "root_cause_service", "fault"],
        "group_hash": f"sha256({PREFIX!r} + compact_json(group)) mod 3",
        "group_count": len(grouped),
        "all_groups_single_fold": all(len({assignments[group]}) == 1 for group in grouped),
        "folds": folds,
        "case_level_contrast": {
            "repeated_conditions": len(repeated),
            "conditions_spanning_multiple_case_folds": split_repeated,
            "interpretation": "Case-level assignment splits repetitions within those conditions by construction; descriptive leakage contrast, not performance.",
        },
    }


def transfer_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for system in ("OB", "TT"):
        re2 = [row for row in rows if row["dataset"] == f"RE2-{system}"]
        re3 = [row for row in rows if row["dataset"] == f"RE3-{system}"]
        train_roots = {row["root_cause_service"] for row in re2}
        eval_roots = {row["root_cause_service"] for row in re3}
        train_conditions = {(row["root_cause_service"], row["fault"]) for row in re2}
        eval_conditions = {(row["root_cause_service"], row["fault"]) for row in re3}
        overlap = train_roots & eval_roots
        result[system] = {
            "re2_cases": len(re2),
            "re3_cases": len(re3),
            "re2_index_root_labels_candidate_proxy": sorted(train_roots),
            "re3_index_root_labels": sorted(eval_roots),
            "root_overlap": sorted(overlap),
            "re3_roots_unseen_in_re2": sorted(eval_roots - train_roots),
            "re2_root_fault_conditions": len(train_conditions),
            "re3_root_fault_conditions": len(eval_conditions),
            "re3_conditions_new_to_re2": sorted(
                f"{root}|{fault}" for root, fault in eval_conditions - train_conditions
            ),
            "re3_conditions_overlapping_re2": sorted(
                f"{root}|{fault}" for root, fault in eval_conditions & train_conditions
            ),
            "candidate_proxy_covers_re3_root_labels": eval_roots <= train_roots,
            "candidate_limit": "Index root labels are not an inventory of every service observed in telemetry.",
        }
    return result


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _path_case(path: str) -> tuple[str, str] | None:
    parts = Path(path).parts
    if len(parts) >= 3 and parts[-1] in {"metrics.parquet", "logs.parquet", "traces.parquet"}:
        return parts[-2], parts[-1].removesuffix(".parquet")
    return None


def build_metadata(rows: list[dict[str, Any]], tree: Any, downloads: Any,
                   audit: Any, readiness_text: str) -> dict[str, Any]:
    validate_rows(rows)
    selected = scope_rows(rows)
    counts = Counter(row["dataset"] for row in rows)
    expected = Counter({"RE2-OB": 90, "RE2-TT": 90, "RE3-OB": 30, "RE3-TT": 30})
    if Counter({name: counts[name] for name in expected}) != expected:
        raise ValueError(f"unexpected relevant suite counts: {dict(counts)}")

    tree_entries = tree.get("entries", [])
    tree_paths = {item["path"] for item in tree_entries if item.get("type") == "file"}
    audited: dict[tuple[str, str], dict[str, Any]] = {}
    audit_items = audit if isinstance(audit, list) else audit.get("files", [])
    for item in audit_items:
        parsed = _path_case(item.get("path", ""))
        if parsed:
            audited[parsed] = item

    local_cases = list(csv.DictReader(readiness_text.splitlines()))
    local_by_case = {item["case"]: item for item in local_cases}
    if len(local_by_case) != len(local_cases):
        raise ValueError("duplicate case in readiness metadata")
    expected_local = {row["case"] for row in selected if row["dataset"].startswith("RE2-")}
    if set(local_by_case) != expected_local:
        raise ValueError("readiness case set does not match local RE2 index cases")

    file_check = []
    for row in selected:
        case = row["case"]
        base = case + "/"
        source_present = {
            modality: base + modality + ".parquet" in tree_paths
            for modality in ("metrics", "logs", "traces")
        }
        if not source_present["metrics"] or source_present["logs"] != row["has_logs"] or source_present["traces"] != row["has_traces"]:
            raise ValueError(f"index availability flags disagree with file manifest: {case}")
        audit_counts = {}
        if case in expected_local:
            for modality in ("metrics", "logs", "traces"):
                item = audited.get((case, modality))
                should_exist = modality == "metrics" or row[f"has_{modality}"]
                if should_exist != (item is not None):
                    raise ValueError(f"local audit file mismatch for {case}/{modality}")
                if item is not None:
                    audit_counts[modality] = item.get("rows")
                    if not isinstance(item.get("rows"), int) or item["rows"] <= 0:
                        raise ValueError(f"invalid audited row count for {case}/{modality}")
            readiness = local_by_case[case]
            if row["has_logs"] != (int(readiness["logs_rows"]) > 0):
                raise ValueError(f"readiness log count contradicts index flag for {case}")
            if row["has_traces"] != (int(readiness["traces_rows"]) > 0):
                raise ValueError(f"readiness trace count contradicts index flag for {case}")
        file_check.append({
            "case": case,
            "dataset": row["dataset"],
            "source_manifest_files": source_present,
            "locally_audited_row_counts": audit_counts,
        })

    repetition_distribution = {
        dataset: repetition_histogram(selected, dataset) for dataset in sorted(RELEVANT)
    }
    suites = {}
    for dataset in sorted(RELEVANT):
        suite_rows = [row for row in selected if row["dataset"] == dataset]
        condition_counts = Counter((row["root_cause_service"], row["fault"]) for row in suite_rows)
        suites[dataset] = {
            "cases": len(suite_rows),
            "systems": sorted({row["system"] for row in suite_rows}),
            "root_service_cases": dict(sorted(Counter(row["root_cause_service"] for row in suite_rows).items())),
            "fault_cases": dict(sorted(Counter(row["fault"] for row in suite_rows).items())),
            "root_fault_conditions": len(condition_counts),
            "condition_repetitions": {
                f"{root}|{fault}": count for (root, fault), count in sorted(condition_counts.items())
            },
            "repetition_count_distribution": repetition_distribution[dataset],
            "has_logs_cases": sum(row["has_logs"] for row in suite_rows),
            "has_traces_cases": sum(row["has_traces"] for row in suite_rows),
        }
    source_files = downloads.get("files", []) if isinstance(downloads, dict) else []
    return {
        "full_index_rows": len(rows),
        "relevant_cases": len(selected),
        "excluded_counts": {
            dataset: counts[dataset] for dataset in sorted(counts) if dataset not in RELEVANT
        },
        "suites": suites,
        "repetition_distribution_by_suite": repetition_distribution,
        "local_acquisition": {
            "readiness_cases": len(local_cases),
            "re2_cases": len(expected_local),
            "re3_cases_not_locally_audited": sum(row["dataset"].startswith("RE3-") for row in selected),
            "pinned_source_manifest_file_records": len(source_files),
            "pinned_source_manifest_verified_records": sum(item.get("verified") is True for item in source_files),
            "readiness_rows_match_re2_scope": True,
        },
        "metadata_file_checks": {
            "cases_checked": len(file_check),
            "index_flags_match_source_file_manifest": True,
            "local_re2_files_checked_against_existing_audit": sum(case in expected_local for case in (r["case"] for r in selected)),
            "case_rows": file_check,
        },
        "partitions": partition_summary(selected),
        "re2_to_re3": transfer_summary(selected),
        "existing_split_boundary": {
            "source": "research/reassessment_20261013/adequacy.md and data_catalog.md",
            "declared": "Existing fixed split is preserved: per system 54 train / 18 validation / 18 final-test cases; 18 / 6 / 6 system-root-fault scenarios. This metadata-only trial does not alter or inspect final observations/predictions.",
            "ambiguity": "The cited report gives role counts but this trial does not read the underlying split manifest; mapping its partitions onto all 240 full-scope cases is not established.",
        },
    }


def run() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        import pyarrow as pa
        import numpy as np
    except ImportError as error:
        raise RuntimeError("the configured environment requires PyArrow and NumPy") from error
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    table = pq.read_table(INDEX, columns=INDEX_COLUMNS)
    rows = table.to_pylist()
    tree = _read_json(TREE)
    downloads = _read_json(DOWNLOADS)
    audit = _read_json(AUDIT)
    result = build_metadata(rows, tree, downloads, audit, READINESS.read_text(encoding="utf-8"))
    result["experiment"] = {
        "name": "RCAEval metadata-only full-scope feasibility",
        "date": "2026-10-16",
        "protected_data_accessed": False,
        "raw_telemetry_or_predictions_read": False,
        "numpy_version": np.__version__,
        "pyarrow_version": pa.__version__,
        "python_version": sys.version.split()[0],
        "elapsed_seconds": round(time.perf_counter() - start, 6),
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (INDEX, README, TREE, DOWNLOADS, AUDIT, READINESS)
        },
        "script_sha256": {
            "rcaeval_trial.py": sha256_file(Path(__file__)),
            "test_rcaeval_trial.py": sha256_file(OUT / "test_rcaeval_trial.py"),
        },
    }
    target = OUT / "rcaeval_trial.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return result


def main() -> None:
    result = run()
    print(
        "RCAEVAL_SUITABILITY_PASS "
        f"cases={result['relevant_cases']} groups={result['partitions']['group_count']} "
        f"local={result['local_acquisition']['readiness_cases']}"
    )


if __name__ == "__main__":
    main()
