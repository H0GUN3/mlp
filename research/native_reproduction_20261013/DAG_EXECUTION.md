# DAG execution after the user's coordination preference

Preparation run: `dag_90b39ab7-6745-4c68-a372-0be565c54206`.
Definition key: `native-reference-preparation-20261013-user-dag-v1`.
Start accepted with no contract warnings.

Preparation gate passed. SN calibration run:
`dag_d81b4846-ae78-4143-b2c4-2fb333936f09`
(`native-sn-calibration50-20261013-v1`), six disjoint training nodes followed by
independent artifact/scoring verification. TT still depends on its producer's
completion and real-data runtime profile.

Update after verification: SN50 passed all six runs and independent rescoring;
DiagMLP selected epochs49/48/50, triggering the already-frozen SN200 diagnostic
for both methods. TT extraction and two real-input one-epoch profiles passed
(about6.57s Eadro /5.46s DiagMLP per epoch,13 updates each).
The next execution phase has three components: six SN200 runs, six TT50 runs,
and a small parameterized verifier reusing the existing independent scoring
formula. All execution lanes use `quick` because they run fixed commands;
the verifier is a mechanical generalization, with SN50 regression checks.
A final fan-in validates both systems' artifacts and scores. No input or
training/model source changes occur during these runs.
Follow-up run: `dag_80ed827d-2a13-418b-8c29-cbbe7cbb3908`
(`native-sn200-tt50-calibration-20261013-v1`).

The follow-up's two CLI punctuation failures were amended in place; successful
runs stayed cached. A later early gate encountered a still-running TT job.
Parent artifact-ready monitor `bash_56` subsequently verified all TT50 outputs
with exit0. SN200 and TT50 are now both PASS.

TT200 launch-registration DAG:
`dag_921c0787-8ea9-41bb-8fc2-0a87d663dc3c`.
Its PASS means six distinct jobs/monitors were registered, **not trained**.
Parent monitor `bash_57` waits for all six final summaries and then runs the
unchanged independent TT200 verifier. This separates launch-node completion
from actual process/artifact completion.

Parallel RCA input/cost audit:
`dag_c91999d3-916c-4b37-9e02-7ddcfff42085`
(`export-audit` → `native-cost` → `verify-audit`).
It reads no final-test telemetry and performs no RCA model training.

Keep completed acquisition, source audit, data profile and native module checks.
Keep the running preprocessing producer `st_01a13304`; do not duplicate it.

## Current phase: executable reference preparation

Three independent components, maximum three new workers plus the existing
preprocessing worker:

1. **Trainer implementation + focused checks** (`deep-low`): normalization,
   graph batching, native joint loss, checkpoint selection and replay form one
   coupled executable path. Writes only `native_train.py` and its own test/report.
2. **RCA label-semantics audit** (`deep-low`): determine from collection evidence
   whether incident labels support faithful native window labels. Read-only
   evidence gathering; no RCA final-test telemetry access.
3. **Data-adequacy explanation** (`writing`): explain actual event/window counts,
   coverage limitations and uncertainty in plain Korean. No training or fixes.

Then one **integration verification** (`quick`) depends on all three. It runs
the trainer's real self-check/type check and checks that the reports preserve
the measured counts and uncertainties. It does not certify model accuracy.

The existing preprocessor and this DAG are independent upstream producers.
The next calibration DAG starts only after both are verified for its system.
SN finished first, so its two one-epoch runtime profiles ran in the main
orchestration step while TT's monitored extraction continued; both passed.
System-specific execution DAGs need not wait on unrelated unfinished systems.
They launch disjoint model/seed runs within `CALIBRATION_BUDGET.md` and verify
saved predictions against checkpoints. Later diagnosis and proposal DAGs are
defined from measured results, not speculative branches.

## Shared producer/consumer contract

`native_inputs/{SN,TT}/raw.npz`:

* `metrics`: `[W,N,10,7]`, unnormalized.
* `traces`: `[W,N,10,2]`, unnormalized.
* `logs`: `[W,N,E]`, native Hawkes features.
* `labels`: `[W]`, -1 normal or canonical node index.
* No object/pickle arrays.

`metadata.json`: `system`, ordered `services`, `edges` as integer `[src,dst]`
pairs, `event_count`, and `windows` with `run_id,start,end,event_id,
root_fault_group`. Fault IDs/groups are null for normal windows. Source hashes,
alignment decisions and quality counts remain attached.

The trainer creates seed42 calibration partitions from the frozen protocol,
fits scalers on training windows only, never selects epochs using test, and
does not run proposed models. Its self-check is:

```
DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --self-check
```

Success requires exit0 and `NATIVE_TRAIN_SELF_CHECK PASSED`, covering a real
optimizer update, train-only scaling, partition accounting, graph/input
contracts and saved-checkpoint prediction replay. Synthetic success is not
reported as an experiment result.

No node may access RCAEval final36 telemetry, install global packages, change
shared/root accounts, edit another producer's files, commit, or contact people.
