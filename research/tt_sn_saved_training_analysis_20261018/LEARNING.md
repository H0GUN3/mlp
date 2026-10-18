# Saved-history learning and checkpoint selection

Scope: native calibration50 TT/SN and calibration200 SN; DiagMLP is primary,
Eadro supplementary. These are fixed native window-level validation histories,
not the corrected SN event split. No training, inference, checkpoint
deserialization, raw feature access, or RE2 work was performed.

## Reading the metrics

`train_batch_weighted_joint_loss` is the training-mode loss averaged over
training minibatches in that epoch, weighted by batch size. `validation_joint_loss`
is the full validation-set loss after that epoch's updates, evaluated in
validation mode. In the trainer, joint loss is
`0.5 * detection cross-entropy + 0.5 * root-localization cross-entropy over
fault windows`; normal windows have no root-localization term.
Conditional Top1 ranks root candidates only on fault windows. Gated Top1
additionally requires fault detection, so it can be lower. Accuracy fields
below are history metrics, not TRAIN accuracy (which was not recorded).

Cells are `train loss / validation loss / conditional Top1 / gated Top1`;
Top1 is shown as percent. `—` means that epoch is beyond that run's history.
Fixed-epoch values are rounded to four decimals for losses and one decimal
percentage point for Top1.

## Primary: DiagMLP

| Cohort / seed | 1 | 10 | 25 | 50 | 75 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|---|---|
| TT50 / 11 | 1.8633/1.8384/16.0/16.0 | .3480/.3031/97.7/97.7 | .1684/.2272/98.5/96.8 | .0511/.3562/97.7/91.5 | — | — | — | — |
| TT50 / 23 | 1.8492/1.8088/15.0/15.0 | .3015/.2733/97.7/97.7 | .1468/.2033/98.1/88.8 | .0511/.3338/97.5/93.9 | — | — | — | — |
| TT50 / 37 | 1.8662/1.8385/10.2/10.2 | .3536/.3115/96.9/96.9 | .1589/.2015/98.1/96.4 | .0766/.2984/97.7/80.3 | — | — | — | — |
| SN50 / 11 | 1.6206/1.5097/1.5/1.5 | 1.2921/1.3660/20.0/20.0 | .6449/.7742/67.7/66.2 | .0615/.3518/81.5/75.4 | — | — | — | — |
| SN50 / 23 | 1.6230/1.5294/9.2/9.2 | 1.3486/1.3869/16.9/16.9 | .6965/.8389/64.6/64.6 | .0620/.2041/96.9/96.9 | — | — | — | — |
| SN50 / 37 | 1.5917/1.4942/0.0/0.0 | 1.3006/1.3817/13.8/13.8 | .6796/.7769/64.6/64.6 | .0706/.2231/89.2/89.2 | — | — | — | — |
| SN200 / 11 | 1.6206/1.5097/1.5/1.5 | 1.2921/1.3660/20.0/20.0 | .6449/.7742/67.7/66.2 | .0615/.3518/81.5/75.4 | .0120/.2791/87.7/84.6 | .0062/.3249/87.7/83.1 | .0020/.2842/89.2/84.6 | .0017/.2612/92.3/87.7 |
| SN200 / 23 | 1.6230/1.5294/9.2/9.2 | 1.3486/1.3869/16.9/16.9 | .6965/.8389/64.6/64.6 | .0620/.2041/96.9/96.9 | .0107/.1413/98.5/98.5 | .0071/.1698/96.9/95.4 | .0027/.1591/96.9/96.9 | .0016/.1634/98.5/96.9 |
| SN200 / 37 | 1.5917/1.4942/0.0/0.0 | 1.3006/1.3817/13.8/13.8 | .6796/.7769/64.6/64.6 | .0706/.2231/89.2/89.2 | .0189/.1217/93.8/93.8 | .0077/.1042/93.8/93.8 | .0030/.1001/93.8/93.8 | .0041/.0796/95.4/95.4 |

### Progress and selection effects

- TT50 DiagMLP's three seeds move from validation loss 1.8088–1.8385 at
  epoch 1 to 0.2015–0.2272 at epoch 25, while conditional Top1 reaches
  98.1–98.5%. Training loss continues downward through epoch 50, but
  validation loss rises to 0.2984–0.3562. The prescribed minimum-loss
  checkpoints are epochs 23, 24, and 27—not the accuracy peaks at 16, 23,
  and 38. At selected checkpoints conditional Top1 is 98.4–98.8%; final
  epoch values are 97.5–97.7%. Gated accuracy can diverge more: seed 37
  falls from 96.1% at its selected epoch to 80.3% at epoch 50.
- SN gains are later by epoch than TT in these records. At SN epoch 50,
  conditional Top1 is 81.5%, 96.9%, and 89.2% (seeds 11/23/37), versus
  epoch 1 values 1.5%, 9.2%, and 0.0%. The clearest broad rise is through
  epochs 1–50; epoch 50 to 100 adds 6.2, 0.0, and 4.6 points for seeds
  11/23/37. Between epochs 100 and 150 the changes are +1.5, 0.0, and
  0.0 points; between 150 and 200 they are +3.1, +1.5, and +1.6 points.
  Seed 23 reaches its accuracy maximum at epoch 51 and seed 37 at 129. Later
  changes are nonmonotonic: seed 37 falls from 96.9% at epoch 129 to 93.8%
  at epoch 150 before ending at 95.4%. Across SN200 seeds, selected epochs
  are 192/78/200, whereas accuracy maxima occur at 167/51/129. Thus
  minimum-loss selection is not equivalent to choosing maximum root accuracy.
- SN50 and SN200 paired runs have identical first-50 numeric history rows
  per seed (excluding elapsed seconds), as recorded in the ledger. These are
  separately invoked runs, not a resumed optimizer state. SN uses 2 logged
  updates per epoch (100 by epoch 50; 400 by epoch 200), versus TT's 13
  (650 by epoch 50). Equal epochs therefore do not mean equal update counts;
  cohort size, input distribution, and model/run system also differ, so
  TT–SN differences are not an isolated causal effect.
- At SN200 selected checkpoints, conditional/gated Top1 is 92.3/89.2%,
  98.5/98.5%, and 95.4/95.4% across seeds 11/23/37. At final epochs it is
  92.3/87.7%, 98.5/96.9%, and 95.4/95.4%. Selected-vs-final loss is
  0.2565 vs 0.2612, 0.1242 vs 0.1634, and 0.0796 vs 0.0796. Selection can
  therefore favor a different detection/localization balance than the final
  epoch, even when conditional root accuracy is unchanged.

### Per-seed selection receipts

| Cohort / seed | Selected epoch (validation loss) | Selected conditional / gated | Final epoch (validation loss) | Final conditional / gated | Earliest absolute 90% / 95% Top1 | Earliest max-accuracy epoch |
|---|---:|---:|---:|---:|---:|---:|
| TT50 / 11 | 27 (.2090) | 98.8 / 94.3 | 50 (.3562) | 97.7 / 91.5 | 7 / 8 | 38 |
| TT50 / 23 | 23 (.1979) | 98.7 / 95.9 | 50 (.3338) | 97.5 / 93.9 | 6 / 7 | 16 |
| TT50 / 37 | 24 (.2001) | 98.4 / 96.1 | 50 (.2984) | 97.7 / 80.3 | 6 / 8 | 23 |
| SN50 / 11 | 49 (.3154) | 84.6 / 80.0 | 50 (.3518) | 81.5 / 75.4 | — / — | 43 |
| SN50 / 23 | 48 (.2013) | 95.4 / 93.8 | 50 (.2041) | 96.9 / 96.9 | 36 / 42 | 47 |
| SN50 / 37 | 50 (.2231) | 89.2 / 89.2 | 50 (.2231) | 89.2 / 89.2 | — / — | 39 |
| SN200 / 11 | 192 (.2565) | 92.3 / 89.2 | 200 (.2612) | 92.3 / 87.7 | 128 / — | 167 |
| SN200 / 23 | 78 (.1242) | 98.5 / 98.5 | 200 (.1634) | 98.5 / 96.9 | 36 / 42 | 51 |
| SN200 / 37 | 200 (.0796) | 95.4 / 95.4 | 200 (.0796) | 95.4 / 95.4 | 58 / 74 | 129 |

90%/95% epochs are the first epochs at or above absolute conditional Top1
0.90/0.95; `—` means the threshold was never reached. They are descriptive,
not selection criteria. No TRAIN accuracy is available. Gated Top1 is native
fault-window detection-gated root accuracy; it is not a detection-only score.

## Supplementary: Eadro

Each cell is `train loss / validation loss / conditional Top1 / gated Top1`;
Top1 is percent. The fixed-epoch trajectory is summarized here separately
from the primary model. Missing later epochs are outside the 50-epoch history.

| Cohort / seed | 1 | 10 | 25 | 50 | 75 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|---|---|
| TT50 / 11 | 1.9404/1.8556/5.0/5.0 | .9458/.9048/44.5/44.5 | .5983/.6760/59.9/59.9 | .4398/.4747/80.8/80.8 | — | — | — | — |
| TT50 / 23 | 1.8634/1.7772/8.2/8.2 | .9199/.8990/49.0/49.0 | .6162/.6403/64.0/64.0 | .4293/.5092/78.4/78.4 | — | — | — | — |
| TT50 / 37 | 1.9562/1.8430/6.8/6.8 | .9574/.8769/46.8/46.8 | .5227/.5510/71.1/71.1 | .4513/.4925/78.7/78.7 | — | — | — | — |
| SN50 / 11 | 1.5869/1.5440/9.2/9.2 | 1.2514/1.2968/15.4/15.4 | .9092/1.1694/30.8/27.7 | .4308/1.3055/56.9/50.8 | — | — | — | — |
| SN50 / 23 | 1.6115/1.5790/4.6/4.6 | 1.2604/1.3248/16.9/16.9 | .8524/1.2012/24.6/23.1 | .4049/1.2144/49.2/46.2 | — | — | — | — |
| SN50 / 37 | 1.6008/1.5743/0.0/0.0 | 1.2672/1.3252/12.3/12.3 | .8208/1.2226/35.4/30.8 | .3977/.9708/64.6/60.0 | — | — | — | — |
| SN200 / 11 | 1.5869/1.5440/9.2/9.2 | 1.2514/1.2968/15.4/15.4 | .9092/1.1694/30.8/27.7 | .4308/1.3055/56.9/50.8 | .2678/1.4283/66.2/60.0 | .2086/1.8388/69.2/64.6 | .0729/2.1878/58.5/53.8 | .0287/2.4137/67.7/63.1 |
| SN200 / 23 | 1.6115/1.5790/4.6/4.6 | 1.2604/1.3248/16.9/16.9 | .8524/1.2012/24.6/23.1 | .4049/1.2144/49.2/46.2 | .2157/.7957/58.5/53.8 | .1511/.8146/61.5/60.0 | .0936/1.0558/63.1/56.9 | .0292/1.1881/64.6/63.1 |
| SN200 / 37 | 1.6008/1.5743/0.0/0.0 | 1.2672/1.3252/12.3/12.3 | .8208/1.2226/35.4/30.8 | .3977/.9708/64.6/60.0 | .2261/.8153/72.3/67.7 | .1336/1.1219/81.5/75.4 | .0868/.9340/83.1/80.0 | .0295/.6838/78.5/72.3 |

Eadro also reduces training loss as training proceeds, but validation loss
often worsens while window accuracy continues to rise. For SN200 seed 11,
validation loss increases from its selected 1.0716 at epoch 31 to 2.4137 at
epoch 200 even as conditional Top1 reaches 67.7%; for seed 23 the selected
epoch is 90 (loss .7642), while the earliest maximum conditional Top1 is
104 (69.2%; final is 64.6%). Seed 37 selects epoch 200 (loss .6838), but
its maximum accuracy occurs at epoch 86 (83.1%, versus 78.5% at epoch 200).
This shows why loss-based selection and accuracy-maximizing selection are
different criteria, not that one criterion is universally preferable.

## Evidence and limits

The run ledger reports all 18 allowed runs' config/split/history/prediction
hashes matching their saved summary artifact hashes; recorded update totals
match histories and summaries. All nine DiagMLP history SHA-256 values used
here also match the read-only `native_learning_diagnosis_20261018/RESULTS.json`
source-hash map; its matching native metadata and config/split/history
receipts support reuse of its selected/peak/threshold calculations. That
analysis script was not executed. Run-ledger verifier receipts are PASS
(6/6 each for TT50, SN50, SN200). No checkpoint was loaded or re-inferred.

This describes saved native validation windows only. These SN windows overlap
28 underlying events, and the split is not a held-out-event generalization
test. Paired-event analysis, corrected SN rotation, and Hawkes arm comparison
are outside this deliverable. The difference between TT and SN cannot isolate
an update-count or cohort causal effect; batch identities/sizes actually
executed and TRAIN accuracy are not saved.
