"""Independent saved-logit scoring and gate verification; no torch/model execution."""
from collections import defaultdict
import hashlib
import json
from math import fsum, isclose
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
METRICS = ("top1", "top3", "mrr")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def credit(scores, root):
    target = scores[root]
    higher = int(np.count_nonzero(scores > target))
    ties = int(np.count_nonzero(scores == target))
    ranks = list(range(higher + 1, higher + ties + 1))
    return {"top1": sum(r == 1 for r in ranks) / ties,
            "top3": sum(r <= 3 for r in ranks) / ties,
            "mrr": fsum(1. / r for r in ranks) / ties}


def mean(values):
    return {m: fsum(v[m] for v in values) / len(values) for m in METRICS} if values else None


def compare(left, right):
    if left is None or right is None:
        assert left is right
    else:
        assert all(isclose(left[m], right[m], abs_tol=1e-12, rel_tol=0) for m in METRICS)


def main():
    compare(credit(np.array([2., 2., 0.]), 0), {"top1": .5, "top3": 1., "mrr": .75})
    compare(credit(np.array([3., 2., 2.]), 1),
            {"top1": 0., "top3": 1., "mrr": (1 / 2 + 1 / 3) / 2})
    runs = json.loads((HERE / "baseline_runs.json").read_text())
    analysis = json.loads((HERE / "baseline_analysis.json").read_text())
    gate = json.loads((HERE / "gate.json").read_text())
    metadata = json.loads((HERE / "artifacts/TT.json").read_text())
    assert runs["status"] == analysis["status"] == "PASS" and len(runs["runs"]) == 18
    for path, expected in analysis["input_hashes"].items():
        assert digest(path) == expected, path
    for name, expected in analysis["source_hashes"].items():
        assert digest(HERE / name) == expected, name
    with np.load(HERE / "artifacts/TT.npz", allow_pickle=False) as saved:
        indices, counts = saved["indices"], saved["unique_count"]
        labels, event_ids, folds = saved["labels"], saved["event_ids"], saved["fold_ids"]
    assert len(indices) == len(set(indices)) == 4069 and len(metadata["faults"]) == 81
    rows_by_index = {int(index): row for row, index in enumerate(indices)}
    evaluations = defaultdict(list)
    prediction_files, scored_fault_windows = 0, 0
    for run in runs["runs"]:
        for split in ("train", "validation"):
            path = Path(run["folder"]) / (split + "_predictions.npz")
            with np.load(path, allow_pickle=False) as pred:
                local = {key: pred[key] for key in pred.files}
            expected = folds != run["fold"] if split == "train" else folds == run["fold"]
            assert np.array_equal(local["indices"], indices[expected])
            assert np.array_equal(local["labels"], labels[expected])
            assert np.array_equal(local["event_ids"], event_ids[expected])
            assert np.isfinite(local["root_logits"]).all()
            records = defaultdict(list)
            for i, root in enumerate(local["labels"]):
                if root < 0:
                    continue
                event = str(local["event_ids"][i])
                row = rows_by_index[int(local["indices"][i])]
                scores = credit(local["root_logits"][i], int(root))
                records[event].append((scores, bool(counts[row, root] > 0)))
                scored_fault_windows += 1
            assert len(records) == (54 if split == "train" else 27)
            for event, values in records.items():
                for part in ("all", "zero", "positive"):
                    selected = [s for s, has_count in values if part == "all" or has_count == (part == "positive")]
                    evaluations[run["kind"], split, event, part].append(
                        (run["fold"], run["seed"], len(selected), mean(selected)))
            prediction_files += 1
    event_checks = 0
    collapsed = {}
    for key, values in evaluations.items():
        kind, split, event, part = key
        assert len(values) == (6 if split == "train" else 3)
        assert len({(v[0], v[1]) for v in values}) == len(values)
        assert len({v[2] for v in values}) == 1
        actual = mean([v[3] for v in values if v[3] is not None])
        compare(actual, analysis["events"][kind][split][event][part]["metrics"])
        collapsed[key] = actual
        event_checks += 1
    summary_checks = 0
    for kind in ("eadro", "diagmlp"):
        for split in ("train", "validation"):
            for group in ("all", "network", "cpu_load", "network_delay", "network_loss"):
                selected = [collapsed[kind, split, event, "all"] for event, fault in metadata["faults"].items()
                            if group == "all" or (group == "network" and fault["fault_type"].startswith("network"))
                            or fault["fault_type"] == group]
                actual = mean(selected)
                summary = analysis["summaries"][kind][split]
                expected = summary[group]["metrics"] if group in ("all", "network") else summary["fault_type"][group]["metrics"]
                compare(actual, expected)
                summary_checks += 1
    deltas = {}
    for seed in (11, 23, 37):
        grouped = {}
        for part in ("zero", "positive"):
            event_scores = []
            for event, fault in metadata["faults"].items():
                if not fault["fault_type"].startswith("network"):
                    continue
                values = evaluations["diagmlp", "validation", event, part]
                event_scores.extend(v[3] for v in values if v[1] == seed and v[3] is not None)
            grouped[part] = mean(event_scores)
        assert grouped["positive"] is not None and grouped["zero"] is not None
        deltas[str(seed)] = grouped["positive"]["top1"] - grouped["zero"]["top1"]
        assert isclose(deltas[str(seed)], gate["per_seed_support_delta"][str(seed)], abs_tol=1e-12)
    assert sum(v >= .05 for v in deltas.values()) == 0
    assert gate["allow_next_stage"] is False
    assert digest(HERE / "PROTOCOL.md") == gate["protocol_sha256"]
    assert digest(HERE / "baseline_runs.json") == gate["baseline_runs_sha256"]
    assert not (HERE / "count_runs.json").exists() and not (HERE / "zero_runs.json").exists()
    result = {"status": "PASS", "prediction_files": prediction_files,
              "scored_fault_window_evaluations": scored_fault_windows,
              "event_subset_checks": event_checks, "summary_checks": summary_checks,
              "per_seed_support_delta": deltas, "count_stage_started": False,
              "analysis_sha256": digest(HERE / "baseline_analysis.json"),
              "source_sha256": digest(__file__), "input_hash_bindings": len(analysis["input_hashes"]),
              "checkpoint_replay": "Already passed in original 18 run processes; not rerun here."}
    with (HERE / "verification.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("INDEPENDENT_RESULTS_PASS", prediction_files, event_checks, summary_checks, flush=True)


if __name__ == "__main__":
    main()
