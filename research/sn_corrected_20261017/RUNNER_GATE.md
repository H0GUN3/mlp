# Runner integration gate

Date: 2026-10-17

## Interfaces and execution boundary

`input_bundle.load_inputs()` returns `(arrays, manifest)` after checking its
source and bundle hashes. The arrays contain only the eight declared keys:
`metrics[394,12,10,7]`, `traces[394,12,10,2]`, `logs[394,12,7]`,
`labels[394]`, `indices[394]`, `fold_ids[394]`, `episode_ids[394]`, and
`event_ids[394]`. `split_indices(arrays, rotation)` returns row positions for
`train`, `validation`, and `evaluation`, not original cache indices.

`scores.event_metrics(root_logits, labels, event_ids)` scores per-event pooled
root probabilities, excludes normal windows from root scoring, and returns
event NLL, Top-1, Top-3, and event details. The runner retains validation use
for model selection and only makes evaluation-part predictions in `evaluate`,
which requires the final selection lock.

Commands:

- `fit --rotation f --kind {eadro,diagmlp} --seed {11,23,37} --target {200,400}`
  remains available. A 400-epoch continuation requires
  `rotation_f.budget.json` with that rotation's target set to 400.
- `train-rotation --rotation f` requires downstream-produced
  `PRETRAIN_CHECKS.json` with PASS status and matching source/input hashes. It
  writes `rotation_f.started.json`, runs that rotation's six 200-epoch fits
  sequentially, decides the budget only from those six validation best epochs,
  and, if any best epoch is at least 180, continues all six once to 400.
  It records run/config/history/checkpoint hashes in `rotation_f.done.json`.
- `train-all` starts exactly one subprocess per rotation (three concurrent
  subprocesses maximum, below the global limit of four). The parent records
  the successful exit code in its done receipt only after all six fits have
  returned normally. The parent also checks the subprocess's actual OS return
  code before invoking `lock`; a mass-ulw lock stage must likewise depend on
  successful completion of each rotation task, not merely receipt appearance.
- `lock` requires all three successful done receipts and verifies all 18
  expected runs, configs, source/input hashes, best/last checkpoint hashes,
  history lengths and hashes, 200-epoch selection records, extension decisions,
  selected epochs, and paired common-initial-state hashes. It creates global
  `budgets.json` and `selection.lock.json` only after the complete validation.
- `evaluate` requires the 18-run selection lock before loading inputs or
  making evaluation predictions. `train-all` remains as the compatibility
  orchestration command.

No `PRETRAIN_CHECKS.json` was present during this gate. It is produced only by
the downstream verification stage; no fit, training, evaluation, or input
preparation was started here.

## Verification evidence

Executed from `/home/gnho1236/r2/research/sn_corrected_20261017`:

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_runner
```

Exit code **0**; **6 tests passed**. The four existing synthetic guards remain:
held-out scaler invariance, shared common initial weights, bitwise resume for
both models, and normal-only/single-window behavior. Two focused guards cover
rotation-local six-run budget decisions (including the 180/179 boundary) and
refusal to create global lock files when a rotation receipt is missing.
Optimizer steps in these tests use synthetic fixtures only.

```sh
pyright --project pyrightconfig.json
```

Exit code **0**; **0 errors, 0 warnings, 0 informations**. The project config
selects the existing `.venv-eadro` Python 3.8 environment and adds this project
and the native reproduction directory as import paths. No diagnostic ignores
or type suppressions were added.

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B runner.py --help
```

Exit code **0**; help lists `fit`, `train-rotation`, `train-all`, `lock`, and
`evaluate`. This does not invoke a training stage.

The native single-file LSP diagnostic still reports unresolved imports for
`dgl`, `native_models`, `native_train`, and `input_bundle` in `runner.py`, and
`runner` in `test_runner.py`. The project Pyright CLI, using the checked-in
project configuration and existing virtual environment, reports no issues.
The LSP directory diagnostic itself could not be run because the workspace
diagnostic endpoint selected its Markdown server for the directory. These
editor/CLI differences are recorded, not suppressed.

## Source fingerprint

`runner.sources()` binds the approved plan hash and the final runner/test
sources. The approved `PLAN.md` SHA-256 is
`5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470`.

| Source | SHA-256 |
|---|---|
| `research/sn_corrected_20261017/PLAN.md` | `5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470` |
| `research/sn_corrected_20261017/EXECUTION.md` | `71ada6226f39f0aaa6360fc38e1cd7bd489174b2806ce65bd225015be9751d31` |
| `research/sn_corrected_20261017/runner.py` | `025a8c94574719183a063ca422bbe722028ebbc661aefffafe099e6ce311b777` |
| `research/sn_corrected_20261017/scores.py` | `9dc141146b364c04d0502cd8c3005522edeaf22b3976b397e28096c54799670c` |
| `research/sn_corrected_20261017/input_bundle.py` | `e94a261509979157b4ec41f7558822c826e8038524aa3258d34686f743ae624d` |
| `research/sn_corrected_20261017/test_runner.py` | `4476438b1ccfdc3943d8dd8c23e9f350462e32623e77758bfcfa5a1f69f3a0c9` |
| `research/sn_corrected_20261017/test_scores.py` | `efe65a9b0342a32282fd43f8996002809e33afe2c66fdca627cbfaaeca36680f` |
| `research/sn_corrected_20261017/test_input_bundle.py` | `1234861d053b38bdac6b5651b1d53350563dca3b6fddd327c4f8ef672b19c35a` |
| `research/native_reproduction_20261013/native_models.py` | `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632` |
| `research/native_reproduction_20261013/native_train.py` | `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7` |
| `research/mlp_prerequisites/eadro_corrected_model.py` | `1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b` |

`pyrightconfig.json` is a checker configuration, not part of the runtime source
fingerprint above. `RUNNER_GATE.md` records this verification and is likewise
not included in the runtime fingerprint.
