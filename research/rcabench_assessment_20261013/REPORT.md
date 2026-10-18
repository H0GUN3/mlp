# RCABench 실제 자료 검수 결과

**검수일:** 2026-10-14  
**범위:** 공식 배포 확보·무결성·메타데이터·변환 관측자료 census.
학습, 튜닝, 실험용 분할, 최종시험은 하지 않았다.

## 요약 결론

실제 배포에는 **1,422개 사례 폴더**가 있었다.
단일 항목 서비스 정답은 **369개**, 두 항목 서비스 정답은 **1,053개**다.
단일 항목 사례 중 **350개**에는 정상·이상 구간의 메트릭과 trace 양쪽에서
정답 서비스의 기초 유효 행이 적어도 하나씩 있었다.

**350개는 검증된 독립 사건 수나 현재 모델에 바로 투입 가능한 수가 아니다.**
현재 native Eadro의 7메트릭+2trace 입력을 그대로 구성하는 데 필요한
CPU user/system 및 네트워크 rx/tx 구분 정보와 단위가 변환 메트릭에 보존되지 않는다.
또한 복수 정답 계약, 관측 누락, 정상·이상 경계의 중복, 수집 독립성 문제가 남는다.

따라서 **추가 사례의 규모는 확인했지만, 기존9채널 연구의 데이터 부족이
그대로 해결됐다고 결론내릴 수 없다.**

## 1. 확보와 용량

공식 파일: `rcabench-absolute_anomaly.tar.gz`  
MD5: `96d32ae290e06be7d4e251be02b36cb8` — 로컬 재계산 일치.
다운로드와 인벤토리 명령 모두 exit0으로 완료됐다.

| 구분 | 바이트 | GB | GiB | 의미 |
|---|---:|---:|---:|---|
| 확보한 gzip tar | 13,444,974,981 | 13.444975 | 12.521609 | 실제 저장된 압축 파일 |
| archive 내부 파일 내용 합계 | 13,635,126,699 | 13.635127 | 12.698701 | 변환 Parquet/JSON 등의 논리 payload |
| SHA256 기준 고유 payload | 13,635,126,699 | 13.635127 | 12.698701 | 비어 있지 않은 파일의 바이트 중복은 없었음 |

전체를 디스크에 압축해제하지 않았다.
따라서 압축파일 크기와 논리 payload를 합쳐 실제 저장 용량처럼 보고하면 안 된다.
이 export는 **변환 자료**이며, 변환 이전 원시 수집자료의 고유 용량은 확인한 것이 아니다.
기존 r2 전체 용량 표와는 별도의 추가 확보 항목이다.

추가 JSON 기록은 `metadata_inventory.json` 1,640,283B,
`schema_probe.json` 28,923B, `quality_audit.json` 45,545,303B다.
압축파일과 이 세 불변 JSON의 합계는 **13,492,189,490B**이며 코드·문서는 별도다.

## 2. 사례와 정답 단위

| 항목 | 실제 수 |
|---|---:|
| 사례 디렉터리 | 1,422 |
| 단일 항목 `ground_truth.service` | 369 |
| 두 항목 `ground_truth.service` | 1,053 |
| 네 core 파일이 실제로 읽히고 비어 있지 않은 사례 | 1,422 |
| 단일 항목 정답의 최소 양모달 관측 지원 | 350 |
| 두 항목 정답 모두의 최소 양모달 관측 지원 | 908 |
| 정답·기간·고장 유형이 같은 metadata 그룹 | 0 |
| 내용이 동일한 비어 있지 않은 파일 그룹 | 0 |
| 네 core 관측 파일이 모두 같은 사례 그룹 | 0 |
| 검증된 독립 유효 사건 수 | 미확정 |

core는 정상/이상 `metrics.parquet`와 `traces.parquet` 네 파일이다.
최소 지원은 정답 서비스에 유한 메트릭 또는 비어 있지 않은 ID·비음수 duration을 가진
기간 내 trace 행이 각 파일에서 **적어도1개** 있다는 뜻이다.
충분한 coverage, 인과 정보, 완전한 graph, 실제 진단 가능성을 뜻하지 않는다.

### 단일 항목 사례의 구성

공식 FSE 코드의 enum 해석에 따른 수량이며, 단일 항목369사례는9종에 속한다.

| 고장 종류 | 사례 |
|---|---:|
| PodKill | 10 |
| PodFailure | 24 |
| ContainerKill | 89 |
| TimeSkew | 2 |
| JVMLatency | 7 |
| JVMReturn | 21 |
| JVMException | 43 |
| JVMCPUStress | 2 |
| JVMMemoryStress | 171 |

JVMMemoryStress가 **46.34%**를 차지한다.
단일 항목만 선택하면 network·HTTP 계열의 많은 두 항목 사례가 빠진다.
따라서 이 부분집합을 원래25종 전체나 기존 SN/TT의 CPU·network3종 분포와
동일한 문제로 취급하지 않는다.

369사례에는129개의 `(service, fault_type)` 조합이 있다.
같은 조합의 여러 사례도 강도·매개변수가 동일한 독립 반복이라고 단정할 수 없다.
이름의 `ts0`–`ts9` 접두사 역시 독립 수집 세션 ID라는 증거가 아니다.
논문의1,430개 유효 설정과 실제1,422폴더의 차이8개는 이유가 확인되지 않았다.

### 복수 정답의 의미

공식 코드에서 `ground_truth.service`는 주입 구성의 expected-impact 규칙으로 생성된다.
HTTP·DNS·network·JVM-MySQL 등은 endpoint/database 두 항목을 의도적으로 포함할 수 있다.
서로 독립적인 두 주입이나 “물리적 원인이 두 개”라는 증거가 아니다.

별도 변환기의 `labels()`는 network 외에는 사례 이름에서 service를 가져온다.
따라서 이 경로와 injection 목록은 같은 정답 계약이 아닐 수 있다.
첫 항목만 임의로 골라 단일 정답으로 바꾸지 않았다.
특히 caller와callee를 모두 정답으로 인정하는 평가로는
둘 중 실제 원인과 전파 증상을 구별했다는 주장을 바로 검증할 수 없다.

## 3. 실제 관측과 품질

총19,991개 파일을 순차 처리했다.
전체 Parquet footer에 기록된 행은853,150,369개이며,
gauge·sum·trace의 필요한 열은 **692,555,650행**을 실제로 읽었다.
로그·histogram·conclusion의 본문까지 검사한 것은 아니다.

| 실제 열을 읽은 자료 | 정상 행 | 이상 행 |
|---|---:|---:|
| gauge metrics | 101,589,374 | 101,267,418 |
| sum metrics | 96,334,626 | 94,528,680 |
| trace/span 행 | 190,935,327 | 107,900,225 |

마지막 줄은 span 행 수이며 서로 다른 요청 trace 수나 장애 사건 수가 아니다.

- 읽은 열의 profile 오류는0건이었다.
- 위6종의8,532개 파일에서 time은 모두 ns 단위였고,
  null time 및 source의 닫힌 추출 구간 밖 시작 timestamp는0행이었다.
  물리적 clock 정합성이나 span 종료 시점 가용성의 증명은 아니다.
- gauge value에는 정상891,445행, 이상1,348,711행,
  합계 **2,240,156행의 NaN/Inf**가 있었다. 임의의0으로 바꾸지 않았다.
- gauge의 빈 service 이름은 정상14,812,947행, 이상14,774,039행이다.
  namespace/global 수준 메트릭일 수 있으므로 특정 서비스에 임의 할당하지 않는다.
- 모든 Parquet footer의 행 수는0보다 컸다.
  로그 등 footer 전용 파일의 페이지 본문까지 읽혔다고 확대하지 않는다.

### 정답 관측이 부족한19사례

단일 항목369사례 모두 정상·이상 gauge에 정답의 기초 유효 행이 있었다.
하지만 정상 trace에서5사례, 이상 trace에서18사례가 최소 정답 관측을 충족하지 못했다.
4사례가 양쪽에 해당하여 서로 다른 사례로는 **19개**다.

여기에는 pod failure 후 trace가 사라지는 경우와 mysql이 trace 서비스로 나타나지 않는
경우 등이 포함된다. 고장 유형별 부족 수는 PodFailure14, ContainerKill2,
PodKill1, TimeSkew1, JVMCPUStress1이다.
이것을 모두 수집 불량으로 단정하거나 평가에서 자동 삭제하지 않는다.
장애 때문에 관측이 사라지는 어려운 사례일 수도 있다.

### `.invalid`는 자동 제외하지 않음

`.finished`는1,422개, `.invalid`는83개였다.
단일 항목의 `.invalid`38사례 중 **36개는 위 최소 양모달 관측 조건을 충족**했다.
반대로 표식이 없는 단일 항목17사례도 최소 정답 관측을 충족하지 못했다.

공식 `valid()`는 변환 export에 없는 raw-pack 파일도 요구하며,
`.invalid`에는 실패 이유가 저장되지 않는다.
표식의 생성 이력이 없으므로 그것만으로 현재 변환자료의 적합성을 판단하지 않는다.

## 4. 정상·이상 경계의 실제 중복

모든 사례의 NORMAL_END와 ABNORMAL_START가 같다.
공식 SQL은 양 끝을 포함하는 `BETWEEN`을 사용한다.
실제로 **133사례에서 정상 끝·이상 시작 경계에 같은 `(trace_id, span_id)`가
나타났으며, 사례별 공유 ID 수 합계는145개**였다.
단일 항목 사례 중에는33개가 해당하며, 이33개는 최소 관측 지원350개에도 포함된다.

따라서 “파일명이 normal/abnormal로 다르니 관측도 완전히 분리됐다”는 전제는 성립하지 않는다.
미래 전처리에서는 경계 규칙과 동일 span 배치를 먼저 정해야 한다.
이번 감사에서는 파일·행·사례를 제거하거나 재배치하지 않았다.
경계 외 전체 span 중복, parent 참조 해소율, 내용 충돌·self-time은 별도 검증 대상이다.

## 5. 현재9채널 입력과의 정합성

전체 gauge/sum에서81개 metric 이름과15개 열을 확인했다.
resource 계열과 JVM·Hubble 계열은 있으나, 변환 열에는
CPU user/system mode, network direction/interface, MetricUnit/Unit이 없다.
공식 FSE 변환 allowlist도 이를 보존하지 않는다.

| 기존 입력 | 실제 export와의 관계 |
|---|---|
| CPU total | `container.cpu.usage` 등 후보는 있으나 정확한 단위/수집 의미 대조 필요 |
| CPU user / system | mode를 구분하는 정보가 변환 메트릭에 보존되지 않음 |
| memory usage / working set | 같은 계열 이름은 있으나 원 수집 단위·개체 집계의 동등성 확인 필요 |
| rx / tx bytes | `k8s.pod.network.io`는 있으나 송수신 방향·interface 정보가 보존되지 않음 |
| trace 평균 지연 / span 수 | 필요한 기본 열은 있으나 표본화·중복·경계·duration 가용성 정책 필요 |

JVM system/process CPU 값을 kernel/user CPU의 동등한 대체물로 쓰지 않는다.
방향이 없는 network I/O를 임의로 rx/tx로 나누지도 않는다.
단위는 값 크기만 보고 추측하지 않는다.

**현재 입력 계약 그대로 연결할 수 있다고 검증한 추가 사건 수는 미확정이다.**
이 자료가 모든 RCA 연구에 부적합하다는 뜻은 아니다.
보존된 정보에 맞춘 공통 입력 계약 또는 구분 정보를 보존한 원자료가 필요하며,
그 결정 전에는 새로운 모델 전처리·학습·최종평가로 넘어가지 않는다.

## 6. 검증 근거와 자원

- 공식 크기·MD5 일치, 메타데이터 도구 exit0.
- schema probe의 인메모리 Parquet 자체 검사와 실제 첫 사례 실행 exit0.
- 품질 검사4개 통과(`Ran 4 tests in 0.009s`, `OK`), 두 검사 파일 LSP 오류 없음.
- 전체 census exit0, profile 오류0건. 원본 archive의 inode·크기·mtime 불변 확인.
- 집계 측정 구간 **290.704초**, 해당 시점까지 peak RSS **517.98MiB**.
  최종 JSON 직렬화/저장은 이 두 측정값 뒤에 수행했다.
  이것은 데이터 감사 비용이지 방법별 학습·전처리의 공정한 비용 비교가 아니다.
- 기존 `.venv-mlp`의 NumPy1.26.4 / Arrow19.0.1 사용. 설치·환경 변경 없음.

산출물:
- [메타데이터 인벤토리](metadata_inventory.json)
- [전체 품질·파일 SHA256 기록](quality_audit.json)
- [검사 기준·재현 명령](QUALITY_CONTRACT.md)
- [표본 스키마](schema_probe.json)

## 7. 연구상의 판단

더 많은 **명목 사례와 다른 고장 조건**은 확보했다.
그러나 고정9채널 입력의 충실한 재구성, 단일 원인과 expected-impact 정답의 차이,
어려운 관측 누락 사례, 수집 독립성은 별개의 문제다.
369 또는350을 새 독립 최종시험 수로 보고하거나, 수 GB의 자료가 부족 문제를
자동으로 해결했다고 주장하지 않는다.

기존의 RCABench 조건부70점은 실제 검수 전 판단이었다.
현재는 입력·정답 계약이 결정되지 않아 그 점수를 선정 근거로 확정하지 않는다.
모든1,422사례를 기록에 남겼으며 결과를 유리하게 만들기 위한 사례 선택이나 모델 튜닝은 하지 않았다.
RCAEval 최종36건과 native test는 계속 봉인한다.

## 출처와 한계

- [공식 배포·라이선스 metadata(CC-BY-4.0)](https://zenodo.org/records/17105974)
- [export 선택](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/export.py)
- [변환 allowlist](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/sources/rcabench.py#L31-L92)
- [기간 추출](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/prepare_inputs.py)
- [정답 구성](https://github.com/OperationsPAI/chaos-experiment/blob/55f9ad16818e89aeed984594434e8fbc66c5d430/handler/groundtruth.go)

소스 코드 리비전과 아카이브를 생성한 정확한 코드 버전의 완전한 연결은 미확인이다.
코드의 의미와 실제 아카이브 측정값을 구분했다.
