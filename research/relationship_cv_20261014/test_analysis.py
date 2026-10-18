"""Synthetic report checks only; no telemetry, models, or artifact access."""
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
from random import Random
from statistics import quantiles
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.relationship_cv_20261014 import analysis


def metric_row(value):
    return {"top1": value, "top3": min(1., value + .2), "mrr": (value + 1) / 2}


def fixture(score=None):
    fold_events = {0: ("a", "b", "c", "d"), 1: ("e",), 2: ("f",)}
    faults = {system: {event: {"run_id": "big" if event in ("a", "e", "f") else event}
                       for events in fold_events.values() for event in events}
              for system in analysis.SYSTEMS}
    reports = []
    for system, fold, seed, mode in product(
        analysis.SYSTEMS, analysis.FOLDS, analysis.SEEDS, analysis.MODES
    ):
        rows = {}
        for event in fold_events[fold]:
            value = (score(system, fold, seed, mode, event) if score else
                     {"local": .2, "global": .4, "directed": {11: .1, 23: .7, 37: .7}[seed]}[mode])
            rows[event] = metric_row(value)
        reports.append({
            "system": system, "fold": fold, "seed": seed, "mode": mode, "fit_seconds": 1.5,
            "metrics": {
                "by_incident": rows,
                "event_balanced": {m: sum(row[m] for row in rows.values()) / len(rows)
                                   for m in analysis.METRICS},
                "windows": 10 * len(rows), "incidents": len(rows),
            },
        })
    return reports, faults


def refresh_counts(report):
    rows = report["metrics"]["by_incident"]
    report["metrics"]["incidents"] = len(rows)
    report["metrics"]["windows"] = 10 * len(rows)
    report["metrics"]["event_balanced"] = {
        m: sum(row[m] for row in rows.values()) / len(rows) for m in analysis.METRICS
    }


class AnalysisTest(unittest.TestCase):
    def test_cli_hashes_exclusive_creation_and_no_verification_dependency(self):
        reports, faults = fixture()
        manifest = {"reports": reports, "systems": {s: {"faults": f} for s, f in faults.items()}}
        input_bytes = json.dumps(manifest).encode()
        with TemporaryDirectory() as directory:
            here = Path(directory)
            (here / "results").mkdir()
            (here / "results" / "runs.json").write_bytes(input_bytes)
            with patch.object(analysis, "HERE", here), patch.object(
                analysis, "summarize", return_value={"synthetic": True}
            ) as summarize, patch("builtins.print") as printed:
                analysis.main()
                summarize.assert_called_once_with(reports, faults)
                printed.assert_called_once_with("CV_ANALYSIS_COMPLETE")
                target = here / "results" / "analysis.json"
                saved = target.read_bytes()
                self.assertEqual(json.loads(saved), {
                    "input_hashes": {
                        "runs.json": hashlib.sha256(input_bytes).hexdigest(),
                        "analysis.py": hashlib.sha256(Path(__file__).with_name("analysis.py").read_bytes()).hexdigest(),
                    },
                    "summary": {"synthetic": True},
                })
                self.assertFalse((here / "results" / "verification.json").exists())
                printed.reset_mock()
                with self.assertRaises(FileExistsError):
                    analysis.main()
                self.assertEqual(target.read_bytes(), saved)
                printed.assert_not_called()

    def test_cli_validation_failure_leaves_no_output(self):
        with TemporaryDirectory() as directory:
            here = Path(directory)
            (here / "results").mkdir()
            (here / "results" / "runs.json").write_text('{"reports": [], "systems": {}}')
            with patch.object(analysis, "HERE", here), patch("builtins.print") as printed:
                with self.assertRaises(ValueError):
                    analysis.main()
                self.assertFalse((here / "results" / "analysis.json").exists())
                printed.assert_not_called()

    def test_unequal_recording_sizes_and_multiplicity(self):
        differences = {e: {m: value for m in analysis.METRICS}
                       for e, value in zip("abcde", (1., 1., 1., -1., 0.))}
        recordings = dict(zip("abcde", ("A", "A", "A", "B", "C")))
        with patch.object(analysis, "Random") as random:
            random.return_value.choices.return_value = [0, 0, 1]
            intervals = analysis._cluster_bootstrap(differences, recordings)
        random.assert_called_once_with(20261014)
        self.assertEqual(random.return_value.choices.call_count, 5000)
        for bounds in intervals.values():
            # Two copies of the three-incident recording, plus one negative incident.
            self.assertAlmostEqual(bounds["low"], 5 / 7)
            self.assertAlmostEqual(bounds["high"], 5 / 7)
            self.assertNotAlmostEqual(bounds["low"], 1 / 3)  # Recording-equal is wrong.
            self.assertNotAlmostEqual(bounds["low"], .5)  # Deduplicating draws is wrong.

    def test_deterministic_bootstrap_matches_expanded_incident_oracle(self):
        differences = {e: metric_row(value) for e, value in zip("abcde", (.1, .3, .8, .2, .9))}
        recordings = dict(zip("abcde", ("A", "A", "A", "B", "C")))
        expected = {m: [] for m in analysis.METRICS}
        rng = Random(20261014)
        for _ in range(5000):
            selected = rng.choices(["A", "B", "C"], k=3)
            expanded = [differences[e] for recording in selected
                        for e in differences if recordings[e] == recording]
            for metric in analysis.METRICS:
                expected[metric].append(sum(row[metric] for row in expanded) / len(expanded))
        actual = analysis._cluster_bootstrap(differences, recordings)
        self.assertEqual(actual, analysis._cluster_bootstrap(
            dict(reversed(list(differences.items()))), recordings))
        for metric, samples in expected.items():
            percentiles = quantiles(samples, n=40, method="inclusive")
            self.assertAlmostEqual(actual[metric]["low"], percentiles[0])
            self.assertAlmostEqual(actual[metric]["high"], percentiles[-1])

    def test_missing_duplicate_and_invalid_run_rejected(self):
        reports, faults = fixture()
        cases = [reports[:-1], reports + [reports[0]],
                 [reports[0]] + reports[:-1]]
        for field, value in (("system", "XX"), ("mode", "unknown"), ("fold", 3),
                             ("fold", True), ("seed", 12), ("seed", 11.)):
            changed = deepcopy(reports)
            changed[0][field] = value
            cases.append(changed)
        for case in cases:
            with self.subTest(key=case[0].get("system"), count=len(case)):
                with self.assertRaises(ValueError):
                    analysis.summarize(case, faults)

    def test_event_coverage_and_pairing_rejected(self):
        reports, faults = fixture()
        for mismatch in ("missing", "unknown", "duplicate_fold", "seed_fold_swap", "mode_fold_swap"):
            changed = deepcopy(reports)
            if mismatch in ("missing", "unknown"):
                rows = changed[0]["metrics"]["by_incident"]
                row = rows.pop("a")
                if mismatch == "unknown":
                    rows["unexpected"] = row
                refresh_counts(changed[0])
            elif mismatch == "duplicate_fold":
                report = next(r for r in changed if (r["system"], r["fold"], r["seed"], r["mode"])
                              == ("SN", 1, 11, "local"))
                report["metrics"]["by_incident"]["a"] = metric_row(.2)
                refresh_counts(report)
            else:
                # Preserve one-time total coverage, but change pairing across a fold boundary.
                seed, mode = (23, "local") if mismatch == "seed_fold_swap" else (11, "global")
                first, second = [next(r for r in changed if
                                      (r["system"], r["fold"], r["seed"], r["mode"])
                                      == ("SN", fold, seed, mode)) for fold in (0, 1)]
                first["metrics"]["by_incident"]["e"] = first["metrics"]["by_incident"].pop("a")
                second["metrics"]["by_incident"]["a"] = second["metrics"]["by_incident"].pop("e")
                refresh_counts(first)
                refresh_counts(second)
            with self.subTest(mismatch=mismatch):
                with self.assertRaises(ValueError):
                    analysis.summarize(changed, faults)
        missing_faults = deepcopy(faults)
        missing_faults["SN"]["extra"] = {"run_id": "unseen"}
        with self.assertRaisesRegex(ValueError, "Missing event coverage"):
            analysis.summarize(reports, missing_faults)

    def test_invalid_metrics_times_counts_and_recordings_rejected(self):
        reports, faults = fixture()
        for field, value in (("fit_seconds", float("nan")), ("fit_seconds", -1),
                             ("fit_seconds", True)):
            changed = deepcopy(reports)
            changed[0][field] = value
            with self.assertRaises(ValueError):
                analysis.summarize(changed, faults)
        for field, value in (("incidents", 99), ("windows", 0),
                             ("event_balanced", metric_row(.9)),
                             ("by_incident", {"a": metric_row(float("inf"))})):
            changed = deepcopy(reports)
            changed[0]["metrics"][field] = value
            with self.assertRaises(ValueError):
                analysis.summarize(changed, faults)
        bad_faults = deepcopy(faults)
        bad_faults["SN"]["a"]["run_id"] = None
        with self.assertRaises(ValueError):
            analysis.summarize(reports, bad_faults)

    def test_seed_average_no_count_inflation_fit_time_and_json_purity(self):
        reports, faults = fixture()
        original = deepcopy((reports, faults))
        result = analysis.summarize(reports, faults)
        self.assertEqual(result["decision"], "expansion_worth_considering")
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)
        self.assertEqual((reports, faults), original)
        self.assertEqual(result, analysis.summarize(list(reversed(reports)), faults))
        for system in result["systems"].values():
            self.assertEqual((system["incidents"], system["recordings"]), (6, 4))
            self.assertEqual(set(system["modes"]), set(analysis.MODES))
            directed = system["modes"]["directed"]
            self.assertAlmostEqual(directed["aggregate"]["top1"], .5)
            self.assertAlmostEqual(directed["by_incident"]["a"]["top1"], .5)
            self.assertEqual(set(directed["per_seed"]), {"11", "23", "37"})
            self.assertAlmostEqual(directed["per_seed"]["11"]["top1"], .1)
            self.assertEqual(set(directed["per_fold"]), {"0", "1", "2"})
            self.assertTrue(all(mode["fit_seconds"] == 13.5 for mode in system["modes"].values()))
            for name, expected in (("directed-global", .1), ("directed-local", .3)):
                comparison = system["comparisons"][name]
                self.assertAlmostEqual(comparison["mean"]["top1"], expected)
                self.assertAlmostEqual(comparison["ci95"]["top1"]["low"], expected)
                self.assertEqual(comparison["top1_win_tie_loss"], {"win": 6, "tie": 0, "loss": 0})
                self.assertEqual(len(comparison["by_incident"]), 6)
                self.assertEqual(comparison["by_incident"]["e"]["run_id"], "big")
                self.assertEqual(comparison["by_incident"]["e"]["fold"], 1)
                self.assertAlmostEqual(comparison["by_incident"]["e"]["difference"]["top1"], expected)

    def test_incident_equal_not_fold_equal_and_win_tie_loss(self):
        values = {"a": .7, "b": .7, "c": .7, "d": .4, "e": .4, "f": .1}
        reports, faults = fixture(lambda system, fold, seed, mode, event:
                                  values[event] if mode == "directed" else .4)
        result = analysis.summarize(reports, faults)["systems"]["SN"]
        self.assertAlmostEqual(result["modes"]["directed"]["aggregate"]["top1"], 3. / 6)
        comparison = result["comparisons"]["directed-global"]
        self.assertAlmostEqual(comparison["mean"]["top1"], .1)
        self.assertAlmostEqual(comparison["mean"]["top3"], .1)
        self.assertAlmostEqual(comparison["mean"]["mrr"], .05)
        self.assertAlmostEqual(comparison["per_fold"]["0"]["top1"], .225)
        self.assertAlmostEqual(comparison["per_fold"]["1"]["top1"], 0)
        self.assertAlmostEqual(comparison["per_fold"]["2"]["top1"], -.3)
        self.assertEqual(comparison["top1_win_tie_loss"], {"win": 3, "tie": 2, "loss": 1})

    def test_decision_requires_both_systems_two_folds_and_two_seeds(self):
        def score(kind):
            def value(system, fold, seed, mode, event):
                if mode != "directed":
                    return .4
                if kind == "system":
                    return .7 if system == "SN" else .3
                if kind == "fold":
                    return .8 if fold == 0 else .3
                if kind == "seed":
                    return .9 if seed == 11 else .3
                if kind == "zero":
                    return .4
                return .5 if fold < 2 and seed != 37 else .4
            return value

        for kind in ("system", "fold", "seed", "zero", "threshold"):
            reports, faults = fixture(score(kind))
            result = analysis.summarize(reports, faults)
            expected = ("expansion_worth_considering" if kind == "threshold"
                        else "insufficient_consistent_gain")
            with self.subTest(kind=kind):
                self.assertEqual(result["decision"], expected)
                if kind in ("fold", "seed"):
                    self.assertGreater(result["systems"]["SN"]["comparisons"]
                                       ["directed-global"]["mean"]["top1"], 0)


if __name__ == "__main__":
    unittest.main()
