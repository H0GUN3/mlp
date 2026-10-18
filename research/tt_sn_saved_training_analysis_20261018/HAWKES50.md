# Hawkes 교정 전후의 첫50epoch — 저장 이력 분석

## 범위와 결과

DiagMLP의 absolute-before(`end_times=window_start+10`)와
relative-after(`end_times=10`)를 비교했다. 각 seed의 기존200epoch
실행에서 첫50개 history 행만 분석했다. relative의 첫50 손실·점수·
optimizer_updates는 별도 SN50 실행과 모두 정확히 같았다(시간 제외).
새 학습·추론·입력 배열 열람은 없다.

**첫50구간에서 교정 후의 일관된 정확도 개선은 관측되지 않았다.**
각 arm의 첫50구간 최소 validation joint-loss 선택점으로 비교하면,
seed 평균 conditional root Top1은91.2821%→89.7436%다.
이는 미리 저장된 history의 요약이며 최종시험이나 새 checkpoint 선택 실행이 아니다.

| seed | absolute 선택 epoch / 정답 수 | relative 선택 epoch / 정답 수 | 상대−절대 |
|---|---:|---:|---:|
| 11 | 49 / 59개(65창 중) | 49 / 55개(65창 중) | −6.1538%p |
| 23 | 50 / 61개(65창 중) | 48 / 62개(65창 중) | +1.5385%p |
| 37 | 50 / 58개(65창 중) | 50 / 58개(65창 중) | 0%p |

각 실행의 첫50구간은 실제 history 합산100회 update다.
해당 선택점까지의 실제 기록 합산은 absolute98/100/100,
relative98/96/100회다.
65는 상관된 validation 장애창 수이며 seed별 독립사건65개가 아니다.

## 같은 epoch 비교

아래는 세 seed의 평균이며 위의 구간 내 선택점과 다르다.
TRAIN은 online batch 가중 joint loss, validation은 해당 epoch 종료
모델의 전체 validation joint loss다.

| epoch | absolute TRAIN / VAL 손실 | relative TRAIN / VAL 손실 | absolute / relative Top1 |
|---|---:|---:|---:|
| 1 | 1.611216 / 1.510576 | 1.611784 / 1.511070 | 3.0769% / 3.5897% |
| 10 | 1.316585 / 1.380523 | 1.313783 / 1.378220 | 16.4103% / 16.9231% |
| 25 | 0.683917 / 0.788291 | 0.673662 / 0.796648 | 65.6410% / 65.6410% |
| 50 | 0.066865 / 0.238108 | 0.064722 / 0.259649 | 89.7436% / 89.2308% |

seed11/23/37 모두 첫50개 validation loss 값이 arm 사이에서 달랐다.
Top1이 달랐던 epoch 수는38/33/37개다.
수치 차이가 있다는 것과 일관된 학습 가속·진단 개선은 다른 주장이다.

## 확인하지 못한 것

- absolute 첫50구간 선택점의 별도 예측은 확인되지 않았다. 기존 directory에는
  전체200epoch 중 선택된 checkpoint/validation_predictions가 있으며,
  선택 epoch는190/115/164다. 이를 첫50구간 예측으로 대신 쓰지 않는다.
  따라서 첫50구간 arm 간 사건별 새 정답·새 오답은 미확인이다.
- TRAIN 정확도 이력과 매 epoch 사례별 logits가 없으므로 어느 사건을
  언제 처음 맞혔는지, 어느 modality를 학습했는지는 복구하지 않는다.
- 원래 horizon 대조의 설정·입력 동등성은 기존
  `sn_hawkes_horizon_contrast_20261017/{SOURCE_EVIDENCE,EXECUTION_VERIFY,REPORT}.md`
  의 검증 범위를 인용한다. 이번에는 특징 배열을 재검사하지 않았다.
- 양쪽 전체200epoch의 선택 Top1 평균95.38%라는 기존 결과는 별도 문맥이다.
  첫50구간의 선택 결과와 섞지 않는다.

## 검증과 실패 기록

`hawkes50.py`는 history/config/summary JSON27개만 읽고 각 summary의
config/history hash, 실제 epoch 수·update 합·최소 손실 선택을 확인했다.
모든 읽은 JSON의 전후 hash는 같다. 작은 exact-tie 최초 epoch self-check도 통과했다.
생성 `HAWKES50.json`의 세 seed 첫50 선택점은 기존
`native_learning_diagnosis_20261018/RESULTS.json:hawkes_first50`과 정확히 일치한다.

첫 부모 실행은 native summary의 `passed`와 absolute summary의 `PASS`를
같은 문자열로 가정해 실패했다
(`mon_XVR4EP6W4B4Q8P3Y`, exit1, 입력/결과 수정 없음).
각 실행의 명시적 스키마를 반영한 후
`mon_283HA40NJ43CTYKS`에서 `HAWKES50_HISTORY_PASS`, 실제exit0을 확인했다.
소스 SHA256은
`0adc9928be5bc0c6de5b0d97ccc782ec002d5dea2da1cf13eb11ed8f579f37ee`다.

초기 child는 `raw.npz`를 참조했다고 보고하고 산출물 없이 종료했으나,
후속으로 제출한 정확한 명령에는 JSON history/config/summary만 있었으며,
스스로 해당 raw 파일 참조·열람·해시·배열 복호화가 없었다고 정정했다.
그 명령은 assertion으로exit1이었다. 초기 완료 상태를 분석 성공으로
취급하지 않았고 부모의 위 JSON 전용 실행으로 누락 산출물을 보완했다.
