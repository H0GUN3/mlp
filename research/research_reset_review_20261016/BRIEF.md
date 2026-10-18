# 장애 정의·평가 재구성·RCABench 분석 범위

## 사용자 요청
18개 질문을 검증하고 다음 연구를 상의한다. 새 학습·분할 확정·원자료 삭제는 하지 않는다.
경량성은 목표가 아니다. 모델과 주 데이터도 아직 최종 합의가 아니다.

## 바로잡을 설명
- validation으로 epoch/설정을 고르는 것은 표준 절차다.
  사건 공유와 최종평가 없이 validation 점수를 일반화하는 문제와 구분한다.
- 이미 사용한 Eadro 자료 자체가 영구적으로 사용할 수 없게 되는 것은 아니다.
  새 사건 그룹 분할·TRAIN 전용 처리·새 학습의 재분석은 가능하다.
  반복적으로 본 자료를 처음 보는 맹검처럼 표현하지 않는다.
- 기존 RCAEval lock은 과거 결정을 보존하는 장치이지 과학적 타당성의 증명이 아니다.
  오류가 있으면 근거와 합의에 따라 새 버전으로 수정하며 기존 파일을 몰래 덮어쓰지 않는다.

## 분석 순서
1. 원문 장애/SLI/정답 정의, 과제별 F1·Top-k의 의미를 확인한다.
2. 기존 RCABench inventory1.6MB와 전수 quality45.5MB를 resident memory에 한 번 읽는다.
3. 13.445GB 확보 archive는 단일 순회로 injection.json/env.json/conclusion.parquet만 읽는다.
   센서 원관측 Parquet의 본문은 재검사하지 않는다. 이미 확보한 품질 통계를 재사용한다.
4. 주입 대상·정답 수·fault type·시각·구성 반복·관측 지원·SLI 요약을 대조한다.
   임의 threshold를 실제 장애 정답으로 선언하거나 subset369/350을 자동 선택하지 않는다.
5. 이론 비교와 연구 범위 선택지를 분석 결과에 연결한다.
6. 작은 검사, 전체 집계 정합성, 근거 경로, 원문/관측/추론 구분을 확인한다.

## 처리·검증 계약
- 기존 Python/pyarrow19.0.1 사용; 설치 없음. JSON/집계는 메모리, archive는 streaming.
- archive member를 파일시스템에 extract하지 않는다. 허용 이름 세 종류만 파싱한다.
- inventory의경로/크기 및 기존 quality의파일sha256과 대조한다.
- 새 산출물은 이 디렉터리에 exclusive-create한다.
- 비유한값/누락/불일치는 남기거나 실패시키며0으로 숨기지 않는다.
- source group ID/생성 버전이 없으면 독립 사건 수를 확정하지 않는다.
- 새 모델·새 feature cache·train/test assignment·최종성능평가를 만들지 않는다.

## 산출물
- 분석 코드와 작은 자기검사
- 원 metadata/결론 요약과 집계 JSON
- RCABench 상세 보고서
- 18개 질문을 연결한 이론·평가·협의 보고서
