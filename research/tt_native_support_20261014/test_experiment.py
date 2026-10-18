import unittest

import numpy as np
import torch

from research.tt_native_support_20261014 import experiment as ex


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def fixture(self):
        rng = np.random.RandomState(7)
        data = {"metrics": rng.randn(4, 3, 10, 7).astype(np.float32),
                "traces": rng.randn(4, 3, 10, 2).astype(np.float32),
                "logs": np.abs(rng.randn(4, 3, 4)).astype(np.float32),
                "labels": np.array([0, 1, -1, 2], dtype=np.int64),
                "support": np.ones((4, 3, 1), dtype=np.float32)}
        data["traces"][..., 1] = 0
        return data, {"services": ["a", "b", "c"], "edges": [[0, 1], [1, 2], [2, 0]]}

    def test_all_model_shapes_and_finite_loss(self):
        data, meta = self.fixture()
        graph, truth = ex.graph_batch(data, np.arange(4), meta)
        for kind in ex.KINDS:
            torch.manual_seed(11)
            model = ex.make_model(kind, 4, nodes=3)
            roots, detection = model(graph)
            self.assertEqual(tuple(roots.shape), (4, 3))
            self.assertEqual(tuple(detection.shape), (4, 2))
            self.assertTrue(torch.isfinite(ex.native_models.joint_loss(roots, detection, truth)))

    def test_initial_equivalence_and_rng_budget(self):
        data, meta = self.fixture()
        graph, _ = ex.graph_batch(data, np.arange(4), meta)
        torch.manual_seed(11)
        baseline = ex.make_model("diagmlp", 4, nodes=3).eval()
        rng_base = torch.get_rng_state()
        torch.manual_seed(11)
        augmented = ex.make_model("diagmlp_count", 4, nodes=3).eval()
        self.assertTrue(torch.equal(rng_base, torch.get_rng_state()))
        ex.require_matching_initial(baseline.state_dict(), augmented.state_dict())
        with torch.no_grad():
            for left, right in zip(baseline(graph), augmented(graph)):
                # Adding an exact-zero column can change GEMM floating-point reduction order.
                torch.testing.assert_close(left, right, rtol=1e-5, atol=1e-6)
        self.assertEqual(sum(p.numel() for p in augmented.parameters())
                         - sum(p.numel() for p in baseline.parameters()), 64)

    def test_support_gradient_and_zero_control(self):
        data, meta = self.fixture()
        graph, truth = ex.graph_batch(data, np.arange(4), meta)
        for kind in ("diagmlp_count", "diagmlp_zero_count"):
            torch.manual_seed(11)
            model = ex.make_model(kind, 4, nodes=3)
            roots, detection = model(graph)
            ex.native_models.joint_loss(roots, detection, truth).backward()
            grad = model.core.encoder.modal[0].weight.grad
            self.assertIsNotNone(grad)
            if grad is None:
                raise AssertionError("Missing modal gradient")
            if kind == "diagmlp_count":
                self.assertGreater(float(grad[:, -1].abs().sum()), 0)
            else:
                self.assertEqual(float(grad[:, -1].abs().sum()), 0)

    def test_changed_or_protected_inventory_rejected(self):
        ex.validate_indices(np.array([1, 3]), np.array([1, 3]))
        with self.assertRaises(ValueError):
            ex.validate_indices(np.array([1, 4]), np.array([1, 3]))
        with self.assertRaises(ValueError):
            ex.validate_indices(np.array([1, 1]), np.array([1, 1]))

    def test_incident_equal_ties_and_normal_exclusion(self):
        logits = np.array([[2., 2.], [1., 0.], [1., 0.], [1., 0.], [1., 0.]])
        result = ex.incident_metrics(logits, np.array([0, 1, 1, 1, -1]),
                                    np.array(["A", "B", "B", "B", ""]))
        self.assertEqual(result["event_balanced"]["top1"], .25)
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["fault_windows"], 4)

    def test_scaler_training_only(self):
        data, _ = self.fixture()
        arrays = dict(data)
        arrays.update({"fold_ids": np.array([0, 1, 1, 2]), "episode_ids": np.array(["A", "B", "B", "C"]),
                       "unique_count": np.ones((4, 3), dtype=np.int64)})
        _, stats, _ = ex.prepare_fold(arrays, 0)
        arrays["metrics"] = arrays["metrics"].copy()
        arrays["metrics"][0] = 999.
        _, changed, _ = ex.prepare_fold(arrays, 0)
        for key in stats:
            np.testing.assert_array_equal(stats[key], changed[key])


if __name__ == "__main__":
    unittest.main()
