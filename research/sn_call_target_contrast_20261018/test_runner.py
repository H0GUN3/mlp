"""Small contract fixtures; no experiment training or source observations."""
import unittest

import numpy as np

import runner


class RunnerTests(unittest.TestCase):
    def test_selection_strict_earliest_tie(self):
        self.assertTrue(runner.strict_improvement(1., float("inf")))
        self.assertFalse(runner.strict_improvement(1., 1.))
        self.assertTrue(runner.strict_improvement(.9, 1.))
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                runner.strict_improvement(value, 1.)

    def test_budget_selection_does_not_use_later_epoch(self):
        history = [{"epoch": i, "validation_joint_loss": 1.} for i in range(1, 201)]
        history[30]["validation_joint_loss"] = .5
        history[40]["validation_joint_loss"] = .5
        history[100]["validation_joint_loss"] = .1
        select = lambda n: min(history[:n], key=lambda r: r["validation_joint_loss"])["epoch"]
        self.assertEqual(select(50), 31)
        self.assertEqual(select(200), 101)

    def test_only_trace_values_may_change(self):
        original = {
            "metrics": np.zeros((394, 12, 10, 7)), "traces": np.zeros((394, 12, 10, 2)),
            "logs": np.zeros((394, 12, 7)), "labels": np.zeros(394, dtype=np.int64),
            "indices": np.arange(394, dtype=np.int64),
        }
        candidate = {k: v.copy() for k, v in original.items()}
        candidate["traces"][0, 0, 0, 0] = 6.
        runner.validate_arrays(candidate, original)
        candidate["logs"][0, 0, 0] = 1.
        with self.assertRaises(AssertionError):
            runner.validate_arrays(candidate, original)
        candidate["logs"][0, 0, 0] = 0.
        candidate["traces"][0, 0, 0, 1] = 1.
        with self.assertRaises(AssertionError):
            runner.validate_arrays(candidate, original)


if __name__ == "__main__":
    unittest.main()
