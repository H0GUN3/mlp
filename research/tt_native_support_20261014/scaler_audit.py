"""Read-only explanation of six extreme scaled validation cells; no model fitting."""
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.tt_native_support_20261014 import experiment as ex

METRIC_NAMES = ("cpu_usage_system", "cpu_usage_total", "cpu_usage_user",
                "memory_usage", "memory_working_set", "rx_bytes", "tx_bytes")


def execute():
    arrays, metadata, inputs = ex.load_data()
    findings = []
    for fold in ex.FOLDS:
        parts, stats, transformed = ex.prepare_fold(arrays, fold)
        for modality in ("metrics", "traces"):
            values = transformed["validation"][modality]
            local_row, node, second, channel = np.unravel_index(np.abs(values).argmax(), values.shape)
            row = int(parts["validation"][local_row])
            raw = float(arrays[modality][row, node, second, channel])
            mean = float(stats[modality + "_mean"][node, channel])
            std = float(stats[modality + "_std"][node, channel])
            scaled = float(values[local_row, node, second, channel])
            expected = np.float32((raw - mean) / (std + ex.native_train.EPSILON))
            if scaled != float(expected):
                raise AssertionError("Scale formula not reproduced exactly")
            event = str(arrays["event_ids"][row])
            fault = metadata["faults"].get(event)
            root = int(arrays["labels"][row])
            training_values = arrays[modality][parts["train"], node, :, channel]
            findings.append({
                "fold": fold, "modality": modality, "original_index": int(arrays["indices"][row]),
                "service": metadata["services"][node], "second_offset": int(second),
                "channel": METRIC_NAMES[channel] if modality == "metrics" else "latency_seconds",
                "raw_value": raw, "train_mean": mean, "train_std": std,
                "train_constant": bool(stats[modality + "_constant"][node, channel]),
                "train_min": float(training_values.min()), "train_max": float(training_values.max()),
                "scaled_value": scaled, "denominator_epsilon": ex.native_train.EPSILON,
                "event_id": event, "fault_type": fault["fault_type"] if fault else None,
                "true_root": metadata["services"][root] if root >= 0 else None,
                "extreme_is_root": bool(node == root),
            })
    for path, digest in inputs.items():
        ex.errors.check_hash(path, digest)
    result = {"status": "PASS", "cells_checked": len(findings), "findings": findings,
              "input_hashes": inputs, "experiment_source_hashes": ex.source_hashes(),
              "training_or_scaler_changes": False,
              "limit": "Six prespecified maxima explain magnitude, not every error or a validated new normalization."}
    ex.write_json(HERE / "scaler_audit.json", result)
    print("SCALER_AUDIT_PASS", len(findings), flush=True)


if __name__ == "__main__":
    execute()
