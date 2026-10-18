"""Focused tests for metadata-only Eadro split roles."""
import unittest

import numpy as np

from research.dataset_suitability_20261016.eadro_trial import analyze_system


def fixture():
    services = ["root-a", "root-b", "root-c"]
    types = ["cpu", "delay", "loss"]
    faults = {}
    windows = []
    indices, labels, events, episodes, folds, partitions = [], [], [], [], [], []
    row = 0
    for ti, fault_type in enumerate(types):
        for ri, service in enumerate(services):
            event = "%s-%s" % (service, fault_type)
            run = "recording-%d" % (ri % 2)
            root = ri
            faults[event] = {
                "event_id": event, "service": service, "fault_type": fault_type,
                "run_id": run, "root": root,
            }
            # Each incident gets its fault window and an assigned normal window.
            for label, event_id in ((root, event), (-1, "")):
                indices.append(row)
                labels.append(label)
                events.append(event_id)
                episodes.append(event)
                folds.append(ti)
                partitions.append("train" if ti else "validation")
                windows.append({"run_id": run, "event_id": event_id, "start": row, "end": row + 1})
                row += 1
    manifest = {"services": services, "faults": faults, "windows": windows}
    arrays = {
        "indices": np.asarray(indices), "labels": np.asarray(labels),
        "event_ids": np.asarray(events), "episode_ids": np.asarray(episodes),
        "fold_ids": np.asarray(folds), "partition": np.asarray(partitions),
    }
    return manifest, arrays


class EadroTrialTests(unittest.TestCase):
    def test_normal_windows_follow_episode_during_type_holdout(self):
        manifest, arrays = fixture()
        result = analyze_system("SYN", manifest, arrays)
        split = result["policies"]["fault_type_cpu"]
        self.assertEqual(split["heldout"]["normal_windows"], 3)
        self.assertEqual(split["heldout"]["normal_windows_by_assigned_fault_type"], {"cpu": 3})
        self.assertEqual(split["train"]["normal_windows_by_assigned_fault_type"], {"delay": 3, "loss": 3})

    def test_recording_holdout_removes_roots_not_candidates(self):
        manifest, arrays = fixture()
        result = analyze_system("SYN", manifest, arrays)
        split = result["policies"]["recording_recording-0"]
        self.assertEqual(split["removed_root_targets"], ["root-a", "root-c"])
        self.assertEqual(split["candidate_inventory"], ["root-a", "root-b", "root-c"])
        self.assertTrue(split["candidate_inventory_unchanged"])
        self.assertEqual(split["checks"]["recording_overlap"], [])

    def test_event_policy_shares_roots_and_recordings_without_incident_overlap(self):
        manifest, arrays = fixture()
        result = analyze_system("SYN", manifest, arrays)
        split = result["policies"]["event_fold_0"]
        self.assertEqual(split["checks"]["incident_overlap"], [])
        self.assertTrue(split["checks"]["all_candidate_roots_known"])
        self.assertEqual(len(split["checks"]["recording_overlap"]), 2)

    def test_missing_normal_support_is_explicit(self):
        manifest, arrays = fixture()
        keep = np.asarray([
            label >= 0 or episode not in {"root-a-cpu", "root-b-cpu", "root-c-cpu"}
            for label, episode in zip(arrays["labels"], arrays["episode_ids"])
        ])
        for key in arrays:
            arrays[key] = arrays[key][keep]
        manifest["windows"] = [
            window for window, selected in zip(manifest["windows"], keep) if selected
        ]
        result = analyze_system("SYN", manifest, arrays)
        split = result["policies"]["fault_type_cpu"]
        self.assertEqual(split["heldout"]["normal_windows"], 0)
        self.assertEqual(split["heldout"]["missing_normal_fault_types"], ["cpu", "delay", "loss"])
        self.assertEqual(split["train"]["missing_normal_fault_types"], ["cpu"])

    def test_rejects_unassigned_episode(self):
        manifest, arrays = fixture()
        arrays["episode_ids"][0] = "unknown"
        with self.assertRaisesRegex(ValueError, "unknown fault"):
            analyze_system("SYN", manifest, arrays)


if __name__ == "__main__":
    unittest.main()
