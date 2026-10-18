"""Complete the two unmeasured first-case cost probes, without changing features."""
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from research.re2_ob_known_condition_20261018 import prepare as p


def choose_positions(keys, sizes):
    ordered = sorted(keys, key=lambda key: sizes[key])
    if not ordered:
        raise ValueError("No nonempty probe inputs")
    return list(dict.fromkeys(ordered[i] for i in (0, len(ordered) // 2, len(ordered) - 1)))


def main():
    assert choose_positions(["a", "b", "c", "d", "e"], dict(a=1, b=2, c=3, d=4, e=5)) == [
        "a", "c", "e"]
    assert choose_positions(["a"], {"a": 2}) == ["a"]
    target = p.OUT / "cost_supplement.json"
    if target.exists():
        raise FileExistsError("Refusing to overwrite " + str(target))
    script_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    original_path = p.OUT / "profile.json"
    original_bytes = original_path.read_bytes()
    original = json.loads(original_bytes)
    started = time.perf_counter()
    rows, metadata, services, _, precheck, guard = p.preflight()
    miner, template = p.frozen_templates(rows, metadata)
    row = rows[0]
    matched, _ = p.matched_case(row, metadata[row["case"]], services, miner, template)
    source = p.arrays_read(p.STAGE1 / row["case"] / "temporal.npz")
    knots_by_key = {
        key: knots for _, _, key, knots in p.pure.case_groups(
            matched, int(source["starts"][0]), template["event_count"])
    }
    selected = choose_positions(knots_by_key, {
        key: sum(map(len, knots)) for key, knots in knots_by_key.items()
    })
    previous = {r["key"]: r for r in original["probe_fits"]}
    records = []
    for key in selected:
        _, record = p.cached_fit(key, knots_by_key[key])
        records.append(dict(record, reused_original_probe=key in previous))
        print("COST_SUPPLEMENT_PROBE", len(records), record["seconds"], flush=True)
    if original_bytes != original_path.read_bytes():
        raise ValueError("Original cost profile changed")
    seconds = [record["seconds"] for record in records]
    result = {
        "status": "PASS", "case": row["case"], "probe_count": len(records),
        "selection": "original first-case smallest/middle/largest knot sizes; no model scores",
        "probe_fits": records, "unique_input_count": original["unique_input_count"],
        "mean_estimate_4worker_seconds": original["unique_input_count"] * float(np.mean(seconds)) / 4,
        "max_estimate_4worker_seconds": original["unique_input_count"] * max(seconds) / 4,
        "limits": "Three first-case samples only; not a guaranteed runtime or whole-corpus convergence.",
        "original_profile_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "script_sha256": script_sha256,
        "input_binding_sha256": precheck["input_binding_sha256"],
        "split_sha256": precheck["split_sha256"],
        "seconds": time.perf_counter() - started,
    }
    p.json_write(target, result)
    print("COST_SUPPLEMENT_PASS", flush=True)


if __name__ == "__main__":
    main()
