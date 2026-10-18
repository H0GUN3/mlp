# 과학적 비판 보고서 검증

## 정정된 검증 대상

이 검증의 최종 판정 대상은 **`research/연구_타당성_압박평가.md`**이다.
이전 검증이 과거 문서인 `research/verification/decision.md`를 대신 확인했던 범위 오류를 바로잡았다.
이번 검증은 그 과거 문서를 읽거나 판정 근거로 사용하지 않았다. 함께 확인한 비판 문서는
`research/critique/problem.md`, `research/critique/novelty.md`,
`research/critique/methodology.md`다.

## PASS/FAIL 표

| 판정 | 확인 대상·주장 | 확인 근거 및 결과 |
|---|---|---|
| **PASS** | 네 보고서 파일의 판정·범위 | 최종 판정은 현 설계의 본격 추진 **HOLD**, 방향의 인과 해석·일반 선별/조합의 신규성·필수 LLM 주장은 **DROP**으로 한정한다. RCA 분야나 root-service 과제 자체를 폐기한다고 과장하지 않는다. |
| **PASS** | 현 과제는 root-service 진단 | 최종 보고서 §1–2, `problem.md`의 요약·강한 반론, `methodology.md` F1은 root-service 정답과 평가를 중심으로 쓴다. 인과-edge·피해 서비스 정확도는 별도 gold 없이는 주장할 수 없다고 구분한다. |
| **PASS** | edge-supervision 및 필수 LLM 주장 | 최종 보고서 §4.B–C, §6은 RCAEval의 root 정답을 edge 정답으로 취급하지 않으며 LLM을 필수로 두지 않는다. 세 비판 문서도 edge/victim 주장과 특정 LLM 기여를 근거 미충족으로 제한한다. |
| **PASS** | 개발 자료와 최종 시험 구분 | 최종 보고서 §3 및 세 비판의 표본 한계는 36건을 개발 결과, 12개 시나리오 그룹×3 반복으로 설명하고 held-out 성능·독립 표본으로 부르지 않는다. smoke 12건은 별도 고정 smoke 비교다. |
| **PASS** | BARO 명칭과 재현 범위 | 최종 보고서 §3·§4.E 및 세 비판은 BARO를 코드 정렬 NumPy 점수 재구현으로 한정하고, 전체 BARO·원본 실행·BOCPD 재현이나 논문 우월성으로 확대하지 않는다. |
| **PASS** | 신규성 문헌 범위 | `novelty.md`, `methodology.md`, 최종 보고서 §4.D·§8은 검토한 MicroHECL/EviRCA/TopoEvo/EG-RCA와의 알려진 중복을 설명하되, 이를 전 세계 문헌의 완전 검색이나 전역 최초성 판정으로 표현하지 않는다. |
| **PASS** | 데이터 크기 및 그룹 수 | `baselines/verification.json::counts`는 `cases=36`, `scenario_groups=12`, `repetitions_per_group=3`이다. `results/summary.json`의 전체 `n=36`과 일치한다. |
| **PASS** | Median 결과 | `verification.json::aggregates.median_change.overall` 및 `results/summary.json::overall.median_change`: Top-1 **30/36**, Top-3 **35/36**. `by_fault.median_change`: delay Top-1 **1/6**, mem **5/6**. 보고서와 일치한다. |
| **PASS** | BARO 코드 정렬 변형 결과 | `results/summary.json::overall.baro_signed` 및 `baro_absolute_variant`: 각 Top-1 **10/36**. `baseline-audit.md`도 동일 수치와 제한된 재현 범위를 명시한다. |
| **PASS** | Smoke와 단순 점수 결과 | `smoke/summary.json::conditions`: cards-only **1/12**, all-calls **1/12**, rule-selected **2/12**, random-selected **1/12**. `simple_anomaly.top1_count=11` (11/12). 세 비판 및 최종 보고서의 비교와 일치한다. |
| **PASS** | 여섯 실패 모두 cap-100 점수 동점 | 아래 사례별 대조에서 `methods.median_change.root_position`과 `ranking`의 원인 위치가 일치했고, `metric_scores`에 root 및 그 앞선 모든 후보의 점수 `100.0`이 확인됐다. 정확한 사례별 근거는 다음 절 참조. |
| **PASS** | 피해·인과, 효능, 일반화의 한계 | `verification.json::boundaries`는 `causal_victim_claimed=false`이며 개발 자료 범위다. 최종 판정과 세 비판은 상위 비원인을 피해 서비스로 부르지 않고, 통계적 유의성·새 방법의 효능·일반화를 결론내리지 않는다. |
| **PASS** | 실제 모순 | 확인한 주장과 지정 근거 사이에서 보고서의 수치를 바꾸거나 감춰야 할 실제 모순은 발견하지 못했다. |

## 여섯 실패의 사례별 동점 대조

점수와 순위는 각 `research/baselines/results/cases/<case>.json`의
`methods.median_change.metric_scores`, `root_position`, `ranking`에서 대조했다.
아래의 동점 ID는 `metric_scores`에서 score가 정확히 `100.0`인 서비스 중 root 및
root보다 앞선 순위에 해당한다. 검증 JSON의 `failure_evidence`도 사례별
`root_position`과 선행 후보의 `top_metric_evidence[].score`를 교차 확인하는 데 사용했다.

| 사례 파일명 | Root 위치 (`root_position`) | root 및 선행 후보의 cap-100 근거 |
|---|---:|---|
| `re2ob_checkoutservice_delay_1.json` | S11, 3위 | S04·S07·S11 모두 `latency-90=100.0` |
| `re2ob_checkoutservice_delay_2.json` | S10, 3위 | S03·S08·S10 모두 `latency-90=100.0` |
| `re2ob_checkoutservice_delay_3.json` | S08, 3위 | S01·S06·S08 모두 `latency-90=100.0` |
| `re2tt_ts-travel-service_delay_1.json` | S49, 6위 | 선행 S06·S13·S19·S43·S48 및 root S49의 `latency-50` 또는 `latency-90` 점수가 모두 100.0 |
| `re2tt_ts-travel-service_delay_3.json` | S25, 3위 | 선행 S07·S18 및 root S25의 `latency-50` 또는 `latency-90` 점수가 모두 100.0 |
| `re2tt_ts-train-service_mem_3.json` | S15, 2위 | 선행 S04와 root S15 모두 `latency-90=100.0`; S15에는 `diskio=100.0`도 기록됨 |

따라서 최종 보고서의 **여섯 건 모두에서 root와 앞선 후보가 cap 100 점수에
동시에 도달했다**는 주장은 사례 JSON으로 지지된다. 이는 저장된 capped metric의
동점을 확인한 것이며, cap 제거 시 순위가 회복된다거나 이 동점만이 순위를
결정했다는 증거는 아니다. 최종 보고서도 cap 전 결과가 없음을 밝혀 그 한계를 넘겨
주장하지 않는다.

## 범위 및 수행 한계

요청된 파일과 지정된 baseline/smoke 집계 및 여섯 case JSON만 읽었다.
점수·모델·실험을 재실행하지 않았고 producer 파일도 수정하지 않았다.
이 검증은 저장된 산출물과 문서 주장 간의 일치 여부를 확인한 것이며,
문헌의 완전성이나 원본 BARO 실행을 독립 재현한 것은 아니다.
