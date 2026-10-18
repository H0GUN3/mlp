"""Read-only SN diagnosis: saved predictions, allowed inputs, and training logs."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "sn_corrected_20261017"
TYPES = ("cpu_load", "network_delay", "network_loss")
PARTS = ("train", "validation", "evaluation")


def log_probabilities(logits):
    shifted = logits.astype(np.float64) - logits.max(axis=1, keepdims=True)
    return shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))


def pool(logp):
    peak = logp.max(axis=0)
    return peak + np.log(np.exp(logp - peak).mean(axis=0))


def credit(scores, root, k=1):
    above = int(np.sum(scores > scores[root]))
    ties = int(np.sum(scores == scores[root]))
    return min(max(k - above, 0), ties) / ties


def self_check():
    assert credit(np.zeros(12), 0) == 1 / 12
    assert credit(np.zeros(12), 0, 3) == 3 / 12
    assert credit(np.array([2., 1., 0.]), 1) == 0
    assert credit(np.array([2., 1., 0.]), 1, 3) == 1
    p = log_probabilities(np.array([[10000., -10000.], [0., 0.]]))
    np.testing.assert_allclose(np.exp(pool(p)), [.75, .25])
    assert np.isfinite(p).all()


def analyze():
    hashes = {}

    def digest(path):
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[str(path)] = value
        return value

    def document(path):
        digest(path)
        return json.loads(path.read_text())

    def archive(path):
        digest(path)
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}

    meta = document(SOURCE / "input_manifest.json")
    recorded = document(SOURCE / "evaluation.json")
    arrays = archive(SOURCE / "inputs.npz")
    assert digest(SOURCE / "inputs.npz") == meta["input_npz_sha256"]
    assert len(arrays["labels"]) == 394
    assert int(np.sum(arrays["labels"] >= 0)) == 325
    services = meta["services"]
    faults = meta["faults"]
    assert len(faults) == 36 and len(services) == 12
    local = {int(v): i for i, v in enumerate(arrays["indices"])}
    assert len(local) == 394
    runs = [r for r in recorded["runs"] if r["kind"] == "diagmlp"]
    assert {(r["rotation"], r["seed"]) for r in runs} == {
        (f, s) for f in range(3) for s in (11, 23, 37)}
    event_rows, window_rows, learning, ranges, cpu_rows = [], [], [], [], []
    max_pool_difference = 0.
    files_checked = 0
    for run in runs:
        rotation, seed = run["rotation"], run["seed"]
        folder = SOURCE / "runs" / f"rotation_{rotation}/diagmlp/seed_{seed}"
        config = document(folder / "config.json")
        stats = archive(folder / "scaler.npz")
        assert digest(folder / "scaler.npz") == config["scaler_sha256"]
        assert config["input_npz_sha256"] == meta["input_npz_sha256"]
        for path, expected in config["source_hashes"].items():
            assert digest(Path(path)) == expected, path
        history = document(folder / "history_200.json")
        epoch_path = folder / "epochs_200.jsonl"
        digest(epoch_path)
        epochs = [json.loads(line) for line in epoch_path.read_text().splitlines()]
        stage = document(folder / "stage_200.json")
        assert stage["config_sha256"] == digest(folder / "config.json")
        assert stage["history_sha256"] == digest(folder / "history_200.json")
        assert history == epochs and [h["epoch"] for h in history] == list(range(1, 201))
        selected = min(history, key=lambda h: h["validation_event_nll"])
        assert selected["epoch"] == run["selected_epoch"] == stage["best_epoch"]
        assert sum(h["updates"] for h in history) == stage["updates"]
        learning.append({
            "rotation": rotation, "seed": seed, "selected_epoch": selected["epoch"],
            "selected_train_joint": selected["train_online_joint_loss"],
            "final_train_joint": history[-1]["train_online_joint_loss"],
            "selected_validation_event_nll": selected["validation_event_nll"],
            "final_validation_event_nll": history[-1]["validation_event_nll"],
        })
        train_indices = config["indices"]["train"]
        train_types = {
            e["root"]: faults[e["event_id"]]["fault_type"]
            for e in run["parts"]["train"]["events"]}
        assert len(train_types) == 12 and sorted(Counter(train_types.values()).values()) == [4, 4, 4]
        event_sets = [{e["event_id"] for e in run["parts"][p]["events"]} for p in PARTS]
        assert all(len(s) == 12 for s in event_sets)
        assert len(set.union(*event_sets)) == 36
        for modality in ("metrics", "traces"):
            raw_train = arrays[modality][train_indices]
            mean = raw_train.mean(axis=(0, 2))
            std = raw_train.std(axis=(0, 2))
            constant = np.all(raw_train == raw_train[:1, :, :1, :], axis=(0, 2))
            mean[constant] = raw_train[0, :, 0, :][constant]
            std[constant] = 0
            np.testing.assert_array_equal(mean, stats[modality + "_mean"])
            np.testing.assert_array_equal(std, stats[modality + "_std"])
        for part in PARTS:
            path = SOURCE / "evaluation" / f"r{rotation}_diagmlp_s{seed}_{part}.npz"
            pred = archive(path)
            assert digest(path) == run["prediction_sha256"][path.name]
            indices = np.array([local[int(v)] for v in pred["indices"]])
            np.testing.assert_array_equal(indices, config["indices"][part])
            np.testing.assert_array_equal(pred["labels"], arrays["labels"][indices])
            np.testing.assert_array_equal(pred["event_ids"], arrays["event_ids"][indices])
            assert np.isfinite(pred["root_logits"]).all()
            logp = log_probabilities(pred["root_logits"])
            zmax = np.zeros(len(indices))
            rootz = np.zeros(len(indices))
            outside = np.zeros(len(indices), dtype=bool)
            normalized = {}
            for modality in ("metrics", "traces"):
                raw = arrays[modality][indices]
                train = arrays[modality][train_indices]
                z = (raw - stats[modality + "_mean"][None, :, None, :]) / (
                    stats[modality + "_std"][None, :, None, :] + 1e-8)
                normalized[modality] = z
                zmax = np.maximum(zmax, np.abs(z).max(axis=(1, 2, 3)))
                for j, root in enumerate(pred["labels"]):
                    if root >= 0:
                        rootz[j] = max(rootz[j], float(np.abs(z[j, root]).max()))
                        outside[j] |= bool(np.any(
                            (raw[j, root] < train[:, root].min(axis=(0, 1))) |
                            (raw[j, root] > train[:, root].max(axis=(0, 1)))))
            if seed == 11:
                ranges.append({"rotation": rotation, "part": part,
                               "max_abs_z": float(zmax.max()),
                               "median_window_max_abs_z": float(np.median(zmax))})
            for event in run["parts"][part]["events"]:
                mask = pred["event_ids"] == event["event_id"]
                root = event["root"]
                assert int(mask.sum()) == event["windows"]
                assert np.all(pred["labels"][mask] == root)
                pooled = pool(logp[mask])
                difference = float(np.max(np.abs(pooled - event["log_probabilities"])))
                max_pool_difference = max(max_pool_difference, difference)
                np.testing.assert_allclose(pooled, event["log_probabilities"], atol=1e-12, rtol=0)
                assert credit(pooled, root) == event["top1"]
                assert credit(pooled, root, 3) == event["top3"]
                assert int(np.sum(pooled == pooled.max())) == 1
                prediction = int(pooled.argmax())
                fault_type = faults[event["event_id"]]["fault_type"]
                event_rows.append({
                    "rotation": rotation, "seed": seed, "part": part,
                    "event": event["event_id"], "type": fault_type,
                    "root": root, "prediction": prediction, "top1": credit(pooled, root),
                    "top3": credit(pooled, root, 3),
                    "root_train_type": train_types[root],
                    "prediction_train_type": train_types[prediction],
                })
            for j, root in enumerate(pred["labels"]):
                if root < 0:
                    continue
                event_id = str(pred["event_ids"][j])
                fault_type = faults[event_id]["fault_type"]
                window_rows.append({
                    "rotation": rotation, "seed": seed, "part": part,
                    "original_index": int(pred["indices"][j]), "event": event_id,
                    "type": fault_type, "root": int(root),
                    "prediction": int(logp[j].argmax()),
                    "top1": credit(logp[j], root), "nll": float(-logp[j, root]),
                    "root_outside_train": bool(outside[j]),
                    "root_max_abs_z": float(rootz[j]), "max_abs_z": float(zmax[j]),
                })
                if part == "evaluation" and seed == 11 and fault_type == "cpu_load":
                    raw_cpu = arrays["metrics"][indices[j], :, :, 1].mean(axis=1)
                    scaled_cpu = normalized["metrics"][j, :, :, 1].mean(axis=1)
                    cpu_rows.append({
                        "event": event_id, "original_index": int(pred["indices"][j]),
                        "raw_root_unique_max": bool(np.all(raw_cpu[root] > np.delete(raw_cpu, root))),
                        "scaled_root_unique_max": bool(np.all(scaled_cpu[root] > np.delete(scaled_cpu, root))),
                    })
            files_checked += 1
    query_events = [e for e in event_rows if e["part"] == "evaluation"]
    query_windows = [w for w in window_rows if w["part"] == "evaluation"]
    assert len(query_events) == 108 and len(query_windows) == 975
    assert len({e["event"] for e in query_events}) == 36
    assert len({w["original_index"] for w in query_windows}) == 325
    scores, confusion, range_groups = {}, {}, {}
    for part in PARTS:
        scores[part] = {}
        for name in ("all",) + TYPES:
            rows = [e for e in event_rows if e["part"] == part and (name == "all" or e["type"] == name)]
            scores[part][name] = {
                "event_seed_evaluations": len(rows),
                "top1": float(np.mean([e["top1"] for e in rows])),
                "top3": float(np.mean([e["top3"] for e in rows])),
            }
    for fault_type in TYPES:
        errors = [e for e in query_events if e["type"] == fault_type and e["top1"] == 0]
        confusion[fault_type] = {
            "errors": len(errors),
            "prediction_was_trained_on_same_fault_type": sum(
                e["prediction_train_type"] == fault_type for e in errors),
            "wrong_candidate_train_type_counts": dict(Counter(e["prediction_train_type"] for e in errors)),
        }
        range_groups[fault_type] = {}
        for out in (False, True):
            rows = [w for w in query_windows if w["type"] == fault_type and w["root_outside_train"] == out]
            range_groups[fault_type][str(out)] = {
                "seed_window_evaluations": len(rows),
                "unique_windows": len({w["original_index"] for w in rows}),
                "top1_credit_sum": sum(w["top1"] for w in rows),
            }
    result = {
        "status": "PASS", "source_directory": str(SOURCE),
        "checks": {"runs": len(runs), "prediction_files": files_checked,
                   "history_epochs": 1800, "max_pool_difference": max_pool_difference,
                   "scalers_recomputed_exactly": True, "protected_rows_decoded": 0,
                   "new_training_or_neural_inference": False},
        "scores": scores, "learning": learning, "normalization_ranges": ranges,
        "query_wrong_candidate_training_type": confusion,
        "root_range_groups": range_groups,
        "cpu_signal": {
            "unique_windows": len(cpu_rows),
            "raw_root_unique_max": sum(r["raw_root_unique_max"] for r in cpu_rows),
            "scaled_root_unique_max": sum(r["scaled_root_unique_max"] for r in cpu_rows),
            "unique_events": len({r["event"] for r in cpu_rows})},
        "query_root_fault_combination_unseen_count": sum(
            e["root_train_type"] != e["type"] for e in query_events),
        "query_event_seed_evaluations": query_events,
        "largest_query_window_loss": max(query_windows, key=lambda w: w["nll"]),
        "source_sha256": hashes,
    }
    for path, expected in list(hashes.items()):
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected
    return result


if __name__ == "__main__":
    self_check()
    result = analyze()
    saved = Path(__file__).with_name("RESULTS.json")
    assert result == json.loads(saved.read_text())
    print("DIAGMLP_FAILURE_CHECK_PASS", result["checks"], result["cpu_signal"])
