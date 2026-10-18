"""Describe verified TT validation errors; no new training or model selection."""
from collections import Counter
import json
from pathlib import Path

import numpy as np

import tt_runner as run


def credits(logits, labels):
    x = np.asarray(logits)
    y = np.asarray(labels)
    assert x.ndim == 2 and y.shape == (len(x),)
    assert np.isfinite(x).all() and np.all((0 <= y) & (y < x.shape[1]))
    truth = x[np.arange(len(y)), y, None]
    above = (x > truth).sum(axis=1)
    tied = (x == truth).sum(axis=1)
    return np.where(above == 0, 1.0 / tied, 0.0)


def describe(values, mask):
    v = np.asarray(values)[mask]
    return {"count": len(v), "median": float(np.median(v)) if len(v) else None,
            "max": float(v.max()) if len(v) else None}


def main():
    assert __debug__
    np.testing.assert_array_equal(credits(np.zeros((2, 27)), [0, 1]), [1 / 27, 1 / 27])
    assert credits([[2., 1.], [1., 2.]], [0, 0]).tolist() == [1., 0.]
    proof = json.loads((run.HERE / "TT_RESULTS.json").read_text())
    assert proof["status"] == "PASS" and proof["sources"] == run.sources()
    arrays, meta, parts = run.load_selected()
    stats, data = run.make_data(arrays, parts)
    positions = parts["validation"]
    labels = arrays["labels"][positions]
    fault = labels >= 0
    roots = labels[fault]
    original = arrays["indices"][positions][fault]
    event_ids = arrays["event_ids"][positions][fault]
    types = np.array([meta["faults"][event]["fault_type"] for event in event_ids])
    with np.load(run.INPUT / "TT.npz", allow_pickle=False) as saved:
        root_counts = saved["unique_count"][positions[fault], roots]
    ranges = {}
    for modality in ("metrics", "traces"):
        train = data["train"][modality]
        val = data["validation"][modality][fault]
        lo, hi = train.min(axis=(0, 2)), train.max(axis=(0, 2))
        ranges[modality] = {
            "max_abs": np.abs(val).max(axis=(1, 2, 3)),
            "fraction_outside_train_range": ((val < lo[None, :, None, :]) |
                                           (val > hi[None, :, None, :])).mean(axis=(1, 2, 3))}
    reports, paired = [], {}
    for record in proof["runs"]:
        kind, seed = record["kind"], record["seed"]
        folder = run.HERE / "tt_runs" / kind / ("seed_" + str(seed))
        assert run.digest(folder / "summary.json") == record["summary_sha256"]
        summary = json.loads((folder / "summary.json").read_text())
        with np.load(folder / "best_validation.npz", allow_pickle=False) as saved:
            np.testing.assert_array_equal(saved["indices"], arrays["indices"][positions])
            np.testing.assert_array_equal(saved["labels"], labels)
            logits = saved["root_logits"][fault].astype(np.float64)
        hit = credits(logits, roots)
        assert abs(hit.mean() - summary["metrics"]["best"]["validation"]["conditional_top1"]) < 1e-12
        paired[(kind, seed)] = hit
        wrong = hit == 0
        shifted = logits - logits.max(axis=1, keepdims=True)
        nll = np.log(np.exp(shifted).sum(axis=1)) - shifted[np.arange(len(roots)), roots]
        groups = {}
        for name, mask in [(t, types == t) for t in sorted(set(types))] + [
                ("root_trace_absent", root_counts == 0), ("root_trace_present", root_counts > 0)]:
            groups[name] = {"windows": int(mask.sum()),
                            "top1": float(hit[mask].mean()) if mask.any() else None,
                            "fully_wrong": int((wrong & mask).sum())}
        by_root = []
        for root in sorted(set(roots)):
            mask = roots == root
            by_root.append({"service": meta["services"][root], "windows": int(mask.sum()),
                            "top1": float(hit[mask].mean()),
                            "fully_wrong": int((wrong & mask).sum())})
        confusions = Counter()
        for i in np.flatnonzero(wrong):
            candidates = np.flatnonzero(logits[i] == logits[i].max())
            names = "|".join(meta["services"][j] for j in candidates)
            confusions[(meta["services"][roots[i]], names)] += 1
        reports.append({
            "kind": kind, "seed": seed, "selected_epoch": record["best_epoch"],
            "selected": summary["metrics"]["best"], "last": summary["metrics"]["last"],
            "fault_type_and_trace_groups": groups, "by_root": by_root,
            "confusions": [{"root": root, "top_candidates": names, "windows": count}
                           for (root, names), count in confusions.most_common()],
            "wrong_original_indices": original[wrong].tolist(),
            "wrong_event_ids": sorted(set(event_ids[wrong])),
            "nll_correct": describe(nll, hit == 1), "nll_wrong": describe(nll, wrong),
            "input_ranges": {m: {k: {"correct": describe(v, hit == 1),
                                    "wrong": describe(v, wrong)}
                                  for k, v in values.items()} for m, values in ranges.items()}})
    contrasts = []
    for seed in run.SEEDS:
        e, d = paired[("eadro", seed)], paired[("diagmlp", seed)]
        contrasts.append({"seed": seed, "both_wrong": int(((e == 0) & (d == 0)).sum()),
                          "eadro_wrong_diag_correct": int(((e == 0) & (d == 1)).sum()),
                          "diag_wrong_eadro_correct": int(((d == 0) & (e == 1)).sum())})
    result = {"status": "PASS", "validation_only": True, "fault_windows": len(roots),
              "protected_observations_opened": False,
              "root_trace_absent_windows": int((root_counts == 0).sum()),
              "sources": run.sources(), "verifier_result_sha256": run.digest(run.HERE / "TT_RESULTS.json"),
              "diagnosis_source_sha256": run.digest(Path(__file__)), "runs": reports,
              "paired_window_outcomes": contrasts,
              "causal_claim": False, "new_hypothesis_tested": False}
    run.dump(run.HERE / "TT_DIAGNOSIS.json", result)
    for item in reports:
        print("TT_ERROR_GROUPS", item["kind"], item["seed"],
              json.dumps(item["fault_type_and_trace_groups"], sort_keys=True), flush=True)
    print("TT_DIAGNOSIS_PASS 6 686", flush=True)


if __name__ == "__main__":
    main()
