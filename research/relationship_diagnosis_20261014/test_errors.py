"""Synthetic, source-independent diagnostic tests; never load observations/models."""
from itertools import product
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import errors


class RankingTests(unittest.TestCase):
    def test_maximum_ties_include_root_and_conserve_mass(self):
        logits = np.asarray([[4., 4., 0., -1.], [4., 4., 4., 4.], [0., 3., 3., -1.]])
        metrics, wrong, target_ties, maximum_ties = errors.ranking(logits, np.asarray([0, 2, 0]))
        np.testing.assert_allclose(metrics["top1"], [.5, .25, 0])
        np.testing.assert_allclose(metrics["top3"], [1, .75, 1])
        self.assertAlmostEqual(metrics["mrr"][1], (1 + .5 + 1 / 3 + .25) / 4)
        np.testing.assert_allclose(wrong, [[0, .5, 0, 0], [.25, .25, 0, .25], [0, .5, .5, 0]])
        np.testing.assert_allclose(wrong.sum(axis=1), 1 - metrics["top1"])
        self.assertEqual((target_ties, maximum_ties), (2, 3))

    def test_nonmaximum_root_tie_and_invalid_inputs(self):
        metrics, wrong, _, _ = errors.ranking(np.asarray([[3., 1., 1., 1.]]), np.asarray([2]))
        self.assertEqual(metrics["top1"][0], 0)
        self.assertAlmostEqual(metrics["top3"][0], 2 / 3)
        self.assertEqual(wrong[0, 0], 1)
        for logits, labels in ((np.asarray([[np.nan, 1.]]), np.asarray([0])),
                               (np.ones((1, 2)), np.asarray([2])),
                               (np.ones((1, 2)), np.asarray([0.0]))):
            with self.assertRaises(ValueError):
                errors.ranking(logits, labels)


class GraphTests(unittest.TestCase):
    def test_all_exclusive_relations_and_direction(self):
        graph = np.zeros((7, 7), dtype=np.bool_)
        graph[0, 1] = graph[1, 0] = True
        graph[0, 2] = True
        graph[3, 0] = True
        graph[2, 4] = True
        graph[5, 6] = True
        np.testing.assert_array_equal(errors.relation_codes(graph, 0), [-1, 0, 1, 2, 3, 4, 4])
        np.testing.assert_array_equal(errors.relation_codes(graph.T, 0), [-1, 0, 2, 1, 3, 4, 4])

    def test_missing_reference_visibility_and_no_root_visibility_gate(self):
        observed = np.zeros((2, 3, 10, 9), dtype=np.bool_)
        observed[0, 1, :, 7] = True
        observed[1, 2, :, 0] = True
        graph = np.zeros((2, 3, 3), dtype=np.bool_)
        graph[:, 0, 1] = True
        graph[:, 2, 0] = True
        fold0 = np.zeros((3, 9), dtype=np.bool_)
        fold0[1, 7] = True
        fold0[2, 0] = True
        summary, context = errors.root_observations(observed, graph, 0, fold0)
        np.testing.assert_array_equal(context["root_visible"], [False, False])
        np.testing.assert_array_equal(context["root_out_visible"], [True, False])
        np.testing.assert_array_equal(context["root_in_visible"], [False, True])
        self.assertEqual(summary["root_reference_available_fraction"], 0)
        self.assertEqual(summary["root_trace_latency_channel7_observed_fraction"], 0)
        self.assertEqual(summary["contexts"]["anygraph"]["present_windows"], 2)
        fold1 = fold0.copy()
        fold1[1, 7] = False
        _, other = errors.root_observations(observed, graph, 0, fold1)
        np.testing.assert_array_equal(other["root_out_visible"], [False, False])
        np.testing.assert_array_equal(other["root_in_visible"], [False, True])
        with self.assertRaisesRegex(ValueError, "reference mask"):
            errors.root_observations(observed, graph, 0, np.zeros((3, 18), dtype=np.bool_))

    def test_raw_trace_is_not_reference_or_feature_visibility(self):
        observed = np.zeros((1, 2, 10, 9), dtype=np.bool_)
        observed[0, 0, :5, 7] = True
        summary, context = errors.root_observations(
            observed, np.zeros((1, 2, 2), dtype=np.bool_), 0,
            np.zeros((2, 9), dtype=np.bool_))
        self.assertEqual(summary["root_trace_latency_channel7_observed_fraction"], .5)
        self.assertAlmostEqual(summary["root_raw9_observed_fraction"], 5 / 90)
        self.assertTrue(context["root_trace_observed"][0])
        self.assertFalse(context["root_visible"][0])


def synthetic_event(event_id, windows, credits, context):
    record = {"event_id": event_id, "window_indices": list(range(windows)),
              "fault_type": "cpu", "decision": "tie", "both_zero": False,
              "both_perfect": False, "delta_directed_global": {"top1": 0}}
    scores = {}
    masses = {}
    for mode in errors.MODES:
        scores[mode] = {metric: np.asarray(credits, dtype=float) for metric in errors.METRICS}
        mass = np.zeros((3, windows, 5))
        mass[:, :, 4] = 1 - scores[mode]["top1"]
        masses[mode] = mass
    return {"record": record, "scores": scores, "relation_mass": masses,
            "contexts": {"root_in_visible": np.asarray(context, dtype=np.bool_)}}


class AggregationTests(unittest.TestCase):
    def test_event_equal_not_window_or_seed_inflation(self):
        first = synthetic_event("a", 1, [[1], [0], [0]], [True])
        second = synthetic_event("b", 9, np.ones((3, 9)), [True] * 9)
        summary = errors.aggregate([(first, np.ones(1, dtype=np.bool_)),
                                    (second, np.ones(9, dtype=np.bool_))])
        self.assertAlmostEqual(summary["modes"]["directed"]["metrics"]["top1"], 2 / 3)
        self.assertNotAlmostEqual(summary["modes"]["directed"]["metrics"]["top1"], 28 / 30)
        self.assertEqual(summary["incidents"], 2)
        self.assertEqual(summary["unique_windows"], 10)
        self.assertEqual(summary["seed_window_decisions_per_mode"], 30)
        wrong = summary["modes"]["directed"]["wrong"]
        self.assertAlmostEqual(wrong["total_mass"], 1 / 3)
        self.assertAlmostEqual(wrong["conditional_on_wrong"]["no_observed_connection"], 1)

    def test_mixed_event_overlaps_and_window_subset_is_averaged_first(self):
        first = synthetic_event("a", 2, [[1, 0]] * 3, [True, False])
        second = synthetic_event("b", 1, [[0]] * 3, [True])
        summary = errors.summarize_system([first, second])
        context = summary["root_context"]["root_in_visible"]
        self.assertEqual(context["overlap_event_ids"], ["a"])
        self.assertEqual(context["present"]["incidents"], 2)
        self.assertEqual(context["absent"]["incidents"], 1)
        self.assertEqual(context["present"]["unique_windows"], 2)
        self.assertEqual(context["absent"]["unique_windows"], 1)
        self.assertEqual(context["present"]["modes"]["directed"]["metrics"]["top1"], .5)
        self.assertEqual(context["absent"]["modes"]["directed"]["metrics"]["top1"], 0)
        self.assertEqual(summary["all"]["modes"]["directed"]["metrics"]["top1"], .25)

    def test_conditional_aggregate_ratio_not_average_event_ratios(self):
        first = synthetic_event("a", 1, [[0]] * 3, [True])
        second = synthetic_event("b", 1, [[.5]] * 3, [True])
        for mode in errors.MODES:
            first["relation_mass"][mode][:, :, 4] = 0
            first["relation_mass"][mode][:, :, 1] = 1
        wrong = errors.aggregate([(e, np.ones(1, dtype=np.bool_)) for e in (first, second)])["modes"]["directed"]["wrong"]
        self.assertAlmostEqual(wrong["conditional_on_wrong"]["root_to_wrong"], 2 / 3)
        self.assertAlmostEqual(wrong["conditional_on_wrong"]["no_observed_connection"], 1 / 3)
        perfect = errors.wrong_summary(np.zeros(5), 1)
        self.assertTrue(all(v is None for v in perfect["conditional_on_wrong"].values()))
        with self.assertRaisesRegex(ValueError, "mass mismatch"):
            errors.wrong_summary(np.ones(5), 1)

    def test_partial_credit_and_exact_tie_preserved(self):
        scores = {m: np.asarray([[.1], [.1], [.1]]) for m in errors.METRICS}
        self.assertEqual(errors.metric_mean(scores)["top1"], sum([.1, .1, .1]) / 3)
        self.assertEqual(errors.outcome(.01), "improvement")
        self.assertEqual(errors.outcome(-.01), "worsening")
        self.assertEqual(errors.outcome(0), "tie")
        self.assertEqual(errors.wtl([0, .01, -.01]), {"win": 1, "tie": 1, "loss": 1})


class RejectionTests(unittest.TestCase):
    def test_missing_duplicate_reports_rejected(self):
        reports = [dict(zip(("system", "fold", "seed", "mode"), key))
                   for key in product(errors.SYSTEMS, errors.FOLDS, errors.SEEDS, errors.MODES)]
        self.assertEqual(len(errors.validate_reports(reports)), 54)
        with self.assertRaisesRegex(ValueError, "Missing reports"):
            errors.validate_reports(reports[:-1])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            errors.validate_reports([reports[0]] + reports[:-1])

    def test_provenance_missing_and_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing"):
            errors.check_hash(Path("not-opened"), None)
        with patch.object(errors, "file_hash", return_value="a" * 64):
            with self.assertRaisesRegex(ValueError, "Provenance mismatch"):
                errors.check_hash(Path("not-opened"), "b" * 64)
            self.assertEqual(errors.check_hash(Path("not-opened"), "a" * 64), "a" * 64)
            reader = errors.Inputs()
            reader.record(Path("not-opened"), "a" * 64, "fixture", ("reference_mask",))
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                reader.record(Path("not-opened"), "a" * 64, "other", ("reference_mask",))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            json.loads('{"event":1,"event":2}', object_pairs_hook=errors.unique_object)

    def test_missing_duplicate_npz_members_rejected(self):
        class Archive:
            def __init__(self, files):
                self.files = files

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        for files, message in ((["other"], "Missing NPZ"), (["indices", "indices"], "Duplicate NPZ")):
            with patch.object(errors, "check_hash", return_value="a" * 64), \
                    patch.object(errors.np, "load", return_value=Archive(files)):
                with self.assertRaisesRegex(ValueError, message):
                    errors.Inputs().npz(Path("not-opened"), "a" * 64, "fixture", ("indices",))

    def test_prediction_missing_duplicate_pairing_and_nonfinite_rejected(self):
        bundle = {"indices": np.asarray([4, 5]), "labels": np.asarray([0, 0]),
                  "event_ids": np.asarray(["event", "event"]), "fold_ids": np.asarray([0, 0]),
                  "adjacency": np.zeros((2, 2, 2), dtype=np.bool_)}
        saved = {k: bundle[k].copy() for k in ("indices", "labels", "event_ids")}
        saved["logits"] = np.ones((2, 2))
        np.testing.assert_array_equal(errors.validate_prediction(saved, bundle, 0), [0, 1])
        for indices in (np.asarray([4]), np.asarray([4, 4])):
            broken = dict(saved, indices=indices)
            with self.assertRaisesRegex(ValueError, "pairing"):
                errors.validate_prediction(broken, bundle, 0)
        broken = dict(saved, logits=np.full((2, 2), np.nan))
        with self.assertRaisesRegex(ValueError, "logits"):
            errors.validate_prediction(broken, bundle, 0)

    def test_bundle_duplicate_indices_and_missing_events_rejected(self):
        bundle = {"indices": np.asarray([0, 0]), "labels": np.asarray([0, 0])}
        manifest = {"services": ["service"], "system": "SN"}
        with self.assertRaisesRegex(ValueError, "Duplicate bundle"):
            errors.validate_bundle(bundle, manifest, "SN")
        bundle.update(indices=np.asarray([0, 1]),
                      observed=np.zeros((2, 1, 10, 9), dtype=np.bool_),
                      adjacency=np.zeros((2, 1, 1), dtype=np.bool_),
                      event_ids=np.asarray(["event", "event"]),
                      episode_ids=np.asarray(["event", "event"]), fold_ids=np.asarray([0, 0]))
        manifest.update(native_window_count=2, windows=[{}, {}], faults={"event": {}, "missing": {}})
        with self.assertRaisesRegex(ValueError, "Missing event coverage"):
            errors.validate_bundle(bundle, manifest, "SN")

    def test_saved_metric_mismatch_is_not_suppressed(self):
        with self.assertRaisesRegex(ValueError, "Saved metric mismatch"):
            errors.compare(dict.fromkeys(errors.METRICS, .5), dict.fromkeys(errors.METRICS, .4), "fixture")

    def test_exclusive_output_and_existing_cli_output_rejected(self):
        stream = io.StringIO()
        with patch.object(Path, "open") as opened:
            opened.return_value.__enter__.return_value = stream
            errors.write_result(Path("not-written"), {"status": "PASS"})
            opened.assert_called_once_with("x", encoding="utf-8")
        self.assertEqual(json.loads(stream.getvalue()), {"status": "PASS"})
        with patch.object(Path, "exists", return_value=True), \
                patch.object(errors, "build_diagnostic") as build:
            with self.assertRaises(FileExistsError):
                errors.main()
            build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
