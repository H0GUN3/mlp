# 호출 방향 문맥 — 제한된 후속 개발 교차검증

## 결정과 범위

2026-10-14 사용자가 “해보는게 좋을 것 같으면 진행해”라고 재량을 주었다.
기존 fold0 스모크에서 SN은 directed가 global보다 좋고 TT는 반대였다.
따라서 전체 연구 로드맵을 재개하기보다 이 내부 비교의 분할·초기화 민감도부터
작게 확인한다. 이 계약은 새 실행 결과를 보기 전에 작성한다.

영향 범위는 이 디렉터리의 실행기·검사·결과뿐이다.
기존 모델·분할·준비기·결과는 수정하지 않고 함수와 개발 bundle을 읽기 전용 재사용한다.
기존 보류 항목은 [DEFERRED.md](DEFERRED.md)에 모두 보존한다.

## 실행 DAG

`기존 계약 확인 → 개발 bundle 해시/분할 검사 → fold별 TRAIN 정규화`
→ `고정 설정 54 fits → checkpoint 재추론/독립 채점 → 사건별 비교와 보고`.
새 코드의 합성 검사는 실제 학습 전에 끝낸다.

## 입력과 누출 경계

- `relationship_smoke_20261013/artifacts/{SN,TT}.{json,npz}`만 관측 입력이다.
- 원본 native test/unassigned, RCAEval, RCABench 관측 파일에는 접근하지 않는다.
- 기존 bundle의 `values`, `observed`, `adjacency`는 허용 개발 행만 포함한다.
- 메타데이터 감사의 3-fold 규칙을 그대로 사용한다.
- 각 fold의 정상 TRAIN만으로 median/IQR reference를 재적합한다.
  해당 fold의 전체 TRAIN(정상+고장)만으로 특징 standardizer를 재적합한다.
  fold0의 정규화된 x나 통계는 다른 fold에 사용하지 않는다.
- validation 값 변경에 reference/standardizer/TRAIN 입력이 불변임을 검사한다.
- 사건·episode 비중첩, 동일 recording 안의 선택 창 비중첩, 보호 행 제외,
  모든 사건의 validation 1회 배정을 기존 감사 함수로 다시 검사한다.
- 같은 recording의 다른 사건이 양쪽에 남는다. recording 독립·물리 시계 정합성·
  10초 종료 즉시 관측 가능성은 보장하지 않는다. 이미 사용한 개발 사건이다.

## 고정 학습 계약

- 시스템 SN/TT, fold 0/1/2, seed 11/23/37, local/global/directed.
- 총 54 fits, 각각 **정확히 5 epoch의 최종 가중치**를 사용한다.
- validation을 checkpoint 선택·조기 종료·튜닝에 사용하지 않는다.
  기존 스모크는 best-validation checkpoint였으므로 그 결과와 숫자를 합치지 않는다.
- 기존 RelationRanker 3,361개 파라미터, 입력54, hidden32, head98→16→1 그대로.
- Adam lr 0.001, weight_decay 0.0001, batch32, CPU2 threads, GPU 없음.
- 사건 역빈도 가중 CE, 모드 간 초기 가중치와 batch 순서 동일.
- 서비스 ID/위치 embedding, 새 특징, 네트워크 방향 추론 등을 추가하지 않는다.
- 5 epoch는 작은 고정 업데이트 예산이다. 동일 wall-clock/FLOPs 예산 또는 수렴 비교가 아니다.

## 검증과 집계

- 새 코드 단위검사, 명시적 프로젝트 타입 검사, 54 checkpoint 별도 프로세스 재추론.
- 원본 행/labels/events, normal reference, standardizer, source/input hashes 확인.
- 기존 tie-aware scorer로 사건별 Top1/Top3/MRR, 별도 기존 Top1 scorer와 대조.
- 각 사건을 seed별 한 번씩 validation에서 평가한다. seed 평균으로 사건당 한 행을
  만들고 사건 균등 평균을 구한다. seed를 독립 사건 수로 늘리지 않는다.
- 주 비교 directed−global, 보조 비교 directed−local.
- seed별 전체 성능과 fold별 seed 평균, 사건별 win/tie/loss를 함께 보고한다.
- 짝지은 사건 차이를 recording 단위로 복원추출하는 percentile bootstrap:
  5,000회, seed 20261014, 2.5/97.5 분위수. 선택된 recording의 모든 사건을 함께
  넣고 사건 균등 평균을 다시 계산한다. 이는 작은 4/9 recording과 겹치는 학습 집합에
  조건부인 탐색적 구간이지 독립 최종 모집단에 대한 유의성 증명이 아니다.
- fit 시간과 준비/검증 포함 프로세스 시간·최대 RSS를 기록한다.
  원자료 추출 비용은 기존 준비에서 이미 지불했으므로 end-to-end 비용 우위를 주장하지 않는다.

## 판단과 종료

두 시스템에서 directed−global 평균이 양수이고 각각 적어도 2/3 fold 및
2/3 seed에서 양수면 “확장 검토 가치 있음”으로만 판정한다.
그 외에는 “일관된 개선 근거 부족: 전체 비교 확장 보류”로 판단한다.
이 기준은 신규성·문헌 경쟁력·통계적 유의성 기준이 아니다.
어떤 결과든 epoch/seed/특징을 늘려 재탐색하지 않고 보고 후 종료한다.

기존 파일은 덮어쓰지 않는다. 실패 시 부분 산출물은 남기고 성공으로 표시하지 않는다.
코드 오류 수정으로 같은 계약을 다시 실행해야 한다면 새 실행 경로를 사용한다.
문헌 방법 본실험, few-shot, 전이, RCABench 학습, 최종평가, 설치·다운로드·commit은 하지 않는다.
