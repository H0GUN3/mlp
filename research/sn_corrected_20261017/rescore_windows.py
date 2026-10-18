"""Rescore frozen query predictions; no fitting, inference, or file writes."""
import hashlib
import json
from pathlib import Path
from typing import Dict

import numpy as np

from scores import event_metrics

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def window_scores(logits, labels, event_ids):
    logits = np.asarray(logits)
    labels = np.asarray(labels)
    ids = np.asarray(event_ids)
    assert logits.shape == (len(labels), 12) and ids.shape == labels.shape
    assert np.isfinite(logits).all() and labels.dtype.kind in "iu"
    assert np.all((labels >= -1) & (labels < 12))
    fault = labels >= 0
    assert fault.any() and np.all(ids[~fault] == "") and np.all(ids[fault] != "")
    x, y, events = logits[fault], labels[fault], ids[fault]
    truth = x[np.arange(len(y)), y, None]
    greater = (x > truth).sum(axis=1)
    ties = (x == truth).sum(axis=1)
    result: Dict[str, float] = {
        "fault_windows": len(y), "normal_windows": int((~fault).sum()),
        "events": len(set(events)), "root_tied_windows": int((ties > 1).sum())}
    for k in (1, 3):
        credits = np.minimum(np.maximum(k - greater, 0), ties) / ties
        result["window_top{}".format(k)] = float(credits.mean())
        result["event_mean_window_top{}".format(k)] = float(np.mean([
            credits[events == event].mean() for event in sorted(set(events))]))
    return result


def self_test():
    tied = window_scores(np.zeros((2, 12)), np.array([0, -1]), ["a", ""])
    assert tied["window_top1"] == 1 / 12 and tied["window_top3"] == 3 / 12
    x = np.zeros((4, 12))
    x[:3, 0] = 1
    x[3, 1:4] = 1
    result = window_scores(x, np.zeros(4, dtype=int), ["a", "a", "a", "b"])
    assert result["window_top1"] == 0.75
    assert result["event_mean_window_top1"] == 0.5
    try:
        window_scores(x, np.full(4, -1), ["a"] * 4)
    except AssertionError:
        pass
    else:
        raise AssertionError("Malformed normal labels must fail")


def main():
    assert __debug__, "Safety assertions must remain enabled"
    self_test()
    evaluation = json.loads((HERE / "evaluation.json").read_text())
    assert evaluation["status"] == "PASS"
    assert evaluation["selection_sha256"] == digest(HERE / "selection.lock.json")
    rows = []
    for kind in ("eadro", "diagmlp"):
        for seed in (11, 23, 37):
            chunks, reference, indices, seen_events = [], [], set(), set()
            records = [r for r in evaluation["runs"]
                       if r["kind"] == kind and r["seed"] == seed]
            assert {r["rotation"] for r in records} == {0, 1, 2} and len(records) == 3
            for record in records:
                name = "r{}_{}_s{}_evaluation.npz".format(record["rotation"], kind, seed)
                path = HERE / "evaluation" / name
                assert digest(path) == record["prediction_sha256"][name]
                with np.load(path, allow_pickle=False) as saved:
                    current_indices = set(saved["indices"].tolist())
                    current_events = set(saved["event_ids"].tolist()) - {""}
                    assert len(current_indices) == len(saved["indices"])
                    assert not indices & current_indices and not seen_events & current_events
                    indices.update(current_indices)
                    seen_events.update(current_events)
                    chunks.append(tuple(saved[key].copy() for key in
                                        ("root_logits", "labels", "event_ids")))
                reference.extend(record["parts"]["evaluation"]["events"])
            x, y, ids = [np.concatenate([chunk[i] for chunk in chunks]) for i in range(3)]
            metrics = window_scores(x, y, ids)
            assert (metrics["fault_windows"], metrics["normal_windows"],
                    metrics["events"]) == (325, 69, 36)
            pooled = event_metrics(x, y, ids)
            for k in (1, 3):
                key = "top{}".format(k)
                assert abs(pooled[key] - np.mean([e[key] for e in reference])) < 1e-12
                metrics["pooled_event_" + key] = pooled[key]
            rows.append(dict(kind=kind, seed=seed, **metrics))
    keys = [key for key in rows[0] if "top" in key]
    means = {kind: {key: float(np.mean([r[key] for r in rows if r["kind"] == kind]))
                    for key in keys} for kind in ("eadro", "diagmlp")}
    print(json.dumps({"status": "PASS", "evaluation_sha256": digest(HERE / "evaluation.json"),
                      "source_sha256": digest(Path(__file__)), "rows": rows,
                      "three_seed_means": means, "detector_gated": False,
                      "split_or_weights_changed": False}, indent=2))
    print("WINDOW_RESCORE_PASS 18 325 36")


if __name__ == "__main__":
    main()
