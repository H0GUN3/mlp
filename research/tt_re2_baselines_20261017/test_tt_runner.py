import unittest
import tempfile
from pathlib import Path

import numpy as np
import torch

from tt_runner import (NativeReference, common_initial_hash, dump, fit_scaler, make_data,
                       original_split, score, selected_positions, setup)


class TTContractTests(unittest.TestCase):
    def test_receipt_failure_leaves_no_false_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(TypeError):
                dump(path, {"root": np.int64(0)})
            self.assertFalse(path.exists())
            dump(path, {"root": 0})
            with self.assertRaises(FileExistsError):
                dump(path, {"root": 1})

    def test_original_split_and_protection(self):
        original = original_split(5814)
        allowed = np.concatenate((original["train"], original["validation"]))[::-1].copy()
        positions = selected_positions(allowed)
        for name in positions:
            np.testing.assert_array_equal(allowed[positions[name]], original[name])
        bad = allowed.copy()
        bad[0] = original["test"][0]
        with self.assertRaises(AssertionError):
            selected_positions(bad)
        duplicate = allowed.copy()
        duplicate[0] = duplicate[1]
        with self.assertRaises(AssertionError):
            selected_positions(duplicate)

    def test_held_values_never_fit_scaler(self):
        rng = np.random.RandomState(7)
        arrays = {"metrics": rng.randn(6, 2, 10, 7),
                  "traces": rng.randn(6, 2, 10, 2),
                  "logs": rng.rand(6, 2, 3), "labels": np.array([0, 1, -1, 0, 1, -1])}
        arrays["traces"][..., 1] = 0
        parts = {"train": np.array([0, 1, 2]), "validation": np.array([3, 4, 5])}
        stats, data = make_data(arrays, parts)
        arrays["metrics"][3:] += 1e9
        arrays["traces"][3:, :, :, 0] += 1e9
        after, changed = make_data(arrays, parts)
        for key in stats:
            np.testing.assert_array_equal(stats[key], after[key])
        np.testing.assert_array_equal(data["train"]["metrics"], changed["train"]["metrics"])
        np.testing.assert_array_equal(data["train"]["traces"], changed["train"]["traces"])

    def test_conditional_gated_and_normal_denominators(self):
        root = torch.zeros(3, 27)
        detection = torch.tensor([[0., 2.], [2., 0.], [2., 0.]])
        labels = torch.tensor([0, 1, -1])
        values = score(root, detection, labels)
        self.assertEqual(values["fault_windows"], 2)
        self.assertEqual(values["conditional_top1"], 1 / 27)
        self.assertEqual(values["conditional_top3"], 3 / 27)
        self.assertEqual(values["end_to_end_top1"], 1 / 54)
        self.assertEqual(values["tp"], 1)
        self.assertEqual(values["tn"], 1)
        self.assertEqual(values["fn"], 1)
        normal = score(root[2:], detection[2:], labels[2:])
        self.assertIsNone(normal["conditional_top3"])
        self.assertIsNone(normal["root_window_nll"])

    def test_common_initial_and_batch_order(self):
        setup(11)
        left = common_initial_hash(NativeReference("eadro", 27, 60))
        setup(11)
        right = common_initial_hash(NativeReference("diagmlp", 27, 60))
        self.assertEqual(left, right)
        np.testing.assert_array_equal(np.random.RandomState(11).permutation(3256),
                                      np.random.RandomState(11).permutation(3256))

    def test_source_constant_channel_policy(self):
        arrays = {"metrics": np.full((4, 2, 10, 7), 2.),
                  "traces": np.zeros((4, 2, 10, 2))}
        stats = fit_scaler(arrays, np.array([0, 1]))
        self.assertTrue(stats["metrics_constant"].all())
        self.assertTrue((stats["metrics_std"] == 0).all())


if __name__ == "__main__":
    unittest.main()
