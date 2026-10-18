# SN 호출 지연 귀속 대조 — 근거 확인 단계

## 사용자 요청과 현재 단계

저장된 TT50·SN50·SN200 학습 결과를 설명하는 작업은 완료됐다.
다음 질문은 호출 지연을 기록한 서비스와 실제 호출 대상을 구분해 표현하면
SN 지연 장애를 같은 학습 예산에서 더 정확히 진단할 수 있는지다.

먼저 기존 compose_media_client 사례에서 **span 기록 서비스 → 실제 호출 대상
→ 전처리 집계 위치**를 연결한다. 실제 차이가 입증된 한 부분만 후속 대조한다.
이번 첫 DAG는 그 연결과 대조의 실행 가능 조건을 확인하는 단계이며,
입력 전체 생성·학습·추론을 아직 실행하지 않는다.

RE2는 계속 보류한다. 기존 파일·원자료·보호 시험·root·공용 계정·
omo-native·Notion·프로젝트 git 이력은 변경하지 않는다.
Hawkes 설정·로그 표현·모델 구조·학습 예산 확대·여러 후보 탐색은 없다.

## 이미 확인한 출처

원문은 arXiv2302.05092v1 IV-A3에서 callee별 시간 구간 평균 latency를
명시한다. 이 진술과 공개 구현의 입력 귀속은 따로 검증해야 한다.

현재 native 기준선이 따른 수정 포크:
`FeiGSSS/Eadro@7d69281a80adce60067aa858729746fc6a362f53`.
`parse_raw_traces.py`는 span.processID의 processes.serviceName으로
service 키를 만들고, `single_process.py::deal_traces`는 이 키별 duration
평균을 만든다. 로컬 `native_data.py::trace_series`도 같은 owner 귀속이다.

원저자 저장소 `BEbillionaireUSD/Eadro@82ff9c9a7a58a9cd2b713aa78754a73c543a15db`
의 single_process.py에서는 같은 집계 소비 코드를 확인했다.
이 revision의 parse_raw_traces.py 경로는404였다.
따라서 원문과 **공개 수정 포크 및 로컬 구현**을 구분하고,
원저자의 원시 parser까지 확인했다고 주장하지 않는다.
이 차이가 곧 신규성이거나 우리 복원만의 오류라는 결론도 내리지 않는다.

구체적인 URL·확인 줄은 `SOURCE_NOTE.md`에 둔다.

## 기존 자료와 허용 범위

기준 root: `/home/gnho1236/r2`.

- `research/native_learning_diagnosis_20261018/raw_media/`
  의 REPORT.md, evidence.json, operation_durations.json: 읽기 전용.
- 기존6개 validation 창: original index112/115/120/129/133/136.
  recording은 `SN.2022-04-17T181245D2022-04-17T183616`.
- 필요한 span 파일 한 개:
  `data/eadro_native/SN_Dataset/SN Dataset/data/SN.2022-04-17T181245D2022-04-17T183616/spans.json`
  (150,526,142 bytes). 기존 evidence.json의 provenance.source_sha256와 대조한다.
- native SN metadata/split은 허용 창의 ID·시간·service 순서를 확인하는 용도다.
  raw.npz, 보호 model input, 기존 checkpoint는 열지 않는다.

이미 확인된 산술은 반복하지 않는다. index115에서 compose_media_client의
6.008163초 duration이 compose 서비스 한 bin의2.4068048초 평균에 포함됐다.
그러나 기존 분석은 **같은 창의 operation별 집계**였으며, 실제 같은 요청의
client/server 연결을 확인한 것은 아니다. 이번에는 그 미확인을 해소한다.

기존 raw_media/diagnose.py 전체는 실행하지 않는다. 이번에 필요 없는
metric/log/scaler 재검사와 pandas를 포함하기 때문이다.

## 여섯 창의 요청 연결 확인

필요한 경우 원본 spans.json은 한 번의 제한된 stream scan으로 읽는다.
각 span의 startTime으로 여섯 허용 창에 속하는지 먼저 판정하고,
선택된 span만 상세 분석·저장한다. 종료 시점은 원래 half-open 경계를 유지한다.
span 시각은 `startTime // 1_000_000 + 28800`이라는 기존 변환을 사용한다.

파일 전체 바이트를 읽고 JSON trace 객체를 파싱한다는 사실을 숨기지 않는다.
선택하지 않은 span의 duration·operation 관측을 분석하거나
보호 model-input 행을 생성하지 않는다. “보호 raw 바이트를 전혀 읽지 않음”이라는
주장은 하지 않는다. 다른 원시 파일·다른 창으로 범위를 넓히지 않는다.

선택된 span의 traceID/spanID, references와 refType, processID/serviceName,
operationName, span.kind/peer.service 등 실제 존재하는 tags를 점검한다.
trace 내 같은 spanID를 다른 trace와 합치지 않는다.
중복 occurrence와 unique span identity를 구분하고,
기존 baseline의 occurrence 가중을 조용히 바꾸지 않는다.

직접 child reference, peer/service tag, 확인된 instrumentation 근거를 구분한다.
operation 이름의 문자열 유사성이나 정답 root만으로 대상 서비스를 정하지 않는다.
client/server span의 같은 요청 연결이 없거나 창 밖이면 **미확인**으로 남긴다.
관측이 없다는 이유만으로 호출 실패·서버 부재·네트워크 지연 원인을 단정하지 않는다.

원래 span 서비스와 실제 callee가 같은 경우도 함께 집계한다.
media만 고른 유리한 사례로 끝내지 말고 해당6창의 선택 client operation 전체에서
target 식별 가능·불가능·다중 대상·충돌 비율을 기록한다.
고정 서비스 목록 밖의 backend 대상은 억지로 기존 root 후보에 매핑하지 않는다.

## 조건부 후속 대조 원칙

후속 phase는 이 단계의 실측 근거를 읽은 뒤 결정한다.
표현상의 차이가 확인되지 않으면 의미 없는 학습을 하지 않고 보고한다.
차이가 확인되면 서비스 귀속 변경 또는 호출 정보 보존 중 **한 개**만 고정한다.
귀속 변경·span 필터·중복 제거·새 채널을 동시에 바꾸지 않는다.
불명확한 mapping이나 근거 없는 fallback 정책은 선택을 숨기지 말고 미확인으로 남긴다.

적용 규칙은 TRAIN 관측 또는 독립적인 source 근거로 정하고,
validation 정답/성능으로 mapping을 고르거나 후보를 탐색하지 않는다.
개발 오류를 보고 선정한 가설이므로 이번 validation 대조는 선택 편향을 가진
개발 실험이지 독립 최종 일반화 증거가 아니다.

예정된 비교 경계는 기존 native SN train316/validation78와 같은
candidate order·metrics·logs·graph·labels·창·split·optimizer·모델 구조,
200epoch·batch256·seed11/23/37·최소 validation joint loss/earliest tie다.
기존 SN50/SN200 기준선은 hash 검증 후 재사용하며 다시 학습하지 않는다.
후속 변경 arm의 단회200epoch 실행에서 첫50구간 선택점도 별도 보존할 수 있지만
별도의 추가50epoch 학습은 하지 않는다. 조건과 정확한 새 fit 수는 실행 전 문서로 고정한다.
후속 입력의 TRAIN-only scaler 정책과 보존 항목 역시 실행 전에 명시한다.
200epoch 뒤 늦게 선택돼도 자동 연장하지 않는다.

## 첫 DAG 구성

source-contract(quick)와 case-link(deep-low)를 병렬로 확인한 뒤
gate(unspecified-low)가 합류한다. 폭2→1.
source는 이미 확인한 논문/공개 코드와 로컬 코드 계약 비교,
case-link는 중복 identity·요청 reference·시간 경계가 결합된 실제 span 연결,
gate는 두 증거의 일치와 단일 변경의 타당성 판단을 맡는다.

- source-contract: SOURCE_CONTRACT.md만 소유.
- case-link: link_cases.py, test_link_cases.py, links.json, CASE_LINK.md,
  case_link_evidence/만 소유. 실제 scan은최대180초, 데이터 파일추가탐색없음.
- gate: PHASE1_GATE.md, PHASE1_GATE.json, PROTOCOL_DRAFT.md만 소유.
  producer 검사를 재실행하지 않고 저장 link/숫자/범위를 독립 대조한다.

작은 합성 검사로 trace-key 충돌·중복 occurrence·다중 target·창 경계를 확인한다.
검사 실패는 원인을 고쳐 해당 경로만 복구한다. 없는 근거를 채워 넣지 않는다.
문서 보완을 수치 입력 변경으로 오인하거나 완료 상태만으로 성공을 주장하지 않는다.
모든 신규 소스·문서는 apply_patch, 실행 산출물은 배타 생성하며
수치 source/input/output hash와 실제 실행 방식을 기록한다.
장시간 실행은 monitor로 완료 증거를 확인한다.
