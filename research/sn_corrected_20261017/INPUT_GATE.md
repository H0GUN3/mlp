# Input producer handoff gate

**Verdict: PASS — input handoff accepted (2026-10-17).**

The selected cache, its manifest, producer contract, allowed index order, fold
assignment, protected-row boundary, and external normal-template provenance
passed the checks below. Preparation was **not rerun**. Native
`research/native_reproduction_20261013/native_inputs/SN/raw.npz` was not opened
or decoded in this gate. Among observation archives, only the selected
`inputs.npz` and permitted `research/relationship_smoke_20261013/artifacts/SN.npz`
index bundle were read.

## Read-only verification performed

Using `/home/gnho1236/r2/.venv-eadro/bin/python -B`:

```text
research/sn_corrected_20261017/input_bundle.py verify
PASS INPUT_VERIFY rows=394 sha256=ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e
EXIT=0
```

The same `-B` environment loaded `inputs.npz` through `load_inputs()` and
compared `indices` to the permitted bundle indices:

```text
ROWS 394 FAULT 325 NORMAL 69 EVENTS 36 ROOTS 12
FOLDS [132, 122, 140]
SELECTED_ORDER_MATCH True
PROTECTED_ORIGINAL_INDICES 170 INTERSECTION 0
SHAPES {'metrics': [394, 12, 10, 7], 'traces': [394, 12, 10, 2], 'logs': [394, 12, 7]}
TRACE_CHANNEL_1_NONZERO 0
LOG_CHANNELS 7 LOG_NONZERO [1415, 1414, 1380, 1414, 1415, 1337, 1414]
FOLD_ROOTS [12, 12, 12]
EXIT=0
```

Manifest protection audit states `permitted_rows=394`,
`excluded_test_rows=169`, `excluded_unassigned_rows=1`,
`protected_rows_decoded=0`; the per-array loader audit reports 394 decoded and
170 opaque-skipped rows for each of metrics, traces, logs, and labels. The
current read-only check independently confirmed that none of the 170 excluded
original indices appears in the selected cache. These are array payload decode
counts; archive decompression/CRC traversal and compressed-file hashing do not
decode excluded observations.

The native contract is retained: metrics `[394,12,10,7]`, traces
`[394,12,10,2]`, logs `[394,12,7]`; trace channel 1 is zero, and all seven log
channels contain nonzero values. The manifest documents Drain templates from
three separate `no fault/SN.*` recordings (53,522 log lines), marked as an
external normal reference shared across rotations. Provenance is recorded and
hash-bound; this gate did not retrain templates or rescan raw recordings.

## Original producer completion evidence

`INPUT_VERIFY.md` records the producer's actual monitor output, not merely its
task status. The producer ran the unit tests and one `prepare` invocation in
the same monitored command. Its recorded monitor/session and output are:

| Producer command | Monitor / session | Recorded result |
|---|---|---|
| `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv-eadro/bin/python -B research/sn_corrected_20261017/test_input_bundle.py` followed by `.../input_bundle.py prepare` | `mon_ZNVN0Z2146XWKXQ6` / `bash_9` | `Ran 15 tests in 0.019s`; `OK`; `PASS INPUT_PREPARATION rows=394 fault=325 normal=69 episodes=36 folds=132/122/140`; `PASS PROTECTION decoded=394 opaque_skipped=170 per_member; protected_decoded=0`; `PASS INPUT_NPZ_SHA256 ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`; `watcher completed (exit code 0)` |
| Full-project Pyright recorded by producer | `mon_SAGPQS203V4ZXAEQ` / `bash_8` | `0 errors, 0 warnings, 0 informations`; `watcher completed (exit code 0)` |
| Producer's generated-cache verify and independent sha256sum | `mon_4NGAWX1A6A7ZWK2D` / `bash_10` | `PASS INPUT_VERIFY rows=394 sha256=ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`; matching NPZ and manifest file hashes; `watcher completed (exit code 0)` |

This gate reused those producer tests and process evidence; it did not rerun the
test suite or preparation.

## Exact artifact and evidence file hashes

SHA-256, relative to `/home/gnho1236/r2`:

| File | SHA-256 |
|---|---|
| `research/sn_corrected_20261017/PLAN.md` | `5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470` |
| `research/sn_corrected_20261017/EXECUTION.md` | `71ada6226f39f0aaa6360fc38e1cd7bd489174b2806ce65bd225015be9751d31` |
| `research/sn_corrected_20261017/DAG_PLAN.md` | `f1232e961418de613c8c3ecfc7bf6629534316dd828f7dd9750425f5dbb49030` |
| `research/sn_corrected_20261017/INPUT_VERIFY.md` | `0aad1974fb3ae69c5acd2e51fce3f6bc5fb951cae99aa2c49f053065d68204ad` |
| `research/sn_corrected_20261017/input_bundle.py` | `e94a261509979157b4ec41f7558822c826e8038524aa3258d34686f743ae624d` |
| `research/sn_corrected_20261017/test_input_bundle.py` | `1234861d053b38bdac6b5651b1d53350563dca3b6fddd327c4f8ef672b19c35a` |
| `research/sn_corrected_20261017/inputs.npz` | `ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e` |
| `research/sn_corrected_20261017/input_manifest.json` (file) | `50169ccbf81bcb1485f0a837fe164cd95628cf3c6161ec7c43f8b78c887ee2d0` |
| `input_manifest.json` canonical payload | `290dd02afad9249af5acc25d325cf6ff83ab33012cab707089c0e36cd26a49d6` |
| `research/relationship_smoke_20261013/artifacts/SN.npz` (permitted bundle) | `1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb` |
| `research/relationship_smoke_20261013/artifacts/SN.json` | `1956804ecec5f191b02ccf52aa189e9529acb6cd256ddde2a24c02caf3e2ae93` |
| `research/native_reproduction_20261013/native_inputs/SN/raw.npz` (compressed archive bytes only; not opened here) | `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8` |

Producer source inventory and pinned source hashes, as listed in
`input_manifest.json` and reproduced in `INPUT_VERIFY.md`:

| File | SHA-256 |
|---|---|
| `research/diagnostic_observability_20261016/sn_tt_audit.json` | `503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3` |
| `research/native_reproduction_20261013/native_data.py` | `05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986` |
| `research/native_reproduction_20261013/native_data_build.json` | `30285605c55634ca29912f9855875afc8040c60bae79aff367395067c970b455` |
| `research/native_reproduction_20261013/native_data_build.md` | `d1352bf1b8ec32cae6b970baccfac5a97ba1494daac0a0fda3685ba3974df6b2` |
| `research/native_reproduction_20261013/native_data_profile.py` | `86d323810f70e732d945e25358d8488df619f0d9a445697f1b77b82fbfbaaa00` |
| `research/native_reproduction_20261013/native_inputs/SN/metadata.json` | `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4` |
| `research/native_reproduction_20261013/native_inputs/SN/raw.npz` | `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8` |
| `research/native_reproduction_20261013/native_inputs/SN_build.json` | `31728994c3aeb41ad9c4dfb401d5d15047a21f055bf81e52c80d8a2acff9e207` |
| `research/relationship_smoke_20261013/artifacts/SN.json` | `1956804ecec5f191b02ccf52aa189e9529acb6cd256ddde2a24c02caf3e2ae93` |
| `research/relationship_smoke_20261013/artifacts/SN.npz` | `1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb` |
| `research/relationship_smoke_20261013/data.py` | `cb6f035cefaaf8c3c67bde91c733d0d0b234a4857cd6cd88ee80a368bc34ec85` |
| `research/resource_study_20261013/trace_preflight.py` | `27cff85c74e628aadc518cde48047ad314932aea230f537abd5f9bf79d7a9ab7` |
| `research/sn_corrected_20261017/PLAN.md` | `5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470` |
| `research/sn_corrected_20261017/input_bundle.py` | `e94a261509979157b4ec41f7558822c826e8038524aa3258d34686f743ae624d` |
| `research/sn_corrected_20261017/test_input_bundle.py` | `1234861d053b38bdac6b5651b1d53350563dca3b6fddd327c4f8ef672b19c35a` |

## Limits

The producer record is the captured monitor transcript embedded in
`INPUT_VERIFY.md`; this session could not query the producer child task directly.
No preparation or producer test was repeated. Raw log/span/metric streams were
not independently rescanned, and this gate makes no new solver-convergence
claim; those limitations do not invalidate the selected-cache handoff criteria.
