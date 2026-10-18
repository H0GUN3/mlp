"""Shared service ranker with local, global, or directed mean contexts."""

from typing import Tuple

import torch
from torch import Tensor, nn


def _pool_neighbors(
    hidden: Tensor, visible: Tensor, adjacency: Tensor
) -> Tuple[Tensor, Tensor]:
    neighbors = adjacency & visible.unsqueeze(1)
    count = neighbors.sum(dim=-1, keepdim=True)
    context = torch.bmm(neighbors.to(hidden.dtype), hidden)
    return context / count.clamp_min(1), count > 0


class RelationRanker(nn.Module):
    """Score services; adjacency rows are callers and columns are callees."""

    def __init__(self, feature_dim: int, mode: str) -> None:
        super().__init__()
        if not isinstance(feature_dim, int) or isinstance(feature_dim, bool) or feature_dim < 1:
            raise ValueError("feature_dim must be a positive integer")
        if not isinstance(mode, str):
            raise TypeError("mode must be a string")
        if mode not in ("local", "global", "directed"):
            raise ValueError("mode must be local, global, or directed")
        self.feature_dim = feature_dim
        self.mode = mode
        self.encoder = nn.Sequential(nn.Linear(3 * feature_dim, 32), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(98, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(
        self, x: Tensor, mask: Tensor, coverage: Tensor, adjacency: Tensor
    ) -> Tensor:
        if not all(isinstance(value, Tensor) for value in (x, mask, coverage, adjacency)):
            raise TypeError("x, mask, coverage, and adjacency must be torch tensors")
        if x.ndim != 3 or x.shape[-1] != self.feature_dim or x.shape[0] < 1 or x.shape[1] < 1:
            raise ValueError(f"x must have shape [B, N, {self.feature_dim}]")
        if mask.shape != x.shape or coverage.shape != x.shape:
            raise ValueError("mask and coverage must have the same shape as x")
        if adjacency.shape != (x.shape[0], x.shape[1], x.shape[1]):
            raise ValueError("adjacency must have shape [B, N, N]")
        if mask.dtype != torch.bool or adjacency.dtype != torch.bool:
            raise TypeError("mask and adjacency must have bool dtype")
        if not x.is_floating_point() or not coverage.is_floating_point():
            raise TypeError("x and coverage must have floating-point dtype")
        first_layer = self.encoder[0]
        assert isinstance(first_layer, nn.Linear)
        if any(value.device != x.device for value in (mask, coverage, adjacency)):
            raise ValueError("all inputs must be on the same device")
        if x.device != first_layer.weight.device:
            raise ValueError("inputs and model must be on the same device")
        if not torch.isfinite(x).all() or not torch.isfinite(coverage).all():
            raise ValueError("x and coverage must be finite, including masked placeholders")
        if torch.any((coverage < 0) | (coverage > 1)):
            raise ValueError("coverage must be in [0, 1]")
        if adjacency.diagonal(dim1=1, dim2=2).any():
            raise ValueError("adjacency must not contain self edges")

        features = torch.cat(
            (torch.where(mask, x, 0), mask.to(x.dtype), coverage), dim=-1
        )
        hidden = self.encoder(features.to(dtype=first_layer.weight.dtype))
        visible = mask.any(dim=-1)
        if self.mode == "directed":
            incoming, in_present = _pool_neighbors(hidden, visible, adjacency.transpose(1, 2))
            outgoing, out_present = _pool_neighbors(hidden, visible, adjacency)
        elif self.mode == "global":
            count = visible.sum(dim=1, keepdim=True).unsqueeze(-1)
            context = torch.where(visible.unsqueeze(-1), hidden, 0).sum(dim=1, keepdim=True)
            incoming = outgoing = (context / count.clamp_min(1)).expand_as(hidden)
            in_present = out_present = (count > 0).expand(*hidden.shape[:2], 1)
        else:
            incoming = outgoing = torch.zeros_like(hidden)
            in_present = out_present = torch.zeros_like(visible.unsqueeze(-1))
        head_input = torch.cat(
            (hidden, incoming, outgoing, in_present.to(hidden.dtype), out_present.to(hidden.dtype)),
            dim=-1,
        )
        return self.head(head_input).squeeze(-1)
