# Verification — relationship diagnosis outputs (2026-10-14)

Scope: checked `PROTOCOL.md`, the three producer outputs (`ERRORS.md` /
`errors.json`, `RECORDINGS.md` / `recordings.json`, `COMPARATORS.md`), their
sources and tests, and only the pinned CV results and permitted SN/TT development
bundle metadata/observation inputs. No producer was rerun; no training,
checkpoint inference, install, download, or generated-result write occurred.
Only this verification report is new.

## Decision

**Overall: FAIL — verification gate not fully satisfied.** Numeric, hash,
recording, and literature-content checks below pass. The mandated unittest
discovery command exits 1, and the scoped files do not contain the original
producer process transcripts needed to independently establish their CLI exit
codes/sentinels. These failures are reported, not repaired or inferred away.

| Criterion | Result | Evidence |
|---|---|---|
| Scope and read-only handling | PASS | Producers were not rerun; no result/source/checkpoint writes. `errors.py` itself records only the permitted NPZ members and rejects mismatches. |
| Consumed-input integrity | PASS | Rehashed all **66** entries in `errors.json/input_hashes` (2 CV JSON, 2 bundle JSON, 2 bundle NPZ, 54 predictions NPZ, 6 fold statistics NPZ): **0 mismatches**. The two recorded source hashes also match. |
| Required unittest discovery | **FAIL** | Exact requested command exits **1**: all 16 `test_errors` tests pass, but discovery cannot import `test_recordings` as a top-level module; its relative `.recordings` import lacks package context. |
| Recording test isolation check | PASS (supplemental only) | Package-qualified `test_recordings` invocation exits **0**, 5 tests pass. This does not change the required discovery failure. |
| Required Pyright | PASS | Exact requested command exits **0**, `0 errors, 0 warnings, 0 informations`. |
| Saved prediction and CV metric reconciliation | PASS | One saved prediction sample independently recomputed without inference; all 18 aggregate metric values (2 systems × 3 modes × Top1/Top3/MRR) match `analysis.json` within stated tolerance. |
| Recording aggregates and holdout metadata | PASS | Independently grouped all **117** incidents by recording; all 13 recording score rows match, with 9 incidents each. Each holdout removes 3 TRAIN root targets while removing 0 candidates. |
| Context denominators / mixed-event labels | PASS | All 9 contexts per system have explicit present/absent counts (empty strata are `null`), overlap counts and event-ID labels agree, and window subsets are marked disjoint. |
| Producer execution exit/sentinel proof | **FAIL — evidence unavailable here** | Producer reports state exit 0 and sentinels, but no raw CLI transcript/process record was present in the scoped diagnostic/CV/smoke files. Reports alone are producer attestations, not independent exit evidence. Analysis was not rerun because its CLI creates the output exclusively. |
| Literature comparison claims | PASS | Three primary methods are cited; the pinned Eadro implementation is called a modified fork, not the author original. No adapted model is called official, no historical score is presented as current 54-fit performance, and the input, onset, and detector-gating differences are explicit. |

## Exact verification commands and exits

Required tests, run through a completion monitor:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest discover -v -s research/relationship_diagnosis_20261014 -p 'test_*.py'
```

**Exit 1.** Output: 16 tests passed, then
`ImportError: Failed to import test module: test_recordings`; the package-
relative import in `test_recordings.py` is not resolvable in this discovery
mode. No tests were skipped or modified.

Supplemental check confirming the recording test module itself runs:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest -v research.relationship_diagnosis_20261014.test_recordings
```

**Exit 0; 5 tests passed.** This is not a substitute for the requested
discovery command.

Required project type check:

```sh
/home/gnho1236/.local/bin/pyright --project /home/gnho1236/r2/research/relationship_diagnosis_20261014
```

**Exit 0; 0 errors, 0 warnings, 0 informations.**

Producer reports record these exact claimed CLI commands and results; they were
not rerun because the output files already exist:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_diagnosis_20261014.errors
# ERRORS.md claims exit 0 and DIAG_ERRORS_COMPLETE

cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_diagnosis_20261014.recordings
# RECORDINGS.md claims exit 0 and DIAG_RECORDINGS_COMPLETE
```

These are **reported claims, not independently captured process evidence in
the scoped files**. Remediation is bounded to supplying the original monitor
transcripts/exit records; do not rerun an exclusive-output producer merely to
recreate evidence.

## Independent numeric checks

- `errors.json` contains **117 events**: SN **36**, TT **81**; **325 / 3,451**
  unique fault windows. It records **54** CV reports, not 54 extra incidents,
  plus **1,053** run-event-mode metric checks and **351** prior-summary
  event-mode checks. Prior incident W/T/L reproduces exactly: SN **17/13/6**,
  TT **28/34/19**.
- Incident-equal Top1, Global → Directed: SN **0.549997 → 0.640356**
  (Δ **+0.090359**); TT **0.537817 → 0.542449** (Δ **+0.004632**).
  These values match the saved `analysis.json`; no claim of new evaluation is
  made.
- Recomputed from one saved prediction file, without checkpoint/model
  inference: `SN.2022-04-17T181245D2022-04-17T183616:fault00`, fold 2, seed 11,
  Directed, 9 rows: Top1/Top3/MRR **1/1/1**, exactly the stored event values.
- Wrong-mass conservation independently holds for the aggregate modes checked:
  SN Global **0.450003**, SN Directed **0.359644**, TT Global **0.462183**,
  TT Directed **0.457551**; each equals `1 − Top1` within floating-point
  tolerance. The report’s directional/weak/no-edge buckets sum to each total;
  synthetic tests exercise reversed direction and exclusive relation cases.
- Recording reconciliation: **13 recordings × 9 incidents = 117**. All 3
  roots in each recording occur once with each of 3 fault types. Every
  leave-one-recording-out row removes exactly **3** roots from TRAIN targets,
  leaves the candidate inventory intact, and reports positive normal/type
  TRAIN support (minimum normal windows: SN **50**, TT **543**; minimum
  per-type support: SN **9**, TT **24**). Root-supervision shift is correctly
  disclosed, not represented as an environment-only split.
- All context strata preserve their own incident/window denominators and show
  mixed-event overlap rather than summing subgroup incident counts. Examples:
  SN any-graph present **36/308**, absent **4/17**, overlap **4**; SN visible
  incoming **31/191**, **25/134**, overlap **20**; TT any-graph **78/640**,
  **81/2,811**, overlap **78**; TT visible incoming **24/123**, **81/3,328**,
  overlap **24**. Empty absence groups are null, not zero estimates. The
  separate `root_any_*` union strata are explicitly disclosed as not produced;
  the supplied protocol does not require those later-requested supplemental
  strata.

## Literature and bounded limitations

`COMPARATORS.md` cites the DiagMLP paper, BARO paper and pinned official
`robust_scorer` source, and Eadro paper plus a commit-pinned **modified repair
fork**. It explicitly states that raw logs/Hawkes outputs and Eadro’s native
static graph are missing from the permitted inputs; it distinguishes adapted
shared-input comparison from full-pipeline comparison. It also distinguishes
BARO onset-given scoring from end-to-end detection and Eadro conditional
localization from detector-gated results. No old performance is mixed into the
current saved 54-run result table. DiagMLP private integration details, current
literature-model performance, implementation cost, and feasibility of native
input preparation remain unverified, as the report states.

No relationship is described as causal, and previous performance inflation is
not claimed as proven. The only test failure needing follow-up is discovery
import context; the separate recording tests pass. Producer-execution evidence
requires the original captured transcript, not a new output-generating run.

## Dated recheck and correction — 2026-10-14

This addendum preserves the preceding initial **FAIL** as history. The parent
fixed `test_recordings.py` to use its absolute package import without weakening
tests, and supplied the missing original recording execution locator. This
recheck supersedes the initial test-import and execution-evidence failures.
**Current decision: PASS — every named gate has evidence; no producer rerun was
needed.** No file other than this `VERIFY.md` was changed in this recheck.

### Rechecked gates and exact command results

| Gate | Result | Evidence |
|---|---|---|
| Required test discovery | **PASS, exit 0** | Exact command below; monitor `mon_SMD6ACSY38SJ7HTP` / `bash_2`: **26 tests**, `Ran 26 tests in 0.028s`, `OK`. The 16 original error tests, 5 recording tests and 5 union tests all pass. |
| Required Pyright | **PASS, exit 0** | Exact command below; monitor `mon_F63JCZVEN6YRNJYD` / `bash_1`; `0 errors, 0 warnings, 0 informations`. |
| Original errors CLI | **PASS, original exit 0** | `ERROR_EXECUTION_EVIDENCE.md` traces the original run to archived session `753b5eed-daf1-4424-bdde-7f98fdffbc80`, event `f2e3273a` (monitor completion: `DIAG_ERRORS_COMPLETE`, exit 0) and event `f4b3b1b4` (retained `bash_output`: `status: completed exit_code: 0` plus sentinel). |
| Original recordings CLI | **PASS, original exit 0** | Exact cited archived session in `RECORDING_EXECUTION_EVIDENCE.md`; event `53282de1`, monitor `bash_25`, says `DIAG_RECORDINGS_COMPLETE` and `watcher completed (exit code 0)`. |
| Root-context union supplement CLI | **PASS, original exit 0** | `ROOT_CONTEXT.md` records monitor `mon_RZSA9ZW2AYW3TGCF` / `bash_8`; its cited archived session event `7ba9b227` records `DIAG_ROOT_CONTEXT_COMPLETE` and exit 0. |
| Hashes and immutable originals | **PASS** | Independently rehashed all 66 `errors.json/input_hashes` entries and all 65 `errors_root_context.json/input_hashes` entries: zero mismatches. `errors.py`, `test_errors.py`, `errors.json`, and `ERRORS.md` still match the original hashes listed above and in `ROOT_CONTEXT.md`. The current `runs.json` and `analysis.json` match the frozen SHA-256 pins `48129c…b6b13` and `3814b0…36b11e`. |
| Current saved-CV reconciliation | **PASS** | `runs.json` says 54 runs and has 54 reports. Exactly 117 unique incidents remain (36 SN, 81 TT), not 54 additional incidents. Reconciliation records 1,053 run/event/mode checks and 351 previous-summary event/mode checks; all Top1 W/T/L counts match. |

Required test command, run exactly as requested:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest discover -v -s research/relationship_diagnosis_20261014 -p 'test_*.py'
```

**Exit 0; 26 tests passed.** This corrects, but does not erase, the initial
discovery failure recorded earlier in this file.

Required type-check command:

```sh
/home/gnho1236/.local/bin/pyright --project /home/gnho1236/r2/research/relationship_diagnosis_20261014
```

**Exit 0; 0 errors, 0 warnings, 0 informations.**

### Independent numeric and scope recheck

- Recomputed a saved prediction sample from
  `SN/fold_2/seed_11/directed/predictions.npz`, with no checkpoint inference:
  event `SN.2022-04-17T181245D2022-04-17T183616:fault00`, 9 windows,
  Top1/Top3/MRR = **1/1/1**, matching the saved event.
- Compared all 18 saved aggregate cells (2 systems × 3 modes × 3 metrics)
  against current `analysis.json`; maximum absolute difference was
  **1.12e-16**. Incident-equal Directed−Global Top1 and W/T/L remain SN
  **0.549997→0.640356**, **17/13/6**; TT **0.537817→0.542449**,
  **28/34/19**.
- Rechecked aggregate wrong-mass conservation for Local, Global and Directed:
  each relation-bucket sum equals its stored total, and total wrong mass equals
  `1 − Top1` within **1.12e-16**. Top-service ties retain uniform `1/k` credit;
  no first-index argmax is used. Directional relation buckets are exclusive.
- Recomputed per-recording event-equal means from the 117 saved incident rows.
  All **13** recording rows (4 SN, 9 TT; 9 incidents each) match
  `recordings.json`; maximum absolute metric difference **1.12e-16**. Each
  leave-one-recording-out holdout removes exactly **3** roots from TRAIN
  targets, while all remain in the saved candidate inventory. Every holdout
  has positive normal and fault-type TRAIN support (minima: SN **50** normal
  windows / **9** per type; TT **543** / **24**). This is correctly disclosed
  as cold-root/root-supervision shift, not environment-only generalization.
- All nine original context strata reconcile from the per-event observation
  counts: present/absent incident counts, unique-window denominators, overlap
  counts, and empty strata. Mixed events legitimately appear on both sides;
  event denominators are not additive. The additional root-any union strata
  also reconcile independently:

  | System / union | Present incidents/windows | Absent incidents/windows | Overlap incidents |
  |---|---:|---:|---:|
  | SN raw and visible | 34 / 211 | 24 / 114 | 22 |
  | TT raw and visible | 33 / 173 | 81 / 3,278 | 33 |

  Event inclusion-exclusion gives 36 SN and 81 TT, and window counts sum to
  their unique fault windows (325 and 3,451). Windows with both directions
  count once. The observed equality of raw and visible selections is a result
  for these bundles, not an implementation assumption. Visibility uses each
  event’s current-fold `reference_mask`; no fold-0 mask is reused, and root
  visibility is not an extra gate on visible neighbors.
- `COMPARATORS.md` retains the required primary-method citations for DiagMLP,
  BARO, and Eadro; identifies the Eadro artifact as a pinned **modified fork**,
  and distinguishes adapted/shared-input models from official/native methods.
  It does not mix historical performance with this 54-run analysis, nor
  conflate BARO’s onset-given scoring with end-to-end detection or Eadro’s
  conditional localization with detector-gated evaluation.

### Remaining bounded limitations

The PASS is for the requested saved-data diagnosis and verification, not new
evaluation. Raw logs/Hawkes output and Eadro’s native static graph are absent
from permitted inputs; DiagMLP private integration details, adapted comparator
performance, and native-input feasibility remain unverified as the comparison
report states. Recording/context and directional findings are descriptive
associations, not causal claims. Previous performance inflation is **not**
proven. No training, checkpoint inference, install, download, or producer
rerun was performed.
