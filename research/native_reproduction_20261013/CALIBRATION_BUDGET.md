# Calibration budget — frozen after runtime profile, before 50-epoch results

For each ready system, run both `eadro` and `diagmlp` with seeds11/23/37:
50 epochs, Adam lr0.001, batch256, CPU2 threads, fixed split42.
These epoch/lr/batch values match the pinned public `codes/main.py` defaults.
Keep the declared native/reconstruction architectures and dropout choices.
No hyperparameter search. Full-budget training replaces the source's
training-loss early stop; checkpoint selection uses validation joint loss only.

SN one-epoch measurements: Eadro0.342s and DiagMLP0.298s for training/validation,
with two updates each. Both saved checkpoints replayed bitwise; their split and
scaler hashes match. These are cost measurements, not competitive accuracy.
Six SN runs ×50 epochs are a small CPU experiment; concurrent timings are not
isolated hardware speed benchmarks. TT requires its own ready-input/time check.

## Bounded convergence diagnostic

Retain every 50-epoch result. If any run in a system selects epoch45 or later,
run exactly one additional, separately labelled **200-epoch calibration** for
both methods and all three seeds of that system, with every other choice fixed.
This is a predeclared baseline adequacy check, not a proposed improvement or an
unbounded tuning loop. Do not extend beyond200; report remaining nonconvergence
or late selection. Do not consult test predictions to trigger this diagnostic.

## Execution DAG

Each system's six independent runs have disjoint output directories under
`calibration50/{system}/{kind}/seed_{seed}`. A dependent verification node reads
all six outputs, verifies matched inputs/splits/scalers, checkpoint hashes and
replay evidence, and independently rescores saved validation predictions.
Only the verified summary determines the next phase. Original paper-score
reproduction remains distinct from this corrected native calibration.
