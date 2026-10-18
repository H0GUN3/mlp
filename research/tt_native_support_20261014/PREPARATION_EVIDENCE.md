# TT preparation evidence

## Pre-execution checks

- Eight focused tests passed before real data preparation. Actual synthetic
  Hawkes fit: 21 iterations, no warnings; repeat with identical seed was exact.
- Initial test run failed because the test's manually transcribed fold row
  counts were wrong. The immutable allowed bundle gives fold0=1366, fold1=1368,
  fold2=1335; the test was corrected to those observed values and rerun.
- Corrected pre-execution run: `Ran 8 tests in 0.542s`, `OK`,
  `TEST_RAW_EXIT=0`.
- Explicit project Pyright was limited to `prepare.py` and `test_prepare.py`:
  `0 errors, 0 warnings, 0 informations`, `PYRIGHT_RAW_EXIT=0`.
- Workspace LSP was also run. `prepare.py` was clean; `test_prepare.py` reported
  an unresolved new preparation-module import. The repository-root LSP config
  targets `scripts` and `.venv-mlp`, whereas the explicit owned-project check
  targets this directory and `.venv-eadro`. No shared config was modified or
  diagnostic suppressed.

## Retained first attempt

`artifacts/preparation_20261014T073920_505150Z/failure.json` and `progress.log`
retain the first preprocessing failure, before template or raw-data processing:

```text
PREPARE_START workers=4 utc=2026-10-14T07:39:20.505316+00:00
PREPARE_FAILED seconds=0.048187
ValueError: Native pure-function sources changed
PREPARE_RAW_EXIT=1
```

The local guard initially compared the final frozen `native_data.py` to the
historical pre-build preparation snapshot in `TT_metadata.json`.
Current SHA256 `05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986`
exactly matches the allowed manifest's
`provenance.native_source.feature_build_source_sha256`; the prior preparation
snapshot hash starts `3ef8683a`. The guard now pins the current frozen module
against the permitted final-build provenance. This corrected the local check,
not any frozen source, metadata, parameter, or input schema.

## Successful execution

Diagnostics: `artifacts/preparation_20261014T074043_892941Z/`.
The already-active producer was allowed to finish without being rerun.
Producer monitor `mon_CMSZCMS12YQ3QTBD` / `bash_13` completed with actual
process exit code 0; its retained raw output includes:

```text
TEST_RAW_EXIT=0
PYRIGHT_RAW_EXIT=0
HAWKES_PROGRESS fits=7845/7845 wall_seconds=209.3934 iteration_counts={'50': 5585, '11': 2037, '21': 113, '41': 76, '31': 34}
PREPARE_COMPLETE seconds=234.812058 sha256=2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597 solver_caps=5585 warnings={}
PREPARE_RAW_EXIT=0
```

- Start UTC: `2026-10-14T07:40:43.893105+00:00`.
- Auxiliary normal TRAIN: 41,004 reference lines, 59 exact-matching templates,
  `event_count=60`, 5.338116 seconds.
- All nine selected recordings passed exact reconstructed per-second retained
  count and duplicate-weighted latency equality against the allowed values.
- Hawkes: 7,845 nonempty selected node/window tasks, four workers,
  native `max_iter=50`. Iterations/cap hits and warnings are retained per task,
  not treated as convergence evidence.

### Published files and SHA256

| File | SHA256 |
|---|---|
| `artifacts/TT.npz` | `2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597` |
| `artifacts/TT.json` | `07c3ad8ae9331dc4d48b0e4a728e34a9d5bf2c87c985d8792d9d50220f355948` |

`success.json` retains both hashes, every shape/dtype, exact publication
round-trip equality, and unchanged source/input hashes.
Final NPZ was published with an exclusive hard link from
`TT.npz.partial`; final JSON used exclusive creation. The completed publication
bytes and failed first attempt remain retained.

| Array | dtype | Shape |
|---|---|---|
| metrics | float64 | [4069,27,10,7] |
| traces | float64 | [4069,27,10,2] |
| logs | float64 | [4069,27,60] |
| unique_count | int64 | [4069,27] |
| labels / indices / fold_ids | int64 | [4069] |
| event_ids / episode_ids | Unicode `<U46` | [4069] |

### Actual processing cost

| Stage | Seconds |
|---|---:|
| Auxiliary template TRAIN | 5.338116 |
| Selected log routing/matching, including source scan/hash | 6.308297 |
| Selected span routing/counting, including source scan/hash | 6.307783 |
| Hawkes wall time, including worker lifecycle | 209.706388 |
| Hawkes summed task fit time across workers | 817.599875 |
| Preparation through NPZ publication/reload, before JSON serialization | 234.770311 |
| Completed preparation including metadata publication | 234.812058 |

Peak parent RSS: 446,812 KiB. Maximum completed-child RSS: 375,220 KiB.
These separate maxima are not a sampled aggregate peak.
All OMP/MKL/OPENBLAS environment limits were 1; Python bytecode writing was
disabled. No model training/inference cost is included or claimed.

### Solver outcome, without a convergence claim

- 7,845 actual fits; 102,018 empty node/window groups retain zero vectors.
- Iterations: 11→2,037; 21→113; 31→34; 41→76; 50→5,585.
- Iteration-cap hits: **5,585**. These are explicitly disclosed, not hidden
  by changing solver defaults or extending its budget.
- Captured solver warnings: `{}`; nonfinite outputs: 0. Every baseline was
  finite and nonnegative; invalid baselines would fail preparation.
- `solver.jsonl` has exactly 7,845 distinct selected `(row,node)` records,
  with original index, `42+original_index*27+node` seed, iterations,
  warnings and actual fit seconds.

### Independent post-publication verification

Monitor `mon_GCX03WB8FWXB327H` / `bash_15` completed with actual exit code 0:

```text
VERIFICATION_COMPLETE
VERIFY_RAW_EXIT=0
```

The independent assertion run loaded only the allowed development bundle and
the newly published selected-only NPZ; native inputs were metadata only.
It checked:

1. Exact nine output keys, shapes/dtypes, finite float arrays, nonnegative logs,
   all-zero native trace channel1, exact original metrics and latency.
2. Exact indices/order/labels/events/episodes/folds/windows/faults; 81 incidents,
   3,451 fault and 618 normal windows. Static graph is 44 author pairs.
3. Original mask: TRAIN 3,256 + validation 813 = 4,069 selected rows;
   protected test 1,744 + unassigned 1 have zero output overlap.
4. Fold support:

   | Fold | TRAIN windows | Validation windows | Validation normals | TRAIN / validation incidents |
   |---|---:|---:|---:|---:|
   | 0 | 2703 | 1366 | 207 | 54 / 27 |
   | 1 | 2701 | 1368 | 195 | 54 / 27 |
   | 2 | 2734 | 1335 | 216 | 54 / 27 |

   Each validation fold supports every service once; TRAIN supports each twice.
5. Output NPZ hash equals metadata; allowed input and all current source hashes
   remain unchanged. Every raw log/span and auxiliary-reference digest matches
   the permitted prior source provenance.
6. Exactly 59 original templates and three designated normal TRAIN references;
   no evaluation-template fit. Selected log total: 57,553.
7. Unique span total 23,171; retained occurrence total 98,775. Each recording's
   unique total independently equals the allowed manifest's prior
   `distinct_selected_spans`; retained totals match allowed counts.
8. Every solver record's original index and seed; iteration/warning/cap
   summaries agree with raw task records. All 102,018 groups without a recorded
   fit are exactly zero. No convergence claim or prohibited evaluation.

Preparation and artifact verification are complete. Baseline/model/scaler work
remains the parent's scope. The workspace-LSP import-resolution issue above
remains disclosed; explicit owned-project Pyright and actual runtime checks pass.
