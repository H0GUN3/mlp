# Native trainer implementation and captured verification

## Delivered

`native_train.py` is executable and uses the pinned `.venv-eadro` environment:
Python 3.8.20, torch 1.12.1+cpu, DGL 0.9.1. `native_train_test.py` supplies the
bounded synthetic self-check. No real-data training, test evaluation, RCA access,
dependency installation, commits, agents, or producer/model/protocol edits occurred.

Normal execution requires `--system SN|TT` and `--kind eadro|diagmlp`.
Options `--seed` (42), `--epochs` (50), `--lr` (.001), `--batch-size` (256),
and `--threads` (2) are explicit and recorded, including defaults.
`--profile-one-epoch` overrides the effective epoch count to one while retaining
the requested count. `--input-dir` and `--output-dir` are also recorded.
Outputs refuse existing directories; output paths must stay below this directory
and outside producer inputs.

Inputs use only the frozen numeric `raw.npz`/`metadata.json` contract.
Validation rejects nonfinite features, incorrect shapes/labels, negative Hawkes
features, invalid edges, missing provenance, overlapping windows, and a nonzero
second trace channel. Metadata preserves ordered services and static edges.
Integer window ends follow the producer’s inclusive `start+9` convention.

## Statistical and execution choices

The split uses independent NumPy RandomState seed42, regardless of model seed.
Train/validation occupies the first `floor(.7W)` shuffled indices; validation
is its final `floor(.2*trainval)` indices. Test takes the next `floor(.3W)`.
All remaining indices are retained as unassigned. The complete permutation,
disjoint partition accounting, expected-count comparison, and pairwise shared
injection counts are saved. Exact historical validation identities are unknown.

After reading pinned public `codes/preprocess/single_process.py`
([source](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py)),
scaling retains population standard deviation (`ddof=0`) and denominator
`std+1e-8`. Statistics pool TRAIN windows/time only, separately per node/channel.
Constant channels explicitly receive zero standard deviation and are recorded;
held-out shifts use the source epsilon, not clipping. Trace channel two stays
zero; Hawkes logs are not normalized.

Training uses NativeReference, joint_loss, native_scores, Adam, seeded shuffling,
mini-batched static graphs, deterministic CPU execution, bounded intra-op threads,
and one inter-op thread. Checkpoint selection uses strict minimum full-validation
joint loss only, retaining the earliest tie. Config, input/source/split/scaler
SHA256 hashes, checkpoint, train/validation histories, validation logits/labels,
parameter counts, and timings are saved. Saved-checkpoint validation replay must
match logits, labels, indices, and loss bitwise.

Metric definitions follow `METRIC_CONTRACT.md`. The trainer preserves the
`native_scores` dictionary unchanged, including conditional and end-to-end root
scores (currently `conditional_top1` and `end_to_end_top1`). Their denominator
is actual fault windows; detection F1 uses ordinary TP/FP/FN, excluding TN
from TP. These are shared measurement corrections, not identical to old source
HR/F1. The later paper’s evaluator implementation remains unknown. No legacy
metric was added, and existing model checks were not rerun for this clarification.

## Captured verification

From `/home/gnho1236/r2`, the required trainer command passed:

```text
pyright --project research/native_reproduction_20261013/pyright-native.json research/native_reproduction_20261013/native_train.py
0 errors, 0 warnings, 0 informations
```

The additional self-check-file pyright also passed. Its first run found three
heterogeneous-DGL tensor-shape diagnostics; explicit Tensor assertions fixed them.
Editor LSP import-resolution diagnostics were not reproduced by project pyright.

```text
DGLBACKEND=pytorch .venv-eadro/bin/python research/native_reproduction_20261013/native_train.py --self-check
NATIVE_TRAIN_SELF_CHECK PASSED
exit code 0
```

Captured stdout: `trainer_self_check_stdout.txt`.
Final detailed evidence: `trainer_self_check_i_yomk00/self_check.json`.
Both model kinds performed three actual Adam updates and bitwise replay.
SN/Eadro: 64,323 parameters, 0.0544s training/validation.
TT/DiagMLP: 139,153 parameters, 0.0461s. Entire synthetic check: 0.2396s.
Checks include train-only scaling immunity to test-feature changes, partition
remainders/shared events, native shapes/labels/edges, malformed-input rejection,
normal-only loss/zero localization gradients, and singleton inference.

Warnings remain visible: expected synthetic protocol-count mismatches and native
CUDA-autocast-unavailable warning. Real dataset integration and calibration belong
to the next DAG. Synthetic timings/scores are not experiment or paper-reproduction
evidence; window splits can share incidents.
