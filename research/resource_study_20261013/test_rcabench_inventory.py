"""Synthetic tests only, using memory and temporary files; no real observations."""
import io
import contextlib
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import rcabench_inventory as audit
from rcabench_inventory import MAX_JSON_BYTES, REQUIRED, inventory


def case_files(name="case-a", roots=None, env=None):
    injection = {"ground_truth": {"service": ["svc-a"] if roots is None else roots}, "fault_type": 1}
    if env is None:
        env = dict(NORMAL_START="100", NORMAL_END="150", ABNORMAL_START="150", ABNORMAL_END="200")
    files = {f"{name}/{key}": b"not-a-real-parquet" for key in REQUIRED}
    files[f"{name}/injection.json"] = json.dumps(injection).encode()
    files[f"{name}/env.json"] = json.dumps(env).encode()
    return list(files.items())


def archive_bytes(entries):
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode="w:gz") as archive:
        for name, payload in entries:
            member = tarfile.TarInfo(name)
            if payload is None:
                member.type = tarfile.SYMTYPE
                member.linkname = "/outside"
                archive.addfile(member)
            else:
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
    target.seek(0)
    return target


class InventoryTest(unittest.TestCase):
    def test_cli_report_does_not_overwrite(self):
        payload = archive_bytes(case_files()).getvalue()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.tar.gz"
            report = Path(directory) / "report.json"
            source.write_bytes(payload)
            with (
                patch.object(audit, "EXPECTED_BYTES", len(payload)),
                patch.object(audit, "EXPECTED_MD5", hashlib.md5(payload).hexdigest()),
                patch("sys.argv", ["inventory", str(source), "--report", str(report)]),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                audit.main()
                saved = report.read_bytes()
                self.assertEqual(json.loads(saved)["case_directories"], 1)
                with self.assertRaises(SystemExit) as raised:
                    audit.main()
                self.assertEqual(raised.exception.code, 1)
                self.assertEqual(report.read_bytes(), saved)

    def test_single_multiple_missing_and_duplicate_metadata(self):
        entries = case_files() + case_files("same-metadata")
        entries += case_files("multi", ["svc-a", "svc-b"])
        entries += [(p, b) for p, b in case_files("missing") if not p.endswith("normal_traces.parquet")]
        report = inventory(archive_bytes(entries))
        self.assertEqual(report["case_directories"], 4)
        self.assertEqual(report["metadata_candidates_not_deduplicated"], 2)
        self.assertEqual(report["multiple_service_label_cases"], 1)
        self.assertIn(["case-a", "missing", "same-metadata"], report["same_label_period_fault_groups"])
        self.assertIsNone(report["independent_usable_incidents"])
        # Deliberately invalid Parquet content must never be called verified observations.
        self.assertEqual(report["stage"], "metadata_only_not_observation_quality")

    def test_bad_periods_and_labels(self):
        for env in [
            {},
            dict(NORMAL_START=100, NORMAL_END=160, ABNORMAL_START=150, ABNORMAL_END=200),
            dict(NORMAL_START=True, NORMAL_END=150, ABNORMAL_START=150, ABNORMAL_END=200),
            dict(NORMAL_START="100.1", NORMAL_END=150, ABNORMAL_START=150, ABNORMAL_END=200),
            dict(NORMAL_START=10**30, NORMAL_END=150, ABNORMAL_START=150, ABNORMAL_END=200),
        ]:
            with self.subTest(env=env):
                report = inventory(archive_bytes(case_files(env=env)))
                self.assertEqual(report["metadata_candidates_not_deduplicated"], 0)
                self.assertIn("invalid_or_overlapping_periods", report["cases"][0]["reasons"])
        for roots in [[], ["svc-a", "svc-a"], [" svc-a"], [123]]:
            with self.subTest(roots=roots):
                self.assertEqual(
                    inventory(archive_bytes(case_files(roots=roots)))["metadata_candidates_not_deduplicated"], 0
                )

    def test_invalid_empty_and_oversized_metadata(self):
        for payload in [b"{", b"[]", b'{"ground_truth":{},"ground_truth":{}}', b"x" * (MAX_JSON_BYTES + 1), b""]:
            with self.subTest(length=len(payload)):
                entries = [(p, payload if p.endswith("injection.json") else b) for p, b in case_files()]
                report = inventory(archive_bytes(entries))
                self.assertEqual(report["metadata_candidates_not_deduplicated"], 0)
                self.assertTrue(report["cases"][0]["reasons"])

    def test_unsafe_duplicate_link_and_unexpected_layout(self):
        for extra in [
            [("../escape", b"x")], [("/absolute", b"x")], [("case/link", None)],
            [("case-a/injection.json", b"{}")], [("case/nested/file", b"x")],
            [("top-level-file", b"x")],
        ]:
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    inventory(archive_bytes(case_files() + extra))

    def test_empty_archive_and_bad_gzip(self):
        with self.assertRaises(ValueError):
            inventory(archive_bytes([]))
        with self.assertRaises(tarfile.ReadError):
            inventory(io.BytesIO(b"not gzip"))


if __name__ == "__main__":
    unittest.main()
