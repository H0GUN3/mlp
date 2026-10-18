"""Ranking and normalization checks without real-data fitting."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.relationship_smoke_20261013.smoke import common_inputs, ranking_metrics
from research.relationship_smoke_20261013.test_data import synthetic_bundle


class SmokeTest(unittest.TestCase):
    def test_ties_and_event_balanced_metrics(self):
        scores = np.asarray([[1., 1., 0.], [0., 2., 1.], [3., 1., 0.]])
        labels = np.array([0, 0, 0], dtype=np.int64)
        events = np.array(["a", "a", "b"])
        result = ranking_metrics(scores, labels, events)
        self.assertAlmostEqual(result["event_balanced"]["top1"], .625)
        self.assertEqual(result["event_balanced"]["top3"], 1)
        self.assertAlmostEqual(result["event_balanced"]["mrr"], (((.75 + 1 / 3) / 2) + 1) / 2)
        self.assertAlmostEqual(result["window"]["top1"], .5)

    def test_invalid_rankings_fail(self):
        scores = np.ones((2, 3))
        with self.assertRaises(ValueError):
            ranking_metrics(scores, np.array([0, 3]), np.array(["a", "b"]))
        with self.assertRaises(ValueError):
            ranking_metrics(scores, np.array([0, 1]), np.array(["", "b"]))
        with self.assertRaises(ValueError):
            ranking_metrics(scores * np.nan, np.array([0, 1]), np.array(["a", "b"]))

    def test_standardizer_train_only_and_four_model_inputs(self):
        arrays, _ = synthetic_bundle()
        stats, tensors, train_rows, val_rows = common_inputs(arrays)
        self.assertEqual(len(tensors), 4)
        self.assertFalse(set(arrays["event_ids"][train_rows]) & set(arrays["event_ids"][val_rows]))
        arrays["x"][arrays["partition"] == "validation"] *= 1000
        changed, _, _, _ = common_inputs(arrays)
        for key in stats:
            np.testing.assert_array_equal(stats[key], changed[key])


if __name__ == "__main__":
    unittest.main()
