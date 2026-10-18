# Native input build — verified outputs and measured cost

## Current status

**Both contracted SN and TT outputs are complete and verified.** Executable
preprocessing, seven focused tests, real-output checks, independent artifact
hashes, and all 6,378 windows' label/event/group provenance passed.
Full ordered services, all static edges (SN24 / TT44), and all seven metrics
were also compared directly with the pinned public `Info` source.
Exact-environment Pyright reports **0 errors, 0 warnings**.
Full extraction exited 0: SN 2,027 fits in **20.76 s**; TT 11,380 fits in
**575.24 s**; combined **596.00 s (9.93 minutes)**. No solver warnings captured.
This is not model execution, score reproduction, normalization, or a split.

## Locked downstream contract

Final producer files are `native_inputs/{SN,TT}/raw.npz` and `metadata.json`.
NPZ keys are only `metrics[W,N,10,7]`, `traces[W,N,10,2]`, `logs[W,N,E]`
(float64) and `labels[W]` (int64). Values are **UNNORMALIZED**, finite numeric
arrays readable with `allow_pickle=False`.

Metadata contains `system`, original ordered `services`, static `edges` as
`[source,target]` pairs, `event_count`, and `windows[W]`. Each window records
`run_id,start,end,event_id,root_fault_group`. End is **inclusive start+9**;
fractional logs use **[start,start+10)**. Normal event/group fields are null.
Source hashes, templates, original event records, and audits remain available.

| Output | W / N / E | Normal windows | Compressed raw NPZ bytes |
|---|---|---:|---:|
| `native_inputs/SN/raw.npz` | 564 / 12 / 7 | 96 | 858,969 |
| `native_inputs/TT/raw.npz` | 5,814 / 27 / 60 | 873 | 11,932,394 |

Both trace channel0 and log arrays have nonzero finite signals; trace channel1
is identically zero. Metric/trace arrays were checked against prepared raw
values, not transformed or fitted.

## Cost measured BEFORE full extraction

| System | W / N / E | Required nonempty-service fits | Sample fits | Mean / max seconds |
|---|---|---:|---:|---:|
| SN | 564 / 12 / 7 | 2,027 | 10 | .01915 / .05015 |
| TT | 5,814 / 27 / 60 | 11,380 | 9 | .08432 / .16592 |

Sample positions span the task list and include smallest/largest event groups.
All dimensions and templates were retained. Native tick0.7.0.1 `HawkesADM4(3)`
uses baseline initialization .2, horizon10, and unchanged solver defaults:
C1000, lasso/nuclear ratio .5, max_iter50, tol1e−5, rho.1, em_max_iter30,
em_tol=None, approximation0, one solver thread.

Mean-fit serial estimate is approximately **16.6 minutes**; two-worker ideal
estimate approximately **8.3 minutes**. The more conservative
`1.5 * sum(max_sample_seconds * fits / 2)` estimate is **1,492.35 s
(24.87 minutes)**, below the requested approximately 30-minute gate.
The gate was recorded before starting extraction. Two processes with
OMP/MKL/OPENBLAS threads1 completed under the conservative estimate.

Same-input/same-seed baseline repetitions were bit-identical for both systems.
Per-fit seed is `42+window*N+node`, retaining tick's default random adjacency
initialization; **memoization remains disabled**.

## Preserved semantics and disclosed repairs

The pinned `FeiGSSS/Eadro` preprocessing at commit
`7d69281a80adce60067aa858729746fc6a362f53` supplies Info ordering/edges,
seven metrics, Drain settings, source match/unseen mapping, zero-time
placeholders for absent event bins, source 1e−5 per-occurrence jitter, and
native Hawkes mathematics. No count/rate estimator or extra trace feature.

The frozen protocol supplies +16h records/metrics, +8h spans/logs, recording
clipping, full ten-second stride10 windows, half-open logs, relative horizon,
source integer-rounded inclusive fault overlap, and ambiguous-root rejection.
Channel0 is mean span duration in seconds per service/second; channel1 is zero.
Auxiliary normal logs (53,522 SN / 41,004 TT) train templates only, through
safe member reads, without archive extraction or supervised normal windows.
Archive traversal is sorted; service/line order and Drain enumeration remain
source-like. The INI's sole byte difference is an explicitly declared terminal
LF added by apply_patch; removing it verifies upstream blob
`a391102e3e8c66ac125fad082e619a2b180e0dcf`.

Span identity is `(traceID,spanID)`. SN has 520,300 repeated identity occurrences,
including 468,969 retained inside recording bounds; no conflicts. TT has
157,308 repeats, 109,577 retained; 2,951 content conflicts but **zero conflicts
in service/start/duration**. Every in-record occurrence retains its original
weight. No deduplication or performance-conditioned filtering was introduced.
Historical occurrences clipped: SN53,034 / TT50,578. Counts include trailing
record seconds; only full windows enter outputs.

## Checks and retained failures

Tests cover shifts, half-open edges/final fractional seconds, enclosed faults,
rounded endpoints, ambiguity, shapes/provenance, unseen bins, relative origin,
jitter overflow, solver determinism, invalid values, duplicate weighting,
and actual nonempty log/trace signals. The initial root Pyright config used
`.venv-mlp`; an owned `native_inputs/pyrightconfig.json` targets `.venv-eadro`.
An initial INI byte check and intermediate type checks failed, were corrected,
and are retained in `native_data_build.json`; no diagnostics were suppressed.

Recheck:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv-eadro/bin/python -B research/native_reproduction_20261013/native_data_test.py --real
pyright --project research/native_reproduction_20261013/native_inputs/pyrightconfig.json
```

Producer stages are `native_data.py prepare`, `calibrate --workers 2 --samples 8`,
then `build --workers 2`, using the same environment/thread prefix. Existing
artifacts are intentionally not overwritten; reuse `raw.npz` with
`np.load(..., allow_pickle=False)`. Calibration data, prepared arrays, and build
summaries remain under `native_inputs/`.

## Known limits

The original solver's iteration50 ceiling was reached by **549 SN / 8,090 TT
fits**; finite baselines are verified, but convergence beyond that unchanged
native budget is not claimed. Original duplicate weighting and non-feature TT
content conflicts remain disclosed, not repaired.
The protocol later gained two downstream `METRIC_CONTRACT.md` clarification
lines. Removing only those lines reproduces the recorded preparation hash;
all preprocessing rules are byte-unchanged. Original provenance hashes remain.

Parent owns partitions, training-only scalers, models, and training. No RCA
access, installs, new agents, or edits to profile, protocol, or model producer
occurred. These outputs are a native reference calibration, **not published
score reproduction**.
