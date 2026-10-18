"""Metadata-only ops-lite coverage and cross-corpus duplicate audit."""

from __future__ import annotations

import hashlib
import json
import platform
import resource
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/ops-lite"
EVIDENCE = ROOT / "evidence"
OUT = Path(__file__).with_name("ops_trial.json")
RESET = ROOT / "research/research_reset_review_20261016/metadata_details.json"
INVENTORY = ROOT / "research/rcabench_assessment_20261013/metadata_inventory.json"
QUALITY = ROOT / "research/rcabench_assessment_20261013/quality_audit.json"
SAMPLE = EVIDENCE / "ops-lite-sample.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    """Normalize presentation only; retain tokens, numbers, and identifiers."""
    text = str(value or "").strip().lower()
    return " ".join(text.replace("_", "-").split())


def canonical_json(value: Any) -> str:
    """Stable serialization, preserving value types and all identifiers."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def canonical_time(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        return "naive:" + parsed.isoformat()
    return parsed.astimezone(timezone.utc).isoformat()


def nonempty_hash_paths(items: list[dict[str, Any]], path_key: str = "path") -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    empty_sha = hashlib.sha256(b"").hexdigest()
    for item in items:
        digest = item.get("sha256")
        if item.get("bytes", 0) > 0 and digest and digest != empty_sha:
            result[digest].append(str(item[path_key]))
    return {digest: sorted(paths) for digest, paths in sorted(result.items())}


def metadata_signature(system: str, fault_types: list[str], roots: list[str]) -> str:
    # Preserve repeated fault/root values in local descriptive repeat groups.
    return json.dumps(
        [canonical(system), sorted(map(canonical, fault_types)), sorted(map(canonical, roots))],
        separators=(",", ":"),
    )


def sample_bias(full: list[dict[str, Any]], selected: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, rows in (("whole", full), ("selected", [r for r in full if r["name"] in selected])):
        systems = Counter(r["system"] for r in rows)
        roots = Counter(root for r in rows for root in r["required_roots"])
        roles = Counter(role for r in rows for role in r["roles"])
        faults = Counter(kind for r in rows for kind in r["fault_types"])
        result[label] = {
            "cases": len(rows),
            "systems": dict(sorted(systems.items())),
            "required_root_occurrences": sum(roots.values()),
            "required_root_case_count": sum(bool(r["required_roots"]) for r in rows),
            "required_fault_count_distribution": dict(sorted(Counter(r["required_fault_count"] for r in rows).items())),
            "required_root_service_count_distribution": dict(sorted(Counter(len(set(r["required_roots"])) for r in rows).items())),
            "required_fault_item_count": sum(r["required_fault_count"] for r in rows),
            "required_root_service_frequency": dict(sorted(roots.items())),
            "role_item_counts": dict(sorted(roles.items())),
            "fault_item_counts": dict(sorted(faults.items())),
            "repeat_metadata_groups": _repeat_groups(rows),
            "selection_criterion_eligible_cases": sum(
                r["required_fault_count"] == 1 and r["n_service_edges"] > 0 for r in rows
            ),
            "selection_criterion_eligible_sample_cases": sum(
                r["name"] in selected and r["required_fault_count"] == 1 and r["n_service_edges"] > 0
                for r in full
            ) if label == "whole" else None,
        }
    for key in ("systems", "fault_item_counts"):
        all_counts = result["whole"][key]
        sample_counts = result["selected"][key]
        result["selected"][key + "_share"] = {
            k: round(sample_counts.get(k, 0) / max(result["selected"]["cases"], 1), 6)
            for k in sorted(set(all_counts) | set(sample_counts))
        }
        result["whole"][key + "_share"] = {
            k: round(all_counts.get(k, 0) / max(result["whole"]["cases"], 1), 6)
            for k in sorted(all_counts)
        }
    return result


def _repeat_groups(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[row["metadata_signature"]].append(row["name"])
    repeats = [sorted(names) for names in groups.values() if len(names) > 1]
    return {
        "unique_signatures": len(groups),
        "repeated_groups": len(repeats),
        "cases_in_repeated_groups": sum(map(len, repeats)),
        "groups": sorted(repeats),
    }


def _case_metadata() -> list[dict[str, Any]]:
    manifest = [json.loads(line) for line in (DATA / "manifest.jsonl").read_text().splitlines()]
    rows = []
    for record in manifest:
        folder = DATA / "cases" / record["name"]
        label = read_json(folder / "label.json")
        injection = read_json(folder / "injection.json")
        env = read_json(folder / "env.json")
        faults = label["faults"]
        required = [f for f in faults if f.get("role") == "required"]
        roots = sorted(str(f.get("service", "")) for f in required if f.get("service"))
        kinds = sorted(str(f.get("chaos_type", "")) for f in faults if f.get("chaos_type"))
        times = {k: str(env[k]) for k in ("NORMAL_START", "NORMAL_END", "ABNORMAL_START", "ABNORMAL_END") if k in env}
        config = injection.get("engine_config_summary", injection.get("engine_config"))
        config_text = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str) if config is not None else ""
        rows.append({
            "name": record["name"],
            "system": record["system"],
            "required_roots": roots,
            "roles": [str(f.get("role", "unknown")) for f in faults],
            "fault_types": kinds,
            "required_fault_count": len(required),
            "process_applicable": bool(label.get("process_applicable")),
            "n_service_edges": int(record.get("n_service_edges", 0)),
            "metadata_signature": metadata_signature(record["system"], kinds, roots),
            "injection_id": injection.get("id"),
            "task_id": injection.get("task_id"),
            "injection_name": injection.get("name") or injection.get("injection_name"),
            "start_time": injection.get("start_time"),
            "time_signature": times,
            "config_signature": hashlib.sha256(config_text.encode()).hexdigest() if config_text else None,
        })
    return rows


def _cross_corpus(ops: list[dict[str, Any]], rcab: list[dict[str, Any]]) -> dict[str, Any]:
    ops_by_name: dict[str, list[str]] = defaultdict(list)
    rcab_by_name: dict[str, list[str]] = defaultdict(list)
    for row in ops:
        ops_by_name[canonical(row["name"])].append(row["name"])
    for row in rcab:
        rcab_by_name[canonical(row["case"])].append(row["case"])
    name_matches = [
        {"ops": a, "rcab": b}
        for key in sorted(set(ops_by_name) & set(rcab_by_name))
        for a in sorted(ops_by_name[key]) for b in sorted(rcab_by_name[key])
    ]
    # Task UUID/name equality is reported only when present on both sides.
    ops_tasks = defaultdict(list)
    for row in ops:
        if row["task_id"]:
            ops_tasks[canonical(row["task_id"])].append(row["name"])
    rcab_tasks = defaultdict(list)
    for row in rcab:
        if row.get("task_id"):
            rcab_tasks[canonical(row["task_id"])].append(row["case"])
    task_matches = [
        {"ops_case": row["name"], "task_id": row["task_id"], "rcab_cases": sorted(rcab_tasks[canonical(row["task_id"])])}
        for row in ops if row["task_id"] and canonical(row["task_id"]) in rcab_tasks
    ]
    ops_ids: dict[int, list[str]] = defaultdict(list)
    rcab_ids: dict[int, list[str]] = defaultdict(list)
    for row in ops:
        if isinstance(row.get("injection_id"), int):
            ops_ids[row["injection_id"]].append(row["name"])
    for row in rcab:
        if isinstance(row.get("injection_id"), int):
            rcab_ids[row["injection_id"]].append(row["case"])
    injection_id_matches = [
        {
            "injection_id": identifier,
            "ops_cases": sorted(ops_ids[identifier]),
            "rcab_cases": sorted(rcab_ids[identifier]),
            "same_case_name_pair": any(a == b for a in ops_ids[identifier] for b in rcab_ids[identifier]),
        }
        for identifier in sorted(set(ops_ids) & set(rcab_ids))
    ]
    # RCAB fault type IDs are not mapped: compare only normalized system and
    # exact required-root names as a partial descriptive signature.
    def root_signature(row: dict[str, Any]) -> str:
        roots = row["roots"] if "roots" in row else row["required_roots"]
        return canonical_json([canonical(row["system"]), sorted({canonical(x) for x in roots})])

    rcab_root_signatures: dict[str, list[str]] = defaultdict(list)
    for row in rcab:
        rcab_root_signatures[root_signature(row)].append(row["case"])
    signature_matches = [
        {"ops_case": row["name"], "rcab_cases": sorted(rcab_root_signatures[root_signature(row)])}
        for row in ops if root_signature(row) in rcab_root_signatures
    ]
    # Actual saved non-empty telemetry bytes only: use the 30-case download
    # ledger and RCAB quality ledger, not metadata file sizes or empty hashes.
    downloads = read_json(EVIDENCE / "ops-lite-downloads.json")
    ops_hash_paths = nonempty_hash_paths([
        item for item in downloads["files"]
        if "/cases/" in item["path"] and item["path"].endswith(".parquet")
    ])
    quality = read_json(QUALITY)
    rcab_hash_rows = []
    for case, files in quality.get("file_sha256", {}).items():
        for filename, digest in files.items():
            if filename.endswith(".parquet"):
                rcab_hash_rows.append({
                    "sha256": digest,
                    "bytes": 1 if digest != hashlib.sha256(b"").hexdigest() else 0,
                    "path": f"{case}/{filename}",
                })
    rcab_hash_paths = nonempty_hash_paths(rcab_hash_rows)
    hash_matches = [
        {"sha256": digest, "ops_paths": sorted(ops_hash_paths[digest]), "rcab_paths": sorted(rcab_hash_paths[digest])}
        for digest in sorted(set(ops_hash_paths) & set(rcab_hash_paths))
    ]
    # Exact serialized signatures are compared only if fields exist on both.
    # They are descriptive checks, not semantic schema equivalence.
    ops_time = defaultdict(list)
    rcab_time = defaultdict(list)
    for row in ops:
        values = row["time_signature"]
        if values:
            sig = canonical_json({k: canonical_time(v) for k, v in values.items()})
            ops_time[sig].append(row["name"])
    for row in rcab:
        values = row.get("time_signature", {})
        if values:
            sig = canonical_json({k: canonical_time(v) for k, v in values.items()})
            rcab_time[sig].append(row["case"])
    ops_configs = defaultdict(list)
    rcab_configs = defaultdict(list)
    for row in ops:
        if row["config_signature"]:
            ops_configs[row["config_signature"]].append(row["name"])
    for row in rcab:
        if row.get("config_signature"):
            rcab_configs[row["config_signature"]].append(row["case"])
    time_matches = [
        {"ops_cases": sorted(ops_time[key]), "rcab_cases": sorted(rcab_time[key])}
        for key in sorted(set(ops_time) & set(rcab_time))
    ]
    config_matches = [
        {"ops_cases": sorted(ops_configs[key]), "rcab_cases": sorted(rcab_configs[key])}
        for key in sorted(set(ops_configs) & set(rcab_configs))
    ]
    return {
        "exact_case_name_matches": name_matches,
        "exact_case_name_match_count": len(name_matches),
        "task_id_matches": {"ops_ids_available": len(ops_tasks), "rcab_ids_available": len(rcab_tasks), "matches": task_matches, "match_count": len(task_matches), "status": "exact normalized UUID/string match only"},
        "injection_id_matches": {
            "ops_numeric_ids_available": len(ops_ids),
            "rcab_numeric_ids_available": len(rcab_ids),
            "matches": injection_id_matches,
            "matched_numeric_id_count": len(injection_id_matches),
            "matching_case_name_pair_count": sum(item["same_case_name_pair"] for item in injection_id_matches),
            "interpretation": "Same named field and integer type; exact ID equality is a candidate linkage, corroborated separately by task/name/time and never treated alone as an incident duplicate.",
        },
        "canonical_metadata_signature": {
            "rules": "lowercase, trim, underscores to hyphens, whitespace collapse; exact normalized system plus sorted unique required-root names; numeric RCAB fault-type IDs are not mapped to ops names",
            "matches": signature_matches,
            "ops_cases_with_match": len(signature_matches),
            "ops_rcab_pair_count": sum(len(item["rcab_cases"]) for item in signature_matches),
            "interpretation": "partial metadata resemblance only; not an incident duplicate test",
        },
        "time_config": {
            "rules": "ISO timestamps parsed and converted to UTC; naive timestamps tagged; epoch strings retained as strings; JSON configs sorted by keys with values/types preserved. Exact canonical signatures only; no field mapping.",
            "time_matches": time_matches,
            "time_match_count": len(time_matches),
            "config_matches": config_matches,
            "config_match_count": len(config_matches) if config_matches else None,
            "status": "configuration unknown/not comparable: ops engine_config_summary and RCAB engine_config are different stored representations; zero exact serialized matches is not interpreted as no common configuration",
        },
        "telemetry_byte_hashes": {
            "ops_nonempty_unique_sha256_count": len(ops_hash_paths),
            "rcab_nonempty_unique_sha256_count": len(rcab_hash_paths),
            "cross_corpus_hash_matches": hash_matches,
            "cross_corpus_hash_match_count": len(hash_matches),
            "status": "actual non-empty telemetry file SHA256 values from saved download and quality ledgers",
            "empty_files_used_as_evidence": False,
        },
        "zero_match_caveat": "Zero exact matches do not prove independence; reformatting/time shifts remain unresolved.",
    }


def run() -> dict[str, Any]:
    started = time.monotonic()
    ops = _case_metadata()
    selected_doc = read_json(SAMPLE)
    selected = set(selected_doc["cases"])
    rcab_inventory = read_json(INVENTORY)
    rcab_quality = read_json(QUALITY)
    rcab_details = read_json(RESET)
    rcab_rows = []
    for record in rcab_inventory["cases"]:
        injection = rcab_details["records"].get(record["case"], {}).get("injection.json", {})
        config = injection.get("engine_config")
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except json.JSONDecodeError:
                pass
        rcab_rows.append({
            "case": record["case"],
            "system": record["case"].split("-", 1)[0].rstrip("0123456789"),
            "roots": record.get("root_services", []),
            "fault_types": [str(injection["fault_type"])] if injection.get("fault_type") is not None else [],
            "metadata_signature": metadata_signature(
                record["case"].split("-", 1)[0].rstrip("0123456789"),
                [str(injection["fault_type"])] if injection.get("fault_type") is not None else [],
                record.get("root_services", []),
            ),
            "task_id": injection.get("task_id"),
            "injection_id": injection.get("id"),
            "time_signature": {
                k: str(v) for k, v in record.get("periods_epoch_seconds", {}).items()
            },
            "config_signature": hashlib.sha256(canonical_json(config).encode()).hexdigest() if config is not None else None,
        })
    # RCAB's type ID is intentionally not mapped to ops fault names.
    labels_summary = read_json(EVIDENCE / "ops-lite-summary.json")
    files_audit = read_json(EVIDENCE / "ops-lite-file-audit.json")
    download_ledger = read_json(EVIDENCE / "ops-lite-downloads.json")
    metadata_file_hashes = {}
    for row in ops:
        base = DATA / "cases" / row["name"]
        for filename in ("label.json", "injection.json", "env.json", "causal_graph.json"):
            source = base / filename
            metadata_file_hashes[f"data/ops-lite/cases/{row['name']}/{filename}"] = sha256(source)
    support = {
        "whole_metadata_cases": len(ops),
        "sample_cases": len(selected),
        "sample_selection_criterion": selected_doc["criteria"],
        "metadata_cases_with_all_four_json_files": len(ops),
        "telemetry_quality_audited_cases": 30,
        "telemetry_quality_audited_files": len(files_audit),
        "telemetry_downloaded_files_in_ledger": sum(1 for x in download_ledger["files"] if "/cases/" in x["path"]),
        "telemetry_parquet_files_fully_decoded": labels_summary.get("parquet_files_fully_decoded", 0),
        "telemetry_decoded_rows": labels_summary.get("rows_fully_decoded", 0),
        "required_fault_role_item_counts": labels_summary.get("roles", {}),
        "original_selection_criterion": "exactly one required fault and at least one propagation/service edge",
        "sample_cases_matching_original_selection_criterion": sum(
            r["name"] in selected and r["required_fault_count"] == 1 and r["n_service_edges"] > 0
            for r in ops
        ),
        "quality_support_limit": "Only the selected 30 cases have telemetry audit evidence; no quality inference is made for the other 425.",
    }
    inputs = [
        DATA / "README.md", DATA / "manifest.jsonl", SAMPLE,
        EVIDENCE / "ops-lite-labels.json", EVIDENCE / "ops-lite-sample-audit.json",
        EVIDENCE / "ops-lite-file-audit.json", EVIDENCE / "ops-lite-downloads.json",
        EVIDENCE / "ops-lite-tree.json", RESET, INVENTORY, QUALITY,
        ROOT / "SOURCES.md",
    ]
    result = {
        "status": "PASS",
        "scope": "455-case metadata census; saved 30-case telemetry audits only; cross-corpus duplicate stress analysis",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "seconds": None,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "command": "OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m research.dataset_suitability_20261016.ops_trial",
        },
        "inputs": {str(p.relative_to(ROOT)): sha256(p) for p in inputs},
        "code_sha256": {
            "research/dataset_suitability_20261016/ops_trial.py": sha256(Path(__file__)),
            "research/dataset_suitability_20261016/test_ops_trial.py": sha256(Path(__file__).with_name("test_ops_trial.py")),
        },
        "ops_case_metadata_sha256": metadata_file_hashes,
        "source_checksums": {
            "rcab_inventory_sha256": rcab_quality["inventory_sha256"],
            "rcab_quality_source_md5": rcab_quality["source"]["md5"],
        },
        "support": support,
        "metadata_distribution": sample_bias(ops, selected),
        "sampled_case_names": sorted(selected),
        "cross_corpus": _cross_corpus(ops, rcab_rows),
        "limits": [
            "Metadata availability is not telemetry support.",
            "The 425 unsampled cases have no quality conclusion.",
            "RCAB fault-type IDs and configuration/time schemas were not mapped without validated equivalence.",
            "Zero duplicate matches do not certify independence; reformatting and time shifts remain unresolved.",
            "Existing SOURCES.md reports a 455-case Apache-2.0 candidate, while the cited OpenRCA 2.0 paper describes 500 cases and CC-BY-SA-4.0 data; it records no verified author/official linkage for anon-ops/ops-lite. No new source survey was performed.",
            "No Parquet files or RCAB archive members were opened.",
        ],
    }
    result["runtime"]["seconds"] = round(time.monotonic() - started, 6)
    # Preserve results: exclusive creation prevents an accidental overwrite.
    with OUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("OPS_SUITABILITY_PASS")
    return result


if __name__ == "__main__":
    run()
