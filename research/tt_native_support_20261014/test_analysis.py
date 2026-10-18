import unittest

import numpy as np

from research.tt_native_support_20261014 import analysis as a


class AnalysisTests(unittest.TestCase):
    def event(self, value, fault="network_delay", windows=1):
        part = {"windows": windows, "metrics": dict.fromkeys(a.METRICS, value),
                "per_seed": {str(s): dict.fromkeys(a.METRICS, value) for s in a.ex.SEEDS}}
        return {"fault": {"fault_type": fault}, "all": part, "zero": part, "positive": part}

    def test_incident_equal_subgroups(self):
        result = a.summarize({"A": self.event(1., windows=1), "B": self.event(0., windows=99)})
        self.assertEqual(result["metrics"]["top1"], .5)
        self.assertEqual(result["windows"], 100)
        self.assertEqual(result["events"], 2)

    def test_no_support_does_not_make_nan(self):
        event = self.event(0.)
        event["positive"] = {"windows": 0, "metrics": None, "per_seed": {}}
        result = a.summarize({"A": event}, part="positive")
        self.assertEqual(result["events"], 0)
        self.assertIsNone(result["metrics"])

    def test_fractional_tie_subset_conservation(self):
        rows = a.root_subset_scores(np.array([[1., 1.], [0., 1.], [1., 0.]]),
                                    np.array([0, 0, -1]), np.array(["A", "A", ""]),
                                    np.array([[0, 1], [2, 1], [1, 1]]), 0, 11)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["all"]["metrics"]["top1"], .25)
        self.assertEqual(rows[0]["zero"]["metrics"]["top1"], .5)
        self.assertEqual(rows[0]["positive"]["metrics"]["top1"], 0.)
        self.assertEqual(rows[0]["all"]["windows"], 2)

    def test_gate_does_not_change_thresholds(self):
        events = {}
        for fault in ("network_delay", "network_loss"):
            for i in range(5):
                event = self.event(.5, fault)
                event["positive"] = self.event(.6, fault)["all"]
                events[fault + str(i)] = event
        reports = [{"kind": "diagmlp", "selected_at_cap": False, "fold": 0, "seed": 11, "best_epoch": 50}]
        gate = a.baseline_gate(reports, events)
        self.assertTrue(gate["allow_next_stage"])
        reports[0]["selected_at_cap"] = True
        self.assertFalse(a.baseline_gate(reports, events)["allow_next_stage"])

    def test_effect_gate_cpu_regression(self):
        base = {"A": self.event(.5), "B": self.event(1., "cpu_load")}
        improved = {"A": self.event(.6), "B": self.event(1., "cpu_load")}
        self.assertTrue(a.count_gate(base, improved)["allow_next_stage"])
        improved["B"] = self.event(.95, "cpu_load")
        self.assertFalse(a.count_gate(base, improved)["allow_next_stage"])

    def test_train_fold_seed_collapsed_before_incident_mean(self):
        metadata = {"faults": {"A": {"fault_type": "network_delay"},
                               "B": {"fault_type": "network_loss"}},
                    "event_folds": {"A": 0, "B": 1}}
        rows = []
        for event, folds, windows in (("A", (1, 2), 100), ("B", (0, 2), 1)):
            for fold in folds:
                for seed in a.ex.SEEDS:
                    value = float(fold - 1) if event == "A" else 1.
                    part = {"windows": windows, "metrics": dict.fromkeys(a.METRICS, value)}
                    rows.append({"event_id": event, "fold": fold, "seed": seed,
                                 "all": part, "positive": part,
                                 "zero": {"windows": 0, "metrics": None}})
        result = a.collapse(rows, metadata, "train")
        self.assertEqual(result["A"]["all"]["metrics"]["top1"], .5)
        self.assertEqual(result["A"]["all"]["per_seed"]["11"]["top1"], .5)
        summary = a.summarize(result)
        self.assertEqual(summary["events"], 2)
        self.assertEqual(summary["windows"], 101)
        self.assertEqual(summary["metrics"]["top1"], .75)
        self.assertIsNone(result["A"]["zero"]["metrics"])
        with self.assertRaises(ValueError):
            a.collapse(rows[:-1], metadata, "train")
        with self.assertRaises(ValueError):
            a.collapse(rows + rows[:1], metadata, "train")


if __name__ == "__main__":
    unittest.main()
