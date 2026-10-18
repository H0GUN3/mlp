# Bounded parser0.4 implementation

This is one named dataset-port configuration, not literal original preprocessing,
an accuracy evaluation, or a scientific improvement. Only `drain_sim_th` becomes
0.4. The pinned original INI git blob and SHA256 are checked; masks, depth4,
max_children100, cap1024, numeric-token policy, snapshot settings and every other
loaded parameter remain unchanged.

`parser_transfer.py` has no old-cost import, framework, installation, training,
threshold search, or raw-data access. Its open audit guard restricts research
reads to approved sources, manifests and TRAIN exports, and writes to parser04.
Python3.8, private `.venv-eadro`, pinned libraries, single-thread environments,
and native unapproximated solver defaults are enforced.

Mining consumes each normal export once, in unchanged order. Whole-file and
per-case hashes, rows, nominal-normal TRAIN membership, timestamps, identifiers,
and file inode/size/mtime/ctime stability are checked in that stream. Null/missing
messages are never mined or coerced. Partially null and unidentified-service
profiles remain unavailable.

`miner.bin` is Drain3's compressed library snapshot of the actual final tree,
clusters and LRU state, not a template-string reconstruction. Metadata fixes
native enumeration, duplicate-template last-index semantics and unseen index0.
Hashes are checked before deserialization; full serialized roundtrip and matching
on the original ten profiles are compared before measurement.

Available profiles use unchanged `native.make_knots` and original report
coordinates/seeds. Workers receive stdin JSON `{knots, coordinates}` through
`<private-python> -B rca_native_cost.py --worker`; each has a 120-second process
deadline. Stdout, stderr, native warnings, failures, iterations, timing and RSS
remain recorded. Two initial attempted timeouts stop further fits, without
misclassifying unavailable profiles.

Only `parser04/OB/` and `parser04/TT/` receive real measurements: `miner.bin`,
`metadata.json`, `report.md`, and final `report.json`. The final report manifest
is published atomically after measurement; absent reports and existing partial
directories are never automatically reused. Self-check fixtures, including
synthetic final-report exercises, live only under `parser04/selfcheck/`.

Reports include original0.9 comparisons, coverage, dimensions, churn and
TRAIN-only cost/memory planning. Completed-fit projections are not upper bounds;
TT high-event null profiles remain a coverage limit. Matrix estimates exclude
solver workspace and are not RSS ceilings.

## Literal focused commands (repository root)

```sh
env -u PYTHONPATH OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-eadro/bin/python -B research/native_reproduction_20261013/parser_transfer.py --self-check
pyright --project research/native_reproduction_20261013/pyright-native.json research/native_reproduction_20261013/parser_transfer.py research/native_reproduction_20261013/parser_transfer_tests.py
```

Both exited0: self-check passed; native Pyright reported zero errors/warnings.
An initial native diagnostic rejected clearing the library's nonoptional
persistence-handler attribute; restoration now retains that handler safely.

Launch nodes use the same Python/environment prefix with `--system OB` or
`--system TT`. After both launches, use `--verify-all`: it hashes inputs and
artifacts and restores profile matching without mining/fits, printing
`PARSER04_VERIFIED` only after both pass.

No real mining, solver fit, model execution, original-file edit, or commit was
performed here. Actual full-miner runtime/memory and final launch reports remain
unverified until those separate launches.
