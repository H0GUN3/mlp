"""Synthetic-only checks: no installed solver import and no real fit."""
import io
import unittest

import numpy as np

import benchmark as b


class SyntheticBenchmarkTests(unittest.TestCase):
    def test_recovery_outputs_cannot_target_preserved_attempt(self):
        self.assertEqual(b.FITS, b.HERE / "fits_recovery")
        self.assertEqual(b.REPORT, b.HERE / "benchmark_recovery.json")
        for path in (b.HERE / "benchmark.json", b.HERE / "fits/checks.json"):
            with self.assertRaisesRegex(ValueError, "Output outside declared artifacts"):
                b.save(path, {})

    def setUp(self):
        self.make_knots = b.native_functions()["make_knots"]
        self.lookup = np.zeros(1025, dtype=np.int64)
        self.lookup[5] = 1
        self.lookup[10] = 2

    def test_mapping_lookup_uses_cluster_ids_not_old_feature_numbers(self):
        templates = {"cluster_id_to_feature": {str(90000 + i): i for i in range(1, 1025)}}
        mapping = {"cluster_id_to_feature": {str(90000 + i): i for i in range(1, 257)}}
        lookup = b.event_lookup(templates, mapping)
        np.testing.assert_array_equal(lookup[:257], np.arange(257))
        self.assertTrue(np.all(lookup[257:] == 0))

    def test_mapped_events_equal_original_per_event_jitter(self):
        times = np.array([100, 100, 101, 100, 100], dtype=np.int64)
        ids = np.array([5, 5, 10, 9, 0], dtype=np.int64)
        record, knots = b.group(times, ids, 100, self.lookup, self.make_knots)
        expected = self.make_knots(times, np.array([1, 1, 2, 0, 0]), 100.0, 257)
        self.assertEqual(record["raw_count"], 5)
        self.assertEqual(record["kept_count"], 3)
        self.assertEqual(record["pooled_count"], 1)
        self.assertEqual(record["unknown_count"], 1)
        self.assertEqual(record["key"], b.knot_key(expected))
        self.assertIsNotNone(knots)
        for actual, wanted in zip(knots or [], expected):
            np.testing.assert_array_equal(actual, wanted)
        np.testing.assert_array_equal(expected[0], [0.0, 0.00001])
        np.testing.assert_array_equal(expected[3], [0.0])

    def test_fully_empty_group_is_zero_without_knots_or_solver(self):
        empty = np.array([], dtype=np.int64)
        record, knots = b.group(empty, empty, 100, self.lookup,
                                lambda *args: self.fail("Empty group reached make_knots"))
        self.assertTrue(record["empty"])
        self.assertIsNone(record["key"])
        self.assertIsNone(knots)

    def test_pooled_jitter_horizon_failure_is_not_clipped(self):
        times = np.array([9.99999, 9.99999, 9.99999])
        ids = np.array([8, 9, 0], dtype=np.int64)
        record, knots = b.group(times, ids, 0, self.lookup, self.make_knots)
        self.assertIsNone(knots)
        self.assertFalse(record["empty"])
        self.assertIn("no clipping applied", record["knot_error"])
        np.testing.assert_array_equal(times, [9.99999, 9.99999, 9.99999])

    def test_dedup_is_exact_not_rounded_or_shape_only(self):
        a = self.make_knots(np.array([1.0]), np.array([1]), 0.0, 257)
        c = [k.copy() for k in a]
        self.assertEqual(b.knot_key(a), b.knot_key(c))
        c[1][0] = np.nextafter(c[1][0], 2.0)
        self.assertNotEqual(b.knot_key(a), b.knot_key(c))
        stream = io.BytesIO()
        np.savez_compressed(stream, baseline=np.zeros(257))
        stream.seek(0)
        with np.load(stream, allow_pickle=False) as archive:
            self.assertEqual(archive["baseline"].shape, (257,))

    def test_cap_and_timeout_accounting_never_invents_convergence(self):
        self.assertTrue(b.fit_accounting(50)["cap50_reached"])
        self.assertFalse(b.fit_accounting(41)["cap50_reached"])
        timed = b.fit_accounting(None, True)
        self.assertTrue(timed["timed_out"])
        self.assertIsNone(timed["iterations"])
        self.assertIsNone(timed["cap50_reached"])
        self.assertIn("not asserted", timed["convergence"])
        self.assertEqual(b.available_timeout(0, 100), 60)
        self.assertEqual(b.available_timeout(40, 50), 8)
        self.assertEqual(b.available_timeout(49, 50), 0)


if __name__ == "__main__":
    unittest.main()
