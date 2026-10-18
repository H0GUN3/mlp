# 독립 검증 — bounded 257차원 비용 점검

## 판정

**복구된 제한 비용 측정과 저장 산출물 독립 검증은 통과했다.** 다만 이는
48/24 전체 실행이나 1,025차원 원형 비용을 측정한 것이 아니다. 현재 257차원
표본 처리량으로 91,060개 비어 있지 않은 위치를 중복 제거 없이 환산하면
47,778.573초(13.272시간)로, 7,200초 예산보다 6.64배 길다. 따라서 현재 증거로
전체 작업이 예산 안에 들어온다고 판단할 수 없다. 실제 전체 257차원 고유 knot
수는 미확인이고, 1,025차원 원형 solver 비용은 별도로 측정하지 않았다.

## 이력과 경계

- 첫 독립 검증 시점에는 upstream 산출물 여러 개가 없었다(`ENOENT`). 그때의
  `verification.json`과 “benchmark 미측정” 판정은 보존했다. 복구 산출물은
  이 결측 상태만 대체하며 과거 실패를 지우지 않는다.
- 최초 mapping 시도는 freeze 전에 validation matched-cache JSON metadata 한
  개를 읽었다고 기록하고 산출물 생성 전에 멈췄다. 그 이력은
  `RECOVERY.md`에 남아 있다. validation 배열, 보호 18건의 관측·예측은 열지
  않았다고 기록되었으며, 전체 이력에 누출이 전혀 없었다고 주장하지 않는다.
- 해당 metadata 확인 뒤에도 선택 규칙은 바뀌지 않았다. 복구 mapping은 frozen
  TRAIN 매칭 occurrence 중 `timestamp < inject_time`만으로 top-256을 산정하고,
  mapping 해시를 저장한 뒤 validation coverage를 집계했다. 기존 독립 검증의
  TRAIN count/top-256·선택·coverage 재계산은 동일한 mapping/selection/coverage
  hash에 한정해 재사용했다. 이 검증에서는 72개 cache를 다시 열거하지 않았다.
  기록된 cache guard는 명시적 loader 경계이지 OS 전체 감사기는 아니다.
- 최초 benchmark는 MAPPING.md prose hash가 기대값
  `27e830d7…012782`에서 검토된 `711c3e41…41b46`으로 바뀌어 fit 전에
  종료했다(exit 1; 140개 미실행, fit 0회). 수치 JSON hash는 그대로였다.
  실패한 `benchmark.json`/`fits/` 및 이전 `verification.json`을 보존했다.
  복구 run은 고정 입력과 선택으로 `benchmark_recovery.json` 및 `fits_recovery/`
  에 별도 생성됐다.

## 이전 검증 결과 재사용

기존 독립 검증은 당시 기록된 source/cache hash에서 다음을 재계산했고, 현재도
그 산출물 hash가 동일함을 확인했다.

- 48 TRAIN / 24 validation / 18 보호 건; frozen template 1,024개.
- 정확한 TRAIN pre-injection frequency, 내림차순 count 및 cluster_id 동률 규칙:
  top-256 일치. 선택되지 않은 768개와 기존 unknown 0은 pooled feature 0이며,
  차원은 257.
- 선택: TRAIN root 5개에서 hash 규칙으로 고른 사건, 정상/장애 창 각 1개씩
  총 10창, 창마다 14 services; 누락 층 없음.
- 72건 × 14 services × TRAIN/validation × pre/post의 56 coverage 셀과 행 보존:
  11,991,116행을 독립 집계와 대조해 일치. 각 셀은
  `total = kept + newly pooled + old unknown`; 분모 0 비율은 null.

## 복구 fits 독립 검사

검사 경로는 이전 72-cache 재계산 결과를 재사용하고, 이번에는 복구된 저장
산출물과 고정 manifest만 확인했다. 새 fit·재표본·validation fit은 실행하지 않았다.

| 검사 | 확인 결과 |
|---|---|
| 선택 위치 | 140 TRAIN 위치; 빈 위치 58, 비어 있지 않은 82 |
| Knot 중복 제거 | 정확히 같은 knot 1개 재사용; 고유 입력 81; knot 실패 0 |
| 실제 fit | 81/81 성공, fit별 process exit 0; 미실행 0 |
| baseline | 모두 float64 `(257,)`, finite 및 nonnegative; 개별 배열·결과 hash 일치 |
| solver 계약 | 설치된 원형 `HawkesADM4`, decay 3, seed 42, `max_iter=50`, `tol=1e-5`, native adjacency/초기화; compact-SVD 경로 없음 |
| fit 결과 상태 | warning 0, exception 0, timeout 0, hard kill 0 |
| 반복 수 | 11:23개, 21:14개, 31:6개, 41:2개, 50:36개 |
| cap / 수렴 | 50 반복 cap 도달 36/81. cap 미도달은 수렴 증명이 아니며 cap 도달도 최적해를 보증하지 않음 |
| resource 경계 | 최대 worker 4, 각 thread 1; fit 제한 60초, 관측 process 최대 3.467초 |
| immutability / provenance | 원본·입력·runtime 356개 immutable 경로, 331개 fit runtime 경로 및 저장 fit 출력 hash ledger 575개 대조 통과 |

140개 위치의 `raw = kept + newly pooled + old unknown` 보존과 빈 위치의 257개
0-vector도 확인했다. 18 보호 건, old54 fitted state, validation fits, 1,025차원
fits는 열거나 실행하지 않았다. `verification_recovery.json`에는 선택된 TRAIN
cache 5쌍의 hash, 핵심 source hash, 집계 수치 및 실제 exit가 있다.

### 실행 시간과 비용 환산

| 측정 | 값 |
|---|---:|
| 선택 window aggregation | 0.770632초 |
| 실제 fit batch wall (worker startup 포함) | 42.500158초 |
| batch throughput | 1.905875 fit/초 |
| solver 시간 합 / median / mean / max | 101.013812 / 1.114554 / 1.247084 / 2.678687초 |
| worker process 시간 합 / median / mean / max | 164.651110 / 1.868092 / 2.032730 / 3.466922초 |
| 복구 producer 전체 내부 wall / 외부 wall | 43.562826 / 43.793464초 |
| 이전 72건 coverage 집계 / 이전 실패 producer | 17.462269 / 0.166154초 |
| 이전 coverage + 실패 + 복구 producer 외부 wall | 61.421888초 |

91,060개 비어 있지 않은 위치를 모두 고유 fit이라고 두면, 관측 batch throughput
기준은 `91,060 ÷ (81 / 42.500158) = 47,778.573초`다. 관측 solver 초의
표본 median/mean/max를 단순 곱한 solver 총량 시나리오는 각각 약 101,491초,
113,559초, 243,921초다. process 초의 표본 min~max를 네 worker가 이상적으로
나눠 처리한다고 가정한 벽시계 범위도 약 22,621~78,924초다. 이는 측정 분포의
기계적 환산이지 통계적 신뢰구간이나 실행 보장이 아니다. 표본은 5개 TRAIN
root의 10개 창에 한정되고, 36개 fit이 반복 cap에 닿아 비용을 끝까지 수렴시킨
상태와 같다고 볼 수 없다.

7,200초 안에 들려면 현재 처리량 기준 고유 fit이 최대 약 13,722개(91,060개
위치의 15.07%)여야 한다. 표본에서는 82개 비어 있지 않은 위치 중 하나만
재사용되어 81개 fit이 필요했다. 전체 고유 knot 수와 중복률은 확인되지 않았고,
원형 80,028 unique 입력 수를 257차원 결과의 대용으로 쓰지 않았다. 이전 중복
producer 지출은 미확정이며 0으로 간주하지 않았다.

## Hash와 실제 종료 코드

| 산출물/source | SHA-256 |
|---|---|
| `mapping.py` | `d23cf7144ad5bbd2a8b3f8de1cf19bb047434fd12cd6d281e1b548ddd057b949` |
| `benchmark.py` | `aa136a9830758d30eed456b1732dec7f9d6d9de7de412ce37d786eeddc7f71f8` |
| `test_benchmark.py` | `0ca49a1e478b9d48a1b10af600ade21b505e95f816c2a827efd189e7c82af726` |
| `mapping.json` / `selection.json` / `coverage.json` | `a9bf14fd…9b006a` / `6b7be427…399e9` / `78a76b05…7181` |
| `MAPPING.md` | `711c3e41334efa1c798ee47ef6606afd9aae670841db59b7ff156ef32ff41b46` |
| 복구 `benchmark_recovery.json` | `716fa43170544445e68084949d402b371e69b66abf69dbd677656e377bd33fa9` |
| 복구 manifest | `ab0977a3a55847d502471fbabebbcc8d8038eb29cb4781b93691338668f780ba` |
| 원형 `native_data.py` | `05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986` |

| 단계 | 실제 exit |
|---|---:|
| 최초 benchmark handoff 실패 | 1 |
| mapping focused tests (4) / mapping Pyright / mapping aggregation | 0 / 0 / 0 |
| benchmark synthetic tests (7) / benchmark Pyright / runtime-default precheck | 0 / 0 / 0 |
| 복구 benchmark producer | 0 |
| 보존 산출물 verifier | 0 |
| 이번 독립 recovery checker | 0 |

전체 전처리, 원형 1,025차원 재적합, DiagMLP 학습·추론, 최종 시험은 실행하지
않았다. 검사와 비용 산정은 사용자가 승인한 257차원 제한 점검에서 종료한다.
