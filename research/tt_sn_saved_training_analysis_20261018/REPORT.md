# TT·SN 저장 학습 분석 — 독립 확인 결과

**2026-10-18 기준.** 기존 학습 기록과 저장 validation 예측만 재집계했다.
주 분석은 DiagMLP이며 Eadro는 별도 보조 결과다. 검증은 실험의 인과효과나
새로운 일반화 성능을 입증하는 시험이 아니라, 저장 기록의 산술과 기존 분석을
확인하는 작업이다.

## 1. 실행량: 설정값과 기록값

표의 `계획 batch`는 split 표본 수와 config의 batch size로 계산했다. `기록
update`는 history의 epoch별 optimizer update를 합한 값이며, trainer의
1 update/학습 batch 규칙에서 batch 횟수를 파생한다. 실제 batch ID나 실제
minibatch 크기 순서는 저장되어 있지 않다.

### DiagMLP — 주 분석

|코호트|seed|TRAIN / validation 창|계획 batch/epoch|계획 update|기록 update 합|최소 validation loss 선택 epoch|
|---|---:|---:|---:|---:|---:|---:|
|TT50|11|3256 / 813|13 (256×12, 184×1)|650|650|27|
|TT50|23|3256 / 813|13 (256×12, 184×1)|650|650|23|
|TT50|37|3256 / 813|13 (256×12, 184×1)|650|650|24|
|SN50|11|316 / 78|2 (256, 60)|100|100|49|
|SN50|23|316 / 78|2 (256, 60)|100|100|48|
|SN50|37|316 / 78|2 (256, 60)|100|100|50|
|SN200|11|316 / 78|2 (256, 60)|400|400|192|
|SN200|23|316 / 78|2 (256, 60)|400|400|78|
|SN200|37|316 / 78|2 (256, 60)|400|400|200|

### Eadro — 별도 보조 표

각 seed의 표본·batch·update 수는 같은 코호트 DiagMLP 행과 같다. 선택은 같은
earliest-minimum validation joint loss 규칙을 따른다.

|코호트|seed 11 선택 epoch (loss)|seed 23 선택 epoch (loss)|seed 37 선택 epoch (loss)|
|---|---:|---:|---:|
|TT50|48 (0.4639)|50 (0.5092)|46 (0.4504)|
|SN50|31 (1.0716)|33 (0.9619)|40 (0.9346)|
|SN200|31 (1.0716)|90 (0.7642)|200 (0.6838)|

18개 실행 모두 설정된 epoch 수와 history 행 수가 맞고, 계획 update·history
update·summary update 합계는 각각 **6,900**이다. 표본은 TT 3256/813,
SN 316/78이다. TT는 epoch당 13회, SN은 2회 update이므로 같은 epoch 수가
같은 최적화 기회를 뜻하지 않는다.

## 2. 손실·정확도 경로와 checkpoint 선택

TRAIN 손실은 epoch 동안 minibatch별 가중 joint loss이고, validation 손실은
각 epoch 종료 모델의 전체 validation joint loss다. 둘은 같은 상태에서 측정한
동일 지표가 아니다. conditional Top1은 fault 창의 후보 root 순위 정확도이며,
gated Top1은 fault 탐지까지 요구하는 값이다. TRAIN 정확도는 기록되지 않았다.

### DiagMLP

|코호트|기록된 구간 변화|선택 epoch / validation loss / conditional Top1|
|---|---|---|
|TT50|validation loss는 epoch 1의 1.8088–1.8385에서 epoch 25의 0.2015–0.2272로 하락한 뒤 epoch 50에는 0.2984–0.3562로 상승. epoch 25 conditional Top1은 98.1–98.5%.|seed 11/23/37: 27/23/24; loss 0.2090/0.1979/0.2001; Top1 98.8/98.7/98.4%.|
|SN50|epoch 1 Top1은 0.0–9.2%, epoch 50은 81.5–96.9%. epoch 50 TRAIN loss는 0.0615–0.0706, validation loss는 0.2041–0.3518.|seed 11/23/37: 49/48/50; loss 0.3154/0.2013/0.2231; Top1 84.6/95.4/89.2%.|
|SN200|seed별 첫 50행은 SN50와 seconds 외 수치가 같음. epoch 200 TRAIN loss는 0.0016–0.0041, validation loss는 0.0796–0.2612, Top1은 92.3–98.5%.|seed 11/23/37: 192/78/200; loss 0.2565/0.1242/0.0796; Top1 92.3/98.5/95.4%.|

손실·정확도 경로의 추가 고정점(범위는 세 seed의 최소–최대):

|코호트 / epoch|TRAIN joint loss|validation joint loss|conditional Top1|
|---|---:|---:|---:|
|TT50 / 1|1.8492–1.8662|1.8088–1.8385|10.2–16.0%|
|TT50 / 25|0.1468–0.1684|0.2015–0.2272|98.1–98.5%|
|TT50 / 50|0.0511–0.0766|0.2984–0.3562|97.5–97.7%|
|SN50·SN200 / 1|1.5917–1.6230|1.4942–1.5294|0.0–9.2%|
|SN50·SN200 / 10|1.2921–1.3486|1.3660–1.3869|13.8–20.0%|
|SN50·SN200 / 25|0.6449–0.6965|0.7742–0.8389|64.6–67.7%|
|SN50·SN200 / 50|0.0615–0.0706|0.2041–0.3518|81.5–96.9%|
|SN200 / 75|0.0107–0.0189|0.1217–0.2791|87.7–98.5%|
|SN200 / 100|0.0062–0.0077|0.1042–0.3249|87.7–96.9%|
|SN200 / 150|0.0020–0.0030|0.1001–0.2842|89.2–96.9%|
|SN200 / 200|0.0016–0.0041|0.0796–0.2612|92.3–98.5%|

SN에서 진단 Top1의 큰 상승은 초기 50 epoch에서 확인된다. 이후의 변화는 seed별로
완만하거나 비단조다. SN200의 conditional Top1 최대 epoch는 167/51/129로,
validation loss 선택 epoch 192/78/200과 다르다. TT50도 Top1 최대점과 선택점이
일치하지 않는다. 선택은 정확도 최대화가 아니라 저장된 최소 full-validation
joint loss를 따랐다. 최대 정확도 checkpoint로 다시 선택하지 않았다.

선택 checkpoint의 세 seed 평균 창 Top1은 **SN50 89.74%→SN200 95.38%**다.
SN50에서 seed별 최고 Top1 epoch를 사후에 고르더라도 평균90.26%로,
실제 선택보다0.51%p 높을 뿐이다. 따라서5.64%p의 전체 증가를
선택 규칙 차이만으로 설명할 수 없다. 이는 저장 이력의 사후 상한 비교이며
새로운 선택법의 검증 성능이 아니다.

갱신 수 차이만으로도 TT–SN 격차가 설명되지는 않는다. 기존 검증된 이력에서
TT epoch7/8은91/104 update에 평균94.70%/96.36%이고,
SN epoch50은100 update에89.23%다. 이는 근접한 갱신 수의 기술적 대조일 뿐,
서로 다른 시스템의 분포·표본·후보 수를 통제한 실험은 아니다.
위 평균과 선택 상한은 동일 history hash가 검증된
`native_learning_diagnosis_20261018/RESULTS.json`의 runs/trajectories와 대조했다.

### Eadro 보조 해석

Eadro에서도 TRAIN 손실이 줄어드는 동안 validation loss가 악화되거나 Top1과
다른 방향으로 움직이는 seed가 있다. SN200 seed 11은 선택 loss 1.0716(epoch 31)
에서 마지막 2.4137(epoch 200)까지 validation loss가 상승했다. seed 37은
epoch 200의 최저 loss 0.6838을 선택하지만 conditional Top1 최대는 epoch 86의
83.1%이며 선택점은 78.5%다. 이는 두 선택 기준이 다름을 보여줄 뿐, 어느 기준이
항상 우월하다는 뜻은 아니다.

## 3. SN50→SN200 저장 예측의 새 정답·새 오답·지속 오답

창 점수는 기존 native fault-window conditional root Top1이다. 사건 대표 점수는
각 사건 validation fault 창의 저장 candidate softmax 확률을 평균해 순위를
정한 별도 기술 요약이다. 창 지표나 checkpoint 선택을 대체하지 않는다. 같은
event_id는 run_id를 포함한 전체 문자열로 대응했다. seed를 독립 사건으로
세지 않았고, exact tie는 임의로 풀지 않았다(관측된 창·사건 동률 0).

### DiagMLP: seed별 전이

|seed|창 지속정답 C|창 새정답 +|창 새오답 −|창 지속오답 W|사건 C|사건 +|사건 −|사건 W|
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|11|54|6|1|4|25|2|0|1|
|23|62|2|0|1|28|0|0|0|
|37|58|4|0|3|26|1|0|1|

세 seed 모두 지속정답(C/C/C)이었던 경우를 제외한 full event_id는 다음4개다.
이는 모두50→200 사이에 판정이 바뀐 사건이라는 뜻은 아니며 지속오답도 포함한다.
표시 순서는 seed11/23/37이고, 나머지24개 사건은 모두C/C/C다.

|full event_id|root / fault type|seed 11 / 23 / 37|
|---|---|---|
|`SN.2022-04-17T181245D2022-04-17T183616:fault07`|media-service / network_delay|C / C / +|
|`SN.2022-04-17T183729D2022-04-17T190100:fault01`|post-storage-service / network_delay|+ / C / W|
|`SN.2022-04-17T183729D2022-04-17T190100:fault07`|url-shorten-service / network_delay|W / C / C|
|`SN.2022-04-17T192658D2022-04-17T195031:fault07`|user-mention-service / network_delay|+ / C / C|

범주: C=지속정답, +=새정답, −=새오답, W=지속오답. 전체 28 event_id를 세 seed에
대해 확인했다. DiagMLP event union은 새정답 3건, 지속오답 2건, 새오답 0건이다.
범주 union은 seed 간 중첩되므로 서로 더해 독립 사건 수로 해석하면 안 된다.

원래 창 단위로는 새 정답12회 중 지연10회·손실2회, 새 오답1회는 지연이다.
CPU 정답 수는56/57로 같고, 지연은58/72→67/72,
손실은61/66→63/66으로 변했다. 이 분모는 창-seed 반복 기록이며
독립 사건 수가 아니다. 후반 선택 모델의 이득은 주로 지연 장애 구별에 있었다.

### Eadro: 별도 보조 집계

|seed|창 C / + / − / W|사건 C / + / − / W|
|---:|---:|---:|
|11|26 / 0 / 0 / 39|11 / 0 / 0 / 17|
|23|22 / 18 / 1 / 24|11 / 8 / 0 / 9|
|37|36 / 15 / 5 / 9|17 / 7 / 2 / 2|

각 seed에서 validation은 65개 fault 창, 28개 고유 사건이다. 세 seed를 합친
195개 창 기록과 84개 seed-event 기록은 반복 측정이며 독립 표본이 아니다.
SN의 validation 28 사건 모두 TRAIN에도 있다. TT의 validation 81 사건도 TRAIN에
포함된다. 그러므로 이 비교는 미학습 사건 일반화 성능이 아니다.

## 4. Hawkes absolute-before 대 relative-after 첫 50 epoch

absolute-before는 `end_times=window_start+10`, relative-after는 `end_times=10`이다.
각각 별도 저장 200-epoch history의 첫 50행만 사용했다. 두 arm은 같은 epoch에서도
손실과 일부 점수가 다르지만, 그 차이만으로 일관된 개선 또는 원인을 주장하지
않는다.

|seed|absolute 첫50 최소-loss epoch / Top1|relative 첫50 최소-loss epoch / Top1|Top1 차이 (상대−절대)|
|---:|---:|---:|---:|
|11|49 / 90.8% (59/65)|49 / 84.6% (55/65)|−6.15%p|
|23|50 / 93.8% (61/65)|48 / 95.4% (62/65)|+1.54%p|
|37|50 / 89.2% (58/65)|50 / 89.2% (58/65)|0.00%p|
|평균|91.28%|89.74%|−1.54%p|

두 arm 모두 seed별 첫 50 epoch에서 기록 update 합은 100이다. relative-after의
첫 50 numeric history는 해당 SN50 실행과 seconds를 제외하고 동일하다. 그러나
absolute arm의 first-50 최소-loss 선택점에 해당하는 저장 예측은 없다. 따라서
그 checkpoint별 새 정답·새 오답 사건 전이는 **미확인**이다. 최종 200-epoch 선택
예측을 first-50 결과인 것처럼 사용하지 않았다. TRAIN 정확도도 저장되지 않았다.

## 결론과 한계

기록상 계획·실제 로그 update, 최소 validation loss 선택, SN 대응 점수 및
Hawkes first-50 수치는 서로 맞는다. 이는 산출 기록의 일관성 확인이다.
TT와 SN은 cohort 크기와 입력 분포, epoch당 update 수가 다르므로 차이를
update 수의 인과 효과로 분리할 수 없다. 이 결과는 최종 held-out 사건 평가가
아니며, 새로운 학습·추론·Hawkes fitting·RE2 작업은 수행하지 않았다.
