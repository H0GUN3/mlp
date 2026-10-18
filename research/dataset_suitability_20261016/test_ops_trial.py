import unittest
import hashlib

from research.dataset_suitability_20261016.ops_trial import (
    canonical,
    canonical_time,
    metadata_signature,
    nonempty_hash_paths,
    sample_bias,
)


class OpsTrialTests(unittest.TestCase):
    def test_empty_byte_hash_is_not_a_duplicate(self):
        rows = [
            {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 1, "path": "a"},
            {"sha256": "same", "bytes": 10, "path": "b"},
            {"sha256": "same", "bytes": 10, "path": "c"},
        ]
        self.assertEqual(nonempty_hash_paths(rows), {"same": ["b", "c"]})

    def test_matching_hash_keeps_distinct_file_names(self):
        result = nonempty_hash_paths([
            {"sha256": "h", "bytes": 3, "path": "case-a/traces.parquet"},
            {"sha256": "h", "bytes": 3, "path": "case-b/metrics.parquet"},
        ])
        self.assertEqual(result["h"], ["case-a/traces.parquet", "case-b/metrics.parquet"])

    def test_canonical_name_normalization_collision_is_explicit(self):
        self.assertEqual(canonical("A_B"), canonical("a-b"))

    def test_time_normalization_converts_offsets_to_utc(self):
        self.assertEqual(canonical_time("2026-01-01T08:00:00+08:00"), "2026-01-01T00:00:00+00:00")

    def test_metadata_signature_sorts_sets_without_schema_mapping(self):
        self.assertEqual(
            metadata_signature("TS", ["PodFailure", "NetworkDelay"], ["b", "a"]),
            metadata_signature("ts", ["networkdelay", "podfailure"], ["a", "b"]),
        )

    def test_multi_item_faults_can_share_one_required_service(self):
        rows = [{
            "name": "multi",
            "system": "ts",
            "required_roots": ["orders"],
            "roles": ["required", "required", "optional"],
            "fault_types": ["Delay", "Loss"],
            "required_fault_count": 2,
            "n_service_edges": 2,
            "metadata_signature": "sig",
        }]
        stats = sample_bias(rows, {"multi"})["whole"]
        self.assertEqual(stats["required_root_occurrences"], 1)
        self.assertEqual(stats["role_item_counts"], {"optional": 1, "required": 2})

    def test_metadata_census_and_telemetry_sample_are_separate(self):
        rows = [
            {"name": "a", "system": "ts", "required_roots": ["x"], "roles": ["required"],
             "fault_types": ["Delay"], "required_fault_count": 1, "n_service_edges": 1, "metadata_signature": "s1"},
            {"name": "b", "system": "hs", "required_roots": ["y"], "roles": ["required"],
             "fault_types": ["PodFailure"], "required_fault_count": 1, "n_service_edges": 1, "metadata_signature": "s2"},
        ]
        result = sample_bias(rows, {"a"})
        self.assertEqual(result["whole"]["cases"], 2)
        self.assertEqual(result["selected"]["cases"], 1)
        # Selection membership does not itself assert telemetry availability.
        self.assertNotIn("telemetry_quality", result["whole"])


if __name__ == "__main__":
    unittest.main()
