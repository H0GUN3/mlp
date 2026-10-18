# Rotation 1 training receipt

**Status: FAIL — training did not start.** The single permitted launch exited
with code 2 before `runner.py` opened. No fit was run; no runner-owned
`rotation_1` receipts or `runs/rotation_1` outputs were created. No retry was
performed.

- Monitor: `mon_HN8X6BCXR0CMSED0` (`bash_2`)
- Required command:
  ```sh
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B runner.py train-rotation --rotation 1
  ```
- Launch directory was `/home/gnho1236/r2`, not the required
  `/home/gnho1236/r2/research/sn_corrected_20261017`.
- Captured monitor result: `watcher exited_2 (exit code 2)`.
- Exact error:
  ```text
  /home/gnho1236/r2/.venv-eadro/bin/python: can't open file 'runner.py': [Errno 2] No such file or directory
  ```
- Sentinels: no `FIT_PASS` or `ROTATION_DONE` observed.
- Budget choice, selected epochs, updates, and stage costs: unavailable; the
  runner never started.
- Warnings: execution directory mismatch. The `PRETRAIN_CHECKS.json` gate was
  PASS, but that did not establish training completion.

The attempt is recorded as failure; training was not relaunched.

## RECOVERED verification — FAIL (2026-10-17)

The original cwd-failure record above is preserved. The parent execution
receipt (`MAIN_TRAIN_EXECUTION.md`, monitor `mon_D2NY7AVB2ZSWYJNS`, parent
`bash_9`) records the recovered producer as `completed exit_code: 0`, with
all six `FIT_PASS 1 {eadro,diagmlp} {11,23,37} 200` sentinels and
`ROTATION_DONE 1 200`. This establishes the producer's actual exit 0; it is
not a checker exit code.

Read-only artifact inspection found `rotation_1.started.json`,
`rotation_1.budget.json`, `rotation_1.done.json`, and six run directories.
The frozen records identify plan SHA-256
`5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470`,
input SHA-256
`ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`,
and the frozen source hashes/configuration in each run config and done
receipt. The six stage summaries report PASS, 200 epochs, 1,000 updates,
and best epochs/NLL:

| Model | Seed | Best epoch | Validation event NLL |
|---|---:|---:|---:|
| eadro | 11 | 4 | 2.4848583739144106 |
| eadro | 23 | 1 | 17.958124542108763 |
| eadro | 37 | 1 | 2.774638360183085 |
| diagmlp | 11 | 31 | 1.9445361614042669 |
| diagmlp | 23 | 70 | 2.063366396988239 |
| diagmlp | 37 | 13 | 2.1776616504660176 |

The corresponding full 200-entry histories exist; spot checks at the
reported best epochs match the summaries. All recorded best epochs are below
180, so the recorded same-rotation extension rule does not trigger. Configs
state the frozen selection rule (minimum validation event NLL of mean window
probabilities; earliest tie), and `evaluation_opened` is false.

**Verdict is FAIL for this verification request:** the required independent
read-only checker was not run, so no checker exit 0 exists. In particular,
this session did not recompute the minimum/earliest-tie across every entry of
all six histories or independently hash-check every config/history/best/last
artifact against its source and input receipts. A direct attempt to read
`runs/rotation_1/diagmlp/seed_11/last.pt` returned ENOENT; the done receipt
contains a `last_sha256`, but that alone does not prove the file's presence
or matching content. Therefore the producer exit 0 and supporting recorded
summaries do not satisfy the requested independent artifact verification.
No training, preparation, evaluation, or other process was started for this
receipt.
