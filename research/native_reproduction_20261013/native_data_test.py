"""Focused native preprocessing checks; --real checks prepared/built outputs."""
import argparse
import json
from typing import Any
import unittest

import numpy as np

import native_data as data


class NativeDataTests(unittest.TestCase):
    def test_source_contract(self) -> None:
        self.assertEqual(len(data.SERVICES["SN"]), 12)
        self.assertEqual(len(data.SERVICES["TT"]), 27)
        self.assertEqual(data.SERVICES["SN"][0], "social-graph-service")
        self.assertEqual(data.SERVICES["TT"][-1], "ts-verification-code-service")
        self.assertEqual(data.METRICS[-2:], ["rx_bytes", "tx_bytes"])
        sn = data.edges("SN")
        self.assertEqual(len(sn[0]), 24)
        self.assertEqual(sn[0][0], 1)
        self.assertEqual(sn[1][0], 1)
        self.assertEqual(len(data.edges("TT")[0]), 44)

    def test_clock_alignment(self) -> None:
        original = 1650161565.787468
        self.assertEqual(int(original) + data.RECORD_SHIFT, 1650219165)
        log = "prefix [2022-Apr-17 10:12:50.490796] message"
        self.assertAlmostEqual(data.log_timestamp(log), 1650219170.490796, places=5)
        self.assertEqual(1650190365490796 // 1000000 + data.TRACE_SHIFT, 1650219165)
        self.assertAlmostEqual(
            data.log_timestamp("2022-04-17 10:12:50.490"), 1650219170.490, places=5)

    def test_windows_and_fault_overlap(self) -> None:
        starts = data.window_starts(100, 125)
        np.testing.assert_array_equal(starts, [100, 110])
        fault = {"start": 105, "end_inclusive": 110, "root": 1,
                 "event_id": "r:0", "root_fault_group": "s|cpu"}
        labels, ids, groups = data.window_labels(starts, [fault])
        np.testing.assert_array_equal(labels, [1, 1])
        self.assertEqual(ids.tolist(), ["r:0", "r:0"])
        self.assertEqual(groups.tolist(), ["s|cpu", "s|cpu"])
        enclosed = dict(fault, start=103, end_inclusive=104)
        np.testing.assert_array_equal(data.window_labels(starts, [enclosed])[0], [1, -1])
        next_window = dict(fault, start=110, end_inclusive=119)
        np.testing.assert_array_equal(data.window_labels(starts, [next_window])[0], [-1, 1])
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            data.window_labels(starts, [fault, dict(fault, root=2)])
        record = {"faults": [{"name": "socialnetwork-text-service-1",
                              "fault": "cpu_load", "start": 100.9, "duration": 120}]}
        rounded = data.rounded_faults(record, "SN", "r")[0]
        self.assertEqual(rounded["start"], 100 + data.RECORD_SHIFT)
        self.assertEqual(rounded["end_inclusive"], 220 + data.RECORD_SHIFT)

    def test_half_open_logs_unseen_and_tail(self) -> None:
        class Miner:
            def match(self, line: str) -> Any:
                return None
        start = data.log_timestamp("2022-04-17 10:12:50.000")
        lines = [
            "2022-04-17 10:12:50.000",
            "2022-04-17 10:12:59.999",
            "2022-04-17 10:13:00.000",
            "2022-04-17 10:13:10.000",
            "2022-04-17 10:13:15.000",
        ]
        rows, counts = data.log_rows(
            json.dumps({"s": lines}).encode(), Miner(), ["known"], ["s"],
            int(start), int(start) + 25, 7)
        self.assertEqual([r[0] for r in rows], [7, 7, 8])
        self.assertEqual([r[2] for r in rows], [0, 0, 0])
        self.assertEqual(counts["used_lines"], 3)
        self.assertEqual(counts["trailing_partial_window_lines"], 1)
        self.assertEqual(counts["record_clipped_lines"], 1)

    def test_hawkes_origin_horizon_and_source_placeholders(self) -> None:
        times = np.array([100.0, 100.0, 109.999])
        ids = np.array([1, 1, 2], dtype=np.int64)
        knots = data.make_knots(times, ids, 100, 4)
        np.testing.assert_array_equal(knots[0], [0])
        np.testing.assert_allclose(knots[1], [0, 1e-5])
        np.testing.assert_array_equal(knots[3], [0])
        shifted = data.make_knots(times + 1000000, ids, 1000100, 4)
        for left, right in zip(knots, shifted):
            np.testing.assert_allclose(left, right, atol=1e-9)
        result = data.fit_hawkes((0, 0, knots, 42))
        repeat = data.fit_hawkes((0, 0, knots, 42))
        self.assertEqual(result["baseline"].shape, (4,))
        self.assertTrue(np.isfinite(result["baseline"]).all())
        self.assertGreater(np.count_nonzero(result["baseline"]), 0)
        np.testing.assert_array_equal(result["baseline"], repeat["baseline"])
        self.assertGreater(result["iterations"], 0)
        with self.assertRaises(ValueError):
            data.make_knots(np.array([110.]), np.array([1]), 100, 4)
        with self.assertRaises(ValueError):
            data.make_knots(np.array([109.999999, 109.999999]), np.array([1, 1]), 100, 4)

    def test_duplicate_conflict_weighting(self) -> None:
        audit = data.SpanAudit()
        trace = {"traceID": "t"}
        span = {"traceID": "t", "spanID": "s", "startTime": 1, "duration": 100}
        audit.observe(trace, span, "service", "r", True)
        audit.observe(trace, span, "service", "r", True)
        audit.observe(trace, dict(span, duration=200), "service", "r2", False)
        result = audit.summary()
        self.assertEqual(result["counts"]["duplicate_identity_occurrences"], 2)
        self.assertEqual(result["counts"]["kept_occurrences"], 2)
        self.assertEqual(result["counts"]["conflicting_feature_occurrences"], 1)
        self.assertIn("no deduplication", result["weighting"])

    def test_shapes_provenance_and_invalid_inputs(self) -> None:
        arrays = {
            "metrics": np.ones((2, 3, 10, 7)),
            "traces": np.zeros((2, 3, 10, 2)), "logs": np.ones((2, 3, 4)),
            "labels": np.array([-1, 2], dtype=np.int64),
            "window_start": np.array([100, 110], dtype=np.int64),
            "run_id": np.array(["r", "r"]), "event_id": np.array(["", "e"]),
            "root_fault_group": np.array(["", "s|cpu"]),
        }
        data.validate_arrays(arrays, 3, 4)
        metadata = data.raw_metadata(arrays, {
            "dataset": "SN", "services": ["a", "b", "c"],
            "edges": [[0, 1], [1, 2]], "event_num": 4,
        })
        self.assertEqual(metadata["system"], "SN")
        self.assertEqual(metadata["edges"], [[0, 1], [1, 2]])
        self.assertEqual(metadata["event_count"], 4)
        self.assertEqual(len(metadata["windows"]), 2)
        self.assertIsNone(metadata["windows"][0]["event_id"])
        self.assertIsNone(metadata["windows"][0]["root_fault_group"])
        self.assertEqual(metadata["windows"][1]["end"], 119)
        bad = dict(arrays, labels=np.array([-2, 2]))
        with self.assertRaises(ValueError):
            data.validate_arrays(bad, 3, 4)
        bad = dict(arrays, logs=np.full((2, 3, 4), np.nan))
        with self.assertRaises(ValueError):
            data.validate_arrays(bad, 3, 4)
        bad_trace = arrays["traces"].copy()
        bad_trace[0, 0, 0, 1] = 1
        with self.assertRaises(ValueError):
            data.validate_arrays(dict(arrays, traces=bad_trace), 3, 4)
        invalid_intervals: Any = ((0, 9), (0.5, 10), (10, 0))
        for start, end in invalid_intervals:
            with self.assertRaises(ValueError):
                data.window_starts(start, end)
        for line in ("missing", "2022-99-99 99:99:99.001"):
            with self.assertRaises(ValueError):
                data.log_timestamp(line)
        with self.assertRaises(ValueError):
            data.make_knots(np.array([100.]), np.array([4]), 100, 4)
        with self.assertRaises(ValueError):
            data.make_knots(np.array([np.nan]), np.array([0]), 100, 4)
        with self.assertRaises(ValueError):
            data.safe_member("../../outside")


def real_checks() -> None:
    for dataset in ("SN", "TT"):
        arrays, metadata = data.load_prepared(dataset)
        nodes, events = len(metadata["services"]), metadata["event_num"]
        assert len(arrays["labels"]) == (564 if dataset == "SN" else 5814)
        assert arrays["metrics"].shape == (len(arrays["labels"]), nodes, 10, 7)
        assert arrays["traces"].shape == (len(arrays["labels"]), nodes, 10, 2)
        assert np.count_nonzero(arrays["traces"][:, :, :, 0]) > 0
        assert np.count_nonzero(arrays["traces"][:, :, :, 1]) == 0
        assert len(arrays["log_timestamp"]) > 0
        tasks = data.event_tasks(arrays, nodes, events)
        assert len(tasks) > 0
        sample = data.fit_hawkes(tasks[0])
        assert np.count_nonzero(sample["baseline"]) > 0
        assert np.isfinite(sample["baseline"]).all()
        for run in np.unique(arrays["run_id"]):
            starts = arrays["window_start"][arrays["run_id"] == run]
            np.testing.assert_array_equal(np.diff(starts), np.full(len(starts) - 1, 10))
        path = data.INPUTS / dataset / "raw.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as source:
                final = {key: source[key] for key in source.files}
            assert set(final) == {"metrics", "traces", "logs", "labels"}
            data.validate_arrays(dict(arrays, **final), nodes, events)
            assert np.count_nonzero(final["logs"]) > 0
            assert np.array_equal(final["metrics"], arrays["metrics"])
            assert np.array_equal(final["traces"], arrays["traces"])
            metadata_path = data.INPUTS / dataset / "metadata.json"
            final_metadata = json.loads(metadata_path.read_text())
            assert final_metadata["system"] == dataset
            assert final_metadata["event_count"] == events
            assert len(final_metadata["windows"]) == len(final["labels"])
            assert all(len(pair) == 2 for pair in final_metadata["edges"])
            assert data.file_hash(path) == final_metadata["raw_npz_sha256"]
            build_summary = json.loads((data.INPUTS / (dataset + "_build.json")).read_text())
            assert data.file_hash(metadata_path) == build_summary["metadata_sha256"]
            faults_by_run = {run["run_id"]: run["faults"] for run in final_metadata["runs"]}
            for index, window in enumerate(final_metadata["windows"]):
                assert window["end"] == window["start"] + 9
                hits = [fault for fault in faults_by_run[window["run_id"]]
                        if fault["start"] <= window["end"]
                        and fault["end_inclusive"] >= window["start"]]
                roots = {fault["root"] for fault in hits}
                assert len(roots) <= 1
                assert final["labels"][index] == (next(iter(roots)) if roots else -1)
                assert window["event_id"] == (";".join(f["event_id"] for f in hits) or None)
                assert window["root_fault_group"] == (
                    ";".join(sorted({f["root_fault_group"] for f in hits})) or None)
        print("NATIVE_REAL_TEST_PASS {} W={} E={} fits={}".format(dataset, len(arrays["labels"]), events, len(tasks)), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeDataTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.real:
        real_checks()
