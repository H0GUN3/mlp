# Seed 23 execution receipt

**Status: PASS — one completed absolute-horizon fit.**

## Preserved interrupted attempt

The first producer was interrupted by the assistant before completion after an
earlier “do not wait” instruction was incorrectly applied to this explicitly
monitored run. Its monitor reported `killed`, exit code `1`; it emitted no
completion summary. Its files were preserved without content changes under
`runs/absolute_seed_23_interrupted_attempt1/` (`config.json`, `history.json`,
`checkpoint.pt`, and `validation_predictions.npz`). That history contains only
19 epochs / 38 optimizer updates and is not a completed model or validated
prediction artifact.

## Completed run

- Exact command:
  `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_hawkes_horizon_contrast_20261017/run_horizon.py --seed 23`
- Monitor `mon_ZZ1AKP8KQ95BXEFR`, session `bash_6`: **completed, actual exit
  code 0**. Captured output is preserved in
  `runs/absolute_seed_23/producer.log`.
- Producer summary: `PASS`; 200/200 epochs, 400/400 optimizer updates; no test
  evaluation. Best epoch is **115**, with minimum validation joint loss
  **0.10320687294006348**.
- Selection was independently checked against all 200 history rows; epoch 115
  is the minimum. The runner's post-load replay compared validation logits
  bitwise and loss exactly (`checkpoint_replay: bitwise predictions and exact
  loss`); the PASS summary was written only after those assertions.
- The first 19 interrupted and completed history rows match across all numeric
  training/validation fields and scores when timing fields are excluded.
- Preflight and preparation manifests both report PASS. Inputs are restricted
  to SN train 316 / validation 78. No protected observation rows were
  materialized; no TT/RE2 observations or SN test/unassigned observations were
  decoded or evaluated.
- Streaming disclosure: NPZ members were sequentially decompressed; unselected
  observation byte blocks were discarded without ndarray construction or
  numeric interpretation. `log_window` was decoded as structural indexing
  metadata, and only selected log fields were interpreted.

## SHA-256 evidence

Completed run artifacts (verified against the producer summary):

| File | SHA-256 |
|---|---|
| `runs/absolute_seed_23/config.json` | `5b73db88329ec8b8c72576c86c7e0f4b908746e3fead50c1521fae5c70476395` |
| `runs/absolute_seed_23/history.json` | `23969e73b5d2ea8bd3f31dd6cef443bd65c176a337fdab4afa4dcad33a805869` |
| `runs/absolute_seed_23/checkpoint.pt` | `798f750b81ba2d0f67dcce7b848000fd2af7f1999490afbcc4d9e55c14d12c8f` |
| `runs/absolute_seed_23/validation_predictions.npz` | `dc6e038caf47175f8e681a458918bf22f81c620f843be003b5810377a1fa97a6` |

Frozen runner/config/input/source hashes:

| File | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `optionalpyright_runner.json` | `6671ba22f20d6f2adb877cf22f8f9a42f87d215c554fbba4e50a47ec9c92828f` |
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/metadata.json` | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| `preflight.json` | `fe464580762a26665bc3f3fdce7407ad628ea1a057f92007d859db92bc4265fc` |
| `native_models.py` | `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632` |
| `native_train.py` | `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7` |

The run config also records and verifies the reused seed-23 baseline artifact
hashes. No source, shared configuration, original data, or existing result was
modified; no install, download, commit, or additional seed fit was performed.
