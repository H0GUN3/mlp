import unittest

import numpy as np

from research.relationship_diagnosis_20261014.recordings import MODES, audit


def fixture(shared_root=False, normal_count=2):
    services = ["root-a", "root-b", "root-c"] if shared_root else [
        "root-%d" % i for i in range(9)
    ]
    run_ids = ["rec-a", "rec-b"] if shared_root else ["rec-a", "rec-b", "rec-c"]
    faults = {}
    for i, run in enumerate(run_ids):
        roots = services if shared_root else services[i * 3:i * 3 + 3]
        for root_i, root in enumerate(roots):
            for j, kind in enumerate(("cpu", "disk", "memory")):
                event = "%s-%s-%d" % (run, kind, root_i)
                faults[event] = {
                    "event_id": event, "run_id": run, "service": root,
                    "root": services.index(root), "fault_type": kind,
                    "start": 20 + j * 20, "end_inclusive": 25 + j * 20,
                }
    windows, indices, labels, event_ids, episode_ids, fold_ids = [], [], [], [], [], []
    index = 0
    for run in run_ids:
        for n in range(normal_count):
            windows.append({"index": index, "run_id": run, "event_id": ""})
            indices.append(index); labels.append(-1); event_ids.append(""); episode_ids.append(next(
                e for e, f in faults.items() if f["run_id"] == run
            )); fold_ids.append(0); index += 1
        for event, fault in faults.items():
            if fault["run_id"] == run:
                windows.append({"index": index, "run_id": run, "event_id": event})
                indices.append(index); labels.append(fault["root"]); event_ids.append(event)
                episode_ids.append(event); fold_ids.append(0); index += 1
    performance = {
        event: {
            mode: {"top1": .2 + (mode == "directed") * .2,
                   "top3": .5, "mrr": .4}
            for mode in MODES
        } for event in faults
    }
    arrays = {
        "indices": np.asarray(indices), "labels": np.asarray(labels),
        "event_ids": np.asarray(event_ids), "episode_ids": np.asarray(episode_ids),
        "fold_ids": np.asarray(fold_ids),
    }
    manifest = {"services": services, "windows": windows, "native_window_count": index}
    reports = []
    return faults, manifest, arrays, performance, reports


class RecordingAuditTests(unittest.TestCase):
    def test_unique_roots_have_cold_root_on_every_holdout(self):
        faults, manifest, arrays, scores, reports = fixture()
        result = audit(reports, {"SN": faults, "TT": faults},
                       {"SN": manifest, "TT": manifest},
                       {"SN": arrays, "TT": arrays},
                       {"SN": scores, "TT": scores})["systems"]["SN"]
        for holdout in result["leave_one_recording_out"].values():
            self.assertEqual(len(holdout["cold_root_services_absent_from_train_targets"]), 3)
            self.assertIn("all three fault types", holdout["cold_root_condition"].lower())
            self.assertEqual(holdout["services_absent_from_candidate_inventory"], [])

    def test_shared_root_across_recordings_remains_train_target(self):
        faults, manifest, arrays, scores, reports = fixture(shared_root=True)
        result = audit(reports, {"SN": faults, "TT": faults},
                       {"SN": manifest, "TT": manifest},
                       {"SN": arrays, "TT": arrays},
                       {"SN": scores, "TT": scores})["systems"]["SN"]
        self.assertEqual(result["leave_one_recording_out"]["rec-a"]["cold_root_services_absent_from_train_targets"], [])

    def test_normal_support_and_row_partition_are_reported(self):
        faults, manifest, arrays, scores, reports = fixture(normal_count=4)
        result = audit(reports, {"SN": faults, "TT": faults},
                       {"SN": manifest, "TT": manifest},
                       {"SN": arrays, "TT": arrays},
                       {"SN": scores, "TT": scores})["systems"]["SN"]
        holdout = result["leave_one_recording_out"]["rec-a"]
        self.assertEqual(holdout["heldout"]["normal_window_count"], 4)
        self.assertEqual(holdout["train"]["normal_window_count"], 8)
        self.assertTrue(holdout["original_row_indices"]["disjoint"])
        self.assertFalse(set(holdout["original_row_indices"]["train"]) &
                         set(holdout["original_row_indices"]["heldout"]))

    def test_unsupported_window_metadata_is_refused(self):
        faults, manifest, arrays, scores, reports = fixture()
        manifest["windows"][0]["run_id"] = "unsupported-recording"
        with self.assertRaisesRegex(ValueError, "recording"):
            audit(reports, {"SN": faults, "TT": faults},
                  {"SN": manifest, "TT": manifest},
                  {"SN": arrays, "TT": arrays},
                  {"SN": scores, "TT": scores})

    def test_event_equal_aggregation_and_directed_global_delta(self):
        faults, manifest, arrays, scores, reports = fixture()
        first = next(iter(faults))
        scores[first]["directed"]["top1"] = 1
        result = audit(reports, {"SN": faults, "TT": faults},
                       {"SN": manifest, "TT": manifest},
                       {"SN": arrays, "TT": arrays},
                       {"SN": scores, "TT": scores})["systems"]["SN"]
        rec = faults[first]["run_id"]
        rows = result["recordings"][rec]["metrics_event_equal"]
        self.assertAlmostEqual(rows["directed"]["top1"], (1 + 8 * .4) / 9)
        self.assertAlmostEqual(rows["directed_minus_global"]["top1"], (1 + 8 * .4) / 9 - .2)
        self.assertEqual(result["recordings"][rec]["incident_count"], 9)


if __name__ == "__main__":
    unittest.main()
