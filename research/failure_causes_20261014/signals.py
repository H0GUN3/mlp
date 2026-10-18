"""Fixed, non-learning input probes on hash-bound development windows only."""
from pathlib import Path
import json
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.relationship_diagnosis_20261014 import errors
from research.method_mlp_20261013 import features

sys.path.insert(0, str(features.HERE))
from research.method_mlp_20261013 import train

GROUPS = {"cpu": [0, 1, 2], "network_bytes": [5, 6],
          "latency": [7], "span_count": [8], "all": list(range(9))}
STATS = ("reference_median", "reference_scale", "reference_count", "reference_mask",
         "standardizer_mean", "standardizer_std", "standardizer_counts",
         "train_indices", "validation_indices")


def top1(scores, labels):
    errors.require(scores.ndim == 2 and len(scores) > 0
                   and labels.shape == (len(scores),)
                   and np.isfinite(scores).all()
                   and np.all((labels >= 0) & (labels < scores.shape[1])),
                   "Invalid probe scores")
    maxima = scores == scores.max(axis=1, keepdims=True)
    return maxima[np.arange(len(labels)), labels] / maxima.sum(axis=1)


def local_duplicates(x, mask, coverage, labels):
    signature = np.concatenate((np.where(mask, x, 0), mask, coverage), axis=-1)
    equal = (signature == signature[np.arange(len(labels)), labels, None, :]).all(axis=-1)
    return equal.sum(axis=1) - 1


def cancellation(values, observed, reference):
    """Fraction of mean absolute signed-log deviation cancelled by signed averaging."""
    valid = observed & reference["mask"][None, :, None, :]
    safe = np.where(valid, values, reference["median"][None, :, None, :])
    z = (safe - reference["median"][None, :, None, :]) / reference["scale"][None, :, None, :]
    log_z = np.sign(z) * np.log1p(np.abs(z))
    denominator = np.maximum(observed.sum(axis=2), 1)
    absolute = np.abs(log_z).sum(axis=2) / denominator
    signed = np.abs(log_z.sum(axis=2) / denominator)
    loss = np.maximum(absolute - signed, 0) / np.maximum(absolute, 1e-12)
    errors.require(np.all((loss >= 0) & (loss <= 1)), "Invalid cancellation")
    return loss, absolute


def mean_records(records):
    errors.require(bool(records), "Empty event group")
    keys = set(records[0]["measurements"])
    errors.require(all(set(row["measurements"]) == keys for row in records),
                   "Mismatched measurements")
    return {
        "events": len(records), "windows": sum(row["windows"] for row in records),
        "measurements": {key: float(np.mean([r["measurements"][key] for r in records]))
                         for key in sorted(keys)},
    }


def measure(values, observed, reference, x, mask, coverage, normalized, labels,
            directed_credit):
    rows = np.arange(len(labels))
    root_observed = observed[rows, labels].any(axis=1)
    root_reference = reference["mask"][labels]
    duplicates = local_duplicates(normalized, mask, coverage, labels)
    loss, absolute = cancellation(values, observed, reference)
    result = {
        "directed_top1": directed_credit,
        "root_latency_observed": root_observed[:, 7].astype(float),
        "root_latency_reference_missing": (~root_reference[:, 7]).astype(float),
        "root_latency_observed_but_masked": (root_observed[:, 7] & ~root_reference[:, 7]).astype(float),
        "root_latency_usable": mask[rows, labels, 7].astype(float),
        "root_local_duplicate_exists": (duplicates > 0).astype(float),
        "root_local_duplicate_count": duplicates.astype(float),
    }
    for name, channels in GROUPS.items():
        channel_scores = np.where(mask[:, :, channels], np.abs(x[:, :, channels]), 0)
        scores = channel_scores.max(axis=-1)
        credit = top1(scores, labels)
        root_scores = scores[rows, labels]
        root_available = mask[rows, labels][:, channels].any(axis=1)
        result.update({
            name + "_probe_top1": credit,
            name + "_root_available": root_available.astype(float),
            name + "_root_magnitude": root_scores,
            name + "_root_positive": (root_scores > 0).astype(float),
            name + "_root_pairwise_percentile": (
                (scores < root_scores[:, None]).sum(axis=1)
                + .5 * ((scores == root_scores[:, None]).sum(axis=1) - 1)
            ) / (scores.shape[1] - 1),
            name + "_probe_correct_model_wrong_mass": credit * (1 - directed_credit),
            name + "_model_correct_probe_wrong_mass": directed_credit * (1 - credit),
            name + "_root_mean_cancellation": loss[rows, labels][:, channels].mean(axis=1),
            name + "_root_mean_absolute_log_deviation": absolute[rows, labels][:, channels].mean(axis=1),
        })
    errors.require(all(np.isfinite(value).all() for value in result.values()),
                   "Nonfinite measurements")
    return result


def execute():
    started = time.perf_counter()
    inputs = errors.Inputs()
    cv = errors.CV
    runs = inputs.json(cv / "runs.json", errors.SNAPSHOT_HASHES["runs.json"], "frozen CV")
    errors.require(runs["status"] == "PASS" and runs["run_count"] == 54, "Incomplete CV")
    reports = errors.validate_reports(runs["reports"])
    for filename, digest in runs["source_hashes"].items():
        inputs.record(filename, digest, "frozen CV source", ())
    records, systems = [], {}
    replay_count = 0
    for system in errors.SYSTEMS:
        manifest_path = errors.BUNDLES / (system + ".json")
        manifest = inputs.json(manifest_path, runs["input_hashes"][str(manifest_path)], "CV input")
        bundle_path = errors.BUNDLES / (system + ".npz")
        digest = runs["input_hashes"][str(bundle_path)]
        errors.require(manifest["npz_sha256"] == digest, "Manifest/bundle mismatch")
        bundle = inputs.npz(bundle_path, digest, "CV input",
                            errors.BUNDLE_MEMBERS + ("values",))
        errors.validate_bundle(bundle, manifest, system)
        errors.require(np.isfinite(bundle["values"]).all()
                       and bundle["values"].shape == bundle["observed"].shape, "Invalid values")
        system_records = []
        for fold in errors.FOLDS:
            relative = Path(system) / ("fold_" + str(fold)) / "statistics.npz"
            statistics = inputs.npz(cv / relative, runs["artifact_hashes"][str(relative)],
                                    "CV fold statistics", STATS)
            reference = {k: statistics["reference_" + k] for k in ("median", "scale", "count", "mask")}
            standardizer = {k: statistics["standardizer_" + k] for k in ("mean", "std", "counts")}
            val_rows = np.flatnonzero((bundle["fold_ids"] == fold) & (bundle["labels"] >= 0))
            errors.require(np.array_equal(statistics["validation_indices"],
                                          bundle["indices"][bundle["fold_ids"] == fold]),
                           "Validation statistics row mismatch")
            errors.require(np.array_equal(statistics["train_indices"],
                                          bundle["indices"][bundle["fold_ids"] != fold]),
                           "TRAIN statistics row mismatch")
            values, observed = bundle["values"][val_rows], bundle["observed"][val_rows]
            x, mask, coverage = features.window_features(values, observed, reference)
            normalized = train.transform(x, mask, standardizer)
            credits = []
            for seed in errors.SEEDS:
                relative_pred = (Path(system) / ("fold_" + str(fold)) /
                                 ("seed_" + str(seed)) / "directed" / "predictions.npz")
                saved = inputs.npz(cv / relative_pred, runs["artifact_hashes"][str(relative_pred)],
                                   "CV Directed validation", errors.PREDICTION_MEMBERS)
                errors.require(np.array_equal(errors.validate_prediction(saved, bundle, fold), val_rows),
                               "Validation rows changed")
                credit = top1(saved["logits"], saved["labels"])
                report = reports[system, fold, seed, "directed"]
                for event in sorted(set(saved["event_ids"])):
                    actual = float(credit[saved["event_ids"] == event].mean())
                    errors.require(np.isclose(actual, report["metrics"]["by_incident"][event]["top1"],
                                              atol=1e-12, rtol=0), "Saved event score differs")
                credits.append(credit)
                replay_count += 1
            labels = bundle["labels"][val_rows]
            measurements = measure(values, observed, reference, x, mask, coverage, normalized,
                                   labels, np.mean(credits, axis=0))
            events = bundle["event_ids"][val_rows]
            for event in sorted(set(events)):
                selected = events == event
                fault = manifest["faults"][event]
                record = {
                    "system": system, "event_id": event, "fold": fold,
                    "root": fault["root"], "service": fault["service"],
                    "fault_type": fault["fault_type"], "run_id": fault["run_id"],
                    "windows": int(selected.sum()),
                    "indices": bundle["indices"][val_rows][selected].tolist(),
                    "measurements": {key: float(value[selected].mean())
                                     for key, value in measurements.items()},
                }
                system_records.append(record)
                records.append(record)
        errors.require(len(system_records) == (36 if system == "SN" else 81)
                       and len({row["event_id"] for row in system_records}) == len(system_records),
                       "Missing or duplicate events")
        fault_types = sorted({row["fault_type"] for row in system_records})
        systems[system] = {
            "all": mean_records(system_records),
            "fault_types": {fault: mean_records([r for r in system_records if r["fault_type"] == fault])
                            for fault in fault_types},
            "unique_windows": sum(row["windows"] for row in system_records),
            "raw_counts": {
                name: int(round(sum(r["measurements"][name] * r["windows"] for r in system_records)))
                for name in ("root_latency_observed", "root_latency_usable",
                             "root_latency_observed_but_masked", "root_local_duplicate_exists")
            },
        }
        print("SIGNALS_SYSTEM", system, systems[system]["all"]["events"],
              systems[system]["unique_windows"], flush=True)
    errors.require(replay_count == 18 and len(records) == 117, "Incomplete diagnostic")
    inputs.recheck()
    return {
        "status": "PASS", "elapsed_seconds": time.perf_counter() - started,
        "read_scope": "Permitted development bundles, fixed CV statistics and saved predictions only.",
        "no_training": True, "directed_prediction_runs_reconciled": replay_count,
        "event_count": len(records), "systems": systems, "events": records,
        "input_hashes": inputs.provenance,
        "source_hashes": {name: errors.file_hash(HERE / name)
                          for name in ("signals.py", "test_signals.py", "PROTOCOL.md")},
        "method": {
            "aggregation": "windows then seeds within event; equal event weights",
            "probes": GROUPS,
            "score": "max absolute existing signed-log-z mean among group channels; masked=0",
            "ties": "uniform fractional Top1; joint masses use independent tie expectations",
            "cancellation": "mean channel fraction, zero when no deviation; descriptive not causal",
            "limits": "Probes are fixed diagnostic rules, not proof of sufficient information or model superiority.",
        },
    }


if __name__ == "__main__":
    result = execute()
    with (HERE / "signals.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print("SIGNALS_PASS", result["event_count"], flush=True)
