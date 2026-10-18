# 257차원 원형 HawkesADM4 제한 비용 측정 — 2026-10-18

## 결과와 fit 상태

**동일한 TRAIN 5사건·10창·14노드의 단회 측정 완료.**
140개 위치 중 완전 빈 그룹 58개는 257차원 0벡터, 비어 있지 않은 82개는
정확한 knot 중복 1개를 제외한 **81회 적합 모두 성공**했다.
실패·timeout·jitter 실패·경고·예산 미실행은 각각 0개다.
81개 baseline 모두 float64 `(257,)`, finite·nonnegative 검증을 통과했다.

| 항목 | 실측 |
|---|---:|
| 최대 worker / BLAS·native thread | 4 / 각각 1 |
| 배치 wall: 새 worker 프로세스 시작·종료 포함 | 42.500158초 |
| 실제 배치 처리량 | 1.905875 fits/초 |
| solver 초: 최소 / 중앙 / 평균 / 최대 | 0.236563 / 1.114554 / 1.247084 / 2.678687 |
| 프로세스 초: 최소 / 중앙 / 평균 / 최대 | 0.993686 / 1.868092 / 2.032730 / 3.466922 |
| solver 시간 합 / 프로세스 시간 합 | 101.013812 / 164.651110초 |
| native 기록 반복 수 → fit 수 | 11→23, 21→14, 31→6, 41→2, 50→36 |
| 반복 상한 50 도달 | **36/81** |
| 부모 peak RSS / 개별 worker 최대 peak RSS | 48,516 / 97,200 KiB |

메모리는 각 프로세스 peak이며 동시 전체 메모리 peak를 합산·추정하지 않았다.
상한 미도달 45개도 최적해 수렴을 입증한 것은 아니다. 원형 기록 규칙 그대로다.
상한 도달 fit을 버리거나 tol·반복 수·초기값·solver를 바꾸지 않았다.

## 실제 입력과 실행 경계

frozen TRAIN 빈도 매핑과 사전 선택을 해시 확인한 후 선택된 TRAIN 캐시
5쌍만 읽었다. 이벤트 id만 재매핑하고 pinned 원형 `make_knots`/`fit_hawkes`
함수 AST를 변경 없이 실행했다. absent bin `[0]`, 이벤트별 `1e-5` jitter,
완전 빈 그룹 0을 유지하며 clipping·기존 baseline 재사용은 없다.
설치 원본 ADM4(decay 3), seed 42, baseline 시작 .2, native random
257×257 adjacency 및 모든 기본값을 유지했다.

아래는 선택된 10창의 서비스별 합계다. 각 서비스 10개 위치와 창별
raw/kept/pooled/unknown·key·empty/reused·fit 상태는 JSON에 모두 저장했다.

| 서비스 | raw | kept | newly pooled | old unknown | 빈 위치 |
|---|---:|---:|---:|---:|---:|
| adservice | 648 | 648 | 0 | 0 | 1 |
| cartservice | 1,104 | 1,099 | 0 | 5 | 1 |
| checkoutservice | 111 | 111 | 0 | 0 | 1 |
| currencyservice | 3,364 | 3,364 | 0 | 0 | 1 |
| emailservice | 37 | 37 | 0 | 0 | 1 |
| frontend | 3,850 | 3,850 | 0 | 0 | 1 |
| frontend-external | 0 | 0 | 0 | 0 | 10 |
| frontendservice | 0 | 0 | 0 | 0 | 10 |
| istio-init | 0 | 0 | 0 | 0 | 10 |
| paymentservice | 74 | 2 | 0 | 72 | 1 |
| productcatalogservice | 0 | 0 | 0 | 0 | 10 |
| recommendationservice | 808 | 5 | 28 | 775 | 1 |
| redis | 5 | 0 | 0 | 5 | 9 |
| shippingservice | 632 | 632 | 0 | 0 | 1 |
| **합계** | **10,633** | **9,748** | **28** | **857** | **58** |

정확한 중복 재사용 1개는 emailservice다. 행 수는 모든 위치에서 보존됐다.
빈 서비스의 기타 비율은 분모 0으로 결측이다. 전체72건 서비스별
TRAIN/validation·주입 전후 집계는 기존 `coverage.json`을 그대로 인계했다.
이는 이번 validation 캐시 열람이나 적합을 뜻하지 않는다.

## 비용 판정과 한계

전체48/24의 **91,060개 원형 비어 있지 않은 위치**를 상한 작업 수로 놓고
이번 실측 배치 처리량을 그대로 가정하면, 중복 제거 없는 시나리오는
**47,778.573초(13.272시간)**다. 이는 7,200초보다 크므로 현재 근거로
전체 실행이 예산 내 가능하다고 승인할 수 없다.
새257차원 전체 고유 입력 수와 전역 비용·validation 비용은 **미확인**이다.
이전 원형의 80,028 고유 입력을 새 실측값으로 쓰지 않았고,
표본의 중복률을 전체에 적용하거나 이론적 4배 성능·전역 CI를 주장하지 않는다.

257은 frozen 후보1,024개 중256개+기타1의 표현이다. 1,025는 이 frozen
템플릿 상한/unknown 배치의 차원이지, Hawkes 이론의 필수 차원이나
데이터 전체 고유 로그 종류 수로 확인된 값이 아니다.
표본 recommendationservice는808행 중28행을 새로 합병하며 기존 unknown
775행과 함께 기타가803행이다. paymentservice도74행 중72행이 기존 unknown이다.
희귀 template 구별 소실, unknown 혼합, jitter·placeholder·이벤트 과정 및
후속 정규화 변화 때문에1,025특징과 동등한 기준선은 아니다.
진단 성능의 개선·저하는 측정하지 않았다.

## 예산과 보존한 실패 이력

| 지출 | 실제 wall |
|---|---:|
| 이전 coverage 집계 | 17.462268967초 |
| 이전 handoff 실패 producer (exit 1, 실제 fit 0회) | 0.166154484초 |
| 이번 선택 입력 집계·검사 | 0.770631833초 |
| 이번 producer 내부 전체 | 43.562826405초 |
| 이번 producer 외부 측정: 시작·종료 포함 (exit 0) | 43.793464433초 |
| coverage + 이전 실패 + 이번 producer 외부 wall | **61.421887884초** |

배치900초·fit당60초·집계+측정1,800초 상한 모두 준수했다.
내부 전체/배치/선택 집계는 서로 포함 관계이므로 다시 합산하지 않는다.
코드 검사 시간은 `checks.json`에 별도로 기록했다.
이전 중복 producer의 미확정 지출을 0으로 간주하지 않는다.

최초 producer는 `MAPPING.md`가 `27e830d7…012782`에서 아래의 검토된
`711c3e41…41b46`으로 설명 수정된 뒤 handoff 해시 불일치로 종료했다.
당시140개 위치 모두 미실행인 `benchmark.json`과 `fits/` 전체9개 파일을
**10개 모두 바이트 단위 보존**했다. 과거 import guard 실패3건
(`/dev/null`, 임시경로 탐색, matplotlib 캐시 쓰기 차단)도 그대로다.
이전 mapping producer의 validation 메타데이터 선행 열람 이력은
`RECOVERY.md`대로 유지하며, 이번 복구로 과거 경계 이력을 지우지 않는다.
최신 복구 승인에 따라 문서 pin과 고정 출력 경로만 변경하고 solver는 건드리지 않았다.

## 검사·산출물·SHA-256

합성 테스트 **7개**, 명시적 Pyright **0 errors / warnings / informations**,
설치 원본 defaults·handoff 사전검사 모두 **exit 0** 후에 실제 실행했다.
두 소스의 LSP diagnostics도 없었다. 테스트는 실제 적합 없이 mapping→원형
knot, empty/pooled jitter 경계, exact dedup, cap/timeout, 이전 출력 차단을 검사했다.
producer **exit 0**, 모든 fit 프로세스 **exit 0**, 저장 입력·baseline·원본 해시
검증 **exit 0 / PASS**다. 저장 산출물575개를 해시 확인했고 재적합하지 않았다.

| 파일 | SHA-256 |
|---|---|
| `benchmark.py` | `aa136a9830758d30eed456b1732dec7f9d6d9de7de412ce37d786eeddc7f71f8` |
| `test_benchmark.py` | `0ca49a1e478b9d48a1b10af600ade21b505e95f816c2a827efd189e7c82af726` |
| `mapping.json` | `a9bf14fd115d55c040c1d7a30b376411f722ef6ef12f3fa3eaf7f12d4f9b006a` |
| `selection.json` | `6b7be4278e61e6752aa8c65b15b7d58b76f227ee7738e4be33788b4e9af399e9` |
| `coverage.json` | `78a76b05fa54cd9b9a3cc92e15adb8e7d86f7ef39dd8a33ff1a1d10d35fd7181` |
| `MAPPING.md` | `711c3e41334efa1c798ee47ef6606afd9aae670841db59b7ff156ef32ff41b46` |
| 원형 `native_data.py` | `05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986` |
| 설치 `hawkes_adm4.py` | `0546b62509c79736e570b4caee78c4766daead25020001bdf13ae963eb0b9ecb` |
| `benchmark_recovery.json` | `716fa43170544445e68084949d402b371e69b66abf69dbd677656e377bd33fa9` |
| `fits_recovery/verification.json` | `33b3f44e40820f2f77f59a0f5621ae350e411b9577ce994d4948c938e1389a47` |

`benchmark_recovery.json`와 `fits_recovery/`에 sentinel, 실제 exit,
81개 입력·baseline·결과·로그, 명령/params, 입력 캐시10파일·knot·원본/설치
모듈 해시, 전후 불변성, 읽기 guard, peak memory를 배타 생성했다.
`cost-summary.json`은 수치 집계와 과거10파일의 전후 해시를 보존한다.
기존1025차원 cache 벡터3개는 읽거나 새 특징으로 재사용하지 않았다.
보호18건 관측·예측, raw, old54 fitted state는 열지 않았고,
1025/validation fit·신경망·전체 전처리·설치·다운로드·project commit은 하지 않았다.
원본/캐시 불변성과 producer·worker 종료를 확인했으며 후속 실행 없이 종료한다.
