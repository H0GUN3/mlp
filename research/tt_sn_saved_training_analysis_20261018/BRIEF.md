# TT·SN 저장 학습 기록 분석 — 2026-10-18

## 현재 요청과 경계

RE2 추가 전처리·학습은 사용자 선택으로 보류한다. 이미 완료한
`re2_ob_known_condition_20261018/cost_257` 산출물과 실패·복구 기록을 보존한다.
이번에는 **기존 기록 읽기·집계·검증·보고만** 한다.
새 학습, checkpoint 재추론, Hawkes 적합, RE2 집계/전처리, 보호 관측·예측 접근,
원본 수정, 설치·다운로드·프로젝트 commit은 없다.

## 네 가지 확인 사항

1. TT50·SN50·SN200의 표본 수, 배치 수, 가중치 갱신 수, 선택 epoch.
   설정으로 산술 계산한 값과 history/summary에 실제 기록된 값을 분리한다.
2. TRAIN/validation 손실과 진단 정확도의 시간 경로, SN 개선 구간,
   최소 validation joint loss 선택이 실제 진단 결과에 연결된 방식.
3. 같은 seed·사건으로 SN50·SN200 저장 예측을 대응해 새 정답·새 오답·
   지속 오답을 집계한다. 창과 seed를 독립 사건으로 세지 않는다.
4. 저장된 Hawkes absolute-before/relative-after 이력의 첫50epoch를
   대조한다. 저장되지 않은 checkpoint별 예측이나 TRAIN 정확도는
   새 계산/추론으로 채우지 않고 미확인으로 둔다.

## 대상 식별과 읽기 범위

기준 root는 `/home/gnho1236/r2/research`다.

- `native_reproduction_20261013/calibration50/TT/{diagmlp,eadro}/seed_{11,23,37}`
- `native_reproduction_20261013/calibration50/SN/{diagmlp,eadro}/seed_{11,23,37}`
- `native_reproduction_20261013/calibration200/SN/{diagmlp,eadro}/seed_{11,23,37}`
- `sn_hawkes_horizon_contrast_20261017/runs/absolute_seed_{11,23,37}`:
  DiagMLP의 과거200epoch 실행, 첫50epoch만 별도 기술한다.

주분석은 DiagMLP다. 같은 코호트의 Eadro 저장 기록은 보조표로 분리한다.
모델 간 차이를 우리 변경의 효과라고 주장하지 않는다.
TT200, corrected SN 사건 순환 분할, RE2와 섞지 않는다.

허용 파일은 위 실행의 config/split/history/summary JSON과 저장된
validation_predictions.npz, 기존 검증 JSON/보고서, 원형 trainer/model 소스다.
입력 metadata.json의 **허용 TRAIN/validation index에 대응하는 사건 식별 정보**는
읽을 수 있다. raw.npz나 특징 배열은 필요 없으며 열지 않는다.
checkpoint.pt는 역직렬화하지 않고, 필요시 기존 hash 증거만 인용한다.

`native_learning_diagnosis_20261018/RESULTS.json`과 `analyze.py`는 이미 존재한다.
변경하지 않고 관련 계산을 검증해 재사용한다. 그 스크립트에는 이번 요청 밖
특징 관측 분석이 있으므로 통째로 실행하지 않는다.

## 고정 분석 규칙

- 과거 native 점수는 장애 **창** conditional root Top1이다.
  탐지 gated 정확도·detection 지표와 구분하고, 원래 선택 규칙을 바꾸지 않는다.
- history의 TRAIN 손실은 학습 중 batch 가중 joint loss이며 validation은
  해당 epoch 종료 모델의 전체 validation joint loss다. 서로 완전히 같은
  평가 상태의 손실처럼 해석하지 않는다. TRAIN 정확도 이력이 없으면 미확인이다.
- 실행량은 실제 split index 길이, config batch size, trainer loop,
  history의 epoch별 optimizer_updates, summary의 총합을 대조한다.
  `ceil(N/batch)`는 계산값, 기록된 update 수는 로그 확인값이다.
  배치별 ID/크기가 저장되지 않았다면 실제 minibatch 실행 내역이라고 부르지 않는다.
- SN50↔SN200은 같은 모델·seed의 입력/split/scaler와 첫50epoch 이력
  동일성을 확인한다. 실제 독립 실행을 optimizer 상태의 이어달리기로
  잘못 표현하지 않는다.
- 개선 구간은 epoch1/10/25/50/75/100/150/200, 각 실행의 선택 epoch,
  최초90%/95% 도달 epoch와 정확도 최대 epoch를 **설명용**으로 표시한다.
  정확도 최대 checkpoint로 다시 모델을 선택하지 않는다.
- TT↔SN은 학습 표본·후보·입력 분포가 달라 갱신 수 차이를 인과 효과로
  분리할 수 없다. 같은 epoch가 같은 학습 기회라는 가정도 하지 않는다.

## 사건별 대응 정의

SN native validation의65장애창은28개 고유 사건에 속한다는 기존 기록이 있다.
실제 metadata로 재확인한다. key는 run_id가 포함된 전체 event_id다.
`fault04` 같은 짧은 번호만으로 합치지 않는다.

원래 창 점수와 사건 분석을 다음처럼 함께 남긴다.

1. 저장 예측을 `(model, seed, original index)`로 정확히 join하고 label,
   candidate order, event_id 및 창 집합을 확인한다.
2. 각 `(model, seed, event)` 안의 창별 새 정답/새 오답/지속 정답/지속 오답을
   기록한다. 한 사건이 여러 종류의 창 변화를 포함할 수 있음을 보인다.
3. 사건당 단일 대표 판정은 해당 사건의 저장된 validation 장애창에서
   **후보 softmax 확률을 평균**한 순위로 정의한다. 이는 이번 기술적
   오류 요약 지표이며 기존 native 창 평가나 checkpoint 선택을 대체하지 않는다.
4. 대표 판정으로 seed별 새 정답/새 오답/지속 오답/지속 정답을 집계한다.
   정확한 동률은 tie-aware credit와 별도 tie 상태로 남기며 임의로 깨지 않는다.
5. seed별28사건과 전체 고유28사건을 구분한다. 84 seed-event 기록을
   84독립사건이라 하지 않는다. 변화 사건의 union/intersection과 seed별
   상태 벡터를 함께 저장한다. 범주별 사건 union은 서로 겹칠 수 있다.

같은 사건의 TRAIN 창이 존재하므로 이 분석은 미학습 사건 일반화 평가가 아니다.
사건별 묶음 역시 물리적으로 독립된 표본임을 입증하지 않는다.

## Hawkes 첫50epoch 비교

absolute-before의 `end_times=start+10`과 relative-after의 `end_times=10`을
구분한다. 둘 다 저장된200epoch 실행의 첫50행을 쓴다.
relative 첫50과 SN50의 같은 이력임을 먼저 확인한다.
동일 epoch 비교와 각 arm의 첫50구간 내 최소 validation loss 선택점을
구분한다. 해당 선택점의 root 정확도는 history에 기록된 값으로만 보고한다.
absolute의 첫50구간 선택 예측 파일이 없으면 사건별 전환은 미확인이다.
200epoch 최종 선택 예측을 첫50epoch 예측으로 대체하지 않는다.

## 실행 계획과 파일 소유권

분리된 경로3개를 병렬로 시작하고, 이력 분석과 종합 검증으로 합류한다.
작업 폭3→1→1. 이번 폴더에만 새 분석 코드·산출물을 만든다.

- ledger / quick: 실행 경로·모델·설정·실제 기록량의 고정 목록과
  RUN_LEDGER.md/json, 필요시 ledger.py와 작은 self-check.
- learning / unspecified-low, ledger 의존: 같은 이력의 손실/정확도·선택
  관계를 해석해야 하므로 LEARNING.md/json, 필요한 분석 코드/검사를 소유.
- paired / deep-low: 창과 사건의 다중 대응·확률 집계·seed 중복 경계를
  함께 검사해야 하므로 PAIRED.md/json/행 목록, 분석 코드와 합성 검사를 소유.
- hawkes / quick: 기존 두 arm의 첫50행과 source 근거만 대조해
  HAWKES50.md/json, 필요한 작은 분석 코드/검사를 소유.
- verify-report / unspecified-low, 모두 의존: 결과간 단위·산술·근거·
  미확인을 대조하고 VERIFY.md/json과 한국어 REPORT.md를 작성한다.

기존 source·입력·예측의 hash를 남기며 변경하지 않는다.
설명 문서의 정상적인 보완을 수치 입력 변경으로 오인해 작업을 중단하지 않는다.
필수 수치 artifact의 불일치는 원인을 확인하고 해당 경로만 복구한다.
없던 자료를 생성한 것처럼 주장하지 않는다.
NumPy/stdlib와 기존 환경을 사용하며 pandas나 새 패키지는 필요 없다.
원래 학습 명령이나 inference CLI를 실행하지 않는다.
새 비자명 집계 코드는 작은 합성 검사와 실제 저장 자료 독립 산술로 확인한다.
이미 통과한 변경 없는 검사/재채점은 반복하지 않는다.

## 종료

네 요청에 대한 확인값·계산값·미확인과 해석 한계를 한 번에 보고한다.
RE2 보류는 유지하고 새 학습·추론·전처리 없이 종료한다.
