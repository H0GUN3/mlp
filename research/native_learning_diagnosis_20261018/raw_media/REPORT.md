# Native SN media: six-window raw-observation diagnosis

## Finding

The clearest operation-specific duration signal is **compose-post-service's
`compose_media_client`**, not a large media-service server duration. Native
preprocessing attributes spans to their owning service, averages **all
occurrences and operations per second**, and fills unobserved seconds with zero.
Consequently, a media call's long client span enters compose's latency feature;
media's own latency can remain tiny or zero-filled.

- **Index115:** `compose_media_client` lasts **6.008163s**, with12
  duplicate-weighted occurrences. Media itself has **no in-window span or log**.
  Native compose trace has just one observed bin, offset7, whose input value is
  **2.4068048s**, not6.008163s. That bin mixes60 occurrences:12 each of
  media-client6008163μs, compose-server6024359μs, text-client917μs,
  unique-ID-client310μs, and creator-client275μs.
  The exact integer duration sum is144408288μs across60 occurrences.
- **Index112:** media's observed server duration is **12μs**, whereas
  compose's media-client mean is **5.997269s** (24 occurrences).

`native_data.trace_series` does not retain `operationName` or per-span callee/
target identity in its latency output: it groups by **emitting service and start
second**, mixing client and server spans. This is verified **representation
attribution and information loss**, not proof that the model used this channel,
that it caused an error/correction, or that it explains SN-versus-TT learning
speed. The static service graph is a separate input; no claim is made that all
topology is absent.

All statements concern **span start times inside these windows**. An unobserved
root span is not proof of a missing/outage request or a zero-duration request;
no outside-window spans were joined to complete the client/server picture.

Media and text emit **zero raw log lines in all six windows**; their frozen
baseline Hawkes vectors are also all zero. The actual logs name social-graph,
home-timeline, compose-post, and user operations, not a media-specific fault.
No normal intervals were compared, so those messages are not characterized as
normal/background or fault-caused.

## Scope and clocks

Only original indices **112,115,120,129,133,136**, all original validation rows,
of `SN.2022-04-17T181245D2022-04-17T183616` were analyzed.
This is original native window-split SN, **not event-disjoint corrected SN**.
Root is media-service (node 6); text is node 7; compose is node 1.

All aligned times below are UTC on **2022-04-17**, with half-open 10-second bounds.
These are the producer's shifted timestamps, not unmodified source wall clocks.

| Original index | Fault | Aligned UTC interval | Aligned epoch `[start,end)` |
|---|---|---|---|
|112|fault07 network_delay|18:31:25–18:31:35|[1650220285,1650220295)|
|115|fault07 network_delay|18:31:55–18:32:05|[1650220315,1650220325)|
|120|fault07 network_delay|18:32:45–18:32:55|[1650220365,1650220375)|
|129|fault08 network_loss|18:34:15–18:34:25|[1650220455,1650220465)|
|133|fault08 network_loss|18:34:55–18:35:05|[1650220495,1650220505)|
|136|fault08 network_loss|18:35:25–18:35:35|[1650220525,1650220535)|

Routing follows `native_data.py` and the selected-only gates in
`tt_native_support_20261014/prepare.py`:
metric timestamp +57600 seconds; log source wall clock +28800 seconds;
span `startTime // 1000000 + 28800`.
Thus the source logs for index112 span 10:31:25–10:31:35; its metric source
timestamps span [1650162685,1650162695), and its span-start timestamps span
[1650191485000000,1650191495000000) microseconds.
The JSON artifact provides corresponding source bounds for every window.
Metadata labels fault07 [1650220261,1650220381] and fault08
[1650220424,1650220544], inclusive original rounded endpoints.

## Actual spans, including duplicate occurrence weights

Each service entry below is **occurrences / unique identities / observed
one-second bins**. Unique identities are descriptive only, never used as weights.

|Index|media|text|compose|media duration range μs|text duration range μs|
|---|---|---|---|---|---|
|112|24 / 2 / 2|72 / 6 / 2|156 / 13 / 3|12–12|222–621|
|115|0 / 0 / 0|36 / 3 / 1|60 / 5 / 1|unobserved|232–643|
|120|0 / 0 / 0|0 / 0 / 0|36 / 3 / 1|unobserved|unobserved|
|129|0 / 0 / 0|99 / 9 / 3|264 / 24 / 4|unobserved|209–1159|
|133|12 / 1 / 1|36 / 3 / 1|96 / 8 / 2|9–9|864–1216|
|136|24 / 2 / 2|72 / 6 / 2|192 / 16 / 2|6–12|228–1232|

Across all services in these windows: **4125 occurrences, 745 unique identities,
3380 repeated occurrences, zero selected identity conflicts**.
Examples: index129 text has counts 33 at offsets 1,3,7; bin means
918.333,354.333,331 μs. Index133 media has count12 at offset8 and mean9 μs;
text has count36 at offset8 and mean995.333 μs.
Zero-filled ten-bin means for text129/text133 are 160.367/99.533 μs; these
are not the observed-bin means (534.556/995.333 μs).
All per-bin counts/means, operation counts, and selected trace/span ID examples
are in `evidence.json`.

### Relevant competing service: compose-post-service

Operation-specific values below are occurrence-weighted raw duration means, μs.
Operations stay attributed to compose, not the callee.

|Index|compose_media_client count / mean / max|compose_text_client count / mean|compose_post_server mean|
|---|---|---|---|
|112|24 / 5997269 / 6003791|24 / 897|6014017|
|115|12 / 6008163 / 6008163|12 / 917|6024359|
|120|unobserved|unobserved|unobserved|
|129|33 / 286370.667 / 650571|33 / 1194|302567.333|
|133|12 / 413740 / 413740|12 / 2075|430258|
|136|24 / 103140 / 205987|24 / 1500.5|119715.5|

At index120, the only observed compose operations are store_post_client,
write_home_timeline_client, write_user_timeline_client: 12 occurrences each,
durations 838,3227,15536 μs. There is **no in-window media-call trace proof**
there. No spans beginning outside the allowed windows were inspected for
cross-boundary request completion.

These are same-window operation comparisons, **not explicitly paired
client/server request joins**. They locate the observed duration signal without
claiming an end-to-end network-cause decomposition.

## Actual logs and frozen templates

Counts are exact timestamp-masked text matches to the six already-frozen SN
templates; no Drain training or new Hawkes fitting was performed.

|Index|social T1/T2|compose T3|user T4/T5|home T6|media/text|
|---|---|---|---|---|---|
|112|5 / 9|4|5 / 5|4|0 / 0|
|115|5 / 9|4|5 / 5|4|0 / 0|
|120|5 / 8|3|5 / 5|3|0 / 0|
|129|11 / 20|9|11 / 11|9|0 / 0|
|133|9 / 17|8|9 / 9|8|0 / 0|
|136|9 / 17|8|9 / 9|8|0 / 0|

**284 selected lines**, all matching existing templates:
T1/T2 `SocialGraphHandler ... GetFollowees/GetFollowers ... ZADD: no key specified`;
T3 `ComposePostHandler ... Failed to write home timeline to home-timeline-service`;
T4/T5 `UserHandler ... User jack/aaa already existed`;
T6 `HomeTimelineHandler ... Failed to get followers from social-network-service`.

Raw selected examples:

```text
[2022-Apr-17 10:34:15.421400] <error>: (ComposePostHandler.h:353:_UploadHomeTimelineHelper) Failed to write home timeline to home-timeline-service
[2022-Apr-17 10:34:57.165276] <error>: (HomeTimelineHandler.h:96:WriteHomeTimeline) Failed to get followers from social-network-service
```

133 and136 have identical service/template **counts**, but not identical
timestamps/bin layouts or all Hawkes inputs. For example, compose T3 bin counts
are `[0,0,1,0,1,2,1,1,0,2]` versus `[1,1,1,1,2,0,1,1,0,0]`.
No conclusion about temporal log information's model contribution follows.

## Metric deviations under the original fixed SN scaler

No scaler was fitted. Used original DiagMLP seed11 `scaler.npz`, byte-identical
to seeds23/37, with `(raw - train_mean)/(train_std + 1e-8)`, no clipping.
All 5040 selected metric cells (6×12×10×7) exactly equal safe selected inputs.
Values below are media's signed window-mean z and maximum per-second z:

|Index|rx raw range|rx mean z / max z|tx raw range|tx mean z / max z|
|---|---|---|---|---|
|112|74–340|-0.323 / 0.069|0–423|-0.314 / 1.270|
|115|74–402|-0.306 / 0.270|0–169|-0.378 / -0.022|
|120|126–402|-0.308 / 0.270|37–211.5|-0.139 / 0.195|
|129|135–1015|0.644 / 2.250|51.5–280|-0.183 / 0.543|
|133|123–1280|0.858 / 3.106|60–909|0.390 / 3.742|
|136|74–474|-0.088 / 0.502|51.5–555|-0.127 / 1.942|

Media CPU and memory channels across these windows remain roughly
z=-0.124 to -0.073, not large positive deviations.
For the text-prediction errors129/133, text rx peaks are 1.583/1.806 z and tx
peaks 1.743/1.406 z; CPU/memory are about -0.22 to -0.14 z.
Thus text has more observed latency bins and larger server durations than media,
but this is **not** proof of greater training-relative anomaly or causal root.
Per-service operation mixtures differ.

Service-wide mean absolute metric z is also not root-specific: at129,
media/text/compose are 0.267/0.340/0.329; at133, 0.359/0.379/0.238.
The script retains complete metric details for media/text/compose and the
largest mean-|z| competitor in that same allowed window (user or user-timeline).
This statistic is descriptive, not a model score.

## Counterexamples to simple explanations

Transition facts here are supplied by the parent, not recomputed:

The parent's full native SN50→SN200 comparison found 12 newly correct outcomes
(10 delay,2 loss),1 newly wrong,8 persistent errors across195 seed-window
outcomes. This report's observations remain restricted to the six requested
windows; those totals are context, not additional raw-data analysis.

- 115 has **the same observed inputs** for seed37's correction and seed11's new
  error. Its media latency is zero-filled despite a 6.008s compose-media client
  span. Parent-verified root probability rises .16386→.68120 for seed37 but
  falls .49635→.29392 for seed11. Raw observability alone cannot explain the
  seed-dependent direction.
- 120 is corrected by seed37 with **no observed media or text spans and no
  media/text logs**. Direct in-window root-server trace evidence is not necessary
  for that reported correction.
- Persistent error133 has substantially larger media rx/tx peaks (3.106/3.742 z)
  than corrected136 (0.502/1.942 z). A stronger root metric spike does not
  monotonically track the reported transitions.
- Persistent112 still has two observed media server identities and ~6s media
  client calls under compose. Persistent129 has no observed media server span
  despite compose_media_client durations up to650571 μs.
- Equal template counts133/136 and zero root/text log features throughout do not
  establish that logs are irrelevant elsewhere in the service graph.

## Provenance, disclosure, and verification

Raw sources are exactly:
`/home/gnho1236/r2/data/eadro_native/SN_Dataset/SN Dataset/data/`
`SN.2022-04-17T181245D2022-04-17T183616/{metrics/*.csv,logs.json,spans.json}`.
**All 12 CSVs plus logs and spans (14 files)** match original metadata SHA256s.
Full hashes are in `evidence.json`; key hashes:

```text
media CSV c54842771cb170232e1f2c3d64fe3b68844141ca827fbad96c4b46f8b028d728
text CSV  d0944419bab10e5f55b6f2fb31733118d234424cdf5812d768aaf1839c20bd8d
logs      4031f36eb8e22b41ccdb5ece90571ad8291bcab4cdff76691e4e09d458094484
spans     9a839e839f216e9a7b0d5d58e4ab45aa3b208749ac4f537a98317b6c90cd534a
selected  6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc
scaler    b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1
metadata  d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4
```

**Shared bytes were read.** CSV records and string fields were parsed across
whole service files to route timestamps; only the720 selected service-second
rows had metric values numerically interpreted/retained.
`logs.json` was wholly parsed (including shared nonselected strings in memory),
and all10534 log timestamps routed; only284 selected contents were analyzed.
`spans.json` was wholly read and every trace object structurally JSON-decoded,
with all153785 span occurrence start timestamps routed; only4125 selected
durations/services/operations/identities were analyzed. This is not a
“no bytes read” or “no JSON decoding outside the windows” claim.
No full-recording observation distribution was computed.

Only six rows of metrics/traces/logs/labels were decoded from safe394
`selected.npz`; the remaining388 rows' decompressed numeric byte blocks were
discarded using existing `selective_loader.read_rows`. Original `raw.npz` was
never opened. Protected169+1 **numeric model-input rows and protected model
outputs** were not opened/decoded; this does **not** exclude reading protected-time
raw bytes or structurally decoding their shared JSON records during routing.
Original window metadata and split/indices are structural metadata.
The boundary counter is `scope.protected_model_input_rows_decoded=0`, explicitly
not a count of raw JSON records parsed.

Assertions passed: allowed validation membership; window boundaries;
all14 raw hashes;720 metric rows; **exact metric equality**;
**exact occurrence-weighted latency equality** (720 per-second values);
zero trace channel1; frozen selected/scaler hashes and same seed scalers.
Final script LSP diagnostics: **none**.

Executed direct command (first version, before adding operation summaries):

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/gnho1236/r2/.venv-eadro/bin/python -B /home/gnho1236/r2/research/native_learning_diagnosis_20261018/raw_media/diagnose.py
```

Monitor `mon_430HZ79VVMKDJR72`, `bash_4`: **exit0**; emitted exact-match
checks and counts above. Terminal output exceeded its retained tail.
Complete evidence was therefore captured with the following non-writing
transport command, also rerun after adding operation summaries:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/gnho1236/r2/.venv-eadro/bin/python -B -c 'import runpy,json,zlib,base64; d=runpy.run_path("/home/gnho1236/r2/research/native_learning_diagnosis_20261018/raw_media/diagnose.py"); print("EVIDENCE_ZLIB_BASE64="+base64.b64encode(zlib.compress(json.dumps(d["diagnose"](),sort_keys=True,allow_nan=False).encode())).decode())'
```

`mon_ANZQYR96DB8QFR7P`/`bash_5`: **exit0**.
Final `mon_4BM408FE74JFX06A`/`bash_7`: **exit0**.
Final output, after removing the new operation-summary fields, was exactly
equal to the earlier complete evidence object. The decoded outputs were saved
using `apply_patch`, not shell redirection or producer writes.
The default analysis kernel could not import the environment's pandas because
of a NumPy ABI mismatch; no raw processing occurred in that failed import.
Its actual error was `numpy.dtype size changed, may indicate binary
incompatibility. Expected 96 from C header, got 88 from PyObject`.
All actual raw evidence comes from the verified existing `.venv-eadro` runs.
Initial script diagnostics also reported unresolved static imports for
`native_data_profile` and `selective_loader`; those were fixed using existing
dynamic-import conventions, without suppressions, before the successful runs.
The workspace has no `.git` at its root, so attempted read-only git status
returned128; no git-based change-status guarantee is claimed.
Initial tool discovery also requested unavailable `glob` schema and returned
`schema() found no tool named "glob"`; subsequent supported discovery succeeded.

After these producer runs, the parent requested a metadata-only correction:
`protected_observation_rows_decoded` was renamed to
`protected_model_input_rows_decoded`, and the disclosure was clarified in both
the source and saved JSON. Numerical evidence and operation summaries were
reused unchanged. **No full producer rerun was performed for this wording
change**; the exit0 producer receipts above refer to the source before this
boundary-field/disclosure amendment. No computational logic changed.
Post-amendment LSP: no diagnostics. A metadata-only assertion passed checking
the new zero-valued model-input field, absence of the old field, and preservation
of the explicit whole-JSON parsing disclosure; it opened only `evidence.json`,
not original sources.

Final representation check read the complete current `evidence.json` and
`operation_durations.json`, without raw rescans. An initial exact equality check
on an independently regrouped floating-point mean failed:
2.4068047999999997 versus stored2.4068048 (difference -4.440892098500626e-16).
The subsequent exact checks passed for integer duration sum144408288μs,
count60, stored bin7 value2.4068048, media-client6008163μs/count12,
root span/log counts0, and index112 client5997269μs/server12μs.
The original producer's raw-to-native **exact array equality** receipts remain
unchanged; no test was skipped or producer logic altered.

Artifacts, all newly created only under this directory:
`diagnose.py` (read-only stdout-producing reproducer), `evidence.json`
(complete initial raw evidence), `operation_durations.json`
(additive final operation means/min/max/counts), and this report.
No existing source, parent artifact, model, or dataset was edited.

Not performed: training, inference, installations, new Hawkes/Drain fitting,
normal/protected interval analysis, prediction/history analysis, cross-window
joins, or causal interventions. Missing server spans mean **unobserved in the
allowed start-time bins**, not measured zero-duration requests or proven outages.
