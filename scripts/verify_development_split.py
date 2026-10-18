#!/usr/bin/env python3
"""Build and verify the RCAEval development-only split audit artifact."""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/BASELINE_PROTOCOL.md"
MANIFEST = ROOT / "research/smoke/manifest.json"
SUMMARY = ROOT / "evidence/rcaeval-summary.json"
PARQUET = ROOT / "data/rcaeval/cases.parquet"
OUTPUT = ROOT / "research/baselines/split-audit.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    protocol_text = PROTOCOL.read_text()
    manifest = json.loads(MANIFEST.read_text())
    summary = json.loads(SUMMARY.read_text())

    require("최종 시험" in protocol_text, "Protocol must define final-test boundary")
    incidents = manifest["cases"]
    require(len(incidents) == 12, "Manifest must contain exactly 12 smoke incidents")
    reserved = []
    groups = []
    for incident in incidents:
        ids = incident["reserved_development_cases"]
        require(len(ids) == 3, f"{incident['id']} must reserve three repetitions")
        require(incident["case"] in ids, f"{incident['id']} smoke case not reserved")
        reserved.extend(ids)
        groups.append(
            {
                "group_id": incident["id"],
                "system": incident["dataset"],
                "root_cause_service": incident["root_cause_service"],
                "fault": incident["fault"],
                "case_ids": ids,
            }
        )
    require(len(reserved) == 36, "Expected 36 reserved development IDs")
    require(len(set(reserved)) == 36, "Reserved development IDs are not unique")

    table = pq.read_table(
        PARQUET,
        columns=["case", "dataset", "system", "root_cause_service", "fault", "repetition"],
    )
    relevant = [
        row
        for row in table.to_pylist()
        if row["dataset"] in ("RE2-OB", "RE2-TT")
    ]
    ids = [row["case"] for row in relevant]
    require(len(relevant) == 180, "Expected 180 RE2-OB/RE2-TT parquet cases")
    require(len(set(ids)) == 180, "RE2-OB/RE2-TT case IDs are not unique")
    dataset_counts = {
        name: sum(row["dataset"] == name for row in relevant)
        for name in ("RE2-OB", "RE2-TT")
    }
    require(dataset_counts == {"RE2-OB": 90, "RE2-TT": 90}, "Unexpected dataset counts")
    by_id = {row["case"]: row for row in relevant}
    missing = sorted(set(reserved) - set(by_id))
    require(not missing, f"Reserved cases absent from parquet: {missing}")
    require(
        set(reserved) <= set(ids),
        "The reserved development set must be a subset of the smoke IDs' universe",
    )

    for group in groups:
        found = [by_id[case_id] for case_id in group["case_ids"]]
        require(
            {row["repetition"] for row in found} == {1, 2, 3},
            f"{group['group_id']} does not contain repetitions 1, 2, 3",
        )
        require(
            all(
                row["dataset"] == group["system"]
                and row["root_cause_service"] == group["root_cause_service"]
                and row["fault"] == group["fault"]
                for row in found
            ),
            f"{group['group_id']} metadata does not match parquet",
        )

    protected = sorted(set(ids) - set(reserved))
    require(len(protected) == 144, "Expected 144 protected/unassigned cases")
    require(not (set(reserved) & set(protected)), "Reserved/protected overlap")
    require(set(reserved) | set(protected) == set(ids), "Split does not cover RE2 cases")
    owner = {case_id: group["group_id"] for group in groups for case_id in group["case_ids"]}
    grouped = {}
    for row in relevant:
        key = (row["dataset"], row["root_cause_service"], row["fault"])
        grouped.setdefault(key, set()).add(row["case"])
    for key, case_ids in grouped.items():
        selected = case_ids & set(reserved)
        if selected:
            require(case_ids <= set(reserved), f"Scenario group crosses boundary: {key}")
            require(
                len({owner[case_id] for case_id in selected}) == 1,
                f"Scenario group has multiple owners: {key}",
            )
        else:
            require(case_ids <= set(protected), f"Unreserved scenario crosses boundary: {key}")

    require(summary["cases"] == 180, "Evidence summary must report 180 cases")
    require(summary["by_system"] == {"RE2-OB": 90, "RE2-TT": 90}, "Evidence counts mismatch")
    artifact = {
        "status": "development_split_guard_passed",
        "purpose": "RCA baseline development-stage split audit only",
        "final_test_set": False,
        "partition_assignment": None,
        "counts": {
            "smoke_cases": len(incidents),
            "reserved_development_cases": len(reserved),
            "scenario_groups": len(groups),
            "cases_re2_ob_tt_total": len(relevant),
            "protected_unassigned_cases": len(protected),
        },
        "reserved_development_case_ids": sorted(reserved),
        "scenario_groups": groups,
        "protected_unassigned_case_ids": protected,
        "input_sha256": {
            "protocol": sha256(PROTOCOL),
            "manifest": sha256(MANIFEST),
            "parquet": sha256(PARQUET),
            "evidence_summary": sha256(SUMMARY),
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n")
    print("SPLIT_GUARD_PASSED")


if __name__ == "__main__":
    main()
