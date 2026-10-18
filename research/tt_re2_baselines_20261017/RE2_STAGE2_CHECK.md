# RE2 Stage2 — frozen handoff and execution evidence

## Frozen parent interface

No field change from the requested interface.
`re2_stage2/inputs.npz`, loaded with `allow_pickle=False`:

| Key | dtype | shape / meaning |
|---|---|---|
| metrics | float64 | W,N,10,8; raw NaNs retained |
| metric_observed | bool | same as metrics; true exactly where finite |
| traces | float64 | W,N,10,2; seconds; finite; channel 1 zero |
| logs | float64 | W,N,E; native Hawkes baseline, finite/nonnegative |
| labels | int64 | W; -1 nominal-normal, otherwise global service index |
| partition | Unicode | W; train or validation |
| case_ids | Unicode | W; original case ID |
| event_ids | Unicode | W; case ID for fault, empty for normal |
| starts | int64 | W; epoch seconds, half-open ten-second windows |
| indices | int64 | W; stable sequential bundle positions |

Order: sorted original allowed case ID, then staged ascending window start.
`metadata.json`: system `RE2-OB`, sorted TRAIN raw-ID `services`,
TRAIN union plus self-loop `edges` (**Kx2 pairs**, consumed by
`src,dst=zip(*metadata["edges"])` in the frozen native runner),
`event_count`, `input_npz_sha256`, `split_sha256`, `stage1_manifest_sha256`,
`cases` (root/global_root/fault/injection/originalpartition and window provenance),
and template/protection/source/cost diagnostics.
Unknown template is feature 0; retained Drain cluster IDs in sorted order map to
features 1..E-1. Candidate/model normalization is exclusively a later parent task.

## Boundaries and plan

- Read only original split metadata, staged authorized 54 TRAIN/18 validation files,
  frozen native implementation/config, and installed package implementation.
- Verify stage1 manifest/input hashes and cross-partition intervals before fitting.
- Fit Drain in sorted TRAIN-case/original-row order on timestamp strictly below
  injection, save/restore the installed Drain snapshot API, then match only.
- Fit templates once, inspect retained/created-cluster counts, then run a bounded
  native Hawkes probe only if the frozen input-format contract remains valid.
  Full preparation is forbidden while `template_partial_progress.json` records
  an unresolved template-cap/input-format review.
- No imputer/scaler/models, alias merging, proxy changes, raw/protected telemetry,
  stage1 reruns, installs, downloads, source edits or overwrite retries.

## Actual evidence

Preflight completed on the actual authorized staged inputs:

- Original split 54 TRAIN / 18 validation; 10,273 complete windows
  (TRAIN 7,732 / validation 2,541), with variable case lengths retained.
- All 72 stage1 metadata hashes and both staged-file hashes per case verified.
  Stage1 source hash and original locked split also verified.
- Cross-partition interval overlaps **0**; all-case interval overlaps **0**.
  No identity review triggered and no raw identity reads performed.
- Sorted TRAIN raw identifier union: **15 nodes**; no new validation identifier.
- Protection guard: raw case opens 0, protected case opens 0, denied opens 0,
  outside-output writes 0.
- Graph handoff is **Kx2** source/destination pairs. The focused fixture uses
  three edges so a 2x2 shape cannot conceal an accidental transpose.
- Split SHA256:
  `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`.
- Stage1 manifest SHA256:
  `7f1c7de45db8e36726279a2ba879823c360755718a29600b7999226b6e004d72`.

## Input-format stop evidence

The single TRAIN template producer ran under
`tool.monitor(timeout_ms=1800000)`. It was stopped intentionally after bounded
staged-message evidence confirmed preprocessing invalidity; no Hawkes fit or
full feature preparation was launched.

- First TRAIN case: 89,795 strictly pre-injection lines, 7,260 clusters created,
  1,024 retained. The configured LRU cap was reached in that first case.
- After seven completed TRAIN cases: 623,356 lines processed, 49,482 clusters
  created, still only 1,024 retained. New-cluster creation was 7.94% of lines;
  only 2.07% of all created clusters remained. This is heavy eviction/churn.
- Seed-42 reservoir sample: 12,000 of the first case's 89,795 pre-injection
  staged messages. No raw message values were retained in the report.
- Current frozen masks left 1,050 distinct masked lines in the 12,000-line
  sample, already exceeding the retained-cluster cap.
- A diagnostic-only normalization of digit-bearing tokens reduced that count to
  40. This was analysis only; no Drain configuration or mask was changed.
- Current masks left IPv4 values in 149 sampled lines. A narrower diagnostic
  normalization of identified fields plus IPv4 reduced 1,050 to 859 distinct
  lines. `Amount` had 40 distinct values in 41 sampled occurrences.
- The staged messages were plain/logfmt-style rather than top-level JSON in the
  earlier 6,000-line bounded check. UUID-shaped values were covered by the
  frozen mask; digit-bearing tokens and IPv4/logfmt values were not generally
  normalized by those TT-specific masks.
- Publishing the churned retained vocabulary would imply `E=1025` and
  1,050,625 dense Hawkes coefficients per nonempty window/node fit. One
  float64 dense matrix is 8,405,000 bytes (8.016 MiB); eight workers holding
  only one such matrix each is 64.125 MiB, before additional solver state.
  Actual Hawkes fits started: 0 because timing an invalid churned vocabulary
  would not justify publication or full preparation.
- The stopped implementation only writes its official Drain snapshot after all
  TRAIN cases, so no partial snapshot existed. Exact case counters and the stop
  reason are preserved in `re2_stage2/template_partial_progress.json`.

The required next step is a separately frozen RE2-specific input-format/masking
contract followed by TRAIN-only template fitting from scratch. No unilateral
mask change was made here. This file does not claim a complete 72-case bundle.

## Proposed RE2 preformat addendum — not frozen

This is a repair proposal for failed raw-format preparation, **not evidence that
RE2-OB is incompatible** and not a replacement for native Hawkes. It runs
before the unchanged frozen Drain masker.

Selective rules:

1. Protect semantic context before the generic TT bracket mask:
   bracketed severity becomes `severity=<level>`; bracketed identifiers are
   preserved only when they equal a known TRAIN observed component; brackets
   around `context_words` are removed while retaining the categorical text.
2. Mask syntactic RFC3339/ISO timestamps and IPv4 endpoints with optional ports.
3. Mask only values of named timestamp/port fields; named request, trace, span,
   transaction and correlation-ID fields; and named user/product/quantity/amount
   business fields.
4. Preserve severity, known component identity, exception names, HTTP/gRPC
   status, `status`, `status_code`, `code`, `error_code`, `errno`, categorical
   business text, and substantive event text.
5. Do **not** mask every integer, digit-bearing token or long token. Do not use
   validation messages to revise the rule.

Sanitized representative TRAIN templates include:

- `conversion request successful`
- `request started` / `request complete`
- `GetCartAsync called with userId=<:RE2_BUSINESS_VALUE:>`
- `[Recv ListRecommendations] product_ids=<:RE2_BUSINESS_VALUE:>`
- `received ad request (context_words=<:PRESERVED_CATEGORICAL:>)`
- `AddItemAsync called with userId=<:RE2_BUSINESS_VALUE:>, productId=<:RE2_BUSINESS_VALUE:>, quantity=<:RE2_BUSINESS_VALUE:>`
- `Detected Google metadata server: [<:RE2_ENDPOINT:>], setting ENV_PLATFORM to GCP.`

Bounded comparison on the first TRAIN case used the first 20,000 strictly
pre-injection staged messages for fitting and the next 5,000 TRAIN messages for
frozen-template matching:

| Format | Created | Retained | Unknown / 5,000 | Unknown rate |
|---|---:|---:|---:|---:|
| Current frozen format | 1,715 | 1,024 | 422 | 8.44% |
| Proposed selective preformat | 113 | 113 | 23 | 0.46% |

The remaining 23 proposed-format unknown messages were all from
`paymentservice`. This is a format-stability result only, not an accuracy or
model-quality result. Validation messages used: 0. Raw telemetry opened: 0.
Full details are in `re2_stage2/format_rule_probe.json`.

Stopped producer evidence: monitor `mon_54P3ED2T2BR4SJDY`, session `bash_2`,
actual exit code 2 after operator Ctrl-C, live producers 0, Hawkes fits 0.
`preflight.json` and `template_partial_progress.json` remain preserved with
their hashes recorded in the probe report.

## Verification

- `.venv-eadro` Python 3.8 focused tests: **7 passed** in 0.102 seconds,
  including frozen TRAIN templates/unknown validation messages, no validation
  fit, half-open timestamp and injection boundaries, seeded native Hawkes cache
  equivalence, NaN/mask/provenance roundtrip, and a non-square three-edge Kx2
  graph fixture.
- Installed Pyright 1.1.408 with `pyright_stage2.json`: **0 errors, 0 warnings,
  0 informations**, exit 0.
- CLI `--help`: exit 0. Invalid mode: exit 2. `--mode profile` re-runs the full
  preflight, then exits 1 on the persisted unresolved format blocker before
  templates or Hawkes fitting.
- Final output audit: `preflight.json`, `template_partial_progress.json`, and
  the proposal-only `format_rule_probe.json` exist under `re2_stage2/`; no live
  producer, snapshot, matched logs, Hawkes cache, or falsely complete
  `inputs.npz` exists.
