# Preparation DAG gate

**PASS — trainer and assessment readiness only.** This does not certify
preprocessing, data integration, calibration, model accuracy, or reproduction.

## Binary checks

Run from `/home/gnho1236/r2`:

```text
pyright --project research/native_reproduction_20261013/pyright-native.json research/native_reproduction_20261013/native_train.py
exit 0 — 0 errors, 0 warnings, 0 informations

DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --self-check
exit 0 — NATIVE_TRAIN_SELF_CHECK PASSED
```

The synthetic fixture emitted two `WARNING: protocol count mismatch; inspect split.json before calibration.` lines and the visible CUDA-unavailable autocast warning. These are not suppressed or treated as real-data results. Evidence: `trainer_self_check_sgs03l7c/self_check.json`, status `passed_synthetic_only`; both model kinds each completed 3 Adam updates, saved a checkpoint and exactly replayed validation logits, labels, indices and loss. `native_train_test.py` checks train-only scaling by changing test-only features and asserting scaler/results unchanged; `fit_scaler` indexes only `train_indices`. `run_training` computes validation loss for checkpoint selection; test is not scaled, evaluated, or used for selection (`test_evaluated: false`).

## Consistency checks

- `native_data_profile.md` records actual annotated Eadro injections: SN **36**, TT **81** (not windows); its archive checks state duplicated all-data members add no cases.
- `rca_native_label_contract.md` and `자료충분성_중간판정.md` preserve RCAEval **180** total and split **108/36/36**, and explicitly state exact activation/end fault intervals are unknown. `DAG_EXECUTION.md` retains the locked split and final36 protection.
- `자료충분성_중간판정.md` reports the earlier DiagMLP validation only, with **18 incidents per system**; it calls these reference values, not proposed-model results. Its stated accuracies are not native trainer results.
- `trainer_implementation.md`, the self-check JSON and `native_self_check.json` characterize checks as synthetic only. None claims native/proposed accuracy from synthetic fixtures.
- Trainer source implements actual optimizer steps, validation-only strict-minimum checkpointing, train-index scaler fitting, and checkpoint replay; these behaviors are also asserted in the self-check rather than inferred from its pass marker alone.

## Unmet prerequisite / boundary

Preprocessing remains a separate, still-needed upstream producer. No raw inputs
were read and no real-data run was performed here. RCAEval fault-duration
uncertainty remains unresolved; therefore faithful native window labels and
calibration are not established. PASS means only that trainer self-check and
assessment artifacts are ready for the next gated step.
