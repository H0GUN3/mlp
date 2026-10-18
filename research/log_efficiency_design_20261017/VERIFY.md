# 독립 검증 — 로그 처리 효율 설계안

**전체 판정: FAIL.** 13개 요구 중 12개는 현재 문서에서 확인한 설계 범위에서 충족한다. 요구 3은 통합 보고서와 대조 계약의 비용 출처·계산 가능성 서술이 서로 모순되어 FAIL이다. 이 파일은 검증 결과만 기록하며 producer 파일은 수정하지 않았다.

## 검증 범위 및 금지 경계

- 먼저 `BRIEF.md`의 “요구 사항”, “접근 제한”, “성공 조건”을 읽고 범위를 적용했다.
- 읽은 항목: 이 디렉터리의 `REPORT.md`, `COST_AUDIT.md`, `COMPARISON_DESIGN.md`, `PRIOR_ART.md`; `tt_native_support_20261014/PREPARATION_EVIDENCE.md`, `PREPARATION.md`, `PROTOCOL.md`, `REPORT.md`, `artifacts/preparation_20261014T074043_892941Z/success.json`, `artifacts/execution_exit_evidence.json`; `tt_re2_baselines_20261017/TT_PROTOCOL.md`, `INTERIM_REPORT.md`, `TT_EXECUTION.md`; `native_reproduction_20261013/native_data.py`, `native_models.py`, `native_train.py`, `fidelity_audit.md`; `method_mlp_20261013/PROTOCOL.md`, `features.py`; `tt_re2_baselines_20261017/tt_runner.py`.
- 공개 1차 자료는 아래 “외부 출처 확인”에 적은 논문 원문·공식 출판 페이지를 확인했다. TraceBudget은 검색 결과의 ResearchGate 업로드만 확인했으며 저자 관리 원문·출판기록은 검증하지 못했다.
- 허용된 작은 JSON 요약만 읽었다. 원자료, telemetry, NPZ, checkpoint, prediction array에는 접근하지 않았다. 연구 Python 모듈을 import/run하지 않았고, 전처리·학습·추론·benchmark·설치·commit·하위 agent 실행도 하지 않았다. 쓰기는 이 `VERIFY.md` 하나뿐이다.
- 판정은 producer의 체크표나 completed 표기를 증거로 삼지 않고, 아래 원문 문서·코드·요약 필드를 대조했다.

## 13개 요구사항 대조

| # | 판정 | 독립 확인 근거 및 판정 사유 |
|---:|:---:|---|
| 1 | **PASS** | `REPORT.md` “문제”는 확인된 배치 효율 비용과 미확인 운영 비용을 나누고, 안정성·구조 제약은 효과가 확인되지 않은 질문으로 구분한다. 오답 수를 연구 진입조건으로 삼지 않는다. `COMPARISON_DESIGN.md` §1도 효율/안정성/구조를 별도 축으로 두고 미확인을 명시한다. |
| 2 | **PASS** | `REPORT.md` “기존 방법”과 `COMPARISON_DESIGN.md` §1은 Eadro 기반 DiagMLP와 TVDiag 기반 GAIA를 구분하고, 앞단 위치가 필요성·성능 원인 증거가 아니라고 제한한다. DiagMLP 원문 §III-C–D 및 §IV-A는 임베딩 뒤 GNN 대체 위치·위치 임베딩·연결형 node-fusion 및 Eadro/TT와 TVDiag/GAIA 비교를 뒷받침한다. 원문 시각화만으로 인과 설명을 하지 않는 서술도 일치한다. |
| 3 | **FAIL** | 출처 문서는 `PREPARATION_EVIDENCE.md` “Actual processing cost”에서 총 234.812058초 및 Hawkes wall 209.706388초를 각각 보고한다. `success.json`의 `seconds=234.81205789599335`는 총 시간의 요약 확인이다. producer `COST_AUDIT.md` “기존 실측·계산 표”와 `REPORT.md` “근거와 비용 경계”는 범위를 선택 입력 배치 준비, 4-worker Hawkes 벽시계로 한정하고 online/cache hit·miss·상시 비용·공유 절감은 미측정으로 적절히 분리한다. 독립 산술은 `209.706388 / 234.812058 * 100 = 89.3081853573…%` (약 89.31%), 차이는 `234.812058 − 209.706388 = 25.105670초`다. 그러나 `COMPARISON_DESIGN.md` §1 및 §5 “출처 수치 분류”는 같은 값의 출처·범위를 “미확인”이라 하고, 비율 계산 근거도 없다고 해 위 근거와 정면으로 충돌한다. 이 때문에 통합 산출물은 비용 출처에 대해 일관된 결론을 내리지 못한다. **수정 소유자:** `COMPARISON_DESIGN.md` producer가 근거 출처·범위·계산을 연결하거나 실제로 미확인인 항목만 분리해야 한다. |
| 4 | **PASS** | `REPORT.md` “1단계: 고정된 두 arm”과 `COMPARISON_DESIGN.md` §2 단계 1은 Hawkes F 대 같은 관측/템플릿에 기반한 고정 log-count L, 공통 split·후보·나머지 encoder/fusion/head·loss·seed·예산을 제안한다. 둘 다 처음부터 재학습하는 arm과 기존 checkpoint의 inference 입력 0 ablation을 별개로 둔다. 기존 `native_models.py` `joint_loss`와 `tt_native_support_20261014/PROTOCOL.md` “분할·모델·학습 선택”은 기준 목적이 `0.5×detection CE + 0.5×fault-window root CE`임을 확인한다. 설계는 같은 loss를 적용하도록 했으며 해당 공통 목적의 변경을 제안하지 않는다. `PREPARATION.md` “Hawkes and verification” 및 `TT_PROTOCOL.md` “공통 native-like 입력 계약”은 기존 10초 창·60 template-bin·Hawkes 입력을 뒷받침한다. count와 rate는 10초 고정창에서 결정적 스케일 차이이고 별도 정보 arm으로 중복 계산하지 않는다는 선택은 명시되어 있다. 로그 변환/어휘 정책과 입력 폭 공정성은 미결정으로 표시되어 실행 전 동결 대상으로 남는다. |
| 5 | **PASS** | `REPORT.md` “결정 요약”, “향후 비교 설계” 및 `COMPARISON_DESIGN.md` §2는 L을 먼저 비교하고 L이 충분하면 선택기 없이 중단하며, 공정한 캐시·중복 제거 F 대비 추가 이득이 없으면 cascade를 만들지 않는다고 한다. `COST_AUDIT.md` “캐시·공유 계산 표”는 기존 cache-hit/온라인 이득을 측정값으로 가장하지 않는다. |
| 6 | **PASS** | `REPORT.md` “2단계: 정오 조합과 선택 가능성” 및 `COMPARISON_DESIGN.md` §2 단계 2에 네 가지 L/F 정오 조합이 모두 있다. L 불확실성과 F paired 증분 효용을 분리하고, 사후 oracle은 상한 진단으로만 제한하며 정답·선계산 F 특징을 선택기 입력으로 금지한다. |
| 7 | **PASS** | `REPORT.md` “향후 비교 설계”와 `COMPARISON_DESIGN.md` §3은 `공통 처리 + L + 선택기 + 실제 전환 F 추가분 + 중복 비용` 식, 항상 L/F·비용맞춤 무작위·임계값 비교, 평균/P95·메모리·학습비용·실제 생략량을 제안한다. `COST_AUDIT.md` 미래 측정 설계도 같은 캐시/중복 정책과 online/batch 경계를 포함한다. 측정 결과가 아닌 향후 계획임을 명시한다. |
| 8 | **PASS** | `PRIOR_ART.md`의 개별 항목을 지정 원문/구간과 대조했다. JMLR 원문 초록은 classifier 및 feature extraction test-time cost를 함께 다룸; AAAI 2021 원문 초록/§1은 confidence 기반 cascade inference의 정확도·연산비용 tradeoff를 다루며 데이터는 CIFAR-100/ImageNet이다. Eadro §IV-A.1은 Drain 이벤트와 Hawkes, TraceDiag §4.3–4.4는 dependency graph pruning, UniSage 초록/§1은 full-stream 분석 후 sampling, ARMOR §3.3·§4.4·§5.1.3·§5.3.2는 관측 mask·modality dropout 및 finer missingness를 뒷받침한다. MicroHECL 초록은 call graph pruning을 말한다. 이들을 로그-feature cascade와 동일 방법으로 합치지 않는 판정은 타당하다. TraceBudget은 1차 출처·심사 상태 미확인으로 유보한다. |
| 9 | **PASS** | `REPORT.md` “후속 후보 B와 C”와 `COMPARISON_DESIGN.md` §4는 sparse 관측을 완전 입력으로 간주하지 않고 자연 결측·요청 없음·추가 마스킹을 구분 대상으로 둔다. B에 동일 missing augmentation을 적용한 Diag+mask 통제를 둔다. ARMOR v3 §3.3/§4.4/§5.1.3/§5.3.2는 수집 가능성 mask와 인위적 dropout/missingness 평가를 다루지만, 현 local/relative 모델 mask와의 의미 동일성은 입증하지 않는다는 경계가 적절하다. |
| 10 | **PASS** | `REPORT.md` “후속 후보 B와 C” 및 `COMPARISON_DESIGN.md` §4는 C에서 위치·encoder·정규화·출력 폭·파라미터 공유를 포함하고, 고정 슬롯+mask, 가변 N 실행, 비용, 새 서비스 정확도를 별도 질문으로 둔다. DiagMLP 원문 §III-D의 node-fusion 규모 및 DeepSets/Set Transformer 후속 제안과 중복을 인정하고 잘못된 순서 입력을 약한 기준선으로 만들지 않는다. |
| 11 | **PASS** | `REPORT.md` “평가, 경계와 중단 기준” 및 `COMPARISON_DESIGN.md` §5는 창 Top1·사건별 credit 평균·사건 확률 평균 순위를 서로 다른 점수로 구분한다. `TT_PROTOCOL.md` “입력·분할·보호 경계”는 3256/813과 보호 1744+1을 명시한다. `INTERIM_REPORT.md` “RE2에서 진행된 범위와 현재 상태”는 기존 54/18/18 및 test 미접근을 기록한다. `COMPARISON_DESIGN.md` §3은 TRAIN 내부 OOF, validation의 개발/설정 선택, 최종 test 분리를 제안하고 F 학습·OOF 추론·선택기 적합 비용을 학습 비용에 넣는다. OOF 그룹/중복 규칙과 최종 재학습 정책은 미결로 표시되어 있으며, 승인 전 시험 접근을 요구하지 않는다. |
| 12 | **PASS** | `REPORT.md` “평가, 경계와 중단 기준”과 `COMPARISON_DESIGN.md` §5는 `1/18 × 100 = 5.555555…%p`, 약 5.56%p로 적고 이를 품질보존 해상도의 한계로만 설명한다. 허용 손실 및 최소 비용 절감 문턱은 “제안/미합의”로 남기며 임의 채택하지 않는다. |
| 13 | **PASS** | `REPORT.md` “결정 요약”, “평가, 경계와 중단 기준”, “요구사항 반영표”는 비용 경계→고정 대체→정오 조합 순서, 조건부 진입/중단, 미결 결정과 요구 반영표를 한국어로 제시한다. `COMPARISON_DESIGN.md` §6은 같은 순서를 승인 후 제안으로 명시한다. 호출 경로는 후보 정보일 뿐 GNN/인과 증명이 아니라는 한계도 명시한다. |

## 산술·로컬 링크·원문 확인

- **산술(계산):** Hawkes 비중 `209.706388 ÷ 234.812058 = 0.893081853573…`, 즉 `89.3081853573…%`; 차이 `25.105670초`. `1 ÷ 18 = 0.05555555556…`, 즉 `5.555555556…%p`. 반올림 보고치 89.31% 및 5.56%p는 맞다. 값의 출처는 측정자료가 아니라 기존 실행 기록이며, 이 검증에서 새 측정은 없다.
- **저장소 링크:** `REPORT.md`의 brief, COST_AUDIT, COMPARISON_DESIGN, PRIOR_ART 및 위에 열거한 비용·split·mask·코드 근거 artifact는 실제로 읽어 존재와 해당 내용을 확인했다. `success.json`에서 `seconds`, `shapes`, `publication_round_trip_exact` 요약 필드를 확인했을 뿐 NPZ를 열지 않았다.
- **외부 1차 자료 확인:** [DiagMLP `arXiv:2501.02766v2`](https://arxiv.org/html/2501.02766v2) §III-C–D, §IV-A–C; [Eadro `arXiv:2302.05092v1`](https://arxiv.org/html/2302.05092v1) §IV-A.1, §IV-B; [Xu et al., JMLR 15(62)](https://www.jmlr.org/papers/v15/xu14a.html) 초록; [Enomoro & Eda, AAAI-21](https://ojs.aaai.org/index.php/AAAI/article/view/16900) 공식 논문 페이지의 초록·서지 및 공식 PDF의 초록/Introduction; [TraceDiag `arXiv:2310.18740v1`](https://arxiv.org/html/2310.18740v1) §4.3–4.4 및 [Microsoft Research 출판 페이지](https://www.microsoft.com/en-us/research/publication/tracediag-adaptive-interpretable-and-efficient-root-cause-analysis-on-large-scale-microservice-systems/); [UniSage `arXiv:2509.26336v2`](https://arxiv.org/html/2509.26336v2) 초록·§1; [ARMOR `arXiv:2603.25538v3`](https://arxiv.org/html/2603.25538v3) §3.3·§4.4·§5.1.3·§5.3.2; [MicroHECL `arXiv:2103.01782v1`](https://arxiv.org/abs/2103.01782v1) 초록. 원문과 sections를 대조해 관련 주장만 확인했으며 논문 실험의 원자료는 검증하지 않았다.
- **접근 불가/미확인:** TraceBudget 제목의 ResearchGate 업로드/검색 결과에는 preprint 표기와 초록이 노출된다. 그러나 이번 확인 범위에서는 저자 관리 저장소의 원문 또는 독립된 심사·출판 기록과 대조하지 못했다. 따라서 해당 초록의 방법·실험 수치, 저자 원문성, 심사 상태를 검증된 사실로 취급하지 않는다. `PRIOR_ART.md`의 “미확인” 처리와 방법/결과를 근거로 쓰지 않는 제한은 적절하다. ARMOR의 지정 arXiv v3 텍스트는 확인했지만, 별도 출판 상태 검증은 수행하지 않았다.

## FAIL 조치

1. `COMPARISON_DESIGN.md` §1 및 §5에서 234.81/209.71초의 범위·원 측정 출처를 미확인으로 처리하고 비율 계산을 거부한다.
2. 반면 `COST_AUDIT.md` “기존 실측·계산 표”와 `REPORT.md` “근거와 비용 경계”는 `PREPARATION_EVIDENCE.md` “Actual processing cost” 및 요약 `success.json`을 출처로 연결하고 동일 비율을 계산한다.
3. 영향 요구: **BRIEF 요구 3**. 수정할 파일은 **`COMPARISON_DESIGN.md`**(또는 producer 간 합의한 통합 문서)이며, 이 검증자는 수정하지 않았다. 총 배치 준비 범위, Hawkes 단계 범위, 배치 비율과 online/cache 비용 미측정을 한 문장 구조로 일치시킨 뒤 독립 재검증해야 한다.

위 모순이 해소되기 전에는 성공 조건의 “13개 모두 충족”을 만족하지 않으므로 최종 PASS를 부여할 수 없다.
