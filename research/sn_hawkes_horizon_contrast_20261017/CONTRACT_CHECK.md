# Execution protocol contract check

**Verdict: PASS — contract-level alignment with the pinned baseline and cited source.**

The protocol specifies a bounded, single-variable horizon contrast and preserves
the baseline’s recorded training/split/selection contract. This is a source and
metadata review only: no NPZ or event arrays, checkpoints, preflight, solver
probe, features, fits, or scores were opened/run here. The later preparation,
reader-safety, equivalence, and runtime checks remain execution gates; their
not-yet-run status is not a contract failure.

## Fixed and changed fields

| Field | Pinned baseline / source evidence | Protocol | Check |
|---|---|---|---|
| Source provenance and interpretation | `native_data.py` pins `COMMIT=7d69281a80adce60067aa858729746fc6a362f53`; `SOURCE_EVIDENCE.md` records the pinned fork’s `single_process.py` and `align.py`. | Same pinned fork semantics for the changed arm; explicitly not author-code reproduction or a novel method claim. | PASS |
| Window/split and order | `seed_11/split.json`: seed 42, NumPy RandomState/MT19937, train 316, validation 78, test 169, unassigned 1; baseline split hash `c38959d0…ee018d`. `REGISTRY.md` records common ordering/hash across seeds. | Train/validation only; preserve original indices/order and split hash. No protected test/unassigned values. | PASS |
| Non-Hawkes inputs | Baseline config identifies SN, ordered 12 services, 7 events, length 10, CPU float32; common raw and metadata hashes are recorded in `sn200_verification.json`. | Metrics, traces, labels, services/graph and selected window correspondence are held fixed; only Hawkes logs may change. | PASS |
| Event selection and knots | Local `native_data.py::make_knots` enforces `[start,start+10)`, subtracts start, sorts per template, adds `idx*1e-5`, and initializes empty template bins to `[0]`. Pinned public `deal_logs` instead selects `timestamp>=s` and `timestamp<=e`; `align.get_basic` uses stride-1 windows. | Keep local selected stride-10 windows and half-open event set in both arms; retain local relative knots, template order/placeholders, and jitter. Do not claim full public pipeline reproduction. | PASS |
| Hawkes model/options | Local `fit_hawkes`: `HawkesADM4(3)`, `end_times=LENGTH` (10), baseline start `.2`, seed `42 + original_window*node_count + node`. Pinned `logHaw`: `HawkesADM4(decay=3)`, `end_time` forwarded to `fit`, baseline start `.2`; `deal_logs` passes `e+1`. With `e=s+9`, this is `s+10`. | Hold model, baseline, solver defaults, seed from original window, knots and event set fixed; change horizon only: relative `10` versus public-source `original_window_start+10`. | PASS |
| Training model and optimization | `seed_11/config.json` (and registry’s cross-seed config review): DiagMLP, SN, CPU float32; Adam lr `.001`, betas `.9/.999`, eps `1e-8`, weight decay 0; batch 256; 200 epochs; 400 updates; two CPU threads, interop one, deterministic algorithms. | Same model/training settings and runtime thread/determinism contract; no added clipping, rescaling, or optimizer/solver tuning. | PASS |
| RNG and training order | Baseline config records model seeds 11/23/37 and seeded NumPy `RandomState(model seed)` epoch shuffle. `native_train.py::run_training` seeds Python, NumPy, Torch before model construction; training uses the original train partition order before each seeded permutation. | Preserve these seeds, initialization call order, partition row order and shuffle policy. Initial tensor hash was not recorded in the baseline; protocol does not claim one. | PASS |
| Scaler and checkpoint selection | Baseline config: scaler fit on train only; strict minimum full-validation joint loss, earliest tie. Shared scaler hash `b9a6a566…4fb1`; split hash above. `summary.json` records existing best epochs (11: 192; 23: 78; 37: 200) and 200 completed epochs. | Compare scaler against existing training-only scaler; preserve loss/selection policy. Relative arm reuses existing SN200 results rather than refitting. | PASS |
| Artifact/replay boundary | Registry cites prior checkpoint replay evidence; no checkpoint was inspected in this check. | Existing checkpoint is not an input. Newly produced owned checkpoints and allowed validation replay are permitted; this correctly distinguishes new-run verification from phase-1 prohibition. | PASS |
| Data access and writes | Brief/Gate/Access constrain protected observations and original artifacts. | Use only SN train316/validation78; do not materialize SN test169+unassigned1 values or access TT/RE2 observations. Any compressed-stream byte skipping must be disclosed distinctly from value decoding. New outputs stay in the owned experiment directory; source/results immutable. | PASS |

## Provenance and limits

- Original baseline evidence read: `calibration200/SN/diagmlp/seed_11/config.json`,
  `seed_11/summary.json`, `seed_11/split.json`,
  `seed_11/history.json`, `seed_23/config.json`, `seed_37/config.json`,
  and `sn200_verification.json`. Existing records identify the seed 11/23/37
  runs as 200 epochs and report the selected epochs/losses in `REGISTRY.md`;
  these are provenance, not new measurements.
- Local source inspected: `native_data.py` constants and
  `make_knots`/`fit_hawkes`/`event_tasks`; `native_train.py` seed, split,
  scaler, model, shuffle, and selection path.
- Pinned public source was retrieved as text from the commit URLs recorded in
  `SOURCE_EVIDENCE.md`: `single_process.py` (`logHaw`, `deal_logs`) and
  `align.py` (`get_basic`). The inspected operations support the stated
  `e+1 = s+10` relation for a length-10 interval ending at `e=s+9`.
- Evidence files and original artifacts were not edited or rehashed here.
  No empirical result, run exit code, log, or newly computed hash is claimed.
- The private author’s original implementation/RNG behavior remains unknown;
  this protocol is a controlled local comparison with pinned public-fork
  horizon semantics, not an exact reproduction of that full pipeline.
