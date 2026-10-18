# Training and selection-lock verification

**Verdict: FAIL — no global selection lock was created.** The required
successful monitored exits and `ROTATION_DONE` sentinels are absent. Per the
gate, lock generation was not attempted. No query evaluation was run.

## Rotation evidence

| Rotation | Upstream record | Actual launch evidence | Six matching run records | Result |
|---|---|---|---|---|
| 0 | `TRAIN_R0.md` | Reports monitor `bash_2`, actual exit code 2, `runner.py` not found (wrong working directory `/home/gnho1236/r2`), and no `FIT_PASS` or `ROTATION_DONE`. | No `rotation_0.done.json`; no matching six-run completion receipt. | FAIL |
| 1 | `TRAIN_R1.md` | Reports monitor `mon_HN8X6BCXR0CMSED0` / `bash_2`, watcher exit code 2, same wrong working directory and missing `runner.py`, and no `FIT_PASS` or `ROTATION_DONE`. | No `rotation_1.done.json`; no matching six-run completion receipt. | FAIL |
| 2 | `TRAIN_R2.md` is absent. `rotation_2.started.json` exists and binds the frozen source/input hashes. | No captured monitored exit code 0 or `ROTATION_DONE` evidence was found. A started marker alone is not completion evidence. | No `rotation_2.done.json`. Partial artifacts exist only for Eadro seeds 11/23/37 at stage 200; the other method’s three runs are not evidenced. These are not six matching completed runs. | FAIL |

R0/R1 receipt contents were read directly. The expected successful done
receipts for all rotations are missing. The partial R2 summaries each report
`best_epoch: 1`; they do not establish completed rotations, budget decisions,
or selected epochs. Therefore extended-rotation count, selected epochs, and
budget-bound flags are **not established**.

## Lock status and scope

`budgets.json` and `selection.lock.json` were both absent when checked. Since
the prerequisites fail, `/home/gnho1236/r2/.venv-eadro/bin/python -B runner.py
lock` was **not run**; there is no lock-command exit code or
`SELECTION_LOCKED18` output to report. No existing lock was reused. No fit,
training, input preparation, install, or query evaluation was performed in
this verification.

Accordingly, the independent lock checks (18 unique runs; 3 rotations × 2
methods × 3 seeds; target 200/400 matching each rotation’s six validation
records; 12/12/12 event counts; source/input/lock provenance; and zero query
evaluation) cannot pass or be claimed. Validation accuracy is not interpreted
as final performance.

## Frozen provenance references

The reviewed `RUNNER_GATE.md` pins these runtime sources:

| File | SHA-256 |
|---|---|
| `PLAN.md` | `5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470` |
| `EXECUTION.md` | `71ada6226f39f0aaa6360fc38e1cd7bd489174b2806ce65bd225015be9751d31` |
| `runner.py` | `025a8c94574719183a063ca422bbe722028ebbc661aefffafe099e6ce311b777` |
| `scores.py` | `9dc141146b364c04d0502cd8c3005522edeaf22b3976b397e28096c54799670c` |
| `input_bundle.py` | `e94a261509979157b4ec41f7558822c826e8038524aa3258d34686f743ae624d` |

The frozen input reference in `PRETRAIN_VERIFY.md` is `inputs.npz`
SHA-256 `ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`.
The started-marker provenance additionally records
`PRETRAIN_CHECKS.json` SHA-256
`cfa041024b2cd0e89f1cd42eab918b177efe5975b3c2522e7f8297ed256da3db`.
These are referenced upstream hashes, not a claim that a global lock was
generated or independently validated.

## Evidence reviewed

- `TRAIN_R0.md`, `TRAIN_R1.md`; `TRAIN_R2.md` missing.
- `DAG_PLAN.md`, `PLAN.md`, `RUNNER_GATE.md`, `PRETRAIN_VERIFY.md`.
- `rotation_2.started.json`; `rotation_{0,1,2}.done.json` missing.
- `runs/rotation_2`: only three Eadro seed stage-200 summaries were located.
- `budgets.json` and `selection.lock.json` missing.

## Latest verification — FAIL (2026-10-17)

The recovered producer evidence establishes actual successful completion for
all three original rotation monitors; the earlier DAG node's premature R2
running status was not used as proof:

| Rotation | Original monitor | Actual result and completion sentinel |
|---|---|---|
| 0 | `mon_7RY6DWGAZ9D7FME4` (parent `bash_8`) | `exit_code: 0`; six `FIT_PASS 0 {eadro,diagmlp} {11,23,37} 200`; `ROTATION_DONE 0 200`; `SN_ROTATION_0_RAW_EXIT=0` |
| 1 | `mon_D2NY7AVB2ZSWYJNS` (parent `bash_9`) | `exit_code: 0`; six `FIT_PASS 1 {eadro,diagmlp} {11,23,37} 200`; `ROTATION_DONE 1 200`; `SN_ROTATION_1_RAW_EXIT=0` |
| 2 | `mon_ZXNEXVAQTGGQJFPY` | `watcher completed (exit code 0)`; six `FIT_PASS 2 {eadro,diagmlp} {11,23,37} 200`; `ROTATION_DONE 2 200` |

The evidence is recorded in the updated `TRAIN_R0.md`, `TRAIN_R1.md`,
`TRAIN_R2.md`, `MAIN_TRAIN_EXECUTION.md`, and `TRAIN_RECOVERY.md`. The three
`rotation_{0,1,2}.done.json` receipts each report PASS and six runs (18 total),
and all 18 expected `history_200.json` paths exist. Rotation budget receipts
set all targets to 200; the largest listed best epoch is 70, below the
rotation-local `>=180` extension boundary, so no 400-epoch extension was
required. Expected update totals are 1000/1000/800 per run for rotations
0/1/2 respectively. These receipts and records establish producer completion,
but do not substitute for the runner's independent lock validation.

Before lock invocation, both global files were absent:
`research/sn_corrected_20261017/budgets.json` and
`research/sn_corrected_20261017/selection.lock.json`.

- Exact command run once:
  `/home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_corrected_20261017/runner.py lock .`
- Monitor/session: `bash_1`; actual exit code: **2**.
- Output: argparse usage error, `runner.py: error: unrecognized arguments: .`
- Required `SELECTION_LOCKED18` sentinel: **absent**.
- Result: the command did not create either global file. No retry with a
  different command was made, and no lock hash exists to record.
- Independent lock audit: **not performed**; there is no lock to audit.
  Consequently 18-entry lock uniqueness, per-entry file/hash/history checks,
  history-wide minimum and earliest-tie recomputation, paired initial-state
  hashes, and the lock's 12-events-per-part checks remain unverified here.
  No budget-bound flag was reported by this failed invocation; the recorded
  rotation-local 200-epoch extension condition is false for all rotations.
- Query evaluation: **not run**.

**Final verdict: FAIL — recovered training completions are evidenced, but the
required exact lock command exited 2 and no verified global selection lock
exists.** The original FAIL above is retained unchanged.

## Latest authoritative verification — PASS (2026-10-17)

Both earlier FAIL sections above are preserved. The trailing-dot command failure
was recovered by running the frozen runner's lock stage without any trailing
argument. No global lock files existed immediately before this run, so none
were overwritten.

- Exact command:
  `/home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_corrected_20261017/runner.py lock`
- Monitor: `mon_1SB5H0H5A9HPF2ZT` (`bash_1`)
- Actual monitor result: exit code **0**, completed.
- Sentinel: `SELECTION_LOCKED 18`.
- `selection.lock.json` SHA-256: `82b3c7897378690ef0526bd10d20fe7b728217e72a605035b96f27ba099281fa`
- `budgets.json` SHA-256: `3ff0fd51a236e4a74cda0ed857d9de8db2c3e6421897b1e9935300a9e24eb193`

An independent read-only audit of the generated lock, all three rotation
receipts/budgets, and all 18 run directories passed:

- The lock contains exactly the unique Cartesian set of rotations 0–2,
  `eadro`/`diagmlp`, and seeds 11/23/37. Each lock entry matches its rotation
  done receipt. The current frozen source files, input NPZ, and input manifest
  match their recorded hashes; every run's config, scaler, history, best
  checkpoint, and `last_200.pt` match the hashes recorded in its receipts and
  lock.
- Each full 200-row history has consecutive epochs and finite validation event
  NLLs. Recomputing `min((validation_event_nll, epoch))` over every epoch in
  each history reproduces the locked best epoch and NLL, including the
  earliest-epoch tie rule; no history had an exact tie at its minimum.
- For every rotation/seed pair, the Eadro and DiagMLP common-initial-state hash
  and tensor count match between configs and lock entries.
- All 18 fits ran 200 epochs. Rotation-local maximum best epoch at epoch 200
  was R0: 23, R1: 70, R2: 15; each is below the `>=180` extension trigger.
  Thus all targets are consistently 200 epochs, with no 400-epoch extension
  and all 18 `budget_bound` flags false.
- Per-fit updates are R0: 1,000; R1: 1,000; R2: 800. Each run's history also
  records the matching per-epoch update count.
- Using each run config's split indices against the frozen manifest, each
  train, validation, and evaluation part contains 12 distinct nonempty fault
  event IDs (normal rows have empty event IDs).
- The lock records `evaluation_opened: false`; no query evaluation was run.

Selected epochs and independently recomputed minimum validation event NLL:

| Rotation | Kind | Seed 11 (epoch / NLL) | Seed 23 (epoch / NLL) | Seed 37 (epoch / NLL) | Updates per fit | Budget-bound flags |
|---:|---|---:|---:|---:|---:|---|
| 0 | eadro | 1 / 2.5072251612739174 | 23 / 6.875896280397247 | 1 / 19.062090202585136 | 1,000 | false / false / false |
| 0 | diagmlp | 8 / 2.4180156397803625 | 3 / 2.491936224905237 | 2 / 2.4888628679861227 | 1,000 | false / false / false |
| 1 | eadro | 4 / 2.4848583739144106 | 1 / 17.958124542108763 | 1 / 2.774638360183085 | 1,000 | false / false / false |
| 1 | diagmlp | 31 / 1.9445361614042669 | 70 / 2.063366396988239 | 13 / 2.1776616504660176 | 1,000 | false / false / false |
| 2 | eadro | 1 / 2.483557827004891 | 1 / 2.458938361327883 | 1 / 2.537931720392998 | 800 | false / false / false |
| 2 | diagmlp | 15 / 2.146435066988127 | 11 / 2.2771370796557235 | 15 / 2.341076015347069 | 800 | false / false / false |

**Latest verdict: PASS — the 18-entry selection lock and requested fit checks
are verified.** The monitored lock process completed; no monitor remains
running. Query evaluation remains unopened.
