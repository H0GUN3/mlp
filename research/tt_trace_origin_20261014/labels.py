"""One-recording metadata gate; no model or original telemetry access."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.relationship_diagnosis_20261014 import errors

RUN = "TT.2022-04-17T212101D2022-04-17T230842"
RAW = HERE.parents[1] / "data/eadro_native/TT_Dataset/TT Dataset"
RECORD = "data/TT.fault-2022-04-17T212101D2022-04-17T230842.json"
EVENTS = [RUN + ":fault" + name for name in ("01", "02", "04")]


def load_bundle(members):
    inputs = errors.Inputs()
    runs = inputs.json(errors.CV / "runs.json", errors.SNAPSHOT_HASHES["runs.json"], "frozen CV")
    manifest_path = errors.BUNDLES / "TT.json"
    manifest = inputs.json(manifest_path, runs["input_hashes"][str(manifest_path)], "CV input")
    bundle_path = errors.BUNDLES / "TT.npz"
    errors.require(manifest["npz_sha256"] == runs["input_hashes"][str(bundle_path)],
                   "Bundle binding mismatch")
    bundle = inputs.npz(bundle_path, manifest["npz_sha256"], "permitted development bundle", members)
    return inputs, manifest, bundle


def rounded_faults(record, services):
    faults = []
    for index, fault in enumerate(record["faults"]):
        parts = fault["name"].split("_")
        errors.require(len(parts) == 3 and parts[0] == "dockercomposemanifests"
                       and parts[1] in services, "Ambiguous root mapping")
        start, duration = fault["start"], fault["duration"]
        errors.require(np.isfinite(start) and np.isfinite(duration) and duration > 0,
                       "Invalid fault interval")
        faults.append({
            "event_id": RUN + ":fault{:02d}".format(index), "service": parts[1],
            "root": services.index(parts[1]), "fault_type": fault["fault"],
            "start": int(start) + 57600, "end_inclusive": int(start + duration) + 57600,
            "raw_start_shifted": start + 57600,
            "raw_end_shifted_exclusive": start + duration + 57600,
        })
    return faults


def hits(start, faults, fractional=False):
    if fractional:
        return [f for f in faults if f["raw_start_shifted"] < start + 10
                and f["raw_end_shifted_exclusive"] > start]
    return [f for f in faults if f["start"] < start + 10 and f["end_inclusive"] >= start]


def execute():
    inputs, manifest, bundle = load_bundle(("indices", "labels", "event_ids"))
    errors.require(sorted(manifest["trace_graph_audit"])[0] == RUN, "Recording selection changed")
    record = inputs.json(RAW / RECORD, manifest["raw_input_hashes"][RECORD], "existing raw metadata pin")
    faults = rounded_faults(record, manifest["services"])
    start, end = int(record["start"]) + 57600, int(record["end"]) + 57600
    stamps = RUN[3:]
    filename_endpoints = [int(datetime.strptime(t, "%Y-%m-%dT%H%M%S")
                             .replace(tzinfo=timezone.utc).timestamp()) for t in stamps.split("D")]
    errors.require(filename_endpoints == [start, end], "Recording/filename endpoints differ")
    errors.require(len(faults) == 9, "Unexpected recording fault count")
    for fault in faults:
        saved = manifest["faults"][fault["event_id"]]
        errors.require(saved["run_id"] == RUN and all(saved[k] == fault[k] for k in
                       ("service", "root", "fault_type", "start", "end_inclusive")),
                       "Raw annotation/manifest mismatch")
    selected_rows = [i for i, w in enumerate(manifest["windows"]) if w["run_id"] == RUN]
    results = []
    differences = []
    for row in selected_rows:
        window = manifest["windows"][row]
        wstart = window["start"]
        errors.require(window["end"] == wstart + 9 and start <= wstart
                       and wstart + 10 <= end and (wstart - start) % 10 == 0, "Invalid window grid")
        nominal = hits(wstart, faults)
        errors.require(len(nominal) <= 1, "Overlapping fault identity")
        expected_label = nominal[0]["root"] if nominal else -1
        expected_event = nominal[0]["event_id"] if nominal else ""
        errors.require(int(bundle["labels"][row]) == expected_label
                       and str(bundle["event_ids"][row]) == expected_event
                       and (window["event_id"] or "") == expected_event,
                       "Allowed window label mismatch")
        continuous = hits(wstart, faults, fractional=True)
        if [f["event_id"] for f in nominal] != [f["event_id"] for f in continuous]:
            differences.append(int(bundle["indices"][row]))
        if expected_event in EVENTS:
            fault = nominal[0]
            overlap = max(0., min(wstart + 10, fault["raw_end_shifted_exclusive"])
                          - max(wstart, fault["raw_start_shifted"]))
            results.append({"bundle_row": row, "original_index": int(bundle["indices"][row]),
                            "event_id": expected_event, "start": wstart, "end_exclusive": wstart + 10,
                            "root": expected_label, "fault_overlap_seconds": overlap,
                            "fully_inside_fault": overlap == 10.})
    errors.require(not differences, "Integer rounding changes an allowed window label")
    errors.require(set(r["event_id"] for r in results) == set(EVENTS), "Missing selected event")
    inputs.recheck()
    return {
        "status": "PASS", "run": RUN, "recording_start": start, "recording_end": end,
        "faults": faults, "metadata_faults_checked": len(faults),
        "development_windows_checked": len(selected_rows),
        "integer_vs_fractional_label_differences": differences,
        "selected_events": EVENTS, "selected_windows": results,
        "selected_summary": {
            event: {"windows": sum(r["event_id"] == event for r in results),
                    "fully_inside": sum(r["event_id"] == event and r["fully_inside_fault"] for r in results)}
            for event in EVENTS},
        "input_hashes": inputs.provenance,
        "source_hashes": {name: errors.file_hash(HERE / name)
                          for name in ("labels.py", "test_labels.py", "PROTOCOL.md")},
        "limits": "Nominal injection metadata agreement only; physical activation/clock synchronization not established.",
    }


if __name__ == "__main__":
    result = execute()
    with (HERE / "metadata.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("METADATA_PASS", result["metadata_faults_checked"],
          result["development_windows_checked"], result["selected_summary"], flush=True)
