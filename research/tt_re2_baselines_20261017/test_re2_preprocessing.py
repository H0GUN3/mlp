import unittest

import numpy as np

from re2_preprocessing import prepare_partitions


def fixture():
    rng = np.random.RandomState(5)
    values = rng.randn(6, 2, 10, 8)
    values[:, 0, :, 0] = np.nan
    values[3:, 0, :, 0] = 100
    values[0, 1, 2, 3] = np.nan
    traces = rng.rand(6, 2, 10, 2)
    traces[..., 1] = 0
    return {"metrics": values, "metric_observed": np.isfinite(values),
            "traces": traces, "logs": rng.rand(6, 2, 3),
            "labels": np.array([-1, 0, 1, -1, 0, 1])}


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.parts = {"train": np.array([0, 1, 2]), "validation": np.array([3, 4, 5])}

    def test_validation_cannot_change_training_fit(self):
        arrays = fixture()
        stats, data, report = prepare_partitions(arrays, self.parts)
        self.assertEqual(report["unsupported_train_node_channels"], 1)
        self.assertEqual(report["validation_observed_cells_masked_as_unsupported"], 30)
        self.assertTrue((data["validation"]["metrics"][:, 0, :, 0] == 0).all())
        arrays["metrics"][3:] += 10000
        arrays["traces"][3:, :, :, 0] += 10000
        again, changed, _ = prepare_partitions(arrays, self.parts)
        for key in stats:
            np.testing.assert_array_equal(stats[key], again[key])
        for key in data["train"]:
            np.testing.assert_array_equal(data["train"][key], changed["train"][key])

    def test_input_is_not_modified_and_missing_is_not_observed_zero(self):
        arrays = fixture()
        before = arrays["metrics"].copy()
        stats, data, _ = prepare_partitions(arrays, self.parts)
        np.testing.assert_equal(arrays["metrics"], before)
        self.assertEqual(stats["metric_train_observed_count"][1, 3], 29)
        self.assertAlmostEqual(float(data["train"]["metrics"][0, 1, 2, 3]), 0., places=6)

    def test_native_constant_policy_is_not_silently_clipped(self):
        arrays = fixture()
        arrays["metrics"][:, 1, :, 1] = 2.
        arrays["metrics"][3:, 1, :, 1] = 3.
        _, data, _ = prepare_partitions(arrays, self.parts)
        self.assertTrue((data["train"]["metrics"][:, 1, :, 1] == 0).all())
        self.assertTrue((data["validation"]["metrics"][:, 1, :, 1] == np.float32(1e8)).all())

    def test_bad_mask_and_partition_are_rejected(self):
        arrays = fixture()
        arrays["metric_observed"][0, 0, 0, 0] = True
        with self.assertRaises(AssertionError):
            prepare_partitions(arrays, self.parts)
        with self.assertRaises(AssertionError):
            prepare_partitions(fixture(), {"train": np.array([0, 1]), "validation": np.array([1, 2])})


if __name__ == "__main__":
    unittest.main()
