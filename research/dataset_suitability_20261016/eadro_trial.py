"""Metadata-only Eadro split-role audit over permitted development bundles."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUNDLE_DIR = ROOT / "research/relationship_smoke_20261013/artifacts"
OUTPUT = HERE / "eadro_trial.json"
ROW_KEYS = ("indices", "labels", "event_ids", "episode_ids", "fold_ids", "partition")


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _counter(values):
    return dict(sorted(Counter(values).items()))


def summarize_split(train, heldout, rows, faults, services, fault_types):
    indices, labels, event_ids, episode_ids, _, _ = rows
    fault_for_event = {fault["event_id"]: fault for fault in faults.values()}
    episode_type = {event: fault["fault_type"] for event, fault in fault_for_event.items()}
    roots = set(services)
    result = {}
    sets = {}
    for name, mask in (("train", train), ("heldout", heldout)):
        fault_mask = mask & (labels >= 0)
        normal_mask = mask & (labels == -1)
        events = set(event_ids[fault_mask].tolist())
        roots_here = {fault_for_event[event]["service"] for event in events}
        types_here = [fault_for_event[event]["fault_type"] for event in events]
        normal_episode_types = [episode_type[event] for event in episode_ids[normal_mask].tolist()]
        result[name] = {
            "windows": int(mask.sum()),
            "fault_windows": int(fault_mask.sum()),
            "normal_windows": int(normal_mask.sum()),
            "incidents": len(events),
            "roots": sorted(roots_here),
            "fault_type_incidents": _counter(types_here),
            "root_type_incidents": _counter(
                fault_for_event[event]["service"] + "|" + fault_for_event[event]["fault_type"]
                for event in events
            ),
            "normal_windows_by_assigned_fault_type": _counter(normal_episode_types),
            "missing_normal_fault_types": sorted(set(fault_types) - set(normal_episode_types)),
            "unknown_roots": sorted(roots_here - roots),
            "original_window_indices": [int(index) for index in indices[mask]],
            "incident_members": sorted(events),
        }
        sets[name] = events
    heldout_runs = {fault_for_event[event]["run_id"] for event in sets["heldout"]}
    train_runs = {fault_for_event[event]["run_id"] for event in sets["train"]}
    result["checks"] = {
        "incident_overlap": sorted(sets["train"] & sets["heldout"]),
        "recording_overlap": sorted(train_runs & heldout_runs),
        "all_candidate_roots_known": not result["train"]["unknown_roots"],
    }
    return result


def analyze_system(system, manifest, arrays):
    if tuple(arrays) != ROW_KEYS:
        raise ValueError("Only the six permitted metadata members may be supplied")
    rows = tuple(np.asarray(arrays[key]) for key in ROW_KEYS)
    indices, labels, event_ids, episode_ids, fold_ids, _ = rows
    count = len(indices)
    if any(row.shape != (count,) for row in rows) or len(manifest["windows"]) != count:
        raise ValueError("Metadata row shapes differ")
    if len(set(int(v) for v in indices)) != count:
        raise ValueError("Repeated original window index")
    if not np.isin(labels, [-1] + list(range(len(manifest["services"])))).all():
        raise ValueError("Unexpected label")
    faults = manifest["faults"]
    services = sorted({fault["service"] for fault in faults.values()})
    fault_types = sorted({fault["fault_type"] for fault in faults.values()})
    if len(fault_types) != 3:
        raise ValueError("Expected three fault types")
    known_events = set(faults)
    if set(event_ids[labels >= 0].tolist()) != known_events:
        raise ValueError("Permitted windows and fault inventory differ")
    if not set(episode_ids.tolist()) <= known_events:
        raise ValueError("Episode assignment references unknown fault")
    if any(int(label) != faults[event]["root"] for label, event in zip(labels[labels >= 0], event_ids[labels >= 0])):
        raise ValueError("Fault row label/root mismatch")

    policies = {}
    # The existing fold_ids assign each fault episode, including its normal windows.
    for fold in sorted(set(int(v) for v in fold_ids)):
        held = fold_ids == fold
        policies["event_fold_" + str(fold)] = summarize_split(
            ~held, held, rows, faults, services, fault_types
        )

    run_ids = sorted({window["run_id"] for window in manifest["windows"]})
    unchanged_inventory = sorted(services)
    for run_id in run_ids:
        held = np.asarray([window["run_id"] == run_id for window in manifest["windows"]])
        split = summarize_split(~held, held, rows, faults, services, fault_types)
        split["recording_holdout"] = run_id
        split["removed_root_targets"] = sorted(set(unchanged_inventory) - set(split["train"]["roots"]))
        split["candidate_inventory"] = unchanged_inventory
        split["candidate_inventory_unchanged"] = split["candidate_inventory"] == unchanged_inventory
        policies["recording_" + run_id] = split

    for fault_type in fault_types:
        held = np.asarray([
            episode_type == fault_type
            for episode_type in (faults[event]["fault_type"] for event in episode_ids)
        ], dtype=bool)
        split = summarize_split(~held, held, rows, faults, services, fault_types)
        split["fault_type_holdout"] = fault_type
        policies["fault_type_" + fault_type] = split

    return {
        "system": system,
        "window_count": count,
        "incident_count": len(faults),
        "candidate_roots": unchanged_inventory,
        "fault_types": fault_types,
        "recordings": run_ids,
        "policies": policies,
    }


def load_system(system):
    manifest_path = BUNDLE_DIR / (system + ".json")
    archive_path = BUNDLE_DIR / (system + ".npz")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["system"] != system:
        raise ValueError("Bundle system mismatch")
    with np.load(archive_path, allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in ROW_KEYS}
    return manifest, arrays, {
        str(manifest_path.relative_to(ROOT)): file_sha256(manifest_path),
        str(archive_path.relative_to(ROOT)): file_sha256(archive_path),
    }


def run_trial():
    started = time.perf_counter()
    systems = {}
    input_hashes = {}
    audit_path = ROOT / "research/relationship_split_audit_20261013/fold_metadata_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if any(audit.get("systems", {}).get(system, {}).get("status") != "PASS"
           for system in ("SN", "TT")):
        raise ValueError("Existing split metadata audit is not PASS")
    for system in ("SN", "TT"):
        manifest, arrays, hashes = load_system(system)
        input_hashes.update(hashes)
        result = analyze_system(system, manifest, arrays)
        prior = audit["systems"][system]
        if result["incident_count"] != prior["incidents"] or result["window_count"] != prior["permitted_windows"]:
            raise ValueError("Existing audit counts do not match bundle metadata")
        event_folds = [result["policies"]["event_fold_" + str(fold)] for fold in (0, 1, 2)]
        for fold, split in enumerate(event_folds):
            old = prior["folds"][fold]["counts"]
            for part in ("train", "validation"):
                current = split["train" if part == "train" else "heldout"]
                if (current["fault_windows"] != old[part]["fault_windows"]
                        or current["normal_windows"] != old[part]["normal_windows"]
                        or current["incidents"] != old[part]["incidents"]):
                    raise ValueError("Event-fold counts differ from frozen audit")
        systems[system] = result
    input_hashes[str(audit_path.relative_to(ROOT))] = file_sha256(audit_path)
    result = {
        "status": "PASS",
        "scope": "permitted development bundle metadata only; no features, observations, fits, checkpoints, inference, or protected evaluation",
        "metadata_members_loaded": list(ROW_KEYS),
        "input_sha256": dict(sorted(input_hashes.items())),
        "source_sha256": {str(Path(__file__).resolve().relative_to(ROOT)): file_sha256(__file__)},
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "elapsed_seconds": time.perf_counter() - started,
            "max_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        },
        "systems": systems,
        "interpretation": [
            "No split is adopted as a final evaluation protocol.",
            "Event folds keep roots known but share recordings.",
            "Recording holdout removes three root targets per held recording while retaining the full candidate inventory.",
            "Fault-type holdout retains root coverage; normal windows follow their assigned fault episode type.",
            "Small incident counts alone do not establish that an MLP is untrainable.",
            "Previously used development incidents are not pristine final observations.",
            "Additional normal archives add no labelled fault incidents.",
            "The earlier CPU-easy/network-hard claim was from a five-epoch probe only; later native-like TT DiagMLP results report network Top1 near 91%, so no broad weakness claim follows.",
        ],
    }
    if OUTPUT.exists() or OUTPUT.is_symlink():
        raise FileExistsError("Refusing to overwrite Eadro result JSON")
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main():
    if sys.version_info[:2] != (3, 10) or np.__version__ != "1.26.4":
        raise RuntimeError("Use the existing .venv-mlp Python 3.10 / NumPy 1.26.4")
    result = run_trial()
    for system, data in result["systems"].items():
        print("EADRO_METADATA_SPLITS", system, data["incident_count"], len(data["recordings"]), flush=True)
    print("EADRO_SUITABILITY_PASS", flush=True)


if __name__ == "__main__":
    main()
