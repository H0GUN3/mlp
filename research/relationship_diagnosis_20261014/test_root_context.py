"""Synthetic union tests: no observations, saved predictions or models loaded."""
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

if __package__:
    from . import root_context
else:
    import root_context

errors = root_context.errors


def event(event_id, credits, raw, visible):
    scores = {
        mode: {metric: np.asarray(credits, dtype=float) for metric in errors.METRICS}
        for mode in errors.MODES
    }
    return {
        "record": {"event_id": event_id},
        "scores": scores,
        "contexts": {"root_any_raw": np.asarray(raw, dtype=np.bool_),
                     "root_any_visible": np.asarray(visible, dtype=np.bool_)},
    }


class UnionTests(unittest.TestCase):
    def test_both_directions_count_window_once_and_no_unrelated_edges(self):
        adjacency = np.zeros((4, 3, 3), dtype=np.bool_)
        adjacency[0, 0, 1] = adjacency[0, 1, 0] = True
        adjacency[1, 0, 1] = True
        adjacency[2, 1, 0] = True
        adjacency[3, 1, 2] = True
        observed = np.ones((4, 3, 10, 9), dtype=np.bool_)
        reference = np.ones((3, 9), dtype=np.bool_)
        _, directions = errors.root_observations(observed, adjacency, 0, reference)
        unions = root_context.union_contexts(directions)
        for context in root_context.CONTEXTS:
            np.testing.assert_array_equal(unions[context], [True, True, True, False])
            self.assertEqual(int(unions[context].sum()), 3)
            self.assertEqual(float(unions[context].mean()), .75)
        self.assertEqual(int(directions["root_in_raw"].sum()
                             + directions["root_out_raw"].sum()), 4)

    def test_invisible_neighbors_and_fold_reference_without_root_visibility(self):
        adjacency = np.zeros((3, 3, 3), dtype=np.bool_)
        adjacency[:, 0, 1] = True
        adjacency[:, 2, 0] = True
        observed = np.zeros((3, 3, 10, 9), dtype=np.bool_)
        observed[0, 1, 0, 7] = True
        observed[1, 2, 9, 8] = True
        reference = np.zeros((3, 9), dtype=np.bool_)
        reference[1, 7] = True
        _, directions = errors.root_observations(observed, adjacency, 0, reference)
        self.assertFalse(directions["root_visible"].any())
        unions = root_context.union_contexts(directions)
        np.testing.assert_array_equal(unions["root_any_raw"], [True, True, True])
        np.testing.assert_array_equal(unions["root_any_visible"], [True, False, False])
        # The other fold's mask must not reuse visibility from this fold.
        other_reference = np.zeros((3, 9), dtype=np.bool_)
        other_reference[2, 8] = True
        _, other = errors.root_observations(observed, adjacency, 0, other_reference)
        np.testing.assert_array_equal(root_context.union_contexts(other)["root_any_visible"],
                                      [False, True, False])
        np.testing.assert_array_equal(directions["root_out_visible"], [True, False, False])

    def test_same_event_crosses_strata_and_event_equal_not_window_weighted(self):
        first = event("a", [[1, 0], [1, 0], [1, 0]], [True, False], [True, False])
        second = event("b", np.zeros((3, 9)), [True] * 9, [False] * 9)
        summary = root_context.summarize([first, second])
        raw = summary["root_any_raw"]
        self.assertEqual(raw["overlap_event_ids"], ["a"])
        self.assertEqual(raw["overlap_incidents"], 1)
        self.assertEqual(raw["present"]["incidents"], 2)
        self.assertEqual(raw["absent"]["incidents"], 1)
        self.assertEqual(raw["present"]["unique_windows"], 10)
        self.assertEqual(raw["absent"]["unique_windows"], 1)
        self.assertEqual(raw["present"]["seed_window_decisions_per_mode"], 30)
        self.assertEqual(raw["present"]["modes"]["directed"]["top1"], .5)
        self.assertEqual(raw["absent"]["modes"]["directed"]["top1"], 0)
        self.assertNotEqual(raw["present"]["modes"]["directed"]["top1"], .1)
        self.assertEqual(summary["root_any_visible"]["absent"]["incidents"], 2)
        self.assertEqual(summary["root_any_visible"]["present"]["modes"]["directed"]["top1"], 1)
        self.assertEqual(raw["present"]["subset_top1_win_tie_loss"],
                         {"win": 0, "tie": 2, "loss": 0})

    def test_seed_equal_ties_delta_and_empty_stratum(self):
        fixture = event("a", [[1], [0], [0]], [True], [False])
        fixture["scores"]["global"] = {
            metric: np.zeros((3, 1)) for metric in errors.METRICS
        }
        summary = root_context.summarize([fixture])
        self.assertIsNone(summary["root_any_raw"]["absent"])
        self.assertIsNone(summary["root_any_visible"]["present"])
        present = summary["root_any_raw"]["present"]
        self.assertEqual(present["modes"]["directed"]["top1"], 1 / 3)
        self.assertEqual(present["delta_directed_global"]["top1"], 1 / 3)
        self.assertEqual(present["subset_top1_win_tie_loss"], {"win": 1, "tie": 0, "loss": 0})

    def test_existing_output_rejected_before_input_reads_or_original_execution(self):
        with patch.object(Path, "exists", return_value=True), \
                patch.object(root_context, "build_supplement") as build, \
                patch.object(errors, "main") as original_main, \
                patch.object(errors, "build_diagnostic") as original_build:
            with self.assertRaises(FileExistsError):
                root_context.main()
            build.assert_not_called()
            original_main.assert_not_called()
            original_build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
