# 다음 RCA 연구 단계 데이터 준비도 평가

기준일: 2026-10-12. 목적은 다음 단계 착수 범위와 보류 조건을 정하는 것이며,
최종 연구 방법이나 성능 결론을 확정하지 않는다.

## 판정 요약
- **GO(제한적):** RCAEval RE2의 root-service supervised 진단 연구 설계 및
  파이프라인 준비는 진행 가능하다. 근거는 180건의 지표 사용 가능 사례와
  명시된 `root_cause_service` 정답이다.
- **HOLD:** RCAEval 호출·메트릭 관계를 인과 전파 정답으로 평가하거나
  causal-edge 성능을 주장하는 작업. 이 데이터의 인과-edge gold는 없다.
- **HOLD(별도 검증 필요):** ops-lite를 공식 OpenRCA 2.0 자료와 동일시하거나
  본 평가 데이터로 확정하는 작업. 확보본 출처/버전 정합성은 미검증이다.

## 확인된 자료와 범위
- RCAEval RE2-OB/RE2-TT: **180건**, 시스템별 **90건/90건**,
  지표 쌍 사용 가능 **180건**, 모든 모달리티 쌍 완비 **178건**.
  2건은 모달리티 불완전, 로그 누락 1건이며 요약에 root-absent trace,
  정상/장애 구간 부재, 인덱스 불일치가 각각 0건으로 기록됐다.
  출처: `evidence/rcaeval-summary.json`.
- 요약의 `cases_with_all_null_metric_columns: 12`는 **12건에서 일부 메트릭
  열이 전부 null**이라는 뜻이다. 모든 메트릭 열 전체가 결측인 12건이라는
  뜻이 아니다. 이 수치만으로 사용 불가 사례 수를 추정하지 않는다.
  출처: `evidence/rcaeval-summary.json`.
- RCAEval README는 RE2가 메트릭·로그·트레이스를 포함하고, OB/TT에는
  트레이스가 있으며, 사례 인덱스가 `root_cause_service`를 정답으로 제공한다고
  기술한다. RE2-TT의 CPU 사례 1건은 로그가 없다.
  출처: `data/rcaeval/README.md`.
- smoke 표본은 시스템 2종 × 장애유형 6종의 **12건**이다. 각 사고의
  동일 시스템/원인서비스/장애유형 반복 3건을 개발용으로 예약한다.
  예약 항목 **36개는 모두 서로 다른 사례**이며, 12개 smoke 사례를 포함한다.
  manifest에는 final-test 목록이 없으므로 **최종 시험 파티션은 아직
  구성되지 않았고**, test와의 overlap 여부도 검증된 수치가 아니다.
  출처: `research/SMOKE_PROTOCOL.md`, `research/smoke/manifest.json`.

## 관측 가능한 특징 가족
- RCAEval smoke JSON 12개에서 서비스별 최소 특징은 메트릭 변화 카드
  (상위 최대 3개 지표명·변화량·방향), 서비스 호출 후보, 트레이스 지연 비율/
  관측 수, 단순 이상 순위다. 로그는 사전 명세상 입력에서 제외된다.
  출처: `research/SMOKE_PROTOCOL.md`,
  `research/smoke/features/incident-01.json`–`incident-12.json`.
- 카드의 메트릭 가족은 **8종**: cpu, mem, diskio, socket, latency-50,
  latency-90, workload, error. 사고당 카드 수는 **13–68**,
  호출 후보(all_calls)는 **9–55쌍**이며 규칙/무작위 선택은 각각 8쌍이다.
  출처: 동일한 12개 smoke feature JSON.
- 카드의 trace 배열 중 **197/487**에는 적어도 하나의 관측 수가 0보다 크고,
  **290/487**은 `[0, 0, null]`이다. 관측 수 범위는 각각
  **0–201,632**, **0–206,310**, 관측된 지연 비율은 **0.372–50.972**다.
  누락 parent span 수는 사고별 **0–87**, 중복·충돌 span key 수는 각각
  사고별 **0–0**이다.
  이는 해당 smoke 카드 요약에서 집계한 값이지 전체 RCAEval trace 완전성
  추정치가 아니다. 출처: 동일한 12개 smoke feature JSON.

## 라벨·누출·분할 제한
- RCAEval의 서비스 수준 root-cause label은 root-supervised 진단 설계를
  지원한다. 다만 causal-edge 정답은 제공되지 않으므로 edge 인과 정확도,
  전파 방향 정답, edge-F1 주장은 지원하지 않는다. 관측 호출은 호출 후보이지
  인과-edge gold가 아니다. 출처: `data/rcaeval/README.md`,
  `research/SMOKE_PROTOCOL.md`.
- 반복 사례는 분할 경계를 넘어가면 안 된다. 동일
  시스템/원인서비스/장애유형 반복 3건은 한 개발 그룹으로 묶어 두고,
  최종 시험 파티션을 만들 때 이 반복 그룹 전체를 한쪽에 배정한다.
  예약 개발 36건은 test로 재사용하지 않도록 추후 명시적으로 분리·기록한다.
  현재 manifest는 개발 예약만 정의하며 final-test 분할을 정의하지 않는다.
  출처: `research/SMOKE_PROTOCOL.md`, `research/smoke/manifest.json`.
- 입력에서 사례명·원 서비스명·장애유형 및 정답 정보는 제외하고 익명화한다.
  ops-lite 사용 시 `env`, `injection`, `label`, `causal_graph`와 사례명 등
  정답 단서를 입력에서 격리한다. 출처: `research/SMOKE_PROTOCOL.md`,
  `SOURCES.md`, `data/ops-lite/README.md`.
- ops-lite 확보본 요약은 **455건**, process 사례 **437건**, 라벨 항목
  **455개**를 기록한다. 역할별 faults는 required **473**, optional **81**,
  not_effective **77**이며, 이 값들은 서로 다른 집계 단위다. 요약상 라벨
  이슈 0건이나, 이것만으로 원 논문 배포본과의 동등성/정답 타당성이 입증되지는
  않는다. 출처: `evidence/ops-lite-summary.json`.
- `SOURCES.md`는 ops-lite 후보의 고정 버전/라이선스가 논문 기술과 다르고
  공식 배포본 연결이 확인되지 않았다고 기록한다. 따라서 출처·버전·사용
  권한을 별도 확인하기 전에는 보조 후보로만 취급한다.

## 다음 단계의 결정 조건
- **GO:** root-service 진단만을 대상으로, RCAEval 180건에서 반복 그룹 단위
  분할을 명시하고, 현재의 개발 예약 36건과 향후 test를 엄격히 분리하며,
  smoke 프로토콜의 작은 탐색 범위와 한계를 그대로 보고할 때.
- **HOLD:** causal-edge 정답을 요구하는 연구 질문, 누출 없는 test 파티션을
  만들지 못한 경우, 또는 ops-lite의 출처/버전·라이선스 확인이 필요한데
  확인되지 않은 경우. ops-lite 검증 보류는 RCAEval root-supervised 경로를
  막지 않는다.
- 최종 시험 분할은 아직 존재하지 않는다. 수치적 성능 우위·통계적 유의성·
  실서비스 일반화는 이 데이터 준비 평가에서 결론 내리지 않는다.
