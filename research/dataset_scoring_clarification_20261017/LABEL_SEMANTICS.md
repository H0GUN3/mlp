# RCAB 라벨 의미: 확인된 규칙과 미확인 연결

**판정 (2026-10-17):** 원래 RCABench의 복수 `ground_truth.service`와 현재 ops-lite의 HTTP `also_accept`가 같은 라벨 규칙이라는 점은 입증되지 않았다. 겉으로 일부 같은 서비스 이름을 포함할 수 있어도 생성 근거와 의미가 다르다.

## 확인된 내용

| 항목 | 확인된 계약 | 근거 |
|---|---|---|
| 원래 RCAB 생성기 | 고정 `chaos-experiment` 커밋 `55f9ad16818e89aeed984594434e8fbc66c5d430`의 `Groundtruth`는 주석상 주입의 **예상 영향(expected impact)** 이다. 기본 앱/컨테이너/JVM 메서드는 단일 서비스를 기록한다. HTTP endpoint helper는 `AppName`과 `ServerAddress` 둘 다를 서비스 목록에 넣고, network pair도 양 endpoint를 담는다. DB operation은 앱과 `mysql`을 담는다. 이는 설정/selector 기반 생성 규칙이지, 해당 두 서비스가 관측상 구별 불가능하다는 규칙은 아니다. | [원본 생성 코드, 고정 커밋](https://github.com/OperationsPAI/chaos-experiment/blob/55f9ad16818e89aeed984594434e8fbc66c5d430/handler/groundtruth.go), [HTTP helper와 pair 생성](https://github.com/OperationsPAI/chaos-experiment/blob/55f9ad16818e89aeed984594434e8fbc66c5d430/handler/groundtruth.go) |
| RCAB 변환기 | 고정 `rcabench-platform` 커밋 `5a463bd2bfaecda1b26aed9fe3f018859196bb0e`의 `get_root_services()`는 `injection.ground_truth.service`를 그대로 반환한다. 따라서 변환기가 복수 항목의 의미를 관측 동등성으로 새로 바꿨다는 증거는 없다. 단, 이 코드 커밋이 실제 보유 아카이브 생성에 사용된 버전이라는 연결은 로컬 감사에서도 미확인이다. | [고정 변환기](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/datasets/rcabench.py); 로컬 근거: `research/rcabench_assessment_20261013/REPORT.md`, `research/rcabench_assessment_20261013/QUALITY_CONTRACT.md`, `research/research_reset_review_20261016/RCABENCH_REPORT.md` |
| 현재 ops-lite 설명 | `label.json`의 `required`는 해당 fault가 자기 서비스 밖으로 영향을 미쳐 복구할 원인 집합에 포함된다는 뜻이다. `also_accept`는 세 HTTP fault에만 있으며, 문서는 telemetry만으로 호출의 어느 끝이 변경됐는지 가릴 수 없다고 설명한다. 즉 관측상 허용 대안을 명시한 채점 예외다. `required`/`optional`/`not_effective`의 효과 판정과 `also_accept`의 대체 예측 허용은 서로 다른 필드·역할이다. | [ops-lite README, `main`의 현재 원문](https://huggingface.co/datasets/anon-ops/ops-lite/raw/main/README.md) |

원래 HTTP 목록에 양 endpoint가 들어가는 것은 생성 코드가 endpoint 쌍을 expected-impact 서비스로 수집하기 때문이다. ops-lite `also_accept`는 문서상 특정 HTTP 경우의 식별 불가능성을 채점에 반영한다. 두 방식이 일부 같은 답을 허용하더라도, 전자는 **무엇을 설정 기반 영향 목록에 넣었나**, 후자는 **관측에서 구별이 어렵다고 하여 어떤 응답을 허용하나**라는 질문이다. 이름의 겹침만으로 동등 규칙이라 할 수 없다.

## 알 수 없는 것과 해석 경계

- ops-lite URL은 고정 revision이 아닌 `main` 경로다. README에는 OpenRCA 2.0 명칭과 455건 구성이 있지만, 이 검토에서 확인한 내용만으로는 해당 문서/라벨 파일의 정확한 release commit과 원래 RCABench 생성 산출물 간 lineage를 고정할 수 없다.
- 공개 생성 코드의 고정 revision은 확인했으나, 실제 RCABench 아카이브가 바로 그 revision으로 생성됐다는 재현·build provenance는 확인되지 않았다.
- ops-lite README의 “telemetry cannot tell”은 현재 데이터 설명의 주장이다. 이번 범위는 이를 사례별로 새로 검증하지 않았다. 두 endpoint를 식별하는 것이 원리적으로 불가능하다는 일반 명제도 아니다.
- 기존 RCAB 감사에서 1,422건 중 비-network 1,168건을 살펴 충돌 1건을 제외한 **1,167건**은 단일 설정 표적 과제의 *후보*다. 이 수는 물리적 단일 원인이 입증된 수, 고유 원인 수, 독립 사건 수가 아니다. network 254건은 endpoint 쌍 설정으로 별도 의미가 있다. 근거: `research/research_reset_review_20261016/RCABENCH_REPORT.md` §4.
- nominal injection target 기준 순위는 설정에 찍힌 표적을 맞히는지 묻는다. 관측상 동등하다고 허용한 root 집합 기준 순위는 허용 집합 안의 정답을 맞히는지 묻는다. 점수 순위의 역전은 허용 정답 집합을 바꾸면 생길 수 있는 **분류 정의의 변화**이며, 그 자체로 DiagMLP 결과나 모델 능력의 변화가 아니다. 현재 pilot은 동일 관측에서 두 서비스를 구분할 수 없음을 증명하지 않는다.
- 기존 33개 테스트는 구현·계산 검증이지, 이 두 세대의 gold semantics 동등성이나 모델의 구별 가능성 검증이 아니다.

## 후속 평가 전에 정할 계약 선택지

사용자가 선택할 정책이며 여기서는 최종 gold를 정하지 않는다.

1. **설정 표적 계약:** nominal injection target을 정답으로 두고 그 일치도를 평가한다. 복수 설정 endpoint를 정답으로 넣은 이유와 순서 의존 여부를 명시한다.
2. **관측-동등 허용 계약:** 사례별로 근거 있는 허용 서비스 집합을 따로 기록하고 그 집합에 대한 채점 규칙을 명시한다. 설정 gold를 사후에 자동 확장하지 않는다.
3. **분리 보고:** 위 두 계약의 점수를 각각 보고하여 설정 표적 식별과 허용 root 집합 적중을 다른 질문으로 다룬다. 평가 해석과 주 비교 기준은 사전에 정한다.

어느 선택도 현재 근거만으로 우월하다고 결론내리지 않는다. 비교 전 사례별 라벨 출처, endpoint 역할, 허용 대안의 근거, null/복수 답 채점, 정확한 데이터·코드 revision을 계약에 고정해야 한다.

## 수행 범위

지정된 로컬 보고서와 README를 읽고, 위 고정 upstream 코드 및 ops-lite `main` README만 확인했다. 원자료·주입 전체 재열람, 모델/데이터 평가, 다운로드, 분할 변경은 하지 않았다. upstream 코드는 의미 정의의 근거이지 보유 자료의 생성 revision을 증명하는 증거는 아니다.
