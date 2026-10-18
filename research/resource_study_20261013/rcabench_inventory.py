"""Read-only first-stage inventory; no download, extraction, row decoding or training."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile


EXPECTED_BYTES = 13_444_974_981
EXPECTED_MD5 = "96d32ae290e06be7d4e251be02b36cb8"
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 100_000
REQUIRED = (
    "normal_metrics.parquet", "abnormal_metrics.parquet",
    "normal_traces.parquet", "abnormal_traces.parquet",
    "injection.json", "env.json",
)
TIME_KEYS = ("NORMAL_START", "NORMAL_END", "ABNORMAL_START", "ABNORMAL_END")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def epoch_seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("expected integer epoch seconds")
    if isinstance(value, str) and not value.isascii():
        raise ValueError("expected ASCII epoch seconds")
    seconds = int(value)
    datetime.fromtimestamp(seconds, tz=timezone.utc)
    return seconds


def summarize_case(name, files, metadata, errors):
    reasons = list(errors)
    missing = [key for key in REQUIRED if key not in files]
    empty = [key for key in REQUIRED if key in files and files[key] == 0]
    if missing:
        reasons.append("missing_required_files")
    if empty:
        reasons.append("empty_required_files")

    injection = metadata.get("injection.json", {})
    ground_truth = injection.get("ground_truth", {})
    roots = ground_truth.get("service") if isinstance(ground_truth, dict) else None
    if not isinstance(roots, list) or not roots or not all(
        isinstance(root, str) and root and root == root.strip() for root in roots
    ):
        roots = []
        reasons.append("invalid_service_labels")
    elif len(set(roots)) != len(roots):
        reasons.append("duplicate_service_labels")
    roots = sorted(set(roots))
    if len(roots) > 1:
        reasons.append("multiple_service_labels")

    periods = None
    env = metadata.get("env.json", {})
    try:
        times = [epoch_seconds(env[key]) for key in TIME_KEYS]
        if not (times[0] < times[1] <= times[2] < times[3]):
            raise ValueError("normal/fault periods are empty, inverted or overlapping")
        periods = dict(zip(TIME_KEYS, times))
    except (KeyError, ValueError, TypeError, OverflowError, OSError):
        reasons.append("invalid_or_overlapping_periods")

    fault_type = injection.get("fault_type")
    if isinstance(fault_type, bool) or not isinstance(fault_type, (str, int)):
        fault_type = None
    return {
        "case": name,
        "files": files,
        "file_payload_bytes": sum(files.values()),
        "root_services": roots,
        "fault_type": fault_type,
        "periods_epoch_seconds": periods,
        "missing_required_files": missing,
        "empty_required_files": empty,
        "reasons": sorted(set(reasons)),
        "metadata_gate_pass": not reasons,
    }


def inventory(stream):
    """Inspect export.py's flat case/file layout, failing closed on other layouts."""
    cases = {}
    seen = set()
    with tarfile.open(fileobj=stream, mode="r|gz") as archive:
        for number, member in enumerate(archive, 1):
            if number > MAX_MEMBERS:
                raise ValueError("member limit exceeded; inspect layout before raising limit")
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or "\\" in member.name:
                raise ValueError(f"unsafe member path: {member.name}")
            if not path.parts or (not member.isdir() and len(path.parts) != 2):
                raise ValueError(f"unexpected case/file layout: {member.name}")
            if member.isdir():
                if len(path.parts) != 1:
                    raise ValueError(f"unexpected nested directory: {member.name}")
                cases.setdefault(path.parts[0], {"files": {}, "metadata": {}, "errors": []})
                continue
            if not member.isfile() or member.issparse():
                raise ValueError(f"links/special/sparse files unsupported: {member.name}")
            if path in seen:
                raise ValueError(f"duplicate archive member: {member.name}")
            seen.add(path)
            name, filename = path.parts
            case = cases.setdefault(name, {"files": {}, "metadata": {}, "errors": []})
            case["files"][filename] = member.size
            if filename not in ("injection.json", "env.json"):
                continue
            if member.size > MAX_JSON_BYTES:
                case["errors"].append(f"oversized_metadata:{filename}")
                continue
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"unreadable metadata: {member.name}")
            with source:
                payload = source.read(MAX_JSON_BYTES + 1)
            if len(payload) != member.size:
                raise ValueError(f"truncated metadata: {member.name}")
            try:
                value = json.loads(payload, object_pairs_hook=unique_object)
                if not isinstance(value, dict):
                    raise ValueError("metadata must be an object")
                if filename == "injection.json":
                    value = {key: value.get(key) for key in ("ground_truth", "fault_type")}
                else:
                    value = {key: value.get(key) for key in TIME_KEYS}
                case["metadata"][filename] = value
            except (ValueError, UnicodeError, RecursionError):
                case["errors"].append(f"invalid_json:{filename}")
    if not cases:
        raise ValueError("archive contains no case directories")

    rows = [summarize_case(name, **cases[name]) for name in sorted(cases)]
    signatures = defaultdict(list)
    for row in rows:
        if row["periods_epoch_seconds"] is not None and row["root_services"]:
            signature = json.dumps(
                [row["root_services"], row["periods_epoch_seconds"], row["fault_type"]],
                sort_keys=True,
            )
            signatures[signature].append(row["case"])
    return {
        "stage": "metadata_only_not_observation_quality",
        "case_directories": len(rows),
        "single_service_label_cases": sum(len(row["root_services"]) == 1 for row in rows),
        "multiple_service_label_cases": sum(len(row["root_services"]) > 1 for row in rows),
        "metadata_candidates_not_deduplicated": sum(row["metadata_gate_pass"] for row in rows),
        "same_label_period_fault_groups": [group for group in signatures.values() if len(group) > 1],
        "exclusion_reason_counts": dict(Counter(reason for row in rows for reason in row["reasons"])),
        "independent_usable_incidents": None,
        "limits": [
            "File presence/size is not Parquet schema, row or coverage verification.",
            "Labels follow injection.ground_truth.service; alternate converted labels unverified.",
            "Equal metadata groups are review flags, not proof of identical or independent events.",
            "Recording independence, seven metric channels, trace quality and self-time unverified.",
        ],
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Already obtained, authorized Zenodo tar.gz")
    parser.add_argument("--report", type=Path, help="Create a new JSON report; never overwrite")
    args = parser.parse_args()
    try:
        with args.archive.open("rb") as stream:
            digest = hashlib.md5()
            size = 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
            if size != EXPECTED_BYTES or digest.hexdigest() != EXPECTED_MD5:
                raise ValueError("archive size/checksum does not match pinned Zenodo artifact")
            print(f"CHECKSUM_OK bytes={size}", file=sys.stderr, flush=True)
            stream.seek(0)
            result = inventory(stream)
            result["source"] = {
                "archive": str(args.archive), "bytes": size, "md5": digest.hexdigest(),
            }
        report = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report is None:
            print(report)
        else:
            with args.report.open("x", encoding="utf-8") as target:
                target.write(report + "\n")
            print(f"INVENTORY_COMPLETE cases={result['case_directories']} report={args.report}")
    except (OSError, EOFError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f"Inventory failed; no complete report: {error}\n")


if __name__ == "__main__":
    main()
