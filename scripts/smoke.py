"""Preregistered, local-only RCA evidence-selection smoke experiment."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import time
import urllib.request

import numpy as np
import pyarrow.parquet as pq

from audit import observed_calls

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "research" / "smoke"
SEED = 20261012
MODEL = "qwen3:8b"
API = "http://127.0.0.1:11435"
CONDITIONS = ("cards_only", "all_calls", "rule_selected", "random_selected")
SYSTEM = """You diagnose the initiating root-cause service in one incident.
Choose from the anonymous service IDs in the evidence. Many services may show downstream
symptoms; the largest change alone is not necessarily the initiating cause.
Metric entries are [metric_family, absolute_robust_change_score, up/down/flat].
The score is a change of medians divided by the normal IQR with a scale floor, capped at100.
Null means unavailable, not healthy. Trace entries are [normal_span_count,
fault_span_count, fault/normal median_duration_ratio]. Counts depend on window coverage.
Call pairs are [caller,callee] observed in traces, NOT verified causal propagation.
Dependencies may propagate symptoms from callee back to caller. An omitted pair is unknown,
not proof that no dependency exists. All service cards remain present in every condition.
Return only a JSON object with ranking: three distinct service IDs, most likely cause first.
Do not infer anything from the anonymous ID order."""


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def api(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(API + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


def metric_change(normal, fault):
    a, b = normal[np.isfinite(normal)], fault[np.isfinite(fault)]
    if len(a) < 20 or len(b) < 20:
        return None
    am, bm = float(np.median(a)), float(np.median(b))
    q25, q75 = np.quantile(a, [.25, .75])
    denominator = max(float(q75 - q25), abs(am) * .05, 1e-9)
    score = min(100., abs(bm - am) / denominator)
    return round(score, 3), ("up" if bm > am else "down" if bm < am else "flat")


def build_features(case_path, injection, seed):
    started = time.monotonic()
    metrics = pq.read_table(case_path / "metrics.parquet")
    times = metrics["time"].to_numpy()
    normal_mask = times < injection
    per_service = defaultdict(list)
    missing = defaultdict(int)
    for name in metrics.column_names:
        if name == "time":
            continue
        service, family = name.split("_", 1)
        values = metrics[name].to_numpy()
        change = metric_change(values[normal_mask], values[~normal_mask])
        per_service.setdefault(service, [])
        if change is None:
            missing[service] += 1
        else:
            per_service[service].append([family, *change])
    traces = pq.read_table(case_path / "traces.parquet", columns=[
        "traceID", "spanID", "parentSpanID", "serviceName", "duration", "startTime"])
    trace_services = np.array(traces["serviceName"].to_pylist(), dtype=object)
    services = sorted(set(per_service) | {s for s in trace_services if s})
    shuffled = services.copy()
    random.Random(seed).shuffle(shuffled)
    mapping = {name: f"S{index + 1:02d}" for index, name in enumerate(shuffled)}
    trace_times = traces["startTime"].to_numpy() / 1e6
    durations = traces["duration"].to_numpy()
    cards, scores = [], {}
    for name in services:
        changes = sorted(per_service[name], key=lambda x: (-x[1], x[0]))
        score = changes[0][1] if changes else 0.
        scores[mapping[name]] = score
        present = trace_services == name
        before = durations[present & (trace_times < injection)]
        after = durations[present & (trace_times >= injection)]
        ratio = None
        if len(before) and len(after) and np.median(before) > 0:
            ratio = round(float(np.median(after) / np.median(before)), 3)
        cards.append({"id": mapping[name], "metrics": changes[:3],
                      "missing_metrics": missing[name],
                      "trace": [len(before), len(after), ratio]})
    call_table = traces.select(["traceID", "spanID", "parentSpanID", "serviceName"]).rename_columns(
        ["trace_id", "span_id", "parent_span_id", "service_name"])
    calls, absent_parents, duplicate_keys, conflicts = observed_calls([call_table])
    all_calls = sorted((mapping[a], mapping[b]) for a, b in calls if a in mapping and b in mapping)
    rule = sorted(sorted(all_calls, key=lambda pair: (-min(scores[pair[0]], scores[pair[1]]), pair))[:8])
    rand = sorted(random.Random(seed + 10000).sample(all_calls, len(rule)))
    return {"cards": sorted(cards, key=lambda card: card["id"]),
            "calls": {"cards_only": [], "all_calls": all_calls,
                      "rule_selected": rule, "random_selected": rand},
            "mapping": mapping, "anomaly_ranking": sorted(scores, key=lambda s: (-scores[s], s)),
            "missing_parent_spans": absent_parents, "duplicate_span_keys": duplicate_keys,
            "conflicting_span_keys_excluded": conflicts,
            "preprocess_seconds": time.monotonic() - started}


def request_for(features, condition):
    candidates = [card["id"] for card in features["cards"]]
    evidence = {"services": features["cards"], "observed_calls": features["calls"][condition]}
    schema = {"type": "object", "properties": {"ranking": {"type": "array", "minItems": 3,
              "maxItems": 3, "items": {"type": "string", "enum": candidates}}},
              "required": ["ranking"], "additionalProperties": False}
    text = json.dumps(evidence, separators=(",", ":"), allow_nan=False)
    # UTF-8 byte bound plus template/schema allowance avoids relying on a hidden truncation.
    assert len((SYSTEM + text + json.dumps(schema)).encode()) + 1000 < 16384 - 384
    return {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": text}], "format": schema, "think": False,
            "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0, "seed": SEED, "num_ctx": 16384, "num_predict": 384}}


def parse_ranking(response, candidates):
    if not response.get("done") or response.get("done_reason") != "stop":
        raise ValueError("generation did not finish normally")
    if response.get("message", {}).get("thinking"):
        raise ValueError("thinking output despite think=false")
    result = json.loads(response["message"]["content"])
    ranking = result.get("ranking")
    if not isinstance(ranking, list) or len(ranking) != 3 or not all(isinstance(x, str) for x in ranking):
        raise ValueError("ranking must contain three strings")
    if len(set(ranking)) != 3 or not set(ranking) <= set(candidates):
        raise ValueError("duplicate or out-of-candidate prediction")
    return ranking


def self_check():
    assert metric_change(np.ones(20), np.full(20, 2)) == (20., "up")
    assert metric_change(np.array([np.nan] * 20), np.ones(20)) is None
    good = {"done": True, "done_reason": "stop", "message": {"content": '{"ranking":["a","b","c"]}'}}
    assert parse_ranking(good, ["a", "b", "c"]) == ["a", "b", "c"]
    try:
        parse_ranking(good, ["a", "b", "d"])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid candidate accepted")


def prepare():
    if (OUT / "manifest.json").exists():
        raise FileExistsError("Manifest already exists; do not silently reselect smoke cases")
    records = pq.read_table(BASE / "data/rcaeval/cases.parquet").to_pylist()
    rng = random.Random(SEED)
    selected = []
    for system in ("RE2-OB", "RE2-TT"):
        for fault in ("cpu", "delay", "disk", "loss", "mem", "socket"):
            eligible = sorted((r for r in records if r["dataset"] == system and r["fault"] == fault),
                              key=lambda r: r["case"])
            selected.append(rng.choice(eligible))
    manifest = {"seed": SEED, "protocol_sha256": hashlib.sha256(
        (BASE / "research/SMOKE_PROTOCOL.md").read_bytes()).hexdigest(), "cases": []}
    for number, record in enumerate(selected, 1):
        identifier = f"incident-{number:02d}"
        features = build_features(BASE / "data/rcaeval" / record["case"], record["inject_time"], SEED + number)
        dump(OUT / "features" / f"{identifier}.json", features)
        for condition in CONDITIONS:
            dump(OUT / "requests" / f"{identifier}-{condition}.json", request_for(features, condition))
        group = (record["dataset"], record["root_cause_service"], record["fault"])
        reserved = [r["case"] for r in records
                    if (r["dataset"], r["root_cause_service"], r["fault"]) == group]
        assert len(reserved) == 3
        manifest["cases"].append({"id": identifier, "case": record["case"], "dataset": record["dataset"],
            "fault": record["fault"], "truth": features["mapping"][record["root_cause_service"]],
            "root_cause_service": record["root_cause_service"], "reserved_development_cases": reserved})
        print(f"PREPARED {identifier} services={len(features['cards'])} calls={len(features['calls']['all_calls'])}", flush=True)
    dump(OUT / "manifest.json", manifest)
    print("PREPARE_COMPLETE", flush=True)


def run():
    manifest = json.loads((OUT / "manifest.json").read_text())
    if (OUT / "predictions.json").exists():
        raise FileExistsError("Predictions already exist; report first-run results, not an overwrite")
    metadata = {"version": api("/api/version"), "tags": api("/api/tags"),
                "model": api("/api/show", {"model": MODEL}),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump(OUT / "model-metadata.json", metadata)
    warmup = api("/api/chat", {"model": MODEL, "messages": [{"role": "user", "content": "Return {} only."}],
                            "think": False, "stream": False, "format": "json", "keep_alive": "10m",
                            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 32}})
    dump(OUT / "warmup.json", warmup)
    jobs = [(case, condition) for case in manifest["cases"] for condition in CONDITIONS]
    random.Random(SEED).shuffle(jobs)
    predictions = []
    for number, (case, condition) in enumerate(jobs, 1):
        stem = f"{case['id']}-{condition}"
        request = json.loads((OUT / "requests" / f"{stem}.json").read_text())
        raw_path = OUT / "responses" / f"{stem}.json"
        started = time.monotonic()
        error, ranking, response = None, [], {}
        try:
            if raw_path.exists():
                response = json.loads(raw_path.read_text())
            else:
                response = api("/api/chat", request)
                dump(raw_path, response)
            ranking = parse_ranking(response, request["format"]["properties"]["ranking"]["items"]["enum"])
            if response["prompt_eval_count"] + response["eval_count"] >= 16384:
                raise ValueError("context limit reached")
        except Exception as exc:
            error, ranking = repr(exc), []
        entry = {"id": case["id"], "dataset": case["dataset"], "condition": condition,
                 "ranking": ranking, "truth": case["truth"], "valid": error is None,
                 "top1": bool(ranking and ranking[0] == case["truth"]), "top3": case["truth"] in ranking,
                 "error": error, "wall_seconds": time.monotonic() - started,
                 "prompt_tokens": response.get("prompt_eval_count"), "output_tokens": response.get("eval_count"),
                 "server_seconds": response.get("total_duration", 0) / 1e9,
                 "load_seconds": response.get("load_duration", 0) / 1e9}
        predictions.append(entry)
        dump(OUT / "predictions-in-progress.json", predictions)
        print(f"RUN {number}/48 {stem} valid={entry['valid']}", flush=True)
    dump(OUT / "predictions.json", predictions)
    summarize(manifest, predictions)
    print("SMOKE_COMPLETE", flush=True)


def summarize(manifest, predictions):
    output = {"n": len(manifest["cases"]), "conditions": {}, "simple_anomaly": {}}
    for condition in CONDITIONS:
        rows = [r for r in predictions if r["condition"] == condition]
        output["conditions"][condition] = {"top1_count": sum(r["top1"] for r in rows),
            "top3_count": sum(r["top3"] for r in rows), "valid": sum(r["valid"] for r in rows),
            "mean_prompt_tokens": float(np.mean([r["prompt_tokens"] for r in rows if r["prompt_tokens"] is not None])),
            "mean_server_seconds": float(np.mean([r["server_seconds"] for r in rows])),
            "by_system": {s: {"n": sum(r["dataset"] == s for r in rows),
                             "top1": sum(r["top1"] for r in rows if r["dataset"] == s)}
                          for s in ("RE2-OB", "RE2-TT")}}
    baseline = []
    for case in manifest["cases"]:
        features = json.loads((OUT / "features" / f"{case['id']}.json").read_text())
        ranks = features["anomaly_ranking"]
        baseline.append({"id": case["id"], "top1": ranks[0] == case["truth"],
                         "top3": case["truth"] in ranks[:3], "ranking": ranks})
    output["simple_anomaly"] = {"top1_count": sum(r["top1"] for r in baseline),
                               "top3_count": sum(r["top3"] for r in baseline)}
    output["paired_rule_vs"] = {}
    for comparator in ("cards_only", "all_calls", "random_selected"):
        pairs = [(next(r["top1"] for r in predictions if r["id"] == c["id"] and r["condition"] == "rule_selected"),
                  next(r["top1"] for r in predictions if r["id"] == c["id"] and r["condition"] == comparator))
                 for c in manifest["cases"]]
        output["paired_rule_vs"][comparator] = {"wins": sum(a and not b for a, b in pairs),
            "losses": sum(b and not a for a, b in pairs), "ties": sum(a == b for a, b in pairs)}
    dump(OUT / "simple-anomaly.json", baseline)
    dump(OUT / "summary.json", output)
    print("SUMMARY " + json.dumps(output), flush=True)


def sanity():
    """Post-hoc execution check only; never merged into the preregistered 12 cases."""
    destination = OUT / "posthoc-synthetic-sanity.json"
    if destination.exists():
        raise FileExistsError("Preserve the first sanity results")
    records = []
    for cause in ("S02", "S05"):
        cards = [{"id": f"S{i:02d}", "metrics": [["cpu", 100 if f"S{i:02d}" == cause else 0,
                  "up" if f"S{i:02d}" == cause else "flat"]], "missing_metrics": 0,
                  "trace": [100, 100, 1]} for i in range(1, 7)]
        request = request_for({"cards": cards, "calls": {"cards_only": []}}, "cards_only")
        response = api("/api/chat", request)
        ranking = parse_ranking(response, [card["id"] for card in cards])
        records.append({"expected": cause, "ranking": ranking, "correct": ranking[0] == cause,
                        "request": request, "response": response})
    dump(destination, {"purpose": "post-hoc synthetic sanity; not benchmark evidence", "cases": records})
    print(f"SANITY_COMPLETE correct={sum(r['correct'] for r in records)}/2")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "run", "self-check", "sanity"])
    args = parser.parse_args()
    self_check()
    if args.phase == "prepare":
        prepare()
    elif args.phase == "run":
        run()
    elif args.phase == "sanity":
        sanity()
    else:
        print("SELF_CHECK_PASSED")
