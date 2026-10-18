import unittest

import numpy as np

from verify_results import check_alignment, independent_events


class IndependentScoringTests(unittest.TestCase):
    def test_equal_twelve_way_ties_and_normal_exclusion(self):
        logits = np.zeros((2, 12))
        result = independent_events(logits, np.array([4, -1]), np.array(["event", ""]))
        self.assertEqual(result["events"][0]["top1"], 1 / 12)
        self.assertEqual(result["events"][0]["top3"], 3 / 12)
        self.assertEqual(result["events"][0]["windows"], 1)

    def test_extreme_logits_stable(self):
        result = independent_events(np.array([[1e300, -1e300] + [0] * 10]),
                                    np.array([0]), np.array(["x"]))
        self.assertTrue(np.isfinite(result["event_nll"]))
        self.assertEqual(result["events"][0]["top1"], 1.0)

    def test_multiwindow_probability_pooling(self):
        result = independent_events(np.array([[8., 0.] + [0.] * 10,
                                               [0., 8.] + [0.] * 10]),
                                    np.array([0, 0]), np.array(["e", "e"]))
        self.assertEqual(result["events"][0]["windows"], 2)
        self.assertAlmostEqual(result["events"][0]["log_probabilities"][0],
                               result["events"][0]["log_probabilities"][1], places=12)

    def test_wrong_label_mapping_changes_credit(self):
        logits = np.array([[9., 0.] + [0.] * 10])
        correct = independent_events(logits, np.array([0]), np.array(["e"]))
        wrong = independent_events(logits, np.array([1]), np.array(["e"]))
        self.assertEqual(correct["top1"], 1.0)
        self.assertEqual(wrong["top1"], 0.0)

    def test_wrong_saved_label_or_index_mapping_fails(self):
        expected = {"labels": np.array([3]), "indices": np.array([17]),
                    "event_ids": np.array(["fault"])}
        for key, bad in (("labels", np.array([4])), ("indices", np.array([18]))):
            prediction = dict(expected)
            prediction[key] = bad
            with self.assertRaises(AssertionError):
                check_alignment(prediction, expected, "fixture.npz")


if __name__ == "__main__":
    unittest.main()
