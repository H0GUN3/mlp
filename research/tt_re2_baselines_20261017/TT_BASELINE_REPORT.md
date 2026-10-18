# TT 기준선 결과 — 검증 자료, 최종시험 아님

## 목적과 조건

같은 TT 시스템의 장애 특성을 학습하고 학습에 넣지 않은 관측 창에서
원인 서비스를 찾는 비교다. 기존 학습3256/검증813창을 유지했다.
양쪽에81개 장애 사건의 서로 다른 창이 있으므로 새 사건 일반화 실험이 아니다.
검증 장애686창이 원인 점수의 분모이며 정상127창은 제외한다.

27개 후보, 원형 지표·트레이스 시계열과Hawkes로그, 두복원본,
Adam0.001/batch256/50epoch/seed11·23·37를공통적용했다.
선택은validation joint loss 최소이며선택자료의점수이지독립최종시험결과가아니다.
논문과비슷한공개설정을참고했지만정확한저자실행본/분할identity재현은아니다.

## 수치

모두세seed평균이며선택checkpoint의창단위조건부진단이다.

| 방법 | TRAIN Top1 | validation Top1 | validation Top3 | 선택epoch(11/23/37) |
|---|---:|---:|---:|---|
| Eadro 복원본 | 83.91% | 79.64% | 98.98% | 48 / 50 / 46 |
| DiagMLP 수식 복원본 | 99.64% | 98.64% | 100.00% | 27 / 23 / 24 |

validation Top1의seed별값은Eadro81.05/78.43/79.45%,
DiagMLP98.83/98.69/98.40%다.
TT_RESULTS.json에정확한값,선택/마지막checkpoint의TRAIN/validation,
conditional/gated Top1/3/5및탐지P/R/F1이있다.

## 확인된 실패와 아직 말할 수 없는 것

- Eadro는TRAIN Top1부터83.91%이며선택epoch가50epoch예산끝에가깝다.
  현재예산에서의차이는확인됐지만충분히최적화된최고성능간차이나
  GNN의순수인과효과라고해석할수없다.
- DiagMLP는선택validation에서seed별8/9/11개창만틀렸다.
  주된반복혼동은ts-travel-service와ts-food-service다.
- Eadro가틀리고DiagMLP가맞힌창은seed별127/148/136개다.
  반대방향은5/9/6개다. 같은검증창의반복예측이며독립표본합산은하지않는다.
- root trace관측이없는validation장애창은634/686개다.
  DiagMLP는그집합에서도높은적중률을보여단순한누락만으로실패를설명할수없다.
- DiagMLP오답의metric/trace는모두각TRAIN채널범위안에있었다.
  따라서TT오답을전반적으로정규화극단값때문이라고보는근거는없다.
  이것은SN에서제안했던가설을SN자료로검사했다는뜻은아니다.
- Eadro선택모델은세seed모두validation정상127창을장애로판정했다.
  탐지F1만높다고정상탐지가잘된것은아니다. 다만주연구는조건부원인진단이며,
  이결과를이유로탐지개선과제로범위를바꾸지않는다.

## 검증과 실행 이력

모든완료모델50epoch/650update. 원래Eadro11/23의시간초과부분실행은
보존후동일seed로재시도했다. Eadro37은완료된가중치를유지하고후처리만복구했다.
원래중단구간의config/epoch수치가재시도에서정확히같음을독립검사했다.
총완료6fits와중단2attempts를구분하며실패를성공으로바꾸어기록하지않는다.

- 실행전6focusedtests/CLI진단/입력검사:exit0.
- 복구된3학습프로세스:실제exit0,각TT_FIT_PASS또는후처리복구sentinel확인.
- mon_N8PEW5NE245R0K5M:CLI진단0,TT_VERIFIED6 24,실제exit0.
  24예측의독립NumPy채점/해시/모델선택/공통초기화/중단prefix대조PASS.
- mon_NV9WA6KWKF1DA913:CLI진단0,TT_DIAGNOSIS_PASS6 686,실제exit0.
  기존예측과허용입력만읽은오답·관측진단이다.

## 남은 작업

반복되는travel/food혼동24개seed-창예측(고유15창)을읽기전용으로검사했다.
15창중13창에서두후보의호출수가모두0이고,차이가있는창은2개뿐이었다.
따라서“후보별호출수차이추가로이혼동을해소한다”는구체적가설은지지부족이다.
호출수의모든가능한활용이무효라는주장이나원인식별불가능성증명은아니다.
mon_32DG6085YKF4PRHX의CLI진단0/TT_CONFUSION_PROBE_PASS/실제exit0을확인했다.
TT_CONFUSION_PROBE.json에모든사례와원본index를보존했다.
근거없이count채널·새모듈을추가하거나개선성능을발명하지않았다.
RE2-OB의반복별새분할은사용자승인대기다.
TT보호시험1744행과미배정1행,RE2보호시험관측은열지않았다.

근거: TT_PROTOCOL.md,TT_INPUT_CHECK.json,TT_EXECUTION.md,
TT_RESULTS.json,TT_DIAGNOSIS.json,각run의config/history/checkpoint/summary.
