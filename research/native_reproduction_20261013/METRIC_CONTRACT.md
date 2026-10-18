# Native calibration metric contract

Source checked: pinned repair fork
[`codes/base.py`, `BaseModel.evaluate`](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/base.py).

The public implementation increments its variable `TP` for both a correctly
detected fault and a correctly detected normal window. Its `pos=TP+FN` therefore
equals **actual faulty windows + correctly detected normal windows**.
However, its HR numerator increases only for correctly localized faults.

Consequences, using ordinary binary detection counts TP/FP/FN/TN:

* Source HR@1 = gated correct-root count / (fault count + TN).
* Source F1 = 2(TP+TN) / (2(TP+TN)+FP+FN).
* Correct normal detections can **decrease source HR@1**, not increase it.
  They can inflate its reported F1 relative to fault-positive F1.

The previously recorded source evaluator fixture demonstrated the denominator
effect: one correctly localized fault gives HR@1=1; adding a correctly detected
normal window gives HR@1=0.5. This is not a model accuracy experiment.

## Our declared outputs

`native_models.native_scores` uses:

1. **Conditional root Top1**: correct root ranking / actual fault windows,
   ignoring the detector. This is diagnosis given that a fault exists.
2. **End-to-end root Top1**: detector says faulty AND root ranking correct /
   actual fault windows. Missed detections count as failures.
3. **Detection F1**: 2TP/(2TP+FP+FN), with normal correct decisions in TN,
   not TP. A no-positive/no-predicted-positive fixture is reported as 0 by
   convention, not a location score.

Root-score ties receive neutral expected credit, rather than an arbitrary
service-index advantage. No-fault batches have null root scores.

Do not call these numbers identical to the old source HR/F1. Do not assume the
later DiagMLP paper used the uncorrected source evaluator: its exact experiment
implementation is unavailable. Published-score comparison must state which
definition can actually be matched. Corrections are shared measurement rules,
not a proposed-model improvement.
