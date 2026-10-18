# RCAEval native input/label contract — 2026-10-13

## Verdict

**VERIFIED:** Full metric sequences, logs and spans exist for the SAME three validation incidents. An encoder-preserving, domain-adapted input port is feasible.

**UNKNOWN:** Exact fault-active window labels. The release supplies an injection boundary, not verified activation and termination intervals. Consequently, a faithful native Eadro/DiagMLP joint detection/localization reproduction is **not established**; do not label every post-boundary window faulty as independently verified ground truth.

## Evidence boundary

Paths below are relative to `/home/gnho1236/r2`. Read `SOURCES.md`, `research/native_reproduction_20261013/{error_analysis.md,CALIBRATION_PROTOCOL.md,fidelity_audit.md}`, relevant `scripts/`, and `research/mlp_prerequisites/{PROTOCOL.md,CANDIDATE_CONTRACT.md,split.json,split.lock.json}`. Inspected `data/rcaeval/cases.parquet` metadata/index only; verified split SHA256 `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5` and train108/validation36/test36 counts.

Before opening any case file, confirmed all `re2tt_ts-train-service_delay_{1,2,3}` rows have `partition=validation`. Case access was limited to their injection text, Parquet schemas/footer timestamp ranges, and service-identifier columns; no metric values, log messages, span durations, features or predictions were read. No final36 case files were opened. No training, implementation or installation occurred.

## Time and label semantics

**VERIFIED — release convention.** The pinned [dataset card][R] calls `inject_time` a “unix timestamp of injection” and states that `inject_time.txt` separates normal-before/faulty-after. `scripts/mlp_readiness.py:extract_features` implements `< injection` versus `>= injection`; `scripts/audit.py:rcaeval` computes `fault_rows` identically. These comparisons implement a convention, not measurements of fault persistence.

Actual index fields are `inject_time:int64`, `time_start:int64`, `time_end:int64`, `duration_minutes:double`, `normal_timesteps:int64`, `faulty_timesteps:int64`; **no fault-end/duration or activation-status field exists**. The card explicitly defines `duration_minutes` as metric coverage and counts as rows before/after injection.

| Validation suffix | inject_time | metric coverage |
|---|---:|---|
| delay_1 | 1705944092 | 1705943372–1705944812 |
| delay_2 | 1706123446 | 1706122726–1706124166 |
| delay_3 | 1706124991 | 1706124271–1706125711 |

Each index row has 1,441 samples, 720 before/721 after, and 24-minute coverage. **Neither 24 minutes nor 721 post-boundary rows is a fault duration.** Their pinned file inventory (`evidence/rcaeval-tree.json`) contains only metrics/logs/traces and injection text, with no interval manifest.

**UNKNOWN — activation versus request.** [RCAEval §3.3][P] describes normal collection followed by injection and abnormal collection; §3.2 identifies stress-ng/resource faults and tc/network faults. Neither specifies when the timestamp is written relative to request, successful application or actual activation. Thus `inject_time` cannot be certified as actual activation, but cannot be asserted to be request time either.

**UNKNOWN — end/recovery.** No release-linked collector/injector revision was identified in the inspected [WWW25 source tree][T] or current tree (`259ea4167160256a74ad30004aa3d96a998c846e`). Public [issue #67][I] requests injection scripts; its inspected comment is another request, not an author-provided procedure. This is an evidence gap, not proof that scripts never existed. Timeout, cleanup, restart and recovery remain unverified; the case root/type alone cannot establish persistence.

**VERIFIED — native distinction.** Eadro `parse_raw_records.py:52–53` reads explicit `fault['start']` and `fault['duration']`, forming integer endpoints. `align.py:get_basic:18–32` consumes those intervals, initializes labels to `-1`, and assigns service node IDs on overlap (default threshold 1). RCAEval lacks that corresponding interval evidence. The pinned [preprocessing source][E] is a public repair fork, not the untouched original artifact.

## Usable native input contract

Use immutable, full 10-second, stride-10 windows with recording/case/time provenance; retain the frozen incident partitions, never re-split windows across them.

**VERIFIED — available schema:**

* Metrics: Unix-second `time:int64`, double `{service}_{family}` sequences. The three schemas contain 371/358/358 channels over 68 metric-node identities; available families are `cpu,mem,diskio,socket,workload,error,latency-50,latency-90`. Train/travel have eight channels in delay_1, seven in delay_2/3: missing `error` is **unknown, not zero errors**. Preserve missingness; freeze channel order and train-only normalization/imputation.
* Logs: `timestamp:int64` (second-scale footer ranges), `container_name`, `message`. Use timed messages→Drain templates/unseen bin→Hawkes baseline vector `[N,E]`, not log-count summaries. Integer timestamps limit available timing precision; native `deal_logs` handles ties explicitly.
* Spans: `time`, `traceID`, `spanID`, `serviceName`, `methodName`, `operationName`, `parentSpanID`, `startTimeMillis`, `startTime`, `duration`, `statusCode`. Footer ranges support millisecond/microsecond start coordinates; `error_analysis.md` previously checked their agreement. Native `parse_raw_traces.py` converts Jaeger microsecond durations to seconds; RCA conversion units still require provenance verification. `deal_traces` builds per-service mean-duration/second `[N,10,2]`, second channel zero—not pooled incident medians or added invocation counts.

Native metrics use `[N,10,M]`. Eadro's seven channels (`util.py:46`) are CPU system/total/user, memory usage/working-set, rx/tx bytes, **not** RCA's eight families. `MetricModel` accepts `metric_num` (`model.py:118–136`): changing M/file adapters is ordinary domain configuration, not replacing the TCN/attention encoder. It does not recover missing original channels. Keep Hawkes→LogModel and temporal TraceModel; the previous 17-feature summaries replace these inputs and are not native.

Canonical names here are `ts-train-service`/`ts-travel-service`, not shorthand train/travel. Freeze one cross-modality candidate order. Eadro TT `Info` has 27 application nodes (train21/travel23); the local common adapter has a different vocabulary (57/60). Reconcile RCA databases/infrastructure and documented proxy exclusions explicitly; do not silently reuse indices or assume identical TT deployments/static edges.

## Exact missing contract / stop

Needed per incident: verified successful activation A, termination E (or evidence it remains active through recording end), affected service/instance, release-linked collector revision, timestamp coordinate/rounding, and whether labels mean injection-active or symptomatic failure—including recovery/normal-period guarantees.

Then freeze an interval-overlap policy for `-1`/nodeID labels; disclose corrections to Eadro's endpoint-overlap bug. Until then, pre-onset windows are only **nominal** normal under [R], post-onset labels remain **UNKNOWN** for exact fidelity; never select strongest-anomaly windows.

Preserve native detection target `label>-1`, root CE ignoring `-1`, and weighted joint loss ([`model.py:212–233`][M]), not root-only classification. [DiagMLP][D] preserves encoders/tasks while replacing graph fusion; exact unpublished integration remains a separate limitation recorded in `fidelity_audit.md`. Unrelated Eadro incidents cannot establish persistence of the RCA error. No model result is proposed.

[R]: https://huggingface.co/datasets/phamquiluan/RCAEval/blob/afeacb11bcc94dadfd1c8f483ee4377b2b8b614e/README.md
[P]: https://arxiv.org/html/2412.17015v4#S3.SS3
[T]: https://github.com/phamquiluan/RCAEval/tree/9d14687ce0644188f1f1a576fd3f57cd903af446
[I]: https://github.com/phamquiluan/RCAEval/issues/67
[E]: https://github.com/FeiGSSS/Eadro/tree/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess
[M]: https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/model.py#L118-L247
[D]: https://arxiv.org/html/2501.02766v2#S4
