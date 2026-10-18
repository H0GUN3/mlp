"""Create the predeclared RE2-OB known-condition incident split."""

import collections
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OLD_SPLIT = ROOT / "research/mlp_prerequisites/split.json"
STAGE1 = ROOT / "research/tt_re2_baselines_20261017/re2_stage1"
MANIFEST = ROOT / "research/tt_re2_baselines_20261017/RE2_STAGE1_MANIFEST.json"
OUTPUT = Path(__file__).with_name("split.json")
RULE = "re2-ob-known-20261018|"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assign_validation_repetition(root_cause_service, fault):
    key = root_cause_service + "|" + fault
    value = int(hashlib.sha256((RULE + key).encode("utf-8")).hexdigest(), 16)
    return 1 + value % 3


def build_split(old_data, manifest, metadata_by_case, source_hashes):
    rows = [row for row in old_data["cases"] if row.get("dataset") == "RE2-OB"]
    if len(rows) != 90:
        raise ValueError("expected exactly 90 RE2-OB source rows")

    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["root_cause_service"], row["fault"])].append(row)
    if len(groups) != 30 or any(len(group) != 3 for group in groups.values()):
        raise ValueError("expected 30 RE2-OB groups with three repetitions each")

    old_counts = collections.Counter(row["partition"] for row in rows)
    if old_counts != {"train": 54, "validation": 18, "test": 18}:
        raise ValueError("unexpected original RE2-OB partition counts")
    protected = sorted(row["case"] for row in rows if row["partition"] == "test")
    development = [row for row in rows if row["partition"] in ("train", "validation")]
    if len(development) != 72 or len({row["case"] for row in development}) != 72:
        raise ValueError("development cases are missing or duplicated")

    manifest_cases = manifest.get("cases", [])
    entries = {entry["case"]: entry for entry in manifest_cases}
    if len(entries) != len(manifest_cases) or set(entries) != {
        row["case"] for row in development
    }:
        raise ValueError("stage1 manifest does not match the 72 development cases")
    if set(protected) & set(entries):
        raise ValueError("protected test case appears in stage1 manifest")

    by_case = {row["case"]: row for row in development}
    output_rows = []
    repetition_counts = collections.Counter()
    raw_hash_parts = collections.defaultdict(lambda: collections.defaultdict(set))
    for case in sorted(by_case):
        row = by_case[case]
        entry = entries[case]
        metadata = metadata_by_case[case]
        expected_metadata_hash = entry["metadata_sha256"]
        if metadata["metadata_sha256"] != expected_metadata_hash:
            raise ValueError("stage1 metadata hash differs from manifest: " + case)
        if metadata.get("case") != case or metadata.get("status") != "PASS_UNSCALED_CASE":
            raise ValueError("stage1 metadata identity/status invalid: " + case)
        if metadata.get("partition") != entry.get("partition"):
            raise ValueError("stage1 partition differs from manifest: " + case)
        if metadata.get("root_service") != row["root_cause_service"]:
            raise ValueError("stage1 root service differs from source: " + case)
        if metadata.get("inject_time") != row["inject_time"]:
            raise ValueError("stage1 injection time differs from source: " + case)

        selected = assign_validation_repetition(
            row["root_cause_service"], row["fault"]
        )
        partition = "validation" if row["repetition"] == selected else "train"
        repetition_counts[selected] += int(row["repetition"] == selected)
        for modality, value in metadata.get("raw_hashes", {}).items():
            raw_hash_parts[modality][value].add(partition)
        output_rows.append(
            {
                "case": case,
                "dataset": row["dataset"],
                "root_cause_service": row["root_cause_service"],
                "fault": row["fault"],
                "repetition": row["repetition"],
                "inject_time": row["inject_time"],
                "old_partition": row["partition"],
                "partition": partition,
                "validation_repetition": selected,
                "windows": metadata["windows"],
                "stage1_partition": entry["partition"],
                "metadata_sha256": expected_metadata_hash,
                "source_sha256": metadata["source_sha256"],
                "raw_hashes": metadata.get("raw_hashes", {}),
            }
        )

    collisions = {
        modality: value
        for modality, hashes in raw_hash_parts.items()
        for value, partitions in hashes.items()
        if len(partitions) > 1
    }
    if collisions:
        raise ValueError("identical raw file hash crosses new partitions: " +
                         json.dumps(collisions, sort_keys=True))

    output_groups = collections.defaultdict(list)
    counts = collections.Counter(row["partition"] for row in output_rows)
    for row in output_rows:
        output_groups[(row["root_cause_service"], row["fault"])].append(row)
    validation = [row for row in output_rows if row["partition"] == "validation"]
    train = [row for row in output_rows if row["partition"] == "train"]
    if counts != {"train": 48, "validation": 24}:
        raise ValueError("unexpected new partition counts: " + repr(counts))
    if any(
        (sum(row["partition"] == "train" for row in group),
         sum(row["partition"] == "validation" for row in group)) != (2, 1)
        for group in output_groups.values()
    ):
        raise ValueError("each development group must partition 2/1")
    if {row["root_cause_service"] for row in validation} != {
        row["root_cause_service"] for row in train
    } or {row["fault"] for row in validation} != {row["fault"] for row in train}:
        raise ValueError("validation root or fault types absent from train")
    if {
        (row["root_cause_service"], row["fault"]) for row in validation
    } - {(row["root_cause_service"], row["fault"]) for row in train}:
        raise ValueError("validation service-fault combination absent from train")
    if repetition_counts != {1: 12, 2: 9, 3: 3}:
        raise ValueError("unexpected selected repetition distribution")

    return {
        "schema": "re2-ob-known-condition-split-v1",
        "selection": {
            "rule": "1 + int(SHA256('re2-ob-known-20261018|' + root + '|' + fault), 16) % 3",
            "selected_repetition_counts": {
                str(key): repetition_counts[key] for key in (1, 2, 3)
            },
            "partition_semantics": {
                "train": "two other repetitions per known service-fault group",
                "validation": "one preselected repetition per known service-fault group",
                "protected": "original test cases; names only, sealed",
            },
        },
        "source_hashes": source_hashes,
        "counts": {
            "development_cases": len(output_rows),
            "train": counts["train"],
            "validation": counts["validation"],
            "protected": len(protected),
            "development_groups": len(output_groups),
            "validation_groups": len(validation),
        },
        "protected_cases": protected,
        "cases": output_rows,
        "overlap_check": {
            "raw_file_hashes": "checked per modality across new partitions; no identical hash crossed",
            "absolute_observation_intervals": "not available in approved metadata; temporal overlap unverified",
        },
    }


def load_inputs():
    old_data = json.loads(OLD_SPLIT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS_UNSCALED_ONLY":
        raise ValueError("stage1 manifest is not PASS_UNSCALED_ONLY")
    if len(manifest.get("cases", [])) != 72:
        raise ValueError("expected exactly 72 stage1 manifest cases")
    allowed = {
        row["case"] for row in old_data["cases"]
        if row.get("dataset") == "RE2-OB" and row["partition"] in ("train", "validation")
    }
    names = [entry["case"] for entry in manifest["cases"]]
    if len(set(names)) != 72 or set(names) != allowed:
        raise ValueError("stage1 manifest contains a protected or unapproved case")
    metadata_by_case = {}
    for entry in manifest["cases"]:
        path = STAGE1 / entry["case"] / "metadata.json"
        text = path.read_text(encoding="utf-8")
        metadata_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if metadata_hash != entry["metadata_sha256"]:
            raise ValueError("metadata hash differs from manifest: " + entry["case"])
        metadata_by_case[entry["case"]] = dict(json.loads(text), metadata_sha256=metadata_hash)
    source_hashes = {
        "original_split_sha256": sha256(OLD_SPLIT),
        "stage1_manifest_sha256": sha256(MANIFEST),
        "stage1_source_sha256": manifest["stage_source_sha256"],
    }
    return old_data, manifest, metadata_by_case, source_hashes


def main():
    if OUTPUT.exists():
        raise FileExistsError("refusing to overwrite " + str(OUTPUT))
    data = build_split(*load_inputs())
    # Exclusive creation preserves any output created by another process.
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("KNOWN_SPLIT_PASS")


if __name__ == "__main__":
    main()
