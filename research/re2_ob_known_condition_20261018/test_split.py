import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from research.re2_ob_known_condition_20261018 import split


def fixture():
    rows, manifest_cases, metadata = [], [], {}
    protected_groups = {
        ("checkoutservice", "disk"), ("currencyservice", "cpu"),
        ("currencyservice", "socket"), ("emailservice", "delay"),
        ("productcatalogservice", "mem"), ("recommendationservice", "loss"),
    }
    original_validation_groups = {
        ("checkoutservice", "cpu"), ("currencyservice", "delay"),
        ("emailservice", "disk"), ("productcatalogservice", "loss"),
        ("recommendationservice", "mem"), ("recommendationservice", "socket"),
    }
    for group_index in range(30):
        root = (
            "checkoutservice", "currencyservice", "emailservice",
            "productcatalogservice", "recommendationservice",
        )[group_index // 6]
        fault = ("cpu", "delay", "disk", "loss", "mem", "socket")[group_index % 6]
        for repetition in (1, 2, 3):
            case = "re2ob_{}_{}_{}".format(root, fault, repetition)
            if (root, fault) in protected_groups:
                partition = "test"
            elif (root, fault) in original_validation_groups:
                partition = "validation"
            else:
                partition = "train"
            row = {
                "case": case,
                "dataset": "RE2-OB",
                "root_cause_service": root,
                "fault": fault,
                "repetition": repetition,
                "inject_time": group_index * 1000 + repetition,
                "partition": partition,
            }
            rows.append(row)
            if partition == "test":
                continue
            meta = {
                "case": case,
                "status": "PASS_UNSCALED_CASE",
                "partition": partition,
                "root_service": root,
                "inject_time": row["inject_time"],
                "windows": 144,
                "source_sha256": "source",
                "raw_hashes": {"metrics": hashlib.sha256(case.encode()).hexdigest()},
            }
            meta_hash = hashlib.sha256(repr(meta).encode()).hexdigest()
            meta["metadata_sha256"] = meta_hash
            metadata[case] = meta
            manifest_cases.append(
                {"case": case, "partition": partition, "metadata_sha256": meta_hash}
            )
    return {"cases": rows}, {"cases": manifest_cases}, metadata


class SplitTests(unittest.TestCase):
    def test_loader_verifies_external_hash_without_self_hash_field(self):
        old, manifest, metadata = fixture()
        texts = {}
        for entry in manifest["cases"]:
            row = dict(metadata[entry["case"]])
            row.pop("metadata_sha256")
            text = json.dumps(row)
            texts[split.STAGE1 / entry["case"] / "metadata.json"] = text
            entry["metadata_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        texts[split.OLD_SPLIT] = json.dumps(old)
        texts[split.MANIFEST] = json.dumps(
            dict(manifest, status="PASS_UNSCALED_ONLY", stage_source_sha256="a" * 64))
        with patch.object(Path, "read_text", lambda path, **kwargs: texts[path]), \
                patch.object(split, "sha256", return_value="b" * 64):
            loaded = split.load_inputs()
        self.assertEqual(len(loaded[2]), 72)
        for entry in manifest["cases"]:
            self.assertEqual(loaded[2][entry["case"]]["metadata_sha256"],
                             entry["metadata_sha256"])

    def test_loader_rejects_protected_name_before_metadata_open(self):
        old, manifest, _ = fixture()
        manifest["cases"][0]["case"] = next(
            row["case"] for row in old["cases"] if row["partition"] == "test")
        texts = {split.OLD_SPLIT: json.dumps(old),
                 split.MANIFEST: json.dumps(dict(manifest, status="PASS_UNSCALED_ONLY"))}
        opened = []

        def read_text(path, **kwargs):
            opened.append(path)
            return texts[path]

        with patch.object(Path, "read_text", read_text):
            with self.assertRaisesRegex(ValueError, "protected or unapproved"):
                split.load_inputs()
        self.assertEqual(opened, [split.OLD_SPLIT, split.MANIFEST])

    def test_each_group_has_two_train_one_validation(self):
        result = split.build_split(*fixture(), source_hashes={})
        self.assertEqual(result["counts"]["train"], 48)
        self.assertEqual(result["counts"]["validation"], 24)
        groups = {}
        for row in result["cases"]:
            groups.setdefault((row["root_cause_service"], row["fault"]), []).append(
                row["partition"]
            )
        self.assertEqual(len(groups), 24)
        self.assertTrue(all(
            group.count("train") == 2 and group.count("validation") == 1
            for group in groups.values()
        ))

    def test_order_does_not_change_assignment(self):
        old_data, manifest, metadata = fixture()
        expected = split.build_split(old_data, manifest, metadata, {})
        old_data["cases"].reverse()
        manifest["cases"].reverse()
        self.assertEqual(expected, split.build_split(old_data, manifest, metadata, {}))

    def test_protected_case_in_manifest_is_rejected(self):
        old_data, manifest, metadata = fixture()
        protected = next(row["case"] for row in old_data["cases"] if row["partition"] == "test")
        manifest["cases"].append(
            {"case": protected, "partition": "test", "metadata_sha256": "invalid"}
        )
        with self.assertRaisesRegex(ValueError, "manifest does not match|protected"):
            split.build_split(old_data, manifest, metadata, {})

    def test_missing_repeat_or_malformed_case_is_rejected(self):
        old_data, manifest, metadata = fixture()
        removed = manifest["cases"].pop()
        metadata.pop(removed["case"])
        with self.assertRaisesRegex(ValueError, "manifest does not match"):
            split.build_split(old_data, manifest, metadata, {})
        old_data, manifest, metadata = fixture()
        manifest["cases"][0]["case"] = "unexpected-case"
        with self.assertRaisesRegex(ValueError, "manifest does not match"):
            split.build_split(old_data, manifest, metadata, {})

    def test_cross_partition_identical_raw_hash_is_rejected(self):
        old_data, manifest, metadata = fixture()
        by_group = {}
        for row in old_data["cases"]:
            if row["partition"] != "test":
                by_group.setdefault(
                    (row["root_cause_service"], row["fault"]), []
                ).append(row["case"])
        first_group = next(iter(by_group.values()))
        first_validation = next(
            case for case in first_group
            if next(row for row in old_data["cases"] if row["case"] == case)["repetition"]
            == split.assign_validation_repetition("svc-6", "cpu")
        )
        first_train = next(case for case in first_group if case != first_validation)
        metadata[first_validation]["raw_hashes"]["metrics"] = "duplicate"
        metadata[first_train]["raw_hashes"]["metrics"] = "duplicate"
        with self.assertRaisesRegex(ValueError, "identical raw file hash"):
            split.build_split(old_data, manifest, metadata, {})


if __name__ == "__main__":
    unittest.main()
