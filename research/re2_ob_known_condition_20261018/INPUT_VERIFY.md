# Independent input and runner verification

Date: 2026-10-18

## Latest verdict — FAIL; do not start real learning

Actual complete72 preparation is not evidenced. `artifacts/input.json`,
`artifacts/bundle.npz`, `templates.json`, and `profile.json` are absent, and
there is no current successful producer exit record or `KNOWN_INPUTS_PASS`
sentinel. Producer writes/reruns were explicitly prohibited, so none was
started. The prior `frontend-check` stop below is historical, not the current
reason for FAIL.

The approved exact-name policy is implemented in the current `prepare.py`:
only the independent node exactly named `frontend-check` is excluded in both
partitions; other frontend identifiers, all cases/windows, and owned
observations are retained. No aliases are merged. Other unknown validation
nodes still stop. Focused fixtures test this behavior, but do not prove actual
72-case preparation completed.

### Latest verification evidence

- Exact requested monitored unittest discovery: **27 tests, OK, exit 0**;
  `INPUT_VERIFY_TEST_EXIT=0`. Synthetic-only coverage included an 11-iteration
  Hawkes fixture with 0 warnings and a synthetic 200-epoch fit plus separate
  replay (fit PID 1555787 and verify PID 1555988; child exits 0 and expected
  sentinels). No production fit/inference occurred.
- Exact requested monitored project Pyright: **0 errors, 0 warnings,
  0 informations, exit 0**; `INPUT_VERIFY_PYRIGHT_EXIT=0`.
- Native LSP reported no diagnostics for all six Python files individually:
  `prepare.py`, `test_prepare.py`, `runner.py`, `test_runner.py`, `split.py`,
  `test_split.py`. The directory-level LSP call auto-selected JSON and scanned
  seven JSON files, so it was not treated as a Python-project check. No
  Pyright/LSP discrepancy was found.
- Current hashes: `prepare.py`
  `16054c56d643db7e6046b0e2ef1789bf3a12172d239a064c0ecf837c5e35c7c3`;
  `test_prepare.py`
  `eee66167966783395234a7c03a699b418982421e1c9797f2a2aeb95316851b5d`;
  `PROTOCOL.md`
  `ce5428274c66d0047cfaa2448c7f7e42db1f606b61bb3a2b91d418a27164c2ac`;
  `UNKNOWN_NODE.md`
  `247966c8e0ac8df821ba2c1f8a11c9582cfd5f160aaa716b269330e76175a086`;
  `runner.py`
  `afa7abc2baec4f0fbd5548cf4517ee1e865fef554535774954d2ad7f8856ad07`.
  Runner `source_hashes()` includes `PROTOCOL.md`.
- Rechecked saved split SHA-256:
  `3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2`;
  original split:
  `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`;
  stage1 manifest:
  `7f1c7de45db8e36726279a2ba879823c360755718a29600b7999226b6e004d72`;
  stage1 conversion source:
  `46436d014378babea7a430ed5f677399bbc751d5ee0ac0ec34044a3ea109a719`.
  Reused prior fitting-free evidence records 72 metadata and 144 stage1
  member hashes matched and rechecked unchanged. No protected/raw observations
  were read in this verification.

The older records below preserve split recovery, producer failures and the
pre-authorization unknown-node stop. They are historical evidence and do not
supersede this latest verdict.

## Historical verdict: FAIL — do not start real learning

At the time of the earlier report, complete72 preparation had not finished and
preflight stopped on validation case `re2ob_checkoutservice_loss_3` containing
`frontend-check`. That stop predates the now-approved exact-name exclusion and
is not the latest reason for FAIL.

The older “split missing” incident is retained below as history only. It is
not the current status.

## Earlier producer records (before current role-policy recovery)

| Item | Historical evidence |
|---|---|
| `split.json` | Present; SHA-256 `3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2`. |
| New input `artifacts/input.json`, `artifacts/bundle.npz` | Both absent (direct read returned ENOENT). Thus no actual bundle shape/hash is available. |
| Complete preparation | Not complete. `KNOWN_INPUTS_PASS` was never emitted. |
| Old-policy final preflight | PID 1513567, stage `preflight`, actual exit 1, `KNOWN_INPUTS_STOP`; error names the then-unapproved validation-only node. Elapsed 1.672148s. Exclusive evidence: `artifacts/node-conflict-1513567.json` and `artifacts/failure-1513567.json`. |
| Earlier full prepare attempt | PID 1512307, actual exit 1 after 1.322430s, same policy stop before template fitting; `artifacts/failure-1512307.json`. |
| Earlier attempt | PID 1511394, actual exit 1 after 0.035659s on a runtime-codec readguard issue; that guard was narrowed to interpreter runtime files only. |
| Split producer | Reuse the existing actual record in `SPLIT.md`: monitor `mon_RP477XAM1S1HM5WE`, `KNOWN_SPLIT_PASS`, exit 0. No split producer was rerun. |

That old-policy preflight stopped before template fitting, Hawkes fitting, or final
bundle creation. No real model fit, production runner check/inference, producer
rerun, install, protected-case read, or protected/raw telemetry read was done
in this verification.

## Split, permitted source, and provenance

The split handoff and saved split were inspected. The saved split has 72
development cases, TRAIN48 / validation24, and 18 protected names. All 24
service-fault groups allocate 2 TRAIN / 1 validation; selected validation
repetition counts are 12 / 9 / 3. The source development case set and fixed
assignment rule match the original split; protected18 are excluded. Original
split SHA-256 remains
`1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`.

I relied on the persisted final-preflight evidence for the allowed stage1
source/member audit: 72 metadata hashes and 144 numeric/log member hashes
matched their manifest entries and were rechecked unchanged; fitting-free
status was `PASS_UNSCALED_ONLY` / `PASS_UNSCALED_CASE`; original partition and
case identity provenance were checked. The recorded stage1 manifest SHA-256
is `7f1c7de45db8e36726279a2ba879823c360755718a29600b7999226b6e004d72`;
conversion source SHA-256 is
`46436d014378babea7a430ed5f677399bbc751d5ee0ac0ec34044a3ea109a719`.
Original source files were read-only; final preflight evidence reports all
stage1 hashes unchanged. The original split and stage1 source hashes match the
recorded references.

The deterministic split and metadata establish the requested group counts.
The preflight read the permitted stage1 window starts and recorded all72 case
intervals: zero cross-partition overlaps, zero within-case interval overlaps,
and zero cross-partition raw/stage1 file-hash duplicates. Each case's windows
stay in one partition. The split handoff separately notes that metadata alone
does not contain absolute intervals; interval evidence comes from the allowed
stage1 temporal members read by the producer preflight, not from metadata
alone.

The preflight reports 6,817 TRAIN / 3,456 validation windows. Corresponding
stage1 nominal counts are TRAIN 3,456 normal / 3,361 fault and validation
1,728 normal / 1,728 fault. These are source/preflight counts—not counts
independently observed in a delivered bundle, because no bundle exists.

Preflight recorded 14 TRAIN candidate identifiers after excluding the
predeclared four proxies:
`adservice`, `cartservice`, `checkoutservice`, `currencyservice`,
`emailservice`, `frontend`, `frontend-external`, `frontendservice`,
`istio-init`, `paymentservice`, `productcatalogservice`,
`recommendationservice`, `redis`, `shippingservice`. This inventory is not
restricted to the five gold roots. Validation's additional identifier
`frontend-check` occurs in exactly
`re2ob_checkoutservice_loss_3`; it is not an evidenced alias. The updated
policy and stage1 recount report this exact node in 144 windows, with 544
observed metric cells across 28 windows (memory 272 cells, all 2,854,912;
socket 272 cells, all 0; other six families 0), zero owned trace observations,
zero log rows named `frontend-check`, and zero observed edges involving it.
All 176,950 log rows in that case remain. These are permitted stage1
accounting values, not final bundle counts. No final input inventory, edge
array, or label alignment was delivered.

Earlier `prepare.py` and `test_prepare.py` hashes are superseded by the latest
hashes above. The preserved old-policy preflight conflict evidence SHA-256 is
`fa2ab04710e0fd89669eb0a481f3a930fb49cd13ebeec465ce527170b7239613`.

## Preparation rules and remaining readiness gap

The audited source/protocol contract specifies TRAIN-only Drain templates and
TRAIN-only runner metric/trace imputation and normalization; the metric mask
is for imputation/unsupported-channel accounting, not a model feature.
Unknown templates use bin 0. All observed TRAIN candidates are retained (not
only the five gold roots). Edges are `[E,2]` integer node pairs with each
self-loop; actual edges were not produced.

The relative Hawkes input is window-relative, constrained to the 10-second
window with the documented decay 3 and seed 42 fitting convention. The
production preflight recorded **0** template fits and **0** Hawkes fits, so
production warning/iteration counts and runtime/cost are **not measured**;
zero here does not mean successful convergence or zero warnings from fits.
No templates, Hawkes features, TRAIN scaler/statistics, or actual
validation-mutation check on real preparation were produced.

Current fixtures cover TRAIN-only metric statistics, unsupported-channel
masking, validation mutations leaving TRAIN statistics/data unchanged,
frozen templates despite validation-only messages, unknown-template bin,
relative-time knots, and synthetic cache equivalence. They establish fixture
behavior only, not producer readiness on actual observations.

## Runner protocol inspected (not run on production inputs)

`RUNNER.md`, `PROTOCOL.md`, `runner.py`, and `test_runner.py` were inspected.
The fixed run contract is seeds **11, 23, 37**, exactly **200 epochs** per fit,
fixed runner configuration, no auto-extension. Validation joint loss is
computed over all validation windows together; strict minimum selects the
checkpoint and exact ties keep the earliest epoch. Primary rank metrics are
case-equal over fault windows; normal windows are excluded from root ranking.
After approval, each seed's best and final checkpoint on TRAIN and validation
produce 3 × 2 × 2 = **12** prediction bundles total, with separate-process
replay verification. None of these production selections/predictions/replays
has occurred.

## Earlier required-check record (superseded by latest checks above)

Ran the exact requested unittest command:

```sh
cd /home/gnho1236/r2 &&
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m unittest discover -v \
  -s research/re2_ob_known_condition_20261018 -p 'test_*.py'
```

Earlier monitored result: **25 tests, OK, exit 0**
(`INPUT_VERIFY_TEST_EXIT=0`). This suite's synthetic-only tests did perform a
small native Hawkes fixture fit (11 iterations, 0 warnings), a 200-epoch
synthetic fit, and separate synthetic checkpoint replay. Synthetic child
processes exited 0: fit PID 1517872 emitted `RE2_OB_FIT_COMPLETE` and
`SYNTHETIC_PROCESS_PASS`; replay PID 1518062 emitted `RE2_OB_VERIFY_PASS` and
`SYNTHETIC_PROCESS_PASS`. All used temporary synthetic inputs, not production
data or checkpoints. This was the behavior of the explicitly required full
test command; no production fit or inference was run.

Ran the requested project diagnostics:

```sh
/home/gnho1236/.local/bin/pyright --project \
  /home/gnho1236/r2/research/re2_ob_known_condition_20261018
```

Earlier monitored result: **0 errors, 0 warnings, 0 informations, exit 0**
(`INPUT_VERIFY_PYRIGHT_EXIT=0`). Native LSP diagnostics on the project also
reported no diagnostics. The newest exact commands/results and individual
Python-file LSP checks are at the top of this report.

## Historical initial failure (preserved)

The initial verification attempt recorded `split.json` missing (probe PID
1491467, exit 2) and therefore FAIL. That prerequisite was later repaired by
the split owner. Its successful split evidence is cited above. The initial
missing-split result is history, not the current reason for FAIL.

## End state, exact current shapes, and gated next commands

No actual bundle exists, so no actual bundle shapes, candidate/edge arrays, or
event count can be reported. Contract/verified stage1 counts only:

- Split: 72 cases = TRAIN48 / validation24 / protected18; 24 groups each
  allocate 2/1, chosen validation repetitions 12/9/3; all windows of a case
  stay in one partition.
- Stage1 source counts: TRAIN 6,817 windows (3,456 normal / 3,361 fault);
  validation 3,456 windows (1,728 normal / 1,728 fault); 10,273 total.
- Candidate inventory recorded by the prior preflight has 14 nodes:
  `adservice`, `cartservice`, `checkoutservice`, `currencyservice`,
  `emailservice`, `frontend`, `frontend-external`, `frontendservice`,
  `istio-init`, `paymentservice`, `productcatalogservice`,
  `recommendationservice`, `redis`, `shippingservice`. This is not restricted
  to five gold roots. Exact `frontend-check` is excluded; no final bundle
  inventory or edges were delivered.
- If produced, required arrays have `metrics [N,S,10,8] float32` and same-shape
  bool mask, `traces [N,S,10,2] float32`, `logs [N,S,E] float32`,
  `labels/case_ids/starts/partition/indices [N]`, and `edge_pairs [K,2] int64`.
  Current N/S/E/K values in the bundle are **unavailable**; 10,273/14 are
  stage1/protocol-based expectations, not observed bundle dimensions.
- TRAIN-only templates/statistics, mask-as-imputation metadata (not a model
  feature), unknown-template bin 0, role-exclusion counts, and final candidate
  array were not produced. Fixtures verify TRAIN-stat mutation invariance,
  unknown-template handling and role filtering. Actual policy application
  across all72 cases remains unverified.
- Production template/Hawkes fits: 0 completed in the last historical
  preflight. Production warnings and iteration-limit counts are **not
  measured**, not zero-fit warning outcomes. Full cost/runtime is **not
  measured**; no completed profile or full preparation is present.
- Last historical preflight readguard record: 1,199 allowed opens, 0 denied,
  0 protected-case opens, 0 raw-case opens, 0 old-state opens. This is not a
  fresh audit under the updated role policy.
- Historical exact producer records remain: split PID/monitor evidence in
  `SPLIT.md` (`KNOWN_SPLIT_PASS`, exit 0); old-policy preflight PID 1513567
  (`KNOWN_INPUTS_STOP`, exit 1); earlier producer failures PIDs 1512307 and
  1511394 (exit 1). No current preparation exit 0/sentinel exists.

The following are fixed runner commands only, not permission to begin. First
the input owner must produce the complete bundle and exact successful
producer-exit/sentinel record; then this verification must be rerun and PASS.
Only after that approval may `runner check` and the serial seed commands run.
No stage auto-starts.

```sh
cd /home/gnho1236/r2
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner check
```

Only after the gate passes, run each fit and then its separate-process verify:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner fit --seed 11
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner verify --seed 11
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner fit --seed 23
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner verify --seed 23
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner fit --seed 37
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner verify --seed 37
```

Constraints: exactly seeds 11/23/37 and 200 epochs; CPU, two threads per
process, at most three concurrent seed processes; retain actual exit codes,
warnings, PIDs, and sentinels; verify only after that seed's fit exits 0;
preserve exclusive-created run folders; timeout is not convergence failure;
never read/evaluate protected18. Readiness remains **FAIL** until complete
input artifacts and current successful producer evidence exist.
