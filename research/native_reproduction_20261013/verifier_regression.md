# Calibration verifier regression

The parameterized verifier preserves the original SN50 verifier and artifacts.
Its SN50 regression uses the `verifier_regression_sn50` output prefix, so the
existing `sn50_verification.json` and `sn50_summary.md` remain untouched.

Independent metrics are recomputed directly from saved validation logits using
the original `independently_score` implementation. Run checks include complete
history, per-file SHA256 integrity, replay evidence, system/seed/epoch options,
protocol split counts, input/split/scaler consistency, validation index/shape
agreement, independently recomputed scores, and minimum-validation-loss
checkpoint selection.

For 200-epoch runs, validation compares against same-system 50-epoch runs:
all input, split, scaler and model settings must match, except epochs/output
paths; each first-50 loss, score and optimizer-update value must match exactly
(timings excluded). Exact floating-point differences are reported as failures,
not rounded away. Best epochs at or beyond 45 are flagged for 50 epochs; for
200 epochs late selections are reported without further extension.

The verifier does not train, inspect test partitions, or certify absent or
incomplete run sets. A negative synthetic check will mutate a copied hash or
score/run-completeness condition and require rejection; production artifacts
are never modified.
