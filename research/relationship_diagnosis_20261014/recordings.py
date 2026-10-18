"""Metadata-only recording-disjoint feasibility and performance audit."""
from __future__ import annotations

import hashlib
import json
from math import fsum, isfinite
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CV = ROOT / "research" / "relationship_cv_20261014" / "results"
SMOKE = ROOT / "research" / "relationship_smoke_20261013" / "artifacts"
SYSTEMS = ("SN", "TT")
MODES = ("local", "global", "directed")
METRICS = ("top1", "top3", "mrr")
METADATA_MEMBERS = ("indices", "labels", "event_ids", "episode_ids", "fold_ids")


def _mean(rows):
    rows = list(rows)
    return {metric: fsum(row[metric] for row in rows) / len(rows) for metric in METRICS}


def _check_metrics(metrics):
    if not isinstance(metrics, dict) or any(
        type(metrics.get(name)) not in (int, float)
        or not isfinite(metrics[name]) or not 0 <= metrics[name] <= 1
        for name in METRICS
    ):
        raise ValueError("Invalid incident ranking metrics")


def _validate_system(system, faults, manifest, arrays, performance):
    services = manifest.get("services")
    windows = manifest.get("windows")
    if not isinstance(services, list) or not services or len(set(services)) != len(services):
        raise ValueError("Invalid service inventory")
    candidate_inventory = set(services)
    if not isinstance(windows, list) or not isinstance(faults, dict) or not faults:
        raise ValueError("Missing manifest windows or fault metadata")
    for key in METADATA_MEMBERS:
        if key not in arrays:
            raise ValueError("Missing permitted metadata member: " + key)
    indices, labels, event_ids, episode_ids, fold_ids = (
        arrays[k] for k in METADATA_MEMBERS
    )
    n = len(indices)
    if any(len(value) != n for value in (labels, event_ids, episode_ids, fold_ids, windows)):
        raise ValueError("Window metadata lengths differ")
    if len(set(int(value) for value in indices)) != n:
        raise ValueError("Repeated original index")
    native_count = manifest.get("native_window_count")
    if type(native_count) is not int or any(not 0 <= int(value) < native_count for value in indices):
        raise ValueError("Original index outside permitted development population")

    recordings, root_services = {}, {}
    for event, fault in faults.items():
        if (not isinstance(fault, dict) or fault.get("event_id") != event
                or not isinstance(fault.get("run_id"), str)
                or fault.get("service") not in services
                or type(fault.get("root")) is not int
                or not 0 <= fault["root"] < len(services)
                or services[fault["root"]] != fault["service"]
                or not isinstance(fault.get("fault_type"), str)):
            raise ValueError("Unsupported fault metadata: " + str(event))
        recordings[event] = fault["run_id"]
        root_services.setdefault(fault["run_id"], set()).add(fault["service"])

    row_recordings, row_events, row_parts = [], [], []
    for i, (original_index, label, event_id, episode_id, fold_id, window) in enumerate(
        zip(indices, labels, event_ids, episode_ids, fold_ids, windows)
    ):
        if not isinstance(window, dict):
            raise ValueError("Manifest windows do not match metadata ordering")
        run_id = window.get("run_id")
        event = window.get("event_id") or ""
        if run_id not in root_services:
            raise ValueError("Window recording has no fault events")
        if int(fold_id) not in (0, 1, 2):
            raise ValueError("Unsupported fold metadata")
        if int(label) == -1:
            if event or not isinstance(episode_id.item() if hasattr(episode_id, "item") else episode_id, (str,)):
                raise ValueError("Invalid normal-window metadata")
            row_events.append("")
            row_parts.append("normal")
        elif int(label) >= 0:
            if (event not in faults or episode_id != event or event_id != event
                    or faults[event]["run_id"] != run_id
                    or faults[event]["root"] != int(label)):
                raise ValueError("Fault-window event/root/recording mismatch")
            row_events.append(event)
            row_parts.append("fault")
        else:
            raise ValueError("Unsupported label metadata")
        row_recordings.append(run_id)
    metadata_events = {event for event in row_events if event}
    if metadata_events != set(faults):
        raise ValueError("Metadata event coverage differs from fault manifest")
    if set(recordings.values()) != set(row_recordings):
        raise ValueError("Recording metadata coverage mismatch")

    # Verify the saved nine-incident, three-root x three-type structure.
    by_recording = {}
    for event, run_id in recordings.items():
        by_recording.setdefault(run_id, []).append(event)
    if any(len(events) != 9 for events in by_recording.values()):
        raise ValueError("Expected exactly nine fault events per recording")
    root_owner = {}
    for run_id, events in by_recording.items():
        roots = {faults[event]["service"] for event in events}
        types = {faults[event]["fault_type"] for event in events}
        pairs = {(faults[event]["service"], faults[event]["fault_type"]) for event in events}
        if len(roots) != 3 or len(types) != 3 or len(pairs) != 9:
            raise ValueError("Recording root/type membership mismatch")
        for root in roots:
            root_owner.setdefault(root, set()).add(run_id)

    if set(performance) != set(faults):
        raise ValueError("Performance event set differs from manifest")
    for event, modes in performance.items():
        if set(modes) != set(MODES):
            raise ValueError("Performance mode coverage mismatch")
        for score in modes.values():
            _check_metrics(score)

    recordings_out = {}
    for run_id, events in sorted(by_recording.items()):
        event_rows = {mode: [performance[event][mode] for event in events] for mode in MODES}
        summaries = {mode: _mean(rows) for mode, rows in event_rows.items()}
        summaries["directed_minus_global"] = {
            metric: summaries["directed"][metric] - summaries["global"][metric]
            for metric in METRICS
        }
        recordings_out[run_id] = {
            "incident_count": len(events),
            "root_services": sorted({faults[e]["service"] for e in events}),
            "fault_types": sorted({faults[e]["fault_type"] for e in events}),
            "root_type_support": {
                service: {
                    kind: sum(faults[e]["service"] == service and faults[e]["fault_type"] == kind
                              for e in events)
                    for kind in sorted({faults[e]["fault_type"] for e in events})
                } for service in sorted({faults[e]["service"] for e in events})
            },
            "metrics_event_equal": summaries,
        }

    holdouts = {}
    all_recordings = sorted(by_recording)
    for heldout in all_recordings:
        train_events = [e for e in faults if recordings[e] != heldout]
        test_events = [e for e in faults if recordings[e] == heldout]
        train_roots = sorted({faults[e]["service"] for e in train_events})
        train_types = sorted({faults[e]["fault_type"] for e in train_events})
        train_normals = sum(
            part == "normal" and rid != heldout
            for part, rid in zip(row_parts, row_recordings)
        )
        holdout_normals = sum(
            part == "normal" and rid == heldout
            for part, rid in zip(row_parts, row_recordings)
        )
        train_rows = [int(indices[i]) for i, rid in enumerate(row_recordings) if rid != heldout]
        heldout_rows = [int(indices[i]) for i, rid in enumerate(row_recordings) if rid == heldout]
        if set(train_rows) & set(heldout_rows):
            raise ValueError("Recording window partition overlaps")
        holdouts[heldout] = {
            "train": {
                "incident_count": len(train_events),
                "root_services": train_roots,
                "root_support_by_service": {
                    service: sum(faults[e]["service"] == service for e in train_events)
                    for service in train_roots
                },
                "fault_types": train_types,
                "fault_type_support": {kind: sum(faults[e]["fault_type"] == kind for e in train_events)
                                       for kind in train_types},
                "normal_window_count": train_normals,
                "window_count": len(train_rows),
            },
            "heldout": {
                "incident_count": len(test_events),
                "root_services": sorted({faults[e]["service"] for e in test_events}),
                "fault_types": sorted({faults[e]["fault_type"] for e in test_events}),
                "normal_window_count": holdout_normals,
                "window_count": len(heldout_rows),
            },
            "original_row_indices": {
                "train": train_rows, "heldout": heldout_rows, "disjoint": True,
                "basis": "Saved development-bundle indices only; no protected rows loaded.",
            },
            "cold_root_services_absent_from_train_targets": sorted(
                {faults[e]["service"] for e in test_events} - set(train_roots)
            ),
            "services_absent_from_candidate_inventory": sorted(
                candidate_inventory - candidate_inventory
            ),
            "cold_root_condition": (
                "Each cold root service has all three fault types co-located in the heldout recording."
                if {faults[e]["service"] for e in test_events} - set(train_roots) else None
            ),
        }
    return {
        "service_inventory": services,
        "recordings": recordings_out,
        "leave_one_recording_out": holdouts,
        "root_service_recording_ownership": {
            service: sorted(owners) for service, owners in sorted(root_owner.items())
        },
        "all_root_services_recording_unique": all(len(owners) == 1 for owners in root_owner.values()),
        "window_count": n,
        "fault_window_count": sum(part == "fault" for part in row_parts),
        "normal_window_count": sum(part == "normal" for part in row_parts),
    }


def audit(reports, faults_by_system, manifests, arrays_by_system, performance_by_system):
    if set(faults_by_system) != set(SYSTEMS) or set(manifests) != set(SYSTEMS):
        raise ValueError("Expected SN and TT metadata")
    systems = {}
    for system in SYSTEMS:
        systems[system] = _validate_system(
            system, faults_by_system[system], manifests[system],
            arrays_by_system[system], performance_by_system[system],
        )
    return {
        "systems": systems,
        "interpretation": (
            "Per-recording scores are event-equal means of seed-averaged incident metrics; "
            "events, not seeds, are counted. Recording differences are descriptive, not causal. "
            "Holding out a recording removes its root from TRAIN targets where roots are recording-unique, "
            "creating a cold-root condition with all three fault types co-located. This cannot isolate "
            "environment leakage from root-supervision shift; services absent from TRAIN targets may "
            "still exist in the candidate inventory."
        ),
        "scope": "Metadata and saved incident metrics only; no training, inference, or protected observations.",
    }


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runs_path, analysis_path = CV / "runs.json", CV / "analysis.json"
    runs_bytes, analysis_bytes = runs_path.read_bytes(), analysis_path.read_bytes()
    runs, analysis = json.loads(runs_bytes), json.loads(analysis_bytes)
    if hashlib.sha256(runs_bytes).hexdigest() != analysis.get("input_hashes", {}).get("runs.json"):
        raise ValueError("Analysis input runs hash mismatch")
    if runs.get("status") != "PASS" or runs.get("run_count") != 54:
        raise ValueError("CV runs result is not a complete passing result")
    input_hashes = dict(runs["input_hashes"])
    for filename, digest in input_hashes.items():
        if _sha(Path(filename)) != digest:
            raise ValueError("CV input hash mismatch: " + filename)
    systems_faults, manifests, arrays, performance = {}, {}, {}, {}
    for system in SYSTEMS:
        systems_faults[system] = runs["systems"][system]["faults"]
        manifests[system] = json.loads((SMOKE / (system + ".json")).read_text())
        npz_path = SMOKE / (system + ".npz")
        with np.load(str(npz_path), allow_pickle=False) as archive:
            arrays[system] = {key: archive[key] for key in METADATA_MEMBERS}
        performance[system] = {
            event: {mode: analysis["summary"]["systems"][system]["modes"][mode]["by_incident"][event]
                    for mode in MODES}
            for event in systems_faults[system]
        }
    result = audit(runs["reports"], systems_faults, manifests, arrays, performance)
    provenance = {
        "runs.json": hashlib.sha256(runs_bytes).hexdigest(),
        "analysis.json": hashlib.sha256(analysis_bytes).hexdigest(),
        "development_bundle_json": {
            system: _sha(SMOKE / (system + ".json")) for system in SYSTEMS
        },
        "development_bundle_npz": {
            system: _sha(SMOKE / (system + ".npz")) for system in SYSTEMS
        },
        "statistics_npz": {
            system: {
                str(fold): _sha(CV / system / ("fold_" + str(fold)) / "statistics.npz")
                for fold in range(3)
            } for system in SYSTEMS
        },
        "cv_input_hashes": input_hashes,
    }
    output = {"status": "PASS", "provenance": provenance, "summary": result}
    output_path = HERE / "recordings.json"
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print("DIAG_RECORDINGS_COMPLETE")


if __name__ == "__main__":
    main()
