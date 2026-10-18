"""Run split-independent case conversion only for the original allowed 72 cases."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing
from pathlib import Path
import time

import pyarrow as pa

import re2_stage1 as stage


def configure_worker():
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)


def checked_existing(row):
    target = stage.OUT / row["case"]
    if not target.exists():
        return None
    report = json.loads((target / "metadata.json").read_text())
    assert report["status"] == "PASS_UNSCALED_CASE"
    assert report["case"] == row["case"] and report["partition"] == row["partition"]
    assert report["split_sha256"] == stage.digest(stage.MANIFEST)
    assert report["source_sha256"] == stage.digest(Path(stage.__file__))
    for name, expected in report["output_hashes"].items():
        assert stage.file_hash(target / name) == expected
    assert report["protected_case_files_opened"] == 0
    return report


def main():
    assert __debug__
    started = time.perf_counter()
    assert not (stage.HERE / "RE2_STAGE1_MANIFEST.json").exists()
    lock = json.loads(stage.MANIFEST.with_name("split.lock.json").read_text())
    assert stage.digest(stage.MANIFEST) == lock["sha256"]
    manifest = json.loads(stage.MANIFEST.read_text())
    rows = [row for row in manifest["cases"] if row["dataset"] == "RE2-OB"
            and row["partition"] in ("train", "validation")]
    assert len(rows) == 72 and sum(row["partition"] == "train" for row in rows) == 54
    results, pending = [], []
    for row in rows:
        stage.allow_case(row)
        existing = checked_existing(row)
        if existing is None:
            pending.append(row)
        else:
            results.append(existing)
    reused = len(results)
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn"),
                             initializer=configure_worker) as pool:
        futures = {pool.submit(stage.convert_case, row): row["case"] for row in pending}
        for future in as_completed(futures):
            result = future.result()
            assert result["case"] == futures[future]
            results.append(result)
    assert len(results) == len({r["case"] for r in results}) == 72
    for row in rows:
        assert checked_existing(row) is not None
    output = {
        "status": "PASS_UNSCALED_ONLY", "cases": [
            {"case": result["case"], "partition": result["partition"],
             "windows": result["windows"], "seconds": result["seconds"],
             "metadata_sha256": stage.digest(stage.OUT / result["case"] / "metadata.json")}
            for result in sorted(results, key=lambda r: r["case"])],
        "reused_verified_cases": reused, "converted_cases_this_run": len(pending),
        "split_sha256": lock["sha256"], "stage_source_sha256": stage.digest(Path(stage.__file__)),
        "batch_source_sha256": stage.digest(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
        "templates_scalers_graph_fitted": False, "protected_case_files_opened": 0,
        "model_ready": False,
        "remaining": ["freeze cross-modal identifier contract", "TRAIN-only vocabulary/templates",
                      "native Hawkes features", "TRAIN-only imputation/scaling", "cross-case overlap check"],
    }
    stage.save_json(stage.HERE / "RE2_STAGE1_MANIFEST.json", output)
    print("RE2_STAGE1_PASS 72 PROTECTED_OPENED_0", flush=True)


if __name__ == "__main__":
    main()
