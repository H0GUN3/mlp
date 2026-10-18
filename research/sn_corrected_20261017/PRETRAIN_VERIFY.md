# SN pretraining gate: independent verification

**Verdict: PASS — training may proceed only with the frozen sources and input
bundle recorded in `PRETRAIN_CHECKS.json`.** Verified 2026-10-17 from the
selected bundle and repository metadata. No producer was edited. This
verification did not fit, train, or evaluate a model and did not open native
protected observation rows.

## Upstream gate artifacts

All required upstream artifacts exist and contain captured execution evidence,
not task-completion claims alone:

| Artifact | Result and captured evidence |
|---|---|
| `INPUT_GATE.md` | PASS; cites actual monitored input verification/preparation and Pyright output, including `watcher completed (exit code 0)`. Its linked `INPUT_VERIFY.md` records monitor `mon_ZNVN0Z2146XWKXQ6` / session `bash_9`, with 15 tests `OK`, preparation PASS, and exit 0. It also records independent verify/hash monitor exit 0. |
| `SCORE_GATE.md` | PASS; includes full actual output for 22 `test_scores` tests, `OK`, exit 0, and Python/NumPy versions. |
| `RUNNER_GATE.md` | PASS; includes actual `test_runner` output (6 passed), Pyright output (0 errors, warnings, or informations; exit 0), and CLI help output. |
| `PLAN.md` | Present; fixed protocol, permitted input scope, splits, model-selection rule, and per-rotation budget rule. Its hash is pinned below. |

The upstream artifacts are corroborated by this independent full-suite and
selected-input verification below. Their results were not accepted solely
because a node/task completed.

## Independent checks

Required command, run from this directory:

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_input_bundle test_scores test_runner
```

**Exit 0; 43 tests passed** (`Ran 43 tests in 0.576s`, `OK`). A PyTorch
autocast warning noted that CUDA is unavailable and was disabled; the affected
synthetic test passed.

```sh
pyright --project pyrightconfig.json
```

**Exit 0; 0 errors, 0 warnings, 0 informations.** Checker version: 1.1.408.
Runtime used: Python 3.8.20, NumPy 1.21.5, PyTorch 1.12.1+cpu, DGL 0.9.1.

Read-only loading through `input_bundle.load_inputs()` plus
`input_bundle.py verify` independently confirmed:

- 394 selected rows: 325 fault and 69 normal; 36 event IDs and 36 episodes.
- Three rotations are mutually disjoint and cover the selected rows exactly.
  Each fold has 12 events, all 12 roots and all three fault types; per-fold
  rows are 132/122/140. Rotation `(train, validation, evaluation)` row counts
  are `(140,122,132)`, `(132,140,122)`, `(122,132,140)`.
- Shapes are metrics `[394,12,10,7]`, traces `[394,12,10,2]`, logs
  `[394,12,7]`; trace channel 1 has zero nonzero values.
- Metadata validation checks event/episode/fold assignment, normal-window
  nearest-event episode assignment and isolation, ordered non-overlapping
  selected windows, labels and the full pinned provenance contract.
- Manifest protection flags record 394 permitted rows, 169 excluded test
  rows, one excluded unassigned row, and zero protected rows decoded. The
  excluded 170 original indices do not appear in the selected cache.
- The manifest declares inputs unnormalized. Drain template provenance is
  three separate `no fault/SN.*` recordings (53,522 lines), hash-bound and
  designated an external normal reference shared across rotations. The
  source cache is hash-bound; raw streams were not rescanned.

`runner.py` source inspection confirms `evaluate()` reads and validates
`selection.lock.json` before loading inputs or producing predictions.
`rotation_target()` requires exactly six 200-epoch summaries and bases the
200-to-400 choice only on those same-rotation validation best epochs
(`>=180`). `train-rotation` checks the PASS status and matching source/input
hashes before starting any fit. No evaluation, fit, or training command was
run for this verification.

## Frozen training allowlist

The only selected observation input authorized by this gate is
`inputs.npz`, SHA-256
`ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`.
Its associated manifest is `input_manifest.json`; file SHA-256
`50169ccbf81bcb1485f0a837fe164cd95628cf3c6161ec7c43f8b78c887ee2d0`.
Manifest payload SHA-256:
`290dd02afad9249af5acc25d325cf6ff83ab33012cab707089c0e36cd26a49d6`.

The exact runtime source allowlist is the `source_hashes` mapping in
`PRETRAIN_CHECKS.json`, as returned by `runner.sources()`. It includes the
plan, execution record, runner/scoring/input code and tests, native model/train
code, and model source. Any source or input hash mismatch invalidates this
authorization; do not update the allowlist by ignoring a difference.

## Boundaries and interpretation

No protected native rows were decoded, no native source preparation was
rerun, and no training/evaluation was performed. Compressed source cache hashes
and existing metadata provenance are reused; raw streams and external normal
recordings were not independently reopened. This gate freezes the existing
selected cache; it makes no new raw-source, solver-convergence, or model
performance claim. This PASS authorizes later fitting under the frozen hashes,
not evaluation before the runner’s selection lock.
