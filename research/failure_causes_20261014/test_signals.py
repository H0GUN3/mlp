import unittest

import numpy as np

from research.failure_causes_20261014 import signals


class SignalTests(unittest.TestCase):
    def test_ties(self):
        np.testing.assert_array_equal(
            signals.top1(np.array([[2., 2., 0.], [1., 2., 3.]]), np.array([0, 0])),
            [.5, 0])

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            signals.top1(np.array([[np.nan, 0.]]), np.array([0]))

    def test_equal_event_not_window_weight(self):
        result = signals.mean_records([
            {"windows": 1, "measurements": {"x": 1.}},
            {"windows": 99, "measurements": {"x": 0.}},
        ])
        self.assertEqual(result["measurements"]["x"], .5)
        self.assertEqual(result["windows"], 100)

    def test_duplicate_input_masks_and_coverage(self):
        x = np.array([[[2., 9.], [2., 42.], [2., 42.]]])
        mask = np.array([[[True, False], [True, False], [True, False]]])
        coverage = np.array([[[1., 0.], [1., 0.], [1., .1]]])
        np.testing.assert_array_equal(signals.local_duplicates(x, mask, coverage, np.array([0])), [1])

    def test_missing_reference_removes_observed_latency(self):
        values = np.ones((1, 2, 10, 9))
        observed = np.ones_like(values, dtype=bool)
        reference = {"median": np.zeros((2, 9)), "scale": np.ones((2, 9)),
                     "mask": np.ones((2, 9), dtype=bool)}
        reference["mask"][0, 7] = False
        x, mask, coverage = signals.features.window_features(values, observed, reference)
        measurements = signals.measure(values, observed, reference, x, mask, coverage, x,
                                       np.array([0]), np.array([0.]))
        self.assertEqual(measurements["root_latency_observed_but_masked"][0], 1.)
        self.assertEqual(measurements["root_latency_usable"][0], 0.)
        self.assertEqual(x[0, 0, 7], 0.)
        self.assertEqual(coverage[0, 0, 7], 1.)

    def test_signed_cancellation_and_mask(self):
        values = np.ones((1, 2, 10, 9))
        values[0, 0, :5, 0] = -1
        observed = np.ones_like(values, dtype=bool)
        reference = {"median": np.zeros((2, 9)), "scale": np.ones((2, 9)),
                     "mask": np.ones((2, 9), dtype=bool)}
        reference["mask"][1, 0] = False
        loss, magnitude = signals.cancellation(values, observed, reference)
        self.assertAlmostEqual(loss[0, 0, 0], 1.)
        self.assertEqual(loss[0, 1, 0], 0.)
        self.assertEqual(magnitude[0, 1, 0], 0.)
        self.assertAlmostEqual(loss[0, 0, 1], 0.)

    def test_probe_credit_mass_difference(self):
        probe, model = np.array([0., .5, 1.]), np.array([.1, .6, .8])
        np.testing.assert_allclose(probe * (1 - model) - model * (1 - probe), probe - model)


if __name__ == "__main__":
    unittest.main()
