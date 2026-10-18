# Absolute-horizon seed 11 execution receipt

## Result

- Producer command exited **0**; the completion event reported `status: PASS`.
- Run summary: `runs/absolute_seed_11/summary.json`
- 200/200 epochs; 400 optimizer updates; test data not evaluated.
- Selected epoch 190, validation joint loss `0.171455979347229`.
- Selection policy: strict minimum validation joint loss, earliest tie.
  The runner saved the checkpoint on strict improvements; its summary records
  epoch 190, and post-load validation replay matched predictions bitwise and
  loss exactly.
- Preparation/preflight gates: PASS (`inputs/preparation.json`,
  `preflight.json`; `preflight.status` is `PASS`).

## Command and log evidence

```text
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_hawkes_horizon_contrast_20261017/run_horizon.py --seed 11
```

The monitored producer output reported PASS, best epoch 190, 200 epochs, and
400 updates; the monitor completion reported exit code 0. This was filtered
monitor output, not a separately persisted full stdout/stderr logfile.

## Frozen inputs and code hashes

SHA-256 values recorded in `runs/absolute_seed_11/config.json`:

| Item | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `optionalpyright_runner.json` | `6671ba22f20d6f2adb877cf22f8f9a42f87d215c554fbba4e50a47ec9c92828f` |
| Native `native_models.py` | `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632` |
| Native `native_train.py` | `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7` |
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| Baseline config | `84e6f67dd9518a950a95f57407aac66d107c7fa593008e65823c542940c30b51` |
| Baseline split | `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d` |
| Baseline scaler | `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1` |

The saved run-config SHA-256 is
`f3edfbfd0b9266dd2334cdf387a25725fc77aef90211947b140fdd5de2d4937c`.

## Produced artifact hashes

Recorded by the run summary:

| Artifact | SHA-256 |
|---|---|
| `runs/absolute_seed_11/config.json` | `f3edfbfd0b9266dd2334cdf387a25725fc77aef90211947b140fdd5de2d4937c` |
| `runs/absolute_seed_11/history.json` | `ad3cb636667ee40dc18439b7f36796945122b3b48edc362ad3892a53a0cc9b78` |
| `runs/absolute_seed_11/checkpoint.pt` | `0c17b822424230553ec960bd6c914c87eb53034cbdba32058c4288fe93bb7248` |
| `runs/absolute_seed_11/validation_predictions.npz` | `0f45452113bf34bbce87458be49c5dbfbadf75611a228ff32254f004a58d9b6b` |

Only the allowed SN train/validation inputs were used. The preparation manifest
records zero forbidden observation rows materialized and discloses sequential
ZIP decompression with unselected observation bytes discarded without array
construction or numeric interpretation. Protected SN rows and TT/RE2 data were
not materialized/accessed.
