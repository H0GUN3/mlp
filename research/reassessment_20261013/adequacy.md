# Sample adequacy and observed DiagMLP-variant errors

## Evidence

**Distinct scenarios and coverage.** The split manifest contains 180 cases arranged into 60 distinct system/root-service/fault scenarios, each with three repetitions (the repetitions are not distinct scenarios). This grouping does not demonstrate statistical independence: shared host, session, time, or other dependencies may correlate even different scenarios. In each system, there are 30 scenarios (5 root services × 6 faults): train 54 cases/18 scenarios, validation 18/6, and final test 18/6. Every partition in both systems covers all 5 root services and all 6 fault classes; for each fault there are 9 train, 3 validation, and 3 test cases (3, 1, and 1 scenarios respectively). The train, validation, and test scenario assignments are disjoint. The final-test figures here come from split metadata only; no final-test raw, feature, or prediction data were opened. [split.json: `cases`; PROTOCOL.md: “데이터 경계”]

**What was run.** Saved results contain 12 runs (2 systems × 2 methods × 3 seeds). For `diagmlp_common`, each seed evaluates the same 18 validation cases per system. Recomputed from the saved `validation_rankings`, the observed top-1 errors are:

- RE2-OB: seed 11, 1/18; seed 23, 0/18; seed 37, 1/18. Both errors are the same validation case, `recommendationservice/socket` repetition 2: seed 11 predicted `checkoutservice`; seed 37 predicted `emailservice`.
- RE2-TT: seed 11, 5/18; seed 23, 1/18; seed 37, 4/18. Errors group as follows: `ts-order-service/loss`, repetition 3, seed 11 predicted `ts-auth-service`; `ts-train-service/delay`, repetition 1 seed 37, repetition 2 all three seeds, and repetition 3 seeds 11 and 37, each predicted `ts-travel-service`; `ts-travel-service/cpu`, repetition 1 seeds 11 and 37 predicted `ts-auth-service` and `ts-route-service` respectively, and repetition 3 seed 11 predicted `ts-train-service`. Thus TT has 10 wrong predictions across 54 seed-case evaluations, but only 6 distinct validation cases in 3 root/fault scenarios. Seeds reuse the same cases; neither those evaluations nor the scenarios should be treated as demonstrated independent observations.

`verification.json` independently summarizes DiagMLP validation top-1 means/ranges as 96.3% (94.4–100%) for OB and 81.5% (72.2–94.4%) for TT. These ranges reflect seeds on the same cases, not new samples. `training_results.json` records 80 epochs for each DiagMLP run; validation loss reaches its minimum at epoch 80 in all six runs, which is also the selected epoch. Train loss falls from 2.21–2.48 to 0.252–0.385 (OB) and 3.89–3.97 to 1.051–1.184 (TT). This supports optimization progress through the run, not proof of convergence or generalization.

Validation loss selected the checkpoint, so reporting ranking performance on those same validation cases is selection-conditioned and can be optimistic; its magnitude is unknown. Final-test access is reported as zero (`verification.json`: `final_test_accesses: 0`; `training_results.json`: `final_test_cases_read: 0`). The protected final split has 6 distinct scenarios per system—too few on this design to treat a resulting score as broad evidence, even if later evaluated once; independence between scenarios is not established.

## Answer

- **Interface/backprop smoke: sufficient for the tested plumbing, not a sample-size claim.** `model_checks.json` reports synthetic DiagMLPCommonInput forward/backward passed at 2 and 5 nodes. Real data are not needed to establish those shape/gradient checks. This does not establish the original DiagMLP pipeline or performance.
- **Preliminary within-benchmark learning: yes, narrowly.** Per system there are 54 training cases from 18 distinct scenarios covering all five roots and six faults, with all six seeds’ training losses decreasing and the lowest recorded validation loss at epoch 80. Together with saved validation rankings, that is preliminary evidence this adapted model can learn on these benchmark splits. Repetitions are grouped; seeds reuse cases; independence across scenarios is not demonstrated.
- **Predicting final held-out accuracy: no.** Validation has only six distinct scenarios (18 repeated cases) per system and is used for checkpoint selection; final-test observations were not accessed. The saved validation scores cannot estimate unbiased final-test performance.
- **Broad production/generalization claims: no.** Evidence covers two fixed benchmark systems and a small set of root/fault groups, with fixed candidate vocabularies and a common-input adaptation. It does not test unseen systems, service identities, faults, deployment shifts, or the original full-paper pipeline. There is no universal sample threshold inferred from parameter count here.

These are observed wrong rankings by our local `DiagMLPCommonInput` common-input variant only. They are not evidence of defects in the original DiagMLP implementation, and no causal failure mechanism is inferred. The local variant is not an original-paper reproduction.

## Unknown

- DiagMLP accuracy on final-test cases, and whether the validation error pattern persists there.
- The amount of validation-selection optimism; saved evidence does not quantify it independently.
- Performance on new systems, services, fault types, distributions, or production workloads.
- Whether continued training, different tuning, or other data would change the observed errors; these were not tested here.

## Sources

- Local primary evidence: `research/mlp_prerequisites/split.json` (`cases`, group/partition metadata); `training_results.json` (`datasets`, `runs[*].history`, `runs[*].validation_rankings`, `runs[*].selected_epoch`, `final_test_cases_read`); `verification.json` (`comparison`, `runs`, `final_test_accesses`, `checks`); `model_checks.json` (`adapted`); `PROTOCOL.md` (“데이터 경계”, “학습/선택/평가”); `MODEL_PROVENANCE.md` (“DiagMLP: primary paper architecture, not author code”).
- DiagMLP architecture reference: [arXiv 2501.02766v2, §III-C/D, Eqs. (2)–(3)](https://arxiv.org/html/2501.02766v2#S3.SS3). Local provenance explicitly describes the implementation as a common-input adaptation, not author code or full reproduction.
