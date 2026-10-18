# Fixed CV checkpoint replay evidence

- Command: `cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_cv_20261014.cv verify`
- Monitor ID: `mon_7VNCPXYAMXJGS4NM`
- Exit code: `0`
- Completion sentinel: `CV_VERIFY_COMPLETE 54 9.054024618992116 899052`
- Replay checks: all 54 checkpoints emitted `CV_REPLAY_OK`; each replay compared saved predictions and ranking metrics and passed the independent Top1 scorer check.
- Result: runner-generated `results/verification.json` reports `status=PASS`, `run_count=54`; its source and input SHA-256 maps exactly match `results/runs.json`.
- Elapsed: `9.054024618992116` seconds (runner-reported).
- Peak RSS: `899052` KiB (runner-reported).
- No fit, tuning, source edit, or overwrite was performed.
