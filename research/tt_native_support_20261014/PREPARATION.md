# Selected-only TT preparation

`PROTOCOL.md` is the frozen contract. `prepare.py` produces only its selected
4,069-row schema, without normalization or model training.

## Execute from repository root

```sh
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv-eadro/bin/python3.8 -B research/tt_native_support_20261014/test_prepare.py
.venv-eadro/bin/python3.8 -B research/tt_native_support_20261014/prepare.py --workers 4
pyright --project research/tt_native_support_20261014/pyrightconfig.json research/tt_native_support_20261014/prepare.py research/tt_native_support_20261014/test_prepare.py
```

No installs or frozen-source edits are needed. Local import paths resolve the
existing sibling modules. Final `artifacts/TT.npz` and `TT.json` refuse overwrite.
Each execution retains a timestamped diagnostic directory, solver records,
progress, complete NPZ publication bytes, and success or failure details.
Failed attempts are not removed.

## Data boundary

- Only `relationship_smoke_20261013/artifacts/TT.npz` observations are loaded.
  Its `values[..., :7]` and `values[..., 7]` supply exact metrics and latency.
  Native trace channel1 remains zero.
- Native metadata supplies recording grids, source hashes and prior template
  provenance only. Original TRAIN+validation indices are reconstructed with
  metadata-only `original_split`; test/unassigned indices cannot enter output.
- Raw log timestamps route to selected half-open windows before `miner.match`.
  Selected evaluation logs never train templates. `native_data.train_templates`
  fits the explicitly permitted three source-designated auxiliary normal TRAIN
  references once with the pinned Drain configuration.
- Raw span timestamps route first. Only selected identities/services/durations
  are validated and accumulated. Repeated `(traceID,spanID)` contributes one
  unique count per service/window. Identity/service/time/duration conflicts in
  selected observations fail preparation. Latency still weights every duplicate
  occurrence. Reconstructed per-second retained counts and latency must equal
  the allowed values exactly.
- No native observation NPZ, original loader, prepare/build pipeline, model,
  RCAEval or RCABench is used. JSON bytes are scanned/hashed, not interpreted as
  features outside selected windows.

## Hawkes and verification

Only selected nonempty node/windows call the unchanged `make_knots` and
`fit_hawkes`; missing groups are all-zero. The seed uses the original index:
`42 + original_index*27 + node`. Horizon10, absent-bin `[0]`, tie jitter1e-5,
decay3 and native solver defaults remain unchanged. Maximum four workers and
one OMP/MKL/OPENBLAS thread per process are enforced.

The output records solver iterations, cap hits and warnings without claiming
convergence. Nonfinite/negative baselines fail rather than being replaced.
Every task retains its original index/seed, duration, warnings and iterations.
Costs separate template training, raw selected routing/counting, and Hawkes;
parent and maximum completed-child peak RSS are reported separately.

Focused tests cover protected exclusion, half-open routing, no evaluation
template fitting, duplicate weighting, identity conflicts, actual deterministic
Hawkes integration, full permitted manifest/fold support, and exclusive
publication. Production validates all row identities, exact copied channels,
source/input hashes, 81 incidents and three 27-validation/54-training supports,
then reloads only its new selected-only NPZ to verify an exact round trip.

The author graph is static `list(zip(*native_data.edges("TT")))` represented as
44 pairs, not the source module's 2-by-edge layout. Windows, faults and
event_folds retain the existing manifest contents and order.

## Verified execution on 2026-10-14

The real producer and independent published-artifact check both exited 0.
All eight focused tests and explicit owned-project Pyright passed.
The completed producer took 234.812058 seconds, including 209.706388 seconds of
Hawkes wall time. Templates were 59 plus the unseen bin (`event_count=60`).
The final schema contains all 4,069 permitted rows, 81 incidents and all three
27-validation/54-training incident supports; no native test/unassigned row.

- `TT.npz` SHA256:
  `2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597`
- `TT.json` SHA256:
  `07c3ad8ae9331dc4d48b0e4a728e34a9d5bf2c87c985d8792d9d50220f355948`
- 7,845 Hawkes fits; 5,585 reached the iteration cap; warnings `{}`;
  nonfinite outputs 0. **Convergence is not claimed.**
- Counts: 23,171 unique identities versus 98,775 retained occurrences;
  original duplicate-weighted latency is exactly preserved.

Detailed timing, memory, solver histograms, raw exit0 evidence, source-pin
correction and retained failed attempt are in `PREPARATION_EVIDENCE.md`.
Diagnostics are in `artifacts/preparation_20261014T074043_892941Z/`.
Workspace LSP reported an import-resolution issue for the new test module;
explicit project Pyright was clean. Shared configuration remains unchanged.
No model fits, installations, project commits or prohibited NPZ loads occurred.
