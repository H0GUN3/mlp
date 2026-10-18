"""Focused fixtures; no original observations or fitted artifacts are opened."""
import copy
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from research.re2_ob_known_condition_20261018 import prepare as prep


class PrepareTests(unittest.TestCase):
    def test_label_boundary(self):
        starts = np.array([100, 110], dtype=np.int64)
        np.testing.assert_array_equal(prep.pure.global_labels(starts, 110, 2), [-1, 2])
        np.testing.assert_array_equal(prep.pure.global_labels(starts, 109, 2), [2, 2])

    def test_train_node_union_sorted_edges_and_unknown_validation_stop(self):
        rows = [{"case": "t", "partition": "train", "root_cause_service": "a"},
                {"case": "v", "partition": "validation", "root_cause_service": "b"}]
        metadata = {"t": {"services": ["c", "a", "b", "BlackHoleCluster"],
                          "observed_edges": [["c", "b"], ["BlackHoleCluster", "b"]]},
                    "v": {"services": ["a", "b"], "observed_edges": [["b", "a"]]}}
        names, edges = prep.inventory(rows, metadata)
        self.assertEqual(names, ["a", "b", "c"])
        self.assertEqual(edges.shape, (4, 2))
        self.assertEqual(edges.tolist(), [[0, 0], [1, 1], [2, 1], [2, 2]])
        metadata["v"]["services"].append("unknown")
        with self.assertRaisesRegex(ValueError, "Unknown validation node"):
            prep.inventory(rows, metadata)

    def test_templates_normal_only_validation_mutations_remain_frozen_unknown(self):
        miner = prep.pure.new_miner()
        self.assertEqual(prep.pure.fit_nominal(miner, [
            (99, "a", "known steady message"),
            (100, "a", "injection boundary excluded"),
            (101, "a", "fault excluded")], 100), 1)
        clusters = prep.pure.cluster_records(miner)
        mapping = {str(c["cluster_id"]): i + 1 for i, c in enumerate(clusters)}
        self.assertGreater(prep.pure.match_event(miner, mapping, "known steady message"), 0)
        for message in ("validation unique", "validation mutated", "fault excluded"):
            self.assertEqual(prep.pure.match_event(miner, mapping, message), 0)
        self.assertEqual(prep.pure.cluster_records(miner), clusters)

    def test_exact_role_exclusion_preserves_other_nodes_and_unknown_stop(self):
        names = ["frontend", "frontendservice", "frontend-external", "frontend-check-extra"]
        rows = [{"case": "t", "partition": "train", "root_cause_service": "frontend"},
                {"case": "v", "partition": "validation", "root_cause_service": "frontend"}]
        metadata = {
            "t": {"services": names + ["frontend-check"], "observed_edges": [
                ["frontend-check", "frontend"], ["frontend", "frontendservice"]]},
            "v": {"services": names + ["frontend-check"], "observed_edges": []},
        }
        services, edges = prep.inventory(rows, metadata)
        self.assertEqual(services, sorted(names))
        self.assertEqual(len(edges), len(names) + 1)
        self.assertNotIn("frontend-check", prep.pure.PROXIES)
        metadata["t"]["services"].remove("frontend-check")
        self.assertEqual(prep.inventory(rows, metadata)[0], services)
        metadata["v"]["services"].append("unapproved-node")
        with self.assertRaisesRegex(ValueError, "Unknown validation node"):
            prep.inventory(rows, metadata)

    def test_owned_observation_exclusion_accounting_alignment_and_logs(self):
        names = ["frontend", "frontend-check", "frontend-external", "frontendservice"]
        metrics = np.arange(2 * 4 * 10 * 8, dtype=np.float64).reshape(2, 4, 10, 8)
        traces = np.zeros((2, 4, 10, 2), dtype=np.float64)
        traces[:, 0, :, 0] = 7
        traces[:, 1, :, 0] = 5
        retained = np.zeros((2, 4, 10), dtype=np.int64)
        retained[:, 0] = 3
        retained[:, 1] = 2
        arrays = {"metrics": metrics, "metric_observed": np.isfinite(metrics),
                  "traces": traces, "retained_count": retained,
                  "starts": np.array([100, 110], dtype=np.int64)}
        meta = {"services": names, "logs_retained": 5, "observed_edges": [
            ["frontend-check", "frontend"], ["frontend", "frontendservice"]]}
        counts = prep.numeric_accounting(meta, arrays)
        excluded = counts["excluded"]["frontend-check"]
        self.assertEqual(excluded["metric_observed_cells"], 160)
        self.assertEqual(excluded["metric_observed_windows"], 2)
        self.assertEqual(excluded["metric_families"]["mem"]["observed_cells"], 20)
        self.assertEqual(excluded["trace_retained_count"], 40)
        self.assertEqual(excluded["trace_nonzero_latency_cells"], 20)
        self.assertEqual(excluded["edge_count"], 1)
        self.assertEqual(counts["retained"]["frontend"]["trace_retained_count"], 60)
        row = {"case": "v", "partition": "validation", "inject_time": 110,
               "root_cause_service": "frontend"}
        services = sorted(set(names) - prep.ROLE_EXCLUSIONS)
        with patch.object(prep, "arrays_read", return_value=arrays):
            aligned = prep.aligned_case(row, meta, services)
        self.assertEqual(len(aligned["starts"]), 2)
        np.testing.assert_array_equal(aligned["labels"], [-1, services.index("frontend")])
        for name in services:
            np.testing.assert_array_equal(aligned["metrics"][:, services.index(name)],
                                          metrics[:, names.index(name)])
            np.testing.assert_array_equal(aligned["traces"][:, services.index(name)],
                                          traces[:, names.index(name)])
        prep.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(prep.OUT)) as folder:
            stage = Path(folder)
            (stage / "v").mkdir()
            records = [(100, "frontend-check", "excluded init message"),
                       (100, "frontend", "retained frontend message"),
                       (101, "frontendservice", "retained service message"),
                       (102, "frontend-external", "retained external message"),
                       (110, "frontend", "fault must not fit")]
            with gzip.open(stage / "v/logs.jsonl.gz", "xt", encoding="utf8") as stream:
                for record in records:
                    stream.write(json.dumps(record) + "\n")
            accounting = {}
            with patch.object(prep, "STAGE1", stage):
                filtered = list(prep.log_records("v", meta, accounting))
            self.assertEqual(filtered, records[1:])
            self.assertEqual(accounting["source_rows"], 5)
            self.assertEqual(accounting["excluded_by_service"], {"frontend-check": 1})
            self.assertEqual(accounting["retained_by_service"]["frontend"], 2)
            miner = prep.pure.new_miner()
            self.assertEqual(prep.pure.fit_nominal(miner, filtered, 110), 3)
            mapping = {str(c["cluster_id"]): i + 1
                       for i, c in enumerate(prep.pure.cluster_records(miner))}
            self.assertEqual(prep.pure.match_event(miner, mapping, records[0][2]), 0)
            self.assertGreater(prep.pure.match_event(miner, mapping, records[1][2]), 0)
            self.assertEqual(prep.pure.match_event(miner, mapping, records[-1][2]), 0)

    def test_relative_knots_cache_seed_and_empty_group(self):
        matched = {"times": np.array([100, 100, 109, 110]),
                   "nodes": np.array([1, 1, 1, 0]), "events": np.array([1, 1, 1, 0])}
        groups = list(prep.pure.case_groups(matched, 100, 3))
        self.assertEqual([(w, n) for w, n, _, _ in groups], [(0, 1), (1, 0)])
        knots = groups[0][3]
        np.testing.assert_array_equal(knots[0], [0.])
        np.testing.assert_allclose(knots[1], [0., .00001, 9.00002])
        np.testing.assert_array_equal(knots[2], [0.])
        moved = dict(matched, times=matched["times"] + 123456)
        self.assertEqual([g[2] for g in groups],
                         [g[2] for g in prep.pure.case_groups(moved, 123556, 3)])
        for time in (99., 110.):
            with self.assertRaises(ValueError):
                prep.pure.make_knots(np.array([time]), np.array([1]), 100., 3)
        empty = {k: np.array([], dtype=np.int64) for k in matched}
        self.assertEqual(list(prep.pure.case_groups(empty, 100, 3)), [])
        prep.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(prep.OUT)) as folder:
            output = Path(folder)
            (output / "hawkes").mkdir()
            with patch.object(prep, "OUT", output):
                direct = prep.pure.fit_hawkes((9, 2, knots, 42))
                baseline, record = prep.cached_fit(groups[0][2], knots)
                again, cached = prep.cached_fit(groups[0][2], knots)
                np.testing.assert_array_equal(baseline, direct["baseline"])
                np.testing.assert_array_equal(again, baseline)
                self.assertEqual(record, cached)
                self.assertEqual(record["seed"], 42)
                self.assertEqual(record["iteration_cap"], 50)
                with patch.object(prep, "INPUT_BINDING", "other-training-input"):
                    with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                        prep.cached_fit(groups[0][2], knots)
                with patch.object(prep, "SNAPSHOT_HASH", "other-template-snapshot"):
                    with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                        prep.cached_fit(groups[0][2], knots)

    def test_interval_and_member_duplicates_stop_before_fit(self):
        rows = [{"case": "a", "partition": "train"}, {"case": "b", "partition": "validation"}]
        meta = {case: {"raw_hashes": {"logs": case}, "output_hashes": {"temporal.npz": case}}
                for case in ("a", "b")}
        intervals = [{"case": "a", "partition": "train", "start": 100, "end_exclusive": 110},
                     {"case": "b", "partition": "validation", "start": 110, "end_exclusive": 120}]
        prep.check_duplicates(rows, meta, intervals)
        intervals[1]["start"] = 109
        with self.assertRaisesRegex(ValueError, "interval conflict"):
            prep.check_duplicates(rows, meta, intervals)
        intervals[1]["start"] = 110
        meta["b"]["raw_hashes"]["logs"] = "a"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prep.check_duplicates(rows, meta, intervals)

    def test_guard_denies_protected_raw_oldstate_writes_and_symlinks(self):
        allowed = prep.STAGE1 / "allowed" / "metadata.json"
        guard = prep.ReadGuard([allowed])
        for path in (prep.STAGE1 / "protected" / "metadata.json",
                     prep.STAGE1 / "allowed" / "not-approved.npz",
                     prep.pure.OUT / "drain.snapshot", prep.REPO / "data/case/logs.parquet",
                     prep.HERE / "runner.py"):
            with self.assertRaises(PermissionError):
                guard.audit("open", (str(path), "r", 0))
        guard.audit("open", (str(allowed), "r", 0))
        guard.audit("open", (str(Path(sys.base_prefix) /
                                  "lib/python3.8/encodings/cp437.py"), "r", 0))
        with self.assertRaises(PermissionError):
            guard.audit("open", (str(allowed), "wb", os.O_WRONLY))
        prep.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(prep.OUT)) as folder:
            link = Path(folder) / "alias"
            link.symlink_to(prep.REPO / "data")
            with self.assertRaisesRegex(ValueError, "Symlink"):
                guard.audit("open", (str(link / "case/logs.parquet"), "r", 0))
        self.assertEqual(guard.stats["protected_case_files_opened"], 0)
        self.assertEqual(guard.stats["old_state_files_opened"], 0)

    def test_bundle_raw_nan_roundtrip_and_case_partition_contract(self):
        count, nodes = 4, 3
        raw = np.ones((count, nodes, 10, 8), dtype=np.float32)
        raw[0, 0, 0, 0] = np.nan
        arrays = {"metrics": raw, "metric_observed": np.isfinite(raw),
                  "traces": np.zeros((count, nodes, 10, 2), dtype=np.float32),
                  "logs": np.zeros((count, nodes, 2), dtype=np.float32),
                  "labels": np.array([-1, 2, -1, 0], dtype=np.int64),
                  "case_ids": np.array(["t", "t", "v", "v"]),
                  "starts": np.array([100, 110, 200, 210], dtype=np.int64),
                  "partition": np.array(["train", "train", "validation", "validation"]),
                  "indices": np.arange(count, dtype=np.int64),
                  "edge_pairs": np.array([[0, 0], [1, 1], [2, 2], [2, 0]], dtype=np.int64)}
        prep.validate_bundle(arrays, ["a", "b", "c"], 2)
        prep.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(prep.OUT)) as folder:
            path = Path(folder) / "bundle.npz"
            prep.arrays_write(path, arrays)
            saved = prep.arrays_read(path)
            for key in arrays:
                np.testing.assert_equal(saved[key], arrays[key])
            with self.assertRaises(FileExistsError):
                prep.arrays_write(path, arrays)
            json_path = Path(folder) / "input.json"
            prep.json_write(json_path, {"fixture": True})
            with self.assertRaises(FileExistsError):
                prep.json_write(json_path, {"fixture": False})
        broken = copy.deepcopy(arrays)
        broken["partition"][0] = "validation"
        with self.assertRaisesRegex(ValueError, "Case crosses"):
            prep.validate_bundle(broken, ["a", "b", "c"], 2)
        broken = copy.deepcopy(arrays)
        broken["metrics"][0, 0, 0, 0] = 0
        with self.assertRaises(AssertionError):
            prep.validate_bundle(broken, ["a", "b", "c"], 2)


if __name__ == "__main__":
    unittest.main()
