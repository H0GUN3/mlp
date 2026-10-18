"""Small in-memory fixtures; no protected observations and no filesystem outputs."""
import importlib.util
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile, ZipExtFile

import numpy as np

spec = importlib.util.spec_from_file_location("sn_input_bundle",
                                             Path(__file__).with_name("input_bundle.py"))
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot locate input preparation module")
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


def npy_bytes(shape=(4, 2), dtype="<f8", fortran=False, payload=None):
    stream = io.BytesIO()
    np.lib.format.write_array_header_1_0(stream, {
        "shape": shape, "fortran_order": fortran, "descr": np.lib.format.dtype_to_descr(np.dtype(dtype)),
    })
    if payload is None:
        payload = np.arange(np.prod(shape), dtype=np.float64).tobytes()
    stream.write(payload)
    return stream.getvalue()


def split_fixture():
    return {
        "fold_ids": np.array([0, 0, 1, 1, 2, 2], dtype=np.int64),
        "episode_ids": np.array(["e0", "e0", "e1", "e1", "e2", "e2"]),
        "event_ids": np.array(["e0", "", "e1", "", "e2", ""]),
        "labels": np.array([0, -1, 1, -1, 2, -1], dtype=np.int64),
    }


class StreamingTests(unittest.TestCase):
    def test_zip_stream_selected_order_and_no_np_load(self):
        zipped = io.BytesIO()
        with ZipFile(zipped, "w", ZIP_DEFLATED) as archive:
            archive.writestr("values.npy", npy_bytes())
        zipped.seek(0)
        with ZipFile(zipped) as archive, archive.open("values.npy") as stream:
            self.assertIsInstance(stream, ZipExtFile)
            with patch.object(inputs.np, "load", side_effect=AssertionError("No whole-array load")):
                result, audit = inputs.selected_npy_rows(
                    stream, np.array([3, 0, 2]), (4, 2), "<f8")
        np.testing.assert_array_equal(result, [[6, 7], [0, 1], [4, 5]])
        self.assertEqual(audit["decoded_rows"], 3)
        self.assertEqual(audit["opaque_skipped_rows"], 1)
        self.assertEqual(audit["opaque_skipped_payload_bytes"], 16)

    def test_protected_sentinel_bytes_never_reach_decoder(self):
        sentinel = b"PROTECT!" * 2
        payloads = [sentinel, struct.pack("<dd", 2, 3), sentinel,
                    struct.pack("<dd", 6, 7), sentinel]
        original_decoder = np.frombuffer
        decoded = []

        def guarded_decoder(payload, **kwargs):
            self.assertNotIn(b"PROTECT!", payload)
            decoded.append(payload)
            return original_decoder(payload, **kwargs)

        zipped = io.BytesIO()
        with ZipFile(zipped, "w", ZIP_DEFLATED) as archive:
            archive.writestr("values.npy", npy_bytes((5, 2), payload=b"".join(payloads)))
        zipped.seek(0)
        with ZipFile(zipped) as archive, archive.open("values.npy") as stream:
            with patch.object(inputs.np, "frombuffer", side_effect=guarded_decoder):
                result, audit = inputs.selected_npy_rows(
                    stream, np.array([3, 1]), (5, 2), "<f8")
        self.assertEqual(decoded, [payloads[1], payloads[3]])
        np.testing.assert_array_equal(result, [[6, 7], [2, 3]])
        self.assertEqual(audit["opaque_skipped_rows"], 3)

    def test_unsafe_dtype_shape_and_order_rejected_before_payload(self):
        cases = [
            {"dtype": object}, {"dtype": "float32"}, {"dtype": ">f8"},
            {"dtype": [("field", "f8")]}, {"shape": (4, 3)},
            {"shape": (3, 2)}, {"fortran": True},
        ]
        for case in cases:
            with self.subTest(case=case):
                with patch.object(inputs.np, "frombuffer",
                                  side_effect=AssertionError("Header must reject before decoding")):
                    with self.assertRaises(ValueError):
                        inputs.selected_npy_rows(io.BytesIO(npy_bytes(payload=b"", **case)),
                                                 np.array([1]), (4, 2), "<f8")

    def test_invalid_duplicate_indices_rejected_before_header(self):
        cases = [np.array([-1]), np.array([4]), np.array([1, 1]), np.array([1.0]),
                 np.array([True]), np.array([1], dtype=object),
                 np.array([], dtype=np.int64), np.array([[1]]),
                 np.array([2**63], dtype=np.uint64)]
        for indices in cases:
            with self.subTest(indices=indices):
                with self.assertRaises(ValueError):
                    inputs.selected_npy_rows(io.BytesIO(b""), indices, (4, 2), "<f8")

    def test_truncated_selected_and_skipped_payloads_fail(self):
        for indices, size in (([3], 50), ([0], 20)):
            with self.subTest(indices=indices):
                with self.assertRaises(ValueError):
                    inputs.selected_npy_rows(
                        io.BytesIO(npy_bytes(payload=b"x" * size)),
                        np.array(indices), (4, 2), "<f8")

    def test_trailing_payload_rejected(self):
        with self.assertRaises(ValueError):
            inputs.selected_npy_rows(io.BytesIO(npy_bytes() + b"extra"),
                                     np.array([0]), (4, 2), "<f8")

    def test_scalar_row_labels_preserve_order(self):
        payload = np.array([-1, 7, 2, 0], dtype=np.int64).tobytes()
        result, _ = inputs.selected_npy_rows(
            io.BytesIO(npy_bytes((4,), "<i8", payload=payload)),
            np.array([2, 0]), (4,), "<i8")
        np.testing.assert_array_equal(result, [2, -1])

    def test_unexpected_archive_member_rejected(self):
        zipped = io.BytesIO()
        with ZipFile(zipped, "w", ZIP_DEFLATED) as archive:
            archive.writestr("unexpected.npy", npy_bytes())
        zipped.seek(0)
        with self.assertRaises(ValueError):
            inputs.selected_native_rows(zipped, np.array([0]))


class ContractTests(unittest.TestCase):
    def test_all_rotations_cover_once_with_normal_episode_isolation(self):
        arrays = split_fixture()
        evaluations = []
        for rotation in range(3):
            split = inputs.split_indices(arrays, rotation)
            for name, group in (("train", (rotation + 2) % 3),
                                ("validation", (rotation + 1) % 3),
                                ("evaluation", rotation)):
                np.testing.assert_array_equal(split[name], [group * 2, group * 2 + 1])
                self.assertEqual(set(arrays["episode_ids"][split[name]]), {"e" + str(group)})
                self.assertEqual(arrays["labels"][split[name]].tolist().count(-1), 1)
            self.assertEqual(sorted(np.concatenate(list(split.values())).tolist()), list(range(6)))
            evaluations.extend(split["evaluation"].tolist())
        self.assertEqual(sorted(evaluations), list(range(6)))

    def test_normal_episode_leakage_rejected(self):
        arrays = split_fixture()
        arrays["episode_ids"][3] = "e0"
        with self.assertRaisesRegex(ValueError, "boundary"):
            inputs.split_indices(arrays, 0)

    def test_event_leakage_rejected(self):
        arrays = split_fixture()
        arrays["event_ids"][2] = "e0"
        with self.assertRaisesRegex(ValueError, "boundary"):
            inputs.split_indices(arrays, 0)

    def test_invalid_rotation_and_fold_metadata_rejected(self):
        for rotation in (-1, 3, 0.0, True):
            with self.subTest(rotation=rotation), self.assertRaises(ValueError):
                inputs.split_indices(split_fixture(), rotation)
        for folds in (np.array([0.0] * 6), np.array([0, 0, 1, 1, 2, 3])):
            arrays = split_fixture()
            arrays["fold_ids"] = folds
            with self.assertRaises(ValueError):
                inputs.split_indices(arrays, 0)

    def test_manifest_mutation_rejected_before_array_load(self):
        manifest = {"input_npz_sha256": "before"}
        manifest["manifest_payload_sha256"] = inputs.manifest_digest(manifest)
        manifest["input_npz_sha256"] = "after"
        with patch.object(inputs, "read_json", return_value=manifest):
            with patch.object(inputs.np, "load") as loader:
                with self.assertRaisesRegex(ValueError, "Manifest payload hash"):
                    inputs.load_inputs()
                loader.assert_not_called()

    def test_generated_npz_hash_checked_before_loading(self):
        sources = dict(inputs.PINS)
        sources.update({str((inputs.HERE / name).relative_to(inputs.ROOT)): "unit"
                        for name in ("input_bundle.py", "test_input_bundle.py")})
        manifest = {"source_hashes": sources, "input_npz_sha256": "not-unit"}
        manifest["manifest_payload_sha256"] = inputs.manifest_digest(manifest)
        with patch.object(inputs, "read_json", return_value=manifest), \
                patch.object(inputs, "sha256", return_value="unit"), \
                patch.object(inputs, "verify_hashes"), patch.object(inputs.np, "load") as loader:
            with self.assertRaisesRegex(ValueError, "Generated input hash"):
                inputs.load_inputs()
            loader.assert_not_called()

    def test_existing_outputs_refused_before_source_access(self):
        with patch.object(inputs.Path, "exists", return_value=True), \
                patch.object(inputs, "verify_hashes") as source_access:
            with self.assertRaisesRegex(ValueError, "overwrite"):
                inputs.prepare()
            source_access.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
