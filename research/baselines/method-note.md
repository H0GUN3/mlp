# 메트릭 기준선 비교의 범위와 의미

## 무엇을 비교하는가

이번 비교는 제안 방법의 최종 시험이나 학습 실험이 아닌, 개발용 메트릭 기준선 점검이다. 입력은 고정 RCAEval 표본 중 `reserved_development_cases`의 36건이다. 12개 시스템·원인 서비스·장애 유형 그룹을 각각 3회 반복한 것이므로 36개의 독립 장애 조건으로 세면 안 된다. 정답 서비스는 표본 선택과 사후 채점에만 쓰며 점수 함수에는 전달하지 않는다. 주입 시각은 세 방법에 공통으로 알려진 장애 시작 시각이다.

각 방법은 사례별 메트릭 시계열과 서비스 대응을 받아 서비스 순위를 출력한다. 평가는 원인 서비스의 Top-1/Top-3 순위 등으로 한다. 이는 알려진 시작 시각 조건의 순위 비교이지, 장애 탐지나 실시간 복구 성능 평가가 아니다.

## 세 가지 점수기

1. **기존 최대 변화 기준선.** 첫 smoke의 `build_features`와 `metric_change` 규칙을 쓴다. 정상·장애 값이 각각 20개 이상인 지표에 대해 점수는
   `min(100, abs(median(abnormal) - median(normal)) / max(IQR(normal), 0.05 × abs(median(normal)), 1e-9))`
   이며 소수 셋째 자리로 반올림한다. 서비스 점수는 그 서비스 지표 점수의 최댓값이다. 이는 현재 smoke의 단순 통제 점수이지 BARO나 MicroHECL 재현이 아니다.

2. **BARO 공식 코드 정렬 점수기.** `phamquiluan/baro` 0.2.0, 고정 커밋 `582d4ead3d3301a34fea4e395bfa3f750fc9a40d`의 BARO RobustScorer 점수 경로를 NumPy로 재구현한다. 지표별 점수는 장애 구간의 **부호 있는 최대값**이다.
   `max((x_abnormal - median(x_normal)) / scale(normal))`
   여기서 `scale`은 정상 구간 IQR이다. float64 기준 `10 × eps`보다 작은 IQR은 분모 1로 처리한다. 정상·장애 구간 각각에서 상수 지표를 제거하고 공통 지표만 남긴다. 메모리는 MB로 환산하며, 서비스·장애 라벨에서 지표를 고르는 옵션은 쓰지 않는다. 동점은 원래 열 순서를 유지하고 서비스는 처음 나온 순서로 중복 제거한다. 남은 지표가 없는 서비스는 순위에 임의 추가하지 않고 후보 누락으로 기록한다.

3. **절댓값 진단 변형.** 2번과 같은 입력 처리, 후보, 정규화를 쓰되 지표 점수만
   `max(abs((x_abnormal - median(x_normal)) / scale(normal)))`
   로 바꾼다. 이는 논문 서술의 절댓값 변화와 공개 코드의 부호 있는 최대값 차이를 분리해 살피는 진단용 변형이다. 새로운 독립 방법이거나 논문 전체 재현은 아니다.

## 전처리 차이와 재현 범위

BARO 코드 정렬 경로는 `read_data(strip=False)`에 맞춰 전체 구간을 유지한다. 무한대는 결측으로 바꾸고, 과거 관측만으로 forward-fill한 뒤 남은 선두 결측을 0으로 채운다. 미래 값으로 backward-fill하지 않는다. `latency-50` 열을 제외하고 `latency-90`을 `latency`로 이름 바꾸며, 메모리 단위는 MB로 바꾼다. 정상·장애 구간을 알려진 주입 시각으로 나눈다.

이는 BARO 전체 실행을 뜻하지 않는다. 고정 소스의 `robust_scorer`는 pandas와 scikit-learn `RobustScaler`를 쓰고 `max(zscores)`를 계산한다. 그 내부 `preprocess`는 시간 열·상수 열 제거와 메모리 환산을 수행하며, `dk_select_useful`이 켜질 때만 추가 열 제외와 유효 열 선택을 한다. 본 비교는 별도의 NumPy 어댑터, 공통 지표 필터, 명시적 작은 IQR 규칙을 사용한다. BARO의 온라인 BOCPD 시작점 탐지나 전체 데이터 파이프라인을 실행하지 않으므로 이를 BARO 논문 전체 재현 또는 탐지 성능으로 부르지 않는다.

첫 번째 기준선도 입력 처리와 점수식이 BARO와 다르다. 따라서 1번과 2번의 차이를 점수식 하나의 효과로 분리할 수 없고, 전처리·정규화·집계 규칙을 포함한 방법 묶음 비교로 해석한다. 2번과 3번만 같은 전처리에서 부호 처리의 차이를 본다.

## 공정성 및 해석 한계

세 방법은 동일 표본·서비스 후보·익명화된 정보 범위와 채점 정답을 공유하지만, 방법에 정의된 전처리 차이는 그대로 공개한다. 정답 서비스나 원인 지표를 이용한 입력 선택은 금지한다. 호출 방향도 인과 정답이 아니다. 알려진 시작 시각을 주므로 결과는 “시작 시각을 아는 RCA 점수기” 범위에 한정된다.

36건은 12개 반복 그룹에 묶여 있다. 이를 독립 표본 36개처럼 취급해 유의성, 일반화, 인과성을 주장할 수 없다. 관측된 순위는 이 개발 표본에서의 탐색 결과일 뿐이며, 우수성이나 신규성을 입증하지 않는다. TORAI와 EviRCA는 현재 미실행이다. 어댑터가 필요하며, 점수 결과가 있는 것처럼 인용하거나 단순 메트릭 점수를 해당 방법의 재현으로 부르면 안 된다.

## 추적 자료

- 프로토콜: `research/BASELINE_PROTOCOL.md`
- 고정 참조 코드: `research/baselines/reference/baro-root-cause-analysis.py`, `research/baselines/reference/baro-utility.py`
- 비교 조건 및 실행 상태: `research/verification/baseline-contract.md`
- BARO 논문: https://arxiv.org/abs/2405.09330
- BARO 0.2.0 공개 코드: https://github.com/phamquiluan/baro/blob/0.2.0/baro/root_cause_analysis.py
- TORAI 논문: https://arxiv.org/html/2604.13522v1
- EviRCA 논문: https://arxiv.org/html/2609.19825v1
