# SN50→SN200 저장 예측 대응 분석

2026-10-18. **DiagMLP 주분석, Eadro 별도 보조분석. 새 학습·추론 없음.**

## 단위와 판정

- 각 모델·seed의 validation은 실제로 78창이며, 그중 **65장애창·28개 고유 사건**이다.
  seed는 11/23/37이다. 같은 65창·28사건을 세 seed로 반복 평가했으므로
  모델당 195 seed-window, 84 seed-event **기록**이지 195/84개의 독립 표본이 아니다.
  모델을 합쳐도 고유 사건은 28개다.
- 창은 `(model, seed, original index)`로 join한다. 양쪽 index 순서·집합과
  label, config/metadata의 12개 후보 서비스 순서, 전체 event_id 및 정답
  root service·fault type을 모두 확인했다. `fault04`만으로 합치지 않는다.
- 원래 native 창 지표는 장애창의 conditional root Top1이다. 탐지 gated
  지표가 아니다. 사건 대표값은 **같은 사건의 저장 validation 장애창별
  candidate softmax 확률을 평균한 뒤 한 번 순위를 매긴 것**이다.
  평균 logits·다수결이 아니며 창별 정오의 혼합도 별도 보존한다.
- 사건 대표값은 이번의 **새 기술적 오류 요약**이지 기존 native 지표나
  checkpoint 선택 규칙을 대체하지 않는다. 저장된 최소 validation joint
  loss 선택 결과를 그대로 사용했다.
- 정확히 같은 최댓값은 top 후보 전부를 남기며 정답이 포함되면
  `1 / 동률 후보 수`의 credit을 준다. 어느 쪽이든 top 동률이면
  `unresolved_tie`로 남긴다. 임의 argmax가 없다. 실제 자료에서는
  두 모델 모두 창·사건 대표의 top 동률이 0이었다.

기호: **C**=`both_correct`(지속 정답), **+**=`new_correct`(새 정답),
**−**=`new_wrong`(새 오답), **W**=`both_wrong`(지속 오답),
**T**=`unresolved_tie`. 모든 전이는 50→200이다.

## 1. DiagMLP — 주분석

### 창 단위와 사건 대표 단위

|seed|창 C|창 +|창 −|창 W|창 T|합계|
|---|---:|---:|---:|---:|---:|---:|
|11|54|6|1|4|0|65|
|23|62|2|0|1|0|65|
|37|58|4|0|3|0|65|
|반복 평가 기록 합계|174|12|1|8|0|195|

기존 `native_learning_diagnosis_20261018/RESULTS.json`의 195행을
`(seed,index)`별 전체 사건 ID·root·예측·범주와 대조해 일치했다.
관련 파일 37개의 기존 SHA256도 일치했다. 기존 `analyze.py`는 실행하지 않았다.
재사용 범위는 정수 전이·정답/예측·사건 식별자이며, 기존 RESULTS의 확률 필드에
환경 간 마지막 비트 일치를 요구하지 않았다.

|창 범주|seed-window 기록|고유 창|해당 고유 사건|
|---|---:|---:|---:|
|C|174|65|28|
|+|12|10|8|
|−|1|1|1|
|W|8|7|6|
|T|0|0|0|

고유 창·사건의 범주별 집합은 서로 겹친다. 위 열을 합산하지 않는다.
새 정답 창 12개 기록을 12개 새 정답 사건으로 해석할 수 없다.

|seed|사건 C|사건 +|사건 −|사건 W|사건 T|합계|혼합 창 결과 사건|
|---|---:|---:|---:|---:|---:|---:|---:|
|11|25|2|0|1|0|28|7|
|23|28|0|0|0|0|28|3|
|37|26|1|0|1|0|28|4|
|반복 평가 기록 합계|79|3|0|2|0|84|14|

창 정답 credit 합은 seed11 55→60/65, seed23 62→64/65,
seed37 58→62/65다. 사건 대표 정답 credit 합은 각각 25→27/28,
28→28/28, 26→27/28이다. 분모가 다르므로 지표를 서로 대체하지 않는다.

예를 들어 seed11의
`SN.2022-04-17T181245D2022-04-17T183616:fault07`
(media-service, network_delay)는 index 112/115/120에서 C/−/W가 하나씩
있지만 사건 대표는 C다. 이 중 index115가 유일한 신규 오답 창이다.
같은 사건은 seed37에서 C 1창·+ 2창이고 사건 대표는 +다.
따라서 해당 사건을 창 결과 하나로 덮거나 seed를 합쳐 단일 전이로 만들지 않는다.

### 동일 seed 내 새 정답·새 오답·지속 오답 사건

|seed|범주|전체 event_id|root service|fault type|
|---|---|---|---|---|
|11|+|SN.2022-04-17T183729D2022-04-17T190100:fault01|post-storage-service|network_delay|
|11|+|SN.2022-04-17T192658D2022-04-17T195031:fault07|user-mention-service|network_delay|
|11|W|SN.2022-04-17T183729D2022-04-17T190100:fault07|url-shorten-service|network_delay|
|37|+|SN.2022-04-17T181245D2022-04-17T183616:fault07|media-service|network_delay|
|37|W|SN.2022-04-17T183729D2022-04-17T190100:fault01|post-storage-service|network_delay|

seed11/23/37의 사건 대표 신규 오답은 모두 0이다.
seed23의 새 정답·지속 오답도 모두 0이다.

### 전체 28사건의 seed 상태 벡터

벡터 순서는 **[11,23,37]**이다. 모든 ID는 전체 run_id를 포함한다.
root 숫자·서비스는 `PAIRED.json`·CSV에, 전체 후보 순서는 JSON의
`alignment`에 저장되어 있다.

|전체 event_id|root service|fault type|[11,23,37]|
|---|---|---|---|
|SN.2022-04-17T181245D2022-04-17T183616:fault04|home-timeline-service|network_delay|C,C,C|
|SN.2022-04-17T181245D2022-04-17T183616:fault06|media-service|cpu_load|C,C,C|
|SN.2022-04-17T181245D2022-04-17T183616:fault07|media-service|network_delay|C,C,+|
|SN.2022-04-17T181245D2022-04-17T183616:fault08|media-service|network_loss|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault00|post-storage-service|cpu_load|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault01|post-storage-service|network_delay|+,C,W|
|SN.2022-04-17T183729D2022-04-17T190100:fault02|post-storage-service|network_loss|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault03|social-graph-service|cpu_load|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault05|social-graph-service|network_loss|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault06|url-shorten-service|cpu_load|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault07|url-shorten-service|network_delay|W,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault00|nginx-web-server|cpu_load|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault01|nginx-web-server|network_delay|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault02|nginx-web-server|network_loss|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault03|unique-id-service|cpu_load|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault04|unique-id-service|network_delay|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault05|unique-id-service|network_loss|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault06|user-service|cpu_load|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault07|user-service|network_delay|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault08|user-service|network_loss|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault00|compose-post-service|cpu_load|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault01|compose-post-service|network_delay|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault02|compose-post-service|network_loss|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault04|user-timeline-service|network_delay|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault05|user-timeline-service|network_loss|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault06|user-mention-service|cpu_load|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault07|user-mention-service|network_delay|+,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault08|user-mention-service|network_loss|C,C,C|

|사건 대표 범주|seed 간 union 사건 수|세 seed intersection 사건 수|
|---|---:|---:|
|C|28|24|
|+|3|0|
|−|0|0|
|W|2|0|
|T|0|0|

범주 union은 **겹친다**. C∩+=3, C∩W=2, +∩W=1이며 그 외 쌍은 0이다.
특히 `SN.2022-04-17T183729D2022-04-17T190100:fault01`은 +/C/W를
모두 갖는다. 3+2를 독립된 개선/실패 사건 수처럼 합산하면 안 된다.
각 union/intersection의 전체 ID 목록은 JSON의
`models.diagmlp.cross_seed.category_sets`에 있다.

## 2. Eadro — 별도 보조표

동일 코호트의 별도 모델 결과이며 모델 차이를 우리 변경 효과라고 주장하지 않는다.

|seed|창 C|창 +|창 −|창 W|창 T|합계|
|---|---:|---:|---:|---:|---:|---:|
|11|26|0|0|39|0|65|
|23|22|18|1|24|0|65|
|37|36|15|5|9|0|65|
|반복 평가 기록 합계|84|33|6|72|0|195|

|seed|사건 C|사건 +|사건 −|사건 W|사건 T|합계|혼합 창 결과 사건|
|---|---:|---:|---:|---:|---:|---:|---:|
|11|11|0|0|17|0|28|6|
|23|11|8|0|9|0|28|9|
|37|17|7|2|2|0|28|11|
|반복 평가 기록 합계|39|15|2|28|0|84|26|

창 정답 credit 합: seed11 26→26/65, seed23 23→40/65, seed37 41→51/65.
사건 대표 credit 합: 각각 11→11/28, 11→19/28, 19→24/28.
아래 전체 벡터가 각 seed의 새 정답·새 오답·지속 오답 ID와 root/type도
빠짐없이 표시한다. JSON `per_seed.*.same_seed_event_ids`에는 범주별로 분리해 저장했다.

|전체 event_id|root service|fault type|[11,23,37]|
|---|---|---|---|
|SN.2022-04-17T181245D2022-04-17T183616:fault04|home-timeline-service|network_delay|W,W,+|
|SN.2022-04-17T181245D2022-04-17T183616:fault06|media-service|cpu_load|W,W,+|
|SN.2022-04-17T181245D2022-04-17T183616:fault07|media-service|network_delay|W,+,W|
|SN.2022-04-17T181245D2022-04-17T183616:fault08|media-service|network_loss|W,W,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault00|post-storage-service|cpu_load|C,C,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault01|post-storage-service|network_delay|W,W,+|
|SN.2022-04-17T183729D2022-04-17T190100:fault02|post-storage-service|network_loss|W,+,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault03|social-graph-service|cpu_load|W,W,C|
|SN.2022-04-17T183729D2022-04-17T190100:fault05|social-graph-service|network_loss|C,C,+|
|SN.2022-04-17T183729D2022-04-17T190100:fault06|url-shorten-service|cpu_load|W,W,+|
|SN.2022-04-17T183729D2022-04-17T190100:fault07|url-shorten-service|network_delay|W,W,+|
|SN.2022-04-17T190213D2022-04-17T192544:fault00|nginx-web-server|cpu_load|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault01|nginx-web-server|network_delay|W,C,−|
|SN.2022-04-17T190213D2022-04-17T192544:fault02|nginx-web-server|network_loss|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault03|unique-id-service|cpu_load|W,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault04|unique-id-service|network_delay|W,W,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault05|unique-id-service|network_loss|W,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault06|user-service|cpu_load|W,W,W|
|SN.2022-04-17T190213D2022-04-17T192544:fault07|user-service|network_delay|C,C,C|
|SN.2022-04-17T190213D2022-04-17T192544:fault08|user-service|network_loss|W,+,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault00|compose-post-service|cpu_load|C,C,+|
|SN.2022-04-17T192658D2022-04-17T195031:fault01|compose-post-service|network_delay|W,+,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault02|compose-post-service|network_loss|W,+,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault04|user-timeline-service|network_delay|C,C,−|
|SN.2022-04-17T192658D2022-04-17T195031:fault05|user-timeline-service|network_loss|C,+,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault06|user-mention-service|cpu_load|C,+,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault07|user-mention-service|network_delay|C,C,C|
|SN.2022-04-17T192658D2022-04-17T195031:fault08|user-mention-service|network_loss|C,+,C|

|사건 대표 범주|seed 간 union 사건 수|세 seed intersection 사건 수|
|---|---:|---:|
|C|21|5|
|+|15|0|
|−|2|0|
|W|17|1|
|T|0|0|

union의 겹침은 C∩+=9, C∩−=2, C∩W=10, +∩W=10, −∩W=1이고
그 외 쌍은 0이다. W intersection의 유일한 사건은
`SN.2022-04-17T190213D2022-04-17T192544:fault06`
(user-service, cpu_load)다. 집합의 전체 ID 목록은
`models.eadro.cross_seed.category_sets`에 있다.

## 3. 정렬·해시·검사 근거

각 쌍에서 입력 manifest·split/scaler 해시, 후보 순서, split 전체 및
첫50epoch의 epoch/update/train loss/validation loss/validation scores를
정확히 대조했다. 시간(seconds)은 동일성 주장에 포함하지 않았다.
SN50·SN200은 별도 seeded 실행이며 optimizer 상태 이어달리기가 아니다.

|모델|seed|SN50 선택 epoch|SN200 선택 epoch|
|---|---:|---:|---:|
|DiagMLP|11|49|192|
|DiagMLP|23|48|78|
|DiagMLP|37|50|200|
|Eadro|11|31|31|
|Eadro|23|33|90|
|Eadro|37|40|200|

공통 입력 manifest:

- raw.npz의 **기록된** SHA256:
  `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8`
- metadata.json 실제 SHA256:
  `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4`
- split.json 실제 SHA256:
  `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d`
- scaler.npz 실제 SHA256:
  `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1`

raw.npz는 열거나 다시 hash하지 않았다. 위 raw 값은 config 양쪽과 metadata의
기존 기록이 일치한다는 뜻이다. scaler는 hash만 읽고 배열을 역직렬화하지 않았다.
각 실행의 config/split/history/scaler/저장 validation NPZ hash가 summary와
일치했다. config의 원형 trainer/model 코드 hash도 현재 파일과 일치했다.
원형 코드, 기존 RESULTS/analyze 및 수치 입력 **78개 파일의 실행 전후 SHA256
일치**를 `evidence_paired.json`에 남겼다. 문서의 정상적인 문구 보완은
수치 입력 변경으로 취급하지 않는다.

검사 결과:

- 합성 **11/11 통과**: 다중창 혼합, 전체 사건키 충돌 방지, seed 중복 방지,
  저장 순서 permutation join, index/label 불일치 거부, 후보/정답 일치,
  창/평균확률 동률 및 fractional credit, 안정 softmax, 확률 평균과
  logits 평균/다수결의 차이, 네 고유-top 전이.
- 실제 12개 저장 NPZ에서 `indices`, `labels`, `root_logits`만 역직렬화했다.
  저장 점수와 선택 history conditional Top1을 정확히 대조했다.
- 168 seed-event 기록의 각 arm 평균확률을 별도 열 합산으로 재계산해 대조했다.
  CSV와 JSON에는 원래 창 index 목록, 창별/사건별 전이, 정답 credit,
  top 후보 전체, 사건 후보 평균확률이 남아 있다.
- 두 Python 파일의 LSP diagnostics 없음. 실행은 resident **Python 3.10.12 /
  NumPy 2.2.6**이며,
  pandas·설치·다운로드·기존 분석 스크립트 실행 없이 완료했다.

산출물:

|파일|내용|
|---|---|
|PAIRED.md|이 보고서|
|PAIRED.json|주/보조 요약, 정렬 증거, 전체 창·사건 및 집합/벡터|
|paired_windows.csv|390행: 모델별 195 seed-window 기록|
|paired_events.csv|168행: 모델별 84 seed-event 기록, 혼합 창 범주별 수 포함|
|paired.py|고정 허용 경로의 읽기 전용 분석 및 JSON/CSV 출력|
|test_paired.py|11개 합성 검사|
|evidence_paired.json|전후 해시, 기존 증거 재사용, 검사 결과 및 수치 receipt|

재실행은 NumPy가 있는 허용 환경에서 `python -B paired.py`로 한다.
이는 합성 검사와 저장 예측 집계만 실행하며 네 JSON/CSV를 다시 쓴다.
보고서는 수치 결과에 맞춰 별도로 작성되며 원형 학습 코드를 실행하지 않는다.

## 해석 한계

28개 validation 사건 전부에 TRAIN 창도 있다(각 실행 TRAIN 36사건,
TRAIN∩validation 28사건). **미학습 사건 일반화가 아니다.** 사건의 물리적
독립성도 입증되지 않았으므로 독립 표본 기반 신뢰구간·유의성 검정은 하지 않았다.
새 학습, checkpoint 추론/역직렬화, Hawkesfit, 특징·raw 배열, 보호 관측·예측,
TT200, corrected rotation, RE2는 접근·실행하지 않았다. RE2 보류는 유지된다.
