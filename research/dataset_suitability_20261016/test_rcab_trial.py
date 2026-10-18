"""Package-qualified imports also work under repository-root unittest discovery."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import io
import itertools
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import pyarrow as pa

from research.dataset_suitability_20261016.rcab_trial import (
    CORE, CRITERIA, METRICS, PILOT_SALT, ROOT, HashingReader, aggregate_table,
    candidate_inventory, empty_counts, exclusive_json, fold, score_counts,
    select_pilot, split_stress, split_support, tie_metrics,
)


def records(values: dict[str, float | None]) -> dict:
    return {s: {"score": v, "supported": v is not None, "missing": v is None}
            for s, v in values.items()}


def permutation_oracle(values: dict[str, float | None], accepted: list[str]) -> dict:
    tiers = defaultdict(list)
    for s, v in values.items():
        tiers[v].append(s)
    keys = sorted(tiers, key=lambda v: (v is not None, v if v is not None else 0),
                  reverse=True)
    outputs = []
    for product in itertools.product(*(itertools.permutations(tiers[k]) for k in keys)):
        ordered = list(itertools.chain.from_iterable(product))
        ranks = [i + 1 for i, s in enumerate(ordered) if s in accepted]
        rank = min(ranks) if ranks else None
        outputs.append((float(rank is not None and rank <= 1),
                        float(rank is not None and rank <= 3),
                        1 / rank if rank is not None else 0.0))
    return {m: sum(o[i] for o in outputs) / len(outputs) for i, m in enumerate(METRICS)}


class TieTests(unittest.TestCase):
    def test_exhaustive_permutation_oracle_all_gold_subsets(self):
        # Includes single/multiple accepted in same and different score/missing tiers.
        for vals in itertools.product((None, -1.0, 0.0, 1.0), repeat=4):
            values = dict(zip("abcd", vals))
            for mask in range(1, 16):
                gold = [s for i, s in enumerate("abcd") if mask & (1 << i)]
                expected = permutation_oracle(values, gold)
                actual = tie_metrics(records(values), gold)
                for m in METRICS:
                    self.assertAlmostEqual(actual[m], expected[m], places=12,
                                           msg=f"{values}, {gold}, {m}")

    def test_supported_negative_before_missing(self):
        scores = records({"a": -100.0, "b": None})
        self.assertEqual(tie_metrics(scores, ["a"])["top1"], 1)
        self.assertEqual(tie_metrics(scores, ["b"])[METRICS[2]], .5)

    def test_all_missing_is_all_tied(self):
        actual = tie_metrics(records(dict.fromkeys("abcd", None)), ["a", "b"])
        self.assertEqual(actual["top1"], .5)
        self.assertEqual(actual["top3"], 1)
        self.assertAlmostEqual(actual[METRICS[2]], permutation_oracle(
            dict.fromkeys("abcd", None), ["a", "b"])[METRICS[2]])

    def test_missing_gold_not_added_or_rescued(self):
        scores = records({"a": 1.0, "b": 0.0})
        actual = tie_metrics(scores, ["not-observed"])
        self.assertTrue(actual["no_gold_candidate"])
        self.assertEqual(actual["missing_gold_candidates"], ["not-observed"])
        self.assertTrue(all(actual[m] == 0 for m in METRICS))
        self.assertEqual(set(scores), {"a", "b"})
        partial = tie_metrics(scores, ["a", "not-observed"])
        self.assertEqual(partial["top1"], 1)
        self.assertEqual(partial["missing_gold_candidates"], ["not-observed"])

    def test_nonfinite_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            tie_metrics(records({"a": float("inf")}), ["a"])

    def test_label_and_name_permutation_invariance(self):
        counts = {
            "a": {"normal": dict(span_rows=2, http_known=2, http_error=1, span_error=0),
                  "abnormal": dict(span_rows=4, http_known=2, http_error=2, span_error=1)},
            "b": {"normal": empty_counts(), "abnormal": empty_counts()},
        }
        before = score_counts(counts)
        renamed = score_counts({{"a": "q", "b": "z"}[s]: v for s, v in counts.items()})
        self.assertEqual(set(before), set(CRITERIA))
        for criterion in CRITERIA:
            self.assertEqual(before[criterion]["a"], renamed[criterion]["q"])
            self.assertEqual(before[criterion]["b"], renamed[criterion]["z"])
            self.assertEqual(tie_metrics(before[criterion], ["a", "b"]),
                             tie_metrics(before[criterion], ["b", "a"]))
            actual = tie_metrics(renamed[criterion], ["q"])
            expected = tie_metrics(before[criterion], ["a"])
            for m in METRICS:
                self.assertEqual(actual[m], expected[m])
        tie_metrics(before["uniform"], ["arbitrary-other-label"])
        self.assertEqual(before, score_counts(counts))


class CountTests(unittest.TestCase):
    def test_missing_denominators_not_zero_or_dropped(self):
        counts = {
            "missing": {"normal": empty_counts(), "abnormal": empty_counts()},
            "no_normal": {"normal": empty_counts(),
                          "abnormal": dict(span_rows=3, http_known=2, http_error=1, span_error=1)},
        }
        scores = score_counts(counts)
        self.assertEqual(scores["uniform"]["missing"]["score"], 0)
        self.assertEqual(scores["abnormal_http_error_fraction"]["no_normal"]["score"], .5)
        self.assertEqual(scores["abnormal_span_error_fraction"]["no_normal"]["score"], 1/3)
        self.assertIsNone(scores["http_error_fraction_increase"]["no_normal"]["score"])
        for criterion in CRITERIA[1:]:
            self.assertEqual(set(scores[criterion]), set(counts))
            self.assertTrue(scores[criterion]["missing"]["missing"])

    def test_candidate_construction_independent_of_targets(self):
        files = {name: {"services": ["", "a", "loadgenerator", "ts-loadgenerator"],
                        "targets": [{"service_name": "gold-not-observed"}]}
                 for name in CORE}
        files["normal_traces.parquet"]["services"].append("trace-only")
        before = candidate_inventory(files)
        for v in files.values():
            v["targets"] = [{"service_name": "different-gold"}]
        self.assertEqual(before, candidate_inventory(files))
        self.assertEqual(before, ["a", "loadgenerator", "trace-only", "ts-loadgenerator"])
        self.assertNotIn("gold-not-observed", before)

    def test_halfopen_and_status_ranges_and_as_published_rows(self):
        ticks = [9, 10, 11, 11, 12, 13, None, 10, 10, 10, 10, 10]
        table = pa.table({
            "service_name": ["a"] * 9 + ["", "a", "a"],
            "time": pa.array([t * 10**9 if t is not None else None for t in ticks],
                             type=pa.timestamp("ns", tz="UTC")),
            "attr.http.response.status_code": pa.array(
                [500, 99, 400, 599, 200, 500, 500, 100, 600, 500, None, 399],
                type=pa.uint16()),
            "attr.status_code": ["Error", "Unset", "Error", "Error", "Ok", "Error",
                                 "Error", "Unset", "Ok", "Error", "Unset", "Ok"],
        })
        normal = aggregate_table(table, 10, 12)
        self.assertEqual(normal["counts"]["a"],
                         dict(span_rows=7, http_known=4, http_error=2, span_error=2))
        self.assertEqual(normal["audit"]["excluded_end_boundary_rows"], 1)
        self.assertEqual(normal["audit"]["excluded_outside_nonboundary_rows"], 2)
        self.assertEqual(normal["audit"]["excluded_null_time_rows"], 1)
        self.assertEqual(normal["audit"]["included_empty_service_rows"], 1)
        abnormal = aggregate_table(table, 12, 14)
        self.assertEqual(abnormal["audit"]["rows_at_start_included"], 1)
        self.assertEqual(abnormal["counts"]["a"]["span_rows"], 2)


class SelectionAndSafetyTests(unittest.TestCase):
    @staticmethod
    def fixture() -> list[dict]:
        rows = []
        for typ in ("HTTPA", "HTTPB"):
            for i in range(10):
                for j in range(2):
                    rows.append({"case": f"{typ}-{i}-{j}", "fault_type": typ,
                                 "semantic_configuration_sha256": f"{typ}-g{i}"})
        return rows

    def test_selection_determinism_whole_groups_prior_and_disjointness(self):
        rows = self.fixture()
        prior = ["HTTPA-9-1", "not-http"]
        actual = select_pilot(rows, prior)
        self.assertEqual(actual, select_pilot(rows[::-1], prior[::-1]))
        self.assertTrue({"HTTPA-9-0", "HTTPA-9-1"} <= set(actual["selected_cases"]))
        self.assertFalse(set(actual["selected_cases"]) &
                         set(actual["metadata_only_http_cases"]))
        self.assertEqual(len(actual["selected_cases"]) + len(actual["metadata_only_http_cases"]),
                         len(rows))
        self.assertFalse(set(actual["selected_groups"]) &
                         set(actual["metadata_only_http_groups"]))
        for typ, info in actual["types"].items():
            self.assertEqual(info["initial_groups"], 2)
            ordered = sorted({r["semantic_configuration_sha256"] for r in rows
                              if r["fault_type"] == typ},
                             key=lambda g: hashlib.sha256((PILOT_SALT + g).encode()).hexdigest())
            initial = [r["group"] for r in info["group_records"]
                       if "first_ceil_20pct_hash_groups" in r["reasons"]]
            self.assertEqual(initial, ordered[:2])

    def test_fold_exact_hash_and_training_support(self):
        self.assertEqual(fold("sample"), int(hashlib.sha256(
            b"suitability-20261016:sample").hexdigest(), 16) % 3)
        rows = [
            dict(case="a", roots=["x", "y"], configuration_anchor="x", fault_type="A"),
            dict(case="b", roots=["x", "y"], configuration_anchor="x", fault_type="B"),
            dict(case="c", roots=["z"], configuration_anchor="z", fault_type="A"),
        ]
        assignments = dict(a=0, b=1, c=1)
        support = split_support(rows, assignments, True)
        self.assertEqual(support["0"]["heldout_case_support"]["a"]["training_root_counts"],
                         dict(x=1, y=1))
        self.assertEqual(support["0"]["heldout_case_support"]["a"]["training_type_count"], 1)
        self.assertEqual(support["1"]["heldout_case_support"]["c"]["training_root_counts"],
                         dict(z=0))
        self.assertEqual(support["2"]["training_cases"], 3)
        self.assertEqual(support["2"]["heldout_cases"], 0)

    def test_whole_metadata_selection_and_group_split_reconciliation(self):
        with (ROOT / "research/research_reset_review_20261016/metadata_analysis.json").open() as f:
            rows = json.load(f)["case_rows"]
        with (ROOT / "research/diagnostic_observability_20261016/rcab_sample_manifest.json").open() as f:
            prior = json.load(f)["deep_sample_cases"]
        selected = select_pilot(rows, prior)
        self.assertEqual(len(selected["selected_cases"]), 173)
        self.assertEqual(len(selected["metadata_only_http_cases"]), 623)
        self.assertTrue({
            "ts2-ts-basic-service-request-replace-method-v6gzn8",
            "ts3-ts-basic-service-response-replace-code-ws6vpb",
        } <= set(selected["selected_cases"]))
        stress = split_stress(rows)
        self.assertEqual(stress["nonnetwork_nominal_anchor_candidates"], 1167)
        self.assertEqual(stress["cases_in_repeated_groups"], 159)
        groups = stress["semantic_group_members"]
        group_assign = stress["schemes"]["semantic_group_hash"]["assignments"]
        reverse_assign = {r["case"]: fold(r["semantic_configuration_sha256"])
                          for r in rows[::-1]}
        self.assertEqual(group_assign, reverse_assign)
        self.assertEqual(len(group_assign), 1422)
        for group, cases in groups.items():
            self.assertEqual({group_assign[c] for c in cases}, {fold(group)})
        partitions = [{c for c, f in group_assign.items() if f == heldout} for heldout in range(3)]
        self.assertEqual(sum(map(len, partitions)), 1422)
        for left, right in itertools.combinations(partitions, 2):
            self.assertFalse(left & right)
        self.assertEqual(stress["schemes"]["semantic_group_hash"]["crossfold_group_count"], 0)
        self.assertGreater(stress["schemes"]["case_hash"]["crossfold_group_count"], 0)
        self.assertEqual(len(stress["positive_window_overlaps"]), 760)

    def test_exclusive_write_protection_and_finite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "result.json"
            exclusive_json(p, {"value": None})
            original = p.read_bytes()
            with self.assertRaises(FileExistsError):
                exclusive_json(p, {"value": "overwritten"})
            self.assertEqual(p.read_bytes(), original)
            self.assertIsNone(json.loads(original)["value"])
            q = Path(directory) / "invalid.json"
            with self.assertRaises(ValueError):
                exclusive_json(q, {"value": float("inf")})
            self.assertFalse(q.exists())

    def test_streamed_archive_hash(self):
        payload = b"archive-compressed-byte-test" * 10
        reader = HashingReader(io.BytesIO(payload))
        while reader.read(7):
            pass
        self.assertEqual(reader.bytes, len(payload))
        self.assertEqual(reader.sha.hexdigest(), hashlib.sha256(payload).hexdigest())
        self.assertEqual(reader.md5.hexdigest(), hashlib.md5(payload).hexdigest())

    def test_single_pass_gzip_tar_with_hashing_reader(self):
        compressed = io.BytesIO()
        with tarfile.open(fileobj=compressed, mode="w:gz") as archive:
            member = tarfile.TarInfo("prefix/case/normal_traces.parquet")
            member.size = 5
            archive.addfile(member, io.BytesIO(b"trace"))
        payload = compressed.getvalue()
        reader = HashingReader(io.BytesIO(payload))
        with tarfile.open(fileobj=reader, mode="r|gz") as archive:
            for member in archive:
                source = archive.extractfile(member)
                self.assertIsNotNone(source)
                if source is None:
                    self.fail("missing synthetic member")
                self.assertEqual(source.read(), b"trace")
        while reader.read(13):
            pass
        self.assertEqual(reader.bytes, len(payload))
        self.assertEqual(reader.sha.hexdigest(), hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
