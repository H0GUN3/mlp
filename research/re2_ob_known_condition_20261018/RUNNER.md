# Fixed DiagMLP runner handoff

Scope: new RE2-OB known-condition development baseline only. This phase implements
and tests the runner **synthetically**; no production input, old learned state,
telemetry, protected18, or real fit is opened/run. `PROTOCOL.md` remains authoritative.
The three delivered files are `runner.py`, `test_runner.py`, and this document.

## Exact CLI

Run from `/home/gnho1236/r2` with the existing `.venv-eadro` environment:

```sh
# SYNTHETIC ONLY: safe now; temporary synthetic files are cleaned up.
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m unittest -v \
  research.re2_ob_known_condition_20261018.test_runner

# Static diagnostics; no installation required.
pyright --project research/re2_ob_known_condition_20261018/pyrightconfig.json \
  research/re2_ob_known_condition_20261018/runner.py \
  research/re2_ob_known_condition_20261018/test_runner.py

# LATER ONLY, after the upstream input verification approval:
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner check
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner fit --seed 11
# Separate process, AFTER that fit exits successfully:
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.runner verify --seed 11
```

`fit` and `verify` require exactly `--seed 11`, `--seed 23`, or `--seed 37`;
repeat the later commands once for each seed. `check` has no seed and writes
nothing. No model, budget, learning-rate, input, checkpoint, device, output-path,
resume, early-stop, or extension options exist. At most three seed processes may
run concurrently, each on two CPU threads. Use a monitored process with an
explicit adequate kill deadline; retain its real exit code, warnings, PID, and
`RE2_OB_FIT_COMPLETE` / `RE2_OB_VERIFY_PASS` sentinel. A timeout is not evidence of
convergence failure. Runner exceptions produce nonzero process exits.

## Inputs and division of responsibility

The only input files are the exact new paths:

- `artifacts/bundle.npz`, with exactly `metrics`, `metric_observed`, `traces`,
  `logs`, `labels`, `case_ids`, `starts`, `partition`, `indices`, `edge_pairs`.
  Shapes/dtypes follow the protocol: float32 `[N,nodes,10,8]` metrics, bool mask,
  float32 `[N,nodes,10,2]` traces, float32 `[N,nodes,event_count]` logs,
  int64 labels/starts/indices, Unicode case IDs and train/validation partition,
  int64 `[E,2]` edges. Observed metrics must be finite; unobserved metrics can be
  NaN or finite masked values, never infinity. No mask becomes a model feature.
- `artifacts/input.json`: `services` (ordered unique nonempty strings),
  `event_count` (integer >=2), `families` in protocol order, `bundle_sha256`,
  `split_sha256`. Preserve all producer provenance/hash/template/cost/version/guard
  evidence as additional JSON fields; runner saves the complete metadata unchanged.
- `split.json`: owned elsewhere; runner hashes it without imposing an undocumented
  schema or dereferencing any metadata path.

Runner checks exact keys/shapes/dtypes, roots within **all** candidate nodes,
48/24 disjoint cases, one nonnormal root per case, unique local indices, no
overlapping within-case windows, no absolute ten-second overlap across parts,
nonnegative logs, trace channel1 zero, and valid unique edges with every self-loop.
It never repairs a conflict by dropping cases, nodes, labels, edges, or features.

The upstream split/input verification remains responsible for the 24 groups×2/1,
fixed hash repetition rule, sealed18 membership, TRAIN-only inventory/edges/Drain/
Hawkes construction, sorted provenance and original source-file/time-identity
audits. This cannot be inferred from the numeric bundle alone. `check` is an
input-contract/scaling check, **not** that approval. Raw-source hashes are preserved
as evidence, not re-opened by the runner. Producer supplies this input contract;
no production files are needed to run the synthetic tests.

## Fixed computation

Uses absolute import of
`research.native_reproduction_20261013.native_models.NativeReference` and
`joint_loss`. DiagMLP uses every supplied service as a candidate, 8 metrics,
length10, dropout0.1, alpha0.5. No original source is edited.

`prepare_partitions` is a minimal adapter of the read pure helpers
`re2_preprocessing.prepare_partitions`, `native_train.fit_scaler`, and
`scaled_partition`. Importing those modules directly would require their
unqualified imports/sys.path mutation. The adapter preserves their formula:
TRAIN observed per-node/channel mean imputation; unsupported TRAIN channels zero
in both parts; TRAIN population mean/std across window/time, denominator
`std + 1e-8`; explicit constant-channel handling; float64 statistics, float32
model input; no clipping; logs unchanged. Missing and unsupported held-out
observations are counted separately. Validation values/masks/logs/traces never
contribute to TRAIN statistics.

Seeds11/23/37; CPU2 threads and interop1; deterministic Torch algorithms plus
Python/NumPy/Torch/DGL seeding; NumPy RandomState(seed) window shuffle each epoch.
Adam lr0.001, weight_decay0, betas(0.9,0.999), eps1e-8, amsgrad false;
batch256; exactly200 epochs. Training calls the unchanged native joint loss,
including the zero root term for all-normal batches. Online TRAIN loss is
batch-size-weighted joint loss **at update time**, not post-fit TRAIN loss.

Validation concatenates all window logits, then computes:

```text
joint = .5 * detection_CE(all windows) + .5 * root_CE(fault windows)
```

It is not the mean of per-batch joint losses. Strict improvement selects the best
state; exact ties retain the earliest epoch. There is no auto-extension. Best
epoch>=180 is explicitly `budget_limited`; the last20 validation losses, final
online TRAIN-minus-validation gap (not a matched evaluation gap), and both
checkpoints' post-fit TRAIN/validation metrics remain available for later budget
analysis. Completion alone does not certify adequate training or final
generalization.

## Scoring and replay

For each faulty window, rank the true root against **all** logits. If `g` entries
are greater and `t` tied with it, expected TopK is
`min(max(K-g,0),t)/t`; expected MRR is
`mean(1/r for r in g+1..g+t)`. Top1/Top3/MRR are averaged over fault windows
within each case and then equally over cases (validation24). Normal windows
are excluded, not assigned root credit. This is not mean-probability incident
classification. Per-case results retain every case, including normal-only cases
with null root metrics if the scoring API is used separately.

Also saved: window-weighted rank metrics; case/window detector-gated rank metrics;
detection TP/FP/FN/TN, precision/recall/F1; root NLL; detection CE; joint loss.
Detection uses ordinary argmax (exact detection ties resolve to normal).
Gating multiplies fault-window root credit by the predicted fault indicator.

`verify` must be a separate OS process (fit PID must differ). It constructs no
optimizer and performs no backward/update. It checks exact source/input/run
SHA256s, full fixed configuration, re-fitted TRAIN statistics, deterministic
initial state, all200 durable epoch records/update counts, minimum-loss/earliest
selection, checkpoint/config/state hashes, and every case. It loads only this
seed's initial/best/final checkpoints. Best/final×TRAIN/validation are re-inferred.
Provenance must be exactly equal; logits and numeric metrics use
rtol1e-5/atol1e-6. Independent scoring enumerates tied ranks and computes float64
NumPy CE rather than calling the training loss; it checks saved metrics and the
selected/final history rows. Verification rechecks input/source/run hashes at exit.
Hashes establish recorded integrity, not security against a malicious author
rewriting the entire manifest.

## Later run artifacts and recovery

Each seed exclusively creates `runs/seed_<seed>/`:

- `config.json`, `sources.json`, `inputs.json`, `scaler.npz`;
- `initial.pt` epoch0, `best.pt`, `final.pt` epoch200, each with full state,
  epoch/update count, config SHA256, and deterministic tensor-state SHA256;
- `epoch_001.json`…`epoch_200.json`, then `history.json`: online TRAIN joint,
  full validation joint/rootNLL/detection CE and P/R/F1 counts,
  case-equal conditional Top1, window Top1, per-epoch/cumulative updates,
  per-epoch/elapsed wall time;
- `best_train.npz`, `best_validation.npz`, `final_train.npz`,
  `final_validation.npz`: raw root/detection logits, labels, case_ids, starts,
  indices, partition, preserving input row order;
- `summary.json`: metrics including per-case results, budget caveat, file hashes,
  fit PID, wall/process CPU time and Linux peak RSS KiB;
- separate `verify` creates `verification.json` with replay metrics, PIDs,
  tolerances and PASS only after all checks succeed.

All writes use exclusive-create, including JSON, NPZ and checkpoints. Run folders
refuse overwrite. Best state is held in memory until training completes; epoch
records/initial state remain durable if training fails. `failure.json` records
fit errors once the run folder exists. Failures before folder creation and
verification failures are nonzero exits/tracebacks, not false PASS reports.
Interrupted/failed folders are preserved; there is no resume/delete/overwrite.
Report the failure and obtain an explicit new-path/recovery decision before any
retry. A second verification cannot overwrite its first audit.

Artifact reads go through an exact allowlist `ReadGuard`; symlink components and
multiply-linked files are rejected, NPZ pickle is disabled. Hashes are checked
before loading this run's locally generated Torch pickle. No metadata pathname
grants read authority, no wildcard checkpoint discovery, no raw-data access, no
stage2 learned state. This application-level guard is not an OS sandbox;
Python/library imports access their installed code normally. Source snapshots
hash only the enumerated implementation/protocol/reference files.

## API and synthetic coverage

Module: `research.re2_ob_known_condition_20261018.runner` (namespace discovery,
absolute imports, no new `__init__.py` needed).

- `load_inputs() -> (arrays, metadata, parts, hashes)` reads only fixed paths.
- `validate_inputs(arrays, metadata, expected_cases=(48,24)) -> parts`;
  the override is for direct synthetic validation, never a CLI budget option.
- `prepare_partitions(arrays, parts) -> (stats, data, report)` is pure.
- `model_for(metadata)`, `graph_batch(data, positions, edges)`,
  `predict(model, data, edges) -> prediction`.
- `full_losses(prediction)`, `score(prediction, independent=False) -> metrics`;
  `expected_ranks(row,label)` implements tie expectation.
- `select_epoch(history)`, `validate_history(history, train_windows)`.
- `fit(seed) -> summary`, `verify(seed) -> report`, `check() -> report`.
- `ReadGuard`, exclusive `write_json`/`write_arrays`/`write_checkpoint`;
  no caller-provided input/checkpoint paths in CLI.

Focused unittest coverage: native forward/single-window/tiny backward and Adam
update; deterministic initial weights; exact TRAIN-only scaler formulas,
validation mutation invariance and unsupported observations; case-equal versus
window-weighted scores; Top1/3/MRR ties and candidate index5 in a six-node
inventory; normal-only loss/backward; full-validation rather than batch-average
loss; earliest selection; strict CLI/budget choices; shape/label/time/partition/
edge rejection; path/symlink/hardlink guard, hashes and overwrite rejection.

One end-to-end synthetic fixture has48 TRAIN/24 validation cases, two windows
per case and two artificial nodes. It uses the native model for the unchanged
200epoch budget, entirely in a temporary directory, followed by a separate
process replay of all four prediction bundles. Test-only temporary-root injection
is not a production CLI feature. Tests also reject input/run hash tampering and
existing outputs; they prohibit optimizer construction during an additional
replay check. All child warnings, exit codes, PIDs and PASS sentinels are surfaced.

## Actual verification — 2026-10-18

- Required monitored unittest command: **11 tests passed**, 10.784s, actual
  `RUNNER_UNITTEST_EXIT=0`; monitor `mon_WGZ2NZTR21X0PTWW`, shell PID1489306,
  explicit kill deadline1800s.
- Synthetic200epoch fit: actual child exit0, PID1489387,
  `RE2_OB_FIT_COMPLETE 11 pid=1489387`.
- Separate synthetic replay: actual child exit0, PID1489582,
  `RE2_OB_VERIFY_PASS 11 pid=1489582`; all four bundles independently checked.
- Explicit scoped Pyright command above: **0 errors, 0 warnings, 0 informations**,
  actual `RUNNER_PYRIGHT_EXIT=0`; monitor `mon_PAF1GPKKZT8X68WE`, shell PID1489312,
  explicit kill deadline1800s. The editor-LSP invocation initially reported
  unresolved namespace import discovery; the explicit project-config invocation
  resolves it and passes. No diagnostic suppression/config edit was used.
- No warnings appeared in the successful monitored unittest output. Temporary
  synthetic artifacts were removed by the tests; no production run was created.

Production-input checks, real model-input forwards, real fits, and protected18
evaluation remain unrun in this phase. No new features/ablations/models or
cross-seed analysis are implemented here. This last change only records
verification evidence in this document; tested Python sources are unchanged.
