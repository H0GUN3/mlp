# Independent prediction verification

Status: **PASS** for both independent artifact verification and the recovered
original evaluation launch. The duplicate launch failure is not attributed to the
original run.

The checker independently computes float64 stable window log-softmax,
event log-mean-exp pooling, NLL, and uniform exact-tie Top-1/Top-3 credits.
Five focused tests passed, including all-equal 12-way ties (Top-1 1/12,
Top-3 3/12), normal exclusion, extreme logits, multi-window aggregation, and
wrong label/index mapping rejection.

The monitored test command exited **0** (`Ran 5 tests`, `OK`). The monitored
read-only replay exited **0** and emitted `VERIFY_PASS 18 54` for 18 unique runs
and all 54 prediction files. All frozen selected checkpoints were reloaded and
replayed through the frozen model/inference helpers. Root and detection logits
matched bitwise; labels, event IDs, and original indices matched split-derived
inputs exactly. TRAIN-only scalers matched exactly. The independent event
probabilities/NLL agreed within `1e-12`; maximum pooled log-probability
difference was `2.842170943040401e-14`, and Top-1/Top-3 tie credits matched
exactly. Out-of-fold event coverage was 36 unique events for each model/seed.
Normal windows were excluded. Frozen source, permitted input, selection, and
checkpoint hashes and the existing protection audit passed; raw streams were
not rescanned.

Commands used (both ran with Python 3.8 from the existing environment):

```sh
cd /home/gnho1236/r2/research/sn_corrected_20261017 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_verify_results
cd /home/gnho1236/r2/research/sn_corrected_20261017 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_corrected_20261017/verify_results.py
```

Configured native LSP diagnostics reported **“No diagnostics found”** for both
new files: `verify_results.py` and `test_verify_results.py`. No tests or replay
were rerun for this documentation-only update.

Producer provenance is separately **PASS**: corrected `EVAL_EXECUTION.md`
identifies the original `bash_1` runner session as exit **0** with
`EVALUATION_PASS 18`. The later duplicate attempt exited 1 at the existing
directory guard before inference; it did not overwrite the completed artifacts.
