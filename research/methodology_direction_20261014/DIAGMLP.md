# DiagMLP: 무엇을 없애고, 무엇을 그대로 사용하는가

작성일: 2026-10-14. 범위는 **DiagMLP 논문 v2 한 편과 그 구조를 해석하는 데 필요한 backbone 근거**다. 모델 실행·학습·원자료 열람은 하지 않았다.

## 1. 핵심 답변

DiagMLP는 원시 데이터를 곧바로 넣는 평범한 MLP 분류기가 아니다. **기존 방법의 전처리·모달별 임베딩·진단 과제와 학습 목적은 유지하고, 명시적 서비스 의존 그래프를 사용하는 표현 학습 부분을 두 개의 단층 융합 MLP로 바꾼 비교 기준**이다. 저자도 독립적인 경쟁 모델보다 GNN의 추가 기여를 확인하는 ablation baseline으로 정의한다. 여기서 backbone은 교체 전의 원 방법 전체 틀을 뜻한다. [P, §I, §III-C, §IV]

일반적인 MLP와 다른 특별한 새 연산이 있는 것은 아니다. 중요한 구성은 다음 네 가지다.

1. **강한 입력 표현을 상속한다.** 로그 파싱, 시계열 처리, 모달별 인코더 등을 없애지 않는다.
2. 서비스별 관측 벡터에 **학습 가능한 서비스 위치/식별 벡터**를 붙인다.
3. 먼저 한 서비스의 여러 모달을 합치고, 다음으로 **모든 서비스 벡터를 정해진 순서로 이어 붙여** 시스템 표현을 만든다.
4. 기존 탐지·원인 위치·장애 종류 예측 모듈과 목적함수를 연결한다. [P, §III-A/C/D, Eq. (2)–(3), §IV]

따라서 정확한 질문은 “관계가 전혀 필요 없는가?”가 아니라 **“이 데이터와 기존 전처리·임베딩을 조건으로, 명시적 그래프 기반 모듈을 추가했을 때 이득이 있는가?”**다. [P, §I–III, §V; 해석]

## 2. 원시 관측에서 예측까지

### 2.1 논문 공통 구조: 전처리·인코더를 통째로 없애지 않는다

```text
원시 metrics / logs / traces
  │
  ├─ 원 backbone의 전처리
  │    시간 창 구성·정렬, 로그 파싱, 시계열/alert 변환 등
  │    ※ 방법마다 다름. trace 처리에 호출·의존 정보가 이미 반영될 수 있음
  │
  └─ 원 backbone의 모달별 임베딩 모듈
       서비스 i의 metric 벡터 / log 벡터 / trace 벡터
                         │
                         ├─ 학습 가능한 위치 벡터 p_i를 함께 CONCAT
                         ▼
                 Modal_Fusion_MLP
               한 서비스의 모달 정보 결합
                         │
                h_1, h_2, …, h_N
                         │
               서비스 순서대로 CONCAT
                         ▼
                  Node_Fusion_MLP
                시스템 전체 벡터 y_g
                         │
           원 backbone의 task head(s)와 목적함수
            ├─ 장애 유무: 정상/비정상
            ├─ 원인 위치: 후보 서비스/인스턴스 순위
            └─ 장애 종류: 해당 backbone에 이 과제가 있을 때

교체 영역: 명시적 그래프 기반 표현 학습 → 두 융합 MLP
유지 영역: 전처리·임베딩 방식·해당 backbone의 과제/학습 목적
```

**모든 backbone에서 세 과제를 동시에 수행한다는 뜻은 아니다.** Eadro는 탐지+위치, TVDiag의 GAIA 실험은 종류+위치, DeepHunt의 D1/D2 실험은 위치다. 공통 구조에서 인코더는 특정 모델로 제한되지 않으며, 논문의 §II에 나오는 TCN·Transformer·FastText·BERT는 기존 방법들을 설명하는 예시다. 이를 모두 DiagMLP 필수 모듈이라고 읽으면 안 된다. [P, §II, §III-A/C, §IV-A, Table I]

### 2.2 Eadro backbone의 구체적인 예

아래는 **Eadro 원 논문의 인코더 설명**이지 모든 DiagMLP 입력의 공통 규격이 아니다.

| 원시 관측 | Eadro의 전처리 및 유지할 모달별 학습 | 서비스별 출력 |
|---|---|---|
| Logs | Drain으로 변수 부분을 제거해 이벤트 템플릿을 얻음 → 창 시작 기준 상대 발생 시각 → 지수 감쇠 커널의 Hawkes process를 Tick으로 추정 → 이벤트별 intensity 벡터 → FC | 로그 임베딩 |
| Metrics/KPIs | 서비스별 여러 지표를 길이 T의 다변량 시계열로 구성 → 1D dilated causal convolution(DCC) → self-attention | metric 임베딩 |
| Traces | 호출받는 서비스(callee)별·시간 슬롯별 평균 지연을 계산, 호출이 없는 슬롯은 0 → 길이 T의 지연 시계열 → DCC → self-attention | trace 임베딩 |

로그는 이 예에서 BERT 의미 임베딩이 아니라 **이벤트 발생 양상**을 모델링한다. trace도 원시 span 자체를 그대로 MLP에 넣지 않는다. [E, §IV-A1–3]

원 Eadro의 다음 단계는 `모달 임베딩 concat → FC → GLU → GAT → global attention pooling → detector/localizer`다. GNN은 과거 호출에서 만든 방향성 의존 그래프를 사용한다. DiagMLP의 공통 Eq. (2)는 모달별 임베딩을 받아 자체 modal/node fusion을 수행한다. **그러나 v2는 Eadro의 GLU를 정확히 어느 코드 경계에서 제거/유지했는지까지 명시하지 않는다.** 따라서 “저자도 GLU 앞에서 encoder 전체를 교체했다”는 구현 수준의 단정은 할 수 없다. 아래 §6의 GLU 앞 교체는 우리 로컬 복원의 명시적 선택이다. [E, §IV-B/C; P, §III-C, Fig. 4, §IV]

Eadro의 유지 대상 task heads는 시스템 표현을 공유하는 FC 기반 detector와 localizer다. 원 논문은 탐지 손실과 위치 손실의 가중 결합을 설명한다. DiagMLP는 새 공통 손실을 제안하는 대신 해당 backbone의 목적함수와 학습 전략을 유지한다고 한다. **“유지”는 모듈/학습 설계를 유지한다는 뜻이지, 인코더 가중치를 반드시 동결하거나 같은 수치의 임베딩을 캐시했다는 뜻은 아니다.** [E, §IV-C; P, §IV]

### 2.3 TVDiag·DeepHunt에서는 유지하는 표현이 다르다

- **TVDiag / GAIA:** DiagMLP 논문의 §IV-C·Fig. 5는 교체 이전 입력을 **FastText에서 나온 node-wise Original Features**라고 명시한다. TVDiag 1차 자료는 모달별 alert를 인스턴스에 연결해 metric/trace/log 특징을 만들고, 원래는 모달별 GraphSAGE encoder와 pooling을 적용한다고 설명한다. 원 TVDiag에는 위치·종류 손실뿐 아니라 task-oriented/cross-modal 대조학습 목적도 있다. 따라서 이를 Eadro의 Hawkes+DCC 입력으로 설명하면 틀린다. 다만 DiagMLP v2의 간략한 공통 그림만으로 **세 그래프 encoder, 보조 손실, augmentation을 두 MLP와 정확히 어떻게 연결했는지**는 복원할 수 없다. 유지 주장은 §IV의 저자 설명과, 공개적으로 확인 가능한 세부 wiring을 구분해야 한다. [P, §IV, §IV-C, Fig. 5; T, §4.2, §4.4–4.5]
- **DeepHunt / D1·D2:** DiagMLP 저자는 원 저자의 **이미 전처리된 multimodal 데이터**를 사용했다고 한다. DeepHunt 저자 README는 노드 특징이 pod metric·trace·log 및 node metric 특징으로 구성되고, 호출·배포 정보로 만든 그래프와 함께 저장된다고 설명한다. DiagMLP 논문은 DeepHunt를 self-supervised graph autoencoder 방식으로 소개한다. 이를 교체하되 목적·학습 전략을 유지했다는 것이 논문 수준 설명이며, **임베딩별 폭, GAE encoder/decoder의 정확한 교체 범위, 재구성 목적과 최종 위치 점수 연결은 v2만으로 확정할 수 없다.** README의 demo 기본값을 DiagMLP 저자의 실험 설정으로 옮겨 쓰지 않는다. [P, §II, §IV-A; D, Dataset, GAE pre-training]

이 구분 때문에 “DiagMLP 하나의 고정된 원시 데이터 처리법”은 없다. 비교마다 입력 생성 비용과 앞단의 학습 내용이 달라진다.

## 3. Eq. (2)–(3)를 차원과 순서까지 읽기

출처는 [P, §III-A/C/D, Eq. (2)–(3)]다. 원문은 융합 전후 모두 `x_i`를 사용한다. 혼동을 피하려고 아래에서 **입력은 z_i, 융합 후는 h_i**로만 이름을 바꿨다.

### 3.1 Eq. (2): 위치 벡터를 먼저 이어 붙인다

논문 표기에서 각 모달 임베딩과 위치 벡터는 각각 d차원이다.

```text
x_i^metric, x_i^log, x_i^trace ∈ R^d
p_i ∈ R^d                         # 학습 가능한 노드 위치 벡터

z_i = x_i^metric ⊕ x_i^log ⊕ x_i^trace ⊕ p_i  ∈ R^(4d)
h_i = Modal_Fusion_MLP(z_i)                     ∈ R^h_m
x_g = h_1 ⊕ h_2 ⊕ … ⊕ h_N                     ∈ R^(N*h_m)
y_g = Node_Fusion_MLP(x_g)                      ∈ R^h_g
```

`⊕`는 원소별 덧셈이 아니라 **concatenation(벡터 이어 붙이기)**다. `p_i`는 modal fusion **이전** 입력의 일부이며, 융합이 끝난 벡터에 나중에 더하는 구조가 아니다. `h_m`, `h_g`는 차원 설명을 위한 기호로, 원문이 정한 수치가 아니다.

위치 벡터는 “이 특징이 어느 서비스 자리의 것인가”를 구별하도록 학습된다. Eq. (2)는 이를 학습 가능한 `p_i`라고만 규정하며, 인접행렬·최단거리·Laplacian을 입력으로 계산하라고 명시하지 않는다. 두 fusion MLP는 **같은 블록 형식**을 사용한다는 뜻이지, 입력 차원이 다른 두 블록의 가중치를 공유한다는 뜻이 아니다.

### 3.2 Eq. (3): 각 블록은 affine 한 층 뒤 LN → ReLU → Dropout

```text
Fusion_MLP(x) = Dropout(ReLU(LN(Wx + b)))

실제 적용 순서:
Linear/affine(Wx+b) → LayerNorm → ReLU → Dropout
```

따라서 shape를 풀면 다음과 같다.

| 블록 | 입력 | W | b / LN 출력 / 최종 출력 |
|---|---|---|---|
| Modal fusion | 4d | h_m × 4d | h_m |
| Node fusion | N·h_m | h_g × (N·h_m) | h_g |

§III-D는 **각 fusion이 single-layer**라고 명시한다. 두 fusion을 순차 적용하지만, 각 fusion 안에 여러 affine hidden layer를 넣는 것이 아니다. 정규화는 BatchNorm이 아닌 **LayerNorm**이고, dropout은 ReLU **뒤**다. 원 Eadro DCC의 정규화와 이 교체 블록의 LN은 별개다. v2 본문은 `h_m`, `h_g`, dropout 확률, LN의 epsilon, 초기화, 위치 벡터 구현체를 재현할 만큼 구체적으로 제공하지 않는다. 로컬의 64차원·dropout 0.1을 논문 공통 설정으로 적으면 안 된다. [P, §III-C/D; E, §V-C]

### 3.3 무엇을 학습할 수 있고, 어떤 제약이 생기는가

- **인접행렬에 따른 이웃 메시지 전달은 없다.** 그렇지만 node fusion은 모든 서비스 벡터를 함께 받으므로, 서비스 간 통계적 조합을 학습할 수 있다. “서비스들을 완전히 독립적으로만 처리한다”는 설명은 modal 단계에만 해당하며 전체 모델에는 맞지 않는다. [P, Eq. (2); 해석]
- 고정 순서 concat은 서비스 자리와 정체성에 민감하다. 서비스↔인덱스 대응을 일관되게 유지해야 한다. 같은 파라미터로 임의의 새 서비스 수를 자연스럽게 처리하는 permutation-invariant 집합 모델은 아니다. [P, Eq. (2), §III-D; 해석]
- node fusion의 affine 파라미터만 `h_g·N·h_m + h_g`이므로, 폭을 고정하면 N에 선형 비례한다. 위치 임베딩도 N·d다. **단순한 구조 ≠ 모든 GNN보다 파라미터가 적음/항상 빠름**이다. 논문도 큰 시스템으로의 확장 문제를 인정한다. [P, §III-D]

## 4. 그래프 모듈 비교 실험은 어떻게 구성했는가

### 4.1 직접 ablation은 세 backbone, 다섯 데이터셋

| 직접 교체 backbone | 데이터 | 실제 평가 과제 | 같은 비교 안에서 유지한다고 명시한 부분 |
|---|---|---|---|
| Eadro | SN, TT | 탐지·원인 위치 | raw dataset, 전처리, 임베딩 방식, 목적, 학습 전략, task module |
| TVDiag | GAIA | 원인 위치·장애 종류 | 위와 같음 |
| DeepHunt | D1, D2 | 원인 위치 | 위와 같음 |

핵심 통제는 **각 backbone 내부에서 GNN 표현 학습을 DiagMLP로 대체**하는 것이다. 서로 다른 backbone의 raw input/embedding을 전부 같은 것으로 통일한 실험이 아니다. 교체로 파라미터 수·정규화·융합 구조도 달라지므로, 특정 한 요소(예: 인접행렬만)의 인과 효과를 완벽하게 분리했다고 확대하면 안 된다. [P, Fig. 1/4, §IV, §IV-A; 통제 범위 해석]

**DiagFusion·CHASE는 추가 문헌 비교군**이다. 호환되는 평가 프로토콜의 결과를 실었을 뿐, 이 두 방법에 대해서도 직접 GNN→DiagMLP 교체를 수행했다고 말하지 않는다. Eadro/TVDiag/DeepHunt 역시 모든 데이터셋에 전부 재실행한 것이 아니다. 예를 들어 Table IV의 Eadro–GAIA·D1·D2는 아래 각주상 원 논문 인용 수치다. [P, §IV-A, Table IV 각주 5–6]

### 4.2 전처리·수정 및 결과 출처

- **SN/TT:** 원 전처리 스크립트가 없어서 DiagMLP 저자가 전처리를 재구현했다.
- **GAIA/D1/D2:** 원 저자가 제공한 전처리 완료 multimodal 데이터를 사용했다.
- 저자는 Eadro의 **창 분할 방식에 누수 위험이 있어 수정하고 validation set을 추가**했다고 적는다. 이것이 모든 데이터의 incident-group 분할, 시간 순서 분할, 누수 가능성의 완전 제거까지 입증하지는 않는다. 정확한 수정 코드·샘플 manifest는 v2 설명만으로 확인되지 않는다.
- **Table IV의 `±`가 있는 결과:** 인용한 방법과 같은 설정으로 DiagMLP 저자가 수행한 **독립 실험 10회**의 결과.
- **Table IV의 `±`가 없는 결과:** 해당 인용 논문에서 직접 가져온 결과. `-`는 미보고이며 0점이 아니다.
- 따라서 Table IV의 수치는 모두 이 논문에 **게재**되어 있지만, 그중 일부만 이 논문 저자가 **재실행**했다. 전처리·분할 수정이 있으므로 원 Eadro 논문의 원래 조건/성능을 그대로 복제했다고도 말할 수 없다. [P, §IV-A Datasets/Notes, Table IV 각주 5]

“동일 조건”은 저자의 실험 설계 진술이다. 본 조사에서 원자료·실험 코드·split manifest를 독립 감사한 것은 아니다. 특히 task head/objective 보존과 backbone별 세부 wiring은 같은 수준의 증거가 아니다.

### 4.3 데이터셋과 과제: Table I 그대로

| 데이터 | #instances | train | valid | test | 과제 | DiagMLP backbone |
|---|---:|---:|---:|---:|---|---|
| SN | 12 | 316 | 78 | 169 | 탐지·위치 | Eadro |
| TT | 27 | 3256 | 813 | 1744 | 탐지·위치 | Eadro |
| GAIA | 10 | 128 | 32 | 939 | 종류·위치 | TVDiag |
| D1 | 46 | 63 | - | 147 | 위치 | DeepHunt |
| D2 | 18 | 40 | - | 93 | 위치 | DeepHunt |

출처: [P, Table I](https://arxiv.org/html/2501.02766v2#S3.T1). train/valid/test는 논문의 표본 수이지 독립 장애 주입 횟수가 아니다. `#instances`도 모든 데이터에서 순수한 business service 수라고 해석하면 안 된다. 예를 들어 DeepHunt 저자 설명상 D1의 46은 microservice instance 40+VM 6이며 D2의 18에는 여러 종류의 시스템 인스턴스가 포함된다. [D, Dataset]

원 Eadro 논문은 SN/TT에서 72/162회 주입과 60%/40% 시기별 train/test를 설명한다. 이것을 DiagMLP의 위 분할 수나 로컬 공개 아카이브의 주입 수와 혼합하지 않는다. fault injection은 데이터를 만들기 위해 장애를 **발생시키는 과정**이고, DiagMLP는 수집 관측에서 장애를 **진단하는 모델**이다. [E, §V-A2]

## 5. 정확한 결과와 읽을 때 주의할 점

### 5.1 Table IV 전체: 위치 정확도, 단위 %

아래는 [P, Table IV](https://arxiv.org/html/2501.02766v2#S4.T4.fig1)의 **모든 Top1/Top3/Top5 셀을 그대로 옮긴 것**이다. 마지막 열은 DiagMLP에 사용한 backbone이지, 왼쪽 모든 모델을 그 backbone으로 실행했다는 뜻이 아니다. `±`는 표준편차이며 신뢰구간이 아니다. 출처 구분은 §4.2를 따른다.

| 데이터 | 지표 | Eadro | DiagFusion | TVDiag | CHASE | DeepHunt | DiagMLP | DiagMLP backbone |
|---|---|---|---|---|---|---|---|---|
| SN | Top1 | 41.8 ± 14.5 | - | - | - | - | 80.2 ± 3.1 | Eadro |
| SN | Top3 | 61.1 ± 16.0 | - | - | - | - | 88.6 ± 2.8 | Eadro |
| SN | Top5 | 71.7 ± 10.8 | - | - | - | - | 89.4 ± 3.2 | Eadro |
| TT | Top1 | 91.1 ± 2.2 | - | - | - | - | 98.5 ± 0.8 | Eadro |
| TT | Top3 | 96.5 ± 0.7 | - | - | - | - | 99.7 ± 0.6 | Eadro |
| TT | Top5 | 97.7 ± 0.6 | - | - | - | - | 99.2 ± 0.6 | Eadro |
| GAIA | Top1 | 30.4 | 41.9 | 59.8 ± 0.8 | 61.4 | - | 61.0 ± 1.0 | TVDiag |
| GAIA | Top3 | 59.2 | 81.3 | 80.4 ± 0.5 | 88.2 | - | 80.7 ± 0.8 | TVDiag |
| GAIA | Top5 | - | 91.4 | 88.5 ± 0.2 | - | - | 87.4 ± 0.8 | TVDiag |
| D1 | Top1 | 31.0 | 33.3 | - | - | 79.8 ± 0.4 | 79.8 ± 1.0 | DeepHunt |
| D1 | Top3 | 44.6 | 50.5 | - | - | 90.6 ± 0.6 | 90.6 ± 0.5 | DeepHunt |
| D1 | Top5 | 48.4 | 64.8 | - | - | 96.7 ± 0.3 | 95.8 ± 1.0 | DeepHunt |
| D2 | Top1 | 21.4 | 39.8 | - | - | 78.9 ± 0.7 | 79.0 ± 0.5 | DeepHunt |
| D2 | Top3 | 38.6 | 55.2 | - | - | 93.4 ± 0.3 | 93.0 ± 0.7 | DeepHunt |
| D2 | Top5 | 45.4 | 75.0 | - | - | 94.6 ± 0.0 | 94.6 ± 0.0 | DeepHunt |

Top-k는 정답 원인 인스턴스가 상위 k개 안에 있는 사례의 비율이다. v2의 간단한 지표 설명만으로 정상 창 포함 여부, detection gate 적용, tie 처리의 세부 구현까지 확정하지 않는다. 로컬 지표와 비교하려면 별도로 분모·게이팅 계약을 맞춰야 한다. [P, §IV-A Evaluation Metrics]

**직접 짝지은 backbone 대비 DiagMLP 평균 차이**를 검산하면 다음과 같다. 단위는 상대 개선율(%)이 아니라 **percentage points, %p**다.

| 짝지은 비교 | Top1 차이 | Top3 차이 | Top5 차이 |
|---|---:|---:|---:|
| SN: DiagMLP − Eadro | +38.4 | +27.5 | +17.7 |
| TT: DiagMLP − Eadro | +7.4 | +3.2 | +1.5 |
| GAIA: DiagMLP − TVDiag | +1.2 | +0.3 | −1.1 |
| D1: DiagMLP − DeepHunt | 0.0 | 0.0 | −0.9 |
| D2: DiagMLP − DeepHunt | +0.1 | −0.4 | 0.0 |

검산은 인쇄된 평균끼리의 뺄셈이다. 표준편차를 뺄셈하거나 paired significance test를 수행한 것이 아니다.

### 5.2 Table II·III: 탐지와 장애 종류

**Table II: 탐지**, 단위 %. 이 표에는 표준편차가 없다. Table IV의 각주만으로 이 표의 각 셀을 모두 10회 재실행 결과라고 확정하지 않는다.

| 데이터 | 방법 | Precision | Recall | F1 |
|---|---|---:|---:|---:|
| SN | Eadro | 92.1 | 92.0 | 92.1 |
| SN | DiagMLP | 93.8 | 99.7 | 96.7 |
| TT | Eadro | 83.3 | 99.5 | 90.7 |
| TT | DiagMLP | 83.4 | 99.8 | 90.8 |

**Table III: GAIA 장애 종류**, 단위 %.

| 방법 | Precision | Recall | F1 |
|---|---|---|---|
| TVDiag | 93.4 ± 0.2 | 95.5 ± 0.0 | 94.5 ± 0.1 |
| DiagMLP | 92.1 ± 0.2 | 94.7 ± 0.3 | 93.4 ± 0.2 |

출처: [P, Table II](https://arxiv.org/html/2501.02766v2#S4.T2), [Table III](https://arxiv.org/html/2501.02766v2#S4.T3).

SN 탐지 F1 차이는 +4.6%p, TT는 +0.1%p다. GAIA 종류 F1은 DiagMLP가 **−1.1%p**다. 표시된 P/R/F1을 그대로 기록했으며, 집계 방식이 충분히 제시되지 않은 상태에서 반올림된 평균 P/R로 F1을 다시 만들어 대체하지 않았다.

### 5.3 원문의 불일치를 숨기지 않는다

1. **비단조 값:** TT DiagMLP의 `Top3 99.7 ± 0.6 > Top5 99.2 ± 0.6`. 동일 사례·순위 목록에 대한 통상적 Top-k라면 각 실행에서 Top5≥Top3이고 평균도 그래야 한다. **표기/집계/평가 중 무엇이 원인인지는 미확인**이다. 위 표는 99.2를 임의 수정하지 않았다. [P, Table IV]
2. **D1 본문 모델 매핑 오류:** §IV-B는 DiagMLP `79.8 ± 0.4`와 “DeepHunt의 31.0”을 비교한다. 그러나 Table IV에서 **31.0은 Eadro**, **79.8 ± 0.4는 DeepHunt**, **DiagMLP는 79.8 ± 1.0**이다. 직접 ablation의 D1 Top1은 48.8%p 개선이 아니라 **평균 동률**이다. [P, §IV-B와 Table IV 대조]
3. **보편적 우위라는 본문 표현:** §IV-B의 “backbone을 모두 능가한다”는 취지의 문장과 달리, GAIA Top5·D1 Top5·D2 Top3는 낮고 D1 Top1/Top3·D2 Top5는 같다. GAIA의 문헌 비교에서는 CHASE의 Top1/Top3, DiagFusion의 Top3/Top5보다도 낮다. [P, Table IV]
4. **표준편차와 유의성:** §IV-B는 GAIA 종류 F1 차이가 표준편차 이내라고 서술하지만 `94.5 ± 0.1`과 `93.4 ± 0.2`의 평균 차이는 1.1%p로 두 SD보다 크고, 단순 ±1SD 구간도 겹치지 않는다. 이 본문 주장을 수치가 뒷받침한다고 쓰면 안 된다. 그렇다고 SD만으로 통계적 유의성/비유의성을 확정할 수도 없다. [P, Table III, §IV-B]

따라서 정확한 요약은 **“수정된 공개 benchmark 조건에서 Eadro 대비 큰 개선, 다른 직접 backbone 대비 대체로 근접한 결과이며 일부 지표는 낮다”**이다.

## 6. 논문 구조와 우리 로컬 복원은 다르다

아래 근거는 허용된 로컬 문서·코드를 **정적 읽기만** 한 것이다. 이 조사에서 self-check나 모델 실행을 새로 수행하지 않았다.

### 6.1 `native_models.py`: Eadro 앞단을 살린 equation-based 복원

`research/native_reproduction_20261013/native_models.py`의 `EquationDiagEncoder`는 원 encoder의 `metric_model`, `log_model`, `trace_model`을 그대로 연결한다.

```text
로컬 Eadro 모달 출력: metric64 ⊕ log16 ⊕ trace64 = 144차원
  ⊕ 로컬 학습 위치 벡터64
  → Linear(208,64) → LayerNorm(64) → ReLU → Dropout(0.1)
  → N개 서비스 벡터 concat: 64*N
  → Linear(64*N,64) → LayerNorm(64) → ReLU → Dropout(0.1)
  → 기존 locator / detector
```

- 위치 벡터를 modal fusion **전**에 넣고 두 블록 순서는 Eq. (2)–(3)와 맞춘다.
- 64차원 position/modal/system 표현, dropout 0.1, fixed node inventory, 선택한 temporal/graph/head 폭은 **로컬 선택**이다. 논문의 동일 d 표기와 달리 모달 폭도 64/16/64로 다르다.
- `CALIBRATION_PROTOCOL.md`는 **원 GLU와 graph/pooling 단계를 교체**한다고 명시한다. 이는 방치된 GLU를 추가로 남기지 않으려는 로컬 해석이며 DiagMLP 저자 코드 확인 결과가 아니다.
- 원 Eadro의 정확한 원본이 아니라, 선언된 공개 repair fork를 로드한다. 모달 인코더와 joint detector/localizer 보존은 원 논문 재현에 필요한 요소지만, 그것만으로 저자 실험 전체를 복제한 것은 아니다.
- 기본값은 로컬 `eadro` dropout 0.0, `diagmlp` dropout 0.1이다. 따라서 이 로컬 설정을 **모든 하이퍼파라미터까지 동일한** 순수 graph-only toggle이라고 표현하면 안 된다.
- 로컬 입력 계약은 metric `[B*N,T,7]`, log `[B*N,event_count]`, trace `[B*N,T,2]`다. calibration 문서는 두 번째 trace 채널을 0으로 보존한다고 밝힌다. 이는 Eadro 논문의 단변량 지연 설명과 구분해야 한다.
- 로컬 `joint_loss`는 탐지 CE와 장애 창의 원인 CE를 결합하며 정상만 있을 때 원인 손실을 0으로 처리한다. detector/localizer 목적을 유지한 복원 선택이지, DiagMLP v2가 이 정확한 코드를 제공한 것이 아니다.

`CALIBRATION_PROTOCOL.md`는 원 공개 아카이브 주입 수·정확한 split manifest가 원 논문과 일치한다고 보장하지 않으며, 창 무작위 분할이 같은 장애 주입의 여러 창을 분할 간 공유할 수 있음을 명시한다. 시간 정렬·Hawkes horizon·학습 자료에만 맞춘 scaling 등 로컬 보정 역시 **우리 프로토콜**이며 DiagMLP 저자의 보정 내역이 아니다.

### 6.2 `MODEL_PROVENANCE.md`: 공통 입력 adaptation은 또 다른 비교다

`research/mlp_prerequisites/MODEL_PROVENANCE.md`의 common-input adaptation은 이미 계산된 일반 수치 특징을 받아 원 metric/log/trace encoder를 재현하지 않는다. 예를 들어 D=17, H=32이면 `position32 → modal Linear(49,32) → node Linear(32*N,32) → 로컬 Linear(32,N) 원인 head`를 쓴다.

이는 Eq. (2)–(3)형 fusion 비교에는 유용하지만 **원 DiagMLP 전체 pipeline도, 원 Eadro detector/localizer·공동 목적을 유지한 재현도 아니다.** 앞의 native 복원과 같은 것으로 부르면 안 된다.

이 문서는 원 Eadro 소스의 runtime blocker와 별도 repair fork의 synthetic smoke를 구분해서 기록한다. 그 코드 결함을 DiagMLP 모델의 약점이라고 옮겨 적지 않는다. 마찬가지로 **우리 5epoch 실험 실패, 희소 trace, 개별 로그 사례는 DiagMLP 원 논문의 한계를 입증하지 않는다.**

### 6.3 공개 구현의 확실성과 통합 불확실성

이번에 읽은 DiagMLP v2는 Eadro/TVDiag/DeepHunt의 자료 위치를 제시하지만, **DiagMLP 저자 구현의 고정 commit·완전한 backbone별 wiring/config/split manifest를 확인할 수 있는 근거는 확보하지 못했다.** 이것은 “어디에도 공개 코드가 없다”는 전역 검색 결론이 아니다.

확정할 수 있는 것은 수식·단층 구조·concat·LN/ReLU/dropout 순서와 논문이 밝힌 통제/결과다. **GLU 경계, TVDiag의 모달별 encoder·대조손실 연결, DeepHunt의 GAE 교체 범위, 폭·초기화·dropout·split identity**는 정확한 저자 재현을 위해 남은 통합 불확실성이다.

## 7. 이 논문이 입증하지 않는 것

| 과도한 주장 | 이 근거로 말할 수 있는 범위 |
|---|---|
| 전체 pipeline이 그래프/의존 정보와 무관하다 | 교체 모듈은 명시적 그래프 입력을 사용하지 않는다. 앞단 trace 처리·인코더·원 framework의 자료 생성에 의존 정보가 남을 수 있다. |
| 유용한 서비스 의존성은 없다 | 기존 특징과 작은 benchmark에서 평가한 GNN의 **추가 이득**이 제한적이다. UMAP 분리도는 의존성 정보의 인과적 기여를 분리한 실험이 아니다. |
| 전처리 비용은 0이다 | 로그 파싱·Hawkes fitting·시계열 변환·임베딩을 유지한다. 이 조사에서 end-to-end 비용 개선을 뒷받침할 정량 결과는 확보하지 않았다. |
| DiagMLP가 항상 더 작고 빠르다 | node concat 층은 서비스 수에 비례해 커진다. 단순한 연산 구조만으로 파라미터·지연 우위를 보장하지 않는다. |
| 모든 지표·시스템에서 GNN보다 우수하다 | Table III/IV에 열세·동률이 있고, 데이터셋은 10–46 instances다. 새 장애/서비스 구성·대규모 시스템 일반화는 별도 검증 대상이다. |
| 공개 전처리·split의 누수 문제가 완전히 해결됐다 | 수정했다는 저자 설명은 있으나, 이 조사에서 코드·표본 ID·incident 경계를 독립 검증하지 않았다. |
| 로컬 저성능이 논문의 실패를 재현했다 | 로컬은 선언된 복원/적응판이다. 학습 예산·입력·분할·지표 계약까지 같음을 확인하기 전에는 귀속할 수 없다. |

근거: [P, §II–V, Eq. (2), Tables I/III/IV; E, §IV-A; 위 로컬 문서]. 특히 “전처리가 중요하다”는 논문의 해석과 **어느 전처리 요소가 얼마만큼 개선했는지 정량 분해했다**는 주장은 다르다.

## 8. 출처·주장 대응과 확인 범위

### 1차 자료

- **[P]** Fei Gao 외, *Are GNNs Actually Effective for Multimodal Fault Diagnosis in Microservice Systems?*, [arXiv:2501.02766v2 전체](https://arxiv.org/html/2501.02766v2), [버전 이력](https://arxiv.org/abs/2501.02766). 본 설명은 요청에서 ICWS2025로 지칭한 연구의 **2025-03-10 v2**에 고정한다. arXiv 메타데이터만으로 학회 최종 출판본과의 동일성까지 확인한 것은 아니다.
- **[E]** Cheryl Lee 외, *Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data*, [원문](https://arxiv.org/html/2302.05092).
- **[T]** Shuaiyu Xie 외, *TVDiag: A Task-oriented and View-invariant Failure Diagnosis Framework for Microservice-based Systems with Multimodal Data*, [읽은 판본 v3](https://arxiv.org/html/2407.19711v3). 필요한 모달 특징·GraphSAGE·목적 설명만 사용하며, 이 후속 판본의 설정을 DiagMLP의 실제 실험 config로 간주하지 않는다.
- **[D]** DeepHunt 저자 저장소의 [README 원문](https://raw.githubusercontent.com/bbyldebb/DeepHunt/main/README.md). 데이터 표현·GAE 배경만 사용했다. 데이터 아카이브를 내려받거나 열지 않았다.

| 주장 | 직접 대응하는 절/표 |
|---|---|
| 경쟁 모델보다 통제 ablation baseline | [P §I](https://arxiv.org/html/2501.02766v2#S1), [§IV](https://arxiv.org/html/2501.02766v2#S4) |
| 임의의 모달별 임베딩을 받아 기존 task module에 연결 | [P §III-A](https://arxiv.org/html/2501.02766v2#S3.SS1), [§III-C/Fig. 4](https://arxiv.org/html/2501.02766v2#S3.SS3) |
| position concat의 위치·두 fusion·적용 순서 | [P Eq. (2)](https://arxiv.org/html/2501.02766v2#S3.E2), [Eq. (3)](https://arxiv.org/html/2501.02766v2#S3.E3) |
| single-layer·concat·N에 따른 확장 문제 | [P §III-D](https://arxiv.org/html/2501.02766v2#S3.SS4) |
| Eadro의 로그/Hawkes·KPI/trace DCC+attention | [E §IV-A](https://arxiv.org/html/2302.05092#S4.SS1) |
| 원 Eadro의 GLU·GAT·pooling 및 공동 task | [E §IV-B](https://arxiv.org/html/2302.05092#S4.SS2), [§IV-C](https://arxiv.org/html/2302.05092#S4.SS3) |
| 직접 세 backbone·추가 비교군·전처리 재구현·분할 수정 | [P §IV-A](https://arxiv.org/html/2501.02766v2#S4.SS1), [Table IV 각주](https://arxiv.org/html/2501.02766v2#S4.T4.fig1) |
| GAIA 입력의 FastText 표현 | [P §IV-C/Fig. 5](https://arxiv.org/html/2501.02766v2#S4.SS3) |
| TVDiag 모달 특징·GraphSAGE·보조 목적 | [T §4.2](https://arxiv.org/html/2407.19711v3#S4.SS2), [§4.4](https://arxiv.org/html/2407.19711v3#S4.SS4), [§4.5](https://arxiv.org/html/2407.19711v3#S4.SS5) |
| 위치/탐지/종류 결과 및 본문과 표 불일치 | [P §IV-B](https://arxiv.org/html/2501.02766v2#S4.SS2), Tables II–IV |
| 의존 정보의 전처리 내재 가능성·규모 제약 해석 | [P §II](https://arxiv.org/html/2501.02766v2#S2), [§V](https://arxiv.org/html/2501.02766v2#S5) |

**검증:** DiagMLP v2 전체 본문과 HTML 표를 읽고, Table IV의 rowspan을 확장해 15개 데이터×지표 행과 9개 열의 매핑을 대조했다. `±` 및 미보고 셀을 보존하고 직접 backbone 차이를 decimal 산술로 계산했으며, Top-k 비단조 값과 본문 매핑 오류를 별도 표시했다. 표·수식·절 인용의 HTML anchor와 자료 URL 접근을 확인했다.

**하지 않은 것/남은 위험:** 모델 실행, 원자료·보호 데이터 접근, exhaustive survey, 저장소 설치·학습·커밋은 하지 않았다. 저자 코드 수준 통합·원 split identity·유의성·일반화·전체 비용은 미검증이다.
