"""Declared TRAIN-only missing-data handling before the unchanged native scaler."""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "native_reproduction_20261013"))
from native_train import fit_scaler, scaled_partition


def prepare_partitions(arrays, parts):
    assert set(parts) == {"train", "validation"}
    train, validation = parts["train"], parts["validation"]
    assert len(train) and len(validation) and not set(train) & set(validation)
    raw = arrays["metrics"]
    observed = arrays["metric_observed"]
    assert raw.ndim == 4 and raw.shape[2:] == (10, 8)
    assert raw.dtype == np.float64 and observed.dtype == np.bool_
    np.testing.assert_array_equal(observed, np.isfinite(raw))
    assert not np.isinf(raw).any()
    for positions in parts.values():
        assert positions.dtype.kind in "iu" and len(set(positions)) == len(positions)
        assert np.all((positions >= 0) & (positions < len(raw)))
    train_values = raw[train]
    seen = observed[train]
    count = seen.sum(axis=(0, 2))
    total = np.where(seen, train_values, 0.).sum(axis=(0, 2))
    mean = np.divide(total, count, out=np.zeros_like(total), where=count > 0)
    supported = count > 0
    filled = np.where(observed, raw, mean[None, :, None, :])
    filled = np.where(supported[None, :, None, :], filled, 0.)
    prepared = dict(arrays, metrics=filled)
    stats = fit_scaler(prepared, train)
    stats.update(metric_impute_mean=mean, metric_supported=supported,
                 metric_train_observed_count=count)
    data = {name: scaled_partition(prepared, positions, stats)
            for name, positions in parts.items()}
    report = {
        "train_windows": len(train), "validation_windows": len(validation),
        "unsupported_train_node_channels": int((~supported).sum()),
        "validation_observed_cells_masked_as_unsupported": int(
            (observed[validation] & ~supported[None, :, None, :]).sum()),
        "missing_metric_cells": {
            name: int((~observed[positions]).sum()) for name, positions in parts.items()},
        "constant_metric_channels": int(stats["metrics_constant"].sum()),
        "constant_trace_channels": int(stats["traces_constant"].sum()),
        "max_absolute_normalized": {
            name: {kind: float(np.max(np.abs(values[kind]))) for kind in ("metrics", "traces")}
            for name, values in data.items()},
        "policy": "TRAIN mean impute; unsupported TRAIN node/channel zeroed; native scaler eps1e-8",
    }
    return stats, data, report
