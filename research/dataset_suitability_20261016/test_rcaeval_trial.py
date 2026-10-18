"""Synthetic tests for RCAEval metadata-only feasibility calculations."""

import unittest

from research.dataset_suitability_20261016.rcaeval_trial import (
    group_fold,
    partition_summary,
    repetition_histogram,
    scope_rows,
    transfer_summary,
    validate_rows,
)


def row(case, dataset, system, root, fault, repetition=1, logs=True, traces=True):
    return {
        "case": case,
        "dataset": dataset,
        "system": system,
        "root_cause_service": root,
        "fault": fault,
        "repetition": repetition,
        "has_logs": logs,
        "n_logs": 10 if logs else 0,
        "has_traces": traces,
        "n_traces": 20 if traces else 0,
    }


class MetadataTests(unittest.TestCase):
    def test_group_folds_keep_condition_repetitions_together(self):
        rows = [
            row("a", "RE2-OB", "OB", "root-a", "cpu", 1),
            row("b", "RE2-OB", "OB", "root-a", "cpu", 2),
            row("c", "RE3-OB", "OB", "root-a", "cpu", 1),
            row("d", "RE3-OB", "OB", "root-b", "f5", 1),
        ]
        summary = partition_summary(rows)
        self.assertEqual(summary["group_count"], 2)
        self.assertTrue(summary["all_groups_single_fold"])
        self.assertEqual(sum(fold["heldout_cases"] for fold in summary["folds"]), len(rows))
        self.assertEqual(group_fold(("OB", "root-a", "cpu")),
                         group_fold(("OB", "root-a", "cpu")))

    def test_case_level_contrast_exposes_within_condition_split(self):
        rows = [row(f"case-{n}", "RE2-OB", "OB", "root-a", "cpu", n) for n in range(1, 8)]
        contrast = partition_summary(rows)["case_level_contrast"]
        self.assertEqual(contrast["repeated_conditions"], 1)
        self.assertEqual(contrast["conditions_spanning_multiple_case_folds"], 1)

    def test_transfer_finds_unseen_root_and_fault_conditions(self):
        rows = [
            row("a", "RE2-OB", "OB", "root-a", "cpu"),
            row("b", "RE2-OB", "OB", "root-b", "delay"),
            row("c", "RE3-OB", "OB", "root-a", "f1"),
            row("d", "RE3-OB", "OB", "root-c", "f5"),
        ]
        result = transfer_summary(rows)["OB"]
        self.assertEqual(result["root_overlap"], ["root-a"])
        self.assertEqual(result["re3_roots_unseen_in_re2"], ["root-c"])
        self.assertFalse(result["candidate_proxy_covers_re3_root_labels"])
        self.assertIn("root-a|f1", result["re3_conditions_new_to_re2"])

    def test_validation_rejects_bad_metadata_and_flag_mismatch(self):
        invalid = row("bad", "RE2-OB", "OB", "root", "cpu", traces=False)
        invalid["n_traces"] = 3
        with self.assertRaises(ValueError):
            validate_rows([invalid])
        invalid = row("bad-root", "RE2-OB", "OB", "", "cpu")
        with self.assertRaises(ValueError):
            validate_rows([invalid])

    def test_relevant_scope_excludes_re1_and_sock_shop(self):
        rows = [
            row("re2ob_x", "RE2-OB", "OB", "root-a", "cpu"),
            row("re2tt_x", "RE2-TT", "TT", "root-b", "cpu"),
            row("re3ob_x", "RE3-OB", "OB", "root-a", "f1"),
            row("re3tt_x", "RE3-TT", "TT", "root-b", "f2"),
            row("re1ob_x", "RE1-OB", "OB", "root-a", "cpu", logs=False, traces=False),
            row("re2ss_x", "RE2-SS", "SS", "root-z", "cpu", traces=False),
        ]
        validate_rows(rows)
        self.assertEqual([item["dataset"] for item in scope_rows(rows)],
                         ["RE2-OB", "RE2-TT", "RE3-OB", "RE3-TT"])

    def test_nonuniform_repetitions_are_preserved(self):
        rows = [
            row("a", "RE3-OB", "OB", "root-a", "f1", 1),
            row("b", "RE3-OB", "OB", "root-a", "f1", 2),
            row("c", "RE3-OB", "OB", "root-b", "f5", 1),
        ]
        result = transfer_summary(rows)["OB"]
        self.assertEqual(result["re3_root_fault_conditions"], 2)
        self.assertEqual(result["re3_conditions_overlapping_re2"], [])
        self.assertEqual(result["re3_cases"], 3)
        self.assertEqual(repetition_histogram(rows, "RE3-OB"), {1: 1, 2: 1})


if __name__ == "__main__":
    unittest.main()
