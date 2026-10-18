# 연구 문제 반증 검토

## 요약 판정

- **현재 주장(“원인/피해 서비스 혼동이 반복되는 핵심 실패이며, 추가 추론/LLM이 필요하다”): HOLD.** 관측된 것은 일부 케이스의 root-service 순위 불일치다. 피해 서비스 정답이나 인과 경로는 없다.
- **범위 수정:** 문제를 일반적인 원인-피해 혼동으로 부르지 말고, 우선 “잘린 점수와 동점 처리에서 root 순위가 어떻게 달라지는가”라는 측정 가능한 현상으로 한정한다.
- **현재 복잡한 진단기/LLM 기여: DROP(현 근거에서).** 이는 RCA 분야 전체의 폐기가 아니다. 기준점보다 더 정확하거나 필요한 역할을 한다는 증거가 아직 없다.
- RCA의 운영상 중요성은 배경 동기일 뿐, 이 데이터에서 특정 기여가 필요하다는 증명은 아니다.

## 강한 반론

### 1. 여섯 건의 순위 실패 중 다섯 건은 실제 낮은 점수가 아니다 — 치명도 높음

- **근거:** `research/baselines/verification.json::failure_evidence`; `research/baselines/results/cases/*.json::methods.median_change.{ranking,metric_scores}`.
- 재계산: median 기준 30/36 Top-1, 35/36 Top-3. 실패 6건은 delay 5, mem 1이다. 후보 누락은 0건.
- delay 다섯 건 모두 root와 앞선 후보 점수가 **100으로 동일**하다. 사례별 동점:
  - `re2ob_checkoutservice_delay_1`: root S11 순위 3, S04/S07/S11/S12 모두 100.
  - `re2ob_checkoutservice_delay_2`: root S10 순위 3, S03/S08/S10/S12 모두 100.
  - `re2ob_checkoutservice_delay_3`: root S08 순위 3, S01/S06/S08/S13 모두 100.
  - `re2tt_ts-travel-service_delay_1`: root S49 순위 6, S06/S13/S19/S43/S48/S49/S50/S65 모두 100.
  - `re2tt_ts-travel-service_delay_3`: root S25 순위 3, S07/S18/S25/S34/S40/S42/S46 모두 100.
- 따라서 이 다섯 건에서 관측된 것은 cap으로 뭉개진 동점의 정렬 결과다. 앞선 후보가 더 높은 anomaly score를 가졌다고 말할 수 없다. 익명 ID 순서가 순위를 가르는 경우를 원인/피해 추론 실패로 해석하면 안 된다.
- **대안 설명:** 상한 100과 동점 tie-break가 서로 다른 실제 크기의 변화를 같은 점수로 만들었다.
- **최소 판별 테스트:** 이 다섯 사례의 동일 입력에서 cap 전 정밀도 점수와 tie 그룹을 재계산하고, cap 제거/동점 처리만 바꿔 root 순위가 회복되는지 확인한다. 이는 원인 분석을 증명하지는 않는다.

### 2. “피해 서비스”는 라벨도 관측도 아니다 — 치명도 높음

- **근거:** `research/baselines/results/cases/re2ob_checkoutservice_delay_{1,2,3}.json` 및 `re2tt_ts-travel-service_delay_{1,3}.json`: `root_cause_service`, `metric_scores`; `research/BASELINE_PROTOCOL.md`의 단일 원인서비스 범위.
- 정답은 주입된 root service뿐이다. 상위 비-root 서비스들의 지표 변화는 상관 신호이지 피해/전파 정답이 아니다. baseline audit도 이를 인과 증거로 보지 않는다.
- **대안 설명:** 지표 변화가 공통 부하, 집계/계측, 장애 주입의 직접 신호일 수 있다. 현재 기록만으로는 이 설명들과 전파 피해를 구별할 수 없다.
- **최소 판별 테스트:** 독립적으로 검증된 피해 서비스와 시각 정렬된 전파 관측이 있는 사례를 별도 수집해, root와 victim을 각각 라벨링한다. 호출 그래프나 비-root 순위만으로 victim gold를 만들지 않는다.
- **판정:** “root-victim 혼동이 실패 원인”은 **미입증**이며 현재 주장으로는 HOLD.

### 3. 여섯 건은 세 독립 메커니즘이 아니다 — 치명도 높음

- **근거:** `research/baselines/verification.json::counts`, `failure_evidence`; `research/baselines/results/summary.json`.
- 36건은 12개 시나리오 그룹의 반복 3회다. 실패 6건은 checkoutservice-delay(반복 3회), ts-travel-service-delay(반복 2회), ts-train-service-mem(반복 1회)의 **3개 그룹**에 모인다. delay 5건도 독립 조건 5개가 아니라 두 그룹의 반복 관측이다.
- 따라서 6/36은 케이스 실패율이지 독립적인 문제 발생률이나 일반화 근거가 아니다. 현재로서는 반복 delay 현상의 원인조차 확정되지 않았다.
- **대안 설명:** 특정 두 주입 그룹의 반복 가능한 점수 포화와 한 번의 mem 순위 역전일 수 있다.
- **최소 판별 테스트:** 원인 서비스·장애유형 조합을 그룹 단위로 분리한 독립 시나리오에서 재현 여부를 확인한다. 반복 실행은 그룹 내 변동성으로 집계한다.

### 4. 단순 기준점이 이 범위에서 강하다 — 치명도 중간~높음

- **근거:** `research/smoke/summary.json::conditions`; `research/baselines/results/summary.json::overall`.
- 고정 smoke12x4에서 median은 11/12 Top-1이다. cards-only, all-calls, random-selected는 각각 1/12, rule-selected는 2/12 Top-1이다. development36 median은 30/36 Top-1, 35/36 Top-3.
- 이는 단순 변화량 기준이 해당 고정 과제에서 강하다는 증거다. 복잡한 추론 모듈이나 LLM을 추가할 필요성은 오히려 입증되지 않았다. 다만 12건 smoke와 개발 36건은 held-out 성능이나 모든 RCA 방법의 열등함을 증명하지 않는다.
- **대안 설명:** smoke는 작고 현재 장애 주입의 자원/지표 신호에 유리할 수 있다.
- **최소 판별 테스트:** 변경 없이 고정한 평가에서 실패 그룹이 독립 조건으로 재현되는지 확인한 뒤, 동일 입력·정답·비용의 강한 기준점과 제안 역할을 비교한다.

### 5. BARO 점수는 복잡한 방법의 필요성을 입증하지 않는다 — 치명도 중간

- **근거:** `research/BASELINE_PROTOCOL.md`의 BARO 경계; `research/baselines/baseline-audit.md::Exact results`; `research/baselines/results/summary.json`.
- 코드 정렬 NumPy 재구현은 signed/absolute 각각 10/36 Top-1이다. 그러나 이는 BARO 전체 논문/원본 실행/BOCPD 재현이 아니며, 전처리와 점수 경로를 정한 제한 비교다. median과의 차이도 단일 수식의 효과로 분리된 ablation이 아니다.
- 따라서 이 결과로 BARO 일반이나 선행연구를 이겼다고 주장할 수 없고, 약한 비교 결과가 새 방법의 기여를 대신하지도 않는다.
- **대안 설명:** 점수 경로·전처리의 차이 또는 주입 신호에 대한 적합도가 결과를 설명할 수 있다.
- **최소 판별 테스트:** 기여 주장을 세우기 전, 원본 구현 또는 논문 재현과 코드 정렬 변형을 명확히 분리해 같은 후보·정답·정보 조건으로 검증한다.

## 남는 증거와 경계

- `research/baselines/verification.json`의 검증 상태는 frozen artifact 재채점 성공을 뜻한다. 일반화·인과성·통계적 유의성·신규성을 뜻하지 않는다.
- 다섯 delay 사례의 root 점수는 모두 100 cap 동점이다. root metric family는 latency-90(OB) 또는 latency-50(TT)가 포화된다. 상위 비-root에도 지표가 있지만, 그 변화가 전파인지 공통/직접 신호인지는 레코드로 판별할 수 없다.
- 여섯 번째 실패 `re2tt_ts-train-service_mem_3`은 root 2위, S04가 1위다. `verification.json::failure_evidence`는 S04의 CPU 하락·mem 상승·diskio 상승을 기록하지만, 이 상관 패턴만으로 victim/원인 경로를 확정할 수 없다.
- BARO signed와 absolute는 모두 10/36 Top-1이며 paired Top-1 결과가 36/36 동일하다. 이는 두 명시 변형의 근접성을 보일 뿐, 다른 방법군이나 원인 메커니즘의 증거는 아니다.
- 본 검토는 지정된 reserved 36건과 원래 smoke 12건의 기록만 사용했다. 보호된 144개 telemetry, trace, 신규 모델/방법은 열지 않았고 평가하지 않았다.

## 범위 결정

| 주장/범위 | 결정 | 이유 |
|---|---|---|
| RCA 운영 문제의 중요성 | **KEEP** (배경 동기만) | 분야 중요성과 특정 기여의 필요성은 별개 |
| “원인/피해 혼동”이 현재 실패 원인 | **HOLD** | 피해 라벨/전파 증거 없음, delay 실패는 cap 동점 |
| 고정 과제에서 점수 포화·tie-break 현상 | **REVISE** | 관측 가능한 좁은 현상으로 표현하고 최소 판별 테스트 필요 |
| 새 복잡한 단일-root 진단기 기여 | **HOLD** | median 기준점이 강하고 추가 가치 미입증 |
| LLM을 필수 방법으로 채택 | **DROP** (현 단계) | smoke 결과에서 이점 없고 필요한 고유 역할이 지정되지 않음; 모든 LLM에 대한 보편적 기각은 아님 |
| 일반 코드 결함/운영 장애까지 일반화 | **DROP** (현재 주장) | 현 주입 사례 밖의 증거가 없음 |
