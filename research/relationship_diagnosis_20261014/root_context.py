"""Exclusive, hash-bound OR-union supplement; never rebuild the original diagnostic."""
from __future__ import annotations

from itertools import product
from pathlib import Path
import platform

import numpy as np

if __package__:
    from . import errors
else:
    import errors

HERE = Path(__file__).resolve().parent
ORIGINAL_HASH = "132181cd7dba112566d8bb140085e6a78dc747c4db8fa5bb58e857f275af5e07"
CONTEXTS = ("root_any_raw", "root_any_visible")
BUNDLE_MEMBERS = ("observed", "adjacency", "indices", "labels", "event_ids", "fold_ids")


def union_contexts(contexts):
    return {
        "root_any_raw": contexts["root_in_raw"] | contexts["root_out_raw"],
        "root_any_visible": contexts["root_in_visible"] | contexts["root_out_visible"],
    }


def aggregate(entries):
    """Average each incident's selected windows and seeds, then incidents equally."""
    errors.require(bool(entries), "Empty union stratum")
    per_mode = {
        mode: [errors.metric_mean(event["scores"][mode], mask) for event, mask in entries]
        for mode in errors.MODES
    }
    modes = {
        mode: {metric: float(np.mean([row[metric] for row in rows]))
               for metric in errors.METRICS}
        for mode, rows in per_mode.items()
    }
    windows = sum(int(mask.sum()) for _, mask in entries)
    return {
        "incidents": len(entries),
        "unique_windows": windows,
        "seed_window_decisions_per_mode": len(errors.SEEDS) * windows,
        "modes": modes,
        "delta_directed_global": {
            metric: modes["directed"][metric] - modes["global"][metric]
            for metric in errors.METRICS
        },
        "subset_top1_win_tie_loss": errors.wtl(
            directed["top1"] - global_["top1"]
            for directed, global_ in zip(per_mode["directed"], per_mode["global"])
        ),
    }


def summarize(events):
    result = {}
    for context in CONTEXTS:
        present, absent, overlap = [], [], []
        for event in events:
            mask = event["contexts"][context]
            if mask.any():
                present.append((event, mask))
            if (~mask).any():
                absent.append((event, ~mask))
            if mask.any() and (~mask).any():
                overlap.append(event["record"]["event_id"])
        result[context] = {
            "present": aggregate(present) if present else None,
            "absent": aggregate(absent) if absent else None,
            "overlap_incidents": len(overlap),
            "overlap_event_ids": overlap,
            "unique_windows_disjoint": True,
        }
        errors.require(len(present) + len(absent) - len(overlap) == len(events),
                       "Union incident coverage mismatch")
    return result


def build_supplement():
    inputs = errors.Inputs()
    original = inputs.json(HERE / "errors.json", ORIGINAL_HASH, "immutable diagnostic pin")
    errors.require(original["status"] == "PASS" and original["event_count"] == 117
                   and len(original["events"]) == 117
                   and len({r["event_id"] for r in original["events"]}) == 117,
                   "Incomplete original diagnostic")
    for name, digest in original["software_hashes"].items():
        errors.require(name in ("errors.py", "test_errors.py"), "Unexpected original software")
        inputs.record(HERE / name, digest, "errors.json/software_hashes", ())

    def load_npz(path, members):
        entry = original["input_hashes"][str(path)]
        return inputs.npz(path, entry["sha256"], "immutable errors.json/input_hashes", members)

    records, systems = [], {}
    for system in errors.SYSTEMS:
        bundle = load_npz(errors.BUNDLES / (system + ".npz"), BUNDLE_MEMBERS)
        indices = bundle["indices"]
        nodes = bundle["adjacency"].shape[1]
        errors.require(indices.ndim == 1 and indices.dtype.kind in "iu"
                       and len(np.unique(indices)) == len(indices)
                       and bundle["labels"].shape == indices.shape
                       and bundle["labels"].dtype.kind in "iu"
                       and np.all((bundle["labels"] >= -1) & (bundle["labels"] < nodes))
                       and bundle["observed"].shape == (len(indices), nodes, 10, 9)
                       and bundle["observed"].dtype == np.bool_
                       and bundle["adjacency"].shape == (len(indices), nodes, nodes)
                       and bundle["adjacency"].dtype == np.bool_
                       and not np.diagonal(bundle["adjacency"], axis1=1, axis2=2).any(),
                       "Invalid supplement bundle")
        for name in ("event_ids", "fold_ids"):
            errors.require(bundle[name].shape == indices.shape, "Invalid row metadata")
        errors.require(bundle["fold_ids"].dtype.kind in "iu"
                       and np.isin(bundle["fold_ids"], errors.FOLDS).all(), "Invalid folds")
        source_records = [r for r in original["events"] if r["system"] == system]
        errors.require(len(source_records) == (36 if system == "SN" else 81)
                       and set(bundle["event_ids"][bundle["labels"] >= 0])
                       == {r["event_id"] for r in source_records}, "Incident coverage mismatch")
        reference, predictions = {}, {}
        for fold in errors.FOLDS:
            base = errors.CV / system / ("fold_" + str(fold))
            reference[fold] = load_npz(base / "statistics.npz", ("reference_mask",))["reference_mask"]
            for seed, mode in product(errors.SEEDS, errors.MODES):
                path = base / ("seed_" + str(seed)) / mode / "predictions.npz"
                saved = load_npz(path, errors.PREDICTION_MEMBERS)
                rows = errors.validate_prediction(saved, bundle, fold)
                scores = errors.ranking(saved["logits"], saved["labels"])[0]
                predictions[fold, seed, mode] = (rows, scores)
        events = []
        for record in source_records:
            event_id, fold, root = record["event_id"], record["fold"], record["root"]
            rows = np.flatnonzero(bundle["event_ids"] == event_id)
            errors.require(len(rows) == record["unique_windows"]
                           and np.array_equal(indices[rows], record["window_indices"])
                           and np.all(bundle["labels"][rows] == root)
                           and np.all(bundle["fold_ids"][rows] == fold),
                           "Original event pairing mismatch")
            observations, directions = errors.root_observations(
                bundle["observed"][rows], bundle["adjacency"][rows], root, reference[fold])
            errors.require(observations == record["observations"], "Original observation mismatch")
            contexts = union_contexts(directions)
            scores = {}
            for mode in errors.MODES:
                per_seed = []
                for seed in errors.SEEDS:
                    prediction_rows, prediction_scores = predictions[fold, seed, mode]
                    mask = bundle["event_ids"][prediction_rows] == event_id
                    errors.require(np.array_equal(prediction_rows[mask], rows),
                                   "Union prediction pairing mismatch")
                    chosen = {metric: value[mask] for metric, value in prediction_scores.items()}
                    errors.compare(errors.metric_mean(chosen),
                                   record["modes"][mode]["per_seed"][str(seed)], "original seed")
                    per_seed.append(chosen)
                scores[mode] = {metric: np.stack([s[metric] for s in per_seed])
                                for metric in errors.METRICS}
                errors.compare(errors.metric_mean(scores[mode]), record["modes"][mode],
                               "original event")
            events.append({"record": record, "contexts": contexts, "scores": scores})
            records.append({
                **{name: record[name] for name in
                   ("system", "event_id", "root", "service", "fault_type", "run_id", "fold",
                    "unique_windows", "window_indices")},
                "contexts": {
                    context: {
                        "present_windows": int(mask.sum()),
                        "absent_windows": int((~mask).sum()),
                        "present_fraction": float(mask.mean()),
                        "present_window_indices": indices[rows][mask].tolist(),
                        "both_direction_windows": int((
                            directions["root_in_" + kind] & directions["root_out_" + kind]
                        ).sum()),
                    }
                    for context, kind in zip(CONTEXTS, ("raw", "visible"))
                    for mask in (contexts[context],)
                },
            })
        systems[system] = summarize(events)
    inputs.recheck()
    return {
        "status": "PASS", "event_count": len(records), "events": records, "systems": systems,
        "original_errors_sha256": ORIGINAL_HASH, "input_hashes": inputs.provenance,
        "software_hashes": {name: errors.file_hash(HERE / name) for name in
                           ("root_context.py", "test_root_context.py", "errors.py", "test_errors.py")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "method": {
            "root_any_raw": "root_in_raw | root_out_raw (same-window boolean OR)",
            "root_any_visible": "root_in_visible | root_out_visible (same-window boolean OR)",
            "visibility": "Neighbor observed.any(time) & fold reference_mask; root visibility is not required.",
            "aggregation": "Selected unique windows then three seeds within event; equal events within stratum.",
            "strata": "An event can be present and absent on different windows; event counts overlap, windows do not.",
            "scope": "Only two union contexts. Original nine contexts and original diagnostic unchanged.",
        },
        "limitations": original["limitations"],
    }


def main():
    output = HERE / "errors_root_context.json"
    if output.exists():
        raise FileExistsError("Refusing to overwrite union supplement: " + str(output))
    errors.write_result(output, build_supplement())
    print("DIAG_ROOT_CONTEXT_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
