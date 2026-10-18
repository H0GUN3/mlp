# TT trace 관측 부재: 한 기록 안의 단계별 조사

## 질문과 중단 규칙

“TT의 원인 서비스 지연 관측이 왜 드문가?”만 조사한다.
첫 기록 하나의 개발 관측으로 한정하며 모델·학습·다른 데이터셋으로 확장하지 않는다.
확인된 가장 이른 문제 지점에서 멈춘다. 단서가 없으면 미확인으로 남긴다.

1. 정합성: 첫 TT recording의 원 장애 metadata 9건과 현재 개발 bundle의
   서비스 이름/정답/시각/창을 대조한다. 틀리면 trace 조사를 실행하지 않는다.
2. 누락 추적: 아래 3건의 허용 개발 창만 원 spans.json에서 복원해
   count·latency·observed를 정확히 대조한다.
3. 원 spans에도 root가 없으면 같은 창의 root 로그와 호출 단서를 소량 확인한다.
   무요청·수집 누락·계측 부재 중 근거 없는 원인은 단정하지 않는다.

## 고정한 좁은 표본

파일명 순 첫 recording: `TT.2022-04-17T212101D2022-04-17T230842`.
metadata 순 첫 network_delay와 같은 root의 network_loss:
`fault01`, `fault02` — ts-food-service.
다른 root의 첫 network_delay: `fault04` — ts-travel-service, 양성 관측 대조.
예측 성공/실패 점수로 표본을 고르지 않는다. TT 전체를 대표한다고 주장하지 않는다.

단계1은 이 recording에 속한 허용 개발 창만 정답 일관성을 확인한다.
단계2·3은 위 3사건에 속한 허용 개발 창만 관측값을 집계한다.
창 경계와 주입 구간이 부분 중첩하는 경우와 완전히 포함되는 경우를 구분한다.

## 읽기·쓰기 범위

- 기존 개발 manifest/bundle, 원 source code, 첫 recording 원 장애 metadata,
  spans.json, 필요할 때 logs.json만 읽는다.
- 최신 요청의 “근본적인 원인을 단계별 조사”는 좁은 원자료 대조 승인이지만,
  protected/native final test/RCAEval/RCABench 관측 사용 승인은 아니다.
- JSON 스트리밍/디코딩과 해시 때문에 단일 원파일 바이트를 읽지만,
  timestamp routing 후 선택한 개발 창 밖의 서비스·duration·로그 본문은
  분석·출력·학습에 사용하지 않는다. 원자료 로더/학습 entrypoint를 실행하지 않는다.
- metadata·span 원파일은 기존 bundle manifest의 보존 SHA256과 대조한다.
  로그는 이전 manifest에 hash가 없으면 시작/종료 snapshot임을 명시한다.
- 기존 +16h(record)·+8h(span/log) 좌표 변환을 대조하되 이를 독립적인
  물리 시계 동기화 검증이라고 부르지 않는다. 보호 창을 이동시킬 offset 탐색은 하지 않는다.
- 새 파일은 이 디렉터리에만 쓴다. 모델/feature/cache를 수정하지 않는다.
  Python은 -B/PYTHONDONTWRITEBYTECODE로 실행한다. 설치·커밋하지 않는다.

## 검증

간단한 fixture로 fractional fault endpoints/10초 창 경계/동일 정답 매핑,
허용 창 routing·latency/count·로그 timestamp 처리를 확인한다.
원자료 복원과 저장 bundle의 count·latency·observed가 정확히 같은지 검사한다.
각 단계는 성공 출력과 exit0, 출처 해시, 선택한 창/사건 목록을 보존한다.
기존 54개 모델과 개발 점수는 재실행하지 않는다.
