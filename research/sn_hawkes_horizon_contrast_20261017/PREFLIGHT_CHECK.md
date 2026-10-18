# Real-input preflight

**READY — preflight PASS; actual process exit code 0.** All seed fits remain
gated on this result and were not run.

Command executed in this directory:

```text
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B run_horizon.py --preflight
```

The monitored process completed with exit code `0`, printed status `PASS`, and
published `preflight.status` as `PASS`. Evidence is in `preflight.json`.

Verified actual inputs: preparation manifest PASS; 394 allowed SN windows,
train 316 and validation 78; selected-input, preparation, metadata, frozen
baseline config, split, and scaler hashes are recorded in `preflight.json`.
The baseline scaler is array-exact. Native helper source hashes matched the
baseline contract. Runtime/model configuration checks passed.

The seed-11 relative-input first epoch matched the recorded baseline history:
training loss `1.620579801028288`, validation loss `1.5096815824508667`,
2 optimizer updates. This is the initialization/order/scaler/relative-epoch
parity proof; no full relative fit was performed.

Only the permitted selected SN rows were materialized. The preparation
disclosure records sequential ZIP decompression and discarding unselected
observation byte blocks without ndarray construction or numeric interpretation.
Protected SN observation values and TT/RE2 data were not materialized/accessed.
Original sources and results remain unchanged.

No fit was started. Focused tests were not rerun because the existing
`RUNNER_CHECK.md` records their passing result for this unchanged runner.
