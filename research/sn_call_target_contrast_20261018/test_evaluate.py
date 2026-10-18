import unittest

import numpy as np

import evaluate


class ScoreTests(unittest.TestCase):
    def test_ties_and_normal_exclusion(self):
        pred = {"root_logits": np.array([[0., 0.], [10., 0.], [0., 2.]]),
                "detection_logits": np.array([[0., 1.], [1., 0.], [1., 0.]]),
                "labels": np.array([0, -1, 1])}
        score = evaluate.metrics(pred)
        self.assertEqual(score["fault_windows"], 2)
        self.assertEqual(score["top1"], .75)
        self.assertEqual(score["top3"], 1.)
        self.assertEqual(score["gated_top1"], .25)
        self.assertEqual(score["tn"], 1)

    def test_extreme_logits_finite(self):
        values = evaluate.lp(np.array([[10000., -10000.]]))
        self.assertTrue(np.isfinite(values).all())
        self.assertEqual(values[0, 0], 0.)

    def test_transition_directions(self):
        self.assertEqual(evaluate.transition(0., 1.), "new_correct")
        self.assertEqual(evaluate.transition(1., 0.), "new_wrong")
        self.assertEqual(evaluate.transition(.5, 1.), "partial_credit_change")


if __name__ == "__main__":
    unittest.main()
