# SN 반복 혼동: 현재 증거와 한계

## 판정

**현재 허용된 요약만으로는 서로 다른 장애 사건에서 반복된 root→오답 후보 쌍을 확인하지 못했다.** 다만 SN200 DiagMLP 검증창 기록에는 `media-service → text-service`가 **두 창, 두 seed**에서 나타난다. 두 창 모두 같은 `fault08` 이벤트에 속하므로 독립적인 사건 반복으로 세면 안 된다. 따라서 이것은 한 이벤트 안의 창 수준 반복이지, 일반화 가능한 반복 혼동쌍의 증거는 아니다.

`native_reproduction_20261013/sn200_error_windows.json`의 `models.diagmlp.error_examples`를 전부 살폈다. 각 `seeds[]` 기록에서 `root_unique_first=false`만 원인 서비스 선택 오답으로 셌고, `top_services[0]`을 오답 1위 후보로 집계했다. `root_unique_first=true`인데 `detected=false`인 탐지 실패는 원인 선택 오답에서 제외했다.

## Cohort별 근거

| SN cohort / 평가 단위 | 원인 선택 분모·관측 점수 | 기록된 root→오답 후보 근거 | 이 cohort에서 말할 수 있는 범위 |
|---|---|---|---|
| **Native SN200 DiagMLP 검증** | JSON `fault_window_seed_evaluations_by_band`: 전체 주석 창 180 + 부분 주석 창 15 = **195 창-seed 평가**(65개 창 × 3 seed). `non_unique_correct_root_evaluations_by_band`: 8 + 1 = **9 오답**. `distinct_root_error_windows`: **8**. | 아래 세부표. JSON의 `root_error_windows_in_all_three_seeds`는 빈 배열이다. 즉 같은 창을 세 seed 모두에서 틀린 사례는 없다. | 9는 독립 장애 9건이 아니다. 오답은 6개의 서로 다른 `event_id`에 분포하며, 같은 이벤트에서 생긴 창/seed 반복을 사건 간 재현성으로 주장할 수 없다. |
| **Native SN50 calibration** | `sn50_summary.md` “SN50 native calibration verification”: SN DiagMLP 조건부 Top-1 평균 **89.74% [84.62, 95.38]**, 검증 고장 창 **65개/run**. 세 seed는 같은 창을 평가한다. | 요약에는 root별 1위 오답 후보, 창별 예측 또는 쌍별 집계가 없다. | 점수만으로 특정 혼동쌍을 도출할 수 없다. SN200 예시와 합쳐 쌍을 세지 않는다. |
| **Native SN200 calibration** | `followup_gate.md` “Final parent verification”: SN DiagMLP 조건부 Top-1 평균 **95.38% [92.31, 98.46]**, gated Top-1 **94.36% [89.23, 98.46]**. **65개 상관된 검증 고장 창/run**, 6/6 run 검증 통과. | 같은 프로토콜의 오류 상세는 위 `sn200_error_windows.json` 예시이며, 아래의 창-seed 집계가 이를 재정리한 것이다. | 세 seed 또는 65개 창을 독립 장애 수로 해석하지 않는다. 검증 점수는 paper 재현이나 원인 메커니즘의 증거가 아니다. |
| **SN corrected 사건 외부평가** | `sn_corrected_20261017/REPORT.md` “정량 결과” 및 `ANALYSIS.json`의 `scope.events`, `seed_oof`, `overall`: **36개 사건**, 각 모델·seed당 36개 사건; DiagMLP 사건 Top-1 seed 평균 **25.00%**. | `ANALYSIS.md` “36개 짝지은 사건·오류 기록”에는 사건별 root와 seed별 후보 순위가 있으나, 이 보고서에서는 그 별도 평가의 후보 쌍을 SN200 calibration 집계에 합산하지 않았다. `WINDOW_RESCORE.md`의 창 점수는 고정 예측의 다른 채점 단위다. | calibration의 65개 창과 corrected 평가의 36개 사건은 서로 다른 평가 조건/분모다. 점수나 후보를 섞어 하나의 오류 빈도로 만들지 않는다. corrected 방법은 복원본이며 논문 저자 코드/수치의 정확 재현이 아니다. |

### SN200 DiagMLP의 기록된 오답 쌍

아래는 `root_unique_first=false`인 기록만 집계한 것이다. “이벤트 수”는 `event_id`의 고유 개수이며, seed 수를 독립 표본으로 세지 않는다.

| 실제 root → 잘못된 1위 후보 | 오답 창-seed 수 | 창 수 | 이벤트 수 | seed |
|---|---:|---:|---:|---|
| media-service → text-service | 2 | 2 | 1 | 11, 37 |
| media-service → url-shorten-service | 1 | 1 | 1 | 11 |
| media-service → unique-id-service | 1 | 1 | 1 | 11 |
| media-service → post-storage-service | 1 | 1 | 1 | 11 |
| url-shorten-service → post-storage-service | 1 | 1 | 1 | 11 |
| nginx-web-server → unique-id-service | 1 | 1 | 1 | 23 |
| post-storage-service → home-timeline-service | 1 | 1 | 1 | 37 |
| unique-id-service → compose-post-service | 1 | 1 | 1 | 37 |
| **합계** | **9** | **8** | **6** | — |

`media-service → text-service` 두 기록은 같은 이벤트 `SN.2022-04-17T181245D2022-04-17T183616:fault08`의 window index 129(seed 37)와 133(seed 11)이다. 한 이벤트 안에서도 seed가 바뀌어 나타났지만, window 129의 seed 11은 다른 후보(`url-shorten-service`)를 골랐다. 따라서 쌍의 seed 안정성은 부분적이며, 서로 다른 이벤트에서의 반복은 관측되지 않았다. 이 결론은 이 JSON의 기록 범위 안에서만 성립한다.

## 기록 완전성 및 분모 대조

- `native_error_windows.py`의 `audit()`는 각 검증 예측 행을 순회하면서 root가 고유 1위가 아니거나(`not unique_correct`) 탐지가 실패한 경우 `examples.setdefault(index, ...)`에 기록하고, 해당 행의 `seed` 정보를 추가한다. 모든 행을 순회한 뒤 `list(examples.values())`를 저장한다. **예시 개수 상한이나 top-k 절단이 없다.** 따라서 이 생성 코드 기준으로 `error_examples`는 샘플링된 예시가 아니라 이 기준에 해당하는 전체 창 목록이다.
- 같은 함수는 `wrong_seeds`에 원인 선택 오답만 넣고 `distinct_root_error_windows` 및 `root_error_windows_in_all_three_seeds`를 만든다. 원인 오답 분모는 JSON의 `fault_window_seed_evaluations_by_band` 합 195, 오답 수는 `non_unique_correct_root_evaluations_by_band` 합 9이다. 9개 오답이 8개 창에 있고 어떤 창도 세 seed 모두 오답은 아니라는 필드와 일치한다.
- `error_examples`에는 탐지 실패만 포함된 창도 들어갈 수 있다. 예를 들어 root는 맞혔지만 `detected=false`인 기록은 원인 선택 오답 집계에서 제외했다. 혼동쌍 표는 반드시 `root_unique_first=false`인 seed 기록만 센다.
- `sn200_error_note.md`의 “원인 선택 오답은 합계9회, 서로 다른 시간 구간으로는8개” 및 고장 종류 5/3/1 요약과도 합계가 맞는다. 창과 seed는 상관되어 있으므로 195를 독립 사건 수로 부르지 않는다.

## 해석의 경계와 다음 진단 하나

관측된 것은 저장 검증 예측에서 어떤 후보가 root보다 높은 점수를 받은 사실뿐이다. 왜 그랬는지는 알 수 없다. `sn200_error_windows.json`의 `limitations`는 seed·창의 상관, 주석 겹침과 실제 증상 가시성의 차이, 경계 동반과 원인의 비동일성을 명시한다. `sn200_error_note.md`도 오류가 입력 또는 구조에서 비롯됐다고 확정하지 않는다. SN200은 200 epoch calibration이고, SN corrected는 별도 사건 분할·평가이며, `REPORT.md`는 학습/선택 상태와 관측 결측의 가능한 교란을 기록한다. 이 차이들은 원인에 대한 인과 주장을 막으며, 효율 비교로 대체하지 않는다. 이들 요약만으로 특정 메커니즘을 선택하지 않는다.

**이 집계로 이미 답한 것:** SN200의 현재 조건부 창 Top1 오답 목록은 상한 없는 전체 목록이다. 따라서 이 목록에서 `media-service → text-service`가 다른 이벤트에서도 나타나는지는 이미 확인했고, 한 이벤트에서만 관측됐다. 이를 알아보려고 예측 배열을 다시 열 필요는 없다. 사건별 확률 평균으로 순위를 새로 만들면 다른 평가 지표가 되므로 현재 질문의 후속으로 제안하지 않는다.

**다음 질문(하나, 미실행):** “같은 media-service 장애 사건 안에서, 해당 seed가 media-service를 맞힌 창과 text-service로 틀린 창은 모델 입력과 두 후보의 점수에서 무엇이 다른가?” 한 사건의 탐색적 오류 원인 점검으로 한정하며 사건 간 일반화나 원인 증명으로 부르지 않는다. 이 질문은 현재 오류 요약만으로 답할 수 없다. 허용 개발 범위의 저장 입력·예측 점수를 대조하는 후속 접근은 별도 승인 후에만 수행하며, 새 학습·보호 시험·새 분할은 요구하지 않는다. 현 단계에서 특정 모델 변경은 선정하지 않는다. 서로 다른 사건에서 같은 쌍이 반복되지 않았다는 사실이 이 한 사건의 분석 가치까지 부정하는 것은 아니다.

보호된 SN169+1 및 TT1744+1 관측은 이 분석에서 열거나 변경하지 않았다. TT cohort 결과도 SN 오류 쌍의 분모나 근거로 사용하지 않았다. 원논문 수치와 복원 실험 결과를 동일시하지 않는다.
