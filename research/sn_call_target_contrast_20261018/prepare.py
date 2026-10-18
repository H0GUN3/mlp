"""One guarded TRAIN-linked destination-only preparation; never fits a model."""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = ROOT / "research/native_reproduction_20261013"
SAFE = ROOT / "research/sn_hawkes_horizon_contrast_20261017/inputs"
RAW = ROOT / "data/eadro_native/SN_Dataset/SN Dataset"
INPUTS = HERE / "inputs"
STRATEGY = "train_linked_destination_only"
ARRAYS = {"metrics", "traces", "logs", "labels", "indices"}
MEDIA = ("compose-post-service", "compose_media_client")
DISCLOSURE = (
    "Both passes stream all four shared spans.json files through the existing "
    "native_data_profile.json_array parser. Whole shared JSON bytes, structure "
    "and primitive values are decoded; every startTime is interpreted for routing. "
    "Pass one interprets operation/duration/service/reference content only after "
    "a TRAIN316 start-bin guard; mapping.json is exclusively written and hashed "
    "before pass two or safe validation tensor loading. Pass two interprets "
    "observation content only after an allowed394 start-bin guard. Test169 and "
    "unassigned1 have no numerical model rows materialized. This is NOT a claim "
    "that their raw bytes or primitive JSON values were never decoded."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, obj):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def code_hashes():
    return {name: file_hash(HERE / name) for name in ("prepare.py", "test_prepare.py")}


def parser_module():
    sys.path.insert(0, str(NATIVE))
    return importlib.import_module("native_data_profile")


def routes_for(metadata, positions):
    routes = {}
    for row in positions:
        window = metadata["windows"][row]
        require(window["end"] == window["start"] + 9, "Changed ten-second bounds")
        for second in range(10):
            key = (window["run_id"], window["start"] + second)
            require(key not in routes, "Overlapping selected windows")
            routes[key] = (row, second)
    return routes


def selected_spans(trace, run, routes, services):
    for span in trace["spans"]:
        start = span["startTime"]
        require(type(start) is int, "Invalid timestamp routing")
        slot = routes.get((run, start // 1000000 + 28800))
        if slot is None:
            continue
        # Never inspect operation/duration/identity before the start-bin guard.
        owner = trace["processes"][span["processID"]]["serviceName"]
        require(owner in services, "Unknown selected owner")
        operation = span["operationName"]
        duration = span["duration"]
        identity = (span["traceID"], span["spanID"])
        require(all(isinstance(s, str) and s for s in identity)
                and identity[0] == trace["traceID"], "Invalid selected identity")
        require(isinstance(operation, str), "Invalid selected operation")
        require(type(duration) is int and duration >= 0, "Invalid selected duration")
        signature = hashlib.sha256(json.dumps(
            {"service": owner, "span": span}, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        refs = tuple(sorted(set(
            (ref["traceID"], ref["spanID"])
            for ref in span.get("references", [])
            if ref.get("refType") == "CHILD_OF"
        )))
        yield {
            "identity": identity, "signature": signature, "owner": owner,
            "operation": operation, "duration": duration, "start": start,
            "references": refs, "slot": slot, "run": run,
        }


class Identities:
    """Deduplicate evidence only; callers still aggregate every yielded record."""
    def __init__(self):
        self.signatures = {}
        self.records = {}
        self.counts = Counter()

    def observe(self, record, split):
        identity = record["identity"]
        previous = self.signatures.get(identity)
        require(previous is None or previous == record["signature"],
                "Conflicting selected identity: " + repr(identity))
        self.signatures[identity] = record["signature"]
        key = (record["run"],) + identity
        self.counts[split + "_occurrences"] += 1
        self.counts[split + "_duplicate_occurrences"] += int(key in self.records)
        if key not in self.records:
            self.records[key] = record


def linked_evidence(records, services, original_indices):
    targets = defaultdict(set)
    evidence = defaultdict(dict)
    counts = Counter()
    for child in records.values():
        for trace_id, span_id in child["references"]:
            counts["unique_child_of_references"] += 1
            parent = records.get((child["run"], trace_id, span_id))
            if parent is None:
                counts["unmatched_selected_parent_references"] += 1
                continue
            # CHILD_OF joins are exact and never completed using another split.
            if trace_id != child["identity"][0]:
                counts["cross_trace_references_rejected"] += 1
                continue
            if not parent["operation"].endswith("_client"):
                counts["nonclient_parent_links"] += 1
                continue
            if child["owner"] == parent["owner"] or child["owner"] not in services:
                counts["same_owner_or_external_links"] += 1
                continue
            key = (parent["owner"], parent["operation"])
            targets[key].add(child["owner"])
            identity = parent["identity"] + child["identity"]
            evidence[key][identity] = {
                "trace_id": trace_id, "parent_span_id": span_id,
                "child_span_id": child["identity"][1], "target": child["owner"],
                "run_id": child["run"],
                "parent_original_index": int(original_indices[parent["slot"][0]]),
                "child_original_index": int(original_indices[child["slot"][0]]),
                "parent_start_second": parent["start"] // 1000000 + 28800,
                "child_start_second": child["start"] // 1000000 + 28800,
            }
    ambiguous = [key for key, values in targets.items() if len(values) != 1]
    require(not ambiguous, "Multiple target gate failure: " + repr(ambiguous))
    mapping = {key: next(iter(values)) for key, values in targets.items()}
    counts["ambiguous_keys"] = len(ambiguous)
    counts["admitted_keys"] = len(mapping)
    counts["deduplicated_support_links"] = sum(len(v) for v in evidence.values())
    return mapping, evidence, dict(counts)


def freeze_mapping(path, mapping, evidence, audit, provenance):
    require(mapping.get(MEDIA) == "media-service", "Missing TRAIN-supported media mapping")
    entries = [
        {"owner": owner, "operation": operation, "target": target,
         "support_count": len(evidence[(owner, operation)]),
         "evidence": sorted(evidence[(owner, operation)].values(),
                            key=lambda item: (item["trace_id"], item["parent_span_id"],
                                              item["child_span_id"]))}
        for (owner, operation), target in sorted(mapping.items())
    ]
    write_json(path, {"strategy": STRATEGY, "support_split": "TRAIN316 only",
                      "entries": entries, "audit": audit, "provenance": provenance})
    return file_hash(path)


def load_frozen(path, expected):
    require(file_hash(path) == expected, "Frozen dictionary changed")
    obj = read_json(path)
    require(obj["strategy"] == STRATEGY, "Incorrect dictionary strategy")
    mapping = {}
    for entry in obj["entries"]:
        key = (entry["owner"], entry["operation"])
        require(key not in mapping and entry["support_count"] > 0
                and entry["operation"].endswith("_client"), "Invalid frozen key")
        mapping[key] = entry["target"]
    require(mapping.get(MEDIA) == "media-service", "Frozen media key missing")
    return mapping


def safe_selected_arrays(archive):
    # The safe horizon archive also stores an unused absolute-horizon arm.
    require(set(archive.files) == ARRAYS | {"log_absolute"}, "Unsafe selected archive members")
    return {key: archive[key] for key in ARRAYS}


def failed_mapping_stage():
    require(read_json(INPUTS / "producer.exit.json")["exit_code"] == 1,
            "Recovery is only for the failed, never-completed producer")
    require(not any((INPUTS / name).exists() for name in (
        "selected.npz", "metadata.json", "preparation.pending.json", "preparation.json")),
        "Never retry a completed producer or overwrite a partial tensor")
    log = (INPUTS / "producer.log").read_text()
    require(log.count("MAPPING_FROZEN ") == 1
            and "ValueError: Unsafe selected archive members" in log
            and "ALLOWED394_RECORDING_DONE" not in log
            and "PREPARATION_PRODUCER_VERIFIED" not in log, "Unrecognized failure; stop")
    digest = log.split("MAPPING_FROZEN ", 1)[1].splitlines()[0]
    require(file_hash(INPUTS / "mapping.json") == digest, "Original frozen mapping changed")
    stage = read_json(INPUTS / "mapping.json")
    initial_claim = read_json(INPUTS / "execution.claim.json")
    original_hashes = stage["provenance"]["input_hashes"]
    for path, expected in original_hashes.items():
        if Path(path) in (HERE / "prepare.py", HERE / "test_prepare.py"):
            require(expected == initial_claim["code_hashes"][Path(path).name],
                    "Unexpected original mapping implementation hash")
        else:
            require(file_hash(path) == expected, "Original mapping source changed: " + path)
    mapping_seconds = (
        (INPUTS / "mapping.json").stat().st_mtime_ns
        - (INPUTS / "execution.claim.json").stat().st_mtime_ns
    ) / 1e9
    failed_seconds = (
        (INPUTS / "producer.exit.json").stat().st_mtime_ns
        - (INPUTS / "execution.claim.json").stat().st_mtime_ns
    ) / 1e9
    require(0 < mapping_seconds <= failed_seconds, "Invalid failed-stage wall-clock timing")
    return digest, stage, {
        "producer_exit_code": 1, "frozen_mapping_sha256": digest,
        "original_code_hashes": initial_claim["code_hashes"],
        "producer_log_sha256": file_hash(INPUTS / "producer.log"),
        "failure_sha256": file_hash(INPUTS / "preparation.failure.json"),
        "mapping_seconds": mapping_seconds, "failed_attempt_seconds": failed_seconds,
        "timing_measurement": (
            "Filesystem nanosecond wall-clock intervals: initial execution.claim.json "
            "to closed mapping.json (mapping stage including initial source checks), "
            "and to producer.exit.json (failed attempt). Initial failure preceded "
            "monotonic cost manifest publication; do not call these monotonic timings."),
        "recovery": "Reuse frozen TRAIN mapping byte-for-byte; fix source-member guard only",
    }


def destination(owner, operation, mapping):
    return mapping.get((owner, operation), owner) if operation.endswith("_client") else owner


class Aggregates:
    def __init__(self, rows, services, mapping, train_positions):
        self.services = {name: i for i, name in enumerate(services)}
        self.mapping = mapping
        self.train = set(train_positions)
        shape = (rows, len(services), 10)
        self.owner_sums = np.zeros(shape, dtype=np.float64)
        self.target_sums = np.zeros(shape, dtype=np.float64)
        self.owner_counts = np.zeros(shape, dtype=np.int64)
        self.target_counts = np.zeros(shape, dtype=np.int64)
        self.owner_us = np.zeros(shape, dtype=np.int64)
        self.target_us = np.zeros(shape, dtype=np.int64)
        self.total_us = np.zeros((rows, 10), dtype=np.int64)
        self.identities = Identities()
        self.coverage = {split: Counter() for split in ("TRAIN", "validation")}
        self.by_key = {split: defaultdict(Counter) for split in self.coverage}
        self.moves = {split: Counter() for split in self.coverage}
        self.affected = {split: set() for split in self.coverage}

    def add(self, record):
        row, second = record["slot"]
        split = "TRAIN" if row in self.train else "validation"
        self.identities.observe(record, split)
        owner, operation, duration = record["owner"], record["operation"], record["duration"]
        target = destination(owner, operation, self.mapping)
        require(target in self.services, "Unknown frozen destination")
        source_id, target_id = self.services[owner], self.services[target]
        require(duration <= np.iinfo(np.int64).max - int(self.total_us[row, second]),
                "Integer duration accounting overflow")
        self.total_us[row, second] += duration
        seconds = duration / 1000000.0
        self.owner_sums[row, source_id, second] += seconds
        self.target_sums[row, target_id, second] += seconds
        self.owner_counts[row, source_id, second] += 1
        self.target_counts[row, target_id, second] += 1
        self.owner_us[row, source_id, second] += duration
        self.target_us[row, target_id, second] += duration
        stats = self.coverage[split]
        stats["all_occurrences"] += 1
        if operation.endswith("_client"):
            kind = "mapped_client_occurrences" if target != owner else "unmapped_client_occurrences"
            stats["client_occurrences"] += 1
            stats[kind] += 1
            key_stats = self.by_key[split][(owner, operation)]
            key_stats["eligible_occurrences"] += 1
            key_stats[kind] += 1
        else:
            stats["nonclient_owner_fallback_occurrences"] += 1
        if target != owner:
            self.moves[split][(owner, target)] += 1
            self.affected[split].add((row, target_id, second))

    def finish(self):
        require(np.array_equal(self.owner_counts.sum(axis=1), self.target_counts.sum(axis=1)),
                "Per-second occurrence counts changed")
        require(np.array_equal(self.owner_us.sum(axis=1), self.total_us)
                and np.array_equal(self.target_us.sum(axis=1), self.total_us),
                "Per-second original duration sums changed")
        require(int(self.owner_counts.sum()) == int(self.target_counts.sum())
                == sum(v["all_occurrences"] for v in self.coverage.values()),
                "Occurrence count not preserved")
        outputs = []
        for sums, counts in ((self.owner_sums, self.owner_counts),
                             (self.target_sums, self.target_counts)):
            values = np.zeros(sums.shape + (2,), dtype=np.float64)
            np.divide(sums, counts, out=values[..., 0], where=counts > 0)
            require(np.isfinite(values).all() and (values >= 0).all(), "Nonfinite trace")
            require(not np.any(values[..., 1]), "Nonzero spare channel")
            require(not np.any(values[..., 0][counts == 0]), "Broken zero fill")
            outputs.append(values)
        return outputs

    def report(self):
        result = {}
        for split in self.coverage:
            result[split] = {
                **{key: self.coverage[split][key] for key in (
                    "all_occurrences", "client_occurrences", "mapped_client_occurrences",
                    "unmapped_client_occurrences", "nonclient_owner_fallback_occurrences")},
                "duplicate_identity_occurrences": self.identities.counts[
                    split + "_duplicate_occurrences"],
                "affected_target_bins": len(self.affected[split]),
                "by_key": [
                    {"owner": owner, "operation": operation,
                     "target": destination(owner, operation, self.mapping), **dict(counts)}
                    for (owner, operation), counts in sorted(self.by_key[split].items())],
                "moved_owner_to_target": [
                    {"owner": owner, "target": target, "occurrences": count}
                    for (owner, target), count in sorted(self.moves[split].items())],
            }
        return result


def exact_arrays(safe, output, owner):
    require(set(safe) == set(output) == ARRAYS, "Extra or missing array member")
    checks = {}
    require(np.array_equal(owner, safe["traces"])
            and owner.dtype == safe["traces"].dtype, "Owner baseline is not elementwise EXACT")
    checks["baseline_owner_exact"] = True
    for key in ("metrics", "logs", "labels", "indices"):
        require(output[key].dtype == safe[key].dtype
                and np.array_equal(output[key], safe[key]), key + " changed")
        checks[key + "_exact"] = True
    require(output["traces"].shape == safe["traces"].shape
            and output["traces"].dtype == safe["traces"].dtype, "Trace shape/dtype changed")
    require(not np.any(output["traces"][..., 1]), "Trace channel 1 changed")
    require(all(np.isfinite(value).all() for value in output.values()), "Nonfinite output")
    checks.update(trace_channel1_zero=True, finite=True)
    return checks


def scan(paths, routes, services, parser, expected_hashes, consume, stage):
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for trace in parser.json_array(stream, digest):
                for record in selected_spans(trace, path.parent.name, routes, services):
                    consume(record)
        require(digest.hexdigest() == expected_hashes[str(path)], "Raw source hash changed")
        print(stage + "_RECORDING_DONE " + path.parent.name, flush=True)


def prepare(resume=False):
    started = time.perf_counter()
    require(not any((INPUTS / name).exists() for name in (
        "selected.npz", "metadata.json", "preparation.pending.json", "preparation.json")),
        "Refusing completed/partial tensor producer retry")
    recovery = None
    frozen_stage = None
    frozen_hash = None
    if resume:
        frozen_hash, frozen_stage, recovery = failed_mapping_stage()
    else:
        require(not (INPUTS / "mapping.json").exists()
                and not (INPUTS / "preparation.failure.json").exists(), "Existing failed attempt")
    meta = read_json(SAFE / "metadata.json")
    prior = read_json(SAFE / "preparation.json")
    require(prior["status"] == "PASS" and prior["producer_exit_code"] == 0,
            "Safe source preparation did not pass")
    expected = {
        str(SAFE / name): prior["output_hashes"][name]
        for name in ("selected.npz", "metadata.json")
    }
    expected[str(SAFE / "preparation.json")] = file_hash(SAFE / "preparation.json")
    require(meta["selected_npz_sha256"] == expected[str(SAFE / "selected.npz")],
            "Safe selected hash disagreement")
    native_meta_path = NATIVE / "native_inputs/SN/metadata.json"
    parser_path = NATIVE / "native_data_profile.py"
    expected[str(native_meta_path)] = meta["input_source_hashes"][str(native_meta_path)]
    expected[str(parser_path)] = meta["input_source_hashes"][str(parser_path)]
    for path, value in expected.items():
        require(file_hash(path) == value, "Safe input hash mismatch: " + path)
    native_meta = read_json(native_meta_path)
    services = meta["services"]
    train, validation = meta["train_positions"], meta["validation_positions"]
    require(len(train) == 316 and len(validation) == 78 and len(meta["windows"]) == 394,
            "Unexpected split sizes")
    require(set(train).isdisjoint(validation)
            and sorted(train + validation) == list(range(394)), "Bad split positions")
    require(meta["window_length"] == meta["stride"] == 10
            and len(services) == 12 and meta["normalized"] is False, "Changed input contract")
    split_path = NATIVE / "calibration200/SN/eadro/seed_11/split.json"
    expected[str(split_path)] = meta["original_split_sha256"]
    require(file_hash(split_path) == expected[str(split_path)], "Original split hash changed")
    split = read_json(split_path)["indices"]
    for positions, name in ((train, "train"), (validation, "validation")):
        require([meta["original_indices"][i] for i in positions] == split[name],
                "Original split order changed")
    require(112 not in split["train"] and 112 in split["validation"], "Index112 is not TRAIN")
    runs = sorted({window["run_id"] for window in meta["windows"]})
    require(len(runs) == 4, "Expected four SN recordings only")
    paths = [RAW / "data" / run / "spans.json" for run in runs]
    for path in paths:
        require(RAW.resolve() in path.resolve().parents, "Raw source escapes authorized root")
        expected[str(path)] = native_meta["input_sha256"][str(path.relative_to(RAW))]
    for path in (HERE / "PROTOCOL.md", HERE / "BASELINE.json",
                 HERE / "attribution_sources/AUDIT.md", HERE / "prepare.py", HERE / "test_prepare.py"):
        expected[str(path)] = file_hash(path)
    for path in paths:
        require(file_hash(path) == expected[str(path)], "Original raw hash mismatch")
    parser = parser_module()
    require(services == parser.SERVICES["SN"], "Service order changed")
    if resume:
        if frozen_stage is None or recovery is None or frozen_hash is None:
            raise ValueError("Missing frozen stage")
        train_link_audit = frozen_stage["audit"]
        mapping_seconds = recovery["mapping_seconds"]
        print("MAPPING_REUSED_UNCHANGED " + frozen_hash, flush=True)
    else:
        train_routes = routes_for(meta, train)
        train_ids = Identities()
        mapping_started = time.perf_counter()
        scan(paths, train_routes, services, parser, expected,
             lambda record: train_ids.observe(record, "TRAIN"), "TRAIN")
        mapping, evidence, train_link_audit = linked_evidence(
            train_ids.records, services, meta["original_indices"])
        frozen_hash = freeze_mapping(
            INPUTS / "mapping.json", mapping, evidence, train_link_audit,
            {"train_original_indices": [meta["original_indices"][i] for i in train],
             "input_hashes": expected,
             "identity_counts": dict(train_ids.counts),
             "protected_model_rows_materialized": 0, "access_disclosure": DISCLOSURE})
        mapping_seconds = time.perf_counter() - mapping_started
        print("MAPPING_FROZEN " + frozen_hash, flush=True)
        del train_ids, evidence, mapping

    if frozen_hash is None:
        raise ValueError("Mapping was not frozen")
    aggregation_started = time.perf_counter()
    mapping = load_frozen(INPUTS / "mapping.json", frozen_hash)
    with np.load(str(SAFE / "selected.npz"), allow_pickle=False) as archive:
        safe = safe_selected_arrays(archive)
    require(safe["traces"].shape == (394, 12, 10, 2)
            and np.array_equal(safe["indices"], meta["original_indices"]), "Unsafe tensor rows")
    aggregate = Aggregates(394, services, mapping, train)
    scan(paths, routes_for(meta, range(394)), services, parser, expected,
         aggregate.add, "ALLOWED394")
    owner, candidate = aggregate.finish()
    output = dict(safe, traces=candidate)
    checks = exact_arrays(safe, output, owner)
    checks.update(occurrence_count_preserved=True, original_duration_sums_exact=True,
                  zero_fill=True, media_train_supported=True,
                  mapping_frozen_before_validation=True)
    linkage = {"TRAIN": train_link_audit}
    for split_name, positions in (("TRAIN", train), ("validation", validation)):
        position_set = set(positions)
        records = {key: value for key, value in aggregate.identities.records.items()
                   if value["slot"][0] in position_set}
        observed, _, audit = linked_evidence(records, services, meta["original_indices"])
        if split_name == "TRAIN":
            require(observed == mapping and audit == train_link_audit,
                    "TRAIN dictionary changed during pass two")
        linkage[split_name] = audit
    checks["conflicting_selected_identities"] = False
    checks["ambiguous_linked_keys"] = False
    aggregation_seconds = time.perf_counter() - aggregation_started
    with (INPUTS / "selected.npz").open("xb") as stream:
        np.savez_compressed(stream, **output)
    output_meta = copy.deepcopy(meta)
    output_meta["strategy"] = STRATEGY
    output_meta["source_selected_sha256"] = expected[str(SAFE / "selected.npz")]
    output_meta["selected_npz_sha256"] = file_hash(INPUTS / "selected.npz")
    output_meta["mapping_sha256"] = frozen_hash
    output_meta["inherited_preparation_provenance"] = {
        key: output_meta.pop(key) for key in ("horizon_only", "access_audit", "access_disclosure")}
    output_meta["hawkes_relative_horizon"] = 10
    output_meta["access_disclosure"] = DISCLOSURE
    output_meta["protected_model_rows_materialized"] = 0
    output_meta["repairs"]["trace"] = (
        "TRAIN-linked destination only; original durations/start-second+28800; "
        "occurrence-weighted arithmetic mean, zero-fill, channel1 zero")
    write_json(INPUTS / "metadata.json", output_meta)
    for key in ("windows", "services", "edges", "train_positions", "validation_positions",
                "original_indices", "split_counts", "window_count", "event_count", "event_num"):
        require(output_meta[key] == meta[key], "Metadata changed: " + key)
    with np.load(str(INPUTS / "selected.npz"), allow_pickle=False) as archive:
        checks.update(exact_arrays(safe, {key: archive[key] for key in archive.files}, owner))
        require(np.array_equal(archive["traces"], candidate), "Candidate roundtrip changed")
    after = {path: file_hash(path) for path in expected}
    require(after == expected, "Input source hashes changed pre/post")
    require(file_hash(INPUTS / "mapping.json") == frozen_hash, "Frozen mapping changed")
    checks.update(source_hashes_pre_post=True, metadata_exact=True, candidate_roundtrip_exact=True)
    pending = {
        "status": "VERIFIED_PENDING_PROCESS_EXIT", "strategy": STRATEGY,
        "protocol_sha256": expected[str(HERE / "PROTOCOL.md")],
        "baseline_sha256": expected[str(HERE / "BASELINE.json")],
        "source_selected_sha256": expected[str(SAFE / "selected.npz")],
        "output_hashes": {name: file_hash(INPUTS / name)
                          for name in ("selected.npz", "metadata.json", "mapping.json")},
        "input_hashes": expected, "input_hashes_after": after, "checks": checks,
        "cost": {"mapping_seconds": mapping_seconds,
                 "aggregation_seconds": aggregation_seconds,
                 "total_seconds": time.perf_counter() - started
                 + (recovery["failed_attempt_seconds"] if recovery else 0),
                 "resumed_producer_seconds": time.perf_counter() - started,
                 "mapping_timing_measurement": recovery["timing_measurement"] if recovery
                 else "monotonic perf_counter; TRAIN-only scan, evidence and mapping freeze"},
        "mapping_key_count": len(mapping), "mapping_coverage": aggregate.report(),
        "linkage_audit": linkage, "code_hashes": code_hashes(),
        "protected_model_rows_materialized": 0, "access_disclosure": DISCLOSURE,
        "shape": list(candidate.shape), "normalized": False,
        "training_executed": False, "inference_executed": False,
        "command": [sys.executable, "-B", str(HERE / "prepare.py"),
                    "--produce-resume" if resume else "--produce"],
        "initial_failure": recovery,
    }
    write_json(INPUTS / "preparation.pending.json", pending)
    print("PREPARATION_PRODUCER_VERIFIED", flush=True)


def fixtures(resume=False):
    prefix = "fixtures.recovery" if resume else "fixtures"
    with (INPUTS / (prefix + ".log")).open("x") as log:
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest",
             "research.sn_call_target_contrast_20261018.test_prepare", "-v"],
            cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    write_json(INPUTS / (prefix + ".json"), {"exit_code": result.returncode,
               "code_hashes": code_hashes(), "log_sha256": file_hash(INPUTS / (prefix + ".log"))})
    require(result.returncode == 0, "Fixture failures; see inputs/fixtures.log")
    print("PREPARATION_FIXTURES_PASS", flush=True)


def execute(resume=False):
    prefix = "fixtures.recovery" if resume else "fixtures"
    attempt = "recovery." if resume else ""
    evidence = read_json(INPUTS / (prefix + ".json"))
    require(evidence["exit_code"] == 0 and evidence["code_hashes"] == code_hashes()
            and evidence["log_sha256"] == file_hash(INPUTS / (prefix + ".log")),
            "Missing current passing fixtures")
    if resume:
        failed_mapping_stage()
    write_json(INPUTS / (attempt + "execution.claim.json"),
               {"code_hashes": code_hashes(), "command": sys.argv,
                "runtime": {"python": sys.version, "executable": sys.executable,
                            "numpy": np.__version__}})
    producer_log = INPUTS / (attempt + "producer.log")
    with producer_log.open("x") as log:
        result = subprocess.run([sys.executable, "-B", str(HERE / "prepare.py"),
                                 "--produce-resume" if resume else "--produce"],
                                cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    write_json(INPUTS / (attempt + "producer.exit.json"), {"exit_code": result.returncode})
    require(result.returncode == 0, "Producer failed; no retry and no PASS")
    pending = read_json(INPUTS / "preparation.pending.json")
    require(pending["status"] == "VERIFIED_PENDING_PROCESS_EXIT", "Missing verified producer")
    require(pending["code_hashes"] == code_hashes(), "Producer code changed")
    for path, expected in pending["input_hashes"].items():
        require(file_hash(path) == expected, "Source changed after producer exit: " + path)
    for name, expected in pending["output_hashes"].items():
        require(file_hash(INPUTS / name) == expected, "Output changed after producer exit: " + name)
    require("PREPARATION_PRODUCER_VERIFIED" in producer_log.read_text(),
            "Missing producer sentinel")
    pending.update(status="PASS", producer_exit_code=result.returncode,
                   producer_log_sha256=file_hash(producer_log),
                   producer_log=str(producer_log),
                   execution_command=[sys.executable, "-B", str(HERE / "prepare.py"),
                                      "--resume-failed" if resume else "--execute"],
                   fixtures=evidence)
    write_json(INPUTS / "preparation.json", pending)
    print("PREPARATION_PASS producer_exit_code=0", flush=True)


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fixtures", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--produce", action="store_true")
    modes.add_argument("--fixtures-recovery", action="store_true")
    modes.add_argument("--resume-failed", action="store_true")
    modes.add_argument("--produce-resume", action="store_true")
    args = parser.parse_args()
    require(sys.version_info[:2] == (3, 8) and np.__version__ == "1.21.5"
            and Path(sys.executable).parent == ROOT / ".venv-eadro/bin",
            "Use existing .venv-eadro Python3.8/NumPy1.21.5 only")
    INPUTS.mkdir(exist_ok=True)
    if args.fixtures or args.fixtures_recovery:
        fixtures(resume=args.fixtures_recovery)
    elif args.execute or args.resume_failed:
        try:
            execute(resume=args.resume_failed)
        except BaseException:
            failure = INPUTS / ("recovery.failure.json" if args.resume_failed
                               else "preparation.failure.json")
            if not failure.exists():
                write_json(failure, {"status": "FAIL", "traceback": traceback.format_exc()})
            raise
    else:
        claim = "recovery.execution.claim.json" if args.produce_resume else "execution.claim.json"
        require((INPUTS / claim).is_file(), "Producer needs guarded supervisor")
        prepare(resume=args.produce_resume)


if __name__ == "__main__":
    main()
