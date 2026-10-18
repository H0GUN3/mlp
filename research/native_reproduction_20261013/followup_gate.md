# Follow-up gate: SN200 and TT50

## Final parent verification — supersedes the earlier snapshot below

**SN200 PASS, TT50 PASS; 6/6 runs each, no remaining verifier failures.**
The final TT37 run was still executing when the earlier gate inspected it.
A parent monitor waited for its `summary.json`, then ran the unchanged TT50
verifier: exit0, `CALIBRATION_VERIFIED`. No duplicate training was launched.
Both verification JSONs now report PASS and empty failure lists.

Independently verified three-seed mean [range], in percent:

| Cohort/model | Fault-only root Top1 | Detector-gated root Top1 | Selected epochs |
|---|---:|---:|---|
| SN200 Eadro | 60.00 [40.00–78.46] | 54.87 [35.38–72.31] | 31,90,200 |
| SN200 DiagMLP | 95.38 [92.31–98.46] | 94.36 [89.23–98.46] | 192,78,200 |
| TT50 Eadro | 79.64 [78.43–81.05] | 78.96 [78.43–79.45] | 48,50,46 |
| TT50 DiagMLP | 98.64 [98.40–98.83] | 95.43 [94.31–96.06] | 27,23,24 |

SN has65 and TT686 correlated validation fault windows, not that many
independent incidents. These remain corrected native calibration scores, not
new-method results or exact published-score reproduction. SN stops at200 even
where the selected epoch is late. The frozen TT200 diagnostic is triggered and
already authorized by the approved budget; no new approval is required.

Two first attempts also failed before training because a prose-ending dot was
copied as a CLI argument. Only those two commands were corrected; successful
runs were reused. Their failures remain in the DAG journal.

## Earlier gate snapshot — retained failure history, no longer current

## Verification outcome

**SN200: PASS.** The verifier exited 0 with `CALIBRATION_VERIFIED`; all 6/6
runs passed, with no failed artifact/hash/input/split/scaler/independent-score
checks. The recorded SN200 first-50 loss/score/update histories exactly match
SN50 for all six runs. **TT50: FAIL.** The verifier exited 1 with
`CALIBRATION_FAILED`; 5/6 runs were checked. Its sole failure, verbatim:

`diagmlp/seed_37: incomplete/unreadable run: [Errno 2] No such file or directory: '/home/gnho1236/r2/research/native_reproduction_20261013/calibration50/TT/diagmlp/seed_37/summary.json'`

The verifier-generated details are in `sn200_verification.json`,
`sn200_summary.md`, `tt50_verification.json`, and `tt50_summary.md`.

## Observed calibration results

Train and validation losses are ranges at each run's selected best epoch.
Correlated fault-window counts are per validation run, not independent
incidents.

| Cohort/model | Best epochs (seeds 11/23/37 where present) | Train loss range | Validation loss range | Parameters | Fault windows/run | Training+validation cost |
|---|---|---:|---:|---:|---:|---:|
| SN200 Eadro | 31, 90, 200 | 0.0295–0.7736 | 0.6838–1.0716 | 64,355 | 65 | 64.29–66.34 s |
| SN200 DiagMLP | 192, 78, 200 | 0.0013–0.0120 | 0.0796–0.2565 | 75,810 | 65 | 53.28–55.93 s |
| TT50 Eadro | 48, 50, 46 | 0.3976–0.4373 | 0.4504–0.5092 | 66,178 | 686 | 341.13–356.67 s |
| TT50 DiagMLP | 27, 23 (seed 37 missing) | 0.1466–0.1620 | 0.1979–0.2090 | 140,033 | 686 | 283.14–285.51 s |

These are observed run costs, not isolated hardware benchmarks. No test
partition was evaluated.

## Next predeclared gate

TT50 meets the frozen best-epoch ≥45 trigger: all three Eadro runs select
epochs 48, 50, and 46. The protocol therefore calls for exactly one bounded
TT200 calibration of both methods and all three seeds, with other settings
fixed. **TT200 has not been run and is not launched here.** First resolve the
missing TT50 `diagmlp/seed_37` artifact and rerun verification; the cohort
remains failed until then. Do not advance to later research gates on this
incomplete verification.

These are native reference calibration results—not original-paper
reproduction and not a proposed improvement.
