# Horizon runner implementation check

The runner consumes only the PASS preparation manifest, its metadata and the
selected 394-row `selected.npz`. It requires exactly `indices`, `metrics`,
`traces`, `logs`, `log_absolute`, and `labels`, and verifies the embedded
original indices against metadata order. It validates the producer hashes, SN-only
dimensions, train/validation positions and their exact order against the frozen
baseline split, and the baseline train-only scaler arrays. It reads baseline
`artifact_hashes` from each seed's `summary.json`; optional original-index and
scaler-hash metadata fields are not assumed. The metadata's
`forbidden_observation_rows_materialized: 0` and protection disclosure are
required and retained in reports.

The runner imports only frozen pure/model helpers from `native_train.py` and
`native_models.py`; it does not call `load_inputs`, `load_prepared`, or the
native training entry point. Preflight checks runtime versions, model config,
native source hashes, and seed-11 relative-input first-epoch history parity.
Training is gated on passing preflight and writes to
`runs/absolute_seed_SEED/` without overwriting. The old seed-specific baseline
validation indices and labels are compared without loading an old checkpoint.
Native initialization, Adam, NumPy `RandomState` epoch shuffling, batch size,
loss, validation order, strict-minimum/earliest-tie selection, and replay
semantics are retained.

The preparation disclosure states that ZIP members are sequentially
decompressed, including unselected byte blocks, which are discarded without
ndarray construction or numeric interpretation. `log_window` is fully decoded
as structural indexing metadata; selected values only are interpreted for
other prepared members. No protected observation values are intentionally
materialized by this runner.

## Verification status

The real prepared-schema integration checks are read-only and may load only
`inputs/selected.npz` (the permitted 394 rows). No real `--preflight`, relative
epoch parity run, or fit is performed by this runner implementation node.
Therefore no actual training result or parity PASS is claimed here. The
dependent preflight node must run `--preflight` before any seed fit.

## Commands and evidence

All commands ran on 2026-10-17. Initial invocation attempts used the wrong
working directory and an unavailable venv-local pyright executable. A later
test attempt also exposed an undersized synthetic `indices` fixture after the
original-index guard was added; the fixture was corrected. These failures were
preserved and not treated as passing results. The final commands ran in this
directory; `pyright` resolved from the shell environment.

```text
/home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_run_horizon
Ran 9 tests in 0.107s
OK
exit: 0

/home/gnho1236/r2/.venv-eadro/bin/python -B run_horizon.py --self-check
Ran 9 tests in 0.112s
OK
HORIZON_SELF_CHECK PASS
exit: 0

pyright --project optionalpyright_runner.json
0 errors, 0 warnings, 0 informations
exit: 0
```

The editor's standalone Pyright diagnostics still report unresolved `dgl` and
native-helper imports; the configured project CLI check above resolves them and
passes. No warnings or errors were suppressed.

SHA-256 (runner, test, type configuration):

| File | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `test_run_horizon.py` | `03d9ec77f2ccc569b437e6628cc55a3b1cbc5019807452d29e98cd4a5cce28e7` |
| `optionalpyright_runner.json` | `6671ba22f20d6f2adb877cf22f8f9a42f87d215c554fbba4e50a47ec9c92828f` |

SHA-256 (prepared input and baseline contract):

| File | SHA-256 |
|---|---|
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/metadata.json` | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| baseline seed 11 `config.json` | `84e6f67dd9518a950a95f57407aac66d107c7fa593008e65823c542940c30b51` |
| baseline seed 11 `summary.json` | `9e0f1ead56569c879f5543cf536d82065a14b1fc4736f607229576889c1187f8` |
| baseline seed 11 `split.json` | `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d` |
| baseline seed 11 `scaler.npz` | `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1` |

No real preflight, parity epoch, or training fit was run. `optionalpyright_runner.json`
was already present and remained unchanged.
