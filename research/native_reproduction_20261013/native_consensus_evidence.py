"""Inspect native TT consensus errors, using only validation/train window indices."""
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(metrics, traces, logs, names):
    assert metrics.ndim == 3 and traces.shape[:2] == metrics.shape[:2]
    return {
        "metric_means_source_units": dict(zip(names, metrics.mean(axis=(0, 1)).tolist())),
        "metric_mean_first_to_last_delta": dict(zip(
            names, (metrics[:, -1] - metrics[:, 0]).mean(axis=0).tolist())),
        "zero_filled_trace_mean_seconds": float(traces[..., 0].mean()),
        "positive_trace_samples": int(np.count_nonzero(traces[..., 0] > 0)),
        "trace_samples": int(traces[..., 0].size),
        "windows_with_nonzero_hawkes_vector": int(np.count_nonzero(np.any(logs != 0, axis=1))),
        "hawkes_min_max": [float(logs.min()), float(logs.max())],
    }


def main():
    fixture = describe(np.arange(12).reshape(2, 3, 2), np.zeros((2, 3, 2)),
                       np.zeros((2, 4)), ["a", "b"])
    assert fixture["metric_means_source_units"] == {"a": 5.0, "b": 6.0}
    assert fixture["metric_mean_first_to_last_delta"] == {"a": 4.0, "b": 4.0}
    assert fixture["positive_trace_samples"] == fixture["windows_with_nonzero_hawkes_vector"] == 0
    verification = json.loads((HERE / "tt200_verification.json").read_text())
    assert verification["status"] == "PASS" and not verification["failures"]
    directory = HERE / "native_inputs/TT"
    for name, expected in verification["common_manifest"]["input_hashes"].items():
        assert digest(directory / name) == expected
    meta = json.loads((directory / "metadata.json").read_text())
    audit = json.loads((HERE / "tt200_error_windows.json").read_text())["models"]["diagmlp"]
    consensus = set(audit["root_error_windows_in_all_three_seeds"])
    splits = [json.loads((HERE / f"calibration200/TT/diagmlp/seed_{s}/split.json").read_text())
              for s in (11, 23, 37)]
    assert all(consensus <= set(s["indices"]["validation"]) for s in splits)
    train = set(splits[0]["indices"]["train"])
    assert not train & consensus
    faults = {f["event_id"]: f for run in meta["runs"] for f in run["faults"]}
    edges = {tuple(edge) for edge in meta["edges"]}
    results = []
    with np.load(directory / "raw.npz", allow_pickle=False) as archive:
        arrays = {key: archive[key] for key in ("metrics", "traces", "logs")}
    for example in audit["error_examples"]:
        index = example["window_index"]
        if index not in consensus:
            continue
        window = meta["windows"][index]
        fault = faults[window["event_id"]]
        wrong_names = {name for s in example["seeds"] for name in s["top_services"]}
        assert len(wrong_names) == 1 and len(example["seeds"]) == 3
        wrong = next(iter(wrong_names))
        root_id, wrong_id = meta["services"].index(example["root"]), meta["services"].index(wrong)
        # A fixed preceding120s reference from TRAIN only; never pick by signal strength.
        normal = sorted(i for i in train if meta["windows"][i]["run_id"] == window["run_id"]
                        and meta["windows"][i]["event_id"] is None
                        and fault["start"] - 120 <= meta["windows"][i]["start"]
                        and meta["windows"][i]["end"] < fault["start"])
        row = {"window_index": index, "event_id": window["event_id"],
               "root": example["root"], "predicted": wrong,
               "predicted_calls_root_in_author_graph": (wrong_id, root_id) in edges,
               "preceding_normal_train_indices": normal, "services": {}}
        for name, node in ((example["root"], root_id), (wrong, wrong_id)):
            values = {"fault_window": describe(
                arrays["metrics"][[index], node], arrays["traces"][[index], node],
                arrays["logs"][[index], node], meta["metrics"])}
            if normal:
                values["preceding_normal_train"] = describe(
                    arrays["metrics"][normal, node], arrays["traces"][normal, node],
                    arrays["logs"][normal, node], meta["metrics"])
            row["services"][name] = values
        results.append(row)
    assert {r["window_index"] for r in results} == consensus
    report = {"scope": "Native processed inputs at consensus validation errors and fixed preceding TRAIN normal windows.",
              "no_rcaeval_raw_access": True, "test_indices_selected": [],
              "notes": [
                  "Zero-filled trace values do not by themselves prove absent spans versus observed zero duration.",
                  "Hawkes vectors include dummy-bin effects; their sum is not an observed log count.",
                  "Metric values/deltas remain in source units, not asserted rates or causal effects.",
                  "Dependency and signal associations do not prove why the model made its decision.",
              ], "results": results}
    (HERE / "tt200_consensus_evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    print("CONSENSUS_EVIDENCE", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
