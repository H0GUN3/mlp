"""Synthetic leakage, fixed-budget training, and artifact checks; no real telemetry."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from research.relationship_cv_20261014 import cv
from research.relationship_smoke_20261013.test_data import synthetic_bundle


class CVTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_all_folds_rebuild_from_raw_and_ignore_validation(self):
        original, manifest = synthetic_bundle()
        # Provide normal support to every synthetic episode/fold.
        original["fold_ids"][original["labels"] == -1] = np.arange(
            int((original["labels"] == -1).sum())) % 3
        for fold in range(3):
            for row in np.flatnonzero(original["labels"] == -1):
                original["episode_ids"][row] = "normal" + str(original["fold_ids"][row])
            result = cv.prepare_fold(original, manifest, fold)
            arrays, reference, stats, tensors, training, validation = result
            changed = {key: value.copy() for key, value in original.items()}
            held = original["fold_ids"] == fold
            changed["values"][held] = 1234567.
            changed["x"][:] = -7654.
            changed["observed"][held] = False
            after = cv.prepare_fold(changed, manifest, fold)
            for expected, actual in ((reference, after[1]), (stats, after[2])):
                for key in expected:
                    np.testing.assert_array_equal(expected[key], actual[key])
            for expected, actual in zip(tensors, after[3]):
                np.testing.assert_array_equal(expected.numpy()[training], actual.numpy()[training])
            self.assertFalse(set(arrays["episode_ids"][training]) & set(arrays["episode_ids"][validation]))
            self.assertEqual(set(arrays["partition"]), {"train", "validation"})

    def test_missing_normal_support_and_invalid_fold_rejected(self):
        arrays, manifest = synthetic_bundle()
        arrays["fold_ids"][arrays["labels"] == -1] = 0
        with self.assertRaisesRegex(ValueError, "normal TRAIN"):
            cv.prepare_fold(arrays, manifest, 0)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            cv.prepare_fold(arrays, manifest, 4)

    def test_fixed_fit_determinism_and_exact_epoch_budget(self):
        arrays, manifest = synthetic_bundle()
        prepared = cv.prepare_fold(arrays, manifest, 0)
        tensors, rows = prepared[3], prepared[4]
        snapshots = []
        for _ in range(2):
            torch.manual_seed(11)
            model = cv.smoke.RelationRanker(18, "directed")
            initial = copy.deepcopy(model.state_dict())
            history = cv.fit_final(model, tuple(t[torch.from_numpy(rows)] for t in tensors),
                                   torch.from_numpy(arrays["labels"][rows]),
                                   arrays["event_ids"][rows], 11)
            self.assertEqual([h["epoch"] for h in history], [1, 2, 3, 4, 5])
            self.assertTrue(all(set(h) == {"epoch", "train_event_ce"} for h in history))
            self.assertTrue(any(not torch.equal(v, initial[k]) for k, v in model.state_dict().items()))
            snapshots.append(copy.deepcopy(model.state_dict()))
        for key in snapshots[0]:
            self.assertTrue(torch.equal(snapshots[0][key], snapshots[1][key]))

    def test_no_overwrite_and_artifact_mismatch(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "statistics.npz"
            cv.save_npz(path, x=np.arange(3))
            cv.assert_npz(path, {"x": np.arange(3)})
            with self.assertRaises(FileExistsError):
                cv.save_npz(path, x=np.arange(4))
            with self.assertRaisesRegex(ValueError, "Saved arrays"):
                cv.assert_npz(path, {"x": np.arange(4)})
            with patch.object(cv, "source_hashes", return_value={}):
                with self.assertRaises(FileExistsError):
                    cv.execute("run", Path(name))

    def test_unauthorized_system_rejected_before_io(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("Unexpected file access")):
            with self.assertRaisesRegex(ValueError, "authorized"):
                cv.load_development("RCAEval")


if __name__ == "__main__":
    unittest.main()
