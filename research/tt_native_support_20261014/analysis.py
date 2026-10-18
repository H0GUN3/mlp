"""Incident-equal native-model diagnostics and frozen conditional experiment gates."""
from collections import defaultdict
import argparse
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.tt_native_support_20261014 import experiment as ex

METRICS = ex.errors.METRICS
FAULTS = ("cpu_load", "network_delay", "network_loss")


def average(metrics):
    if not metrics:
        return None
    return {key: float(np.mean([m[key] for m in metrics])) for key in METRICS}


def collapse(rows, metadata, split):
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        identity = (row["event_id"], row["fold"], row["seed"])
        ex.errors.require(identity not in identities, "Duplicate incident evaluation")
        identities.add(identity)
        groups[row["event_id"]].append(row)
    ex.errors.require(set(groups) == set(metadata["faults"]), "Missing incident")
    events = {}
    for event_id, evaluations in sorted(groups.items()):
        validation_fold = metadata["event_folds"][event_id]
        folds = set(ex.FOLDS) - {validation_fold} if split == "train" else {validation_fold}
        ex.errors.require({(e["fold"], e["seed"]) for e in evaluations}
                          == {(f, s) for f in folds for s in ex.SEEDS}, "Missing fold/seed")
        event = {"fault": metadata["faults"][event_id], "evaluations": evaluations}
        for part in ("all", "zero", "positive"):
            counts = {e[part]["windows"] for e in evaluations}
            ex.errors.require(len(counts) == 1, "Inconsistent window subset")
            event[part] = {
                "windows": next(iter(counts)),
                "metrics": average([e[part]["metrics"] for e in evaluations if e[part]["metrics"] is not None]),
                "per_seed": {
                    str(seed): average([e[part]["metrics"] for e in evaluations
                                       if e["seed"] == seed and e[part]["metrics"] is not None])
                    for seed in ex.SEEDS},
            }
        events[event_id] = event
    return events


def summarize(events, types=FAULTS, part="all", seed=None):
    selected = [event for event in events.values() if event["fault"]["fault_type"] in types
                and event[part]["windows"] > 0]
    values = [e[part]["metrics"] if seed is None else e[part]["per_seed"][str(seed)] for e in selected]
    return {"events": len(selected), "windows": sum(e[part]["windows"] for e in selected),
            "metrics": average(values)}


def root_subset_scores(logits, labels, event_ids, counts, fold, seed):
    faulty = labels >= 0
    score, _, _, _ = ex.errors.ranking(logits[faulty], labels[faulty])
    events, roots = event_ids[faulty], labels[faulty]
    support = counts[faulty][np.arange(len(roots)), roots]
    records = []
    for event in sorted(set(events)):
        chosen = events == event
        record = {"event_id": str(event), "fold": fold, "seed": seed}
        for part, mask in (("all", chosen), ("zero", chosen & (support == 0)),
                           ("positive", chosen & (support > 0))):
            record[part] = {
                "windows": int(mask.sum()),
                "metrics": {m: float(v[mask].mean()) for m, v in score.items()} if mask.any() else None,
            }
        records.append(record)
    return records


def baseline_gate(reports, events):
    network = ("network_delay", "network_loss")
    at_cap = [dict(fold=r["fold"], seed=r["seed"], epoch=r["best_epoch"])
              for r in reports if r["kind"] == "diagmlp" and r["selected_at_cap"]]
    overall = summarize(events, network)
    support = {fault: {part: summarize(events, (fault,), part) for part in ("zero", "positive")}
               for fault in network}
    deltas = {}
    for seed in ex.SEEDS:
        absent = summarize(events, network, "zero", seed)["metrics"]
        present = summarize(events, network, "positive", seed)["metrics"]
        deltas[str(seed)] = present["top1"] - absent["top1"] if present is not None and absent is not None else None
    coverage = all(v["events"] >= 5 for by_part in support.values() for v in by_part.values())
    checks = {
        "no_diagmlp_selected_at_epoch_cap": not at_cap,
        "network_top1_at_most_95_percent": overall["metrics"] is not None and overall["metrics"]["top1"] <= .95,
        "both_support_groups_at_least_five_events_each_type": coverage,
        "positive_minus_zero_at_least_5pp_in_two_seeds":
            sum(v is not None and v >= .05 for v in deltas.values()) >= 2,
    }
    return {
        "allow_next_stage": all(checks.values()), "checks": checks, "at_cap": at_cap,
        "network": overall, "support_by_type": support, "per_seed_support_delta": deltas,
        "interpretation": "Exploratory association gate, not causal or significance evidence; subgroup composition may differ.",
    }


def count_gate(base, proposed):
    base_all, prop_all = summarize(base), summarize(proposed)
    base_cpu, prop_cpu = summarize(base, ("cpu_load",)), summarize(proposed, ("cpu_load",))
    overall = prop_all["metrics"]["top1"] - base_all["metrics"]["top1"]
    cpu = prop_cpu["metrics"]["top1"] - base_cpu["metrics"]["top1"]
    seeds = {str(seed): summarize(proposed, seed=seed)["metrics"]["top1"]
             - summarize(base, seed=seed)["metrics"]["top1"] for seed in ex.SEEDS}
    checks = {"overall_top1_improvement_at_least_2pp": overall >= .02,
              "positive_in_at_least_two_seeds": sum(v > 0 for v in seeds.values()) >= 2,
              "cpu_decline_at_most_1pp": cpu >= -.01}
    return {"allow_next_stage": all(checks.values()), "checks": checks,
            "overall_top1_difference": overall, "cpu_top1_difference": cpu,
            "per_seed_top1_difference": seeds,
            "interpretation": "Prespecified exploratory engineering threshold; not new-data efficacy proof."}


def execute(stage):
    stages = {"baseline": ("baseline",), "count": ("baseline", "count"), "zero": ("baseline", "count", "zero")}
    if stage not in stages:
        raise ValueError("Invalid analysis stage")
    arrays, metadata, inputs = ex.load_data()
    provenance = dict(inputs)
    evaluations = defaultdict(list)
    reports = []
    for stage_name in stages[stage]:
        path = HERE / (stage_name + "_runs.json")
        provenance[str(path)] = ex.errors.file_hash(path)
        index = json.loads(path.read_text())
        kinds = {"baseline": ("eadro", "diagmlp"), "count": ("diagmlp_count",),
                 "zero": ("diagmlp_zero_count",)}[stage_name]
        expected = {(f, s, k) for f in ex.FOLDS for s in ex.SEEDS for k in kinds}
        identities = {(r["fold"], r["seed"], r["kind"]) for r in index["runs"]}
        ex.errors.require(index["status"] == "PASS" and identities == expected
                          and len(index["runs"]) == len(expected), "Stage run coverage mismatch")
        for report in index["runs"]:
            fold, seed, kind = report["fold"], report["seed"], report["kind"]
            folder = HERE / "runs" / ("fold_" + str(fold)) / ("seed_" + str(seed)) / kind
            ex.errors.require(str(folder) == report["folder"]
                              and json.loads((folder / "report.json").read_text()) == report,
                              "Stage/report mismatch")
            provenance[str(folder / "report.json")] = ex.errors.file_hash(folder / "report.json")
            for name, digest in report["artifact_hashes"].items():
                ex.errors.check_hash(folder / name, digest)
                provenance[str(folder / name)] = digest
            config = json.loads((folder / "config.json").read_text())
            ex.errors.require(config["input_hashes"] == inputs and config["settings"] == ex.SETTINGS,
                              "Config/input mismatch")
            for filename, digest in config["source_hashes"].items():
                ex.errors.check_hash(filename, digest)
                provenance[filename] = digest
            for split in ("train", "validation"):
                chosen = arrays["fold_ids"] != fold if split == "train" else arrays["fold_ids"] == fold
                rows = np.flatnonzero(chosen)
                with np.load(folder / (split + "_predictions.npz"), allow_pickle=False) as saved:
                    prediction = {key: saved[key] for key in saved.files}
                for key in ("indices", "labels", "event_ids"):
                    ex.errors.require(np.array_equal(prediction[key], arrays[key][rows]), "Prediction row mismatch")
                metrics = ex.incident_metrics(prediction["root_logits"], prediction["labels"], prediction["event_ids"])
                ex.errors.require(metrics == report[split]["ranking"], "Independent event score mismatch")
                records = root_subset_scores(prediction["root_logits"], prediction["labels"],
                                             prediction["event_ids"], arrays["unique_count"][rows], fold, seed)
                evaluations[kind, split].extend(records)
            reports.append(report)
    events, summaries = {}, {}
    for kind in sorted({r["kind"] for r in reports}):
        events[kind], summaries[kind] = {}, {}
        for split in ("train", "validation"):
            collapsed = collapse(evaluations[kind, split], metadata, split)
            events[kind][split] = collapsed
            summaries[kind][split] = {
                "all": summarize(collapsed),
                "network": summarize(collapsed, ("network_delay", "network_loss")),
                "fault_type": {fault: summarize(collapsed, (fault,)) for fault in FAULTS},
                "support": {part: summarize(collapsed, part=part) for part in ("zero", "positive")},
                "per_seed": {str(seed): summarize(collapsed, seed=seed) for seed in ex.SEEDS},
            }
        kind_reports = [r for r in reports if r["kind"] == kind]
        summaries[kind]["cost"] = {
            "parameters": sorted({r["parameters"] for r in kind_reports}),
            "sum_fit_validation_seconds": sum(r["fit_validation_seconds"] for r in kind_reports),
            "median_validation_inference_with_graph_seconds":
                float(np.median([r["validation"]["inference_with_graph_seconds"] for r in kind_reports])),
            "max_process_peak_mib": max(r["peak_process_mib"] for r in kind_reports),
            "best_epochs": [r["best_epoch"] for r in kind_reports],
        }
    gate = None
    if stage == "baseline":
        gate = baseline_gate(reports, events["diagmlp"]["validation"])
    elif stage == "count":
        gate = count_gate(events["diagmlp"]["validation"], events["diagmlp_count"]["validation"])
    for path, digest in provenance.items():
        ex.errors.check_hash(path, digest)
    result = {"status": "PASS", "stage": stage, "run_count": len(reports),
              "summaries": summaries, "events": events, "gate": gate,
              "input_hashes": provenance,
              "source_hashes": {name: ex.errors.file_hash(HERE / name) for name in ("analysis.py", "test_analysis.py")},
              "limits": [
                  "Reused development data and validation checkpoint selection, not a fresh final test.",
                  "Support subgroups can share incidents and differ in root/type/recording composition.",
                  "Three seeds do not multiply independent incident count; no significance claim.",
                  "Inference timings include graph construction, exclude already-reported preparation; concurrent-fit conditions.",
              ]}
    ex.write_json(HERE / (stage + "_analysis.json"), result)
    if gate is not None:
        gate.update({"protocol_sha256": ex.errors.file_hash(HERE / "PROTOCOL.md"),
                     "baseline_runs_sha256": ex.errors.file_hash(HERE / "baseline_runs.json")})
        if stage == "count":
            gate["count_runs_sha256"] = ex.errors.file_hash(HERE / "count_runs.json")
        ex.write_json(HERE / ("gate.json" if stage == "baseline" else "count_gate.json"), gate)
    print("NATIVE_ANALYSIS_PASS", stage, "runs", len(reports),
          "allow_next", gate["allow_next_stage"] if gate else None, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("baseline", "count", "zero"))
    execute(parser.parse_args().stage)
