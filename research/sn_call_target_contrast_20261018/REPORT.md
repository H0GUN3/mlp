# SN 호출 대상 귀속 대조 결과

2026-10-18 · 단일 변경, 동일3seed·50/200epoch 선택 규칙 · 검증 PASS

## 1. 결론

**50epoch에서 작은 개선은 관측됐지만, 일관된 지연 장애 진단 개선법으로
채택할 근거는 부족하다.** 초기 개선을 없었다고 처리하지 않되, 기존
SN200 기준선까지 포함하면 이 destination-only 후보는 현재 조건에서 보류한다.

| 예산 | 지표 | 기존 owner 집계 | 호출 대상 집계 | 차이 |
|---|---|---:|---:|---:|
| 50epoch | 전체 Top-1 | 89.74% | **90.26%** | +0.51%p |
| 50epoch | 지연 장애 Top-1 | 80.56% | **83.33%** | +2.78%p |
| 200epoch | 전체 Top-1 | **95.38%** | **95.38%** | 0.00%p |
| 200epoch | 지연 장애 Top-1 | 93.06% | **91.67%** | −1.39%p |

50epoch의 지연 순증은 seed37에서만 발생했고, 다른 두 seed는 순증0이었다.
200epoch에서는 seed23의 지연 정답이1창 줄었고 나머지 두 seed는 동일했다.
따라서 일관된 초기 학습 가속이나 최종 지연 정확도 개선이 확인됐다고 말하지 않는다.
이 결과는 **이 고정된 귀속 방식·모델·개발 분할**에 대한 판단이지, 호출 대상
정보의 모든 활용이 무효라는 증명은 아니다.

근거: `RESULTS.json:aggregates`, `seed_scores`, 전수 `paired`.

## 2. 실제로 무엇을 바꿨는가

### 귀속 확인

허용 index112에서 같은 trace의 compose 소유 `compose_media_client`
span과 media 소유 `compose_media_server` span이 정확한 CHILD_OF ID로 연결됐다.
client는5.990747초, server는12μs였다. index115의 client6.008163초도 compose가
기록했다. **약6초는 caller-observed 호출 경과시간이며 media 내부 처리시간이 아니다.**

고정 공개 parser와 로컬 전처리 모두 `process.serviceName`에 귀속한다.
논문의 callee별 평균 서술과 별개로, 공개 parser에는 operation→target 사전이
없었다. 따라서 로컬 구현만 잘못됐다고 확정하지 않았다.

### 단일 처리 변경

기존 TRAIN316에서 양 끝 span의 시작시각이 모두 TRAIN인 직접 CHILD_OF 연결로만
`(기록 서비스, 정확한 client operation) → 호출 대상` 사전을 만들었다.
11개 singleton key,6,622개 중복 제거된 근거 쌍이며 media key에는602개 근거가 있다.
validation index112는 사전 생성에 사용하지 않았다.

- 사전을 먼저 동결한 후 validation 입력을 처리했다.
- 확인된 client occurrence의 **집계 서비스 인덱스만** target으로 옮겼다.
- unknown client·nonclient는 기존 owner에 그대로 남겼다.
- 모든394,075개 occurrence를 각각 한 번 보존했다. 중복 span ID 가중을 제거하지 않았다.
- duration·시작 bin·산술평균·zero-fill·서비스 순서·`(394,12,10,2)` shape와
  channel1=0을 유지했다.
- metrics·relative Hawkes logs·labels·indices는 원소별 정확히 같았다.
- 모델 구조·75,810파라미터·초기화·optimizer·분할·선택 규칙은 동일하다.
- 정규화 규칙은 기존 TRAIN mean/std/epsilon1e-8/no clipping 그대로다.
  metric 통계는 기존과 정확히 같고, trace 계수만 변경된 TRAIN trace에서
  같은 규칙으로 다시 계산됐다. 새로운 정규화 방법을 추가한 것은 아니다.

TRAIN의155,584개 client occurrence 중79,959개, validation의38,902개 중
20,307개가 이동했다. 미확인 호출은 추정하지 않았으며 각 fallback 내역은
`inputs/preparation.json:mapping_coverage`에 보존했다.

원시 index115에서는 media trace가 기존0-filled에서 약6.008163초로 실제
이동했다. 다만 다른 서비스의 incoming 호출도 함께 귀속되므로 “가장 큰 값이
항상 root가 된다”는 변경은 아니다.

근거: `PROTOCOL.md`, `attribution_cases.json`,
`attribution_sources/AUDIT.md`, `inputs/mapping.json`, `PREPARATION.md`.

## 3. 실험 조건과 seed별 결과

원형 SN TRAIN316/validation78을 유지했다. root 분모는 장애65창이며 정상13창은
root 점수에서 제외했다. 기존 SN50/SN200 결과를 hash 고정해 재사용했고,
새 실행은 seed11/23/37 각각200epoch,400update였다. batch256,Adam lr0.001,
dropout0.1,validation joint loss strict minimum/earliest tie를 유지했다.

첫50 범위의 선택 checkpoint·예측을 따로 보존한 뒤 동일 optimizer/RNG 학습
경로를200까지 계속했다. 50에서 재시작하지 않았으며 연장·추가 seed·튜닝은 없었다.

| 예산 | seed | 선택 epoch: 기존→변경 | 전체 Top-1: 기존→변경 | 지연 정답: 기존→변경 |
|---|---:|---|---|---|
| 50 | 11 | 49→49 | 84.62%→86.15% | 17/24→17/24 |
| 50 | 23 | 48→49 | 95.38%→93.85% | 23/24→23/24 |
| 50 | 37 | 50→44 | 89.23%→90.77% | 18/24→20/24 |
| 200 | 11 | 192→89 | 92.31%→93.85% | 21/24→21/24 |
| 200 | 23 | 78→187 | 98.46%→96.92% | 24/24→23/24 |
| 200 | 37 | 200→155 | 95.38%→95.38% | 22/24→22/24 |

선택 epoch도 한 방향으로 빨라지지 않았다. 선택 epoch가 이르더라도 모든
실행은200epoch를 수행했으므로 그 숫자로 실제 학습시간 절감을 주장하지 않는다.

### 종류별·보조 지표

| 예산 | 종류 | Top-1 기존→변경 | Top-3 기존→변경 |
|---|---|---|---|
| 50 | CPU | 98.25%→98.25% | 98.25%→100.00% |
| 50 | 지연 | 80.56%→83.33% | 98.61%→97.22% |
| 50 | 손실 | 92.42%→90.91% | 96.97%→98.48% |
| 200 | CPU | 98.25%→98.25% | 98.25%→100.00% |
| 200 | 지연 | 93.06%→91.67% | 98.61%→98.61% |
| 200 | 손실 | 95.45%→96.97% | 98.48%→100.00% |

전체 Top-3는50에서97.95%→98.46%,200에서98.46%→99.49%였다.
Root NLL 평균은50에서0.36433→0.33511,200에서0.17539→0.16990으로 낮아졌다.
반면 detection F1은50에서0.97408→0.96684,200에서0.98211→0.97169로 낮아졌다.
200의 gated Top-1도94.36%→92.82%였다. 주 연구는 조건부 root 진단이지만
유리한 보조 지표만 고르지 않고 반대 방향도 공개한다.

근거: `RESULTS.json:seed_scores`, `aggregates.*.by_type`.

## 4. 새 정답과 새 오답: 여러 사건인가

각 budget은65창×3seed=195회 대응 예측이다. 아래 수치는195개 독립 사건을
뜻하지 않는다. 고유 창·사건은 seed가 다르면 여러 범주에 겹치므로 합산하지 않는다.

| 예산 | 변화 | 창×seed 횟수 | 고유 창 | 고유 사건 | recording |
|---|---|---:|---:|---:|---:|
| 50 | 새 정답 | 12 | 9 | 5 | 3 |
| 50 | 새 오답 | 11 | 6 | 5 | 3 |
| 50 | 지속 오답 | 8 | 7 | 7 | 4 |
| 200 | 새 정답 | 6 | 5 | 3 | 2 |
| 200 | 새 오답 | 6 | 6 | 5 | 4 |
| 200 | 지속 오답 | 3 | 3 | 3 | 2 |

50은 동시 정답164회,200은180회다. 동률 부분 credit 사례는 없었다.
50 지연에서 새 정답9회·새 오답7회,200 지연에서 새 정답3회·새 오답4회였다.

사건 안의 여러 창을 고려하기 위해 사건별 window-hit 평균을 계산하고
3seed 평균 차이를 기술적으로 집계했다. 원래 창 점수를 대체한 새 주 지표가 아니다.

| 예산 | 순개선 사건 | 동률 사건 | 순악화 사건 | 순개선 recording 수 |
|---|---:|---:|---:|---:|
| 50 | 3 | 22 | 3 | 2 |
| 200 | 2 | 23 | 3 | **1** |

200의 순개선 두 사건은 최초 문제를 살핀 같은 recording의 media 지연/손실
사건이다. 특히 media 지연은 기존7/9→변경9/9의 사건-seed-window 정답으로
좋아졌다. 그러나 다른 지연 사건에서 생긴 오답 때문에 전체 지연 정답은 줄었다.
예를 들어 seed11/index112·115는200에서 새 정답이 됐지만, media 손실
index136은 같은 seed에서 새 오답이 됐다.

따라서 특정 media 사례에서 줄어든 오류는 확인됐으나 **여러 독립 사건에 걸친
일반화된 개선**은 확인되지 않았다. 28개 validation event_id가 TRAIN과 사건을
공유하고, 전체 자료도4개 recording을 공유한다. 단순 고유 ID 수를 독립 표본 수로
부풀리지 않는다.

근거: `RESULTS.json:paired`, `event_window_hit_means`,
`aggregates.*.transitions`, `event_window_hit_mean_win_tie_loss`.

## 5. 실제 처리 시간

| 항목 | 기존 기록 | 이번 대조 |
|---|---:|---:|
| seed당 첫50 학습+validation 평균 | 13.10초 | 13.60초 |
| seed당200 학습+validation 평균 | 54.65초 | 52.26초 |
| 새3개 실행의 실제 병렬 경과 | 비교 가능한 기록 없음 | 54.01초 |
| 새3개 실행200 학습+validation 시간 합 | — | 156.77초 |
| 새 입력 준비의 active 처리 시간 | 동일 조건의 비교 아님 | 45.08초 |

각 seed의 checkpoint50/200 재검증은 합쳐 약0.09초였다.
첫50 시간은200 시간에 포함되므로 두 값을 더하지 않는다.
병렬 경과54.01초와 프로세스 시간 합156.77초도 서로 다른 비용이다.

입력 준비45.08초에는 최초 guard 실패 시도17.98초와 복구 producer27.10초가
포함되고 코드 수정·대기 시간은 제외된다. 사전 단계17.86초는 실패 이전의
filesystem wall-clock 기록이며, 재개한 집계21.72초는 monotonic 측정이다.
중단 없는 정상 한 번의 전체 전처리 benchmark라고 부르지 않는다.

기존과 현재는 비동시 실행이고 공유 서버 부하가 다를 수 있다. 기존 runner는
매 epoch 전체 history JSON을 갱신하고 새 runner는 JSONL을 기록하는 등
기록 비용도 달라 **52.26초 대54.65초로 효율 개선을 주장하지 않는다**.
모델 구조와 학습 update 수는 동일하다.

근거: `RESULTS.json:timing`, `preparation_cost`,
`concurrent_candidate_wall_seconds`; `PREPARATION.md`.

## 6. 연구상 분류와 다음 단계 판정

- **관측 효과:**50 예산에서 작은 초기 개선,200에서는 전체 Top-1 동률과
  지연 Top-1 감소. 초기 개선은 존재하지만 seed·예산별 일관성이 없다.
- **재현 교정 여부:**로컬과 고정 공개 parser가 같은 owner 집계를 하므로
  로컬만의 재현 오류를 고쳤다고 확정할 수 없다. 논문의 callee 서술에 근거한
  입력 귀속 변형의 대조로 분류한다. 공개 포크와 저자 전체 실행의 동일성도
  확인한 것이 아니다.
- **방법·노벨티:**호출 대상 지연 활용 자체는 Eadro/MicroHECL의 선행 개념과
  겹친다. 이번 실험은 새 RCA 원리를 입증하거나 기존 방법보다 발전한 모델을
  확립한 결과가 아니다. 출처 범위는 `attribution_sources/AUDIT.md`에 명시했다.
- **판정:**이 destination-only 후보를 현재 설정에서 개선법으로 채택하지 않는다.
  media의 일부 오류를 줄였지만 다른 오류가 상쇄했고,200 지연 목표도 개선되지 않았다.
  이 한 차례의 대조는 여기서 종료하며 추가 튜닝·모듈·귀속 변형·TT·RE2 확장으로
  자동 진행하지 않는다.

이 판단은 모든 call-aware 표현을 포기해야 한다는 주장이 아니다.
이번에 실제 실행한 한 후보를 지지할 충분한 근거가 없다는 제한된 결론이다.

## 7. 검증·보존

- 입력10개,runner3개,독립 scorer3개의 집중 fixture가 통과했다.
- 지정 `.venv-eadro`/Python3.8 Pyright는0errors/0warnings.
  일반 workspace의 DGL 경로 진단은 별도 환경 문제로 기록했고 억제하지 않았다.
- 새3개 학습 모두 실제 exit0/200epoch/400update.
-50/200 선택 checkpoint6개 모두 bitwise logits·labels·indices replay와
  exact loss replay 통과.
- 독립 NumPy 평가가 기존6개·신규6개 예측의390개 대응 기록을 재계산했다.
  `mon_XKVSHD5WSK2A5AVC`:exit0,`CALL_TARGET_EVALUATION_PASS 390`.
- baseline42개 파일과 새 source/input/예측/checkpoint hash를 대조했다.
  초기 입력 guard 실패는 보존됐고,학습 재시도·추가 fit·기준선 재학습은 없었다.
- 공유 raw JSON은 시각 라우팅 과정에서 구조적으로 파싱했다. 보호 구간의
  raw 바이트가 전혀 읽히지 않았다고 주장하지 않는다. 보호169+1의 수치 모델
  입력·정답 평가에는 접근하지 않았다.

실행 명령·실제 완료 영수증은 `EXECUTION.md`, 전체 수치는 `RESULTS.json`,
입력 재현·사전 근거·실패 복구 기록은 `PREPARATION.md`와 `inputs/`에 있다.
기존 실험·데이터·공용 계정은 수정하지 않았고,TT/RE2는 실행하지 않았다.
