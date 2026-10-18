# 네트워크 장애 오분류의 제한된 원인 진단

## 목표

사용자 요청: 대단한 발견보다 특정 부분의 개선을 정량적 평가와 논리로 입증한다.
먼저 현재 SN/TT 네트워크 지연·손실 root-service 오분류를 설명할 근거를 확인한다.
호출 관계가 해답이라고 가정하지 않는다.

## 범위와 보존

- 허용 입력: relationship_smoke_20261013/artifacts의 SN/TT 개발 bundle,
  relationship_cv_20261014/results의 manifest, fold statistics, 54개 run의
  config/history/predictions/checkpoint, 기존 relationship_diagnosis_20261014 결과 및 코드.
- bundle에는 이미 선택된 개발 관측만 있다. 원본 수집 스트림, native_inputs,
  protected/test/unassigned 관측, RCAEval/RCABench 관측을 열지 않는다.
- 체크포인트는 고정된 최종 모델의 TRAIN/validation 추론에만 사용한다.
  optimizer, backward, 재학습, 튜닝, 체크포인트 선택, 입력 교란 실험을 실행하지 않는다.
- 기존 함수의 순수 변환만 재사용한다. 원자료 로더와 학습 entrypoint를 실행하지 않는다.
- 이전 산출물은 수정하지 않는다. 해시로 입력을 묶고 종료 시 다시 확인한다.
- 모든 새 코드·결과·보고서는 이 디렉터리에만 생성한다. 설치·커밋하지 않는다.

## 결과를 보기 전 고정한 진단

### A. 입력/특징 단서 — 주 에이전트

각 validation fold의 저장된 정상 TRAIN reference로 기존 18개 특징을 복원한다.
정규화는 저장된 TRAIN standardizer만 사용한다.

1. 원인 서비스 trace latency 관측과 정상 참조 부재로 마스킹되는 비율.
2. 원인과 다른 후보의 로컬 모델 입력(value, mask, coverage)이 완전히 같은 비율.
   동일 입력이면 local/global의 공유 scorer가 구분할 수 없다는 제한만 판단한다.
   동일 입력이 없다고 해서 식별 가능성을 증명하지 않는다.
3. 고정 비학습 단서 점수: 기존 signed-log-z mean의 절댓값을
   CPU(0:3), network bytes(5:7), latency(7), span count(8), all(0:9) 안에서 최대화.
   마스크된 채널은 0이다. 모든 후보에 동일 규칙을 적용하고 동점을 균등 처리한다.
   서비스별 장애 라벨을 점수 계산에 사용하지 않는다. 이는 진단용 probe이지
   튜닝된 모델·선행연구 재현·새 검증집합 결과가 아니다.
4. probe가 맞히는데 고정 Directed 모델이 틀리는 질량과 반대 방향을 모두 보고한다.
   각 probe를 별도로 보고하며 정답을 보고 유리한 probe를 선택한 합성 정확도를 만들지 않는다.
5. 10초 signed 평균에서 상쇄되는 변화의 크기를 root에서 측정한다.
   원시 시간순서/peak를 복구한 개선 실험이나 정보 부족의 인과 증명으로 부르지 않는다.

### B. 학습 상태/평가 조건 — 독립 child

1. 54개 저장 history의 1→5 및 4→5 TRAIN CE 변화와 실제 optimizer step 수.
   history는 epoch 중 업데이트되는 모델의 손실 평균이지 최종 모델의 고정 CE가 아니다.
2. 최종 체크포인트로 TRAIN/validation을 평가해 fault type별 Top1/Top3/MRR/CE를 보고한다.
   validation logits가 저장 predictions와 재현되는지 확인한다.
3. 집계 순서: 창→seed/해당 fold 평가→사건 균등. TRAIN 사건은 두 fold에 등장하므로
   독립 사건으로 중복 집계하지 말고 사건 안에서 평균한다.
4. root별 TRAIN 두 유형/validation 한 유형 구조를 명시한다.
   TRAIN 실패는 표현/최적화/정보 중 원인을 단독 확정하지 못한다.
   계속 감소하는 CE는 미수렴 가능성이지 학습 연장 효과의 증명이 아니다.

## DAG와 검증

코드·계약 확인 → A와 B 병렬 → 근거 대조·보고서.
부모 쓰기: PROTOCOL.md, signals.py, test_signals.py, signals.json, REPORT.md,
pyrightconfig.json, VERIFY.md. Child 쓰기: training.py, test_training.py,
training.json, TRAINING.md, TRAINING_EVIDENCE.md.

작은 synthetic fixture로 마스크, 동점, 사건 균등 집계, 상쇄 진단을 검증한다.
프로젝트 Python 환경에서 테스트·분석 producer exit0, 정적 진단,
54개 validation 재현 및 기존 사건별 점수 대조, 입력 해시 불변을 확인한다.
원인 판정은 확정된 기계적 사실/정량적 연관성/미확인 가설을 구분한다.
근거가 부족하면 단일 원인을 지어내지 않고 다음의 좁은 대조실험을 제안만 한다.
