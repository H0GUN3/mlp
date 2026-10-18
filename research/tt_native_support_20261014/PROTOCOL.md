# TT native-like 기준 모델 → 관측 개수 보완: 사전 실험 계약

2026-10-14. 사용자 “진행”에 따른 제한된 실행이다.
이 문서는 새 모델 학습·새 결과 열람 전에 작성했다.

## 범위와 데이터 경계

- TT만 사용한다. 후보 서비스 27개, 개발 사건 81개.
- 입력 행은 `relationship_smoke_20261013/artifacts/TT.npz`의 기존 허용
  4,069개 개발 창(장애3,451 + 정상618)과 동일한 index/order/event/fold다.
- 기존 native raw/prepared NPZ는 열지 않는다. 보호 test/unassigned,
  RCAEval/RCABench 관측·예측도 사용하지 않는다.
- metric7채널·native mean latency는 허용 bundle의 values에서 재사용한다.
  native trace 두 번째 채널은 0으로 유지한다. 기존 retained count를 이 채널에
  넣으면 원 기준 모델이 달라지므로 금지한다.
- raw logs/spans를 읽을 때 timestamp routing 후 허용 개발 초/창만 의미를
  처리·보존한다. 원 JSON 바이트는 파싱/해시를 위해 스캔하되 다른 창은 사용하지 않는다.
- 원 source-designated TT 정상 로그 reference 3개는 **공통 TRAIN reference**다.
  이전 native 계약과 같은 auxiliary normal 로그로 Drain template을 한 번 만들고
  정상 reference의 출처/해시를 공개한다. 이 자료는 평가 사건/정답이 아니다.
- 전역 scaler·학습 가능한 model은 각 fold TRAIN만 fit.
  Hawkes는 원 방법의 관측 창별 case-local 입력 변환으로 허용 개발 창 각각에서
  실행하며 전역 validation 적합/하이퍼파라미터 선택과 구분한다.
- 기존 `TT_metadata.json`/`TT/metadata.json`은 필요하면 source hash·고정 그래프·
  template 출처의 **메타데이터만** 참고할 수 있다. native observation NPZ 접근은 금지.
- frozen source/results/기존 사용자 파일을 수정하지 않는다.
  모든 새 코드·cache·모델·보고서는 이 디렉터리 안에만 둔다.

## 공통 native-like 입력 계약

`artifacts/TT.npz`:

- `metrics`: float64 [W,27,10,7]
- `traces`: float64 [W,27,10,2], 채널0 기존 latency, 채널1=0
- `logs`: float64 [W,27,E], native Hawkes baseline vectors, 유한·비음수
- `unique_count`: int64 [W,27], 동일 service/window 안 (traceID,spanID) 한 번
- `labels`, `indices`, `fold_ids`: int64 [W]
- `event_ids`, `episode_ids`: Unicode [W]

W=4069. E=template 수+unseen bin; 원 Drain 설정·normal reference로 결정한다.
로그 없는 service/window는 원 계약처럼 zero log vector.
로그 있는 창은 원 Hawkes 함수와 zero-time placeholder 규칙, 상대 horizon10,
tie jitter1e-5, `seed=42+original_index*27+node`를 사용한다.
solver iteration cap·warning·유한성은 기록하고 수렴했다고 단정하지 않는다.

`artifacts/TT.json`:
`system`, `services`, `event_count`, `edges`(E×2 pair 목록), `windows`,
`faults`, `event_folds`, `npz_sha256`, `input_hashes`, `source_hashes`,
normal-reference/template·Hawkes·unique-count 감사 및 처리 비용.
순서는 기존 개발 manifest와 정확히 동일하며 static graph는 author Info의
고정 서비스 구조를 코드에서 재사용한다. validation trace로 그래프를 fit하지 않는다.
누락 후보를 삭제하거나 정답을 입력 feature로 만들지 않는다.

## 분할·모델·학습 선택

- 기존 incident fold0/1/2 유지. fold별 54사건 TRAIN, 27사건 validation.
  같은 root의 두 고장 유형으로 학습하고 남은 유형을 validation에 둔다.
  정상 창은 기존 episode_ids의 fold를 그대로 따른다.
- seed11/23/37, baseline `eadro`/`diagmlp`: 총18회.
- 기존 `native_models.NativeReference`의 보존 인코더·공동 detector/localizer,
  방정식 기반 DiagMLP 교체를 재사용한다. native 구현 출처와 private wiring
  미확인 경계를 그대로 공개한다. 저자 원 실험의 완전한 재현이라고 부르지 않는다.
- 두 모델에 dropout=0.1을 **명시**하고 나머지 폭은 NativeReference 계약을 유지.
  예전 로컬 Eadro dropout=0 기본값을 몰래 섞지 않는다.
- Adam lr0.001, batch256, weight_decay0, 최대200epoch **고정**, 임의 연장/튜닝 없음.
  native joint loss = 0.5*detection CE + 0.5*fault-window root CE.
  원형 목적을 보존하므로 새 event weighting을 loss에 추가하지 않는다.
- 매 epoch full-validation joint loss의 엄격한 최솟값 checkpoint를 선택.
  동률은 이른 epoch. 정상만 있는 batch의 root loss는0.
  선택에 사용한 validation에서 개발 성능을 보고하는 한계를 명시한다.
- shuffle·초기화·결정적 연산·thread 수 기록. 프로세스당 torch2 threads,
  최대3개 동시 학습. 가능 자원에 따라 동시성만 줄일 수 있고 학습 조건은 바꾸지 않는다.
- checkpoint·root/detection logits·indices·labels·event IDs·history·scaler·초기 가중치/
  설정 해시를 보존하고 저장 모델 재추론을 정확히 대조한다.

## 관측 정보 및 평가

주 평가: **장애 조건부 사건 균등 Top1**, 보조 Top3/MRR.
동점은 균등 기대 credit. 먼저 사건 내부 창, 다음 seed, 마지막 사건을 평균한다.
정상 정확도를 root 점수에 섞지 않는다. 탐지 지표는 별도다.
CPU/지연/손실, root unique_count=0/>0 부분집합과 분모를 보고한다.
같은 사건이 두 관측 부분집합에 걸칠 수 있다.
TRAIN도 최종 선택 checkpoint로 평가해 학습 실패와 validation 실패를 구분한다.
3seed는 같은 사건의 반복 학습이지 독립 사건을 3배로 늘리지 않는다.

## q 실험 진입 gate — 효과 입증이 아닌 탐색용 공학 기준

baseline18회와 입력 검증·재현이 모두 성공해야 한다. 다음을 사전 고정한다.

1. DiagMLP의 9개 run 중 **선택 epoch가200인 run이 없어야** 한다.
   이는 수렴 증명이 아니라 상한 의존성 경고를 피하는 보수적 조건이다.
   하나라도 걸리면 q 진입을 보류하고 학습 예산 한계를 보고한다.
2. DiagMLP의 network(delay+loss) 사건 균등 Top1 ≤95%:
   최소5%p 오답 여지가 있어야 한다.
3. delay/loss 각각의 root count0/>0 집합에 고유 사건이 최소5개씩 있어야 한다.
4. 각 seed의 network에서 count>0 집합 Top1 − count0 집합 Top1이
   5%p 이상인 seed가3개 중2개 이상이어야 한다.
   유형별 차이도 전부 기록한다. 이 사후 부분집합의 구성 차이를 인과 효과로 부르지 않는다.

하나라도 미충족이면 조건부 q task를 기각/보류하고 baseline+gate 근거를 보고한다.
조건·threshold를 결과에 맞춰 바꾸거나 유리한 유형/seed만 선택하지 않는다.

## gate 통과 시 한 변경

- `q_i=log1p(unique_count_i)` 한 scalar를 DiagMLP Modal Fusion 전에 추가.
  metric/log/trace encoder, position, node fusion, heads, loss, 학습 조건은 동일.
- 같은 seed의 원 DiagMLP 초기 상태를 보존하고 추가 q 가중치는0으로 시작.
  새 Linear 생성 시 RNG 상태를 복원해 기존 초기화/dropout RNG 예산을 보존한다.
  초기 값·q=0 기능 동등성을 synthetic test로 확인한다.
- `diagmlp_count`: 같은3fold×3seed=최대9회. native latency weighting은 바꾸지 않는다.
- 탐색용 효과 판단: 전체 사건 Top1 개선≥2%p, seed별 개선이2/3 이상,
  CPU Top1 하락≤1%p. 이를 통과하면 `diagmlp_zero_count`(같은 추가폭, q항0)
  최대9회를 더 실행해 추가 폭/수치 경로 대조를 한다.
- 입력 보완 효과만 주장한다. architecture 우위를 주장하려고 Eadro에 불리한
  정보 차이를 숨기지 않는다. Eadro+q 확장은 이번 실행 범위가 아니다.
- q 개선이 zero-count 대조와 구분되지 않으면 관측량 정보 효과 주장을 하지 않는다.

## 비용·검증·중단

- 입력 parsing/Hawkes/count 비용, 학습+validation 시간, checkpoint 추론 시간,
  peak RSS를 분리한다. cache 이후 forward 시간만 전체 비용으로 부르지 않는다.
- 추가 처리·추론 비용 증가와 정확도 이득을 함께 보고하며 새 SLA/경량성 우위로
  과장하지 않는다. 기존5epoch 또는 논문 window split 점수와 직접 순위 비교 금지.
- synthetic tests: 보호 index 제외, TRAIN-only scaler, event/seed 집계·동점,
  모형형태·q0 동등성·보완항 gradient·metadata routing.
- real checks: source/input hash 불변, 모든 사건/창/seed coverage,
  checkpoint 재현, 별도 scorer 대조, train/validation event disjointness,
  LSP 및 프로젝트 정적 진단, 실제 producer/test/fit exit0.
- 입력/solver/학습 실패는 고친 뒤 해당 검사만 재실행하며 불리한 결과를 삭제하지 않는다.
  별도 fit이 중단되면 미완료 상태를 보존하고 재시도 이력을 기록한다.
- 기존 자료는 반복 사용된 개발 자료다. 새 사건·새 환경·최종 평가 성능이나
  관측 개수 활용의 신규성을 입증하는 실험이라고 부르지 않는다.
