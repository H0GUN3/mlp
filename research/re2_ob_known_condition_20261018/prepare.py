"""Fresh48/24 native inputs from pinned, fitting-free stage1 observations only."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any, Dict

sys.dont_write_bytecode = True
# Workers and the native BLAS runtime must use one CPU each, including probes.
for _variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_variable] = "1"

import numpy as np
from drain3.file_persistence import FilePersistence

from research.tt_re2_baselines_20261017 import re2_stage2 as pure
from research.re2_ob_known_condition_20261018 import split as splitting

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / "artifacts"
STAGE1 = pure.STAGE1
SPLIT = HERE / "split.json"
MANIFEST = pure.MANIFEST
SPLIT_HASH = "3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2"
MANIFEST_HASH = "7f1c7de45db8e36726279a2ba879823c360755718a29600b7999226b6e004d72"
OLD_HASH = pure.SPLIT_HASH
MEMBERS = ("metadata.json", "temporal.npz", "logs.jsonl.gz")
KEYS = {"metrics", "metric_observed", "traces", "logs", "labels", "case_ids",
        "starts", "partition", "indices", "edge_pairs"}
BUDGET_SECONDS = 7200
# User-approved component role, deliberately separate from the frozen proxy policy.
ROLE_EXCLUSIONS = frozenset({"frontend-check"})
ROLE_POLICY = {
    "excluded_independent_nodes": sorted(ROLE_EXCLUSIONS),
    "basis": "loadgenerator initContainer; user authorization 2026-10-18",
    "source_evidence": "research/re2_ob_known_condition_20261018/UNKNOWN_NODE.md",
    "official_reference": "GoogleCloudPlatform/microservices-demo v0.9.0 release/kubernetes-manifests.yaml:531-577",
    "dataset_exact_release_confirmed": False,
    "scope": "exact owned node only, both partitions; no alias merge or incident/window removal",
}
POLICY_HASH = hashlib.sha256(json.dumps(ROLE_POLICY, sort_keys=True).encode()).hexdigest()
INPUT_BINDING = POLICY_HASH
SNAPSHOT_HASH = "synthetic-fixture"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    require(".." not in Path(path).parts, "Parent traversal forbidden")
    result = Path(os.path.abspath(str(path)))
    require(not any(p.is_symlink() for p in (result,) + tuple(result.parents)),
            "Symlink forbidden: " + str(result))
    return result


def json_read(path):
    return json.loads(safe_path(path).read_text(encoding="utf8"))


def digest(path):
    path = safe_path(path)
    require(path.is_file() and path.stat().st_nlink == 1,
            "Expected unaliased regular file: " + str(path))
    return pure.digest(path)


def json_write(path, value):
    with safe_path(path).open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def arrays_read(path):
    with safe_path(path).open("rb") as stream, np.load(stream, allow_pickle=False) as source:
        return {key: source[key] for key in source.files}


def arrays_write(path, arrays):
    return pure.save_npz(safe_path(path), arrays)


class ReadGuard:
    """Audit all observation/state opens; exact files, never metadata-granted paths."""

    def __init__(self, allowed_paths, output=OUT):
        self.allowed = frozenset(safe_path(p) for p in allowed_paths)
        self.output = safe_path(output)
        self.stats = {"protected_case_files_opened": 0, "raw_case_files_opened": 0,
                      "old_state_files_opened": 0, "denied": [], "allowed_opens": 0}

    def audit(self, event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = safe_path(os.fsdecode(args[0]))
        mode, flags = args[1:3]
        writing = ((isinstance(mode, str) and any(c in mode for c in "wax+")) or
                   (isinstance(flags, int) and
                    bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))))
        output = self.output in path.parents
        runtime = (REPO / ".venv-eadro" in path.parents or
                   Path(sys.base_prefix) / "lib" in path.parents)
        in_repo = path == REPO or REPO in path.parents
        permitted = output if writing else (output or runtime or not in_repo or
                                            path in self.allowed)
        if not permitted:
            self.stats["denied"].append(str(path))
            raise PermissionError("Outside exact preparation allowlist: " + str(path))
        if not writing and path.exists():
            require(path.is_file() and path.stat().st_nlink == 1,
                    "Nonregular/hardlinked input forbidden: " + str(path))
        self.stats["allowed_opens"] += 1


def source_paths():
    return [SPLIT, MANIFEST, pure.SPLIT, HERE / "PROTOCOL.md", HERE / "SPLIT.md",
            HERE / "UNKNOWN_NODE.md",
            HERE / "prepare.py", HERE / "test_prepare.py", HERE / "split.py",
            Path(pure.__file__), STAGE1.parent / "re2_stage1.py",
            STAGE1.parent / "re2_preprocessing.py"] + [
                pure.NATIVE / name for name in pure.PINNED]


def inventory(rows, metadata):
    services = sorted({s for r in rows if r["partition"] == "train"
                       for s in metadata[r["case"]]["services"]} - pure.PROXIES - ROLE_EXCLUSIONS)
    require(len(services) >= 2, "Insufficient TRAIN observed nodes")
    for row in rows:
        unknown = set(metadata[row["case"]]["services"]) - set(services) - pure.PROXIES - ROLE_EXCLUSIONS
        require(not unknown, "Unknown validation node; STOP, do not drop: " +
                row["case"] + " " + repr(sorted(unknown)))
        require(row["root_cause_service"] in services, "Root not in observed TRAIN union")
    edges = {(s, s) for s in services}
    for row in rows:
        if row["partition"] == "train":
            edges.update(tuple(pair) for pair in metadata[row["case"]]["observed_edges"]
                         if not set(pair) & (pure.PROXIES | ROLE_EXCLUSIONS))
    return services, np.asarray(pure.indexed_edge_pairs(services, edges), dtype=np.int64)


def numeric_accounting(meta, arrays):
    """Count owned observations only; a parent/child name never changes span ownership."""
    result = {"excluded": {}, "retained": {}}
    require(arrays["retained_count"].shape == arrays["metrics"].shape[:3] and
            arrays["retained_count"].dtype.kind in "iu" and
            (arrays["retained_count"] >= 0).all(), "Invalid retained trace counts")
    for index, name in enumerate(meta["services"]):
        seen = arrays["metric_observed"][:, index]
        values = arrays["metrics"][:, index]
        record: Dict[str, Any] = {
            "metric_observed_cells": int(seen.sum()),
            "metric_observed_windows": int(seen.any(axis=(1, 2)).sum()),
            "trace_retained_count": int(arrays["retained_count"][:, index].sum()),
            "trace_nonzero_latency_cells": int(np.count_nonzero(arrays["traces"][:, index, :, 0])),
        }
        excluded = name in ROLE_EXCLUSIONS
        if excluded:
            record["metric_families"] = {
                family: {"observed_cells": int(seen[..., channel].sum()),
                         "minimum": float(values[..., channel][seen[..., channel]].min())
                         if seen[..., channel].any() else None,
                         "maximum": float(values[..., channel][seen[..., channel]].max())
                         if seen[..., channel].any() else None}
                for channel, family in enumerate(pure.FAMILIES)}
            record["observed_edges"] = [pair for pair in meta["observed_edges"] if name in pair]
            record["edge_count"] = len(record["observed_edges"])
        result["excluded" if excluded else "retained"][name] = record
    return result


def check_duplicates(rows, metadata, intervals):
    overlaps = pure.interval_overlaps(intervals)
    require(not overlaps, "Cross-part absolute interval conflict: " + repr(overlaps))
    hashes = {}
    for row in rows:
        meta = metadata[row["case"]]
        for kind, values in (("raw", meta["raw_hashes"]), ("stage1", meta["output_hashes"])):
            for modality, value in values.items():
                key = kind, modality, value
                previous = hashes.setdefault(key, row["partition"])
                require(previous == row["partition"],
                        "Cross-part duplicate {} {} in {}".format(kind, modality, row["case"]))


def preflight():
    global INPUT_BINDING
    require(sys.version_info[:2] == (3, 8), "Use .venv-eadro Python3.8")
    require(digest(SPLIT) == SPLIT_HASH, "Recovered split hash mismatch")
    require(digest(MANIFEST) == MANIFEST_HASH, "Stage1 manifest hash mismatch")
    data = json_read(SPLIT)
    manifest = json_read(MANIFEST)
    old = json_read(pure.SPLIT)
    require(digest(pure.SPLIT) == OLD_HASH, "Original split changed")
    allowed = {r["case"] for r in old["cases"] if r["dataset"] == "RE2-OB"
               and r["partition"] in ("train", "validation")}
    protected = {r["case"] for r in old["cases"] if r["dataset"] == "RE2-OB"
                 and r["partition"] == "test"}
    rows = sorted(data["cases"], key=lambda r: r["case"])
    require(len(rows) == len(allowed) == 72 and
            {r["case"] for r in rows} == allowed and not allowed & protected,
            "New split case allowlist mismatch")
    require(all(Path(c).name == c and c not in (".", "..") for c in allowed),
            "Case path injection")
    entries = {r["case"]: r for r in manifest["cases"]}
    require(len(manifest["cases"]) == 72 and set(entries) == allowed,
            "Manifest outside original development allowlist")
    paths = source_paths() + [STAGE1 / case / name for case in allowed for name in MEMBERS]
    guard = ReadGuard(paths)
    sys.addaudithook(guard.audit)
    source_hashes = {str(p.relative_to(REPO)): digest(p) for p in source_paths()}
    require(manifest["status"] == "PASS_UNSCALED_ONLY" and
            manifest["split_sha256"] == OLD_HASH, "Not fitting-free manifest")
    require(digest(STAGE1.parent / "re2_stage1.py") == manifest["stage_source_sha256"],
            "Stage1 conversion source changed")
    for name, expected in pure.PINNED.items():
        require(digest(pure.NATIVE / name) == expected, "Native source hash: " + name)
    metadata, intervals, sizes, accounting = {}, [], [], {}
    for row in rows:
        case = row["case"]
        folder = STAGE1 / case
        require(digest(folder / "metadata.json") == entries[case]["metadata_sha256"] ==
                row["metadata_sha256"], "Metadata hash: " + case)
        meta = json_read(folder / "metadata.json")
        require(meta["case"] == case and meta["partition"] == entries[case]["partition"] ==
                row["old_partition"] == row["stage1_partition"], "Old/new provenance: " + case)
        require(meta["root_service"] == row["root_cause_service"] and
                meta["inject_time"] == row["inject_time"] and
                meta["raw_hashes"] == row["raw_hashes"], "Source identity: " + case)
        require(meta["status"] == "PASS_UNSCALED_CASE" and
                meta["families"] == pure.FAMILIES and
                meta["split_sha256"] == OLD_HASH and
                meta["source_sha256"] == manifest["stage_source_sha256"] ==
                row["source_sha256"], "Unfitted source protocol: " + case)
        require(not meta["templates_or_scalers_fitted"] and
                not meta["metric_imputation_fitted"] and
                meta["protected_case_files_opened"] == 0, "Stage1 fitted/protected state")
        require(meta["services"] == sorted(set(meta["services"])) and
                not set(meta["services"]) & pure.PROXIES, "Invalid local service order")
        for member in MEMBERS[1:]:
            require(digest(folder / member) == meta["output_hashes"][member],
                    "Stage1 member hash: " + case + "/" + member)
        z = arrays_read(folder / "temporal.npz")
        starts, count, nodes = z["starts"], meta["windows"], len(meta["services"])
        require(starts.dtype == np.int64 and starts.shape == (count,) and count > 1 and
                np.all(np.diff(starts) == 10), "Invalid starts")
        require(z["metrics"].shape == (count, nodes, 10, 8) and
                z["metrics"].dtype == np.float64 and not np.isinf(z["metrics"]).any(),
                "Invalid raw metric contract")
        require(z["metric_observed"].dtype == np.bool_, "Invalid observed dtype")
        np.testing.assert_array_equal(z["metric_observed"], np.isfinite(z["metrics"]))
        require(z["traces"].shape == (count, nodes, 10, 2) and
                np.isfinite(z["traces"]).all() and (z["traces"] >= 0).all() and
                np.all(z["traces"][..., 1] == 0), "Invalid trace contract")
        expected = pure.global_labels(starts, row["inject_time"],
                                      meta["services"].index(row["root_cause_service"]))
        np.testing.assert_array_equal(z["labels"], expected)
        require(z["labels"].dtype == np.int64 and (expected < 0).any() and
                (expected >= 0).any(), "Invalid case labels")
        intervals.append({"case": case, "partition": row["partition"],
                          "start": int(starts[0]), "end_exclusive": int(starts[-1]) + 10,
                          "windows": count})
        sizes.append(sum(value.nbytes for value in z.values()))
        metadata[case] = dict(meta, metadata_sha256=row["metadata_sha256"])
        accounting[case] = dict(numeric_accounting(meta, z), partition=row["partition"],
                                windows=count)
        if accounting[case]["excluded"]:
            log_counts = {}
            for _ in log_records(case, meta, log_counts):
                pass
            accounting[case]["log_counts"] = log_counts
    rebuilt = splitting.build_split(old, manifest, metadata, data["source_hashes"])
    require(rebuilt == data, "New partition differs from deterministic split")
    check_duplicates(rows, metadata, intervals)
    services = sorted({s for r in rows if r["partition"] == "train"
                       for s in metadata[r["case"]]["services"]} - pure.PROXIES - ROLE_EXCLUSIONS)
    conflicts = [{"case": r["case"], "partition": r["partition"],
                  "unknown_nodes": sorted(set(metadata[r["case"]]["services"]) -
                                          set(services) - pure.PROXIES - ROLE_EXCLUSIONS)}
                 for r in rows if set(metadata[r["case"]]["services"]) -
                 set(services) - pure.PROXIES - ROLE_EXCLUSIONS]
    INPUT_BINDING = hashlib.sha256(json.dumps({
        "source_hashes": source_hashes, "policy_sha256": POLICY_HASH,
        "cases": [dict(r, members=metadata[r["case"]]["output_hashes"]) for r in rows],
    }, sort_keys=True).encode()).hexdigest()
    available = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    stat = os.statvfs(str(HERE))
    report = {"status": "STOP_UNKNOWN_VALIDATION_NODE" if conflicts else "PREFLIGHT_PASS",
              "pid": os.getpid(), "cases": len(rows),
              "case_counts": dict(Counter(r["partition"] for r in rows)),
              "windows": sum(m["windows"] for m in metadata.values()),
              "services": services, "unknown_node_cases": conflicts, "intervals": intervals,
              "partition_counts": {
                  part: {name: sum(metadata[r["case"]][name] for r in rows
                                   if r["partition"] == part)
                         for name in ("windows", "nominal_normal_windows", "nominal_fault_windows",
                                      "logs_retained", "metric_missing_cells")}
                  for part in ("train", "validation")},
              "verified_cases": [
                  dict(r, stage1_member_hashes=metadata[r["case"]]["output_hashes"])
                  for r in rows],
              "cross_partition_overlaps": [], "all_case_overlaps":
                  pure.interval_overlaps(intervals, False),
              "source_hashes": source_hashes, "split_sha256": SPLIT_HASH,
              "role_policy": ROLE_POLICY, "policy_sha256": POLICY_HASH,
              "input_binding_sha256": INPUT_BINDING, "observation_accounting": accounting,
              "stage1_manifest_sha256": MANIFEST_HASH, "original_split_sha256": OLD_HASH,
              "resources": {"available_memory_bytes": available,
                            "free_disk_bytes": stat.f_bavail * stat.f_frsize,
                            "largest_stage1_array_bytes": max(sizes),
                            "all_stage1_array_bytes": sum(sizes),
                            "stage1_member_bytes": sum(p.stat().st_size for p in paths
                                                       if STAGE1 in p.parents)},
              "protection": guard.stats}
    require(available > max(sizes) * 10, "Insufficient preflight working memory")
    if conflicts:
        # Preserve the actual policy conflict before fitting; never repair the inventory from labels.
        for row in rows:
            folder = STAGE1 / row["case"]
            require(digest(folder / "metadata.json") == row["metadata_sha256"], "Metadata changed")
            for name, expected in metadata[row["case"]]["output_hashes"].items():
                require(digest(folder / name) == expected, "Original stage1 changed")
        report["checks"] = {"metadata_hashes_verified": 72, "member_hashes_verified": 144,
                            "all_stage1_hashes_rechecked_unchanged": True,
                            "cross_part_raw_and_stage1_duplicates": 0,
                            "template_fit_calls": 0, "hawkes_fit_calls": 0}
        json_write(OUT / ("node-conflict-{}.json".format(os.getpid())), report)
        raise ValueError("Unknown validation node; STOP, do not drop or augment: " + repr(conflicts))
    services, edges = inventory(rows, metadata)
    report["edge_pairs"] = edges.tolist()
    if (OUT / "preflight.json").exists():
        previous = json_read(OUT / "preflight.json")
        require(previous["source_hashes"] == source_hashes and
                previous["intervals"] == intervals and
                previous["input_binding_sha256"] == INPUT_BINDING, "Checkpoint source changed")
    else:
        json_write(OUT / "preflight.json", report)
    print("PREFLIGHT_PASS pid={} cases=72 nodes={} windows={} overlaps=0".format(
        os.getpid(), len(services), report["windows"]), flush=True)
    return rows, metadata, services, edges, report, guard


def log_records(case, meta, accounting=None):
    require(Path(case).name == case, "Invalid case")
    count, retained, excluded = 0, Counter(), Counter()
    with gzip.open(STAGE1 / case / "logs.jsonl.gz", "rt", encoding="utf8") as stream:
        for line in stream:
            stamp, name, message = json.loads(line)
            require(type(stamp) is int and name in meta["services"] and
                    isinstance(message, str), "Invalid staged log")
            count += 1
            if name in ROLE_EXCLUSIONS:
                excluded[name] += 1
                continue
            retained[name] += 1
            yield stamp, name, message
    require(count == meta["logs_retained"], "Stage1 log count changed")
    if accounting is not None:
        accounting.update(source_rows=count, excluded_by_service=dict(excluded),
                          retained_by_service=dict(retained), retained_rows=sum(retained.values()))


def frozen_templates(rows, metadata):
    global SNAPSHOT_HASH
    path, snapshot = OUT / "templates.json", OUT / "drain.snapshot"
    if path.exists():
        report = json_read(path)
        require(report["split_sha256"] == SPLIT_HASH and
                report["input_binding_sha256"] == INPUT_BINDING and
                report["policy_sha256"] == POLICY_HASH and
                digest(snapshot) == report["snapshot_sha256"], "Fresh template hash")
        miner = pure.new_miner(snapshot)
        require(pure.cluster_records(miner) == report["clusters"], "Snapshot clusters changed")
        SNAPSHOT_HASH = report["snapshot_sha256"]
        return miner, report
    require(not snapshot.exists(), "Preserve incomplete snapshot; cannot overwrite")
    begin = time.perf_counter()
    miner, sources = pure.new_miner(), []
    for row in rows:
        if row["partition"] != "train":
            continue
        count = pure.fit_nominal(miner, log_records(row["case"], metadata[row["case"]]),
                                 row["inject_time"])
        sources.append({"case": row["case"], "partition": "train",
                        "strictly_preinject_lines": count})
        print("TEMPLATE_CASE case={} lines={} retained={} created={}".format(
            row["case"], count, len(miner.drain.clusters), miner.drain.clusters_counter), flush=True)
    clusters = pure.cluster_records(miner)
    miner.persistence_handler = FilePersistence(str(snapshot))
    miner.save_state("fresh TRAIN48 strictly preinject frozen final")
    report = {"split_sha256": SPLIT_HASH, "clusters": clusters, "sources": sources,
              "input_binding_sha256": INPUT_BINDING, "policy_sha256": POLICY_HASH,
              "event_count": len(clusters) + 1, "unknown_bin": 0,
              "cluster_id_to_feature": {str(c["cluster_id"]): i + 1
                                       for i, c in enumerate(clusters)},
              "snapshot_sha256": digest(snapshot), "config_sha256": digest(pure.CONFIG),
              "lines": sum(r["strictly_preinject_lines"] for r in sources),
              "validation_fit_lines": 0, "clusters_created": int(miner.drain.clusters_counter),
              "clusters_evicted": int(miner.drain.clusters_counter) - len(clusters),
              "order": "sorted TRAIN case; original log row order; timestamp < injection",
              "seconds": time.perf_counter() - begin}
    restored = pure.new_miner(snapshot)
    require(pure.cluster_records(restored) == clusters, "Fresh snapshot roundtrip")
    json_write(path, report)
    SNAPSHOT_HASH = report["snapshot_sha256"]
    print("TEMPLATES_FROZEN events={} seconds={:.3f} evicted={}".format(
        report["event_count"], report["seconds"], report["clusters_evicted"]), flush=True)
    return restored, report


def matched_case(row, meta, services, miner, template):
    path = OUT / "matched" / (row["case"] + ".npz")
    record = path.with_suffix(".json")
    if path.exists() or record.exists():
        require(path.exists() and record.exists(), "Incomplete matched checkpoint")
        saved = json_read(record)
        require(digest(path) == saved["sha256"] and saved["split_sha256"] == SPLIT_HASH and
                saved["input_binding_sha256"] == INPUT_BINDING and
                saved["policy_sha256"] == POLICY_HASH and
                saved["snapshot_sha256"] == template["snapshot_sha256"] and
                saved["stage1_log_sha256"] == meta["output_hashes"]["logs.jsonl.gz"],
                "Matched checkpoint source mismatch")
        return arrays_read(path), saved
    begin = time.perf_counter()
    z = arrays_read(STAGE1 / row["case"] / "temporal.npz")
    start, end = int(z["starts"][0]), int(z["starts"][-1]) + 10
    times, nodes, events = [], [], []
    mapping = {s: i for i, s in enumerate(services)}
    log_counts = {}
    for stamp, name, message in log_records(row["case"], meta, log_counts):
        require(start <= stamp < end, "Log outside complete window")
        times.append(stamp)
        nodes.append(mapping[name])
        events.append(pure.match_event(miner, template["cluster_id_to_feature"], message))
    require(pure.cluster_records(miner) == template["clusters"], "Frozen template mutated")
    arrays = {k: np.asarray(v, dtype=np.int64) for k, v in
              (("times", times), ("nodes", nodes), ("events", events))}
    saved = {"case": row["case"], "partition": row["partition"], "rows": len(times),
             "input_binding_sha256": INPUT_BINDING, "policy_sha256": POLICY_HASH,
             "log_counts": log_counts,
             "unknown_rows": events.count(0), "sha256": arrays_write(path, arrays),
             "split_sha256": SPLIT_HASH, "snapshot_sha256": template["snapshot_sha256"],
             "stage1_log_sha256": meta["output_hashes"]["logs.jsonl.gz"],
             "seconds": time.perf_counter() - begin}
    json_write(record, saved)
    print("MATCHED case={} rows={} unknown={}".format(
        row["case"], len(times), saved["unknown_rows"]), flush=True)
    return arrays, saved


def cached_fit(key, knots):
    require(key == pure.knot_key(knots), "Relative cache key mismatch")
    path, record = OUT / "hawkes" / (key + ".npz"), OUT / "hawkes" / (key + ".json")
    if path.exists() or record.exists():
        require(path.exists() and record.exists(), "Incomplete fresh Hawkes cache")
        meta = json_read(record)
        require(digest(path) == meta["sha256"] and meta["split_sha256"] == SPLIT_HASH and
                meta["input_binding_sha256"] == INPUT_BINDING and
                meta["policy_sha256"] == POLICY_HASH and meta["snapshot_sha256"] == SNAPSHOT_HASH and
                meta["key"] == key and meta["seed"] == 42 and
                meta["event_count"] == len(knots), "Fresh cache provenance mismatch")
        baseline = arrays_read(path)["baseline"]
        require(baseline.shape == (len(knots),) and np.isfinite(baseline).all() and
                (baseline >= 0).all(), "Invalid cached baseline")
        return baseline, meta
    result = pure.fit_hawkes((0, 0, knots, 42))
    baseline = result.pop("baseline")
    result.update(key=key, seed=42, split_sha256=SPLIT_HASH, event_count=len(knots),
                  input_binding_sha256=INPUT_BINDING, policy_sha256=POLICY_HASH,
                  snapshot_sha256=SNAPSHOT_HASH,
                  iteration_cap=50, cap_reached=result["iterations"] >= 50,
                  worker_pid=os.getpid(), threads=1)
    result["sha256"] = arrays_write(path, {"baseline": baseline})
    json_write(record, result)
    print("HAWKES_FIT key={} pid={} seconds={:.6f} iterations={} warnings={}".format(
        key, os.getpid(), result["seconds"], result["iterations"], len(result["warnings"])), flush=True)
    for warning in result["warnings"]:
        print("HAWKES_WARNING " + warning, flush=True)
    return baseline, result


def worker_fit(task):
    key, knots = task
    return cached_fit(key, knots)[1]


def profile(rows, metadata, services, miner, template, resources):
    """Match all 72 cases and count exact unique inputs before bounded actual fits."""
    if (OUT / "profile.json").exists():
        report = json_read(OUT / "profile.json")
        require(report["split_sha256"] == SPLIT_HASH and
                report["input_binding_sha256"] == INPUT_BINDING and
                report["policy_sha256"] == POLICY_HASH and
                report["snapshot_sha256"] == template["snapshot_sha256"], "Profile changed")
        return report
    begin = time.perf_counter()
    unique, groups, empty, by_case, sample_knots = set(), 0, 0, [], {}
    for row in rows:
        matched, _ = matched_case(row, metadata[row["case"]], services, miner, template)
        z = arrays_read(STAGE1 / row["case"] / "temporal.npz")
        count = 0
        for _, _, key, knots in pure.case_groups(matched, int(z["starts"][0]),
                                                template["event_count"]):
            unique.add(key)
            count += 1
            if not by_case:
                sample_knots[key] = knots
        groups += count
        empty += len(z["starts"]) * len(services) - count
        by_case.append({"case": row["case"], "nonempty_groups": count})
    events, total = template["event_count"], sum(m["windows"] for m in metadata.values())
    bundle_bytes = total * len(services) * (10 * 8 * 5 + 10 * 2 * 4 + events * 4)
    # Tick allocates dense adjacency and optimization matrices; report a conservative bound.
    worker_bytes = 64 * events * events * 8
    working_bytes = bundle_bytes * 3 + worker_bytes * 4
    require(working_bytes < resources["available_memory_bytes"] // 2 and
            bundle_bytes * 5 < resources["free_disk_bytes"], "Working-set/disk probe exceeds safety bound")
    ordered = sorted(sample_knots, key=lambda k: sum(map(len, sample_knots[k])))
    require(bool(ordered), "No nonempty log groups to profile")
    chosen = list(dict.fromkeys(ordered[i] for i in
                               (0, len(ordered) // 2, len(ordered) - 1)))
    results = []
    print("PROFILE_INPUTS events={} unique={} groups={} bundle_bytes={} working_bytes={}".format(
        events, len(unique), groups, bundle_bytes, working_bytes), flush=True)
    for key in chosen:
        _, result = cached_fit(key, sample_knots[key])
        results.append(result)
        estimate = len(unique) * float(np.mean([r["seconds"] for r in results])) / 4
        print("HAWKES_PROBE completed={} unique={} estimated_4worker_seconds={:.3f}".format(
            len(results), len(unique), estimate), flush=True)
        if estimate > BUDGET_SECONDS:
            break
    measured = [r["seconds"] for r in results]
    estimate = len(unique) * float(np.mean(measured)) / 4
    report = {"split_sha256": SPLIT_HASH, "snapshot_sha256": template["snapshot_sha256"],
              "input_binding_sha256": INPUT_BINDING, "policy_sha256": POLICY_HASH,
              "event_count": events, "unique_input_count": len(unique),
              "unique_keys_sha256": hashlib.sha256("\n".join(sorted(unique)).encode()).hexdigest(),
              "nonempty_groups": groups, "true_empty_groups_zero": empty,
              "by_case": by_case, "probe_fits": results,
              "estimated_4worker_seconds": estimate,
              "max_sample_4worker_seconds": len(unique) * max(measured) / 4,
              "budget_seconds": BUDGET_SECONDS, "affordable": estimate <= BUDGET_SECONDS,
              "estimate_limit": "three first-case knot-size positions; estimate not a convergence claim",
              "bundle_uncompressed_bytes": bundle_bytes, "working_set_bound_bytes": working_bytes,
              "matching_profile_seconds": time.perf_counter() - begin,
              "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    json_write(OUT / "profile.json", report)
    print("COST_GATE affordable={} estimated_4worker_seconds={:.3f}".format(
        report["affordable"], estimate), flush=True)
    return report


def aligned_case(row, meta, services):
    z = arrays_read(STAGE1 / row["case"] / "temporal.npz")
    count = len(z["starts"])
    selected = [(i, services.index(s)) for i, s in enumerate(meta["services"])
                if s not in ROLE_EXCLUSIONS]
    source, local = zip(*selected)
    raw = np.full((count, len(services), 10, 8), np.nan, dtype=np.float32)
    traces = np.zeros((count, len(services), 10, 2), dtype=np.float32)
    observed = np.zeros(raw.shape, dtype=bool)
    raw[:, local] = z["metrics"][:, source]
    traces[:, local] = z["traces"][:, source]
    observed[:, local] = z["metric_observed"][:, source]
    return {"metrics": raw, "metric_observed": observed, "traces": traces,
            "starts": z["starts"], "labels": pure.global_labels(
                z["starts"], row["inject_time"], services.index(row["root_cause_service"])),
            "partition": np.full(count, row["partition"]), "case_ids": np.full(count, row["case"])}


def validate_bundle(arrays, services, events):
    require(set(arrays) == KEYS, "Unexpected bundle fields")
    count, nodes = len(arrays["labels"]), len(services)
    for key, shape in (("metrics", (count, nodes, 10, 8)),
                       ("traces", (count, nodes, 10, 2)), ("logs", (count, nodes, events))):
        require(arrays[key].dtype == np.float32 and arrays[key].shape == shape,
                "Invalid bundle " + key)
    require(arrays["metric_observed"].dtype == np.bool_, "Invalid metric mask")
    np.testing.assert_array_equal(arrays["metric_observed"], np.isfinite(arrays["metrics"]))
    require(not np.isinf(arrays["metrics"]).any() and np.isfinite(arrays["traces"]).all() and
            np.all(arrays["traces"][..., 1] == 0) and np.isfinite(arrays["logs"]).all() and
            (arrays["logs"] >= 0).all(), "Invalid raw numeric values")
    for key in ("labels", "starts", "indices"):
        require(arrays[key].dtype == np.int64 and arrays[key].shape == (count,),
                "Invalid provenance " + key)
    require(np.all((arrays["labels"] >= -1) & (arrays["labels"] < nodes)), "Invalid root index")
    np.testing.assert_array_equal(arrays["indices"], np.arange(count, dtype=np.int64))
    for key in ("partition", "case_ids"):
        require(arrays[key].dtype.kind == "U" and arrays[key].shape == (count,), "Invalid strings")
    intervals = []
    for case in np.unique(arrays["case_ids"]):
        use = arrays["case_ids"] == case
        require(len(set(arrays["partition"][use])) == 1, "Case crosses partitions")
        stamps = arrays["starts"][use]
        require(np.all(np.diff(stamps) == 10), "Case window order/duplication")
        require(len(set(arrays["labels"][use]) - {-1}) == 1, "Case root changes")
        intervals.append({"case": str(case), "partition": str(arrays["partition"][use][0]),
                          "start": int(stamps[0]), "end_exclusive": int(stamps[-1]) + 10})
    require(not pure.interval_overlaps(intervals), "Cross-part absolute interval conflict")
    edges = arrays["edge_pairs"]
    require(edges.dtype == np.int64 and edges.ndim == 2 and edges.shape[1] == 2 and
            len(edges) >= 3 and np.all((edges >= 0) & (edges < nodes)), "Invalid Kx2 edges")
    pairs = set(map(tuple, edges.tolist()))
    require(len(pairs) == len(edges) and all((i, i) in pairs for i in range(nodes)),
            "Missing self-loop/duplicate edge")


def prepare(rows, metadata, services, edges, miner, template, precheck, cost, guard, workers):
    require(1 <= workers <= 4, "At most four CPU1 workers")
    require(cost["affordable"], "STOP_COST: measured unchanged native Hawkes exceeds two-hour budget")
    require(not (OUT / "bundle.npz").exists() and not (OUT / "input.json").exists(),
            "Never overwrite final inputs")
    begin = time.perf_counter()
    pieces, cases, fitted = {}, [], {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for row in rows:
            meta = metadata[row["case"]]
            arrays = aligned_case(row, meta, services)
            matched, matched_meta = matched_case(row, meta, services, miner, template)
            groups = list(pure.case_groups(matched, int(arrays["starts"][0]), template["event_count"]))
            unique = {key: knots for _, _, key, knots in groups}
            missing = [(key, knots) for key, knots in unique.items()
                       if not (OUT / "hawkes" / (key + ".json")).exists()]
            for record in pool.map(worker_fit, missing, chunksize=1):
                fitted[record["key"]] = record
            logs = np.zeros((len(arrays["starts"]), len(services), template["event_count"]),
                            dtype=np.float32)
            for window, node, key, knots in groups:
                baseline, record = cached_fit(key, knots)
                logs[window, node] = baseline
                fitted[key] = record
            arrays["logs"] = logs
            offset = sum(c["windows"] for c in cases)
            cases.append(dict(row, row_start=offset, row_end_exclusive=offset + len(logs),
                              windows=len(logs), stage1_member_hashes=meta["output_hashes"],
                              absent_global_nodes=sorted(set(services) - set(meta["services"])),
                              matched=matched_meta))
            for key, value in arrays.items():
                pieces.setdefault(key, []).append(value)
            print("FEATURE_CASE case={} windows={} groups={} new_fits={}".format(
                row["case"], len(logs), len(groups), len(missing)), flush=True)
    bundle = {key: np.concatenate(values) for key, values in pieces.items()}
    bundle["indices"] = np.arange(len(bundle["labels"]), dtype=np.int64)
    bundle["edge_pairs"] = edges
    validate_bundle(bundle, services, template["event_count"])
    require(len(fitted) == cost["unique_input_count"], "Unique Hawkes input count changed")
    require(pure.cluster_records(miner) == template["clusters"] and
            digest(OUT / "drain.snapshot") == template["snapshot_sha256"], "Templates mutated")
    for path, expected in precheck["source_hashes"].items():
        require(digest(REPO / path) == expected, "Source changed during preparation")
    for row in rows:
        folder = STAGE1 / row["case"]
        require(digest(folder / "metadata.json") == row["metadata_sha256"], "Metadata changed")
        for name, expected in metadata[row["case"]]["output_hashes"].items():
            require(digest(folder / name) == expected, "Original stage1 changed")
    bundle_hash = arrays_write(OUT / "bundle.npz", bundle)
    records = list(fitted.values())
    counts = {part: {"cases": sum(r["partition"] == part for r in rows),
                     "windows": int((bundle["partition"] == part).sum()),
                     "normal": int(((bundle["partition"] == part) & (bundle["labels"] < 0)).sum()),
                     "fault": int(((bundle["partition"] == part) & (bundle["labels"] >= 0)).sum()),
                     "missing_metric_cells": int((~bundle["metric_observed"][
                         bundle["partition"] == part]).sum())}
              for part in ("train", "validation")}
    result = {"status": "KNOWN_INPUTS_PASS", "services": services,
              "event_count": template["event_count"], "families": pure.FAMILIES,
              "bundle_sha256": bundle_hash, "split_sha256": SPLIT_HASH,
              "stage1_manifest_sha256": MANIFEST_HASH, "sources": precheck["source_hashes"],
              "role_policy": ROLE_POLICY, "policy_sha256": POLICY_HASH,
              "input_binding_sha256": INPUT_BINDING,
              "source_evidence_sha256": precheck["source_hashes"][ROLE_POLICY["source_evidence"]],
              "observation_accounting": precheck["observation_accounting"],
              "template_sha256": digest(OUT / "templates.json"), "templates": template,
              "cases": cases, "counts": counts, "rows": len(bundle["labels"]),
              "windows": [{"index": i, "case_id": str(bundle["case_ids"][i]),
                           "start": int(bundle["starts"][i]), "partition": str(bundle["partition"][i]),
                           "label": int(bundle["labels"][i])} for i in range(len(bundle["labels"]))],
              "graph_source": "TRAIN observed edge union + self-loops; raw identifiers, no alias merge",
              "edge_pairs": edges.tolist(), "normalization": "NONE; runner TRAIN-only imputation/scaling",
              "protection": guard.stats, "software": {name: importlib.metadata.version(name)
                  for name in ("numpy", "tick", "drain3", "torch")},
              "cost": {"workers": workers, "threads_per_worker": 1, "pid": os.getpid(),
                       "worker_pids": sorted({r["worker_pid"] for r in records}),
                       "preparation_seconds": time.perf_counter() - begin,
                       "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       "unique_fits": len(fitted), "fit_seconds": sum(r["seconds"] for r in records),
                       "cap_reached": sum(r["cap_reached"] for r in records),
                       "warning_fits": sum(bool(r["warnings"]) for r in records),
                       "warnings": dict(Counter(w for r in records for w in r["warnings"])),
                       "profile": cost},
              "checks": {"original_hashes_unchanged": True, "cross_partition_overlaps": 0,
                         "templates_frozen": True, "protected_opens": 0, "roundtrip": True}}
    json_write(OUT / "input.json", result)
    print("KNOWN_INPUTS_PASS cases=72 rows={} nodes={} events={} bundle_sha256={}".format(
        len(bundle["labels"]), len(services), template["event_count"], bundle_hash), flush=True)


def main():
    require(__debug__, "Assertions must remain enabled")
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preflight", "profile", "prepare"), nargs="?", default="prepare")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    require(1 <= args.workers <= 4, "At most four workers")
    OUT.mkdir(exist_ok=True)
    for name in ("matched", "hawkes"):
        (OUT / name).mkdir(exist_ok=True)
    started = time.perf_counter()
    print("PREPARE_START pid={} stage={} deadline_seconds={}".format(
        os.getpid(), args.stage, BUDGET_SECONDS), flush=True)
    try:
        rows, metadata, services, edges, precheck, guard = preflight()
        if args.stage == "preflight":
            return
        miner, template = frozen_templates(rows, metadata)
        cost = profile(rows, metadata, services, miner, template, precheck["resources"])
        if args.stage == "profile":
            return
        prepare(rows, metadata, services, edges, miner, template, precheck, cost, guard, args.workers)
    except Exception as error:
        failure = {"status": "STOP", "pid": os.getpid(), "stage": args.stage,
                   "error_type": type(error).__name__, "error": str(error),
                   "seconds": time.perf_counter() - started}
        json_write(OUT / ("failure-{}.json".format(os.getpid())), failure)
        print("KNOWN_INPUTS_STOP " + json.dumps(failure, sort_keys=True), flush=True)
        raise


if __name__ == "__main__":
    main()
