# Frozen evaluation-analysis-report check

**Final verdict: PASS.** The evaluation, analysis, and report satisfy the
checked frozen requirements. Required upstream success evidence is present;
historical failed attempts remain recorded and are not substituted for the
successful runs. No unresolved deliverable defect was found.

Checked 2026-10-17. Scope was read-only verification plus this file. No fitting,
tuning, inference replay, install, download, raw-data scan, protected-row
decoding, source edit, old-study edit, or commit was performed. `analysis.py`
was run against the authorized 394-row `inputs.npz` and saved predictions; it
does not load the mixed raw cache or run model inference.

## Requirement-by-requirement evidence

| Requirement | Result and evidence |
|---|---|
| Frozen requirements and scope | **PASS.** Read `PLAN.md` §2–§9 and `ANALYSIS_PROTOCOL.md`. The specified 36 known-root/type-combination events, 12 candidates, three event-disjoint rotations, 2 methods × 3 seeds, event-level scoring, tied-rank credit, recording bootstrap, and interpretation limits are reflected in `ANALYSIS.json`, `ANALYSIS.md`, and `REPORT.md`. |
| PLAN §9 deliverables | **PASS.** Frozen plan/config/input provenance: `PLAN.md`, `input_manifest.json`, `PRETRAIN_CHECKS.json`, per-run configs/scalers. Preparation and execution gates: `INPUT_VERIFY.md`, `PRETRAIN_VERIFY.md`, `RUNNER_GATE.md`, `SCORE_GATE.md`. Execution and selection: rotation receipts, histories/checkpoints, `TRAIN_VERIFY.md`. Evaluation: `evaluation.json` and 54 prediction files. Independent verification: `VERIFY.json`/`.md`. Failure analysis and next-step decision: `ANALYSIS.json`/`.md` and `REPORT.md`. |
| Input/protection boundary | **PASS.** `PRETRAIN_VERIFY.md` and the checked analysis provenance bind the selected `inputs.npz` SHA-256 `ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`; manifest records 394 permitted rows and zero protected rows decoded. `ANALYSIS.json` records 325 fault windows, 69 normal windows, `protected_rows_decoded: 0`, and `native_raw_scans: 0`. No protected rows or native raw inputs were opened in this check. |
| Required artifacts and successful fit evidence | **PASS.** `TRAIN_VERIFY.md` latest authoritative section records all three rotations, six fits per rotation, actual producer exit 0 and completion sentinels, 18 histories, frozen source/input hashes, 200 epochs, and the 200/400 extension decision. It independently recomputes each selected epoch from the full history using minimum validation event NLL with earliest-epoch tie-breaking, verifies checkpoint/config/history/scaler hashes and common initialization, and confirms update counts 1,000/1,000/800 per rotation and all `budget_bound=false`. `ANALYSIS_PASS 36` below independently rechecks the relevant receipts and artifacts. |
| Evaluation launch and outputs | **PASS.** `EVAL_EXECUTION.md` correction identifies original session `bash_1`, actual exit **0**, and `EVALUATION_PASS 18`; `evaluation.json` binds the selection lock and reports 18 unique runs. The checked artifact set has 54 prediction files, with their hashes matched to receipts. The later duplicate attempt's exit 1 at the existing-directory guard is separately retained and did not replace the original successful launch. |
| Independent replay and event coverage | **PASS.** `VERIFY.json`/`.md` record test exit **0** (5 tests), replay exit **0**, `VERIFY_PASS 18 54`, 18 checkpoint replays, 54 prediction files, and 36 unique out-of-fold events per model/seed. Root/detection logits were bitwise equal; labels, event IDs, indices, and TRAIN-only scalers matched; independent float64 pooled log probabilities differed by at most `2.842170943040401e-14` against `1e-12` tolerance; exact tie credits matched. Replay was not repeated because valid proof already exists. |
| Independent report recomputation | **PASS.** The focused `analysis.py` run reloaded only the permitted NPZ and saved prediction files; checked rotation/run/history/checkpoint/prediction/source hashes and mappings; independently pooled event probabilities and recalculated metrics, prior, paired comparisons, type/recording tables, bootstrap, learning state, and costs; then byte-compared regenerated `ANALYSIS.json` and the generated body of `ANALYSIS.md` with the saved files. It emitted `ANALYSIS_PASS 36`, exit **0**. |
| Numeric statements in `REPORT.md` | **PASS.** Compared against the recomputed `ANALYSIS.json` and `ANALYSIS.md`: seed Top-1/Top-3 values and sample SDs; paired differences and 12/22/2 and 17/14/5 win/tie/loss counts; 5,000-replicate, seed-20261017, four-recording bootstrap ranges; prior 1/12 and 3/12; type/recording results; selected-epoch and update ranges; stage-cost sums. Values and rounding agree. Report links to `PLAN.md`, `ANALYSIS_PROTOCOL.md`, `ANALYSIS.json`/`.md`, `TRAIN_VERIFY.md`, `PRETRAIN_VERIFY.md`, `EVAL_EXECUTION.md`, and `VERIFY.json`/`.md` resolve to existing files. |
| Learning, costs, and failures | **PASS.** Analysis validates full 200-epoch histories against epoch logs and selection receipts, epoch/update counts, stage receipts, and rotation done receipts; `ANALYSIS.json` retains first/selected/final learning records and actual stage-cost sums. `REPORT.md` distinguishes event NLL from joint loss and overlapping stage sums from elapsed time. Earlier R0/R1 wrong-working-directory launches, trailing-dot lock invocation, and duplicate evaluation guard failure remain in `TRAIN_R0.md`, `TRAIN_R1.md`, `TRAIN_VERIFY.md`, and `EVAL_EXECUTION.md`; recovered successful evidence is separately identified. |
| Protocol and claims | **PASS.** Analysis preserves all 36 events and 12 candidates, excludes normal windows from root scoring, checks 12 events per split, computes exact tie credit, and reports event-level rather than treating 108 seed-event predictions as independent. Type/recording breakdowns and bootstrap parameters are present. The report does not claim a blind final test, cold-root/new-recording/general-population performance, convergence, a pure GNN causal effect, or a new-method/pristine improvement; it explicitly says the proposed read-only scaling diagnostic was **not run** and that evidence is insufficient for an architecture change. |

## Commands and actual exits

Commands executed for this check, from
`/home/gnho1236/r2/research/sn_corrected_20261017`:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 \
  /home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_analysis
# exit 0; Ran 11 tests; OK

OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 \
  /home/gnho1236/r2/.venv-eadro/bin/python -B analysis.py
# exit 0; ANALYSIS_PASS 36
```

The monitored processes completed; neither was still running at handoff.

Previously captured upstream command results reused rather than redundantly
rerun: training gates and lock **exit 0** with `ROTATION_DONE {0,1,2} 200` and
`SELECTION_LOCKED 18`; original evaluation **exit 0** with
`EVALUATION_PASS 18`; independent replay tests and replay **exit 0** with
`VERIFY_PASS 18 54`. The failed attempts listed above remain failures in their
own receipts; they are not reported as passing commands.

## Findings / owner

**No unresolved finding.** No producer amendment is requested. The explicitly
unrun standardized-input-range diagnostic is a proposed future read-only
follow-up, not a missing requirement for this deliverable. No optional
`check_report.py` was needed: the existing frozen analysis recomputation and
focused test suite supplied the numeric assertions.

## Latest focused report interpretation check (2026-10-17)

**Focused verdict: PASS.** Re-read the latest `REPORT.md` and `ANALYSIS.md`,
then checked the corresponding `TRAIN_VERIFY.md` and `EVAL_EXECUTION.md`
receipts. The three requested corrections are present:

1. **Scoring units versus independence — PASS.** `REPORT.md` says, “점수
   산출 단위는 고유 사건 36개” and “이 36개 사건 사이의 독립성은
   확립되지 않았고, recording cluster도 4개뿐이다.” It does not claim
   36 independent effective samples; it separately says the 108 seed-event
   predictions are not 108 independent events.
2. **Trace observation — PASS.** `REPORT.md` says, “모든 장애 창에서
   root trace가 적어도 일부 관측된 CPU 사건에서도 두 모델이 놓친
   사건이 있었고.” This is a claim of at least some observed trace in each
   window of the referenced CPU cases, not that every time bin was observed.
   The event-level counts in `ANALYSIS.md` are consistent with that narrower
   wording.
3. **Failed attempts and recovery — PASS.** `REPORT.md` states, “R0와 R1의
   최초 작업 디렉터리 실행 시도는 학습 전에 `runner.py`를 찾지 못해
   exit 2로 실패했으며,” then discloses the trailing-dot lock failure and
   recovery (`SELECTION_LOCKED 18`), the duplicate evaluation guard exit 1,
   and the recovered original exit 0 / `EVALUATION_PASS 18`. These distinctions
   match the authoritative sections of `TRAIN_VERIFY.md` and
   `EVAL_EXECUTION.md`; the failed attempts are not represented as successes.

**Numerical/artifact verification: reused PASS.** The numeric tables and
claims remain unchanged from the previously verified report and agree with
the latest `ANALYSIS.md`; the existing comprehensive numerical and artifact
PASS above is preserved. No fitting, inference, command, or test was rerun.
Tests are not needed for this prose-only correction. No additional unsupported
claim was found in the focused interpretation and receipt checks.
