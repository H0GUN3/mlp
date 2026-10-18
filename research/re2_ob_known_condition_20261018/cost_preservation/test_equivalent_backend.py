"""Focused fixed-tolerance checks; only one paired four-dimensional solver fixture."""
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import warnings

import numpy as np
from tick.prox import ProxNuclear

from equivalent_backend import ZeroStructureProxNuclear, zero_support

ERRORS = []
ATOL = RTOL = 5e-14


class EquivalentBackendTests(unittest.TestCase):
    def compare(self, x, strength=.3, step=.7, positive=False, ranged=False):
        coeffs = x.ravel().copy()
        outside = np.array([-7., 13., -19., 23.])
        selected_range = None
        if ranged:
            coeffs = np.r_[outside[:2], coeffs, outside[2:]]
            selected_range = (2, coeffs.size - 2)
        a = ProxNuclear(strength, n_rows=x.shape[0], positive=positive)
        b = ZeroStructureProxNuclear(strength, n_rows=x.shape[0], positive=positive)
        if selected_range is not None:
            a.range = selected_range
            b.range = selected_range
        original = coeffs.copy()
        out = np.full_like(coeffs, 999.)
        with warnings.catch_warnings(record=True) as wa:
            warnings.simplefilter("always")
            expected = a.call(coeffs, step=step)
        with warnings.catch_warnings(record=True) as wb:
            warnings.simplefilter("always")
            actual = b.call(coeffs, step=step, out=out)
        self.assertIs(actual, out)
        np.testing.assert_array_equal(coeffs, original)
        np.testing.assert_allclose(actual, expected, atol=ATOL, rtol=RTOL)
        self.assertEqual([str(w.message) for w in wa], [str(w.message) for w in wb])
        if ranged:
            np.testing.assert_array_equal(actual[[0, 1, -2, -1]], outside)
        # The native public API supports aliasing out with coeffs.
        alias = coeffs.copy()
        self.assertIs(b.call(alias, step=step, out=alias), alias)
        np.testing.assert_array_equal(alias, actual)
        value_error = None
        if x.shape[0] == x.shape[1]:
            va, vb = a.value(coeffs), b.value(coeffs)
            np.testing.assert_allclose(vb, va, atol=ATOL, rtol=RTOL)
            value_error = abs(float(vb - va))
        else:
            for prox in (a, b):
                with self.assertRaisesRegex(ValueError, "squared matrix"):
                    prox.value(coeffs)
        ERRORS.append(dict(test=self.id(), shape=list(x.shape), positive=positive,
                           ranged=ranged, strength=float(strength), step=float(step),
                           max_abs=float(np.max(np.abs(actual - expected))) if actual.size else 0.,
                           value_abs=value_error, exact=bool(np.array_equal(actual, expected))))
        return a, b, expected, actual

    def test_rectangular_zero_row_and_column(self):
        for shape in ((5, 7), (7, 5)):
            x = np.zeros(shape)
            x[np.ix_([1, 3], [0, 2, 4])] = [[1., -2., 3.], [4., 5., -6.]]
            self.compare(x, ranged=True)

    def test_all_zero(self):
        for shape in ((4, 4), (3, 6)):
            for positive in (False, True):
                self.compare(np.zeros(shape), positive=positive, ranged=True)
                self.compare(np.zeros(shape), strength=0., positive=positive)

    def test_row_only_column_only_both_signed(self):
        rng = np.random.RandomState(42)
        for mode in ("rows", "columns", "both"):
            x = rng.randn(7, 7)
            if mode in ("rows", "both"):
                x[[0, 3, 6]] = 0
            if mode in ("columns", "both"):
                x[:, [1, 5]] = 0
            for positive in (False, True):
                self.compare(x, positive=positive, ranged=True)

    def test_full_rank_dense_exact_fallback(self):
        x = np.random.RandomState(12).randn(5, 5)
        self.assertIsNone(zero_support(x))
        with patch("equivalent_backend.svd", side_effect=AssertionError("Must delegate dense")):
            a, b, expected, actual = self.compare(x)
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(a.value(x.ravel()), b.value(x.ravel()))

    def test_original_threshold_at_and_around_boundary(self):
        below = np.nextafter(1., 0.)
        above = np.nextafter(1., 2.)
        x = np.diag([0., below, 1., above, 2., 0.])
        _, _, expected, actual = self.compare(x, strength=1., step=1.)
        np.testing.assert_array_equal(actual, expected)
        diagonal = actual.reshape(x.shape).diagonal()
        self.assertEqual(diagonal[1], 0.)
        self.assertEqual(diagonal[2], 0.)
        self.assertGreater(diagonal[3], 0.)

    def test_no_epsilon_pruning(self):
        x = np.diag([1e-200, 2., 0., 0.])
        support = zero_support(x)
        self.assertIsNotNone(support)
        assert support is not None
        np.testing.assert_array_equal(support[0], [0, 1])
        _, _, _, actual = self.compare(x, strength=0.)
        self.assertEqual(actual.reshape(x.shape)[0, 0], 1e-200)

    def test_negative_threshold_and_float32_fallback(self):
        x = np.diag([-3., 2., 0., 0.])
        for strength, step in ((-.3, 1.), (.3, -1.)):
            with patch("equivalent_backend.svd", side_effect=AssertionError("Must delegate")):
                a = ProxNuclear(strength, n_rows=4)
                b = ZeroStructureProxNuclear(strength, n_rows=4)
                np.testing.assert_array_equal(a.call(x.ravel(), step), b.call(x.ravel(), step))
        x = x.astype(np.float32)
        self.assertIsNone(zero_support(x))
        self.compare(x)

    def test_invalid_shape_and_nonfinite_semantics(self):
        for cls in (ProxNuclear, ZeroStructureProxNuclear):
            with self.assertRaisesRegex(ValueError, "must be set"):
                cls(.3).call(np.ones(4))
            with self.assertRaisesRegex(ValueError, "multiple"):
                cls(.3, n_rows=3).call(np.ones(4))
        x = np.diag([np.nan, 0.])
        self.assertIsNone(zero_support(x))
        for cls in (ProxNuclear, ZeroStructureProxNuclear):
            with self.assertRaises(np.linalg.LinAlgError):
                cls(.3, n_rows=2).call(x.ravel())

    def test_compact_svd_receives_only_exact_support(self):
        x = np.zeros((8, 8))
        x[np.ix_([2, 6], [1, 3, 7])] = [[1, 2, 3], [4, -1, 5]]
        real = np.linalg.svd
        shapes = []

        def measured(matrix, **kwargs):
            shapes.append(matrix.shape)
            return real(matrix, **kwargs)

        with patch("equivalent_backend.svd", side_effect=measured):
            self.compare(x)
        self.assertTrue(shapes)
        self.assertTrue(all(shape == (2, 3) for shape in shapes))

    def test_unchanged_adm4_with_tiny_substitution(self):
        from probes.native_runtime import HawkesADM4
        module = importlib.import_module("tick.hawkes.inference.hawkes_adm4")
        outputs = []
        for cls in (ProxNuclear, ZeroStructureProxNuclear):
            with patch.object(module, "ProxNuclear", cls), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                np.random.seed(42)
                model = HawkesADM4(3)
                self.assertEqual(model.max_iter, 50)
                self.assertEqual(model.em_max_iter, 30)
                self.assertEqual(model.tol, 1e-5)
                self.assertEqual(model.record_every, 10)
                self.assertEqual(model.n_threads, 1)
                knots = [np.array(k) for k in ([0.], [0., 1., 2.], [0.], [0., 3.])]
                model.fit(knots, end_times=10., baseline_start=np.ones(4) * .2)
            outputs.append((model.baseline.copy(), model.history.last_values["n_iter"],
                            [str(w.message) for w in caught]))
        np.testing.assert_allclose(outputs[0][0], outputs[1][0], atol=ATOL, rtol=RTOL)
        np.testing.assert_array_equal(outputs[0][0].astype(np.float32), outputs[1][0].astype(np.float32))
        self.assertEqual(outputs[0][1:], outputs[1][1:])
        ERRORS.append(dict(test=self.id(), max_abs=float(np.max(np.abs(outputs[0][0] - outputs[1][0]))),
                           iterations=int(outputs[0][1]), warnings=outputs[0][2]))


if __name__ == "__main__":
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EquivalentBackendTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = dict(tests_run=result.testsRun, success=result.wasSuccessful(),
                  failures=len(result.failures), errors=len(result.errors),
                  fixed_atol=ATOL, fixed_rtol=RTOL, comparisons=ERRORS, output=stream.getvalue(),
                  pandas_loaded="pandas" in sys.modules)
    target = Path(__file__).parent / "probes" / (
        sys.argv[1] if len(sys.argv) > 1 else "unit-tests.json")
    if target.parent != Path(__file__).parent / "probes" or target.suffix != ".json":
        raise ValueError("Only an exclusive probes JSON report is allowed")
    with target.open("x") as handle:
        json.dump(report, handle, sort_keys=True, indent=2, allow_nan=False)
    print(stream.getvalue(), end="", flush=True)
    if result.wasSuccessful() and "pandas" not in sys.modules:
        print("NUMERICS_UNIT_TESTS_PASS", flush=True)
    else:
        sys.exit(1)
