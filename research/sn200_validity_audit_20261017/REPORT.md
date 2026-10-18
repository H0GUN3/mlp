# SN200 기준선 타당성 감사

## 질문과 상태

SN DiagMLP의 validation 점수 95.38%가 저장 산출물과 평가 절차로 뒷받침되는가? **검사한 범위에서는 점수·정답 대응·모델 선택 오류를 발견하지 못했고, 저장 예측의 독립 채점도 95.38%와 일치했다.** 독립 검증에서 확인된 감사 문서의 접근 표현 불일치는 부모가 정정했다. 최종 감사 coverage는 PASS지만, 원시 레코드 교차분할 중복·독립 사건 일반화·최종시험 성능까지 인증한 것은 아니다.

| 감사 축 | 확인된 결과 | 판정 |
|---|---|---|
| 분할 경계 | 564개 index가 중복 없이 train 316, validation 78, test 169, unassigned 1로 분할됨. 창 구간은 `a.start < b.start+10 and b.start < a.start+10`으로 비교했으며 train-validation 겹침은 0쌍. 창 identity 중복도 0. 두 분할은 28개 event와 4/4 recording을 공유한다. | 창 중복은 `notfoundwithinscope`. 사건 독립 평가 한계는 `limitedevaluation`. 원시 record identity 교차는 `unknown`. 근거: [BOUNDARY.md](./BOUNDARY.md), [VERIFY.md](./VERIFY.md), metadata `window_count`, `window_length`, `stride`. |
| 전처리·정보 흐름 | scaler는 train-only. Drain은 별도 정상 reference에서 학습. Hawkes는 각 창의 로그 관측으로 계산. 확인 범위에서 label에서 feature나 candidate 선택으로 가는 결함은 찾지 못함. 과거 loader가 split 전에 test 포함 전체 raw 배열을 메모리에 읽은 것은 확인됐으나, 그 자체로 test fit이나 평가를 뜻하지 않음. | 요청 범위 결함은 `notfoundwithinscope`; 창 로컬 held-out 관측 사용과 전체 선로딩은 해석 한계 `limitedevaluation`. 근거: [PREPROCESSING.md](./PREPROCESSING.md), `native_train.py:47–58,158–188,231–238`. |
| checkpoint 선택·평가 | 6개 실행의 history 최소 validation loss와 summary epoch/loss가 일치. strict `<` 비교라 동률이면 앞선 epoch 유지. test 평가 호출은 없고 기존 replay 결과만 재사용함. | 선택 경로 결함은 `notfoundwithinscope`; validation을 선택에 사용한 것은 `limitedevaluation`. 근거: [SELECTION.md](./SELECTION.md), [VERIFY.md](./VERIFY.md), `native_train.py:198–209,286–311`; verifier JSON `status=PASS`, `runs_checked=6`, `failures=[]`는 기존 검증 기록임. |
| 라벨·점수 | 세 허용 validation 산출물은 split index 순서와 일치하고 각각 78행, 65 fault와 13 normal. 서비스 열·라벨 대응 불일치 없음. seed별 독립 채점 결과는 아래와 같음. | 검증 산출물 내 결함은 `notfoundwithinscope`. 이는 validation 채점이지 test나 ensemble 결과가 아님. 근거: [SCORING.md](./SCORING.md), [VERIFY.md](./VERIFY.md), summary JSON `artifact_hashes.validation_predictions.npz`. |

## 95.38%의 의미

조건부 fault Top-1은 seed 11/23/37에서 각각 92.307692%, 98.461538%, 95.384615%다. 동등 가중 seed 평균은 `1 - (5+1+3)/(65×3) = 1 - 9/195 = 95.384615%`다. 오답 9건은 validation의 195개 fault 예측에 대한 합계이며, seed logits를 합친 ensemble 점수가 아니다. 따라서 이 수치는 저장된 validation prediction의 채점 결과를 지지하지만 전체 실험의 타당성, 독립 사건 일반화 또는 test 성능을 증명하지 않는다.

논문 기준 80.2%는 선택된 validation 점수 95.38%의 직접 비교군이 아니다. 23.59%와의 차이 원인도 이 감사로 확인되지 않았다. 점수만으로 누출을 추론하지 않는다.

## 남은 미확인과 필요한 조치

메타데이터만으로 raw metric/log/trace record identity의 train-validation 교차 중복, 원본 논문 split manifest와 재현 split의 정확한 대응, test 성능 및 신규 사건 일반화는 확인할 수 없다. 동일한 입력값만으로 record 누출을 판정하지 않았다. `raw.npz`는 해시 계산을 위해 **파일 바이트를 읽었으나 NPZ 배열을 decode하지 않았다**. `inputs.npz`와 보호 관측·예측은 열지 않았다.

**문서 정정 완료:** [BOUNDARY.md](./BOUNDARY.md)는 경계 계산의 metadata 접근과 전체 감사의 raw 바이트 해시 접근을 구분하도록 부모가 수정했다. PREPROCESSING과 VERIFY에도 같은 구분을 명시했다. 이는 기록 표현의 정정이며 실험 결과나 코드를 변경한 것이 아니다. 새 실험은 수행하지 않았고 자동 승인하지 않는다.

감사 문서의 `confirmeddefect`였던 SELECTION의 protocol hash 오기와 BatchNorm 설명, BOUNDARY의 구간·접근 표기는 정정됐다. 현재 source hash 불일치는 없다. 이 정정들은 파이프라인 결함 수정이 아니다.

감사에서 허용된 source·metadata·JSON을 대조했고, SCORING.md에 기록된 세 validation prediction NPZ의 `allow_pickle=False` 독립 채점을 근거로 재사용했다. 이 최종 보고 단계에서는 VERIFY와 감사 문서만 읽었다. 기존 verifier·학습 코드를 실행하거나 import하지 않았고, 재학습·재추론·새 분할은 없었다. 과거 verifier와 replay 기록은 기존 증거로만 인용했다.
