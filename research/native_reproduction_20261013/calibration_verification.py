#!/usr/bin/env python3
"""Independent verification of parameterized native calibration artifacts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from sn50_verification import independently_score, sha256

HERE = Path(__file__).resolve().parent
SEEDS = (11, 23, 37)
KINDS = ("eadro", "diagmlp")
HASHED = ("scaler.npz", "validation_predictions.npz", "history.json",
          "config.json", "split.json", "checkpoint.pt")
COUNTS = {"SN": {"train": 316, "validation": 78, "test": 169, "unassigned": 1},
          "TT": {"train": 3256, "validation": 813, "test": 1744, "unassigned": 1}}


def history_complete(history, epochs):
    return len(history) == epochs and all(
        isinstance(row, dict) and row.get("epoch") == index
        for index, row in enumerate(history, 1))


def exact(actual, expected):
    return actual == expected


def check(system, epochs, prefix):
    root = HERE / ("calibration" + str(epochs)) / system
    failures, runs, common = [], [], {}

    def require(run, condition, label, detail=None):
        item = {"check": label, "passed": bool(condition)}
        if detail is not None:
            item["detail"] = detail
        run["checks"].append(item)
        if not condition:
            failures.append(f"{run['kind']}/seed_{run['seed']}: {label}")

    for kind in KINDS:
        for seed in SEEDS:
            directory = root / kind / f"seed_{seed}"
            run = {"kind": kind, "seed": seed,
                   "path": str(directory.relative_to(HERE)), "checks": [],
                   "score_recomputations": []}
            runs.append(run)
            try:
                summary, config, history, split = [
                    json.loads((directory / name).read_text())
                    for name in ("summary.json", "config.json", "history.json", "split.json")]
                hashes = {name: sha256(directory / name) for name in HASHED
                          if (directory / name).is_file()}
            except Exception as error:
                failures.append(f"{kind}/seed_{seed}: incomplete/unreadable run: {error}")
                continue
            require(run, summary.get("status") == "passed", "summary status passed")
            require(run, summary.get("epochs_completed") == epochs and
                    config.get("effective_epochs") == epochs and
                    config.get("effective_options", {}).get("epochs") == epochs,
                    "requested and completed epochs match")
            require(run, summary.get("test_evaluated") is False and
                    config.get("test_evaluated") is False, "test_evaluated false")
            require(run, summary.get("checkpoint_replay") ==
                    "bitwise equal validation logits, labels, indices and loss",
                    "checkpoint replay evidence")
            for name in HASHED:
                require(run, name in hashes, f"{name} exists")
                require(run, exact(summary.get("artifact_hashes", {}).get(name), hashes.get(name)),
                        f"{name} SHA256 matches summary")
            require(run, split.get("counts") == COUNTS[system], "protocol split counts",
                    split.get("counts"))
            services = config.get("services")
            expected_nodes = {"SN": 12, "TT": 27}[system]
            require(run, isinstance(services, list) and len(services) == expected_nodes and
                    len(set(services)) == expected_nodes, "ordered service inventory")
            fingerprint = json.dumps(services, separators=(",", ":"))
            if "services" not in common:
                common["services"] = fingerprint
            require(run, common["services"] == fingerprint, "service order identical")
            current = {"input_hashes": config.get("input_hashes"),
                       "split_hash": hashes.get("split.json"),
                       "scaler_hash": hashes.get("scaler.npz")}
            common.setdefault("manifest", current)
            require(run, current == common["manifest"], "input/split/scaler identical")
            require(run, config.get("artifact_hashes", {}).get("split.json") ==
                    hashes.get("split.json") and config.get("artifact_hashes", {}).get(
                        "scaler.npz") == hashes.get("scaler.npz"), "config artifact hashes match")
            require(run, config.get("effective_options", {}).get("seed") == seed and
                    config.get("effective_options", {}).get("system") == system and
                    config.get("effective_options", {}).get("kind") == kind,
                    "system/kind/seed options match")
            require(run, history_complete(history, epochs), "complete sequential history")
            if epochs == 200:
                reference = HERE / "calibration50" / system / kind / f"seed_{seed}"
                try:
                    ref_config = json.loads((reference / "config.json").read_text())
                    ref_history = json.loads((reference / "history.json").read_text())
                    ref_hashes = {name: sha256(reference / name)
                                  for name in ("split.json", "scaler.npz")}
                    cfg, ref = dict(config), dict(ref_config)
                    for value in (cfg, ref):
                        value.pop("effective_epochs", None)
                        options = dict(value["effective_options"])
                        options.pop("epochs", None)
                        options.pop("output_dir", None)
                        value["effective_options"] = options
                    require(run, cfg == ref, "200-epoch config matches 50-epoch settings")
                    require(run, hashes.get("split.json") == ref_hashes["split.json"] and
                            hashes.get("scaler.npz") == ref_hashes["scaler.npz"],
                            "200-epoch split/scaler hashes match 50-epoch")
                    fields = ("train_batch_weighted_joint_loss", "validation_joint_loss",
                              "validation_scores", "optimizer_updates")
                    require(run, len(ref_history) == 50 and
                            [{k: row.get(k) for k in fields} for row in history[:50]] ==
                            [{k: row.get(k) for k in fields} for row in ref_history],
                            "first 50 loss/score/update history exactly matches")
                except Exception as error:
                    require(run, False, "200-epoch same-system 50 comparison available",
                            str(error))
            best = summary.get("best_epoch")
            run["best_epoch"] = best
            run["late_epoch_trigger"] = isinstance(best, int) and best >= (
                45 if epochs == 50 else 180)
            if not isinstance(best, int) or not 1 <= best <= len(history):
                require(run, False, "best epoch in history")
                continue
            selected = history[best - 1]
            run["train_loss"] = selected.get("train_batch_weighted_joint_loss")
            run["validation_loss"] = selected.get("validation_joint_loss")
            require(run, selected.get("validation_joint_loss") ==
                    summary.get("best_validation_joint_loss"), "best loss matches summary")
            losses = [row.get("validation_joint_loss") for row in history]
            require(run, all(isinstance(loss, (int, float)) for loss in losses) and
                    losses[best - 1] == min(losses), "best epoch is minimum validation loss")
            try:
                with np.load(directory / "validation_predictions.npz",
                             allow_pickle=False) as saved:
                    indices, roots, detects, labels = (saved[k] for k in
                        ("indices", "root_logits", "detection_logits", "labels"))
                scores = independently_score(roots, detects, labels)
                run["fault_windows"] = int(np.count_nonzero(labels >= 0))
                count = COUNTS[system]["validation"]
                for metric, value in scores.items():
                    recorded = selected.get("validation_scores", {}).get(metric)
                    passed = exact(recorded, value)
                    require(run, passed, f"independent {metric} exact match",
                            {"history": recorded, "independent": value})
                    run["score_recomputations"].append(
                        {"metric": metric, "history": recorded, "independent": value,
                         "passed": passed})
                require(run, len(indices) == count and roots.shape == (count, expected_nodes)
                        and detects.shape == (count, 2) and labels.shape == (count,),
                        "prediction dimensions")
                require(run, np.array_equal(indices, np.asarray(
                    split["indices"]["validation"])), "prediction indices match split")
            except Exception as error:
                failures.append(f"{kind}/seed_{seed}: prediction verification failed: {error}")
            run["parameters"] = summary.get("parameters")
            run["checkpoint_sha256"] = hashes.get("checkpoint.pt")

    prefix = prefix or f"{system.lower()}{epochs}"
    late = [r for r in runs if r.get("late_epoch_trigger")]
    result = {"status": "PASS" if not failures else "FAIL", "system": system,
              "epochs": epochs, "runs_expected": 6,
              "runs_checked": len(runs) - sum("incomplete" in f or "unreadable" in f
                                               for f in failures),
              "late_epoch_diagnostic": {
                  "triggered": bool(late),
                  "triggering_runs": [f"{r['kind']}/seed_{r['seed']}:{r['best_epoch']}"
                                      for r in late],
                  "extension_executed": False},
              "common_manifest": common.get("manifest"), "failures": failures, "runs": runs}
    (HERE / f"{prefix}_verification.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n")
    lines = [f"# {system}{epochs} calibration artifact verification", "",
             f"**{result['status']}** — checked {result['runs_checked']}/6 expected runs.",
             "Scores are independently recomputed from saved validation logits and labels.",
             "No test partition is evaluated.", "",
             f"Late-selection diagnostic (best epoch ≥ {'45' if epochs == 50 else '180'}): "
             f"{'triggered' if late else 'not triggered'}.",
             "No further training or epoch extension was performed.", ""]
    if failures:
        lines += ["## Failed checks", ""] + [f"- {failure}" for failure in failures] + [""]
    (HERE / f"{prefix}_summary.md").write_text("\n".join(lines))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", choices=("SN", "TT"), required=True)
    parser.add_argument("--epochs", type=int, choices=(50, 200), required=True)
    parser.add_argument("--output-prefix")
    args = parser.parse_args(argv)
    # Negative proof exercises the same predicates against isolated mutations.
    assert not exact("recorded-hash", "mutated-hash")
    assert not exact(0.5, 0.6)
    assert not history_complete([{"epoch": 1}], 2)
    result = check(args.system, args.epochs, args.output_prefix)
    print("CALIBRATION_VERIFIED" if result["status"] == "PASS" else "CALIBRATION_FAILED")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
