"""Read only injection/env/SLI summaries from the already acquired RCABench archive."""
import argparse
from datetime import date, datetime
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import resource
import tarfile
import time

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "rcabench_assessment_20261013"
TARGETS = {"injection.json", "env.json", "conclusion.parquet"}
MAX_MEMBER = 4 * 1024 * 1024
MAX_CONCLUSION_ROWS = 10_000


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": repr(value)}
    if isinstance(value, (datetime, date)):
        return {"iso_datetime": value.isoformat()}
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    return value


def decode(payload, filename):
    if filename.endswith(".json"):
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("Expected metadata object")
        return clean(value)
    parquet = pq.ParquetFile(pa.BufferReader(payload))
    if parquet.metadata.num_rows > MAX_CONCLUSION_ROWS:
        raise ValueError("Conclusion is larger than the declared metadata budget")
    columns = parquet.schema_arrow.names
    if "SpanName" not in columns or "Issues" not in columns:
        raise ValueError("Unknown SLI summary schema")
    allowed = {"SpanName", "Issues", "AbnormalAvgDuration", "NormalAvgDuration",
               "AbnormalSuccRate", "NormalSuccRate", "AbnormalP90", "NormalP90",
               "AbnormalP95", "NormalP95", "AbnormalP99", "NormalP99"}
    if set(columns) - allowed:
        raise ValueError("Unexpected conclusion fields; inspect before widening")
    return {"schema": {field.name: str(field.type) for field in parquet.schema_arrow},
            "rows": clean(parquet.read(columns=columns).to_pylist())}


def collect(archive, cases, expected_hashes):
    result = {}
    digests = {}
    bytes_read = 0
    visited = 0
    finished = 0
    for member in archive:
        if not member.isfile():
            continue
        visited += 1
        parts = PurePosixPath(member.name).parts
        if len(parts) != 2 or parts[0] not in cases:
            raise ValueError("Unexpected archive member path")
        case, name = parts
        if member.size != cases[case]["files"].get(name):
            raise ValueError("Member size differs from inventory")
        if name not in TARGETS:
            continue
        if member.size > MAX_MEMBER:
            raise ValueError("Metadata payload exceeds budget")
        if name in result.get(case, {}):
            raise ValueError("Duplicate metadata member")
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("Unreadable metadata member")
        with source:
            payload = source.read(member.size + 1)
        if len(payload) != member.size:
            raise ValueError("Truncated metadata member")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected_hashes[case][name]:
            raise ValueError("Metadata hash differs from previous full census")
        result.setdefault(case, {})[name] = decode(payload, name)
        digests.setdefault(case, {})[name] = digest
        bytes_read += len(payload)
        if len(result[case]) == len(TARGETS):
            finished += 1
            if finished == 1:
                print("METADATA_FIRST_CASE", json.dumps(
                    {"case": case, "injection": result[case]["injection.json"],
                     "env": result[case]["env.json"],
                     "conclusion_first": result[case]["conclusion.parquet"]["rows"][:1]},
                    ensure_ascii=False, allow_nan=False), flush=True)
            if finished % 200 == 0:
                print("METADATA_PROGRESS", finished, "of", len(cases), flush=True)
    if set(result) != set(cases):
        raise ValueError("Missing cases")
    for case, values in result.items():
        if set(values) != TARGETS:
            raise ValueError("Incomplete metadata triple for " + case)
    return result, digests, {"visited_regular_members": visited,
                             "parsed_metadata_bytes": bytes_read,
                             "cases": finished, "metadata_files": finished * len(TARGETS)}


def self_test():
    conclusion = pa.table({
        "SpanName": ["request"], "Issues": ["[]"],
        "NormalAvgDuration": [1.], "AbnormalAvgDuration": [float("nan")]})
    buf = pa.BufferOutputStream()
    pq.write_table(conclusion, buf)
    payloads = {"injection.json": b'{"ground_truth":{"service":["a","b"]}}',
                "env.json": b'{"NORMAL_START":0}', "conclusion.parquet": buf.getvalue().to_pybytes(),
                "abnormal_metrics.parquet": b"this must never be parsed"}
    cases = {"case": {"files": {name: len(value) for name, value in payloads.items()}}}
    hashes = {"case": {name: hashlib.sha256(value).hexdigest() for name, value in payloads.items()}}
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w") as archive:
        for name, payload in payloads.items():
            info = tarfile.TarInfo("case/" + name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    packed.seek(0)
    with tarfile.open(fileobj=packed, mode="r|") as archive:
        result, _, counts = collect(archive, cases, hashes)
    assert counts["metadata_files"] == 3 and counts["visited_regular_members"] == 4
    assert result["case"]["conclusion.parquet"]["rows"][0]["AbnormalAvgDuration"] == {"nonfinite": "nan"}
    bad_hashes = {"case": dict(hashes["case"], **{"injection.json": "bad"})}
    packed.seek(0)
    try:
        with tarfile.open(fileobj=packed, mode="r|") as archive:
            collect(archive, cases, bad_hashes)
    except ValueError as error:
        assert "hash" in str(error)
    else:
        raise AssertionError("Mismatched hash accepted")
    try:
        decode(b"[]", "env.json")
    except ValueError:
        pass
    else:
        raise AssertionError("Non-object metadata accepted")
    print("METADATA_SELF_TEST_PASS", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "metadata_details.json")
    options = parser.parse_args()
    if options.self_test:
        self_test()
        return
    if options.output.exists():
        raise FileExistsError(options.output)
    started = time.perf_counter()
    inv_bytes = (AUDIT / "metadata_inventory.json").read_bytes()
    quality_bytes = (AUDIT / "quality_audit.json").read_bytes()
    inventory, quality = json.loads(inv_bytes), json.loads(quality_bytes)
    inv_hash = hashlib.sha256(inv_bytes).hexdigest()
    if quality["inventory_sha256"] != inv_hash:
        raise ValueError("Inventory and quality census do not match")
    cases = {case["case"]: case for case in inventory["cases"]}
    archive_path = AUDIT / "rcabench-absolute_anomaly.tar.gz"
    before = archive_path.stat()
    if before.st_size != inventory["source"]["bytes"]:
        raise ValueError("Archive size changed")
    pa.set_cpu_count(2)
    pa.set_io_thread_count(1)
    with tarfile.open(archive_path, mode="r|gz") as archive:
        records, digests, counts = collect(archive, cases, quality["file_sha256"])
    after = archive_path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Archive changed during scan")
    expected_members = sum(len(case["files"]) for case in cases.values())
    if counts["visited_regular_members"] != expected_members:
        raise ValueError("Archive member coverage differs from census")
    result = {
        "status": "PASS", "scope": "metadata and existing SLI summary only; no sensor Parquet body",
        "counts": counts, "source": inventory["source"], "inventory_sha256": inv_hash,
        "quality_sha256": hashlib.sha256(quality_bytes).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "pyarrow_version": pa.__version__, "seconds": time.perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "file_sha256": digests, "records": records,
        "limits": [
            "Decompression traverses archive bytes but sensor Parquet bodies are not parsed.",
            "Per-member hashes match the earlier full census; archive MD5 was not recalculated.",
            "SLI summaries are author-generated summaries, not independently recomputed telemetry.",
            "No split, model feature preparation, training, inference or final evaluation."]}
    with options.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("METADATA_EXTRACTION_PASS", json.dumps(counts), "seconds", result["seconds"], flush=True)


if __name__ == "__main__":
    main()
