# TT 고정 기준선 계약 — 결과 확인 전

- 입력: `../tt_native_support_20261014/artifacts/TT.npz` 및 `TT.json`.
  NPZ SHA256 `2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597`;
  JSON SHA256 `07c3ad8ae9331dc4d48b0e4a728e34a9d5bf2c87c985d8792d9d50220f355948`.
- 허용4069행만 디코딩: 기존 원본5814행 seed42 분할의 train3256/validation813.
  test1744/unassigned1 관측은 접근하지 않는다. 원본 index만 메타데이터로 검증.
  같은 사건의 다른 창이 양쪽에 있는 분할임을 명시하며 사건 일반화로 부르지 않는다.
- 후보27개/원형44간선/metric7채널/trace2채널(둘째0)/Hawkes60차원.
  이미 준비된 native frontend 입력만 사용한다. 18특징 요약으로 대체하지 않는다.
- `native_models.NativeReference`의 Eadro 및 수식 기반 DiagMLP 복원본을 재사용한다.
  공통 encoder/head 초기값과 학습 창 순서를 seed별로 맞춘다.
  GLU·fusion·위치·dropout 차이를 GNN 하나의 순수 효과라 하지 않는다.
- Adam lr0.001, batch256, **고정50epoch**, seed11/23/37: 두 방법×3=6회.
  epoch당13회, 실행당650회 업데이트. 결과에 따른 연장/재튜닝 없음.
  CPU2 threads/interop1; 최대3개 학습 프로세스 병렬.
- 목적은 기존 joint loss(탐지CE0.5+장애 창 rootCE0.5).
  metric/trace scaler는 TRAIN 정상+장애 창만으로 평균/표준편차를 적합한다.
  기존 epsilon1e-8/상수 채널 정책을 보존하고 clipping은 추가하지 않는다.
- checkpoint: validation joint loss 최소, 정확한 동률이면 이른 epoch.
  선택 checkpoint와 고정50epoch checkpoint의 TRAIN/validation 예측을 모두 남긴다.
  validation은 선택·진단 자료이며 독립 최종시험 결과가 아니다.
- 주지표는 장애 창별 conditional Top1/3/5. 보조는 탐지 gating을 적용한 Top1/3/5,
  탐지 precision/recall/F1, root NLL 및 joint loss. 정상 정답을 root 분모에 넣지 않는다.
  정확한 동률은 균등 기대 credit. 사건별 창 적중률 평균은 별도로 보고할 수 있다.
  사건 전체 확률 평균을 기본 채점으로 사용하지 않는다.
- 논문 50epoch/batch256과 DiagMLP 보고 train/valid 크기에 가깝게 맞추되,
  정확한 저자 split identity·모델 통합·checkpoint 선택 규칙은 미확보다.
  기존 공개 수리 포크/수식 복원 및 전처리 교정도 명시한다.
  따라서 “공개 설정을 참고한 고정 조건 기준선”이지 정확한 원논문 재현은 아니다.
- 보호 시험을 통한 최종 비교는 이번 개발 실행에 포함하지 않는다.
