"""Replay saved reference checkpoints without reopening any raw incidents."""
from collections import Counter, defaultdict
import hashlib
import json

import numpy as np
import torch

from mlp_readiness import BASE, OUT, load_split, save_new, sha, vectorize
from mlp_reference import DiagMLPCommonInput, EadroGATCommonInput


def independent_metrics(logits, targets, present):
    total = np.zeros(3)
    for values, root, mask in zip(logits, targets, present):
        ordered = sorted(values[mask], reverse=True)
        positions = [i + 1 for i, value in enumerate(ordered) if value == values[root]]
        assert positions
        total += [sum(i <= 1 for i in positions) / len(positions),
                  sum(i <= 3 for i in positions) / len(positions),
                  sum(1 / i for i in positions) / len(positions)]
    return dict(zip(("top1", "top3", "mrr"), (total / len(targets)).tolist()))


def main():
    manifest = load_split()
    result = json.loads((OUT / "training_results.json").read_text())
    features = json.loads((OUT / "features.json").read_text())
    expected = {r["case"] for r in manifest["cases"] if r["partition"] != "test"}
    test_ids = {r["case"] for r in manifest["cases"] if r["partition"] == "test"}
    accesses = Counter(r["case"] for r in result["feature_access"])
    assert set(accesses) == expected and set(accesses.values()) == {1}
    assert not set(accesses) & test_ids
    assert set(features["cases"]) == expected
    assert result["split_sha256"] == sha(OUT / "split.json")
    assert result["candidate_contract_sha256"] == sha(OUT / "CANDIDATE_CONTRACT.md")
    for name, digest in result["code_sha256"].items():
        assert sha(BASE / "scripts" / name) == digest
    assert len(result["runs"]) == 12
    torch.set_num_threads(2)
    summaries = []
    grouped = defaultdict(list)
    for run in result["runs"]:
        system, method = run["system"], run["method"]
        dataset = result["datasets"][system]
        history = run["history"]
        expected_epoch = min(range(len(history)), key=lambda i: history[i]["validation_loss"]) + 1
        assert run["selected_epoch"] == expected_epoch
        assert run["final_train_loss"] < run["initial_train_loss"]
        checkpoint = BASE / run["checkpoint"]
        assert checkpoint.resolve().is_relative_to((OUT / "checkpoints").resolve())
        assert sha(checkpoint) == run["checkpoint_sha256"]
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        digest = hashlib.sha256()
        for name, tensor in sorted(state.items()):
            digest.update(name.encode())
            digest.update(tensor.numpy().tobytes())
        assert digest.hexdigest() == run["state_sha256"]
        cls = DiagMLPCommonInput if method == "diagmlp_common" else EadroGATCommonInput
        model = cls(len(dataset["vocabulary"]), 17, hidden_dim=32, dropout=.1)
        model.load_state_dict(state)
        model.eval()
        rows = [r for r in manifest["cases"] if r["dataset"] == system and r["partition"] == "validation"]
        x, targets, present, edges = vectorize(rows, features["cases"], dataset["vocabulary"])
        x = ((x - np.asarray(dataset["scaler_center"])) / np.asarray(dataset["scaler_scale"])).astype(np.float32)
        x[~present] = 0
        with torch.no_grad():
            inputs = torch.from_numpy(x)
            logits = (model(inputs, edges=edges) if method == "eadro_gat_common" else model(inputs)).numpy()
        saved = np.asarray(run["validation_logits"])
        np.testing.assert_allclose(logits[present], saved[present], atol=1e-6, rtol=1e-5)
        measured = independent_metrics(saved, targets, present)
        for key, value in measured.items():
            assert abs(value - run["validation"][key]) < 1e-12
        summaries.append({"system": system, "method": method, "seed": run["seed"],
                          "selected_epoch": expected_epoch, **measured})
        grouped[(system, method)].append(run)
    comparison = []
    for (system, method), runs in sorted(grouped.items()):
        assert {run["seed"] for run in runs} == {11, 23, 37}
        comparison.append({
            "system": system, "method": method, "seeds": len(runs),
            "validation_cases": result["datasets"][system]["validation_shape"][0],
            "nodes": len(result["datasets"][system]["vocabulary"]),
            "parameters": runs[0]["parameter_count"],
            "top1_mean": float(np.mean([r["validation"]["top1"] for r in runs])),
            "top1_min": min(r["validation"]["top1"] for r in runs),
            "top1_max": max(r["validation"]["top1"] for r in runs),
            "top3_mean": float(np.mean([r["validation"]["top3"] for r in runs])),
            "mrr_mean": float(np.mean([r["validation"]["mrr"] for r in runs])),
            "initial_train_loss_mean": float(np.mean([r["initial_train_loss"] for r in runs])),
            "final_train_loss_mean": float(np.mean([r["final_train_loss"] for r in runs])),
            "selected_epochs": [r["selected_epoch"] for r in runs],
        })
    artifact = {
        "status": "passed",
        "comparison": comparison,
        "prior_validation": {
            system: data["train_root_frequency_prior_validation"]
            for system, data in result["datasets"].items()
        },
        "excluded_proxy_clusters": result["excluded_proxy_clusters"],
        "checks": ["split_lock", "unique_allowed_access", "test_access_disjoint",
                   "code_hash", "validation_only_epoch_selection", "training_loss_decrease",
                   "checkpoint_hash", "checkpoint_prediction_replay", "independent_rank_rescore"],
        "trained_runs_verified": len(summaries),
        "observed_feature_accesses": len(accesses),
        "final_test_accesses": len(set(accesses) & test_ids),
        "runs": summaries,
    }
    path = OUT / "verification.json"
    if path.exists():
        assert json.loads(path.read_text()) == artifact, "Stored verification differs"
    else:
        save_new(path, artifact)
    print("VERIFICATION_PASS checkpoints=12 rescored=12 final_test_accesses=0", flush=True)


if __name__ == "__main__":
    main()
