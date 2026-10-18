"""Independent exact reconstruction of saved RCAB Top1 credits."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from math import fsum
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "research/dataset_suitability_20261016/rcab_trial.json"
HERE = Path(__file__).resolve().parent
OUT = HERE / "scoring_check.json"
CRITERIA = ("uniform", "abnormal_http_error_fraction",
            "http_error_fraction_increase", "abnormal_span_error_fraction")
CONTRACTS = ("nominal_anchor", "original_accepted_roots")


def credit(scores: dict, accepted: list[str]) -> tuple[Fraction, int]:
    """Top1 expectation: accepted members / highest-score tier size."""
    candidates = list(scores)
    supported = [s for s in candidates if scores[s]["score"] is not None]
    score_values = {scores[s]["score"] for s in supported}
    if supported and score_values == {0.0}:
        tier = supported
    elif supported:
        high = max(scores[s]["score"] for s in supported)
        tier = [s for s in supported if scores[s]["score"] == high]
    else:
        tier = supported if supported else candidates
    gold = set(accepted)
    return Fraction(len(gold.intersection(tier)), len(tier)), len(tier)


def self_check() -> None:
    assert credit({"a": {"score": 2}, "b": {"score": 2}, "c": {"score": 1}},
                  ["a"])[0] == Fraction(1, 2)
    assert credit({"a": {"score": 2}, "b": {"score": 2}}, ["a", "b"])[0] == 1
    assert credit({"a": {"score": None}, "b": {"score": None}}, ["b"])[0] == Fraction(1, 2)
    assert credit({"a": {"score": -1}, "b": {"score": None}}, ["b"])[0] == 0
    assert credit({"a": {"score": -1}, "b": {"score": None}}, ["a"])[0] == 1
    assert credit({"a": {"score": 1}}, ["absent"])[0] == 0
    sc = {"a": {"score": 1}, "b": {"score": 1}, "c": {"score": 0}}
    assert credit(sc, ["a"])[0] == credit(dict(reversed(list(sc.items()))), ["a"])[0]


def main() -> None:
    self_check()
    before = hashlib.sha256(PILOT.read_bytes()).hexdigest()
    with PILOT.open(encoding="utf-8") as f:
        data = json.load(f)
    cases = data["pilot_cases"]
    assert len(cases) == 173
    rows = []
    all_credits: dict[tuple[str, str], list[Fraction]] = {}
    for criterion in CRITERIA:
        for contract in CONTRACTS:
            credits, tiers = [], []
            for case in cases.values():
                accepted = case[contract]
                if isinstance(accepted, str):
                    accepted = [accepted]
                c, tier_size = credit(case["scores"][criterion], accepted)
                saved = case["metrics"][contract][criterion]["top1"]
                assert abs(float(c) - saved) <= 1e-12, (criterion, contract, saved, str(c))
                credits.append(c)
                tiers.append(tier_size)
            counts = Counter("zero" if x == 0 else "one" if x == 1 else "partial" for x in credits)
            exact_sum = sum(credits)
            exact_mean = exact_sum / Fraction(len(credits))
            rows.append({
                "criterion": criterion, "label_contract": contract, "N": len(credits),
                "credit_sum": {"numerator": exact_sum.numerator,
                               "denominator": exact_sum.denominator},
                "mean": {"numerator": exact_mean.numerator,
                         "denominator": exact_mean.denominator},
                "mean_float_fsum_check": fsum(map(float, credits)) / len(credits),
                "zero_cases": counts["zero"], "partial_cases": counts["partial"],
                "one_cases": counts["one"], "top_tier_tie_cases": sum(t > 1 for t in tiers),
                "partial_tie_cases": sum(0 < x < 1 and t > 1 for x, t in zip(credits, tiers)),
                "missing_candidate_scores": sum(
                    len(case.get("missing_score_candidates", {}).get(criterion, []))
                    for case in cases.values()),
                "evaluation_cases": len(cases),
            })
            all_credits[(criterion, contract)] = credits
            saved_mean = data["pilot_summary"]["overall"]["case_equal_metrics"][contract][criterion]["top1"]
            exact_mean = fsum(map(float, credits)) / len(credits)
            assert abs(saved_mean - exact_mean) <= 1e-12
    examples = []
    for case_id, case in cases.items():
        c = case["scores"]["abnormal_http_error_fraction"]
        accepted = case["nominal_anchor"]
        if isinstance(accepted, str):
            accepted = [accepted]
        x, tier = credit(c, accepted)
        if 0 < x < 1:
            examples.append({"case_id": case_id, "credit": f"{x.numerator}/{x.denominator}",
                             "top_tier_size": tier,
                             "accepted_in_tier": x.numerator,
                             "accepted_roots": accepted,
                             "top_tier": [s for s in c if c[s]["score"] is not None
                                          and c[s]["score"] == max(
                                              r["score"] for r in c.values()
                                              if r["score"] is not None)]})
        if len(examples) == 2:
            break
    assert len(examples) == 2
    spans = {}
    for contract in CONTRACTS:
        cs = all_credits[("abnormal_span_error_fraction", contract)]
        spans[contract] = {
            "credit_sum": f"{sum(cs).numerator}/{sum(cs).denominator}",
            "98_over_173": sum(cs) == Fraction(98),
            "99_over_173": sum(cs) == Fraction(99),
        }
    result = {"input_sha256": before, "N": len(cases), "rows": rows,
              "http_partial_examples": examples, "span_exact_check": spans,
              "self_checks": "PASS"}
    after = hashlib.sha256(PILOT.read_bytes()).hexdigest()
    assert before == after
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with OUT.open("x", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    print("SCORING_CHECK_PASS")


if __name__ == "__main__":
    main()
