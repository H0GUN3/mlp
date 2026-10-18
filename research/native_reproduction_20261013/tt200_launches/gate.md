# TT200 launch-registration gate

**Result: PASS — launch registration only.** The six records cover exactly
`eadro` × seeds 11/23/37 and `diagmlp` × seeds 11/23/37. Each command uses
`--epochs 200 --lr 0.001 --batch-size 256 --threads 2`, consistent with the
separately labelled 200-epoch calibration described in `CALIBRATION_BUDGET.md`.
All output directories are distinct. No command has a trailing dot argument.

| Kind / seed | Command (from repo root) | Monitor identity |
|---|---|---|
| eadro / 11 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind eadro --seed 11 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/eadro/seed_11` | `mon_1CKM1M8V3GYMQMYN` |
| eadro / 23 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind eadro --seed 23 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/eadro/seed_23` | `mon_YY8BQXN23SXGZTTX` |
| eadro / 37 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind eadro --seed 37 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/eadro/seed_37` | `mon_5CTBJSP1VCDHQF2P` |
| diagmlp / 11 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind diagmlp --seed 11 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/diagmlp/seed_11` | `mon_KGVQMDWDPHE7T07Y` |
| diagmlp / 23 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind diagmlp --seed 23 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/diagmlp/seed_23` | `mon_10PH1FREV6GN4R7A` |
| diagmlp / 37 | `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --system TT --kind diagmlp --seed 37 --epochs 200 --lr 0.001 --batch-size 256 --threads 2 --output-dir research/native_reproduction_20261013/calibration200/TT/diagmlp/seed_37` | `mon_RA26V807BEX8ESF2` |

Records report monitor registration for all six. No immediate launch error is
recorded; eadro/11 notes the monitor was registered against the already-live
PID after the initial launch call omitted its identity. Parent must await all
six `summary.json` files, then run the independent verifier. These records do
not establish training completion or make any accuracy claim; propagate any
immediate launch error if one is observed.
