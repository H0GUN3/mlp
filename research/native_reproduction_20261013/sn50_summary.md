# SN50 native calibration verification

**Verification: PASS** — checked 6/6 runs.
Validation scores below were recomputed directly from saved logits and labels using NumPy, including neutral expected credit for exact root-score ties.

Validation fault windows per run: [65, 65, 65, 65, 65, 65]. These are correlated windows, not independent incidents; the three seeds are not three incident replications.

| Kind | Conditional Top1 mean [range] | Gated Top1 mean [range] | Detection F1 mean [range] | Best epochs | Train loss mean [range] | Validation loss mean [range] | Parameters |
|---|---:|---:|---:|---|---:|---:|---:|
| eadro | 0.461538 [0.353846, 0.630769] | 0.420513 [0.323077, 0.584615] | 0.928378 [0.928, 0.929134] | 31, 33, 40 | 0.660355 [0.54221, 0.773555] | 0.989344 [0.934552, 1.07162] | 64355, 64355, 64355 |
| diagmlp | 0.897436 [0.846154, 0.953846] | 0.876923 [0.8, 0.938462] | 0.974079 [0.953125, 0.992366] | 49, 48, 50 | 0.0668933 [0.0643196, 0.0706176] | 0.246593 [0.201286, 0.315396] | 75810, 75810, 75810 |

Predeclared ≥45 best-epoch trigger: **TRIGGERED**. Runs: diagmlp/seed_11 (epoch 49), diagmlp/seed_23 (epoch 48), diagmlp/seed_37 (epoch 50).
No 200-epoch diagnostic was run. Protocol calls for a separate 200-epoch diagnostic of both methods × three seeds.

This is corrected native calibration, not exact reproduction of original paper scores. The historical source evaluator used different HR@1/F1 denominators, and the exact original DiagMLP experiment implementation is unavailable. No test partition was evaluated.
