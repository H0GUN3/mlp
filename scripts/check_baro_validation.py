"""Evaluate the previously verified BARO score-path implementation, without tuning."""
from collections import defaultdict
import json

import numpy as np

from baseline_dev import REFERENCE_COMMIT, baro_rank, case_metrics, self_check
from mlp_readiness import BASE, DATA, NON_SERVICE_NODES, OUT, allow_read, load_split, rank_metrics, save_new, sha


def main():
    self_check()
    manifest = load_split()
    reference = json.loads((OUT / "training_results.json").read_text())
    records = []
    for row in manifest["cases"]:
        if row["partition"] != "validation":
            continue
        allow_read(row["case"], manifest)
        names, matrix, normal = case_metrics(DATA / row["case"], row["inject_time"])
        _, metrics, _ = baro_rank(names, matrix, normal, "signed")
        per_service = {}
        for metric in metrics:
            service = metric["metric"].split("_", 1)[0]
            if service not in NON_SERVICE_NODES:
                per_service.setdefault(service, metric["score"])
        dataset = reference["datasets"][row["dataset"]]
        vocabulary = dataset["vocabulary"]
        assert not set(per_service) - set(vocabulary), "Unexpected metric service"
        position = dataset["validation_cases"].index(row["case"])
        present = np.asarray(dataset["validation_present"][position], bool)
        truth = vocabulary.index(row["root_cause_service"])
        if per_service:
            minimum = min(per_service.values())
            floor = minimum - max(abs(minimum), 1.0)
            scores = np.asarray([per_service.get(service, floor) for service in vocabulary])
            measured = rank_metrics(scores[None], np.array([truth]), present[None])
        else:
            measured = {"cases": 1, "top1": 0., "top3": 0., "mrr": 0.}
        abstained = row["root_cause_service"] not in per_service
        if abstained:
            measured = {"cases": 1, "top1": 0., "top3": 0., "mrr": 0.}
        records.append({"case": row["case"], "system": row["dataset"],
                        "root_score_unavailable": abstained,
                        "scored_services": len(per_service), **measured})
    assert len(records) == 36
    expected = {r["case"] for r in manifest["cases"] if r["partition"] == "validation"}
    accessed = {r["case"] for r in records}
    assert accessed == expected
    test_ids = {r["case"] for r in manifest["cases"] if r["partition"] == "test"}
    assert not accessed & test_ids
    assert all(0 <= r["top1"] <= r["top3"] <= 1 and 0 <= r["mrr"] <= 1 for r in records)
    grouped = defaultdict(list)
    for record in records:
        grouped[record["system"]].append(record)
    summary = {}
    for system, rows in grouped.items():
        summary[system] = {
            "cases": len(rows),
            **{key: float(np.mean([r[key] for r in rows])) for key in ("top1", "top3", "mrr")},
            "root_score_unavailable": sum(r["root_score_unavailable"] for r in rows),
        }
    output = {
        "method": "BARO signed score-path NumPy reimplementation; not BOCPD or full paper reproduction",
        "source_commit": REFERENCE_COMMIT,
        "source_implementation_sha256": sha(BASE / "scripts/baseline_dev.py"),
        "split_sha256": sha(OUT / "split.json"), "summary": summary,
        "policy": "same candidate inventory; unscored services below scored ones; root abstention counts as zero; exact score ties use common expected-rank evaluator",
        "tuning_performed": False, "final_test_accesses": len(accessed & test_ids), "cases": records,
    }
    save_new(OUT / "baro_validation.json", output)
    print("BARO_VALIDATION_PASS", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
