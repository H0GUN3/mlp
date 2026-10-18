"""Read-only diagnostics from hash-bound development bundles and saved predictions."""
from __future__ import annotations

import hashlib
from itertools import product
import json
from math import fsum
from pathlib import Path
import platform
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
CV = HERE.parent / "relationship_cv_20261014" / "results"
BUNDLES = HERE.parent / "relationship_smoke_20261013" / "artifacts"
SYSTEMS = ("SN", "TT")
FOLDS = (0, 1, 2)
SEEDS = (11, 23, 37)
MODES = ("local", "global", "directed")
METRICS = ("top1", "top3", "mrr")
RELATIONS = ("both_direct", "root_to_wrong", "wrong_to_root",
             "other_weakly_connected", "no_observed_connection")
BUNDLE_MEMBERS = ("observed", "adjacency", "indices", "labels", "event_ids",
                  "episode_ids", "fold_ids")
PREDICTION_MEMBERS = ("logits", "labels", "indices", "event_ids")
# analysis.json has no producer-saved self hash: explicitly bind its frozen snapshot.
SNAPSHOT_HASHES = {
    "runs.json": "48129c9be79d251f5278a6ed79ccd72dca2373d10ef4e3f9038b0e9b055b6b13",
    "analysis.json": "3814b07ee7d5a255c02b419f5407a76bba96b3da9c75e0511ad07513a636b11e",
}
EXPECTED_WTL = {"SN": {"win": 17, "tie": 13, "loss": 6},
                "TT": {"win": 28, "tie": 34, "loss": 19}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_hash(path, expected):
    require(isinstance(expected, str) and len(expected) == 64
            and all(c in "0123456789abcdef" for c in expected),
            "Missing or invalid saved hash: " + str(path))
    actual = file_hash(path)
    require(actual == expected, "Provenance mismatch: " + str(path))
    return actual


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Nonfinite JSON constant: " + value)


class Inputs:
    """Track only explicitly consumed files; never follow raw provenance paths."""

    def __init__(self):
        self.provenance = {}

    def record(self, path, expected, binding, members):
        path = Path(path)
        digest = check_hash(path, expected)
        entry = {"sha256": digest, "expected_sha256": expected,
                 "binding": binding, "members_read": list(members)}
        previous = self.provenance.get(str(path))
        require(previous is None or previous == entry, "Conflicting hash binding")
        self.provenance[str(path)] = entry

    def json(self, path, expected, binding):
        self.record(path, expected, binding, ())
        result = json.loads(Path(path).read_text(encoding="utf-8"),
                            object_pairs_hook=unique_object,
                            parse_constant=reject_constant)
        check_hash(path, expected)
        return result

    def npz(self, path, expected, binding, members):
        self.record(path, expected, binding, members)
        with np.load(path, allow_pickle=False) as archive:
            require(len(archive.files) == len(set(archive.files)),
                    "Duplicate NPZ members: " + str(path))
            require(set(members) <= set(archive.files), "Missing NPZ member: " + str(path))
            result = {key: archive[key] for key in members}
        check_hash(path, expected)
        return result

    def recheck(self):
        for path, entry in self.provenance.items():
            check_hash(path, entry["expected_sha256"])


def validate_reports(reports):
    expected = set(product(SYSTEMS, FOLDS, SEEDS, MODES))
    require(isinstance(reports, list) and len(reports) == 54, "Missing reports: expected 54")
    result = {}
    for report in reports:
        key = tuple(report[name] for name in ("system", "fold", "seed", "mode"))
        require(key in expected, "Unexpected run identity")
        require(key not in result, "Duplicate run identity")
        result[key] = report
    require(set(result) == expected, "Missing run identity")
    return result


def validate_bundle(bundle, manifest, system):
    indices, labels = bundle["indices"], bundle["labels"]
    n, nodes = len(indices), len(manifest["services"])
    require(manifest["system"] == system, "Bundle system mismatch")
    require(len(set(manifest["services"])) == nodes, "Duplicate service")
    require(indices.shape == labels.shape == (n,) and indices.dtype.kind in "iu"
            and labels.dtype.kind in "iu", "Invalid bundle indices/labels")
    require(len(np.unique(indices)) == n, "Duplicate bundle indices")
    require(np.all(indices >= 0) and np.all(indices < manifest["native_window_count"]),
            "Bundle index outside manifest")
    require(np.all((labels >= -1) & (labels < nodes)), "Invalid bundle root")
    require(bundle["observed"].shape == (n, nodes, 10, 9)
            and bundle["observed"].dtype == np.bool_, "Invalid raw observation mask")
    require(bundle["adjacency"].shape == (n, nodes, nodes)
            and bundle["adjacency"].dtype == np.bool_, "Invalid adjacency")
    require(not np.diagonal(bundle["adjacency"], axis1=1, axis2=2).any(),
            "Unexpected self edge")
    for key in ("event_ids", "episode_ids", "fold_ids"):
        require(bundle[key].shape == (n,), "Invalid bundle metadata shape")
    require(bundle["fold_ids"].dtype.kind in "iu"
            and np.isin(bundle["fold_ids"], FOLDS).all(), "Invalid bundle folds")
    require(len(manifest["windows"]) == n, "Missing manifest windows")
    require(set(bundle["event_ids"][labels >= 0]) == set(manifest["faults"]),
            "Missing event coverage in bundle")
    for row, window in enumerate(manifest["windows"]):
        event = str(bundle["event_ids"][row])
        require(window["event_id"] == (event or None), "Window event mismatch")
        if labels[row] >= 0:
            require(event in manifest["faults"], "Missing fault metadata")
            fault = manifest["faults"][event]
            require(fault["event_id"] == event and fault["root"] == labels[row]
                    and fault["service"] == manifest["services"][int(labels[row])]
                    and fault["run_id"] == window["run_id"]
                    and manifest["event_folds"][event] == bundle["fold_ids"][row]
                    and bundle["episode_ids"][row] == event, "Fault identity/fold mismatch")
        else:
            require(not event, "Normal window has a fault event")


def validate_prediction(saved, bundle, fold):
    rows = np.flatnonzero((bundle["fold_ids"] == fold) & (bundle["labels"] >= 0))
    for key in ("indices", "labels", "event_ids"):
        require(np.array_equal(saved[key], bundle[key][rows]), "Prediction pairing mismatch: " + key)
    require(len(np.unique(saved["indices"])) == len(rows), "Duplicate prediction indices")
    logits = saved["logits"]
    require(logits.shape == (len(rows), bundle["adjacency"].shape[1])
            and np.isfinite(logits).all(), "Invalid saved logits")
    return rows


def ranking(logits, labels):
    """Expected rank credit under uniform permutations of exact score ties."""
    require(logits.ndim == 2 and len(logits) > 0 and logits.shape[1] > 0
            and labels.shape == (len(logits),) and labels.dtype.kind in "iu"
            and np.all((labels >= 0) & (labels < logits.shape[1]))
            and np.isfinite(logits).all(), "Invalid ranking inputs")
    target = logits[np.arange(len(labels)), labels]
    greater = (logits > target[:, None]).sum(axis=1)
    ties = (logits == target[:, None]).sum(axis=1)
    metrics = {
        "top1": np.clip((1 - greater) / ties, 0, 1),
        "top3": np.clip((3 - greater) / ties, 0, 1),
        "mrr": np.asarray([np.mean(1 / np.arange(g + 1, g + t + 1, dtype=np.float64))
                           for g, t in zip(greater, ties)]),
    }
    maxima = logits == logits.max(axis=1, keepdims=True)
    probability = maxima / maxima.sum(axis=1, keepdims=True)
    require(np.allclose(probability.sum(axis=1), 1, atol=1e-12, rtol=0),
            "Top-service probability is not conserved")
    require(np.allclose(probability[np.arange(len(labels)), labels], metrics["top1"],
                        atol=1e-12, rtol=0), "Root credit mismatch")
    wrong = probability.copy()
    wrong[np.arange(len(labels)), labels] = 0
    require(np.allclose(wrong.sum(axis=1), 1 - metrics["top1"], atol=1e-12, rtol=0),
            "Wrong-service mass is not conserved")
    return metrics, wrong, int((ties > 1).sum()), int((maxima.sum(axis=1) > 1).sum())


def relation_codes(adjacency, root):
    """Exclusive observed relations; weak paths ignore direction, not time."""
    nodes = len(adjacency)
    require(adjacency.shape == (nodes, nodes) and adjacency.dtype == np.bool_
            and 0 <= root < nodes, "Invalid relation inputs")
    weak = adjacency | adjacency.T
    reached = {root}
    pending = [root]
    while pending:
        node = pending.pop()
        for neighbor in np.flatnonzero(weak[node]):
            index = int(neighbor)
            if index not in reached:
                reached.add(index)
                pending.append(index)
    result = np.full(nodes, 4, dtype=np.int64)
    result[root] = -1
    for wrong in range(nodes):
        if wrong == root:
            continue
        outgoing, incoming = adjacency[root, wrong], adjacency[wrong, root]
        result[wrong] = (0 if outgoing and incoming else 1 if outgoing else 2 if incoming
                         else 3 if wrong in reached else 4)
    return result


def root_observations(observed, adjacency, root, reference_mask):
    require(observed.ndim == 4 and observed.shape[2:] == (10, 9)
            and observed.dtype == np.bool_, "Invalid observation shape")
    windows, nodes = observed.shape[:2]
    require(reference_mask.shape == (nodes, 9) and reference_mask.dtype == np.bool_,
            "Missing or invalid fold reference mask")
    require(adjacency.shape == (windows, nodes, nodes) and adjacency.dtype == np.bool_
            and 0 <= root < nodes, "Invalid observation adjacency/root")
    visible = (observed.any(axis=2) & reference_mask[None, :, :]).any(axis=-1)
    raw = observed[:, root]
    contexts = {
        "anygraph": adjacency.any(axis=(1, 2)),
        "root_in_raw": adjacency[:, :, root].any(axis=1),
        "root_out_raw": adjacency[:, root, :].any(axis=1),
        "root_in_visible": (adjacency[:, :, root] & visible).any(axis=1),
        "root_out_visible": (adjacency[:, root, :] & visible).any(axis=1),
        "root_visible": visible[:, root],
        "root_trace_observed": raw[:, :, 7].any(axis=1),
        "root_reference_any": np.full(windows, reference_mask[root].any(), dtype=np.bool_),
        "root_reference_trace": np.full(windows, reference_mask[root, 7], dtype=np.bool_),
    }
    summary = {
        "contexts": {key: {"present_windows": int(value.sum()),
                           "absent_windows": int((~value).sum()),
                           "present_fraction": float(value.mean())}
                     for key, value in contexts.items()},
        "root_raw9_observed_fraction": float(raw.mean()),
        "root_raw_channel_observed_fractions": raw.mean(axis=(0, 1)).tolist(),
        "root_trace_latency_channel7_observed_fraction": float(raw[:, :, 7].mean()),
        "root_reference_mask": reference_mask[root].tolist(),
        "root_reference_available_fraction": float(reference_mask[root].mean()),
        "root_reference_trace_available": bool(reference_mask[root, 7]),
    }
    return summary, contexts


def compare(actual, expected, where):
    for metric in METRICS:
        require(metric in expected and np.isfinite(expected[metric])
                and np.isclose(actual[metric], expected[metric], atol=1e-12, rtol=1e-9),
                "Saved metric mismatch: " + where + "/" + metric)


def metric_mean(scores, mask=None):
    result = {}
    for metric, value in scores.items():
        chosen = value if mask is None else value[:, mask]
        result[metric] = (float(chosen.mean()) if chosen.ndim == 1
                          else fsum(float(v) for v in chosen.mean(axis=1)) / len(chosen))
    return result


def outcome(delta):
    return "improvement" if delta > 0 else "worsening" if delta < 0 else "tie"


def wtl(deltas):
    values = list(deltas)
    return {"win": sum(d > 0 for d in values), "tie": sum(d == 0 for d in values),
            "loss": sum(d < 0 for d in values)}


def wrong_summary(mass, top1):
    values = np.asarray(mass, dtype=np.float64)
    total = float(values.sum())
    require(np.isclose(total, 1 - top1, atol=1e-12, rtol=0), "Event wrong mass mismatch")
    return {
        "total_mass": total,
        "relation_mass": dict(zip(RELATIONS, values.tolist())),
        "conditional_on_wrong": (dict(zip(RELATIONS, (values / total).tolist()))
                                 if total > 0 else dict.fromkeys(RELATIONS, None)),
        "conditional_denominator": total,
    }


def aggregate(entries):
    """Each entry is one incident and its unique-window subset, never a seed row."""
    require(bool(entries), "Empty stratum")
    modes = {}
    subset_deltas = []
    for mode in MODES:
        per_event = [metric_mean(event["scores"][mode], mask) for event, mask in entries]
        metrics = {key: float(np.mean([row[key] for row in per_event])) for key in METRICS}
        masses = [event["relation_mass"][mode][:, mask].mean(axis=1).mean(axis=0)
                  for event, mask in entries]
        modes[mode] = {"metrics": metrics,
                       "wrong": wrong_summary(np.mean(masses, axis=0), metrics["top1"])}
    for event, mask in entries:
        subset_deltas.append(metric_mean(event["scores"]["directed"], mask)["top1"]
                             - metric_mean(event["scores"]["global"], mask)["top1"])
    records = [event["record"] for event, _ in entries]
    return {
        "incidents": len(entries),
        "unique_windows": sum(int(mask.sum()) for _, mask in entries),
        "seed_window_decisions_per_mode": 3 * sum(int(mask.sum()) for _, mask in entries),
        "modes": modes,
        "delta_directed_global": {m: modes["directed"]["metrics"][m]
                                 - modes["global"]["metrics"][m] for m in METRICS},
        "full_event_decisions": {name: sum(r["decision"] == name for r in records)
                                 for name in ("improvement", "worsening", "tie")},
        "full_event_both_zero": sum(r["both_zero"] for r in records),
        "full_event_both_perfect": sum(r["both_perfect"] for r in records),
        "subset_top1_win_tie_loss": wtl(subset_deltas),
    }


def summarize_system(events):
    all_entries = [(event, np.ones(len(event["record"]["window_indices"]), dtype=np.bool_))
                   for event in events]
    faults = sorted({event["record"]["fault_type"] for event in events})
    contexts = {}
    for context in events[0]["contexts"]:
        present, absent, overlap = [], [], []
        for event in events:
            mask = event["contexts"][context]
            if mask.any():
                present.append((event, mask))
            if (~mask).any():
                absent.append((event, ~mask))
            if mask.any() and (~mask).any():
                overlap.append(event["record"]["event_id"])
        contexts[context] = {
            "present": aggregate(present) if present else None,
            "absent": aggregate(absent) if absent else None,
            "overlap_incidents": len(overlap),
            "overlap_event_ids": overlap,
            "unique_windows_disjoint": True,
        }
    return {
        "all": aggregate(all_entries),
        "fault_type": {fault: aggregate([(event, mask) for event, mask in all_entries
                                         if event["record"]["fault_type"] == fault])
                       for fault in faults},
        "root_context": contexts,
    }


def build_diagnostic() -> dict[str, Any]:
    inputs = Inputs()
    runs = inputs.json(CV / "runs.json", SNAPSHOT_HASHES["runs.json"], "frozen snapshot")
    saved_analysis = inputs.json(CV / "analysis.json", SNAPSHOT_HASHES["analysis.json"],
                                 "explicit frozen snapshot pin; no producer self hash")
    require(saved_analysis["input_hashes"]["runs.json"] == SNAPSHOT_HASHES["runs.json"],
            "Analysis/runs provenance mismatch")
    require(runs["status"] == "PASS" and runs["run_count"] == 54, "CV incomplete")
    reports = validate_reports(runs["reports"])
    records, internal_by_system = [], {}
    reconciliation = {"run_event_metric_checks": 0, "summary_event_metric_checks": 0,
                      "report_count": len(reports), "top1_win_tie_loss": {}}
    for system in SYSTEMS:
        manifest_path = BUNDLES / (system + ".json")
        manifest = inputs.json(manifest_path, runs["input_hashes"].get(str(manifest_path)),
                               "runs.json/input_hashes")
        bundle_path = BUNDLES / (system + ".npz")
        expected_bundle_hash = runs["input_hashes"].get(str(bundle_path))
        require(manifest["npz_sha256"] == expected_bundle_hash, "Manifest/bundle hash mismatch")
        bundle = inputs.npz(bundle_path, expected_bundle_hash,
                            "runs.json/input_hashes and manifest/npz_sha256", BUNDLE_MEMBERS)
        validate_bundle(bundle, manifest, system)
        require(manifest["faults"] == runs["systems"][system]["faults"], "Fault manifest mismatch")
        require(len(manifest["faults"]) == (36 if system == "SN" else 81),
                "Unexpected incident count")
        reference = {}
        predictions = {}
        for fold in FOLDS:
            stats_path = CV / system / ("fold_" + str(fold)) / "statistics.npz"
            stats_hash = runs["artifact_hashes"].get(str(stats_path.relative_to(CV)))
            stats = inputs.npz(stats_path, stats_hash, "runs.json/artifact_hashes",
                               ("reference_mask",))
            reference[fold] = stats["reference_mask"]
            require(reference[fold].shape == (len(manifest["services"]), 9)
                    and reference[fold].dtype == np.bool_, "Invalid fold mask")
            for seed, mode in product(SEEDS, MODES):
                report = reports[system, fold, seed, mode]
                path = CV / system / ("fold_" + str(fold)) / ("seed_" + str(seed)) / mode / "predictions.npz"
                digest = runs["artifact_hashes"].get(str(path.relative_to(CV)))
                require(digest == report["artifact_hashes"].get("predictions.npz"),
                        "Report/artifact provenance mismatch")
                prediction = inputs.npz(path, digest, "runs.json/artifact_hashes and report/artifact_hashes",
                                        PREDICTION_MEMBERS)
                rows = validate_prediction(prediction, bundle, fold)
                scores, wrong, target_ties, maximum_ties = ranking(prediction["logits"], prediction["labels"])
                events = prediction["event_ids"]
                require(set(events) == set(report["metrics"]["by_incident"]), "Missing report event")
                require(report["metrics"]["windows"] == len(rows)
                        and report["metrics"]["incidents"] == len(set(events))
                        and report["metrics"]["target_score_tie_windows"] == target_ties,
                        "Report counts mismatch")
                per_event = {}
                for event in sorted(set(events)):
                    metric = {m: float(v[events == event].mean()) for m, v in scores.items()}
                    compare(metric, report["metrics"]["by_incident"][event], str((system, fold, seed, mode, event)))
                    per_event[event] = metric
                    reconciliation["run_event_metric_checks"] += 1
                compare({m: float(np.mean([v[m] for v in per_event.values()])) for m in METRICS},
                        report["metrics"]["event_balanced"], "report event-balanced")
                compare(metric_mean(scores), report["metrics"]["window"], "report window")
                predictions[fold, seed, mode] = {
                    "rows": rows, "events": events, "scores": scores, "wrong": wrong,
                    "maximum_tie_windows": maximum_ties,
                }
        system_events = []
        for event_id, fault in sorted(manifest["faults"].items()):
            fold, root = manifest["event_folds"][event_id], fault["root"]
            bundle_rows = np.flatnonzero(bundle["event_ids"] == event_id)
            require(len(bundle_rows) > 0 and np.all(bundle["fold_ids"][bundle_rows] == fold),
                    "Missing/duplicate fold event")
            adjacency = bundle["adjacency"][bundle_rows]
            observations, contexts = root_observations(bundle["observed"][bundle_rows], adjacency,
                                                       root, reference[fold])
            codes = np.asarray([relation_codes(graph, root) for graph in adjacency])
            mode_records, all_scores, all_masses = {}, {}, {}
            for mode in MODES:
                seed_scores, seed_wrong, seed_mass, per_seed = [], [], [], {}
                for seed in SEEDS:
                    prediction = predictions[fold, seed, mode]
                    mask = prediction["events"] == event_id
                    require(np.array_equal(prediction["rows"][mask], bundle_rows),
                            "Event window pairing mismatch")
                    scores = {m: v[mask] for m, v in prediction["scores"].items()}
                    wrong = prediction["wrong"][mask]
                    mass = np.asarray([np.sum(wrong * (codes == code), axis=1)
                                       for code in range(len(RELATIONS))]).T
                    require(np.allclose(mass.sum(axis=1), 1 - scores["top1"], atol=1e-12, rtol=0),
                            "Relation mass conservation failed")
                    seed_scores.append(scores)
                    seed_wrong.append(wrong)
                    seed_mass.append(mass)
                    per_seed[str(seed)] = metric_mean(scores)
                stacked = {m: np.stack([s[m] for s in seed_scores]) for m in METRICS}
                all_scores[mode] = stacked
                all_masses[mode] = np.stack(seed_mass)
                metrics = metric_mean(stacked)
                compare(metrics, saved_analysis["summary"]["systems"][system]["modes"][mode]["by_incident"][event_id],
                        "analysis/" + event_id + "/" + mode)
                reconciliation["summary_event_metric_checks"] += 1
                services = np.stack(seed_wrong).mean(axis=1).mean(axis=0)
                service_rows = [{"service": manifest["services"][index], "service_index": index,
                                 "mass": float(value)}
                                for index, value in enumerate(services) if value > 0]
                service_rows.sort(key=lambda row: (-row["mass"], row["service"]))
                mode_records[mode] = {
                    **metrics, "per_seed": per_seed,
                    "wrong": wrong_summary(all_masses[mode].mean(axis=1).mean(axis=0), metrics["top1"]),
                    "wrong_services": service_rows, "dominant_wrong_services": service_rows[:3],
                }
            directed, global_ = mode_records["directed"], mode_records["global"]
            delta = {m: directed[m] - global_[m] for m in METRICS}
            prior_comparison = saved_analysis["summary"]["systems"][system]["comparisons"]["directed-global"]["by_incident"][event_id]
            require(prior_comparison["run_id"] == fault["run_id"]
                    and prior_comparison["fold"] == fold, "Prior comparison identity mismatch")
            compare(delta, prior_comparison["difference"], "analysis comparison/" + event_id)
            record = {
                "event_id": event_id, "system": system, "root": root, "service": fault["service"],
                "fault_type": fault["fault_type"], "root_fault_group": fault["root_fault_group"],
                "run_id": fault["run_id"], "fold": fold, "unique_windows": len(bundle_rows),
                "seeds": list(SEEDS), "window_indices": bundle["indices"][bundle_rows].tolist(),
                "windows": [manifest["windows"][int(row)] for row in bundle_rows],
                "modes": mode_records, "delta_directed_global": delta,
                "decision": outcome(delta["top1"]),
                "both_zero": directed["top1"] == 0 and global_["top1"] == 0,
                "both_perfect": directed["top1"] == 1 and global_["top1"] == 1,
                "directed_partial": 0 < directed["top1"] < 1,
                "global_partial": 0 < global_["top1"] < 1,
                "observations": observations,
            }
            records.append(record)
            system_events.append({"record": record, "contexts": contexts,
                                  "scores": all_scores, "relation_mass": all_masses})
        internal_by_system[system] = system_events
        counts = wtl(row["record"]["delta_directed_global"]["top1"] for row in system_events)
        require(counts == EXPECTED_WTL[system]
                == saved_analysis["summary"]["systems"][system]["comparisons"]["directed-global"]["top1_win_tie_loss"],
                "Saved win/tie/loss mismatch")
        reconciliation["top1_win_tie_loss"][system] = counts
    require(len(records) == 117 and len({r["event_id"] for r in records}) == 117, "Missing/duplicate event record")
    summaries = {system: summarize_system(events) for system, events in internal_by_system.items()}
    for system in SYSTEMS:
        for mode in MODES:
            compare(summaries[system]["all"]["modes"][mode]["metrics"],
                    saved_analysis["summary"]["systems"][system]["modes"][mode]["aggregate"],
                    "analysis aggregate/" + system + "/" + mode)
        compare(summaries[system]["all"]["delta_directed_global"],
                saved_analysis["summary"]["systems"][system]["comparisons"]["directed-global"]["mean"],
                "analysis aggregate difference/" + system)
    examples = {}
    for system in SYSTEMS:
        candidates = [r for r in records if r["system"] == system]
        positive = sorted([r for r in candidates if r["decision"] == "improvement"],
                          key=lambda r: (-r["delta_directed_global"]["top1"], r["event_id"]))
        negative = sorted([r for r in candidates if r["decision"] == "worsening"],
                          key=lambda r: (r["delta_directed_global"]["top1"], r["event_id"]))
        zero = sorted([r for r in candidates if r["both_zero"]], key=lambda r: r["event_id"])
        examples[system] = {"largest_positive_delta": positive[0]["event_id"] if positive else None,
                            "largest_negative_delta": negative[0]["event_id"] if negative else None,
                            "first_both_zero_lexicographic": zero[0]["event_id"] if zero else None}
    inputs.recheck()
    return {
        "status": "PASS", "event_count": len(records), "input_hashes": inputs.provenance,
        "software_hashes": {name: file_hash(HERE / name) for name in ("errors.py", "test_errors.py")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "reconciliation": reconciliation, "events": records, "systems": summaries,
        "examples": examples,
        "method": {
            "aggregation": "Within incident: unique windows, then three seeds; between incidents: equal weight.",
            "wrong_probability": "Uniform 1/k over all exact maximum-score ties; root excluded from wrong mass.",
            "conditional_fraction": "Event-equal relation mass divided by event-equal total wrong mass, not mean of per-event ratios.",
            "graph_direction": "Same-window observed CHILD_OF: adjacency rows=caller, columns=callee.",
            "visibility": "(observed.any(axis=2) & fold.reference_mask[None,:,:]).any(axis=-1)",
            "root_neighbors": "Filter neighbors by visibility, not root itself; no edge means no observed connection.",
            "strata": "Presence/absence selects windows within each incident before equal-incident averaging. Full-event decisions retained separately. Mixed incidents overlap; unique windows do not.",
            "reference": "Read only fold-specific reference_mask; no fitting, standardizer, normalized x or values read.",
            "examples": "Per system: largest positive/negative Top1 delta; event_id tie-break; first lexicographic both-zero.",
        },
        "limitations": [
            "Post-hoc description of previously used development incidents, not new validation or causal evidence.",
            "Overlapping CV training sets and only four SN/nine TT recordings limit independent generalization.",
            "Observed same-window CHILD_OF is incomplete topology, not inferred causal fault propagation.",
            "Metric observed bits are a data contract, not proof of collection health; raw/reference/visibility differ.",
            "Partial event credit is not binary solved/failed; both-zero and both-perfect are separate exact flags.",
            "Context strata overlap in incidents; their incident denominators must not be summed.",
            "No original streams, native test/unassigned, RCAEval or RCABench observations were opened.",
            "Hashes bind consumed files to saved manifests plus explicit local frozen snapshot pins, not external authenticity.",
            "No training, inference, checkpoint loading, tuning, feature fitting, installs, downloads or commits.",
        ],
    }


def write_result(path, result):
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def main():
    output = HERE / "errors.json"
    if output.exists():
        raise FileExistsError("Refusing to overwrite diagnostic: " + str(output))
    result = build_diagnostic()
    write_result(output, result)
    print("DIAG_ERRORS_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
