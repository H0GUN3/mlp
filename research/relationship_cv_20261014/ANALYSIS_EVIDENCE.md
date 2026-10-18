# CV aggregation evidence

- Test command: `cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest -v research.relationship_cv_20261014.test_analysis`
- Test exit code: `0` (`Ran 10 tests`; `OK`).
- Aggregation command: `cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_cv_20261014.analysis`
- Aggregation exit code: `0`; emitted `CV_ANALYSIS_COMPLETE`.
- Input: `results/runs.json`, SHA-256 `48129c9be79d251f5278a6ed79ccd72dca2373d10ef4e3f9038b0e9b055b6b13` (PASS; 54 reports).
- Analysis source: `analysis.py`, SHA-256 `6ad65e71a2d41252e5f8c8dc290d4a9893633bcd98bb57b76a6176a550fdd049`.
- Protocol source: `PROTOCOL.md`, SHA-256 `1d24e290525bade19beb96d7ad610889c417ad58d3f03635ff4d51b9c57a1e88`.
- Test source: `test_analysis.py`, SHA-256 `56bffa07e821e9241c72c559ff5b56fb50f4f1ca530f6ddc954692cb8371abd3`.
- Output: `results/analysis.json`, SHA-256 `3814b07ee7d5a255c02b419f5407a76bba96b3da9c75e0511ad07513a636b11e`. JSON embeds the matching `runs.json` and `analysis.py` hashes above.

## Fixed checks and decision

The manifest contains 36 SN incidents across 4 unique recording IDs and 81 TT incidents across 9 unique recording IDs. Seeds are averaged within each incident; they do not inflate incident counts. The summary uses 5,000 recording-cluster percentile bootstrap replicates with seed `20261014` and 2.5/97.5 percentiles.

The frozen criterion requires directed-minus-global mean Top1 to be positive in both systems and positive in at least 2 of 3 folds and 2 of 3 seeds for each. SN: mean `+0.09035894660894662`, positive folds `3/3`, positive seeds `3/3`. TT: mean `+0.00463229902672994`, positive folds `2/3`, positive seeds `2/3`. Decision: **`expansion_worth_considering`**.

This is only the protocol's exploratory continuation decision, not statistical significance or independent-population evidence. The bootstrap intervals are conditional on only 4 SN / 9 TT recordings and overlapping training sets.
