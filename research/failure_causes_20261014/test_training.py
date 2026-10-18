"""Focused synthetic checks; no checkpoint or observation reads."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import training


class TrainingTests(unittest.TestCase):
    def test_exact_ties_and_cross_entropy(self):
        scores, target_ties, maxima = training.window_scores(
            np.zeros((1, 4), dtype=np.float32), np.array([2], dtype=np.int64))
        self.assertEqual(target_ties, 1)
        self.assertEqual(maxima, 1)
        self.assertEqual(scores["top1"][0], .25)
        self.assertEqual(scores["top3"][0], .75)
        self.assertAlmostEqual(scores["mrr"][0], (1 + 1 / 2 + 1 / 3 + 1 / 4) / 4)
        self.assertAlmostEqual(scores["ce"][0], math.log(4))

    def test_stable_ce_and_nonleading_tie(self):
        logits = np.array([[10001., 10000., 10000., 9999.]], dtype=np.float32)
        labels = np.array([1], dtype=np.int64)
        scores, _, maxima = training.window_scores(logits, labels)
        self.assertEqual(scores["top1"][0], 0)
        self.assertEqual(scores["top3"][0], 1)
        self.assertAlmostEqual(scores["mrr"][0], (1 / 2 + 1 / 3) / 2)
        self.assertEqual(maxima, 0)
        self.assertAlmostEqual(scores["ce"][0], math.log(math.e + 2 + 1 / math.e))
        shifted, _, _ = training.window_scores(logits - 10000, labels)
        np.testing.assert_array_equal(scores["ce"], shifted["ce"])
        with self.assertRaises(ValueError):
            training.window_scores(np.array([[float("nan"), 0.]]), labels)

    def test_window_then_fold_seed_then_incident_equal(self):
        rows = []
        for fold in (0, 1):
            for seed in (11, 23, 37):
                window_scores = np.array([0., 1., 0., 1.]) if fold == 0 else np.ones(4)
                value = float(window_scores.mean())
                rows.append({"event_id": "A", "fold": fold, "seed": seed, "window_count": 4,
                             "metrics": dict.fromkeys(training.METRICS, value)})
        rows.append({"event_id": "B", "fold": 2, "seed": 11, "window_count": 1,
                     "metrics": dict.fromkeys(training.METRICS, 0.)})
        collapsed = training.collapse_evaluations(rows)
        self.assertEqual(collapsed["A"]["metrics"]["top1"], .75)
        summary = training.group_mean(list(collapsed.values()))
        self.assertEqual(summary["metrics"]["top1"], .375)
        self.assertEqual(summary["independent_event_count"], 2)
        self.assertEqual(summary["unique_windows"], 5)
        self.assertEqual(collapsed["A"]["evaluation_count"], 6)
        with self.assertRaises(ValueError):
            training.collapse_evaluations(rows + rows[:1])
        with self.assertRaises(ValueError):
            training.group_mean([])

    def test_history_deltas_are_not_inference_ce(self):
        row = {"epoch1_ce": 3., "epoch4_ce": 2., "epoch5_ce": 1.5,
               "delta_1_to_5": -1.5, "delta_4_to_5": -.5,
               "fractional_drop_1_to_5": .5, "fractional_drop_4_to_5": .25,
               "optimizer_steps": 35}
        summary = training.history_summary([row])
        self.assertEqual(summary["decreasing_4_to_5"], 1)
        self.assertEqual(summary["total_optimizer_steps"], [35])
        self.assertEqual(summary["statistics"]["delta_4_to_5"]["mean"], -.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
