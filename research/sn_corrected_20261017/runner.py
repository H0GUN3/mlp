"""Approved SN grouped training; evaluation is a separate, selection-locked stage."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

os.environ.setdefault("DGLBACKEND", "pytorch")
import dgl
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent / "native_reproduction_20261013"
sys.path.insert(0, str(NATIVE))
from native_models import NativeReference, joint_loss, SOURCE
from native_train import fit_scaler, scaled_partition, graph_batch, validation_predictions
from input_bundle import load_inputs, split_indices
from scores import event_metrics, paired_cluster_bootstrap

SEEDS = (11, 23, 37)
KINDS = ("eadro", "diagmlp")
PLAN_HASH = "5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def sources():
    assert digest(HERE / "PLAN.md") == PLAN_HASH
    paths = [HERE / n for n in ("PLAN.md", "EXECUTION.md", "runner.py", "scores.py", "input_bundle.py",
                                "test_runner.py", "test_scores.py", "test_input_bundle.py")]
    paths += [NATIVE / "native_models.py", NATIVE / "native_train.py", SOURCE]
    return {str(p): digest(p) for p in paths}


def setup(seed):
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    dgl.seed(seed)


def common_initial_hash(model):
    h = hashlib.sha256()
    prefixes = ("core.encoder.metric_model.", "core.encoder.trace_model.",
                "core.encoder.log_model.", "core.locator.", "core.detector.")
    matched = 0
    for key, value in sorted(model.state_dict().items()):
        if key.startswith(prefixes):
            h.update(key.encode())
            h.update(value.detach().cpu().numpy().tobytes())
            matched += 1
    assert matched > 10
    return {"sha256": h.hexdigest(), "tensors": matched}


def partitions(arrays, rotation):
    indices = split_indices(arrays, rotation)
    stats = fit_scaler(arrays, indices["train"])
    data = {}
    for part in ("train", "validation", "evaluation"):
        data[part] = scaled_partition(arrays, indices[part], stats)
        data[part]["event_ids"] = arrays["event_ids"][indices[part]]
        data[part]["indices"] = arrays["indices"][indices[part]]
    return indices, stats, data


def predict(model, data, metadata):
    root, detection, labels, loss = validation_predictions(model, data, metadata, 32)
    metrics = event_metrics(root.numpy(), labels.numpy(), data["event_ids"])
    if not math.isfinite(metrics["event_nll"]):
        raise ValueError("Non-finite event validation NLL")
    return root, detection, labels, loss, metrics


def train_epoch(model, optimizer, data, metadata, shuffle):
    model.train()
    order = shuffle.permutation(len(data["labels"]))
    total, updates = 0.0, 0
    for start in range(0, len(order), 32):
        batch = order[start:start + 32]
        graph, labels = graph_batch(data, batch, metadata)
        optimizer.zero_grad()
        root, detection = model(graph)
        loss = joint_loss(root, detection, labels)
        if not torch.isfinite(loss):
            raise ValueError("Non-finite training loss")
        loss.backward()
        if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
            raise ValueError("Non-finite gradient")
        optimizer.step()
        total += loss.item() * len(batch)
        updates += 1
    return total / len(order), updates


def snapshot(model, optimizer, shuffle, epoch, best_nll, best_epoch, config_hash):
    return {
        "model": model.state_dict(), "optimizer": optimizer.state_dict(),
        "shuffle": shuffle.get_state(), "torch_rng": torch.get_rng_state(),
        "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
        "epoch": epoch, "best_nll": best_nll, "best_epoch": best_epoch,
        "config_sha256": config_hash}


def restore(state, model, optimizer, shuffle):
    model.load_state_dict(state["model"])
    optimizer.load_state_dict(state["optimizer"])
    shuffle.set_state(state["shuffle"])
    torch.set_rng_state(state["torch_rng"])
    random.setstate(state["python_rng"])
    np.random.set_state(state["numpy_rng"])


def run_path(rotation, kind, seed):
    return HERE / "runs" / ("rotation_" + str(rotation)) / kind / ("seed_" + str(seed))


def rotation_target(runs):
    if len(runs) != 6:
        raise ValueError("A rotation budget requires exactly six 200-epoch runs")
    return 400 if any(run["best_epoch"] >= 180 for run in runs) else 200


def fit(rotation, kind, seed, target):
    started = time.perf_counter()
    setup(seed)
    arrays, meta = load_inputs()
    idx, stats, data = partitions(arrays, rotation)
    folder = run_path(rotation, kind, seed)
    model = NativeReference(kind, 12, 7)
    initial = common_initial_hash(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    shuffle = np.random.RandomState(seed)
    if target == 200:
        folder.mkdir(parents=True, exist_ok=False)
        with (folder / "scaler.npz").open("xb") as stream:
            np.savez(stream, **stats)
        config = {
            "rotation": rotation, "kind": kind, "seed": seed, "model": model.config,
            "lr": .001, "batch_size": 32, "initial_epochs": 200, "maximum_epochs": 400,
            "selection": "minimum validation event NLL of mean window probabilities; earliest tie",
            "source_hashes": sources(), "input_npz_sha256": digest(HERE / "inputs.npz"),
            "input_manifest_sha256": digest(HERE / "input_manifest.json"),
            "scaler_sha256": digest(folder / "scaler.npz"),
            "indices": {k: v.tolist() for k, v in idx.items()},
            "common_initial_state": initial,
            "parameter_count": sum(p.numel() for p in model.parameters()),
            "versions": {"python": sys.version, "torch": torch.__version__, "dgl": dgl.__version__,
                         "numpy": np.__version__}}
        dump(folder / "config.json", config)
        history, epoch0, best_nll, best_epoch = [], 0, float("inf"), 0
    else:
        budgets = json.loads((HERE / ("rotation_{}.budget.json".format(rotation))).read_text())
        assert budgets["rotations"][str(rotation)]["target_epochs"] == 400
        config = json.loads((folder / "config.json").read_text())
        assert config["source_hashes"] == sources()
        assert config["input_npz_sha256"] == digest(HERE / "inputs.npz")
        assert config["input_manifest_sha256"] == digest(HERE / "input_manifest.json")
        state = torch.load(folder / "last_200.pt", map_location="cpu")
        assert state["config_sha256"] == digest(folder / "config.json")
        assert state["epoch"] == 200
        restore(state, model, optimizer, shuffle)
        epoch0, best_nll, best_epoch = state["epoch"], state["best_nll"], state["best_epoch"]
        history = json.loads((folder / "history_200.json").read_text())
        assert len(history) == 200
    config_hash = digest(folder / "config.json")
    epoch_log = folder / ("epochs_{}.jsonl".format(target))
    with epoch_log.open("x", encoding="utf-8") as log:
        for epoch in range(epoch0 + 1, target + 1):
            loss, updates = train_epoch(model, optimizer, data["train"], meta, shuffle)
            _, _, _, val_joint, val = predict(model, data["validation"], meta)
            row = {"epoch": epoch, "train_online_joint_loss": loss, "updates": updates,
                   "validation_joint_loss": val_joint, "validation_event_nll": val["event_nll"],
                   "validation_top1": val["top1"], "validation_top3": val["top3"]}
            history.append(row)
            log.write(json.dumps(row, allow_nan=False) + "\n")
            log.flush()
            if val["event_nll"] < best_nll:
                best_nll, best_epoch = val["event_nll"], epoch
                # This run's own best checkpoint is deliberately updated; old experiments never are.
                torch.save({"model": model.state_dict(), "epoch": epoch,
                            "validation_event_nll": best_nll, "config_sha256": config_hash},
                           folder / "best.pt")
            if epoch % 25 == 0:
                print("EPOCH", rotation, kind, seed, epoch, "val_nll", val["event_nll"], flush=True)
    torch.save(snapshot(model, optimizer, shuffle, target, best_nll, best_epoch, config_hash),
               folder / ("last_{}.pt".format(target)))
    dump(folder / ("history_{}.json".format(target)), history)
    summary = {
        "status": "PASS", "rotation": rotation, "kind": kind, "seed": seed,
        "epochs": target, "updates": sum(r["updates"] for r in history),
        "best_epoch": best_epoch, "best_validation_event_nll": best_nll,
        "stage_seconds": time.perf_counter() - started, "config_sha256": config_hash,
        "history_sha256": digest(folder / ("history_{}.json".format(target))),
        "last_sha256": digest(folder / ("last_{}.pt".format(target))),
        "best_sha256": digest(folder / "best.pt"), "evaluation_opened": False}
    assert summary["updates"] == target * math.ceil(len(idx["train"]) / 32)
    dump(folder / ("stage_{}.json".format(target)), summary)
    print("FIT_PASS", rotation, kind, seed, target, flush=True)


def rotation_job(rotation):
    (HERE / "logs").mkdir(exist_ok=True)
    started_path = HERE / ("rotation_{}.started.json".format(rotation))
    done_path = HERE / ("rotation_{}.done.json".format(rotation))
    budget_path = HERE / ("rotation_{}.budget.json".format(rotation))
    if any(path.exists() for path in (started_path, done_path, budget_path)):
        raise FileExistsError("Rotation artifacts already exist: {}".format(rotation))
    guard = json.loads((HERE / "PRETRAIN_CHECKS.json").read_text())
    assert guard["status"] == "PASS"
    assert guard["source_hashes"] == sources()
    assert guard["input_npz_sha256"] == digest(HERE / "inputs.npz")
    dump(started_path, {
        "rotation": rotation, "source_hashes": sources(),
        "input_npz_sha256": digest(HERE / "inputs.npz"),
        "pretrain_checks_sha256": digest(HERE / "PRETRAIN_CHECKS.json"),
        "started_epoch": time.time()})
    runs = []
    for kind in KINDS:
        for seed in SEEDS:
            fit(rotation, kind, seed, 200)
            folder = run_path(rotation, kind, seed)
            stage = json.loads((folder / "stage_200.json").read_text())
            runs.append(stage)
    target = rotation_target(runs)
    budget = {
        "rotation": rotation,
        "rule": "any of this rotation's six 200-epoch best epochs>=180 extends all six once",
        "target_epochs": target,
        "initial_best_epochs": [run["best_epoch"] for run in runs],
        "initial_summaries": runs,
    }
    dump(budget_path, {"rotations": {str(rotation): budget}})
    if target == 400:
        for kind in KINDS:
            for seed in SEEDS:
                fit(rotation, kind, seed, 400)
    target_runs = []
    for kind in KINDS:
        for seed in SEEDS:
            folder = run_path(rotation, kind, seed)
            stage = json.loads((folder / ("stage_{}.json".format(target))).read_text())
            history_path = folder / ("history_{}.json".format(target))
            history = json.loads(history_path.read_text())
            config = json.loads((folder / "config.json").read_text())
            assert len(history) == target
            selected = min(history, key=lambda row: (row["validation_event_nll"], row["epoch"]))
            assert selected["epoch"] == stage["best_epoch"]
            assert digest(folder / "best.pt") == stage["best_sha256"]
            assert digest(history_path) == stage["history_sha256"]
            target_runs.append({
                **stage, "path": str(folder.relative_to(HERE)),
                "history_path": history_path.name,
                "history_epochs": len(history),
                "history_sha256": digest(history_path),
                "config": config,
                "common_initial_state": config["common_initial_state"],
                "budget_bound": target == 400 and stage["best_epoch"] >= 360,
            })
    for seed in SEEDS:
        paired = [r["common_initial_state"] for r in target_runs if r["seed"] == seed]
        assert len(paired) == 2 and paired[0] == paired[1]
    dump(done_path, {
        "status": "PASS", "rotation": rotation, "source_hashes": sources(),
        "input_npz_sha256": digest(HERE / "inputs.npz"),
        "started_sha256": digest(started_path),
        "budget_sha256": digest(budget_path), "target_epochs": target,
        "runs": target_runs, "rotation_process_exit": 0,
    })
    print("ROTATION_DONE", rotation, target, flush=True)


def train_all():
    guard = json.loads((HERE / "PRETRAIN_CHECKS.json").read_text())
    assert guard["status"] == "PASS"
    assert guard["source_hashes"] == sources()
    if (HERE / "budgets.json").exists() or (HERE / "selection.lock.json").exists():
        raise FileExistsError("Global training lock artifacts already exist")
    (HERE / "logs").mkdir(exist_ok=True)

    def execute(rotation):
        path = HERE / "logs" / "rotation_{}.log".format(rotation)
        command = [sys.executable, "-B", str(Path(__file__)), "train-rotation",
                   "--rotation", str(rotation)]
        environment = dict(os.environ, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                           OPENBLAS_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1")
        with path.open("x", encoding="utf-8") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=environment)
        if result.returncode:
            raise RuntimeError("Rotation {} exited {}; see {}".format(rotation, result.returncode, path))
        done_path = HERE / "rotation_{}.done.json".format(rotation)
        done = json.loads(done_path.read_text())
        assert done["status"] == "PASS" and done["rotation_process_exit"] == result.returncode
        print("ROTATION_EXIT", rotation, result.returncode, flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(execute, rotation) for rotation in range(3)]
        for future in as_completed(futures):
            future.result()
    lock()


def lock():
    if (HERE / "budgets.json").exists() or (HERE / "selection.lock.json").exists():
        raise FileExistsError("Global training lock artifacts already exist")
    selections, budgets = [], {"rule": "per-rotation 200-to-400 extension", "rotations": {}}
    for rotation in range(3):
        done_path = HERE / ("rotation_{}.done.json".format(rotation))
        done = json.loads(done_path.read_text())
        assert done["status"] == "PASS" and done["rotation"] == rotation
        assert done["rotation_process_exit"] == 0
        assert done["source_hashes"] == sources()
        assert done["input_npz_sha256"] == digest(HERE / "inputs.npz")
        assert done["started_sha256"] == digest(HERE / ("rotation_{}.started.json".format(rotation)))
        assert done["budget_sha256"] == digest(HERE / ("rotation_{}.budget.json".format(rotation)))
        budget = json.loads((HERE / ("rotation_{}.budget.json".format(rotation))).read_text())
        expected_target = budget["rotations"][str(rotation)]["target_epochs"]
        assert expected_target in (200, 400) and done["target_epochs"] == expected_target
        runs = done["runs"]
        assert len(runs) == 6
        assert {(run["kind"], run["seed"]) for run in runs} == {
            (kind, seed) for kind in KINDS for seed in SEEDS}
        initial_runs = budget["rotations"][str(rotation)]["initial_summaries"]
        assert len(initial_runs) == 6
        assert expected_target == rotation_target(initial_runs)
        assert budget["rotations"][str(rotation)]["initial_best_epochs"] == [
            run["best_epoch"] for run in initial_runs]
        initial_by_run = {(run["kind"], run["seed"]): run for run in initial_runs}
        for run in runs:
            folder = HERE / run["path"]
            config = json.loads((folder / "config.json").read_text())
            history_path = folder / run["history_path"]
            history = json.loads(history_path.read_text())
            assert len(history) == expected_target == run["history_epochs"]
            assert run["rotation"] == rotation and run["epochs"] == expected_target
            assert config["source_hashes"] == sources()
            assert run["config_sha256"] == digest(folder / "config.json")
            assert run["history_sha256"] == digest(history_path)
            assert run["best_sha256"] == digest(folder / "best.pt")
            assert run["last_sha256"] == digest(folder / ("last_{}.pt".format(expected_target)))
            selected = min(history, key=lambda row: (row["validation_event_nll"], row["epoch"]))
            assert selected["epoch"] == run["best_epoch"] and run["best_epoch"] <= expected_target
            initial = initial_by_run[(run["kind"], run["seed"])]
            history_200_path = folder / "history_200.json"
            history_200 = json.loads(history_200_path.read_text())
            stage_200 = json.loads((folder / "stage_200.json").read_text())
            first_200_best = min(
                history[:200], key=lambda row: (row["validation_event_nll"], row["epoch"]))
            assert len(history_200) == 200
            assert digest(history_200_path) == initial["history_sha256"] == stage_200["history_sha256"]
            assert first_200_best["epoch"] == initial["best_epoch"] == stage_200["best_epoch"]
            assert stage_200["config_sha256"] == run["config_sha256"]
            assert stage_200["best_validation_event_nll"] == initial["best_validation_event_nll"]
            checkpoint = torch.load(folder / "best.pt", map_location="cpu")
            assert checkpoint["epoch"] == run["best_epoch"]
            assert checkpoint["config_sha256"] == run["config_sha256"]
            selections.append({key: value for key, value in run.items() if key != "config"})
        for seed in SEEDS:
            paired = [run["common_initial_state"] for run in runs if run["seed"] == seed]
            assert len(paired) == 2 and paired[0] == paired[1]
        assert done["rotation_process_exit"] == 0
        budgets["rotations"][str(rotation)] = budget["rotations"][str(rotation)]
    assert len(selections) == 18
    dump(HERE / "budgets.json", budgets)
    dump(HERE / "selection.lock.json", {
        "status": "LOCKED", "source_hashes": sources(), "runs": selections,
        "budgets_sha256": digest(HERE / "budgets.json"),
        "input_npz_sha256": digest(HERE / "inputs.npz"), "evaluation_opened": False})
    print("SELECTION_LOCKED", len(selections), flush=True)


def evaluate():
    selection = json.loads((HERE / "selection.lock.json").read_text())
    assert selection["source_hashes"] == sources()
    assert selection["input_npz_sha256"] == digest(HERE / "inputs.npz")
    assert len(selection["runs"]) == 18
    out = HERE / "evaluation"
    out.mkdir(exist_ok=False)
    arrays, meta = load_inputs()
    results = []
    for entry in selection["runs"]:
        f, kind, seed = entry["rotation"], entry["kind"], entry["seed"]
        setup(seed)
        folder = HERE / entry["path"]
        assert digest(folder / "best.pt") == entry["best_sha256"]
        checkpoint = torch.load(folder / "best.pt", map_location="cpu")
        assert checkpoint["epoch"] == entry["best_epoch"]
        assert checkpoint["config_sha256"] == entry["config_sha256"]
        indices, stats, data = partitions(arrays, f)
        with np.load(folder / "scaler.npz", allow_pickle=False) as saved:
            for key in stats:
                np.testing.assert_array_equal(stats[key], saved[key])
        model = NativeReference(kind, 12, 7)
        model.load_state_dict(checkpoint["model"])
        result = {"rotation": f, "kind": kind, "seed": seed, "selected_epoch": entry["best_epoch"],
                  "budget_bound": entry["budget_bound"], "parts": {}, "prediction_sha256": {}}
        for part in ("train", "validation", "evaluation"):
            roots, detects, labels, loss, metrics = predict(model, data[part], meta)
            if part == "validation":
                assert metrics["event_nll"] == entry["best_validation_event_nll"]
            filename = "r{}_{}_s{}_{}.npz".format(f, kind, seed, part)
            with (out / filename).open("xb") as stream:
                np.savez(stream, root_logits=roots.numpy(), detection_logits=detects.numpy(),
                         labels=labels.numpy(), event_ids=data[part]["event_ids"],
                         indices=data[part]["indices"])
            metrics["joint_loss"] = loss
            result["parts"][part] = metrics
            result["prediction_sha256"][filename] = digest(out / filename)
        results.append(result)
        print("EVALUATED", f, kind, seed, flush=True)
    dump(HERE / "evaluation.json", {
        "status": "PASS", "selection_sha256": digest(HERE / "selection.lock.json"),
        "runs": results, "source_hashes": sources(), "original_protected_test_opened": False})
    print("EVALUATION_PASS", len(results), flush=True)


def main():
    if not __debug__:
        raise RuntimeError("Safety assertions must not be disabled")
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("fit", "train-rotation", "train-all", "lock", "evaluate"))
    parser.add_argument("--rotation", type=int, choices=range(3))
    parser.add_argument("--kind", choices=KINDS)
    parser.add_argument("--seed", type=int, choices=SEEDS)
    parser.add_argument("--target", type=int, choices=(200, 400))
    args = parser.parse_args()
    if args.stage == "fit":
        if any(v is None for v in (args.rotation, args.kind, args.seed, args.target)):
            parser.error("fit needs rotation, kind, seed, target")
        fit(args.rotation, args.kind, args.seed, args.target)
    elif args.stage == "train-rotation":
        if args.rotation is None or any(v is not None for v in (args.kind, args.seed, args.target)):
            parser.error("train-rotation needs only --rotation")
        rotation_job(args.rotation)
    elif args.stage == "train-all":
        train_all()
    elif args.stage == "lock":
        lock()
    else:
        evaluate()


if __name__ == "__main__":
    main()
