# Independent bounded-CV evidence verification

**Result: PASS for the bounded execution contract and its stated exploratory decision.**
This verification inspected the captured outputs and permitted source/input files only.
No fit, replay, aggregation command, or generated output was rerun or overwritten.
The independent aggregate below was calculated directly from `runs.json` per-incident
records; it did not call `analysis.summarize`.

## Criteria

| Criterion | Result | Evidence |
|---|---|---|
| Required unit tests | **PASS** | Exact requested command completed with exit 0; 15 tests, `OK` (output below). |
| Required Pyright | **PASS** | Exact requested command completed with exit 0: `0 errors, 0 warnings, 0 informations`. |
| Fit command evidence | **PASS** | `FIT_EVIDENCE.md` records the exact fit command, monitor `mon_HSBEZJ4Y0K0P89CX`, exit code `0`, and `CV_RUN_COMPLETE 54 39.554640357993776 898688`. This is captured producer evidence; fits were not repeated here. |
| Replay command evidence | **PASS** | `REPLAY_EVIDENCE.md` records the exact verify command, monitor `mon_7VNCPXYAMXJGS4NM`, exit code `0`, and `CV_VERIFY_COMPLETE 54 9.054024618992116 899052`; all 54 replay checks are reported passed. |
| Aggregation command evidence | **PASS** | `ANALYSIS_EVIDENCE.md` records the aggregation command, exit code `0`, and `CV_ANALYSIS_COMPLETE`; it also records the exact runs, source, protocol, test, and analysis-output hashes. No aggregation was rerun. |
| Exact fit grid | **PASS** | `runs.json`: status `PASS`, run_count `54`; 54/54 identities are unique and exactly the expected 2 systems × 3 folds × 3 seeds × 3 modes. |
| Fixed epoch budget | **PASS** | All 54 reports say `epochs_run=5`; each corresponding saved history has precisely epochs `[1,2,3,4,5]`. |
| Protected-data flags | **PASS** | Both `runs.json` and `verification.json` report `test_evaluated=false`, `rcaeval_access=false`, `rcabench_access=false`. |
| Source/input integrity | **PASS** | Recomputed SHA-256 values for all 11 saved source entries and all 4 input entries match the hashes in `runs.json`. Replay source/input maps exactly match the run maps. |
| Generated artifact integrity | **PASS** | Recomputed SHA-256 values for all 276 paths in `runs.json` match. |
| Replay/provenance metadata | **PASS** | `verification.json` has status `PASS`, run_count `54`; all 54 producer replay checks are reported; its source and input hashes match `runs.json`. |
| Incident coverage / uniqueness | **PASS** | Every seed/mode combination covers every incident exactly once across folds: SN 36/36, TT 81/81. Per-fold coverage is 12/12/12 and 27/27/27 respectively. |
| Recording counts | **PASS** | Fault metadata has 4 unique SN recordings and 9 unique TT recordings. These incident counts are not multiplied by seeds. |
| Seed-averaged incident aggregation | **PASS** | Independently averaged each incident's three seed scores, then equally averaged incidents; per-mode means and directed−global means/fold/seed deltas match `analysis.json` to floating-point tolerance (<1e-12). |
| Frozen decision | **PASS** | Independently recomputed directed−global Top1 is positive in each system, at least 2/3 folds, and at least 2/3 seeds: SN 3/3 folds and 3/3 seeds; TT 2/3 folds and 2/3 seeds. This yields `expansion_worth_considering`, as saved. |
| Same-recording fold overlap disclosed | **PASS (limitation confirmed)** | From incident-to-recording metadata and fold membership, train and validation share 4/4 SN recordings and 9/9 TT recordings in each fold. This is not recording-independent validation. |
| Bounded interpretation disclosed | **PASS (limitation confirmed)** | The protocol uses previously used development incidents; five fixed epochs are an update budget, not an equal wall-clock/FLOPs budget. No literature-competitiveness or final-test claim is supported or made. |

No criterion above failed. “PASS” for command evidence means the captured producer
evidence records the command, exit code, and completion output; this verifier did not
re-execute fits or replay because the task prohibited repeating them.

## Commands and observed output

Required unit-test command:

```text
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest discover -v -s research/relationship_cv_20261014 -p 'test_*.py'
```

Observed output (exit code 0):

```text
test_cli_hashes_exclusive_creation_and_no_verification_dependency (test_analysis.AnalysisTest) ... ok
test_cli_validation_failure_leaves_no_output (test_analysis.AnalysisTest) ... ok
test_decision_requires_both_systems_two_folds_and_two_seeds (test_analysis.AnalysisTest) ... ok
test_deterministic_bootstrap_matches_expanded_incident_oracle (test_analysis.AnalysisTest) ... ok
test_event_coverage_and_pairing_rejected (test_analysis.AnalysisTest) ... ok
test_incident_equal_not_fold_equal_and_win_tie_loss (test_analysis.AnalysisTest) ... ok
test_invalid_metrics_times_counts_and_recordings_rejected (test_analysis.AnalysisTest) ... ok
test_missing_duplicate_and_invalid_run_rejected (test_analysis.AnalysisTest) ... ok
test_seed_average_no_count_inflation_fit_time_and_json_purity (test_analysis.AnalysisTest) ... ok
test_unequal_recording_sizes_and_multiplicity (test_analysis.AnalysisTest) ... ok
test_all_folds_rebuild_from_raw_and_ignore_validation (test_cv.CVTest) ... ok
test_fixed_fit_determinism_and_exact_epoch_budget (test_cv.CVTest) ... ok
test_missing_normal_support_and_invalid_fold_rejected (test_cv.CVTest) ... ok
test_no_overwrite_and_artifact_mismatch (test_cv.CVTest) ... ok
test_unauthorized_system_rejected_before_io (test_cv.CVTest) ... ok
Ran 15 tests in 1.208s
OK
watcher completed (exit code 0)
```

Required Pyright command and observed output (exit code 0):

```text
/home/gnho1236/.local/bin/pyright --project /home/gnho1236/r2/research/relationship_cv_20261014
0 errors, 0 warnings, 0 informations
watcher completed (exit code 0)
```

The fit, replay, and aggregation command lines and their completion/exit evidence are
captured in `FIT_EVIDENCE.md`, `REPLAY_EVIDENCE.md`, and `ANALYSIS_EVIDENCE.md`.

## Independent numeric recomputation

For each system, incident, and mode, the calculation averaged the per-incident Top1
from seeds 11, 23, and 37; then averaged those incident means equally. Fold deltas
use incidents in the fold; seed deltas average per-incident paired differences for
that seed. The saved summary agrees to floating-point rounding.

| System | Incidents | Recordings | Directed Top1 | Global Top1 | Directed−global | Positive folds | Positive seeds | Fixed criterion |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SN | 36 | 4 | 0.640356 | 0.549997 | +0.090359 | 3/3 | 3/3 | PASS |
| TT | 81 | 9 | 0.542449 | 0.537817 | +0.004632 | 2/3 | 2/3 | PASS |

Independent fold deltas (fold 0/1/2): SN `+0.065674`, `+0.029982`, `+0.175421`;
TT `−0.009170`, `+0.019462`, `+0.003605`.
Independent seed deltas (11/23/37): SN `+0.087911`, `+0.086953`, `+0.096213`;
TT `+0.011092`, `+0.008185`, `−0.005381`.

## Hash evidence

The following current SHA-256 values were recalculated and compared to the saved
manifest values; all matched. Full artifact-path hashes (276 entries) also all
matched their `runs.json` entries.

| Kind | Current path | SHA-256 |
|---|---|---|
| Source | `research/relationship_smoke_20261013/data.py` | `cb6f035cefaaf8c3c67bde91c733d0d0b234a4857cd6cd88ee80a368bc34ec85` |
| Source | `research/relationship_smoke_20261013/PROTOCOL.md` | `1b6720acd702579b307b2b927263b36f2bb0221f0fa772a9dc2ee5ca130bc288` |
| Source | `research/method_mlp_20261013/features.py` | `80c591f13e257d1435b6da32ff4fe8ad2096adb10855a2004972dc44e409ccfd` |
| Source | `research/native_reproduction_20261013/native_data_profile.py` | `86d323810f70e732d945e25358d8488df619f0d9a445697f1b77b82fbfbaaa00` |
| Source | `research/relationship_smoke_20261013/smoke.py` | `deaeb67a948289ae1bfa3bb10174572a55ce3ccb04e023038e91cef98e0234a6` |
| Source | `research/relationship_smoke_20261013/relation_model.py` | `ef6622426c9e9fe4ff63296f2875b53a479d0907fbcf5d632fe60f44958bc359` |
| Source | `research/method_mlp_20261013/train.py` | `7f2c4619f79ce3a0d5d142f609b7aa94963383019eb65ce9e605a0f4ae657e59` |
| Source | `research/method_mlp_20261013/ranker.py` | `78158d20e3347f24d7ef50af56ba0cc31dcf0ffacb706a945dbd11598aa2d829` |
| Source | `research/relationship_cv_20261014/cv.py` | `7829160d6f493e34dd9224624ce578cc614dea56cf3109f27b5c07d51e41a8dd` |
| Source | `research/relationship_cv_20261014/PROTOCOL.md` | `1d24e290525bade19beb96d7ad610889c417ad58d3f03635ff4d51b9c57a1e88` |
| Source | `research/relationship_split_audit_20261013/audit.py` | `71eddd068f9472e6928ca3d0b0c0b2c990ec42372326af55bfc4ff9934c6be4a` |
| Input | `research/relationship_smoke_20261013/artifacts/SN.json` | `1956804ecec5f191b02ccf52aa189e9529acb6cd256ddde2a24c02caf3e2ae93` |
| Input | `research/relationship_smoke_20261013/artifacts/SN.npz` | `1519a69e10aaa402fb88bf0be027502610bfaaa0dfd4c7b37ff4f44f3400efb` |
| Input | `research/relationship_smoke_20261013/artifacts/TT.json` | `3749e36e00dce4a2110b7582f11af9e92b4177fee2ec3e487684ef0fd9a45e1b` |
| Input | `research/relationship_smoke_20261013/artifacts/TT.npz` | `4e568299514f10f247c0b2496e3392a6457825844e2145ad3df36b13c9cd9cff` |

Saved output/provenance digests:

| File | SHA-256 |
|---|---|
| `results/runs.json` | `48129c9be79d251f5278a6ed79ccd72dca2373d10ef4e3f9038b0e9b055b6b13` |
| `results/verification.json` | `89992784e7b14affadadd039cfb41372bcf254936dd39aedbb8f4653f9780930` |
| `results/analysis.json` | `3814b07ee7d5a255c02b419f5407a76bba96b3da9c75e0511ad07513a636b11e` |
| `analysis.py` (also embedded as analysis source hash) | `6ad65e71a2d41252e5f8c8dc290d4a9893633bcd98bb57b76a6176a550fdd049` |

## Unresolved limitations

- Folds are not recording-disjoint: incidents from the same recording occur in
  training and validation (4 SN and 9 TT recordings overlap in every fold).
- These are previously used development incidents, not untouched final-test data.
- Five epochs are a fixed update count, not an equal wall-clock or FLOPs budget,
  nor evidence of convergence.
- The recording-cluster bootstrap uses only 4 SN / 9 TT recordings and overlapping
  training sets; its intervals are exploratory and do not establish significance
  or independent-population generalization.
- No literature comparison, novelty, final-test, or end-to-end extraction-cost claim
  follows from this bounded run.
