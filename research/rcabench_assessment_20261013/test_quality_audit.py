import copy
import unittest

import pyarrow as pa

from quality_audit import CORE, profile_table, summarize_case


class QualityTest(unittest.TestCase):
    def test_metric_finite_period_and_half_open_bins(self):
        table = pa.table({
            "time": pa.array([0, 10_000_000_000, 20_000_000_000, 21_000_000_000, None],
                             type=pa.timestamp("ns", tz="UTC")),
            "service_name": ["root"] * 5, "metric": ["cpu"] * 5,
            "value": [1.0, float("nan"), 2.0, 3.0, 4.0],
        })
        result = profile_table(table, "metric", ["root", "missing"], 0, 20)
        self.assertEqual(result["outside_closed_period"], 1)
        self.assertEqual(result["nonfinite_values"], 1)
        roots = result["roots"]
        assert isinstance(roots, dict)
        self.assertEqual(roots["root"]["basic_valid_rows"], 2)
        self.assertEqual(roots["root"]["occupied_10s_bins"], 1)
        self.assertEqual(roots["missing"]["basic_valid_rows"], 0)

    def test_trace_boundary_and_missing_identity(self):
        table = pa.table({
            "time": pa.array([0, 20_000_000_000, 10_000_000_000], type=pa.timestamp("ns", tz="UTC")),
            "service_name": ["root"] * 3, "trace_id": ["t", "t", ""],
            "span_id": ["a", "b", "c"], "parent_span_id": ["", "a", "a"],
            "duration": pa.array([1, 2, 3], type=pa.uint64()),
        })
        result = profile_table(table, "trace", ["root"], 0, 20)
        self.assertEqual(result["empty_or_null_identity_rows"], 1)
        self.assertEqual(result["_boundary_end"], {("t", "b")})
        roots = result["roots"]
        assert isinstance(roots, dict)
        self.assertEqual(roots["root"]["basic_valid_rows"], 2)

    def test_marker_is_not_a_quality_verdict_and_missing_root_fails_support(self):
        case = {"case": "x", "root_services": ["root"], "fault_type": 0,
                "files": {".invalid": 0}, "metadata_gate_pass": True}
        files = {name: {"rows": 1, "roots": {"root": {"basic_valid_rows": 1}}} for name in CORE}
        files["normal_traces.parquet"]["_boundary_end"] = {("t", "s")}
        files["abnormal_traces.parquet"]["_boundary_start"] = {("t", "s")}
        result = summarize_case(case, copy.deepcopy(files))
        self.assertTrue(result["invalid_marker"])
        self.assertTrue(result["single_label_basic_row_support"])
        self.assertEqual(result["shared_boundary_trace_span_identities"], 1)
        files["abnormal_traces.parquet"]["roots"]["root"]["basic_valid_rows"] = 0
        self.assertFalse(summarize_case(case, files)["single_label_basic_row_support"])

    def test_unsupported_schema_stays_unverified(self):
        self.assertEqual(profile_table(pa.table({"time": [1]}), "metric", ["root"], 0, 1)
                         ["profile_error"], "missing_columns")


if __name__ == "__main__":
    unittest.main()
