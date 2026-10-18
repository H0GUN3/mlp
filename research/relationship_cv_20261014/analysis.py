"""Pure fixed-epoch CV aggregation; no fitting, artifact reads, or data access."""
from __future__ import annotations

import hashlib
from itertools import product
import json
from math import fsum, isclose, isfinite
from pathlib import Path
from random import Random
from typing import Any

SYSTEMS = ("SN", "TT")
FOLDS = (0, 1, 2)
SEEDS = (11, 23, 37)
MODES = ("local", "global", "directed")
METRICS = ("top1", "top3", "mrr")
BOOTSTRAP_REPS = 5000
BOOTSTRAP_SEED = 20261014
HERE = Path(__file__).resolve().parent


def _mean(rows):
    rows = list(rows)
    return {metric: fsum(row[metric] for row in rows) / len(rows) for metric in METRICS}


def _difference(left, right):
    return {metric: left[metric] - right[metric] for metric in METRICS}


def _validate(reports, faults_by_system):
    if not isinstance(faults_by_system, dict) or set(faults_by_system) != set(SYSTEMS):
        raise ValueError("Expected faults for exactly SN and TT")
    for faults in faults_by_system.values():
        if not isinstance(faults, dict) or not faults:
            raise ValueError("Expected nonempty event metadata")
        for event, fault in faults.items():
            if (not isinstance(event, str) or not event or not isinstance(fault, dict)
                    or not isinstance(fault.get("run_id"), str) or not fault["run_id"]):
                raise ValueError("Each event needs a nonempty string recording run_id")
    if not isinstance(reports, list) or len(reports) != 54:
        raise ValueError("Expected exactly 54 reports")
    expected = set(product(SYSTEMS, FOLDS, SEEDS, MODES))
    runs = {}
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("Each report must be a dict")
        system, fold, seed, mode = (report.get(k) for k in ("system", "fold", "seed", "mode"))
        if (not isinstance(system, str) or not isinstance(mode, str)
                or type(fold) is not int or type(seed) is not int
                or (system, fold, seed, mode) not in expected):
            raise ValueError("Unexpected run key")
        key = (system, fold, seed, mode)
        if key in runs:
            raise ValueError(f"Duplicate run key: {key}")
        seconds = report.get("fit_seconds")
        if (not isinstance(seconds, (int, float)) or isinstance(seconds, bool)
                or not isfinite(seconds) or seconds < 0):
            raise ValueError("fit_seconds must be finite and nonnegative")
        metrics = report.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError("Missing metrics")
        rows = metrics.get("by_incident")
        if not isinstance(rows, dict) or not rows or not set(rows) <= set(faults_by_system[system]):
            raise ValueError("Unexpected or empty event coverage")
        for row in [metrics.get("event_balanced"), *rows.values()]:
            if not isinstance(row, dict) or any(
                type(row.get(m)) not in (int, float) or not isfinite(row[m]) or not 0 <= row[m] <= 1
                for m in METRICS
            ):
                raise ValueError("Ranking metrics must be finite values in [0, 1]")
        if (type(metrics.get("incidents")) is not int or metrics["incidents"] != len(rows)
                or type(metrics.get("windows")) is not int or metrics["windows"] < len(rows)):
            raise ValueError("Invalid window or incident counts")
        if any(not isclose(metrics["event_balanced"][m], value, rel_tol=1e-9, abs_tol=1e-12)
               for m, value in _mean(rows.values()).items()):
            raise ValueError("event_balanced disagrees with by_incident")
        runs[key] = report
    if set(runs) != expected:
        raise ValueError("Missing run keys")
    for system in SYSTEMS:
        for seed, mode in product(SEEDS, MODES):
            seen = set()
            for fold in FOLDS:
                events = set(runs[system, fold, seed, mode]["metrics"]["by_incident"])
                if seen & events:
                    raise ValueError("Event coverage must occur exactly once across folds")
                seen.update(events)
            if seen != set(faults_by_system[system]):
                raise ValueError("Missing event coverage across folds")
        for fold in FOLDS:
            reference = set(runs[system, fold, SEEDS[0], MODES[0]]["metrics"]["by_incident"])
            for seed, mode in product(SEEDS, MODES):
                if set(runs[system, fold, seed, mode]["metrics"]["by_incident"]) != reference:
                    raise ValueError("Paired event sets differ across modes or seeds within a fold")
    return runs


def _cluster_bootstrap(differences, recording_ids):
    recordings = sorted(set(recording_ids.values()))
    clusters = [[differences[event] for event in sorted(differences)
                 if recording_ids[event] == recording] for recording in recordings]
    totals = [{m: fsum(row[m] for row in cluster) for m in METRICS} for cluster in clusters]
    draws = {m: [] for m in METRICS}
    rng = Random(BOOTSTRAP_SEED)
    for _ in range(BOOTSTRAP_REPS):
        selected = rng.choices(range(len(clusters)), k=len(clusters))
        # Retain all incidents and repeated clusters, not equally weighted recording means.
        count = sum(len(clusters[index]) for index in selected)
        for metric in METRICS:
            draws[metric].append(fsum(totals[index][metric] for index in selected) / count)

    def percentile(values, fraction):
        position = (len(values) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return values[lower] + (values[upper] - values[lower]) * (position - lower)

    return {m: {"low": percentile(values, .025), "high": percentile(values, .975)}
            for m, samples in draws.items() for values in [sorted(samples)]}


def summarize(
    reports: list[dict[str, Any]],
    faults_by_system: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Validate all 54 reports and return seed-averaged incident-balanced summaries.

    Raises ValueError for invalid run grids, coverage, pairing, metrics, or metadata.
    Bootstrap intervals are conditional exploratory summaries, not population inference.
    """
    runs = _validate(reports, faults_by_system)
    systems = {}
    consistent = []
    for system in SYSTEMS:
        events = sorted(faults_by_system[system])
        recording_ids = {e: faults_by_system[system][e]["run_id"] for e in events}
        event_folds = {e: fold for fold in FOLDS
                       for e in runs[system, fold, SEEDS[0], MODES[0]]["metrics"]["by_incident"]}
        modes = {}
        for mode in MODES:
            by_incident = {
                e: _mean(runs[system, event_folds[e], seed, mode]["metrics"]["by_incident"][e]
                         for seed in SEEDS) for e in events
            }
            modes[mode] = {
                "aggregate": _mean(by_incident.values()),
                "per_seed": {
                    str(seed): _mean(runs[system, event_folds[e], seed, mode]["metrics"]["by_incident"][e]
                                     for e in events) for seed in SEEDS
                },
                "per_fold": {str(fold): _mean(by_incident[e] for e in events if event_folds[e] == fold)
                             for fold in FOLDS},
                "by_incident": by_incident,
                "fit_seconds": fsum(runs[system, fold, seed, mode]["fit_seconds"]
                                   for fold, seed in product(FOLDS, SEEDS)),
            }
        comparisons = {}
        for baseline in ("global", "local"):
            directed, other = modes["directed"], modes[baseline]
            differences = {e: _difference(directed["by_incident"][e], other["by_incident"][e])
                           for e in events}
            comparisons[f"directed-{baseline}"] = {
                "mean": _mean(differences.values()),
                "per_seed": {str(seed): _difference(directed["per_seed"][str(seed)],
                                                   other["per_seed"][str(seed)]) for seed in SEEDS},
                "per_fold": {str(fold): _difference(directed["per_fold"][str(fold)],
                                                   other["per_fold"][str(fold)]) for fold in FOLDS},
                "ci95": _cluster_bootstrap(differences, recording_ids),
                "top1_win_tie_loss": {
                    "win": sum(row["top1"] > 0 for row in differences.values()),
                    "tie": sum(row["top1"] == 0 for row in differences.values()),
                    "loss": sum(row["top1"] < 0 for row in differences.values()),
                },
                "by_incident": {e: {"run_id": recording_ids[e], "fold": event_folds[e],
                                    "difference": differences[e]} for e in events},
            }
        primary = comparisons["directed-global"]
        consistent.append(
            primary["mean"]["top1"] > 0
            and sum(row["top1"] > 0 for row in primary["per_fold"].values()) >= 2
            and sum(row["top1"] > 0 for row in primary["per_seed"].values()) >= 2
        )
        systems[system] = {
            "incidents": len(events), "recordings": len(set(recording_ids.values())),
            "modes": modes, "comparisons": comparisons,
        }
    return {
        "decision": ("expansion_worth_considering" if all(consistent)
                     else "insufficient_consistent_gain"),
        "bootstrap": {
            "method": "recording_cluster_percentile", "repetitions": BOOTSTRAP_REPS,
            "seed": BOOTSTRAP_SEED, "percentiles": [2.5, 97.5],
            "interpretation": (
                "Exploratory intervals conditional on the small recording clusters "
                "(4 SN / 9 TT in the planned data) and overlapping training sets; "
                "not independent population inference. Seeds are averaged within incidents."
            ),
        },
        "systems": systems,
    }


def main() -> None:
    """Aggregate the parent manifest without depending on replay verification."""
    input_bytes = (HERE / "results" / "runs.json").read_bytes()
    runs = json.loads(input_bytes)
    summary = summarize(runs["reports"], {s: entry["faults"] for s, entry in runs["systems"].items()})
    output = {
        "input_hashes": {
            "runs.json": hashlib.sha256(input_bytes).hexdigest(),
            "analysis.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "summary": summary,
    }
    with (HERE / "results" / "analysis.json").open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print("CV_ANALYSIS_COMPLETE")


if __name__ == "__main__":
    main()
