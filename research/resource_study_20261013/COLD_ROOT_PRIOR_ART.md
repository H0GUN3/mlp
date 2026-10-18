# 원인 미학습 대상 진단: DéjàVu와의 중복 검토

## 결론

`연구문제_재검토.md`에서 제안한 원인 미학습 서비스 조건은 실용성 평가에 의미가 있지만,
**그 조건이나 공유 점수기 자체를 신규 기여라고 할 수 없다.**
DéjàVu(FSE2022)가 과거에 고장 원인이었던 적 없는 대상의 진단을 명시적으로 다룬다.
다만 failure unit과 서비스는 정답 단위가 다르므로 모든 세부 조건이 같다는 판정도 피한다.

이번에는 논문과 공식 README만 확인했다. 코드 설치·실행·관측자료 다운로드는 하지 않았다.
다른 연구 전체를 망라한 신규성 조사나 DéjàVu 재현 완료가 아니다.

## 원문에서 확인한 사실

논문: *Actionable and Interpretable Fault Localization for Recurring Failures
in Online Service Systems*, 공개 v3, DOI10.1145/3540250.3549092.

| 항목 | 원문 확인 |
|---|---|
| 과제 | 장애가 발생했을 때 최신 FDG와 메트릭으로 고장 failure unit을 순위화 |
| 정답 단위 | 컴포넌트와 해당 고장을 나타내는 지표군의 조합. 서비스만의 정답보다 세밀하며 DB·container·OS도 포함 |
| 목표의 중복 | §1은 unseen failures를 “no failures of the same kinds have occurred at the same locations”로 설명 |
| 학습 정보 | 과거 장애와 정답 failure units, 메트릭, 실패 의존성 그래프(FDG) |
| 공유 구조 | 같은 failure class의 feature extractor 공유, 전체 unit의 aggregator와 classifier 공유 |
| 구체적 기제 | GRU→1D CNN→dense 표현, 다층·다중 head GAT 집계, 공유2층 dense 의심 점수기 |
| 그래프 준비 | trace의 호출 관계 및 배포/구성 관계에서 FDG 생성, 지표군·failure class의 사전 정의 필요 |
| 평가 자료 | A188+B158+C99+D156=601건. 3개 운영 시스템과 TrainTicket, 실제 운영 장애99건. 일부16건은 복수 원인 |
| 기본 분할 | 각 자료 train40%/validation20%/test40% |
| 지표 | A@k 및 mean average rank(MAR), 학습·진단 시간. MAR은 MRR이 아님 |
| 일반화 평가 | §5.5/Figure15에서 과거 faulty 이력이 있는/없는 정답 unit의 추천 순위를 비교. 그림은A/B 자료 |
| 비용 근거 | 원문은 학습 수십 분·진단1초 미만을 보고하나 우리 호스트의 전체 비용은 미측정. 설정의3000epochs를 실측비용으로 대체하지 않음 |

§3.1의 핵심:

> “the failure units in the same failure class share a feature extractor,
> and all failure units share a feature aggregator and classifier”

§5.5의 seen/unseen 구분:

> “previously seen (the ground truths are faulty in some historical failures)
> and unseen failures”

유사 장애 검색 후 과거 정답을 복사하는 방법과 달리, 현재 unit의 메트릭과 상대적
그래프 구조를 이용해 과거에 정답이 아니었던 unit도 추천하려는 설계다.
같은 절은 공유 decision tree나 비학습 heuristic도 일반화할 수 있다고 논의한다.
즉, **지도학습=과거 정답만 출력**이라는 일반화도, **공유 점수기=우리만의 새로운 해결책**이라는
일반화도 피해야 한다.

## 우리 조건과 같은 점·다른 점

| 비교 | 판단 |
|---|---|
| 같은 유형의 문제가 다른 위치에서 처음 원인으로 나타남 | 직접 겹치는 동기 |
| 위치별 독립 분류보다 공유 표현·점수로 전이 | 이미 제시된 설계 원리 |
| 특정 failure unit의 positive 라벨이 없었음 | DéjàVu가 실제로 분리 보고한 조건 |
| 한 서비스의 모든 고장 유형을 TRAIN 원인 라벨에서 제외 | 이번 읽기에서 동일한 강제 holdout 절차는 확인하지 못함. unit holdout과 같다고 단정하지 않음 |
| 완전히 새로운 고장 종류 | recurring failure와 별도 문제. 사전 정의된 failure class를 넘어선 무조건 일반화 근거 아님 |
| 새로 배포된 서비스/전체 시스템 전이 | 동적 FDG와 unit 추가를 설계에서 설명하지만 이와 별개의 전용 평가를 확인하지 못함 |
| 우리 상대 MLP | 메트릭7+trace2 요약, 그래프·위치 embedding 없이 공유 scorer. 더 적은 구조 정보를 쓰는 차이는 있으나 성능·비용 이점 미입증 |

DéjàVu의failure unit 수준 결과를 그대로 서비스 Top-1과 비교할 수 없다.
실제 비교 후보로 채택할 경우 정답 변환, 지표군·FDG 생성에 제공하는 정보,
관측 길이(원문은20분 window)와 입력 비용을 사전에 정해야 한다.
원형의 그래프나 feature extractor를 제거한 뒤 같은 방법이라고 부르지 않는다.

## 연구 방향에 주는 영향

1. cold-root를“새 문제 발견”이 아니라 **미학습 위치에 대한 실용성 검증 조건**으로 둔다.
2. 이 조건을 연구의 중심으로 삼으면 DiagMLP뿐 아니라 DéjàVu 같은 직접 관련 접근을 검토해야 한다.
3. “그래프 없이도 가능”은 BARO·PRISM·DiagMLP가 이미 다루므로 그 문장만으로도 차별성이 부족하다.
4. 차별적 기여가 있다면 실제 운영 제약 아래 필요한 정보/라벨/준비 비용을 줄이면서
   진단 품질을 유지하는 구체적 기제와 증거가 필요하다. 이는 가능성이지 현재 확보한 결과가 아니다.
5. 현재 상대 MLP를 유지하려고 평가 조건을 사후에 고르지 않는다.
   단순 통계 방법으로 충분하거나 직접 경쟁자 대비 이점이 없으면 기준선으로 남길 수 있다.

이번 확인으로 기존의“현재 신규성 미확인”판정은 더 중요해졌다.
새 모델 실험보다 **선행연구 대비 정확한 차이와 필요한 정보의 정당성 확인**이 우선이다.

## 출처·접근 기록

- 논문 초록/서지: https://arxiv.org/abs/2207.09021
- 공개v3 본문: https://arxiv.org/html/2207.09021v3
- 공유 구조 §3.1: https://arxiv.org/html/2207.09021v3#S3.SS1
- 실험 설정 §5.1: https://arxiv.org/html/2207.09021v3#S5.SS1
- 일반화 §5.5: https://arxiv.org/html/2207.09021v3#S5.SS5
- 공식 코드: https://github.com/NetManAIOps/DejaVu
- 확인 당시master: `d1f082b086cef5597f5301a7b02882b5d0238ebe`
- README: https://github.com/NetManAIOps/DejaVu/blob/d1f082b086cef5597f5301a7b02882b5d0238ebe/README.md

처음 시도한main/README는404였고 공식 repo API가 기본 branch=master임을 확인한 뒤
master README를 읽었다. 공개 코드/자료 링크는 존재하지만 로컬 실행 가능성은 검증하지 않았다.
본문 도구 출력이 중간에 잘려, 전체 HTML387,358B를 받아 §5.5를 끝까지 추가 확인했다.
