"""Focused tests for the independent matched rankers."""

import io
import unittest
from typing import cast

import torch
from torch import nn

from ranker import Ranker


class RankerTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(17)
        self.x = torch.tensor(
            [[[1.0, 3.0], [5.0, 0.0], [99.0, -88.0]]], dtype=torch.float32
        )
        self.mask = torch.tensor([[[True, True], [True, False], [False, False]]])
        self.coverage = torch.tensor([[[1.0, 0.5], [0.7, 0.0], [0.0, 0.0]]])

    def test_masked_context_arithmetic_and_all_missing(self) -> None:
        ranker = Ranker(2, relative=True)
        captured: list[torch.Tensor] = []
        handle = ranker.network[0].register_forward_pre_hook(
            lambda _module, args: captured.append(args[0].detach())
        )
        ranker(self.x, self.mask, self.coverage)
        handle.remove()
        encoded = captured[0]
        expected_relative = torch.tensor(
            [[[-2.0, 0.0], [2.0, 0.0], [0.0, 0.0]]]
        )
        self.assertTrue(torch.equal(encoded[..., 2:4], expected_relative))
        expected_context_mask = self.mask.any(dim=1, keepdim=True).expand_as(self.mask).float()
        self.assertTrue(torch.equal(encoded[..., 8:10], expected_context_mask))
        all_missing = torch.zeros_like(self.mask)
        expected_x = torch.tensor([[[1.0, 3.0], [5.0, 0.0], [0.0, 0.0]]])
        self.assertTrue(torch.equal(encoded[..., :2], expected_x))
        self.assertTrue(torch.equal(encoded[..., 8:10][0, 0], torch.tensor([1.0, 1.0])))
        all_missing_features: list[torch.Tensor] = []
        handle = ranker.network[0].register_forward_pre_hook(
            lambda _module, args: all_missing_features.append(args[0].detach())
        )
        ranker(torch.zeros_like(self.x), all_missing, self.coverage)
        handle.remove()
        self.assertTrue(torch.equal(all_missing_features[0][..., 8:10], torch.zeros(1, 3, 2)))
        for mode in (False, True):
            scores = Ranker(2, relative=mode)(torch.zeros_like(self.x), all_missing, self.coverage)
            self.assertEqual(tuple(scores.shape), (1, 3))
            self.assertTrue(torch.isfinite(scores).all())

    def test_missing_placeholder_invariance_and_permutation(self) -> None:
        ranker = Ranker(2, relative=True)
        baseline = ranker(self.x, self.mask, self.coverage)
        changed = self.x.clone()
        changed[~self.mask] = torch.tensor([1234.0, -567.0, 900.0])
        self.assertTrue(torch.allclose(baseline, ranker(changed, self.mask, self.coverage)))
        permutation = torch.tensor([2, 0, 1])
        permuted = ranker(self.x[:, permutation], self.mask[:, permutation], self.coverage[:, permutation])
        self.assertTrue(torch.allclose(permuted, baseline[:, permutation]))

    def test_local_independence_and_relative_dependence(self) -> None:
        local = Ranker(1, relative=False)
        relative = Ranker(1, relative=True)
        with torch.no_grad():
            for model in (local, relative):
                for parameter in model.parameters():
                    parameter.zero_()
                cast(nn.Linear, model.network[0]).weight[0, 2] = 1.0
                cast(nn.Linear, model.network[0]).weight[1, 4] = 1.0
                cast(nn.Linear, model.network[2]).weight[0, 0] = 1.0
                cast(nn.Linear, model.network[2]).weight[0, 1] = 1.0
                cast(nn.Linear, model.network[4]).weight[0, 0] = 1.0
            cast(nn.Linear, relative.network[0]).weight[0, 1] = -1.0
            cast(nn.Linear, relative.network[2]).weight[0, 0] = 1.0
        x = torch.tensor([[[2.0], [10.0]]])
        mask = torch.ones_like(x, dtype=torch.bool)
        coverage = torch.ones_like(x)
        altered_other = x.clone()
        altered_other[0, 1, 0] = 20.0
        self.assertEqual(local(x, mask, coverage)[0, 0].item(), local(altered_other, mask, coverage)[0, 0].item())
        self.assertNotEqual(relative(x, mask, coverage)[0, 0].item(), relative(altered_other, mask, coverage)[0, 0].item())

    def test_variable_candidate_count_and_matched_initialization(self) -> None:
        for count in (1, 4):
            x = torch.randn(2, count, 2)
            mask = torch.ones_like(x, dtype=torch.bool)
            coverage = torch.rand_like(x)
            self.assertEqual(Ranker(2, True)(x, mask, coverage).shape, (2, count))
        torch.manual_seed(42)
        local = Ranker(3, False)
        torch.manual_seed(42)
        relative = Ranker(3, True)
        self.assertEqual(sum(p.numel() for p in local.parameters()), sum(p.numel() for p in relative.parameters()))
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(local.parameters(), relative.parameters())))

    def test_validation_errors(self) -> None:
        ranker = Ranker(2, False)
        bad_inputs = (
            (self.x[0], self.mask, self.coverage, ValueError),
            (self.x[..., :1], self.mask, self.coverage, ValueError),
            (torch.full_like(self.x, float("inf")), self.mask, self.coverage, ValueError),
            (self.x, self.mask.float(), self.coverage, TypeError),
            (self.x, self.mask, self.coverage[..., :1], ValueError),
            (self.x, self.mask, torch.full_like(self.coverage, float("nan")), ValueError),
            (self.x, self.mask, torch.full_like(self.coverage, 2.0), ValueError),
            (self.x, torch.ones(1), self.coverage, ValueError),
        )
        for x, mask, coverage, error in bad_inputs:
            with self.subTest(error=error, shape=tuple(x.shape)):
                with self.assertRaises(error):
                    ranker(x, mask, coverage)

    def test_finite_gradients_and_save_reload(self) -> None:
        for mode in (False, True):
            ranker = Ranker(2, mode)
            scores = ranker(self.x, self.mask, self.coverage)
            loss = scores.square().mean()
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in ranker.parameters()))
            stream = io.BytesIO()
            torch.save(ranker.state_dict(), stream)
            stream.seek(0)
            restored = Ranker(2, mode)
            restored.load_state_dict(torch.load(stream))
            self.assertTrue(torch.equal(scores.detach(), restored(self.x, self.mask, self.coverage)))


if __name__ == "__main__":
    unittest.main()
