# Shared feature preparation — completed 2026-10-13

This implements **our independent local-versus-relative MLP protocol**, not a
published-model modification. Only `features.py`, `features_tests.py`, this note,
and `features/` were created. Existing native/reference code, artifacts, labels,
and splits were not edited.

## Real artifacts

`features/SN.npz`, `features/TT.npz` and adjacent `SN.json`, `TT.json` are complete.
NPZ keys are exactly `x`, `mask`, `coverage`, `labels`, `indices`, `event_ids`,
`partition`. Shapes, dtypes, Unicode provenance, invalid-slot zeros, all
candidates, original labels, and the stored seed42 split passed saved-artifact
replay checks.

| Actual count | SN | TT |
|---|---:|---:|
| x shape | 394×12×18 | 4069×27×18 |
| TRAIN / validation rows | 316 / 78 | 3256 / 813 |
| Normal TRAIN / validation | 56 / 13 | 491 / 127 |
| Original span occurrences scanned | 622,351 | 193,761 |
| Recording-retained occurrences | 569,317 | 143,183 |
| Selected-window retained occurrences | 394,075 | 98,775 |
| Selected observed latency seconds | 14,332 | 7,910 |
| Selected zero-duration occurrences | 0 | 0 |
| Missing normal-reference channels | 0 | 14 |
| Valid feature slots | 82,918 | 1,773,192 |
| Preparation seconds | 11.167 | 9.970 |

## Mechanism and evidence

Seven original metrics plus reconstructed mean duration (seconds) and retained
span count form nine channels. The pinned producer's `metric_series` validates
finite numeric CSV values, contiguous unique integer seconds, and complete
recording coverage. All 291 metric CSV hashes were rechecked against prepared
provenance; therefore metric zeros are observations, not missingness guesses.
Build, metadata, raw/prepared NPZ, source/helper and original split hashes bind
the inputs. JSON manifests record raw hashes, source/code/protocol hashes,
ordered services, selected window provenance, references and limitations.

Each original span file was streamed once using the bounded native JSON parser,
+8h clock shift, integer-second buckets and unchanged duplicate weighting.
Only selected TRAIN/validation seconds accumulated duration/count features.
Their reconstructed latency arrays matched existing native arrays **exactly**.
Latency is observed iff count>0; count0 measures zero retained occurrences.

Only normal TRAIN observed seconds fit per-node/channel median/IQR.
Scale is `max(IQR,.05*abs(median),1e-8)`. Nine signed-log z means precede nine
`abs(z)>2` fractions. Coverage remains observed-seconds/10 independently of
reference availability. Missing-reference features stay masked and zero.
No feature standardization occurs here. Both systems were staged and reloaded
before exclusive, non-overwriting publication.

## Commands and checks

From `/home/gnho1236/r2`, Python commands used
`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`:

```sh
.venv-eadro/bin/python -B -m research.method_mlp_20261013.features_tests
pyright --project research/native_reproduction_20261013/pyright-native.json research/method_mlp_20261013/features.py research/method_mlp_20261013/features_tests.py
.venv-eadro/bin/python -B research/method_mlp_20261013/features.py prepare
.venv-eadro/bin/python -B -m research.method_mlp_20261013.features_tests --real
```

All final commands exited0; eight tests passed; native Pyright reported
0 errors/0 warnings. Initial failures were an incorrect pooled-IQR test
expectation and import resolution, corrected without suppressions.

Limits: compressed NPZ members decode before selected-row slicing; held-out
values are never fitted/evaluated/exported. No training, logs/Hawkes, RCAEval,
protected-test predictions, installations, commits or additional agents.
Count0 does not prove collector health. Window splits share injection events.
True-zero latency handling is tested synthetically; selected real spans had none.
