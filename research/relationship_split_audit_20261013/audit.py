"""Audit all development fold indices without loading observations or fitting models."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.relationship_smoke_20261013 import data

ROW_KEYS = ("indices", "labels", "event_ids", "episode_ids", "fold_ids", "partition")


def canonical_source_hashes(sources):
    result = {}
    for source, digest in sources.items():
        # Python3.8 recorded the preparer's __file__ relative to its working directory.
        path = str((data.HERE / Path(source)).resolve())
        if path in result:
            raise ValueError("Ambiguous source path aliases")
        result[path] = digest
    return result


def inspect_splits(manifest, rows):
    indices, labels = rows["indices"], rows["labels"]
    count = len(indices)
    if any(rows[key].shape != (count,) for key in ROW_KEYS) or len(manifest["windows"]) != count:
        raise ValueError("Row metadata shape mismatch")
    if not np.issubdtype(indices.dtype, np.integer) or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Noninteger indices or labels")
    native = data.base_features.original_split(manifest["native_window_count"])
    if not np.array_equal(indices, np.concatenate((native["train"], native["validation"]))):
        raise ValueError("Permitted original row inventory/order mismatch")

    runs = defaultdict(list)
    for fault in manifest["faults"].values():
        runs[fault["run_id"]].append(fault)
    meta = {
        "window_count": manifest["native_window_count"], "services": manifest["services"],
        "runs": [{"run_id": run, "faults": faults} for run, faults in runs.items()],
        "windows": {int(index): window for index, window in zip(indices, manifest["windows"])},
    }
    for run in runs:
        windows = sorted((w["start"], w["end"]) for w in manifest["windows"] if w["run_id"] == run)
        if any(left[1] >= right[0] for left, right in zip(windows, windows[1:])):
            raise ValueError("Overlapping windows within recording")

    services = manifest["services"]
    types = {fault["fault_type"] for fault in manifest["faults"].values()}
    if len(services) % 3:
        raise ValueError("Type-balanced audit expects a service count divisible by three")
    validation_events, validation_rows, reports = Counter(), Counter(), []
    for fold in range(3):
        split = data.event_partition(meta, indices, labels, fold)
        for key in ("event_ids", "episode_ids", "fold_ids"):
            if not np.array_equal(split[key], rows[key]):
                raise ValueError("Stored invariant row metadata differs: " + key)
        if split["event_folds"] != manifest["event_folds"]:
            raise ValueError("Stored incident folds differ")
        if fold == 0 and (
            not np.array_equal(split["partition"], rows["partition"])
            or split["few_shot"] != manifest["few_shot"]
        ):
            raise ValueError("Existing fold0 metadata differs")
        stats, selected, event_sets, recordings = {}, {}, {}, {}
        for part, per_service in (("train", 2), ("validation", 1)):
            chosen = split["partition"] == part
            selected[part] = indices[chosen].tolist()
            events = set(split["event_ids"][chosen & (labels >= 0)].tolist())
            event_sets[part] = events
            type_counts = Counter(manifest["faults"][event]["fault_type"] for event in events)
            if type_counts != Counter({kind: len(services) * per_service // 3 for kind in types}):
                raise ValueError("Fault type support mismatch")
            recordings[part] = {w["run_id"] for w, keep in zip(manifest["windows"], chosen) if keep}
            stats[part] = {
                "incidents": len(events), "fault_windows": int((chosen & (labels >= 0)).sum()),
                "normal_windows": int((chosen & (labels == -1)).sum()),
                "fault_types": dict(sorted(type_counts.items())),
            }
        if event_sets["train"] & event_sets["validation"]:
            raise ValueError("Incident overlap")
        normal_indices = indices[(split["partition"] == "train") & (labels == -1)].tolist()
        if not normal_indices:
            raise ValueError("No normal TRAIN rows")
        a, b = (set(split["few_shot"][name]["event_ids"]) for name in ("A", "B"))
        if a & b or a | b != event_sets["train"]:
            raise ValueError("Few-shot incidents are not disjoint TRAIN complements")
        for name, events in (("A", a), ("B", b)):
            support = Counter(manifest["faults"][event]["service"] for event in events)
            if support != Counter({service: 1 for service in services}):
                raise ValueError("Few-shot root support mismatch")
            expected = [int(index) for index, event in zip(indices, rows["event_ids"]) if event in events]
            actual = split["few_shot"][name]["original_indices"]
            if expected != actual or not set(actual) <= set(selected["train"]):
                raise ValueError("Few-shot original row membership mismatch")
        validation_events.update(event_sets["validation"])
        validation_rows.update(selected["validation"])
        reports.append({
            "fold": fold, "counts": stats, "original_indices": selected,
            "train_normal_original_indices": normal_indices,
            "few_shot": split["few_shot"],
            "shared_train_validation_recordings": sorted(recordings["train"] & recordings["validation"]),
        })
    if validation_events != Counter({event: 1 for event in manifest["faults"]}):
        raise ValueError("An incident is not validation exactly once")
    if validation_rows != Counter({int(index): 1 for index in indices}):
        raise ValueError("A permitted row is not validation exactly once")
    return {
        "status": "PASS", "permitted_windows": count, "incidents": len(manifest["faults"]),
        "checks": {
            "native_test_unassigned_excluded": True, "incident_episode_disjoint": True,
            "nonoverlapping_windows_within_recording": True, "root_and_fault_type_balance": True,
            "few_shot_fault_complements": True, "validation_exactly_once": True,
        },
        "folds": reports,
    }


def audit_system(system):
    manifest_path = data.OUT / (system + ".json")
    manifest = json.loads(manifest_path.read_text())
    manifest_hash = data.base_features.file_hash(manifest_path)
    archive_path = data.OUT / (system + ".npz")
    data.base_features.require_hash(archive_path, manifest["npz_sha256"])
    sources = canonical_source_hashes(data.source_hashes())
    if sources != canonical_source_hashes(manifest["source_hashes"]):
        raise ValueError("Frozen partition source changed")
    with np.load(archive_path, allow_pickle=False) as archive:
        rows = {key: archive[key] for key in ROW_KEYS}
    result = inspect_splits(manifest, rows)
    data.base_features.require_hash(manifest_path, manifest_hash)
    if canonical_source_hashes(data.source_hashes()) != sources:
        raise ValueError("Partition source changed during audit")
    result["provenance"] = {
        "manifest_path": str(manifest_path), "manifest_sha256": manifest_hash,
        "npz_sha256": manifest["npz_sha256"], "partition_source_hashes": sources,
    }
    print("SPLIT_METADATA_VERIFIED", system,
          [{"fold": f["fold"], "counts": f["counts"],
            "shared_recordings": len(f["shared_train_validation_recordings"])} for f in result["folds"]],
          flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.is_symlink():
        raise FileExistsError("Refusing to overwrite audit report")
    if sys.version_info[:2] != (3, 8) or np.__version__ != "1.21.5":
        raise RuntimeError("Use pinned .venv-eadro Python3.8 / NumPy1.21.5")
    report = {
        "scope": "all-fold split metadata only; no new observations/features/models evaluated",
        "observation_arrays_loaded": False, "model_fitting": False, "test_evaluated": False,
        "rcaeval_access": False, "fold1_2_feature_normalization_validated": False,
        "script_sha256": data.base_features.file_hash(Path(__file__)),
        "systems": {system: audit_system(system) for system in ("SN", "TT")},
        "limitations": [
            "Already used incidents; not pristine final evidence, cold-root, or recording-disjoint.",
            "Row interval nonoverlap does not prove clock correctness or causal online availability.",
            "Do not reuse fold0 normalized x/normal reference/standardizer for folds1/2.",
            "Few-shot A/B are disjoint fault subsets; their allowed normal TRAIN reference pool is shared.",
            "Future few-shot feature standardization must exclude unselected fault rows.",
        ],
    }
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("SPLIT_METADATA_AUDIT_COMPLETE", args.report, flush=True)


if __name__ == "__main__":
    main()
