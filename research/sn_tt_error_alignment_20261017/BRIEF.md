# Goal — TT 유지·SN 반복 오류: 기존 증거 기반 분석

최신 사용자 요청은 효율 연구에서 진단 성능 연구로 명시적 방향 전환이다.
공통 모델 구조·학습 원칙을 시스템별로 따로 적용해 TT 강점을 유지하면서
다른 데이터에서 반복 오류 하나를 개선하는 것이 목표다.
이번 권한은 mass-ulw를 이용한 조건 대조·기존 오류 근거 점검·검증안 작성이다.
새 학습/재추론/전처리, 원자료·보호 관측·모델·예측 배열 접근은 하지 않는다.
효율 DAG의 미수정 FAIL과 옛 RE2/TT 실행은 재개하지 않는다.
기존 goal 도구는 user-interrupted 상태의 미완료 옛 실험으로 묶여 있어 새 등록이
거부된 기록이 있다. 이를 허위 완료 처리하지 않는다. 이 Goal과 최신 지시가
이번 단일 분석 단계의 범위다.

## 확인할 것

1. TT/SN 각 실험의 입력·정규화·어휘 참조·split·학습량·selection·score를 대조.
   native calibration SN50/SN200/TT50, 최근 TT, 별도 SN corrected를 섞지 않는다.
   이미 확인한 followup_gate의 SN200 conditional95.38%와 TT50 98.64%,
   SN corrected window23.59%를 다른 조건으로 명시한다.
2. 기존 SN 요약/분석 JSON·Markdown에서 root→잘못고른후보 반복 근거를 찾는다.
   saved prediction 배열을 열거나 추론하지 않는다. 기록에 후보명이 없으면
   오류율만으로 혼동쌍을 발명하지 않고 필요한 최소 후속 분석을 명시한다.
   seed를 독립사건으로 세지 않고 창/사건/recording 반복을 구분한다.
3. 낮은 점수 조건을 골라 문제를 만들어내지 않는다. 조건 차이 때문에 인과
   설명이 불가능하면 명시한다. 전파·결측·그래프 부재를 원인으로 선결정하지 않는다.
4. 확인된 문제 하나에 대응하는 변경 하나의 조건부 검증안을 만들되,
   근거가 없으면 변경 설계 대신 오류 확인을 위한 한 단계만 제안한다.
5. TT 유지 기준은 같은 평가 원칙·시스템별 독립학습에 둔다. 손실 허용폭은
   합의 전 미정. 추가 데이터 선정/가공/다운로드·일반화 과제 확장은 하지 않는다.
6. DiagMLP 논문 TT/SN은 Eadro, GAIA는 TVDiag 기반임을 구분한다.
   저자 수치·로컬 복원 수치·실험 조건을 분리하며 GAIA를 자동 채택하지 않는다.

## DAG

조건대조 quick → CONDITIONS.md
SN오류 unspecified-low(여러 조건의 근거를 묶어 반복성 판단) → SN_ERRORS.md
TT유지 quick → RETENTION.md
세 결과 → 통합 unspecified-low(어떤 문제를 주장할 수 있는지 판단) → REPORT.md
통합 → 독립검증 quick → VERIFY.md
최대 병렬3,5노드. 파일 쓰기 소유 범위는 독점적이다.
부모는 완료 알림 뒤 VERIFY와 보고서를 대조한다. FAIL은 해당 노드만 수정한다.

## 경계와 검증

허용: 기존 연구 .md/.py 및 명시적인 summary/analysis/verification .json을
read로 조사, 필요시 요약 수치의 가벼운 산술. 원자료·NPZ·checkpoint·saved
prediction array는 금지. 기존 연구 코드를 import/run하지 않는다.
쓰기: 이 디렉터리의 지정 Markdown만 apply_patch로 작성.
추가 에이전트·새 goal·다운로드·설치·commit 금지.
비교 가능한 조건인지 명시, 수치는 원문 file:section/JSONfield 출처를 기록.
문헌 확인은 지정 DiagMLP/Eadro만, 불필요한 문헌 확대 금지.
성공 조건: 6요구사항 모두 추적, 반복 오류 주장 또는 명확한 증거 부족 판정,
하나의 후속 검증안, 독립 VERIFY PASS 및 부모 확인. 실험 성공으로 부르지 않는다.

## 실행 식별자

run_id: `dag_9afce00a-9d92-40b4-8e57-194de158aab9`
key: `sn-tt-error-alignment-20261017-v1`
5노드 시작, 정의 warnings0. 종료 알림 뒤 기존 run 산출물을 확인한다.
학습 권한은 부여되지 않았으며 결과에서 부족함이 발견돼도 자동 재학습하지 않는다.
