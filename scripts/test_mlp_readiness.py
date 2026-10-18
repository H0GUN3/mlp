"""Focused checks for data boundaries, diagnosis metrics and model selection."""
import copy
import inspect
import unittest

import numpy as np

from mlp_readiness import (
    allow_read, change, extract_features, load_split, rank_metrics,
    selected_epoch, train_scaler, validate_split, vectorize,
)


class ReadinessTests(unittest.TestCase):
    def test_perfect_fault_and_normal_denominator(self):
        single = rank_metrics([[4, 1, 0]], np.array([0]), [[True] * 3])
        mixed = rank_metrics([[4, 1, 0], [0, 0, 0]], np.array([0, -1]), [[True] * 3] * 2)
        self.assertEqual(single, mixed)
        self.assertEqual(single["top1"], 1)
        self.assertEqual(single["mrr"], 1)

    def test_ties_have_no_service_order_advantage(self):
        for truth in range(3):
            result = rank_metrics([[2, 2, 2]], np.array([truth]), [[True] * 3])
            self.assertAlmostEqual(result["top1"], 1 / 3)
            self.assertAlmostEqual(result["top3"], 1)
            self.assertAlmostEqual(result["mrr"], (1 + 1 / 2 + 1 / 3) / 3)

    def test_lower_root_rank_and_absent_candidate(self):
        result = rank_metrics([[4, 3, 2, 1]], np.array([3]), [[True] * 4])
        self.assertEqual(result["top1"], 0)
        self.assertEqual(result["top3"], 0)
        self.assertEqual(result["mrr"], .25)
        result = rank_metrics([[4, np.inf, 2]], np.array([0]), [[True, False, True]])
        self.assertEqual(result["top1"], 1)
        with self.assertRaises(ValueError):
            rank_metrics([[4, 3]], np.array([1]), [[True, False]])

    def test_invalid_predictions_are_not_silently_dropped(self):
        for values, target in (([np.nan, 1], 0), ([1, 0], 2), ([1, 0], -2)):
            with self.assertRaises(ValueError):
                rank_metrics([values], np.array([target]), [[True, True]])
        with self.assertRaises(ValueError):
            rank_metrics([[1, 0]], np.array([.5]), [[True, True]])

    def test_validation_only_checkpoint_selection(self):
        self.assertEqual(list(inspect.signature(selected_epoch).parameters), ["validation_losses"])
        self.assertEqual(selected_epoch([2, 1, 3]), 1)
        self.assertEqual(selected_epoch([1, 1]), 0)
        with self.assertRaises(ValueError):
            selected_epoch([1, np.nan])

    def test_scaler_uses_only_supplied_training_observations(self):
        train = np.array([[[1., 2.], [3., 2.], [999., 999.]]])
        center, scale = train_scaler(train, np.array([[True, True, False]]))
        np.testing.assert_array_equal(center, [2, 2])
        np.testing.assert_array_equal(scale, [1, 1])
        self.assertEqual(list(inspect.signature(train_scaler).parameters), ["x", "present"])

    def test_change_keeps_order_past_old_cap(self):
        lower = change(np.ones(20), np.full(20, 100))
        higher = change(np.ones(20), np.full(20, 200))
        self.assertGreater(higher[0], lower[0])
        self.assertEqual(change(np.ones(19), np.ones(20)), (0, 0))
        self.assertLess(change(np.ones(20), np.zeros(20))[0], 0)
        self.assertEqual(list(inspect.signature(extract_features).parameters),
                         ["case_path", "injection", "cache"])

    def test_graph_keeps_direction_and_self_evidence(self):
        rows = [{"case": "fixture", "root_cause_service": "a"}]
        features = {"fixture": {"nodes": {"a": [1.] * 17, "b": [0.] * 16 + [1.]},
                                "edges": [["a", "b"]]}}
        x, y, mask, edges = vectorize(rows, features, ["a", "b"])
        self.assertEqual(x.shape, (1, 2, 17))
        self.assertEqual(y.tolist(), [0])
        self.assertEqual(mask.tolist(), [[True, True]])
        self.assertEqual(edges, [[(0, 0), (0, 1), (1, 1)]])
        with self.assertRaises(ValueError):
            vectorize(rows, features, ["a"])

    def test_proxy_clusters_are_not_a_generic_unknown_fallback(self):
        rows = [{"case": "fixture", "root_cause_service": "a"}]
        features = {"fixture": {"nodes": {s: [1.] * 17 for s in ("a", "b", "PassthroughCluster")},
                                "edges": [["a", "PassthroughCluster"], ["PassthroughCluster", "b"]]}}
        x, _, _, edges = vectorize(rows, features, ["a", "b"])
        self.assertEqual(x.shape, (1, 2, 17))
        self.assertEqual(edges, [[(0, 0), (1, 1)]])
        rows[0]["root_cause_service"] = "PassthroughCluster"
        with self.assertRaises(ValueError):
            vectorize(rows, features, ["a", "b"])
        rows[0]["root_cause_service"] = "a"
        features["fixture"]["nodes"]["new_actual_service"] = [1.] * 17
        with self.assertRaises(ValueError):
            vectorize(rows, features, ["a", "b"])

    def test_frozen_split_and_read_boundary(self):
        manifest = load_split()
        validate_split(manifest)
        for row in manifest["cases"]:
            if row["partition"] == "test":
                with self.assertRaises(PermissionError):
                    allow_read(row["case"], manifest)
            else:
                allow_read(row["case"], manifest)
        with self.assertRaises(PermissionError):
            allow_read("unknown_case", manifest)
        broken = copy.deepcopy(manifest)
        developed = next(r for r in broken["cases"] if r["previously_developed"])
        developed["partition"] = "test"
        with self.assertRaises(AssertionError):
            validate_split(broken)


if __name__ == "__main__":
    unittest.main(verbosity=2)
