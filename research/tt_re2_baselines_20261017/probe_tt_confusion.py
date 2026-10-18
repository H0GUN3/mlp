"""Check a single descriptive hypothesis for observed travel/food confusions."""
import json
from pathlib import Path

import numpy as np

import tt_runner as run


def main():
    assert __debug__
    proof = json.loads((run.HERE / "TT_RESULTS.json").read_text())
    assert proof["status"] == "PASS" and proof["sources"] == run.sources()
    arrays, meta, parts = run.load_selected()
    positions = parts["validation"]
    pair = {meta["services"].index("ts-travel-service"), meta["services"].index("ts-food-service")}
    assert len(pair) == 2
    with np.load(run.INPUT / "TT.npz", allow_pickle=False) as saved:
        counts = saved["unique_count"]
    assert counts.shape == (4069, 27) and np.all(counts >= 0)
    records = []
    for seed in run.SEEDS:
        folder = run.HERE / "tt_runs/diagmlp" / ("seed_" + str(seed))
        summary = json.loads((folder / "summary.json").read_text())
        path = folder / "best_validation.npz"
        assert run.digest(path) == summary["hashes"][path.name]
        with np.load(path, allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved["indices"], arrays["indices"][positions])
            labels, logits = saved["labels"], saved["root_logits"]
        for i, root in enumerate(labels):
            if root not in pair:
                continue
            top = np.flatnonzero(logits[i] == logits[i].max())
            if len(top) != 1 or top[0] == root or top[0] not in pair:
                continue
            other, pos = int(top[0]), int(positions[i])
            event = str(arrays["event_ids"][pos])
            fault = meta["faults"][event]
            window = meta["windows"][pos]
            records.append({
                "seed": seed, "original_index": int(arrays["indices"][pos]),
                "event_id": event, "fault_type": fault["fault_type"],
                "root": meta["services"][root], "predicted": meta["services"][other],
                "root_count": int(counts[pos, root]), "predicted_count": int(counts[pos, other]),
                "root_trace_nonzero_bins": int((arrays["traces"][pos, root, :, 0] != 0).sum()),
                "predicted_trace_nonzero_bins": int((arrays["traces"][pos, other, :, 0] != 0).sum()),
                "equal_metric_vectors": bool(np.array_equal(arrays["metrics"][pos, root],
                                                           arrays["metrics"][pos, other])),
                "equal_log_vectors": bool(np.array_equal(arrays["logs"][pos, root],
                                                        arrays["logs"][pos, other])),
                "window_start": window["start"], "window_end": window["end"],
                "fault_start": fault["start"], "fault_end_inclusive": fault["end_inclusive"],
            })
    assert records
    unique = {row["original_index"]: row for row in records}
    counts_differ = sum(r["root_count"] != r["predicted_count"] for r in unique.values())
    result = {
        "status": "PASS", "hypothesis": "Candidate-local invocation counts distinguish travel/food confusion",
        "scope": "Only the observed DiagMLP travel/food validation confusions; no causal claim",
        "seed_window_errors": len(records), "unique_windows": len(unique),
        "windows_with_different_candidate_counts": counts_differ,
        "windows_both_counts_zero": sum(r["root_count"] == r["predicted_count"] == 0 for r in unique.values()),
        "records": records, "model_changed": False, "hypothesis_tested_by_training": False,
        "protected_observations_opened": False, "source_sha256": run.digest(Path(__file__)),
        "evaluation_sha256": run.digest(run.HERE / "TT_RESULTS.json"),
    }
    run.dump(run.HERE / "TT_CONFUSION_PROBE.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    print("TT_CONFUSION_PROBE_PASS", flush=True)


if __name__ == "__main__":
    main()
