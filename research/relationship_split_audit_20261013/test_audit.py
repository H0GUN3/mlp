"""Synthetic metadata checks only; no original or protected observations."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.relationship_split_audit_20261013.audit import canonical_source_hashes, data, inspect_splits
from research.relationship_smoke_20261013.test_data import synthetic_metadata, event_partition


def fixture(spread_faults=True):
    meta, indices, labels = synthetic_metadata()
    if spread_faults:
        # The original fixture leaves all normal rows near one incident.
        for window in meta["windows"]:
            window["event_id"] = ""
        labels.fill(-1)
        positions = np.linspace(0, len(indices) - 1, 9, dtype=np.int64)
        for fault, index in zip(meta["runs"][0]["faults"], np.sort(indices)[positions]):
            fault["start"], fault["end_inclusive"] = int(index) * 10 + 1, int(index) * 10 + 8
            meta["windows"][int(index)]["event_id"] = fault["event_id"]
            labels[indices == index] = fault["root"]
    split = event_partition(meta, indices, labels)
    manifest = {
        "native_window_count": meta["window_count"], "services": meta["services"],
        **{key: split[key] for key in ("windows", "faults", "event_folds", "few_shot")},
    }
    rows = {"indices": indices, "labels": labels, **{
        key: split[key] for key in ("event_ids", "episode_ids", "fold_ids", "partition")}}
    return manifest, rows


class AuditTest(unittest.TestCase):
    def test_relative_source_paths_keep_hashes_and_reject_aliases(self):
        absolute = str(data.HERE / "data.py")
        self.assertEqual(canonical_source_hashes({"data.py": "original"}), {absolute: "original"})
        self.assertNotEqual(canonical_source_hashes({"data.py": "changed"}), {absolute: "original"})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            canonical_source_hashes({"data.py": "original", absolute: "changed"})

    def test_missing_normal_train_support_rejected(self):
        manifest, rows = fixture(spread_faults=False)
        with self.assertRaisesRegex(ValueError, "No normal TRAIN rows"):
            inspect_splits(manifest, rows)

    def test_all_folds_and_few_shot_are_complete(self):
        manifest, rows = fixture()
        result = inspect_splits(manifest, rows)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["folds"]), 3)
        for fold in result["folds"]:
            self.assertEqual(fold["counts"]["train"]["incidents"], 6)
            self.assertEqual(fold["counts"]["validation"]["incidents"], 3)
            self.assertEqual(fold["shared_train_validation_recordings"], ["run"])
            a, b = (set(fold["few_shot"][k]["original_indices"]) for k in ("A", "B"))
            self.assertFalse(a & b)
            self.assertTrue(a | b <= set(fold["original_indices"]["train"]))

    def test_changed_fold_and_few_shot_metadata_rejected(self):
        manifest, rows = fixture()
        corrupted = copy.deepcopy(rows)
        corrupted["fold_ids"][0] = (corrupted["fold_ids"][0] + 1) % 3
        with self.assertRaisesRegex(ValueError, "invariant row metadata"):
            inspect_splits(manifest, corrupted)
        manifest["few_shot"]["A"]["event_ids"].append(manifest["few_shot"]["B"]["event_ids"][0])
        with self.assertRaisesRegex(ValueError, "fold0 metadata"):
            inspect_splits(manifest, rows)

    def test_protected_row_and_overlapping_windows_rejected(self):
        manifest, rows = fixture()
        corrupted = copy.deepcopy(rows)
        protected = next(i for i in range(manifest["native_window_count"]) if i not in rows["indices"])
        corrupted["indices"][0] = protected
        with self.assertRaisesRegex(ValueError, "inventory"):
            inspect_splits(manifest, corrupted)
        order = np.argsort([w["start"] for w in manifest["windows"]])
        manifest["windows"][int(order[1])]["start"] = manifest["windows"][int(order[0])]["end"]
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            inspect_splits(manifest, rows)


if __name__ == "__main__":
    unittest.main()
