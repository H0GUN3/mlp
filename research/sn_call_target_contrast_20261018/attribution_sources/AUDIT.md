# SN call-target attribution source audit

Date: 2026-10-18. Read-only audit; no dataset reads, installation, training,
inference, or implementation changes. No children were spawned.

## Branch decision

**NO: a public operation-to-target dictionary is not available in the inspected
pinned parser. YES: select the ORIGINAL destination-only contrast: reassign
only TRAIN-link-confirmed client-operation occurrences to their frozen target;
keep every other occurrence at its owner. Keep each span occurrence exactly
once and channel 1 zero. No mapping has yet been populated or validated.**

Do not describe this as a local attribution bug, coding correction, restoration
of the pinned implementation, or original-author reproduction: local owner
attribution agrees with that implementation. The controlled destination change
tests the observed caller-owner versus called-target distinction and is
motivated by the paper's callee-oriented description. The paper/code semantic
discrepancy remains a discrepancy, not an established bug. Full SN target
reconstruction is NOT established by these sources.

The spare-channel alternative was explicitly withdrawn before any protocol
freeze. It is not selected; no code, input generation, fit, or inference ran.

The parent supplied exact media linkage after source inspection. That makes
media a concrete mapping candidate, but does not waive TRAIN-only derivation.
Allowed index 112 is a validation row in the existing local report; it must not
seed or disambiguate the frozen dictionary.

## Sources and exact locations

All code locations below are **1-based lines in the original fetched text**,
including blank lines, not the browser's compacted line numbering.

### E1: Eadro paper

Retrieved with webfetch: arXiv v1 HTML. PDF webfetch exceeded its response-size
limit; the PDF was not inspected. The HTML relevant sections were successfully
returned before unrelated truncation.

```text
https://arxiv.org/html/2302.05092v1
https://zbchern.github.io/papers/icse23c.pdf
```

- Section II-A defines invocation latency as including processing and caller–
  callee communication.
- Section IV-A3, “Trace Learning”: **“calculating the average
  latency at a time slot for each callee”** (13 quoted words).
- The same paragraph specifies callee-level series and empty-slot zero padding.

This establishes the documented aggregation destination, not a Jaeger
operation-name lookup, span-kind policy, or client/server pairing algorithm.

### E2: pinned public parser

Repository: FeiGSSS/Eadro; commit:
`7d69281a80adce60067aa858729746fc6a362f53`.

```text
https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_traces.py
```

`parse_spans`, lines 12–30:

- Line 15: `service = processes[span['processID']]['serviceName']`.
- Lines 16, 23, 30 retain that service's node ID and duration list.
- Lines 17–22 use floored start seconds +28,800 and duration /1,000,000.
- Every occurrence is appended. Line 27 uniquifies timestamps, **not spans**.
- No operationName, references, spanID, span.kind, or peer.service is read.
  Thus there is no operation→target map or type-specific routing here.

The SN and TT entry points both call this same function (lines 48–63).

### E3: downstream public aggregation

```text
https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py
```

`deal_traces`, lines 75–115:

- Line 90 allocates zero-filled `(windows, nodes, chunk_length, 2)`.
- Lines 94–106 iterate inclusive second slots and calculate arithmetic means
  of occurrence lists; channel 1 stays zero.
- Line 102: `t_node = int(k.split('-')[-1])`. This decodes the owner's appended
  numeric suffix; the variable name does not establish a called target.
- Lines 109–110 subsequently standardize channel 0 per node. Consequently,
  public zero padding is **pre-standardization**, not necessarily final zeros.
- The edge-shaped wording in lines 81–82 is a docstring, not parser behavior.

### E4: static node metadata

```text
https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/util.py
```

`Info`, lines 29–42 lists twelve SN service nodes and static service adjacency;
lines 48–50 assign node IDs. This is not an operation lookup. A compose node
having several neighbors cannot identify which neighbor a particular span calls.
Database/cache nodes are not among these twelve dimensions.

### M1: one MicroHECL novelty caveat only

```text
https://arxiv.org/html/2103.01782v1
```

Section III, “1) Service Call Graph Construction”: **“each indicating the average
response time of a minute”** (10 quoted words). The paragraph attaches RT series
to directed service calls and aggregates instance-level calls to service pairs.

Therefore call-aware latency attribution/aggregation is prior art, not by itself
a new RCA mechanism. This does not imply MicroHECL uses this SN dictionary or
the proposed unchanged-node contrast.

### Local inspected evidence

- `research/native_reproduction_20261013/native_data.py:270–297`:
  `trace_series` resolves owner, accumulates duration sum/count by start second,
  divides where count > 0, and leaves empty bins/channel 1 zero.
- `native_data.py:229–268`: `SpanAudit` records identities/conflicts without
  removing repeated feature occurrences.
- `native_data.py:379–383`: the existing trace output is reshaped into
  `(windows, services, 10, 2)`.
- `research/native_reproduction_20261013/native_data_profile.py:35–41`:
  local SN twelve-service ordering.
- `research/native_learning_diagnosis_20261018/raw_media/REPORT.md:5–32,40–45,95–113`
  and `operation_durations.json:1–150`: prior selected-window evidence.
  Those documents were inspected only in relevant bounded ranges; their
  unneeded remainder and the rest of the repository were not mapped.

## Emitter, called target, aggregation destination

| Span category | Emitting service | Called target | Pinned and local destination |
|---|---|---|---|
| RPC client | owning process | potentially another service | owner, not a resolved peer |
| RPC server | owning process | owner is the receiving service, if server semantics hold | owner |
| Internal work | owning process | no separately established external target | owner |
| DB/cache client | owning process | external store, if independently established | owner |

These categories describe interpretation, not a classifier present in E2.
Without span.kind, an operation suffix alone is not proof of span semantics.
E2 treats all categories alike. In particular, server-owner attribution may
coincide with callee attribution; client-owner attribution need not. Neither
paper wording nor static adjacency supplies missing per-span target identities.

## Mapping candidates, not a frozen dictionary

The names below come from existing local operation observations and the
parent's linkage report, not fault-root labels. Except for the reported media
pair, target names remain candidates rather than proven mappings.

| Emitter | Observed operation | Candidate target | Present evidence / unresolved issue |
|---|---|---|---|
| compose-post-service | compose_media_client | media-service | Parent reports exact CHILD_OF pair at index 112; TRAIN support not checked |
| compose-post-service | compose_text_client | text-service | Operation names and observed server operation; no exact join audited here |
| compose-post-service | compose_creator_client | user-service | Observed compose_creator_server under user; no exact join audited here |
| compose-post-service | compose_unique_id_client | unique-id-service | Name/adjacency only |
| compose-post-service | store_post_client | post-storage-service | Name/adjacency only |
| compose-post-service | write_home_timeline_client | home-timeline-service | Name/adjacency only |
| compose-post-service | write_user_timeline_client | user-timeline-service | Name/adjacency only |
| text-service | compose_urls_client | url-shorten-service | Name/adjacency only |
| text-service | compose_user_mentions_client | user-mention-service | Name/adjacency only |
| user-service | user_mmc_get_client; user_mmc_get_user_id_client | unresolved cache target | No child-process target proved; retain emitter |

Parent-provided evidence, not independently re-read raw data:

- At allowed index 112, compose owns client `d5cf84b0f2dedf69` (5.990747 s);
  media owns server `6e622be069adfb34` (12 microseconds), whose CHILD_OF reference
  points to that exact client.
- Index 115 has a compose-owned 6.008163 s media client with no same-window
  child. Parent reports only internal.span.format tags, not span.kind or
  peer.service.

The first pair distinguishes emitter from a directly observed receiver. The
second cannot establish a receiver through a same-window join. Do not replace
client duration with server duration, subtract them, infer network delay, or
manufacture a receiver from the injected-fault label.

## Exactly one proposed treatment: destination only

Let `owner(s)` be the existing process service and let `F` be a frozen dictionary
keyed by **(owner service, exact eligible client operation)**. Define:

```text
destination(s) = F[(owner(s), operation(s))] if admitted; otherwise owner(s)
channel0[destination, second] = sum(original durations) / occurrence count
channel0[destination, second] = 0 when its count is zero
channel1 = 0
```

Only the node index of the existing channel-0 sum/count update changes for an
admitted client-operation key. Keep all server, internal, database, and unmapped
client occurrences at their original owners. A mapped client leaves its owner
aggregate and enters its target aggregate exactly once. Retain every duplicate
occurrence and both original client and server spans; do not deduplicate, pair,
subtract, replace durations, or append a second-channel feature.

Keep duration conversion, original start-second bin and shifts, recording
clipping, arithmetic-mean estimator, zero-fill rule, service order, twelve nodes,
ten seconds, two channels, existing normalization policy, splits, labels,
model structure/parameter count and training settings, graph, logs, and metrics
unchanged. The requested `(394, 12, 10, 2)` shape is a user-specified constraint;
this audit verified the local reshaping rule but did not load the saved tensor
to independently count 394 rows. No new statistic, scaler, edge axis, or model
component is proposed. Mean values and empty-bin locations can change:
preserving the mean and zero-fill means preserving their rules, not their
previous numerical outputs. Channel 1 must remain identically zero.

### TRAIN-only derivation and ambiguity gates

1. Use the already chosen TRAIN split only, without reading gold roots to
   derive targets. Both parent/client and child span start-bins must qualify as
   TRAIN; do not complete links with validation/test spans across boundaries.
2. Eligible exact client-operation keys require an actual direct CHILD_OF
   link to a child in a different, existing service node, matched by
   traceID/spanID/reference identity. A `_client` spelling is only an eligibility
   convention, never sufficient target evidence.
3. Collapse repeated identities **only for checking mapping evidence**, not
   for feature weights. Conflicting identity content or inconsistent links
   fail the ambiguity/provenance gate. Multiple links to the same target may
   support one key; different target services for a key make it ambiguous and
   fail the contrast gate. No majority vote or silent ambiguous-key fallback.
4. Admit only keys with a nonempty singleton target set and consistent identity
   evidence. Freeze the dictionary and its TRAIN provenance before evaluating.
   Unseen/unlinked keys, internal/server spans, and out-of-dimension DB/cache
   cases retain their original owner destination. Report unresolved cases
   separately, not as zero-duration calls. Ambiguity is gate failure, not
   ordinary missing coverage.
5. For this media contrast specifically, require TRAIN-admitted
   `(compose-post-service, compose_media_client) -> media-service`.
   If absent or ambiguous, **NO-GO for the media-target contrast**; do not seed
   it from allowed index 112 or a fault label. An empty/no-op map is not success.
6. Once TRAIN-admitted, apply that same frozen key everywhere, including
   index 115 without a same-window child. This is a learned instrumentation
   association, not proof that every unpaired call reached the receiver.

Report mapping coverage by split and `(owner, operation)`: eligible occurrences,
reassigned occurrences, unresolved owner-fallback occurrences, duplicate-weighted
counts, and affected target bins. These are accounting, not additional model
features. Validation/test coverage must not update the map.

Before a future run, require unchanged shape/order and other modalities,
channel 1 identically zero, exactly the same multiset of occurrence identities/
durations/start-bins, unchanged total counts and per-second duration sums across
nodes (allowing ordinary floating-point summation tolerance), and a nonempty
TRAIN-confirmed media key. Each reassignment must equal a frozen admitted key;
all other destinations must equal baseline owners. These are acceptance
criteria, not tests executed by this source audit.

This is a reproducible partial-target attribution treatment, **not** a claim
that spans represent unique calls or that all latency is callee-pure. The map,
TRAIN coverage, and exact tensor invariants remain unverified in this audit.
Public code establishes owner attribution and an unused zero channel, not a
target dictionary or proof that this contrast improves localization.

## Verification and provenance

Three full pinned code texts were fetched with webfetch and inspected. Bounded
assertions passed for owner routing, occurrence appending, mean aggregation,
and later scaling. One initial assertion used a misspelled expected string;
it was corrected and rerun without any source edit. No runtime or model test
was appropriate or executed for this read-only source decision.

SHA-256 of the webfetch-returned decoded text, not independently certified raw
HTTP bytes:

| Source | SHA-256 |
|---|---|
| parse_raw_traces.py | e798486864fa5adf847c5d0dff2f8a6bfb53afbe3e6bad6cc836211563b417cc |
| single_process.py | 977cb23d960815947e76c9ccc4ceccc5ac0471b135021d3d7937d3ebc92c5712 |
| util.py | 7ae22d1f0aa369e49f3e5e7a90635782be65d44fa3b3d3f2bc512bfcc9cc1207 |

Only this audit artifact was created. No existing file was changed. No raw
dataset or cached-source tree was searched. Parent raw-linkage checks remain
parent-supplied evidence, not duplicate work performed here.
