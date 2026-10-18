from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings

import numpy as np

import prepare_horizon as prep


class PreparationTests(unittest.TestCase):
    def test_original_seed_template_order_jitter_and_boundaries(self):
        events = {
            "log_window": np.array([19, 19, 19, 19]),
            "log_node": np.array([2, 2, 2, 2]),
            "log_template": np.array([3, 1, 3, 0]),
            "log_timestamp": np.array([100., 109.9, 100., 101.]),
            "window_start": np.array([100]),
        }
        tasks = prep.build_tasks(events, np.array([19]))
        task = tasks[0]
        self.assertEqual(task["seed"], 42 + 19 * 12 + 2)
        self.assertEqual(task["event_count"], 4)
        self.assertEqual(len(task["knots"]), 7)
        np.testing.assert_array_equal(task["knots"][3], [0., 1e-5])
        np.testing.assert_array_equal(task["knots"][2], [0.])
        np.testing.assert_array_equal(task["knots"][0], [1.])
        for timestamp in (99.999, 110.):
            events["log_timestamp"][0] = timestamp
            with self.assertRaisesRegex(ValueError, "half-open"):
                prep.build_tasks(events, np.array([19]))
        events["log_timestamp"][:] = 109.999999
        with self.assertRaisesRegex(ValueError, "jitter"):
            prep.build_tasks(events, np.array([19]))

    def test_paired_solver_changes_only_horizon_same_rng_knots_defaults(self):
        native = prep.native_helpers()
        calls = []

        class RecordingModel:
            def __init__(self, *args, **kwargs):
                self.args, self.kwargs = args, kwargs
                self.history = SimpleNamespace(last_values={"n_iter": 50})
                self.baseline = np.ones(7)

            def fit(self, knots, **kwargs):
                calls.append((self.args, self.kwargs, knots, kwargs,
                              np.random.random(3)))
                warnings.warn("synthetic solver cap", RuntimeWarning)

        knots = native.make_knots(np.array([100., 101.]), np.array([2, 1]), 100., 7)
        task = {"window": 9, "node": 4, "knots": knots,
                "seed": 42 + 9 * 12 + 4, "start": 100.}
        with patch.object(native, "HawkesADM4", RecordingModel):
            relative = native.fit_hawkes((9, 4, knots, task["seed"]))
            absolute = prep.fit_absolute(task, RecordingModel)
        self.assertEqual(calls[0][:2], calls[1][:2])
        self.assertEqual(calls[0][0], (3,))
        self.assertEqual(calls[0][1], {})
        self.assertIs(calls[0][2], calls[1][2])
        np.testing.assert_array_equal(calls[0][4], calls[1][4])
        self.assertEqual(calls[0][3]["end_times"], 10.)
        self.assertEqual(calls[1][3]["end_times"], 110.)
        np.testing.assert_array_equal(calls[0][3]["baseline_start"],
                                      calls[1][3]["baseline_start"])
        self.assertEqual(relative["warnings"], ["synthetic solver cap"])
        self.assertEqual(absolute["warnings"], ["synthetic solver cap"])
        self.assertEqual(absolute["iterations"], 50)

    def test_mismatch_stops_before_absolute_and_preserves_error_values(self):
        native = prep.native_helpers()
        task = {"window": 9, "node": 4, "knots": [np.array([0.])] * 7,
                "seed": 154, "start": 100., "expected": np.zeros(7)}
        with patch.object(native, "fit_hawkes", return_value={"baseline": np.ones(7)}):
            with patch.object(prep, "fit_absolute", side_effect=AssertionError("must not fit")):
                with self.assertRaisesRegex(ValueError, "RELATIVE_EXACT_MISMATCH.*expected=.*actual="):
                    prep.paired_fit(task)

    def test_invalid_absolute_outputs_fail_without_clipping(self):
        class BadModel:
            def __init__(self, decay):
                self.baseline = np.array([np.nan] * 7)
                self.history = SimpleNamespace(last_values={"n_iter": 50})

            def fit(self, knots, **kwargs):
                pass

        task = {"knots": [np.array([0.])] * 7, "seed": 42, "start": 100.}
        for bad in (np.nan, -1.):
            class Model(BadModel):
                def __init__(self, decay):
                    super().__init__(decay)
                    self.baseline[:] = bad
            with self.assertRaisesRegex(ValueError, "Invalid absolute Hawkes"):
                prep.fit_absolute(task, Model)

    def test_five_different_length_probes_cover_extremes(self):
        tasks = [{"event_count": size} for size in (1, 1, 2, 3, 4, 7, 9, 20)]
        positions = prep.probe_indices(tasks)
        lengths = [tasks[i]["event_count"] for i in positions]
        self.assertEqual(len(set(lengths)), 5)
        self.assertEqual((lengths[0], lengths[-1]), (1, 20))
        with self.assertRaises(ValueError):
            prep.probe_indices(tasks[:4])

    def test_writer_roundtrip_exclusive_and_partial_preservation(self):
        prep.INPUTS.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(prep.INPUTS), prefix="writer_fixture_") as directory:
            path = Path(directory) / "selected.npz"
            values = {"labels": np.array([2], dtype=np.int64),
                      "logs": np.zeros((1, 12, 7))}
            digest = prep.publish_arrays(path, values)
            self.assertEqual(digest, prep.file_hash(path))
            with self.assertRaises(FileExistsError):
                prep.publish_arrays(path, values)
            failed = Path(directory) / "failed.npz"
            with patch.object(prep.np, "load", side_effect=ValueError("synthetic roundtrip failure")):
                with self.assertRaisesRegex(ValueError, "synthetic roundtrip"):
                    prep.publish_arrays(failed, values)
            self.assertFalse(failed.exists())
            self.assertTrue(failed.with_name("failed.npz.partial").exists())
            with self.assertRaises(FileExistsError):
                prep.publish_arrays(failed, values)

    def test_difference_empty_group_zeros_and_per_window_node_counts(self):
        relative = np.zeros((2, 12, 7))
        relative[1, 3, 2] = 1.
        absolute = relative.copy()
        absolute[1, 3, 2] = .01
        report = prep.difference(relative, absolute, np.array([9, 22]))
        self.assertEqual(report["changed_cells"], 1)
        self.assertEqual(report["changed_window_node_groups"], 1)
        self.assertEqual(report["by_window"][1]["original_window"], 22)
        self.assertEqual(report["by_node"][3]["changed_cells"], 1)
        self.assertEqual(report["relative"]["nonzero"], 1)
        self.assertEqual(report["absolute"]["nonzero"], 1)

    def test_finalize_nonzero_exit_never_publishes_pass(self):
        with self.assertRaisesRegex(ValueError, "actual producer exit 0"):
            prep.finalize(1)


if __name__ == "__main__":
    unittest.main()
