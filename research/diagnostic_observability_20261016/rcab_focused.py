"""Resolve both configured endpoints by trace/parent identity, without requiring client tags."""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "rcabench_assessment_20261013"
CASES = [
    "ts2-ts-ui-dashboard-response-replace-code-qzfj27",
    "ts2-ts-basic-service-request-replace-method-v6gzn8",
]
COLS = ["trace_id", "span_id", "parent_span_id", "service_name", "attr.span_kind",
        "attr.http.response.status_code", "attr.status_code", "span_name",
        "attr.http.request.method"]


def joined_pairs(rows, anchor, counterpart):
    indexed, ambiguous = {}, set()
    for row in rows:
        key = row[:2]
        if not all(key):
            continue
        if key in indexed and indexed[key] != row:
            ambiguous.add(key)
        indexed[key] = row
    outcomes, operations = Counter(), Counter()
    for key, row in indexed.items():
        pk = (row[0], row[2])
        if key in ambiguous or pk in ambiguous or pk not in indexed:
            continue
        parent = indexed[pk]
        if parent[3] == row[3] or {parent[3], row[3]} != {anchor, counterpart}:
            continue
        outcomes[tuple(parent[3:7]) + tuple(row[3:7])] += 1
        operations[(parent[7], parent[8], row[7], row[8])] += 1
    return {
        "ambiguous_identities": len(ambiguous),
        "pair_count": sum(outcomes.values()),
        "outcomes": [{"parent_service": key[0], "parent_kind": key[1],
                      "parent_http": key[2], "parent_status": key[3],
                      "child_service": key[4], "child_kind": key[5],
                      "child_http": key[6], "child_status": key[7], "count": n}
                     for key, n in outcomes.items()],
        "operation_pairs": [{"parent_name": k[0], "parent_method": k[1],
                             "child_name": k[2], "child_method": k[3], "count": n}
                            for k, n in operations.most_common(30)],
        "operation_pair_distinct_count": len(operations),
    }


def main():
    out = HERE / "rcab_focused.json"
    if out.exists():
        raise FileExistsError(out)
    parent = ("t", "a", "", "ui", "Server", 500, "Error", "/x", "GET")
    child = ("t", "b", "a", "backend", "Server", 200, "Unset", "/x", "GET")
    assert joined_pairs([parent, child], "ui", "backend")["pair_count"] == 1
    assert joined_pairs([parent, child, (*child[:5], 404, *child[6:])],
                        "ui", "backend")["pair_count"] == 0
    print("FOCUSED_LINK_SELF_TEST_PASS", flush=True)
    previous_bytes = (HERE / "rcab_observability.json").read_bytes()
    previous = json.loads(previous_bytes)
    expected = {f"{case}/{period}_traces.parquet" for case in CASES for period in ("normal", "abnormal")}
    result = {}
    with tarfile.open(OLD / "rcabench-absolute_anomaly.tar.gz", "r|gz") as archive:
        for member in archive:
            if member.name not in expected:
                continue
            source = archive.extractfile(member)
            if source is None or member.size > 16 * 1024 * 1024:
                raise ValueError("Unexpected selected member")
            with source:
                payload = source.read(member.size + 1)
            digest = hashlib.sha256(payload).hexdigest()
            assert len(payload) == member.size
            assert digest == previous["file_sha256"][member.name]
            case, filename = PurePosixPath(member.name).parts
            table = pq.ParquetFile(pa.BufferReader(payload)).read(columns=COLS, use_threads=False)
            rows = zip(*(table[name].to_pylist() for name in COLS))
            meta = previous["cases"][case]
            result[member.name] = joined_pairs(rows, meta["anchor"], meta["counterpart"])
            result[member.name]["input_sha256"] = digest
            if set(result) == expected:
                break
    assert set(result) == expected
    report = {
        "status": "PASS", "selection": "two previously discussed cases, no model-score selection",
        "files": result, "previous_audit_sha256": hashlib.sha256(previous_bytes).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limits": [
            "Same-trace parent identity links, not proof that every edge is a direct HTTP wire exchange.",
            "Two cases only, not a whole-corpus identifiability or model-performance result.",
            "Top30 operation pairs retained; all outcome counts retained. No source data changed."]}
    with out.open("x", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print("FOCUSED_LINK_PASS", len(result), flush=True)


if __name__ == "__main__":
    main()
