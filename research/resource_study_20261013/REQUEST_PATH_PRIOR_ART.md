# 요청 경로·지연 분해의 선행연구 대조

2026-10-13 후속 문헌 검토. 새 특징 생성·학습·실제 trace 재분석은 하지 않았다.
완료된 스모크의 코드·입력·결과를 바꾸지 않는다.

## 결론

**호출 방향에 따른 전파 추적과 요청별 critical-path 지연 분해는 이미 연구됐다.**
또한 다음 셋은 서로 다른 양이므로 같은 이름의 “자기 처리 시간”으로 합치면 안 된다.

1. 관측된 자식 구간으로 덮이지 않는 부모의 벽시계 잔여 시간.
2. 요청 critical path 위에서 특정 operation에 귀속되는 exclusive 시간.
3. 그 서비스가 실제 CPU에서 실행한 시간.

현재 directed 원형은 같은 창의 boolean 서비스 관계에서 이웃 표현을 평균한다.
**요청 실행 경로, critical path, blocking 시간, CPU 시간을 복원한 모델이 아니다.**
지연 분해를 새 특징으로 추가하는 것만으로 신규성이 성립하지도 않는다.

## 1. 확인한 선행 기제

### CRISP — critical-path 지연 귀속

Uber의 저자 설명은 요청의 span 관계·시작·종료 시각으로 실행 의존 DAG를 구성하고,
늦게 끝난 자식에서 역방향으로 critical path를 찾는 방법을 설명한다.
겹치는 모든 자식 duration을 합산하는 것이 아니다.
결과에는 operation별 critical-path inclusive/exclusive 시간과 여러 trace의 집계가 있다.

이것은 **어느 operation이 요청 지연에 기여하는지** 분석하는 도구다.
큰 기여를 보인 operation이 주입 장애의 원인 서비스라는 정답까지 자동으로 따라오지는 않는다.
정상 대비 변화, 서비스 단위 집계, 원인 순위화 등의 추가 계약이 필요하다.

저자 설명에는 다음 교정 정책도 명시돼 있다.

- clock skew로 순차 호출이 겹쳐 보이면 작은 겹침을 허용한다.
- 자식 시간이 부모 밖으로 나가면 잘라내고 후손에도 교정을 전파한다.
- 부모와 완전히 떨어진 자식과 그 후손은 제외한다.

이것은 저자의 처리 정책이지 원자료 시계가 정확해졌다는 증명은 아니다.
우리 자료에 적용한다면 원래 위반량과 교정·제외량을 따로 기록해야 한다.
저자 설명의 동기/비동기 호출 해석도 우리 수집기의 실제 계측 의미와 대조해야 한다.

### MicroHECL — 유형별 방향을 가진 이상 전파 추적

원문 §III–IV와 Table I을 확인했다.
최근 호출 관계에 edge별 RT(response time), EC(error count), QPS 이력을 결합한다.
처음 이상이 보고된 서비스에서 전파 방향의 반대 방향으로 후보 원인을 탐색하고,
연속 edge의 시계열 상관으로 무관한 경로를 가지치기한다.
후보는 초기 서비스의 business metric과 후보 quality metric의 상관으로 순위화한다.

- 성능·신뢰성 이상: 논문이 가정하는 전파 방향은 downstream→upstream.
- 트래픽 이상: upstream→downstream.
- RT 이상 탐지에는 12특징 OC-SVM, EC에는 5특징 Random Forest,
  QPS에는 통계 규칙을 사용한다.

따라서 “이상 유형에 따라 방향을 다르게 보자”, “전파된 이상을 따라 원인을 찾자”는
새로운 문제 정의가 아니다. 반면 MicroHECL은 span별 exclusive 시간을 분해하는 방법은 아니다.
논문의 탐지 모델이 우리 3,361파라미터 MLP와 동일 규모라고 판단할 근거도 없다.

## 2. 다섯 기준에 따른 위치

| 기준 | CRISP | MicroHECL |
|---|---|---|
| 과제 일치 | 요청 지연의 operation별 귀속. 단일 원인 서비스 순위와는 부분 일치 | 원인 서비스와 이상 유형 진단으로 가까움. 문제별 복수 이상 유형을 허용 |
| 입력 정보 | 요청별 span 관계·시간·service/operation 및 분석할 진입점 | 초기 이상 서비스·business metric·edge별 RT/EC/QPS와 긴 정상/과거 이력 |
| 전처리 포함 비용 | trace 수집·중복/시계 처리·경로 계산·요청 간 집계가 필요 | 호출 집계·TSDB 조회·탐지 모델 특징/학습·graph 탐색이 필요 |
| 모델/학습 자료 규모 | 읽은 원형은 학습 모델이 아닌 경로 분석 알고리즘. trace 수를 장애 사건 수로 세면 안 됨 | 저자는 RT 탐지 학습 100,000사례, EC 탐지 학습 1,000라벨 사례를 설명. root-cause 평가의 75 availability issue와 다른 단위 |
| 구현/재현성 | 공식 저장소·Apache-2.0 코드 라이선스 확인. 설치·실행·공개 artifact 검수는 미실행 | 원문 기제 확인. 이번 검토에서 저자 구현·산업 자료의 공개 범위/라이선스는 미확인 |

MicroHECL의 설명에는 최근 30분 호출 graph, 60분 edge 이력,
RT 기준의 전날·전주 대응 시간대가 등장한다.
우리의 허용 10초 창과 9채널 bundle이 이를 그대로 공급한다고 가정하지 않는다.
또한 수집된 span 수를 실제 QPS로, 누락된 status를 정상 응답으로 대체해서는 안 된다.

두 방법은 **기제 중복과 입력 요구량을 판단하는 보충 선행연구**다.
DiagMLP와 가까운 규모의 실제 문헌 비교군을 대체하지 않으며,
이들의 발표 점수를 현재 스모크 점수와 직접 비교하지 않는다.

## 3. 단순 duration 차감이 위험한 이유

합성 예시: 부모 `[0,100]ms`, 직접 자식 A `[10,70]ms`, B `[40,90]ms`.

- duration 단순 차감: `100 - 60 - 50 = -10ms`.
- 관측 자식 구간의 합집합은 `[10,90]`, 길이 80ms.
- 관측 자식에 덮이지 않은 부모 구간은 `100 - 80 = 20ms`.

이 산술은 별도 메모리 내 assert로 확인했으며 실제 데이터 검증 결과가 아니다.
일반적으로 관측된 직접 자식 집합 C에 대한 잔여량은

\[
R(P)=|I_P|-\left|\bigcup_{c\in C}(I_c\cap I_P)\right|
\]

로 정의할 수 있다. 하지만 이 20ms도 CPU 실행 시간은 아니다.
스케줄링 지연·로컬 I/O·계측되지 않은 작업이 포함될 수 있고,
부모가 자식과 병렬 실행한 시간은 합집합에 덮여 제외될 수도 있다.
누락 자식은 잔여량을 부풀리며, 단순 clipping은 clock skew를 해결했다는 증거가 아니다.
CRISP의 critical-path exclusive 귀속과도 일반적으로 같은 양이 아니다.

## 4. 현재 자료와 모델에 대한 판단

- 서비스별로 합쳐진 호출 graph는 요청별 span 실행 DAG가 아니다.
  재호출·서비스 수준 cycle과 병렬 호출의 순서를 boolean edge만으로 복원할 수 없다.
- 현재 그래프는 같은 허용 창에서 시작한 cross-service 연결만 유지한다.
  창 밖 parent와 같은 서비스 내부 span을 제외한 입력으로 완전한 요청 경로를 주장할 수 없다.
- 자기 시간 분석에는 같은 서비스 내부를 포함한 직접 자식, span identity 중복 정책,
  누락·동기/비동기 의미·시계 정합성·완료 시점 가용성의 검증이 별도로 필요하다.
- 기존의 높은 “관측 parent 확인률”은 전체 요청이나 모든 자식이 관측됐다는 증거가 아니다.
- 실제 관측에서 자기 시간의 유효성이나 진단 정확도 효과는 이번에 검사하지 않았다.
  관련 미완료 실험을 이 문헌 검토만으로 완료 처리하지 않는다.

기존 TraceRCA의 방향별 이상 호출 불균형, CIRCA의 parent-conditioned 정상 잔차,
DéjàVu의 공유 분석·관계 집계와 함께 보면,
새로운 주장은 단순한 관계 추가나 시간 차감보다 더 구체적인 근거를 필요로 한다.
현재 스모크의 SN 개선·TT 혼합 결과에 새로운 인과 설명을 사후 부여하지 않는다.

## 근거 범위와 출처

- CRISP 저자 기술 설명: https://www.uber.com/gb/en/blog/crisp-critical-path-analysis-for-microservice-architectures/
  경로 알고리즘·inclusive/exclusive·clock-skew 절을 확인했다.
- CRISP 공식 README: https://raw.githubusercontent.com/uber-research/CRISP/master/README.md
  확인 당시 branch API는 main의 `676abf01118c5bb88d85fd8a6f5a279eebf8be4d`를 가리켰다.
  2026년 현재 README를 2022년 원논문 구현과 완전 동일하다고 하지 않는다.
  README의 속도/대규모 검증 수치는 독립 재현하지 않았고 여기서 성능 근거로 쓰지 않는다.
- 코드 LICENSE: https://github.com/uber-research/CRISP/blob/676abf01118c5bb88d85fd8a6f5a279eebf8be4d/LICENSE
  코드의 Apache-2.0을 연결된 데이터의 라이선스로 확대 해석하지 않는다.
- CRISP 원논문 안내: https://www.usenix.org/conference/atc22/presentation/zhang-zhizhou
  이 보충 검토에서 원논문 PDF 전체를 읽었다고 주장하지 않는다.
- MicroHECL 원문: https://arxiv.org/html/2103.01782
  §I–IV와 §V 일부를 확인했다. 반환 텍스트가 §V-E 도중 50KB에서 잘렸으므로
  뒤의 현장 적용·한계 전체를 확인했다고 하지 않는다.
- FIRM도 조회했으나 발표 페이지에서 본문이 추출되지 않았고 PDF는 binary로 반환됐다.
  검색 요약만으로 세부 기제를 판단하지 않았으며 이 비교 표에 넣지 않았다.
- 기존 검토: [관계 기반 문제 재설계](RESEARCH_REDESIGN.md),
  [실제 스모크 보고서](../relationship_smoke_20261013/REPORT.md).
