# Native reference calibration — frozen before model results

## Purpose and limits

First exercise native Eadro and an equation-based DiagMLP reconstruction on the
author-linked Eadro release. This is a **reference calibration**, not validation
of a proposed contribution. Exact private DiagMLP wiring, dimensions and split
manifest are unavailable. The public archive has SN36/TT81 annotated injections,
not the SN72/TT162 reported for the original Eadro experiments.

Keep all three native modality encoders and the joint detector/localizer.
`native_models.py` preserves the pinned repair fork's modules and heads.
DiagMLP concatenates metric/log/trace embeddings and a learned 64-dimensional
position, then uses 64-dimensional modal and node fusion blocks, each
Linear→LayerNorm→ReLU→Dropout. It replaces the original GLU and graph/pooling
stage, following the equations rather than silently retaining an extra GLU.
These dimension choices are declared reconstruction choices, not recovered
author settings. Native encoders produce 64/16/64 dimensions respectively.

## Public data and shared processing

Use the four SN and nine TT `data/` recordings. Never count the byte-identical
all-data archives again. Use the three author-designated `no fault` log
recordings per system only as auxiliary training material for Drain templates,
as the public parser does. One TT auxiliary recording lacks a metadata JSON:
do not create supervised fault/normal window labels for it. This is an offline
benchmark with a supplied normal reference, not an online chronological claim.

Preserve the author Info service order, static edges, seven metric channels,
TCN input sequences and two trace channels. The original second trace channel
remains zero; adding invocation counts would be another change.

Common, disclosed alignment/correctness rules:

* Records/metrics use the fork's +16h coordinate; spans use its +8h coordinate.
  Explicitly add +8h to parsed log wallclock coordinates, justified by recording
  boundaries across the corpus, not model accuracy.
* Keep only each recording's own time interval. Historical spans are not new
  observations in later recordings. Audit duplicate span identities and any
  conflicting contents before deciding whether a correction is needed.
* Form full 10-second, stride-10 windows. Metrics occupy ten integer samples;
  fractional log times use the corresponding half-open `[start,start+10)`
  interval, rather than silently losing the final fractional second.
* Preserve source integer-rounded fault endpoints and identify any overlapping
  fault interval. Reject ambiguous simultaneous roots rather than choosing one.
* Keep the source Drain configuration and unseen-template bin. HawkesADM4 uses
  tick0.7.0.1, decay3, baseline initialization0.2 and original solver defaults.
  After shifting events to a relative origin, its observation horizon is the
  window duration, not the absolute epoch timestamp. No substitute estimator.
* Fit metric/trace centering and scaling on the selected training windows only.
  Record constant channels and scaler statistics. No test-driven repairs or
  performance-conditioned exclusions.

All raw arrays retain recording, interval, fault-event and root/type provenance.
An individual fault spans multiple correlated windows.

## Calibration partition

Use nonoverlapping windows and an explicitly recorded seed42 permutation.
Reconstruct the public splitting convention with
`train_validation=floor(0.7*n)`, `test=floor(0.3*n)`,
`validation=floor(0.2*train_validation)`. Record any remainder as unassigned,
never silently discard it. The expected count check is SN316/78/169 and
TT3256/813/1744; investigate a mismatch rather than forcing sample selection.
Matching counts does **not** establish the original sample identities.

This window partition can put different windows of one injection into several
partitions. Report that overlap explicitly. It is unsuitable as sole evidence
of generalization to a new incident, and must not be marketed as such.

Only baseline models belong in this first calibration. Choose checkpoints on
validation, never test. Training budget and seed list must be recorded before
training starts. Report both fault-only root accuracy and end-to-end measures;
do not merge correct normal detection into fault localization accuracy.
`METRIC_CONTRACT.md` spells out the old source's inconsistent denominators and
the declared conditional-root, gated-root and fault-positive detection metrics.

## Subsequent research gate

Preserve the existing RCAEval train108/validation36/final36 lock. Do not open
RCAEval final36 during development. The local 17-feature error is not yet a
demonstrated native-method failure. Verify appropriate native input/label
semantics before testing persistence on those incidents; unrelated Eadro
incidents do not prove persistence of that exact error.

Only then define at most two bounded proposed mechanisms. Freeze their
comparison protocol and equal tuning budget before results. A stronger
incident-grouped evaluation must disclose its smaller independent sample count
and changed question; it cannot be substituted for the published window task
and presented as a universal improvement.
