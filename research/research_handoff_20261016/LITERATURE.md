# 논문별 조사: 무엇을 문제로 삼았고, 어떻게 검증했는가

2026-10-16 기준. [연구 전체 흐름](REPORT.md)과 함께 읽는다.
아래 수치는 **각 저자가 자기 평가 조건에서 보고한 값**이다. 우리 실험 결과가 아니다.
`D1/D2`, `TT`, `GAIA`라는 이름이 같아도 논문별 자료·후보·분할이 같다는 뜻이 아니다.
인용된 연구와 실제 실행 비교군도 구분한다. 원문 미확보 항목은 별도 표시했다.

## A. 중심 비교 연구

### [S02] Eadro — 다중 관측과 탐지·위치 진단의 결합

Cheryl Lee 외, **Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data**, ICSE 2023, 1750–1762. 분석본 arXiv v1.

- **배경·문제:** trace만으로 드러나지 않는 자원 장애, 전파된 증상, 선행 탐지 오류가 위치 진단에 미치는 영향을 함께 다룬다.
- **처리:** 로그 Drain→Hawkes→FC; 지표·평균 trace latency→인과 convolution·attention; 모달 concat→GLU→호출 그래프 GAT·pooling→탐지/원인 head. 두 목적을 공동 학습한다.
- **자료:** TT 전체41/업무27서비스, SN 전체21/업무14서비스. Chaosblade CPU 고갈·지연·패킷 손실. 보고된 주입은 TT162/SN72회, 시기별 train/test 60/40. 운영 장애 표본이 아닌 주입 benchmark다.
- **비교·선정 이유:** 탐지는 TraceAnomaly/MultimodalTrace, 위치 진단은 TBAC/NetMedic/MonitorRank/CloudRanger/DyCause. 입력 정보량 차이를 줄이기 위해 MS-RF/SVM/LSTM/DCC를 추가했다. 관련연구는 로그·KPI·trace 탐지와 통계/그래프 위치 진단을 구분한다.
- **결과·한계:** TT/SN HR@1 .990/.974; GAT 제거 .803/.791. Eadro 자체에도 그래프 제거 대조가 있다. 일부 비교군은 실제 장애 유무를 제공받지만 Eadro는 detector 결과를 쓰므로 순수 조건부 ranking과 다르다. 주입 범위 밖 논리 장애·라벨 비용·현장 일반화는 한계다.
- **우리 역할:** DiagMLP와 같은 입력 계열의 그래프 기준. 원 점수를 맞추는 것이 아니라 처리·공동학습을 보존한다.

원문 §IV, §V-A/B, Tables II–IV, §VI–VII:
`https://arxiv.org/html/2302.05092v1`
공식 자료: `https://github.com/BEbillionaireUSD/Eadro`
DOI: `10.1109/ICSE48619.2023.00150`.

### [S03] DiagMLP — 복잡한 그래프 연산의 추가 기여를 묻는 대조

Fei Gao 외, **Are GNNs Actually Effective for Multimodal Fault Diagnosis in Microservice Systems?**
ICWS 2025 출판 기록(127–129, WIP)이 있다. 아래 분석은 **6쪽 arXiv v2(2025-03-10)** 기준이며, 3쪽 출판본과 동일하다고 단정하지 않는다.

- **문제·방법:** 기존 성능의 원인이 전처리/인코더인지 GNN인지 구분한다. 기존 앞단과 과제 head를 유지하고, 모달 벡터+학습형 위치벡터→Modal Fusion→전체 노드 concat→Node Fusion으로 교체한다. 각 fusion은 Linear→LayerNorm→ReLU→Dropout이다.
- **실제 교체:** Eadro·TVDiag·DeepHunt. DiagFusion·CHASE는 문헌 비교군이다. 비GNN 방법 전체와 경쟁하기보다 구성요소 기여를 조사하려는 선정이다.
- **관련연구:** 전처리(Drain 등), 표현학습(TCN/FastText 등), 그래프 모델링을 분해한다. DeepSets/Set Transformer는 확장 대안이지 이 논문의 실행 모델이 아니다.

| 자료 | instance 수 | train/valid/test 표본 | 교체 대상 | Top1: 교체 전 → DiagMLP (%) |
|---|---:|---|---|---:|
| SN | 12 | 316/78/169 | Eadro | 41.8±14.5 → 80.2±3.1 |
| TT | 27 | 3256/813/1744 | Eadro | 91.1±2.2 → 98.5±0.8 |
| GAIA | 10 | 128/32/939 | TVDiag | 59.8±0.8 → 61.0±1.0 |
| D1 | 46 | 63/—/147 | DeepHunt | 79.8±0.4 → 79.8±1.0 |
| D2 | 18 | 40/—/93 | DeepHunt | 78.9±0.7 → 79.0±0.5 |

±는 표준편차이며 해당 행은10회 반복이다. SN/TT 전처리 재구현과 분할 누수 위험 수정이 보고됐다.
Table IV의 TT Top3 99.7>Top5 99.2, D1 본문의 비교 대상 오류는 미해결이다.
따라서 **모든 GNN보다 우수하다는 근거가 아니다.** 전체 노드를 함께 보므로 관계정보를 전혀 이용하지 않는 모델도 아니다.

원문 §III, Tables I/IV: `https://arxiv.org/pdf/2501.02766v2`
출판 DOI: `10.1109/ICWS67624.2025.00025`;
공식 WIP 프로그램: `https://services.conferences.computer.org/2025/wp-content/uploads/sites/3/2025/07/SERVICES_webprogram7-5.pdf`.

## B. 중심 연구와 연결되는 다중모달·통계 방법

### [S04] TVDiag — 위치와 장애 종류에 필요한 정보를 구분

Shuaiyu Xie 외, **TVDiag: A Task-oriented and View-invariant Failure Diagnosis Framework for Microservice-based Systems with Multimodal Data**. 분석본 arXiv v3, 2025-03-21. 원고의 placeholder 출판정보는 정식 서지로 사용하지 않았다.

- **문제·방법:** 모달을 무차별 결합하면 과제별 정보 차이가 사라진다는 문제를 다룬다. 지표/trace/log alert→FastText→모달별 GraphSAGE, 과제 지향·모달 간 대조학습, 정상 노드 관측 비활성화 augmentation. 출력은 원인 **인스턴스**와 장애 종류다.
- **자료:** A=GAIA(5서비스/10인스턴스/5유형), B=AIOps22(10/40/9; instance 장애113건 선택), C=Sock Shop(14/21/7; Chaos Mesh). C는 CPU·메모리·네트워크·pod 관련 주입이다. 이 숫자는 논문 Table3 분석 대상 기준이다.
- **비교·이유:** RCL은 DiagFusion/Eadro/RF-RCL/MicroRank/TraceRCA/MicroRCA/MicroHECL. 일반 관측자료에 적용 가능하고 소스 코드 침습이 필요 없는 방법을 선택했다. FTI 비교는 별도로 한다.
- **관련연구·우리 시사점:** 단일모달과 다중모달을 구분하고 DiagFusion의 조기 결합, Eadro의 중간 결합과 대조한다. 공유 scorer·관측 masking·모달별 학습은 이미 선행 구성이다. 단순 추가만으로 신규성을 주장하지 않는다. root/type 라벨과 전처리 비용을 맞추지 않으면 우리 기준과 직접 비교할 수 없다.

§4, §5.1/Table3, §6: `https://arxiv.org/html/2407.19711v3`
공식 구현: `https://github.com/WHU-AISE/TVDiag`.

### [S05] DeepHunt — 정상 학습과 운영자 피드백을 결합한 순위

Yongqian Sun 외, **Interpretable Failure Localization for Microservice Systems Based on Graph Autoencoder**, ACM TOSEM 34(2), Article52, 2025. DOI `10.1145/3695999`.

- **문제·방법:** 장애 라벨 부족과 결과 해석을 다룬다. 지표·로그·trace latency/request count/status→호출·배치 그래프→정상자료 graph autoencoder 재구성. 본인/상하류 이상과 시간별 재구성 오차로 순위를 만들고 root 피드백 ranking loss로 보정한다. feature masking도 사용한다.
- **자료:** D1은 모의 전자상거래46인스턴스(서비스40+VM6), 정상3714/장애210; 실제 고장 패턴 replay. D2는 은행18인스턴스, 정상12297/장애133; 2021년1–6월 기록을 운영자2명이 검토. 장애 분할은 시간순30/70. D2 raw는 NDA다.
- **비교·이유:** 비심층 MicroHECL/MicroRank/AutoMAP/TraceRCA/Microscope/RCD와 지도 DéjàVu/Eadro/DiagFusion을 비교해 학습·자료 계열을 함께 평가한다. zero-feedback와 피드백 사용 성능을 섞으면 안 된다.
- **관련연구·우리 시사점:** 통계/그래프 순위와 지도 진단을 연결한다. count·masking·공유 점수기·ranking loss가 이미 존재한다. 출력에는 VM 등이 포함되므로 업무 서비스27개 문제와 그대로 같지 않다. request count는 중복 제거한 span 수와 정확히 같은 정의가 아니다.

§4, §5.1/Table2, §6.2:
`https://nkcs.iops.ai/wp-content/uploads/2025/07/deephunt.pdf`
구현: `https://github.com/bbyldebb/DeepHunt`.

### [S06] BARO — 정상 대비 변화로 만드는 단순 통계 기준

**BARO: Robust Root Cause Analysis for Microservices via Multivariate Bayesian Online Change Point Detection**, PACMSE/FSE 2024, DOI `10.1145/3660805`.

- **문제·방법:** 부정확한 장애 시작시각에 민감한 RCA를 다룬다. 다변량 BOCPD로 변화점을 찾고 정상 median/IQR 대비 편차로 metric을 정렬한 뒤 서비스 순위로 변환한다. root 라벨로 학습하는 신경망이 아니다.
- **자료:** Kubernetes의 Online Boutique12/Sock Shop11/Train Ticket64서비스, CPU·메모리·지연·손실 주입. Eadro의 TT27후보 자료와 다른 배포/자료다.
- **비교·이유:** CausalRCA/RCD/CIRCA, ε-Diagnosis/N-Sigma, Dummy로 인과추정과 통계검정 계열을 비교한다. 변화점 탐지와 원인 순위, 실제 onset 제공과 검출 onset 조건을 나눠 평가한다.
- **관련연구·우리 역할:** “복잡한 모델이 단순한 이상 편차보다 나은가”를 확인할 보조 기준이다. 다중모달 fusion의 직접 대조는 아니다. 논문의 절대편차 식과 공개0.2.0 코드의 signed-max 차이, service 집계 규칙을 명시해야 한다. Avg@5를 Top1처럼 읽지 않는다.

§2.4, §3–4: `https://arxiv.org/html/2405.09330v1`
구현: `https://github.com/phamquiluan/baro/tree/0.2.0`.

### [S07] DiagFusion — 서로 다른 관측을 공통 event로 표현

Shenglin Zhang 외, **Robust Failure Diagnosis of Microservice System through Multimodal Data**,
IEEE Transactions on Services Computing16(6),3851–3864,2023.
DOI `10.1109/TSC.2023.3290018`. 방법·수치는 arXiv:2302.10512v2 분석 기준이다.

- **문제·방법:** 자료 이질성과 라벨 부족을 다룬다. 세 모달을 event로 통일하고 event embedding·증강, 배치/호출 그래프와 topology-adaptive convolution으로 서비스 그룹/장애 종류를 학습한다. 그룹 내 인스턴스를 추가 순위화한다.
- **자료:** GAIA 계열 D1은 표 기준17인스턴스, train/test160/939; 은행 D2는 표 기준18인스턴스,80/79. 시간순 분할이다. D2 본문은14인스턴스라고 써 표와 다르다. DeepHunt의 D1/D2와 동일 자료로 합치지 않는다.
- **비교·선정:** 위치는 MicroHECL/MicroRank/AutoMAP/MS-Rank/PDiagnose, 종류는 Cloud19/LogCluster/CloudRCA. 모달별 대표 방법과 다중모달을 비교하되 지원 과제별로 나눴다.
- **결과·관련연구:** Table IV 위치 A@1은 D1 .419/D2 .646. 관련연구는 단일/다중모달로 구성된다. **모달 결합은 이미 선행연구의 중심 아이디어**이며 우리 신규성 자체가 아니다. 그룹→인스턴스 출력과 추가 type 라벨이 우리 단일 서비스 head와 다르다.

§IV–V, Tables II/IV, §VII: `https://arxiv.org/html/2302.10512v2`.

### [S08] CHASE — 모달 이질성과 여러 노드에 걸친 관계

Ziming Zhao 외, **CHASE: A Causal Heterogeneous Graph based Framework for Root Cause Analysis in Multimodal Microservice Systems**. 여기서는 DiagMLP가 참조한 시기의 **arXiv v1(2024)**을 검토했다. 후속 제목/판본과 혼합하지 않는다.

- **방법:** instance/log/metric 이종 노드→attention message passing→호출 경로 hyperedge→hypergraph convolution→instance별 점수. 쌍별 관계만으로 부족하다는 문제 설정이다.
- **자료:** GAIA10인스턴스/1099표본(학습160), AIOps2020의68주입장애. 후자는 동적 trace를 다룬다.
- **비교·선정:** PC/GES, CloudRanger/MicroRCA, CausalRCA/TrinityRCL/DiagFusion으로 인과탐색·상관·GNN 계열을 비교한다. 관련연구도 비GNN/GNN으로 나눈다.
- **결과·한계:** GAIA A@1 .6135/A@3 .8823. AIOps2020의 Percentage@n은 시간 구간의 이상 trace 비율이지 원인 서비스 Top1이 아니다. “causal”이라는 명칭만으로 개입 검증을 마친 인과그래프가 되지 않는다. DiagMLP에서는 실제 교체 대상이 아닌 문헌 비교군이다.

§III, §IV-A/TableII: `https://arxiv.org/html/2406.19711v1`.

## C. 기존 중심 목록 밖의 해외 관련 연구

### [S01] Groot — 실제 운영에서의 원인 조사 우선순위

Hanzhang Wang 외, **Groot: An Event-graph-based Approach for Root Cause Analysis in Industrial Settings**, ASE 2021.

- **문제·방법:** 서비스 상태·변경 등 서로 다른 원인 단서를 event로 만들고 운영자의 규칙과 연결해 event graph에서 원인을 정렬한다.
- **자료·결과:** eBay 약5000서비스 환경, 15개월 동안 수집하고 라벨링한 실제 운영952사건. Top1 78%, Top3 95%.
- **비교·관련연구:** 단순 service PageRank와 비적응 event-rule 변형을 비교한다. 이벤트 지식과 기존 그래프 RCA의 차이가 핵심이다.
- **우리 의미:** 실제 조사 우선순위 문제의 존재를 뒷받침한다. 출력이 원인 event이고 복수 원인의 단일 정답 선정도 있어, 우리 서비스 순위와 성능을 직접 비교하지 않는다.

§V/Tables III–IV: `https://arxiv.org/html/2108.00344v2`
학회 기록: `https://conf.researchr.org/details/ase-2021/ase-2021-papers/60/Groot-An-Event-graph-based-Approach-for-Root-Cause-Analysis-in-Industrial-Settings`.

### [S09] MicroHECL — 전파 방향을 따라 후보를 줄이는 산업 연구

Dewei Liu 외, **MicroHECL: High-Efficient Root Cause Localization in Large-Scale Microservice Systems**, ICSE-SEIP 2021.

- **문제·처리:** 부정확한 탐지와 큰 호출 그래프 탐색 비용. latency/error/QPS의 유형별 이상을 탐지하고 방향별 전파·상관 pruning으로 root 서비스와 이상 종류를 추천한다.
- **자료:** Alibaba 실제 장애75건(2020년2–6월),28개 하위시스템, 평균265서비스. 별도 온라인 적용은600여사건이다.
- **비교·이유:** 당시 위치 진단 방법인 MonitorRank/Microscope. 관련연구는 로그 탐지, 시각적 진단, trace 및 의존 그래프 분석으로 구분한다.
- **결과·한계:**75건 HR@1 .48/HR@3 .67/MRR .58. reliability detector에는 라벨1000학습/400검증 표본을 사용하므로 완전 비지도라 부르면 안 된다. 이 detector 표본과75진단사건은 다른 단위다. 단일 기업, 관측에 나타나지 않는 장애는 한계다.
- **우리 의미:** 서비스 순위가 실제 운영 과제라는 직접 근거. 단순 GNN 대 MLP 비교와는 다른 탐지·탐색 방식이다.

§IV–VII, Tables III–V: `https://arxiv.org/pdf/2103.01782`.

### [S10] TraceRCA — 장애 라벨 없이 trace 차이를 활용

Zeyan Li 외, **Practical Root Cause Localization for Microservice Systems via Trace Analysis**, IWQoS 2021. DOI `10.1109/IWQOS52092.2021.9521340`.

- **문제·처리:** 장애 라벨 의존성과 고정 전파 가정. 다중 invocation 지표의 이상→이상 trace→FP-growth 의심 서비스 집합→support/confidence 기반 점수·전파 민감 순위.
- **자료:** Train-Ticket41서비스/200주입사례(잘못된 응답·CPU·지연, 다중 원인11건 포함), ISP13서비스/22제공 장애. ISP22건의 자연발생/주입 구분은 확인한 본문에서 불명확하다.
- **비교·이유:** MicroScope/TraceAnomaly/MEPFL-RF/Random Walk/RCSF로 지도·비지도 및 trace/invocation 계열을 비교한다. 지도 비교는 **같은 장애 안의 trace20/80 분할**이다.
- **결과·한계:** 두 자료 A@1 .82/.88, 지도 MEPFL .92/.94. 따라서 모든 지도 모델을 이긴다는 연구가 아니다. 별도 은행 적용은 사례 보고이며 코호트 정확도가 아니다.
- **우리 의미:** 라벨 예산이 다른 비교 축. 동일 장애 내부 trace 분할을 새로운 장애 일반화로 해석하지 않는다.

§IV/Tables I–IV, §V–VI:
`https://netman.aiops.org/wp-content/uploads/2021/05/1570705191.pdf`
구현: `https://github.com/NetManAIOps/TraceRCA`.

### [S11] MicroRCA — 지표와 서비스·호스트 그래프

Li Wu 외, **MicroRCA: Root Cause Localization of Performance Issues in Microservices**, NOMS 2020. DOI `10.1109/NOMS47738.2020.9110353`.

- **문제·방법:** frontend 증상만으로 backend 자원 장애를 놓칠 수 있다. 서비스 간 latency·컨테이너/호스트 metric→BIRCH 탐지→이상 부분그래프→상관 가중 personalized PageRank로 서비스 순위를 만든다.
- **자료:** Sock Shop13서비스, 기능 서비스7개 주입 대상,95사례. `tc` 지연과 `stress-ng` CPU/메모리,5초 수집. 운영 사건 평가가 아니다.
- **비교·이유:** random/MonitorRank/Microscope. 알고리즘 유사성과 같은 benchmark 사용을 근거로 골랐고, 탐지기를 공통 적용하여 위치 진단을 비교한다. 관련연구는 log/trace/metric 방식이다.
- **결과·한계:** 저자 precision89%/MAP97%; 우리 사건 Top1과 같지 않다. 소규모·단일 replica 조건, graph 상관은 인과 증명 아님.
- **우리 의미:** 경량 지표/그래프 대조 가능성. 호스트 노드를 쓰더라도 최종 서비스 후보 계약을 확인해야 한다.

원고 §II–V: `https://hal.inria.fr/hal-02441640/document`
HAL 접근 제한으로 동일 원고 mirror를 검토:
`https://scispace.com/pdf/microrca-root-cause-localization-of-performance-issues-in-c2prqbtonz.pdf`
공식 코드: `https://github.com/elastisys/MicroRCA`.

### [S12] CausalRCA — 서비스와 세부 metric 진단의 구별

Ruyue Xin 외, **CausalRCA: Causal inference based precise fine-grained root cause localization for microservice applications**, JSS203,111724,2023. 분석은 저자 arXiv 원고 기준.

- **문제·방법:** 서비스만 찾는 것보다 세부 자원 원인을 찾고 싶다는 문제. latency/resource metric→gradient 기반 weighted DAG 학습→역방향·절대 가중 그래프 PageRank.
- **자료:** Sock Shop13서비스/기능7서비스, Pumba CPU·메모리·지연 주입.5분 주입/10분회복/5초관측;10회 모델 반복.
- **비교·이유:** PC/GES/LiNGAM에 동일 PageRank를 붙여 그래프 학습 선택을 비교한다. 관련연구는 통계·토폴로지·인과 방법과 인과발견 계열이다.
- **결과·주의:** 서비스 AC@1 .20/AC@3 .5749와, **원인 서비스 안에서의 metric** AC@3 .719를 구분해야 한다. 후자를 서비스 찾기 정확도로 인용하지 않는다.
- **우리 의미:** root 단위와 조건부 평가를 명확하게 해야 하는 근거. 관측자료에서 학습한 DAG는 개입 검증된 인과 정답이 아니다.

§III-C–IV/TableIII: `https://arxiv.org/pdf/2209.02500`
출판 DOI: `10.1016/j.jss.2023.111724`.

### [S13] LatentScope — 관측 metric과 실제 원인 리소스의 차이

**Microservice Root Cause Analysis With Limited Observability Through Intervention Recognition in the Latent Space**, KDD2024.

- **문제·방법:** 관측 metric 하나가 실제 원인 resource 하나와 일치하지 않는 제한적 관측. 원인 후보를 latent variable로 두고 metric 잔차와 리소스 관계를 이용해 개입 위치를 식별한다.
- **자료:** eBay66실제사건/300여서비스 및 Online Boutique11서비스/88주입사건. 후자는 service/pod/host 혼합 원인이다.
- **비교·관련연구:** RandomWalk/MonitorRank/Microscope/CloudRanger/MicroCause/CIRCA/TrinityRCL 계열. metric 출력 비교군은 연결된 metric 최대점수로 resource 점수를 만든다. 회귀 기반 CIRCA에서 latent resource로 문제를 확장한 위치에 있다.
- **우리 의미·한계:** 이상 metric을 찾는 것과 원인 서비스를 찾는 것을 동일시하지 않게 한다. AnoProp의 직접 선행이며, resource mapping이 없는 우리 자료에 바로 적용할 수 있다고 단정하지 않는다.

§3, §4.1, Appendix:
`https://netman.aiops.org/wp-content/uploads/2024/07/LatentScope_CameraReady_final.pdf`
공식 코드: `https://github.com/eBay/LatentScope`.

### [S14] LagRCA — 전파의 시간차를 명시한 최근 산업 연구

Shenglin Zhang 외, **Bridging the Delay: Lag-Aware Spatio-Temporal Causal Inference for Microservice Root Cause Analysis**, FSE2026 Industry 공식 프로그램 확인.

- **실측 문제:** 은행146사건에서 root와 영향 instance 사이 최대 이상 시작시간 차이가1분이하27건,2–5분94건,6분이상25건.1분 관측 해상도다.
- **방법:** trace+metric, 정상 예측학습, 여러 시차의 시공간 attention, upstream에서 전달된 이상을 보정한 instance 순위.
- **자료·비교:** D1 은행46인스턴스/146사건; D2 Online Boutique41인스턴스/161주입. BARO/DyCause/CauseLens/RCD/MicroCause/CausalRCA로 통계·시간/인과 계열을 비교한다. 상세 파라미터 공정성은 독립 검증하지 않았다.
- **결과:** D1 AC@1 .667/AC@5 .858; D2 .519/.883. 별도 Alibaba 적용과 은행 D1은 같은 자료로 합치지 않는다.
- **우리 의미·한계:** 실제 전파 시간차를 다룬 선행연구. TT의 오답도 이 때문이라는 증거는 아니다. 코드의 prefix-match 판정, instance→service 관계, 시간/validation 분할 확인이 필요하다.

§3/Table1, §5–6:
`https://netman.aiops.org/wp-content/uploads/2026/04/fse2026-industry-paper77.pdf`
공식 구현: `https://github.com/kjhjk566/LagRCA`
공식 행사 프로그램:
`https://conf.researchr.org/details/fse-2026/fse-2026-industry-papers/18/Bridging-the-Delay-Lag-Aware-Spatio-Temporal-Causal-Inference-for-Microservice-Root-`
행사일은7월5–9일이며 원고 머리말6월 표기와 다르다.

### [S19] PRISM — 그래프 없는 내부·외부 관측 구분

Luan Pham, **Graph-Free Root Cause Analysis**, arXiv:2601.21359v1,2026-01-29 preprint.

- **문제·방법:** 다른 곳에서 전파된 외부 증상과 원인 내부 상태를 구분한다. 정상/장애 편차를 계산하고 내부 자원·외부 인터페이스 속성을 각각 pooling한 뒤 결합 점수로 component를 정렬한다. MLP가 아니라 통계적 방법이다.
- **자료·비교:** RCAEval9자료/735benchmark 장애(RE1 375/RE2 270/RE3 90), OB/SS/TT. BARO/ScoreOrdering/Cholesky/PC-PageRank와 구조가 제공되는 Counterfactual/RCLAgent/Traversal/SmoothTraversal을 비교한다.
- **결과·한계:** 저자 평균Top1 .68(BARO .19), 약8ms diagnosis time.735자연발생 운영사건이 아니며, 우리 환경의 전처리 포함 비용도 아니다. 보장에는 관측 충분성·내부→외부 방향·외부를 통한 서비스간 영향 등의 가정이 있다. 증명 자체는 독립 검증하지 않았다.
- **우리 의미:** “피해 서비스의 외부 지연과 원인의 내부 자원 구별”, “graph-free 경량 순위”는 이미 가까운 선행이다. 공식 실행 artifact는 이번 범위에서 검증하지 못했다.

§2–4/Tables1–2/AppendixE: `https://arxiv.org/html/2601.21359v1`.

### [S20] Controlled MLP / PSC-GRCA — 상대 특징·prior·그래프의 통제

Imad Buljić, **Does Graph Structure Earn Its Place in Microservice Root-Cause Analysis? A Controlled Study on RCAEval, and What the Benchmark Was Really Measuring**, arXiv:2609.27069v1,2026-09-22 preprint. 정식 학회 채택은 확인하지 않았다.

- **문제·설계:** 성능이 그래프 메시지 전달, 입력 특징, 학습 대상 빈도 중 무엇에서 오는지 분리한다. GNN/no-neighbor 비교와 flat MLP, random/root-frequency/max-deviation/BARO를 둔다. flat MLP에도 사건 내 상대 rank 정보가 이미 들어간다.
- **자료·결과:** 주분석은RE1 375주입/3시스템,6fold 및3개 held-out-system fold. GNN/MLP Avg@5 .867/.864(p=.844,n=6)는 동등성 증명이 아니다. prior·telemetry·graph residual을 분리한PSC .915, prior-free .850. 이 점수를Top1처럼 읽지 않는다.
- **관련연구·한계:** graph 기여 통제와 benchmark prior 편향을 함께 다룬다. “PSC RE2”로 표시했던 이전 실행은 실제RE1이었다며 철회했다. **PSC 근거는RE1 한정**이며 별도의RE2 topology 연구까지 철회된 것은 아니다. 일부 ablation은 재학습 없이 같은 모델에서 점수화한다.
- **우리 의미:** 작은 MLP·상대정보·prior 분리는 가까운 선행이므로 단독 신규성 주장이 어렵다. 공식 코드/manifest 존재는 확인했지만 실행하지 않았다.

§3–6/§10: `https://arxiv.org/html/2609.27069v1`
저자 공개 원고·코드: `https://github.com/Buljic/kintsugi-rca/tree/15f9a862e4b656c765860bcf1f8486a726883ae9`
저자 연결 metadata: `https://zenodo.org/records/22832168`.

## D. 국내 발표 및 국내 소속 연구자의 국제 발표

국내 여부는 한국어 초록이나 이름이 아니라 **발표처와 확인한 소속**으로 구분했다.

### [S15] AnoProp — 국내 학술지, 공유 자원으로 인한 이상 전파

박준호·황지영(KAIST 전산학부), **자원 공유에 따른 이상치 전파를 활용한 마이크로서비스 시스템 결함의 근본 원인 분석**, 정보과학회논문지52(4),341–349,2025.

- **문제·방법:** 자원을 공유하는 대상의 관측 이상이 단순 원인 점수를 왜곡할 수 있다는 문제. 회귀 잔차와 공유 관계의 전파 점수를 결합한다.
- **자료:** Online Boutique11서비스/32pod/2node,1976metrics,88주입사건.1분 수집; 정상은 탐지120분전부터10분전. 장애 구간은 원문 표현상 **“결함 탐지 전후10분”**이며 정확한 양끝 시각은 별도 명세하지 않았다. 주입 고장 기법 목록은 본문에서 확인되지 않았다.
- **비교·이유:** MonitorRank/CloudRanger/RandomWalk/Microscope/MicroCause/CIRCA/TrinityRCL/LatentScope. 기존 graph 탐색·회귀와 특히 공유자원 처리의 추가 효과를 비교한다. 관련 흐름은 **CIRCA→LatentScope→AnoProp**이다.
- **결과·한계:** micro Hit@1 .4625/MRR .6367. service/pod/node 혼합 순위이므로 우리 서비스 Top1과 직접 비교 불가. 동점 처리·개별 평가 분모는 추가 확인 사항이며 성적에서 정수 정답건수를 역산하지 않는다.
- **우리 의미:** 새 점수 모듈을 만들기 전에 반드시 대조할 국내 선행. 단순히 “이상 전파를 고려한다”는 주장은 새롭지 않다.

§3–5, Table1: `https://bdi-lab.kaist.ac.kr/assets/pdf/domestic_kiise2025.pdf`
KCI: `https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003194718`
KCI DOI `10.5626/JOK.2025.52.4.341` 사용; 저자PDF DOI suffix와 불일치한다.

### [S16] HERO — 국내 소속의 국제 학회 poster; 초록만 확인

Juyoung Yang, EunChan Park, KyeongDeok Baek, In-Young Ko(KAIST),
**Troubleshooting Microservices with Heterogeneous Graph Neural Network**,
ICWE2025 poster, LNCS15749,374–378. 온라인2025-10-12, KAIST 서지는2026 표기를 사용한다.

- **확인된 문제·방법:** 복잡한 의존성과 root 라벨 의존성. 이종 GNN과 설명기법으로 탐지/위치 진단을 통합하며 **root-cause 라벨 없이 학습**한다는 주장이다. 모든 종류의 라벨이 불필요하다는 뜻은 아니다.
- **미확인:** dataset 이름·사건수·split·정확한 출력 단위·실제 비교군·점수. 출판사 preview와 연구실까지 확인했으나 원문을 확보하지 못했다.
- **관련연구 경계:** 참고문헌의 Eadro/Microscope/ε-diagnosis/GAMMA를 실제 실행 baseline이라고 단정할 수 없다.
- **우리 의미:** 라벨 비용과 이종 그래프 방향의 관련 후보. 본문 없이 직접 비교 대상으로 확정하지 않는다.

출판사: `https://link.springer.com/chapter/10.1007/978-3-031-97207-2_30`
연구실 poster 분류: `https://webeng.kaist.ac.kr/international-conferences/`.

### [S17] GRAFlow — 국내 소속 참여 국제 공동연구; 수치 해석 주의

Shuangshi Zhao, Kunming Liu 외, **Graflow: A Microservice Anomaly Detection Method Based on Cross-Modal Feature Fusion and Multi-Scale Graph Attention Networks**, JAISCR16(4),343–366,2026.
Zhao/Liu의 아주대 소속과 중국 기관 공동저자 소속을 확인했다. 온라인2026-06-29/발행10-01.

- **방법·자료:** 모달 간 attention과 다중 scale 그래프 attention. Drain3 로그·지표·서비스 latency를10초 창으로 정렬하여 탐지와 서비스 위치를 학습한다. TT27업무서비스/41인스턴스, SN14/21; CPU·지연·손실 주입.
- **비교:** 탐지 표에는 TraceAnomaly/MultimodalTrace, RF/SVM/LSTM/DCC 계열, LogAnomaly/SCWarn/AnoFusion/STEAD/DySAT/EvolveGCN/Eadro가 있다. 위치 비교군 전체와 선택 근거는 별도 미확인이다.
- **한계:** publisher metadata와 논문 mirror를 구분했다. mirror의 표들에 F1 및 ablation 수치 불일치가 있어 성능 우위를 근거로 채택하지 않았다. split/사건 독립성도 미확인이다.
- **우리 의미:** 모달 결합·전파 범위 개선의 최근 인접 연구. “국내에서 관련 연구가 없다”는 주장은 부적절하지만, 강한 직접 baseline으로 바로 선정할 근거도 부족하다.

출판사/소속: `https://reference-global.com/article/10.2478/jaiscr-2026-0017?tab=authors`
검토 mirror: `https://www.researchgate.net/publication/408255369_Graflow_A_Microservice_Anomaly_Detection_Method_Based_on_Cross-Modal_Feature_Fusion_and_Multi-Scale_Graph_Attention_Networks`.

### [S18] KubeIn — 국내 인접 연구; Kubernetes resource 진단

성찬민·최광미·김남호(호남대학교), **Dependency Graph와 LLM을 결합한 쿠버네티스 장애 근본 원인 자동 분석 시스템**, 한국전자통신학회논문지21(03),1273–1282,2026. **KCI 초록만 확인**했다.

- **문제·방법:** 추가 관측 agent 없이 Kubernetes API13종 resource snapshot→dependency graph→DFS 원인·역방향BFS 영향범위→RAG/LLM 보고서.
- **자료·비교:** Sock Shop20주입시나리오. Hybrid/DFS-only/LLM-only를 비교하나 이는 진단 보고서 품질 비교도 포함한다. 기존 service-ranker와의 비교로 바꿔 읽지 않는다.
- **결과·한계:** Top1 100%는 **탐지 가능한10개**에 한정된다. 전체20개 성공률이 아니다. 장애 종류·split·세부 출력단위·관련연구 전개는 본문 미확보로 미확인이다.
- **우리 의미:** 운영 진단 도구의 인접 연구지만, 현재의 고정 서비스 후보 순위 baseline에서는 제외한다.

KCI: `https://kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003357552`.

## E. 공통 해석 규칙과 조사 범위

1. **인과·상관:** 그래프 edge, attention, residual이 있다는 사실만으로 원인관계가 실험적으로 입증되지는 않는다.
2. **데이터명:** Eadro-TT27후보와 BARO-TT64서비스는 같은 관측 자료가 아니다. DeepHunt-D2와 DiagFusion-D2도 선택 사건이 다르다.
3. **정답 단위:** 서비스/인스턴스/metric/pod/node/event 순위와 장애 종류 분류를 구분한다.
4. **정보 예산:** root/type 라벨, 정상 자료, operator feedback, 배치 정보, 원인 onset 제공 여부를 맞춰야 한다.
5. **수치:** Top3, Avg@5, MRR, NDCG, 조건부 탐지가능 표본 정확도를 같은 지표처럼 비교하지 않는다.
6. **현장 근거:** Groot/MicroHECL/일부 은행 자료는 실제 운영 사건이며, TT/Sock Shop/Online Boutique 주입과 근거 수준이 다르다.
7. **범위:** 핵심2편과 직접 인접 연구, 추가 해외·국내 연구를 선정한 조사다. 전 분야의 전수 목록이나 서지계량 systematic review는 아니다.
8. **접근 제한:** MicroRank의 독립 전문, HERO/KubeIn 전문은 미확보. QROOT/TransTVDiag는 검색 후보 수준이므로 상세 실험 및 중심 결론에 사용하지 않았다.

이 문헌 조사는 새 모델의 이름을 정하기 위한 것이 아니다.
**우리에게 확인된 오류를 어떤 기존 방법도 이미 다루고 있는지, 무엇을 통제해야 실제 추가 효과를 주장할 수 있는지** 판단하기 위한 것이다.
