"""Focused synthetic checks for the frozen relationship smoke model."""

import io
import unittest
from typing import Any, List, Tuple, Type, cast

import torch
from torch import Tensor, nn

from relation_model import RelationRanker


MODES = ("local", "global", "directed")


class RelationRankerTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(11)
        self.x = torch.tensor(
            [[[2.0, 3.0], [4.0, 999.0], [8.0, -4.0], [999.0, -777.0], [0.0, 0.0]]]
        )
        self.mask = torch.tensor(
            [[[True, True], [True, False], [True, True], [False, False], [True, True]]]
        )
        self.coverage = torch.tensor(
            [[[1.0, 0.5], [0.7, 0.0], [0.2, 1.0], [0.0, 0.0], [1.0, 1.0]]]
        )
        self.adjacency = torch.zeros(1, 5, 5, dtype=torch.bool)
        for caller, callee in ((0, 1), (0, 2), (1, 2), (2, 3), (3, 0)):
            self.adjacency[0, caller, callee] = True

    def _arithmetic_model(self, mode: str) -> RelationRanker:
        model = RelationRanker(2, mode)
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
            encoder = cast(nn.Linear, model.encoder[0])
            encoder.weight[0, 0] = 1.0
            encoder.bias[0] = 10.0
            encoder.bias[1] = 5.0
            head = cast(nn.Linear, model.head[0])
            for column, weight in ((0, 1.0), (32, 2.0), (64, 3.0), (96, 7.0), (97, 11.0)):
                head.weight[0, column] = weight
            cast(nn.Linear, model.head[2]).weight[0, 0] = 1.0
        return model

    def _head_features(
        self, model: RelationRanker, mask: Tensor, adjacency: Tensor
    ) -> Tensor:
        captured: List[Tensor] = []
        handle = model.head[0].register_forward_pre_hook(
            lambda _module, args: captured.append(args[0].detach())
        )
        try:
            model(self.x, mask, self.coverage, adjacency)
        finally:
            handle.remove()
        return captured[0]

    def test_exact_incoming_outgoing_visible_neighbor_means(self) -> None:
        model = self._arithmetic_model("directed")
        features = self._head_features(model, self.mask, self.adjacency)
        expected = torch.zeros(1, 5, 98)
        expected[0, :, 0] = torch.tensor([12.0, 14.0, 18.0, 10.0, 10.0])
        expected[0, :, 1] = 5.0
        expected[0, :, 32] = torch.tensor([0.0, 12.0, 13.0, 18.0, 0.0])
        expected[0, :, 64] = torch.tensor([16.0, 18.0, 0.0, 12.0, 0.0])
        expected[0, :, 96] = torch.tensor([0.0, 1.0, 1.0, 1.0, 0.0])
        expected[0, :, 97] = torch.tensor([1.0, 1.0, 0.0, 1.0, 0.0])
        expected[..., 33] = 5.0 * expected[..., 96]
        expected[..., 65] = 5.0 * expected[..., 97]
        torch.testing.assert_close(features, expected, rtol=0, atol=0)
        torch.testing.assert_close(
            model(self.x, self.mask, self.coverage, self.adjacency),
            torch.tensor([[71.0, 110.0, 51.0, 100.0, 10.0]]),
            rtol=0,
            atol=0,
        )

    def test_global_repeats_visible_mean_including_self(self) -> None:
        features = self._head_features(
            self._arithmetic_model("global"), self.mask, self.adjacency
        )
        expected = torch.zeros(1, 5, 32)
        expected[..., 0] = 13.5
        expected[..., 1] = 5.0
        torch.testing.assert_close(features[..., 32:64], expected, rtol=0, atol=0)
        torch.testing.assert_close(features[..., 64:96], expected, rtol=0, atol=0)
        self.assertTrue(torch.equal(features[..., 96:], torch.ones(1, 5, 2)))

    def test_encoder_layout_masks_values_and_preserves_coverage(self) -> None:
        model = RelationRanker(2, "directed").double()
        captured: List[Tensor] = []
        handle = model.encoder[0].register_forward_pre_hook(
            lambda _module, args: captured.append(args[0].detach())
        )
        try:
            scores = model(self.x, self.mask, self.coverage.double(), self.adjacency)
        finally:
            handle.remove()
        expected = torch.cat(
            (torch.where(self.mask, self.x, 0), self.mask.float(), self.coverage), dim=-1
        ).double()
        torch.testing.assert_close(captured[0], expected, rtol=0, atol=0)
        self.assertEqual(scores.dtype, torch.float64)
        self.assertIsInstance(model.encoder[1], nn.ReLU)
        self.assertIsInstance(model.head[1], nn.ReLU)

    def test_permutation_equivariance_both_adjacency_axes(self) -> None:
        x = self.x.repeat(2, 1, 1)
        mask = self.mask.repeat(2, 1, 1)
        coverage = self.coverage.repeat(2, 1, 1)
        adjacency = torch.cat((self.adjacency, self.adjacency.transpose(1, 2)), dim=0)
        x[1] = x[1] + 1.0
        mask[1, 1, 1] = True
        permutation = torch.tensor([3, 0, 4, 2, 1])
        for mode in MODES:
            with self.subTest(mode=mode):
                model = self._arithmetic_model(mode)
                baseline = model(x, mask, coverage, adjacency)
                permuted = model(
                    x[:, permutation],
                    mask[:, permutation],
                    coverage[:, permutation],
                    adjacency[:, permutation][:, :, permutation],
                )
                torch.testing.assert_close(permuted, baseline[:, permutation])

    def test_local_and_global_are_graph_independent(self) -> None:
        alternatives = (
            torch.zeros_like(self.adjacency),
            self.adjacency.transpose(1, 2),
            (~torch.eye(5, dtype=torch.bool)).unsqueeze(0),
        )
        for mode in ("local", "global"):
            with self.subTest(mode=mode):
                model = self._arithmetic_model(mode)
                baseline = model(self.x, self.mask, self.coverage, self.adjacency)
                for adjacency in alternatives:
                    torch.testing.assert_close(
                        model(self.x, self.mask, self.coverage, adjacency),
                        baseline,
                        rtol=0,
                        atol=0,
                    )

    def test_local_has_zero_contexts_and_no_cross_service_dependence(self) -> None:
        model = self._arithmetic_model("local")
        features = self._head_features(model, self.mask, self.adjacency)
        self.assertTrue(torch.equal(features[..., 32:], torch.zeros(1, 5, 66)))
        baseline = model(self.x, self.mask, self.coverage, self.adjacency)
        x, mask, coverage = self.x.clone(), self.mask.clone(), self.coverage.clone()
        x[:, 1:] = 123.0
        mask[:, 1:] = True
        coverage[:, 1:] = 0.25
        torch.testing.assert_close(
            model(x, mask, coverage, self.adjacency)[:, 0], baseline[:, 0],
            rtol=0, atol=0,
        )

    def test_zero_edge_directed_equals_local_with_copied_weights(self) -> None:
        local = RelationRanker(2, "local")
        directed = RelationRanker(2, "directed")
        directed.load_state_dict(local.state_dict())
        empty = torch.zeros_like(self.adjacency)
        torch.testing.assert_close(
            directed(self.x, self.mask, self.coverage, empty),
            local(self.x, self.mask, self.coverage, empty),
            rtol=0,
            atol=0,
        )

    def test_all_missing_and_isolated_nodes_are_finite(self) -> None:
        for mode in MODES:
            model = self._arithmetic_model(mode)
            for mask in (self.mask, torch.zeros_like(self.mask)):
                for adjacency in (self.adjacency, torch.zeros_like(self.adjacency)):
                    with self.subTest(mode=mode, all_missing=not mask.any().item()):
                        scores = model(self.x, mask, self.coverage, adjacency)
                        self.assertEqual(scores.shape, (1, 5))
                        self.assertTrue(torch.isfinite(scores).all().item())
                        if not mask.any():
                            features = self._head_features(model, mask, adjacency)
                            self.assertTrue(torch.equal(features[..., 32:], torch.zeros(1, 5, 66)))
        for mode in MODES:
            x = torch.zeros(2, 1, 2)
            scores = RelationRanker(2, mode)(
                x, torch.ones_like(x, dtype=torch.bool), torch.ones_like(x),
                torch.zeros(2, 1, 1, dtype=torch.bool),
            )
            self.assertEqual(scores.shape, (2, 1))
            self.assertTrue(torch.isfinite(scores).all().item())

    def test_masked_finite_placeholder_invariance(self) -> None:
        changed = self.x.clone()
        changed[~self.mask] = torch.tensor([-1e20, 7e19, 1e20])
        for mode in MODES:
            with self.subTest(mode=mode):
                model = RelationRanker(2, mode)
                torch.testing.assert_close(
                    model(changed, self.mask, self.coverage, self.adjacency),
                    model(self.x, self.mask, self.coverage, self.adjacency),
                    rtol=0,
                    atol=0,
                )

    def test_parameter_count_and_identical_seeded_initialization(self) -> None:
        models = []
        for mode in MODES:
            torch.manual_seed(11)
            model = RelationRanker(18, mode)
            self.assertEqual(sum(parameter.numel() for parameter in model.parameters()), 3361)
            self.assertEqual(cast(nn.Linear, model.encoder[0]).in_features, 54)
            self.assertEqual(cast(nn.Linear, model.head[0]).in_features, 98)
            models.append(model)
        reference = models[0].state_dict()
        for model in models[1:]:
            self.assertEqual(list(model.state_dict()), list(reference))
            for name, value in model.state_dict().items():
                self.assertTrue(torch.equal(value, reference[name]), name)

    def test_finite_backward_gradients_and_masked_input_gradients(self) -> None:
        for mode in MODES:
            for all_missing in (False, True):
                with self.subTest(mode=mode, all_missing=all_missing):
                    model = RelationRanker(2, mode)
                    x = self.x.clone().requires_grad_()
                    coverage = self.coverage.clone().requires_grad_()
                    mask = torch.zeros_like(self.mask) if all_missing else self.mask
                    scores = model(x, mask, coverage, self.adjacency)
                    loss = nn.functional.cross_entropy(scores, torch.tensor([2]))
                    loss.backward()
                    self.assertTrue(torch.isfinite(loss).item())
                    for name, parameter in model.named_parameters():
                        gradient = parameter.grad
                        assert gradient is not None, name
                        self.assertTrue(torch.isfinite(gradient).all().item(), name)
                    x_gradient, coverage_gradient = x.grad, coverage.grad
                    assert x_gradient is not None
                    assert coverage_gradient is not None
                    self.assertTrue(torch.isfinite(x_gradient).all().item())
                    self.assertTrue(torch.isfinite(coverage_gradient).all().item())
                    self.assertTrue(torch.equal(
                        x_gradient[~mask], torch.zeros_like(x_gradient[~mask])
                    ))

    def test_checkpoint_replay(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                model = RelationRanker(2, mode)
                baseline = model(self.x, self.mask, self.coverage, self.adjacency)
                stream = io.BytesIO()
                torch.save(model.state_dict(), stream)
                stream.seek(0)
                restored = RelationRanker(2, mode)
                restored.load_state_dict(torch.load(stream))
                torch.testing.assert_close(
                    restored(self.x, self.mask, self.coverage, self.adjacency),
                    baseline, rtol=0, atol=0,
                )

    def test_invalid_constructor_arguments(self) -> None:
        invalid_dimensions: Tuple[Any, ...] = (0, -1, 1.5, True, None)
        for feature_dim in invalid_dimensions:
            with self.subTest(feature_dim=feature_dim):
                with self.assertRaises(ValueError):
                    RelationRanker(feature_dim, "local")
        for mode in ("", "relative", "DIRECTED"):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    RelationRanker(2, mode)
        invalid_modes: Tuple[Any, ...] = (None, True, 1)
        for mode in invalid_modes:
            with self.subTest(mode=mode):
                with self.assertRaises(TypeError):
                    RelationRanker(2, mode)

    def test_malformed_inputs(self) -> None:
        diagonal = self.adjacency.clone()
        diagonal[0, 0, 0] = True
        masked_nan = self.x.clone()
        masked_nan[~self.mask] = float("nan")
        cases: Tuple[Tuple[str, int, Any, Type[Exception]], ...] = (
            ("x not tensor", 0, [], TypeError),
            ("mask not tensor", 1, None, TypeError),
            ("coverage not tensor", 2, [], TypeError),
            ("adjacency not tensor", 3, [], TypeError),
            ("x rank", 0, self.x[0], ValueError),
            ("feature dimension", 0, self.x[..., :1], ValueError),
            ("empty batch", 0, self.x[:0], ValueError),
            ("empty services", 0, self.x[:, :0], ValueError),
            ("mask shape", 1, self.mask[..., :1], ValueError),
            ("coverage shape", 2, self.coverage[..., :1], ValueError),
            ("adjacency rank", 3, self.adjacency[0], ValueError),
            ("adjacency batch", 3, self.adjacency.repeat(2, 1, 1), ValueError),
            ("adjacency services", 3, self.adjacency[:, :, :4], ValueError),
            ("mask dtype", 1, self.mask.float(), TypeError),
            ("adjacency dtype", 3, self.adjacency.float(), TypeError),
            ("integer x", 0, self.x.long(), TypeError),
            ("complex x", 0, self.x.to(torch.complex64), TypeError),
            ("integer coverage", 2, self.coverage.long(), TypeError),
            ("complex coverage", 2, self.coverage.to(torch.complex64), TypeError),
            ("infinite x", 0, torch.full_like(self.x, float("inf")), ValueError),
            ("masked nan", 0, masked_nan, ValueError),
            ("nan coverage", 2, torch.full_like(self.coverage, float("nan")), ValueError),
            ("infinite coverage", 2, torch.full_like(self.coverage, float("inf")), ValueError),
            ("negative coverage", 2, torch.full_like(self.coverage, -0.01), ValueError),
            ("coverage above one", 2, torch.full_like(self.coverage, 1.01), ValueError),
            ("self edge", 3, diagonal, ValueError),
        )
        for mode in MODES:
            model = RelationRanker(2, mode)
            for name, position, value, error in cases:
                with self.subTest(mode=mode, invalid=name):
                    inputs: List[Any] = [self.x, self.mask, self.coverage, self.adjacency]
                    inputs[position] = value
                    with self.assertRaises(error):
                        model(*inputs)

    def test_device_mismatches_without_gpu(self) -> None:
        model = RelationRanker(2, "directed")
        inputs = (self.x, self.mask, self.coverage, self.adjacency)
        for position in range(4):
            with self.subTest(position=position):
                mixed = list(inputs)
                mixed[position] = torch.empty_like(inputs[position], device="meta")
                with self.assertRaisesRegex(ValueError, "same device"):
                    model(*mixed)
        with self.assertRaisesRegex(ValueError, "inputs and model"):
            model(*(torch.empty_like(value, device="meta") for value in inputs))


if __name__ == "__main__":
    unittest.main()
