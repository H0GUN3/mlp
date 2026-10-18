"""Offline independent checks for the saved RCA smoke experiment."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

BASE = Path(__file__).resolve().parents[1]
SMOKE = BASE / "research" / "smoke"
REPORT = BASE / "research" / "verification" / "smoke-checks.json"
CONDITIONS = ("cards_only", "all_calls", "rule_selected", "random_selected")
COMMAND = "cd /home/gnho1236/r2 && .venv/bin/python scripts/verify_smoke.py"


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []
    failures = []

    def check(name, passed, details):
        entry = {"name": name, "passed": bool(passed), "details": details}
        checks.append(entry)
        if not passed:
            failures.append(entry)

    manifest_path = SMOKE / "manifest.json"
    protocol_path = BASE / "research" / "SMOKE_PROTOCOL.md"
    manifest = read_json(manifest_path)
    protocol_hash = digest(protocol_path)
    check("protocol_hash_matches_manifest", manifest.get("protocol_sha256") == protocol_hash,
          {"manifest": manifest.get("protocol_sha256"), "actual": protocol_hash})

    cases = manifest.get("cases", [])
    case_ids = [case.get("id") for case in cases]
    check("manifest_has_12_unique_cases", len(cases) == 12 and len(set(case_ids)) == 12,
          {"count": len(cases), "unique_ids": len(set(case_ids))})
    selected_groups = [(case.get("dataset"), case.get("root_cause_service"), case.get("fault"))
                       for case in cases]
    reservation_errors = []
    if len(set(selected_groups)) != len(selected_groups):
        reservation_errors.append({"reason": "selected scenario groups are not distinct",
                                   "groups": selected_groups})
    audit_rows = read_json(BASE / "evidence" / "rcaeval-cases.json")
    audit_by_case = {row["case"]: row for row in audit_rows}
    feature_by_case, request_by_case = {}, {}
    source_paths = [manifest_path, protocol_path, BASE / "evidence" / "rcaeval-cases.json",
                    BASE / "research" / "SMOKE_POSTCHECK.md",
                    BASE / "scripts" / "smoke.py", BASE / "scripts" / "audit.py",
                    BASE / "research" / "smoke" / "predictions.json",
                    BASE / "research" / "smoke" / "simple-anomaly.json",
                    BASE / "research" / "smoke" / "posthoc-synthetic-sanity.json"]
    source_paths += sorted((SMOKE / "features").glob("*.json"))
    source_paths += sorted((SMOKE / "requests").glob("*.json"))
    source_paths += sorted((SMOKE / "responses").glob("*.json"))
    source_paths += [SMOKE / "summary.json"]
    source_paths += [BASE / "scripts" / "verify_smoke.py"]
    predictions = read_json(SMOKE / "predictions.json")
    feature_errors, mapping_errors = [], []
    message_leaks, cards_errors, edge_errors = [], [], []
    reserved_by_case = {}

    for case in cases:
        case_id = case.get("id")
        feature_path = SMOKE / "features" / f"{case_id}.json"
        feature = read_json(feature_path)
        feature_by_case[case_id] = feature
        source_paths.append(feature_path)
        evidence = audit_by_case.get(case.get("case"))
        if not evidence or evidence.get("root_cause_service") != case.get("root_cause_service"):
            mapping_errors.append({"case": case_id, "reason": "manifest truth/service disagrees with local audit"})
        mapping = feature.get("mapping", {})
        if mapping.get(case.get("root_cause_service")) != case.get("truth"):
            mapping_errors.append({"case": case_id, "reason": "truth ID does not map to manifest root service"})
        card_ids = {card.get("id") for card in feature.get("cards", [])}
        if case.get("truth") not in card_ids:
            mapping_errors.append({"case": case_id, "reason": "truth ID absent from feature cards"})

        selected_group = (case.get("dataset"), case.get("root_cause_service"), case.get("fault"))
        reserved = case.get("reserved_development_cases", [])
        reserved_by_case[case_id] = set(reserved)
        reserved_groups = []
        for name in reserved:
            row = audit_by_case.get(name)
            if row is None:
                reservation_errors.append({"case": case_id, "reserved_case": name, "reason": "absent from local audit"})
            else:
                reserved_groups.append((row.get("dataset"), row.get("root_cause_service"), row.get("fault")))
                if (row.get("dataset"), row.get("root_cause_service"), row.get("fault")) != selected_group:
                    reservation_errors.append({"case": case_id, "reserved_case": name, "reason": "reserved group mismatch"})
        if len(reserved) != 3 or case.get("case") not in reserved:
            reservation_errors.append({"case": case_id, "reason": "reserved set must contain selected case and three repetitions"})
        if any(group != selected_group for group in reserved_groups):
            reservation_errors.append({"case": case_id, "reason": "reserved group overlaps another scenario"})

        calls = feature.get("calls", {})
        card_sets = []
        candidate_sets = []
        normalized_edges = {}
        for condition in CONDITIONS:
            stem = f"{case_id}-{condition}"
            request_path = SMOKE / "requests" / f"{stem}.json"
            response_path = SMOKE / "responses" / f"{stem}.json"
            request = read_json(request_path)
            raw = read_json(response_path)
            source_paths += [request_path, response_path]
            request_by_case.setdefault(case_id, {})[condition] = request
            user_content = request["messages"][1]["content"]
            message_blob = "\n".join(message.get("content", "") for message in request.get("messages", []))
            originals = [case.get("case", ""), case.get("root_cause_service", "")]
            originals += [str(name) for name in feature.get("mapping", {})]
            found = sorted({name for name in originals if name and name in message_blob})
            if found:
                message_leaks.append({"case": case_id, "condition": condition, "matches": found})
            evidence_payload = json.loads(user_content)
            cards = evidence_payload.get("services", [])
            card_sets.append(cards)
            candidate_sets.append(set(request.get("format", {}).get("properties", {}).get("ranking", {})
                                      .get("items", {}).get("enum", [])))
            submitted_edges = {tuple(edge) for edge in evidence_payload.get("observed_calls", [])}
            expected_edges = {tuple(edge) for edge in calls.get(condition, [])}
            if submitted_edges != expected_edges:
                edge_errors.append({"case": case_id, "condition": condition,
                                    "reason": "request calls differ from saved feature calls"})
            normalized_edges[condition] = submitted_edges
            ranking = json.loads(raw.get("message", {}).get("content", "{}")).get("ranking")
            prediction = next((row for row in predictions
                               if row.get("id") == case_id and row.get("condition") == condition), None)
            if ranking != (prediction or {}).get("ranking"):
                feature_errors.append({"case": case_id, "condition": condition,
                                       "reason": "raw response ranking differs from saved prediction"})
            if ranking is not None and (len(ranking) != 3 or len(set(ranking)) != len(ranking)
                                        or not set(ranking) <= candidate_sets[-1]):
                feature_errors.append({"case": case_id, "condition": condition,
                                       "reason": "raw ranking violates candidate schema"})
        if any(cards != card_sets[0] for cards in card_sets[1:]) or any(
                candidates != candidate_sets[0] for candidates in candidate_sets[1:]):
            cards_errors.append(case_id)
        observed = normalized_edges["all_calls"]
        if not normalized_edges["rule_selected"] <= observed or not normalized_edges["random_selected"] <= observed:
            edge_errors.append({"case": case_id, "reason": "selected edge absent from observed full calls"})
        if len(normalized_edges["rule_selected"]) != len(normalized_edges["random_selected"]):
            edge_errors.append({"case": case_id, "reason": "rule and random edge counts differ"})

    for left_id, left_reserved in reserved_by_case.items():
        for right_id, right_reserved in reserved_by_case.items():
            if left_id < right_id and left_reserved & right_reserved:
                reservation_errors.append({"cases": [left_id, right_id],
                                           "overlap": sorted(left_reserved & right_reserved)})
        for other in cases:
            other_id = other.get("id")
            if other_id != left_id and other.get("case") in left_reserved:
                reservation_errors.append({"case": left_id, "reason": "selected case overlaps another reservation",
                                           "other_selected_case": other.get("case"), "other_id": other_id})

    expected_keys = {(case_id, condition) for case_id in case_ids for condition in CONDITIONS}
    prediction_keys = [(row.get("id"), row.get("condition")) for row in predictions]
    check("48_unique_predictions", len(predictions) == 48 and set(prediction_keys) == expected_keys
          and len(set(prediction_keys)) == 48,
          {"rows": len(predictions), "unique": len(set(prediction_keys)), "expected": 48})
    check("raw_response_rankings_match_predictions", not feature_errors,
          {"mismatches": feature_errors})
    check("truth_ids_match_manifest_features_and_local_audit", not mapping_errors,
          {"issues": mapping_errors})
    check("cards_and_candidate_sets_identical_across_conditions", not cards_errors,
          {"cases_with_mismatch": cards_errors})
    check("rule_random_edge_counts_equal_and_edges_observed", not edge_errors,
          {"issues": edge_errors})
    check("original_service_and_case_names_absent_from_messages", not message_leaks,
          {"leaks": message_leaks})
    check("reserved_groups_are_consistent_and_disjoint", not reservation_errors,
          {"issues": reservation_errors})

    scores = defaultdict(lambda: {"n": 0, "top1": 0, "top3": 0, "valid": 0})
    recomputed = []
    for row in predictions:
        case = next((item for item in cases if item.get("id") == row.get("id")), {})
        ranking = row.get("ranking") or []
        truth = case.get("truth")
        top1, top3 = bool(ranking and ranking[0] == truth), truth in ranking
        condition = row.get("condition")
        bucket = scores[condition]
        bucket["n"] += 1
        bucket["top1"] += top1
        bucket["top3"] += top3
        bucket["valid"] += bool(row.get("valid"))
        recomputed.append({"id": row.get("id"), "condition": condition, "truth": truth,
                           "ranking": ranking, "top1": top1, "top3": top3,
                           "saved_top1": row.get("top1"), "saved_top3": row.get("top3")})
    score_flag_errors = [row for row in recomputed
                         if row["top1"] != row["saved_top1"] or row["top3"] != row["saved_top3"]]
    check("prediction_correctness_flags_recomputed", not score_flag_errors,
          {"flags_recomputed": len(recomputed), "mismatches": score_flag_errors})
    check("condition_aggregates_recomputed", all(scores[c]["n"] == 12 for c in CONDITIONS),
          {"conditions": dict(scores)})
    expected_counts = {"cards_only": 1, "all_calls": 1, "rule_selected": 2, "random_selected": 1}
    check("claimed_condition_top1_counts", all(scores[c]["top1"] == expected_counts[c] for c in CONDITIONS),
          {"expected": expected_counts, "observed": {c: scores[c]["top1"] for c in CONDITIONS}})
    saved_summary = read_json(SMOKE / "summary.json")
    summary_mismatches = []
    for condition in CONDITIONS:
        saved = saved_summary.get("conditions", {}).get(condition, {})
        for key, actual_key in (("top1_count", "top1"), ("top3_count", "top3"), ("valid", "valid")):
            if saved.get(key) != scores[condition][actual_key]:
                summary_mismatches.append({"condition": condition, "field": key,
                                           "saved": saved.get(key), "recomputed": scores[condition][actual_key]})
    check("saved_condition_summary_matches_recomputed", not summary_mismatches,
          {"mismatches": summary_mismatches})

    anomaly = read_json(SMOKE / "simple-anomaly.json")
    anomaly_counts = {"n": len(anomaly),
                      "top1": sum(item.get("ranking", [None])[0] == next(
                          (case.get("truth") for case in cases if case.get("id") == item.get("id")), None)
                                  for item in anomaly),
                      "top3": sum(next((case.get("truth") for case in cases if case.get("id") == item.get("id")), None)
                                  in item.get("ranking", [])[:3] for item in anomaly)}
    anomaly_flags = []
    anomaly_ranking_mismatches = []
    for item in anomaly:
        truth = next((case.get("truth") for case in cases if case.get("id") == item.get("id")), None)
        if item.get("top1") != bool(item.get("ranking") and item["ranking"][0] == truth):
            anomaly_flags.append(item.get("id"))
        score_map = {card["id"]: (card["metrics"][0][1] if card.get("metrics") else 0.0)
                     for card in feature_by_case[item.get("id")].get("cards", [])}
        recomputed_ranking = sorted(score_map, key=lambda service: (-score_map[service], service))
        if item.get("ranking") != recomputed_ranking:
            anomaly_ranking_mismatches.append({"case": item.get("id"),
                                               "saved": item.get("ranking"),
                                               "recomputed": recomputed_ranking})
    check("simple_anomaly_11_of_12_recomputed", anomaly_counts["n"] == 12 and anomaly_counts["top1"] == 11
          and not anomaly_flags and not anomaly_ranking_mismatches,
          {"counts": anomaly_counts, "saved_flag_mismatches": anomaly_flags,
           "ranking_mismatches": anomaly_ranking_mismatches})

    sanity = read_json(SMOKE / "posthoc-synthetic-sanity.json")
    sanity_results = [{"expected": row.get("expected"), "ranking": row.get("ranking"),
                       "recomputed_correct": bool(row.get("ranking") and row["ranking"][0] == row.get("expected")),
                       "saved_correct": row.get("correct")} for row in sanity.get("cases", [])]
    sanity_pass = len(sanity_results) == 2 and all(
        item["recomputed_correct"] and item["saved_correct"] == item["recomputed_correct"]
        for item in sanity_results)
    check("synthetic_sanity_two_of_two_recomputed", sanity_pass, {"cases": sanity_results})

    summaries = {}
    for condition in CONDITIONS:
        rows = [row for row in predictions if row.get("condition") == condition]
        prompt = [row["prompt_tokens"] for row in rows if isinstance(row.get("prompt_tokens"), (int, float))]
        output = [row["output_tokens"] for row in rows if isinstance(row.get("output_tokens"), (int, float))]
        llm = [row["server_seconds"] for row in rows if isinstance(row.get("server_seconds"), (int, float))]
        wall = [row["wall_seconds"] for row in rows if isinstance(row.get("wall_seconds"), (int, float))]
        summaries[condition] = {
            **scores[condition],
            "prompt_tokens_mean": statistics.mean(prompt) if prompt else None,
            "prompt_tokens_total": sum(prompt),
            "output_tokens_mean": statistics.mean(output) if output else None,
            "output_tokens_total": sum(output),
            "llm_server_seconds_mean": statistics.mean(llm) if llm else None,
            "llm_server_seconds_total": sum(llm),
            "request_wall_seconds_mean": statistics.mean(wall) if wall else None,
            "request_wall_seconds_total": sum(wall),
        }
    preprocess = {case_id: feature_by_case[case_id].get("preprocess_seconds") for case_id in case_ids}
    source_hashes = {str(path.relative_to(BASE)): digest(path) for path in sorted(set(source_paths))}
    passed = not failures
    report = {
        "verifier": "offline RCA smoke verification",
        "command": COMMAND,
        "command_result": {"exit_code": 0 if passed else 1,
                           "line": "VERIFY_SMOKE_PASSED" if passed else "VERIFY_SMOKE_FAILED"},
        "passed": passed,
        "checks": checks,
        "counts": {"predictions": 48, "conditions": {key: dict(value) for key, value in scores.items()},
                   "simple_anomaly": anomaly_counts, "synthetic_sanity": sanity_results},
        "timings_and_tokens": {
            "per_condition": summaries,
            "preprocess_seconds_by_case": preprocess,
            "preprocess_seconds_total": sum(value for value in preprocess.values() if value is not None),
            "timing_note": "server_seconds is LLM/server request inference duration; wall_seconds is request wall time. Neither includes feature preprocessing. Preprocess values are recorded from smoke feature generation, not recomputed by this verifier."
        },
        "source_sha256": source_hashes,
        "failure_count": len(failures),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("VERIFY_SMOKE_PASSED" if passed else "VERIFY_SMOKE_FAILED")
    print(f"checks={len(checks)} failures={len(failures)} report={REPORT.relative_to(BASE)}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
