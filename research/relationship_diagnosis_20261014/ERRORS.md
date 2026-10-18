# Frozen CV error and observation diagnostic — 2026-10-14

## Result and scope

**PASS:** the actual CLI created `errors.json` exclusively, exited **0**, and
printed **`DIAG_ERRORS_COMPLETE`**. Python **3.8.20**, NumPy **1.21.5**.
All **117 incident records** are in `errors.json/events`, not only the examples
below: **36 SN / 81 TT**, **325 / 3,451 unique fault windows**. There are three
seeds per incident and three modes; seeds and repeated mode evaluations are not
new incidents or unique windows. This is descriptive development-result analysis,
not a new experiment, validation set, or causal fault-propagation analysis.

Only `errors.py`, `test_errors.py`, `errors.json`, and this document were produced
by this node. No producer sibling module is imported. No training, inference,
checkpoint loading, feature-statistic fitting, tuning, installs, downloads,
commits, original streams, native test/unassigned observations, RCAEval, or
RCABench observation access occurred. Original files/results were not edited.
The parent owns `PROTOCOL.md`, `pyrightconfig.json`, and `REPORT.md`.

## Probability, averaging, and observations

- Each window/seed assigns **1/k** to every exact maximum-score tie. Root
  probability is Top1 credit; the other services sum to **1 − root credit**.
  Top3 is the fraction of root-tie positions in ranks 1–3; MRR averages the
  reciprocal ranks across all root-tie positions. No arbitrary argmax tie-break.
- Average windows within each incident/seed, then the three seeds, then give
  every incident equal weight. All saved per-run incident Top1/Top3/MRR,
  event-balanced/window metrics, counts and target-tie counts reconcile.
  All prior seed-averaged incident/aggregate metrics and Directed−Global
  incident differences reconcile with numerical tolerance
  `abs_tol=1e-12, rel_tol=1e-9`; win/tie/loss and identity/counts match exactly.
- Improvement/worsening/tie uses the incident-average Directed−Global Top1
  difference. `both_zero` and `both_perfect` are **separate exact** Global and
  Directed flags, not substitutes for tie. Local is a supplemental baseline.
  Partial credit remains partial; it is never recoded as binary solved/failed.
- Graphs are binary same-10-second-window observed CHILD_OF relations:
  **row = caller, column = callee**. Root-to-wrong and wrong-to-root are distinct.
  Bidirectional direct, root-to-wrong direct, wrong-to-root direct, non-direct
  weak connectivity, and no observed connection are mutually exclusive.
  Root itself is not a wrong service. Weak paths ignore direction, not time.
- Root observations preserve raw9 channel/time observed fraction, each raw
  channel fraction, channel-7 trace-latency fraction, root reference mask,
  reference availability, anygraph, raw incoming/outgoing root adjacency,
  visibility and available incoming/outgoing neighbor context.
  Fold-specific saved `reference_mask` has shape **[nodes,9]**:
  `visible = (observed.any(axis=2) & reference_mask[None,:,:]).any(axis=-1)`.
  Incoming availability is any `A[j,root] & visible[j]`; outgoing availability
  is any `A[root,j] & visible[j]`. **Root visibility is not an extra gate.**
  No fold0 mask reuse, standardizer fitting, values, or old normalized `x`.

## Incident-equal performance

Numbers below are rounded; JSON retains the numeric results and all identities.
W/T/L is **Directed−Global**, in win/tie/loss order.

| System | Incidents / unique windows | Local Top1 | Global Top1 | Directed Top1 | Δ Top1 | Δ Top3 | Δ MRR | W/T/L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SN | 36 / 325 | .547715 | .549997 | .640356 | +.090359 | +.010917 | +.045763 | 17/13/6 |
| TT | 81 / 3,451 | .527333 | .537817 | .542449 | +.004632 | −.003849 | +.001305 | 28/34/19 |

SN has **2 both-zero**, **11 both-perfect**, **22 Directed-partial** and
**16 Global-partial** incidents. TT has **3 both-zero**, **25 both-perfect**,
**51 Directed-partial** and **50 Global-partial** incidents. Partial counts can
overlap across modes. These flags refer to the Global/Directed pair; they do not
assert that Local also failed or was perfect.

### Fault-type strata

Each stratum averages its complete incidents equally; fault types partition
incidents and unique windows. Counts describe the existing full-event decisions.

| System / fault type | Incidents | Unique windows | Δ Top1 | Improvement / tie / worsening |
|---|---:|---:|---:|---:|
| SN cpu_load | 12 | 107 | −.002525 | 0 / 11 / 1 |
| SN network_delay | 12 | 113 | +.148910 | 8 / 2 / 2 |
| SN network_loss | 12 | 105 | +.124692 | 9 / 0 / 3 |
| TT cpu_load | 27 | 1,170 | +.000013 | 1 / 25 / 1 |
| TT network_delay | 27 | 1,125 | +.007248 | 14 / 3 / 10 |
| TT network_loss | 27 | 1,156 | +.006636 | 13 / 6 / 8 |

### Root-context strata

Each table cell is **incident count / unique-window count; subset Δ Top1**.
Select present/absent windows *within* each incident first, average those windows
and seeds, then average contributing incidents equally. The JSON additionally
retains full-event decision counts separately from subset W/T/L. Subset results
are not reclassifications of the full event.

| System / context | Present | Absent | Incidents appearing in both |
|---|---|---|---:|
| SN anygraph | 36 / 308; +.098656 | 4 / 17; −.023810 | 4 |
| SN visible incoming root neighbor | 31 / 191; +.063769 | 25 / 134; +.178052 | 20 |
| SN visible outgoing root neighbor | 12 / 71; −.146044 | 31 / 254; +.124742 | 7 |
| SN root trace latency observed at least once | 35 / 225; +.039542 | 24 / 100; +.182903 | 23 |
| SN root channel7 reference available | 36 / 325; +.090359 | empty | 0 |
| TT anygraph | 78 / 640; +.019187 | 81 / 2,811; +.000038 | 78 |
| TT visible incoming root neighbor | 24 / 123; +.112599 | 81 / 3,328; +.001124 | 24 |
| TT visible outgoing root neighbor | 19 / 92; −.035380 | 81 / 3,359; +.005059 | 19 |
| TT root trace latency observed at least once | 38 / 254; +.047883 | 81 / 3,197; +.000105 | 38 |
| TT root channel7 reference available | 39 / 1,672; +.013525 | 42 / 1,779; −.003625 | 0 |

For these actual bundles, raw incoming/outgoing edge-presence groups equal their
visible-neighbor groups; the implementation does **not** assume that equality.
Root feature visibility and any-channel reference availability are present in
every fault window in both systems. All SN fold masks have zero missing slots;
each TT fold mask has 14 missing slots. Root raw trace observation and normal
trace reference availability are different quantities.

Incident denominators **must not be summed** across present/absent groups:
mixed events legitimately enter both. Unique-window subsets are disjoint.
`errors.json/systems/*/root_context` includes all nine contexts, exact overlap
counts and identities, each mode's metrics and wrong masses. An empty group is
`null`, not an invented zero-valued estimate.

## Wrong-service observation relations

Each cell is **event-equal unconditional probability mass (conditional percent)**.
First aggregate relation probabilities within window/seed and incident, then
average incidents. Conditional percentages divide these event-equal relation
masses by the **event-equal total wrong mass**, not by window counts, not by the
number of failing events, and not by averaging individual event ratios.

| System / mode | Total wrong mass | Both direct | Root→wrong | Wrong→root | Other weak connection | No observed connection |
|---|---:|---:|---:|---:|---:|---:|
| SN Global | .450003 | .000000 (0%) | .022447 (4.988%) | .140208 (31.157%) | .035509 (7.891%) | .251839 (55.964%) |
| SN Directed | .359644 | .000000 (0%) | .012967 (3.605%) | .025964 (7.219%) | .070774 (19.679%) | .249940 (69.496%) |
| TT Global | .462183 | .000000 (0%) | .000000 (0%) | .006876 (1.488%) | .000201 (.043%) | .455107 (98.469%) |
| TT Directed | .457551 | .000000 (0%) | .000692 (.151%) | .001738 (.380%) | .000292 (.064%) | .454829 (99.405%) |

Each relation row sums to its total wrong mass, which equals 1−Top1. A perfect
incident has conditional fractions `null` because its denominator is zero.
All positive wrong-service masses and the top-three dominant wrong services are
preserved per event/mode. Local and every stratum have the same complete relation
summaries in JSON. The higher conditional no-observed-connection percentage for
Directed does not mean a higher absolute no-connection mass: its denominator is
smaller. These are observed relationships, **not causal propagation categories**.

## Mechanical examples, not selected causal stories

Selection is fixed per system: largest positive Top1 delta, largest negative
Top1 delta, and lexicographically first both-zero incident; equal deltas break
ties by event ID. All other records remain available in JSON.

| System / selection | Event ID | Root / fault type | Fold / windows | Global → Directed Top1 | Δ |
|---|---|---|---:|---:|---:|
| SN largest positive | `SN.2022-04-17T190213D2022-04-17T192544:fault04` | unique-id-service / network_delay | 1 / 9 | .111111 → .740741 | +.629630 |
| SN largest negative | `SN.2022-04-17T183729D2022-04-17T190100:fault05` | social-graph-service / network_loss | 1 / 10 | .700000 → .366667 | −.333333 |
| SN first both-zero | `SN.2022-04-17T190213D2022-04-17T192544:fault01` | nginx-web-server / network_delay | 0 / 9 | .000000 → .000000 | .000000 |
| TT largest positive | `TT.2022-04-18T203805D2022-04-18T222547:fault01` | ts-station-service / network_delay | 1 / 41 | .674797 → .796748 | +.121951 |
| TT largest negative | `TT.2022-04-18T150729D2022-04-18T165511:fault01` | ts-train-service / network_delay | 0 / 31 | .236559 → .129032 | −.107527 |
| TT first both-zero | `TT.2022-04-18T150729D2022-04-18T165511:fault08` | ts-cancel-service / network_loss | 0 / 45 | .000000 → .000000 | .000000 |

The positive and negative examples are **partial** events, not solved/unsolved
labels. Dominant Directed wrong-service masses are, respectively:

- SN positive: user-service .111111, user-timeline-service .111111,
  compose-post-service .037037.
- SN negative: compose-post-service .166667, user-mention-service .166667,
  media-service .100000.
- SN both-zero: user-service .740741, url-shorten-service .259259.
- TT positive: ts-auth-service .048780, ts-security-service .048780,
  ts-basic-service .024390.
- TT negative: ts-verification-code-service .408602, ts-food-service .139785,
  ts-security-service .086022.
- TT both-zero: ts-verification-code-service .688889,
  ts-inside-payment-service .066667, ts-user-service .051852.

Local Top1 is .037037 and .007407 in the SN and TT both-zero examples; therefore
“all modes failed” would be false.

## Hash binding and result integrity

Exactly **66 data inputs** are consumed: runs + analysis JSON, two development
manifest JSONs, two development NPZ bundles, 54 prediction NPZs, six statistics
NPZs. Every file is checked before and after loading and rechecked before output.
No referenced raw/native/checkpoint provenance path is followed.

- `runs.json` SHA-256:
  `48129c9be79d251f5278a6ed79ccd72dca2373d10ef4e3f9038b0e9b055b6b13`,
  matching `analysis.json/input_hashes/runs.json` and the explicit snapshot pin.
- `analysis.json` SHA-256:
  `3814b07ee7d5a255c02b419f5407a76bba96b3da9c75e0511ad07513a636b11e`.
  Its producer did not save a self hash. This diagnostic explicitly pins the
  current frozen local snapshot; that is not independent external authenticity.
- Development manifest/bundle hashes come from saved `runs.json/input_hashes`;
  bundle hashes must also match each manifest's saved `npz_sha256`.
- Prediction hashes must agree between saved full artifact hashes and the
  corresponding report. Statistics hashes come from saved full artifact hashes.
- NPZ members read: development `observed, adjacency, indices, labels, event_ids,
  episode_ids, fold_ids`; predictions `logits, labels, indices, event_ids`;
  statistics **only `reference_mask`**. No values, x, or standardizer members.
- `errors.json/input_hashes` records every consumed path, actual/expected digest,
  binding source and selected members. `software_hashes` binds both own Python
  files. Missing hashes/files/members, duplicate JSON keys/NPZ members/run keys/
  indices, invalid folds, pairing differences, nonfinite values and reconciliation
  failures are errors, never skipped rows.
- Result SHA-256:
  `132181cd7dba112566d8bb140085e6a78dc747c4db8fa5bb58e857f275af5e07`.
  `open("x")` refuses overwrites, with an early CLI existence check. Serialization
  rejects NaN. A failed output is not silently replaced or marked successful.

## Exact execution and verification evidence

All commands ran through `tool.monitor`, with no polling loops. Completion
notifications provided the recorded exit codes.

**Unit tests** — monitor `mon_VGX6VKW0RYQC1BYZ` / `bash_3`, exit **0**:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest -v research.relationship_diagnosis_20261014.test_errors
```

Output: **`Ran 16 tests in 0.017s`**, **`OK`**. All passed:

1. `test_conditional_aggregate_ratio_not_average_event_ratios`
2. `test_event_equal_not_window_or_seed_inflation`
3. `test_mixed_event_overlaps_and_window_subset_is_averaged_first`
4. `test_partial_credit_and_exact_tie_preserved`
5. `test_all_exclusive_relations_and_direction`
6. `test_missing_reference_visibility_and_no_root_visibility_gate`
7. `test_raw_trace_is_not_reference_or_feature_visibility`
8. `test_maximum_ties_include_root_and_conserve_mass`
9. `test_nonmaximum_root_tie_and_invalid_inputs`
10. `test_bundle_duplicate_indices_and_missing_events_rejected`
11. `test_exclusive_output_and_existing_cli_output_rejected`
12. `test_missing_duplicate_npz_members_rejected`
13. `test_missing_duplicate_reports_rejected`
14. `test_prediction_missing_duplicate_pairing_and_nonfinite_rejected`
15. `test_provenance_missing_and_mismatch_rejected`
16. `test_saved_metric_mismatch_is_not_suppressed`

Fixtures and provenance/I/O mocks are synthetic; tests do not create external
fixture files or load protected observations. Coverage includes exact maximum
ties with the root, mass conservation, reversed directions, bidirectional and
non-direct weak links, missing reference, invisible root with visible neighbor,
different masks per fold, missing/duplicate/provenance rejection, exclusive
creation, unequal incident lengths and three-seed averaging.

**Explicit own-file Pyright** — monitor `mon_NRK58WH6DFH6GATB` / `bash_5`,
exit **0**, **`0 errors, 0 warnings, 0 informations`**:

```sh
cd /home/gnho1236/r2 && pyright --project research/relationship_diagnosis_20261014/pyrightconfig.json research/relationship_diagnosis_20261014/errors.py research/relationship_diagnosis_20261014/test_errors.py
```

Own-file `lsp_diagnostics(..., severity="all")` was also called.
`errors.py` returned **No diagnostics found**. For `test_errors.py`, the live LSP
returned `reportMissingImports` at line 13: `Import "errors" could not be
resolved`; a directory LSP call repeated it. This resolver discrepancy is
**not suppressed** and not described as clean LSP evidence. The exact same test
module imports successfully in the requested Python execution and the explicit
project-bound Pyright check above is clean. No parent configuration was edited.
The parent owns final project-wide tests/types; they were not run by this node.

**Actual CLI** — monitor `mon_WM0RJ4JMNJPG2T4A` / `bash_6`, exit **0**,
exact sentinel **`DIAG_ERRORS_COMPLETE`**:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m research.relationship_diagnosis_20261014.errors
```

Actual JSON was inspected after completion: **54 reports**, **1,053 per-run
incident metric checks** (117×3 seeds×3 modes), **351 prior-summary incident
metric checks** (117×3 modes), all **117 unique events**, and exact prior W/T/L
**SN 17/13/6**, **TT 28/34/19**. Window, seed, incident, fault-type and
context-overlap denominators are explicit. No failed tests were removed,
weakened, skipped, or hidden.

## Limits and stop condition

These development incidents were used previously; their event folds do not
separate all recordings. Training sets overlap, and only four SN/nine TT
recordings exist. Fault-type/context differences are post-hoc associations, not
population inference, new evaluation, or explanations of causal propagation.
Same-window CHILD_OF omits cross-window or unobserved relations; “no observed
connection” does not prove no call/dependency. Seven metric channels being
marked observed is a data contract, not evidence of collector completeness.
Latency duration assignment is not proof of online availability.

The original diagnostic data and invariant checks are present. No model,
feature, epoch, seed, or literature-comparator choice is made from these results.
Final parent verification is separate.

### Subsequent union-context request — pending supplemental-path authorization

After the exclusive CLI output was finalized, the parent requested
`root_any_raw = root_in_raw OR root_out_raw` and
`root_any_visible = root_in_visible OR root_out_visible`, with a test ensuring a
window containing both directions is counted only once. These **combined strata
are not yet present** in `errors.json` or the implementation/tests.

The existing JSON remains unchanged. Its directional event summaries retain
marginal counts, not the same-window intersection, so adding those counts cannot
recover a correct union. This addition needs only the same permitted saved
development adjacency/observed and fold masks; no learning or broader analysis.
Requested targeted non-overwrite path:
`research/relationship_diagnosis_20261014/errors_root_context.json`.
Await parent authorization for that additional write path before changing the
currently hash-bound implementation/tests and generating the supplement.
