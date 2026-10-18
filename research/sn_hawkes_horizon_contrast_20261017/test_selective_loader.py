import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

import selective_loader as loader


class SelectiveLoaderTests(unittest.TestCase):
    def setUp(self):
        self.root = loader.HERE / "inputs"
        self.root.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=str(self.root), prefix="fixture_")
        self.path = Path(self.directory.name) / "synthetic.npz"

    def tearDown(self):
        self.directory.cleanup()

    def save(self, **arrays):
        with self.path.open("xb") as stream:
            np.savez_compressed(stream, **arrays)

    def test_sentinel_skipped_before_and_between_selected_order_preserved(self):
        forbidden = np.array([987654321.125, -987654321.125])
        data = np.array([[3., 4.], forbidden, [5., 6.], forbidden, [7., 8.]])
        self.save(metrics=data)
        decoded = []
        original = np.frombuffer

        def guard(block, *args, **kwargs):
            self.assertNotIn(forbidden.tobytes(), block)
            decoded.append(bytes(block))
            return original(block, *args, **kwargs)

        audit = []
        with patch.object(loader.np, "frombuffer", side_effect=guard):
            actual = loader.read_rows(self.path, "metrics", [4, 0, 2], (5, 2), "f", audit)
        np.testing.assert_array_equal(actual, data[[4, 0, 2]])
        self.assertEqual(len(decoded), 3)
        self.assertEqual(audit[0]["skipped_rows"], 2)
        self.assertEqual(audit[0]["discarded_decompressed_bytes"], 32)

    def test_empty_selection_never_calls_frombuffer(self):
        self.save(labels=np.array([123, 456], dtype=np.int64))
        audit = []
        with patch.object(loader.np, "frombuffer", side_effect=AssertionError("forbidden decode")):
            actual = loader.read_rows(self.path, "labels", [], (2,), "iu", audit)
        self.assertEqual(actual.shape, (0,))
        self.assertEqual(audit[0]["decoded_bytes"], 0)

    def test_ragged_only_selected_event_values_interpreted(self):
        sentinel = -999999
        self.save(
            log_window=np.array([0, 1, 1, 2, 3], dtype=np.int64),
            log_node=np.array([sentinel, 0, 1, sentinel, 1], dtype=np.int64),
            log_template=np.array([sentinel, 2, 1, sentinel, 0], dtype=np.int64),
            log_timestamp=np.array([np.nan, 100., 109.999, np.nan, 301.]),
            window_start=np.array([sentinel, 100, sentinel, 300], dtype=np.int64),
        )
        original = np.frombuffer
        forbidden_integer = np.array([sentinel], dtype=np.int64).tobytes()
        forbidden_float = np.array([np.nan], dtype=np.float64).tobytes()

        def guard(block, *args, **kwargs):
            self.assertNotIn(forbidden_integer, block)
            self.assertNotIn(forbidden_float, block)
            return original(block, *args, **kwargs)

        audit = []
        with patch.object(loader.np, "frombuffer", side_effect=guard):
            selected = loader.load_events(self.path, np.array([1, 3]), 4, 2, 3, audit)
        np.testing.assert_array_equal(selected["log_window"], [1, 1, 3])
        np.testing.assert_array_equal(selected["log_template"], [2, 1, 0])
        np.testing.assert_array_equal(selected["window_start"], [100, 300])
        self.assertEqual(sum(a["structural_metadata"] for a in audit), 1)

    def test_shape_dtype_indices_and_fortran_rejected(self):
        self.save(values=np.asfortranarray(np.arange(6.).reshape(3, 2)),
                  objects=np.array([object()], dtype=object),
                  integers=np.arange(3, dtype=np.int64))
        for key, rows, shape, kind in (
            ("values", [0], (3, 2), "f"),
            ("objects", [0], (1,), "fiu"),
            ("integers", [0], (2,), "iu"),
            ("integers", [0], (3,), "f"),
            ("integers", [0, 0], (3,), "iu"),
            ("integers", [-1], (3,), "iu"),
            ("integers", [3], (3,), "iu"),
            ("integers", [1.5], (3,), "iu"),
        ):
            with self.subTest(key=key, rows=rows, shape=shape, kind=kind):
                with self.assertRaises(ValueError):
                    loader.read_rows(self.path, key, rows, shape, kind, [])

    def test_truncated_or_duplicate_member_rejected(self):
        buffer = io.BytesIO()
        np.save(buffer, np.array([1., 2.]), allow_pickle=False)
        with zipfile.ZipFile(self.path, "x") as archive:
            archive.writestr("values.npy", buffer.getvalue()[:-1])
        with self.assertRaisesRegex(ValueError, "byte size"):
            loader.read_rows(self.path, "values", [0], (2,), "f", [])
        duplicate = Path(self.directory.name) / "duplicate.npz"
        with zipfile.ZipFile(duplicate, "x") as archive:
            archive.writestr("values.npy", buffer.getvalue())
            with self.assertWarns(UserWarning):
                archive.writestr("values.npy", buffer.getvalue())
        with self.assertRaisesRegex(ValueError, "duplicate"):
            loader.read_rows(duplicate, "values", [0], (2,), "f", [])

    def test_frozen_split_original_indices_and_training_order(self):
        permutation = np.random.RandomState(42).permutation(564)
        split = {"seed": 42, "counts": {"train": 316, "validation": 78,
                                      "test": 169, "unassigned": 1},
                 "indices": {"train": permutation[:316].tolist(),
                             "validation": permutation[316:394].tolist()}}
        indices, positions = loader.selected_split(split)
        np.testing.assert_array_equal(indices[positions["train_positions"]], permutation[:316])
        np.testing.assert_array_equal(indices[positions["validation_positions"]], permutation[316:394])
        self.assertEqual(len(indices), 394)
        self.assertTrue(np.all(np.diff(indices) > 0))
        split["indices"]["train"].reverse()
        with self.assertRaisesRegex(ValueError, "order mismatch"):
            loader.selected_split(split)


if __name__ == "__main__":
    unittest.main()
