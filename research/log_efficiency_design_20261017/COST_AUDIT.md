# TT 로그 특징 비용 경계 감사

## 판정 요약

현재 확인 가능한 실측은 **오프라인 선택 입력 준비 한 번의 배치 비용**이다.
공개된 기록에서 전체 준비는 234.812058초, 그중 Hawkes는 4 worker 병렬 벽시계
209.706388초다. 단순 산술상 Hawkes 비중은 **89.31% (약 89.3%)**, 차이는
25.105670초다. 이는 파이프라인의 해당 실행에서 관측된 비중이지 온라인 요청의
예상 절감률이나 재사용 가능한 속도향상 추정치가 아니다.

현재 모델 평가는 준비가 끝난 NPZ를 읽어 수행했다. 준비·학습·추론은 서로 다른
경계이며, 기존 실측에는 캐시 hit/miss 비교, 새 창 도착 시 지연, 비용을 맞춘
최적화 기준선의 측정이 없다. 따라서 비용 최적화가 실제로 얼마나 유효한지는
아직 미확인이다.

## 호출 경로와 비용 경계

### 관측부터 순위까지

1. **기존 원형 전처리 경로(선행 비용)** — `native_data.prepare()`는
   `train_templates()`에서 지정 정상 참조 로그로 템플릿을 학습한 다음 각
   recording에서 `metric_series()`, `trace_series()`, `log_rows()`를 실행하고
   준비 배열을 저장한다. 이 선행 작업은 기존 입력 번들을 만드는 경로다.
   TT 선택 준비는 이 번들의 허용된 metrics/latency를 재사용한다
   (`native_reproduction_20261013/native_data.py`, `prepare`, `train_templates`,
   `metric_series`, `trace_series`, `log_rows`; `tt_native_support_20261014/PROTOCOL.md`
   「공통 native-like 입력 계약」).
2. **선택 로그 준비** — `tt_native_support_20261014/prepare.py`,
   `prepare()`는 공통 정상 TRAIN 참조 세 개로 Drain 템플릿을 한 번 학습하고,
   recording별 로그를 timestamp로 선택 창에 라우팅한 후 매칭한다. span도
   선택 창에 라우팅하며, 동일 `(traceID, spanID)`의 고유 개수와 기존 중복
   가중 latency를 별도로 보존한다. 이어 로그가 있는 각 `(창,node)`에 대해
   `hawkes_task()` → `native.fit_hawkes()`를 호출하고 없는 그룹은 0 벡터로
   둔다. 선택 입력을 검증하고 NPZ를 저장·재로딩해 확인한다
   (`prepare.py`, `prepare`, `selected_logs`, `selected_spans`, `hawkes_task`,
   `validate_output`, `publish_npz`; `PREPARATION.md` 「Data boundary」 및
   「Hawkes and verification」).
3. **학습 및 validation** — `tt_re2_baselines_20261017/tt_runner.py`,
   `fit()` → `load_selected()` → `make_data()`에서 선택된 기존 NPZ를 열고,
   TRAIN 창으로 metric/trace scaler를 적합한 뒤 각 창을 batch로 구성해
   `NativeReference`에 전달한다. epoch별 validation, checkpoint 선택, 저장
   checkpoint 재추론이 이어진다. 이 경로는 TT 로그 원문을 다시 파싱하거나
   Hawkes를 재계산하지 않는다 (`tt_runner.py`, `fit`, `load_selected`,
   `make_data`; `native_train.py`, `fit_scaler`, `scaled_partition`,
   `graph_batch`, `validation_predictions`).
4. **추론/순위** — 이미 준비된 metric/trace/log 텐서와 고정 graph를 사용해
   전체 validation fold를 batch 추론하고 점수를 산출한다. 기존 보고서의
   추론 중앙값은 약 1,335–1,368개 창 전체의 graph 구성+모델 추론이다.
   이는 사건 하나의 온라인 응답 지연이 아니며 parsing/Hawkes는 포함하지 않는다
   (`tt_native_support_20261014/REPORT.md`, 「비용」).

### 기존 실측·계산 표

| 구간/측정 | 값 | 분류와 범위 |
|---|---:|---|
| TT 선택 입력 준비 전체 | 234.812058초 (표시 반올림 234.81초) | **측정**: producer 시작부터 선택 NPZ 및 JSON 발행 포함. 단, 원래 허용 입력 번들을 만들기까지의 선행 전처리는 포함하지 않음. `PREPARATION_EVIDENCE.md` 「Actual processing cost」, `artifacts/.../success.json` `seconds` |
| 준비 중 Hawkes 벽시계 | 209.706388초 (표시 반올림 209.71초) | **측정**: 7,845 nonempty 창-node fit, worker lifecycle 포함, 4 worker. `PREPARATION_EVIDENCE.md` 「Actual processing cost」 |
| Hawkes / 전체 준비 | 89.308% (약 89.3%) | **계산**: 209.706388 ÷ 234.812058. 해당 배치 실행의 비중이며 온라인 절감 가능 비율이 아님 |
| 전체 준비−Hawkes | 25.105670초 | **계산**: 234.812058−209.706388. 로그/trace 스캔·템플릿·저장·검증 등 잔여 구간 전체의 합계이지 하나의 처리 단계 실측은 아님 |
| Hawkes fit 시간 합 | 817.599875초 | **측정**: 7,845 task의 개별 fit 초를 worker 간 합산. 병렬 벽시계와 더하거나 같은 지표로 비교하지 않음. `PREPARATION_EVIDENCE.md` 「Actual processing cost」 |
| 준비 세부 단계 | 템플릿 5.338116초; 로그 6.308297초; span 6.307783초 | **측정**: 각각 정상 참조 템플릿 적합, 선택 로그 라우팅/매칭(원문 스캔·hash 포함), 선택 span 라우팅/count(원문 스캔·hash 포함). 단계들을 전체 준비와 더해 재구성하지 않음 |
| 준비 자원 | parent peak RSS 446,812 KiB; 최대 완료 child peak RSS 375,220 KiB | **측정**: 서로 다른 프로세스의 최대치. 동시 합산 peak RSS로 해석 불가. thread 환경 OMP/MKL/OPENBLAS 각 1 |
| solver 상태 | 7,845 fit; 5,585가 50 iteration 상한 도달; warning 0; nonfinite 0 | **측정**: 수렴은 주장되지 않음. 비용 단축 설계가 solver 의미를 바꾸면 출력/품질도 별도 검증 필요 |
| 기준 모델 훈련+validation 시간 | DiagMLP 합 8,643.80초; Eadro 합 9,629.85초; 총 실행 경과 6,561.44초 | **측정**: 18회 학습, 최대 3개 병렬. 실행 시간 합과 wall-clock 경과는 다름. 입력 준비비를 포함하지 않음. `tt_native_support_20261014/REPORT.md`, 「비용」 |
| 기준 모델 추론 | fold 전체 중앙값: DiagMLP 0.704초, Eadro 0.804초 | **측정**: 준비된 입력 사용, graph 구성+fold 전체 추론. 온라인 단일 창 latency나 Hawkes 포함 총비용 아님 |
| 원래 허용 bundle 생성 시간 | 미확인 | **Unknown**: 위 234.812058초는 이미 존재하는 허용 입력 bundle을 바탕으로 한 selected-log 준비 시작 이후의 값이다. upstream 원형 전처리 전체비용은 이 숫자에 포함되었다고 볼 근거 없음 |
| RE2 비용/최종 telemetry | 미확인·열지 않음 | **Unknown**: 이번 점검은 RE2 final telemetry 및 비공개 측정치를 읽지 않았다. RE2 결과로 TT 비용을 추정하지 않음 |

위 표의 출력 크기는 4,069창 × 27 node, logs 60 template-bin,
unique_count 4,069 × 27이다. 준비 4 worker는 **프로세스 수**이며 각 worker의
OMP/MKL/OPENBLAS 제한은 1이다. TT 기준 실행의 모델 프로세스는 CPU thread 2,
interop 1, 최대 세 모델 실행 병렬이었다. 서로 다른 단계의 thread 설정과
동시성을 혼합해 비교하지 않는다.

### 캐시·공유 계산 표

| 항목 | 기존 동작/경계 | 감사 결과 |
|---|---|---|
| 정상 참조 기반 Drain template fit | 선택 준비 실행당 1회, 모든 recording에 공유 | 이 실행에서 5.338116초 측정. 영속 캐시 hit/miss나 여러 실행 간 재사용 여부는 미측정 |
| 선택 로그 parsing·timestamp routing·template match | recording 로그를 훑고 선택 관측을 매칭 | 한 번 생성된 prepared NPZ를 쓰는 기존 학습/추론에서는 반복하지 않음. 새로운 준비 실행/새 창 요청 시 같은 작업을 생략할 캐시는 코드에서 확인되지 않음 |
| span routing·count 및 latency 합산 | recording span을 스캔. ID 중복은 고유 count에서 제거하지만 latency는 occurrence별 유지 | 동일 창/node의 반복 관측 비용을 제거하지 않음. 중복 identity 수는 98,775 retained occurrences 대 23,171 unique identities로 보고됨. 이 과거 batch 비율만으로 온라인 처리시간 절감률을 산정할 수 없음 |
| Hawkes 변환 | nonempty `(window,node)`마다 한 fit; empty group은 zero vector | 총 7,845 fit 대 전체 4,069×27=109,863 가능한 창-node 중 102,018 empty zero group. 서로 다른 창이나 node 사이 fit 결과 공유/중복 제거는 없음. 동일 입력/seed 결정성은 검사됐지만 memoization은 기존/native 경로에서 disabled |
| 출력 NPZ | 준비 완료 후 모델 실행이 공유해 읽는 정적 artifact | 파일을 한 번 만든 뒤 이후 학습 호출이 재사용하는 것은 측정 경계상 준비 재실행 방지다. cache-hit 속도, filesystem/page cache 상태, eviction·버전 무효화는 기록되지 않음 |
| scaler·모델 graph/batch | runner가 실행 중 TRAIN scaler를 만들고 각 batch graph를 구성 | 이 실행 산출물 간 공용 캐시 hit 측정은 없음. scaler는 fold별 학습 데이터 경계로 적합하고 graph는 batch inference/training에서 구성됨 |
| 요청 간 중복 창·서비스 | 기존 producer는 원래 행 순서와 창/node 단위 작업을 유지 | 동일 시간 구간을 다른 recording/요청이 재사용하는 dedup 또는 online shared-compute 경계는 확인되지 않음. 고유 창 정의, tenant/service key, 변경 시 invalidation은 미정 |

**상시 비용 vs 요청 후 비용:** 현 자료는 offline batch 입력 준비와 별도 학습/validation만
측정한다. 상시 collector/ingestion 비용은 측정 범위 밖이고, 요청 후 한 창의
온라인 파싱→rank 지연은 측정하지 않았다. 이미 만든 bundle을 불러오는 연구
실행 비용을 운영 cache-hit latency로 부르지 않는다.

## 미래 측정 설계 — 실행 전 제안

현재 권한에서 실제 측정은 하지 않는다. 다음은 별도 승인 후에만 실행할 최소 설계다.

1. **입력 경계 고정:** 기존 불변 입력으로 먼저 “원문 관측 처리 시작→최종 27개
   후보 순위 산출”을 정의한다. 수집 및 변경하지 않는 앞단 collector는 제외하되,
   기존 bundle을 만드는 전처리가 생략되지 않도록 그 비용을 별도 upstream
   항목으로 기록한다. 배치 준비 1회와 요청 단위 새 창을 따로 측정한다.
2. **공정 기준선(F):** 동일한 관측, template set/학습 참조, 창 분할, 후보,
   나머지 encoder, 학습 checkpoint 및 예산에서 Hawkes 특징을 쓰는 원 F를 둔다.
   F에도 template 결과/입력 파싱의 합법적 공유와 단순 캐시를 적용한다.
   최적화 제안과 F 모두 동일 cache policy·warm-up·worker/thread budget을 쓴다.
3. **비용 맞춘 저비용 대체:** Hawkes를 동일 템플릿의 count/rate로 고정 대체하는
   비교를 먼저 한다. 입력/모델을 재학습하는 비교와, 동일 checkpoint에서
   inference 입력만 0으로 두는 ablation은 별도 표기한다. 단순 캐시 및 중복
   제거를 반영한 F 대비 추가 이득이 충분하지 않으면 선택기는 만들지 않는다.
4. **Cold/warm 정의:** cold는 프로세스 재시작 후 해당 window/service cache key가
   없는 miss로 정의하고, warm은 같은 버전 key의 결과가 hit하는 반복으로 정의한다.
   운영상 유효성 확인용 변경/invalidation 사례도 최소 1개 포함한다. process,
   OS page cache 상태 등 통제하지 못한 warm 조건은 기록하고 cold와 혼합 평균하지 않는다.
5. **공유·중복 단위:** `(input version, window identity, service, feature config)`
   를 cache key 후보로 명시한다. 고유 window 수, 요청 수, node 수, nonempty 및
   empty node-window 수, 중복 요청/관측 수, 실제 계산 수, cache hit/miss를 각각
   기록한다. 공유된 한 계산을 여러 요청에 배분할 때 실제 wall latency와 CPU
   task-sum을 각각 보존한다. 과거 batch에서 관측된 중복 수를 가능한 온라인
   speedup으로 환산하지 않는다.
6. **최소 지표:** end-to-end 관측처리→ranking latency 평균/P50/P95와 단계별
   latency, CPU time/task 합, worker/thread 수, parent+child 동시 peak RSS,
   cache 크기 및 hit rate를 기록한다. 모델 학습 시간/비용은 inference/preparation과
   분리한다. 예측 품질은 동일한 고정 후보·분할의 Top1 및 사전 지정 보조지표로
   함께 기록한다. 기존 보호 창은 열지 않는다.
7. **보고식:** 선택된 feature 사용 시 전체 비용 경계는
   `공통 처리 + L + 선택기 + 실제 전환 F 추가분 + 중복 비용`으로 보고하고,
   해당 경계의 latency 및 memory와 별도 학습 비용을 함께 제시한다. 무작위
   비용맞춤, 단순 임계값, 항상 L, 항상 F 비교군은 같은 입력/예산에서 둔다.
   평균만으로 꼬리 지연을 숨기지 않는다.

### 미확정 결정 및 중단 조건

- 허용 가능한 품질 손실과 최소 비용 절감률은 미합의다. 임의 숫자를 채택하지
  않으며 합의 전에는 비용-품질 tradeoff를 기술적으로만 보고하고 성공 판정을
  하지 않는다.
- 실제 운영의 요청 단위와 고유 window identity, 반복 창 도착 패턴, cache
  freshness/invalidation 및 cold/warm 재현 조건은 미확인이다.
- 고정 저비용 대체가 공정한 캐시 F 대비 충분하면 선택기를 설계하지 않는다.
  이득이 없거나 품질 비용을 합의하지 못하면 후속 계층화 작업을 중단한다.

## 요구사항 추적 및 검증 체크리스트

| Brief 요구 | 보고서 반영 | 상태 |
|---|---|---|
| 3 — 234.81/209.71 출처·범위·비중, offline/online 및 cache miss/hit 분리 | 실제 측정 표, 89.31% 산술, upstream 미포함 경계, 미측정 구분 | **PASS** |
| 5 — 저비용 대체 우선, 캐시·중복제거 F 대비 추가 이득, 역사적 batch share로 online speedup 주장 금지 | 미래 측정 설계 2–5 및 중단 조건 | **PASS** |
| 7 — 전체 비용식, 조건부 비교군, latency/memory/train 비용 분리 | 미래 측정 설계 6–7 및 전체 비용식 | **PASS** |

## 근거 목록

- `research/log_efficiency_design_20261017/BRIEF.md` — 접근 경계 및 요구 3/5/7.
- `research/tt_native_support_20261014/REPORT.md` — 「비용」 및 baseline 해석.
- `research/tt_native_support_20261014/PROTOCOL.md` — 「공통 native-like 입력 계약」,
  「비용·검증·중단」.
- `research/tt_native_support_20261014/PREPARATION.md` — 「Data boundary」,
  「Hawkes and verification」, 「Verified execution」.
- `research/tt_native_support_20261014/PREPARATION_EVIDENCE.md` —
  「Actual processing cost」, 「Solver outcome」, 「Independent post-publication verification」.
- `research/tt_native_support_20261014/artifacts/preparation_20261014T074043_892941Z/success.json`
  — `seconds`, `shapes`, `publication_round_trip_exact`.
- `research/tt_native_support_20261014/artifacts/execution_exit_evidence.json`
  — producer exit 0, solver cap 5,585, warning/nonfinite 및 verification 상태.
- `research/native_reproduction_20261013/native_data.py` — `prepare`,
  `train_templates`, `trace_series`, `metric_series`, `log_rows`,
  `make_knots`, `fit_hawkes`, `event_tasks`, `build`.
- `research/native_reproduction_20261013/native_train.py` — `fit_scaler`,
  `scaled_partition`, `graph_batch`, `validation_predictions`, `run_training`.
- `research/tt_re2_baselines_20261017/tt_runner.py` — `load_selected`,
  `make_data`, `fit`, `validation_predictions` 호출 경로.
- `research/tt_re2_baselines_20261017/TT_PROTOCOL.md` — 기존 prepared 입력,
  3 seed/두 모델 및 CPU thread/병렬 budget.
- `research/tt_re2_baselines_20261017/TT_EXECUTION.md` — 실제 여섯 완료 fit과
  복구·실행 경계.

보호된 TT test 1,744행과 unassigned 1행, RE2 final telemetry, 원본 관측,
NPZ·checkpoint·prediction array는 이번 감사에서 열지 않았다. 실행/import,
벤치마크, preprocessing, 설치, commit도 수행하지 않았다.
