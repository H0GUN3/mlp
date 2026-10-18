# Eadro 인계

- **통과:** 허용 개발 bundle metadata에서 사건 3-fold, recording holdout,
  fault-type holdout의 전체 membership 및 지원 수를 계산했다.
- **고정 사실:** SN 36건/4 fault recording, TT 81건/9 fault recording.
  두 자료 모두 3개 fault type이며 모든 root×type 조합은 한 번씩만 관측됐다.
  각각 normal-only archive recording 3개가 더 있으나 이는 fault 정답 수를
  늘리지 않는다.
- **역할:** 사건 3-fold는 이미 사용된 개발 사건의 설정 탐색에만 쓴다. Recording
  holdout은 각 경우 root 3개가 TRAIN에서 빠지는 한계를 보인다. Fault-type
  holdout은 root를 유지하지만 정상 창도 연결 episode의 종류를 따라 배정한다.
- **비채택:** 어떤 정책도 최종 평가 분할로 채택하지 않았다. 새로운 모델 정확도,
  학습 가능성 또는 독립 최종평가 적합성은 입증하지 않았다.
- **재현:** `EADRO.md`에 단위검사·진단 결과와 실제 monitor/session ID, exit 0,
  `EADRO_SUITABILITY_PASS`의 보존 응답이 있다. `eadro_trial.json`에는 정확한
  창/사건 membership과 input/source SHA-256이 있다.

실험 범위는 메타데이터에 한정된다. Native test/unassigned 자료, RCAEval 보호 관측,
feature arrays, checkpoints, inference, 추가 학습에는 접근하지 않았다.
