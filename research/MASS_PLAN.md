# mass-ulw 전환 계획

2026-10-12, 사용자의 명시적 mass-ulw 요청으로 남은 작업을 의존 DAG로 수행한다.
기존 활성 goal과 9개 요구사항을 유지한다. 이미 완료한 문헌 조사·데이터 검수·
12건×4조건 스모크를 재실행하지 않는다.

## 독립 구성요소
1. 스모크 실험 증거의 일관성과 입력 누출 검사.
2. 데이터·특징·정답의 연구 적합성.
3. 문헌에 근거한 baseline 계약과 차별성 한계.
4. 검증 결과에 따른 연구 계획·결과 보고·재현 안내.

## Run 1: 증거 확인 단계
- 1차 wave 3개:
  - smoke-audit / unspecified-low: 여러 JSON·정답 매핑·요청의 일관성을 확인하는 작은 검사기.
    쓰기 범위 `scripts/verify_smoke.py`, `research/verification/smoke-audit.md`,
    `research/verification/smoke-checks.json`.
  - data-audit / quick: 기존 검수와 실제 특징에서 데이터·관측 누락 조건을 대조.
    쓰기 범위 `research/verification/data-readiness.md`.
  - baseline-audit / quick: 기존 관련 연구 문서에서 구현/평가 계약을 명확히 구분.
    쓰기 범위 `research/verification/baseline-contract.md`.
- 2차 wave 1개:
  - decision / unspecified-low, 위 3개에 의존: 검증된 근거를 통합하여 확대/보류 조건 판정.
    쓰기 범위 `research/verification/decision.md`.
- 3개 동시 작업은 기본 모델 동시성 5 이하. 쓰기 범위가 겹치지 않는다.
- 원래 모델 응답·정답·입력·사전 명세는 수정하지 않는다.
- baseline 전체 재현, 외부 연락, 새 데이터 다운로드·모델 실행은 하지 않는다.

## Run 2: 문서화 단계
Run 1의 검증된 결과를 읽은 뒤 별도 정의한다.
- 연구 계획, 스모크 결과, 재현 안내를 독립 경로에 작성한다.
- 종합 검증 노드가 모든 작성 노드에 의존해 근거 수치·링크·주장 범위를 확인한다.
- 이전 스모크는 실제 결과를 기록하고 본 실험의 성공 증거로 포장하지 않는다.

## 성공 조건
- 현재 9개 요구사항 각각의 답과 근거를 문서에서 찾을 수 있다.
- 48개 원본 응답과 채점/요약 수치가 일치한다.
- 모델/양자화/고정 입력/표본/반복 그룹/정답 차단을 재현할 기록이 있다.
- 데이터 한계, baseline 미재현 상태, 신규성 미입증 상태가 명시된다.
- '완료'라는 노드 주장 대신 실제 검사 결과와 산출물을 확인한 후 최종 보고한다.

## 합의 후 변경: 문서화 전 개발용 기준점 단계 삽입

사용자는 단일 원인 서비스·정확도 우선·기존 방법 실패 분석 후 방법 선택을 승인했다.
따라서 문서화 run 전에 `BASELINE_PROTOCOL.md`를 따르는 별도 run을 수행한다.

- baselines / unspecified-low: NumPy 점수기 구현·self-check·개발 36건 실행.
  기존 helper와 원본 전처리 의미를 맞추므로 기계적 단일 파일 작업을 넘는다.
  쓰기: `scripts/baseline_dev.py`, `research/baselines/results/**`.
- split-guard / quick: 개발 36건·보호 144건과 반복 그룹 경계 검증.
  쓰기: `scripts/verify_development_split.py`, `research/baselines/split-audit.json`.
- method-note / writing: 실제 비교 범위와 원본 대비 차이 설명.
  쓰기: `research/baselines/method-note.md`.
- verify / unspecified-low, 위 3개에 의존: 집계·원본 점수·실패 사례의 독립 검증.
  쓰기: `scripts/verify_baselines.py`, `research/baselines/verification.json`,
  `research/baselines/baseline-audit.md`.

3개 동시 producer는 쓰기 범위가 겹치지 않는다. 원래 smoke와 source data는 읽기 전용.
각 run 완료 주장은 verifier의 실행 증거를 확인한 뒤에만 채택한다.
이 결과에서 확인된 현상에 맞춰 다음 문서화 run의 지시문을 정의한다.

## Run 3: 연구 타당성 반증 단계

개발용 결과는 중앙값30/36, BARO 코드 정렬 재구현10/36, 절댓값 변형10/36이며
독립 검증이 통과했다. 이를 기존 아이디어의 성공 근거로 해석하지 않는다.

- problem / unspecified-low: 원인/증상 혼동이라는 문제가 실재하는지, 지연 장애 실패가
  상한·동점·관측/전처리 결과인지 사례 근거로 검토한다.
  쓰기: `research/critique/problem.md`.
- novelty / unspecified-low: 6편의 관련 연구와 현재 기여 후보가 실제로 다른지 검토한다.
  쓰기: `research/critique/novelty.md`.
- methodology / unspecified-low: 입력·모델·baseline·분할·통계와 기여의 논리적 연결을 검토한다.
  쓰기: `research/critique/methodology.md`.
- verdict / deep-high, 위3개에 의존: 연구 가치·범위·기여를 유지/수정/보류/폐기로 판정한다.
  이 결정은 수치 한 개로 결정되지 않는 연구 선택의 trade-off를 포함한다.
  쓰기: `research/연구_타당성_압박평가.md`.
- verify / quick, 위4개 모두에 의존: 모든 수치·범위·인용과 미확인 주장의 표기를 검사한다.
  쓰기: `research/critique/verification.md`.

첫 wave3개는 기본 슬롯5 이하이며 파일 쓰기 범위가 겹치지 않는다.
새 모델 실험·보호144건 접근·원본/첫 결과 수정은 금지한다.
수치 검증의 기존 증거는 재사용하며, 실패하거나 입력이 달라진 검사만 재실행한다.
