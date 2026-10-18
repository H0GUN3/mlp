# SN Hawkes horizon 변경은 도움이 됐나?

## 결론

**이 고정된 SN validation 조건에서는 horizon 변경이 일관된 Top-1 개선을 보이지 않았다.** Relative-after와 absolute-before의 fault conditional Top-1 세 seed 평균은 둘 다 95.38%였다. Seed 11은 3/65만큼 하락했고, seed 23과 37은 각각 1/65, 2/65만큼 상승했다. Top-3 평균은 99.49%에서 98.46%로 낮아졌다. 새 정답과 새 오답도 primary 지표에서 각각 3건이었다. 따라서 이번 결과는 이 변경이 해당 조건에서 일관되게 도움을 줬다는 주장을 지지하지 않는다. 효과가 없다는 보편적 증명은 아니다.

비교 방향은 전 구간에서 **relative-after minus absolute-before**다. Primary 지표는 fault 창만 대상으로 한 conditional root Top-1이며, normal 창은 제외한다. 보고는 저장된 여섯 validation prediction을 독립 검산한 [분석 검증](ANALYSIS_VERIFY.md)에 근거한다. 이번 비교는 작은 고정 SN validation의 horizon-only 대조이지, 원저자 전체 실험 재현이나 최종 test 평가가 아니다.

## 1. 바뀐 설정과 고정한 설정

공개 전처리 코드에서는 로그 사건 시간을 창 시작점 `s`를 빼 상대시각으로 바꾸면서 Hawkes 종료 시각에는 절대 좌표 `e+1`을 전달한다. 길이 10초 창에서 이는 `s+10`이다. 이번 대조는 선택된 창, 사건, 로그 knot, 템플릿 순서, solver 및 학습 설정을 고정하고 종료 시각만 바꿨다. 공개 코드의 다른 전처리 차이까지 재현한 실험은 아니다. 자세한 근거는 [source 확인](SOURCE_EVIDENCE.md)과 [대조 정의](CONTRAST.md)에 있다.

| 설정 | Before, absolute | After, relative |
|---|---|---|
| Hawkes 종료 시각 | `original_window_start + 10` | `10` |
| 창·로그 사건 | 동일한 394개 선택 창, 동일한 사건 집합 | 동일 |
| 모델·입력 처리 | HawkesADM4, decay 3, baseline 초기값 0.2, 최대 50회 반복, 동일 template와 seed 규칙 | 동일 |
| 분할과 모델 | DiagMLP, 12개 서비스, 7개 이벤트, train 316 / validation 78 | 동일 설정 |
| 학습 예산 | seed 11, 23, 37, 200 epoch / 400 update, batch 256, Adam, learning rate 0.001 | 기존 relative 결과 재사용 |
| 체크포인트 선택 | validation joint loss 최솟값, 동률이면 이른 epoch | 동일 |

세 absolute 모델은 이번 contrast 실험에서 각각 학습했고, 세 relative 결과는 기존 calibration 결과에서 재사용했다. 양쪽 모두 검증 라벨·순서가 일치하며 test 평가는 하지 않았다. 실제 config 요약은 [settings.csv](analysis_v2/settings.csv)에 있다.

## 2. 입력에서 관측된 차이

Hawkes 로그 입력은 394 × 12 × 7 형상이다. 두 설정의 유일한 의도된 차이는 종료 시각이었다. 그 결과 394개 창 전체에서 feature 차이가 관측됐고, nonempty 1,415개 창-서비스 그룹에서 9,789개 feature cell이 달라졌다. 나머지 3,313개 빈 그룹은 두 설정 모두 0이었다. `metrics`, `traces`, `labels`, `indices`는 동일하게 보존됐다.

Relative 로그 feature는 평균 0.072716, 최댓값 2.445443, nonzero 9,789개였다. Absolute 쪽은 평균 `1.4243e-10`, 최댓값 `6.0598e-10`, nonzero 8,557개였다. 즉 absolute 값은 수치적으로 거의 0에 가까웠다. 이것은 관측된 출력 차이이지, 개별 예측 변화의 원인을 입증하는 것은 아니다. 전체 요약은 [input_difference.json](analysis_v2/input_difference.json), 준비 기록은 [preparation.json](inputs/preparation.json)에 있다.

| Seed | Before 선택 epoch | After 선택 epoch | Before 최소 validation joint loss | After 최소 validation joint loss |
|---:|---:|---:|---:|---:|
| 11 | 190 | 192 | 0.171456 | 0.256505 |
| 23 | 115 | 78 | 0.103207 | 0.124237 |
| 37 | 164 | 200 | 0.066057 | 0.079576 |

아래는 history에 저장된 validation joint loss의 epoch 1 / 50 / 200 값이다. 선택 epoch와 선택 loss도 함께 표시했다. 이들은 학습 이력이지, 별도 최종 test 결과가 아니다. 전체 기록은 [history_metrics.csv](analysis_v2/history_metrics.csv)에 있다.

| Seed | Arm | Validation loss, epoch 1 / 50 / 200 | 선택 epoch loss |
|---:|---|---|---|
| 11 | Before absolute | 1.511500 / 0.313641 / 0.185182 | 190: 0.171456 |
| 11 | After relative | 1.509682 / 0.351770 / 0.261217 | 192: 0.256505 |
| 23 | Before absolute | 1.527627 / 0.173304 / 0.138531 | 115: 0.103207 |
| 23 | After relative | 1.529352 / 0.204080 / 0.163427 | 78: 0.124237 |
| 37 | Before absolute | 1.492602 / 0.227378 / 0.216587 | 164: 0.066057 |
| 37 | After relative | 1.494176 / 0.223097 / 0.079576 | 200: 0.079576 |

## 3. Seed별 validation 점수

Root 점수의 분모는 seed당 fault 65개다. Detection은 fault 65개와 normal 13개, 총 78개를 사용한다. 정확한 동률은 균등 기대 credit으로 처리했고 ensemble은 사용하지 않았다. 평균은 세 seed의 비가중 평균이다.

| Seed | Conditional root Top-1, before → after | 차이 | Conditional root Top-3, before → after | 차이 |
|---:|---:|---:|---:|---:|
| 11 | 63/65 (96.92%) → 60/65 (92.31%) | −4.62%p | 65/65 (100%) → 63/65 (96.92%) | −3.08%p |
| 23 | 63/65 (96.92%) → 64/65 (98.46%) | +1.54%p | 64/65 (98.46%) → 64/65 (98.46%) | 0.00%p |
| 37 | 60/65 (92.31%) → 62/65 (95.38%) | +3.08%p | 65/65 (100%) → 65/65 (100%) | 0.00%p |
| 평균 | 95.38% → 95.38% | **0.00%p** | 99.49% → 98.46% | **−1.03%p** |

별도 secondary 지표인 gated joint Top-1 평균은 94.36%로 양쪽이 같고, Top-3는 98.46%에서 97.44%로 낮아졌다. Detection F1 평균은 0.9796에서 0.9821로 약 0.25%p 올랐다. Fault-only root NLL 평균은 0.13155에서 0.17539로 높아졌다. 지표 방향이 하나의 개선 결론으로 모이지 않는다. seed별 및 전체 점수는 [scores.json](analysis_v2/scores.json)에 있다.

Primary conditional root Top-1의 195개 fault window-seed 기록은 **둘 다 정답 183, 둘 다 오답 6, 새 정답 3, 새 오답 3**이다. 별도의 secondary gated-joint Top-1은 **181, 8, 3, 3**이다. 두 분할을 혼동하지 않는다. 195개 기록은 같은 창과 사건을 여러 seed에서 센 것이므로 독립 사건 195개가 아니다. Primary 지표의 전체 짝지은 행은 [paired_fault_windows.csv](analysis_v2/paired_fault_windows.csv), distinct window/event 집계는 [paired_summary.json](analysis_v2/paired_summary.json)에 있다.

새 정답 전체는 [root_new_correct.csv](analysis_v2/root_new_correct.csv), 새 오답 전체는 [root_new_wrong.csv](analysis_v2/root_new_wrong.csv)에서 확인할 수 있다. Primary 새 정답은 distinct window 2개, event 2개, seed 2개에 걸쳤고, 새 오답은 distinct window/event 3개로 모두 seed 11에서 발생했다.

읽기 쉬운 사례:

- 새 정답, seed 23, 원본 index 136, `fault08`, `media-service|network_loss`: 정답 root `media-service`를 놓쳤다가 맞혔다.
- 새 정답, seed 37, 원본 index 346, `fault04`, `unique-id-service|network_delay`: 정답 root `unique-id-service`를 놓쳤다가 맞혔다.
- 새 오답, seed 11, 원본 index 129, `fault08`, `media-service|network_loss`: 정답 root `media-service`를 맞혔다가 놓쳤다.
- 다른 새 오답은 seed 11의 원본 index 112 (`fault07`, `media-service|network_delay`)와 index 258 (`fault07`, `url-shorten-service|network_delay`)이다.

Normal detection 변화 3건은 별도 [normal_detection_changes.csv](analysis_v2/normal_detection_changes.csv)에 기록했고 fault root 분모에는 넣지 않았다.

## 실패 이력과 제한

- **Seed 23 실행 이력:** 최초 시도는 “대기하지 마” 지시를 적용한 assistant의 조기 중단으로 19/200 epoch, 38/400 update에서 종료됐고 exit 1을 기록했다. summary와 완료 exit-0 증거가 없어 phase 2의 초기 판정은 FAIL이었다. partial 시도는 `runs/absolute_seed_23_interrupted_attempt1/`에 보존했다. 이후 canonical `runs/absolute_seed_23/` 실행은 200 epoch / 400 update, 선택 epoch 115로 완료되어 실제 exit 0과 checkpoint replay가 검증됐다. 최종 phase-2 판정은 이 완료 실행에 대한 PASS다. 이전 실패는 숨기거나 현재 완료 실행과 동일시하지 않는다. 세부 기록은 [EXECUTION_VERIFY.md](EXECUTION_VERIFY.md)와 [FIT_23.md](FIT_23.md)에 있다.
- **분석 이력:** 첫 분석 시도는 seed 필드 경로를 잘못 가정해 `KeyError: 'seed'`와 exit 1로 끝났으며 그 시도는 점수를 만들지 않았다. 과거 검증에서 absolute와 relative의 config hash를 서로 같아야 한다고 비교한 것도 잘못된 arm 간 비교였다. 각 arm 내부의 config와 summary hash는 일치한다. 이전 분석 산출물 부재 판정은 갱신된 결과를 반영하지 않으며, 현재 `analysis_v2/` 분석은 실제 exit 0이고 독립 검증도 PASS다. 실패와 정정 내역은 [ANALYSIS_VERIFY.md](ANALYSIS_VERIFY.md)에 남아 있다.
- **그 밖의 검증 이력:** 과거 preflight NOTREADY와 최초 pyright 실패는 후속 corrected preflight 및 수정 후 pyright PASS로 대체됐지만 기록은 보존돼 있다. 준비 테스트 로그의 SciPy deprecation warning도 남아 있다. 실행 검증에는 `EXECUTION_PROTOCOL.md` 문서 fingerprint drift가 provenance caveat로 기록돼 있다. 상세 내용은 [EXECUTION_VERIFY.md](EXECUTION_VERIFY.md)와 [PREPARATION_CHECK.md](PREPARATION_CHECK.md)에 있다.
- **Solver 경고와 수렴:** 최대 반복 50회에 도달한 그룹은 relative 387개, absolute 470개다. cap 도달은 수렴 증거가 아니며 어느 쪽도 수렴했다고 주장하지 않는다. Absolute 로그가 거의 0이고 relative 로그가 유의미한 크기인 대비는 측정됐지만, 구체적 계산 오류 원인이나 점수 변화의 인과 설명은 확인되지 않았다.
- **비용·출처:** 준비 본체는 27.858544초였고, 기록된 보수적 feature 준비 잔여 시간 추정은 65.329829초였다. 이는 오프라인 실행 비용이며 온라인 추론 benchmark나 서비스 지연 측정이 아니다. 준비 당시 NPZ 멤버는 순차 압축 해제 스트림을 통과했고 비선택 observation 바이트는 폐기했다. 따라서 바이트 자체를 전혀 읽지 않았다고 주장하지 않는다. 금지 observation 행은 ndarray로 materialize되지 않았다. 실행 기록에는 `EXECUTION_PROTOCOL.md` 문서 fingerprint drift가 provenance caveat로 남아 있으며, 이를 데이터나 코드 변경으로 단정하지 않는다.
- **분석 경계:** 결과는 65 fault와 13 normal을 가진 고정 SN validation 창에 한정된다. 작은 표본이고 같은 창을 seed별로 반복한 paired 기록은 독립 표본이 아니다. 보호된 SN test/unassigned 관측값과 TT/RE2 자료는 분석하지 않았다. TT 자동 확장도 하지 않았다.

## 완료 및 미수행

완료: 저장된 validation 예측 독립 채점, 실제 입력 차이 확인, seed별 Top-1/Top-3와 history checkpoint 비교, primary 새 정답·새 오답 전체 목록 및 secondary gated 결과 확인. 분석 및 독립 검증은 PASS다.

미수행: phase 3에서의 신규 학습·추론·전처리, 최종 test 평가, TT 자동 확장. 다만 전체 contrast 실험 단계에서는 입력 feature를 생성하고 absolute 모델 3개를 각 200 epoch 학습했으며, relative 모델 3개는 기존 결과를 재사용했다.
