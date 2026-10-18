# REPORT.md 대조 확인

## 주 담당 최종 문구 점검

원래 수치 검증 후, 보고서에서 미확인을 반증처럼 표현한 부분과
새 진단 순위를 계산하고도 “예측 없음”이라고 쓴 부분을 정정했다.
같은 순위를 두 정답 계약으로 평가한다는 의미와 Top1 credit이 정확히0인
83사례의 정의도 명확히 했다. RCABench의 조건부 주 데이터 역할을 유지하고,
추가 수집이 모든 활용에 필수인 것처럼 읽히는 권고는 제한했다.

실제 resident-kernel 대조 결과:

- 수치 결과 표 **18행은 정정 전후 동일**.
- 정답 계약·동점 점수·미확인과 반증의 구분·권고 범위에 대한 문구 검사 **6/6 PASS**.
- 분석 코드·입력·결과 JSON은 변경하지 않았으므로 기존 실험·테스트 근거를 재사용했다.
- 최종 `REPORT.md` SHA256:
  `1faabfb2ab23903298facebfaf5fb80e6248646dec2585e384b434a3da68cfea`.

아래 원래13개 수치·링크·요구사항 검증과 함께 최종 문서의 근거로 사용한다.

**판정: PASS (범위 한정).** 보고서의 주요 수치·단위·해석을 저장된 네 결과 JSON과 `rcab_selection.json`에 대조했다. 아래 assertion은 workstation resident kernel의 Python 표준 `json` 파서로 전체 파일을 읽어 계산했다. producer/test를 재실행하지 않았다.

## 실제 assertion 결과

**13/13 PASS**

| 검사 | 결과 |
|---|---|
| 네 결과 JSON 완전 파싱 | PASS |
| 선택목록 및 pilot 사례 수 173 | PASS |
| 사례당 후보 49, 총 8,477 후보-사례 쌍 | PASS |
| 세 비균등 점수의 결측 수 3,637 / 3,647 / 3,635, 균등 기준 0 | PASS |
| REPORT.md의 상대 링크 11개 모두 존재 | PASS |
| VERIFY.md 최신 판정 “All requested verification gates pass within their declared scope” | PASS |
| RCAB 전체 1,422건, 비network 총 1,168건 중 명목 후보 1,167건 구분 | PASS |
| RCAEval 관련 240건, RE3 60건 미감사, Sock Shop 제외 언급 | PASS |
| Eadro SN/TT 사건·recording·root·유형 수 및 adequacy 한계 | PASS |
| ops-lite 전수 metadata 455건과 균형 표본 30건 및 미확인 425건 구분 | PASS |
| 관측/metadata 범위, 인과·독립성·모델 성능 과장 금지 | PASS |
| RCAB 값의 span-row 단위, 결측 보존, 정답 계약과 입력 역할 구분 | PASS |
| 보고서의 RCAB Top1 대표값이 JSON 요약과 일치 | PASS |

## 수치·단위 대조

RCAB JSON의 사례균등 평균과 REPORT 표는 6자리 반올림까지 일치한다. 순서는 Top1 / Top3 / ERR(기대 reciprocal first-accepted rank)이다.

| 기준 | 명목 표적 | 원래 허용 정답 집합 |
|---|---|---|
| 균등 | 0.020408 / 0.061224 / 0.091412 | 0.040816 / 0.119898 / 0.144967 |
| 장애 HTTP 오류 비율 | 0.480987 / 0.814256 / 0.656739 | 0.609373 / 0.842064 / 0.742138 |
| HTTP 오류 비율 증가 | 0.486767 / 0.814256 / 0.659630 | 0.615153 / 0.842064 / 0.745028 |
| 장애 span 오류 비율 | 0.566474 / 0.807362 / 0.699179 | 0.572254 / 0.816558 / 0.708507 |

JSON에서 직접 합산한 결측 점수는 기준별 0 / 3,637 / 3,647 / 3,635다. pilot 173건의 각 사례에는 후보 49개가 있고, `null` 결측은 0점으로 바뀌지 않는다. 보고서는 이 입력이 정답 표적만이 아니라 전체 관측 후보이며, 단위가 독립 요청/사건이 아닌 배포 span 행이라고 명시한다. 따라서 결측 후보를 정상 0으로 취급하거나 후보 순위를 정답에서 유도했다는 수치상 불일치는 확인되지 않았다.

RCAB 전체 분할의 1,422건은 metadata census다. 1,168 비network 사례에서 충돌 1건을 제외한 1,167은 **명목 검토 후보**로 구분돼 있고, 인과 원인 입증이나 승인된 학습집합이라고 하지 않는다. 173건 HTTP pilot도 전체 HTTP 796건 성능으로 확대하지 않는다.

RCAEval JSON은 전체 인덱스 735, 관련 OB/TT RE2/RE3 240(180/60), RE3 로컬 미감사 60을 뒷받침한다. 보고서는 trace 필수 현재 범위에서 Sock Shop 및 RE1을 제외하고, 그룹분할이 사건 독립성이나 관측 품질을 증명하지 않는다고 제한한다.

Eadro JSON은 SN 36 사건/4 fault recording/12 root/3 fault types, TT 81/9/27/3이다. 보고서는 기존 사건 분할의 recording 공유, recording holdout의 root 지원 손실, 유형 holdout의 정상 창 배정 문제를 다뤄 숫자만으로 부적합을 결론내리지 않는다. 추가 normal-only archive가 장애 정답 사례를 늘리지 않는다는 범위도 유지한다.

ops-lite JSON은 whole 455(시스템별 275/148/32)와 선택 표본 30(10/10/10)을 구분하며, 표본 밖 425건의 관측 품질을 미확인으로 둔다. 이는 대표성·독립성으로 확대되지 않는다.

## 정확한 불일치 / 남은 확인

- 숫자, 단위, 링크 또는 위 요청 범위에서 **확인된 불일치 없음**.
- 정확한 절대값의 모든 JSON metric, 모든 9개 fault-type 요약, 모든 split 통계까지 REPORT 전체에 걸쳐 기계적으로 전 항목 비교한 것은 아니다. 핵심 요약표·지정 경계·coverage를 확인했다.
- Eadro의 “full release” 자체의 파일 전수·보호 경계는 이번 요청에서 허용된 metadata/report/JSON 증거 밖에서 검증하지 않았다. 확인 가능한 것은 JSON이 가리키는 개발 묶음의 사건·recording 지원 및 보고서가 기술한 기존 감사 한계다. 따라서 full-release 전체 적합성 PASS를 뜻하지 않는다.
- REPORT.md와 함께 읽은 VERIFY.md의 최신 명시 판정은 PASS지만, 이 문서는 저장된 결과 대조이지 원자료 재검증이나 producer 완료 증거의 독립 재실행이 아니다.

**하지 않은 일:** producer/test 재실행, 학습, 다운로드·설치, 보호된 관측 데이터 열람, 보고서·원본·결과 JSON 수정. 이 파일만 추가했다.
