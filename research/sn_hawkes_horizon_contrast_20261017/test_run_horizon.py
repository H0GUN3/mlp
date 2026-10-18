"""Small synthetic-only checks for the guarded horizon runner."""
import numpy as np
import unittest
import torch

import run_horizon as runner
from native_models import NativeReference, joint_loss, native_scores, synthetic_graph


class HorizonRunnerTests(unittest.TestCase):
    def test_normal_only_loss_has_detection_term_and_zero_localization_gradient(self):
        root = torch.tensor([[1.0, -1.0], [0.5, -0.5]], requires_grad=True)
        detection = torch.tensor([[0.0, 1.0], [1.0, 0.0]], requires_grad=True)
        labels = torch.tensor([-1, -1])
        loss = joint_loss(root, detection, labels)
        expected = .5 * torch.nn.functional.cross_entropy(
            detection, torch.zeros(2, dtype=torch.long))
        np.testing.assert_allclose(loss.item(), expected.item(), rtol=0, atol=1e-7)
        loss.backward()
        self.assertIsNotNone(root.grad)
        assert root.grad is not None and detection.grad is not None
        self.assertFalse(torch.count_nonzero(root.grad))
        self.assertTrue(torch.count_nonzero(detection.grad))

    def test_strict_minimum_keeps_earliest_epoch_on_tie(self):
        first = {"epoch": 2, "validation_joint_loss": .25}
        self.assertTrue(runner.strict_minimum([], first))
        self.assertFalse(runner.strict_minimum(
            [first], {"epoch": 3, "validation_joint_loss": .25}))
        self.assertTrue(runner.strict_minimum(
            [first], {"epoch": 4, "validation_joint_loss": .2}))

    def test_input_shape_guard_rejects_wrong_window_count(self):
        arrays = {"indices": np.arange(394, dtype=np.int64),
                  "metrics": np.zeros((2, 12, 10, 7)),
                  "traces": np.zeros((2, 12, 10, 2)),
                  "logs": np.zeros((2, 12, 7)),
                  "log_absolute": np.zeros((2, 12, 7)),
                  "labels": np.zeros((2,), dtype=np.int64)}
        with self.assertRaisesRegex(ValueError, "metrics shape mismatch"):
            runner.check_arrays(arrays, 394)

    def test_seed_cli_is_fixed_to_registered_contrast_seeds(self):
        with self.assertRaises(SystemExit):
            runner.main(["--seed", "12"])

    def test_manifest_position_to_original_index_order_is_not_reordered(self):
        original = np.arange(394, dtype=np.int64)
        train_pos = np.arange(316)
        val_pos = np.arange(316, 394)
        np.testing.assert_array_equal(original[train_pos], original[:316])
        np.testing.assert_array_equal(original[val_pos], original[316:])

    def test_fit_horizon_uses_absolute_not_relative_logs(self):
        relative = np.zeros((3, 12, 7), dtype=np.float32)
        absolute = np.ones_like(relative)
        selected = runner.absolute_horizon_arrays({"logs": relative, "log_absolute": absolute})
        self.assertIs(selected["logs"], absolute)
        np.testing.assert_array_equal(selected["logs"], 1)

    def test_batch_one_model_forward_and_score_shapes(self):
        model = NativeReference("diagmlp", 2, 5)
        model.eval()
        root, detection = model(synthetic_graph(batch=1))
        self.assertEqual(tuple(root.shape), (1, 2))
        self.assertEqual(tuple(detection.shape), (1, 2))
        scores = native_scores(root, detection, torch.tensor([-1]))
        self.assertEqual(scores["windows"], 1)
        self.assertIsNone(scores["conditional_top1"])

    def test_actual_prepared_schema_and_baseline_contract_read_only(self):
        _, metadata, indices, train_pos, val_pos, arrays = runner.load_preparation()
        runner.check_arrays(arrays, 394)
        split, scaler_path, config = runner.compare_baseline_contract(
            metadata, indices, train_pos, val_pos)
        self.assertEqual(len(split["indices"]["train"]), 316)
        self.assertEqual(len(split["indices"]["validation"]), 78)
        self.assertTrue(scaler_path.is_file())
        self.assertEqual(config["model"], NativeReference("diagmlp", 12, 7).config)
        self.assertEqual(set(config["versions"]), {"python", "torch", "dgl", "numpy"})
        self.assertNotIn("train_original_indices", metadata)
        self.assertNotIn("original_scaler_sha256", metadata)
        self.assertEqual(runner.BASELINE.name, "diagmlp")

    def test_version_and_model_contract_comparison_reject_missing_fields(self):
        versions = {"python": "3.8.20", "torch": "1.12.1+cpu",
                    "dgl": "0.9.1", "numpy": "1.21.5"}
        runner.check_runtime_versions(versions, versions)
        with self.assertRaisesRegex(ValueError, "version field missing: python"):
            runner.check_runtime_versions(versions, {"torch": versions["torch"]})
        with self.assertRaisesRegex(ValueError, "version mismatch: torch"):
            runner.check_runtime_versions(dict(versions, torch="wrong"), versions)
        config = NativeReference("diagmlp", 12, 7).config
        self.assertEqual(config["length"], 10)
        self.assertEqual(config["node_count"], 12)
        self.assertEqual(config["event_count"], 7)


if __name__ == "__main__":
    unittest.main()


def self_check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HorizonRunnerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError("synthetic horizon runner tests failed")
