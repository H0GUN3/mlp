# DiagMLP 저성능 원인 점검

2026-10-17 · 기존 허용 입력·저장 예측·학습 로그의 읽기 전용 분석

## 1. 무엇이 낮았는가

확인된 저성능은 **SN(Social Network)의 사건 분리 평가에서 실행한 DiagMLP 수식 복원본**이다.
원 논문의 저자 실행본 자체가 SN에서 실패한다고 확인한 것은 아니다.

| SN 로컬 실행 조건 | DiagMLP Top-1 | 점수의 의미 |
|---|---:|---|
| 기존 SN200 창 분할 | 95.38% | 검증 장애 65창/run, 3 seed 평균. 같은 사건의 창이 학습·검증에 걸칠 수 있음 |
| 사건 분리 평가 | 25.00% | 36사건 각각의 창 확률을 평균해 한 순위, 3 seed 평균 |
| 사건 분리 평가의 같은 예측을 창별 채점 | 23.59% | 325장애창, 3 seed 평균 |

95.38%와 25%의 차이를 한 요인의 효과로 해석하지 않는다. 분할, 입력 준비 경로,
학습량·batch 크기, 정규화 적합 자료, 모델 선택 기준과 채점 단위가 다르다.
다만 같은 사건 분리 예측을 창별로 채점해도 낮으므로, 이번 저성능은 사건별
확률 평균이라는 채점 방식만의 현상이 아니다.

근거: `../native_reproduction_20261013/sn200_verification.json`의
`runs[kind=diagmlp].score_recomputations[metric=conditional_top1].independent`
(seed 순서 11/23/37: 0.9230769231 / 0.9846153846 / 0.9538461538),
`../sn_corrected_20261017/WINDOW_RESCORE.md`,
이번 `RESULTS.json:scores.evaluation`.

## 2. 실패 위치: CPU와 네트워크 지연

선택된 checkpoint의 사건 Top-1을 저장 logits에서 다시 계산했다.

| 고장 종류 | TRAIN | validation | query 평가 |
|---|---:|---:|---:|
| CPU 부하 | 91.67% | 11.11% | **8.33%** |
| 네트워크 지연 | 86.11% | 58.33% | **2.78%** |
| 네트워크 손실 | 75.00% | 8.33% | **63.89%** |
| 전체 | 84.26% | 25.93% | **25.00%** |

각 고장 종류는 12개 고유 사건이다. 세 seed의 36회 예측을 36개 독립 사건으로
세지 않는다. TRAIN·validation·query는 순환별로 다른 사건과 다른 checkpoint의
평가를 집계한 것이므로, 같은 사건·같은 모델의 짝지은 일반화 차이는 아니다.
validation과 query의 종류별 우열이 뒤집히는 점도 전체 평균만으로 숨기지 않았다.

**분할에서 실제로 달라진 조건:** 각 순환 TRAIN에는 서비스마다 장애 사건이
하나씩 있고, 고장 종류마다 4사건이다. query 36사건 모두에서 정답 서비스는
TRAIN에 존재하지만 **그 서비스의 해당 고장 종류는 TRAIN에 없다**.
108개 사건-seed 평가 전체에서 확인했다. 이는 미지 서비스 시험이 아니라
같은 시스템의 **미학습 서비스·고장 조합**에 대한 시험이다.

근거: `RESULTS.json:scores`, `query_root_fault_combination_unseen_count`,
`query_event_seed_evaluations`; `diagnose.py`의 서비스 지원·종류별 균형·사건 분리 assert.

## 3. CPU: 입력에는 정답 단서가 있지만 모델이 활용하지 못했다

CPU 장애 12사건의 **107개 고유 창 전부**에서 정답 서비스의 시간 평균
`cpu_usage_total`이 다른 11개 서비스보다 엄격하게 컸다.
각 순환의 고정 TRAIN scaler로 정규화한 뒤에도 **107/107창에서 정답이 최댓값**이었다.

그런데 DiagMLP는 CPU 사건-seed 36회 중 3회만 맞혔다(8.33%).
따라서 이 CPU 실패를 **“CPU 단서가 관측되지 않았기 때문” 또는
“정규화하면서 정답의 CPU 순위가 사라졌기 때문”**이라고 설명하는 것은 실제 입력과 맞지 않는다.
이 최대값 검사는 CPU로 라벨링된 자료에서 한 사후 진단이며,
다른 고장까지 해결하는 새 기준법이나 일반화 성능을 입증한 것은 아니다.

오답의 방향도 대조했다. CPU 사건-seed 오답 33회 중 **26회(78.79%)**는
그 순환 TRAIN에서 CPU 장애를 경험한 다른 서비스를 선택했다.
네트워크 지연 오답은 35회 중 21회가 TRAIN에서 지연을 경험한 서비스를 선택했다.
이는 **학습된 서비스·고장 조합 쪽으로 잘못 연결하는 경향**과 일치한다.
하지만 서비스별 선택 빈도 등을 통제한 인과 실험은 아니므로
“고장 종류를 외운 것이 유일한 원인”이라고 단정하지 않는다.

근거: `RESULTS.json:cpu_signal`, `query_wrong_candidate_training_type`.

## 4. 정규화 분포 이탈은 실제다. 그러나 전체 실패의 원인은 아니다

고정 scaler를 TRAIN 입력으로 독립 재계산해 **완전히 동일함**을 확인했다.
정규화 산술 오류는 발견하지 못했다. metric/trace의 최대 절대 표준화 값은 다음과 같다.

| 순환 | TRAIN | validation | query |
|---|---:|---:|---:|
| 0 | 37.20 | 293,954.51 | 60,933.04 |
| 1 | 36.29 | 12,520.26 | 61,632.60 |
| 2 | 33.76 | 59,612.08 | 15,416.27 |

세 seed는 같은 순환의 같은 scaler를 쓰므로 위 표는 순환별 한 번만 센다.
CPU의 정답 서비스 입력은 **107/107창에서 자신의 TRAIN 채널별 최솟값–최댓값을 벗어났다**.
TRAIN에서 그 서비스의 CPU 장애를 보지 않은 분할 조건과 큰 입력 분포 이탈이 함께 관측된다.
다만 CPU 정답 순위는 여전히 보존되므로 큰 값과 오답의 동반만으로
“clipping하면 해결된다”고 말할 수 없다.

**반례:** 지연 장애 중 정답 서비스의 metric/trace가 모두 자신의 TRAIN 범위 안인
81개 고유 창도 세 seed의 243회 예측 중 **234회 오답(96.30%)**이었다.
전체 query에서 창 손실이 가장 큰 사례도 범위 내 지연 장애였다:

- 사건: `SN.2022-04-17T183729D2022-04-17T190100:fault01`
- 순환 1, seed 11, original index 158
- 정답 `post-storage-service` → 예측 `home-timeline-service`
- root NLL **9.6889**
- 정답 서비스 최대 |z| **1.0062**, 전체 후보 metric/trace 최대 |z| **1.6903**

따라서 정규화 극단값은 CPU 실패의 기여 후보이지만, 지연을 포함한 전체 실패를
설명하는 필요조건은 아니다. 범위 검사는 metric/trace에 한정되며 logs나
시계열의 결합 분포까지 동일하다는 뜻은 아니다.

근거: `RESULTS.json:normalization_ranges`, `root_range_groups`,
`largest_query_window_loss`.

## 5. 단순한 학습 횟수 부족으로도 설명하기 어렵다

9개 실행 모두 실제 200 epoch를 완료했다. 선택 epoch는 2–70이다.
9/9실행에서 선택 시점보다 마지막 epoch의 TRAIN online joint loss는 낮아졌지만,
validation 사건 NLL은 높아졌다.

예를 들어 순환 0, seed 11:

- 선택 epoch 8 → 최종 epoch 200
- TRAIN online joint: **0.93849 → 0.000317**
- validation 사건 NLL: **2.41802 → 4.59143**

이미 더 학습한 기록에서 학습 목적함수는 개선되지만 validation 손실은 악화됐다.
따라서 단순히 “학습이 실행되지 않았다”거나 “epoch를 늘리기만 하면 해결된다”는
설명은 이 로그로 뒷받침되지 않는다. 이는 최적화 완료의 증명은 아니며,
최종 query 성능이나 저장되지 않은 최종 TRAIN 정확도를 추정하지 않는다.

근거: `RESULTS.json:learning`; 실제 `history_200.json`과 `epochs_200.jsonl`
1,800행의 일치, 최소 validation 사건 NLL 선택 규칙을 재검사했다.

## 6. 결론: 확인한 실패와 미확인 원인

**확인:** SN 전체가 본질적으로 어렵다는 주장이 아니라, 이 사건 분리 조건에서
CPU·지연 장애의 서비스 진단이 실패한다. 특히 CPU는 명확한 서비스별 단서가
입력과 정규화 결과에 모두 남아 있는데도, 학습하지 않은 서비스·고장 조합에
정답을 연결하지 못한다. TRAIN 고장 경험이 있는 다른 서비스로 향하는 오답,
큰 입력 분포 이탈, 후반 학습·검증 손실의 분리가 수치로 확인됐다.

**미확인:** 분할의 각 효과, 정규화의 인과적 기여, modality encoder와 후단
분류기 중 어느 단계가 결정적인 원인인지, 어떤 변경으로 개선되는지는 분리되지 않았다.
저장 결과만으로 이를 특정 모듈의 결함이나 개선 효과로 승격하지 않는다.
새 모델·scaler·학습 실험은 실행하지 않았다.

## 7. 실행 및 검증 영수증

새로 만든 파일은 이 디렉터리의 진단 코드·결과·보고서뿐이다.
기존 source/input/result는 변경하지 않았고, 보호 시험 자료·기존 checkpoint는 열지 않았다.
86개 사용 파일의 SHA-256을 기록하고 분석 전후 일치를 확인했다.

- 394개 허용 입력(325장애+69정상), 36사건.
- DiagMLP 9개 실행, 27개 TRAIN/validation/query 예측, 1,800 epoch 로그.
- 사건 확률 집계 독립 재계산 최대 차이 `1.7763568394002505e-15`, Top-1/3 정확 일치.
- scaler 독립 재계산 정확 일치; 선택 epoch·run config·예측 hash·인덱스 대응 확인.
- 동률 credit, 극단 logits, 다중 창 확률 집계 self-check 통과.
- `diagnose.py` LSP diagnostics: **No diagnostics found**.
- 독립 CLI: **exit 0**, `DIAGMLP_FAILURE_CHECK_PASS`.
- monitor `mon_H36SFCGBWM557TS7`, session `bash_1`.

재현 명령(파일 쓰기 없음, 기존 `RESULTS.json`과 재계산 결과 대조):

```sh
cd /home/gnho1236/r2
PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  .venv-mlp/bin/python -B research/diagmlp_failure_check_20261017/diagnose.py
```

로컬 복원본·해당 개발 자료에 한정한 사후 진단이다. 새 사건이나 원 논문 저자
실행본의 성능 검증, 인과 개입 실험, 보호 최종시험은 수행하지 않았다.
