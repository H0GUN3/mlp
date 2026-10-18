# mass-ulw 실행 의존관계

2026-10-17: 실행 중 사용자가 mass-ulw를 명시했다.
완료된 채점 코드와 진행 중 입력 준비를 버리거나 중복 실행하지 않는다.
skill의 planning.md 전체를 읽은 뒤 아래 단계로 전환한다.

## 목표 연결

기존 등록 목표의 미완료 항목인 교정 평가를 그대로 수행한다.
새 목표 등록은 기존 미완료 목표 때문에 거부됐다. 이를 완료로 가장하지 않는다.
기존 목표의 자료선택 중단 사유는 사용자의 SN 선택/진행 지시로 해소됐으며,
실행 경계는 승인 PLAN.md와 새 지시를 따른다.

## 독립 구성요소

1. 보호행을 해석하지 않는 입력 복원/분할.
2. 사건 확률 집계/동률/불확실성 채점.
3. 학습/재개/선택 잠금 실행기.
4. 선택 후 평가·독립 재추론/재채점.
5. 실패 분석과 결과 보고.

## 단계 A: 학습 진입 조건

`input-receipt (quick)` + `score-check (quick)` + `runner-integration (unspecified-low)`
→ `pretrain-verify (unspecified-low)`.

첫파동3개는 입력 인계/채점/실행기로 쓰기범위를 분리한다.
input-receipt는 진행 중 st_01a148db의 INPUT_VERIFY.md를 file monitor로 기다린다.
생산자를 재실행하지 않고 source/hash/허용행/실제종료근거를 확인한다.
score-check는 완료된 scores.py를 실제 .venv-eadro 환경에서 검사한다.
runner-integration은 runner.py/test_runner.py/pyrightconfig.json만 통합·수정한다.
이 노드는 기존 코드에 이어 per-rotation 실행을 노출하므로 몇 파일의 통합 판단이 필요하다.
pretrain-verify는 전체 경계/재개/학습전용 통계/채점과 실제 환경을 검사하므로
단순 완료표시 확인보다 넓은 검증 판단이 필요하다. PRETRAIN_CHECKS.json을 최종 생성한다.
이 단계에서는 실제 데이터의 본학습/평가를 하지 않는다.

인계: INPUT_GATE.md, SCORE_GATE.md, RUNNER_GATE.md → PRETRAIN_VERIFY.md/PRETRAIN_CHECKS.json.
단계 A가 실제 PASS이면 단계 B를 새 run으로 시작한다.

## 단계 B: 학습과 선택 잠금

`train-r0 (quick)` + `train-r1 (quick)` + `train-r2 (quick)`
→ `lock-verify (quick)`.

각 순환은6실행을 순차 실행하므로 전체 동시 모델 프로세스는3개, 각 CPU2threads다.
승인된 최대4개보다 작다. 각 순환은 자기 검증 결과만으로200→400 규칙을 적용한다.
서로 다른 순환의 budget/start/done 파일을 사용해 쓰기 충돌을 막는다.
최종 노드가18실행/공통초기값/예산/최선epoch/hash를 검증한 뒤 selection.lock.json 생성.
인계: rotation_{f}.done.json 및 run 산출물 → TRAIN_VERIFY.md/selection.lock.json.
평가 점수는 이 단계에서 열지 않는다.

## 단계 C: 검증된 평가 보고

`evaluate (quick)` → `independent-verify (unspecified-low)`
→ `analyze (deep-low)` → `report (writing)` → `report-check (quick)`.

독립검증은 직접재추론/다른채점계산과 hash 대조가 필요하다.
분석은 실패·훈련상태·관측손실과 관련된 하나의 해석 판단이라 deep-low를 사용한다.
보고는 한국어 연구 결과의 기술이므로 writing을 사용한다.
세부 node prompt는 이전 단계의 실제 산출물을 읽고 시작 전에 전부 정의한다.
인계: evaluation.json/예측 → VERIFY.json/md → ANALYSIS.json/md → REPORT.md → REPORT_CHECK.md.

## 실패 복구

- 같은 run에서 실패 노드만 retry, 완료 노드 수정은 amend를 사용한다.
- 본학습 생산자를 성능 때문에 재실행하지 않는다.
- 파일 누락/명세 불일치/종료코드 미확인은 FAIL이며 완료 노드 주장으로 대신하지 않는다.
- 기존 학습·입력 결과는 덮지 않는다. 코드 실패로 재실행이 필요하면 이유와 버전을 남긴다.
- 모든 단계의 실제 증거가 통과해야 목표 완료로 처리한다.
