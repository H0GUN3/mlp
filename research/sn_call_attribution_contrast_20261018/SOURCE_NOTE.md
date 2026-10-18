# 사전 확인한 논문·공개 코드

확인일:2026-10-18. 아래는 원문 및 고정 revision의 읽기 결과다.
설치나 기존 파일 변경은 하지 않았다.

## 논문

`https://arxiv.org/html/2302.05092v1`

IV-A3 Trace Learning은 시간 구간마다 callee별 평균 latency 시계열을
만든다고 설명한다. 핵심 원문 구절:
“calculating the average latency at a time slot for each callee.”
II-A의 invocation latency 정의에는 서비스 내부 처리와 통신 시간이 포함된다.
이 명세만으로 데이터의 모든 span.processID가 callee라는 결론은 나오지 않는다.

## 현재 native 기준선의 수정 포크

`https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_traces.py`

parse_spans에서 span.processID에 대응하는 processes.serviceName을 service로
선택한다. duration을 초로 변환하고 timestamp/service별 list로 묶는다.
callee 추론, operation별 분리, client/server 필터는 이 경로에 없다.

`https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py`

deal_traces가 위 service key에서 node index를 얻어
그 노드의 bin별 duration 평균을 만든다. 둘째 trace channel은 초기0이고,
invocation count는 별도 객체로 계산된다. 이번 대조는 count 추가가 아니다.
정규화·시간축·label 등 다른 public/local 차이까지 고치자는 작업이 아니다.

## 원저자 revision과 확인 한계

`https://raw.githubusercontent.com/BEbillionaireUSD/Eadro/82ff9c9a7a58a9cd2b713aa78754a73c543a15db/codes/preprocess/single_process.py`

해당 deal_traces 소비 코드도 위와 같은 service-key별 평균 구조를 확인했다.
그러나 같은 revision의 `codes/preprocess/parse_raw_traces.py` URL은404였다.
따라서 원저자 전체 원시 전처리 구현의 callee 귀속이 확정됐다고 주장하지 않는다.

## 로컬 연결

`../native_reproduction_20261013/native_data.py:270–298`의 trace_series도
process.serviceName을 노드로 정해 occurrence 가중 평균을 만든다.
기존 raw_media 보고서는 이 경로의 산술을 이미 실제 입력과 대조했다.
이제 확인할 것은 owner와callee의 실제 연결이며,
산술 재검사나 논문의 신규성 재주장은 아니다.
