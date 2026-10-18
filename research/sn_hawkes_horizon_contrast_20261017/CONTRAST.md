# Hawkes horizon-only contrast — frozen proposal

## Scope and interpretation

This is a preservation/feasibility contract for a future bounded empirical
contrast; no fits, feature generation, array decoding, or model runs are part of
this phase. The contrast is the public repair fork's log-Hawkes horizon
behavior versus the local relative-window horizon. It is **not** the actual
DiagMLP authors' implementation, a new scientific principle, or evidence of a
novel method. The public source is pinned at
`FeiGSSS/Eadro@7d69281a80adce60067aa858729746fc6a362f53`.

## Before/after contract

| Item | Before (public-fork behavior) | After (proposed bounded arm) | Evidence/status |
|---|---|---|---|
| Source revision | Pinned repair fork above | Same fork's preprocessing semantics, with only horizon overridden | `native_data.py: COMMIT`; source `single_process.py` |
| Window and event selection | In this contrast use existing selected 394 local stride-10 windows and half-open `[s,s+10)` log events | Identical local selection | Public source uses `<=e` and stride1; that separate difference is NOT varied. See `SOURCE_EVIDENCE.md`. |
| Knot coordinates | Sorted event timestamps minus window start `s` | Identical relative coordinates | `single_process.py:35-41`; `native_data.py: make_knots` |
| Per-template ties | Per-template occurrence-index jitter `idx*1e-5` | Identical; no clipping or replacement | `single_process.py:40-41`; `native_data.py: make_knots` |
| Template identity/order and placeholder | `event_num` includes unseen bin; every bin starts `[0.0]`, populated bins replaced by observed knots | Identical | `single_process.py:16-23,35-41`; local source metadata and `make_knots` |
| Hawkes model and fit options | `HawkesADM4(decay=3)`; fit with baseline initialization `0.2`; return baseline | Identical model, baseline, default solver, and output selection | `single_process.py:3-6,42`; local `native_data.py: fit_hawkes` |
| Randomness | No explicit seed in shown public `deal_logs`/`logH` path | Hold local per-fit seed rule fixed across arms (`42 + window*N + node`) | Local `native_data.py: SEED`, `event_tasks`, `fit_hawkes`; public exact RNG behavior is otherwise unknown |
| Empty groups | A present service group gets all template bins initialized at `[0.0]`; an absent service remains zero in result array | Same; absent groups remain exact zeros and are not fitted | `single_process.py:23,33-43`; local event-task construction |
| **Hawkes observation horizon** | **`end_time=e+1`**, where `e` is the absolute window end | **`end_times=10`**, the local relative ten-second window duration | Public `single_process.py:42`; local `native_data.py: LENGTH=10`, `fit_hawkes` |
| Output constraints | Source stores returned baseline in result array | Require every fitted output finite and nonnegative; retain exact zeros for empty groups; warn/report any cap or solver warning without tuning around it | Source baseline return `single_process.py:3-6`; proposed validation gate, not yet run |

No clipping, renormalization, alternate estimator, changed template policy,
count feature, GLU, or architecture change is included. If any item other than
the horizon cannot be held constant in a future paired probe, stop for a parent
decision rather than silently expanding the contrast.

## Source-grounded mismatch

The public fork builds `knots` as event timestamps minus `s`
(`single_process.py:39`), so event times are relative to the window start, but
passes `e+1` to `logH` (`single_process.py:42`), which forwards that value as
`HawkesADM4.fit(..., end_time, ...)` (`single_process.py:3-6`). For a ten-second
window whose `s` and `e` are absolute epoch-like coordinates, this combines
relative event times with an absolute-coordinate horizon. The local reference
uses the same relative knots and `end_times=10` (`native_data.py:
make_knots`, `fit_hawkes`). This is a time-reference/unit mismatch in public
fork behavior. It is not evidence about private DiagMLP author code and does
not by itself establish that either horizon improves scientific validity.

The local native calibration is not byte-for-byte public reproduction: among
other details, its logged-time selection is half-open and its explicit per-fit
seed is recorded locally. Those policies must be frozen identically in both
arms; the proposed question is the horizon-only contrast, not complete fork
reproduction. Public RNG behavior is not established by the inspected
`single_process.py`; confirm the actual solver/RNG environment before paired
execution. Do not claim all other behavior is source-identical if that cannot
be confirmed.

## Predicted outcome and reporting

The hypothesis is deliberately non-directional: the horizon change may improve,
worsen, or leave downstream results unchanged. Report observed input changes
and downstream differences separately; because the changed horizon changes
Hawkes-derived inputs, any score difference is an association under this
controlled contrast, not causal proof from changed inputs alone.

For each fitted group, the future probe must report baseline shape, finite and
nonnegative checks, exact empty-group zero counts, solver warnings/iteration
cap status, and paired absolute and relative input differences against the
relative-horizon arm. Define relative difference as
`abs(after-before)/abs(before)` only where `before != 0`; separately report
zero-to-nonzero transitions and never silently replace undefined ratios.
Summaries must be stratified at least by window and node, with finite-value and
nonzero sparsity summaries. No favorable threshold is predeclared.

## Failure conditions and minimum gates

The future actual-solver probe and relative-arm reproduction are required
before any full comparison; neither is authorized or executed here.

1. **Contract failure:** any input, knot, template order, placeholder, jitter,
   seed, solver option, output handling, or training/selection policy differs
   between arms beyond the horizon. Stop and obtain a parent decision.
2. **Invalid observations:** non-finite or negative fitted baselines, malformed
   output shape, changed empty-group zero behavior, invalid knots, or
   horizon-incompatible jitter. Preserve and report the failure; do not clip,
   normalize, substitute a count, or change the solver to rescue it.
3. **Solver boundary:** solver warning, iteration cap, or convergence behavior
   differs materially between arms. Record the exact warning/iteration evidence;
   do not increase limits or change solver settings within this contrast.
4. **Unreproducible relative arm:** the local relative-horizon arm cannot be
   reproduced under the frozen code, seed, and environment. Do not infer
   paired input effects or launch the full contrast until explained.
5. **Cost gate:** obtain a bounded actual-solver probe and record measured fit
   cost and a conservative total estimate before full execution. If projected
   execution exceeds the authorized budget, stop for a decision.
6. **Protected-scope violation:** no raw/prepared NPZ or event-array decoding,
   checkpoint deserialization, protected SN169+1 access, or TT/RE2 observation.
   Phase remains source/text/JSON-metadata only.

No fitted inputs, scores, causal attribution, or full-run feasibility claim is
made by this document.
