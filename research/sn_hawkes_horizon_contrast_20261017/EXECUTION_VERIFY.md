# Phase 2 execution verification

## Initial verifier result — FAIL (historical; preserved)

At the first verification snapshot, the decision was **FAIL — do not begin independent phase-3 scoring or paired-case
analysis.** Preparation and the corrected runtime preflight pass. Seeds 11 and
37 have complete, internally consistent fit evidence. Seed 23 does not: its
current run directory has only 19/200 epochs and 38/400 updates, with no
`summary.json` or producer exit-0 receipt. This is an incomplete fit, not a
completed run. No producer was started or retried during this verification.

The comparison remains the bounded SN-only horizon contrast
`end_times=10` versus `original_window_start+10`; it is not a reproduction of
the original DiagMLP authors’ experiment, nor evidence of an accuracy effect.

## Evidence and disposition

| Stage | Result | Evidence |
|---|---|---|
| Input preparation | **PASS** | `PREPARATION_CHECK.md`, `inputs/preparation.json`, `inputs/preparation-run.log`, `inputs/finalization.log`; preparation and finalization actual exit codes 0 and `PREPARATION_PASS`. |
| Corrected real-input preflight | **PASS** | `PREFLIGHT_CHECK.md`, root `preflight.json` (`status: PASS`), root `preflight.status` (`PASS`). The preflight command’s actual exit code is documented as 0. |
| Seed 11 | **PASS** | `FIT_11.md`, `runs/absolute_seed_11/{config,history,summary}.json`, checkpoint and validation predictions. Exit 0 per receipt; 200 epochs / 400 updates, summary PASS, selected epoch 190, checkpoint replay bitwise-equal predictions/exact loss. |
| Seed 23 | **FAIL — incomplete** | `runs/absolute_seed_23/config.json`, `history.json`, `validation_predictions.npz`; config declares seed 23/absolute/200 epochs, but history has only 19 epochs / 38 updates and there is no summary. No current completion exit-0 evidence. |
| Seed 37 | **PASS** | `FIT_37.md`, `runs/absolute_seed_37/{config,history,summary}.json`, checkpoint and validation predictions. Exit 0 per receipt; 200 epochs / 400 updates, summary PASS, selected epoch 164, checkpoint replay bitwise-equal predictions/exact loss. |

### Preparation, probe, and protection boundary

The preparation producer and finalizer are both recorded as actual exit 0.
The five paired real-solver probes cover different-sized groups, all with
relative exact-match; the recorded conservative remaining estimate is
65.329829 seconds against the 1,500-second allowance. Preparation reports
394 allowed windows (train 316 / validation 78), 1,415 nonempty groups with
exact relative equivalence, and 3,313 empty groups remaining zero. The produced
log arrays are `(394,12,7)`, finite and nonnegative; other selected arrays and
split/order are reported unchanged. The source/input before-after hash check is
recorded in the preparation manifest.

**Streaming disclosure:** ZIP members were sequentially decompressed, including
unselected observation byte blocks. Those blocks were discarded without
ndarray construction or numeric interpretation. `log_window` was decoded in
full as structural indexing metadata. This is not a claim that protected bytes
were never traversed. Preparation records zero forbidden observation rows
materialized. No protected SN test/unassigned observation values or TT/RE2 data
were accessed for this verification.

The focused preparation tests are recorded as 14 passing; corrected pyright
exit 0 is recorded with 0 errors/warnings/informations. The earlier pyright
exit 1 remains preserved and was followed by the corrected passing run. The
test log’s SciPy deprecation warning remains disclosed, not suppressed.
Hawkes solver iteration-cap counts were relative 387 / absolute 470; reaching
the cap is not convergence evidence, and no convergence claim is made.

### Corrected preflight and stale record

The current authoritative runner preflight is the root `preflight.json` and
`preflight.status`, not `inputs/preflight.json` and not the historical
`runtimepreflight.json`. The current JSON has `status: PASS`, Python 3.8.20 /
Torch 1.12.1+cpu / DGL 0.9.1 / NumPy 1.21.5, 394 allowed rows, 316/78 split,
and matching recorded hashes for preparation, metadata, selected input,
baseline config, split, scaler, runner, and runner type-check config.
`PREFLIGHT_CHECK.md` records actual process exit 0.

Preflight also records array-exact baseline scaler comparison and seed-11
relative first-epoch parity: training loss `1.620579801028288`, validation
loss `1.5096815824508667`, 2 updates. The existing relative baseline was not
refit. The older `runtimepreflight.json` NOTREADY record is historical and is
superseded by this corrected PASS; it is not the current gate.

Runner receipt `RUNNER_CHECK.md` documents the adopted output contract
`runs/absolute_seed_SEED/`. Current directories use that contract, not the
earlier `newruns` name. Actual root preflight evidence is consistent with the
corrected filename ownership and is not blocked by the earlier output-name
conflict.

### Fit evidence and consistency checks

For seeds 11 and 37, current summaries report PASS, 200 completed epochs,
400 optimizer updates, `test_evaluated: false`, selected epoch and minimum
validation joint loss, plus successful checkpoint replay. Their on-disk
config/history/checkpoint/validation-prediction hashes match the hashes inside
each summary. History-derived strict minima match the summary selections:
seed 11 epoch 190; seed 37 epoch 164. Their recorded run config is absolute,
uses the corresponding seed, 200 effective epochs, batch 256, and learning
rate 0.001. Their receipts report actual producer exit 0. No persistent full
stdout logfile was retained for either fit; completion is evidenced by the
monitor receipt and artifact/summary consistency documented in `FIT_11.md` and
`FIT_37.md`.

For all three seeds, including the incomplete seed 23, the allowed new
validation prediction files contain 78 indices and labels, and their indices
and labels match the existing baseline validation predictions exactly and in
order. Each run config records 316 training and 78 validation original indices.
This verifies validation-label/order reuse; it does not validate seed 23’s
partial predictions as final.

The current seed-23 history hash is
`30079e880c3519d4b26d11f28c5fd12b560aa014c2236471e1e1f06466295562`;
its current config hash is
`5b73db88329ec8b8c72576c86c7e0f4b908746e3fead50c1521fae5c70476395`.
`FIT_23.md` describes an interrupted producer with exit 1, but the identity of
that receipt relative to the corrected output generation is not established
by a current summary or persisted producer log. Therefore this report does not
attribute the current incomplete run to a named owner or treat that older
receipt as a current actual-exit record. The objective blocker is exact:
19 epochs / 38 updates, no summary, no exit-0 completion receipt, and no
selection/replay proof. No retry was authorized or launched.

### Hashes independently checked during this verification

| File | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `preflight.json` | `fe464580762a26665bc3f3fdce7407ad628ea1a057f92007d859db92bc4265fc` |
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/metadata.json` | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| Seed 11 config | `f3edfbfd0b9266dd2334cdf387a25725fc77aef90211947b140fdd5de2d4937c` |
| Seed 11 history | `ad3cb636667ee40dc18439b7f36796945122b3b48edc362ad3892a53a0cc9b78` |
| Seed 11 summary | `cddcad47a9b38dcddaf6cec7f2934996efd1ac574554be5e62f9e2ecdfe0a57f` |
| Seed 37 config | `b58e79cefa1837b85d2befe5d40b50a0ab988ee29406169405245ed117d04411` |
| Seed 37 history | `fc8436a35df7713b6c6c58674aa5e964fcc207032abf1db471cf1f21472dd90d` |
| Seed 37 summary | `1ef1f5af7aeeb353f9de92e4ec80a6f73e16f81ced1f61527be50da0c009af1f` |

The report verified summary artifact hashes for seeds 11 and 37. Checkpoint
files were not loaded or deserialized during this verification; replay evidence
is taken from the completed trainer summaries. No baseline checkpoint or
protected array was opened.

## Stop condition

Phase 2 is **not complete** until seed 23 has a verified actual exit 0 and a
consistent 200-epoch / 400-update summary, history, selected checkpoint,
validation replay, and recorded artifact hashes. This verification did not
repeat preparation, tests, preflight, fits, replay, or scoring. Phase-3
independent scoring and paired-error analysis remain **not done**. No jobs were
launched; original sources/results remain unmodified.

## Final verification — PASS (phase 2 only)

**Decision: PASS — preparation, corrected preflight, and all three absolute
fits meet the phase-2 execution gate.** The initial seed-23 FAIL above is
retained as the first snapshot and superseded by the separately preserved
partial attempt plus the completed canonical `runs/absolute_seed_23/` run.
The recorded phase-2 execution run is
`dag_16f6fc1f-81f1-464b-9cd5-539e09785fa3`.
Independent phase-3 scoring and paired-error analysis have **not** been done.
This does not establish an accuracy effect, reproduce the DiagMLP authors’
experiment, or claim solver convergence.

### Preparation and preflight

| Stage | Verified result | Evidence |
|---|---|---|
| Preparation producer | **PASS, actual exit 0** | `inputs/preparation.json` records `producer_exit_code: 0`; `inputs/preparation-run.log` SHA-256 `f52bce8745c2b52c24a4595c20b17c4ed9a5902df917d1e01a1eb6f7851e11b6`. |
| Finalization | **PASS, actual exit 0** | `inputs/finalization.log` contains `PREPARATION_PASS`; SHA-256 `777d64c2fdca37e1da967e1a8390206bb4dfeba1080f9e34b3e8a45321928161`. |
| Corrected real-input preflight | **PASS, actual exit 0** | `PREFLIGHT_CHECK.md`, root `preflight.json` (`status: PASS`), and root `preflight.status` (`PASS`). The old `runtimepreflight.json` NOTREADY record is historical, not the current gate. |
| Existing focused checks | **PASS, reused** | `PREPARATION_CHECK.md`: 14 focused tests and configured preparation pyright passed after a preserved initial pyright failure. `RUNNER_CHECK.md`: 9 runner tests, self-check, and configured runner pyright passed. They were not repeated because their verified code/artifacts are unchanged. The recorded SciPy deprecation warning remains disclosed. |

Preparation reports 394 allowed SN windows (train 316, validation 78),
unchanged `metrics`, `traces`, `logs`, `labels`, and `indices`, and
`(394,12,7)` relative/absolute log arrays. All 1,415 nonempty allowed
window-node groups reproduced relative values exactly; all 3,313 empty groups
were zero. Five real paired probes were exact relative matches. The
conservative remaining-cost estimate was 65.329829 seconds against the
1,500-second budget; the preparation producer recorded 27.858544 seconds.
The only intended input difference is Hawkes `end_times`: relative `10`
versus absolute `original_window_start+10`.

**Streaming disclosure:** NPZ members were sequentially decompressed, so
unselected observation byte blocks were traversed and discarded without
constructing ndarrays or numerically interpreting, validating, or retaining
those values. `log_window` was decoded as structural indexing metadata. The
manifest records zero forbidden observation rows materialized. No protected
SN test/unassigned observation values or TT/RE2 data were materialized or
analyzed.

The preparation manifest records matching before/after hashes for its source
set. A read-only current rehash matched 13 of those 14 captured paths; the
sole mismatch is the documentation file `EXECUTION_PROTOCOL.md` (captured
hash `c65ddccf793888d82dd7a083a17a0f083741368fb58c14f6b58557cd0d1bd84a`,
current hash `e8c998544201e116a9bb0e03c86cd80f57fe3284ff7c48707e2ddf39c2ec9d6d`).
The available evidence does not establish when or why that document changed.
The recorded preparation, selected-input, metadata, runner, native-helper,
baseline config, split, and scaler hashes match their run/preflight records.
This documentation fingerprint drift is disclosed as a provenance caveat;
it is not attributed to a data or runtime-code change.

Root preflight fingerprints agree with current files:

| Artifact | SHA-256 |
|---|---|
| `preflight.json` | `fe464580762a26665bc3f3fdce7407ad628ea1a057f92007d859db92bc4265fc` |
| `inputs/preparation.json` | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| `inputs/metadata.json` | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| `inputs/selected.npz` | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |

Recorded executable/configuration and reused-baseline fingerprints:

| Artifact | SHA-256 |
|---|---|
| `run_horizon.py` | `481895f478d3c6153172f159ffb45a309fb129564c97707cce2bdc041e2007fc` |
| `optionalpyright_runner.json` | `6671ba22f20d6f2adb877cf22f8f9a42f87d215c554fbba4e50a47ec9c92828f` |
| native `native_models.py` | `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632` |
| native `native_train.py` | `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7` |
| reused seed-11 baseline `config.json` | `84e6f67dd9518a950a95f57407aac66d107c7fa593008e65823c542940c30b51` |
| reused split | `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d` |
| reused train-only scaler | `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1` |

Preflight records Python 3.8.20, Torch 1.12.1+cpu, DGL 0.9.1, NumPy 1.21.5,
an array-exact baseline scaler check, and seed-11 relative first-epoch parity
(training loss `1.620579801028288`, validation loss `1.5096815824508667`,
2 updates). The existing relative baseline was reused, not refit.

### Completed fits and consistency

Each run config records `diagmlp`, `horizon: absolute`, its assigned seed,
200 effective epochs, batch 256, Adam at 0.001, 12 nodes / 7 events / 7
metrics / length 10, and 316 training plus 78 validation original indices.
`RUNNER_CHECK.md` and the identical runner hash record the shared
initialization, seed/determinism, shuffle, loss, selection, and replay path.
Each summary says `test_evaluated: false`.

| Seed | Producer receipt | Epochs / updates | Selected epoch; minimum validation joint loss |
|---:|---|---:|---|
| 11 | **PASS, actual exit 0** (`FIT_11.md`; monitor completion recorded there) | 200 / 400 | 190; `0.171455979347229` |
| 23 | **PASS, actual exit 0** (`FIT_23.md`, `runs/absolute_seed_23/producer.log`; monitor `mon_ZZ1AKP8KQ95BXEFR`, session `bash_6`) | 200 / 400 | 115; `0.10320687294006348` |
| 37 | **PASS, actual exit 0** (`FIT_37.md`; monitor completion recorded there) | 200 / 400 | 164; `0.06605657935142517` |

Seed 23 has a persisted producer log. Seeds 11 and 37 have actual exit-0
completion recorded in their fit receipts, but no persistent full producer
stdout log or monitor ID is recorded there; this logging limitation is not
filled in by inference.

I parsed all three current histories and summaries. Each has 200 history rows
and 400 total optimizer updates; each history’s strict minimum matches its
summary selection. Every current `config.json`, `history.json`,
`checkpoint.pt`, and `validation_predictions.npz` SHA-256 matches the
corresponding `summary.json.artifact_hashes` entry:

| Seed | Config | History | Checkpoint | Validation predictions | Summary |
|---:|---|---|---|---|---|
| 11 | `f3edfbfd0b9266dd2334cdf387a25725fc77aef90211947b140fdd5de2d4937c` | `ad3cb636667ee40dc18439b7f36796945122b3b48edc362ad3892a53a0cc9b78` | `0c17b822424230553ec960bd6c914c87eb53034cbdba32058c4288fe93bb7248` | `0f45452113bf34bbce87458be49c5dbfbadf75611a228ff32254f004a58d9b6b` | `cddcad47a9b38dcddaf6cec7f2934996efd1ac574554be5e62f9e2ecdfe0a57f` |
| 23 | `5b73db88329ec8b8c72576c86c7e0f4b908746e3fead50c1521fae5c70476395` | `23969e73b5d2ea8bd3f31dd6cef443bd65c176a337fdab4afa4dcad33a805869` | `798f750b81ba2d0f67dcce7b848000fd2af7f1999490afbcc4d9e55c14d12c8f` | `dc6e038caf47175f8e681a458918bf22f81c620f843be003b5810377a1fa97a6` | `3ecde2357ebd6b755bef3be848bbbca6c0b20e523e868e5c9bb7f9743235a3f6` |
| 37 | `b58e79cefa1837b85d2befe5d40b50a0ab988ee29406169405245ed117d04411` | `fc8436a35df7713b6c6c58674aa5e964fcc207032abf1db471cf1f21472dd90d` | `596a602ea4394ad39b8ab2eaeb885981a6264916534bf99c8d5e20d5f636a615` | `af678df5966fac884ac25eff08583fe692c01d11fff45590563884f24cb4add4` | `1ef1f5af7aeeb353f9de92e4ec80a6f73e16f81ced1f61527be50da0c009af1f` |

The completed-run receipts report checkpoint replay with bitwise-equal
validation predictions and exact loss. Replay was not repeated here; this
verification did not deserialize checkpoints. Seed 23’s initial interrupted
attempt remains preserved at `runs/absolute_seed_23_interrupted_attempt1/`
and is not treated as canonical. Its first 19 rows match the completed history
for epoch, training/validation losses, optimizer updates, and validation
scores; timing fields were excluded. The partial attempt is recovery evidence,
not a completed fit.

The allowed current validation prediction arrays were read without loading
checkpoints and compared with each existing baseline validation prediction:
for every seed, all 78 `indices` and `labels` matched exactly and in order.
The selected input archive contains only permitted members with expected
shapes: metrics `(394,12,10,7)`, traces `(394,12,10,2)`, logs and
`log_absolute` `(394,12,7)`, labels and indices `(394,)`. This read-only
check used `/home/gnho1236/r2/.venv-eadro/bin/python -B`, exited 0, and
produced no stderr. It did not load raw/prepared source arrays or protected
values.

Solver cap counts remain a caveat: relative 387 groups and absolute 470 groups
reached the 50-iteration cap. Reaching the cap is not convergence; no
convergence claim is made.

### Scope closure

The initial seed-23 incomplete-fit blocker is resolved by its separately
receipted completed run. No unresolved preparation, preflight, or fit failure
remains for phase 2. The `EXECUTION_PROTOCOL.md` fingerprint drift above is
the sole provenance caveat. This verifier launched no producer, fit, replay,
test, or scoring job and changed no source, original input, or existing result.
Independent phase-3 scoring and paired-case analysis remain **not done**.
