"""Routing/identity boundaries and a small actual native Hawkes integration."""
from collections import Counter
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import research.tt_native_support_20261014.prepare as prep


def log_line(stamp, content):
    text = datetime.fromtimestamp(stamp - prep.native.LOG_SHIFT, timezone.utc)
    return text.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + content


def fixture():
    start = 1650000000
    run = {"record_start": start, "record_end_exclusive": start + 40, "run_id": "fixture"}
    windows = [{"run_id": "fixture", "start": start, "end": start + 9},
               {"run_id": "fixture", "start": start + 20, "end": start + 29}]
    return start, windows, prep.Router(run, windows, [0, 1])


def span_trace(stamp, duration=1000000, span_id="span", service="service"):
    return {
        "traceID": "trace", "processes": {"p": {"serviceName": service}},
        "spans": [{"traceID": "trace", "spanID": span_id, "processID": "p",
                   "startTime": int((stamp - prep.native.TRACE_SHIFT) * 1000000),
                   "duration": duration}],
    }


class PreparationTests(unittest.TestCase):
    def test_original_mask_exact_and_protected_excluded(self):
        parts = prep.original_split(23)
        allowed = np.r_[parts["train"], parts["validation"]].astype(np.int64)
        prep.check_mask(allowed, 23)
        for replacement in (parts["test"][0], parts["unassigned"][0], allowed[0]):
            changed = allowed.copy()
            changed[-1] = replacement
            with self.assertRaises(ValueError):
                prep.check_mask(changed, 23)
        with self.assertRaises(ValueError):
            prep.check_mask(allowed[:-1], 23)

    def test_router_half_open_boundaries_and_unselected_window(self):
        start, _, router = fixture()
        self.assertEqual(router.route(start), (0, start))
        self.assertEqual(router.route(start + 9.999), (0, start))
        self.assertIsNone(router.route(start + 10))
        self.assertIsNone(router.route(start + 19.999))
        self.assertEqual(router.route(start + 20), (1, start + 20))
        self.assertIsNone(router.route(start + 30))
        self.assertIsNone(router.route(start - .001))
        self.assertIsNone(router.route(start + 40))

    def test_log_timestamp_before_match_no_validation_template_fit(self):
        start, _, router = fixture()
        miner = Mock()
        miner.match.return_value = None
        body = json.dumps({"service": [
            log_line(start + 10, "PROTECTED CONTENT"),
            log_line(start, "selected normal"),
            log_line(start + 20, "selected validation"),
            log_line(start + 40, "outside record"),
        ]}).encode()
        groups, audit = prep.selected_logs(body, miner, ["training template"], ["service"], router)
        self.assertEqual(set(groups), {(0, 0), (1, 0)})
        self.assertEqual(audit["selected_lines"], 2)
        self.assertEqual(audit["unselected_lines_content_not_used"], 2)
        self.assertEqual(miner.match.call_count, 2)
        self.assertTrue(all("PROTECTED" not in call.args[0] for call in miner.match.call_args_list))
        miner.add_log_message.assert_not_called()

    def test_spans_route_before_protected_content_and_keep_duplicate_latency(self):
        start, _, router = fixture()
        sums = np.zeros((2, 1, 10), dtype=np.float64)
        counts = np.zeros((2, 1, 10), dtype=np.int64)
        unique = np.zeros((2, 1), dtype=np.int64)
        first = span_trace(start + 1, duration=1000000)
        second = span_trace(start + 1, duration=3000000, span_id="second")
        protected = {"spans": [{"startTime": int((start + 10 - prep.native.TRACE_SHIFT) * 1000000),
                                "duration": "bad", "traceID": None, "processID": "missing"}]}
        records = {}
        audit = prep.selected_spans([protected, first, copy.deepcopy(first), second],
                                    ["service"], router, sums, counts, unique, records)
        self.assertEqual(unique[0, 0], 2)
        self.assertEqual(counts[0, 0, 1], 3)
        self.assertAlmostEqual(sums[0, 0, 1] / counts[0, 0, 1], 5 / 3)
        self.assertEqual(audit["duplicate_selected_occurrences"], 1)
        self.assertEqual(audit["unselected_occurrences_content_not_used"], 1)
        self.assertEqual(unique[1, 0], 0)

    def test_selected_identity_service_time_duration_conflicts_rejected(self):
        start, _, router = fixture()
        original = span_trace(start + 1)
        variants = [
            span_trace(start + 1, duration=2),
            span_trace(start + 2),
            span_trace(start + 21),
            span_trace(start + 1, service="other"),
        ]
        for changed in variants:
            with self.subTest(changed=changed):
                sums = np.zeros((2, 2, 10))
                counts = np.zeros((2, 2, 10), dtype=np.int64)
                unique = np.zeros((2, 2), dtype=np.int64)
                with self.assertRaisesRegex(ValueError, "Conflicting"):
                    prep.selected_spans([original, changed], ["service", "other"], router,
                                        sums, counts, unique, {})
        for key, value in (("duration", -1), ("traceID", "wrong"), ("spanID", "")):
            changed = copy.deepcopy(original)
            changed["spans"][0][key] = value
            with self.assertRaises(ValueError):
                prep.selected_spans([changed], ["service"], router, np.zeros((2, 1, 10)),
                                    np.zeros((2, 1, 10), dtype=np.int64),
                                    np.zeros((2, 1), dtype=np.int64), {})

    def test_actual_hawkes_integration_seed_jitter_placeholders_and_zero_group(self):
        start, windows, router = fixture()
        miner = Mock()
        miner.match.return_value = None
        body = json.dumps({"service": [log_line(start + 1, "a"), log_line(start + 1, "b")]}).encode()
        groups, _ = prep.selected_logs(body, miner, ["auxnormal template"], ["service"], router)
        task = prep.hawkes_task(0, 0, groups[(0, 0)],
                               {"indices": np.array([73, 88], dtype=np.int64)}, windows, 2)
        self.assertEqual(task[3], 42 + 73 * 27)
        np.testing.assert_array_equal(task[2][1], [0.0])
        np.testing.assert_allclose(task[2][0], [1.0, 1.00001], rtol=0, atol=1e-12)
        logs = np.zeros((2, 1, 2), dtype=np.float64)
        result = prep.native.fit_hawkes(task)
        logs[0, 0] = result["baseline"]
        self.assertTrue(np.isfinite(logs).all())
        self.assertTrue((logs >= 0).all())
        np.testing.assert_array_equal(logs[1, 0], [0., 0.])
        repeat = prep.native.fit_hawkes(task)
        np.testing.assert_array_equal(repeat["baseline"], result["baseline"])
        print("TEST_HAWKES iterations={} warnings={}".format(result["iterations"], result["warnings"]))

    def test_permitted_real_manifest_metadata_and_fold_support(self):
        with patch.object(prep.native, "load_prepared", side_effect=AssertionError("Forbidden loader")), \
                patch.object(prep.native, "prepare", side_effect=AssertionError("Forbidden prepare")), \
                patch.object(prep.native, "build", side_effect=AssertionError("Forbidden build")):
            manifest = json.loads((prep.ALLOWED / "TT.json").read_text())
            metadata = json.loads((prep.NATIVE / "native_inputs" / "TT_metadata.json").read_text())
            self.assertEqual(prep.file_hash(prep.NATIVE / "native_data.py"),
                             manifest["provenance"]["native_source"]["feature_build_source_sha256"])
            with np.load(prep.ALLOWED / "TT.npz", allow_pickle=False) as bundle:
                arrays = {key: bundle[key] for key in ("values",) + prep.ROW_KEYS}
            result = prep.check_selection(arrays, manifest, metadata)
            self.assertEqual(result["windows"], 4069)
            self.assertEqual(result["incidents"], 81)
            self.assertEqual(result["protected_selected_rows"], 0)
            self.assertEqual(Counter(arrays["fold_ids"].tolist()),
                             Counter({0: 1366, 1: 1368, 2: 1335}))

    def test_exclusive_publication_retains_existing_bytes(self):
        prep.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=prep.OUT, prefix="test_publication_") as folder:
            directory = Path(folder)
            output = directory / "TT.npz"
            first = directory / "attempt1"
            second = directory / "attempt2"
            first.mkdir()
            second.mkdir()
            original = {"x": np.array([1], dtype=np.int64)}
            digest = prep.publish_npz(output, original, first)
            with self.assertRaises(FileExistsError):
                prep.publish_npz(output, {"x": np.array([2])}, second)
            self.assertEqual(prep.file_hash(output), digest)
            self.assertTrue((second / "TT.npz.partial").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
