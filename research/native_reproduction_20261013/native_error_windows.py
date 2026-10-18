"""Describe saved validation errors; do not train or access raw/test telemetry."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def labelled_points(window, events):
    """Count integer samples covered by source-rounded fault annotations."""
    return sum(any(event["start"] <= t <= event["end_inclusive"] for event in events)
               for t in range(window["start"], window["end"] + 1))


def audit(system, epochs):
    verification = json.loads((HERE / f"{system.lower()}{epochs}_verification.json").read_text())
    assert verification["status"] == "PASS" and verification["runs_checked"] == 6
    metadata_path = HERE / "native_inputs" / system / "metadata.json"
    expected_hash = verification["common_manifest"]["input_hashes"]["metadata.json"]
    assert hashlib.sha256(metadata_path.read_bytes()).hexdigest() == expected_hash
    metadata = json.loads(metadata_path.read_text())
    events = {event["event_id"]: event for run in metadata["runs"] for event in run["faults"]}
    by_kind = {}
    for kind in ("eadro", "diagmlp"):
        examples, denominators, mistakes = {}, Counter(), Counter()
        wrong_seeds, gated_seeds = defaultdict(list), defaultdict(list)
        reference_indices = None
        for seed in (11, 23, 37):
            directory = HERE / f"calibration{epochs}" / system / kind / f"seed_{seed}"
            split = json.loads((directory / "split.json").read_text())
            with np.load(directory / "validation_predictions.npz", allow_pickle=False) as saved:
                indices, labels = saved["indices"], saved["labels"]
                roots, detection = saved["root_logits"], saved["detection_logits"]
                assert indices.tolist() == split["indices"]["validation"]
                if reference_indices is None:
                    reference_indices = indices.copy()
                np.testing.assert_array_equal(indices, reference_indices)
                assert np.isfinite(roots).all() and np.isfinite(detection).all()
                for row, index in enumerate(indices):
                    truth = int(labels[row])
                    if truth < 0:
                        continue
                    window = metadata["windows"][int(index)]
                    faults = [events[event_id] for event_id in window["event_id"].split(";")]
                    assert all(event["root"] == truth for event in faults)
                    points = labelled_points(window, faults)
                    assert 0 < points <= 10
                    band = "partial_annotation" if points < 10 else "full_annotation"
                    denominators[band] += 1
                    greater = int(np.sum(roots[row] > roots[row, truth]))
                    ties = int(np.sum(roots[row] == roots[row, truth]))
                    unique_correct = greater == 0 and ties == 1
                    detected = int(np.argmax(detection[row])) == 1
                    if not unique_correct:
                        wrong_seeds[int(index)].append(seed)
                        mistakes[band] += 1
                    if not (unique_correct and detected):
                        gated_seeds[int(index)].append(seed)
                    if not unique_correct or not detected:
                        example = examples.setdefault(int(index), {
                            "window_index": int(index), "run_id": window["run_id"],
                            "event_id": window["event_id"], "start": window["start"],
                            "root": metadata["services"][truth],
                            "fault_type": [event["fault_type"] for event in faults],
                            "labelled_integer_points_of_10": points, "seeds": [],
                        })
                        example["seeds"].append({
                            "seed": seed, "root_rank_interval": [greater + 1, greater + ties],
                            "top_services": [metadata["services"][int(i)] for i in
                                             np.flatnonzero(roots[row] == roots[row].max())],
                            "detected": detected, "root_unique_first": unique_correct,
                            "top_minus_root_logit": float(roots[row].max() - roots[row, truth]),
                        })
        by_kind[kind] = {
            "fault_window_seed_evaluations_by_band": dict(denominators),
            "non_unique_correct_root_evaluations_by_band": dict(mistakes),
            "distinct_root_error_windows": len(wrong_seeds),
            "root_error_windows_in_all_three_seeds": sorted(i for i, seeds in wrong_seeds.items()
                                                           if len(seeds) == 3),
            "distinct_gated_error_windows": len(gated_seeds),
            "error_examples": list(examples.values()),
        }
    return {"system": system, "epochs": epochs, "status": "descriptive_audit_complete",
            "scope": "Saved validation predictions and recording metadata only; no raw/test reads.",
            "limitations": [
                "Integer annotation overlap is not measured symptom visibility or physical activation.",
                "Seeds and windows are correlated; this is not a significance test.",
                "Association with an annotation boundary is not proof of an error mechanism.",
                "These Eadro-data errors do not establish persistence of an RCAEval case error.",
                "No model, label, feature, partition or score was changed.",
            ], "models": by_kind}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=("SN", "TT"), required=True)
    parser.add_argument("--epochs", type=int, choices=(50, 200), required=True)
    args = parser.parse_args()
    assert labelled_points({"start": 0, "end": 9}, [{"start": 3, "end_inclusive": 20}]) == 7
    assert labelled_points({"start": 0, "end": 9}, [{"start": 3, "end_inclusive": 4}]) == 2
    assert labelled_points({"start": 0, "end": 9},
                           [{"start": 0, "end_inclusive": 6}, {"start": 4, "end_inclusive": 9}]) == 10
    result = audit(args.system, args.epochs)
    target = HERE / f"{args.system.lower()}{args.epochs}_error_windows.json"
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("ERROR_WINDOW_AUDIT", json.dumps({
        kind: {k: v for k, v in value.items() if k != "error_examples"}
        for kind, value in result["models"].items()
    }), flush=True)
