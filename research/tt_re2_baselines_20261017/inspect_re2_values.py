"""One existing TRAIN case: validate cross-modal service names and clock units."""
from collections import Counter
import json
import os
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from inspect_re2_schema import DATA, HERE, MANIFEST, allow_case, digest


def main():
    assert __debug__
    lock = json.loads(MANIFEST.with_name("split.lock.json").read_text())
    assert digest(MANIFEST) == lock["sha256"]
    manifest = json.loads(MANIFEST.read_text())
    row = next(r for r in manifest["cases"]
               if r["dataset"] == "RE2-OB" and r["partition"] == "train")
    allow_case(row)
    folder = DATA / row["case"]
    sizes = {name: (folder / (name + ".parquet")).stat().st_size
             for name in ("metrics", "logs", "traces")}
    available = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    assert sum(sizes.values()) * 30 < available / 4, "Use streaming for this case"
    metrics = pq.read_table(folder / "metrics.parquet")
    timestamps = metrics["time"].to_numpy()
    assert timestamps.dtype.kind in "iu" and len(timestamps) > 10
    assert np.all(np.diff(timestamps) > 0)
    services = sorted({name.partition("_")[0] for name in metrics.column_names if name != "time"})
    nonfinite = {}
    for name in metrics.column_names:
        if name != "time":
            nonfinite[name] = int((~np.isfinite(metrics[name].to_numpy())).sum())
    logs = pq.read_table(folder / "logs.parquet", columns=["timestamp", "container_name"])
    log_names = Counter(logs["container_name"].to_pylist())
    log_times = logs["timestamp"].to_numpy()
    assert log_times.dtype.kind in "iu"
    traces = pq.read_table(folder / "traces.parquet",
                           columns=["serviceName", "startTime", "startTimeMillis", "duration"])
    trace_names = Counter(traces["serviceName"].to_pylist())
    start_us, start_ms = traces["startTime"].to_numpy(), traces["startTimeMillis"].to_numpy()
    durations = traces["duration"].to_numpy()
    assert start_us.dtype.kind in "iu" and start_ms.dtype.kind in "iu"
    assert np.all(start_us // 1000 == start_ms), "Trace time coordinates disagree"
    assert durations.dtype.kind in "iu" and np.all(durations >= 0)
    bounds = int(timestamps.min()), int(timestamps.max())
    report = {
        "status": "PASS_ONE_TRAIN_CASE", "case": row["case"], "partition": row["partition"],
        "split_sha256": lock["sha256"], "source_sha256": digest(Path(__file__)),
        "metric_rows": len(timestamps), "metric_services": services,
        "metric_cadence_counts_seconds": {str(int(k)): int(v) for k, v in zip(
            *np.unique(np.diff(timestamps), return_counts=True))},
        "metric_nonfinite_columns": {k: v for k, v in nonfinite.items() if v},
        "metric_time_range_seconds": bounds, "injection_time": row["inject_time"],
        "log_rows": len(log_times), "log_container_counts": dict(log_names),
        "log_time_range_seconds": [int(log_times.min()), int(log_times.max())],
        "logs_outside_metric_range": int(((log_times < bounds[0]) | (log_times > bounds[1])).sum()),
        "trace_rows": len(start_us), "trace_service_counts": dict(trace_names),
        "trace_start_us_range": [int(start_us.min()), int(start_us.max())],
        "trace_duration_source_unit": "Jaeger duration microseconds; converted /1e6 for seconds",
        "duration_unit_source": "https://pkg.go.dev/github.com/jaegertracing/jaeger/model/json#Span",
        "trace_duration_us_quantiles": np.quantile(durations, [0, .5, .99, 1]).tolist(),
        "trace_start_us_div1000_matches_millis": True,
        "traces_outside_metric_range": int(((start_us < bounds[0] * 1000000) |
                                           (start_us >= (bounds[1] + 1) * 1000000)).sum()),
        "log_names_not_metric_names": sorted(set(log_names) - set(services)),
        "trace_names_not_metric_names": sorted(set(trace_names) - set(services)),
        "file_bytes": sizes, "available_ram_bytes_before": available,
        "protected_case_files_opened": 0, "templates_or_scalers_fitted": False,
        "warning": "One TRAIN case only; not a full-cohort compatibility verdict",
    }
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    with (HERE / "RE2_VALUE_PROBE.json").open("x") as stream:
        stream.write(payload)
    print(payload)
    print("RE2_VALUE_PROBE_PASS ONE_TRAIN_CASE PROTECTED_OPENED_0", flush=True)


if __name__ == "__main__":
    main()
