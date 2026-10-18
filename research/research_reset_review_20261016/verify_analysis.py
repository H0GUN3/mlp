"""Independent metadata reconciliation and configuration-anchor support, no model use."""
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "rcabench_assessment_20261013"


def main():
    files = {
        "details": HERE / "metadata_details.json",
        "analysis": HERE / "metadata_analysis.json",
        "quality": AUDIT / "quality_audit.json",
        "inventory": AUDIT / "metadata_inventory.json",
    }
    blobs = {name: path.read_bytes() for name, path in files.items()}
    values = {name: json.loads(blob) for name, blob in blobs.items()}
    details, analysis = values["details"], values["analysis"]
    quality = {c["case"]: c for c in values["quality"]["cases"]}
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    assert sha((HERE / "extract_metadata.py").read_bytes()) == details["script_sha256"]
    assert sha((HERE / "analyze_metadata.py").read_bytes()) == analysis["script_sha256"]
    for path, expected in analysis["input_sha256"].items():
        matched = [name for name, p in files.items() if str(p) == path]
        assert len(matched) == 1 and sha(blobs[matched[0]]) == expected
    records = details["records"]
    assert set(records) == set(quality) == {r["case"] for r in analysis["case_rows"]}
    assert len(records) == analysis["cases"] == 1422
    types = Counter(r["injection.json"]["fault_type"] for r in records.values())
    assert types == Counter({r["id"]: r["cases"] for r in analysis["observed_fault_types"]})
    labels = Counter(len(r["injection.json"]["ground_truth"]["service"]) for r in records.values())
    assert labels == {1: 369, 2: 1053}
    flagged_cases = []
    for case, record in records.items():
        if any(any(v.get("slo_violated") is True for v in json.loads(row["Issues"]).values()
                   if isinstance(v, dict)) for row in record["conclusion.parquet"]["rows"]):
            flagged_cases.append(case)
    assert len(flagged_cases) == analysis["sli"]["cases_with_slo_flag"] == 1422
    comparable_anchor_cases, anchor_missing, conflict_cases = [], [], []
    for case, record in records.items():
        point = json.loads(record["injection.json"]["display_config"])["injection_point"]
        if "source_service" in point:
            continue
        anchor = point.get("app_name", point.get("app_label"))
        labels_for_case = record["injection.json"]["ground_truth"]["service"]
        if anchor not in labels_for_case:
            conflict_cases.append(case)
            continue
        assert anchor
        comparable_anchor_cases.append(case)
        missing = []
        for filename in ("normal_metrics.parquet", "abnormal_metrics.parquet",
                         "normal_traces.parquet", "abnormal_traces.parquet"):
            if quality[case]["files"][filename]["roots"][anchor]["basic_valid_rows"] == 0:
                missing.append(filename)
        if missing:
            anchor_missing.append({"case": case, "anchor": anchor, "files": missing})
    assert len(comparable_anchor_cases) == 1167 and len(conflict_cases) == 1
    within_overlap = cross_overlap = 0
    within_examples, cross_examples = [], []
    for (a, ra), (b, rb) in itertools.combinations(records.items(), 2):
        ea, eb = ra["env.json"], rb["env.json"]
        left = max(int(ea["NORMAL_START"]), int(eb["NORMAL_START"]))
        right = min(int(ea["ABNORMAL_END"]), int(eb["ABNORMAL_END"]))
        if left < right:
            if ea["NAMESPACE"] == eb["NAMESPACE"]:
                within_overlap += 1
                if len(within_examples) < 3:
                    within_examples.append([a, b])
            else:
                cross_overlap += 1
                if len(cross_examples) < 3:
                    cross_examples.append([a, b])
    assert within_overlap == analysis["intervals"]["counts"]["data_overlap_pairs"] == 0
    repeated = analysis["repeat_candidates"]
    repeated_cases = sum(len(g) for g in repeated["semantic_repeated_groups"])
    result = {
        "status": "PASS", "case_count": 1422, "fault_types": len(types),
        "source_sli_flag_cases": len(flagged_cases), "labels": dict(labels),
        "source_script_hashes_match": True,
        "candidate_non_network_anchor_cases": len(comparable_anchor_cases),
        "candidate_anchor_label_conflicts": conflict_cases,
        "candidate_anchor_basic_support_cases": len(comparable_anchor_cases) - len(anchor_missing),
        "candidate_anchor_missing_cases": anchor_missing,
        "candidate_anchor_missing_by_file": dict(Counter(f for r in anchor_missing for f in r["files"])),
        "within_namespace_positive_overlap_pairs": within_overlap,
        "cross_namespace_positive_overlap_pairs": cross_overlap,
        "cross_namespace_examples": cross_examples,
        "cases_in_semantically_repeated_configuration_groups": repeated_cases,
        "input_hashes": {str(files[name]): sha(blob) for name, blob in blobs.items()},
        "verifier_sha256": sha(Path(__file__).read_bytes()),
        "limits": [
            "1167 are configuration-target candidates, NOT adopted training cases or proven physical causes.",
            "Support is at least one valid root row per file, not sufficient coverage.",
            "Cross-namespace temporal overlap is not proof of duplicate telemetry; host sharing is unresolved.",
            "Source-generated SLI flags are not independently recomputed tests.",
            "No new split or model execution."]}
    with (HERE / "verification.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print("RCAB_METADATA_VERIFICATION_PASS", result["candidate_non_network_anchor_cases"],
          result["candidate_anchor_basic_support_cases"], cross_overlap, flush=True)


if __name__ == "__main__":
    main()
