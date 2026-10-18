"""Focused synthetic guards; no real model fit or protected observation access."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

import runner


def fixture():
    rng = np.random.RandomState(7)
    traces = rng.normal(size=(8, 12, 10, 2)).astype(np.float32)
    traces[..., 1] = 0
    data = {
        "metrics": rng.normal(size=(8, 12, 10, 7)).astype(np.float32),
        "traces": traces, "logs": np.abs(rng.normal(size=(8, 12, 7))).astype(np.float32),
        "labels": np.array([0, 1, -1, 2, 3, -1, 4, 5], dtype=np.int64),
        "event_ids": np.array(["a", "b", "", "c", "d", "", "e", "f"]),
        "indices": np.arange(8)}
    meta = {"services": list(map(str, range(12))), "edges": [[i, i] for i in range(12)],
            "event_count": 7}
    return data, meta


class RunnerTests(unittest.TestCase):
    def test_rotation_budget_is_isolated_to_six_runs(self):
        rotation_zero = [{"best_epoch": epoch} for epoch in (180, 40, 50, 60, 70, 80)]
        rotation_one = [{"best_epoch": epoch} for epoch in (179, 40, 50, 60, 70, 80)]
        self.assertEqual(runner.rotation_target(rotation_zero), 400)
        self.assertEqual(runner.rotation_target(rotation_one), 200)
        with self.assertRaisesRegex(ValueError, "exactly six"):
            runner.rotation_target(rotation_zero[:5])

    def test_lock_refuses_missing_rotation_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runner, "HERE", Path(directory)):
                with self.assertRaises(FileNotFoundError):
                    runner.lock()
                self.assertFalse((Path(directory) / "budgets.json").exists())
                self.assertFalse((Path(directory) / "selection.lock.json").exists())

    def test_training_only_scaler(self):
        arrays, _ = fixture()
        train = np.arange(5)
        before = runner.fit_scaler(arrays, train)
        data_before = runner.scaled_partition(arrays, train, before)
        changed = {k: v.copy() for k, v in arrays.items()}
        for key in ("metrics", "traces", "logs"):
            changed[key][5:] += 100000
        after = runner.fit_scaler(changed, train)
        for key in before:
            np.testing.assert_array_equal(before[key], after[key])
        data_after = runner.scaled_partition(changed, train, after)
        for key in data_before:
            np.testing.assert_array_equal(data_before[key], data_after[key])

    def test_common_initial_encoder_and_heads(self):
        for seed in runner.SEEDS:
            runner.setup(seed)
            first = runner.common_initial_hash(runner.NativeReference("eadro", 12, 7))
            runner.setup(seed)
            second = runner.common_initial_hash(runner.NativeReference("diagmlp", 12, 7))
            self.assertEqual(first, second)

    def test_resume_equivalence_both_models(self):
        data, meta = fixture()
        for kind in runner.KINDS:
            runner.setup(23)
            model = runner.NativeReference(kind, 12, 7)
            optimizer = torch.optim.Adam(model.parameters(), lr=.001)
            shuffle = np.random.RandomState(23)
            runner.train_epoch(model, optimizer, data, meta, shuffle)
            buffer = io.BytesIO()
            torch.save(runner.snapshot(model, optimizer, shuffle, 1, 1.0, 1, "test"), buffer)
            expected_losses = [runner.train_epoch(model, optimizer, data, meta, shuffle)[0]
                               for _ in range(2)]
            expected = {k: v.clone() for k, v in model.state_dict().items()}
            expected_predictions = runner.predict(model, data, meta)[0]
            runner.setup(23)
            resumed = runner.NativeReference(kind, 12, 7)
            resumed_optimizer = torch.optim.Adam(resumed.parameters(), lr=.001)
            resumed_shuffle = np.random.RandomState(23)
            buffer.seek(0)
            state = torch.load(buffer, map_location="cpu")
            runner.restore(state, resumed, resumed_optimizer, resumed_shuffle)
            actual_losses = [runner.train_epoch(resumed, resumed_optimizer, data, meta, resumed_shuffle)[0]
                             for _ in range(2)]
            self.assertEqual(expected_losses, actual_losses)
            for key, value in resumed.state_dict().items():
                self.assertTrue(torch.equal(expected[key], value), kind + " " + key)
            self.assertTrue(torch.equal(expected_predictions, runner.predict(resumed, data, meta)[0]))

    def test_normal_only_loss_and_single_window(self):
        data, meta = fixture()
        runner.setup(11)
        for kind in runner.KINDS:
            model = runner.NativeReference(kind, 12, 7)
            model.eval()
            graph, _ = runner.graph_batch(data, np.array([0]), meta)
            root, detect = model(graph)
            self.assertEqual(tuple(root.shape), (1, 12))
            loss = runner.joint_loss(root, detect, torch.tensor([-1], dtype=torch.long))
            self.assertTrue(torch.isfinite(loss))
            loss.backward()


if __name__ == "__main__":
    unittest.main(verbosity=2)
