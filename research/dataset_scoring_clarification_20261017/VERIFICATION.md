# 독립 확인 기록

기준일: 2026-10-17. 범위는 후속 평가 준비의 세 handoff 확인이다. 새 모델 평가·학습·추론, 다운로드, 원시 telemetry/archive 접근, split 변경, 보호된 native/RCAEval 최종 자료 열람은 하지 않았다. 변경·생성한 파일은 이 디렉터리의 `REPORT.md`와 `VERIFICATION.md`뿐이다.

## 판정 요약

세 인계 문서를 확인했다: [SCORING.md](SCORING.md), [INVENTORY.md](INVENTORY.md), [LABEL_SEMANTICS.md](LABEL_SEMANTICS.md). 요청 본문에 적힌 `ReadSCORING.md`라는 파일명은 존재하지 않고, 대소문자 그대로의 `SCORING.md` 인계가 존재하므로 해당 인계를 확인했다. 인계 누락을 임의로 채우지 않았다.

| 확인 항목 | 결과 | 실제 확인 |
|---|---|---|
| 저장된 RCAB 점수 | 통과 | 원시 `scores`와 정답 계약만 사용해 173사례×4기준×2계약=1,384개 credit을 Fraction으로 재계산. 저장 사례별 Top1과 최대 절대 오차 `5.551115123125783e-17`. |
| 집계 행 | 통과 | 8개 기준×계약 행의 N, 정확 credit 합, 평균(credit 합/173), 0/부분/1 수, 최상위 동점 사례 수, 후보 결측 수 일치. |
| 부분 credit·span 산술 | 통과 | HTTP 예시 1/28, 1/27 확인. span 명목 표적 98, 허용 집합 99; 각각 98/173, 99/173. |
| RCAEval 구성 | 통과 | 저장 `rcaeval_trial.json`의 suite 집계 90/90/30/30=240, 기존 로컬 감사 180, 감사되지 않은 RE3 60을 대조. |
| ops-lite 중복 범위 | 통과 | 기존 저장 결과의 197 metadata 사례 일치와 80 hash 그룹을 확인. 80은 8 ops 사례/8 RCAB 사례에 연결된 비어 있지 않은 관측 hash 결과. |
| 정답 의미 경계 | 통과 | 고정 생성 코드 의미와 현재 ops-lite 설명을 구분하고, 아카이브 생성 revision 및 정확한 release lineage가 입증되지 않은 주장을 미확인으로 유지. |

## 점수 재계산 방식과 수치

resident Python kernel에서 표준 라이브러리 `json`, `fractions.Fraction`, `hashlib`로 `/home/gnho1236/r2/research/dataset_suitability_20261016/rcab_trial.json`을 직접 읽었다. `scoring_check.py`를 import하거나 그 scorer를 호출하지 않았다. 각 기준·사례에서 지원되고 점수가 있는 후보만 순위화하고 최고 점수 후보 전체를 T로 삼았다. 그 뒤 `g/|T|`를 직접 계산했다. 지원 점수가 하나도 없는 경우만 전체 후보가 tier가 되도록 처리했다. 정답 계약은 `nominal_anchor`와 `original_accepted_roots`를 각각 적용했다.

- 직접 계산된 평가 행: 8.
- 저장된 사례별 Top1과 비교한 credit: 1,384.
- 사례별 최대 float 차이: `5.551115123125783e-17`.
- 독립 합계/평균·사례 count와 `scoring_check.json` 8행 일치: 예.
- HTTP 부분 credit 예: `ts0-ts-ui-dashboard-request-delay-wcm5qd` = `1/28`; `ts0-ts-ui-dashboard-response-delay-zd6lz6` = `1/27`.
- span 점수 합: 명목 표적 `98/1`, 원래 허용 정답 `99/1`; 분모 173을 적용한 비율은 각각 약 56.6474%, 57.2254%.
- 기준 우열: 명목 표적 계약에서 span 0.566474 > 장애 HTTP 오류 비율 0.480987; 원래 허용 정답 계약에서 장애 HTTP 오류 비율 0.609373 > span 0.572254.

credit 0/부분/1의 부분 credit count는 사례의 credit이 엄격히 0과 1 사이인 수로 계산했다. 최상위 동점 사례 count는 `|T|>1`인 수로 별도 계산했다. 따라서 장애 HTTP 오류 비율의 원래 허용 정답 계약에서 부분 credit 6건, 최상위 동점 8건은 서로 다른 통계이며 모순이 아니다. 분모는 후보별 미지원 점수가 있어도 항상 173이다.

## 입력 무결성 및 기존 실행 증거

저장 점수 입력의 SHA-256은 보존된 기록과 현재 파일 모두 다음과 같다.

```text
research/dataset_suitability_20261016/rcab_trial.json
98eccf62060e398c691242aca1f532c444646f93bc9c239d7a3c4ac0e7d64b00
```

현재 `scoring_check.json` SHA-256:

```text
5db5d16b8e7389ef61eb17aa0e8a9e58c4deaea571578f8887a21b35cb3c9196
```

새 계산 중 점수 입력 파일을 쓰지 않았다. `SCORING.md`에는 기존 scoring check 명령의 실제 `exit 0`, stdout `SCORING_CHECK_PASS`, 빈 stderr, 입력 hash 전후 동일 기록이 있다. 같은 문서에는 173사례 대조 및 작은 동점·복수 정답·전체 결측·음수 지원 점수 대 결측·정답 부재·후보 순열 자체검사 통과가 기록돼 있다. 이 실행을 이번에 다시 실행하지 않았으며, 기존 기록에 적힌 범위 이상으로 실행 증거를 주장하지 않는다.

이 독립 확인은 resident kernel의 실제 계산 결과다. 별도 새 shell script를 만들거나 그 exit code를 주장하지 않았다. 원래 `33 tests passed`는 기존 구현·계산 검사에 대한 기록이며, 과학적 정답 의미 또는 DiagMLP 능력 검증으로 취급하지 않았다.

## RCAEval·ops-lite·출처 경계

RCAEval 숫자는 저장된 `rcaeval_trial.json`의 suite count와 local acquisition 필드를 대조했다. 추가로 inventory handoff의 기존 assertion proof가 인덱스·원격 목록·다운로드 원장·RE2 readiness 감사의 정합성만을 대상으로 하고 파일 내용/RE3 관측 품질을 확인하지 않았다고 명시한 점을 반영했다. 240은 메타데이터 범위, 180/60은 기존 감사시점의 확보/미감사 구분이다.

ops-lite 값은 기존 `ops_trial.json` 및 [OPS.md](../dataset_suitability_20261016/OPS.md)의 보존된 결과다. 여기서 telemetry를 열어 재검증하지 않았다. 197은 metadata 일치 수, 80은 비어 있지 않은 hash 그룹이며, 후자는 8개 사례의 바이트 동일성 증거다.

라벨 의미 근거 및 provenance 경계는 [LABEL_SEMANTICS.md](LABEL_SEMANTICS.md)에 인용된 고정 `chaos-experiment` commit `55f9ad16818e89aeed984594434e8fbc66c5d430`, 고정 `rcabench-platform` commit `5a463bd2bfaecda1b26aed9fe3f018859196bb0e`, 현재 고정되지 않은 ops-lite README `main` 설명에 따른다. 고정 upstream 코드 revision이 실제 보유 RCAB 아카이브 생성 revision이었다는 점은 미확인이다. 현재 `main` 설명과 과거 RCAB/ops-lite 라벨 간 release lineage도 미확인이다. 이에 따라 의미의 동등성 주장은 하지 않았다.

## 최종 확인 경계

결과 수치와 보고 문구는 세 handoff의 범위를 넘지 않는다. 최신 SN 결과는 완료 상태로 표현하고, TT/RE2 중단 작업은 중단 상태로 유지했다. raw archive/telemetry, checkpoint, 보호된 최종 자료는 열지 않았다. 기존 산출물이나 이전 보고서를 편집하지 않았다.

