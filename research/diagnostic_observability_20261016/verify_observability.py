"""Reconcile audit artifacts and produce bounded, source-linked descriptive totals."""
from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    destination = HERE / "verified_summary.json"
    if destination.exists():
        raise FileExistsError(destination)
    paths = {n: HERE / n for n in ("rcab_observability.json", "rcab_focused.json", "sn_tt_audit.json")}
    blobs = {n: p.read_bytes() for n, p in paths.items()}
    audit, focused, native = [json.loads(blobs[n]) for n in paths]
    sha = lambda b: hashlib.sha256(b).hexdigest()
    assert all(v["status"] == "PASS" for v in (audit, focused, native))
    assert sha((HERE / "rcab_audit.py").read_bytes()) == audit["script_sha256"]
    assert sha((HERE / "rcab_focused.py").read_bytes()) == focused["script_sha256"]
    assert focused["previous_audit_sha256"] == sha(blobs["rcab_observability.json"])
    assert len(audit["manifest"]["http_census_cases"]) == 796
    assert len(audit["manifest"]["deep_sample_cases"]) == 14
    assert audit["files_read"] == len(audit["file_sha256"]) == 3220
    assert audit["rows_read"] == sum(f["rows"] for c in audit["cases"].values() for f in c["files"].values())
    trace_totals = {p: Counter() for p in ("normal", "abnormal")}
    roots, candidate_sizes, non_loadgen_sizes = Counter(), Counter(), Counter()
    candidates = set()
    for case in audit["manifest"]["http_census_cases"]:
        row = audit["cases"][case]
        names = {s for f in row["files"].values() for s in f.get("services", [])}
        candidates.update(names)
        candidate_sizes[len(names)] += 1
        non_loadgen_sizes[len(names - {"loadgenerator", "loadgenerator-service"})] += 1
        for p in trace_totals:
            tr = row["files"][p + "_traces.parquet"]
            t = tr["totals"]
            assert 0 <= t["http_error_sum"] <= t["http_known_sum"] <= t["rows_sum"] == tr["rows"]
            for seconds in (10, 30, 60):
                assert 0 <= t[f"prefix{seconds}_unfinished_sum"] <= t[f"prefix{seconds}_starts_sum"] <= tr["rows"]
            trace_totals[p].update(t)
            root = Counter()
            for r in tr["targets"]:
                if r["service_name"] == row["anchor"]:
                    root.update({k: v for k, v in r.items() if k.endswith("_sum")})
            for k in ("rows_sum", "http_known_sum", "http_error_sum", "span_error_sum"):
                roots[p + "_" + k] += int(root[k] > 0)
    sample_totals = {}
    for p in ("normal", "abnormal"):
        total = Counter()
        for case in audit["manifest"]["deep_sample_cases"]:
            files = audit["cases"][case]["files"]
            d, l = files[p + "_traces.parquet"]["detail"], files[p + "_logs.parquet"]
            assert 0 <= d["resolved_parent_references"] <= d["unambiguous_parent_references"] <= d["unique_span_identities"]
            assert d["pairs_with_both_http_codes"] <= d["client_server_parent_pairs"] <= d["resolved_parent_references"]
            assert l["keys_joinable_to_trace"] <= l["identified_log_span_keys"] <= l["rows"]
            for k in ("unique_span_identities", "conflicting_identities", "unambiguous_parent_references",
                      "resolved_parent_references", "client_server_parent_pairs", "pairs_with_both_http_codes"):
                total[k] += d[k]
            total["log_rows"] += l["rows"]
            total["log_identity_keys"] += l["identified_log_span_keys"]
            total["log_keys_joinable"] += l["keys_joinable_to_trace"]
            total["injection_marker_rows"] += sum(r["injection_marker_sum"] for r in l["per_service"])
        sample_totals[p] = dict(total)
    for filename, data in focused["files"].items():
        assert data["input_sha256"] == audit["file_sha256"][filename]
        assert data["pair_count"] == sum(r["count"] for r in data["outcomes"])
    native_totals = {}
    for system, data in native["systems"].items():
        assert all(data["checks"].values())
        native_totals[system] = {
            "windows": data["schema"]["values"]["shape"][0],
            "services": len(data["services"]),
            "services_without_latency": sum(s["latency_present_windows"] == 0 for s in data["services"]),
            "temporal_loss": data["temporal_loss"]["transforms"],
            "root_contrasts": {k: v for k, v in data["root_contrasts"].items() if k != "windows"},
            "fold_support": data["fold_support"]}
    result = {
        "status": "PASS", "source_sha256": {n: sha(b) for n, b in blobs.items()},
        "http_cases": 796, "sample_cases": 14, "trace_totals": trace_totals,
        "root_observation_cases": dict(roots),
        "candidate_name_union": sorted(candidates),
        "raw_candidate_count_histogram": dict(candidate_sizes),
        "without_two_loadgenerator_names_histogram": dict(non_loadgen_sizes),
        "candidate_policy_adopted": False, "sample_totals": sample_totals, "native": native_totals,
        "limits": "Descriptive observation audit; neither causal identifiability nor new-model performance.",
        "verifier_sha256": sha(Path(__file__).read_bytes())}
    with destination.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print("OBSERVABILITY_RECONCILIATION_PASS", 796, 14, audit["rows_read"], flush=True)


if __name__ == "__main__":
    main()
