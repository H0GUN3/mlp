# 원인 서비스 순위: 방법론과 최소 비교군

## 1. 결론과 범위

**핵심 비교군은 `DiagMLP(Eadro backbone)`과 `Eadro` 두 가지다.** 동일한 전처리·모달 encoder·학습 목적·task head를 유지하면서 모델링 구간의 차이를 묻는 가장 직접적인 쌍이다. 필요하면 **BARO를 세 번째, 비학습 통계 보조 기준**으로 추가한다. TVDiag와 DeepHunt는 관련 방법론을 확인하되, 현재의 한 구성요소 질문에 필수인 전체-framework 비교군으로 늘리지 않는다.

목표는 **장애가 발생했다는 조건에서, 고정된 후보 서비스 inventory의 root-service 순위를 산출하는 것**이다. CPU·메모리·네트워크 장애는 평가 조건이지 연구 도메인 변경이 아니다. 관측이 없더라도 후보를 삭제해 문제를 쉽게 만들지 않는다. 가변 노드·미학습 서비스 일반화는 이번 개선 목표가 아니다.

기존 `relationship_diagnosis_20261014/COMPARATORS.md`의 shortlist는 출처·비용 계약을 참고했다. 그 문서의 DiagMLP→BARO→Eadro 우선순위는 통계 기준까지 포함한 좌표 설정이고, 여기서는 **동일 backbone 구성요소 비교**를 우선해 Eadro를 핵심 쌍으로 올린다. 성능 재측정에 따른 순위 변경이 아니다. DiagMLP의 정확한 식·수치 표는 별도 `DIAGMLP.md` 담당 범위다.

## 2. Fault injection과 diagnosis의 구분

- **Fault injection:** CPU hog, 메모리 압박/고갈, network delay·packet loss 등으로 지정한 위치·시점에 장애를 발생시키는 실험 조작이다. Chaosblade·Chaos Mesh는 이 조작을 수행하는 도구이지 root-service 순위 모델이 아니다. Eadro §V-A2는 Chaosblade로 CPU exhaustion, network jam, packet loss를 주입한다. **Eadro 실험에 메모리 주입도 있었다고 확대하지 않는다.** TVDiag 공식 README는 자체 benchmark에 Chaos Mesh를 사용했다고 밝힌다. [E1, T2]
- **Diagnosis:** 발생한 장애의 metric/log/trace 등을 이용해 원인 후보를 점수화·순위화한다. 주입 도구가 알고 있는 위치는 평가 정답이지 진단 입력이 아니다. 진단 시점에 제공할 onset과 관측 창도 방법 간 동일하게 고정한다.

| 진단 클래스 | 핵심 메커니즘 | 이번 비교에서의 역할 |
|---|---|---|
| 통계적 score | 정상 참조 구간 대비 분포·편차 변화로 metric/service 점수 산출 | BARO가 보조 기준. root 라벨로 학습하는 다중모달 모델과 같은 계열이 아니다. |
| 인과/토폴로지 graph | 인과관계 추정 또는 호출·배치 graph 위에서 관계·전파를 분석하여 ranking | 클래스 수준 설명만 한다. 호출 edge나 GNN attention을 인과관계가 입증된 edge로 부르지 않는다. |
| 학습형 다중모달 fusion | 모달별 전처리/embedding, fusion, 학습한 모델링·ranking head | Eadro/TVDiag/DeepHunt와 DiagMLP 교체 baseline이 직접 조사 대상. graph 사용과 이 클래스는 상호배타적이지 않다. |

위 클래스 설명의 좁은 원문 근거는 BARO §2.4와 DiagMLP §II다. 별도 AIOps 전면 survey는 수행하지 않았다. [B1, D]

## 3. 직접 비교 가능한 학습 방법론

| 방법·과제 적합성 | 입력·전처리/embedding | 모델링·supervision/head | 접근 가능한 구현과 충실도 | 비용 경계·선택 이유 |
|---|---|---|---|---|
| **DiagMLP(Eadro backbone)**: 지도 root localization; Eadro와 같은 downstream task를 유지하는 교체 실험 | **Eadro의 전체** metric/log/trace 전처리·encoder를 보존. 일반적인 작은 MLP에 임의 feature를 넣는 baseline이 아님 | 위치 embedding과 modal/node fusion MLP로 기존 모델링 구간을 교체. task objective/head는 backbone과 동일하게 유지해야 함 | 논문 §III–IV가 교체 계약. 원문은 SN/TT 전처리를 저자가 재구현했다고 명시한다. 로컬에는 방정식 기반 복원·공통입력 adaptation이 있지만, 그것을 저자 통합 artifact로 부를 수 없음 | 전처리/encoder 비용도 보존한 채 교체 구간과 전체 pipeline 비용을 각각 기록. **가장 가까운 중심 baseline** [D] |
| **Eadro**: anomaly detection+root localization 공동 학습; 조건부 ranking은 별도 추출 가능 | Drain→로그 event occurrence의 Hawkes→FC; KPI와 trace latency 시계열→DCC/선택적 attention; historical invocation graph | 서비스별 concat→Linear+**GLU**→GAT/attention pooling→FC detector와 고정 후보 localizer. 정상/장애 및 root label 공동 목적 | 저자 원 repository의 보존 소스와 repair fork를 구분. 로컬 provenance에 원 `MainModel` 이름/인자 오류와 fork synthetic smoke가 기록되어 있음. 공개 코드 접근 가능 ≠ 이번 데이터에서 실행·재현 완료 | log parsing/Hawkes, 시간 정렬·normalization, temporal encoder, graph, 학습·추론 모두 포함. **DiagMLP의 동일 backbone 대조군** [E1–E3, L1] |
| **TVDiag**: 장애 검출 후 instance root ranking+failure-type identification. 서비스 단위와 매핑 계약 필요 | metric 3-sigma, trace Isolation Forest, 로그 Drain+ERROR/저빈도 규칙→alert; 모달별 fastText feature; trace 기반 양방향 correlation graph | 모달별 GraphSAGE→node/graph feature. root label 기반 metric/trace contrastive, type label 기반 log contrastive, cross-modal contrastive, 두 task 공동 학습. **공유 node MLP→scalar→후보 softmax**가 RCL head | 공식 code 공개; 확인 revision `cf6f334887036f363807bac1b8995c3b6f47c5db`. 공개 README와 arXiv v3의 dataset 범위를 하나의 동일 artifact로 단정하지 않음. 실행 미검증 | alert extractor·fastText 학습과 type label 예산을 빼면 불공정. 단순 fusion·공유 scorer 신규성 확인에는 필수 참고, **전체 성능 비교는 선택** [T1–T3] |
| **DeepHunt**: instance root ranking; microservice 외 VM 등도 포함하므로 후보 범위 조정 필요 | trace 평균 latency/**request count**/status frequency; Drain log template occurrence; metric 1분 resampling/interpolation; sliding-history z-score→concat; 호출+배치 System Behavior Graph(SBG) | GAE reconstruction self-supervision+feature masking; 시간별 reconstruction error를 FC1로 집계, upstream/downstream 최대 anomaly를 GA로 집계, 공유 FC2로 ranking. zero-label 초기화와 root feedback ranking-loss fine-tuning은 별도 모드 | 공식 code와 preprocessed artifact 안내 공개. source revision `ec414bc7dd213034bd0f3fa34ef16b4dac47aaa2`. D2 raw는 NDA라는 README 설명; 전처리본 공개와 raw 공개를 혼동하지 않음. 논문은 GraphSAGE이나 이 revision의 그 이름을 가진 encoder/decoder는 `dgl.nn.GraphConv` 사용 | SBG/feature 준비+GAE pretraining+feedback 비용·라벨 예산을 분리. 감독·head가 다른 **선택적 전체-framework 비교** [H1–H3] |
| **BARO**: metric/service ranking, 비신경 통계 기준 | multivariate metric 시계열; latency/error의 BOCPD onset 탐지; 정상 median/IQR 대비 이상 편차 | RobustScorer metric 점수→service 순위; root-label supervision·MLP parameter 수 없음 | 공식 `0.2.0` code 공개. 논문 abs 편차와 code signed-max 차이가 직접 확인됨. 서비스 집계·후보 유지 계약은 별도 명시 필요 | 알려진 onset scorer-only와 BOCPD 포함 전체 비용 구분. 학습형 fusion 개선의 대조군이 아니라 **보조 좌표** [B1–B2] |

**고정 후보 문제와 양립하는 사용법:** TVDiag/DeepHunt의 instance 출력을 서비스로 집계할 경우 사전 고정한 instance→service mapping과 aggregation이 필요하다. 이 mapping 없이 원문 instance accuracy를 root-service accuracy로 읽지 않는다. 현재 주질문은 Eadro의 고정 후보 head를 유지하므로, 가변 노드 head로 변경할 필요가 없다.

## 4. 최소 비교 계약: MLP 이름·parameter 수만 맞추면 안 되는 이유

1. **구성요소 질문:** Eadro-compatible 전처리·encoder·head·objective·후보 순서·split을 고정하고 DiagMLP 교체 구간 및 제안할 단일 변경을 비교한다. 어느 GLU/fusion/pooling까지 교체하는지는 별도 DiagMLP 분석의 경계 계약을 따른다. 일부 모듈을 더 바꾸고 “GNN만 교체”라고 하지 않는다.
2. **전체 방법 질문:** 각 framework의 native 입력, 전처리, 학습 목적과 head를 보존한 결과다. TVDiag의 alert/contrastive/type-label 학습, DeepHunt의 정상 pretraining/feedback를 제거해 공통 feature MLP와 맞추면 **adaptation 실험**이지 원 방법 전체 비교가 아니다.
3. **동일 정보·라벨 예산:** 같은 incident·후보·root 정답·query window를 사용한다. fit/tuning은 TRAIN/validation에 제한하고 incident별 묶음 split으로 인접 창 누수를 막는다. 추가 관측상태 feature를 평가한다면 양쪽 architecture에도 동일한 정보를 제공하는 대조가 필요하다. type label·정상 학습자료·operator feedback의 사용량도 공개한다.
4. **동일 질문·측정:** fault-conditioned ranking과 detector-gated end-to-end 결과를 분리한다. incident 동등 가중 Top-1/Top-k/MRR와 사전 고정한 동점 처리, 정상화/로그 전처리/encoder/학습/새 사건 추론의 시간·메모리를 보고한다. BARO는 metric→service 집계와 원 code signed-score/논문 abs-score 중 무엇을 평가하는지 고정한다.
5. **parameter/epoch는 보조 지표:** 원 입력·pretrained/temporal encoder·graph 정보·loss/head·label budget이 다르면 같은 “MLP” 명칭이나 parameter 수가 같은 비교를 보장하지 않는다. 강한 backbone을 로컬 작은 MLP 크기로 축소하거나 동일 epoch만 강제하면 용량·수렴 차이가 섞인다. validation 선택 예산을 명시하고, 교체 모듈 크기와 전체 학습 가능한 parameter를 나눠 기록한다.

**로컬 부분-feature 모델은 출판된 DiagMLP/Eadro가 아니다.** `MODEL_PROVENANCE.md`의 공통입력 adaptation은 원 metric/log/trace encoder·Hawkes·joint head를 재현하지 않는다. 짧은 로컬 학습 성능, 희소 trace, omitted-log 한 창 관측을 원 DiagMLP/Eadro의 성능 결함으로 전가하지 않는다. 이 worker는 그 관측자료·실험 결과를 재조회하지 않았다. [L1]

## 5. 좁은 관측상태 점검: 결측과 정상 저활동은 구별되는가?

다음 세 상태를 같은 말로 취급하지 않는다.

- **정상 저활동:** collector는 동작하지만 실제 요청/로그가 적거나 없음.
- **관측 불능/누락:** collector 중단·sampling·전송 누락 등으로 활동을 관측하지 못함.
- **alert 없음:** 수집은 되었어도 threshold·로그 필터를 통과한 이상 event가 없음.

request count나 occupied-second 비율은 **관측 support**이지 그 자체로 collector availability의 증거가 아니다. count=0만으로 정상 무요청과 수집 장애를 판별할 수 없다. collection-state를 쓰려면 별도의 실제 측정 근거가 있어야 하며, root label이나 주입 위치로 만든 indicator는 금지한다.

| 방법 | 원문/소스에서 확인한 관측 표현 | 증거가 허용하는 결론과 허용하지 않는 결론 |
|---|---|---|
| **Eadro** | 논문 §IV-A3: slot별 callee 평균 latency, invocation 없는 slot을 0 padding. §IV-B2: concat+Linear+GLU. pinned fork parser의 `deal_traces`는 latency와 count dictionary `invok`를 모두 만들지만, `align.get_chunks`는 **`traces["latency"]`만** 저장. `MultiSourceEncoder.forward`는 traces/logs/metrics만 소비. [E1–E3] | 이 공개 경로에서 **trace support count가 모델 입력에 전달되지 않는 것은 code-established**. GLU는 이미 있으나 버려진 count를 trace만으로 복원할 수 있는 명시적 계약은 없음. 다른 모달이 보완할 수 있으므로 ranking 오류·전체 pipeline 정보 부재·모든 Eadro 구현의 결함을 증명하지 않음. |
| **DiagMLP** | §III-A/C: 이미 만들어진 세 모달 embedding을 받아 concat·fusion. embedding pipeline은 제한하지 않고 backbone에 의존. [D] | DiagMLP 자체가 모든 pipeline에서 count/availability를 버린다는 주장은 불가능. Eadro-backbone 특정 경로 문제와 architecture 자체를 구별한다. 명시적 관측상태 계약 부재는 **명세/평가 gap**이지 정확도 결함이 아님. |
| **TVDiag** | §4.3: non-root node/edge를 drop하여 불완전 관측을 모사. §5.3은 augmentation ablation, §5.5는 모달 feature와 관련 module 전체 제거 실험. 공식 fastText encoder는 빈 alert sentence를 **zero vector**로 출력; `MainModel`은 모달 feature를 encode/concat하고 별도 collection availability를 읽지 않음. [T1–T3] | **불완전 관측 robustness가 이미 연구됐다.** 빈/모두 미등록 token의 문장과 정상 no-alert는 확인한 encoder 경로에서 0이 될 수 있다. 그러나 no-alert가 곧 low traffic은 아니다. node 자체의 존재/부재 정보는 graph에 남을 수 있고 embedding에는 alert 정보도 있으므로 “결측을 전혀 구별 못함”은 과장. 모달 제거 재학습은 동일 후보를 유지한 사건별 수집 누락 구별을 직접 입증한 실험이 아님. |
| **DeepHunt** | §4.2.1에 request count·status frequency가 이미 포함됨. §4.3.2 feature masking으로 data absence 모사. code `data_aug`는 feature/node 값을 zero로 바꾸고 **`(g,z)`만 반환**. sliding z-score의 0은 평균 수준 값이기도 함. §6.2는 불완전 모달과 observability 저하를 논의. [H1–H3] | “count 추가”·“결측 feature masking”은 여기서 새로운 아이디어가 아니다. 이 masking 함수가 별도 mask indicator를 전달하지 않는 것은 code-established; 다만 실제 입력 feature에 숨은 quality 신호가 없다고 dataset 미확인 상태에서 단정하지 않는다. 결측 대 정상 저활동 구별의 정확도 결함은 미입증. |
| **BARO** | metric 변화 score가 중심이며 cross-modal fusion/availability head는 없음. [B1–B2] | 정상 reference·유효 sample 처리 계약이 필요하나, 이번 source 확인만으로 실제 결측 취약성을 주장하지 않는다. 같은 fusion 문제를 푸는 중심 모델로 선택하지 않는다. |

### 공개 Eadro fork의 trace 정보 경로: 부모의 추가 질문에 대한 직접 답

revision **`7d69281a80adce60067aa858729746fc6a362f53`**에서 다음 경로를 직접 읽었다.

1. `parse_raw_traces.py::parse_spans`: startTime을 초 단위로 내리고 `duration / 1_000_000`을 서비스·초별 list로 보존한다. **spanID deduplication이나 unique-span count 생성은 이 함수에 없다.**
2. `single_process.py::deal_traces`: `(windows, nodes, seconds, 2)`를 0으로 초기화한다. list 길이로 `invok` count를 누적하고, 채널 0에 서비스·초별 `np.mean(...)`을 넣는다. 채널 1에는 값을 쓰지 않는다. 이후 **서비스별 모든 chunk의 채널 0에 `z_zero_scaler`를 적용**한다. 따라서 “span 없는 slot은 모델 입력에서도 언제나 0”이라고 쓰면 부정확하다. 원래의 padding 0도 표준화된다.
3. 반환·cache 객체에는 `{"invok": ..., "latency": ...}`가 모두 존재한다. 그러나 `align.py::get_chunks`는 `chunks[id]["traces"] = traces["latency"][idx]`만 취한다. count가 계산조차 안 된 것이 아니라 **후속 chunk 구성에서 count가 제외된 것**이다.
4. `model.py::TraceModel`은 두 채널 ConvNet을 사용하고, attention을 쓰지 않을 때 마지막 temporal hidden을 반환한다. `MultiSourceEncoder`는 trace/log/metric embedding concat→Linear+GLU로 진행한다. **별도 count·coverage·availability 입력은 확인한 경로에 없다.**

이로써 **동일한 서비스·초별 mean-duration 시계열에 서로 다른 span multiplicity가 대응할 수 있다는 구조적 정보 손실**이 확인된다. 같은 mean 배열을 같은 조건으로 표준화해도 count는 되살아나지 않는다. 다만 graph·metric·log까지 모두 동일하다고 증명한 것은 아니다.

부모가 전달한 “10초 창, 10ms span 10개와 100개의 동일 mean-latency 입력” synthetic witness는 **부모의 로컬-only 관측**이며 이 worker가 실행한 실험이 아니다. 공개 parser를 그대로 실행하거나 native reconstruction의 표준화·중복 처리까지 검증한 결과로 확대하지 않는다. 우리 `native_data.py`의 channel0 mean/channel1 zero 설명도 **선언된 로컬 복원 선택**으로 구분한다. [E2–E3]

## 6. 한계의 근거 강도와 부모 합성에 필요한 경고

| 주장 | 증거 수준 | 이번 설계에 주는 의미 |
|---|---|---|
| DiagMLP node concat의 parameter가 후보 수에 따라 증가 | **논문 보고**: §III-D가 직접 명시 | 사실이지만 이번 고정 inventory의 핵심 실패 원인으로 선택하지 않음. DeepSets/SetTransformer는 원문이 이미 제시한 미래 방향. |
| GNN의 추가 이득이 제한적일 수 있음 | **논문 보고**: DiagMLP의 보존-pipeline ablation 범위 | 전체 연구 분야에서 graph가 쓸모없다는 정리도, 우리 데이터에서 재현한 결론도 아님. |
| Eadro trace 지원 count가 모델 입력에서 빠짐 | **공개 코드 확인**: parser→aggregation→chunk→encoder | 변경할 좁은 경로는 존재. 정보 손실을 ranking 성능 손실과 동일시하지 않음. |
| Eadro source만으로 원 실험 전체를 재현하기 어려움 | **코드 확인+기존 로컬 provenance** | 원 보존 source의 오류와 repair fork를 구별하고 변경 provenance를 기록. 논문 모델의 정확도 결함이 아니라 재현 artifact 경계. |
| TVDiag는 불완전 관측과 모달별 역할을 이미 다룸 | **논문 보고+공개 코드 확인** | 단순 node-drop/modal-aware learning/공유 scorer를 새로 제안하지 않음. 완전 모달 제거와 사건별 수집상태 구별은 다른 질문. |
| DeepHunt는 count·masking·공유 scorer·ranking loss를 이미 사용 | **논문 보고+공개 코드 확인** | 이들을 추가하는 것만으로 신규성 주장 불가. supervision 및 artifact 구조도 Eadro와 다름. |
| partial-feature omitted-log 또는 sparse-trace 로컬 사례 | **우리 로컬-only 관측**: 부모 제공, 이번 worker 재검증 없음 | 개발 진단의 신호일 뿐 출판 모델 한계의 근거 아님. |
| 관측상태 metadata 보존이 root ranking을 개선 | **미검증 가설** | source/명세 점검만으로 채택·성능 주장 불가. 동일 후보·입력 계약 아래 baseline 오류와의 연결을 먼저 확인해야 함. |

### 이미 있는 모듈: 재발명하지 않을 것

- **로그 추가·다중모달 concat:** Eadro/TVDiag/DeepHunt의 기존 구성.
- **일반 modality gating:** Eadro §IV-B2의 Linear+GLU가 선행 구성. TVDiag의 dynamic weight는 **task/contrastive loss weight**이지 사건별 collection-quality gate와 동일하지 않다.
- **관측 누락 모사·feature/node masking:** TVDiag §4.3, DeepHunt §4.3.2 및 code에 존재.
- **서비스/노드 공유 scorer:** TVDiag §4.5의 scalar-output MLP, DeepHunt §4.4의 공유 FC1/FC2에 존재.
- **시간/이웃 pooling·ranking-aware supervision:** DeepHunt에 이미 존재. DiagMLP의 scalability용 set/pooling 교체도 원문이 제시한 방향과 겹친다.
- **traffic/request count 추가:** DeepHunt가 이미 활용한다. Eadro-compatible 평균-latency 경로에서 누락된 support를 보존하는 것은 가능한 작은 변경이지만, 새로운 일반 진단 원리라고 포장하지 않는다.

**합성에 넘길 한 후보:** 고정 후보 inventory·head를 그대로 두고 **Eadro-compatible trace 집계에서 관측 support/실제 collection-state의 명시적 보존**이 필요한지 검토할 수 있다. 독립적인 collection-state 근거가 없다면 occupied seconds/count를 “availability”로 이름 붙이지 말고 “observed support”로 제한한다. unique-span count는 현재 공개 parser의 값이 아니므로 deduplication 정의도 필요하다.

이 후보는 기존 마스킹/GLU/count 활용을 무효화하지 않는다. 현재 근거는 **좁은 입력 계약과 평가의 빈틈**까지이며, 신규성·효과는 아직 미확정이다. 원 baseline 오류가 동일 입력의 저-support 조건에 연결되지 않거나 기존 count/masking만으로 설명되면 후보를 기각/축소해야 한다. baseline에 동일 정보를 제공한 비교 없이 gains를 architecture 개선이라 주장하지 않는다. 최종 하나의 개선 선택·모듈 설계·정량 기각 기준은 부모의 합성 범위다.

### 부모의 잠정 q 설계에 대한 선행 구성요소 대조

부모가 전달한 `q_i = [log1p(unique span identity count), occupied-second ratio]`를 retained embedding과 함께 DiagMLP modal fusion 전에 넣는 안은 **observed-support 표현 기여 가설**로 이해한다. 입력 정보를 늘리는 비교이지 동일 정보의 architecture 우월성 주장이 아니다. 고정 후보·graph·node fusion·head를 유지하고 충분히 학습한 native-like baseline의 해당 오류가 없으면 중단한다는 경계와 양립한다.

- **Eadro/DiagMLP(Eadro 경로):** 확인한 공개 fork에는 이 두 값을 명시적인 q로 전달하는 경로가 없다. 다만 `invok` count는 중간 산출물에 이미 있고 chunk 구성에서 빠진다. 따라서 가장 정확한 설명은 “이 경로에서 버려진 support 정보의 보존/재도입”이다.
- **DeepHunt:** §4.2.1의 **분당 request count**가 q의 첫 항과 정보 의미상 상당히 겹친다. unique identity deduplication·초별 occupancy·동일한 log1p 변환을 명시한 것은 확인하지 못했으므로 **완전히 같은 q가 이미 있다고 단정하지 않는다.** 그러나 변환·집계 해상도 차이만으로 “진단에 support count를 처음 사용”이라는 신규성은 성립하지 않는다. §4.3.2의 absence masking도 선행 구성이다.
- **TVDiag:** 확인한 alert template/fastText/encoder/head에 동일한 명시적 q는 없었다. 그래프 node-drop robustness와 zero no-alert feature는 별도 메커니즘이다. 일반적인 “관측 불완전성 대응”의 최초 제안은 아니다.
- **occupied-second ratio 주의:** 모든 실제 duration이 양수라면, **표준화 전** Eadro의 zero-padded mean-latency 배열에서 nonzero slot 비율로 occupancy를 계산할 수 있다. 이 경우 두 번째 항은 raw 표현에 전혀 없던 독립 정보가 아니라 encoder 압축 이전에 이미 유도 가능한 요약이다. encoder 이후 충분히 보존되는지는 미검증이다. 표준화된 값을 단순히 `!=0`으로 세면 이 의미가 유지되지 않는다.
- **unique count 주의:** 공개 parser는 spanID를 보존·deduplicate하지 않으므로 현재 `invok`는 unique span 수가 아니다. `(traceID, spanID)` 등 identity 정의, 중복 및 재수집 처리, 서비스·창별 할당 계약이 먼저 필요하다. count/occupancy 둘 다 collector availability와 정상 저활동을 그 자체로 구별하지는 못한다.

따라서 q 안은 기존 선행연구 때문에 **무조건 중복이라 기각할 단계도, 새롭다고 확정할 단계도 아니다.** 좁게 남는 질문은 “Eadro-compatible mean-latency 집계/embedding에서 지원 정보를 명시적으로 보존하는 것이 같은 후보의 오류를 줄이는가”이다. count만·occupancy만의 역할과 traffic량 대리변수 설명도 분리해야 한다. 부모의 추가 `2h` parameter 통제는 용량 대안을 다루지만, 입력 의미와 count 선행연구의 중복을 대신 해결하지 않는다.

## 7. 일차 출처와 확인 경계

논문은 아래 **5편**, 각 방법의 공식 source와 명시한 Eadro repair fork만 사용했다. 검색은 TVDiag/DeepHunt 원문·공식 repository 위치 확인에 한정했으며 추가 framework 문헌을 늘리지 않았다.

- **[D] DiagMLP** — *Are GNNs Actually Effective for Multimodal Fault Diagnosis in Microservice Systems?*, arXiv v2. [§III-C/D](https://arxiv.org/html/2501.02766v2#S3.SS3), [§IV-A: pipeline 보존과 source 전처리 재구현](https://arxiv.org/html/2501.02766v2#S4.SS1). numerical tables는 별도 분석에 맡겼다.
- **[E1] Eadro** — *An End-to-End Troubleshooting Framework for Microservices on Multi-source Data*, ICSE 2023. [§IV-A: Hawkes/DCC/trace 0-padding](https://arxiv.org/html/2302.05092v1#S4.SS1), [§IV-B: Linear+GLU와 graph](https://arxiv.org/html/2302.05092v1#S4.SS2), [§IV-C: 공동 head](https://arxiv.org/html/2302.05092v1#S4.SS3), [§V-A2: 주입 조건](https://arxiv.org/html/2302.05092v1#S5.SS1.SSS2). 저자 공식 repository: [BEbillionaireUSD/Eadro](https://github.com/BEbillionaireUSD/Eadro).
- **[E2] 공개 repair fork 전처리, 고정 revision** — [span parser](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/parse_raw_traces.py), [deal_traces](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py), [get_chunks](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/align.py).
- **[E3] 공개 repair fork 모델** — [TraceModel/MultiSourceEncoder/MainModel](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/model.py). fork의 구조적 증거를 저자 private integration이나 모든 DiagMLP backbone의 계약으로 일반화하지 않았다.
- **[T1] TVDiag** — *A Task-oriented and View-invariant Failure Diagnosis Framework for Microservice-based Systems with Multimodal Data*, arXiv **v3**. [§4.1–4.2: alert/embedding](https://arxiv.org/html/2407.19711v3#S4.SS1), [§4.3: 관측 비활성화 augmentation](https://arxiv.org/html/2407.19711v3#S4.SS3), [§4.4: contrastive](https://arxiv.org/html/2407.19711v3#S4.SS4), [§4.5: 공유 scalar RCL scorer](https://arxiv.org/html/2407.19711v3#S4.SS5), [§5.3: augmentation](https://arxiv.org/html/2407.19711v3#S5.SS3), [§5.5: 모달 제거](https://arxiv.org/html/2407.19711v3#S5.SS5). DiagMLP가 참조한 당시 version과 현재 v3 결과·artifact를 동일시하지 않았다.
- **[T2] TVDiag 공식 repository** — [README](https://github.com/WHU-AISE/TVDiag).
- **[T3] TVDiag 고정 source** — [MainModel](https://github.com/WHU-AISE/TVDiag/blob/cf6f334887036f363807bac1b8995c3b6f47c5db/core/model/MainModel.py), [fastText empty-sentence 처리](https://github.com/WHU-AISE/TVDiag/blob/cf6f334887036f363807bac1b8995c3b6f47c5db/process/events/fasttext_w2v.py). EventProcess와 Voter도 읽었고, 핵심 두 파일은 main에서 읽은 내용과 pinned revision이 동일함을 대조했다.
- **[H1] DeepHunt** — *Interpretable Failure Localization for Microservice Systems Based on Graph Autoencoder*, TOSEM 34(2), article 52; 확보한 PDF 표기는 January 2025. [DOI](https://doi.org/10.1145/3695999), [저자 소속 연구실 PDF](https://nkcs.iops.ai/wp-content/uploads/2025/07/deephunt.pdf). §4.2는 pp.9–10, §4.3.2는 pp.10–11, §4.4–4.5는 pp.11–14, §5.3–5.5는 pp.18–21, §6.2는 p.23.
- **[H2] DeepHunt 공식 repository** — [README: 데이터/비용 단계](https://github.com/bbyldebb/DeepHunt).
- **[H3] DeepHunt 고정 source** — [noise_engineering](https://github.com/bbyldebb/DeepHunt/blob/ec414bc7dd213034bd0f3fa34ef16b4dac47aaa2/models/noise_engineering.py), [encoder/decoder/loss](https://github.com/bbyldebb/DeepHunt/blob/ec414bc7dd213034bd0f3fa34ef16b4dac47aaa2/models/layers.py), [RCScorer](https://github.com/bbyldebb/DeepHunt/blob/ec414bc7dd213034bd0f3fa34ef16b4dac47aaa2/models/rc_scorer.py).
- **[B1] BARO** — *Robust Root Cause Analysis for Microservices via Multivariate Bayesian Online Change Point Detection*, FSE 2024. [§2.4: 클래스](https://arxiv.org/html/2405.09330v1#S2.SS4), [§3.3–3.4: BOCPD/RobustScorer](https://arxiv.org/html/2405.09330v1#S3.SS4).
- **[B2] BARO 공식 0.2.0** — [robust_scorer](https://github.com/phamquiluan/baro/blob/0.2.0/baro/root_cause_analysis.py): 정상 RobustScaler fit 후 이상 값의 **signed max**, 논문 abs 식과 구별.
- **[L1] 로컬 provenance** — `research/mlp_prerequisites/MODEL_PROVENANCE.md`와 보존된 `eadro_model.py`를 읽었다. `COMPARATORS.md`는 기존 범위·출처 출발점이며 원논문을 대신하지 않는다.

**검증 범위:** 핵심 원문 section과 위 source의 연결을 읽어 비교했다. 길게 잘린 TVDiag 후반부는 HTML을 메모리에서 section별로 추출해 확인했고, DeepHunt PDF는 메모리에서 해당 페이지 text를 추출했다. Eadro/BARO 웹 결과 전체는 잘렸으나 이 보고서에서 사용한 앞부분의 지정 method section·알고리즘은 확인했다. 문헌 수치 재계산, 원/native pipeline 실행, 실제 ranking 오류·비용·새 metadata 효과, 원자료/보호 관측자료 조회는 **하지 않았다**. dataset 다운로드·설치·학습·추가 agent·프로젝트 commit 없이 `METHODS.md`만 작성했다.
