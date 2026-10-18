"""Synthetic fixtures only: no source dataset, inference, or fitting."""
import copy
import io
import hashlib
from pathlib import Path
import tempfile
import unittest

import numpy as np

from . import prepare as p


SERVICES = ["compose-post-service", "media-service", "text-service"]


def span(identity, owner, operation, second=0, duration=1000000, refs=(), trace="t"):
    return {"traceID": trace, "spanID": identity, "processID": owner,
            "operationName": operation, "startTime": second * 1000000 + 999999,
            "duration": duration, "references": list(refs)}


def ref(identity, trace="t", kind="CHILD_OF"):
    return {"traceID": trace, "spanID": identity, "refType": kind}


def trace(spans):
    return {"traceID": "t", "spans": spans,
            "processes": {service: {"serviceName": service} for service in SERVICES}}


def selected(spans, routes=None):
    if routes is None:
        routes = {("run", 28800): (0, 0), ("run", 28801): (1, 0)}
    return list(p.selected_spans(trace(spans), "run", routes, SERVICES))


def linked(spans):
    identities = p.Identities()
    for record in selected(spans):
        identities.observe(record, "TRAIN")
    return p.linked_evidence(identities.records, SERVICES, [100, 101])


def media_pair(second=0):
    return [span("p", SERVICES[0], "compose_media_client", second),
            span("c", SERVICES[1], "compose_media_server", second, refs=[ref("p")])]


class PreparationFixtures(unittest.TestCase):
    def test_exact_reference_join_not_name_adjacency_or_follows(self):
        spans = media_pair()
        spans.extend([
            span("wrong-trace", SERVICES[2], "server", refs=[ref("p", trace="other")]),
            span("wrong-id", SERVICES[2], "server", refs=[ref("absent")]),
            span("follows", SERVICES[2], "server", refs=[ref("p", kind="FOLLOWS_FROM")])])
        mapping, evidence, audit = linked(spans + copy.deepcopy(spans[:2]))
        self.assertEqual(mapping, {p.MEDIA: SERVICES[1]})
        self.assertEqual(len(evidence[p.MEDIA]), 1)
        self.assertEqual(audit["unmatched_selected_parent_references"], 2)
        self.assertEqual(audit["ambiguous_keys"], 0)

    def test_train_only_guard_before_observation_interpretation(self):
        class TimestampOnly(dict):
            def __getitem__(self, key):
                if key != "startTime":
                    raise AssertionError("Read nonTRAIN observation: " + key)
                return super().__getitem__(key)

        routes = {("run", 28800): (0, 0)}
        guarded = trace(media_pair() + [TimestampOnly(startTime=1000000)])
        records = list(p.selected_spans(guarded, "run", routes, SERVICES))
        self.assertEqual(len(records), 2)
        # Validation child may not complete a TRAIN parent reference.
        parent, child = media_pair()
        child["startTime"] = 1000000
        identities = p.Identities()
        for record in selected([parent, child], routes):
            identities.observe(record, "TRAIN")
        mapping, _, _ = p.linked_evidence(identities.records, SERVICES, [100])
        self.assertEqual(mapping, {})
        # Conversely a validation parent cannot complete a TRAIN child.
        parent["startTime"], child["startTime"] = 1000000, 0
        identities = p.Identities()
        for record in selected([parent, child], routes):
            identities.observe(record, "TRAIN")
        mapping, _, audit = p.linked_evidence(identities.records, SERVICES, [100])
        self.assertEqual(mapping, {})
        self.assertEqual(audit["unmatched_selected_parent_references"], 1)

    def test_ambiguous_key_fails_not_majority(self):
        spans = media_pair() + [span("c2", SERVICES[2], "server", refs=[ref("p")])]
        with self.assertRaisesRegex(ValueError, "Multiple target"):
            linked(spans + copy.deepcopy(spans[:2]) * 3)

    def test_conflicting_identity_duration_operation_or_reference_fails(self):
        for field, changed in (("duration", 2000000), ("operationName", "other_client"),
                               ("references", [ref("different")])):
            first = media_pair()[0]
            second = copy.deepcopy(first)
            second[field] = changed
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "Conflicting selected identity"):
                    linked([first, second])

    def test_unknown_and_nonclient_fallback_owner(self):
        mapping = {p.MEDIA: SERVICES[1], (SERVICES[0], "internal"): SERVICES[1]}
        self.assertEqual(p.destination(*p.MEDIA, mapping), SERVICES[1])
        self.assertEqual(p.destination(SERVICES[0], "unknown_client", mapping), SERVICES[0])
        self.assertEqual(p.destination(SERVICES[0], "internal", mapping), SERVICES[0])
        self.assertEqual(p.destination(SERVICES[2], p.MEDIA[1], mapping), SERVICES[2])

    def test_duplicate_weight_mean_original_timing_zero_channel(self):
        mapping = {p.MEDIA: SERVICES[1]}
        first = span("p", SERVICES[0], "compose_media_client", duration=1000000)
        spans = [first, copy.deepcopy(first),
                 span("long", SERVICES[0], "compose_media_client", duration=4000000),
                 span("server", SERVICES[1], "server", duration=2000000),
                 span("unknown", SERVICES[0], "unknown_client", second=1, duration=9000000)]
        aggregate = p.Aggregates(2, SERVICES, mapping, [0])
        for record in selected(spans):
            aggregate.add(record)
        owner, candidate = aggregate.finish()
        self.assertEqual(owner[0, 0, 0, 0], 2.0)
        self.assertEqual(candidate[0, 1, 0, 0], 2.0)
        self.assertEqual(candidate[1, 0, 0, 0], 9.0)
        self.assertEqual(candidate[0, 0, 0, 0], 0.0)
        self.assertEqual(int(aggregate.target_counts.sum()), 5)
        self.assertEqual(aggregate.report()["TRAIN"]["duplicate_identity_occurrences"], 1)
        self.assertEqual(aggregate.report()["TRAIN"]["mapped_client_occurrences"], 3)
        self.assertEqual(aggregate.report()["validation"]["unmapped_client_occurrences"], 1)
        self.assertFalse(np.any(candidate[..., 1]))
        self.assertFalse(np.any(candidate[:, :, 1:, :]))

    def test_unchanged_other_arrays_and_exact_baseline_gate(self):
        owner = np.zeros((2, 3, 10, 2), dtype=np.float64)
        safe = {"traces": owner,
                **{key: np.arange(2, dtype=np.int64) for key in p.ARRAYS - {"traces"}}}
        output = {key: value.copy() for key, value in safe.items()}
        self.assertTrue(all(p.exact_arrays(safe, output, owner).values()))
        for key in ("metrics", "logs", "labels", "indices"):
            changed = {name: value.copy() for name, value in output.items()}
            changed[key][0] += 1
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, key + " changed"):
                    p.exact_arrays(safe, changed, owner)
        changed_owner = owner.copy()
        changed_owner[0, 0, 0, 0] = np.nextafter(0.0, 1.0)
        with self.assertRaisesRegex(ValueError, "elementwise EXACT"):
            p.exact_arrays(safe, output, changed_owner)

    def test_safe_source_extra_absolute_arm_is_not_loaded_or_output(self):
        class SafeArchive:
            files = list(p.ARRAYS) + ["log_absolute"]

            def __getitem__(self, key):
                if key == "log_absolute":
                    raise AssertionError("Unused absolute arm must not be loaded")
                return np.zeros(1)

        self.assertEqual(set(p.safe_selected_arrays(SafeArchive())), p.ARRAYS)
        archive = SafeArchive()
        archive.files = list(p.ARRAYS - {"metrics"}) + ["log_absolute"]
        with self.assertRaisesRegex(ValueError, "Unsafe selected archive members"):
            p.safe_selected_arrays(archive)

    def test_mapping_freeze_exclusive_hash_and_media_support(self):
        mapping, evidence, audit = linked(media_pair())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            with self.assertRaisesRegex(ValueError, "Missing TRAIN-supported"):
                p.freeze_mapping(path, {}, {}, {}, {})
            self.assertFalse(path.exists())
            digest = p.freeze_mapping(path, mapping, evidence, audit, {})
            self.assertEqual(p.load_frozen(path, digest), mapping)
            with self.assertRaises(FileExistsError):
                p.freeze_mapping(path, mapping, evidence, audit, {})
            with self.assertRaisesRegex(ValueError, "Frozen dictionary changed"):
                p.load_frozen(path, "wrong hash")

    def test_existing_streaming_parser_and_window_routing(self):
        parser = p.parser_module()
        digest = hashlib.sha256()
        parsed = list(parser.json_array(io.BytesIO(b'[{"spans": []}]'), digest))
        self.assertEqual(parsed, [{"spans": []}])
        self.assertEqual(digest.hexdigest(), hashlib.sha256(b'[{"spans": []}]').hexdigest())
        meta = {"windows": [{"run_id": "r", "start": 28800, "end": 28809}]}
        routes = p.routes_for(meta, [0])
        self.assertEqual(routes[("r", 28809)], (0, 9))
        self.assertNotIn(("r", 28810), routes)
        self.assertNotIn(("other", 28800), routes)


if __name__ == "__main__":
    unittest.main()
