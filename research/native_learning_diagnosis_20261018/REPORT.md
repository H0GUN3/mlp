# TT50·SN50·SN200: 실제 학습 양상과 오답 변화

2026-10-18 · 기존 native DiagMLP 복원본의 기록 분석, 새 학습 없음

## 1. 질문과 결론

질문은 **“왜 SN은 TT보다 초기 진단 정확도가 낮았으며, SN50에서 SN200으로
늘리는 동안 무엇이 달라졌는가?”**이다. 별도 사건 분리 SN의 25% 결과로 이
질문을 대신하지 않는다. 아래 점수는 기존 창 분할의 validation 조건부 root
Top-1이며, 원논문 저자 실행본 재현이나 독립 최종시험 점수가 아니다.

확인한 것은 다음과 같다.

1. **실제 갱신 횟수가 달랐다.** TT50은 650회, SN50은 100회였다.
   그러나 비슷한 update 시점에도 TT의 점수가 더 높아 갱신 횟수만으로
   차이를 설명할 수 없다.
2. **SN의 후반 개선은 네트워크 장애에 집중됐다.** CPU 점수는 그대로였고,
   새 정답 12회 중 지연 10회·손실 2회였다. 새 오답도 1회 있었다.
3. **원시 media 지연 단서는 root 서버 내부가 아니라 호출자 span에 있었다.**
   `compose_media_client`의 약 6초 지연이 모델 입력에서는 호출자 서비스의
   평균 latency로 합쳐졌다. 호출 대상·operation별 구별은 그 trace 입력에
   보존되지 않는다. 이 표현상의 사실은 확인됐지만 학습 속도 차이의 단독
   원인이나 특정 개선안의 효과를 입증한 것은 아니다.
4. **공동 손실 선택과 정확도는 같은 지표가 아니며, Hawkes 교정도 초기
   학습을 일관되게 빠르게 하지는 않았다.**

따라서 “SN은 단순히 덜 학습해서 낮았고 원인 분석은 끝났다”는 결론은
지지되지 않는다. 반대로 이번 기록만으로 특정 모델 구조가 원인이라고
확정하는 것도 불가능하다.

## 2. 실제 학습량과 선택된 모델

`history.json[].optimizer_updates`를 직접 합산하고 trainer의 batch loop,
`summary.json.optimizer_updates`, 최소 validation joint-loss 선택과 대조했다.
마지막 작은 batch도 사용한다.

| 실행 | 학습 창 | epoch당 update | 전체 update | 선택 epoch: seed 11/23/37 | 선택까지 update |
|---|---:|---:|---:|---|---|
| TT50 | 3,256 | 13 | 650 | 27 / 23 / 24 | 351 / 299 / 312 |
| SN50 | 316 | 2 | 100 | 49 / 48 / 50 | 98 / 96 / 100 |
| SN200 | 316 | 2 | 400 | 192 / 78 / 200 | 384 / 156 / 400 |

SN50과 SN200은 입력·분할·scaler가 같고 첫 50epoch의 손실·정확도·update
이력이 세 seed 모두 정확히 같다. 실행시간 필드는 동일성 대상에서 제외했다.
SN50 선택점은 모두 예산 끝에 가까웠지만 이것만으로 학습 부족을 확정하지 않는다.

### 비슷한 update에서 비교해도 차이가 남는다

아래는 해당 epoch의 점수이지 각 예산에서 선택된 checkpoint 점수가 아니다.

| 이력 시점 | update | 평균 TRAIN online joint | 평균 validation joint | 평균 validation Top-1 |
|---|---:|---:|---:|---:|
| TT epoch 7 | 91 | 0.61985 | 0.52386 | 94.70% |
| SN epoch 50 | 100 | 0.06472 | 0.25965 | 89.23% |
| TT epoch 8 | 104 | 0.49131 | 0.41394 | 96.36% |
| SN epoch 100 | 200 | 0.00700 | 0.19962 | 92.82% |
| SN epoch 200 | 400 | 0.00246 | 0.16807 | 95.38% |

TT의 91/104 update와 SN의 100 update는 근접 시점 대조이지 정확한
step-matched 통제 실험이 아니다. 시스템·입력 분포·후보 수·모델 크기도 다르다.
TRAIN online joint는 학습 중 batch마다 가중치가 바뀌는 손실이므로 고정 모델의
정확도로 바꿔 읽지 않는다.

자료 차이도 실제 존재한다. TRAIN 장애 사건당 창 수의 중앙값은 SN **7개**
(4–10), TT **34개**(24–43)다. 같은 사건이 학습·검증에 걸치는 수는
SN 28개, TT 81개다. 이들은 사건 일반화 평가가 아니다.
SN/TT 모델 파라미터 수도 75,810 / 140,033으로 다르다.
따라서 갱신 수를 맞춘다고 모든 학습 조건이 같아지지 않는다.

근거: `RESULTS.json:runs`, `trajectories`, `dataset_support`,
`sn_prefix50_exact`; 원본 `native_reproduction_20261013/native_train.py`.

## 3. SN50→SN200: 무엇을 더 맞혔는가

선택 checkpoint의 동일 seed·동일 validation 창을 연결했다.
정상 13창은 root 점수에서 제외하고 장애 65창 × 3seed = 195회 예측을 집계했다.

| 변화 | 창-seed 예측 수 | 고유 창 | 고유 사건 |
|---|---:|---:|---:|
| 두 조건 모두 정답 | 174 | 65 | 28 |
| 새 정답 | **12** | **10** | **8** |
| 새 오답 | **1** | **1** | **1** |
| 두 조건 모두 오답 | 8 | 7 | 6 |

고유 창·사건은 seed가 다르면 여러 행에 겹칠 수 있어 열끼리 합산하지 않는다.
195회는 독립 사건 195개가 아니다. 순증은 11/195 = **5.64%p**이고
평균 Top-1은 **89.74% → 95.38%**다.

| 종류 | SN50 정답/예측 | SN200 정답/예측 | 정확도 변화 | TT50 참고 |
|---|---:|---:|---|---:|
| CPU | 56/57 | 56/57 | 98.25% → 98.25% | 100.00% |
| 지연 | 58/72 | 67/72 | **80.56% → 93.06%** | 99.23% |
| 손실 | 61/66 | 63/66 | 92.42% → 95.45% | 96.42% |

새 정답은 지연 10회(8창·6사건), 손실 2회(2창·2사건)였다.
새 오답 1회도 지연이다. “모든 장애를 고르게 늦게 배웠다”가 아니라,
**이 평가에서 후반 선택 모델의 이득은 주로 네트워크 지연 구별에 있었다**.
매 epoch의 사례별 logits는 저장돼 있지 않아서 각 사례를 처음 맞힌 epoch나
어느 입력 단서를 언제 배웠는지는 복구할 수 없다.

### 같은 입력에서도 seed별 방향이 달랐다

`media-service|network_delay`, original index 115:

| seed | SN50→SN200 | 정답 media 확률 |
|---|---|---|
| 37 | post-storage 오답 → media 정답 | 0.16386 → 0.68120 |
| 11 | media 정답 → post-storage 오답 | 0.49635 → 0.29392 |

입력은 그대로다. 학습 연장이 모든 사례·seed를 단조롭게 개선한다는
설명은 이 반례와 맞지 않는다.

근거: `RESULTS.json:transition_summary`, `transitions`, `type_scores`.
전체 195회 대응 기록을 보존했고, 유리한 사례만 남기지 않았다.

## 4. 원시 관측과 표현: media 사례 여섯 창

이전 질문에 나온 media→text 혼동과 같은 recording의 개선·악화 사례를 연결했다.
대상은 original index **112, 115, 120**(media 지연)와
**129, 133, 136**(media 손실)이다. 다른 변화 사례는 기존 입력까지 대조했고
원시 파일 재검사는 이 여섯 창으로 제한했다.

### 원시 지연이 root 입력에 그대로 붙어 있지는 않았다

| 창 | 원시 media 서버 span | 원시 compose의 media-client span | 전달된 trace 입력 |
|---|---|---|---|
| 112 | 2개 고유 ID, 각 12μs | 약 5.997초 평균 | compose 서비스의 해당 1초 bin 평균 약 2.400/2.405초 |
| 115 | 해당 시작시각 창에 없음 | 6.008163초 | compose 서비스 한 bin **2.4068048초**, media는 0-filled |
| 120 | 해당 시작시각 창에 없음 | 해당 시작시각 창에 없음 | media 0-filled; 다른 호출 관측은 존재 |
| 133 | 1개 고유 ID, 9μs | 0.413740초 | compose bin 평균 약 0.169539초 |
| 136 | 2개 고유 ID, 6/12μs | 평균 0.103140초 | compose bin 평균 약 0.056604/0.004642초 |

원본은 동일 span ID가 반복 등장한다. 예를 들어 창 115의 media-client 기록
12회는 12개 독립 요청이라는 뜻이 아니다. 기존 전처리와 동일하게 occurrence
가중을 유지해 latency 입력을 재현했다.

`native_data.py::trace_series`는 **span이 속한 서비스·시작시각·duration**으로
서비스별 1초 평균을 만든다. `operationName`, 호출 대상 구별, client/server
operation별 분리는 그 입력에 남지 않는다. 따라서 “media 호출이 길다”는
원시 단서는 “compose 서비스의 평균 latency가 크다”는 값으로 전달된다.
모델이 다른 서비스의 관측과 함께 root를 구별해야 하는 표현이라는 점은
코드와 실제 수치 양쪽에서 확인했다.
이는 trace 특징의 설명이며, 별도의 서비스 목록·정적 그래프까지 없다는 주장은 아니다.

이는 **전처리 산술 오류를 발견했다는 뜻은 아니다**. 원시 지표 720개
서비스-초 행(7채널)과 occurrence-weighted trace 평균은 저장된 원형 입력과
정확히 일치했다. 다만 전달되는 정보의 서비스 위치와 구별 수준이 원시 span과 다르다.

### 로그와 지표도 함께 확인했다

- 여섯 창 모두 media와 text의 원시 로그 행은 없고 해당 서비스 Hawkes 입력도 0이다.
- 로그는 compose/home-timeline/social-graph/user에 있었다. compose의 기록은
  home-timeline 쓰기 실패, home-timeline의 기록은 social-network 팔로워 조회 실패였다.
  이를 media 원인의 직접 명명 증거로 해석할 수 없다.
- 창 115/120의 media 지표 최대 |z|는 각각 **0.881 / 0.693**이다.
  이 두 창은 큰 root 지표 이상치로 정답을 바로 구별하는 형태가 아니다.
- 창 129/133에서는 같은 media 손실 사건 안에서 text로 틀리는 예측이 남았다.
  그러나 동일 창을 다른 seed는 맞히기도 하므로 “입력으로 식별 불가능하다”고
  결론내리지 않는다.

이 원시 확인은 네트워크 사례가 단순한 root-local 이상치 탐지와 다른 이유를
보여 준다. **그 표현이 SN·TT 학습 속도 차이를 얼마나 만들었는지**, 또는
후반 모델이 실제 어떤 단서를 이용했는지는 개입·내부 표현 검사가 없어 미확인이다.
TT도 같은 종류의 집계를 사용하므로 SN 사례만으로 TT와의 인과적 차이를 확정하지 않는다.

근거: `raw_media/evidence.json`, `raw_media/operation_durations.json`,
`RESULTS.json:changed_window_inputs`; 원시 시작시각 및 서비스별 지표·span·로그가
각 사례 파일에 보존돼 있다.

### 단순 root trace 결측 설명의 반례

같은 정의의 validation 장애 창에서 root trace 값이 모두 0인 창은
SN **21/65**, TT **634/686**이다. 해당 창의 세 seed 평균 정답률은
SN **92.06%**, TT **98.90%**였다. 따라서 root trace 결측 하나로
TT보다 SN이 느리다는 설명은 성립하지 않는다. 0-filled 값은 관측된 latency
0이라는 뜻이 아니며, 전체 로그·지표 정보의 부재를 뜻하지도 않는다.

근거: `RESULTS.json:root_trace_absence`, `cache_checks`.
허용된 TT 4,069행 캐시의 TRAIN scaler가 원래 native 실행과 정확히 일치함을 확인했다.

## 5. 공동 손실 선택은 정확도와 어긋날 수 있다

원래 선택 규칙은 `0.5 × detection CE + 0.5 × fault-root CE`의
validation 최솟값이다. 최고 root Top-1 선택이 아니다.

예를 들어 SN50 seed 23은 epoch 48의 joint loss가 최소여서 62/65를 선택했지만,
epoch 47/50에서는 63/65를 맞혔다. SN200 seed 37도 최고 root Top-1은
63/65(epoch 129에서 최초)이지만 실제 선택 epoch 200은 62/65다.

그렇다고 SN50 저점을 선택 규칙만으로 설명할 수는 없다. 첫 50epoch에서
seed별 최고 Top-1을 사후 선택해도 평균은 **90.26%**로, 실제 89.74%보다
0.51%p 높을 뿐이다. 이는 검증자료를 본 사후 상한 점검이지 새 기준법의
성능이 아니다.

SN seed 11의 선택 모델을 비교하면 root CE는 **0.43787 → 0.26012**로
낮아졌지만 detection CE는 **0.19292 → 0.25289**로 높아졌다.
공동 손실 개선과 각 과제의 변화가 같지 않음을 저장 logits에서 재계산했다.

근거: `RESULTS.json:runs`, `selected_loss_components`.

## 6. Hawkes 교정 전후: 첫 50epoch도 비교했다

방향은 **relative-after − absolute-before**다. 두 arm 모두 relative
event knots를 쓰고 horizon만 `10`과 `window_start+10`으로 다르다.
공개 포크의 이 horizon 차이만 다룬 대조이며 저자 전체 구현 재현이 아니다.

| seed | absolute 첫50 선택 epoch / 정답 | relative 첫50 선택 epoch / 정답 |
|---|---|---|
| 11 | 49 / 59/65 | 49 / 55/65 |
| 23 | 50 / 61/65 | 48 / 62/65 |
| 37 | 50 / 58/65 | 50 / 58/65 |
| 평균 Top-1 | **91.28%** | **89.74%** |

두 arm 모두 200epoch까지 선택 범위를 넓힌 결과의 평균 Top-1은 95.38%다.
하지만 초기 50epoch의 joint loss는 각 seed의 50개 시점 모두 달랐고,
Top-1도 각각 38/33/37개 시점에서 달랐다. “200epoch 결과가 같으니 초기
학습도 같았다”는 해석은 틀리다.

동시에 교정의 첫50 효과는 seed별 −6.15 / +1.54 / 0%p로 방향이 일치하지
않아, 교정이 SN 초기 학습을 일관되게 가속했다는 주장도 지지되지 않는다.

한계: relative 쪽은 기존 SN50 예측이 남아 있지만 absolute 쪽에는 첫50
선택 모델의 예측이 남지 않았다. aggregate history로 선택 epoch·점수는
복구할 수 있지만 **양 arm의 첫50 사례별 오답 대조는 불가능**하다.
중단됐던 absolute seed23의 epoch19 산출물은 첫50 선택 모델의 대체물이 아니다.

근거: `RESULTS.json:hawkes_first50`; 기존 contrast의 `REPORT.md`,
각 canonical `runs/absolute_seed_*/{config,history,summary}.json`.

## 7. 어디까지 원인을 설명했는가

| 질문 | 현재 판정 |
|---|---|
| 실제 학습량이 달랐나? | **확인.** 650 대 100 update. 선택 모델의 update도 확인했다. |
| 갱신 횟수만으로 차이를 설명하나? | **미입증.** 근접 update에서도 TT 우위가 남고 조건도 다르다. |
| SN에서 무엇이 후반에 개선됐나? | **확인.** 주로 지연 장애의 root 선택, CPU 점수는 그대로다. |
| root의 직접 지연·로그 단서가 항상 있었나? | **아니다.** media 원시 사례에서 caller 쪽 지연과 root-local 부재를 확인했다. |
| 입력 표현은 그 단서를 어떻게 전달했나? | **확인.** 호출 operation을 지우고 호출자 서비스 평균으로 합쳤다. |
| 그 정보 손실이 느린 학습의 결정적 원인인가? | **미확인.** 동일 입력의 seed별 방향도 다르고 통제 개입이 없다. |
| joint-loss 선택 또는 Hawkes 교정 하나로 설명되나? | **그 근거는 없다.** 선택 격차는 일부이고 초기 horizon 효과는 seed별로 다르다. |
| 어떤 특징을 어느 epoch에 배웠나? | **기록 부족.** 매 epoch 사례별 logits·내부 표현이 저장되지 않았다. |

이번 확인으로 **학습 예산을 무시한 구조적 결함 주장도, 예산 하나로 분석을
끝내는 주장도 피해야 한다**는 점이 더 구체화됐다. 특정 새 모듈·정규화 변경·
데이터 확장이나 추가 학습은 실행하지 않았다.

## 8. 검증 및 접근 경계

- native 9개 실행과 absolute Hawkes 3개 실행의 기존 기록을 재사용했다.
- native 9개 저장 예측의 라벨·인덱스·점수와 선택 손실을 독립 재계산했다.
- SN50/SN200 첫50 수치 이력·입력·split·scaler 일치, 195회 paired 결과 보존.
- 부모 분석이 사용한 파일 70개의 SHA-256을 기록하고 분석 전후 일치를 확인했다.
- `analyze.py` LSP: **No diagnostics found**.
- 동률·정상 제외·극단 logits·전환 분류 self-check 통과.
- 독립 CLI **exit 0 / NATIVE_LEARNING_CHECK_PASS 9**:
  `mon_CPS96JVGQXP8YTQV`, `bash_4`.

재현 명령은 결과 JSON을 생성한 Python 3.10.12 / NumPy 2.2.6 환경을 사용한다.
소수값까지 엄격한 JSON 일치 검사를 유지했다.

```sh
cd /home/gnho1236/r2
PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  /usr/bin/python3 -B research/native_learning_diagnosis_20261018/analyze.py
```

초기 `.venv-mlp` 환경의 검사는 최종 JSON 일치 assert에서 exit 1이었다.
원인 조사 출력에서 NumPy 환경 간 확률·손실의 마지막 소수 자릿수 불일치가
확인됐다(총 202개 불일치, 처음 10개 진단 출력 보존). 조건·점수·해시 assert는
그 단계 전에 통과했다. 같은 생성 환경으로 실행 경로를 수정했으며 비교 허용
오차를 늘리거나 실패 검사를 삭제하지 않았다.

원시 검사에서는 공유 파일 전체를 해시/시각 라우팅 때문에 읽고 JSON을 파싱했다.
따라서 보호 구간의 **바이트나 JSON을 전혀 열지 않았다고 주장하지 않는다**.
관측 내용 분석·모델 입력 수치 해석은 지정된 여섯 개발 창에 한정했고
보호 test/unassigned 모델 입력의 특징화·학습·평가는 하지 않았다.
원시 검사 상세 영수증 `raw_media/REPORT.md`까지 대조를 완료했다.

- 원시 14개 파일의 기존 SHA-256 일치, 선택 지표 5,040개 cell 및 trace
  720개 서비스-초 평균의 **정확 일치**를 확인했다.
- 원시 producer `mon_430HZ79VVMKDJR72`, 전체 출력 회수
  `mon_ANZQYR96DB8QFR7P`, operation 집계 추가
  `mon_4BM408FE74JFX06A`는 모두 **exit 0**이다.
- 이후 보호 경계 필드 이름·설명만 명확히 수정했다. 수치 계산은 바뀌지
  않았으며 원시 파일을 다시 스캔하지 않았다. 수정 후 LSP와 metadata-only
  검사는 통과했다. 위 producer 영수증은 설명 수정 전 소스의 실행임을 구분한다.
- 자식 검사에서 처음 발생한 NumPy/pandas ABI import 실패, 정적 import 진단,
  독립적으로 재그룹한 평균의 마지막 소수 자릿수 차이와 복구 내역도 해당
  원시 보고서에 남아 있다. 기존 raw-to-input 정확 일치 검사는 약화하지 않았다.
