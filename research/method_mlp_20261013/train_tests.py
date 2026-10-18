"""Focused arithmetic and actual training checks without real/test data."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
import torch

from ranker import Ranker
from train import event_weights, fit_model, fit_standardizer, score, transform


class TrainingTests(unittest.TestCase):
    def test_training_only_masked_standardization(self):
        x = np.array([[[1., 100.], [3., 100.]], [[900., 8.], [900., 9.]]])
        mask = np.array([[[True, False], [True, False]], [[True, True], [True, True]]])
        stats = fit_standardizer(x, mask, np.array([0]))
        np.testing.assert_array_equal(stats["mean"], [2, 0])
        np.testing.assert_array_equal(stats["counts"], [2, 0])
        np.testing.assert_array_equal(stats["std"], [1, 1])
        x[1] = -9999
        changed = fit_standardizer(x, mask, np.array([0]))
        np.testing.assert_array_equal(changed["mean"], stats["mean"])
        normalized = transform(x, mask, stats)
        np.testing.assert_array_equal(normalized[0], [[-1, 0], [1, 0]])

    def test_event_weight_and_tie_scoring(self):
        events = np.array(["a", "a", "b"])
        np.testing.assert_allclose(event_weights(events), [.75, .75, 1.5])
        logits = np.array([[3., 0.], [1., 1.], [0., 2.]])
        labels = np.array([0, 0, 0])
        measured = score(logits, labels, events)
        self.assertEqual(measured["window_top1"], .5)
        self.assertEqual(measured["event_balanced_top1"], .375)
        self.assertEqual(measured["correct_root_tied_at_top"], 1)

    def test_real_optimization_and_serialization(self):
        torch.set_num_threads(1)
        rng = np.random.RandomState(19)
        x = rng.normal(size=(40, 3, 2)).astype(np.float32)
        labels = torch.from_numpy(x[:, :, 0].argmax(axis=1))
        tensors = (torch.from_numpy(x), torch.ones_like(torch.from_numpy(x), dtype=torch.bool),
                   torch.ones_like(torch.from_numpy(x)))
        train, val = np.arange(32), np.arange(32, 40)
        settings = {"learning_rate": .01, "weight_decay": 0., "batch_size": 8,
                    "epochs": 25, "patience": 25}
        for relative in (False, True):
            torch.manual_seed(11)
            model = Ranker(2, relative=relative)
            predictions, history, epoch, best = fit_model(
                model, tensors, labels, train, val, torch.ones(32), torch.ones(8), 11, settings)
            self.assertGreater(epoch, 0)
            self.assertLess(best, history[0]["validation_event_ce"])
            self.assertTrue(np.isfinite(predictions).all())
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.pt"
                torch.save(model.state_dict(), path)
                replay = Ranker(2, relative=relative)
                replay.load_state_dict(torch.load(path, map_location="cpu"))
                replay.eval()
                with torch.no_grad():
                    result = replay(*(value[torch.from_numpy(val)] for value in tensors)).numpy()
                np.testing.assert_array_equal(predictions, result)


if __name__ == "__main__":
    unittest.main()
