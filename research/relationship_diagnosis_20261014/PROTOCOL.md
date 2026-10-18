# 기존 교차검증의 오류 진단과 문헌 비교군 선정

## 목표와 범위

사용자가 기존 실험의 실패 사례·관측 조건 진단을 진행하고, 실제 선행연구 모델도
비교해야 하는지 확인해 달라고 요청했다. 새 학습 없이 저장된 결과를 분석한다.
내부 Local/Global 대조군은 문헌 경쟁자를 대신하지 않는다.

주 입력은 `../relationship_cv_20261014/results/`의 runs.json, analysis.json,
54개 predictions.npz와 여섯 statistics.npz,
`../relationship_smoke_20261013/artifacts/{SN,TT}.{json,npz}`다.
관측 bundle에서는 필요한 허용 개발 행의 adjacency/observed와 행 메타데이터만 읽는다.
Native test/unassigned, RCAEval, RCABench 관측과 원 수집 스트림은 읽지 않는다.
기존 source/results, 모델 checkpoint는 변경하거나 다시 학습하지 않는다.

## 진단 계약

### 사건·오답 분석

- 주 비교는 Directed−Global, Local은 보조 기준이다.
- 각 window·seed의 최댓값 동점 서비스 전체에 1/k credit을 배분한다.
  잘못 선택된 서비스의 확률 질량 합은 1−root Top1 credit과 같아야 한다.
  argmax의 첫 서비스로 동점을 임의 처리하지 않는다.
- 먼저 사건 안의 창과 세 seed를 평균하고 사건을 동일 비중으로 집계한다.
  사건 승/동/패는 사건 평균 Top1 차이로 판단한다.
  “모두 실패”는 두 사건 평균이 정확히0일 때만, “모두 완전 정답”은 모두1일 때만 사용한다.
  부분 정답·동점 사건을 이진적인 해결/실패로 바꾸지 않는다.
- 모든 사건의 서비스·장애 유형·recording·fold·모드별 지표와 관측량을 보존한다.
- 오답 서비스와 root의 **관측 관계**를 direct root→wrong, wrong→root,
  양방향 direct, direct가 아닌 weakly-connected, 관측 연결 없음으로 구분한다.
  self/root는 오답에서 제외한다. 방향이나 연결을 이상 전파의 인과 증거로 부르지 않는다.
- 전체 오답 관계 질량은 사건 균등 평균으로 보고하고, 오답 조건부 비율의 분모도 명시한다.

### 관측과 실패 조건

- “어떤 서비스 간 edge라도 있음”과 **root에 인접한 edge/사용 가능한 이웃 문맥**을 구분한다.
- adjacency[row,caller,callee]이며 graph는 같은10초 창 내 관측 CHILD_OF만 포함한다.
- 각 fold의 저장된 statistics.npz `reference_mask`와 원 observed를 이용해
  서비스 visibility를 복원한다. fold0의 feature mask를 다른 fold에 재사용하지 않는다.
- root의 incoming/outgoing 이웃 가운데 visible한 이웃의 존재를 separately 기록한다.
  이웃을 거르지만 root 자신의 visibility를 추가 조건으로 만들지 않는다:
  실제 RelationRanker의 이웃 pooling과 일치시킨다.
- root raw9채널 관측 비율, trace latency 관측, 정상 참조 가용성과 feature visibility를 구분한다.
  7개 메트릭이 항상 observed인 자료 계약을 실제 수집기 완전성으로 해석하지 않는다.
- root 문맥 존재/부재별 사건 내 창 집계와 각 subgroup의 사건 수·창 수를 함께 보고한다.
  같은 사건이 여러 subgroup에 등장할 수 있음을 표시하고 전체 사건 수로 합산하지 않는다.
- 장애 유형별 및 recording별 차이는 사후 기술적 분석이다. 인과나 새 검증자료로 주장하지 않는다.
- 모델/특징/epoch/seed 선택에는 이번 결과를 사용하지 않고 보고 후 종료한다.

### Recording 분리 가능성

자료별 recording과 원인 서비스·고장 유형의 대응표를 만든다.
Leave-one-recording-out을 가정했을 때 남는 TRAIN 사건·root·고장 유형 지원,
정상 TRAIN 창과 보호 행 제외를 메타데이터로 점검한다. 실제 재학습은 하지 않는다.
한 recording에서만 root 정답으로 나오는 서비스는 holdout 시 **cold-root 조건**이 되므로,
recording 분리 실험이 환경 변화만을 분리하는 검증인 것처럼 제안하지 않는다.
Validation 서비스가 TRAIN에서 root 정답이 아니어도 정상/관측 입력에는 존재할 수 있다.

## 문헌 비교군 계약

DiagMLP, BARO, Eadro를 우선 검토하고 필요하면 직접 관련 후보를 소수만 보완한다.
과제, 요구 입력, 전처리 포함 비용, 모델·학습 자료 규모, 구현 재현성의 다섯 기준으로 정리한다.
기존 조사 `../resource_study_20261013/METHODS.md`와 fidelity 기록을 활용하고,
확인 가능한 논문/공식 코드의 원출처를 대조한다.

“공식 원형”, “수정 fork 복원”, “논문식 복원”, “공통 입력 adapted 모델”을 구분한다.
BARO의 지표→서비스 집계, onset 제공 여부, Eadro의 로그·정적 관계와 탐지 gating,
DiagMLP의 고유 encoder/위치 표현 등 비교 조건을 명시한다.
강한 기준법을 작게 줄여 약화시키거나 현재18개 특징으로 바꾼 것을 원형이라고 부르지 않는다.
문헌에 보고된 수치나 과거 창 분할 결과를 이번 사건 분할 성능표에 섞지 않는다.
공통 정보 조건 비교와 방법별 고유 입력을 보존한 전체 파이프라인 비교는 별도다.
이번에는 문헌 모델 설치·다운로드·학습을 실행하지 않는다.

## DAG와 검증

이번 phase는 세 독립 구성요소를 병렬 실행한 뒤 증거 확인으로 합류한다.

| 노드 | 산출물/쓰기 범위 | 경로 선택 이유 |
|---|---|---|
| errors | errors.py, test_errors.py, errors.json, ERRORS.md | 동점 질량·관계·fold mask를 연결하는 분석이므로 deep-low |
| recordings | recordings.py, test_recordings.py, recordings.json, RECORDINGS.md | 기존 메타데이터 패턴을 따르는 제한된 집계이므로 quick |
| literature | COMPARATORS.md | 입력/원형 충실도 간 비교 판단이 필요하므로 unspecified-low |
| verify | VERIFY.md | 세 산출물의 근거·합계·계약을 연결 검증하므로 unspecified-low |

첫 wave 폭3, 검증 wave 폭1. 병렬 쓰기 경로는 겹치지 않는다.
verify는 세 producer 모두에 의존한다. 주 에이전트는 검증된 결과를 REPORT.md로 종합한다.

RESULT VERIFICATION: 완료 알림만 믿지 않는다. 실제 집중 테스트/명시적 Pyright exit0,
실제 분석 스크립트 exit0, 입력·예측 hash, 기존 사건별 Top1 및 승/동/패 재현,
오답 질량 보존, root/오답 관계의 방향 synthetic fixture,
recording holdout의 root 지원 검사를 확인한다.
보고서의 숫자는 JSON에 대조하고 문헌 주장은 원출처와 복원 한계에 연결한다.
부분 실패는 해당 노드만 수정하고 불리한 결과를 삭제·약화하지 않는다.
생성 JSON은 덮어쓰지 않으며 실패 산출물은 성공으로 표시하지 않는다.
