"""Freeze a TRAIN-only 257-event map, select windows, then count pooling."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, List, Set

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
ARTIFACTS = ROOT / "artifacts"
MATCHED = ARTIFACTS / "matched"
SPLIT = ROOT / "split.json"
PREFLIGHT = ARTIFACTS / "preflight.json"
TEMPLATES = ARTIFACTS / "templates.json"
SNAPSHOT = ARTIFACTS / "drain.snapshot"
EXPECTED_SPLIT = "3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2"
EXPECTED_BINDING = "e65db027735a564075197173189bc7bdfb2672dd42401aae23370e5a7f8e534c"
EXPECTED_SNAPSHOT = "70c77a932c150cf47488a7fd3b1a0efc9abfde11856c30090c7584e1925b3072"
EXPECTED_POLICY = "beefc91967df310e692707047aac8c98661ae205b1debb0b2104e4be1b64421e"
PARTS = ("train", "validation")


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def exclusive_json(path: Path, value: dict) -> str:
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(payload).hexdigest()


def case_rank(case: str) -> str:
    return hashlib.sha256(("re2-ob-257-cost-v1|case|" + case).encode()).hexdigest()


def window_rank(case: str, start: int) -> str:
    return hashlib.sha256(
        ("re2-ob-257-cost-v1|window|" + case + "|" + str(start)).encode()
    ).hexdigest()


def select_windows(cases: List[dict], intervals: List[dict], services: List[str]) -> dict:
    by_case = {row["case"]: row for row in cases}
    iv = {row["case"]: row for row in intervals}
    roots = sorted({r["root_cause_service"] for r in cases if r["partition"] == "train"})
    chosen = []
    missing = []
    for root in roots:
        candidates = [r for r in cases if r["partition"] == "train"
                      and r["root_cause_service"] == root]
        if not candidates:
            missing.append({"root": root, "layer": "case"})
            continue
        case = min(candidates, key=lambda r: (case_rank(r["case"]), r["case"]))
        interval = iv[case["case"]]
        starts = list(range(interval["start"], interval["end_exclusive"], 10))
        for fault, eligible in (
            (False, [s for s in starts if s + 9 < case["inject_time"]]),
            (True, [s for s in starts if not s + 9 < case["inject_time"]]),
        ):
            if not eligible:
                missing.append({"root": root, "case": case["case"], "fault": fault,
                                "layer": "window"})
                continue
            start = min(eligible, key=lambda s: (window_rank(case["case"], s), s))
            chosen.append({"case": case["case"], "partition": "train", "root": root,
                           "fault": fault, "start": start,
                           "window_index": (start - interval["start"]) // 10,
                           "services": list(services)})
    return {"schema": "re2-ob-257-selection-v1", "rule": "sha256 minimum; TRAIN only",
            "cases": len(roots), "windows": len(chosen), "services": list(services),
            "records": chosen, "missing": missing}


def make_mapping(counts: Dict[int, int], all_ids: List[int]) -> dict:
    require(0 not in counts and all(i > 0 for i in all_ids), "Invalid template ids")
    top = sorted(all_ids, key=lambda i: (-counts.get(i, 0), i))[:256]
    selected = sorted(top)
    ids = {str(cluster): index + 1 for index, cluster in enumerate(selected)}
    return {"schema": "re2-ob-257-mapping-v1", "dimensions": 257, "retained": 256,
            "unknown_cluster_id": 0, "unknown_feature_id": 0,
            "rank_rule": "descending TRAIN pre-injection matched occurrences, then cluster_id ascending",
            "feature_rule": "selected cluster_id ascending assigned feature ids 1..256",
            "counts": {str(i): int(counts.get(i, 0)) for i in sorted(all_ids)},
            "selected_cluster_ids": selected, "cluster_id_to_feature": ids,
            "unselected_cluster_ids": sorted(set(all_ids) - set(selected))}


def summary(value: str) -> str:
    # Exclude obvious identifier-like tokens and keep only a short generic fragment.
    words = re.findall(r"[A-Za-z][A-Za-z_-]{2,}", value.lower())
    words = [w for w in words if w not in {"user", "session", "request", "token", "account"}]
    return " ".join(words[:6]) or "template text omitted"


class CacheGuard:
    def __init__(self, train_cases: Set[str], validation_cases: Set[str], frozen: Path):
        self.train = train_cases
        self.validation = validation_cases
        self.frozen = frozen
        self.phase = "train"
        self.opens: List[str] = []

    def advance(self, expected_hash: str) -> None:
        require(self.frozen.is_file() and digest(self.frozen) == expected_hash,
                "Mapping must be exclusively saved and hashed before validation reads")
        self.phase = "coverage"

    def check(self, case: str) -> None:
        allowed = self.train if self.phase == "train" else self.train | self.validation
        require(case in allowed, "Cache read outside current phase: " + case)
        if self.phase == "train":
            require(case not in self.validation, "Validation read before mapping freeze")
        self.opens.append(self.phase + ":" + case)


def main() -> None:
    started = time.monotonic()
    evidence = HERE / "mapping_evidence"
    evidence.mkdir(exist_ok=True)
    require(not (HERE / "mapping.json").exists() and
            not (HERE / "selection.json").exists() and
            not (HERE / "coverage.json").exists(), "Refusing to overwrite mapping outputs")
    require(digest(SPLIT) == EXPECTED_SPLIT, "split hash mismatch")
    split = json.loads(SPLIT.read_text())
    pre = json.loads(PREFLIGHT.read_text())
    templates = json.loads(TEMPLATES.read_text())
    require(pre["cases"] == 72 and pre["case_counts"] == {"train": 48, "validation": 24},
            "Preflight case allowlist mismatch")
    require(pre["input_binding_sha256"] == EXPECTED_BINDING and
            pre["policy_sha256"] == EXPECTED_POLICY and
            digest(SNAPSHOT) == EXPECTED_SNAPSHOT, "Preflight provenance mismatch")
    require(templates["snapshot_sha256"] == EXPECTED_SNAPSHOT and
            templates["split_sha256"] == EXPECTED_SPLIT and
            templates["input_binding_sha256"] == EXPECTED_BINDING and
            templates["policy_sha256"] == EXPECTED_POLICY, "Template provenance mismatch")
    rows = split["cases"]
    require(len(rows) == 72 and len({r["case"] for r in rows}) == 72 and
            sum(r["partition"] == "train" for r in rows) == 48 and
            sum(r["partition"] == "validation" for r in rows) == 24,
            "Split allowlist mismatch")
    services = pre["services"]
    require(len(services) == 14 and len(set(services)) == 14, "Expected 14 services")
    intervals = pre["intervals"]
    require(len(intervals) == 72 and {x["case"] for x in intervals} == {r["case"] for r in rows},
            "Interval allowlist mismatch")
    row_by_case = {r["case"]: r for r in rows}
    iv_by_case = {r["case"]: r for r in intervals}
    cache_rows = {}
    train = {r["case"] for r in rows if r["partition"] == "train"}
    validation = {r["case"] for r in rows if r["partition"] == "validation"}
    guard = CacheGuard(train, validation, HERE / "mapping.json")
    template_records = {int(c["cluster_id"]): c for c in templates["clusters"]}
    all_ids = sorted(template_records)
    feature_to_cluster = {int(feature): int(cluster)
                          for cluster, feature in templates["cluster_id_to_feature"].items()}
    require(len(feature_to_cluster) == 1024 and set(feature_to_cluster) == set(range(1, 1025)),
            "Invalid frozen template feature map")
    require(len(all_ids) == 1024 and 0 not in template_records, "Expected frozen 1024 templates")
    counts = {i: 0 for i in all_ids}
    source_hashes = {"split": digest(SPLIT), "preflight": digest(PREFLIGHT),
                     "templates": digest(TEMPLATES), "snapshot": digest(SNAPSHOT)}
    for case in sorted(train):
        guard.check(case)
        meta_path, data_path = MATCHED / (case + ".json"), MATCHED / (case + ".npz")
        meta = json.loads(meta_path.read_text())
        row = row_by_case[case]
        require(meta["case"] == case and meta["partition"] == "train" and
                meta["split_sha256"] == EXPECTED_SPLIT and
                meta["input_binding_sha256"] == EXPECTED_BINDING and
                meta["policy_sha256"] == EXPECTED_POLICY and
                meta["snapshot_sha256"] == EXPECTED_SNAPSHOT,
                "TRAIN cache provenance mismatch: " + case)
        require(digest(data_path) == meta["sha256"] and
                meta["stage1_log_sha256"] == next(
                    c["stage1_member_hashes"]["logs.jsonl.gz"]
                    for c in pre["verified_cases"] if c["case"] == case),
                "TRAIN cache hash/source mismatch: " + case)
        with np.load(data_path, allow_pickle=False) as z:
            require(set(z.files) == {"times", "nodes", "events"}, "Unexpected cache arrays")
            times, nodes, events = z["times"], z["nodes"], z["events"]
            require(all(a.dtype == np.int64 and a.ndim == 1 for a in (times, nodes, events))
                    and len(times) == len(nodes) == len(events) == meta["rows"],
                    "Cache row shape/dtype mismatch: " + case)
            require(bool(np.all((nodes >= 0) & (nodes < len(services)))) and
                    bool(np.all((events >= 0) & (events <= 1024))) and
                    np.all((times >= iv_by_case[case]["start"]) &
                           (times < iv_by_case[case]["end_exclusive"])).all(),
                    "Cache node/event/time integrity failure: " + case)
            for event, stamp in zip(events.tolist(), times.tolist()):
                if event and stamp < row["inject_time"]:
                    cluster_id = feature_to_cluster[event]
                    require(cluster_id in counts, "Unknown frozen cluster id")
                    counts[cluster_id] += 1
            cache_rows[case] = {"meta": meta, "times": times.copy(),
                                "nodes": nodes.copy(), "events": events.copy()}
        require(sum(meta["log_counts"]["retained_by_service"].values()) == meta["rows"],
                "TRAIN metadata row conservation")
        source_hashes["matched/" + case + ".json"] = digest(meta_path)
        source_hashes["matched/" + case + ".npz"] = digest(data_path)
    mapping = make_mapping(counts, all_ids)
    mapping.update({"split_sha256": EXPECTED_SPLIT, "input_binding_sha256": EXPECTED_BINDING,
                    "policy_sha256": EXPECTED_POLICY, "snapshot_sha256": EXPECTED_SNAPSHOT,
                    "frequency_source_cases": 48, "frequency_validation_reads": 0,
                    "strictly_preinject_occurrences": sum(counts.values()),
                    "source_hashes": source_hashes})
    mapping_hash = exclusive_json(HERE / "mapping.json", mapping)
    selection = select_windows(rows, intervals, services)
    selection.update({"split_sha256": EXPECTED_SPLIT, "preflight_sha256": digest(PREFLIGHT),
                      "mapping_sha256": mapping_hash})
    selection_hash = exclusive_json(HERE / "selection.json", selection)
    guard.advance(mapping_hash)

    # No template text is emitted; summaries are sanitized and bounded.
    services_i = {s: i for i, s in enumerate(services)}
    aggregate = {(p, phase, s): {"total": 0, "kept": 0, "newly_pooled": 0,
                                  "old_unknown": 0, "other": 0, "pooled": {}}
                 for p in PARTS for phase in ("pre", "post") for s in services}
    for case in sorted(train | validation):
        guard.check(case)
        if case not in cache_rows:
            meta_path, data_path = MATCHED / (case + ".json"), MATCHED / (case + ".npz")
            meta = json.loads(meta_path.read_text())
            row = row_by_case[case]
            require(meta["case"] == case and meta["partition"] == "validation" and
                    meta["split_sha256"] == EXPECTED_SPLIT and
                    meta["input_binding_sha256"] == EXPECTED_BINDING and
                    meta["policy_sha256"] == EXPECTED_POLICY and
                    meta["snapshot_sha256"] == EXPECTED_SNAPSHOT and
                    digest(data_path) == meta["sha256"], "Validation cache provenance/hash mismatch")
            require(meta["stage1_log_sha256"] == next(
                c["stage1_member_hashes"]["logs.jsonl.gz"]
                for c in pre["verified_cases"] if c["case"] == case),
                "Validation cached source mismatch")
            with np.load(data_path, allow_pickle=False) as z:
                require(set(z.files) == {"times", "nodes", "events"}, "Unexpected cache arrays")
                times, nodes, events = z["times"], z["nodes"], z["events"]
                require(all(a.dtype == np.int64 and a.ndim == 1 for a in (times, nodes, events))
                        and len(times) == len(nodes) == len(events) == meta["rows"] and
                        bool(np.all((nodes >= 0) & (nodes < len(services)))) and
                        bool(np.all((events >= 0) & (events <= 1024))) and
                        np.all((times >= iv_by_case[case]["start"]) &
                               (times < iv_by_case[case]["end_exclusive"])).all(),
                        "Validation cache integrity failure: " + case)
                cache_rows[case] = {"meta": meta, "times": times.copy(),
                                    "nodes": nodes.copy(), "events": events.copy()}
            require(sum(meta["log_counts"]["retained_by_service"].values()) == meta["rows"],
                    "Validation row conservation")
            source_hashes["matched/" + case + ".json"] = digest(meta_path)
            source_hashes["matched/" + case + ".npz"] = digest(data_path)
        cache = cache_rows[case]
        part = row_by_case[case]["partition"]
        for stamp, node, event in zip(cache["times"], cache["nodes"], cache["events"]):
            phase = "pre" if stamp < row_by_case[case]["inject_time"] else "post"
            bucket = aggregate[(part, phase, services[int(node)])]
            bucket["total"] += 1
            if event == 0:
                bucket["old_unknown"] += 1
                bucket["other"] += 1
            elif str(feature_to_cluster[int(event)]) in mapping["cluster_id_to_feature"]:
                bucket["kept"] += 1
            else:
                bucket["newly_pooled"] += 1
                bucket["other"] += 1
                cluster_id = feature_to_cluster[int(event)]
                bucket["pooled"][cluster_id] = bucket["pooled"].get(cluster_id, 0) + 1
    records = []
    for (part, phase, service), b in sorted(aggregate.items()):
        require(b["total"] == b["kept"] + b["newly_pooled"] + b["old_unknown"],
                "Per-service row conservation")
        total = b["total"]
        top = sorted(b["pooled"].items(), key=lambda x: (-x[1], x[0]))[:10]
        records.append({"partition": part, "phase": phase, "service": service,
                        "total": total, "kept": b["kept"],
                        "newly_pooled": b["newly_pooled"], "old_unknown": b["old_unknown"],
                        "other": b["other"],
                        "other_ratio": b["other"] / total if total else None,
                        "distinct_pooled_templates": len(b["pooled"]),
                        "top_pooled_templates": [
                            {"cluster_id": cid, "rows": n,
                             "summary": summary(str(template_records[cid].get("template", "")))}
                            for cid, n in top]})
    coverage = {"schema": "re2-ob-257-coverage-v1", "split_sha256": EXPECTED_SPLIT,
                "mapping_sha256": mapping_hash, "selection_sha256": selection_hash,
                "input_binding_sha256": EXPECTED_BINDING, "policy_sha256": EXPECTED_POLICY,
                "snapshot_sha256": EXPECTED_SNAPSHOT, "cases": 72, "services": services,
                "records": records, "cache_reads": guard.opens,
                "validation_opened_after_mapping_sha256": mapping_hash,
                "row_conservation": True,
                "source_hashes": source_hashes,
                "aggregation_seconds": time.monotonic() - started}
    coverage_hash = exclusive_json(HERE / "coverage.json", coverage)
    evidence_value = {"status": "PASS", "mapping_sha256": mapping_hash,
                      "selection_sha256": selection_hash, "coverage_sha256": coverage_hash,
                      "mapping_py_sha256": digest(HERE / "mapping.py"),
                      "split_sha256": digest(SPLIT), "source_hashes": source_hashes,
                      "elapsed_seconds": time.monotonic() - started,
                      "exits": {"aggregation": 0}, "validation_read_boundary_enforced": True}
    exclusive_json(evidence / "completion.json", evidence_value)
    print(json.dumps({"mapping_sha256": mapping_hash, "selection_sha256": selection_hash,
                      "coverage_sha256": coverage_hash, "cases": 72,
                      "mapping_counts": {"selected": len(mapping["selected_cluster_ids"]),
                                         "pooled_templates": len(mapping["unselected_cluster_ids"])},
                      "coverage_records": len(records),
                      "aggregation_seconds": coverage["aggregation_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
