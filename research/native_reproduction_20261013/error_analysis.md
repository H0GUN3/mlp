# Local DiagMLP-common error analysis

## Scope and replay

This diagnoses **the local 17-feature adaptation**, not original DiagMLP or its paper.
No training, dependencies, final-test raw reads, or existing-file changes were made.
Only `re2tt_ts-train-service_delay_{1,2,3}` raw metrics/traces were inspected,
after all three were confirmed `partition=validation` in `split.json`.
Their injection times are 1705944092, 1706123446, and 1706124991.
No raw logs were read.

From `/home/gnho1236/r2`, the final diagnostic command is:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-mlp/bin/python -B research/native_reproduction_20261013/error_analysis.py --raw
```

Before any raw read, it checks split hashes against feature/training artifacts,
both implementation hashes, all three checkpoint hashes, validation ordering,
targets/presence, and the train-only scaler. It replays all 18 cached RE2-TT
validation inputs: **all candidate logits match saved values exactly**
(`max_abs_replay_error=0` for seeds 11/23/37), and all saved rankings match.
All selected epochs are 80. Existing `verification.json` separately records
`checkpoint_prediction_replay` as passed.

For delay_2, validation row **10** (zero-based), vocabulary indices are
**57=train**, **60=travel**; the target is 57. Both candidates are present;
68/69 candidates are present, only `istio-init` absent. Thus this is not a
missing-root, label-offset, or masked-out-root error.

| Seed | Train logit | Travel logit | Travel−train | Root rank |
|---|---:|---:|---:|---:|
| 11 | 1.917927 | 1.993522 | 0.075595 | 2 |
| 23 | 2.313661 | 2.513377 | 0.199716 | 2 |
| 37 | 1.630457 | 1.947839 | 0.317382 | 2 |

These are three model seeds on **one incident**, not three independent failures.
Sibling root ranks (delay_1/2/3) are 1/2/2, 1/2/1, and 2/2/2 respectively.

## Verified inputs

`mlp_readiness.change` retains signed `log1p` of a median shift divided by
`max(normal IQR, 0.05*abs(normal median), 1e-9)`, with ≥20 finite samples
per window. Each case has 720/721 metric samples and 719/720-second spans.
Independent reconstruction of both services' **all 17 features**, for all
three siblings, matches `features.json` exactly.

Delay_2 feature changes, before standardization:

| Field | Train | Travel |
|---|---:|---:|
| CPU | −0.925268 | −0.816205 |
| Memory | 0.131121 | 0.062480 |
| latency-50 | 6.813993 | 6.379434 |
| latency-90 | 7.561007 | 3.021242 |
| Workload | −1.174496 | −0.634873 |
| log trace-median ratio | 5.255389 | 0.436318 |

Both services have validity masks `[1,1,1,1,1,0,1,1]` for
CPU/memory/latency-50/latency-90/workload/error/trace-ratio/presence.
The **error columns are absent**, not observed error-free.
Delay_1 has error-valid=1 for both; delay_3 has the same masks as delay_2.
Train/travel latency-50 metric medians change
0.005567→0.500000 / 0.017500→0.532520;
latency-90 changes 0.009311→0.903553 / 0.095363→3.414462
(stored metric units).
Standardized latency-50, latency-90, trace-ratio values are
9.340/8.613/19.001 for train versus 8.734/3.315/1.527 for travel.
The root's large signal is retained, not accidentally erased.

## Trace semantics and information loss

Source: `extract_features` groups **every span by `serviceName`**, using
`startTime/1e6` for onset and pooled duration medians. `startTimeMillis`
agrees within 0.001 seconds; `(traceID,spanID)` has no duplicates.
Duration numbers below use stored units; this inspection does not independently
certify their unit or raw upstream conversion.

Train counts are 37800→27403, median 1051→201367 (**191.596×**).
Travel counts are 21302→15295, median 5902→9129 (**1.547×**),
but travel p90 grows 39636→641860.
Train spans include `TrainTypeRepository.findById`
(median 1108→201441), `find ts.trainType` (845→201121), and
`GET /api/v1/trainservice/trains/{id}` (3975→404770).
Travel mixes generic `GET`, repository, and endpoint spans:
`TripRepository.findByTripId` stays 1399→1405 while
`GET /api/v1/travelservice/train_types/{tripId}` rises 9758.5→610671.5.
Parent joins show 4216 travel→train span pairs; 483 selected spans have
unresolved parents, so the reconstructed topology is incomplete.

`serviceName` identifies recorded instrumentation ownership, **not physical
fault location**. The schema has no span-kind/peer tags; generic `GET` cannot
be definitively classified. Neither these records nor `fault=delay` establish
network versus application/database injection mechanics. Injection source
was outside the permitted read scope.

The adapter retains six metric-change/validity pairs, two log span-count
rates, rounded median-duration log-ratio/validity, and presence.
It discards operation identity, duration tails, sequences/timing beyond
onset, parent-child timing, and logs; `diskio`/`socket` are ignored despite
being available. `DiagMLPCommonInput.forward` consumes no edges: position
embedding→modal fusion→flattened node fusion→root head.

## Conclusion and unproven explanations

No evident replay, indexing, masking, scaler, or adapter-reconstruction defect
explains this failure. Upstream raw conversion correctness remains unverified.
Learning/representation mismatch is **a hypothesis**, not a demonstrated cause:
train-root training groups are CPU/disk/memory, while travel-root includes
delay; operation pooling and topology omission could obscure propagation.
The large standardized root signal does not force this nonlinear global
classifier to choose the largest anomaly. No sensitivity probes, causal tests,
or new accuracy experiment were performed.

To test persistence, a separately authorized run must verify original-source
modality preprocessing/encoders and label/head contract, rebuild inputs and
train the full original pipeline with fixed seeds and frozen partitions,
then inspect these validation incidents without case-specific tuning.
Final-test evaluation would require separate authorization. **Original
DiagMLP was not run.**

Diagnostic failures retained in companion JSON: initial wrong-path read,
import-resolution diagnostics, and a corrected nullable-status summary bug.
