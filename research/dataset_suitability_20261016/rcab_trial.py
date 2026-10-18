"""Predeclared RCABench development diagnostic; no fitting or final split."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import tarfile
import time
from typing import Any, BinaryIO

import numpy as np
import pyarrow as pa
import pyarrow.lib as pa_lib
import pyarrow.parquet as pq


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "research/rcabench_assessment_20261013/rcabench-absolute_anomaly.tar.gz"
INPUT_PATHS = (
    "research/research_reset_review_20261016/metadata_analysis.json",
    "research/research_reset_review_20261016/metadata_details.json",
    "research/research_reset_review_20261016/verification.json",
    "research/diagnostic_observability_20261016/rcab_sample_manifest.json",
    "research/diagnostic_observability_20261016/rcab_observability.json",
    "research/diagnostic_observability_20261016/verified_summary.json",
    "research/rcabench_assessment_20261013/quality_audit.json",
    "research/rcabench_assessment_20261013/metadata_inventory.json",
)
CORE = tuple(f"{p}_{k}.parquet" for p in ("normal", "abnormal")
             for k in ("metrics", "traces"))
TRACE = ("normal_traces.parquet", "abnormal_traces.parquet")
COLUMNS = ("service_name", "time", "attr.http.response.status_code", "attr.status_code")
CRITERIA = ("uniform", "abnormal_http_error_fraction",
            "http_error_fraction_increase", "abnormal_span_error_fraction")
METRICS = ("top1", "top3", "expected_reciprocal_first_accepted_rank")
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 2_000_000
PILOT_SALT = "suitability-pilot-20261016:"
SPLIT_SALT = "suitability-20261016:"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def exclusive_json(path: Path, value: Any) -> None:
    """Never truncate a result, including when serialization itself fails."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())


def salted_hash(salt: str, key: str) -> str:
    return hashlib.sha256((salt + key).encode("utf-8")).hexdigest()


def fold(key: str) -> int:
    return int(salted_hash(SPLIT_SALT, key), 16) % 3


def select_pilot(rows: list[dict[str, Any]], prior_cases: list[str]) -> dict[str, Any]:
    http = [r for r in rows if r["fault_type"].startswith("HTTP")]
    prior = set(prior_cases) & {r["case"] for r in http}
    by_type: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in http:
        by_type[r["fault_type"]][r["semantic_configuration_sha256"]].append(r["case"])
    selected: set[str] = set()
    selected_groups: set[str] = set()
    type_records = {}
    for typ, groups in sorted(by_type.items()):
        ordered = sorted(groups, key=lambda g: (salted_hash(PILOT_SALT, g), g))
        initial = set(ordered[:math.ceil(len(ordered) * .2)])
        forced = {g for g, cases in groups.items() if prior.intersection(cases)}
        records = []
        for g in ordered:
            reasons = []
            if g in initial:
                reasons.append("first_ceil_20pct_hash_groups")
            if g in forced:
                reasons.append("contains_prior_http_deep_sample")
            if reasons:
                selected.update(groups[g])
                selected_groups.add(g)
            records.append({
                "group": g, "selection_hash": salted_hash(PILOT_SALT, g),
                "cases": sorted(groups[g]), "selected": bool(reasons), "reasons": reasons,
            })
        type_records[typ] = {
            "cases": sum(map(len, groups.values())), "groups": len(groups),
            "initial_groups": len(initial), "forced_groups": len(forced),
            "selected_groups": len(initial | forced), "group_records": records,
        }
    remainder = {r["case"] for r in http} - selected
    remainder_groups = {r["semantic_configuration_sha256"] for r in http
                        if r["case"] in remainder}
    require(not selected_groups.intersection(remainder_groups), "pilot group leakage")
    require(prior <= selected, "prior deep HTTP case omitted")
    return {
        "policy": "per HTTP type ceil(.2 * semantic groups), union prior deep HTTP groups",
        "salt": PILOT_SALT, "uses_scores_or_observation_density": False,
        "prior_http_deep_cases": sorted(prior), "types": type_records,
        "selected_cases": sorted(selected), "metadata_only_http_cases": sorted(remainder),
        "selected_groups": sorted(selected_groups),
        "metadata_only_http_groups": sorted(remainder_groups),
        "group_disjoint": True,
    }


def candidate_inventory(files: dict[str, Any]) -> list[str]:
    """Only full service-name census lists, never target-conditioned profiles."""
    return sorted({s for name in CORE for s in files[name]["services"]
                   if isinstance(s, str) and s != ""})


def empty_counts() -> dict[str, int]:
    return {"span_rows": 0, "http_known": 0, "http_error": 0, "span_error": 0}


def aggregate_table(table: pa.Table, start: int, end: int) -> dict[str, Any]:
    require(start < end, "invalid half-open period")
    ticks = table["time"].cast(pa.int64()).to_numpy(zero_copy_only=False)
    valid_time = np.isfinite(ticks)
    inside = valid_time & (ticks >= start * 10**9) & (ticks < end * 10**9)
    at_end = valid_time & (ticks == end * 10**9)
    outside = valid_time & ~inside & ~at_end
    names = np.array([s if s is not None else "" for s in table["service_name"].to_pylist()],
                     dtype=object)
    unique, inverse = np.unique(names, return_inverse=True)
    http = table["attr.http.response.status_code"].to_numpy(zero_copy_only=False)
    known = (http >= 100) & (http <= 599)
    error = (http >= 400) & (http <= 599)
    span_error = np.array(table["attr.status_code"].to_pylist(), dtype=object) == "Error"
    masks = {"span_rows": inside, "http_known": inside & known,
             "http_error": inside & error, "span_error": inside & span_error}
    totals = {key: np.bincount(inverse, weights=mask.astype(np.int64),
                               minlength=len(unique)).astype(np.int64)
              for key, mask in masks.items()}
    counts = {str(s): {key: int(values[i]) for key, values in totals.items()}
              for i, s in enumerate(unique) if s != ""}
    audit = {
        "published_span_rows": table.num_rows, "included_rows": int(inside.sum()),
        "excluded_end_boundary_rows": int(at_end.sum()),
        "excluded_outside_nonboundary_rows": int(outside.sum()),
        "excluded_null_time_rows": int((~valid_time).sum()),
        "rows_at_start_included": int((valid_time & (ticks == start * 10**9)).sum()),
        "included_empty_service_rows": int((inside & (names == "")).sum()),
        "start_epoch_seconds": start, "end_epoch_seconds": end,
        "period": "[start,end)", "unit": "as-published span rows; not independent requests",
    }
    require(table.num_rows == audit["included_rows"] + audit["excluded_end_boundary_rows"]
            + audit["excluded_outside_nonboundary_rows"] + audit["excluded_null_time_rows"],
            "period row reconciliation failed")
    require(sum(c["span_rows"] for c in counts.values())
            + audit["included_empty_service_rows"] == audit["included_rows"],
            "service row reconciliation failed")
    return {"counts": counts, "audit": audit}


def score_counts(counts: dict[str, dict[str, dict[str, int]]]) -> dict[str, Any]:
    """The only scoring input is per-candidate period counts; no labels or case context."""
    output: dict[str, Any] = {criterion: {} for criterion in CRITERIA}
    for service, periods in counts.items():
        n, a = periods["normal"], periods["abnormal"]
        ar = a["http_error"] / a["http_known"] if a["http_known"] else None
        nr = n["http_error"] / n["http_known"] if n["http_known"] else None
        values = (0.0, ar, ar - nr if ar is not None and nr is not None else None,
                  a["span_error"] / a["span_rows"] if a["span_rows"] else None)
        for criterion, value in zip(CRITERIA, values):
            output[criterion][service] = {
                "score": value, "supported": value is not None, "missing": value is None,
            }
    return output


def tie_metrics(scores: dict[str, dict[str, Any]], accepted: list[str]) -> dict[str, Any]:
    """Exact first-accepted order statistic in the first tier containing a gold."""
    gold = set(accepted)
    present = gold.intersection(scores)
    result: dict[str, Any] = {
        **{m: 0.0 for m in METRICS}, "missing_gold_candidates": sorted(gold - set(scores)),
        "present_gold_candidates": sorted(present), "no_gold_candidate": not bool(present),
        "first_accepted_tier": None,
    }
    if not present:
        return result
    tiers: dict[float | None, list[str]] = defaultdict(list)
    for service, record in scores.items():
        value = record["score"]
        require(record["supported"] == (value is not None), "score support inconsistent")
        require(value is None or math.isfinite(value), "nonfinite score")
        tiers[value].append(service)
    ordered = sorted(tiers, key=lambda v: (v is not None, v if v is not None else 0),
                     reverse=True)
    before = 0
    for value in ordered:
        services = tiers[value]
        size, matches = len(services), len(gold.intersection(services))
        if matches:
            denom = math.comb(size, matches)
            for k in (1, 3):
                slots = min(size, max(0, k - before))
                miss = (math.comb(size - matches, slots) / math.comb(size, slots)
                        if slots <= size - matches else 0.0)
                result[f"top{k}"] = 1.0 - miss
            result[METRICS[2]] = sum(
                math.comb(size - j, matches - 1) / denom / (before + j)
                for j in range(1, size - matches + 2))
            result["first_accepted_tier"] = {
                "score": value, "higher_candidates": before,
                "tier_candidates": size, "tier_accepted": matches,
            }
            return result
        before += size
    raise AssertionError("present gold not found")


def archive_stat(path: Path) -> dict[str, int]:
    st = path.stat()
    return {k: int(getattr(st, k)) for k in
            ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")}


class HashingReader(io.RawIOBase):
    """Hash compressed bytes during the single sequential archive traversal."""
    def __init__(self, raw: BinaryIO):
        super().__init__()
        self.raw = raw
        self.sha = hashlib.sha256()
        self.md5 = hashlib.md5()
        self.bytes = 0

    def read(self, size: int = -1) -> bytes:
        block = self.raw.read(size)
        self.sha.update(block)
        self.md5.update(block)
        self.bytes += len(block)
        return block


def software_evidence() -> dict[str, Any]:
    import numpy.core._multiarray_umath as np_core
    import pyarrow._parquet as pa_parquet
    modules = (np, np_core, pa, pa_lib, pa_parquet, tarfile, gzip, json, hashlib)
    paths = {str(Path(sys.executable).resolve())}
    paths.update(str(Path(m.__file__).resolve()) for m in modules if m.__file__)
    return {
        "python": sys.version, "executable": sys.executable,
        "numpy": np.__version__, "pyarrow": pa.__version__, "platform": platform.platform(),
        "sha256": {p: sha256_file(Path(p)) for p in sorted(paths)},
        "hash_scope": "interpreter, imported numeric/Parquet core binaries and listed entry modules; "
                      "not a complete transitive OS shared-library attestation",
    }


def load_inputs() -> tuple[dict[str, Any], dict[str, str]]:
    inputs, hashes = {}, {}
    for relative in INPUT_PATHS:
        p = ROOT / relative
        hashes[relative] = sha256_file(p)
        with p.open(encoding="utf-8") as f:
            inputs[p.stem] = json.load(f)
    for p in (Path(__file__), HERE / "test_rcab_trial.py", HERE / "PROTOCOL.md",
              HERE / "pyrightconfig.json"):
        hashes[str(p.relative_to(ROOT))] = sha256_file(p)
    analysis, details = inputs["metadata_analysis"], inputs["metadata_details"]
    quality, inventory = inputs["quality_audit"], inputs["metadata_inventory"]
    require(len(analysis["case_rows"]) == 1422 and analysis["cases"] == 1422,
            "metadata case count changed")
    require(len({r["fault_type"] for r in analysis["case_rows"]}) == 25,
            "fault type count changed")
    for key in ("metadata_analysis", "metadata_details", "verification",
                "rcab_observability", "verified_summary"):
        require(inputs[key]["status"] == "PASS", f"{key} not PASS")
    expected = {
        "inventory": hashes[INPUT_PATHS[7]], "quality": hashes[INPUT_PATHS[6]],
        "details": hashes[INPUT_PATHS[1]],
    }
    require(details["inventory_sha256"] == expected["inventory"]
            and details["quality_sha256"] == expected["quality"], "details source mismatch")
    require(quality["inventory_sha256"] == expected["inventory"], "quality source mismatch")
    require(inputs["rcab_sample_manifest"]["source_sha256"] == expected,
            "manifest sources mismatch")
    require(inputs["verified_summary"]["source_sha256"]["rcab_observability.json"]
            == hashes[INPUT_PATHS[4]], "observability source mismatch")
    for key in ("metadata_analysis", "verification"):
        for path, digest in inputs[key]["input_hashes" if key == "verification"
                                         else "input_sha256"].items():
            relative = str(Path(path).relative_to(ROOT))
            require(relative in hashes and hashes[relative] == digest,
                    f"{key} source binding mismatch: {relative}")
    require(quality["source"] == inventory["source"] == details["source"],
            "archive identity mismatch")
    return inputs, hashes


def budget_probe(selected: list[str], inventory: dict[str, Any],
                 quality: dict[str, Any]) -> dict[str, Any]:
    ii = {r["case"]: r for r in inventory["cases"]}
    qi = {r["case"]: r for r in quality["cases"]}
    sizes = [ii[c]["files"][f] for c in selected for f in TRACE]
    rows = [qi[c]["files"][f]["rows"] for c in selected for f in TRACE]
    available = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")
    require(max(sizes) <= MAX_BYTES and max(rows) <= MAX_ROWS, "selected file budget exceeded")
    require(available >= 512 * 1024**2, "less than 512 MiB available RAM")
    require(ARCHIVE.stat().st_size == inventory["source"]["bytes"], "archive size changed")
    return {
        "available_ram_sysconf_bytes": available,
        "free_output_filesystem_bytes": os.statvfs(HERE).f_bavail * os.statvfs(HERE).f_frsize,
        "archive_bytes": ARCHIVE.stat().st_size, "selected_trace_files": len(sizes),
        "selected_payload_bytes": sum(sizes), "selected_published_rows": sum(rows),
        "largest_selected_file_bytes": max(sizes), "largest_selected_file_rows": max(rows),
        "max_member_bytes": MAX_BYTES, "max_member_rows": MAX_ROWS,
        "placement": "one compressed member in memory; only four projected columns; release each file",
        "archive_processes": 1, "arrow_cpu_threads": pa.cpu_count(),
        "arrow_io_threads": pa.io_thread_count(),
    }


def read_selected_traces(selection: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    chosen = set(selection["selected_cases"])
    metadata = {r["case"]: r for r in inputs["metadata_analysis"]["case_rows"]}
    quality = inputs["quality_audit"]
    qi = {r["case"]: r for r in quality["cases"]}
    ii = {r["case"]: r for r in inputs["metadata_inventory"]["cases"]}
    results: dict[str, dict[str, Any]] = {c: {} for c in sorted(chosen)}
    visited = 0
    total_rows = 0
    start_stat = archive_stat(ARCHIVE)
    with ARCHIVE.open("rb") as raw:
        hashed = HashingReader(raw)
        with tarfile.open(fileobj=hashed, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                visited += 1
                parts = member.name.split("/")
                if len(parts) < 2:
                    continue
                c, filename = parts[-2:]
                if c not in chosen or filename not in TRACE:
                    continue
                require(filename not in results[c], f"duplicate trace member {c}/{filename}")
                require(0 < member.size <= MAX_BYTES, f"trace byte budget {member.name}")
                require(member.size == ii[c]["files"][filename], "inventory size mismatch")
                stream = archive.extractfile(member)
                require(stream is not None, "missing selected member stream")
                if stream is None:
                    raise ValueError("selected trace stream unavailable")
                payload = stream.read(MAX_BYTES + 1)
                stream.close()
                require(len(payload) == member.size, "selected member read length mismatch")
                digest = hashlib.sha256(payload).hexdigest()
                require(digest == quality["file_sha256"][c][filename], "quality hash mismatch")
                require(digest == inputs["rcab_observability"]["file_sha256"][f"{c}/{filename}"],
                        "census hash mismatch")
                reader = pq.ParquetFile(pa.BufferReader(payload))
                require(reader.metadata is not None, "no parquet metadata")
                row_count = reader.metadata.num_rows
                require(row_count <= MAX_ROWS, "trace row budget exceeded")
                require(row_count == qi[c]["files"][filename]["rows"],
                        "quality row count mismatch")
                table = reader.read(columns=list(COLUMNS), use_threads=True)
                require(table.column_names == list(COLUMNS), "trace projection incomplete")
                require(str(table["time"].type) == "timestamp[ns, tz=UTC]",
                        "unexpected timestamp unit/timezone")
                period = filename.split("_")[0]
                record = aggregate_table(table, metadata[c][period + "_start"],
                                         metadata[c][period + "_end"])
                record.update({"member": member.name, "bytes": len(payload), "sha256": digest,
                               "projection": list(COLUMNS)})
                results[c][period] = record
                total_rows += row_count
                del table, reader, payload, record
        # tar end markers may leave trailing compressed bytes; hash them without decoding.
        while hashed.read(1024 * 1024):
            pass
        archive_hash = hashed.sha.hexdigest()
        md5 = hashed.md5.hexdigest()
        require(hashed.bytes == start_stat["st_size"], "archive hash incomplete")
    end_stat = archive_stat(ARCHIVE)
    require(start_stat == end_stat, "archive changed during traversal")
    require(md5 == quality["source"]["md5"], "published archive MD5 mismatch")
    require(visited == quality["file_count"], "archive traversal census mismatch")
    require(all(set(v) == {"normal", "abnormal"} for v in results.values()),
            "selected trace file absent; selection preserved, no rescue")
    return {
        "cases": results, "files_read": 2 * len(results), "published_rows_read": total_rows,
        "visited_regular_members": visited, "archive_sha256": archive_hash,
        "archive_md5": md5, "archive_compressed_bytes_hashed": hashed.bytes,
        "archive_stat_before": start_stat, "archive_stat_after": end_stat,
        "archive_stat_unchanged": True,
    }


def evaluate_cases(selection: dict[str, Any], traces: dict[str, Any],
                   inputs: dict[str, Any]) -> dict[str, Any]:
    rows = {r["case"]: r for r in inputs["metadata_analysis"]["case_rows"]}
    census = inputs["rcab_observability"]["cases"]
    output = {}
    for c in selection["selected_cases"]:
        row = rows[c]
        candidates = candidate_inventory(census[c]["files"])
        periods = traces["cases"][c]
        counts = {s: {p: periods[p]["counts"].get(s, empty_counts())
                      for p in ("normal", "abnormal")} for s in candidates}
        require(set().union(*(set(periods[p]["counts"]) for p in periods)) <= set(candidates),
                "trace contains service absent from full census")
        scores = score_counts(counts)
        anchor, roots = row["configuration_anchor"], row["roots"]
        metrics = {contract: {criterion: tie_metrics(values, gold)
                              for criterion, values in scores.items()}
                   for contract, gold in (("nominal_anchor", [anchor]),
                                          ("original_accepted_roots", roots))}
        paired = {criterion: {
            metric: metrics["original_accepted_roots"][criterion][metric]
                    - metrics["nominal_anchor"][criterion][metric] for metric in METRICS}
            for criterion in CRITERIA}
        anchor_missing = {p: counts.get(anchor, {}).get(p, {}).get("span_rows", 0) == 0
                          for p in ("normal", "abnormal")}
        roots_missing = {p: [s for s in roots
                             if counts.get(s, {}).get(p, {}).get("span_rows", 0) == 0]
                         for p in ("normal", "abnormal")}
        output[c] = {
            "fault_type": row["fault_type"], "fault_type_id": row["fault_type_id"],
            "semantic_configuration_sha256": row["semantic_configuration_sha256"],
            "namespace": row["namespace"], "nominal_anchor": anchor,
            "original_accepted_roots": roots, "candidates": candidates, "counts": counts,
            "scores": scores, "metrics": metrics,
            "accepted_minus_anchor_paired_difference": paired,
            "anchor_missing_trace_rows": anchor_missing,
            "accepted_roots_missing_trace_rows": roots_missing,
            "trace_files": {p: {k: v for k, v in periods[p].items() if k != "counts"}
                            for p in periods},
            "missing_score_candidates": {
                criterion: [s for s, v in values.items() if v["missing"]]
                for criterion, values in scores.items()},
        }
    return output


def metric_summary(cases: dict[str, Any]) -> dict[str, Any]:
    n = len(cases)
    return {
        "cases": n,
        "case_equal_metrics": {
            contract: {criterion: {
                m: sum(c["metrics"][contract][criterion][m] for c in cases.values()) / n
                if n else None for m in METRICS} for criterion in CRITERIA}
            for contract in ("nominal_anchor", "original_accepted_roots")},
        "accepted_minus_anchor_case_equal_paired_difference": {
            criterion: {m: sum(c["accepted_minus_anchor_paired_difference"][criterion][m]
                               for c in cases.values()) / n if n else None
                        for m in METRICS} for criterion in CRITERIA},
        "missing_candidates": {criterion: sum(len(c["missing_score_candidates"][criterion])
                                              for c in cases.values())
                               for criterion in CRITERIA},
        "cases_with_missing_scores": {
            criterion: sum(bool(c["missing_score_candidates"][criterion]) for c in cases.values())
            for criterion in CRITERIA},
        "anchor_trace_missing_cases": {
            p: [name for name, c in cases.items() if c["anchor_missing_trace_rows"][p]]
            for p in ("normal", "abnormal")},
        "accepted_root_trace_missing_cases": {
            p: [name for name, c in cases.items() if c["accepted_roots_missing_trace_rows"][p]]
            for p in ("normal", "abnormal")},
        "missing_gold_candidate_cases": {
            contract: [name for name, c in cases.items()
                       if c["metrics"][contract]["uniform"]["missing_gold_candidates"]]
            for contract in ("nominal_anchor", "original_accepted_roots")},
    }


def summarize_pilot(cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall": metric_summary(cases),
        "by_fault_type": {
            typ: metric_summary({n: c for n, c in cases.items() if c["fault_type"] == typ})
            for typ in sorted({c["fault_type"] for c in cases.values()})},
        "by_anchor_abnormal_trace_missing": {
            str(missing): metric_summary({
                n: c for n, c in cases.items()
                if c["anchor_missing_trace_rows"]["abnormal"] == missing})
            for missing in (False, True)},
        "counterexample_cases_anchor_top1_zero": {
            criterion: [n for n, c in cases.items()
                        if c["metrics"]["nominal_anchor"][criterion]["top1"] == 0]
            for criterion in CRITERIA},
    }


def split_support(rows: list[dict[str, Any]], assignments: dict[str, int],
                  use_original_roots: bool) -> dict[str, Any]:
    folds = {}
    for heldout in range(3):
        train = [r for r in rows if assignments[r["case"]] != heldout]
        test = [r for r in rows if assignments[r["case"]] == heldout]
        roots = Counter(s for r in train for s in
                        (r["roots"] if use_original_roots else [r["configuration_anchor"]]))
        types = Counter(r["fault_type"] for r in train)
        pairs = Counter("|".join(sorted(r["roots"])) for r in train)
        cases = {}
        for r in test:
            gold = r["roots"] if use_original_roots else [r["configuration_anchor"]]
            cases[r["case"]] = {
                "training_root_counts": {s: roots[s] for s in gold},
                "training_type_count": types[r["fault_type"]],
                "training_original_root_set_count": pairs["|".join(sorted(r["roots"]))],
                "all_roots_supported": all(roots[s] > 0 for s in gold),
                "type_supported": types[r["fault_type"]] > 0,
            }
        folds[str(heldout)] = {
            "training_cases": len(train), "heldout_cases": len(test),
            "training_root_counts": dict(sorted(roots.items())),
            "training_type_counts": dict(sorted(types.items())),
            "training_original_root_set_counts": dict(sorted(pairs.items())),
            "heldout_case_support": cases,
            "heldout_cases_without_root_support": [
                c for c, v in cases.items() if not v["all_roots_supported"]],
            "heldout_cases_without_type_support": [
                c for c, v in cases.items() if not v["type_supported"]],
        }
    return folds


def split_stress(rows: list[dict[str, Any]]) -> dict[str, Any]:
    nominal = [r for r in rows if r["target_scope"] != "network_pair"
               and r["label_set_matches_config_rule"]]
    http = [r for r in rows if r["fault_type"].startswith("HTTP")]
    network = [r for r in rows if r["target_scope"] == "network_pair"]
    require((len(rows), len(nominal), len(http), len(network)) == (1422, 1167, 796, 254),
            "whole metadata subset counts changed")
    groups: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        groups[r["semantic_configuration_sha256"]].append(r["case"])
    assignments = {
        "case_hash": {r["case"]: fold(r["case"]) for r in rows},
        "semantic_group_hash": {r["case"]: fold(r["semantic_configuration_sha256"]) for r in rows},
    }
    overlaps = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            seconds = min(a["abnormal_end"], b["abnormal_end"]) - max(a["normal_start"],
                                                                      b["normal_start"])
            if seconds > 0:
                overlaps.append({"cases": [a["case"], b["case"]],
                                 "same_namespace": a["namespace"] == b["namespace"],
                                 "overlap_seconds": seconds})
    reports = {}
    for scheme, assignment in assignments.items():
        cross = {g: sorted(cases) for g, cases in groups.items()
                 if len({assignment[c] for c in cases}) > 1}
        if scheme == "semantic_group_hash":
            require(not cross, "semantic group split leaks groups")
        sharing = {
            "namespace_fold_counts": {
                ns: dict(sorted(Counter(str(assignment[r["case"]]) for r in rows
                                        if r["namespace"] == ns).items()))
                for ns in sorted({r["namespace"] for r in rows})},
            "positive_window_overlap_pairs": len(overlaps),
            "same_namespace_overlap_pairs": sum(p["same_namespace"] for p in overlaps),
            "cross_fold_window_overlap_pairs": sum(
                assignment[p["cases"][0]] != assignment[p["cases"][1]] for p in overlaps),
        }
        reports[scheme] = {
            "assignments": assignment, "fold_counts": dict(sorted(Counter(assignment.values()).items())),
            "repeated_configuration_crossfold_groups": cross,
            "crossfold_group_count": len(cross),
            "cases_in_crossfold_groups": sum(map(len, cross.values())),
            "namespace_time_sharing": sharing,
            "support": {
                "all_metadata_nominal_anchor_descriptive": split_support(rows, assignment, False),
                "nonnetwork_nominal_anchor_candidates": split_support(nominal, assignment, False),
                "http_nominal_anchor": split_support(http, assignment, False),
                "network_pair_original_roots": split_support(network, assignment, True),
            },
        }
    return {
        "salt": SPLIT_SALT, "fold_rule": "int(sha256(salt + key),16) modulo 3",
        "adopted_final_split": False, "independence_certified": False,
        "metadata_case_rows": rows, "cases": len(rows), "fault_types": 25,
        "nonnetwork_nominal_anchor_candidates": len(nominal),
        "nonnetwork_conflicts_excluded": [r["case"] for r in rows
                                         if r["target_scope"] != "network_pair"
                                         and not r["label_set_matches_config_rule"]],
        "http_cases": len(http), "network_pair_cases": len(network),
        "semantic_group_members": {g: sorted(v) for g, v in sorted(groups.items())},
        "repeated_group_count": sum(len(v) > 1 for v in groups.values()),
        "cases_in_repeated_groups": sum(len(v) for v in groups.values() if len(v) > 1),
        "positive_window_overlaps": overlaps,
        "schemes": reports,
    }


def main() -> None:
    started = time.perf_counter()
    started_utc = datetime.now(timezone.utc).isoformat()
    for path in (HERE / "rcab_selection.json", HERE / "rcab_trial.json"):
        if path.exists():
            raise FileExistsError(f"{path} is frozen; do not overwrite or delete. "
                                  "Owner must authorize a new output location/revision.")
    pa.set_cpu_count(2)
    pa.set_io_thread_count(2)
    require(np.__version__ == "1.26.4" and pa.__version__ == "19.0.1"
            and sys.version_info[:2] == (3, 10), "unexpected runtime")
    require(all(os.environ.get(k) == "2" for k in
                ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")),
            "set all three declared thread environment variables to 2")
    inputs, source_hashes = load_inputs()
    software = software_evidence()
    selection = select_pilot(inputs["metadata_analysis"]["case_rows"],
                             inputs["rcab_sample_manifest"]["deep_sample_cases"])
    require(len(selection["selected_cases"]) == 173, "unexpected fixed selection")
    require(len(selection["selected_cases"]) + len(selection["metadata_only_http_cases"]) == 796,
            "HTTP selection reconciliation failed")
    require(set(inputs["rcab_sample_manifest"]["http_census_cases"])
            == set(selection["selected_cases"]) | set(selection["metadata_only_http_cases"]),
            "HTTP manifest mismatch")
    budget = budget_probe(selection["selected_cases"], inputs["metadata_inventory"],
                          inputs["quality_audit"])
    selection.update({
        "source_sha256": source_hashes, "software": software, "budget_probe": budget,
        "archive_stat_before_selection": archive_stat(ARCHIVE),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "saved_before_trace_processing": True,
    })
    exclusive_json(HERE / "rcab_selection.json", selection)
    print(f"RCAB_SELECTION_FROZEN cases={len(selection['selected_cases'])} "
          f"sha256={sha256_file(HERE / 'rcab_selection.json')}", flush=True)
    split = split_stress(inputs["metadata_analysis"]["case_rows"])
    traces = read_selected_traces(selection, inputs)
    cases = evaluate_cases(selection, traces, inputs)
    require(traces["files_read"] == budget["selected_trace_files"]
            and traces["published_rows_read"] == budget["selected_published_rows"],
            "selected trace totals do not match preflight")
    require(traces["archive_stat_before"] == selection["archive_stat_before_selection"],
            "archive changed after selection")
    require(inputs["verification"]["candidate_non_network_anchor_cases"]
            == split["nonnetwork_nominal_anchor_candidates"], "nominal anchor count mismatch")
    require(inputs["verification"]["cross_namespace_positive_overlap_pairs"]
            == sum(not p["same_namespace"] for p in split["positive_window_overlaps"]),
            "metadata time overlap reconciliation failed")
    require(all(sha256_file(ROOT / p) == digest for p, digest in source_hashes.items()),
            "consumed input/source changed during execution")
    require(all(sha256_file(Path(p)) == digest for p, digest in software["sha256"].items()),
            "software changed during execution")
    result = {
        "status": "PASS", "scope": "173-case predeclared HTTP development pilot; metadata-only remainder",
        "criteria": list(CRITERIA), "metrics": list(METRICS),
        "tie_policy": "uniform random ordering within exact score tiers; supported before missing",
        "missing_gold_policy": "absent gold never added; zero if none accepted present; otherwise "
                               "first present accepted candidate; absent members explicitly retained",
        "selection": selection, "selection_sha256": sha256_file(HERE / "rcab_selection.json"),
        "source_sha256_before_and_after": source_hashes, "software": software,
        "pilot_cases": cases, "pilot_summary": summarize_pilot(cases),
        "whole_metadata_split_stress": split,
        "trace_run": {k: v for k, v in traces.items() if k != "cases"},
        "http_census_reused": {
            "cases": 796, "verified_summary_sha256": source_hashes[INPUT_PATHS[5]],
            "root_observation_cases": inputs["verified_summary"]["root_observation_cases"],
            "no_target_profiles_used_for_scoring": True,
        },
        "runtime": {
            "started_utc": started_utc, "finished_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": time.perf_counter() - started,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "thread_environment": {k: os.environ[k] for k in
                                  ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")},
        },
        "limitations": [
            "Span rows are as published, not independent requests or incidents.",
            "Given fault windows; descriptive offline ranking, not causal identification.",
            "Forced prior deep groups alter a plain 20% sample; no tuning or rescue.",
            "623 HTTP cases unranked; previous census means not certified untouched final data.",
            "Other 626 cases metadata only; HTTP scores not generalized to them.",
            "1167 are nominal configuration-anchor review candidates, not proven physical causes.",
            "Neither paper baseline reproduction nor model training, inference or final split.",
            "Semantic grouping blocks identical configuration hashes, not all dependence.",
        ],
    }
    exclusive_json(HERE / "rcab_trial.json", result)
    print(f"RCAB_RESULT_SHA256 {sha256_file(HERE / 'rcab_trial.json')}", flush=True)
    print("RCAB_SUITABILITY_PASS", flush=True)


if __name__ == "__main__":
    main()
