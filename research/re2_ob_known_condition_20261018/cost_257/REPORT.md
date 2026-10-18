# 257차원 비용 점검 — 결정 보고서

## 상황과 목적

이 점검은 로그 event 입력을 frozen 1,024개 template feature + unknown 1개에서
257차원으로 pooling할 때, 원형 HawkesADM4의 제한된 TRAIN 작업 비용과 표현
손실 범위를 확인했다. 48/24 전체 전처리, 1,025차원 재적합, 신경망 학습·추론은
승인 범위가 아니며 실행하지 않았다. 이 결과는 모델 정확도 평가가 아니다.

## 결정

**현재 실측으로는 48/24 전체 작업이 7,200초 안에 들어온다고 볼 수 없다.**
257차원에서 관측한 4-worker 처리량을 91,060개 비어 있지 않은 위치에 적용하고
중복 제거가 전혀 없다고 놓은 시나리오는 **47,778.573초(13.272시간)**로 예산의
6.64배다. 81개 fit의 sample min~max process 시간을 네 worker가 이상적으로
처리한다고 놓아도 이 작업량 환산은 약 22,621~78,924초다. 표본 82개 비어 있지
않은 위치 중 재사용은 1개뿐이었다.

이는 비용 가능성의 강한 경고이지 전체 비용의 상한 보증은 아니다. 전체 257차원
고유 knot 수·중복률은 미측정이며, 7,200초 안에 들려면 현재 throughput 기준
고유 fit이 약 13,722개 이하(전체 위치의 15.07% 이하)여야 한다. 전역 중복이
이 정도일 가능성을 이 작은 표본이 배제하거나 입증하지 못한다. 더구나 이
benchmark는 **257차원**이다. 원형 1,025차원 기준선의 비용은 이번 측정으로
확정할 수 없고, 257 비용 결과를 1,025 비용 측정처럼 해석해서는 안 된다.
따라서 원형 전체 기준선이 예산 안에 들 것이라는 근거는 없다.

## 방법과 실제 fit 상태

48 TRAIN에서 injection 전 frozen matcher occurrence만으로 빈도 상위 256개를
선택했다. 동률은 기존 cluster_id 오름차순이며, 선택된 feature는 cluster_id
오름차순으로 1–256을 부여했다. 기존 unknown 0과 미선택 768 template은 새 0으로
합친다. 이 mapping, 5개 TRAIN root 사건, 사건당 정상/장애 창 각 1개(총 10개)는
고정된 hash 규칙과 TRAIN 자료만으로 benchmark 전에 정해졌다. 창마다 14개
서비스를 유지했다.

| 측정 항목 | 결과 |
|---|---:|
| 위치 / 빈 위치 / 비어 있지 않은 위치 | 140 / 58 / 82 |
| 고유 knot fit / 정확한 재사용 | 81 / 1 |
| 성공 / 실패 / timeout / warning | 81 / 0 / 0 / 0 |
| batch wall / 처리량 (startup 포함) | 42.500초 / 1.906 fit·초⁻¹ |
| solver 초 median / mean / max | 1.115 / 1.247 / 2.679초 |
| worker process 초 median / mean / max | 1.868 / 2.033 / 3.467초 |
| 50 iteration cap 도달 | 36/81 |

81개 결과 모두 float64 `(257,)` finite/nonnegative baseline이었다. 반복 수는
11회 23개, 21회 14개, 31회 6개, 41회 2개, 50회 36개다. cap 미도달은
수렴 증명이 아니며 cap 도달은 최적해 보장이 아니다. 원형 설치
HawkesADM4(decay 3), seed 42, 기본 파라미터, native 초기화/adjacency,
원형 make_knots와 tie jitter를 유지했다. 최대 worker는 4, worker thread는
각 1, fit별 hard limit은 60초, batch 예산 900초였다. 복구 producer는 exit 0으로
43.793초에 끝났고, coverage 17.462초와 기존 실패 producer 0.166초를 포함한
기록 wall 합은 61.422초다. 이전 중복 producer 지출은 미확정이라 0으로 놓지
않았다.

선택된 10개 창에서 서비스별 fit 입력 행은 다음과 같다. `kept / pooled / old
unknown`이며 58개 빈 위치는 0 vector여서 solver를 호출하지 않았다.

| 서비스 | 원행 | kept | 새 pooled | 기존 unknown | 빈 위치 |
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

## 72건 coverage: service 및 split 차이

아래 각 셀은 `새 pooled / 기존 unknown; 전체 행; 기타 비율 (새 pooled distinct
template 수)`다. 기타 비율은 `(새 pooled + 기존 unknown)/전체`이며, —는 행이
없어 비율을 계산할 수 없음을 뜻한다. 이 값은 cached matched-row 집계이지
모델의 성능·영향 측정이 아니다.

| 서비스 | TRAIN 전 | TRAIN 후 | VAL 전 | VAL 후 |
|---|---|---|---|---|
| adservice | 0/0; 257,939; 0.000% (0) | 0/4; 227,719; 0.002% (0) | 0/0; 128,669; 0.000% (0) | 0/0; 117,845; 0.000% (0) |
| cartservice | 0/4,404; 442,096; 0.996% (0) | 0/3,975; 391,934; 1.014% (0) | 0/2,194; 220,466; 0.995% (0) | 0/2,121; 201,979; 1.050% (0) |
| checkoutservice | 0/0; 48,456; 0.000% (0) | 0/43; 42,898; 0.100% (0) | 0/0; 24,175; 0.000% (0) | 0/37; 21,855; 0.169% (0) |
| currencyservice | 0/0; 1,332,038; 0.000% (0) | 0/20; 1,176,263; 0.002% (0) | 0/0; 624,077; 0.000% (0) | 0/4; 590,162; 0.001% (0) |
| emailservice | 0/0; 16,154; 0.000% (0) | 0/25; 14,251; 0.175% (0) | 0/0; 8,059; 0.000% (0) | 0/22; 7,266; 0.303% (0) |
| frontend | 0/0; 1,527,680; 0.000% (0) | 0/2,924; 1,365,226; 0.214% (0) | 0/0; 763,449; 0.000% (0) | 0/605; 699,440; 0.086% (0) |
| frontend-external | — | — | — | — |
| frontendservice | — | — | — | — |
| istio-init | — | — | — | — |
| paymentservice | 270/31,396; 32,306; 98.019% (74) | 230/27,762; 28,510; 98.183% (26) | 124/15,660; 16,118; 97.928% (18) | 98/14,166; 14,554; 98.007% (16) |
| productcatalogservice | — | 0/43; 43; 100.000% (0) | — | 0/31; 31; 100.000% (0) |
| recommendationservice | 13,435/304,457; 322,393; 98.604% (689) | 12,281/269,662; 284,912; 98.958% (687) | 6,842/151,964; 160,545; 98.917% (682) | 6,273/140,724; 148,562; 98.947% (680) |
| redis | 5/520; 525; 100.000% (5) | 0/585; 585; 100.000% (0) | 0/285; 285; 100.000% (0) | 0/285; 285; 100.000% (0) |
| shippingservice | 0/0; 257,616; 0.000% (0) | 0/0; 228,158; 0.000% (0) | 0/0; 128,416; 0.000% (0) | 0/0; 117,176; 0.000% (0) |

| Partition/phase | 전체 행 | 새 pooled | 기존 unknown | 기타 비율 |
|---|---:|---:|---:|---:|
| TRAIN 전 | 4,237,203 | 13,710 | 340,777 | 8.366% |
| TRAIN 후 | 3,760,499 | 12,511 | 305,043 | 8.444% |
| VAL 전 | 2,074,259 | 6,966 | 170,103 | 8.536% |
| VAL 후 | 1,919,155 | 6,371 | 157,995 | 8.564% |

새 pooling은 주로 recommendationservice에 집중된다: TRAIN 25,716행(4.234%),
VAL 13,115행(4.243%). 반면 해당 서비스의 전체 기타 비율은 기존 unknown까지
포함해 TRAIN 98.770%, VAL 98.931%다. paymentservice의 새 pooling은 TRAIN
500행(0.822%), VAL 222행(0.724%)이지만 기존 unknown 때문에 기타는 각각
98.096%, 97.966%다. redis는 TRAIN 전 5행이 새 pooling되고, 나머지 및 VAL 행은
기존 unknown이다. paymentservice의 pooled event 예시는 charge/transaction
amount·currency 유형, recommendationservice는 recommendation 요청의 여러
product-ID 조합, redis는 RDB background-save 유형이다. 이 짧은 분류는 저장된
sanitized template summary를 요약한 것이며 raw log를 재출력하지 않는다.

## 해석과 한계

- 1,025는 Drain `max_clusters=1,024` 상한에 도달한 frozen LRU snapshot의
  template feature 1,024개와 기존 unknown bin 1개를 합친 설정상 차원이다.
  이론적으로 필수인 모델 폭도, 데이터 전체의 고유 로그 유형 수라는 뜻도
  아니다. 1,024를 왜 선택했는지에 관한 이론적 또는 독립 최적화 근거는 찾지
  못했다.
- top-256은 frozen snapshot의 현재 생존 template 안에서만 순위를 매긴다.
  LRU로 이전에 퇴출된 template까지 포함한 전역 빈도 순위가 아니다. 관측된
  희귀 생존 template 간 구별은 0으로 합쳐지며, recommendationservice에서는
  한 split/phase 셀에서 680–689개의 서로 다른 pooled template가 나타났다.
- 기존 unknown은 처음부터 의미가 불명확한 별도 이벤트였지만 새 규칙에서는
  pooled template와 동일한 0 bin에 들어간다. paymentservice와
  recommendationservice의 기타 대부분이 기존 unknown이며, redis 및 일부
  productcatalogservice 관측 행은 전부 기존 unknown이었다.
- 이벤트 ID 병합 뒤 원형 make_knots를 다시 호출했으므로 동시각 tie jitter가
  적용되는 이벤트 수·관계가 달라질 수 있다. placeholder 포함 event process,
  Hawkes 입력값/너비, 후속 정규화도 원형 1,025-feature 입력과 동일하지 않다.
  모델 구조와 solver 구현을 그대로 쓴 사실만으로 같은 baseline이라고 볼 수 없다.
- 이 pooled 표현이 진단 정확도에 미치는 방향과 크기, 희귀 template별 성능,
  전체 기준선의 완료 비용은 미측정이다. 앞선1,025차원 소수 표본 비용 기록은
  존재하지만 이번257차원 측정과 구별한다. 추가 합병 행이0인 서비스도
  차원·placeholder 수가 달라져 같은 Hawkes 특징값임을 보장하지 않는다.
  성능 개선·저하 주장은 하지 않는다.

## 과거 실행 기록

첫 mapping/verification 단계에서는 일부 upstream 산출물이 아직 없어 누락으로
기록됐고, 첫 mapping 시도에서는 freeze 전 validation JSON metadata 열람 후
중단했다. 이후 recovery는 고정 규칙과 TRAIN-only 빈도 경계를 유지해 완료했다.
최초 benchmark 시도는 MAPPING.md 설명 hash 변경으로 fit 전에 exit 1이었으며,
그 실패 artifact는 그대로 보존했다. 이번 recovery의 producer와 독립 verifier는
각 exit 0이다. 자세한 종료 코드, hash, fit 상태 및 복구 경계는
`VERIFICATION.md`와 `verification_recovery.json`에 있다.

**종료 상태:** 승인된 bounded 257차원 비용 점검만 완료했다. 전체 48/24 준비,
1025차원 전체 재적합, neural training/inference, final test는 미실행이며,
현재 결과만으로 후속 전체 실행을 승인하지 않는다.
