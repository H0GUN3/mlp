# Lane B — training state and evaluation conditions

## Answer

The network deficit is already present on TRAIN, not only on root/type-held-out
validation. Directed network Top1 is **53.22% TRAIN / 46.18% validation in SN**,
and **32.73% / 31.38% in TT**. These are incident-equal means, not independent
window trials. CPU TRAIN Top1 is 100.00% in SN and 99.99% in TT.

SN received only **35–40 optimizer updates**, versus **360–365 in TT**. All 54
online histories decrease both from epoch 1→5 and 4→5. SN's late decline is
substantial; stopping before optimization settled is plausible. **Neither the
update count nor the decline establishes checkpoint underfitting as the cause**.
TT has roughly ten times as many updates yet high network TRAIN error; “five
epochs means too few steps” is not an adequate common explanation.

No fitting, checkpoint selection, epoch choice, input perturbation or new model
was performed. This diagnosis does not establish an improvement from training
longer, nor distinguish optimization from representation/information limitations.

## Exact budget and online history

The preserved `cv.fit_final` loop performs one update per nonempty batch, with
batch size 32 and five epochs, without early stopping. Counts below are exactly
implied by saved TRAIN indices, saved histories, and that hash-bound loop.
No separate optimizer counter/state was saved, so these are reconstructed counts,
not independently observed optimizer telemetry.

| System | Fold | TRAIN fault windows | TRAIN events | Steps/epoch | Total updates |
|---|---:|---:|---:|---:|---:|
| SN | 0 | 217 | 24 | 7 | 35 |
| SN | 1 | 227 | 24 | 8 | 40 |
| SN | 2 | 206 | 24 | 7 | 35 |
| TT | 0 | 2292 | 54 | 72 | 360 |
| TT | 1 | 2278 | 54 | 72 | 360 |
| TT | 2 | 2332 | 54 | 73 | 365 |

Each history row is event-weighted CE accumulated while parameters change within
the epoch. **It is not CE from the final fixed checkpoint.** The following means
use nine runs per system/mode (three seeds × three folds). Relative late drop is
the mean of each run's `(CE4−CE5)/CE4`, not a ratio of displayed rounded means.

| System | Mode | Online CE1 | CE4 | CE5 | Δ1→5 | Δ4→5 | Relative 4→5 drop |
|---|---|---:|---:|---:|---:|---:|---:|
| SN | local | 2.399606 | 1.932309 | 1.720684 | −0.678922 | −0.211625 | 10.95% |
| SN | global | 2.395025 | 1.887365 | 1.675328 | −0.719697 | −0.212037 | 11.22% |
| SN | directed | 2.395379 | 1.862461 | 1.627800 | −0.767579 | −0.234662 | 12.60% |
| TT | local | 2.476773 | 1.802931 | 1.763641 | −0.713132 | −0.039291 | 2.18% |
| TT | global | 2.460022 | 1.775375 | 1.727278 | −0.732744 | −0.048098 | 2.72% |
| TT | directed | 2.466207 | 1.762194 | 1.713853 | −0.752354 | −0.048342 | 2.76% |

All nine runs in every row decline in both intervals. Directed Δ4→5 ranges are
SN −0.263277…−0.215665 and TT −0.086112…−0.018294. A negative late online delta is
evidence of continuing loss reduction, not a convergence test or proof that
another epoch would improve network root ranking.

## Final-checkpoint fault-type performance

Saved fold `statistics.npz` supplies both the normal TRAIN reference and the
standardizer. Only pure `features.window_features` and `train.transform` are
called; nothing is refitted. Each final checkpoint is evaluated in inference mode
on all its TRAIN faults and on the same whole validation batch used by `cv.predict`.
All 54 validation logits match saved predictions with `np.array_equal`.

Aggregation is: **windows inside an event/evaluation → seeds and applicable folds
inside that event → equally weighted independent events**. Every TRAIN event has
six evaluations (three seeds in two folds); every validation event has three in
its single held-out fold. TRAIN events are not counted twice as independent.
Exact score ties receive uniform Top-k credit and expected reciprocal rank.
CE is stable float64 logsumexp from the unchanged final float32 logits.

### Directed, separated by type

Top1/Top3 are percentages; MRR/CE are unscaled. Each SN type contains 12 independent
events; each TT type contains 27. Unique window totals are SN CPU/delay/loss
107/113/105; TT 1170/1125/1156. The same incidents appear under TRAIN and validation,
but are evaluated by different models/support.

| System | Fault type | Split | Top1 % | Top3 % | MRR | Final CE |
|---|---|---|---:|---:|---:|---:|
| SN | cpu_load | TRAIN | 100.00 | 100.00 | 1.000000 | 0.312168 |
| SN | cpu_load | validation | 99.75 | 100.00 | 0.998737 | 0.444038 |
| SN | network_delay | TRAIN | 55.11 | 77.38 | 0.689342 | 2.108905 |
| SN | network_delay | validation | 51.91 | 70.82 | 0.646580 | 2.122830 |
| SN | network_loss | TRAIN | 51.34 | 76.67 | 0.665055 | 2.080744 |
| SN | network_loss | validation | 40.44 | 65.78 | 0.570174 | 2.207752 |
| TT | cpu_load | TRAIN | 99.99 | 100.00 | 0.999928 | 0.004889 |
| TT | cpu_load | validation | 99.97 | 99.97 | 0.999760 | 0.005976 |
| TT | network_delay | TRAIN | 39.27 | 59.07 | 0.530012 | 2.290601 |
| TT | network_delay | validation | 37.74 | 57.10 | 0.512643 | 2.345190 |
| TT | network_loss | TRAIN | 26.18 | 44.52 | 0.405332 | 2.752036 |
| TT | network_loss | validation | 25.02 | 43.28 | 0.392647 | 2.813409 |

### Combined network, all modes

SN: 24 independent events / 218 unique windows. TT: 54 / 2281. Both network types
are included with equal incident weighting; no advantageous type/probe is selected.

| System | Mode | Split | Top1 % | Top3 % | MRR | Final CE |
|---|---|---|---:|---:|---:|---:|
| SN | local | TRAIN | 37.80 | 71.53 | 0.574631 | 2.204534 |
| SN | local | validation | 32.16 | 66.31 | 0.535766 | 2.243862 |
| SN | global | TRAIN | 36.55 | 70.61 | 0.566073 | 2.181671 |
| SN | global | validation | 32.50 | 66.66 | 0.539101 | 2.222697 |
| SN | directed | TRAIN | 53.22 | 77.02 | 0.677199 | 2.094825 |
| SN | directed | validation | 46.18 | 68.30 | 0.608377 | 2.165291 |
| TT | local | TRAIN | 30.32 | 50.25 | 0.448212 | 2.602295 |
| TT | local | validation | 29.10 | 48.49 | 0.434244 | 2.653516 |
| TT | global | TRAIN | 32.04 | 52.04 | 0.464273 | 2.543589 |
| TT | global | validation | 30.69 | 50.75 | 0.450639 | 2.596947 |
| TT | directed | TRAIN | 32.73 | 51.80 | 0.467672 | 2.521318 |
| TT | directed | validation | 31.38 | 50.19 | 0.452645 | 2.579299 |

Directed network TRAIN error is 46.78% SN / 67.27% TT. Validation minus TRAIN
Top1 is −7.04 / −1.35 percentage points; CE increases by 0.070466 / 0.057981.
The network deficit exists in the fitted support itself, not solely under held-out
evaluation. These differences are descriptive contrasts, **not a decomposition
of error into causal training and holdout contributions**. In particular, they
are not a paired same-model generalization gap.

## Root/type support

Every root service has exactly three development events, one per fault type.
Each fold trains on two types for that root (one event each) and validates on its
remaining type (one event). This was checked for all 36 SN and 81 TT root/fold
combinations. It is **root-specific fault-type holdout**, not unseen-root testing;
the held-out type can occur at other roots in TRAIN.

SN has just 14–24 TRAIN fault windows per root per fold (two events), and 6–12
validation windows (one). TT has 66–97 and 31–51 respectively. For example, SN fold
0 compose-post-service TRAIN has cpu_load (11 windows) and network_loss (6);
validation has network_delay (11). TT fold 0 ts-auth-service TRAIN has cpu_load
(40) and network_loss (48); validation has network_delay (39).

Sparse incident support and root/type transfer are real evaluation conditions.
The high TRAIN network error means they cannot be the entire descriptive story.
Whether the failing network windows lack useful features, the representation is
insufficient, or optimization has not learned available cues is unidentifiable
from these noninterventional observations. Missing/ambiguous measurements and
label issues are also not excluded.

## Narrow consequence and limits

Keep the diagnosis fault-type-specific: separate the SN small-update-budget
warning from TT's high TRAIN network error after many more updates. Do not explain
both with a blanket “five epochs underfit” claim or promise that training longer
fixes them. The parent input-signal lane may further delimit mechanical limits;
this lane does not assume its findings or prescribe a model/epoch change.

These are reused development incidents, not new evaluation. CV TRAIN sets overlap,
and incidents share only four SN/nine TT recordings; no independence-based
confidence interval or significance claim is made. An intervention would be
needed to distinguish optimization from representation/information effects;
none was performed or selected here.

Evidence: [`training.json`](training.json), [`TRAINING_EVIDENCE.md`](TRAINING_EVIDENCE.md).
Exact per-event/fold/seed metrics for **all modes and types** are in
`events[system][mode][split][event_id]`; group results are in `summary`, history
rows/ranges in `histories`/`history_summary`, and root/type support in `support`.
