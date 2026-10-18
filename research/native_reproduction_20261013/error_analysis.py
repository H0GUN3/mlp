"""Read-only, bounded checkpoint diagnostic; no training or artifact writes."""
import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import sys

import numpy as np
import pyarrow.parquet as pq
import torch

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
readiness = importlib.import_module("scripts.mlp_readiness")
reference = importlib.import_module("scripts.mlp_reference")
FAMILIES, change = readiness.FAMILIES, readiness.change
train_scaler, vectorize = readiness.train_scaler, readiness.vectorize
DiagMLPCommonInput = reference.DiagMLPCommonInput

ART = BASE / "research/mlp_prerequisites"
CASES = tuple(f"re2tt_ts-train-service_delay_{n}" for n in (1, 2, 3))
SERVICES = ("ts-train-service", "ts-travel-service")


def load(name):
    return json.loads((ART / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay():
    split, artifact, results = load("split.json"), load("features.json"), load("training_results.json")
    assert sha(ART / "split.json") == artifact["split_sha256"] == results["split_sha256"]
    siblings = [next(r for r in split["cases"] if r["case"] == case) for case in CASES]
    assert all(r["partition"] == "validation" and r["root_cause_service"] == SERVICES[0]
               for r in siblings)
    for name, digest in results["code_sha256"].items():
        assert sha(BASE / "scripts" / name) == digest, name
    dataset = results["datasets"]["RE2-TT"]
    vocabulary = dataset["vocabulary"]
    features = artifact["cases"]
    rows = [r for r in split["cases"]
            if r["dataset"] == "RE2-TT" and r["partition"] == "validation"]
    assert [r["case"] for r in rows] == dataset["validation_cases"]
    x, y, mask, _ = vectorize(rows, features, vocabulary)
    assert y.tolist() == dataset["validation_targets"]
    assert mask.tolist() == dataset["validation_present"]
    train_rows = [r for r in split["cases"]
                  if r["dataset"] == "RE2-TT" and r["partition"] == "train"]
    assert [r["case"] for r in train_rows] == dataset["train_cases"]
    tx, _, tm, _ = vectorize(train_rows, features, vocabulary)
    center, scale = train_scaler(tx, tm)
    columns = [1, 3, 5, 7, 9, 11, 15, 16]
    center[columns], scale[columns] = 0, 1
    assert np.array_equal(center, np.asarray(dataset["scaler_center"], dtype=np.float32))
    assert np.array_equal(scale, np.asarray(dataset["scaler_scale"], dtype=np.float32))
    standardized = ((x - center) / scale).astype(np.float32)
    standardized[~mask] = 0
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    runs = []
    for run in results["runs"]:
        if run["system"] != "RE2-TT" or run["method"] != "diagmlp_common":
            continue
        checkpoint = BASE / run["checkpoint"]
        assert checkpoint.parent == ART / "checkpoints"
        assert sha(checkpoint) == run["checkpoint_sha256"]
        model = DiagMLPCommonInput(len(vocabulary), 17, hidden_dim=32, dropout=.1)
        model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
        model.eval()
        with torch.no_grad():
            logits = model(torch.from_numpy(standardized)).numpy()
        saved = np.asarray(run["validation_logits"])
        error = float(np.max(np.abs(logits[mask] - saved[mask])))
        np.testing.assert_allclose(logits[mask], saved[mask], rtol=0, atol=1e-6)
        rankings = np.argsort(-np.where(mask, logits, -np.inf), axis=1, kind="stable")
        assert rankings.tolist() == run["validation_rankings"]
        case_runs = {}
        for case in CASES:
            i = dataset["validation_cases"].index(case)
            case_runs[case] = {
                "target_index": int(y[i]), "target_rank": int(np.where(rankings[i] == y[i])[0][0] + 1),
                "top3": [[vocabulary[j], float(logits[i, j])] for j in rankings[i, :3]],
                "train_logit": float(logits[i, vocabulary.index(SERVICES[0])]),
                "travel_logit": float(logits[i, vocabulary.index(SERVICES[1])]),
            }
        runs.append({"seed": run["seed"], "epoch": run["selected_epoch"],
                     "checkpoint_sha256": run["checkpoint_sha256"],
                     "max_abs_replay_error": error, "cases": case_runs})
    assert {r["seed"] for r in runs} == {11, 23, 37}
    inputs = {}
    for case in CASES:
        i = dataset["validation_cases"].index(case)
        inputs[case] = {
            "validation_row_index": i, "present_count": int(mask[i].sum()),
            "absent": [s for j, s in enumerate(vocabulary) if not mask[i, j]],
            "services": {s: {"index": vocabulary.index(s),
                              "present": bool(mask[i, vocabulary.index(s)]),
                              "raw17": features[case]["nodes"][s],
                              "standardized17": standardized[i, vocabulary.index(s)].tolist()}
                         for s in SERVICES},
            "relevant_edges": [edge for edge in features[case]["edges"]
                               if any(s in edge for s in SERVICES)],
        }
    return {"split_sha256": results["split_sha256"], "validation_gate": siblings,
            "replay": runs, "inputs": inputs}, siblings, features


def summary(values):
    finite = values[np.isfinite(values)]
    return {"count": len(values), "finite": len(finite),
            "median": float(np.median(finite)) if len(finite) else None,
            "p90": float(np.quantile(finite, .9)) if len(finite) else None}


def raw_evidence(rows, features):
    output = {}
    for row in rows:
        case, onset = row["case"], row["inject_time"]
        assert case in CASES and row["partition"] == "validation"
        path = BASE / "data/rcaeval" / case
        names = pq.read_schema(path / "metrics.parquet").names
        columns = ["time"] + [name for name in names
                              if any(name.startswith(s + "_") for s in SERVICES)]
        metrics = pq.read_table(path / "metrics.parquet", columns=columns)
        times = metrics["time"].to_numpy()
        normal = times < onset
        windows = [max(float(np.ptp(times[m])), 1.) for m in (normal, ~normal)]
        traces = pq.read_table(path / "traces.parquet", columns=[
            "traceID", "spanID", "parentSpanID", "serviceName", "duration",
            "startTime", "startTimeMillis", "operationName", "methodName", "statusCode"])
        services = np.asarray(traces["serviceName"].to_pylist(), dtype=object)
        start = traces["startTime"].to_numpy() / 1e6
        before = start < onset
        duration = traces["duration"].to_numpy()
        records = traces.select(["traceID", "spanID", "parentSpanID", "serviceName"]).to_pylist()
        parents = {(r["traceID"], r["spanID"]): r["serviceName"] for r in records}
        duplicate_keys = len(records) - len(parents)
        pairs = Counter()
        unresolved = 0
        for r in records:
            if r["serviceName"] not in SERVICES:
                continue
            parent = parents.get((r["traceID"], r["parentSpanID"]))
            if parent is None:
                unresolved += 1
            elif parent != r["serviceName"]:
                pairs[(parent, r["serviceName"])] += 1
        details = {}
        for service in SERVICES:
            reconstructed = np.zeros(17)
            reconstructed[16] = 1
            metric_stats = {}
            for family in (*FAMILIES, "diskio", "socket"):
                name = service + "_" + family
                if name not in columns:
                    metric_stats[family] = {"column_present": False}
                    continue
                column = metrics[name].to_numpy()
                a, b = column[normal], column[~normal]
                delta, valid = change(a, b)
                metric_stats[family] = {"column_present": True, "before": summary(a),
                                        "after": summary(b), "change": delta, "valid": valid}
                if family in FAMILIES:
                    j = FAMILIES.index(family) * 2
                    reconstructed[j:j + 2] = delta, valid
            match = services == service
            a, b = duration[match & before], duration[match & ~before]
            ratio = round(float(np.median(b) / np.median(a)), 3)
            assert ratio > 0 and np.isfinite(ratio)
            reconstructed[12:16] = [np.log1p(len(a) / windows[0]),
                                    np.log1p(len(b) / windows[1]), np.log(ratio), 1.]
            np.testing.assert_allclose(reconstructed, features[case]["nodes"][service],
                                       rtol=0, atol=1e-12)
            operations = np.asarray(traces["operationName"].to_pylist(), dtype=object)
            methods = np.asarray(traces["methodName"].to_pylist(), dtype=object)
            statuses = np.asarray(traces["statusCode"].to_pylist(), dtype=object)
            groups = Counter(zip(operations[match], methods[match]))
            operation_stats = []
            for (operation, method), count in groups.most_common(12):
                selected = match & (operations == operation) & (methods == method)
                status_counts = {str(k): v for k, v in Counter(statuses[selected]).items()}
                assert sum(status_counts.values()) == count
                operation_stats.append({
                    "operation": operation, "method": method, "count": count,
                    "before": summary(duration[selected & before]),
                    "after": summary(duration[selected & ~before]),
                    "status_counts": status_counts,
                })
            details[service] = {"metrics": metric_stats, "trace_before": summary(a),
                                "trace_after": summary(b), "trace_median_ratio_rounded": ratio,
                                "operation_group_count": len(groups), "top_operations": operation_stats,
                                "raw17_reconstruction_max_error": float(np.max(np.abs(
                                    reconstructed - features[case]["nodes"][service])))}
        output[case] = {
            "metric_window_samples": [int(normal.sum()), int((~normal).sum())],
            "metric_window_seconds": windows,
            "startTime_vs_startTimeMillis_max_seconds": float(np.max(np.abs(
                start - traces["startTimeMillis"].to_numpy() / 1000))),
            "trace_rows": len(records), "duplicate_trace_span_keys": duplicate_keys,
            "unresolved_selected_parent_count": unresolved,
            "selected_cross_service_parent_pairs": [[a, b, count] for (a, b), count in pairs.most_common(12)],
            "services": details,
        }
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true")
    args = parser.parse_args()
    report, rows, features = replay()
    print("CHECKPOINT_REPLAY_PASS seeds=11,23,37 validation_rows=18", flush=True)
    if args.raw:
        report["raw_evidence"] = raw_evidence(rows, features)
    text = json.dumps(report, allow_nan=False)
    assert len(text) < 80000, "Diagnostic output exceeded bound"
    print(text)
