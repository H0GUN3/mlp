# Guarded destination-only input preparation

2026-10-18. **PASS: finite prepared tensor published after real producer exit0.**
Only prepare.py, test_prepare.py, inputs/* and this document belong to this task.
Runner, evaluation, training and existing artifacts are outside this task.

## Fixed mechanism

1. Check safe selected/metadata hashes against the prior PASS preparation;
   check native metadata/parser hashes against safe provenance and all four
   spans.json hashes against native metadata. Never open old/full raw.npz.
2. Stream the four shared arrays through existing native_data_profile.json_array.
   Route original start-second +28800 first. Only TRAIN316 spans may contribute
   operation/duration/service/identity/reference interpretation in pass one.
3. Exact direct CHILD_OF joins require both endpoints to be selected TRAIN.
   Deduplicate evidence identities only. Fail conflicting selected identities,
   nonsingleton targets or missing TRAIN compose_media_client → media support.
4. Exclusively create inputs/mapping.json and compute its SHA-256 before
   any pass-two or validation-tensor loading. Reopen the frozen map for use.
5. Process only allowed394 observations in pass two. Aggregate every occurrence
   into both owner baseline and destination treatment with its original duration
   and original second. Preserve float64 addition order, mean and zero-fill.
6. Require elementwise EXACT owner equality with all394 safe cached trace rows;
   preserve other arrays, positions/windows/services/edges/counts and original
   split ordering; require exact per-second count and integer-microsecond sums,
   finite tensors and channel1=0. No normalization or fitting.
7. Producer writes only pending verification. Supervisor records its actual
   exit code, rechecks hashes and publishes preparation.json PASS only after0.
   Exclusive outputs/claim prevent completed producer retries and tensor
   overwrites. The one failed source-member gate can resume only before any
   tensor exists and with the original mapping hash unchanged.

## Access boundary

Both passes structurally decode the whole shared JSON, including primitive
values, and interpret every span startTime for routing. TRAIN-only/allowed394
guards precede numerical observation interpretation. Protected numerical model
rows materialized:0. This does **not** mean no protected raw bytes were decoded.
Gold-root labels are copied, not used to derive or disambiguate the mapping.
Validation112 is explicitly excluded from dictionary support.

## Initial issues retained

- Initial workspace inspection reported that /home/gnho1236/r2 is not a Git
  repository. No Git operation modified any file.
- Two initial metadata inspection attempts could not parse tool-truncated JSON;
  field-focused reads replaced them. No producer or source mutation occurred.
- First LSP pass: prepare.py clean; test_prepare.py had unresolved local import
  and overly narrow mixed-array dictionary inference. The dictionary was fixed;
  tests use package-relative import and namespace-module unittest execution.
- Directory LSP also surfaced parent-owned test_evaluate.py and runner.py import
  errors. Those files were not changed; preparation-only diagnostic results and
  actual fixture/runtime evidence will be recorded below.

## Execution evidence

Working directory for all commands: /home/gnho1236/r2.

Pre-producer commands (completed, exit0):

```sh
pyright --project research/sn_call_target_contrast_20261018/inputs/pyright.json
.venv-eadro/bin/python -B research/sn_call_target_contrast_20261018/prepare.py --fixtures
```

Explicit Python3.8/.venv-eadro Pyright configuration: **0 errors, 0 warnings,
0 informations**. The general workspace LSP was called before execution; its
package-root resolution limitations are preserved above, not suppressed.
Nine synthetic unittest fixtures passed in0.181s, with actual fixture exit0
recorded by the fixture supervisor. Exact join, both TRAIN-boundary directions,
ambiguity/conflict rejection, fallback, duplicate weighting, timing/zero channel,
unchanged arrays/exact-baseline rejection, exclusive/hash-frozen media support,
and reuse of the original streaming parser were exercised.

Fixture log SHA-256:
`3c38bbe0b4eec3c49e13c5587934c5f7a8c28460f0cf7b19cece3d89833796f4`.
Fixture record: inputs/fixtures.json. No fixture accesses source dataset spans.

Initial guarded execution command (monitored; exit1, retained):

```sh
.venv-eadro/bin/python -B research/sn_call_target_contrast_20261018/prepare.py --execute
```

Its producer command was:

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_call_target_contrast_20261018/prepare.py --produce
```

The producer completed the TRAIN pass and froze11 singleton keys, then failed
before reading numerical source tensor members: safe selected.npz contains the
expected five arrays **plus log_absolute**. The implementation incorrectly
required exactly five source members. This was an implementation guard error,
not a source-hash, baseline-value or tolerance mismatch. The final output still
must have exactly five members. log_absolute is neither loaded nor output.

Initial log, exit1, claim, fixture results and preparation.failure.json remain
untouched. The dictionary was not redrawn, edited or overwritten. Its original
SHA-256 remains:
`6974f58562f6a2723b10cc7f9d7767d3053da729a9a2d2feb0c2f1b3cf7f4169`.

Recovery validation (completed, exit0): preparation-only Pyright again reports
0 errors/warnings/informations;10 fixtures passed in0.180s, including a new
archive-member trap proving the unused absolute arm is never loaded.
Recovery LSP prepare.py is clean; the general-workspace test package-root
resolution diagnostic remains distinct from the passing explicit project check.

```sh
pyright --project research/sn_call_target_contrast_20261018/inputs/pyright.json
.venv-eadro/bin/python -B research/sn_call_target_contrast_20261018/prepare.py --fixtures-recovery
.venv-eadro/bin/python -B research/sn_call_target_contrast_20261018/prepare.py --resume-failed
```

The last command completed through monitor with **exit0**; its only continuation
producer process used `--produce-resume` and also exited0. It accepts only the specifically identified failed member
gate, verifies all original mapping/data hashes, retains mapping.json byte for
byte, and starts the still-unexecuted allowed394 aggregation. A completed
producer cannot be retried. This is one frozen treatment and one full aggregation,
with an initial failed process explicitly preserved, not a claim of one process.

The initial failure preceded monotonic cost-manifest publication. Its mapping
stage and failed-attempt costs therefore use actual filesystem nanosecond
wall-clock intervals from execution.claim.json to closed mapping.json and
producer.exit.json. Mapping-stage cost includes initial source hash checks.
The resumed aggregation uses perf_counter. Total active preparation cost sums
the failed-attempt interval and resumed producer time; it excludes coding/repair
idle time and is not a clean uninterrupted-run timing.

## Final acceptance and costs

Actual continuation producer command (exit0):

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/sn_call_target_contrast_20261018/prepare.py --produce-resume
```

Producer sentinel in inputs/recovery.producer.log:
`PREPARATION_PRODUCER_VERIFIED`.
Supervisor sentinel, observed with monitor exit0:
`PREPARATION_PASS producer_exit_code=0`.
Actual child exit evidence: inputs/recovery.producer.exit.json.
Canonical final interface: **inputs/preparation.json**, status PASS,
strategy `train_linked_destination_only`, producer_exit_code0.
The earlier inputs/preparation.failure.json remains evidence of the first
exit1, not the canonical final status.

- Shape `(394,12,10,2)`, float64, finite, no normalized arrays, channel1 all zero.
- Owner baseline recomputed alongside candidate: elementwise **EXACT** equality
  against all394 safe trace rows, including every zero/channel; no tolerance.
- Metrics, relative-horizon10 logs, labels, indices: dtype and elementwise exact.
- Metadata positions/order/windows/services/edges/counts preserved. Current
  strategy is destination-only; old horizon-only description is explicitly
  nested under inherited preparation provenance, not the current treatment.
- All394,075 allowed span occurrences retained once each; repeated identity
  occurrences remain weighted. Counts and original integer-microsecond duration
  sums across services match exactly for every original row/second.
- Mean and zero-fill rules unchanged; candidate saved-array roundtrip exact.
- Input source hashes verified before/after and again after producer exit.
- Conflicting selected identities0; ambiguous linked keys0. The corresponding
  presence flags in checks are false; required positive acceptance flags are true.
- Protected numerical model rows materialized0.

| Cost | Seconds | Measurement |
|---|---:|---|
| Mapping stage | 17.858115758 | Initial filesystem wall-clock interval, includes source checks |
| First failed attempt | 17.981123444 | Initial filesystem wall-clock interval |
| Allowed394 aggregation and checks | 21.718859743 | Resumed producer perf_counter |
| Resumed producer total | 27.097920351 | perf_counter, includes rechecks/publication |
| Total active preparation | 45.079040871 | Failed-attempt interval + resumed producer |

No mapping stage was rerun. One full allowed394 aggregation completed.
Supervisor post-exit rehash time is not included in producer cost.

## Frozen dictionary and coverage

Eleven singleton TRAIN keys;6,622 deduplicated direct cross-service linkage
evidence pairs. Required media key has **602 TRAIN evidence pairs**.
Validation112 and all other validation observations supply **zero dictionary
support**. Validation linkage below is a post-freeze audit only.

| Accounting | TRAIN316 | validation78 |
|---|---:|---:|
| All feature occurrences | 315,780 | 78,295 |
| Client-suffix occurrences | 155,584 | 38,902 |
| Mapped/moved client occurrences | 79,959 | 20,307 |
| Unmapped client owner fallback | 75,625 | 18,595 |
| Nonclient owner fallback | 160,196 | 39,393 |
| Repeated identity occurrences retained | 259,105 | 64,574 |
| Affected destination node/second bins | 6,125 | 1,571 |
| Deduplicated direct cross-service linkage pairs | 6,622 | 1,675 |
| Unmatched CHILD_OF parent references in same split | 252 | 35 |
| Ambiguous linked keys | 0 | 0 |

Unmatched means the exact parent was absent from the admitted same-split
identity set; protected/other-split parents are not opened to resolve it.
Evidence counts deduplicate identity pairs; moved feature counts below **do not**.

| Owner | Exact operation | Target | TRAIN evidence | TRAIN moved | val moved |
|---|---|---|---:|---:|---:|
| compose-post-service | compose_creator_client | user-service | 605 | 7,254 | 1,848 |
| compose-post-service | compose_media_client | media-service | 602 | 7,266 | 1,848 |
| compose-post-service | compose_text_client | text-service | 601 | 7,254 | 1,848 |
| compose-post-service | compose_unique_id_client | unique-id-service | 593 | 7,254 | 1,848 |
| compose-post-service | store_post_client | post-storage-service | 604 | 7,310 | 1,849 |
| compose-post-service | write_home_timeline_client | home-timeline-service | 604 | 7,298 | 1,849 |
| compose-post-service | write_user_timeline_client | user-timeline-service | 605 | 7,310 | 1,849 |
| home-timeline-service | get_followers_client | social-graph-service | 612 | 7,311 | 1,872 |
| nginx-web-server | compose_post_client | compose-post-service | 595 | 7,166 | 1,848 |
| text-service | compose_urls_client | url-shorten-service | 595 | 7,268 | 1,824 |
| text-service | compose_user_mentions_client | user-mention-service | 606 | 7,268 | 1,824 |

Each listed owner→target pair has one admitted exact operation here, so these
are also all moved-owner→target counts. Every unresolved client key, its split
counts and fallback destination are retained in
preparation.json.mapping_coverage.{TRAIN,validation}.by_key; no unknown target
is guessed. Every direct TRAIN evidence pair, endpoint original index and
timestamp is in mapping.json.

## SHA-256

| Artifact | SHA-256 |
|---|---|
| PROTOCOL.md | `767b0d2e628d13411742851ad5886a15b503d9aabe98d761e94cec39b5bbe541` |
| BASELINE.json | `29d610a21e0f80026bf2617ee7978267b0db2b94b597a43a48117a81edd08eee` |
| Safe source selected.npz | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| New inputs/selected.npz | `5c9dba4a13d97ac74632df0ef04c6885f2e3da8caab1cfd7f9b68147dbe7caa2` |
| New inputs/metadata.json | `bf2ac9c890017c4cf5014b077211187e589b000630e71ab00c38dfb82e52ada0` |
| Frozen inputs/mapping.json | `6974f58562f6a2723b10cc7f9d7767d3053da729a9a2d2feb0c2f1b3cf7f4169` |
| Final prepare.py | `3632ce2f2281acf26f43a3471fcc3e6e0071ba1b45717b584ced6cf5cfb20e31` |
| Final test_prepare.py | `317327e3b25a9d40aa3f846f9557e429da175de0ae534dc193ddfce6c7b5b7b5` |
| Recovery fixture log | `5dbaad59269027bb69e462fbd6183aba3cbc4fe1308b557f3f562f74654ebcf2` |
| Initial failed producer log | `c6c616ae57a1712c6ee1f155e62751ebc5c62b8961abbab6eb66ae381d24972d` |

All per-file source hashes, including the safe metadata/preparation, native
metadata/parser, original split and four raw recordings, are in
preparation.json.input_hashes and input_hashes_after. The mapping retains
original pre-failure implementation hashes; initial_failure records those and
the failed log hash, while code_hashes records the final implementation.

## Scope and limits

No child agents, installs, training, neural inference, Hawkes/Drain fitting,
other datasets, old full raw.npz reads, source edits or runner/report edits.
No scaler was fitted: parent runner must retain the same TRAIN-only scaler
policy. Exact metadata/source hash checks and fixtures establish preparation,
not diagnostic accuracy or that an unpaired client actually reached its target.
The mapping is a TRAIN-supported instrumentation association; client duration
remains caller-observed elapsed time, not callee-internal processing time.
