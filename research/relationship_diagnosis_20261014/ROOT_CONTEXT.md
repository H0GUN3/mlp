# Root-context OR union supplement

This supplements [ERRORS.md](ERRORS.md) and the original nine contexts without
changing `errors.py`, `test_errors.py`, `errors.json`, or `ERRORS.md`.
Machine-readable output: [errors_root_context.json](errors_root_context.json).
Original CLI evidence: [ERROR_EXECUTION_EVIDENCE.md](ERROR_EXECUTION_EVIDENCE.md).

## Definition and aggregation

Only two same-window boolean unions are added:

```python
root_any_raw = root_in_raw | root_out_raw
root_any_visible = root_in_visible | root_out_visible
```

An incoming **and** outgoing window counts once, not twice. Adjacency is
caller→callee observed CHILD_OF in the same 10-second window, not causal
propagation. An edge elsewhere in the graph does not create root context.
Visible neighbors use the corresponding saved fold `reference_mask` and
`observed.any(time)`; root visibility is **not** an extra condition.

Each event retains its root, service, fault type, recording, fold, original
window indices, union present/absent counts, fraction, selected indices and
both-direction count. The fraction denominator is that event's unique windows.
Performance first averages the selected windows and three seeds inside each
event, then averages events equally. Exact score ties retain the original
uniform rank credit via read-only `errors.ranking`.

A mixed event belongs to both presence and absence strata on different
windows. **Do not sum their event counts**. Window counts are disjoint.
For an empty stratum the result is `null`, not an invented zero score.

## Numeric findings

Raw and visible unions select identical windows for all 117 saved development
events in this dataset; this observed equality is not assumed by the code.
The following tables therefore apply separately to **both** unions.

| System | Total events/windows | Present events/windows | Absent events/windows | Overlapping events | Event-equal present fraction |
|---|---:|---:|---:|---:|---:|
| SN | 36 / 325 | 34 / 211 | 24 / 114 | 22 | 0.645700 |
| TT | 81 / 3451 | 33 / 173 | 81 / 3278 | 33 | 0.049780 |

The corresponding window-weighted fractions are 211/325 = 64.9231% and
173/3451 = 5.0130%; these are descriptive counts, **not** performance weights.
There are 51 SN and 42 TT windows with both directions. Adding directional
counts would incorrectly give 262 and 215 rather than union counts 211 and 173.
Event coverage is 34+24−22=36 and 33+81−33=81.

Event-equal performance (fractions, rounded to six decimals):

| System / stratum | Mode | Top1 | Top3 | MRR |
|---|---|---:|---:|---:|
| SN present | Local | 0.588235 | 0.757516 | 0.706831 |
| SN present | Global | 0.588235 | 0.758427 | 0.708593 |
| SN present | Directed | 0.633306 | 0.762636 | 0.723778 |
| SN absent | Local | 0.279299 | 0.695238 | 0.522429 |
| SN absent | Global | 0.288194 | 0.687202 | 0.526432 |
| SN absent | Directed | 0.484259 | 0.726819 | 0.637754 |
| TT present | Local | 0.680211 | 0.837935 | 0.766687 |
| TT present | Global | 0.679614 | 0.838215 | 0.764134 |
| TT present | Directed | 0.739590 | 0.884091 | 0.815607 |
| TT absent | Local | 0.521765 | 0.649725 | 0.617428 |
| TT absent | Global | 0.532353 | 0.665633 | 0.628710 |
| TT absent | Directed | 0.533795 | 0.659953 | 0.627550 |

| System / stratum | Directed−Global Top1 | Top3 | MRR | Subset Top1 win/tie/loss | Seed-window decisions per mode |
|---|---:|---:|---:|---:|---:|
| SN present | +0.045070 | +0.004209 | +0.015185 | 9 / 19 / 6 | 633 |
| SN absent | +0.196065 | +0.039616 | +0.111322 | 16 / 7 / 1 | 342 |
| TT present | +0.059977 | +0.045875 | +0.051473 | 10 / 20 / 3 | 519 |
| TT absent | +0.001441 | −0.005679 | −0.001160 | 26 / 36 / 19 | 9834 |

These win/tie/loss counts use **subset** event means, not the original full-event
decisions. Directed's SN Top1 advantage is larger in absent windows
(+19.6065 percentage points) than present (+4.5070 points); TT's is
+5.9977 points present and +0.1441 points absent. TT absent Top3/MRR differences
are negative. These overlapping post-hoc strata do **not** establish a causal
benefit of context, explain every model behavior, or constitute new validation.
No selection, fitting, training, inference or protected observations were used.

## Verification and execution

Focused command:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B -m unittest -v research.relationship_diagnosis_20261014.test_errors research.relationship_diagnosis_20261014.test_root_context
```

Monitor `mon_MKQCPT7TW6NATGKM` / `bash_5`: **exit 0**,
`Ran 21 tests in 0.021s`, `OK` (16 original + 5 union tests).
New fixtures cover bidirectional deduplication, graph edges unrelated to root,
invisible neighbors, missing/switching fold references, no root-visibility gate,
the same event crossing strata, equal-event/equal-seed rather than window
weighting, empty strata, and refusing existing output before any input reads.

```sh
pyright --project research/relationship_diagnosis_20261014/pyrightconfig.json research/relationship_diagnosis_20261014/root_context.py research/relationship_diagnosis_20261014/test_root_context.py
```

Monitor `mon_VH3AF743KW3G0PE5` / `bash_7`: **exit 0**,
`0 errors, 0 warnings, 0 informations`.
The standalone LSP reported two unresolved-import diagnostics in the new test
(`.` and `root_context`), while source diagnostics were empty. This is reported,
not suppressed: explicit project Pyright and actual package unittest imports
both pass, as with the original diagnostic's documented resolver discrepancy.
No project/LSP configuration was changed.

Supplement CLI was run **once**, after the passing focused tests:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-eadro/bin/python -B research/relationship_diagnosis_20261014/root_context.py
```

Monitor `mon_RZSA9ZW2AYW3TGCF` / `bash_8` returned the completion event:

```text
Monitor event(Execute exclusive root-context union supplement once): DIAG_ROOT_CONTEXT_COMPLETE
watcher completed (exit code 0)
```

The actual `bash_output` response was:

```text
status: completed exit_code: 0
DIAG_ROOT_CONTEXT_COMPLETE
```

Runtime: Python 3.8.20, NumPy 1.21.5. Output is exclusive-create (`open("x")`).
The CLI never invokes `errors.main` or `errors.build_diagnostic`.
It hash-checks the original result/software and 62 necessary input files
(2 bundles, 6 saved reference-mask archives, 54 predictions); no checkpoint,
normalized features, standardizer values or raw stream is read.
Predictions are paired against bundle rows and every original per-seed and
full-event metric is reconciled; all original observation summaries are checked
for equality. Only incident rows are passed to context calculations.
An independent JSON check passed 238 count/OR-inclusion-exclusion/overlap checks
without rerunning either CLI.

## Immutable provenance

Before/after SHA-256 values are identical:

| Original file | SHA-256 |
|---|---|
| errors.py | `130512dbb5850236c467384238c37d40065bb0a2f8fb185777a5b7ffcf7e2910` |
| test_errors.py | `527ee4bb3692f3e289fcbc5bafd51790e3f28f76ea65f9533beb7ce8cb23b7d0` |
| errors.json | `132181cd7dba112566d8bb140085e6a78dc747c4db8fa5bb58e857f275af5e07` |
| ERRORS.md | `9f822d5fc1f2928c652f32e9cf18f198db8013184cf31ff3db7d47352c8c46fa` |

Supplement JSON SHA-256:
`8b4d23c1ab590f7c2be5572713b49da011792d56919bdcf3cb645086c2fab96b`.
Its `software_hashes` and `input_hashes` bind every consumed file. Original input
and software hash bindings remain valid. The supplement does not replace any
original context or diagnostic. Repository-wide checks were not run.
