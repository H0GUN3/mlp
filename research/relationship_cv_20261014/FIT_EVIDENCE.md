# Fixed development CV run evidence

- Command: `cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_cv_20261014.cv run`
- Monitor ID: `mon_HSBEZJ4Y0K0P89CX`
- Exit code: `0`
- Completion sentinel: `CV_RUN_COMPLETE 54 39.554640357993776 898688`
- Result: `results/runs.json` reports `status=PASS`, `run_count=54`; 54 unique system/fold/seed/mode identities, each at exactly 5 epochs.
- Elapsed: `39.554640357993776` seconds (runner-reported).
- Peak RSS: `898688` KiB (runner-reported).
- Artifacts: 54 each of `report.json`, `config.json`, `history.json`, `checkpoint.pt`, and `predictions.npz`; six fold `statistics.npz` files (276 hashed artifacts total).
- Provenance: all 11 source and 4 input SHA-256 hashes in `runs.json` matched the current files. The runner records `test_evaluated=false`, `rcaeval_access=false`, and `rcabench_access=false`.
- Pre-run verification: the required unittest command passed (5 tests); diagnostics on `cv.py` and `test_cv.py` found no issues. Directory-wide diagnostics also reported one unrelated pre-existing import error in `test_analysis.py` (`analysis` unknown); no source was changed.

No rerun, tuning, or additional fits were performed.
