# Dataset suitability verification — 2026-10-16

## Verdict

**All requested verification gates pass within their declared scope.** The
four canonical Markdown reports—`RCAB.md`, `RCAEVAL.md`, `EADRO.md`, and
`OPS.md`—are the producer handoffs. Their exact absolute paths were reread;
each contains experiment criteria and retained command/exit evidence. No
separate `finalhandoff*.md` sentinel files are required.

This is not a four-dataset performance comparison. **Only the 173-case RCAB
pilot contains new score-based experimental data.** RCAEval, Eadro, and ops-lite
results below are metadata-feasibility/coverage checks only.

| Gate | Verdict | Evidence / bound |
|---|---|---|
| Required unittest discovery | **PASS** | Exact command and live exit 0 below; 33 tests |
| Required project Pyright | **PASS** | Exact command and live exit 0 below; 0 diagnostics |
| RCAB R1: frozen sample, candidates, scores, ties, boundaries | **PASS** | Independently recomputed from saved counts/scores; no archive reopened |
| RCAB R2: semantic-group dry-run | **PASS, with support gaps** | 1,422 cases / 1,322 groups; zero group leakage; root/type gaps reported below |
| RCAEval A1: relevant-scope metadata feasibility | **PASS, metadata only** | 240 relevant; 180 locally audited, 60 RE3 not locally audited |
| Eadro E1: split-role metadata feasibility | **PASS, metadata only** | SN 36 and TT 81 fault incidents; no model evaluation |
| ops O1: census, sample bias, duplicate stress | **PASS, metadata/ledger scope** | 455 vs 30; 80 nonempty telemetry byte-hash matches |
| Producer CLI completion evidence | **PASS** | Each retained producer report has a quoted status/sentinel and monitor locator |
| Four canonical Markdown handoffs | **PASS** | All four named reports present and read at their exact paths |
| Protected-data/source boundary | **PASS** | Read-only source/path inspection; no protected observations or predictions opened |

## Required verification commands

Both commands below were run for this verification through monitors; neither is
a producer rerun.

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m unittest discover -v -s research/dataset_suitability_20261016 -p 'test_*.py'
```

Monitor `mon_W39RZ9954NJZB7NM` / session `bash_1`; retained completion:

```text
status: completed exit_code: 0
Ran 33 tests in 0.766s
OK
```

```sh
/home/gnho1236/.local/bin/pyright --project /home/gnho1236/r2/research/dataset_suitability_20261016
```

Monitor `mon_Q5KSSRYVTN4MR174` / session `bash_2`; retained completion:

```text
status: completed exit_code: 0
0 errors, 0 warnings, 0 informations
```

## Producer CLI evidence (original runs; not rerun)

These are quoted retained `bash_output` responses in the named report/handoff,
not success inferred from JSON status fields.

| Producer | Captured locator | Retained completion and sentinel |
|---|---|---|
| RCAB | `/home/gnho1236/r2/research/dataset_suitability_20261016/RCAB.md`; monitor `mon_2BXX0SZJ24S502BC`, producer session `st_01a145b8` | `status: completed exit_code: 0`; `RCAB_SELECTION_FROZEN cases=173 sha256=2c00110435d5365b6b0fadc6446a9d6a74b65affe21f4f05d8ad42970e2124d5`; `RCAB_RESULT_SHA256 98eccf62060e398c691242aca1f532c444646f93bc9c239d7a3c4ac0e7d64b00`; `RCAB_SUITABILITY_PASS`; `RCAB_CLI_EXIT=0` |
| RCAEval | `/home/gnho1236/r2/research/dataset_suitability_20261016/RCAEVAL.md`; monitor `mon_P0F5FF2HMKMBMM23`, session `bash_3` | `status: completed exit_code: 0`; `RCAEVAL_SUITABILITY_PASS cases=240 groups=78 local=180` |
| Eadro | `/home/gnho1236/r2/research/dataset_suitability_20261016/EADRO.md`; monitor `mon_9JCN7Q3NT8WXFPVR`, session `bash_15` | `status: completed exit_code: 0`; `EADRO_METADATA_SPLITS SN 36 4`; `EADRO_METADATA_SPLITS TT 81 9`; `EADRO_SUITABILITY_PASS` |
| ops-lite | `/home/gnho1236/r2/research/dataset_suitability_20261016/OPS.md`; monitor `mon_VP5WEZX6E1YS6JAM`, session `bash_11` | `status: completed exit_code: 0`; `OPS_SUITABILITY_PASS` |

The retained producer commands are the protocol commands: each module was
invoked with the existing `.venv-mlp/bin/python -B -m
research.dataset_suitability_20261016.<trial>` and all three thread variables
set to `2`. The RCAB report also preserves its exact shell command and CLI
completion response. No producer, model, or archive processing command was run
again here.

## RCAB: independent verification of the sole scored pilot

### Selection, candidate coverage, and scores

- Recomputed the HTTP selection from the allowed metadata rows, saved prior
  deep-sample list, per-type semantic-group hashes, and fixed salt. Exact match:
  **173 selected / 623 not ranked**, **164 / 759 groups selected**; all 12
  prior deep-sample HTTP cases are included and all group members stay together.
  The selected and unranked group sets are disjoint. `rcab_selection.json`
  records `saved_before_trace_processing=true`; the inspected producer source
  exclusive-creates it before entering selected-trace processing.
- The saved candidate list has **49 candidates per pilot case** (8,477
  case-candidate pairs), constructed from the full observation census service
  lists. Source and fixture check show it does not use target-only profiles;
  `loadgenerator` is retained.
- All **173/173** nominal anchors and **346/346** accepted-root entries are in
  the candidate inventories; there are zero cases with an accepted gold absent
  from candidates. Each case has two accepted roots, so the comparison is the
  single-anchor contract versus a two-gold accepted-root contract.
- Recomputed every saved criterion score from the saved per-service counts and
  independently recomputed both contracts' tie-aware Top1, Top3, expected
  reciprocal first-accepted rank (MRR), and paired differences. Results:
  **0 score/count mismatches, 0 case metric mismatches, 0 paired-difference
  mismatches, 0 fault-type-summary mismatches**. This check reads the saved
  JSON only; it does not validate raw archive rows a second time.
- Case-equal means, \(n=173\):

| Fixed criterion | Single gold: Top1 / Top3 / MRR | Two-gold set: Top1 / Top3 / MRR |
|---|---:|---:|
| Uniform | 0.020408 / 0.061224 / 0.091412 | 0.040816 / 0.119898 / 0.144967 |
| Abnormal HTTP-error fraction | 0.480987 / 0.814256 / 0.656739 | 0.609373 / 0.842064 / 0.742138 |
| HTTP-error fraction increase | 0.486767 / 0.814256 / 0.659630 | 0.615153 / 0.842064 / 0.745028 |
| Abnormal span-error fraction | 0.566474 / 0.807362 / 0.699179 | 0.572254 / 0.816558 / 0.708507 |

These are pilot-only descriptive results, not model performance or causal
identification. Changing the gold contract changes the score; the two columns
must not be treated as a method comparison.

### Missing support, boundaries, and dry-run split

- Every candidate remains in the score maps. Missing denominators are `null`,
  unsupported, and ranked after supported values; tests cover all-missing ties
  and supported negative values ahead of missing values. Across the 8,477
  candidate-case pairs, missing scores were **3,637** for abnormal HTTP-error
  fraction, **3,647** for HTTP-error increase, and **3,635** for abnormal
  span-error fraction. None were silently converted to a supported zero.
- The fixed fixtures passed half-open `[start,end)` and status-range tests. In
  saved pilot audits, normal periods had 22 excluded end-boundary rows and
  abnormal periods 7; 8 normal and 22 abnormal start-boundary rows were
  included. Other out-of-window and null-time rows were zero. Totals reconcile
  to 38,120,215 published span rows. Counts are published span rows, not
  independent requests.
- Root trace absence did not remove pilot cases: three cases have an accepted
  root missing abnormal trace rows, zero have such a normal-period absence,
  and all remain among the 173 scored cases. This differs from a gold absent
  from the candidate inventory (zero cases).
- Recomputed the all-case semantic split from the metadata: **1,422 cases,
  1,322 groups, zero groups split across folds**. Case-ID hashing instead
  splits 45 repeated groups (130 cases) across folds. This controls repeated
  configuration membership only; it does not certify independent collection:
  namespaces span folds and 502 of 760 positive time-overlap pairs cross folds.
  The split is a dry run, not an adopted final split.
- For the 1,167 nominal nonnetwork candidates, semantic-fold train/heldout case
  counts are 761/406, 774/393, and 799/368. Heldout anchor-root support gaps
  are 2/0/0 cases (two cases sharing one unsupported root service in fold 0);
  heldout type support gaps are 0/3/2. Those support gaps are retained, not
  repaired by moving cases. Of 1,168 nonnetwork metadata cases,
  one label/config conflict is excluded from the nominal-candidate count but
  retained in the 1,422-row metadata census. All 626 non-HTTP cases remain
  metadata-only; no HTTP pilot metric is generalized to them.

## RCAEval: A1 metadata-only feasibility

**PASS for the declared metadata question; raw coverage remains unverified.**
The retained index has 735 rows; relevant OB/TT RE2/RE3 scope is 240 (RE2 180,
RE3 60). Existing local readiness/audit covers 180 RE2; the 60 RE3 cases have
no local case audit in the allowed evidence. No RE3 telemetry was opened or
downloaded.

- Excluded scope is 375 RE1 cases, 90 RE2-SS, and 30 RE3-SS; hence no SockShop
  or RE1 metric-only data were included.
- The grouped `(system, root, fault)` hash dry run contains 78 groups, keeps
  every group intact, and accounts for all 240 heldout cases. By contrast, a
  case-ID comparison places cases from 67 of 78 repeated `(system, root,
  fault)` label conditions in multiple folds. This establishes condition-label
  sharing across folds only. It does **not** establish same-incident identity,
  observation overlap, or label leakage. Event-disjoint and stricter
  condition-disjoint evaluation answer different questions: if the cases are
  independent incidents, a case split can legitimately measure performance
  on a new repetition of a known condition. These metadata do not establish
  that incident independence. Accordingly, read RCAEVAL.md's “leaks condition
  identity by construction” as a warning about repeated condition labels
  crossing folds, not as proof of event/observation leakage.
- “Group-disjoint” means only that identical indexed `(system, root, fault)`
  labels stay together. It does not imply independent events, cold-root
  evaluation, or telemetry quality; reported supports are union-over-systems,
  not per-system guarantees.
- RE3 is imbalanced: OB roots are adservice 9, cartservice 3, currencyservice
  3, emailservice 15; TT roots split 15/15. TT repetition counts are 3×4,
  4×3, and 6×1, not a uniform grid.
- RE2→RE3 root overlap is two OB roots and both TT roots; none of the 10 OB or
  8 TT RE3 root/fault label pairs exactly overlaps RE2. The `f*` taxonomy is
  not mapped to RE2 fault labels. Root-label overlap is not telemetry-service
  inventory or RCA performance.
- The existing per-system 54/18/18 split boundary was not edited. Its mapping
  to all 240 rows remains unresolved; the hypothetical folds do not replace it.

## Eadro: E1 split-role metadata feasibility

**PASS for metadata support inspection only.** SN has 36 fault incidents over
4 fault recordings; TT has 81 over 9. Each has three fault types and every
root×type condition occurs once. Additional normal-only archives do not add
labelled fault incidents.

- Event folds are **seen-root** splits: all roots appear in TRAIN and heldout
  (SN 12/12, TT 27/27), but all recordings are shared (4/4 and 9/9). Incident
  IDs do not overlap, but this is not recording-disjoint evidence and cannot
  establish independent-collection performance.
- Recording holdout is a valid **hypothetical joint recording/environment +
  cold-root** evaluation condition: three root targets per held recording are
  absent from TRAIN, the candidate inventory is unchanged, and no recording
  overlaps each holdout. It is not categorically invalid. The metadata check
  establishes that split composition and target-support loss, but measures no
  generalization under that joint shift and does not establish that recording
  is an independently sampled environment.
- Fault-type holdout retains root coverage. Normal windows follow their
  assigned episode's fault type, so a held-out type's normal windows do not
  appear in TRAIN. No model was fit and no split was adopted as final.

## ops-lite: O1 metadata bias and duplicate stress

**PASS for the bounded census and saved-ledger comparisons; independence and
unsampled telemetry quality are not certified.**

- Metadata census: **455** cases (TrainTicket 275, Hotel Reservation 148,
  OTel Demo 32) versus the selected **30** (10 per system); **425** cases
  remain without telemetry-quality evidence. The sample is deliberately
  balanced, not representative of the full system mix.
- Required-fault item counts are 437 single / 18 double in the full census
  versus 30 single in the sample. Distinct required-root counts are 438 single
  / 17 double versus 30 single. Full role-item counts are required 473,
  optional 81, not-effective 77; sample counts are 30, 12, and 3. Eligibility
  and sample membership are not telemetry evidence.
- Exact comparisons find 197 case-name, 197 task-ID, and 197 time matches;
  204 numeric injection-ID matches include 8 pairs with different case names,
  so ID alone is insufficient. The **80 exact nonempty telemetry-byte SHA-256
  match groups** map to **8 distinct ops case IDs and 8 distinct RCAB case
  directories** in `ops_trial.json`. The comparison covers 291 ops and 15,642
  RCAB unique nonempty hashes. Empty-file hashes are excluded by code and
  tested. Thus some
  shared bytes are evidenced; lack of a match in another comparison does not
  prove independence. Configuration encodings are not comparable, so zero
  exact serialized matches is **unknown**, not evidence of disjoint
  configurations. Reformat/time-shift duplicates remain unresolved.
- Publisher/author linkage, license suitability, and telemetry quality of the
  unsampled 425 remain unverified.

## Source boundary and hashes

The four producer sources/tests and exact input hashes embedded in their result
manifests were inspected or rehashed; no protected observation/prediction path
was opened. The source search hits for `final-test` were descriptive split
metadata, and `unassigned` was only a synthetic test case, not a file path.
The RCAB archive was not reopened. Current hashes below identify the artifacts
read during this verification; only hashes with a producer-recorded counterpart
are a before/after integrity comparison.

| Hash binding | Recheck |
|---|---:|
| RCAB `source_sha256_before_and_after` inputs/code/protocol/config | 12/12 matched |
| RCAB selection's source hash bindings | 12/12 matched |
| RCAEval input + source/test hashes | 8/8 matched |
| Eadro input + producer-source hashes | 6/6 matched |
| ops declared input + source/test hashes | 14/14 matched |
| ops per-case metadata files | 1,820/1,820 matched |

Current result/report hashes (SHA-256):

| Artifact | SHA-256 |
|---|---|
| `PROTOCOL.md` | `569703d983be487c7c752a25610b63db2b5fbd7775c541881e13416284057352` |
| `rcab_selection.json` | `2c00110435d5365b6b0fadc6446a9d6a74b65affe21f4f05d8ad42970e2124d5` |
| `rcab_trial.json` | `98eccf62060e398c691242aca1f532c444646f93bc9c239d7a3c4ac0e7d64b00` |
| `RCAEVAL.md` / `rcaeval_trial.json` | `d31b7aa1f6e43aefb521174efddcfd8339ba3e924338ffe78b47774a300a18bf` / `025f82f0094127118faf2492417dcf35af7f2a33287ad4909f4bb373fc08a197` |
| `EADRO.md` / `eadro_trial.json` | `4f344aac2863a14c5117a376c10ca0308f50ca37a7ec5680d7c288f2b21e68d3` / `6dec41af0248aa9da11fd3459247c18dc3cf421f7f9e222982eee6ae33d8d411` |
| `OPS.md` / `ops_trial.json` | `edcc5fecbd50aada0e586c0860523b724d22145132fbdf8e65507c43cd718407` / `69b18b041fc71f130909bf80f377651385f913da51744ba82b73a8dd2354389c` |
| `RCAB.md` | `c6b73ef6cb0a753b3800acd2efb6a41f745e879703d2040d88083840bf9b149e` |

Producer/test source hashes and exhaustive input-path hashes remain in the
four result JSON manifests and `rcab_selection.json`; current rehashes matched
those bindings. Original artifacts were not edited by this verification. The
four canonical report/handoff paths were read directly and are identified by
the current hashes above.

## Limits and report-node numbers

Bounded numbers safe to carry forward:

- **RCAB:** 173/796 HTTP pilot scored; 623 HTTP and 626 other cases not ranked;
  four fixed heuristics, two separate gold contracts. No causal claim, model
  result, or final split.
- **RCAEval:** 240 relevant metadata rows, 180 locally audited and 60 RE3
  unaudited. No raw RE3 coverage or ranking claim.
- **Eadro:** 36 SN / 81 TT fault incidents for split-support analysis only.
  No new model or independent-test performance.
- **ops-lite:** 455 metadata cases, 30 telemetry-audited sample cases, 80
  nonempty exact byte-hash match groups. No quality claim for the other 425 or
  corpus-independence certification.

No arbitrary primary dataset was selected. The limitations above remain
unresolved by design; no supplementary experiment, download, training, or
producer rerun was performed.
