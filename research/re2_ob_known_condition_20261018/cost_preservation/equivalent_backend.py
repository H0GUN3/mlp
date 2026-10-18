"""Experimental exact-zero support compression; no solver or installation edits."""
import numpy as np
from tick.prox import ProxNuclear
from tick.prox.prox_nuclear import svd


def zero_support(x):
    """Return retained coordinates, or None when dense delegation is required."""
    if x.dtype != np.float64 or not np.isfinite(x).all():
        return None
    rows = np.flatnonzero(np.any(x != 0, axis=1))
    cols = np.flatnonzero(np.any(x != 0, axis=0))
    if len(rows) == x.shape[0] and len(cols) == x.shape[1]:
        return None
    return rows, cols


class ZeroStructureProxNuclear(ProxNuclear):
    """Same real-arithmetic operator; float32 feature preservation requires testing."""

    def _call(self, coeffs, step, out):
        x = self._get_matrix(coeffs)
        support = zero_support(x)
        threshold = step * self.strength
        if (support is None or not isinstance(threshold, (float, int, np.floating, np.integer)) or
                not np.isfinite(threshold) or threshold < 0):
            return super()._call(coeffs, step, out)
        rows, cols = support
        expanded = np.zeros_like(x)
        if len(rows) and len(cols):
            compact = x[np.ix_(rows, cols)]
            u, s, v = svd(compact, compute_uv=True, full_matrices=False)
            # Preserve the original strict threshold, including exact boundary equality.
            s = (s - threshold) * (s > threshold)
            expanded[np.ix_(rows, cols)] = u.dot(np.diag(s)).dot(v)
        result = expanded.ravel()
        if self.positive:
            result[result < 0.] = 0.
        start, end = (0, coeffs.shape[0]) if self.range is None else self.range
        out[start:end] = result

    def value(self, coeffs):
        x = self._get_matrix(coeffs)
        # Native value rejects rectangular full inputs, even if a compact core is square.
        if x.shape[0] != x.shape[1]:
            return super().value(coeffs)
        support = zero_support(x)
        if support is None or not np.isfinite(self.strength):
            return super().value(coeffs)
        rows, cols = support
        if not len(rows) or not len(cols):
            return self.strength * 0.
        s = svd(x[np.ix_(rows, cols)], compute_uv=False, full_matrices=False)
        return self.strength * s.sum()
