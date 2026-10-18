# ADM4 영구조 비용·수치 검토

## 상태

**대표 5개 저장값 보존: 통과. 전체 요청·운영 적용 승인: 불통과/보류.**
실제 비교 CLI는 exit0으로 끝났고 5×1025 float32 원소가 비트 단위로
동일했다. 하지만 첫 표본 profile 저장 실패 때문에 엄격한 전체 요청
충족을 성공으로 판정할 수 없다. 비용도 원래7200초 예산을 초과한다.
기계 판정은 `benchmark.json`의
`REPRESENTATIVE_NUMERICS_PASS_PROTOCOL_INCOMPLETE`,
`strict_request_satisfied=false`, `affordable_firstcase_extrapolation=false`다.
원본 `artifacts`, 원본 코드 및 설치 패키지는 수정하지 않는다.

## 고정 계약과 선택

48 TRAIN / 24 validation / protected18, 1025차원, seed42,
HawkesADM4(decay=3), baseline 시작값 .2, 원래 랜덤 adjacency,
ADMM z/u=0, max_iter50, tol1e-5, inner EM30, 원래 기록 주기를 유지한다.
원본 함수를 AST 단위로 그대로 실행해 pandas/Drain을 쓰는
`native_data` 전체 모듈 초기화를 피한다. 새 원자료 읽기, Drain 학습,
템플릿 축소, 신경망 실행은 하지 않는다.

`probes/selection.json`은 solver 실행 전에 고정했다.
첫 사례는 기존 `re2ob_checkoutservice_cpu_1`의 저장된 세 key다.
교차 사례는 TRAIN48 중
SHA256(`cost-preserve-20261018:` + case) 순서로 서로 다른
root/fault 조합을 골랐다:
`re2ob_emailservice_socket_1`, `re2ob_currencyservice_loss_1`.
각 교차 사례의 사전 정렬된 첫 비어 있지 않은 `(window,node)`를 쓴다.
gold/error 기반 선택이 아니다. 전체72 knot 재조사는 하지 않았다.

## 반드시 보존하는 실패

- 선택 CLI: monitor `mon_XESDPMNZ709MT026`, `NUMERICS_SELECT_EXIT=0`,
  `NUMERICS_SELECTION_PASS`.
- 첫 원본 profile: monitor `mon_4YH7K211NX466CNP`, PID1636157,
  exit1, 12.996745117초. fit 후 pandas import 금지 assertion에서
  실패했다. 이 fit은 추가 원형3회 한도에 포함하며 재실행하지 않는다.
  cProfile 및 baseline은 그 assertion 앞에서 메모리에만 존재했고
  저장되지 않았으므로, 첫 표본의 계측치를 복구했다고 주장하지 않는다.
  `probes/completion-profile-0.json`에 실제 stderr/command/PID/exit가 있다.
- 기본 tick import는 `tick.base_model.ModelLabelsFeatures` 경유
  `tick.preprocessing`에서 pandas를 자동 import한다. 직접 pandas 코드는
  없었지만 첫 실행의 전이 import는 금지조건을 충족하지 못했다.
- pandas import 차단 검사: `mon_0CE7P547YKCMPZDF`, exit1.
  부분 namespace 분리 검사: `mon_Q9MHWWPMWYVXZKEG`, exit1.
  잔여 경로 추적: `mon_1Q52Z92HGCQJ6C6B`, exit1.
  `probes/import_audit.json`, `probes/import_isolated.json`에 경로를 보존했다.
  이 검사들에는 solver fit이 없다.
- 최초 타입 검사 `mon_13DPSR1FHVC78MSN`: exit1, 3 errors.
  동적으로 선택한 기반 클래스와 설치 tick의 range 타입 주석 문제였다.
  명시적 서브클래스와 원본 range setter 사용으로 수정했으며
  오류를 숨기거나 tolerance를 변경하지 않았다.
- 첫 artifact verifier `mon_MK0T14Y9BWG1B6P9`: exit1.
  `read_guard.denied`의 **차단된** `.pyc` 탐색을 실제 입력 열기로
  잘못 분류했다. Python `-B`는 쓰기를 막지만 존재하지 않는 bytecode
  파일의 읽기 탐색까지 막지 않는다. guard가 정확히
  `cost_preservation/__pycache__/equivalent_backend.cpython-38.pyc`를
  차단하고 Python이 원본 `.py`로 fallback한 것이다.
  guard는 수정하지 않았고, verifier에서 이 경로가 정확히1개이며
  존재하지 않는지를 검사하도록 고쳤다. 다른 거부 경로는 여전히 실패다.
  `probes/verification-initial-failure.json`에 실패를 보존했다.

## 실제 병목

첫 표본 재실행 대신 이미 승인된 교차 reference 1회에 cProfile과
원본 연산을 그대로 호출하는 래퍼를 붙였다.
`probes/reference-3.json` 및 `completion-reference-3.json`,
monitor `mon_V2FC632CGGTWBV2G`, PID1642116, exit0,
`NUMERICS_CROSS_PROFILE_COMPLETE`가 실제 완료 근거다.

대상은 `re2ob_emailservice_socket_1`, window0/node0(adservice),
key `256ced53930466b4aae8c50dfb20e03dcebd1d42b5e8bad35b0522a86a7d0f3f`.
31 outer iterations, 367 native EM solve 호출, warning0,
fit 타이머 **35.591710초**다.

| 원본 실제 성분 | 시간 | 해석 |
|---|---:|---|
| NumPy SVD 39회 | 23.928487초 | fit의 약67.2%; prox31회 + value8회 |
| prox SVD | 20.490257초 | 위 SVD 총시간의 부분집합 |
| value SVD | 3.438231초 | 초기 조밀한 objective 포함 |
| ndarray.dot 62회 | 4.798초 | 원본 prox의 두 행렬곱 × 31회 |
| native HawkesADM4_solve 367회 | 3.432초 | C++ EM 계산 |
| relative_distance 742회 | 1.350초 | 누적시간; norm 등을 포함 |
| 원본 nuclear prox 전체 | 25.561351초 | SVD/행렬곱 포함, 위 항목과 더하면 중복 |
| 원본 nuclear value 전체 | 3.473028초 | SVD 포함 |

모든 prox 입력은 1025×1025이고 비영 열은1025개다.
첫 prox의 비영 행5개, 이후30회는8개다. value는 초기 한 번
1025행/1025열 모두 비영, 이후7회는5행/1025열 비영이다.
원본 SVD에서 발생한 미세 비영 값도 **0으로 간주하지 않는다**.
정확히0이 아닌 행은 모두 유지한다.
초기 조밀한 value 호출은 **0.462031초**이고 삭제·가짜 objective·
랜덤 초기값 변경은 하지 않았다.
모든 호출별 counts/time은 JSON `records`, 모든 SVD의 shape/time은
`svd_records`, 함수별 프로파일은 `cprofile` 필드에 남아 있다.
이 계측은 첫 사례의 대체 실측이라고 주장하지 않는다.

## pandas 없는 원본 로딩

`probes/native_runtime.py`는 설치 파일의 수치 함수나 클래스를 복사하지 않는다.
미사용 pandas 의존 클래스까지 일괄 import하는 package initializer 대신
필요한 namespace를 구성하고, 실제 `Model*`, `Solver`,
`LearnerHawkesNoParam`, simulation, HawkesADM4 모듈을 설치 경로에서 읽는다.
ADM4 클래스의 `__module__`은 원래
`tick.hawkes.inference.hawkes_adm4`이며 `_solve`를 재구현하지 않았다.
이 격리는 benchmark 전용이고 다른 프로세스/원래 pipeline에 적용하지 않는다.
원형/후보 모두 같은 격리 로더를 쓴다.

`mon_V39M3A5F8413RKFG`: `NUMERICS_NATIVE_IMPORT_PASS`,
`NUMERICS_MINIMAL_IMPORT_EXIT=0`.
완료된 교차 reference와 최종 작은 fixture에서 pandas 미로딩을 확인했다.
첫 실패 실행에서 pandas가 전이 import된 사실은 이 후속 성공으로 지우지 않는다.

## 집중 검사

- 최초 fixture: `mon_D2MJAAPCJRVK7P08`, 9 tests, exit0.
- 최종 fixture: `mon_938JDF5BQM1TG40Q`, **10 tests / 0.150초 / OK**,
  `NUMERICS_UNIT_TESTS_PASS`, `NUMERICS_FINAL_TEST_EXIT=0`.
  결과는 `probes/unit-tests-final.json`; 최초 결과도 보존했다.
- 직사각형/모두0/0행·0열/조밀 fallback/음수 원소/positive/range/out alias/
  threshold 정확한 경계/1e-200 비영 보존/음의 threshold fallback/
  float32 입력 fallback/잘못된 shape/NaN 원본 오류를 검사했다.
  value는 원본과 같이 **전체 입력이 직사각형이면 거부**한다.
- 고정 float64 fixture 허용치는 `atol=rtol=5e-14`; 실행 후 변경하지 않았다.
  관측한 fixture 최대절대차는 prox `3.553e-15`, value `8.882e-16`이며
  작은 ADM4 baseline은 float64에서도 정확히 같았다.
  작은 4차원 ADM4 원형/후보 1쌍도 default 반복·기록 조건 그대로 비교했다.
  이것은 실제1025차원 적합 한도에 해당하는 추가 실사례가 아니다.
- 최종 타입 검사 `mon_JWRMHB5ES9T4MN1S`: 원래 프로젝트
  `pyrightconfig.json`을 명시하여 새 코드4개를 검사,
  **0 errors / 0 warnings / 0 informations / exit0**.
  LSP 자동 루트에서는 설치 tick/local import를 못 찾는 진단이 남았으므로
  “LSP도 0”이라고 주장하지 않는다. 기존 설정의 명시적 CLI 결과를 사용한다.
- 기존 pipeline 전체 테스트는 재실행하지 않았다.
  기존 `INPUT_VERIFY.md`의27 tests 및 기존 Pyright 결과는 역사적 검증이며,
  이번 후보가 실제 작동한다는 근거는 이번 집중 검사와 실제 비교뿐이다.

## 실제 5개 저장값 비교

결과 비교는 각1025차원 **전체**를 대상으로 한다. `np.array_equal`과
float32 `tobytes()` 일치 둘 다 검사했다. fixture의 작은 허용 오차를
실제 특징값 판정에 사용하지 않았다.

| 입력 | 원형초 | 후보초 | 가속 | outer iter 원형=후보 | float64 최대절대차 |
|---|---:|---:|---:|---:|---:|
| 첫 사례 small, window20/node2 | 11.410172 | 1.586255 | 7.193배 | 11 | 0 |
| 첫 사례 middle, window12/node0 | 14.278112 | 3.545019 | 4.028배 | 21 | 1.277e-15 |
| 첫 사례 large, window17/node5 | 43.526409 | 19.542496 | 2.227배 | 50 | 3.003e-14 |
| email/socket, window0/node0 | 35.591710 | 7.458152 | 4.772배 | 31 | 3.331e-16 |
| currency/loss, window0/node0 | 22.267443 | 3.078095 | 7.234배 | 21 | 1.110e-16 |

**5/5 float32 배열·bytes 동일, 불일치 index 없음, 모든 경고 목록 `[]` 동일.**
large는 원형/후보 모두50회 상한에 도달했다. 동일한 상한 도달이지,
추가 수렴이나 최적해를 입증한 결과가 아니다.
float64 배열 전체의 비트 일치는 small만 통과했고 나머지4개는 다르다.
“동일”의 실측 판정 대상은 계약된 최종 float32 특징이며,
float64 상태/adjacency 전체가 같다고 주장하지 않는다.

첫 사례3개 원형 baseline은 원래 float64 NPZ와 metadata를 그대로 재사용했다.
캐시 metadata의 window/node=0은 `cached_fit`의 실행용 placeholder이며
실제 입력 위치는 이번 `selection.json`에서 matched→make_knots로
복원한 위 위치다. seed는 항상42이고 위치에 따라 바꾸지 않았다.

### 정확한 knot key

| index | case | key |
|---|---|---|
| 0 | re2ob_checkoutservice_cpu_1 | `02da892953b24a791b942ca0957f01146803ffbd4cb15c90649bd821420ea769` |
| 1 | re2ob_checkoutservice_cpu_1 | `8ec3888e3d3f4a338ef633f9ff119eed95604cbf2c2807e353dec762003240c6` |
| 2 | re2ob_checkoutservice_cpu_1 | `a28ca4be74f07bed0c393a3bc88deb773caa1e618c5b4b39add372759990dbb1` |
| 3 | re2ob_emailservice_socket_1 | `256ced53930466b4aae8c50dfb20e03dcebd1d42b5e8bad35b0522a86a7d0f3f` |
| 4 | re2ob_currencyservice_loss_1 | `c7a77521fb6a18c0fde4af23045c1b905d523d2a2e0b9918434a3391556500a5` |

각 knot JSON 자체 SHA256, matched NPZ/metadata SHA256, split/policy/
input binding/snapshot hash도 선택 파일에 묶었다. 첫 사례는 validation이지만
기존 지정3개 probe를 그대로 유지한 것이며, 추가2개는 TRAIN이다.

### 후보 fastpath와 매 반복 구조

| index | prox fastpath / 전체 | prox 비영행×비영열 | value fastpath / 전체 |
|---|---:|---|---:|
| 0 | 11/11 | 0×0 | 3/4 |
| 1 | 21/21 | 5×1025 | 5/6 |
| 2 | 50/50 | 12×1025 | 11/12 |
| 3 | 31/31 | 5×1025 | 7/8 |
| 4 | 21/21 | 5×1025 | 5/6 |

prox 총134/134, value 총31/36이 영구조 경로다.
value의 나머지5회는 **매 fit 초기의 조밀한 랜덤 adjacency**이며
원본 SVD로 fallback했다. 초기 nuclear value는 원형 교차 profile과
각 후보 모두 `1.9639756064568241`로 같았다.
value의 실제 비영열 수는 large에서1024/1025,
currency에서512/743/1025로 변한다. 이 변화도 매 호출 `records`에 남겼다.
행렬 전체는 끝까지1025×1025이며 compact SVD 결과를 같은 위치에 확장한다.
0에 가까운 값에 tolerance를 적용하거나 support를 미리 고정하지 않았다.

## 속도와 예산 판정

| 표본 범위 | 원형 평균 / 최대초 | 후보 평균 / 최대초 | 평균시간 비율 |
|---|---:|---:|---:|
| 첫 사례3개 | 23.071565 / 43.526409 | 8.224590 / 19.542496 | 2.805배 |
| 교차 사례2개 | 28.929576 / 35.591710 | 5.268124 / 7.458152 | 5.491배 |

첫 사례3개 평균으로만 단순 외삽하면
`80,028 × 8.224590 / 4 = 164,549.375초 = 45.708시간`이다.
첫 사례 최대시간 외삽은108.607시간이다.
기존 평균 외삽128.220시간보다 줄었으나 **7200초(2시간) 예산에는 불충족**이다.
이 값은 전체 분포의 평균·통계적 신뢰구간·실제4-worker 처리량이 아니다.
샘플은 비무작위5개뿐이며 동일 CPU의 동시 paired 반복측정도 아니다.
원형 첫3개 시간은 기존 기록, 교차 첫 reference는 cProfile 오버헤드를
포함한다. 후보와 교차 reference 모두 구조 관찰 래퍼의 비용을 포함한다.
전체 parallel speedup이나 global CI로 해석하지 않는다.
BLAS/OMP/MKL/NUMEXPR/VECLIB 환경은 모두1,
native ADM4 n_threads=1을 유지했다.

추가 원형은 **실패한 첫 profile1 + 교차 reference2 = 3회**,
후보는 **5회**다. 총8개 실제 프로세스 벽시간은
**110.620549초**, 모두180초 제한 안에서 종료했다.
성공7개 solver 타이머 합은93.069170초이며 첫 실패 fit의 정확한
solver 시간은 소실됐다. 그 실패 프로세스 전체12.996745초를 포함하는
110.620549초를 보수적 예산 사용량으로 삼아15분 이내임을 확인한다.
작은 fixture의 전체 테스트 시간0.150초까지 더해도 여유가 있다.
후보 결과가 다르지 않아 수치 수정/허용치 탐색/추가 후보 fit은 하지 않았다.

## 실행·출처와 최종 인계

실제 작업 디렉터리는 `/home/gnho1236/r2`다. 실행한 CLI:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py select
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py profile
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py cross-profile
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/test_equivalent_backend.py unit-tests-final.json
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py run
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B research/re2_ob_known_condition_20261018/cost_preservation/probes/verify_artifacts.py
pyright --project research/re2_ob_known_condition_20261018/pyrightconfig.json research/re2_ob_known_condition_20261018/cost_preservation/equivalent_backend.py research/re2_ob_known_condition_20261018/cost_preservation/test_equivalent_backend.py research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py research/re2_ob_known_condition_20261018/cost_preservation/probes/native_runtime.py
```

`profile`은 실패 기록이며 재실행하지 않았다. 최종 `run`은 monitor
`mon_J2YJWK8G84YB2JSM`, **exit0**,
`NUMERICS_BENCHMARK_COMPLETE REPRESENTATIVE_NUMERICS_PASS_PROTOCOL_INCOMPLETE`
및 `NUMERICS_BENCHMARK_EXIT=0`으로 끝났다.
이 sentinel은 **실험 종료**이지 전체 프로토콜 성공을 뜻하지 않는다.
`completion-*.json`에 각 PID, 전체 command, stdout/stderr, 실제 exit,
timeout 여부가 있다. 단순 백그라운드 launch를 완료로 취급하지 않았다.
JSON은 exclusive 생성이며 같은 실행을 재호출해 결과를 덮어쓰지 못한다.

추가 fit 없는 최종 artifact 재검산:
`mon_WP6BKW29D5YWYFMY`, `NUMERICS_ARTIFACT_CHECK_PASS`,
`NUMERICS_FINAL_ARTIFACT_CHECK_EXIT=0`.
결과는 `probes/verification.json`이며 benchmark JSON SHA256은
`0b12c598faff453324ad16d94642eff0b6e79fa50a2ced40adb6c1da02e0b52f`다.
보조 검사 코드 타입 검사도 `mon_R028EDPYFZWRV15V`,
수정 후 `mon_ZNMJXA11GT927306`에서 각각0 errors/0 warnings/exit0이다.
작업 종료 시 benchmark/검증 프로세스가 남아 있지 않음을 확인했다.

원형31개 파일의 전후 hash 동일:
원래 prepare/native_data/re2_stage2/ADM4/prox 소스, split,
template/snapshot, profile/supplement/preflight,
사용한 matched3쌍 및 원래 Hawkes3쌍을 포함한다.
후보5개와 마지막 reference에서는 로드된 tick90개 `.py`/공유라이브러리도
전후 해시를 확인했다. 읽지 않은 다른 파일까지 전부 해시 감사했다고
주장하지 않는다. 첫 실패 및 첫 교차 reference의 실험 래퍼 자체는
최종 버전과 다르며 초기 launch에는 래퍼 자체 hash가 없었다.
**설치된 수치 소스의 hash는 그때도 고정되어 있었고**
최종 후보와 마지막 reference의 실험 코드 hash는 launch에 보존했다.

결정: 실제 병목이 SVD였으므로 **정확한 영행/영열 compact SVD**를 선택했다.
원래 SVD 후0특이값 곱만 생략하는 대안은 주병목 SVD를 남기므로 이번에는
구현하지 않았다. solver 복사, objective 생략, tolerance/iteration 축소,
시각 반올림, 템플릿 축소·병합, 초기 adjacency 변경은 하지 않았다.

**운영 rollout은 하지 않는다.** 이번 항등식은 실수 연산의 근거이고,
5개 통과는80,028개 전체 bitwise 일치 증명이 아니다.
전체 적용 검증에는 별도 승인 아래 모든 실제 고유 knot 입력의
원형/후보1025차원 float32 정확 일치, iteration/warning, 입력 provenance,
전체 범위의 속도·메모리 및 병렬 처리량 검증이 필요하다.
현재 전체 원형 캐시도3개뿐이므로 그 검증 비용은 미측정이다.
이번 예산 안에서 수행하거나 자동 rollout하지 않았다.
첫 표본 profile 누락과 최초 pandas 전이 import의 프로토콜 미충족은
다음 담당자에게 명시적으로 남긴다.

## 수학적 후보와 적용 경계

유한 실수 행렬 X의 **정확히 0인** 행·열만 제거한다.
남는 좌표를 선택하는 직교 열행렬 P,Q에 대해
`X = P B Qᵀ`, `PᵀP = I`, `QᵀQ = I`이다.
B의 compact SVD가 `U Σ Vᵀ`이면
`(P U) Σ (Q V)ᵀ`는 X의 비영 특이성분을 나타낸다.
나머지 특이값은 정확히 0이므로 `||X||_* = ||B||_*`.
τ≥0일 때 `(σ-τ)·1[σ>τ]`는 σ=0을 0으로 보내므로
`prox_τ(X) = P prox_τ(B) Qᵀ`.
따라서 원래 크기로 0을 채워 되돌리는 연산은 실수 산술에서 같다.

이는 일부 템플릿을 모델에서 빼는 것이 아니다. 모델·초기 adjacency·
baseline·EM/ADMM 상태는 모두 원래 차원이다. 각 prox/value 내부에서
현재 입력에 실제로 존재하는 영구조만 검사한다.
`positive=True`의 원래 후처리 `max(x,0)`도 0 확장과 가환한다.
range 외부는 원래 `Prox.call`이 복사하므로 변경하지 않는다.
원래 value가 요구하는 전체 입력의 정사각형 조건은 compact 전에 검사한다.
음의 threshold, 비유한 값, 영구조 없는 행렬 등은 원본 연산으로 fallback한다.

SVD 차원과 합산 순서가 바뀌면 float64 결과는 달라질 수 있다.
위 실수 항등식만으로 float32 bitwise 보존 또는 80,028개 입력 전체의
동등성을 증명하지 않는다. 허용 오차를 사후 확대하지 않고,
실제 5개 입력의 1025개 float32 원소 전체 및 iteration/warning 일치를
별도로 확인해야 한다.
