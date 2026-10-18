"""Independent local and relative service rankers."""

import torch
from torch import Tensor, nn


class Ranker(nn.Module):
    """Score every service using shared local or relative MLP features."""

    def __init__(self, feature_dim: int, relative: bool) -> None:
        super().__init__()
        if not isinstance(feature_dim, int) or isinstance(feature_dim, bool) or feature_dim < 1:
            raise ValueError("feature_dim must be a positive integer")
        if not isinstance(relative, bool):
            raise TypeError("relative must be bool")
        self.feature_dim = feature_dim
        self.relative = relative
        self.network = nn.Sequential(
            nn.Linear(5 * feature_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: Tensor, mask: Tensor, coverage: Tensor) -> Tensor:
        if not isinstance(x, Tensor) or not isinstance(mask, Tensor) or not isinstance(coverage, Tensor):
            raise TypeError("x, mask, and coverage must be torch tensors")
        if x.ndim != 3 or x.shape[-1] != self.feature_dim or x.shape[0] < 1 or x.shape[1] < 1:
            raise ValueError(f"x must have shape [B, N, {self.feature_dim}]")
        if mask.shape != x.shape or coverage.shape != x.shape:
            raise ValueError("mask and coverage must have the same shape as x")
        if mask.dtype != torch.bool:
            raise TypeError("mask must have bool dtype")
        if not x.is_floating_point() or not coverage.is_floating_point():
            raise TypeError("x and coverage must have floating-point dtype")
        if x.device != mask.device or x.device != coverage.device:
            raise ValueError("x, mask, and coverage must be on the same device")
        if not torch.isfinite(x).all() or not torch.isfinite(coverage).all():
            raise ValueError("x and coverage must be finite")
        if torch.any((coverage < 0) | (coverage > 1)):
            raise ValueError("coverage must be in [0, 1]")

        valid_x = torch.where(mask, x, 0)
        valid_count = mask.sum(dim=1, keepdim=True)
        context_mask = (valid_count > 0).expand_as(mask)
        if self.relative:
            context = valid_x.sum(dim=1, keepdim=True) / valid_count.clamp_min(1)
            relative_x = torch.where(mask & context_mask, valid_x - context, 0)
        else:
            relative_x = torch.zeros_like(x)
            context_mask = torch.zeros_like(mask)
        features = torch.cat(
            (valid_x, relative_x, mask.to(x.dtype), coverage, context_mask.to(x.dtype)),
            dim=-1,
        )
        first_layer = self.network[0]
        assert isinstance(first_layer, nn.Linear)
        return self.network(features.to(dtype=first_layer.weight.dtype)).squeeze(-1)
