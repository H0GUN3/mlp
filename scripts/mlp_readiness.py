"""Frozen split, common evaluation and reference-component training readiness."""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import inspect
import json
from pathlib import Path
import random
import time

import numpy as np
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "research/mlp_prerequisites"
DATA = BASE / "data/rcaeval"
SYSTEMS = ("RE2-OB", "RE2-TT")
FAMILIES = ("cpu", "mem", "latency-50", "latency-90", "workload", "error")
SEEDS = (11, 23, 37)
NON_SERVICE_NODES = frozenset({
    "BlackHoleCluster", "PassthroughCluster",
    "InboundPassthroughClusterIpv4", "InboundPassthroughClusterIpv6",
})
SCRIPT_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def group(record):
    return (record["dataset"], record["root_cause_service"], record["fault"])


def validate_split(manifest):
    rows = manifest["cases"]
    assert len(rows) == len({r["case"] for r in rows}) == 180
    assert Counter(r["partition"] for r in rows) == {
        "train": 108, "validation": 36, "test": 36}
    owners = defaultdict(set)
    repeats = defaultdict(set)
    for row in rows:
        owners[group(row)].add(row["partition"])
        repeats[group(row)].add(row["repetition"])
        assert not row["previously_developed"] or row["partition"] == "train"
    assert len(owners) == 60
    assert all(len(parts) == 1 for parts in owners.values())
    assert all(values == {1, 2, 3} for values in repeats.values())
    assert sum(r["previously_developed"] for r in rows) == 36
    for system in SYSTEMS:
        roots = {r["root_cause_service"] for r in rows if r["dataset"] == system}
        for part, count in (("train", 54), ("validation", 18), ("test", 18)):
            subset = [r for r in rows if r["dataset"] == system and r["partition"] == part]
            assert len(subset) == count
            assert {r["root_cause_service"] for r in subset} == roots
            expected_per_fault = 9 if part == "train" else 3
            assert set(Counter(r["fault"] for r in subset).values()) == {expected_per_fault}


def prepare():
    target = OUT / "split.json"
    if target.exists():
        raise FileExistsError("Split is frozen; never overwrite it")
    smoke = json.loads((BASE / "research/smoke/manifest.json").read_text())
    developed = {c for r in smoke["cases"] for c in r["reserved_development_cases"]}
    fields = ["case", "dataset", "root_cause_service", "fault", "repetition", "inject_time"]
    rows = [r for r in pq.read_table(DATA / "cases.parquet", columns=fields).to_pylist()
            if r["dataset"] in SYSTEMS]
    groups = defaultdict(list)
    for row in rows:
        groups[group(row)].append(row)
    dev_groups = {group(r) for r in rows if r["case"] in developed}
    assert len(dev_groups) == 12
    rng = random.Random(20261012)
    for attempt in range(1, 10001):
        assignment = {key: "train" for key in groups}
        for system in SYSTEMS:
            for fault in sorted({r["fault"] for r in rows}):
                available = sorted(key for key in groups
                                   if key[0] == system and key[2] == fault and key not in dev_groups)
                assert len(available) == 4
                rng.shuffle(available)
                assignment[available[0]] = "validation"
                assignment[available[1]] = "test"
        balanced = all(
            {key[1] for key, value in assignment.items() if key[0] == system and value == part}
            == {key[1] for key in groups if key[0] == system}
            for system in SYSTEMS for part in ("train", "validation", "test")
        )
        if balanced:
            break
    else:
        raise ValueError("No metadata-balanced group split found")
    manifest = {
        "seed": 20261012, "metadata_only_assignment_attempt": attempt,
        "protocol_sha256": sha(OUT / "PROTOCOL.md"),
        "index_sha256": sha(DATA / "cases.parquet"),
        "smoke_manifest_sha256": sha(BASE / "research/smoke/manifest.json"),
        "cases": [{**r, "partition": assignment[group(r)],
                   "previously_developed": r["case"] in developed}
                  for r in sorted(rows, key=lambda r: r["case"])],
    }
    validate_split(manifest)
    save_new(target, manifest)
    save_new(OUT / "split.lock.json", {"sha256": sha(target)})
    print(f"SPLIT_PASS train=108 validation=36 test=36 groups=60 attempt={attempt}", flush=True)


def load_split():
    path = OUT / "split.json"
    assert sha(path) == json.loads((OUT / "split.lock.json").read_text())["sha256"]
    manifest = json.loads(path.read_text())
    assert manifest["protocol_sha256"] == sha(OUT / "PROTOCOL.md")
    assert manifest["index_sha256"] == sha(DATA / "cases.parquet")
    assert manifest["smoke_manifest_sha256"] == sha(BASE / "research/smoke/manifest.json")
    validate_split(manifest)
    return manifest


def allow_read(case, manifest):
    row = next((r for r in manifest["cases"] if r["case"] == case), None)
    if row is None or row["partition"] not in ("train", "validation"):
        raise PermissionError(f"Incident is not available to this run: {case}")


def rank_metrics(scores, targets, present):
    scores, targets, present = np.asarray(scores), np.asarray(targets), np.asarray(present, bool)
    if scores.ndim != 2 or present.shape != scores.shape or targets.shape != (len(scores),):
        raise ValueError("Invalid ranking shapes")
    if not np.issubdtype(targets.dtype, np.integer):
        raise ValueError("Targets must be integer class indices")
    results = []
    for values, truth, mask in zip(scores, targets, present):
        if truth == -1:
            continue
        if truth < 0 or truth >= len(values) or not mask[truth]:
            raise ValueError("Root missing from candidate set")
        if not np.isfinite(values[mask]).all():
            raise ValueError("Non-finite candidate score")
        higher = int(np.sum(values[mask] > values[truth]))
        ties = int(np.sum(values[mask] == values[truth]))
        results.append([min(max(k - higher, 0), ties) / ties for k in (1, 3)]
                       + [sum(1 / (higher + i) for i in range(1, ties + 1)) / ties])
    if not results:
        raise ValueError("No fault incidents to score")
    means = np.mean(results, axis=0)
    return {"cases": len(results), "top1": float(means[0]),
            "top3": float(means[1]), "mrr": float(means[2])}


def selected_epoch(validation_losses):
    if not validation_losses or not np.isfinite(validation_losses).all():
        raise ValueError("Invalid validation loss history")
    return int(np.argmin(validation_losses))


def train_scaler(x, present):
    values = x[present]
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Invalid training features")
    center, scale = values.mean(axis=0), values.std(axis=0)
    scale[scale < 1e-8] = 1.0
    return center, scale


def change(normal, fault):
    a, b = normal[np.isfinite(normal)], fault[np.isfinite(fault)]
    if min(len(a), len(b)) < 20:
        return 0.0, 0.0
    center = float(np.median(a))
    q25, q75 = np.quantile(a, [0.25, 0.75])
    delta = (float(np.median(b)) - center) / max(float(q75 - q25), abs(center) * .05, 1e-9)
    return float(np.sign(delta) * np.log1p(abs(delta))), 1.0


def extract_features(case_path, injection, cache):
    """Only observations and known onset enter; root/fault labels do not."""
    from audit import observed_calls
    metrics = pq.read_table(case_path / "metrics.parquet")
    times = metrics["time"].to_numpy()
    normal = times < injection
    if not normal.any() or normal.all():
        raise ValueError("Empty observation window")
    durations = [max(float(np.ptp(times[m])), 1.0) for m in (normal, ~normal)]
    per_service = defaultdict(lambda: np.zeros(17, dtype=np.float64))
    for name in metrics.column_names:
        if name == "time":
            continue
        service, family = name.split("_", 1)
        values = per_service[service]
        values[-1] = 1
        if family in FAMILIES:
            column = metrics[name].to_numpy()
            value, valid = change(column[normal], column[~normal])
            i = FAMILIES.index(family) * 2
            values[i:i + 2] = value, valid
    if cache is not None:
        inverse = {v: k for k, v in cache["mapping"].items()}
        trace_stats = {inverse[card["id"]]: card["trace"] for card in cache["cards"]}
        calls = [(inverse[a], inverse[b]) for a, b in cache["calls"]["all_calls"]]
    else:
        traces = pq.read_table(case_path / "traces.parquet", columns=[
            "traceID", "spanID", "parentSpanID", "serviceName", "duration", "startTime"])
        services = np.asarray(traces["serviceName"].to_pylist(), dtype=object)
        ts = traces["startTime"].to_numpy() / 1e6
        duration = traces["duration"].to_numpy()
        trace_stats = {}
        for service in sorted({s for s in services if s}):
            match = services == service
            a, b = duration[match & (ts < injection)], duration[match & (ts >= injection)]
            ratio = None
            if len(a) and len(b) and np.median(a) > 0:
                ratio = round(float(np.median(b) / np.median(a)), 3)
            trace_stats[service] = [len(a), len(b), ratio]
        call_table = traces.select(["traceID", "spanID", "parentSpanID", "serviceName"]).rename_columns(
            ["trace_id", "span_id", "parent_span_id", "service_name"])
        calls, _, _, _ = observed_calls([call_table])
    for service, (before, after, ratio) in trace_stats.items():
        values = per_service[service]
        valid = ratio is not None and np.isfinite(ratio) and ratio > 0
        values[12:] = [np.log1p(before / durations[0]), np.log1p(after / durations[1]),
                       np.log(ratio) if valid else 0, float(valid), 1]
    return {"nodes": {key: value.tolist() for key, value in sorted(per_service.items())},
            "edges": sorted([list(pair) for pair in calls])}


def develop_cache_paths():
    manifest = json.loads((BASE / "research/smoke/manifest.json").read_text())
    paths = {r["case"]: BASE / f"research/smoke/features/{r['id']}.json" for r in manifest["cases"]}
    for r in manifest["cases"]:
        for case in r["reserved_development_cases"]:
            paths.setdefault(case, BASE / f"research/baselines/results/development-features/{case}.json")
    return paths


def feature_digest():
    source = inspect.getsource(change) + inspect.getsource(extract_features)
    source += repr(FAMILIES) + sha(BASE / "scripts/audit.py")
    return hashlib.sha256(source.encode()).hexdigest()


def extract(manifest):
    result = {}
    caches = develop_cache_paths()
    access = []
    version = feature_digest()
    for row in manifest["cases"]:
        if row["partition"] == "test":
            continue
        allow_read(row["case"], manifest)
        path = OUT / "feature_cache" / version / f"{row['case']}.json"
        if path.exists():
            entry = json.loads(path.read_text())
            assert entry["split_sha256"] == sha(OUT / "split.json")
        else:
            cached = None
            if row["case"] in caches:
                loaded = json.loads(caches[row["case"]].read_text())
                cached = loaded.get("features", loaded)
            features = extract_features(DATA / row["case"], row["inject_time"], cached)
            entry = {"features": features, "split_sha256": sha(OUT / "split.json"),
                     "access": {"case": row["case"], "partition": row["partition"],
                                "raw_metrics": True, "raw_traces": cached is None,
                                "trace_cache_sha256": sha(caches[row["case"]])
                                if cached is not None else None}}
            save_new(path, entry)
        result[row["case"]] = entry["features"]
        access.append(entry["access"])
        print(f"FEATURE {len(result)}/144 {row['case']} nodes={len(entry['features']['nodes'])}", flush=True)
    save_new(OUT / "features.json", {"split_sha256": sha(OUT / "split.json"),
                                  "script_sha256": SCRIPT_SHA256, "extractor_sha256": version,
                                  "cases": result, "access": access})
    print("FEATURES_PASS test_raw_access=0", flush=True)


def vectorize(rows, features, vocabulary):
    indices = {s: i for i, s in enumerate(vocabulary)}
    x = np.zeros((len(rows), len(vocabulary), 17), dtype=np.float32)
    present = np.zeros(x.shape[:2], bool)
    targets, edges = [], []
    for i, row in enumerate(rows):
        data = features[row["case"]]
        unknown = set(data["nodes"]) - NON_SERVICE_NODES - set(indices)
        if unknown:
            raise ValueError(f"Unseen services in {row['case']}: {sorted(unknown)}")
        for service, values in data["nodes"].items():
            if service in NON_SERVICE_NODES:
                continue
            x[i, indices[service]] = values
            present[i, indices[service]] = True
        if row["root_cause_service"] in NON_SERVICE_NODES:
            raise ValueError("Proxy cluster cannot be a root-service label")
        targets.append(indices[row["root_cause_service"]])
        observed = {(indices[a], indices[b]) for a, b in data["edges"]
                    if a not in NON_SERVICE_NODES and b not in NON_SERVICE_NODES}
        # GAT self messages preserve local evidence; these are not causal call edges.
        observed.update((indices[s], indices[s]) for s in data["nodes"] if s not in NON_SERVICE_NODES)
        edges.append(sorted(observed))
        assert present[i, targets[-1]]
    return x, np.asarray(targets), present, edges


def train_one(model, train, validation, seed, method, checkpoint):
    import torch
    from torch import nn
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=.0001)
    loss_fn = nn.CrossEntropyLoss()

    def forward(bundle):
        x, y, mask, edges = bundle
        values = model(x, edges=edges) if method == "eadro_gat_common" else model(x)
        if values.shape != mask.shape or not torch.isfinite(values).all():
            raise ValueError("Invalid model logits")
        return values.masked_fill(~mask, -torch.inf)

    history, states = [], []
    started = time.monotonic()
    model.eval()
    with torch.no_grad():
        initial_loss = float(loss_fn(forward(train), train[1]))
    for epoch in range(80):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(forward(train), train[1])
        if not torch.isfinite(loss):
            raise ValueError("Non-finite training loss")
        loss.backward()
        if not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()):
            raise ValueError("Invalid gradient")
        optimizer.step()
        model.eval()
        with torch.no_grad():
            train_loss = float(loss_fn(forward(train), train[1]))
            val_loss = float(loss_fn(forward(validation), validation[1]))
        history.append({"epoch": epoch + 1, "train_loss": train_loss, "validation_loss": val_loss})
        states.append(copy.deepcopy(model.state_dict()))
    chosen = selected_epoch([r["validation_loss"] for r in history])
    model.load_state_dict(states[chosen])
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("xb") as stream:
        torch.save(model.state_dict(), stream)
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    with torch.no_grad():
        raw_train = forward(train).numpy()
        raw_val = forward(validation).numpy()
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.cpu().numpy().tobytes())
    return {
        "seed": seed, "method": method, "selected_epoch": chosen + 1,
        "initial_train_loss": initial_loss, "selected_train_loss": history[chosen]["train_loss"],
        "final_train_loss": history[-1]["train_loss"],
        "selected_validation_loss": history[chosen]["validation_loss"],
        "train": rank_metrics(raw_train, train[1].numpy(), train[2].numpy()),
        "validation": rank_metrics(raw_val, validation[1].numpy(), validation[2].numpy()),
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "state_sha256": digest.hexdigest(), "seconds": time.monotonic() - started,
        "checkpoint": str(checkpoint.relative_to(BASE)),
        "checkpoint_sha256": sha(checkpoint),
        "history": history,
        "validation_rankings": np.argsort(-raw_val, axis=1, kind="stable").tolist(),
        "validation_logits": np.where(validation[2].numpy(), raw_val, 0).tolist(),
    }


def run():
    import torch
    import dgl
    from mlp_reference import DiagMLPCommonInput, EadroGATCommonInput
    if (OUT / "training_results.json").exists():
        raise FileExistsError("Completed results exist; do not overwrite")
    manifest = load_split()
    feature_file = OUT / "features.json"
    if not feature_file.exists():
        extract(manifest)
    feature_artifact = json.loads(feature_file.read_text())
    assert feature_artifact["split_sha256"] == sha(OUT / "split.json")
    assert feature_artifact["extractor_sha256"] == feature_digest()
    features = feature_artifact["cases"]
    assert set(features) == {r["case"] for r in manifest["cases"] if r["partition"] != "test"}
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    results, datasets = [], {}
    for system in SYSTEMS:
        train_rows = [r for r in manifest["cases"] if r["dataset"] == system and r["partition"] == "train"]
        val_rows = [r for r in manifest["cases"] if r["dataset"] == system and r["partition"] == "validation"]
        vocabulary = sorted({s for r in train_rows for s in features[r["case"]]["nodes"]}
                            - NON_SERVICE_NODES)
        a = vectorize(train_rows, features, vocabulary)
        b = vectorize(val_rows, features, vocabulary)
        center, scale = train_scaler(a[0], a[2])
        mask_columns = [1, 3, 5, 7, 9, 11, 15, 16]
        center[mask_columns], scale[mask_columns] = 0, 1
        bundles = []
        for x, y, mask, edges in (a, b):
            standardized = ((x - center) / scale).astype(np.float32)
            standardized[~mask] = 0
            bundles.append((torch.from_numpy(standardized), torch.from_numpy(y),
                            torch.from_numpy(mask), edges))
        counts = np.bincount(a[1], minlength=len(vocabulary)).astype(float)
        prior = rank_metrics(np.tile(counts, (len(val_rows), 1)), b[1], b[2])
        datasets[system] = {"vocabulary": vocabulary, "train_shape": list(a[0].shape),
                            "validation_shape": list(b[0].shape),
                            "train_cases": [r["case"] for r in train_rows],
                            "validation_cases": [r["case"] for r in val_rows],
                            "validation_targets": b[1].tolist(),
                            "validation_present": b[2].tolist(),
                            "scaler_center": center.tolist(), "scaler_scale": scale.tolist(),
                            "train_root_frequency_prior_validation": prior}
        for method, cls in (("diagmlp_common", DiagMLPCommonInput), ("eadro_gat_common", EadroGATCommonInput)):
            for seed in SEEDS:
                torch.manual_seed(seed)
                dgl.seed(seed)
                np.random.seed(seed)
                model = cls(len(vocabulary), 17, hidden_dim=32, dropout=.1)
                checkpoint = OUT / "checkpoints" / f"{system}-{method}-{seed}.pt"
                result = train_one(model, bundles[0], bundles[1], seed, method, checkpoint)
                result["system"] = system
                results.append(result)
                print(f"FIT_PASS {system} {method} seed={seed} epoch={result['selected_epoch']} "
                      f"train_loss={result['initial_train_loss']:.4f}->{result['final_train_loss']:.4f} "
                      f"validation_top1={result['validation']['top1']:.4f}", flush=True)
    test_ids = {r["case"] for r in manifest["cases"] if r["partition"] == "test"}
    test_accesses = len({r["case"] for r in feature_artifact["access"]} & test_ids)
    assert test_accesses == 0
    output = {
        "scope": "adapted reference readiness; validation scores, NOT final test or paper reproduction",
        "versions": {"torch": torch.__version__, "dgl": dgl.__version__, "numpy": np.__version__},
        "split_sha256": sha(OUT / "split.json"), "protocol_sha256": sha(OUT / "PROTOCOL.md"),
        "candidate_contract_sha256": sha(OUT / "CANDIDATE_CONTRACT.md"),
        "excluded_proxy_clusters": {
            case: sorted(set(data["nodes"]) & NON_SERVICE_NODES)
            for case, data in features.items() if set(data["nodes"]) & NON_SERVICE_NODES
        },
        "code_sha256": {p.name: sha(p) for p in [Path(__file__), BASE / "scripts/mlp_reference.py"]},
        "datasets": datasets, "runs": results, "final_test_cases_read": test_accesses,
        "feature_access": feature_artifact["access"],
    }
    save_new(OUT / "training_results.json", output)
    print("READINESS_TRAINING_COMPLETE runs=12 final_test_cases_read=0", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "extract", "run"))
    command = parser.parse_args().command
    if command == "prepare":
        prepare()
    elif command == "extract":
        extract(load_split())
    else:
        run()
