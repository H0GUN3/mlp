"""Focused protocol fixtures; only synthetic arrays, no model or raw-data access."""
import unittest

import numpy as np

from analysis import (boundary_counts, candidates, check_alignment, independent_events,
                      join_observability, paired_summary, proof_gate, saved_joint,
                      training_prior, variability)
from scores import event_metrics, paired_cluster_bootstrap


class AnalysisTests(unittest.TestCase):
    def test_train_event_prior_ignores_window_imbalance(self):
        labels = np.repeat(np.arange(12), np.arange(1, 13))
        events = np.repeat(["e{}".format(n) for n in range(12)], np.arange(1, 13))
        counts, prior = training_prior(np.append(labels, -1), np.append(events, ""))
        np.testing.assert_array_equal(counts, np.ones(12))
        np.testing.assert_array_equal(prior, np.full(12, 1 / 12))
        for root in range(12):
            m = independent_events(np.log(prior)[None, :], np.array([root]), np.array(["query"]))
            self.assertEqual(m["top1"], 1 / 12)
            self.assertEqual(m["top3"], 3 / 12)

    def test_train_prior_rejects_missing_root_or_inconsistent_event(self):
        with self.assertRaisesRegex(AssertionError, "exactly one"):
            training_prior(np.arange(11), np.array(["e{}".format(n) for n in range(11)]))
        with self.assertRaisesRegex(AssertionError, "inconsistent"):
            training_prior(np.array([0, 1]), np.array(["same", "same"]))

    def test_exact_ties_and_candidates_include_third_boundary(self):
        logits = np.array([[2., 1., 1., 1.] + [0.] * 8])
        m = independent_events(logits, np.array([1]), np.array(["event"]))
        e = m["events"][0]
        self.assertEqual(e["top1"], 0.)
        self.assertEqual(e["top3"], 2 / 3)
        fixed = event_metrics(logits, np.array([1]), np.array(["event"]))
        self.assertEqual(e["top3"], fixed["events"][0]["top3"])
        c = candidates(e, ["s{}".format(n) for n in range(12)])
        self.assertEqual(c["root_rank_first"], 2)
        self.assertEqual(c["root_rank_last"], 4)
        self.assertEqual(c["top_rank_groups_through_3"][1]["services"], ["s1", "s2", "s3"])

    def test_stable_pooling_averages_probabilities_not_logits(self):
        logits = np.zeros((3, 12))
        logits[0, :2] = [1000., 999.]
        logits[1, :2] = [0., 10.]
        logits[2, 11] = 1e6
        labels = np.array([1, 1, -1])
        m = independent_events(logits, labels, np.array(["fault", "fault", ""]))
        self.assertEqual(len(m["events"]), 1)
        self.assertEqual(m["events"][0]["windows"], 2)
        self.assertEqual(m["top1"], 1.)
        fixed = event_metrics(logits, labels, np.array(["fault", "fault", ""]))
        np.testing.assert_allclose(m["events"][0]["log_probabilities"],
                                   fixed["events"][0]["log_probabilities"], atol=1e-12, rtol=0)
        self.assertTrue(np.isfinite(m["event_nll"]))

    def test_alignment_rejects_wrong_indices_and_labels(self):
        expected = {"labels": np.array([0]), "indices": np.array([537]),
                    "event_ids": np.array(["fault"])}
        for field in ("indices", "labels", "event_ids"):
            bad = dict(expected)
            bad[field] = np.array(["wrong"] if field == "event_ids" else [99])
            with self.assertRaises(AssertionError):
                check_alignment(bad, expected, "synthetic")

    def test_boundary_uses_inclusive_end_and_actual_window_indices(self):
        windows = [{"original_index": i, "start": start, "end": end}
                   for i, start, end in [(537, 100, 109), (3, 95, 104), (88, 110, 119)]]
        b = boundary_counts(windows, {"start": 100, "end_inclusive": 118})
        self.assertEqual(b, {"boundary_windows": 2, "fully_inside_windows": 1,
                             "boundary_original_indices": [3, 88]})

    def test_observability_joins_original_indices_not_positions(self):
        windows = [{"original_index": 537, "start": 100, "end": 109,
                    "event_id": "fault", "label": 2},
                   {"original_index": 3, "start": 110, "end": 119,
                    "event_id": "fault", "label": 2}]
        fault = {"root": 2, "service": "root", "start": 100, "end_inclusive": 118}
        audit = {"original_indices": [3, 537], "root": 2, "service": "root",
                 "root_latency_present_fraction": .5, "root_any_edge_fraction": .5,
                 "root_metric_at_least_nonroot_fraction": 0.}
        contrasts = {i: {"event_id": "fault", "root_service": "root",
                         "original_index": i, "root_latency_seconds": bins}
                     for i, bins in [(3, 0), (537, 7)]}
        result = join_observability("fault", windows, fault, audit, contrasts)
        self.assertEqual(result["root_trace_observed_bins"], 7)
        self.assertEqual(result["root_trace_missing_windows"], 1)
        self.assertEqual(result["possible_bins"], 20)
        self.assertEqual(result["boundary_original_indices"], [3])
        contrasts[537]["event_id"] = "wrong"
        with self.assertRaisesRegex(AssertionError, "join mismatch"):
            join_observability("fault", windows, fault, audit, contrasts)

    def test_missing_upstream_proof_fails_closed(self):
        with self.assertRaises((AssertionError, KeyError)):
            proof_gate({"verdict": "FAIL"}, "Status: **PASS**")
        with self.assertRaises((AssertionError, KeyError)):
            proof_gate({"verdict": "PASS", "upstream_execution_provenance":
                        {"verdict": "PASS", "runner_exit": 1, "runner_sentinel": "EVALUATION_PASS 18"}},
                       "Status: **PASS**")

    def test_joint_window_loss_is_not_event_root_nll(self):
        pred = {"root_logits": np.zeros((3, 12)), "detection_logits": np.zeros((3, 2)),
                "labels": np.array([0, 1, -1])}
        components = saved_joint(pred)
        self.assertAlmostEqual(components["root_window_nll"], np.log(12))
        self.assertAlmostEqual(components["detection_window_nll"], np.log(2))
        self.assertAlmostEqual(components["joint_loss_recomputed_float64"],
                               .5 * np.log(12) + .5 * np.log(2))
        self.assertNotEqual(components["root_window_nll"],
                            components["joint_loss_recomputed_float64"])

    def test_paired_direction_and_seed_variability(self):
        rows = [{"difference": {"top1": d, "top3": -d}} for d in [1 / 3, 0., -2 / 3]]
        s = paired_summary(rows)
        self.assertAlmostEqual(s["top1"]["mean_difference"], -1 / 9)
        self.assertEqual([s["top1"][k] for k in ("wins", "ties", "losses")], [1, 1, 1])
        self.assertEqual(variability([0., 1., 2.])["sample_sd_ddof1"], 1.)

    def test_fixed_four_recording_bootstrap(self):
        recs = np.repeat(["a", "b", "c", "d"], 9)
        diffs = np.repeat([-1., 0., 0., 1.], 9)
        first = paired_cluster_bootstrap(diffs, recs, samples=5000, seed=20261017)
        second = paired_cluster_bootstrap(diffs[::-1], recs[::-1], samples=5000, seed=20261017)
        self.assertEqual(first, second)
        self.assertEqual(first, {"lower": -.75, "upper": .75})
        self.assertEqual(paired_cluster_bootstrap(np.ones(36) / 4, recs, 5000, 20261017),
                         {"lower": .25, "upper": .25})


if __name__ == "__main__":
    unittest.main()
