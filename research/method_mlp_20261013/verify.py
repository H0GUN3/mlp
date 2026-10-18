"""Replay all own checkpoints and independently rescore the frozen validation set."""
from collections import defaultdict
import json

import numpy as np
import torch

from ranker import Ranker
from train import HERE, NATIVE, SEEDS, SETTINGS, dump, load_data, sha, source_hashes


def independent_scores(logits, labels, events):
    credit, unique = [], []
    grouped = defaultdict(list)
    for row, label, event in zip(logits, labels, events):
        if not np.isfinite(row).all():
            raise AssertionError("Nonfinite logits")
        top = np.flatnonzero(row == max(row))
        hit = 1. / len(top) if int(label) in top else 0.
        credit.append(hit)
        unique.append(float(hit == 1.))
        grouped[str(event)].append(hit)
    if not credit:
        raise AssertionError("Empty validation partition")
    return {"window_top1": float(np.mean(credit)),
            "event_balanced_top1": float(np.mean([np.mean(v) for v in grouped.values()])),
            "unique_window_top1": float(np.mean(unique)),
            "windows": len(credit), "incidents": len(grouped)}


def verify_run(system, mode, seed, bundle):
    data, meta, provenance = bundle
    folder = HERE / "runs" / system / mode / ("seed_" + str(seed))
    report = json.loads((folder / "report.json").read_text())
    assert report["status"] == "complete"
    for name, digest in report["artifact_hashes"].items():
        assert "/" not in name and sha(folder / name) == digest, "Artifact hash mismatch"
    config = json.loads((folder / "config.json").read_text())
    assert (config["system"], config["mode"], config["seed"]) == (system, mode, seed)
    assert config["settings"] == SETTINGS and config["source_hashes"] == source_hashes()
    assert config["input_hashes"] == provenance and config["services"] == meta["services"]
    assert config["test_evaluated"] is False and config["rcaeval_access"] is False
    all_train = np.flatnonzero(data["partition"] == "train")
    train = np.flatnonzero((data["partition"] == "train") & (data["labels"] >= 0))
    val = np.flatnonzero((data["partition"] == "validation") & (data["labels"] >= 0))
    assert config["normalization_train_indices"] == data["indices"][all_train].tolist()
    assert config["train_indices"] == data["indices"][train].tolist()
    assert config["validation_indices"] == data["indices"][val].tolist()
    with np.load(folder / "standardizer.npz", allow_pickle=False) as archive:
        stats = {name: archive[name] for name in archive.files}
    for feature in range(data["x"].shape[-1]):
        values = data["x"][all_train, :, feature][data["mask"][all_train, :, feature]].astype(np.float64)
        mean = float(values.mean()) if len(values) else 0.
        std = float(values.std()) if len(values) else 1.
        if std <= 1e-12:
            std = 1.
        assert stats["counts"][feature] == len(values)
        np.testing.assert_allclose(stats["mean"][feature], mean, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(stats["std"][feature], std, rtol=1e-12, atol=1e-12)
    x = np.where(data["mask"][val],
                 (data["x"][val].astype(np.float64) - stats["mean"]) / stats["std"], 0).astype(np.float32)
    checkpoint = torch.load(folder / "checkpoint.pt", map_location="cpu")
    assert checkpoint["config_sha256"] == sha(folder / "config.json")
    model = Ranker(config["feature_dim"], relative=(mode == "relative"))
    model.load_state_dict(checkpoint["state_dict"])
    assert sum(p.numel() for p in model.parameters()) == config["parameter_count"] == report["parameter_count"]
    model.eval()
    with torch.no_grad():
        replay = model(torch.from_numpy(x), torch.from_numpy(data["mask"][val]),
                       torch.from_numpy(data["coverage"][val])).numpy()
    with np.load(folder / "predictions.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["indices"], data["indices"][val])
        np.testing.assert_array_equal(saved["labels"], data["labels"][val])
        np.testing.assert_array_equal(saved["event_ids"], data["event_ids"][val])
        np.testing.assert_array_equal(saved["logits"], replay)
    measured = independent_scores(replay, data["labels"][val], data["event_ids"][val])
    for key, value in measured.items():
        assert np.isclose(value, report["metrics"][key], rtol=0, atol=1e-12), key
    history = json.loads((folder / "history.json").read_text())
    best = min(history, key=lambda row: row["validation_event_ce"])
    assert report["epochs_run"] == len(history) <= SETTINGS["epochs"]
    assert best["epoch"] == report["best_epoch"]
    assert best["validation_event_ce"] == report["best_event_ce"]
    assert report["train_windows"] == len(train)
    return {"system": system, "method": mode, "seed": seed, "metrics": measured,
            "parameter_count": report["parameter_count"], "best_epoch": report["best_epoch"],
            "epochs_run": report["epochs_run"], "seconds": report["seconds"],
            "report_sha256": sha(folder / "report.json")}, checkpoint["initial_state_dict"]


def external_reference(system, method, seed, bundle):
    data, meta, _ = bundle
    gate = json.loads((NATIVE / (system.lower() + "200_verification.json")).read_text())
    assert gate["status"] == "PASS" and not gate["failures"]
    path = NATIVE / "calibration200" / system / method / ("seed_" + str(seed)) / "validation_predictions.npz"
    with np.load(path, allow_pickle=False) as archive:
        labels, ids = archive["labels"], archive["indices"]
        keep = labels >= 0
        own = (data["partition"] == "validation") & (data["labels"] >= 0)
        assert set(ids[keep].tolist()) == set(data["indices"][own].tolist())
        truth = dict(zip(data["indices"][own].tolist(), data["labels"][own].tolist()))
        assert all(truth[int(i)] == int(label) for i, label in zip(ids[keep], labels[keep]))
        events = np.asarray([meta["windows"][int(i)]["event_id"] for i in ids[keep]])
        result = independent_scores(archive["root_logits"][keep], labels[keep], events)
    return {"system": system, "method": method + "_external_reconstruction", "seed": seed,
            "metrics": result, "predictions_sha256": sha(path)}


def main():
    torch.set_num_threads(SETTINGS["threads"])
    torch.set_num_interop_threads(1)
    fixture = independent_scores(np.array([[1., 1.], [0., 2.], [3., 0.]]),
                                 np.array([0, 0, 0]), np.array(["a", "a", "b"]))
    assert fixture["window_top1"] == .5 and fixture["event_balanced_top1"] == .625
    results, references = [], []
    for system in ("SN", "TT"):
        bundle = load_data(system)
        for seed in SEEDS:
            paired = {}
            for mode in ("local", "relative"):
                result, initial = verify_run(system, mode, seed, bundle)
                results.append(result)
                paired[mode] = initial
            assert paired["local"].keys() == paired["relative"].keys()
            assert all(torch.equal(paired["local"][key], paired["relative"][key]) for key in paired["local"])
            for method in ("diagmlp", "eadro"):
                references.append(external_reference(system, method, seed, bundle))
    aggregates = []
    for system in ("SN", "TT"):
        for method in ("local", "relative", "diagmlp_external_reconstruction", "eadro_external_reconstruction"):
            selected = [r for r in results + references if r["system"] == system and r["method"] == method]
            assert len(selected) == 3 and {r["seed"] for r in selected} == set(SEEDS)
            aggregates.append({"system": system, "method": method,
                               "event_balanced_top1": float(np.mean([r["metrics"]["event_balanced_top1"] for r in selected])),
                               "window_top1": float(np.mean([r["metrics"]["window_top1"] for r in selected]))})
    deltas = {}
    for system in ("SN", "TT"):
        pair = {r["method"]: r for r in aggregates if r["system"] == system}
        deltas[system] = pair["relative"]["event_balanced_top1"] - pair["local"]["event_balanced_top1"]
    report = {"status": "PASS", "checks": ["frozen_splits_labels_candidates", "same_feature_inputs",
              "training_only_standardization", "paired_initial_weights_and_parameter_counts",
              "saved_checkpoint_replay", "independent_tie_neutral_scoring", "validation_ce_selection",
              "no_test_evaluation"], "runs": results, "external_references": references,
              "aggregates": aggregates, "relative_minus_local_event_top1": deltas,
              "both_systems_improved": all(value > 0 for value in deltas.values()),
              "limitations": ["Validation windows may share injections with training.",
                              "Zero baseline slots have inactive input connections.",
                              "External references differ in preprocessing and joint learning objective.",
                              "This is not evidence of novelty, causal correctness or unseen-incident generalization."]}
    dump(HERE / "verification.json", report)
    lines = ["# 자체 기준선·제안 모델 검증 결과", "",
             "기준선과 제안 모델 각각 SN/TT×3 seed, 총12회를 검증했다. 최종시험은 평가하지 않았다.", "",
             "| 자료 | 모델 | 사건 균등 Top-1 | 창 단위 Top-1 |",
             "|---|---|---:|---:|"]
    names = {"local": "자체 기준선", "relative": "자체 제안 모델",
             "diagmlp_external_reconstruction": "DiagMLP 복원본(외부 참고)",
             "eadro_external_reconstruction": "Eadro 복원본(외부 참고)"}
    for row in aggregates:
        lines.append("| {} | {} | {:.2%} | {:.2%} |".format(
            row["system"], names[row["method"]], row["event_balanced_top1"], row["window_top1"]))
    lines += ["", "## 자체 기준선 대비 제안 모델 차이",
              *["- {}: {:+.2f} percentage points".format(system, value * 100) for system, value in deltas.items()],
              "", "모든 앱에서 개선됐는지: " + ("예" if report["both_systems_improved"] else "아니오"),
              "", "## 해석 한계",
              "- 검증 결과이며, 같은 주입 사건의 다른 창이 학습에 포함될 수 있다.",
              "- 논문 모델을 개조한 실험이 아니다. 외부 복원본은 전처리·학습 목적이 달라 별도 참고다.",
              "- 자체 기준선 대비 향상만으로 선행법 우위·인과 추론·미관측 사고 일반화·신규성을 주장하지 않는다.",
              "- 호출 이웃 특징, 논문 모델 수정, RCAEval 특정 사건 재검증, 최종시험 채점은 하지 않았다.",
              "- 개별 seed·사건별 점수와 입력/코드/산출물 해시는 verification.json과 각 run 파일에 보존했다."]
    (HERE / "결과.md").write_text("\n".join(lines) + "\n")
    print("OWN_METHOD_VERIFIED", json.dumps(deltas), flush=True)


if __name__ == "__main__":
    main()
