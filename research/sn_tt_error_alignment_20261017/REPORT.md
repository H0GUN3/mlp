# SN–TT 진단 정확도 연구 결정

## 결정

목표는 **각 데이터셋에서 독립적으로 학습하면서 공통 평가·개선 원칙을 쓰고, TT 진단 성능은 유지하며 SN에서 확인된 오류를 개선하는 것**이다. 현재 근거로는 개선할 특정 원인이나 모델 변경을 고를 수 없다. 따라서 효율 비교로 방향을 바꾸지 않는다. 기존 오류 요약의 전수 집계는 끝났으며, 후속 후보는 확인된 한 사건 안에서 정답 창과 오답 창의 입력·점수 차이를 대조하는 좁은 진단이다. 그 후속 접근은 이번에 수행하지 않았다.

점수를 먼저 구분한다. **SN200 native DiagMLP 95.38%**는 65개 검증 장애창/run의 조건부 root Top-1이고, **TT50 native 98.64%**는 TT 검증 장애창의 같은 이름 지표다. **교정 SN 23.59%**는 별도 사건 분리 예측을 창 동일가중으로 다시 채점한 값이며, 그 보고서의 사건당 점수는 25.00%다. 입력·분할·채점 단위가 다르므로 이 세 수치로 데이터셋 순위, 공통 저성능 SN 기준선, 또는 한 변경의 효과를 주장할 수 없다. 특히 SN200 점수가 높다는 점을 숨기거나 23.59%와 같은 조건으로 다루지 않는다. (`CONDITIONS.md` “조건 행렬”, “수치가 말해 주는 범위”; `sn_corrected_20261017/ANALYSIS.md` “사건 외부평가”; `sn_corrected_20261017/WINDOW_RESCORE.md` “Results”)

## 관측된 오류와 선택

SN200 native 요약에서 root 선택 오답은 **3개 seed 전체 합계 9회**, 8개 고유 창, 6개 이벤트다. `media-service → text-service`는 2회/2창이지만 **같은 fault08 이벤트 하나**에만 나타났다. 따라서 한 이벤트 안의 반복은 관측됐지만 서로 다른 사건에서 반복되는 혼동쌍은 확인되지 않았다. 9회는 seed별 9회가 아니며, seed와 창을 독립 장애로 세지 않는다. 이는 오답 후보가 기록됐다는 관측이지, 왜 틀렸는지의 설명은 아니다. (`SN_ERRORS.md` “SN200 DiagMLP의 기록된 오답 쌍”; `native_reproduction_20261013/sn200_error_note.md`; `native_reproduction_20261013/sn200_error_windows.json`의 `models.diagmlp.non_unique_correct_root_evaluations_by_band`, `distinct_root_error_windows`, `error_examples`)

TT에서는 최근 native 검증에서 `ts-travel-service → ts-food-service` 혼동이 관측됐다. probe는 24개 seed-window 오류, 15개 고유 창을 기록하고, 13개 창에서 두 후보 호출 수가 모두 0이며 2개에서만 호출 수가 달랐다고 보고한다. 이것은 혼동과 호출 수의 동반 현황일 뿐 호출 수를 추가하면 해결된다는 증거가 아니다. 이는 오래된 RCAEval 17-feature `train-service/delay_2` 적응 실험의 오류가 아니다. (`tt_re2_baselines_20261017/INTERIM_REPORT.md` §1–2; `tt_re2_baselines_20261017/TT_CONFUSION_PROBE.json`의 `seed_window_errors`, `unique_windows`, `windows_both_counts_zero`, `windows_with_different_candidate_counts`; `CONDITIONS.md` “RE2 travel/food 오류 근거의 경계”)

**판정:** 기존 증거는 SN에서 오류가 존재함을 보이지만, 사건 간 반복 혼동이나 원인을 확정하지 않으며 특정 변경을 지지하지 않는다. 상한 없는 전체 오답 목록에서 해당 쌍은 한 이벤트에만 있으므로, 사건 간 반복 여부를 확인하려고 예측 배열을 다시 열거나 채점 단위를 바꿀 필요가 없다.

다음 질문은 **“같은 media-service 장애 사건에서 해당 seed가 맞힌 창과 text-service로 틀린 창 사이에 입력·후보 점수 차이가 있는가?”** 하나로 제한한다. 이는 한 사건의 탐색적 원인 점검이며, 공통 결함이나 개선 효과의 증명이 아니다. 필요한 허용 개발 입력·저장 예측 점수의 접근은 별도 명시 승인 후에만 가능하고 이번에는 하지 않았다. 새로운 모델 학습·분할·보호 시험 접근을 요구하지 않는다. 사건 간 반복이 없다는 이유로 모든 후속 연구를 금지하는 것도 아니다.

또한 조건 대조에서 **SN50 89.74% → SN200 95.38%**를 확인했다. 같은 입력·분할과 첫 50epoch 이력이 검증된 두 예산의 validation 선택 결과다. 단순히 “SN은 23.59%이니 약하다”는 출발점보다 학습 예산·모델 선택 조건을 먼저 맞춰야 함을 보여준다. 다만 이 차이는 선택 checkpoint 변화도 포함하며 수렴이나 일반화의 증명은 아니다. (`CONDITIONS.md`; `native_reproduction_20261013/sn50_summary.md`; `followup_gate.md`)

향후 어떤 변경을 승인하더라도 SN과 TT는 각각 자기 자료로 학습하고, 각 데이터셋 내부에서 같은 split·채점 정의의 기준선과 변경안을 짝지어 비교해야 한다. TT 유지의 주 지표는 조건부 Top-1이며 Top-3와 gated 점수도 함께 보고한다. 허용 가능한 TT 하락폭은 아직 합의되지 않았으므로 임의 기준을 만들지 않는다. (`RETENTION.md` “평가 원칙”, “TT 유지 판정”)

## 요구사항 추적 (6)

| # | 요구 | 결정·확인 근거 |
|---|---|---|
| 1 | 실험 조건과 점수 구분 | SN200 95.38%, TT50 98.64%, corrected SN 창 점수 23.59%를 각 cohort·분할·분모와 함께 분리했다. 직접 증감 비교나 “낮은 SN 기준선” 주장은 하지 않는다. `CONDITIONS.md` “조건 행렬”, “수치가 말해 주는 범위”; `WINDOW_RESCORE.md` “Results”. |
| 2 | SN 오류쌍과 반복 단위 | 9회는 세 seed 전체 합계이며 8창·6이벤트다. `media-service → text-service` 2회는 한 이벤트에 국한되어 사건 간 반복 증거가 아니다. `SN_ERRORS.md`의 쌍별 표 및 `sn200_error_note.md`; JSON 필드는 위 절 참조. |
| 3 | 관측과 원인 분리 | SN/TT 오답을 관측으로만 기술했다. 결측, 전파, 그래프, 호출 수를 원인으로 단정하지 않았고 낮은 점수 조건을 골라 문제를 만들지 않았다. `SN_ERRORS.md` “해석의 경계”; `TT_CONFUSION_PROBE.json`의 `scope`, `hypothesis`. |
| 4 | 변경 하나 또는 최소 후속 | 현재 특정 변경은 근거 부족으로 선택하지 않는다. 전수 오답 목록 재집계나 사건 단위 재채점 대신, 한 사건 내 정답·오답 창의 입력·점수 차이 확인을 후속 후보로 둔다. 후속 데이터 접근은 별도 승인 전 실행하지 않는다. `SN_ERRORS.md` “해석의 경계와 다음 진단 하나”; 본 보고서 “관측된 오류와 선택”. |
| 5 | TT 유지와 독립 데이터셋 학습 | 공통 원칙은 데이터셋별 독립 학습·동일 데이터셋 내 짝지은 평가다. TT 하락 허용폭은 사용자 합의 전 미정이며 새 split은 제안하지 않는다. `RETENTION.md` “평가 원칙”, “TT 유지 판정”. |
| 6 | 논문 수치와 복원 결과 구분 | 논문 DiagMLP는 SN/TT에 Eadro, GAIA에 TVDiag를 사용한다. 로컬 native·corrected 결과는 복원/재구성 조건의 결과이며 논문 재현 수치로 부르지 않는다. `RETENTION.md` “다른 데이터셋 결과의 해석”, `CONDITIONS.md` “논문 수치와 재구성 수치”. |

## 수행 범위

기존 지정 보고서와 명시된 요약·분석·검증 근거만 대조했다. 학습, 추론, 전처리, 원자료·NPZ·checkpoint·저장 예측 배열 접근, 보호 SN169+1/TT1744+1 관측의 열람은 하지 않았다. 이 문서는 연구 판단 제안이며 실험 승인이나 실험 결과가 아니다.
