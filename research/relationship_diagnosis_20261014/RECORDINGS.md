# Recording-disjoint feasibility and performance

## Result

`recordings.json` preserves every recording and every leave-one-recording-out
candidate. Per-recording Local, Global, and Directed Top1/Top3/MRR are
event-equal means of the saved seed-averaged incident metrics; the
Directed−Global delta is included. Seeds are not counted as independent events.
The output also records root/type membership, TRAIN/held-out incident and
normal-window support, root-target support, development original-row partition
counts and disjointness, and the full candidate service inventory.

The metadata verifies nine incidents per recording: three root services, each
paired once with each of the three fault types. All root services are unique to
one recording in the observed development data. Consequently, each of the 13
recording holdouts removes three root targets from TRAIN, while those services
remain in the all-window candidate inventory. Each cold root has all three
fault types co-located in the held-out recording. This split cannot isolate
environment leakage from root-supervision shift. Recording-level score
differences are descriptive, not causal.

The initial implementation and synthetic fixture briefly assumed one root
service per recording. That was an implementation assumption, not a property
of the supplied data; after checking the saved fault metadata, validation and
fixtures were corrected to the verified three-root × three-type structure.
No source data or saved results were changed.

## Verification

Both commands ran from `/home/gnho1236/r2` with the requested thread limits and
`.venv-eadro` Python:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m unittest -v \
  research.relationship_diagnosis_20261014.test_recordings
```

Exit code: **0**; 5 tests passed. Synthetic cases cover shared versus unique
roots, normal-window support, row-partition disjointness, unsupported metadata,
and event-equal aggregation with Directed−Global deltas.

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.relationship_diagnosis_20261014.recordings
```

Exit code: **0**; printed `DIAG_RECORDINGS_COMPLETE`. The result was created
using exclusive file creation. Python diagnostics for `recordings.py` and
`test_recordings.py`: **0 errors**.

## Provenance and limits

`recordings.json` records hashes for the CV `runs.json`, `analysis.json`, both
saved development JSON/NPZ bundles, each CV fold `statistics.npz`, and the
development bundle input hashes. The CLI checks the runs hash against
`analysis.input_hashes["runs.json"]`, and verifies every input hash recorded in
CV `runs.json` before aggregation. Only the permitted NPZ metadata members
`indices`, `labels`, `event_ids`, `episode_ids`, and `fold_ids` are loaded.
No model, checkpoint, feature values, observations, adjacency, protected
original input, or external dataset was accessed. No training, inference,
tuning, installs, or downloads were performed.
