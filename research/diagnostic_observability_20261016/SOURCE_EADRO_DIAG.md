# Eadro·DiagMLP: 원인 서비스 진단의 관측·평가 감사

2026-10-16. **관측된 구분 단서, 구조적 제약, 입증된 성능 차이를 분리한다.**
원자료·학습 없이 아래 세 로컬 자료를 먼저 읽고 유효 근거를 재사용했다.

## 출처와 확인 범위

- **[E]** Eadro v1, `https://arxiv.org/pdf/2302.05092v1`: PDF 접근 성공, §I–IV 및 §V-A/C/D/E/F/G 확인.
- **[D]** DiagMLP v2, `https://arxiv.org/html/2501.02766v2`: HTML 접근 성공, 전체 본문 확인.
- **[A]** `../native_reproduction_20261013/fidelity_audit.md`: 공개 수리 포크 `FeiGSSS/Eadro@7d69281a80adce60067aa858729746fc6a362f53`의 기존 코드 감사. 원 ICSE 구현과 동일시하지 않는다.
- **[N]** `../native_reproduction_20261013/native_models.py`: 이번 직접 읽기.
- **[R]** `../research_reset_review_20261016/REPORT.md`: 특히 §1/3/4/7–10/12/14.
- **[C]** `../mlp_prerequisites/eadro_corrected_model.py`: 이번 직접 읽기. [N]은 `load_reference`에서 Git blob SHA-1 `d0cf0560a4a2ad0f5d9814f7d6118fc6d989bbbc`를 요구한다. 이번에는 실행하지 않았다.

원문 요청은 재열기·빈 응답을 포함해 **7회**다. 기본 6회 후 논문 60/40과 포크 70/30의 상충을 확인하기 위해 허용된 추가 1회를 사용했다. 초기 PDF 도구 응답 2회는 빈 출력이었고 이후 추출에 성공했다(접근거부는 확인되지 않음). HTML 접근은 성공했다. 추가 원격 코드 조회는 없었다. DiagMLP 저자 실행본·분할 manifest 미확보는 접근 실패를 관측했다는 뜻이 아니다.

## 1. 원인과 전파 증상을 무엇으로 구분하는가?

**[1] 관측 근거:** Eadro Fig.1의 `order` 고장은 호출 사슬의 다른 서비스도 지연시킨다. 반면 §III-A/Figs.2–4에서는 CPU 고갈이 latency보다 자원 KPI에, 네트워크 장애가 latency·로그 발생 감소에 드러난다. 따라서 **가장 느린 서비스=원인**은 성립하지 않는다. [E §I/III-A] citeturn0view0

**해석:** 주입 대상의 국소 자원 변화와 호출 방향·동시 증상을 결합하면 구분 단서가 생긴다. 그러나 자원 상승·오류 로그도 전파 결과일 수 있다. 논문의 예시는 보편적인 인과 판정 규칙이나 각 오분류의 원인 증명이 아니다. 주입 정답은 관측 입력과 별개다. [E §V-E; R §1/2]

## 2. 전처리·인코더가 남기는 것과 버리는 것

**[2] 공개 포크 감사와 직접 읽은 모델 기준:**

| 경로 | 보존·변환 | 입력/표현에서 사라지는 구분 |
|---|---|---|
| `single_process.py::deal_metrics` → [C] `MetricModel` | 7개 자원·네트워크 채널의 시간열, 합성곱의 시간·채널 결합 | 전체 서비스/run 표준화로 원 단위·절대 수준이 직접 남지 않음; 학습 전용 통계가 아님 |
| `deal_traces` → `TraceModel` | 서비스별 초당 평균 span 지연 | 요청별 분포·꼬리, caller별 지연, 부모 연결·상태 코드가 해당 텐서에 없음; 계산한 호출 수도 전달되지 않고 두 번째 채널은 0 |
| `deal_logs/logHaw` → `LogModel` | Drain 템플릿별 발생 시각을 Hawkes 추정에 사용하고 baseline 벡터를 선형 임베딩 | 변수값·텍스트 의미 임베딩·원 이벤트열 및 fitted excitation 행렬은 downstream에 없음 |
| `MultiSourceEncoder/GraphModel` | Linear+GLU, 방향 그래프의 GATv2, head-max·전역 attention pooling | 개별 모달리티/서비스 표현을 압축하므로 역복원을 보장하지 않음 |

출처: [A Native input/Fairness, `preprocess/{single_process,util}.py`, `main.py::chunkDataset`; C 위 클래스]. 표준화 누출 위험과 Hawkes 상대시각/절대 horizon 불일치는 **기존 감사 결과**이며 이번 원격 재검증은 아니다.

시간축을 처음부터 평균만 내는 모델은 아니다. [C] `ConvNet` 뒤 `SelfAttention`은 **tanh 가중합** 또는 마지막 시점이며, 논문 Eq.(2)의 Q/K/V softmax와 다르다. 따라서 “논문 그대로인 Transformer attention”이라 부를 수 없다. [C `SelfAttention/MetricModel/TraceModel`; E §IV-A Eq.(2)] citeturn1view0

## 3. DiagMLP는 이미 전역 결합이다

**[3]** 모달 임베딩+위치 → Modal_Fusion → **모든 노드의 순서 있는 concat** → Node_Fusion이다. 두 fusion은 affine→LN→ReLU→Dropout이다. concat 자체는 값을 버리지 않지만 이후 유한 폭 변환은 압축한다. 고정 N·노드 위치 의존은 **구조적 제약이지 관측된 성능 결함이 아니다**. 평균대비 특징은 전역 정보의 최초 도입이 아니라 상대 비교를 명시하는 학습 편향이다. [D §III-C/D Eqs.(2)/(3); N `EquationDiagEncoder.forward`] citeturn1view1

## 4. 공개 분할 단위와 known/unseen 해석

**[4]**
- Eadro 논문: 표본은 관측 창이며, 서로 다른 기간의 자료를 train/test **60/40**, 정상·장애 및 원인 분포 유사하게 나눴다고 한다. 사건/run 배정과 purge 규칙은 명세하지 않는다. [E §II-B/V-A] citeturn0view0turn2view0
- 감사된 포크: stride-1 길이 L 창을 shuffle 후 분할, CLI test=.3. 인접 창은 L−1 관측을 공유할 수 있고 사건 ID가 소실된다. **논문 60/40과 별도**다. [A `align.py::{get_chunks,split_chunks}`]
- DiagMLP: SN train/valid/test **316/78/169**, TT **3256/813/1744**; 창 분할 누출 수정과 validation 도입을 보고한다. 정확한 창 생성·사건 그룹·시간 purge·manifest는 본문에 없다. [D §IV-A Notes, Table I] citeturn1view1

따라서 논문만으로 **사건 독립 시험**, 미지 고장 종류·새 root 서비스·새 토폴로지 일반화를 주장할 수 없다. 반대로 DiagMLP도 반드시 같은 사건을 공유한다고 단정할 수 없다. 로컬 실험의 동일 주입 사건 공유는 별도 확인 사실이다. [R §3/14]

## 5. validation과 모델 선택

**[5]** Eadro는 50 epochs 등 설정을 보고하지만 별도 validation/checkpoint 선택은 확인되지 않는다. [E §V-C] DiagMLP는 validation을 도입했으나 선택 지표·patience·seed별 선택 절차는 본문에 명시하지 않는다. [D §IV-A] citeturn2view0turn1view1

포크의 test HR@1 checkpoint 선택은 [A `base.py::fit/evaluate`]의 문제다. 이를 DiagMLP 저자의 절차로 전가하면 안 된다. 로컬 고득점도 선택에 사용한 validation 결과이지 잠근 최종시험이 아니다. [R §3/4]

## 6. 지표와 분모

**[6]** Eadro 탐지 precision/recall/F1은 장애를 양성으로 한 TP/FP/FN이다. HR@k는 창별 top-k 정답 포함 평균이며 N은 시험 표본 수다. §V-F는 Eadro의 예측 탐지와 baseline의 oracle 탐지를 구별하지만 정상 제외·탐지 누락 분모의 정확한 구현은 미명세다. NDCG 인쇄식은 k 절단·이상적 DCG 정규화가 명료하지 않아 표준 정의로 임의 보정하지 않는다. [E §V-D/F] citeturn2view0

DiagMLP는 탐지 P/R/F1과 위치 Top-k를 보고하나 SN/TT 위치 지표의 정상 제외·detector gating 분모는 본문상 미명세다. Table IV의 TT DiagMLP **Top3 99.7 > Top5 99.2**는 동일 사례·순위라면 불가능하므로 미해결 보고 모순이다. [D §IV-A/B Table IV] citeturn1view1

[A `base.py::evaluate`]는 정상 정답을 TP에 섞는 문제를 기록한다. 반면 [N `native_scores`]는 탐지 전체 창, 위치 **장애 창만**을 분모로 하고 conditional/gated Top1을 분리한다. 이는 로컬 수정 계약이지 저자 점수의 검증이 아니다. 창 수≠사건 수다.

## 7. frontend 보존과 최소 변경을 정당화하는 범위

**[7]** Eadro 자체 ablation에서는 모달리티 제거와 GAT→FC가 모두 악화됐다. 반면 DiagMLP의 10회 비교는 SN Top1 41.8→80.2%, TT 91.1→98.5%를 보고한다. **서로 다른 프로토콜의 결과**이며, 전처리도 SN/TT에서 재구현했다. frontend 보존·결합부 대조의 동기는 되지만 UMAP·분산만으로 인과 이해·GAT 과적합의 원인을 확정하지 못한다. [E §V-G Table IV; D §III-B/IV-A/B Table IV/V] citeturn2view0turn1view1

우선순위는 다음 **조건부 가설**이다.

1. 기존 임베딩에 정답 구분 단서가 있는데 결합 후 혼동이 늘어난다면, encoder·공동 목적을 고정하고 fusion만 대조한다.
2. 요청 소실이 구분 단서라면, 포크가 계산하고 버린 **호출 수 한 채널**을 우선 검토한다. 상태 코드나 caller별 지연도 필요성이 확인된 하나만 추가한다.
3. 무호출 0과 누락이 혼동된다면 관측 마스크를 검토한다. [E §IV-A의 무호출 zero padding; A `deal_traces`; C `TraceModel`]

이는 아직 성능 개선 근거가 아니다. [N]의 수식 복원은 GLU와 그래프/pooling까지 교체한다. [D]의 “GNN만 교체” 서술과 Eq.(2) 사이에 GLU 경계가 미해결이므로 **GAT만 바꾼 저자 실행본**이라고 부르지 않는다. [A Fusion boundary; N `NativeReference.__init__`]

## 8. 원시 진단 없이는 결론낼 수 없는 것

**[8] 미확인:** 오답에서 원인보다 전파 서비스가 얼마나 자주 높게 순위화되는지, 평균 지연이 숨긴 꼬리·요청량·오류 상태가 실제 구별력을 갖는지, 누락/정렬/정규화가 오차를 얼마나 설명하는지, fusion 전후 어디서 단서가 약화되는지, 새 사건에서 개선되는지는 모른다. [2–7의 제한에서 도출]

필요 근거는 사건·시간 provenance, 실제 split/선택 기록, 입력 누락률, 서비스별 원관측과 예측 순위, 모달리티/결합 전후 진단이다. **특정 신호가 표현에 없다는 사실과 그 누락 때문에 틀렸다는 주장은 다르다.**

검증: 원문·로컬 코드 경로 대조와 문서 범위 확인. 미실행: 학습, 원격 코드 실행, telemetry 열람, 데이터 다운로드·설치·clone·subagent. 개선 효과와 정확한 저자 재현은 주장하지 않는다.
