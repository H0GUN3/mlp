"""Synthetic incident and trace tests; no protected or real telemetry is opened."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.relationship_smoke_20261013.data import (
    adjacency_from_records, base_features, event_partition, read_adjacency, validate_bundle,
)


def synthetic_metadata():
    count = 60
    parts = base_features.original_split(count)
    indices = np.concatenate((parts["train"], parts["validation"]))
    chosen = sorted(indices.tolist())[:9]
    windows = [{"start": i * 10, "end": i * 10 + 9, "run_id": "run", "event_id": ""}
               for i in range(count)]
    all_labels = np.full(count, -1, dtype=np.int64)
    faults = []
    for i, index in enumerate(chosen):
        event = "run:fault" + str(i)
        root, kind = divmod(i, 3)
        faults.append({
            "event_id": event, "service": "svc" + str(root), "root": root,
            "fault_type": ("cpu", "delay", "loss")[kind],
            "start": index * 10 + 1, "end_inclusive": index * 10 + 8,
        })
        windows[index]["event_id"] = event
        all_labels[index] = root
    return {
        "window_count": count, "services": ["svc0", "svc1", "svc2"],
        "windows": windows, "runs": [{"run_id": "run", "faults": faults}],
    }, indices, all_labels[indices]


def synthetic_bundle():
    meta, indices, labels = synthetic_metadata()
    split = event_partition(meta, indices, labels)
    values = np.arange(len(indices) * 3 * 10 * 9, dtype=np.float64).reshape(len(indices), 3, 10, 9)
    observed = np.ones(values.shape, dtype=np.bool_)
    reference = base_features.fit_reference(values, observed, labels, split["partition"])
    x, mask, coverage = base_features.window_features(values, observed, reference)
    arrays = {
        "values": values, "observed": observed, "x": x, "mask": mask, "coverage": coverage,
        "indices": indices, "labels": labels, "event_ids": split["event_ids"],
        "episode_ids": split["episode_ids"], "partition": split["partition"],
        "fold_ids": split["fold_ids"], "adjacency": np.zeros((len(indices), 3, 3), dtype=np.bool_),
    }
    manifest = {"services": meta["services"], "native_window_count": meta["window_count"],
                "normal_reference": {key: value.tolist() for key, value in reference.items()}}
    return arrays, manifest


class DataTest(unittest.TestCase):
    def test_event_disjoint_balanced_and_few_shot_complements(self):
        meta, indices, labels = synthetic_metadata()
        validation_union = set()
        for fold in range(3):
            split = event_partition(meta, indices, labels, fold)
            train = set(split["event_ids"][(labels >= 0) & (split["partition"] == "train")])
            val = set(split["event_ids"][(labels >= 0) & (split["partition"] == "validation")])
            self.assertEqual((len(train), len(val)), (6, 3))
            self.assertFalse(train & val)
            self.assertFalse(validation_union & val)
            validation_union |= val
            a, b = (set(split["few_shot"][key]["event_ids"]) for key in ("A", "B"))
            self.assertFalse(a & b)
            self.assertEqual(a | b, train)
            for row, label in enumerate(labels):
                if label == -1:
                    window = split["windows"][row]
                    expected = min(meta["runs"][0]["faults"], key=lambda f: (
                        max(f["start"] - window["end"], window["start"] - f["end_inclusive"], 0),
                        f["start"], f["event_id"]))
                    self.assertEqual(split["episode_ids"][row], expected["event_id"])
        self.assertEqual(len(validation_union), 9)

    def test_protected_index_and_missing_incident_rejected(self):
        meta, indices, labels = synthetic_metadata()
        protected = base_features.original_split(meta["window_count"])["test"][0]
        with self.assertRaisesRegex(ValueError, "protected"):
            event_partition(meta, np.append(indices, protected), np.append(labels, -1))
        with self.assertRaisesRegex(ValueError, "no permitted"):
            event_partition(meta, indices[labels != 0], labels[labels != 0])

    def test_reference_is_train_only_and_saved_features_reconstruct(self):
        arrays, manifest = synthetic_bundle()
        validate_bundle(arrays, manifest)
        training = arrays["partition"] == "train"
        original = base_features.fit_reference(
            arrays["values"], arrays["observed"], arrays["labels"], arrays["partition"])
        changed = arrays["values"].copy()
        changed[~training] *= 100
        new = base_features.fit_reference(changed, arrays["observed"], arrays["labels"], arrays["partition"])
        for key in original:
            np.testing.assert_array_equal(original[key], new[key])
        arrays["episode_ids"][np.flatnonzero(~training)[0]] = arrays["episode_ids"][np.flatnonzero(training)[0]]
        with self.assertRaisesRegex(ValueError, "Episode leakage"):
            validate_bundle(arrays, manifest)

    def test_graph_direction_and_boundary_exclusions(self):
        records = {
            ("t", "p"): (0, 0, 100, 10, ()),
            ("t", "c"): (0, 1, 105, 3, (("CHILD_OF", "t", "p"),)),
            ("t", "later"): (1, 2, 120, 2, (("CHILD_OF", "t", "p"),)),
            ("t", "absent"): (0, 2, 107, 1, (("CHILD_OF", "t", "missing"),)),
            ("t", "async"): (0, 2, 108, 1, (("FOLLOWS_FROM", "t", "p"),)),
            ("t", "foreign"): (0, 2, 109, 1, (("CHILD_OF", "foreign", "p"),)),
        }
        graph, audit = adjacency_from_records(records, 2, 3)
        self.assertTrue(graph[0, 0, 1])
        self.assertEqual(int(graph.sum()), 1)
        self.assertEqual(audit["cross_window_parents_ignored"], 1)
        self.assertEqual(audit["parent_unresolved_or_unselected"], 1)
        self.assertEqual(audit["cross_trace_references_ignored"], 1)

    def test_stream_deduplicates_and_never_uses_outside_windows(self):
        parent = {"traceID": "t", "spanID": "p", "processID": "p0",
                  "startTime": 1000000, "duration": 5000000, "references": []}
        child = {"traceID": "t", "spanID": "c", "processID": "p1",
                 "startTime": 2000000, "duration": 1000000,
                 "references": [{"refType": "CHILD_OF", "traceID": "t", "spanID": "p"}]}
        trace = {"traceID": "t", "processes": {"p0": {"serviceName": "a"}, "p1": {"serviceName": "b"}},
                 "spans": [parent, child, dict(child)]}
        run = {"record_start": 28800, "record_end_exclusive": 28820}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spans.json"
            payload = json.dumps([trace]).encode()
            path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            graph, audit = read_adjacency(path, ["a", "b"], run, [28800], digest)
            self.assertEqual((int(graph.sum()), audit["duplicate_occurrences"]), (1, 1))
            graph, audit = read_adjacency(path, ["a", "b"], run, [28810], digest)
            self.assertFalse(graph.any())
            self.assertEqual(audit["distinct_selected_spans"], 0)
            trace["spans"][-1]["duration"] += 1
            payload = json.dumps([trace]).encode()
            path.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                read_adjacency(path, ["a", "b"], run, [28800], hashlib.sha256(payload).hexdigest())

    def test_graph_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spans.json"
            path.write_text("[]")
            with self.assertRaisesRegex(ValueError, "source changed"):
                read_adjacency(path, ["a"], {"record_start": 28800, "record_end_exclusive": 28810},
                               [28800], "not-the-source-hash")


if __name__ == "__main__":
    unittest.main()
