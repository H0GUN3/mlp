"""Inspect only Parquet metadata for the existing allowed RE2-OB development cases."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = REPO / "research/mlp_prerequisites/split.json"
DATA = REPO / "data/rcaeval"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allow_case(row):
    if row["dataset"] != "RE2-OB" or row["partition"] not in ("train", "validation"):
        raise PermissionError("Only the original RE2-OB train/validation scope is allowed")
    if "/" in row["case"] or not row["case"].startswith("re2ob_"):
        raise ValueError("Invalid case path")


def main():
    assert __debug__
    try:
        allow_case({"dataset": "RE2-OB", "partition": "test", "case": "re2ob_probe"})
    except PermissionError:
        pass
    else:
        raise AssertionError("Protected case was accepted")
    lock = json.loads(MANIFEST.with_name("split.lock.json").read_text())
    assert digest(MANIFEST) == lock["sha256"]
    manifest = json.loads(MANIFEST.read_text())
    rows = [r for r in manifest["cases"] if r["dataset"] == "RE2-OB"]
    assert Counter(r["partition"] for r in rows) == {"train": 54, "validation": 18, "test": 18}
    selected = [r for r in rows if r["partition"] != "test"]
    schemas = {kind: {} for kind in ("metrics", "logs", "traces")}
    services = {"train": set(), "validation": set()}
    families = {"train": set(), "validation": set()}
    coverage = defaultdict(lambda: defaultdict(set))
    case_reports = []
    for row in selected:
        allow_case(row)
        case = row["case"]
        info = {"case": case, "partition": row["partition"], "files": {}}
        for kind in schemas:
            path = DATA / case / (kind + ".parquet")
            before = path.stat()
            footer = pq.ParquetFile(path)
            fields = [(field.name, str(field.type)) for field in footer.schema_arrow]
            key = json.dumps(fields)
            schemas[kind].setdefault(key, {"fields": fields, "examples": [], "case_count": 0})
            entry = schemas[kind][key]
            entry["case_count"] += 1
            if len(entry["examples"]) < 2:
                entry["examples"].append(case)
            info["files"][kind] = {"rows": footer.metadata.num_rows,
                                   "bytes": before.st_size, "mtime_ns": before.st_mtime_ns}
            assert footer.metadata.num_rows > 0
            if kind == "metrics":
                assert "time" in footer.schema_arrow.names
                for name in footer.schema_arrow.names:
                    if name == "time":
                        continue
                    service, separator, family = name.partition("_")
                    assert separator and service and family
                    services[row["partition"]].add(service)
                    families[row["partition"]].add(family)
                    coverage[row["partition"]][service].add(family)
                assert row["root_cause_service"] in {
                    name.partition("_")[0] for name in footer.schema_arrow.names if name != "time"}
            after = path.stat()
            assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        case_reports.append(info)
    report = {
        "status": "PASS_METADATA_ONLY", "split_sha256": lock["sha256"],
        "source_sha256": digest(Path(__file__)), "cases": case_reports,
        "schemas": {kind: list(variants.values()) for kind, variants in schemas.items()},
        "metric_services": {part: sorted(values) for part, values in services.items()},
        "metric_families": {part: sorted(values) for part, values in families.items()},
        "metric_service_family_coverage": {
            part: {service: sorted(values) for service, values in mapping.items()}
            for part, mapping in coverage.items()},
        "validation_only_metric_services": sorted(services["validation"] - services["train"]),
        "validation_only_metric_families": sorted(families["validation"] - families["train"]),
        "protected_case_files_opened": 0, "observation_rows_decoded": 0,
        "candidate_order_frozen": False, "templates_or_scalers_fitted": False,
    }
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with (HERE / "RE2_SCHEMA_CHECK.json").open("x") as stream:
        stream.write(payload)
    print(json.dumps({k: report[k] for k in ("metric_services", "metric_families",
                                           "validation_only_metric_services",
                                           "validation_only_metric_families")}, indent=2))
    print("RE2_SCHEMA_PASS 54 18 PROTECTED_OPENED_0 ROWS_DECODED_0", flush=True)


if __name__ == "__main__":
    main()
