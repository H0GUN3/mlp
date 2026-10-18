"""Focused feature checks, using synthetic data only; optional real-artifact replay."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from . import features as data


class FeatureTests(unittest.TestCase):
    def test_train_normal_only_against_validation_test_and_fault_changes(self):
        values = np.tile(np.arange(10, dtype=float)[None, None, :, None], (5, 2, 1, 9))
        observed = np.ones(values.shape, dtype=bool)
        labels = np.array([-1, -1, -1, -1, 1], dtype=np.int64)
        partition = np.array(["train", "train", "validation", "test", "train"])
        reference = data.fit_reference(values, observed, labels, partition)
        before = data.window_features(values[:2], observed[:2], reference)
        changed = values.copy()
        changed[2:] = 1e12
        changed_observations = observed.copy()
        changed_observations[2:] = False
        again = data.fit_reference(changed, changed_observations, labels, partition)
        for key in reference:
            np.testing.assert_array_equal(reference[key], again[key])
        for left, right in zip(before, data.window_features(changed[:2], observed[:2], again)):
            np.testing.assert_array_equal(left, right)
        np.testing.assert_array_equal(reference["count"], np.full((2, 9), 20))
        np.testing.assert_array_equal(reference["median"], np.full((2, 9), 4.5))
        np.testing.assert_array_equal(reference["scale"], np.full((2, 9), 5.))

    def test_scale_floor_and_valid_values_only(self):
        values = np.zeros((1, 1, 10, 9))
        values[..., 1] = 100
        values[0, 0, :5, 2] = [1, 2, 3, 4, 5]
        values[0, 0, 5:, 2] = np.nan
        observed = np.ones(values.shape, dtype=bool)
        observed[0, 0, 5:, 2] = False
        reference = data.fit_reference(values, observed, np.array([-1]), np.array(["train"]))
        self.assertEqual(reference["scale"][0, 0], 1e-8)
        self.assertEqual(reference["scale"][0, 1], 5.)
        self.assertEqual(reference["median"][0, 2], 3.)
        self.assertEqual(reference["scale"][0, 2], 2.)
        self.assertEqual(reference["count"][0, 2], 5)

    def test_signed_log_persistence_and_observed_seconds_denominator(self):
        values = np.full((1, 1, 10, 9), np.nan)
        observed = np.zeros(values.shape, dtype=bool)
        values[0, 0, :3, 0] = [-3, 2, 4]
        observed[0, 0, :3, 0] = True
        reference = {
            "median": np.zeros((1, 9)), "scale": np.ones((1, 9)),
            "mask": np.ones((1, 9), dtype=bool),
        }
        x, mask, coverage = data.window_features(values, observed, reference)
        self.assertAlmostEqual(float(x[0, 0, 0]), (-np.log(4) + np.log(3) + np.log(5)) / 3, places=6)
        self.assertAlmostEqual(float(x[0, 0, 9]), 2 / 3, places=6)
        self.assertAlmostEqual(float(coverage[0, 0, 0]), .3, places=6)
        self.assertTrue(mask[0, 0, 0])
        self.assertFalse(mask[0, 0, 1])
        self.assertEqual(x[0, 0, 1], 0)
        self.assertEqual(coverage[0, 0, 1], 0)
        np.testing.assert_array_equal(mask[..., :9], mask[..., 9:])
        np.testing.assert_array_equal(coverage[..., :9], coverage[..., 9:])

    def test_missing_reference_keeps_current_coverage_not_feature(self):
        values = np.ones((2, 1, 10, 9))
        observed = np.ones(values.shape, dtype=bool)
        observed[0, :, :, 7] = False
        reference = data.fit_reference(values, observed, np.array([-1, -1]), np.array(["train", "validation"]))
        x, mask, coverage = data.window_features(values, observed, reference)
        self.assertFalse(reference["mask"][0, 7])
        self.assertEqual(reference["count"][0, 7], 0)
        self.assertFalse(mask[1, 0, 7])
        self.assertFalse(mask[1, 0, 16])
        self.assertEqual(coverage[1, 0, 7], 1)
        self.assertEqual(coverage[1, 0, 16], 1)
        self.assertEqual(x[1, 0, 7], 0)
        self.assertEqual(x[1, 0, 16], 0)
        # An arbitrary missing placeholder, even NaN, cannot alter valid features.
        changed = values.copy()
        changed[~observed] = np.nan
        for left, right in zip((x, mask, coverage), data.window_features(changed, observed, reference)):
            np.testing.assert_array_equal(left, right)

    def trace_fixture(self, folder: Path):
        start = 30000
        run = {"record_start": start, "record_end_exclusive": start + 31}
        def span(second, duration, identity):
            return {"traceID": "t", "spanID": identity, "processID": "p",
                    "startTime": (start + second - 28800) * 1000000 + 999999,
                    "duration": duration}
        duplicated = span(1, 1000000, "duplicate")
        spans = [
            span(-1, 8, "before"), span(0, 0, "true-zero"),
            duplicated, span(1, 3000000, "other"), duplicated,
            span(10, 999999999, "held-out"),
            span(20, 2000000, "selected"),
            span(30, 7, "trailing"), span(31, 8, "after"),
        ]
        trace = {"traceID": "t", "spans": spans, "processes": {"p": {"serviceName": "s"}}}
        path = folder / "spans.json"
        path.write_text(json.dumps([trace]) + "\n")
        return path, run, data.file_hash(path)

    def test_stream_zero_absent_duplicates_clock_intervals_and_native_equality(self):
        with tempfile.TemporaryDirectory(dir=str(data.OUTPUT), prefix=".test-") as temporary:
            path, run, digest = self.trace_fixture(Path(temporary))
            latency, count, audit, actual_hash = data.reconstruct_trace(
                path, ["s"], run, [30000, 30020], digest)
            expected = np.zeros((2, 1, 10))
            expected[0, 0, 1] = 5 / 3
            expected[1, 0, 0] = 2
            data.require_trace_equal(latency, expected)
            self.assertEqual(actual_hash, digest)
            self.assertEqual(count[0, 0, 0], 1)
            self.assertEqual(count[0, 0, 1], 3)
            self.assertEqual(count[0, 0, 2], 0)
            self.assertEqual(int(count.sum()), 5)
            self.assertEqual(audit["raw_span_occurrences"], 9)
            self.assertEqual(audit["kept_occurrences"], 7)
            self.assertEqual(audit["record_clipped_occurrences"], 2)
            self.assertEqual(audit["selected_zero_duration_occurrences"], 1)
            self.assertEqual(audit["selected_observed_zero_latency_seconds"], 1)
            observed = np.ones((2, 1, 10, 9), dtype=bool)
            observed[..., 7] = count > 0
            values = np.zeros(observed.shape)
            values[..., 7], values[..., 8] = latency, count
            reference = data.fit_reference(values, observed, np.array([-1, -1]), np.array(["train", "validation"]))
            x, mask, coverage = data.window_features(values, observed, reference)
            self.assertEqual(reference["count"][0, 7], 2)
            self.assertTrue(mask[0, 0, 7])
            self.assertAlmostEqual(float(coverage[0, 0, 7]), .2, places=6)
            self.assertEqual(coverage[0, 0, 8], 1)
            self.assertEqual(reference["median"][0, 8], 0)
            self.assertTrue(mask[0, 0, 8])
            self.assertTrue(np.isfinite(x).all())
            with self.assertRaisesRegex(ValueError, "differs"):
                data.require_trace_equal(latency, expected + 1)
            with self.assertRaisesRegex(ValueError, "Hash mismatch"):
                data.reconstruct_trace(path, ["s"], run, [30000], "0" * 64)
            with self.assertRaisesRegex(ValueError, "Hash mismatch"):
                data.require_hash(path, "0" * 64)
            with self.assertRaisesRegex(ValueError, "grid"):
                data.reconstruct_trace(path, ["s"], run, [30001], digest)

    def test_invalid_spans_and_observed_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory(dir=str(data.OUTPUT), prefix=".test-") as temporary:
            path, run, _ = self.trace_fixture(Path(temporary))
            payload = json.loads(path.read_text())
            payload[0]["spans"][0]["duration"] = -1
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "Invalid native span"):
                data.reconstruct_trace(path, ["s"], run, [30000], data.file_hash(path))
        values = np.full((1, 1, 10, 9), np.nan)
        observed = np.ones(values.shape, dtype=bool)
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            data.fit_reference(values, observed, np.array([-1]), np.array(["train"]))

    def test_original_split_complete_disjoint_seed42(self):
        for count, expected in ((564, (316, 78, 169, 1)), (5814, (3256, 813, 1744, 1))):
            split = data.original_split(count)
            self.assertEqual(tuple(len(v) for v in split.values()), expected)
            flat = np.concatenate(list(split.values()))
            np.testing.assert_array_equal(flat, np.random.RandomState(42).permutation(count))
            np.testing.assert_array_equal(np.sort(flat), np.arange(count))

    def test_final_output_refusal_and_exact_contract(self):
        with tempfile.TemporaryDirectory(dir=str(data.OUTPUT), prefix=".test-") as temporary:
            folder = Path(temporary)
            data.refuse_outputs(folder, ("SN", "TT"))
            path = folder / "TT.json"
            path.write_text("keep")
            with self.assertRaisesRegex(FileExistsError, "Refusing"):
                data.refuse_outputs(folder, ("SN", "TT"))
            self.assertEqual(path.read_text(), "keep")
        arrays = {
            "x": np.zeros((2, 1, 18), dtype=np.float32),
            "mask": np.zeros((2, 1, 18), dtype=bool),
            "coverage": np.zeros((2, 1, 18), dtype=np.float32),
            "labels": np.array([-1, 0], dtype=np.int64),
            "indices": np.array([3, 7], dtype=np.int64),
            "event_ids": np.array(["", "incident"]),
            "partition": np.array(["train", "validation"]),
        }
        data.validate_output(arrays, 1)
        for key, invalid in (
            ("partition", np.array(["train", "test"])),
            ("indices", np.array([3, 3], dtype=np.int64)),
            ("event_ids", np.array(["wrong", "incident"])),
            ("x", np.ones((2, 1, 18), dtype=np.float32)),
        ):
            with self.assertRaises(ValueError):
                data.validate_output(dict(arrays, **{key: invalid}), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Verify saved feature artifacts, no raw span replay")
    args = parser.parse_args()
    data.OUTPUT.mkdir(exist_ok=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FeatureTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.real:
        data.verify_artifacts()
    print("FEATURE_TESTS_PASSED", flush=True)


if __name__ == "__main__":
    main()
