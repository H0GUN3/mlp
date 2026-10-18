"""Synthetic-only scoring checks; run with python -B -m unittest -v test_scores."""

import unittest

import numpy as np

from scores import event_metrics, paired_cluster_bootstrap


class EventMetricsTests(unittest.TestCase):
    def test_probability_pooling_not_mean_logits_or_window_hits(self):
        logits = np.array([[0.0, 100.0], [2.0, 0.0], [2.0, 0.0]])
        result = event_metrics(logits, [0, 0, 0], ["e", "e", "e"])
        probabilities = np.exp(logits - logits.max(axis=1, keepdims=True))
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        expected = probabilities.mean(axis=0)
        np.testing.assert_allclose(
            result["events"][0]["log_probabilities"], np.log(expected)
        )
        self.assertAlmostEqual(result["event_nll"], -np.log(expected[0]))
        self.assertEqual(result["top1"], 1.0)
        self.assertEqual(np.argmax(logits.mean(axis=0)), 1)
        self.assertAlmostEqual(np.mean(np.argmax(logits, axis=1) == 0), 2 / 3)

    def test_events_have_equal_weight_not_windows(self):
        result = event_metrics(
            [[2, 0], [2, 0], [2, 0], [0, 2]],
            [0, 0, 0, 0],
            ["long", "long", "long", "short"],
        )
        self.assertEqual(result["top1"], 0.5)
        self.assertAlmostEqual(
            result["event_nll"], (np.log1p(np.exp(-2)) + np.log1p(np.exp(2))) / 2
        )
        self.assertEqual([event["windows"] for event in result["events"]], [3, 1])

    def test_adding_correct_normal_windows_changes_nothing(self):
        original = event_metrics([[0, 2, 1]], [0], ["fault"])
        with_normals = event_metrics(
            [[0, 2, 1], [1000, -1000, 0], [0, 0, 0]],
            [0, -1, -1],
            ["fault", "", ""],
        )
        self.assertEqual(original, with_normals)

    def test_twelve_way_ties(self):
        result = event_metrics(np.zeros((3, 12)), [11, 11, 0], ["b", "b", "a"])
        self.assertAlmostEqual(result["top1"], 1 / 12)
        self.assertAlmostEqual(result["top3"], 3 / 12)
        self.assertAlmostEqual(result["event_nll"], np.log(12))
        for event in result["events"]:
            self.assertAlmostEqual(event["top1"], 1 / 12)
            self.assertAlmostEqual(event["top3"], 3 / 12)

    def test_partial_tie_crossing_top_three_boundary(self):
        result = event_metrics([[2, 2, 1, 1, 1, 0]], [3], ["e"])
        self.assertEqual(result["top1"], 0.0)
        self.assertAlmostEqual(result["top3"], 1 / 3)

    def test_extreme_logits_keep_uncapped_log_ranking(self):
        result = event_metrics([[0, -1000, -1001, -1002]], [2], ["e"])
        self.assertEqual(result["event_nll"], 1001.0)
        self.assertEqual(result["top1"], 0.0)
        self.assertEqual(result["top3"], 1.0)
        self.assertEqual(
            result["events"][0]["log_probabilities"], [0.0, -1000, -1001, -1002]
        )

    def test_extreme_logits_pool_without_probability_underflow(self):
        result = event_metrics(
            [[10000, -10000], [10000, -9998]], [1, 1], ["e", "e"]
        )
        expected = 20000 - np.logaddexp(0, 2) + np.log(2)
        self.assertAlmostEqual(result["event_nll"], expected)
        self.assertTrue(np.isfinite(result["event_nll"]))
        large = event_metrics([[1e300, -1e300, 0]], [1], ["large"])
        self.assertEqual(large["event_nll"], 2e300)

    def test_no_rounding_to_create_ties(self):
        result = event_metrics([[0, 1e-12, -1]], [0], ["e"])
        self.assertEqual(result["top1"], 0.0)
        self.assertLess(
            result["events"][0]["log_probabilities"][0],
            result["events"][0]["log_probabilities"][1],
        )

    def test_float32_input_uses_float64_computation(self):
        logits = np.array([[80, -80, 79], [-10, 10, 11]], dtype=np.float32)
        self.assertEqual(
            event_metrics(logits, [1, 1], ["e", "e"]),
            event_metrics(logits.astype(np.float64), [1, 1], ["e", "e"]),
        )

    def test_window_candidate_permutations_and_sorted_events(self):
        logits = np.array([[3, 1, 2], [0, 4, 2], [1, 5, 0], [2, 1, 0]])
        labels = np.array([0, 1, 1, 0])
        ids = np.array(["z", "a", "a", "z"])
        original = event_metrics(logits, labels, ids)
        rows = [2, 0, 3, 1]
        candidates = np.array([2, 0, 1])
        mapped_labels = np.argsort(candidates)[labels]
        permuted = event_metrics(
            logits[rows][:, candidates], mapped_labels[rows], ids[rows]
        )
        self.assertEqual([event["event_id"] for event in original["events"]], ["a", "z"])
        for metric in ("event_nll", "top1", "top3"):
            self.assertAlmostEqual(original[metric], permuted[metric])
        for before, after in zip(original["events"], permuted["events"]):
            self.assertEqual(before["event_id"], after["event_id"])
            self.assertEqual(before["windows"], after["windows"])
            self.assertEqual(candidates[after["root"]], before["root"])
            np.testing.assert_allclose(
                np.array(before["log_probabilities"])[candidates],
                after["log_probabilities"],
            )

    def test_return_contract_and_no_input_mutation(self):
        logits = np.array([[1, 2, 3]], dtype=np.int64)
        before = logits.copy()
        result = event_metrics(logits, np.array([2], dtype=np.uint8), ["e"])
        self.assertEqual(set(result), {"event_nll", "top1", "top3", "events"})
        for metric in ("event_nll", "top1", "top3"):
            self.assertIs(type(result[metric]), float)
        event = result["events"][0]
        self.assertEqual(
            set(event), {"event_id", "root", "windows", "log_probabilities", "top1", "top3"}
        )
        self.assertIs(type(event["root"]), int)
        self.assertIs(type(event["windows"]), int)
        self.assertIs(type(event["log_probabilities"]), list)
        self.assertEqual(len(event["log_probabilities"]), 3)
        np.testing.assert_array_equal(logits, before)

    def test_inconsistent_roots_rejected(self):
        with self.assertRaisesRegex(ValueError, "inconsistent roots"):
            event_metrics([[0, 1], [1, 0]], [0, 1], ["same", "same"])

    def test_bad_shapes_rejected(self):
        cases = [
            ([1, 2], [0], ["e"]),
            (np.zeros((1, 2, 1)), [0], ["e"]),
            (np.empty((0, 2)), [], []),
            (np.empty((1, 0)), [0], ["e"]),
            ([[0, 1]], [[0]], ["e"]),
            ([[0, 1]], [0], [["e"]]),
            ([[0, 1]], [0, 1], ["e"]),
            ([[0, 1]], [0], ["e", "f"]),
        ]
        for logits, labels, ids in cases:
            with self.subTest(shapes=(np.shape(logits), np.shape(labels), np.shape(ids))):
                with self.assertRaises(ValueError):
                    event_metrics(logits, labels, ids)

    def test_bad_labels_and_event_ids_rejected(self):
        cases = [
            ([0.0], ["e"]), ([True], ["e"]), (["0"], ["e"]),
            ([-2], ["e"]), ([2], ["e"]), ([0], [""]), ([0], [" "]),
            ([0], [None]), ([0], [1]), ([-1], ["e"]),
        ]
        for labels, ids in cases:
            with self.subTest(labels=labels, ids=ids):
                with self.assertRaises(ValueError):
                    event_metrics([[0, 1]], labels, ids)

    def test_nonfinite_and_nonreal_logits_rejected_even_for_normals(self):
        for value in (np.nan, np.inf, -np.inf, 1j, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    event_metrics(np.array([[0, 1], [value, 0]]), [0, -1], ["e", ""])

    def test_no_fault_events_rejected(self):
        with self.assertRaisesRegex(ValueError, "no fault events"):
            event_metrics([[0, 1]], [-1], [""])


class PairedClusterBootstrapTests(unittest.TestCase):
    def test_matches_explicit_cluster_resampling_with_unequal_sizes(self):
        differences = np.array([-1.0, -0.5, 0, 0.5, 1, 1])
        recordings = np.array(["a", "b", "b", "c", "d", "d"])
        clusters = [differences[recordings == key] for key in sorted(set(recordings))]
        rng = np.random.default_rng(123)
        explicit = []
        wrong_cluster_means = []
        for _ in range(301):
            selected = rng.integers(4, size=4)
            explicit.append(np.concatenate([clusters[index] for index in selected]).mean())
            wrong_cluster_means.append(np.mean([clusters[index].mean() for index in selected]))
        expected = np.percentile(explicit, [2.5, 97.5])
        result = paired_cluster_bootstrap(differences, recordings, samples=301, seed=123)
        np.testing.assert_allclose([result["lower"], result["upper"]], expected)
        self.assertFalse(np.allclose(expected, np.percentile(wrong_cluster_means, [2.5, 97.5])))

    def test_defaults_reproducibility_and_order(self):
        differences = np.array([-1.0, 0.25, 0.75, 1, 0])
        recordings = np.array(["b", "a", "b", "c", "d"])
        result = paired_cluster_bootstrap(differences, recordings)
        self.assertEqual(
            result,
            paired_cluster_bootstrap(differences, recordings, samples=5000, seed=20261017),
        )
        order = [4, 2, 0, 3, 1]
        self.assertEqual(
            result, paired_cluster_bootstrap(differences[order], recordings[order])
        )
        self.assertIs(type(result["lower"]), float)
        self.assertIs(type(result["upper"]), float)

    def test_single_cluster_keeps_all_events(self):
        result = paired_cluster_bootstrap([-1, 0, 1, 1], [7, 7, 7, 7], samples=20)
        self.assertEqual(result, {"lower": 0.25, "upper": 0.25})

    def test_constant_differences_and_one_sample(self):
        result = paired_cluster_bootstrap([0.5] * 4, ["a", "b", "c", "d"], samples=1)
        self.assertEqual(result, {"lower": 0.5, "upper": 0.5})

    def test_invalid_differences_and_recordings(self):
        cases = [
            ([], []), ([[0, 1]], ["a"]), ([0], [["a"]]), ([0, 1], ["a"]),
            ([np.nan], ["a"]), ([np.inf], ["a"]), ([-np.inf], ["a"]),
            (["1"], ["a"]), ([1j], ["a"]), ([0], [""]), ([0], [" "]),
            ([0], [None]), ([0], [False]), ([0], [1.5]),
        ]
        for differences, recordings in cases:
            with self.subTest(differences=differences, recordings=recordings):
                with self.assertRaises(ValueError):
                    paired_cluster_bootstrap(differences, recordings, samples=2)

    def test_invalid_samples_and_seed(self):
        for samples in np.array([0, -1, 1.5, True, "5"], dtype=object):
            with self.subTest(samples=samples):
                with self.assertRaises(ValueError):
                    paired_cluster_bootstrap([0], ["a"], samples=samples)
        for seed in np.array([-1, 1.5, True, "5"], dtype=object):
            with self.subTest(seed=seed):
                with self.assertRaises(ValueError):
                    paired_cluster_bootstrap([0], ["a"], samples=2, seed=seed)


if __name__ == "__main__":
    unittest.main()
