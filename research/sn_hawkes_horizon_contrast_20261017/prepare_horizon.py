"""Paired horizon-only Hawkes preparation. No model training or whole-source load."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import importlib
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import platform
import sys
import time
import traceback
from typing import Any, Dict, List, Tuple
import warnings

import numpy as np

from selective_loader import (
    HERE, NATIVE, SPLIT, file_hash, load_selected, preflight, read_json,
)


INPUTS = HERE / "inputs"
THREADS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
           "NUMEXPR_NUM_THREADS")
BUDGET = 1500.0


def native_helpers() -> Any:
    if str(NATIVE) not in sys.path:
        sys.path.insert(0, str(NATIVE))
    return importlib.import_module("native_data")


def write_json(path: Path, value: Any) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def save_npz(path: Path, arrays: Dict[str, np.ndarray]) -> None:
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def code_hashes() -> Dict[str, str]:
    names = ("selective_loader.py", "prepare_horizon.py", "test_selective_loader.py",
             "test_prepare_horizon.py", "pyright_prep.json")
    return {name: file_hash(HERE / name) for name in names}


def environment() -> Dict[str, Any]:
    versions = {name: importlib.metadata.version(name)
                for name in ("numpy", "pandas", "tick", "drain3", "scipy")}
    if sys.version_info[:2] != (3, 8):
        raise ValueError("Use existing .venv-eadro Python3.8")
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("All four numeric thread environment variables must be 1")
    for name, expected in (("numpy", "1.21.5"), ("pandas", "1.4.2"),
                           ("tick", "0.7.0.1"), ("drain3", "0.9.11")):
        if versions[name] != expected:
            raise ValueError("Frozen environment version mismatch: " + name)
    return {"python": platform.python_version(), "executable": sys.executable,
            "packages": versions, "threads": {k: os.environ[k] for k in THREADS},
            "workers": 2}


def build_tasks(events: Dict[str, np.ndarray], indices: np.ndarray
                ) -> List[Dict[str, Any]]:
    native = native_helpers()
    positions = {int(window): i for i, window in enumerate(indices)}
    windows, nodes = events["log_window"], events["log_node"]
    if len(windows) and (np.any(np.diff(windows) < 0)
                        or np.any((np.diff(windows) == 0) & (np.diff(nodes) < 0))):
        raise ValueError("Selected event group order differs from frozen source")
    bounds = np.r_[0, np.flatnonzero(
        (np.diff(windows) != 0) | (np.diff(nodes) != 0)) + 1, len(windows)]
    tasks = []
    for left, right in zip(bounds[:-1], bounds[1:]):
        if left == right:
            continue
        window, node = int(windows[left]), int(nodes[left])
        position = positions[window]
        start = float(events["window_start"][position])
        knots = native.make_knots(events["log_timestamp"][left:right],
                                  events["log_template"][left:right], start, 7)
        tasks.append({
            "window": window, "position": position, "node": node, "knots": knots,
            "start": start, "seed": 42 + window * 12 + node,
            "event_count": int(right - left),
            "knot_count": sum(len(knot) for knot in knots),
        })
    if len({(t["window"], t["node"]) for t in tasks}) != len(tasks):
        raise ValueError("Duplicate nonempty group")
    return tasks


def fit_absolute(task: Dict[str, Any], model_class: Any = None) -> Dict[str, Any]:
    knots, horizon = task["knots"], task["start"] + 10.0
    if not np.isfinite(horizon) or horizon < 10:
        raise ValueError("Invalid absolute horizon")
    for knot in knots:
        if (knot.ndim != 1 or not len(knot) or not np.isfinite(knot).all()
                or np.any(knot < 0) or np.any(knot >= 10)
                or np.any(np.diff(knot) <= 0)):
            raise ValueError("Invalid common relative knots")
    if model_class is None:
        model_class = importlib.import_module("tick.hawkes").HawkesADM4
    np.random.seed(task["seed"])
    begin = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = model_class(3)
        model.fit(knots, end_times=horizon,
                  baseline_start=np.ones(len(knots)) * .2)
        baseline = np.asarray(model.baseline, dtype=np.float64)
    if (baseline.shape != (len(knots),) or not np.isfinite(baseline).all()
            or np.any(baseline < 0)):
        raise ValueError("Invalid absolute Hawkes baseline")
    return {"baseline": baseline, "seconds": time.perf_counter() - begin,
            "warnings": [str(w.message) for w in caught],
            "iterations": int(model.history.last_values["n_iter"])}


def paired_fit(task: Dict[str, Any]) -> Dict[str, Any]:
    native = native_helpers()
    begin = time.perf_counter()
    relative = native.fit_hawkes(
        (task["window"], task["node"], task["knots"], task["seed"]))
    if not np.array_equal(relative["baseline"], task["expected"]):
        raise ValueError(
            "RELATIVE_EXACT_MISMATCH window={} node={} expected={} actual={}".format(
                task["window"], task["node"], task["expected"].tolist(),
                relative["baseline"].tolist()))
    absolute = fit_absolute(task)
    return {"window": task["window"], "node": task["node"],
            "relative": relative, "absolute": absolute,
            "paired_seconds": time.perf_counter() - begin}


def probe_indices(tasks: List[Dict[str, Any]]) -> List[int]:
    by_length: Dict[int, int] = {}
    for i, task in enumerate(tasks):
        by_length.setdefault(task["event_count"], i)
    lengths = sorted(by_length)
    if len(lengths) < 5:
        raise ValueError("Need five actual different-length paired probes")
    return [by_length[lengths[int(i)]]
            for i in np.linspace(0, len(lengths) - 1, 5, dtype=int)]


def result_record(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "window": result["window"], "node": result["node"],
        "paired_seconds": result["paired_seconds"],
        "relative_exact": True,
        **{arm: {k: v for k, v in result[arm].items()
                  if k not in ("baseline", "window", "node")}
           for arm in ("relative", "absolute")},
    }


def distribution(values: np.ndarray) -> Dict[str, Any]:
    return {"shape": list(values.shape), "dtype": str(values.dtype),
            "finite": bool(np.isfinite(values).all()),
            "nonzero": int(np.count_nonzero(values)),
            "min": float(values.min()), "max": float(values.max()),
            "mean": float(values.mean()), "std": float(values.std()),
            "quantiles_0_25_50_75_100": np.quantile(values, [0, .25, .5, .75, 1]).tolist()}


def difference(relative: np.ndarray, absolute: np.ndarray,
               indices: np.ndarray) -> Dict[str, Any]:
    delta = absolute - relative
    changed = absolute != relative
    return {
        "relative": distribution(relative), "absolute": distribution(absolute),
        "delta": distribution(delta), "changed_cells": int(changed.sum()),
        "changed_windows": int(np.any(changed, axis=(1, 2)).sum()),
        "changed_window_node_groups": int(np.any(changed, axis=2).sum()),
        "by_window": [
            {"original_window": int(window), "changed_cells": int(changed[i].sum()),
             "relative_nonzero": int(np.count_nonzero(relative[i])),
             "absolute_nonzero": int(np.count_nonzero(absolute[i])),
             "max_abs_delta": float(np.abs(delta[i]).max())}
            for i, window in enumerate(indices)],
        "by_node": [
            {"node": node, "changed_cells": int(changed[:, node].sum()),
             "relative_nonzero": int(np.count_nonzero(relative[:, node])),
             "absolute_nonzero": int(np.count_nonzero(absolute[:, node])),
             "max_abs_delta": float(np.abs(delta[:, node]).max())}
            for node in range(relative.shape[1])],
    }


def publish_arrays(path: Path, arrays: Dict[str, np.ndarray]) -> str:
    temporary = path.with_name(path.name + ".partial")
    if path.exists() or temporary.exists():
        raise FileExistsError("Refusing existing artifact/partial: " + str(path))
    save_npz(temporary, arrays)
    with np.load(temporary, allow_pickle=False) as source:
        if set(source.files) != set(arrays):
            raise ValueError("Own output key roundtrip mismatch")
        for key, value in arrays.items():
            actual = source[key]
            if (actual.dtype != value.dtype or actual.shape != value.shape
                    or actual.tobytes() != value.tobytes()):
                raise ValueError("Own output exact roundtrip mismatch: " + key)
    # Exclusive hard-link publication cannot overwrite a concurrent writer.
    os.link(str(temporary), str(path))
    temporary.unlink()
    return file_hash(path)


def verify_published(expected: Dict[str, Any]) -> Dict[str, Any]:
    metadata = read_json(INPUTS / "metadata.json")
    if file_hash(INPUTS / "selected.npz") != expected["output_hashes"]["selected.npz"]:
        raise ValueError("Published selected hash mismatch")
    if file_hash(INPUTS / "metadata.json") != expected["output_hashes"]["metadata.json"]:
        raise ValueError("Published metadata hash mismatch")
    arrays, _, selection = load_selected(
        read_json(NATIVE / "native_inputs/SN/metadata.json"), read_json(SPLIT))
    with np.load(INPUTS / "selected.npz", allow_pickle=False) as source:
        if set(source.files) != set(arrays) | {"log_absolute"}:
            raise ValueError("Published input interface mismatch")
        for key, value in arrays.items():
            if source[key].dtype != value.dtype or source[key].tobytes() != value.tobytes():
                raise ValueError("Published unchanged input mismatch: " + key)
        absolute = source["log_absolute"]
        if (absolute.shape != arrays["logs"].shape or absolute.dtype != np.float64
                or not np.isfinite(absolute).all() or np.any(absolute < 0)):
            raise ValueError("Published absolute contract mismatch")
    for key in ("original_indices", "train_positions", "validation_positions", "windows"):
        if metadata[key] != selection[key]:
            raise ValueError("Published selection metadata mismatch: " + key)
    return {"all_selected_arrays_byte_exact": True,
            "absolute_shape_finite_nonnegative": True, "metadata_order_exact": True}


def prepare() -> None:
    begin = time.perf_counter()
    env = environment()
    raw_meta, prep_meta, split, hashes = preflight()
    scripts = code_hashes()
    write_json(INPUTS / "preflight.json", {
        "input_source_hashes_before": hashes, "code_config_hashes": scripts,
        "environment": env,
        "historical_extraction_source_sha256": prep_meta["source"]["native_data_source_sha256"],
        "actual_feature_build_source_sha256": raw_meta["source"]["feature_build_source_sha256"],
        "note": "Historical extraction hash and later feature-build hash are distinct fields.",
    })
    arrays, events, selection = load_selected(raw_meta, split)
    tasks = build_tasks(events, arrays["indices"])
    for task in tasks:
        task["expected"] = arrays["logs"][task["position"], task["node"]]
    occupied = np.zeros(arrays["logs"].shape[:2], dtype=bool)
    for task in tasks:
        occupied[task["position"], task["node"]] = True
    if np.any(arrays["logs"][~occupied] != 0):
        raise ValueError("Existing empty log groups must be exactly zero")
    relative = np.zeros_like(arrays["logs"])
    absolute = np.zeros_like(arrays["logs"])
    records: List[Dict[str, Any]] = []
    cached: Dict[int, Dict[str, Any]] = {}
    probes = []
    for i in probe_indices(tasks):
        result = paired_fit(tasks[i])
        cached[i] = result
        record = dict(result_record(result), event_count=tasks[i]["event_count"],
                      knot_count=tasks[i]["knot_count"], task_index=i)
        probes.append(record)
        stem = "probe_{}_{}".format(result["window"], result["node"])
        save_npz(INPUTS / (stem + ".npz"), {
            "relative": result["relative"]["baseline"],
            "absolute": result["absolute"]["baseline"],
        })
        write_json(INPUTS / (stem + ".json"), record)
        print("PAIRED_PROBE " + json.dumps(record, sort_keys=True), flush=True)
    conservative = max(r["paired_seconds"] for r in probes) * len(tasks) * 1.5 / 2
    estimate = {
        "paired_groups": len(tasks), "actual_probe_groups": probes,
        "probe_paired_seconds": sum(r["paired_seconds"] for r in probes),
        "conservative_remaining_seconds": conservative,
        "formula": "max measured paired seconds * ALL groups * 1.5 / 2 workers",
        "budget_seconds": BUDGET, "elapsed_seconds": time.perf_counter() - begin,
        "probe_results_reused": True,
    }
    write_json(INPUTS / "probe.json", estimate)
    if conservative + time.perf_counter() - begin > BUDGET:
        raise RuntimeError("COST_BLOCKER conservative total exceeds 1500 seconds: "
                           + json.dumps(estimate, sort_keys=True))

    def accept(i: int, result: Dict[str, Any]) -> None:
        task = tasks[i]
        relative[task["position"], task["node"]] = result["relative"]["baseline"]
        absolute[task["position"], task["node"]] = result["absolute"]["baseline"]
        record = result_record(result)
        records.append(record)
        print("PAIRED_GROUP " + json.dumps(record, sort_keys=True), flush=True)

    for i, result in cached.items():
        accept(i, result)
    remaining = [i for i in range(len(tasks)) if i not in cached]
    with ProcessPoolExecutor(max_workers=2,
                             mp_context=multiprocessing.get_context("spawn")) as pool:
        results = pool.map(paired_fit, (tasks[i] for i in remaining), chunksize=1)
        for i, result in zip(remaining, results):
            accept(i, result)
            if time.perf_counter() - begin > BUDGET:
                raise RuntimeError("COST_BLOCKER actual preparation exceeded 1500 seconds")
    if not np.array_equal(relative, arrays["logs"]):
        raise ValueError("FULL_RELATIVE_EXACT_MISMATCH; publication forbidden")
    if not np.isfinite(absolute).all() or np.any(absolute < 0):
        raise ValueError("Invalid full absolute output")
    write_json(INPUTS / "paired_groups.json", {
        "nonempty_groups": len(tasks), "empty_groups": int((~occupied).sum()),
        "records": records,
    })
    save_npz(INPUTS / "relative_rebuilt.npz",
             {"logs": relative, "indices": arrays["indices"]})
    hashes_after = {path: file_hash(Path(path)) for path in hashes}
    if hashes_after != hashes or code_hashes() != scripts:
        raise ValueError("Source/input/script changed during preparation")
    arrays["log_absolute"] = absolute
    output_hash = publish_arrays(INPUTS / "selected.npz", arrays)
    metadata = {key: raw_meta[key] for key in (
        "system", "dataset", "services", "edges", "event_count", "event_num",
        "templates", "unseen_index", "metrics", "window_length", "stride",
        "normalized", "end_convention", "template_training", "source", "repairs")}
    metadata.update(selection)
    metadata.update({
        "window_count": 394, "original_window_count": 564,
        "original_split_sha256": hashes[str(SPLIT)],
        "input_source_hashes": hashes, "code_config_hashes": scripts,
        "selected_npz_sha256": output_hash,
        "horizon_only": {"relative": 10, "absolute": "original_window_start+10"},
    })
    write_json(INPUTS / "metadata.json", metadata)
    solver_reports = {}
    for arm in ("relative", "absolute"):
        solver_reports[arm] = {
            "warning_counts": dict(Counter(
                warning for r in records for warning in r[arm]["warnings"])),
            "iteration_counts": dict(Counter(str(r[arm]["iterations"]) for r in records)),
            "max_iter_cap_count": sum(r[arm]["iterations"] >= 50 for r in records),
            "fit_seconds_sum": sum(r[arm]["seconds"] for r in records),
        }
    pending = {
        "status": "VERIFIED_PENDING_PROCESS_EXIT", "environment": env,
        "probe": estimate, "nonempty_groups": len(tasks),
        "empty_groups": int((~occupied).sum()),
        "relative_equivalence": {"exact": True, "nonempty_groups": len(tasks),
                                 "all_window_node_groups": 394 * 12,
                                 "empty_groups_exact_zero": True},
        "absolute": {"finite": True, "nonnegative": True, "empty_groups_zero": True},
        "solver": solver_reports,
        "solver_settings": {
            "decay": 3, "baseline_start": .2, "max_iter": 50, "tol": 1e-5,
            "C": 1000, "lasso_nuclear_ratio": .5, "rho": .1, "approx": 0,
            "em_max_iter": 30, "em_tol": None, "n_threads": 1,
            "seed": "42+original_window*12+node",
            "relative_helper": "frozen native_data.fit_hawkes",
            "knot_helper": "frozen native_data.make_knots",
            "absolute_change_only": "end_times=original_window_start+10",
            "cap_is_not_convergence": True,
        },
        "unchanged_arrays": {key: True for key in ("metrics", "traces", "logs", "labels", "indices")},
        "input_difference": difference(relative, absolute, arrays["indices"]),
        "input_source_hashes_before": hashes, "input_source_hashes_after": hashes_after,
        "code_config_hashes": scripts, "source_immutable": True,
        "output_hashes": {
            "selected.npz": output_hash,
            "metadata.json": file_hash(INPUTS / "metadata.json"),
            "relative_rebuilt.npz": file_hash(INPUTS / "relative_rebuilt.npz"),
            "paired_groups.json": file_hash(INPUTS / "paired_groups.json"),
        },
        "protection": selection["access_disclosure"],
        "forbidden_observation_rows_materialized": 0, "training_executed": False,
        "producer_log": str(INPUTS / "preparation-run.log"),
        "preparation_seconds": time.perf_counter() - begin,
        "command": [sys.executable, "-B", str(Path(__file__).resolve()), "--prepare"],
    }
    pending["read_roundtrip"] = verify_published(pending)
    write_json(INPUTS / "preparation.pending.json", pending)
    print("PREPARATION_PRODUCER_VERIFIED; PASS awaits actual process exit 0", flush=True)


def finalize(producer_exit_code: int) -> None:
    if producer_exit_code != 0:
        raise ValueError("Cannot publish PASS without actual producer exit 0")
    pending = read_json(INPUTS / "preparation.pending.json")
    if pending["status"] != "VERIFIED_PENDING_PROCESS_EXIT":
        raise ValueError("Missing completed producer verification")
    if code_hashes() != pending["code_config_hashes"]:
        raise ValueError("Preparation code/config changed after producer exit")
    for path, expected in pending["input_source_hashes_before"].items():
        if file_hash(Path(path)) != expected:
            raise ValueError("Source changed after producer exit: " + path)
    for name, expected in pending["output_hashes"].items():
        if file_hash(INPUTS / name) != expected:
            raise ValueError("Output changed after producer exit: " + name)
    pending["read_roundtrip"] = verify_published(pending)
    pending.update(status="PASS", producer_exit_code=producer_exit_code,
                   producer_log_sha256=file_hash(INPUTS / "preparation-run.log"),
                   finalization_command=sys.argv)
    write_json(INPUTS / "preparation.json", pending)
    if read_json(INPUTS / "preparation.json") != pending:
        raise ValueError("PASS manifest JSON roundtrip mismatch")
    print("PREPARATION_PASS", flush=True)


class Tee:
    def __init__(self, console: Any, log: Any) -> None:
        self.console, self.log = console, log

    def write(self, text: str) -> int:
        self.console.write(text)
        self.log.write(text)
        return len(text)

    def flush(self) -> None:
        self.console.flush()
        self.log.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--producer-exit-code", type=int)
    args = parser.parse_args()
    INPUTS.mkdir(exist_ok=True)
    log_path = INPUTS / ("preparation-run.log" if args.prepare else "finalization.log")
    with log_path.open("x") as log:
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(stdout, log), Tee(stderr, log)
        try:
            if args.prepare:
                prepare()
            else:
                if args.producer_exit_code is None:
                    raise ValueError("Supply actual observed --producer-exit-code")
                finalize(args.producer_exit_code)
        except BaseException as error:
            traceback.print_exc()
            failure = INPUTS / ("preparation.failure.json" if args.prepare else "finalization.failure.json")
            write_json(failure, {"status": "FAIL", "error": repr(error),
                                 "traceback": traceback.format_exc(),
                                 "code_config_hashes": code_hashes()})
            raise
        finally:
            sys.stdout, sys.stderr = stdout, stderr


if __name__ == "__main__":
    main()
