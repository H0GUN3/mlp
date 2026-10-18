import unittest

import numpy as np

from inspect_re2_schema import allow_case
from re2_stage1 import metric_grid, trace_grid


class StageOneTests(unittest.TestCase):
    def test_metric_grid_preserves_missing_and_drops_only_tail(self):
        times = np.arange(100, 121, dtype=np.int64)
        values = np.arange(21, dtype=float)
        values[6] = np.nan
        starts, grid = metric_grid(times, {"a_cpu": values}, ["a", "b"])
        np.testing.assert_array_equal(starts, [100, 110])
        self.assertEqual(grid.shape, (2, 2, 10, 8))
        self.assertTrue(np.isnan(grid[0, 0, 6, 0]))
        self.assertTrue(np.isnan(grid[:, 1]).all())
        self.assertEqual(grid[1, 0, 9, 0], 19)

    def test_missing_time_is_not_filled_with_observed_zero(self):
        times = np.array([100, 101, 102, 103, 105, 106, 107, 108, 109, 110, 111])
        _, grid = metric_grid(times, {"a_cpu": np.ones(len(times))}, ["a"])
        self.assertTrue(np.isnan(grid[0, 0, 4, 0]))
        with self.assertRaises(AssertionError):
            metric_grid(np.array([100] * 10), {"a_cpu": np.ones(10)}, ["a"])

    def test_trace_mean_units_empty_bins_and_bounds(self):
        us = np.array([100500000, 100700000, 110000000], dtype=np.int64)
        duration = np.array([1000, 3000, 5000], dtype=np.int64)
        values, counts, keep = trace_grid(us, duration, ["a"] * 3, np.array([100]), ["a"])
        self.assertEqual(values[0, 0, 0, 0], .002)
        self.assertEqual(counts[0, 0, 0], 2)
        self.assertTrue((values[..., 1] == 0).all())
        self.assertTrue((values[0, 0, 1:, 0] == 0).all())
        np.testing.assert_array_equal(keep, [True, True, False])

    def test_no_implicit_frontend_alias_merger(self):
        _, grid = metric_grid(np.arange(100, 110), {"frontend_cpu": np.ones(10)},
                              ["frontend", "frontendservice"])
        self.assertTrue(np.isnan(grid[:, 1]).all())

    def test_protected_and_path_boundaries(self):
        with self.assertRaises(PermissionError):
            allow_case({"dataset": "RE2-OB", "partition": "test", "case": "re2ob_a"})
        with self.assertRaises(ValueError):
            allow_case({"dataset": "RE2-OB", "partition": "train", "case": "re2ob_/../a"})


if __name__ == "__main__":
    unittest.main()
