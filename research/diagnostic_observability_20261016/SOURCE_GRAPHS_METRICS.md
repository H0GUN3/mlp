# 그래프는 무엇을 처리하고, 지표는 무엇을 맞혔는가?

2026-10-16. 기존 `../research_reset_review_20261016/REPORT.md`를 읽었으며, 자료 획득·공개 여부는 반복하지 않는다. 아래 **원문 사실**과 **판단/도출**을 구분한다. 새 실험·데이터 접근은 하지 않았다.

## 1. TVDiag: 관측 그래프의 지도학습

**원문 사실.** 노드는 서비스 **instance**, 간선은 trace의 호출쌍을 **양방향화**한 관계다. alert가 노드인 그래프가 아니다. 노드에는 모달별 alert 임베딩을 붙인다. metric은 지표명·증감 방향, trace는 caller·operation·비정상 코드/지연, log는 Drain logKey를 담는다. 추출기는 각각 3-sigma, Isolation Forest, ERROR/저빈도 규칙이다.[T §4.1–4.2, Table 1]

세 GraphSAGE encoder가 모달별 이웃 정보를 결합하고, max-pooling으로 그래프 표현을 만든다. 학습 정답은 사건의 **원인 instance와 고장 종류**다. 과제별 대조학습은 metric/trace를 원인 정답으로, log를 종류 정답으로 묶는다. 교차모달 대조학습은 같은 사건의 metric–trace, metric–log를 정렬한다. 두 예측 head의 cross-entropy까지 네 손실을 동적 가중한다.[T §4.4–4.5, Algorithms 1–2, Eqs. 7–13]

```text
TVDiag [T §4, Fig.10]
metric / trace / log -> alerts -> instance 그래프 [A <-> B <-> C]
                                      |
                              모달별 GraphSAGE
                         +------------+------------+
                     노드 표현                  max-pool 표현
                  공유 MLP -> 순위             MLP -> 고장 종류
```

추론은 새 관측에 같은 추출·그래프·encoder·head를 적용한다. 원인 head는 instance마다 점수를 내고 전체 softmax로 순위를 만든다. 사건을 검색하는 단계는 없다.[T §4, §4.5]

## 2. DeepHunt: 정상 특징 재구성과 원인 순위

**원문 사실.** 분 단위 System Behavior Graph(SBG)의 노드는 **서비스 instance와 host instance**, 간선은 호출·배치 의존성이다. 방향 그래프이며 저자 표기 `(vi,vj)`는 `vj`가 `vi`를 호출하거나 그 위에 배치되어 의존함을 뜻한다. 단순 caller→callee 도식과 간선 표기를 혼동하면 안 된다.[D §2.1, §4.2.3]

노드 특징은 분별 trace 지연·요청수·상태코드 빈도, 묶은 log template 빈도, metric 시계열을 sliding-window z-score로 표준화·결합한 값이다. 정상 기간 SBG로 GNN encoder/decoder를 학습하며, MSE 정답은 **입력 노드 특징**이다. 여기서 재구성은 미지 간선·인과 그래프 복원이 아니다.[D §4.2–4.3, §5.2]

```text
DeepHunt [D §4.3–4.5]
정상 SBG -> GNN encoder -> latent -> GNN decoder -> 특징 복원(MSE)
장애 SBG -----------------------^
                   -> 노드별 재구성 오차
                   -> FC1(시간) -> GA(자신/상류/하류) -> FC2 -> 순위
                                              ^
                              운영자 원인 정답 -> ranking loss
```

상·하류는 1-hop 오차의 max를 사용한다. **zero-label 초기화는 시간 균등가중, 이웃 가중 0**이므로 처음부터 전파정보를 적극 사용하는 것은 아니다. 피드백으로 공유 점수 가중치를 보정한다.[D §4.4.2–4.5, Table 1]

### 탐지를 범위 밖에 둔 이유

- **저자가 명시한 근거:** 장애 탐지는 연구 범위 밖이며, 이미 사용할 수 있는 방법들이 있다고 설명한다.[D §2.3, p.52:6]
- **해석:** 탐지를 별도 구성요소에 맡기고 위치 진단에 집중한 범위 설정으로 읽힌다. 이것은 저자의 추가 동기 진술이 아니다.
- **말할 수 없는 것:** “DeepHunt는 RCA를 못한다”가 아니다. 시작·종료 시각 탐지의 불가능성이나 정확도를 입증한 것도 아니다. TVDiag 역시 장애가 탐지된 뒤의 진단을 문제로 정의한다.[D §2.3; T §2.3]

## 3. 원래 GraphRAG와 일반 검색·재정렬

**원문 사실.** Microsoft 원논문은 문서에서 entity와 relationship을 추출한다. 노드에는 이름·유형·설명, 관계에는 양끝·설명이 있으며, 인덱스는 관계 출현수 기반 가중치의 **무방향 그래프**다. Leiden 계층 커뮤니티를 요약하고, 질의마다 커뮤니티별 답을 생성한 뒤 helpfulness로 정렬·통합한다. RCA 정답으로 GNN/MLP/reranker를 학습하는 논문이 아니다.[G §2.1–2.6]

```text
원래 GraphRAG [G §2]
문서 corpus -> entity--relationship -> Leiden -> 커뮤니티 요약
질의 ---------------------------------------> 부분답 -> 통합답

일반 검색+재정렬 설계 [아래는 비교용 개념도, 세 논문의 공통 구조 아님]
현재 사건 + 검색 corpus/인덱스 -> 후보 C_k -> reranker -> 최종 순위
                                             |
                                    MLP를 점수기로 쓸 수도 있음
```

**구분:** GNN 처리는 그래프 이웃의 표현 결합, 재구성은 입력 복원, 그래프 검색은 인덱스에서 후보/근거 선택이다. MLP는 점수 함수이지 그 자체로 검색은 아니다. 세 논문의 그래프·전파·추출 관계를 **개입으로 식별된 인과관계의 증명**으로 바꾸어 읽으면 안 된다.[판단: T §4; D §4; G §2]

## 4. 같은 F1도 같은 과제가 아니다

| 지표·대상 | 정의·평균 | 실제 보고 범위 |
|---|---|---|
| 탐지 F1: 정상/장애 판정 | `2TP/(2TP+FP+FN)`; 창·시점·사건 중 단위와 매칭 규칙 필요 | T/D/G의 해당 평가에는 없음.[T §5.1; D §5.1.3; G §3.4] |
| 종류 F1: 사건의 고장 종류 | 종류별 F1의 macro, 전체 TP 집계 micro, support 가중 평균은 서로 다름 | T가 precision/recall/F1 보고. **macro/micro/weighted는 원문에 명시되지 않아 확정 불가.** D/G는 미보고.[T §5.1, Table 5; D §5; G §3.4] |
| MRR: 원인 instance 순위 | 사건별 역순위 평균. T의 `MRR@k=mean(1[rank<=k]/rank)`는 cutoff 밖 0 | T는 **MRR@3**, HR@1/3, Avg@3. D는 MRR 대신 A@1/3/5, Avg@5.[T Eqs.14–16, Table 4; D Eqs.4–5, Table 3] |
| set recall: 복수 정답 집합 G | 사건별 `|Top-k∩G|/|G|` 후 사건 평균; 전체 집계는 별도 명시 | 세 논문 모두 이 평가를 보고하지 않는다. 하나라도 맞는 any-hit와 다름.[T §5.1; D §5.1.3; G §3.4; 정의는 본 문서] |

T/D 순위 평가는 정답 instance의 포함 여부를 사건 균등으로 평균한다. `Avg@k`는 `HR/A@1…k`의 평균이지 MRR이 아니다. D는 실행 5회 평균도 명시한다.[T Eqs.14–16; D §5.1.3–5.1.4]

**원문 불일치:** T §5.1 도입은 NDCG를 언급하지만 Eq.16·§5.2·Table 4는 MRR@3다. 실제 보고 지표는 후자를 따른다.

G는 문서 전역 요약답의 포괄성·다양성·판단지원·직접성을 LLM 쌍대평가하고, 비교 5회 평균과 질의별 집계 승률을 제시한다. 이는 탐지 F1·RCA MRR·set recall의 증거가 아니다.[G §3.2–3.6, Fig.4]

## 5. 작은 후보군에서 검색+reranker+MLP가 필요한가?

**판단, 성능 주장이 아님.** 기존 사건/지식 corpus가 없고 후보가 적다는 전제에서는 이 조합의 필요성이 아직 입증되지 않았다. 검색 대상이 서비스 노드인지, 과거 사건인지, 문서인지부터 정해야 한다. 현재 topology를 검색 대상으로 삼을 수는 있지만, 그것이 과거 해결지식을 만들어주지는 않는다. 전체 후보를 직접 점수화하는 기준과 비교 없이 단계 추가를 정당화할 수 없다. 원래 GraphRAG의 문서 요약 성과도 이 RCA 조합의 근거로 전용할 수 없다.[판단: G §2–3]

**검색 상한의 수학적 도출:** 최종 답을 `C_k` 내부로 제한하고 정답이 하나라면,

`P(최종 Top-1 정답) = P(r∈C_k) × P(정답 선택 | r∈C_k) ≤ Retrieval Recall@k`.

복수 정답이면 최종 출력의 set recall도 검색 후보의 set recall을 넘지 못한다. reranker가 후보 밖을 추가하면 이 전제는 달라진다. **사건 검색 recall과 서비스 검색 recall의 분모도 서로 다르다.**

누락 trace에서는 호출 간선뿐 아니라 지연·코드 특징도 사라질 수 있다. 배치도·기존 topology는 관계 일부를 보충할 수 있어도 실제 요청 관측은 대체하지 못한다. T의 비원인 노드 삭제, D의 특징 마스킹을 **원인 trace 누락 전체의 해결 증거**로 해석할 수 없다.[판단: T §4.2–4.3; D §4.2–4.3] 따라서 관측·정답·검색 대상을 먼저 확인해야 하며, LLM을 자동 추천하지 않는다.

## 원문 식별

- **[T]** TVDiag, arXiv2407.19711v3: `https://arxiv.org/html/2407.19711v3`
- **[D]** DeepHunt, *Interpretable Failure Localization for Microservice Systems Based on Graph Autoencoder*, TOSEM 34(2), Article 52: `https://nkcs.iops.ai/wp-content/uploads/2025/07/deephunt.pdf`
- **[G]** Microsoft 원 GraphRAG 논문, *From Local to Global*, arXiv2404.16130 **v1**: `https://arxiv.org/abs/2404.16130` / `https://arxiv.org/html/2404.16130v1`

검증 범위: 위 원문·절·수식·표 대조. 구현 재현·성능·관측 누락의 실제 영향은 검증하지 않았다.
