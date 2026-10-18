"""Bounded generated-fixture checks; no producer inputs are opened."""
import copy
import json
import math
from pathlib import Path
import tempfile
import time

import numpy as np
import torch

import native_train as trainer
from native_models import NativeReference, joint_loss


def fixture(system):
    nodes = {"SN": 12, "TT": 27}[system]
    count, events = 17, 5
    rng = np.random.RandomState(19)
    arrays = {
        "metrics": rng.normal(size=(count, nodes, 10, 7)),
        "traces": rng.uniform(size=(count, nodes, 10, 2)),
        "logs": rng.uniform(size=(count, nodes, events)),
        "labels": np.array(([-1, 0, nodes - 1] * 6)[:count], dtype=np.int64),
    }
    arrays["metrics"][:, 0, :, 0] = 7
    arrays["traces"][..., 1] = 0
    metadata = {
        "system": system, "services": ["synthetic-service-{}".format(i) for i in range(nodes)],
        "event_count": events,
        "edges": [[i, i] for i in range(nodes)] + [[i, (i + 1) % nodes] for i in range(nodes)],
        "windows": [{"run_id": "synthetic-run", "start": i * 10, "end": i * 10 + 9,
                     "event_id": None if label == -1 else "event-{}".format(label),
                     "root_fault_group": None if label == -1 else "service-{}|fault".format(label)}
                    for i, label in enumerate(arrays["labels"])],
    }
    return arrays, metadata


def rejected(arrays, metadata, system):
    try:
        trainer.validate_inputs(arrays, metadata, system)
    except ValueError:
        return
    raise AssertionError("Malformed fixture was accepted")


def self_check(options):
    started = time.perf_counter()
    workspace = Path(tempfile.mkdtemp(prefix="trainer_self_check_", dir=str(trainer.HERE)))
    checks, runs = [], {}
    for system, kind in (("SN", "eadro"), ("TT", "diagmlp")):
        arrays, metadata = fixture(system)
        trainer.validate_inputs(arrays, metadata, system)
        parts, split = trainer.make_split(len(arrays["labels"]), metadata["windows"])
        assert split["counts"] == {"train": 9, "validation": 2, "test": 5, "unassigned": 1}
        assert split["disjoint_indices"]
        assert split["shared_event_counts"]["train__test"] > 0
        repeated, _ = trainer.make_split(len(arrays["labels"]), metadata["windows"])
        for name in parts:
            np.testing.assert_array_equal(parts[name], repeated[name])
        for count, expected in ((564, (316, 78, 169, 1)), (5814, (3256, 813, 1744, 1))):
            windows = [{"run_id": "accounting-only", "event_id": None}] * count
            _, accounting = trainer.make_split(count, windows)
            assert tuple(accounting["counts"].values()) == expected
        scaler = trainer.fit_scaler(arrays, parts["train"])
        changed = {k: v.copy() for k, v in arrays.items()}
        changed["metrics"][parts["test"]] += 10000
        changed["traces"][parts["test"], :, :, 0] += 10000
        changed["logs"][parts["test"]] += 10000
        unaffected = trainer.fit_scaler(changed, parts["train"])
        for key in scaler:
            np.testing.assert_array_equal(scaler[key], unaffected[key])
        normalized = trainer.scaled_partition(arrays, parts["train"], scaler)
        other_train = trainer.scaled_partition(changed, parts["train"], unaffected)
        for key in normalized:
            np.testing.assert_array_equal(normalized[key], other_train[key])
        np.testing.assert_allclose(
            scaler["metrics_std"][0, 1], arrays["metrics"][parts["train"], 0, :, 1].std(ddof=0))
        assert scaler["metrics_constant"][0, 0]
        assert np.all(scaler["traces_constant"][:, 1])
        assert not np.count_nonzero(normalized["traces"][..., 1])
        assert not np.count_nonzero(normalized["metrics"][:, 0, :, 0])
        np.testing.assert_array_equal(normalized["logs"],
                                      arrays["logs"][parts["train"]].astype(np.float32))
        graph, truth = trainer.graph_batch(normalized, np.array([0, 1]), metadata)
        nodes = len(metadata["services"])
        for key, shape in (("metrics", (2 * nodes, 10, 7)),
                           ("traces", (2 * nodes, 10, 2)), ("logs", (2 * nodes, 5))):
            tensor = graph.ndata[key]
            assert isinstance(tensor, torch.Tensor)
            assert tuple(tensor.shape) == shape
        assert truth.dtype == torch.long and truth.shape == (2,)
        src, dst = graph.edges()
        expected_edges = np.array(metadata["edges"]).T
        np.testing.assert_array_equal(src.numpy()[:len(metadata["edges"])], expected_edges[0])
        np.testing.assert_array_equal(dst.numpy()[:len(metadata["edges"])], expected_edges[1])
        for key in ("metrics", "traces", "logs"):
            broken = {k: v.copy() for k, v in arrays.items()}
            broken[key].flat[0] = np.nan
            rejected(broken, metadata, system)
        broken = {k: v.copy() for k, v in arrays.items()}
        broken["labels"][0] = nodes
        rejected(broken, metadata, system)
        broken = {k: v.copy() for k, v in arrays.items()}
        broken["traces"][..., 1] = 1
        rejected(broken, metadata, system)
        broken = dict(arrays, metrics=arrays["metrics"][:, :, :, :-1])
        rejected(broken, metadata, system)
        bad_meta = copy.deepcopy(metadata)
        bad_meta["windows"][1]["start"] = 0
        bad_meta["windows"][1]["end"] = 9
        rejected(arrays, bad_meta, system)
        bad_meta = copy.deepcopy(metadata)
        bad_meta["edges"][0][0] = nodes
        rejected(arrays, bad_meta, system)
        input_dir = workspace / (system + "_fixture")
        input_dir.mkdir()
        np.savez(input_dir / "raw.npz", **arrays)
        trainer.dump_json(input_dir / "metadata.json", metadata)
        output = workspace / (system + "_" + kind)
        args = trainer.parse_options([
            "--system", system, "--kind", kind, "--seed", str(options.seed),
            "--epochs", "3", "--lr", str(options.lr), "--batch-size", "4",
            "--threads", str(options.threads), "--profile-one-epoch",
            "--input-dir", str(input_dir), "--output-dir", str(output)])
        summary = trainer.run_training(args)
        assert summary["epochs_completed"] == 1 and summary["optimizer_updates"] == 3
        assert summary["test_evaluated"] is False and summary["mode"] == "one_epoch_profile"
        checkpoint = torch.load(output / "checkpoint.pt", map_location="cpu")
        torch.manual_seed(options.seed)
        initial = NativeReference(kind, nodes, 5)
        assert any(not torch.equal(p, checkpoint["state_dict"][name])
                   for name, p in initial.named_parameters())
        runs[kind] = summary
        config = json.loads((output / "config.json").read_text())
        assert config["effective_options"]["epochs"] == 3 and config["effective_epochs"] == 1
        assert config["split_seed"] == 42 and config["parameters"] > 0
        for filename, digest in config["input_hashes"].items():
            assert trainer.file_hash(input_dir / filename) == digest
        history = json.loads((output / "history.json").read_text())
        assert math.isfinite(history[0]["train_batch_weighted_joint_loss"])
        assert history[0]["validation_joint_loss"] == checkpoint["validation_joint_loss"]
        initial.eval()
        roots, detection = initial(graph)
        normal = torch.full_like(truth, -1)
        normal_loss = joint_loss(roots, detection, normal)
        torch.testing.assert_close(normal_loss, .5 * torch.nn.functional.cross_entropy(
            detection, torch.zeros_like(normal)))
        initial.zero_grad()
        normal_loss.backward()
        assert torch.isfinite(normal_loss)
        assert all(p.grad is None or not torch.count_nonzero(p.grad)
                   for p in initial.core.locator.parameters())
        assert any(p.grad is not None and torch.count_nonzero(p.grad)
                   for p in initial.core.detector.parameters())
        single, _ = trainer.graph_batch(normalized, np.array([0]), metadata)
        one_root, one_detection = initial(single)
        assert one_root.shape == (1, nodes) and one_detection.shape == (1, 2)
    checks.extend(["both_kinds_actual_adam_parameter_update", "SN12_TT27_native_shapes_labels_edges",
                   "train_only_scaler_unchanged_by_test_only_features", "source_ddof0_epsilon",
                   "constant_channels_zero_trace_and_unchanged_logs",
                   "seed42_disjoint_partition_remainder_and_shared_events",
                   "normal_only_loss_and_zero_localizer_gradient",
                   "one_epoch_profile_overrides_epochs", "checkpoint_bitwise_validation_replay",
                   "strict_nonfinite_shape_label_edge_provenance_rejection",
                   "saved_effective_options_input_and_artifact_hashes", "single_window_forward"])
    report = {"status": "passed_synthetic_only", "checks": checks, "runs": runs,
              "effective_self_check_options": vars(options), "artifact_directory": str(workspace),
              "seconds": time.perf_counter() - started, "real_data_training": False,
              "marker": "NATIVE_TRAIN_SELF_CHECK PASSED",
              "warning_note": "Native source CUDA autocast warning is intentionally not suppressed."}
    trainer.dump_json(workspace / "self_check.json", report)
    print("SELF_CHECK_EVIDENCE", workspace / "self_check.json", flush=True)
