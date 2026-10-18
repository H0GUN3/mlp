# RCABench·LEMMA-RCA 데이터 선정 평가

## 2026-10-14 실제 RCABench 검수 반영

[후속 실제 검수 보고서](../rcabench_assessment_20261013/REPORT.md):
공식 MD5가 맞는 아카이브에서1,422사례, 단일 항목 정답369개,
그중 최소 양모달 정답 관측 지원350개를 확인했다.
파일 payload는13.635127GB/12.698701GiB이며 전체 해제본을 저장하지 않았다.
133사례의 정상/이상 경계에 공유 span ID가 있었고,
변환 메트릭은 CPU user/system·network 방향·단위를 보존하지 않는다.
350을 독립 유효 사건이나 현재9채널 직접 입력 가능 수로 보지 않는다.

초기 RCABench70점은 아래의 **과거 metadata 기반 가설**로 보존한다.
현재는 입력·정답 계약의 재결정 전까지 종합 선정 점수를 보류하며,
LEMMA 등 다른 후보를 새로 처리하거나 순위를 자동 변경하지 않는다.

## 초기 metadata 평가의 범위와 결론 — 과거 기록

공식 논문·문서·파일 목록만 확인했다. **관측자료 아카이브 다운로드, 전처리,
새 분할·학습은 하지 않았다.** 아래 점수는 `DATA_SELECTION_SCORECARD.md`의
동일한 기준을 적용한 조건부 선정 판단이며 정확도나 객관적 품질 순위가 아니다.

| 후보 | 과제20 | 특징30 | 규모25 | 준비도15 | 비용10 | 합계 |
|---|---:|---:|---:|---:|---:|---:|
| 전파 인지 RCABench | 16 | 24 | 20 | 6 | 4 | **70** |
| LEMMA-RCA IT 부분 | 12 | 12 | 10 | 9 | 4 | **47** |

등급 원본은 각각 `[4,4,4,2,2]`, `[3,2,2,3,2]`다.
**신규 후보 중에는 RCABench의 적합성이 더 높다.** 그러나 논문 보고와 공개
아카이브의 사례 대응을 아직 확인하지 못했으므로 주실험/최종평가 자료로 확정하지 않는다.
LEMMA-RCA의 낮은 점수는 현재의 서비스·trace 기반 방향에 대한 판단이다.
메트릭·로그 기반 개체 RCA용 자료로서의 가치를 부정하지 않는다.

## 1. 전파 인지 RCABench

### 논문 보고와 확인된 배포 사실

- 논문 *Rethinking the Evaluation of Microservice RCA with a Fault Propagation-Aware
  Benchmark*의 공개 v2는 FSE2026 채택을 저자가 명시한다. 최종 학회본을 별도로 검수한 것은 아니다.
- **저자 보고:** 확장 TrainTicket 50서비스, 9,152주입에서 영향이 확인된
  1,430개의 서로 다른 유효 고장 설정, 동적 부하. 본문 주요 설명은 6범주25종이나
  다른 설명에는 7범주31종도 있어 버전 내 집계 표현에 주의해야 한다.
- 188.1시간, 1,120만 traces, 평균16.47QPS 등도 저자 집계다.
  실제 배포의 관측 밀도를 우리가 측정한 수치가 아니다.
- 초기 주입의84.4%가 NoAnomaly로 분류됐다는 설명은 영향 검증 절차의 근거다.
  선택된1,430설정이 반복 실험1,430회 또는 서로 독립적인 수집 세션이라는 뜻은 아니다.
- 평가 정답은 서비스 수준으로 통일할 수 있도록 계층형으로 제공한다고 설명한다.
  전체 사례가 단일 원인 서비스인지, 같은 세션/설정의 사례를 어떻게 묶어야 하는지는 미검증이다.

Zenodo 공식 export에서 확인한 파일 크기:

| 파일 | 바이트 | MD5 |
|---|---:|---|
| rcabench-absolute_anomaly.tar.gz | 13,444,974,981 | 96d32ae290e06be7d4e251be02b36cb8 |
| rcabench-fse-26.zip | 1,436,695 | 51b80c5d7b79c67e531c2639ec43412f |
| rcabench-platform-feat-fse26.zip | 557,891 | b363d3a0fff3a1047c907648afbe8575 |
| 합계 | **13,446,969,567** | |

주 관측자료 압축파일은 **13.445GB**, 해제 크기는 미확인이다.
주 관측자료 체크섬은 배포 metadata 값이며 재계산하지 않았다.
후속 조사에서는 코드 ZIP 두 개만 내려받아 메모리에서 MD5를 재계산했고 모두 일치했다.
라이선스 metadata는 CC-BY-4.0이다.
**`absolute_anomaly`가 논문의1,430사례 전부와 정확히 일치하는지는 아직 모른다.**

### 특징 적합성

저자 연결 프로젝트의 AegisLab-doc 개발자 문서는 다음 필드를 명시한다.

- 정상/이상 trace: `time`, `trace_id`, `span_id`, `parent_span_id`,
  `service_name`, `duration`, `span_kind`, 상태 및 HTTP 응답 코드.
- 이 문서의 시간은 UTC ns, duration은 UInt64 ns.
- 정상/이상 메트릭: 시간·이름·값·서비스·Kubernetes metadata.
- `injection.json`: 정답 서비스 목록, 주입 시작/끝, 고장 유형.
- 따라서 자기 처리 시간, 오류, 지연 분포, 정상 대비 변화의 **스키마상 근거는
  기존 신규 후보들보다 직접적**이다. 현재7개 메트릭의 정확한 대응은 미확인이다.

중요한 제한:

1. 문서에서 metric/log 파일은 선택적이다. 모든 사례의 채널 완비를 보장하지 않는다.
2. 다른 데이터 구조 문서는 `trace.parquet`, 시작/끝 µs 등 다른 포맷을 설명한다.
   catalog의100/200개 묶음과 예시 용량은 Zenodo의 실제 manifest가 아니다.
3. 부모 ID만으로 self-time 계산의 타당성이 입증되지 않는다.
   부모 포함률, 시간 중첩, 비동기 호출, 관측 밀도를 실제 행으로 확인해야 한다.
4. 정답·주입 metadata와 파생 `conclusion.parquet`가 입력 폴더에 함께 있다.
   학습 입력은 관측 필드 허용목록으로 제한해야 하며 정답 유출을 막아야 한다.
5. 공개 알고리즘 예시는 있으나 문서의 온라인 경로에는 사설 서버/마운트가 있다.
   해당 연결·명령은 실행하지 않았고 공개 배포만으로의 오프라인 재현은 미검증이다.

### 점수 이유와 남은 선정 조건

과제4: 서비스 계층 정답은 적합하나 단일 원인 수 미확인.
특징4: 필수 trace 필드가 명시되지만 실제 아카이브와의 대응 미확인.
규모4: 다양한 설정이라는 논문 근거가 있으나 실제 유효 사례/수집 세션 수 미확인.
준비도2: 공개 배포와 문서 연결은 확인했지만 여러 포맷·사설 경로가 혼재.
비용2: 13.445GB 압축자료와 신규 변환기가 필요하며 실행 비용은 측정하지 않았다.

선정 전에는 실제 배포 manifest→정답/수집 세션 대응, 필수 채널·시간 단위,
단일 서비스 사례 수, 비교군까지 포함한 오프라인 처리 가능성을 확인해야 한다.
현재 입력과 비슷하고 전파를 명시적으로 다룬다는 이유로 **우선 검토 후보**이지,
논문의 다른 방법 정확도가 낮다는 이유로 고른 후보는 아니다.

### 후속 확인: 배포 당시 코드에서 찾은 실제 선정 조건

두 코드 ZIP 합계 **1,994,586B**만 메모리에서 읽었다. 파일시스템에 압축을 풀거나
코드를 실행하지 않았고, 관측자료 아카이브는 접근하지 않았다.
`rcabench-fse-26.zip`은852개 ZIP 항목의 서버/SDK 코드,
`rcabench-platform-feat-fse26.zip`은186개 항목의 변환/평가 프레임워크였다.
이 항목 수는 코드 ZIP의 파일·디렉터리 수이지 장애 사례 수가 아니다.

후자의 `cli/export.py`에서 확인한 내용:

- `compress_all(tags=["absolute_anomaly"])`가 실행 진입점이다.
- 주입 API에서 해당 태그의 이름을 조회하고, 각 사례의 `converted/` 폴더가 있을 때만
  그 폴더를 사례 이름 아래에 저장한다. 생성 이름도 `rcabench-absolute_anomaly.tar.gz`다.
- 따라서 공개 아카이브 이름과 고장 선택 태그의 연결은 **코드로 확인**했다.
  그러나 당시 API 응답/실행 로그가 없으므로 그 수를1,430으로 확정할 수는 없다.
- export는 `valid()`를 호출하지 않는다. 이름과 폴더 존재만으로 포함하며,
  유효성 함수가 요구하는 파일·JSON·Parquet 행 검사를 실제로 통과했는지 보장하지 않는다.

동일 코드의 `docs/specifications.md`와 `datasets/spec.py`는 사례 목록
`meta/{dataset}/index.parquet`, 정답 `labels.parquet`를 설명한다.
그러나 **두 코드 ZIP에는 `.parquet`, `.csv`, `.jsonl`, `.sql` 항목이 없었다.**
export 역시 전역 meta 폴더를 별도로 추가하지 않는다. 이는 확인한 코드 배포에서
실제 인덱스를 얻지 못했다는 뜻이지, 다른 모든 공개 경로에도 없다는 증명은 아니다.
HF 예시는 `anonymous-user/rcabench-platform-private-test`이며 공개 데이터 주소로
사용하지 않았다. 사설 API/스토리지에 접속하거나 예제의 업로드·삭제 명령을 실행하지 않았다.

정답 단위도 추가 주의가 필요하다:

- `sources/rcabench.py:459–473`의 변환기는 Network 고장에 source와 target이
  모두 있으면 **양쪽 서비스를 정답**으로 생성한다.
- `datasets/rcabench.py:483–490`의 분석기는 `injection.json`의
  `ground_truth.service` 목록을 직접 반환한다.
- 따라서 사례별 injection 정답과 변환 정답을 대조해야 한다.
  단일 서비스 정답 수를 전체 고장 설정 수와 같다고 가정하지 않는다.
- 참고로 `valid()`의 반환형은 `(path, bool)`인데 일부 테스트 도구는 이를
  조건문에 직접 넣는다. 비어 있지 않은 tuple은 False 결과도 참으로 평가되므로,
  그 도구의 “valid” 목록을 검증 근거로 그대로 신뢰하지 않는다.
  이 문제를 외부 코드에서 수정하거나 실행한 것은 아니다.

**현재 결과:** 태그→배포 생성 규칙과 정답 생성 경로는 확인했지만,
사용 가능한 추가 사건의 정확한 수는 여전히 미확정이다. 점수를 올리지 않는다.
이제 필요한 것은 `injection.json`·`env.json`·파일 목록/Parquet schema와 행 수에
근거한 실제 사례별 집계다. 행 수만으로 self-time·오류 관측 품질까지 검증되지는 않는다.
자료가 단일 gzip tar이고 코드상 전역 인덱스의 별도 배포가 확인되지 않아,
모든 사례의 내부 정보를 얻으려면 통상 **13,444,974,981B(12.52GiB)**의 압축 스트림을
끝까지 읽어야 한다. ZIP처럼 끝의 목록만 원격 조회하는 방식으로 해결되지 않는다.
이 전송 및 내부 검수는 아직 시작하지 않았으며, 기존의 처리 보류 경계를 유지한다.

### 별도 공개 인덱스 경로 추가 확인

전체 관측자료 전송을 피하기 위해 공개 검색에서 `absolute_anomaly`, `1430`,
`index.parquet` 연결을 추가 조사했다. 검색에 나타난 HF `lincyaw/rca`는 직접
접근 시 페이지404, README/API는 인증 오류를 반환했다.
공개 HF API의 `search=rcabench` 및 `author=lincyaw` 조회도 빈 목록이었다.
검색 요약에 나온 파일 구성을 검증된 배포 사실로 채택하지 않았으며,
로그인·토큰·비공개 접근을 시도하지 않았다.
이 결과는 해당 자료가 없다는 증명이 아니라 **현재 익명으로 읽을 수 있는
별도 사례 인덱스를 확보하지 못했다**는 한계다. 같은 실패 경로를 반복 조회하지 않는다.

- 검색에 나타난 후보: https://huggingface.co/datasets/lincyaw/rca
- 직접 확인: https://huggingface.co/datasets/lincyaw/rca/raw/main/README.md
- 공개 검색: https://huggingface.co/api/datasets?search=rcabench&limit=50
- 공개 저자 목록: https://huggingface.co/api/datasets?author=lincyaw&limit=50

## 2. LEMMA-RCA의 IT 부분

### 대상과 유효 규모

공개 arXiv v4는 CIKM2026 채택을 저자가 명시한다.
이 평가에는 Product Review와 Cloud Computing만 포함하고 SWaT/WADI 등 OT는 제외했다.
공식 표의4/6 faults는 카드의4/6고장 유형,4/6날짜별 원자료 ZIP과 대응한다.
따라서 확인된 것은 **총10개 시나리오 배포 묶음**이지 독립 사건10건이 아니다.
묶음 내부의 주입 횟수·반복·단일 정답 사례 수는 아직 알 수 없다.

고장 조건은 DDoS, 외부 저장소, 자원 경합, noisy neighbor와
cryptojacking, pod 성능 저하, malware, GitOps/설정/코드 문제 등이다.
카드는 시뮬레이션이라고 설명하므로 자연 발생 운영 장애로 단정하지 않는다.
정답은 machine/container/pod 등 개체 중심이며 전체 서비스 매핑은 미검증이다.

### 정확한 공개 ZIP 용량

Hugging Face의 고정 revision 파일 목록에서 ZIP만 합산했다.
작은 README와 `.gitattributes`는 제외했고 페이지 누락은 없었다.

| 부분 | ZIP 수 | 바이트 | GB |
|---|---:|---:|---:|
| Product Review 원자료 | 4 | 53,633,808,946 | 53.634 |
| Cloud Computing 원자료 | 6 | 33,002,132,069 | 33.002 |
| **IT 원자료 합계** | **10** | **86,635,941,015** | **86.636** |
| Product Review 전처리본 | 8 | 6,655,484,106 | 6.655 |
| Cloud Computing 전처리본 | 11 | 4,737,524,465 | 4.738 |
| **IT 전처리본 합계** | **19** | **11,393,008,571** | **11.393** |

전처리본은 Product metric685,605,065B + log5,969,879,041B,
Cloud metric625,270,486B + log4,112,253,979B다.
원자료/전처리본은 같은 시나리오이므로 사건 수를 합산하지 않는다.
사이트의765G/540G는 포장·단위 해석이 불명확한 저자 표기로 다운로드 크기에 사용하지 않았다.
해제 크기·trace만의 크기는 미확인이다. GB는10^9B다.

Zenodo20516735는 관측자료가 아니라 metadata/접근 문서4파일,
총7,527B인 기록이다. 실제 관측자료 배포는 위 HF 저장소다.

### 특징·정답·이용조건의 제약

- 원자료 README는 메트릭·로그와 함께 **“and even trace data”**를 명시한다.
  따라서 trace가 없다고 결론내리면 안 된다. 다만 부모/자식 ID, span 시간,
  오류 필드, 시나리오별 coverage는 검토한 metadata에서 확인되지 않았다.
- 전처리본은 metric/log 중심이다. 이를 받는 것만으로 기존 duration/span count나
  self-time 입력을 만들 수 있다고 보장할 수 없다.
- PPTX의 측정/고장 시각은 JST, 관측자료는 UTC다. 9시간 변환 및 실제 구간 확인이 필요하다.
- Cloud20240207은 EKS log 없이 CloudTrail CSV만 제공한다고 설명하며 대응 Log ZIP도 없다.
- website/Zenodo/카드 본문의 CC-BY-ND-4.0과 HF YAML/저장소 LICENSE의
  CC-BY-NC-4.0이 충돌한다. 어느 하나로 임의 확정하지 않는다.
- 공개 전처리·6개 baseline 코드 존재는 확인했지만 실행하지 않았다.
  MSDS/RCAEval/GAIA와의 중복 또는 독립성을 확정하는 출처 대응표도 확인하지 못했다.

과제3, 특징2, 규모2, 준비도3, 비용2를 적용했다.
서비스 정답 매핑·사건 인덱스·trace 스키마·이용조건이 해결되기 전에는
현재 trace 중심 실험의 주자료로 권하지 않는다.

## 근거 URL 및 고정 버전

### RCABench

- 논문: https://arxiv.org/html/2510.04711v2
- 공식 배포: https://zenodo.org/records/17105974/export/json
- 저자 웹사이트 소스: https://github.com/OperationsPAI/revisiting-rca-evaluation/tree/a654cf79f9a550a10f54f5c1d19e5169cee4bd13
- 필드 문서: https://github.com/OperationsPAI/AegisLab-doc/blob/65cefb34d67b72452334e7050874d68914f3060e/content/algorithm-developers/development-guide/data-formats/_index.md
- catalog: https://github.com/OperationsPAI/AegisLab-doc/blob/65cefb34d67b72452334e7050874d68914f3060e/content/algorithm-developers/reference/dataset-catalog/_index.md
- 다른 구조 문서: https://github.com/OperationsPAI/AegisLab-doc/blob/65cefb34d67b72452334e7050874d68914f3060e/content/dataset-creators/dataset-management/dataset-structure/_index.md
- 알고리즘: https://github.com/OperationsPAI/rca-algo-contrib/tree/55bdea5ed31ca1464887e24174eb980420b9f82b

### LEMMA-RCA

- 논문: https://arxiv.org/abs/2406.05375v4
- 공식 웹 소스: https://github.com/lemma-rca/lemma-rca.github.io/blob/e1ab1179e427f3c33defab516620ef9923573a62/docs/data.html
- 저자 설명·코드: https://github.com/KnowledgeDiscovery/rca_baselines/tree/ae67f70d705b9fe28e89792d4ca0363b91590b42
- Product 원자료 manifest: https://huggingface.co/api/datasets/Lemma-RCA-NEC/Product_Review_Original/tree/63aa4abe7dd7217d9b0b108894c7d893e2b29aef?recursive=true
- Cloud 원자료 manifest: https://huggingface.co/api/datasets/Lemma-RCA-NEC/Cloud_Computing_Original/tree/9e5ad23fa390f6b596f41be014233fe446679bcd?recursive=true
- Product 전처리본 manifest: https://huggingface.co/api/datasets/Lemma-RCA-NEC/Product_Review_Preprocessed/tree/df25484004e50483de6f6756c3a4d7ab03174b83?recursive=true
- Cloud 전처리본 manifest: https://huggingface.co/api/datasets/Lemma-RCA-NEC/Cloud_Computing_Preprocessed/tree/03f82a2c4b16afe09e9315def9f5d6990427000a?recursive=true
- 문서 아카이브: https://zenodo.org/records/20516735

접근 실패도 범위에 포함한다: 공식 custom domain의 TLS 오류는 검증을 끄지 않고
저자 연결 GitHub 소스로 대체했다. Zenodo API 일부504는 export 또는 기록 페이지
manifest로 대체했다. 이 우회가 관측자료 검수나 원형 실행을 대신하지는 않는다.
