"""Small deterministic checks of join identity, aggregation and tie semantics."""
import unittest

import numpy as np

from paired import CATEGORIES, counts, cross_seed, decision, paired_rows, softmax, transition


SERVICES = ["root", "other"]


def saved(indices, logits, labels=None):
    return dict(indices=np.array(indices), root_logits=np.array(logits, dtype=float),
                labels=np.array(labels if labels is not None else [0] * len(indices)))


def identity(event="run-a:fault04", run="run-a", root="root"):
    return dict(event_id=event, run_id=run, root_fault_group=root + "|network_delay")


def pair(before, after, windows=None, seed=11):
    if windows is None:
        windows = {int(i): identity() for i in before["indices"]}
    return paired_rows("test", seed, before, after, windows, SERVICES)


class PairingTests(unittest.TestCase):
    def test_multiwindow_mixed_outcomes_are_not_events(self):
        a = saved([1, 2, 3], [[0, 2], [2, 0], [0, 2]])
        b = saved([1, 2, 3], [[2, 0], [0, 2], [0, 2]])
        windows, events = pair(a, b)
        self.assertEqual(counts(windows), dict(
            both_correct=0, new_correct=1, new_wrong=1, both_wrong=1, unresolved_tie=0))
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["mixed_window_outcomes"])
        self.assertEqual(events[0]["window_categories"], counts(windows))
        self.assertEqual(events[0]["category"], "both_wrong")

    def test_full_run_event_key_avoids_fault_number_collision(self):
        a = saved([1, 2], [[2, 0], [2, 0]])
        _, events = pair(a, a, {1: identity(), 2: identity("run-b:fault04", "run-b")})
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]["event_id"], events[1]["event_id"])
        with self.assertRaises(AssertionError):
            pair(a, a, {1: identity("fault04"), 2: identity("fault04")})

    def test_seed_evaluations_do_not_multiply_unique_events(self):
        a = saved([1], [[2, 0]])
        b = saved([1], [[0, 2]])
        _, first = pair(a, b, seed=11)
        _, second = pair(b, a, seed=23)
        result = cross_seed(first + second, (11, 23))
        self.assertEqual(result["unique_events"], 1)
        self.assertEqual(result["seed_event_records"], 2)
        self.assertEqual(result["vectors"][0]["status_vector"],
                         {"11": "new_wrong", "23": "new_correct"})
        self.assertEqual(result["category_sets"]["new_correct"]["intersection_count"], 0)
        self.assertEqual(result["union_overlaps"][0]["count"], 1)
        with self.assertRaises(AssertionError):
            cross_seed(first + first + second, (11, 23))

    def test_ties_preserve_credit_and_unresolved_category(self):
        a = saved([1], [[2, 2]])
        b = saved([1], [[3, 0]])
        windows, events = pair(a, b)
        for row in windows + events:
            self.assertEqual(row["50"]["top_candidates"], [0, 1])
            self.assertEqual(row["50"]["root_credit"], .5)
            self.assertEqual(row["category"], "unresolved_tie")
        wrong_tie = decision([1., 2., 2.], 0)
        self.assertEqual(wrong_tie["root_credit"], 0.)
        self.assertEqual(wrong_tie["status"], "tied_wrong")
        self.assertEqual(transition(wrong_tie, decision([3, 2, 2], 0)), "unresolved_tie")

    def test_event_mean_can_introduce_a_tie(self):
        a = saved([1, 2], [[2, 0], [0, 2]])
        windows, events = pair(a, a)
        self.assertTrue(all(not r["50"]["tie"] for r in windows))
        self.assertEqual(events[0]["50"]["top_candidates"], [0, 1])
        self.assertEqual(events[0]["category"], "unresolved_tie")

    def test_storage_permutation_is_joined_by_original_index(self):
        a = saved([2, 1], [[2, 0], [0, 2]])
        b = saved([1, 2], [[2, 0], [0, 2]])
        rows, _ = pair(a, b)
        self.assertEqual([(r["index"], r["category"]) for r in rows],
                         [(1, "new_correct"), (2, "new_wrong")])
        shuffled, _ = pair(a, saved([2, 1], [[0, 2], [2, 0]]))
        self.assertEqual(rows, shuffled)

    def test_softmax_large_offsets_stays_finite(self):
        values = np.array([[10000., 10001.], [-10000., -10000.]])
        actual = softmax(values)
        self.assertTrue(np.isfinite(actual).all())
        np.testing.assert_allclose(actual.sum(axis=1), 1.)
        np.testing.assert_allclose(actual, softmax(values + 100000.))
        np.testing.assert_allclose(actual[1], [.5, .5])
        with self.assertRaises(AssertionError):
            softmax([[float("nan"), 0]])

    def test_mean_softmax_is_not_mean_logits_or_majority_vote(self):
        a = saved([1, 2, 3], [[.2, 0], [.2, 0], [-3, 0]])
        _, events = pair(a, a)
        expected = softmax(a["root_logits"]).mean(axis=0)
        np.testing.assert_allclose(events[0]["50"]["mean_candidate_probabilities"], expected)
        self.assertEqual(events[0]["50"]["top_candidates"], [1])
        b = saved([1, 2, 3], [[100, 0], [-2, 0], [-2, 0]])
        _, events = pair(b, b)
        self.assertGreater(b["root_logits"].mean(axis=0)[0], 0)
        self.assertEqual(events[0]["50"]["top_candidates"], [1])

    def test_mismatched_duplicate_indices_and_labels_are_rejected(self):
        a = saved([1, 2], [[2, 0], [2, 0]])
        for b in (saved([1, 1], [[2, 0], [2, 0]]),
                  saved([1, 3], [[2, 0], [2, 0]]),
                  saved([1, 2], [[2, 0], [2, 0]], labels=[0, 1])):
            with self.assertRaises(AssertionError):
                pair(a, b)

    def test_candidate_metadata_root_and_event_root_consistency(self):
        a = saved([1, 2], [[2, 0], [2, 0]])
        with self.assertRaises(AssertionError):
            pair(a, a, {1: identity(root="other"), 2: identity(root="other")})
        a = saved([1, 2], [[2, 0], [0, 2]], labels=[0, 1])
        with self.assertRaises(AssertionError):
            pair(a, a, {1: identity(), 2: identity(root="other")})

    def test_all_unique_top_transitions(self):
        good, bad = decision([2, 0], 0), decision([0, 2], 0)
        self.assertEqual([transition(a, b) for a, b in
                          ((good, good), (bad, good), (good, bad), (bad, bad))],
                         list(CATEGORIES[:-1]))


if __name__ == "__main__":
    unittest.main()
