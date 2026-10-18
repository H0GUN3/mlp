"""Synthetic fixtures only: no production artifacts, telemetry, or old checkpoints."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

import research.re2_ob_known_condition_20261018.runner as r


def fixture(train_cases=2, validation_cases=1, nodes=3):
    cases = train_cases + validation_cases
    count = cases * 2
    rng = np.random.RandomState(918)
    metrics = rng.uniform(0, 3, (count, nodes, 10, 8)).astype(np.float32)
    observed = np.ones(metrics.shape, dtype=np.bool_)
    observed[:, 0, :, 0] = False
    metrics[:, 0, :, 0] = np.nan
    observed[0, 1, 0, 2] = False
    metrics[0, 1, 0, 2] = np.nan
    traces = rng.uniform(0, .01, (count, nodes, 10, 2)).astype(np.float32)
    traces[..., 1] = 0
    arrays = {
        "metrics": metrics, "metric_observed": observed, "traces": traces,
        "logs": rng.uniform(.01, .2, (count, nodes, 3)).astype(np.float32),
        "labels": np.array([v for i in range(cases) for v in (-1, i % nodes)], dtype=np.int64),
        "case_ids": np.array(["synthetic_{:02d}".format(i) for i in range(cases) for _ in range(2)]),
        "starts": np.arange(count, dtype=np.int64) * 10 + 10000,
        "partition": np.array(["train"] * (2 * train_cases) +
                              ["validation"] * (2 * validation_cases)),
        "indices": np.arange(count, dtype=np.int64) + 100,
        "edge_pairs": np.array([[i, i] for i in range(nodes)], dtype=np.int64),
    }
    # A held-out observation on an unsupported TRAIN channel must be masked, not fitted.
    metrics[2 * train_cases:, 0, :, 0] = 999.
    observed[2 * train_cases:, 0, :, 0] = True
    meta = {"services": ["synthetic_node_" + str(i) for i in range(nodes)],
            "event_count": 3, "families": list(r.FAMILIES),
            "synthetic_only": True}
    parts = {p: np.flatnonzero(arrays["partition"] == p) for p in r.PARTS}
    return arrays, meta, parts


def prediction(roots, labels, cases, detects=None):
    labels = np.asarray(labels, dtype=np.int64)
    return {"root_logits": np.asarray(roots, dtype=np.float32),
            "detection_logits": np.asarray(
                detects if detects is not None else [[0., 2.]] * len(labels),
                dtype=np.float32),
            "labels": labels, "case_ids": np.asarray(cases),
            "starts": np.arange(len(labels), dtype=np.int64) * 10,
            "indices": np.arange(len(labels), dtype=np.int64),
            "partition": np.full(len(labels), "validation")}


def synthetic_process(root, action):
    """Test-only injection of temp input root, never exposed as a runner CLI option."""
    root = Path(root)
    sources = r.source_hashes()
    with mock.patch.object(r, "HERE", root), mock.patch.object(r, "source_hashes", return_value=sources):
        result = r.fit(11) if action == "fit" else r.verify(11)
    print("SYNTHETIC_PROCESS_PASS", action, os.getpid(), result["status"], flush=True)


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r.setup(11)

    def test_native_forward_tiny_backward_and_determinism(self):
        arrays, meta, parts = fixture()
        _, data, _ = r.prepare_partitions(arrays, parts)
        r.setup(11)
        model = r.model_for(meta)
        initial = r.state_hash(model)
        r.setup(11)
        self.assertEqual(initial, r.state_hash(r.model_for(meta)))
        model.train()
        graph, labels = r.graph_batch(data["train"], np.arange(2), arrays["edge_pairs"])
        root, detection = model(graph)
        self.assertEqual(tuple(root.shape), (2, 3))
        self.assertEqual(tuple(detection.shape), (2, 2))
        before = r.state_hash(model)
        loss = r.joint_loss(root, detection, labels, alpha=.5)
        loss.backward()
        gradients = [p.grad for p in model.parameters() if p.grad is not None]
        self.assertTrue(gradients)
        self.assertTrue(all(bool(torch.isfinite(g).all()) for g in gradients))
        self.assertGreater(sum(g.abs().sum().item() for g in gradients), 0)
        optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=0)
        optimizer.step()
        self.assertNotEqual(before, r.state_hash(model))
        single = r.predict(model, {k: v[:1] for k, v in data["validation"].items()},
                           arrays["edge_pairs"])
        self.assertEqual(single["root_logits"].shape, (1, 3))

    def test_train_only_scaler_formula_and_validation_mutation(self):
        arrays, _, parts = fixture()
        original = {key: value.copy() for key, value in arrays.items()}
        stats, data, report = r.prepare_partitions(arrays, parts)
        train = parts["train"]
        raw = arrays["metrics"].astype(np.float64)
        seen = arrays["metric_observed"][train]
        total = np.where(seen, raw[train], 0).sum(axis=(0, 2))
        counts = seen.sum(axis=(0, 2))
        mean = np.divide(total, counts, out=np.zeros_like(total), where=counts > 0)
        np.testing.assert_array_equal(mean, stats["metric_impute_mean"])
        self.assertEqual(report["unsupported_train_node_channels"], 1)
        self.assertEqual(report["validation_observed_cells_masked_as_unsupported"], 20)
        self.assertTrue((data["validation"]["metrics"][:, 0, :, 0] == 0).all())
        self.assertTrue((data["train"]["traces"][..., 1] == 0).all())
        for key, value in original.items():
            np.testing.assert_array_equal(arrays[key], value)
        shifted = {key: value.copy() for key, value in arrays.items()}
        idx = parts["validation"]
        shifted["metrics"][idx] = 12345.
        shifted["metric_observed"][idx] = True
        shifted["traces"][idx, ..., 0] = 100.
        shifted["logs"][idx] = 999.
        new_stats, new_data, _ = r.prepare_partitions(shifted, parts)
        for key in stats:
            np.testing.assert_array_equal(stats[key], new_stats[key])
        for key in data["train"]:
            np.testing.assert_array_equal(data["train"][key], new_data["train"][key])
        self.assertGreater(np.max(np.abs(new_data["validation"]["metrics"])), 100)
        # Trace and metric scale formula: population std, epsilon, no clipping.
        for key in ("metrics", "traces"):
            raw_values = (np.where(arrays["metric_observed"], raw,
                                  mean[None, :, None, :]) if key == "metrics"
                          else arrays[key].astype(np.float64))
            if key == "metrics":
                raw_values = np.where((counts > 0)[None, :, None, :], raw_values, 0.)
            avg = raw_values[train].mean(axis=(0, 2))
            std = raw_values[train].std(axis=(0, 2), ddof=0)
            np.testing.assert_allclose(stats[key + "_mean"], avg, atol=1e-14)
            np.testing.assert_allclose(stats[key + "_std"], std, atol=1e-14)

    def test_case_equal_not_window_weighted_and_normal_excluded(self):
        p = prediction([[3, 0]] + [[0, 3]] * 3 + [[999, -999]],
                       [0, 0, 0, 0, -1], ["short"] + ["long"] * 3 + ["normal"])
        score = r.score(p)
        self.assertEqual(score["conditional_case"]["top1"], .5)
        self.assertEqual(score["conditional_window"]["top1"], .25)
        self.assertEqual(score["fault_cases"], 2)
        self.assertIsNone(score["cases"]["normal"]["conditional"]["top1"])
        self.assertEqual(len(score["cases"]), 3)
        r.assert_close(r.score(p, independent=True), score)

    def test_tie_expectations_mrr_and_all_candidate_inventory(self):
        p = prediction([[1] * 6, [9, 8, 8, 8, 0, -1], [0, 0, 0, 0, 0, 10]],
                       [5, 2, 5], ["a", "b", "c"],
                       [[1, 1], [0, 1], [0, 1]])
        result = r.score(p)
        a = result["cases"]["a"]["conditional"]
        self.assertAlmostEqual(a["top1"], 1 / 6)
        self.assertAlmostEqual(a["top3"], .5)
        self.assertAlmostEqual(a["mrr"], sum(1 / i for i in range(1, 7)) / 6)
        b = result["cases"]["b"]["conditional"]
        self.assertEqual(b["top1"], 0)
        self.assertAlmostEqual(b["top3"], 2 / 3)
        self.assertAlmostEqual(b["mrr"], (1 / 2 + 1 / 3 + 1 / 4) / 3)
        self.assertEqual(result["cases"]["c"]["conditional"]["top1"], 1)
        self.assertEqual(result["cases"]["a"]["gated"]["top1"], 0)
        self.assertEqual(result["detection"]["fn"], 1)  # argmax tie -> normal
        r.assert_close(r.score(p, independent=True), result)

    def test_all_normal_batch_backward_and_metrics(self):
        roots = torch.tensor([[1., 2., 3.], [3., 1., 0.]], requires_grad=True)
        detects = torch.tensor([[0., 1.], [2., 0.]], requires_grad=True)
        labels = torch.tensor([-1, -1], dtype=torch.long)
        loss = r.joint_loss(roots, detects, labels)
        self.assertTrue(bool(torch.isfinite(loss)))
        loss.backward()
        assert roots.grad is not None and detects.grad is not None
        self.assertTrue(torch.equal(roots.grad, torch.zeros_like(roots)))
        self.assertGreater(detects.grad.abs().sum().item(), 0)
        p = prediction(roots.detach().numpy(), [-1, -1], ["a", "b"],
                       detects.detach().numpy())
        result = r.score(p)
        self.assertIsNone(result["root_nll"])
        self.assertIsNone(result["conditional_case"]["top1"])
        self.assertIsNone(result["conditional_window"]["mrr"])
        self.assertEqual(result["fault_cases"], 0)
        r.assert_close(r.score(p, independent=True), result)

    def test_full_validation_joint_not_batch_joint_average(self):
        p = prediction([[0, 8], [8, 0], [8, 0], [8, 0]],
                       [0, -1, 0, 0], ["a", "a", "b", "b"],
                       [[1, 0], [0, 1], [0, 1], [0, 1]])
        expected = r.joint_loss(torch.from_numpy(p["root_logits"]),
                                torch.from_numpy(p["detection_logits"]),
                                torch.from_numpy(p["labels"])).item()
        batches = [r.full_losses({k: v[start:start + 2] for k, v in p.items()})["joint_loss"]
                   for start in (0, 2)]
        self.assertAlmostEqual(r.full_losses(p)["joint_loss"], expected, places=6)
        self.assertGreater(abs(expected - np.mean(batches)), .5)
        r.assert_close(r.score(p, independent=True), r.score(p))

    def test_earliest_minimum_selection_and_history_budget(self):
        history = [{"epoch": i, "validation_joint_loss": loss}
                   for i, loss in enumerate([3., 1., 2., 1.], 1)]
        self.assertEqual(r.select_epoch(history), 2)
        with self.assertRaises(ValueError):
            r.select_epoch([{"epoch": 1, "validation_joint_loss": float("nan")}])
        with self.assertRaises(ValueError):
            r.validate_history(history, 4)
        with self.assertRaises(ValueError):
            r.validate_history([], 4)

    def test_input_contract_and_rejections(self):
        arrays, meta, _ = fixture()
        parts = r.validate_inputs(arrays, meta, expected_cases=(2, 1))
        self.assertEqual(len(parts["train"]), 4)
        mutations = {
            "protected_partition": lambda a: a["partition"].__setitem__(0, "test"),
            "duplicate_index": lambda a: a["indices"].__setitem__(0, a["indices"][1]),
            "bad_trace": lambda a: a["traces"].__setitem__((0, 0, 0, 1), 1.),
            "bad_observed": lambda a: a["metrics"].__setitem__((0, 1, 1, 1), np.nan),
            "cross_time": lambda a: a["starts"].__setitem__(4, a["starts"][0]),
            "case_overlap": lambda a: a["case_ids"].__setitem__(4, a["case_ids"][0]),
            "bad_label": lambda a: a["labels"].__setitem__(0, 3),
            "missing_loop": lambda a: a.__setitem__("edge_pairs", a["edge_pairs"][:-1]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                bad = {k: v.copy() for k, v in arrays.items()}
                mutate(bad)
                with self.assertRaises(ValueError):
                    r.validate_inputs(bad, meta, expected_cases=(2, 1))
        bad_meta = dict(meta, families=list(reversed(r.FAMILIES)))
        with self.assertRaises(ValueError):
            r.validate_inputs(arrays, bad_meta, expected_cases=(2, 1))
        with self.assertRaises(ValueError):
            r.validate_inputs(arrays, meta)  # production cannot accept tiny fixture counts

    def test_guard_hash_and_exclusive_create(self):
        with tempfile.TemporaryDirectory(prefix="diagmlp_guard_") as temp:
            root = Path(temp)
            good, forbidden = root / "good.json", root / "protected.json"
            r.write_json(good, {"a": 1})
            r.write_json(forbidden, {"sealed": True})
            guard = r.ReadGuard([good])
            self.assertEqual(guard.json(good), {"a": 1})
            expected = hashlib.sha256(b'{\n  "a": 1\n}\n').hexdigest()
            self.assertEqual(guard.digest(good), expected)
            with self.assertRaises(ValueError):
                guard.open(forbidden)
            with self.assertRaises(ValueError):
                guard.open(root / "sub" / ".." / "good.json")
            alias = root / "alias.json"
            alias.symlink_to(forbidden)
            with self.assertRaises(ValueError):
                r.ReadGuard([alias]).open(alias)
            os.link(good, root / "hardlink")
            with self.assertRaises(ValueError):
                guard.open(good)
            with self.assertRaises(FileExistsError):
                r.write_json(good, {"a": 2})
            bundle = root / "fixture.npz"
            r.write_arrays(bundle, {"x": np.array([1])})
            with self.assertRaises(FileExistsError):
                r.write_arrays(bundle, {"x": np.array([2])})
            checkpoint = root / "fixture.pt"
            r.write_checkpoint(checkpoint, {"x": torch.tensor([1])})
            with self.assertRaises(FileExistsError):
                r.write_checkpoint(checkpoint, {})
            with mock.patch.object(r, "HERE", root):
                folder = r.make_run(11)
                self.assertEqual(folder, root / "runs/seed_11")
                with self.assertRaises(FileExistsError):
                    r.make_run(11)
                with self.assertRaises(ValueError):
                    r.run_folder(42)

    def test_cli_fixed_budget_and_choices(self):
        for argv in (["fit"], ["verify"], ["fit", "--seed", "42"],
                     ["fit", "--seed", "11", "--epochs", "1"],
                     ["fit", "--seed", "11", "--input", "/tmp/forbidden"]):
            with self.subTest(argv=argv), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    r.main(argv)
        with mock.patch.object(r, "fit", return_value={"status": "synthetic"}) as fit:
            r.main(["fit", "--seed", "23"])
            fit.assert_called_once_with(23)

    def test_synthetic_fixed_200_epoch_fit_and_separate_replay(self):
        arrays, meta, _ = fixture(48, 24, nodes=2)
        with tempfile.TemporaryDirectory(prefix="diagmlp_synthetic_") as temp:
            root = Path(temp)
            (root / "artifacts").mkdir()
            r.write_json(root / "split.json", {"fixture": "synthetic only, no real split"})
            r.write_arrays(root / "artifacts/bundle.npz", arrays)
            paths = [root / "artifacts/bundle.npz", root / "split.json"]
            guard = r.ReadGuard(paths)
            meta.update(bundle_sha256=guard.digest(paths[0]), split_sha256=guard.digest(paths[1]))
            r.write_json(root / "artifacts/input.json", meta)
            results = {}
            for action in ("fit", "verify"):
                code = ("from research.re2_ob_known_condition_20261018.test_runner "
                        "import synthetic_process; synthetic_process({!r}, {!r})").format(temp, action)
                result = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(r.REPO),
                                        env=dict(os.environ, OMP_NUM_THREADS="2",
                                                 MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2"),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        universal_newlines=True, timeout=1200)
                # Warnings are evidence: always surface, never filter/silence them.
                if result.stderr:
                    print(result.stderr, file=sys.stderr, flush=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                sentinels = [line for line in result.stdout.splitlines()
                             if line.startswith(("RE2_OB_FIT_COMPLETE", "RE2_OB_VERIFY_PASS",
                                                 "SYNTHETIC_PROCESS_PASS"))]
                self.assertEqual(len(sentinels), 2, result.stdout)
                print("SYNTHETIC_CHILD_EXIT", action, result.returncode, *sentinels, flush=True)
                results[action] = result
            folder = root / "runs/seed_11"
            files = [folder / name for name in
                     ("history.json", "summary.json", "verification.json", "config.json")]
            saved_guard = r.ReadGuard(files)
            history = saved_guard.json(files[0])
            summary = saved_guard.json(files[1])
            report = saved_guard.json(files[2])
            config = saved_guard.json(files[3])
            self.assertEqual(len(history), 200)
            self.assertEqual(summary["updates"], 200)
            self.assertEqual(report["predictions_replayed"], 4)
            self.assertNotEqual(report["pid"], report["fit_pid"])
            self.assertEqual(config["optimizer"]["weight_decay"], 0)
            self.assertEqual(config["epochs"], 200)
            self.assertEqual(config["model"]["metric_count"], 8)
            self.assertEqual(report["metrics"]["best"]["validation"]["fault_cases"], 24)
            sources = r.source_hashes()
            with mock.patch.object(r, "HERE", root), mock.patch.object(
                    r, "source_hashes", return_value=sources):
                # Repeat verify refuses overwriting its audit, without any optimizer.
                with mock.patch.object(torch.optim, "Adam", side_effect=AssertionError("optimizer forbidden")):
                    with self.assertRaises(FileExistsError):
                        r.verify(11)
                with self.assertRaises(ValueError):
                    r.fit(11)
                # Replace the expected bundle hash in-memory, not any immutable fixture file.
                original_json = r.ReadGuard.json

                def bad_hash(guard, path):
                    value = original_json(guard, path)
                    if Path(path).name == "input.json":
                        value["bundle_sha256"] = "0" * 64
                    return value

                with mock.patch.object(r.ReadGuard, "json", bad_hash):
                    with self.assertRaisesRegex(ValueError, "bundle_sha256"):
                        r.load_inputs()
                # A mismatching artifact hash must stop before pickle/model loading.
                def bad_run_hash(guard, path):
                    value = original_json(guard, path)
                    if Path(path).name == "summary.json":
                        value["hashes"]["best.pt"] = "0" * 64
                    return value

                with mock.patch.object(r.ReadGuard, "json", bad_run_hash):
                    with self.assertRaisesRegex(ValueError, "Run hash mismatch"):
                        r.verify(11)


if __name__ == "__main__":
    unittest.main()
