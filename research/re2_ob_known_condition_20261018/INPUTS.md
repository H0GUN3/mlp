# Fresh48/24 input preparation handoff — measured cost stop

## 주 담당 보완 실측 — 2026-10-18

**현재 중단 이유는 비용이며 `frontend-check` 문제가 아니다.**
원래 템플릿과72사례 매칭·프로파일을 해시 검증해 재사용하는 CLI는
부모 `mon_JZ1PFGXXRPQP2WSY` / `bash_14`에서
`CACHED_PROFILE_VERIFY_EXIT=0`으로 종료했다. 최초 명령의 exit와 혼동하지 않는다.

첫 측정1개에서 예산 초과로 중단된 추정을 보완하려고, 이미 선택 규칙에 있던
첫 사례의 중간·최대 knot-size 입력2개만 추가 측정했다.
새 neural model 평가·학습, 전체 Hawkes 준비, 특징·반복 상한 변경은 하지 않았다.
원래 profile.json은 불변이다.

| 표본 위치 | 실제 시간(초) | iteration / 상한 | 원래 결과 재사용 |
|---|---:|---:|---|
| 작은 입력 | 11.410172 | 11 / 50 | 예 |
| 중간 입력 | 14.278112 | 21 / 50 | 아니오 |
| 큰 입력 | 43.526409 | 50 / 50 | 아니오 |

세 실행의 warning 목록은 비어 있지만, 마지막 실행은 iteration 상한에 도달했다.
수렴을 인증하지 않는다. 평균 시간으로80,028개를 단순 외삽하면
**4작업자 약128.22시간**, 최대 표본 시간 외삽은 **241.90시간**이다.
이는 첫 사례의3표본만 이용한 거친 추정이며 보장 시간이나 통계적 구간이 아니다.
작업자를16개로 늘려도 이상적인 선형 가속을 가정한 평균 외삽은 약32.06시간이다.
실제 병렬 가속과 다른 사례의 비용은 미측정이다.

보완 명령:
`.venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.cost_supplement`
는 `mon_A3RK1H4K7H20CP8F` / 부모 `bash_15`에서
`COST_SUPPLEMENT_PASS`, exit0으로 종료했다. 자체 선택 검사와 LSP 오류0을 확인했다.
정확한 측정값·해시는 `artifacts/cost_supplement.json`에 있다.

이 정도 비용의 전체 실행이나 로그 표현 변경은 자동 진행하지 않는다.
72사건·48/24·보호18과 이미 만든 새 TRAIN48 산출물은 유지한다.
현재 완성 bundle 및 실제 DiagMLP 학습 결과는 없다.
이하 첫 표본의63.4시간 기록은 당시 측정 이력으로 보존한다.

## Final status — 2026-10-18

**`STOP_COST`; no complete bundle is claimed.**

The repaired 48/24 split, exact `frontend-check` role exclusion, all 72
fitting-free stage1 cases, frozen TRAIN-only Drain state, and all-case log
matching passed their gates. The unchanged native Hawkes preparation did not
fit within the fixed two-hour budget:

- frozen events: 1,025, including unknown bin 0;
- nonempty case/node/window groups: 91,060;
- unique relative Hawkes inputs: 80,028;
- measured probe: 11.410171868 seconds, 11 iterations, 0 warnings;
- estimated four-worker fit time: 228,283.308564 seconds;
- authorized budget: 7,200 seconds.

The estimate is about 63.4 hours at four CPU1 workers, 31.7 times the allowed
budget. No case, feature, template, iteration, or solver setting was reduced.
`artifacts/bundle.npz` and `artifacts/input.json` do not exist. This satisfies
the task's concrete-blocker stop condition, not its successful-bundle condition.

## Actual commands, exits, sentinels, and processes

Focused fixtures and diagnostics:

```sh
cd /home/gnho1236/r2 &&
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m unittest -v \
  research.re2_ob_known_condition_20261018.test_prepare &&
/home/gnho1236/.local/bin/pyright \
  --project research/re2_ob_known_condition_20261018
```

Actual result:

```text
Ran 9 tests in 0.040s
OK
0 errors, 0 warnings, 0 informations
FIXTURE_DIAGNOSTIC_ACTUAL_EXIT=0
```

Both assigned Python files also had zero LSP diagnostics. The synthetic native
Hawkes fixture took 0.003199 seconds, used 11 iterations, and emitted no warning.

The already-running profile producer was adopted rather than duplicated:

```text
timeout PID 1551779
profile PID 1551780
EXISTING_PROFILE_EXITED pid=1551780
monitor exit 0
```

It exclusively created all 72 matched JSON/NPZ pairs, one Hawkes probe
JSON/NPZ pair, and `profile.json`. The checkpoint is bound to the current
split, role policy, source/case/member inventory, and frozen snapshot hashes.

Required full CLI:

```sh
cd /home/gnho1236/r2 &&
timeout --signal=TERM --kill-after=30s 7200s \
  env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B \
  -m research.re2_ob_known_condition_20261018.prepare
```

Monitor `mon_SSRGS6JNS2M9NTK3` / session `bash_3`, PID 1598763:

```text
PREPARE_START pid=1598763 stage=prepare deadline_seconds=7200
PREFLIGHT_PASS pid=1598763 cases=72 nodes=14 windows=10273 overlaps=0
KNOWN_INPUTS_STOP {"error":"STOP_COST: measured unchanged native Hawkes exceeds two-hour budget",...}
FULL_PREPARATION_ACTUAL_EXIT=1
watcher exited_1 (exit code 1)
```

The gate stopped after 2.062819112 seconds by reusing and revalidating the
completed cost profile. PIDs 1551780 and 1598763 were absent in the final audit.
`artifacts/failure-1598763.json` preserves the actual stop.

## Verified input contract

| Partition | Cases | Windows | Normal | Fault | Retained log rows | Missing metric cells |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 48 | 6,817 | 3,456 | 3,361 | 7,997,702 | 2,089,953 |
| validation | 24 | 3,456 | 1,728 | 1,728 | 3,993,414 | 1,092,997 |
| Total | 72 | 10,273 | 5,184 | 5,089 | 11,991,116 | 3,182,950 |

All 72 metadata hashes and 144 numeric/log member hashes matched the pinned
fitting-free manifest. The deterministic 48/24 assignment, whole-case
partitioning, labels, source/member provenance, local shapes, metric masks,
trace finiteness, and old/new partition provenance passed. No absolute interval
overlap or cross-part raw/stage1 member duplicate was found.

Final ordered candidates:

```text
adservice, cartservice, checkoutservice, currencyservice, emailservice,
frontend, frontend-external, frontendservice, istio-init, paymentservice,
productcatalogservice, recommendationservice, redis, shippingservice
```

The TRAIN observed-edge union plus self-loops contains 23 edges. Candidates
were not restricted to gold roots. Raw metric NaNs and the observation mask
remain stage1 values; no imputer or scaler was fitted.

## Exact role exclusion and retention evidence

The local role rule excludes only the exact independent node
`frontend-check`, in both partitions. It is separate from the frozen four
proxy identifiers. There is no alias merge, incident removal, or 48/24 resplit.
The official pinned v0.9.0 manifest identifies the name as the loadgenerator
init container; the dataset's exact release remains unconfirmed.

The actual excluded observation appears only in validation case
`re2ob_checkoutservice_loss_3`, whose 144 windows remain:

- observed metric cells: 544 across 28 windows;
- `mem`: 272 cells, all 2,854,912;
- `socket`: 272 cells, all 0;
- other six metric families: 0 cells;
- owned trace retained count: 0;
- nonzero owned trace latency cells: 0;
- excluded log rows: 0;
- observed edges containing the node: 0.

All 176,950 case log rows remain. In that case, `frontend` retains 63,439 log
rows, while `frontendservice`, `frontend-external`, and every other owned
observation remain separate and unmerged. The focused fixtures verify
exact-name-only exclusion, frontend preservation, owned span/log retention,
whole-case preservation, exclusion accounting, and rejection of any other
unexpected validation node.

## Frozen templates and cost profile

TRAIN48 strictly pre-injection template fitting:

- fitted log lines: 4,237,203;
- validation fit lines: 0;
- retained clusters: 1,024;
- event count with unknown bin: 1,025;
- clusters created: 339,038;
- clusters evicted at the unchanged native cap: 338,014;
- fitting time: 626.046300273 seconds;
- snapshot SHA256:
  `70c77a932c150cf47488a7fd3b1a0efc9abfde11856c30090c7584e1925b3072`.

All 72 cases were matched using the frozen snapshot. Matching and profiling
took 1,696.294516023 seconds and reached 617,108 KiB peak RSS. The projected
uncompressed bundle is 658,704,760 bytes; the conservative working-set bound is
4,127,794,280 bytes. The one native probe reached neither its 50-iteration cap
nor a warning. The profile is a cost estimate, not a convergence certificate.

## Resources and readguard

Preflight measurements:

- available memory: 115,905,572,864 bytes;
- free disk: 312,409,874,432 bytes;
- all staged numeric arrays: 128,647,888 bytes;
- largest staged numeric working set: 1,937,664 bytes;
- approved stage1 members: 63,466,514 bytes.

Readguard evidence from the hash-bound preflight:

```text
allowed_opens=770
denied=[]
protected_case_files_opened=0
raw_case_files_opened=0
old_state_files_opened=0
```

Fixtures also deny protected members, unapproved stage1 members, raw Parquet,
old stage2 state, unauthorized source writes, hardlinks, and symlink escapes.
No protected18 observation, raw case Parquet, old stage2 template/cache/
snapshot/checkpoint, runner, other dataset/model kind, final test, download,
install, training, commit, root/shared account, omo-native, or Notion access
was used.

## Final hashes

```text
prepare.py
16054c56d643db7e6046b0e2ef1789bf3a12172d239a064c0ecf837c5e35c7c3
test_prepare.py
eee66167966783395234a7c03a699b418982421e1c9797f2a2aeb95316851b5d
split.json
3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2
UNKNOWN_NODE.md
247966c8e0ac8df821ba2c1f8a11c9582cfd5f160aaa716b269330e76175a086
role policy
beefc91967df310e692707047aac8c98661ae205b1debb0b2104e4be1b64421e
source/case/member/split/policy binding
e65db027735a564075197173189bc7bdfb2672dd42401aae23370e5a7f8e534c
artifacts/preflight.json
264f5ca84c1fefa1855773478e97a71a4e314d4f71aad04af0ec68cde6caf101
artifacts/templates.json
8fbdd0cf419679294fe645cea1d3c66f81484ff1be7d59f6deb330d73b2b6b53
artifacts/drain.snapshot
70c77a932c150cf47488a7fd3b1a0efc9abfde11856c30090c7584e1925b3072
artifacts/profile.json
816970f164622661ea59c4ad1a057ec946f9583bca2adbf32311e60ff9249c78
artifacts/failure-1598763.json
bbe3437651ac23f1eabac0be364e914698ae9889b956f60b3378416591c0cfdb
```

## Preserved recovery history

The initial attempt stopped because `split.json` was missing. The split owner
later repaired and verified it; this preparer did not regenerate it. A later
preflight correctly stopped on validation-only `frontend-check` under the old
unknown-node contract. The user then explicitly authorized only the exact
role-based exclusion documented above. Historical `failure-*.json` and
`node-conflict-*.json` files remain untouched.

The recovered policy allowed preparation to proceed through all 72 matched
cases and measured native cost. The current blocker is therefore no longer the
split or node policy: it is the quantified, unchanged native Hawkes cost.
Resumption requires explicit authority to change the fixed budget or input/
algorithm contract; silently doing either would invalidate this run.
