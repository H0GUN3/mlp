"""Focused staged-only fixtures, including actual native Hawkes equivalence."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import re2_stage2 as stage


class Stage2Test(unittest.TestCase):
    def test_frozen_templates_unknown_and_no_validation_fit(self):
        miner = stage.new_miner()
        records = [(99, "node", "known steady message"), (100, "node", "injection boundary excluded"),
                   (101, "node", "fault excluded")]
        self.assertEqual(stage.fit_nominal(miner, records, 100), 1)
        before = stage.cluster_records(miner)
        mapping = {str(c["cluster_id"]): i + 1 for i, c in enumerate(before)}
        self.assertGreater(stage.match_event(miner, mapping, "known steady message"), 0)
        for validation_message in ("validation unknown", "changed validation value", "fault excluded"):
            self.assertEqual(stage.match_event(miner, mapping, validation_message), 0)
        self.assertEqual(before, stage.cluster_records(miner))
        stage.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(stage.OUT)) as folder:
            snapshot = Path(folder) / "snapshot"
            miner.persistence_handler = stage.FilePersistence(str(snapshot))
            miner.save_state("fixture frozen TRAIN")
            restored = stage.new_miner(snapshot)
            self.assertEqual(before, stage.cluster_records(restored))
            self.assertEqual(stage.match_event(restored, mapping, "validation unknown"), 0)
        self.assertEqual(before, stage.cluster_records(miner))

    def test_timestamp_end_window_and_injection_boundaries(self):
        knots = stage.make_knots(np.array([100., 100., 109.]), np.array([1, 1, 1]), 100., 3)
        np.testing.assert_array_equal(knots[0], [0.])
        np.testing.assert_allclose(knots[1], [0., .00001, 9.00002])
        np.testing.assert_array_equal(knots[2], [0.])
        for times in ([99.], [110.]):
            with self.assertRaises(ValueError):
                stage.make_knots(np.array(times), np.array([1]), 100., 3)
        starts = np.array([100, 110], dtype=np.int64)
        np.testing.assert_array_equal(stage.global_labels(starts, 110, 2), [-1, 2])
        np.testing.assert_array_equal(stage.global_labels(starts, 109, 2), [2, 2])

    def test_interval_half_open_gate(self):
        a = {"case": "a", "partition": "train", "start": 100, "end_exclusive": 110}
        b = {"case": "b", "partition": "validation", "start": 110, "end_exclusive": 120}
        self.assertEqual(stage.interval_overlaps([a, b]), [])
        b["start"] = 109
        self.assertEqual(len(stage.interval_overlaps([a, b])), 1)

    def test_graph_handoff_is_k_by_2_with_three_edges(self):
        edges = {("a", "a"), ("a", "b"), ("c", "b")}
        self.assertEqual(
            stage.indexed_edge_pairs(["a", "b", "c"], edges),
            [[0, 0], [0, 1], [2, 1]],
        )

    def test_group_coordinates_empty_and_shift_invariant_cache(self):
        arrays = {"times": np.array([100, 109, 110]), "nodes": np.array([1, 1, 0]),
                  "events": np.array([1, 1, 0])}
        groups = list(stage.case_groups(arrays, 100, 2))
        self.assertEqual([(w, n) for w, n, _, _ in groups], [(0, 1), (1, 0)])
        arrays["times"] += 123456
        shifted = list(stage.case_groups(arrays, 123556, 2))
        self.assertEqual([key for _, _, key, _ in groups], [key for _, _, key, _ in shifted])
        empty = {"times": np.array([], dtype=np.int64), "nodes": np.array([], dtype=np.int64),
                 "events": np.array([], dtype=np.int64)}
        self.assertEqual(list(stage.case_groups(empty, 0, 2)), [])

    def test_actual_native_cached_fit_equivalence(self):
        knots = stage.make_knots(np.array([100., 101., 103.]), np.array([1, 1, 1]), 100., 2)
        direct = stage.fit_hawkes((9, 4, knots, 42))
        previous = stage.OUT
        stage.OUT.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=str(stage.OUT)) as folder:
                stage.OUT = Path(folder)
                (stage.OUT / "hawkes").mkdir()
                key = stage.knot_key(knots)
                first, meta = stage.cached_fit(key, knots)
                cached, reused = stage.cached_fit(key, knots)
                np.testing.assert_array_equal(first, direct["baseline"])
                np.testing.assert_array_equal(first, cached)
                self.assertEqual(meta, reused)
                self.assertTrue(np.isfinite(cached).all() and np.all(cached >= 0))
        finally:
            stage.OUT = previous

    def test_synthetic_bundle_roundtrip_raw_nan_masks_and_labels(self):
        previous_out, previous_stage1 = stage.OUT, stage.STAGE1
        stage.OUT.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=str(stage.OUT)) as folder:
                stage.OUT = Path(folder)
                stage.STAGE1 = stage.OUT / "staged_fixture"
                (stage.OUT / "hawkes").mkdir()
                miner = stage.new_miner()
                stage.fit_nominal(miner, [(99, "a", "known message")], 100)
                clusters = stage.cluster_records(miner)
                miner.persistence_handler = stage.FilePersistence(str(stage.OUT / "drain.snapshot"))
                miner.save_state("synthetic TRAIN only")
                template = {"clusters": clusters, "event_count": 2,
                            "cluster_id_to_feature": {str(clusters[0]["cluster_id"]): 1},
                            "snapshot_sha256": stage.digest(stage.OUT / "drain.snapshot")}
                rows, metadata = [], {}
                raw = np.arange(320, dtype=np.float64).reshape(2, 2, 10, 8)
                raw[0, 0, 0, 0] = np.nan
                for index, partition in enumerate(("train", "validation")):
                    case = "fixture_" + partition
                    root, start = ("a" if index == 0 else "b"), 100 + index * 100
                    rows.append({"case": case, "partition": partition, "root_cause_service": root,
                                 "inject_time": start + 10, "fault": "synthetic"})
                    target = stage.STAGE1 / case
                    target.mkdir(parents=True)
                    stage.save_npz(target / "temporal.npz", {
                        "metrics": raw, "metric_observed": np.isfinite(raw),
                        "traces": np.zeros((2, 2, 10, 2), dtype=np.float64),
                        "starts": np.array([start, start + 10], dtype=np.int64)})
                    with gzip.open(target / "logs.jsonl.gz", "wt") as stream:
                        stream.write(json.dumps([start + 1, "a", (
                            "known message" if index == 0 else "validation unknown")]) + "\n")
                    stage.save_json(target / "metadata.json", {"synthetic": True})
                    metadata[case] = {
                        "services": ["a", "b"], "windows": 2, "logs_retained": 1, "logs_excluded": {},
                        "metric_missing_cells": 1, "trace_rows": 0, "trace_rows_in_complete_windows": 0,
                        "output_hashes": {"logs.jsonl.gz": stage.digest(target / "logs.jsonl.gz")}}
                expected_edges = [[0, 0], [0, 1], [1, 1]]
                stage.prepare(rows, metadata, ["a", "b"], expected_edges, miner, template,
                              {"stage1_manifest_sha256": stage.digest(stage.MANIFEST), "protection": {}},
                              {"affordable": True}, 1)
                result = stage.load_json(stage.OUT / "metadata.json")
                self.assertEqual(result["input_npz_sha256"], stage.digest(stage.OUT / "inputs.npz"))
                self.assertEqual(result["edges"], expected_edges)
                self.assertEqual(result["edges_layout"], "Kx2 source/destination pairs")
                self.assertEqual(result["candidates"]["services"], ["a", "b"])
                self.assertFalse(result["candidates"]["validation_fit"])
                self.assertEqual(result["cost"]["true_empty_groups_zero"], 6)
                with np.load(stage.OUT / "inputs.npz", allow_pickle=False) as bundle:
                    np.testing.assert_equal(bundle["metrics"], np.concatenate([raw, raw]))
                    np.testing.assert_array_equal(bundle["labels"], [-1, 0, -1, 1])
                    np.testing.assert_array_equal(bundle["event_ids"],
                                                  ["", "fixture_train", "", "fixture_validation"])
                    self.assertTrue(np.all(bundle["logs"][:, 1] == 0))
                    self.assertFalse(result["normalization"]["imputer_fitted"])
                    self.assertFalse(result["normalization"]["scaler_fitted"])
                self.assertEqual(clusters, stage.cluster_records(miner))
        finally:
            stage.OUT, stage.STAGE1 = previous_out, previous_stage1


if __name__ == "__main__":
    unittest.main()
