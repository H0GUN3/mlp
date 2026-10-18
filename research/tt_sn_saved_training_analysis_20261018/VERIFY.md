# 독립 검증 기록

검증일: 2026-10-18. 입력은 허용된 native 실행의 config/split/history/summary와
저장 validation prediction, TRAIN/validation window identity metadata, 기존
검증 receipt다. RE2 및 제외 실험은 읽지 않았다.

## 독립 산술 결과

실행 방식은 resident Python eval의 assertion이며 오류 없이 완료됐다.
별도 OS subprocess를 실행하지 않았으므로 이 독립 산술의 process exit code는
해당 없음이다. 최초 VERIFY.json의 exit_code=0 표기는 담당자의 확인을 받아
null과 실제 실행 방식으로 정정했다. 수치 결과나 검사를 바꾸거나 재실행하지 않았다.
Hawkes JSON 전용 분석의 실제 CLI exit0 및 과거 학습 실행 증거와 구분한다.

- 18개 run(세 코호트 × 두 모델 × 세 seed)의 split 길이, epoch 수, batch size,
  `ceil(TRAIN/batch_size)` 계획, epoch별 `optimizer_updates`, 합계, summary 총합을
  대조했다. 6,900 계획 update = history 6,900 = summary 6,900.
- 각 실행의 epoch 순서는 설정된 50/200행으로 연속이며, history의 가장 이른
  validation joint loss 최솟값이 summary 선택 epoch/loss와 일치한다.
- 모든 run의 config/split/history/validation-prediction SHA-256이 ledger 및
  summary artifact hash와 일치했다. TRAIN/validation 표본·normal/fault 수 역시
  split과 허용 metadata identity에서 재계산한 값과 ledger가 일치했다.
- update 하나를 batch 하나로 해석하는 것은 pinned trainer의 로그 규칙에 따른
  파생치다. batch ID 및 관측된 실제 batch 크기 순서는 저장되어 있지 않다.

## SN 대응 점수 독립 재계산

세 seed × 두 모델의 SN50/SN200 저장 NPZ에서 `indices`, `labels`,
`root_logits`만 읽었다. index join, label/candidate/root 일치, 선택 epoch의
conditional Top1, 창별 전이 및 사건별 평균 softmax 확률 전이를 재계산했다.
여섯 쌍 모두 PAIRED receipt의 per-seed 전이 수와 정확히 일치했다.
모든 쌍은 78 validation 창, 65 fault 창, 28 전체 event_id이며, SN50/SN200
numeric history 첫 50행은 elapsed seconds를 제외하고 일치했다.

|모델 / seed|창 C / + / − / W / T|사건 C / + / − / W / T|
|---|---:|---:|
|DiagMLP / 11|54 / 6 / 1 / 4 / 0|25 / 2 / 0 / 1 / 0|
|DiagMLP / 23|62 / 2 / 0 / 1 / 0|28 / 0 / 0 / 0 / 0|
|DiagMLP / 37|58 / 4 / 0 / 3 / 0|26 / 1 / 0 / 1 / 0|
|Eadro / 11|26 / 0 / 0 / 39 / 0|11 / 0 / 0 / 17 / 0|
|Eadro / 23|22 / 18 / 1 / 24 / 0|11 / 8 / 0 / 9 / 0|
|Eadro / 37|36 / 15 / 5 / 9 / 0|17 / 7 / 2 / 2 / 0|

C=지속 정답, +=새 정답, −=새 오답, W=지속 오답, T=동률 미해결.
세 seed 각각 같은 28 full event_id를 포함하고 root/type가 안정적인 것을 확인했다.
모델별 84 seed-event 행은 반복 평가 기록이다. 고유 사건은 모델별 28개이며
seed를 독립 사건으로 합산하지 않았다. DiagMLP event-category union은 서로
겹칠 수 있다(C와 + 3개, C와 W 2개, +와 W 1개가 겹침).

## 학습 기록과 Hawkes 이력

- 저장된 LEARNING 표의 고정 epoch loss/conditional·gated Top1, 선택점,
  threshold/max-accuracy 지점을 대조했다. selection은 full-validation
  `validation_joint_loss`의 가장 이른 최솟값이며 accuracy 최대점으로 재선택하지
  않았다. TRAIN accuracy는 미기록.
- Hawkes absolute-before 및 relative-after 200-epoch 기록의 첫 50행을 비교했다.
  세 seed 모두 first-50 update 합은 arm마다 100이며, relative first-50은
  calibration SN50과 seconds 이외 numeric fields가 정확히 일치했다.
  각 arm의 첫 50행 안에서 따로 구한 최소 validation-loss epoch와 history Top1을
  receipt와 대조했다. 27개 config/history/summary hash가 현재 파일과 일치했다.
- 같은 epoch에서 validation loss는 모든 50 epoch에서 arms 간 달랐고,
  conditional Top1 차이는 seed별 38/33/37 epoch에서 관측됐다. 이는 저장 history
  비교일 뿐 원인이나 일반화 효과의 증거로 확대하지 않았다.

## 재사용 receipt 및 scope

- 기존 `tt50_verification.json`, `sn50_verification.json`,
  `sn200_verification.json`: 각각 PASS, 6/6 실행 확인, 실패 0.
- `evidence_paired.json`의 78개 수치/소스 파일 before/after SHA-256 map은 동일했고,
  현재 파일 hash도 기록과 일치했다. `RESULTS.json` 현재 hash는 receipt의
  `a382b76b…0b9fd5`와 일치한다. 기존 `analyze.py`는 실행하지 않았다.
- 허용 source 4종 및 TT/SN metadata hash가 ledger의 고정 hash와 일치했다.
  raw.npz와 feature arrays는 열지 않았고 checkpoint는 역직렬화하지 않았다.
  저장 validation 예측 외의 예측을 만들지 않았으며 학습·추론·Hawkes fit을 하지
  않았다. TT200, corrected SN rotation, RE2는 분석하지 않았다.

## 실패/수정 기록

독립 hash 확인의 첫 시도에서 `CALIBRATION_PROTOCOL.md` 경로를 잘못 추정해
파일 경로 오류가 났다. 허용된 native reproduction 경로로 수정해 재실행했고
모든 pinned hash가 통과했다. 수치 입력이나 파일은 변경되지 않았다.

HAWKES50 handoff에는 native/absolute summary의 status 문자열 차이를 동일시한
초기 assertion 실패가 기록되어 있다. 스키마별 status를 반영한 JSON-only 재실행은
`HAWKES50_HISTORY_PASS`로 종료했다. 기존 paired 합성 검사 11/11 통과 receipt는
재사용했고 변경 없는 검사로 재실행하지 않았다. 이번 독립 저장 자료 산술 검증은
오류 없이 완료됐다.

## 미확인 범위

사건별 검증은 기존 native window score와 다른 기술적 요약이며 이를 대체하지
않는다. SN 65 fault window는 28 사건에 걸쳐 있고, 28개 모두 TRAIN과 공유된다.
TT validation의 81 사건도 TRAIN에 포함된다. 따라서 held-out-event 최종 일반화
주장이 아니다. Hawkes absolute arm의 first-50 선택점별 저장 예측이 없으므로
사건별 전이는 미확인이다. 최종 200-epoch 예측을 그 대용으로 쓰지 않았다.
TT↔SN 차이는 표본·분포·후보 및 update 수가 함께 달라 원인 효과로 분리할 수
없다.
