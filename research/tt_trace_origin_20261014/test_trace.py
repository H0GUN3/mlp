import unittest

import numpy as np

from research.tt_trace_origin_20261014 import labels, trace


class TraceTests(unittest.TestCase):
    def windows(self):
        return [{"start": 28800, "end_exclusive": 28810, "root": 0,
                 "event_id": labels.EVENTS[0], "original_index": 1}]

    def test_routing_preserves_duplicates_and_excludes_other_windows(self):
        span = {"startTime": 1500000, "duration": 2000000, "processID": "p",
                "traceID": "t", "spanID": "s"}
        # Nonselected observations are never required to have duration/process fields.
        ignored = {"startTime": 10000000}
        traces = [{"traceID": "t", "processes": {"p": {"serviceName": "ts-food-service"}},
                   "spans": [span, dict(span), ignored]}]
        counts, latency, unique, root_unique, _, _ = trace.collect_traces(
            traces, self.windows(), ["ts-food-service"])
        self.assertEqual(counts[0, 0, 1], 2)
        self.assertEqual(latency[0, 0, 1], 2.)
        self.assertEqual(len(unique[0]), 1)
        self.assertEqual(len(root_unique[0]), 1)
        self.assertEqual(np.count_nonzero(counts), 1)

    def test_overlapping_selection_rejected(self):
        with self.assertRaises(ValueError):
            trace.second_lookup(self.windows() * 2)

    def test_log_formats_and_half_open_boundary(self):
        self.assertEqual(trace.log_second("1970-Jan-01 00:00:01.500 root"), 28801)
        self.assertEqual(trace.log_second("1970-01-01 00:00:01.500 root"), 28801)
        self.assertIsNone(trace.log_second("no timestamp"))
        counts, samples, skipped = trace.collect_logs(
            {"ts-food-service": ["1970-Jan-01 00:00:01.500 inside",
                                 "1970-Jan-01 00:00:10.000 outside", "untimed"]},
            self.windows(), ["ts-food-service"])
        self.assertEqual(counts[0, 0], 1)
        self.assertEqual(len(samples[labels.EVENTS[0]]), 1)
        self.assertEqual(skipped, {"ts-food-service": 1})


if __name__ == "__main__":
    unittest.main()
