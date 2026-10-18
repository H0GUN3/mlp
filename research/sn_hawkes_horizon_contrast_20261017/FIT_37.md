# Seed 37 absolute-horizon execution receipt

**Status: PASS.** The sole authorized seed-37 fit completed successfully.

- Date: 2026-10-17.
- Actual producer result: monitor completion `status: PASS`, `exit code 0`;
  reported 200 epochs and 400 optimizer updates.
- Command:
  `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_hawkes_horizon_contrast_20261017/run_horizon.py --seed 37`
- Preflight and input-preparation gates were both PASS before launch.
  Preflight recorded 394 allowed SN rows (train 316, validation 78), with
  protected observation values not materialized. Its streaming disclosure
  states that ZIP members were sequentially decompressed; unselected
  observation bytes were discarded without ndarray construction or numeric
  interpretation, while `log_window` was decoded as structural indexing data.
- Selection: best epoch **164**, minimum validation joint loss
  **0.06605657935142517**. Independently checked all 200 history entries;
  epoch 164 is the strict minimum, and summed optimizer updates are 400.
- Checkpoint validation replay: trainer summary reports bitwise prediction
  equality and exact loss after checkpoint reload.
- Test evaluation: false.

## Provenance hashes (SHA-256)

Frozen preflight/input:

| File | SHA-256 |
|---|---|
| `preflight.json` | `fe464580762a26665bc3f3fdce7407ad628ea1a057f92007d859db92bc4265fc` |
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/metadata.json` | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |

Trainer/code:

| File | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `optionalpyright_runner.json` | `6671ba22f20d6f2adb877cf22f8f9a42f87d215c554fbba4e50a47ec9c92828f` |
| `runs/absolute_seed_37/config.json` | `b58e79cefa1837b85d2befe5d40b50a0ab988ee29406169405245ed117d04411` |
| `runs/absolute_seed_37/history.json` | `fc8436a35df7713b6c6c58674aa5e964fcc207032abf1db471cf1f21472dd90d` |
| `runs/absolute_seed_37/checkpoint.pt` | `596a602ea4394ad39b8ab2eaeb885981a6264916534bf99c8d5e20d5f636a615` |
| `runs/absolute_seed_37/validation_predictions.npz` | `af678df5966fac884ac25eff08583fe692c01d11fff45590563884f24cb4add4` |

The trainer's `summary.json` contains these four run-artifact hashes and
reports `status: PASS`, 200 epochs, 400 updates, and successful checkpoint
replay. The trainer output directory contains `config.json`, `history.json`,
`checkpoint.pt`, `validation_predictions.npz`, and `summary.json`.

**Logging note:** the monitored producer reported its completion status and
summary fields, but no separate persistent stdout logfile was created. No
failure or partial artifact was overwritten or retried.
