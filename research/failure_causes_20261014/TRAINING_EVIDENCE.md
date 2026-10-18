# Lane B verification evidence — 2026-10-14

Only `training.py`, `test_training.py`, `training.json`, `TRAINING.md`, and this
file were created by this lane. No old source/artifact was modified. Python used
`-B` and `PYTHONDONTWRITEBYTECODE=1` to avoid bytecode writes outside the allowlist.
No installation, commit, training, optimizer/backward call, feature fitting,
perturbation, native loader or CV execute/run was used. Native source files were
hashed as source bytes only; raw/native/protected/RCAEval/RCABench observations
were not opened and raw provenance paths were not followed.

## Producer and synthetic tests

Monitor: `mon_YBQ5XND4Z82XQGNM`, terminal `bash_2`.
The following sequential command completed with **raw exit code 0**, establishing
both the tests and producer succeeded:

```sh
cd /home/gnho1236/r2 &&
PYTHONDONTWRITEBYTECODE=1 /home/gnho1236/r2/.venv-eadro/bin/python -B \
  -m unittest discover -s research/failure_causes_20261014 -p test_training.py -v &&
PYTHONDONTWRITEBYTECODE=1 /home/gnho1236/r2/.venv-eadro/bin/python -B \
  research/failure_causes_20261014/training.py
```

Raw terminal result:

```text
status: completed exit_code: 0
test_exact_ties_and_cross_entropy (test_training.TrainingTests) ... ok
test_history_deltas_are_not_inference_ce (test_training.TrainingTests) ... ok
test_stable_ce_and_nonleading_tie (test_training.TrainingTests) ... ok
test_window_then_fold_seed_then_incident_equal (test_training.TrainingTests) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.004s

OK
TRAINING_REPLAY_OK SN 0 11 local
TRAINING_REPLAY_OK SN 0 11 global
TRAINING_REPLAY_OK SN 0 11 directed
TRAINING_REPLAY_OK SN 0 23 local
TRAINING_REPLAY_OK SN 0 23 global
TRAINING_REPLAY_OK SN 0 23 directed
TRAINING_REPLAY_OK SN 0 37 local
TRAINING_REPLAY_OK SN 0 37 global
TRAINING_REPLAY_OK SN 0 37 directed
TRAINING_REPLAY_OK SN 1 11 local
TRAINING_REPLAY_OK SN 1 11 global
TRAINING_REPLAY_OK SN 1 11 directed
TRAINING_REPLAY_OK SN 1 23 local
TRAINING_REPLAY_OK SN 1 23 global
TRAINING_REPLAY_OK SN 1 23 directed
TRAINING_REPLAY_OK SN 1 37 local
TRAINING_REPLAY_OK SN 1 37 global
TRAINING_REPLAY_OK SN 1 37 directed
TRAINING_REPLAY_OK SN 2 11 local
TRAINING_REPLAY_OK SN 2 11 global
TRAINING_REPLAY_OK SN 2 11 directed
TRAINING_REPLAY_OK SN 2 23 local
TRAINING_REPLAY_OK SN 2 23 global
TRAINING_REPLAY_OK SN 2 23 directed
TRAINING_REPLAY_OK SN 2 37 local
TRAINING_REPLAY_OK SN 2 37 global
TRAINING_REPLAY_OK SN 2 37 directed
TRAINING_REPLAY_OK TT 0 11 local
TRAINING_REPLAY_OK TT 0 11 global
TRAINING_REPLAY_OK TT 0 11 directed
TRAINING_REPLAY_OK TT 0 23 local
TRAINING_REPLAY_OK TT 0 23 global
TRAINING_REPLAY_OK TT 0 23 directed
TRAINING_REPLAY_OK TT 0 37 local
TRAINING_REPLAY_OK TT 0 37 global
TRAINING_REPLAY_OK TT 0 37 directed
TRAINING_REPLAY_OK TT 1 11 local
TRAINING_REPLAY_OK TT 1 11 global
TRAINING_REPLAY_OK TT 1 11 directed
TRAINING_REPLAY_OK TT 1 23 local
TRAINING_REPLAY_OK TT 1 23 global
TRAINING_REPLAY_OK TT 1 23 directed
TRAINING_REPLAY_OK TT 1 37 local
TRAINING_REPLAY_OK TT 1 37 global
TRAINING_REPLAY_OK TT 1 37 directed
TRAINING_REPLAY_OK TT 2 11 local
TRAINING_REPLAY_OK TT 2 11 global
TRAINING_REPLAY_OK TT 2 11 directed
TRAINING_REPLAY_OK TT 2 23 local
TRAINING_REPLAY_OK TT 2 23 global
TRAINING_REPLAY_OK TT 2 23 directed
TRAINING_REPLAY_OK TT 2 37 local
TRAINING_REPLAY_OK TT 2 37 global
TRAINING_REPLAY_OK TT 2 37 directed
TRAINING_COMPLETE 54 EXACT_REPLAYS HASHES_UNCHANGED
```

Tests cover uniform exact ties, nonleading ties, expected MRR, stable CE and shift
invariance, rejection of nonfinite scores, window/fold/seed/incident aggregation,
duplicate evaluation rejection, empty group rejection, and history deltas.

## Static diagnostics

`lsp_diagnostics(training.py)` returned `No diagnostics found`. Initial file LSP
resolution of the newly created test import was unresolved; it was **not
suppressed**. The existing project-configured Pyright then checked both lane
files successfully:

```sh
cd /home/gnho1236/r2 &&
/home/gnho1236/.local/bin/pyright \
  --project research/failure_causes_20261014/pyrightconfig.json \
  research/failure_causes_20261014/training.py \
  research/failure_causes_20261014/test_training.py
```

Monitor `mon_54RQWPRMYK47AQ6C`, terminal `bash_4`, raw output:

```text
status: completed exit_code: 0
0 errors, 0 warnings, 0 informations
```

This is focused lane B analysis; parent owns final project-wide checking.

## Reconciliation, coverage and provenance

`training.json` status is `PASS`, with:

- 54/54 exact whole-validation-batch logits matches; no tolerance was loosened.
- 1053 per-run validation incident metric reconciliations against saved reports.
- 351 seed-averaged incident reconciliations against immutable `analysis.json`,
  plus all system/mode aggregate reconciliations.
- All 54 histories contain exactly epochs 1–5; exact saved TRAIN fault indices
  agree with reconstructed rows and fold window counts.
- All 117 independent incidents covered: SN 36/325 fault windows and TT 81/3451.
  Normal windows 69/618 are used only through permitted saved-reference feature
  reconstruction; only fault rows receive checkpoint inference.
- Each mode has six TRAIN evaluations and three validation evaluations per event;
  folds/seeds and equal unique-window counts are checked explicitly.
- Every root/fold has two disjoint TRAIN fault types and its remaining validation
  type, one incident per type: SN 36 and TT 81 root/fold checks.
- All 240 consumed-file hash bindings are checked on read and rechecked before
  output. The saved 11 source hashes, six fold statistics, four development
  bundle/manifest files, 216 run config/history/prediction/checkpoint files,
  runs/analysis snapshots, and the diagnostic helper snapshot are included.
- Producer/test source hashes were rechecked before publication.
- Output `training.json` is refused if already present; final publication uses
  exclusive `open("x")`. Existing results are never overwritten.

Frozen snapshot SHA256:

| File | SHA256 |
|---|---|
| `relationship_cv_20261014/results/runs.json` | `48129c9be79d251f5278a6ed79ccd72dca2373d10ef4e3f9038b0e9b055b6b13` |
| `relationship_cv_20261014/results/analysis.json` | `3814b07ee7d5a255c02b419f5407a76bba96b3da9c75e0511ad07513a636b11e` |
| `relationship_diagnosis_20261014/errors.py` | `130512dbb5850236c467384238c37d40065bb0a2f8fb185777a5b7ffcf7e2910` |
| `training.py` | `0da132a27fc1b11d2c1fbe707389e149b673f27897c7a8530d5a974b6e03131a` |
| `test_training.py` | `a46a751aa0c4604a60fc0a3088b60d776eb9128fb59710b36a37ef144291eece` |
| `training.json` | `e633bedd844fdb243e844f85eb8e27945393fa5bfaecdf882319986cb0ecc171` |

The helper hash is a start/end local snapshot, not a historical externally signed
pin. Saved CV sources/artifacts use the previous producer's hash contract.
Hashes bind bytes and local provenance, not authenticity of the original data.

Environment: Python 3.8.20, NumPy 1.21.5, torch 1.12.1+cpu, two compute threads,
one interop thread, deterministic algorithms, CPU.

## Parent handoff

- Quantitative interpretation and caveats: `TRAINING.md`.
- Machine-readable events, histories, support, replay identities, consumed input
  paths and hashes: `training.json`.
- Implementation and focused synthetic checks: `training.py`, `test_training.py`.
- Raw command/exit and static evidence: this file.

Training extension, representation changes, causal attribution, held-out/native
evaluation and new-model/epoch decisions remain untested and intentionally
unperformed. No output from the parent's input-signal lane was used here.
