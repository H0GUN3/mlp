# 독립 검증: SN–TT 진단 정확도 분석

## 최종 한정 재검증 (2026-10-17)

### 종합 판정: **PASS**

아래는 기존 검증 이력을 보존하면서, 현재 `SN_ERRORS.md`와 `REPORT.md`에 대한 최종 타깃 일관성 확인을 덧붙인 것이다. 범위는 BRIEF의 여섯 요구사항이며, 이 재검증에서는 추가 배열 열람·재채점·확률 재평가를 하지 않았다.

| # | 판정 | 결정적 근거 |
|---|---|---|
| 1. 점수·조건 분리 | **PASS** | `CONDITIONS.md` “조건 행렬” 및 `REPORT.md` “결정”은 SN200 native 95.38%, TT50 native 98.64%, 교정 SN 창 동일가중 23.59%를 서로 다른 입력·분할·평가 단위의 수치로 구분한다. 이를 하나의 순위나 효과로 비교하지 않는다. 교정 SN 사건당 점수 25.00%도 창 점수와 분리되어 있다. |
| 2. 실제 후보명·반복 단위 | **PASS** | 허용된 텍스트 요약 `research/native_reproduction_20261013/sn200_error_windows.json`, `models.diagmlp`에서 분모는 `fault_window_seed_evaluations_by_band` 180+15=195, 원인 선택 오답은 `non_unique_correct_root_evaluations_by_band` 8+1=9, `distinct_root_error_windows`=8, `root_error_windows_in_all_three_seeds`=[]다. `error_examples`의 모든 기록에서 `root_unique_first=false`인 후보만 보면 오답 기록은 9개이고 8개 창이다. `media-service → text-service` 두 기록은 창 129와 133이며 같은 `SN.2022-04-17T181245D2022-04-17T183616:fault08` 이벤트다. 그러므로 9는 사건 수가 아니고 사건 간 반복도 아니다. 고장 종류에서 후보 이름을 추정하지 않았다. |
| 3. 관측과 원인 구분 | **PASS** | JSON `limitations`는 창·seed 상관, 주석 겹침과 실제 증상 가시성의 차이, 경계 연관이 기전 증명이 아님을 명시한다. 현재 `SN_ERRORS.md`와 `REPORT.md`는 반복 예측을 관측으로만 두고, 기전은 미확인으로 서술한다. 이벤트는 독립 seed가 아니다. |
| 4. 승인된 범위·독립 데이터셋 원칙 | **PASS** | `RETENTION.md` “평가 원칙” 및 `REPORT.md` 요구사항 5는 각 데이터셋에서 독립 학습하고 시스템 안에서 동일 조건을 짝비교하는 원칙을 유지한다. 추가 split·학습·효율 비교를 되살리지 않았고 TT 허용 하락폭도 미정이다. 현재 제안은 실험 실행이 아니다. |
| 5. 증거 공백·한정 후속 | **PASS** | 현 문서의 정확한 미확인점은 동일 `fault08` 이벤트에서 같은 seed의 정답 창과 `text-service` 오답 창 사이 입력·후보점수가 어떻게 다른지다. `SN_ERRORS.md` “다음 질문(하나)” 및 `REPORT.md` “관측된 오류와 선택”은 이를 한 이벤트 안의 탐색적 질문으로 한정하고, 후속 입력/저장 점수 접근은 별도 명시 승인 후에만 가능하다고 쓴다. 새 split이나 fit은 요구하지 않으며 이번에 수행하지 않았다. 이 최종 판정은 이전 VERIFY의 “요약 JSON만으로 event별 혼동쌍을 집계”하자는 문구를 대체한다. |
| 6. 여섯 항목·링크 | **PASS** | `REPORT.md` “요구사항 추적 (6)”은 요구사항 1–6을 각각 추적한다. 보고서가 인용한 로컬 경로는 기존 VERIFY의 링크 확인 기록과 일치한다. 이번에 원 요약의 정확한 경로와 필드를 직접 확인했다. `TT_CONFUSION_PROBE.json`의 TT native travel/food 조건은 `CONDITIONS.md` “RE2 travel/food 오류 근거의 경계”와 같이 RCAEval의 과거 17-feature `error_analysis.md`와 구분되어 있다. |

### 충돌과 정확한 수정 소유자

- **기존 VERIFY 자기모순:** 상단의 과거 종합 PASS와 item 5 FAIL은 당시 상태 기록으로 유지한다. 이 날짜 최종 표가 해당 충돌을 덮어쓰지 않고, 여섯 항목 모두 재판정한 현재 결론을 명시한다.
- **후속 제안 문구:** 이전 VERIFY의 “기존 summary JSON에서 event별 혼동쌍 집계” 제안은 최신 요청 및 현재 producer 문서의 좁은 후속과 맞지 않는다. **수정 소유자: VERIFY 작성자(본 파일)**. 위 PASS가 기존 해당 문단을 대체한다. `SN_ERRORS.md`와 `REPORT.md`에는 추가 수정이 필요하지 않다.
- **향후 승인 경계:** 현재 질문에 필요한 입력·점수 자료 접근은 이번 권한에 포함되지 않는다. 향후 수행하려면 사용자 별도 명시 승인이 먼저 있어야 하며, 승인 없이는 미확인으로 둔다. 승인 전 배열 열람, 새 집계, 재채점, 새 fit은 하지 않는다.
- **제약 확인:** 이 재검증은 보호된 SN169+1/TT1744+1 및 RE2 관측을 읽거나 바꾸지 않았고, 예측 배열·NPZ·checkpoint 접근이나 코드 실행·학습·추론을 하지 않았다.

## 종합 판정: PASS (분석 보고서), 단 후속 제안은 범위 수정 필요

네 산출물과 명시적으로 참조된 원 요약/분석·검증 JSON의 텍스트만 대조했다. 수치 및 핵심 경계는 근거와 일치하고, 반복 혼동쌍은 확인된 사실로 과장하지 않았다. 다만 `SN_ERRORS.md`와 `REPORT.md`의 후속 집계 제안은 저장된 “개발 예측”을 읽는다고 명시한다. 이번 검증 요청은 saved prediction arrays를 명시적으로 금지했으므로, 보고서에 쓰인 “요약”이 실제로 배열을 뜻하는 경우에는 수행 권한이 없다. 아래의 한정 문구처럼 **예측 배열을 열지 않고 허용된 텍스트 요약에 후보 연결이 이미 기록됐는지만 확인**하도록 제안 범위를 좁혀야 한다. 현재 요청을 넘어 그 집계를 수행하지 않았다.

| # | 판정 | 결정적 근거 및 확인 |
|---|---|---|
| 1. 점수·조건 분리 | **PASS** | `CONDITIONS.md` “수치가 말해 주는 범위”와 `REPORT.md` 첫 절은 SN200 95.38%와 TT50 98.64%를 각각 native validation 장애창 조건부 Top-1, SN corrected 23.59%를 별도 corrected 평가의 창 동일가중 Top-1로 구분한다. 원문 `followup_gate.md` “Final parent verification” 표는 SN200 DiagMLP 95.38%, TT50 DiagMLP 98.64% 및 분모 창 65/686을 제시한다. `WINDOW_RESCORE.md` “Results”는 corrected 창 점수 23.589744%와 사건당 순위 25.000000%를 별도 행에 둔다. 반올림하면 23.59%; 어느 값도 native 창 점수와 혼합되지 않았다. |
| 2. 실제 root→후보 반복 근거 | **PASS** | `SN_ERRORS.md`는 SN50/200 요약에 후보 교차표가 없음을 판정 불가로 남기고, corrected 분석은 다른 조건이므로 calibration에 일반화하지 않는다. `sn200_error_note.md`는 DiagMLP 오답 9 seed-평가, 고유 창 8, 세 seed 공통 오답 창 없음이라고 명시한다. `sn200_error_windows.json`의 `models.diagmlp.distinct_root_error_windows` 및 `root_error_windows_in_all_three_seeds` 요약이 이를 뒷받침한다. 이 JSON의 개별 예시에는 실제 root·후보명이 일부 존재하지만, 단일/일부 사건 예시는 반복 혼동쌍 집계가 아니며 보고서는 이를 반복 주장에 쓰지 않았다. |
| 3. 관측과 원인 가설 구분 | **PASS** | `SN_ERRORS.md` “해석 경계”, `CONDITIONS.md` “수치가 말해 주는 범위”, `REPORT.md` #3은 점수 저하와 혼동쌍을 원인 설명으로 바꾸지 않는다. `sn200_error_windows.json` `limitations`는 annotation overlap이 증상 가시성/물리적 활성의 측정이 아니고, seed·창이 상관되며 경계 연관이 기전 증명이 아니라고 명시한다. fault type별 횟수를 인과로 해석하지 않았다. |
| 4. 범위 및 시스템별 원칙 | **PASS** | `RETENTION.md` “평가 원칙”은 같은 데이터셋 안의 paired 비교와 시스템별 별도 결과를 규정하며, “TT 유지 판정”은 손실 허용폭을 사용자 합의 전 미정으로 둔다. `REPORT.md` #4–6 및 마지막 절은 변경안·새 학습을 선택/승인하지 않고 기존 오류 확인 제안만 제시한다. 새 split, 효율 연구, 교차 데이터셋 전이를 부활시키지 않았다. 단, §상단 종합판정의 저장 예측 접근 경계는 별도 교정 대상이다. |
| 5. 증거 공백의 정직성 및 한정된 후속 | **FAIL — 후속 제안 표현만** | 반복 혼동쌍이 입증되지 않았다는 결론 자체는 타당하며, 부족한 증거(후보 연결/코호트 간 일관 집계 없음)도 특정했다. 그러나 `SN_ERRORS.md` “한 가지 다음 진단”은 `paired_events`와 seed 후보 기록을 연결하자고 하고, `REPORT.md` “단일 다음 단계”도 기존 개발 예측을 연결하자고 한다. 이번 작업은 prediction arrays를 읽지 말라고 명시한다. 따라서 실제로는 배열/비요약 예측 artifact를 열어야 하는지 텍스트 자료만으로 확정되지 않은 상태에서 제안이 권한 경계를 분명히 보존하지 못한다. **교정:** 이 VERIFY 단계에서 후속 집계를 실행하지 않는다. 허용 가능한 다음 단계는 기존의 허용된 Markdown/요약 JSON에 이미 root와 Top-1 후보별 카운터가 기록됐는지 확인하는 것으로 한정한다. 해당 요약에 후보 연결이 없으면 “현재 허용 증거로 기전/혼동쌍 미확인”으로 종결하고, 추가 접근은 별도 승인 후 판단한다. |
| 6. 링크·여섯 항목 추적 | **PASS** | `REPORT.md`는 1–6 요구사항을 모두 표의 개별 행으로 다루며, 각 행에 파일·절 또는 JSON 필드를 지목한다. 로컬 상대 참조는 `../native_reproduction_20261013/...`, `../sn_corrected_20261017/...`, `../tt_re2_baselines_20261017/...`, `../research_handoff_20261016/...` 형태로 이 작업 디렉터리 기준 유효한 경로다. `ANALYSIS.json`의 `scope.protected_rows_decoded=0`은 SN corrected artifact 내부 보호행 접근 경계를 확인한다. 본 검증도 금지된 관측·배열·체크포인트에 접근하지 않았다. |

## 충돌 및 수정 소유자

- **범위 충돌:** 이번 사용자 요청은 “saved prediction arrays” 열람을 금지한다. 반면 producer 제안은 저장 예측에서 사건별 후보를 집계할 가능성을 열어 둔다. 이는 분석의 현재 결론을 반박하지 않지만, 후속 작업의 허용 범위와 산출물이 될 수 있는 데이터 형태를 명확히 해야 한다.
- **수정 소유자:** `SN_ERRORS.md` 및 `REPORT.md` producer. 이 검증 파일은 독점 쓰기 범위인 `VERIFY.md`만 작성하므로 두 보고서는 수정하지 않았다.
- **정확한 교정 문구:** “후속은 기존 허용 Markdown/요약 JSON에 root와 Top-1 오답 후보별 집계가 이미 기록되어 있는지만 확인한다. saved prediction arrays를 열거나 그로부터 새 집계를 만들지 않는다. 후보 연결이 허용된 요약에 없으면 혼동쌍을 미확인으로 남긴다.”
- `CONDITIONS.md`, `SN_ERRORS.md`, `RETENTION.md`, `REPORT.md` 사이에서 위 범위 이외의 실질적 수치·해석 모순은 찾지 못했다. 보호된 SN169+1/TT1744+1 및 RE2 관측은 확인하거나 재해석하지 않았다.

## 검사 한계

검사는 기존 문서와 지정된 JSON 텍스트 요약에 한정했다. 저장 예측 배열, NPZ, checkpoint, 모델 코드 실행/가져오기, 학습·추론·전처리, 다운로드는 하지 않았다. 따라서 후보별 전수 빈도나 새 혼동쌍은 검증하지 않았으며, 이를 완료한 것처럼 주장하지 않는다. 이 문서는 실험 성과 판정이 아니라 보고서의 증거·범위 적합성 검증이다.

## 최종 재검증 (2026-10-17)

### 종합 판정: PASS — 단, 반복 혼동의 사건 간 재현성은 미확인

이 최종 판정은 위 초기 검증 이력과 item 5의 당시 FAIL을 보존한다. 이후 요청의 구체 조건을 기준으로 producer의 후속 문구를 다시 확인했다. 배열 접근은 별도 명시 승인 전 실행하지 않는다고 두 문서가 분명히 제한하므로 item 5는 아래와 같이 재판정한다. 보고서/검증 문서의 PASS는 실험 성공이나 인과 메커니즘 확인을 뜻하지 않는다.

| # | 최종 판정 | 결정적 확인 근거 |
|---|---|---|
| 1. 조건·점수 분리 | **PASS** | `CONDITIONS.md` “조건 행렬” 및 `REPORT.md` “결정”: SN200 native 조건부 Top-1 95.38%, TT50 native 조건부 Top-1 98.64%, corrected SN 창 동일가중 23.589744%(반올림 23.59%)를 각각 분리한다. `followup_gate.md` “Final parent verification”은 앞의 두 수치와 각각 65/686개의 상관된 validation 장애창/run을 제시한다. `WINDOW_RESCORE.md` “결과”는 corrected 창 점수와 사건당 순위 25.000000%를 별도로 둔다. `sn50_summary.md` “SN50 native calibration verification”은 SN50 DiagMLP 89.74% [84.62,95.38]를 보조 확인한다. 모두 서로 다른 분할·평가 단위로 표현되어 점수 차이를 조건 효과로 단정하지 않는다. |
| 2. 실제 root→오답 후보 및 반복 단위 | **PASS** | `SN_ERRORS.md` “SN200 DiagMLP의 기록된 오답 쌍”에는 후보 이름과 쌍별 seed-window 오류 수가 명시되어 있고, 표의 오류 수는 2+1+1+1+1+1+1+1=9다. 이는 `sn200_error_note.md` 첫머리의 총 9회/8개 고유 창과 맞는다. 9회는 seed 평가 횟수의 합이고, 쌍별 창 수는 후보가 다른 seed 오답에서 겹칠 수 있으므로 행을 더해 고유 창 수로 부르지 않는다. `SN_ERRORS.md`는 `media-service → text-service`의 2창이 같은 `fault08` 한 이벤트임을 특정하며, 서로 다른 이벤트 간 재현으로 주장하지 않는다. SN50 요약에는 후보 쌍별 집계가 없다고 명시한다. 고장 종류만으로 후보쌍을 추측하지 않았다. |
| 3. 관측과 원인 가설 | **PASS** | `sn200_error_note.md`는 fault-type 횟수를 원인 증명과 구분한다. `SN_ERRORS.md` “해석의 경계”, `CONDITIONS.md` “수치가 말해 주는 범위”, `REPORT.md` “관측된 오류와 선택”은 결측·전파·그래프·호출 수 등을 원인으로 확정하지 않는다. TT 호출 수 수치는 `TT_CONFUSION_PROBE.json`의 집계 필드(`seed_window_errors=24`, `unique_windows=15`, `windows_both_counts_zero=13`, `windows_with_different_candidate_counts=2`)가 동반 현황일 뿐이라는 한계를 지킨다. |
| 4. 범위 및 시스템별 원칙 | **PASS** | `BRIEF.md` “확인할 것”과 `RETENTION.md` “평가 원칙”은 시스템별 독립 학습 및 시스템 내 동일 평가조건의 짝비교를 요구한다. 새 split, 교차 시스템 학습, 효율 비교 부활은 없다. TT 유지 허용폭은 `RETENTION.md` “TT 유지 판정”대로 미정이며 임의 한계를 만들지 않았다. |
| 5. 정직한 증거 공백 및 한정 후속 | **PASS** | 이전 VERIFY의 item 5 FAIL은 당시 후속 표현의 승인 경계가 불명확하다는 우려였다. 재확인한 `SN_ERRORS.md` “다음 질문(하나)”은 저장 예측 배열 분석이 별도 승인 전에는 실행되지 않는다고 명시하고, `REPORT.md` “관측된 오류와 선택”도 “별도 명시 승인이 있다면”으로 조건을 건다. 이번 단계에서는 그 배열 접근·집계를 하지 않았다. 정확한 미확인점은 SN200의 `media-service → text-service`가 다른 `event_id`에서도 반복되는지다. 한정 후속은 기존 허용 summary JSON에 이미 있는 event/root/candidate 요약만으로 이 한 쌍을 event별 집계하는 것으로 제한한다. 필요한 필드가 그 요약에 없으면 멈추고, arrays 접근이나 새 fit은 별도 명시 승인을 받은 뒤에만 검토·실행한다. 승인되지 않으면 미확인으로 종결한다. |
| 6. 여섯 항목·근거 링크 | **PASS** | `REPORT.md` “요구사항 추적 (6)”에 1–6 각 항목이 개별 행으로 있고, 본 VERIFY도 각 항목을 별도 판정했다. 인용한 주요 로컬 파일은 존재 확인했다: `followup_gate.md`, `sn50_summary.md`, `sn200_error_note.md`, `sn200_error_windows.json`, `WINDOW_RESCORE.md`, `INTERIM_REPORT.md`, `TT_CONFUSION_PROBE.json`, `error_analysis.md`, `DIAGMLP_DATAFLOW_AND_VALIDITY.md`. 이 링크 존재 확인은 보호 파일의 열람을 뜻하지 않는다. |

### 충돌 및 정확한 교정 소유자

- **기록된 판정 이력:** 초기 VERIFY는 종합 PASS와 item 5 FAIL을 함께 기록했다. 그 내부 불일치는 당시 상태의 오류다. 본 날짜의 최종 판정은 6개 필수 항목을 각각 재평가한 뒤 종합 PASS로 정정하며, 과거 기록은 삭제하지 않는다.
- **수치/조건 충돌:** 최종 대조에서 SN200 95.38%, TT50 98.64%, corrected SN 창 23.59% 사이의 조건 혼합을 찾지 못했다. SN200 오류 집계는 9 seed-window 오답과 8개 고유 창이며, 이를 9개 독립 사건이나 9개 고유 창으로 바꾸어 말하지 않는다.
- **TT 오류 cohort 경계:** `CONDITIONS.md` “RE2 travel/food 오류 근거의 경계” 및 `INTERIM_REPORT.md` §1–2는 travel/food 관측을 TT native 입력 DiagMLP validation으로 한정한다. 이는 별도 RCAEval 17-feature `train-service/delay_2` 로컬 adaptation (`native_reproduction_20261013/error_analysis.md` 첫 절)의 단일 incident 결과가 아니다.
- **정확한 수정 소유자:** 초기 VERIFY의 자기 판정 모순은 `VERIFY.md` 검증 작성자 소유이며, 이 날짜의 추가 절이 이를 정정했다. producer 보고서에서 추가 수정할 필수 항목은 확인되지 않았다. 후속 제안이 배열 접근이나 새 fit을 포함하도록 바뀌면 `SN_ERRORS.md` 및 `REPORT.md` producer가 먼저 명시적 승인을 요구해야 하며, 승인 전 실행해서는 안 된다.
- **보호 범위:** 본 재검증은 예측 배열·NPZ·checkpoint·모델 실행에 접근하지 않았고, SN169+1/TT1744+1 및 RE2 보호 관측을 열거나 재해석하지 않았다. 이전 검증의 보호 접근 주장도 본 재검증에서 그대로 유지한다.
