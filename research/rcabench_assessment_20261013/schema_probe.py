"""Bounded first-case schema discovery; not a corpus quality verdict."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
WANTED = {
    "normal_metrics.parquet", "abnormal_metrics.parquet",
    "normal_metrics_sum.parquet", "normal_metrics_histogram.parquet",
    "normal_traces.parquet", "abnormal_traces.parquet", "conclusion.parquet",
}


def describe(payload):
    parquet = pq.ParquetFile(pa.BufferReader(payload))
    result = {
        "rows": parquet.metadata.num_rows,
        "schema": {field.name: str(field.type) for field in parquet.schema_arrow},
        "columns": {},
    }
    wanted = [name for name in parquet.schema_arrow.names if name in (
        "time", "duration", "service_name", "metric", "attr.span.kind",
        "attr.status.code", "attr.k8s.namespace.name", "attr.k8s.container.name",
    )]
    table = parquet.read(columns=wanted)
    for name in wanted:
        column = table[name]
        summary = {"null_count": column.null_count}
        if name in ("time", "duration"):
            values = column.cast(pa.int64()) if pa.types.is_timestamp(column.type) else column
            summary["min_max"] = pc.call_function("min_max", [values]).as_py()
        else:
            unique = pc.call_function("unique", [column]).to_pylist()
            summary["distinct_count"] = len(unique)
            summary["sample_values"] = unique[:80]
        result["columns"][name] = summary
    return result


def self_check():
    table = pa.table({
        "time": pa.array([1, 2], type=pa.timestamp("ns", tz="UTC")),
        "duration": pa.array([0, 10], type=pa.uint64()),
        "service_name": ["a", "a"], "metric": ["cpu", "cpu"],
    })
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    result = describe(sink.getvalue())
    assert result["rows"] == 2
    assert result["columns"]["service_name"]["distinct_count"] == 1
    assert result["columns"]["time"]["min_max"] == {"min": 1, "max": 2}
    assert result["columns"]["duration"]["min_max"] == {"min": 0, "max": 10}
    empty_sink = pa.BufferOutputStream()
    pq.write_table(table.slice(0, 0), empty_sink)
    assert describe(empty_sink.getvalue())["rows"] == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise FileExistsError("Refusing to overwrite schema discovery")
    self_check()
    inventory_path = HERE / "metadata_inventory.json"
    inventory_bytes = inventory_path.read_bytes()
    inventory = json.loads(inventory_bytes)
    cases = {case["case"]: case for case in inventory["cases"]}
    archive_path = HERE / "rcabench-absolute_anomaly.tar.gz"
    if archive_path.stat().st_size != inventory["source"]["bytes"]:
        raise ValueError("Previously verified archive size changed")
    case_name, files = None, {}
    with tarfile.open(archive_path, mode="r|gz") as archive:
        for number, member in enumerate(archive, 1):
            if number > 64:
                raise ValueError("First-case probe exceeded member budget")
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if len(parts) != 2 or parts[0] not in cases:
                raise ValueError("Archive layout differs from verified inventory")
            name, filename = parts
            if case_name is None:
                case_name = name
            if name != case_name or filename not in WANTED:
                continue
            if member.size != cases[name]["files"][filename] or member.size > 16 * 1024 * 1024:
                raise ValueError("Unexpected or oversized probe member")
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Missing member payload")
            with source:
                payload = source.read(member.size + 1)
            if len(payload) != member.size:
                raise ValueError("Truncated member")
            files[filename] = describe(payload)
            if set(files) == WANTED:
                break
    if case_name is None or set(files) != WANTED:
        raise ValueError("Incomplete first-case schema discovery")
    result = {
        "scope": "one case only; schema discovery, not dataset suitability",
        "pyarrow_version": pa.__version__, "case_metadata": cases[case_name],
        "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(), "files": files,
    }
    with args.report.open("x", encoding="utf-8") as target:
        json.dump(result, target, ensure_ascii=False, indent=2, default=str)
        target.write("\n")
    print("SCHEMA_PROBE_COMPLETE", case_name, args.report, flush=True)


if __name__ == "__main__":
    main()
