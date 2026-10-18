#!/usr/bin/env python3
"""Bounded, read-only SN/TT audit. No original streams, model imports or fits."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
from typing import Dict, List

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUNDLES = ROOT / "research/relationship_smoke_20261013/artifacts"
FEATURES = ROOT / "research/method_mlp_20261013/features.py"
REPORT_INPUTS = [
    HERE / "BRIEF.md",
    FEATURES,
    FEATURES.parent / "ranker.py",
    FEATURES.parent / "features_implementation.md",
    ROOT / "research/resource_study_20261013/trace_preflight.json",
    ROOT / "research/resource_study_20261013/PREFLIGHT_REPORT.md",
    *[ROOT / "research/relationship_diagnosis_20261014" / name for name in
      ("COMPARATORS.md", "PROTOCOL.md", "RECORDINGS.md", "recordings.json",
       "ROOT_CONTEXT.md", "errors_root_context.json")],
]
KEYS = {"values", "observed", "x", "mask", "coverage", "adjacency", "indices",
        "labels", "event_ids", "episode_ids", "fold_ids", "partition"}
EXPECTED = {"SN": "1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb",
            "TT": "4e568299514f10f247c0b2496e3392a6457825844e2145ad3df36b13c9cd9cff"}


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_functions():
    # Executing the module would import native helpers; extract only pure QA functions.
    tree = ast.parse(FEATURES.read_text())
    functions: List[ast.stmt] = [
        node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in ("fit_reference", "window_features")]
    assert len(functions) == 2
    namespace = {"np": np, "Dict": Dict}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(FEATURES), "exec"),
         namespace)
    return namespace["fit_reference"], namespace["window_features"]


def nonconstant(values, observed):
    """Numeric variation among at least two observed seconds, not padding variation."""
    low = np.where(observed, values, np.inf).min(axis=2)
    high = np.where(observed, values, -np.inf).max(axis=2)
    return (observed.sum(axis=2) >= 2) & (high > low)


def changed(values, observed, other_values, other_observed):
    return ((observed != other_observed) |
            (observed & other_observed & (values != other_values))).any(axis=(1, 2, 3))


def count_rate(mask):
    return {"numerator": int(np.count_nonzero(mask)), "denominator": int(mask.size),
            "fraction": float(mask.mean()) if mask.size else None}


def self_check(fit, features):
    values = np.zeros((3, 1, 10, 9))
    values[..., 0] = np.arange(10)
    observed = np.ones_like(values, dtype=bool)
    observed[:, :, :4, 7] = False
    labels = np.array([-1, 0, -1])
    partition = np.array(["train", "validation", "validation"])
    ref = fit(values, observed, labels, partition)
    before = features(values, observed, ref)
    after = features(values[:, :, ::-1], observed[:, :, ::-1], ref)
    for a, b in zip(before, after):
        np.testing.assert_allclose(a, b, rtol=1e-6, atol=1e-6)
    assert changed(values, observed, values[:, :, ::-1], observed[:, :, ::-1]).all()
    assert nonconstant(values, observed)[..., 0].all()
    assert not nonconstant(values, observed)[..., 1:].any()
    assert not nonconstant(np.zeros_like(values), observed).any()
    changed_validation = values.copy()
    changed_validation[1:] += 999
    for key, value in fit(changed_validation, observed, labels, partition).items():
        np.testing.assert_array_equal(value, ref[key])
    missing = {key: value.copy() for key, value in ref.items()}
    missing["mask"][0, 7] = False
    x, mask, coverage = features(values, observed, missing)
    assert not mask[..., [7, 16]].any()
    assert not x[..., [7, 16]].any()
    assert (coverage[..., [7, 16]] > 0).all()
    print("SN_TT_SELF_CHECK_PASS (order, constancy, missing reference, TRAIN-only)", flush=True)


def audit_system(system, fit, features, preflight, old_context):
    stem = BUNDLES / system
    meta = json.loads(stem.with_suffix(".json").read_text())
    assert sha(stem.with_suffix(".npz")) == meta["npz_sha256"] == EXPECTED[system]
    assert sha(FEATURES) == meta["source_hashes"][str(FEATURES)]
    with np.load(stem.with_suffix(".npz"), allow_pickle=False) as archive:
        assert set(archive.files) == KEYS
        data = {key: archive[key] for key in archive.files}
    v, o = data["values"], data["observed"]
    rows, nodes, seconds, channels = v.shape
    assert (seconds, channels) == (10, 9)
    assert o.dtype == np.bool_ and o.shape == v.shape
    assert np.isfinite(v).all() and len(meta["windows"]) == rows
    assert o[..., :7].all() and o[..., 8].all()
    assert np.array_equal(o[..., 7], v[..., 8] > 0)
    assert np.all(v[..., 8] >= 0) and np.all(v[..., 8] == v[..., 8].astype(np.int64))
    assert not np.diagonal(data["adjacency"], axis1=1, axis2=2).any()
    assert len(set(data["indices"])) == rows
    assert (data["partition"] == "validation").tolist() == (data["fold_ids"] == 0).tolist()
    assert set(data["indices"]) <= set(
        np.random.RandomState(42).permutation(meta["native_window_count"])[
            :int(.7 * meta["native_window_count"])])
    for i, w in enumerate(meta["windows"]):
        assert w["end"] == w["start"] + 9
        assert (w["event_id"] or "") == data["event_ids"][i]
        if w["event_id"]:
            assert meta["faults"][w["event_id"]]["root"] == data["labels"][i]
    normal_train = (data["labels"] == -1) & (data["partition"] == "train")
    assert sorted(data["indices"][normal_train].tolist()) == sorted(meta["normal_train_indices"])
    reference = fit(v, o, data["labels"], data["partition"])
    for key, expected in meta["normal_reference"].items():
        np.testing.assert_array_equal(reference[key], np.array(expected))
    replay = features(v, o, reference)
    for actual, key in zip(replay, ("x", "mask", "coverage")):
        np.testing.assert_array_equal(actual, data[key])
    nc = nonconstant(v, o)
    fault = data["labels"] >= 0
    fault_rows = np.flatnonzero(fault)
    roots = data["labels"][fault]
    root_nc = nc[fault_rows, roots]
    temporal = {
        "reference": "QA only; refit normal TRAIN, exact equality to saved fold0 reference",
        "exact_saved_feature_replay": True,
        "scalar_slots_before_after": [seconds * channels, 18],
        "not_information_bits_or_causal_effect": True,
        "nonconstant_service_channel_windows": count_rate(nc),
        "nonconstant_system_windows": count_rate(nc.any(axis=(1, 2))),
        "nonconstant_fault_system_windows": count_rate(nc[fault].any(axis=(1, 2))),
        "nonconstant_root_service_windows": count_rate(root_nc.any(axis=1)),
        "nonconstant_root_channel_windows": count_rate(root_nc),
        "root_observation_timing_variable_channels": int(
            ((o.sum(axis=2) > 0) & (o.sum(axis=2) < 10))[fault_rows, roots].sum()),
        "per_channel_nonconstant_all": nc.sum(axis=(0, 1)).tolist(),
        "per_channel_nonconstant_root": root_nc.sum(axis=0).tolist(),
        "transforms": {},
    }
    rng = np.random.RandomState(20261016)
    transforms = [
        ("reverse", np.arange(9, -1, -1)[None, None, :, None]),
        ("shared_permutation", rng.permutation(10)[None, None, :, None]),
        ("independent_channel_permutation",
         np.argsort(rng.random_sample(v.shape), axis=2)),
    ]
    for name, order in transforms:
        vv = np.take_along_axis(v, order, axis=2)
        oo = np.take_along_axis(o, order, axis=2)
        transformed = features(vv, oo, reference)
        for a, b in zip(replay, transformed):
            np.testing.assert_allclose(a, b, rtol=1e-6, atol=1e-6)
        delta = np.max(np.abs(replay[0] - transformed[0]), axis=(1, 2))
        changed_rows = changed(v, o, vv, oo)
        changed_roots = changed(v[fault_rows, roots][:, None],
                                o[fault_rows, roots][:, None],
                                vv[fault_rows, roots][:, None],
                                oo[fault_rows, roots][:, None])
        temporal["transforms"][name] = {
            "changed_system_windows": count_rate(changed_rows),
            "changed_root_service_windows": count_rate(changed_roots),
            "summary_equal_windows_tolerance": count_rate(delta <= 1e-6),
            "max_absolute_float32_feature_difference": float(delta.max()),
            "mask_exact_equal": bool(np.array_equal(replay[1], transformed[1])),
            "coverage_exact_equal": bool(np.array_equal(replay[2], transformed[2])),
            "permutation_sha256": hashlib.sha256(order.tobytes()).hexdigest(),
        }
    adjacency = data["adjacency"]
    incoming = adjacency[fault_rows, :, roots]
    outgoing = adjacency[fault_rows, roots, :]
    root_context = incoming.any(axis=1) | outgoing.any(axis=1)
    old = [e for e in old_context["events"] if e["system"] == system]
    assert {e["event_id"] for e in old} == set(data["event_ids"][fault])
    assert sum(e["contexts"]["root_any_raw"]["present_windows"] for e in old) == int(root_context.sum())
    contrasts = []
    # Root/nonroot anomaly contrast is descriptive; nonroots are not labelled victims.
    metric_magnitude = np.abs(data["x"][..., :7]).mean(axis=2)
    for i, root, inc, out in zip(fault_rows, roots, incoming, outgoing):
        nonroot = np.arange(nodes) != root
        contrasts.append({
            "original_index": int(data["indices"][i]),
            "event_id": str(data["event_ids"][i]),
            "root_service": meta["services"][root],
            "root_latency_seconds": int(o[i, root, :, 7].sum()),
            "root_metric_magnitude": float(metric_magnitude[i, root]),
            "max_nonroot_metric_magnitude": float(metric_magnitude[i, nonroot].max()),
            "root_at_least_max_nonroot": bool(
                metric_magnitude[i, root] >= metric_magnitude[i, nonroot].max()),
            "observed_callers": [meta["services"][n] for n in np.flatnonzero(inc)],
            "observed_callees": [meta["services"][n] for n in np.flatnonzero(out)],
            "mean_caller_metric_magnitude": float(metric_magnitude[i, inc].mean()) if inc.any() else None,
            "mean_callee_metric_magnitude": float(metric_magnitude[i, out].mean()) if out.any() else None,
        })
    services = []
    for node, service in enumerate(meta["services"]):
        rr = data["labels"] == node
        services.append({
            "service": service,
            "observed_seconds_per_channel": o[:, node].sum(axis=(0, 1)).tolist(),
            "possible_seconds_per_channel": rows * 10,
            "zero_observed_seconds_per_channel": ((v[:, node] == 0) & o[:, node]).sum(axis=(0, 1)).tolist(),
            "nonconstant_windows_per_channel": nc[:, node].sum(axis=0).tolist(),
            "latency_present_windows": int(o[:, node, :, 7].any(axis=1).sum()),
            "reference_mask": reference["mask"][node].tolist(),
            "effective_feature_present_windows": data["mask"][:, node].sum(axis=0).tolist(),
            "root_events": len(set(data["event_ids"][rr])),
            "root_windows": int(rr.sum()),
            "root_latency_present_windows": int(o[rr, node, :, 7].any(axis=1).sum()),
            "root_latency_seconds": int(o[rr, node, :, 7].sum()),
            "root_incoming_windows": int(adjacency[rr, :, node].any(axis=1).sum()),
            "root_outgoing_windows": int(adjacency[rr, node, :].any(axis=1).sum()),
            "root_nonconstant_windows": int(nc[rr, node].any(axis=1).sum()),
        })
    episodes = []
    for episode in sorted(set(data["episode_ids"])):
        selected = data["episode_ids"] == episode
        parts = set(data["partition"][selected])
        folds = set(data["fold_ids"][selected])
        assert len(parts) == len(folds) == 1
        episodes.append({"episode": str(episode), "partition": str(next(iter(parts))),
                         "fold": int(next(iter(folds))), "windows": int(selected.sum()),
                         "normal_windows": int((selected & ~fault).sum())})
    folds = []
    for fold in range(3):
        hold = data["fold_ids"] == fold
        train_roots = set(data["labels"][~hold & fault])
        held_roots = set(data["labels"][hold & fault])
        train_events = set(data["event_ids"][~hold & fault])
        held_events = set(data["event_ids"][hold & fault])
        assert not train_events & held_events and train_roots == held_roots == set(range(nodes))
        folds.append({"fold": fold, "train_events": len(train_events),
                      "holdout_events": len(held_events),
                      "train_normal_windows": int((~hold & ~fault).sum()),
                      "holdout_normal_windows": int((hold & ~fault).sum()),
                      "train_root_count": len(train_roots), "cold_roots": [],
                      "train_types": sorted({meta["faults"][e]["fault_type"] for e in train_events}),
                      "holdout_types": sorted({meta["faults"][e]["fault_type"] for e in held_events}),
                      "same_root_fault_pair_repeated_events": False})
    recordings = []
    runs = sorted({w["run_id"] for w in meta["windows"]})
    for run in runs:
        selected = np.array([w["run_id"] == run for w in meta["windows"]])
        held_events = {e for e, f in meta["faults"].items() if f["run_id"] == run}
        held_roots = {meta["faults"][e]["root"] for e in held_events}
        other_roots = {f["root"] for f in meta["faults"].values() if f["run_id"] != run}
        assert len(held_events) == 9 and len(held_roots) == 3
        assert not held_roots & other_roots
        recordings.append({
            "recording": run, "events": sorted(held_events),
            "roots": [meta["services"][n] for n in sorted(held_roots)],
            "fault_types": sorted({meta["faults"][e]["fault_type"] for e in held_events}),
            "holdout_windows": int(selected.sum()),
            "holdout_normal_windows": int((selected & ~fault).sum()),
            "train_normal_windows": int((~selected & ~fault).sum()),
            "cold_roots": [meta["services"][n] for n in sorted(held_roots - other_roots)],
            "train_events": len(meta["faults"]) - len(held_events),
            "candidate_count_unchanged": nodes,
        })
    event_details = []
    for event, entry in sorted(meta["faults"].items()):
        selected = np.flatnonzero(data["event_ids"] == event)
        contrast_rows = [c for c in contrasts if c["event_id"] == event]
        event_details.append({
            **entry, "fold": meta["event_folds"][event],
            "windows": int(len(selected)),
            "original_indices": data["indices"][selected].tolist(),
            "root_metric_at_least_nonroot_fraction": float(np.mean(
                [c["root_at_least_max_nonroot"] for c in contrast_rows])),
            "root_latency_present_fraction": float(np.mean(
                [c["root_latency_seconds"] > 0 for c in contrast_rows])),
            "root_any_edge_fraction": float(np.mean(
                [bool(c["observed_callers"] or c["observed_callees"]) for c in contrast_rows])),
        })
    assert len(event_details) == nodes * 3
    pairs = Counter((f["root"], f["fault_type"]) for f in meta["faults"].values())
    assert set(pairs.values()) == {1}
    boundary = {"fully_inside_fault_windows": 0, "fault_windows_crossing_injection_boundary": 0,
                "normal_windows_overlapping_injection": 0}
    for i, w in enumerate(meta["windows"]):
        if fault[i]:
            entry = meta["faults"][w["event_id"]]
            inside = w["start"] >= entry["start"] and w["end"] <= entry["end_inclusive"]
            boundary["fully_inside_fault_windows" if inside else
                     "fault_windows_crossing_injection_boundary"] += 1
        elif any(w["run_id"] == f["run_id"] and
                 w["start"] <= f["end_inclusive"] and w["end"] >= f["start"]
                 for f in meta["faults"].values()):
            boundary["normal_windows_overlapping_injection"] += 1
    for run in runs:
        starts = sorted(w["start"] for w in meta["windows"] if w["run_id"] == run)
        assert all(b - a >= 10 for a, b in zip(starts, starts[1:]))
    pf = next(s for s in preflight["systems"] if s["system"] == system)
    assert pf["selected_windows"] == rows and pf["candidate_services"] == nodes
    assert int(v[..., 8].sum()) == pf["counts"]["selected_span_occurrences"]
    assert int(o[..., 7].any(axis=2).sum()) == rows * nodes - pf[
        "window_service_retained_span_count_histogram"]["0"]
    assert all(meta["raw_input_hashes"][p] == h for p, h in pf["raw_source_hashes"].items())
    return {
        "schema": {k: {"shape": list(a.shape), "dtype": str(a.dtype)} for k, a in data.items()},
        "channels": [s.split("__")[0] for s in meta["feature_names"][:9]],
        "bundle_provenance": meta["provenance"], "source_hashes_recorded": meta["source_hashes"],
        "raw_hashes_recorded_only_not_reopened": meta["raw_input_hashes"],
        "bundle_limitations": meta["limitations"], "services": services,
        "counts": meta["counts"], "boundary_audit": boundary,
        "temporal_loss": temporal, "episodes": episodes, "fold_support": folds,
        "recording_holdouts": recordings, "events": event_details,
        "root_contrasts": {
            "definition": "mean abs of seven signed-log-z metric means, fold0 QA reference; no scores fitted",
            "nonroot_victim_labels_available": False,
            "fault_windows": len(contrasts),
            "root_any_edge_windows": int(root_context.sum()),
            "root_incoming_windows": int(incoming.any(axis=1).sum()),
            "root_outgoing_windows": int(outgoing.any(axis=1).sum()),
            "root_both_direction_windows": int((incoming.any(axis=1) & outgoing.any(axis=1)).sum()),
            "event_equal_root_any_edge_fraction": float(np.mean(
                [e["root_any_edge_fraction"] for e in event_details])),
            "event_equal_root_latency_present_fraction": float(np.mean(
                [e["root_latency_present_fraction"] for e in event_details])),
            "event_equal_root_metric_at_least_nonroot_fraction": float(np.mean(
                [e["root_metric_at_least_nonroot_fraction"] for e in event_details])),
            "windows": contrasts,
        },
        "preflight_existing_evidence": {
            k: pf[k] for k in ("selected_windows", "candidate_services", "counts",
                               "reference_types", "span_kind_values", "outcome_tag_values",
                               "span_tag_key_occurrences", "distinct_selected_span_identities",
                               "distinct_conflicting_selected_identities",
                               "window_service_distinct_span_identity_histogram")},
        "checks": {"schema_valid": True, "bundle_hash_pinned": True,
                   "normal_train_reference_exact": True, "no_native_test_indices": True,
                   "episode_disjoint": True, "selected_windows_nonoverlap": True,
                   "existing_root_context_counts_equal": True,
                   "existing_preflight_counts_and_raw_hashes_equal": True},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--output", default="sn_tt_audit.json")
    args = parser.parse_args()
    output = HERE / args.output
    if output.parent != HERE or not output.name.startswith("sn_tt_") or output.suffix != ".json":
        raise ValueError("Output must be a new sn_tt_*.json in this directory")
    if not args.self_check and (output.exists() or output.is_symlink()):
        raise FileExistsError("Refusing existing output: " + str(output))
    fit, features = source_functions()
    self_check(fit, features)
    if args.self_check:
        return
    paths = REPORT_INPUTS + [BUNDLES / (s + ext) for s in ("SN", "TT") for ext in (".json", ".npz")]
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    preflight = json.loads(REPORT_INPUTS[4].read_text())
    old_context = json.loads((ROOT / "research/relationship_diagnosis_20261014/errors_root_context.json").read_text())
    result = {"status": "PASS", "scope": "allowed development bundles only; QA transforms not training",
              "environment": {"python": platform.python_version(), "numpy": np.__version__},
              "software_sha256": sha(Path(__file__)), "inputs_sha256": before,
              "systems": {}}
    for system in ("SN", "TT"):
        result["systems"][system] = audit_system(system, fit, features, preflight, old_context)
        print("SN_TT_SYSTEM_PASS " + system, flush=True)
    assert before == {str(p.relative_to(ROOT)): sha(p) for p in paths}
    result["inputs_unchanged_after"] = True
    result["not_run"] = ["model fits/inference", "original streams", "native_inputs/raw.npz",
                         "native test/unassigned observations", "RCAEval/RCABench observations",
                         "downloads/installs", "public fusion code verification"]
    with output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("SN_TT_AUDIT_PASS " + output.name + " sha256=" + sha(output), flush=True)


if __name__ == "__main__":
    main()
