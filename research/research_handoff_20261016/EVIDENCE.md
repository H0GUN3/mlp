# 근거 조사·판단 기록

기준일 2026-10-16. 검색 요약은 후보 탐색에만 사용하며, 아래의 사실은 원문/로컬 기록에서 확인한다.
실제 운영 근거와 실험용 장애 주입, 방법론과 평가 설정, 저자 주장과 우리 판단을 분리한다.

## 1차 확인: 실제 문제와 기존 진행

- Groot, arXiv:2108.00344v2, §I/III/V: eBay 5,000여 서비스, SRE가 검증한
  952개 실제 운영 장애. Table III Top1 78%, Top3 95%; Table IV 실제 온라인
  적용과 사후 dataset 평가를 구분. 출력은 원인 event이며 서비스 순위만의 과제와
  완전히 같지 않다. 복수 원인 중 하나만 정답으로 선정한 사건도 있어 Top1 차이를
  모두 모델 오류나 우리 TT와 같은 메커니즘으로 설명하면 안 된다.
  https://arxiv.org/html/2108.00344v2
- 같은 논문 §V-A3: 직접 구현한 naive 서비스 PageRank와 non-adaptive
  event-rule 변형이 비교군. 공개되지 않은 다른 도구를 대리 구현한 비교라는 경계가 있다.
- LagRCA 저자 공개 FSE2026 industry PDF §3.1/Table1: 은행 D1의146사건에서
  최대 전파 지연 ≤1분27건, 2–5분94건, ≥6분25건.
  이는 실제 시스템의 전파시간 다양성 근거이며 우리10초 TT 창 오답 원인이라는 증거는 아니다.
  https://netman.aiops.org/wp-content/uploads/2026/04/fse2026-industry-paper77.pdf
- 현재 TT 결과는 `../tt_native_support_20261014/REPORT.md`,
  `baseline_analysis.json`, `gate.json`, `verification.json`을 기준으로 한다.
  이전 `../methodology_direction_20261014/REPORT.md`의 count 실험 예정/미실행 상태는
  이후 완료 결과로 갱신해 읽어야 하며 원 파일은 수정하지 않는다.
- 최근 데이터 후보 검토는 별도 metadata 단계다. GAIA/OpenRCA 후보가 준비된
  학습자료나 이미 선정된 추가 실험으로 바뀌지 않도록 주의한다.

## 기존 인접 방법 원문 재확인

- TVDiag v3 §4/§5.1/Table3: GAIA 기반 A(5서비스/10인스턴스/5유형),
  AIOps22 기반 B(10/40/9), Sockshop C(14/21/7). B는113개 instance-level
  장애를 선택. C는 Chaos Mesh 주입. 논문 본문의 MicroSS 전체10개 기술과
  분석 대상 표의5서비스/10인스턴스는 분모가 같다고 단정하지 않는다.
  RCL 비교군: DiagFusion/Eadro/RF-RCL/MicroRank/TraceRCA/MicroRCA/MicroHECL.
  저자 선택 기준은 일반적인 관측자료에 적용 가능하고 코드 침습이 필요 없는 방법.
  FTI는 별도 과제다. https://arxiv.org/html/2407.19711v3
- DeepHunt §4.2–4.5/§5.1/Table2: D1 모의 전자상거래46인스턴스
  (40서비스 인스턴스+6VM), 정상3,714/장애210; D2 은행18인스턴스,
  정상12,297/장애133. D1은 실제 장애 기반 replay; D2는2021년1–6월 기록을
  두 운영자가 검토. D2 원자료 NDA와 전처리본 접근 가능성은 별개.
  비교군9개: MicroHECL/MicroRank/AutoMAP/TraceRCA/Microscope/RCD/
  DéjàVu/Eadro/DiagFusion. 정상 자기지도 사전학습과 장애 feedback 라벨 예산을 구분.
  이미 request count, masking, 공유 scorer, ranking loss를 사용.
  https://nkcs.iops.ai/wp-content/uploads/2025/07/deephunt.pdf
- BARO §3–4: Online Boutique12/Sock Shop11/Train Ticket64서비스 배포,
  주입 CPU/MEM/DELAY/LOSS, metric-only. BOCPD onset+median/IQR 편차 순위.
  비교: CausalRCA/RCD/CIRCA/ε-Diagnosis/N-Sigma/Dummy.
  known-onset과검출-onset 평가, 서비스와metric순위, Avg@5와Top1을 구분.
  이는 Eadro TT27후보 자료와 같은 Train Ticket 관측 데이터가 아니다.
  https://arxiv.org/html/2405.09330v1

## 판단 경계

| 주장 | 현재 판단 | 이유 |
|---|---|---|
| 원인 조사 우선순위 결정은 실제 운영 문제다 | 문헌 근거 있음 | 운영 장애를 SRE가 라벨링하고 실제 RCA 시스템으로 평가 |
| 우리 TT의 Top1 오류가 모두 전파 혼동 때문이다 | 미확인 | 잘못 올라간 후보와 관측 증거의 사건별 검사가 아직 없음 |
| trace count가 없어서 오류가 발생한다 | 현재 추진 근거 부족 | 사전 exploratory gate 미충족; 모든 count 사용법을 반증한 것은 아님 |
| 원 논문 수치까지 같아야 비교 가능하다 | 채택하지 않음 | 사용자 기준은 방법론/처리 충실도와 공정 비교 |
| 낮은 Eadro 점수는 GNN 열등성을 증명한다 | 채택하지 않음 | split/scaling/selection 효과 미분리 |
| 상위3와1위 차이가 있으니 reranker가 반드시 해결한다 | 미확인 | 측정된 현상이지 원인·최적 해결책의 증거가 아님 |
| 외부 데이터 후보 건수는 독립 학습 사건 수다 | 채택하지 않음 | metadata/창/주입 기록과 관측 지원·독립 사건은 다름 |

## 독립 조사 결과와 교차 확인

- 핵심 문헌 조사: Eadro는 ICSE2023, DiagMLP는 arXiv v2 외에
  ICWS2025 pp.127–129 출판 기록이 있다. Crossref DOI
  `10.1109/ICWS67624.2025.00025` 및 공식 프로그램의 WIP 기록 확인.
  분석한6쪽 v2와 출판3쪽 본문의 동일성은 미확인.
- DiagMLP Table IV는 PDF5쪽 이미지로 직접 재확인:
  TT Top3 99.7>Top5 99.2, D1 31.0은 Eadro 열이며 DeepHunt가 아님.
  오류를 임의 정정하거나 전체 GNN 열등성 결론으로 확대하지 않음.
- 추가 해외: MicroHECL(실제 Alibaba75사건), TraceRCA(주입 TT200+ISP22),
  MicroRCA(주입 Sock Shop95), CausalRCA(서비스와메트릭 과제 분리),
  LagRCA(은행146/Online Boutique161)를 원문 기준으로 조사.
  LagRCA 공식 행사일은2026-07-05~09로 원고 머리말6월 날짜와 다름.
  bank 자료와 별도 Alibaba 적용의 관계, prefix-match 정답 판정은 미확인 경계.
- 국내: AnoProp은 Applied Sciences가 아니라 정보과학회논문지52(4),341–349,
  KAIST 박준호·황지영. KCI DOI와 저자PDF의 DOI suffix가 다름.
  PDF6쪽에서88주입사건과Table1을 이미지 재확인. service/pod/node는
  원인 리소스 종류이지 주입 고장 종류가 아님. 실제 주입기법 목록은 미기재.
- AnoProp의Hit@1 .4625에 정수 정답건수를 역산하지 않는다.
  upstream LatentScope evaluator의 동점 기대점수는 가능한 설명이나
  AnoProp이 같은 evaluator를 그대로 썼다는 증거는 없다.
- HERO는 KAIST 소속의 국제 ICWE2025 poster이며 국내학회 논문이 아니다.
  KAIST lab까지 조회했으나 원문은 구하지 못했다. 초록/서지만 확인.
- GRAFlow는 Ajou 소속 저자와 중국 기관의 공동 연구. publisher metadata와
  author-paper mirror를 구분하며 numerical inconsistencies는 최종 성능 근거로 쓰지 않는다.
- KubeIn은 국내 논문이나 Kubernetes resource 진단이며10/20 detectable
  조건부 Top1을 전체20건의 성공률로 바꾸지 않는다. 초록만 확인.
- MicroRank는 본문 접근 불가로 독립 상세 카드에서 제외. 기존 논문의 비교군이라는
  사실과 그 자체의 검증된 성능은 다르다. QROOT/TransTVDiag는 검색 후보로만 남기고
  상세 실험·비교군 검증을 하지 않았으므로 중심 결론에 사용하지 않는다.
- LatentScope(KDD2024)는 AnoProp의 직접 선행이므로 추가 원문 확인:
  eBay66실제장애/300여서비스와Online Boutique88주입사건,
  metric 공간과잠재resource 공간의 관계를 모델링. 정상 대비회귀 잔차와
  원인resource 추정이 단순 “이상치가큰서비스”와 다름을 보여주는 관련연구.

## 진행 경로 감사

독립 로컬 감사자는 보고서/metadata/집계JSON만 조회했다. 학습/예측 실행 없음.
초기RCAEval180case는60반복시나리오그룹; 후속108/36/36 group split과
최종test보호가 기록되어 있다. 현재TT와 섞지 않는다.
자체method_mlp 실험은18-feature이지만최대200epoch·조기종료이며12회 완료했다.
별도관계모델의5epoch 탐색과 혼동하지 않는다.
자체local→relative Top1 SN80.42→89.35/TT71.15→75.08의개발효과는있다.
이를누락하고“아무개선도확인못했다”고쓰거나출판모델개선으로바꾸면안된다.
RCABench350은 최소2모달 root-observation 조건 통과수일 뿐 준비된 독립사건수가 아니다.
GAIA/OpenRCA의10월16일 검토는 별도metadata 후보단계이며 선정/가공완료가 아니다.
TT의18회 baseline과정확replay,20tests,독립36예측파일검산은 기존유효기록을 재사용한다.
이번 조사에서 다시 학습·재추론했다고 쓰지 않는다.
`resource_study_20261013/REPORT.md`는없었다. 실제근거는
`OPENRCA_GAIA_FINDINGS.md`와`DATA_SELECTION_SCORECARD.md`다.
후자는이미개발/학습에쓴SN/TT가미접촉최종사건관문을통과하지못한다고명시한다.

## 원문·원기록 대조에서 정정한 사항

- AnoProp 구간을초기에“탐지전10분”으로잘못읽었다. 최종PDF6쪽이미지에서는
  “결함탐지전후10분”임을확인해정정했다. 이를엄밀한[-10,+10]구간이라고
  추가해석하지않고원문표현과양끝시각명세미확인을함께기록한다.
- CHASEv1 첫저자는Ziming Zhao다. 최종arXiv HTML저자행으로확인했고,
  중간초안의잘못된Arjun Nakshatra표기를제거했다. 데이터·비교군·TableII도대조했다.
- `method_mlp_20261013`은5epoch시험이아니다. 프로토콜의최대200epoch와
  실제12회비교를확인하고별도5epoch관계진단과분리했다.
- 이전자체방법의개발효과와현재count후보미실행을분리했다.
  전체연구에서개선효과가전혀관측되지않았다는표현을제거했다.
- 기존병행조사의직접유사문헌PRISM/controlled-MLP를추가확인했다.
  PRISM은735benchmark장애이지735자연발생사건이아니다.
  controlled-MLP는상대rank와root-frequency prior를이미다룬다.
  PSC-RE2표시실행은실제RE1으로철회됐지만별도RE2통제연구의철회가아니다.
  이전기록과달리공식KINTSUGI repo/manifest의존재를확인했다.
  코드실행은없음. 논문상세S19/S20의판본/URL을기준으로한다.

## 합성 전 반대 근거 점검

| 검토할 주장 | 반대 근거/위험 | 보고서에 허용한 결론 |
|---|---|---|
| 현장에서Top1이낮으므로우리방법이필요 | 과제·후보·정답·시기·가용자료가다름 | 실제문제의존재만근거화,우리효과는미입증 |
| Top3가높으므로reranker면해결 | 입력범위·표현·학습·선택등여러원인이가능 | 오류양상만확정,CPU오답상위후보부터조사 |
| DiagMLP가GNN불필요를입증 | backbone별효과차이·표오류·복합교체·고정후보 | 강한단순기준의필요성,보편적우열아님 |
| 처리재현이면점수문제는볼필요없음 | 구현충실도와평가설정의적합성은별개 | 원논문수치일치요구없이Eadro선택현상은명시 |
| count 실험은실패했다 | 추가모델자체를학습하지않음 | 가설추진gate미충족으로미실행 |
| 보호test가있으니독립평가확보 | 창분리와사건/recording분리는다름 | 독립성별도검증및새확인자료필요 |

## 산출물 검증

- `HANDOFF_STATIC_NUMERIC_QA_PASS`: 문헌ID20개 중복/누락 없음,
  REPORT/LITERATURE/EVIDENCE의 코드블록·로컬 링크·문헌참조 점검 통과.
  현재 두 모델의 전체 결과, DiagMLP3유형·3seed, count gate,
  과거 자체/외부 참고6개 점수를 원 기록과 대조했다.
- `HANDOFF_REQUIREMENTS_TABLE_QA_PASS`: 사용자6요구의 해당 절과 표 열 수 점검 통과.
  자체200epoch계약/별도5epoch탐색, count 미실행, 미접촉최종사건 불가 경계를 확인했다.
- 문헌 상세는20편, 원문·기관·출판사·저자artifact URL37개/16개domain을 포함한다.
  이는37개의 독립실험 또는 모든URL의접근성보장이 아니다.
  HERO/KubeIn은초록수준, 일부원고는저자논문의mirror를사용했다고표시했다.
- 별도의학습·전처리·추론·성능재실행은없다. 이번검증은문헌과기존산출물대조다.
- 검사초기JS경로도구미정의오류를고치고영향검사를다시실행했다.
  두문서patch의context불일치는수정후반영했으며미반영요구사항은없다.
- 요청범위와무관한모델/데이터/과거보고서파일은수정하지않았다.

## 후속 질문 1–15 대조

- CLARIFICATIONS.md에15개 질문을 모두 대응했고 REPORT.md의 모델 명칭,
  연구 결론/한계, 경량성 제외, CPU의 보조적 지위, 전체 데이터 역할을 정정했다.
- 과거 `calibration200` split metadata를 직접 읽었다.
  SN은TRAIN36/validation28사건, 공유28; TT는81/81, 공유81이다.
  과거95.52/98.80은이200epoch calibration의validation을재집계한값이다.
- 현재baseline_runs.json의18개run에대해 `ranking.by_event`를대조:
  각각TRAIN54/validation27, 교집합0. `CURRENT_EVENT_SPLIT_AUDIT_PASS`.
  같은recording/환경의공유와논문원분할동일성까지검증한것은아니다.
- 현재DiagMLP9회평균Top1 .8656427281713888,Top3 .9973635132615924 재집계.
  config의`support:none`,200epoch/dropout.1/widths[64,16,64]를확인했다.
  제안기법미투입과원논문설정완전동일은다른주장이다.
- RCABench1053개두항목은expected-impact규칙일수있어두독립원인으로단정하지않는다.
  전체1422모집단,369/350자동선정금지,고정9채널호환성만으로배제금지를반영했다.
- `QUESTION_COVERAGE_PASS`, `CLARIFICATION_QA_PASS`:15개항목·모델명칭·핵심수치·
  정답단위·자료역할·로컬링크·표형식검사통과.
- 제시한모델/재학습계획은협의안이다. 사용자합의완료나새학습개시로기록하지않았다.
- 새모델실행·원자료전처리·봉인관측/예측접근은없음. 기존보고서/설정/집계/분할metadata만대조했다.

## 추가 질문 1–12: 실제 흐름과 평가 타당성

- 새 설명은 DIAGMLP_DATAFLOW_AND_VALIDITY.md. 이전 MLP/RCABench 권고는 미합의·실행 보류다.
- `ACTUAL_FLOW_SOURCE_PASS`: 현재 읽은 복원 코드6개가 저장된 run의 해시와 일치.
  설정과 코드에서 metric/log/trace64/16/64, concat144, position 추가208,
  노드27개 concat1728, root27/detection2 출력을 대조했다.
  중간 activation 추적 실행이나 추가 모델 forward는 하지 않았다.
- 보존 인코더의 attention은 실제로tanh가중합이다. 로그는HawkesADM4의baseline벡터이며
  템플릿59+미등록bin=60이다. 자체점수기는18개관측특징과mask등으로90차원을입력한다.
- `LEGACY_SPLIT_UNIT_AUDIT`: 과거SN316/78창,TT3256/813창의TRAIN/validation
  index교집합0. 사건은SN28/28,TT81/81공유다. 이결과를새사건성능으로사용하면부적절하다.
- `RCAEVAL_EXISTING_SPLIT_PASS`: split.lock해시일치,TRAIN108/validation36/test36,
  반복그룹60개는분할을가로지르지않음.기존개발사례는TRAIN에만배치돼있다.
- 실제RCABench case `ts0-mysql-corrupt-jkgn5j`의root_services는
  `mysql`, `ts-order-service`. 생성코드의expected-impact/endpoint-pair규칙도확인.
  해당사례의유일한물리적원인을단정하거나전체archive의생성revision일치를주장하지않는다.
- `DATAFLOW_AND_VALIDITY_QA_PASS`:12문항,표·코드블록·로컬근거링크,
  실제차원·분할수·사례·보류상태대조통과.
- 모델·원자료·기존split·동결실험결과는수정하지않았다.
