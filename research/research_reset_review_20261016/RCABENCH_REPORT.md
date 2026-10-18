# RCABench 실제 확보본 전체 분석

2026-10-16. 대상은 확보된 **1,422개 사례 전부**다.
논문이 보고한 1,430개 구성·9,152회 주입과 같은 집합이라고 가정하지 않았다.
단일 정답이나 관측이 잘 갖춰진 사례만 고르지 않았다. 학습·분할 배정은 하지 않았다.

## 1. 조사 범위와 실제 근거

- 기존 archive: `../rcabench_assessment_20261013/rcabench-absolute_anomaly.tar.gz`.
  13,444,974,981bytes, 기존 획득 검사에서 배포 MD5 일치.
- 19,991개 member를 단일 순회하여 사례별 `injection.json`, `env.json`,
  `conclusion.parquet`만 파싱했다. 4,266파일, 15,090,330bytes.
- 대상 member의 경로·크기 및 sha256을 기존 전수 검사와 대조했다.
  filesystem에 archive member를 풀지 않았다.
- metrics/sum/traces의 기존 전수 품질 기록 `quality_audit.json`을 재사용했다.
  보호된 최종시험 자료나 새 원관측을 모델 특징으로 변환하지 않았다.
- 추출42.928초/peakRSS292,564KiB, 분석1.308초. 실제 실행 exit0.
  이는 자료 감사 비용이지 모델의 학습·추론 효율이 아니다.

핵심 산출물:
`metadata_details.json` 원 metadata/결론 요약,
`metadata_analysis.json` 전체 집계와 사례별 기록,
`verification.json` 독립 대조 및 설정 표적의 관측 지원.

## 2. 사용자가 실제 실패를 경험한 사례인가?

저장된 API 결론 **27,146행**을 검사했다.

| 확인 항목 | 실제 결과 |
|---|---:|
| 최소 한 API에 비어 있지 않은 Issues가 있는 사례 | 1,422/1,422 |
| 최소 하나의 `slo_violated=true`가 있는 사례 | 1,422/1,422 |
| Issues JSON 파싱 오류 사례 | 0 |
| 수치 요약의 누락·비유한값 | 0 |

종류별 판정 항목 수는 성공률2,197, 평균지연1,895,
p90지연1,122, p95지연869, p99지연588이다. 한 API에 여러 항목이 있으므로
이를 더해서 독립 장애 수로 세면 안 된다.

사례별 **가장 큰 API 성공률 하락**의 중앙값은85.88%p,
사례별 **가장 큰 API 평균지연 비율**의 중앙값은26.71배다.
이는 각 사례에서 변화가 가장 큰 API를 고른 기술통계이지,
전체 서비스의 평균 성공률/지연 변화나 모델 성능이 아니다.

### 실제 예

`ts5-ts-order-service-stress-svfvxk`의 JVM 메모리 주입 설정은
`order.service.OrderServiceImpl.getOrderPrice`를 가리킨다.

| 사용자 API | 정상 성공률 | 주입 구간 성공률 |
|---|---:|---:|
| POST `/api/v1/orderservice/order/refresh` | 1.0000 | 0.7364 |
| POST `/api/v1/travelservice/trips/left` | 1.0000 | 0.8360 |

같은 사례의 verifycode API는1.0→1.0, Issues는 비어 있다.
고장 조작, 일부 API의 사용자 영향, 원인 서비스 정답을 따로 볼 수 있는 예다.

**증거의 경계:** 수집자가 계산해 export한 SLI 요약·판정 기록을 확인했다.
원요청 수, 성공 판정 구현, 통계검정, 당시 적용한 API별 임계값과 활성화 시점은
독립 재계산하지 않았다. 정상 구간도 “주입 이전”이라는 의미이며,
모든 API가 절대적으로 건강했다고 보증하는 것은 아니다.
이 export는 `absolute_anomaly` 태그로 선택된 자료이므로,
영향 없는 주입·조용한 의미 오류·일반 정상 운영 전체를 대표하지 않는다.

## 3. 고장 종류의 실제 전체 분포

파일명의 `stress` 같은 단어가 아니라 저장된 fault_type과 고정된 공개 enum을 대조했다.

| ID | 종류 | 사례 |
|---:|---|---:|
| 0 | PodKill | 10 |
| 1 | PodFailure | 24 |
| 2 | ContainerKill | 89 |
| 5 | HTTPRequestAbort | 60 |
| 6 | HTTPResponseAbort | 44 |
| 7 | HTTPRequestDelay | 88 |
| 8 | HTTPResponseDelay | 89 |
| 9 | HTTPResponseReplaceBody | 51 |
| 10 | HTTPResponsePatchBody | 4 |
| 11 | HTTPRequestReplacePath | 39 |
| 12 | HTTPRequestReplaceMethod | 190 |
| 13 | HTTPResponseReplaceCode | 231 |
| 15 | DNSRandom | 1 |
| 16 | TimeSkew | 2 |
| 17 | NetworkDelay | 21 |
| 18 | NetworkLoss | 48 |
| 20 | NetworkCorrupt | 46 |
| 21 | NetworkBandwidth | 42 |
| 22 | NetworkPartition | 97 |
| 23 | JVMLatency | 7 |
| 24 | JVMReturn | 21 |
| 25 | JVMException | 43 |
| 27 | JVMCPUStress | 2 |
| 28 | JVMMemoryStress | 171 |
| 29 | JVMMySQLLatency | 2 |
| **합계** | **25종류** | **1,422** |

CPU·메모리 자원 고장만 있는 자료가 아니다. HTTP 계열796건(55.98%)이 가장 많고,
method/code 변경만421건이다. DNS1건, TimeSkew/JVMCPUStress/JVMMySQLLatency 각2건 등
매우 희소한 종류도 있다. 전체 평균만으로 모든 고장 종류에 대한 성능을 보장할 수 없다.

## 4. “정답 서비스 두 개”의 실제 의미

원래 `ground_truth.service`는1항목369건, 2항목1,053건이다.
두 항목이 두 번의 독립 주입을 의미하는 것은 아니다.

| 설정 범위 | 사례 | 설정의 필드 | 공개 생성 코드에서 확인한 의미 |
|---|---:|---|---|
| 단일 애플리케이션 | 369 | app_name 또는 app_label | pod/container/JVM 등의 대상 |
| HTTP endpoint | 796 | app_name, server_address, route/method | 동작 선택자는 app_name의 pod들 |
| DNS endpoint | 1 | app_name, domain | app_name의 pod들에서 domain 패턴 대상 |
| DB operation | 2 | app_name, db_name, operation/table | app_name의 JVM/MySQL connector 동작 |
| Network pair | 254 | source_service, target_service, direction | 두 endpoint 선택자와 방향 |

HTTP/DNS/DB의 정답 목록은 애플리케이션에 더해 상대 서비스·도메인·mysql을 담는다.
JVMMySQLLatency를 mysql 서버에 직접 고장을 주입한 사례로 읽으면 안 된다.
HTTP helper는 `server_address`를 실제 remote-host 필터에 사용하지 않으므로,
그 정답 쌍이 오직 그 두 서비스 사이의 트래픽만 바뀌었다는 증명도 아니다.

Network의 방향은both102/to80/from72건이다.
source 필드만 보고 유일한 물리적 원인으로 정하지 않는다.
구체적으로 어느 endpoint에 kernel rule이 적용됐는지는 실행 controller 확인이 필요하다.

### 실제 불일치 1건

`ts4-ts-food-service-container-kill-lv5htg`:

- display_config: `ts-food-service`의 container/pod.
- ground_truth: `ts-config-service`의 service/container/pod.
- 실제 실행 대상은 이 metadata만으로 확정할 수 없다.

나머지1,421건은 유형별 설정에서 예상되는 정답 집합과 일치했다.
원 목록의 첫 항목과 구성앵커도1,421건에서 일치하지만,
**그 순서만으로 원인을 선택한 것이 아니라 별도 설정 필드를 대조한 결과**다.
불일치 사례를 몰래 수정하거나 자료에서 삭제하지 않았다.

### 가능한 재구성

비network1,168건 중 이 충돌1건을 제외하면 **1,167건이 단일 설정 표적 과제의 검토 후보**다.
이는 최종 학습 수나 유일한 인과 원인이 증명된 사건 수가 아니다.
공개 selector 구현과 명목상 설정에 근거한 후보이며,
각 archive의 정확한 실행 revision·실제 활성화는 미확인이다.
기존 “단일 정답369/기초지원350만 사용”이라는 자동 필터는 정당하지 않다.

## 5. 관측이 얼마나 제공되는가?

기존 전수 감사에서는1,422건의 정상/이상 gauge와 trace 네 핵심 파일이 모두
읽을 수 있고 비어 있지 않았다. 그래도 **파일에 행이 있는 것과 정답 서비스에
충분한 정보가 있는 것은 다르다.**

| 기준 | 실제 결과 |
|---|---:|
| 원래 라벨의 모든 서비스에 정상/이상 gauge·trace 기초 행 존재 | 1,258/1,422 |
| 원래 라벨 중 정상 trace 기초 행이 없는 사례 | 139 |
| 원래 라벨 중 이상 trace 기초 행이 없는 사례 | 163 |
| Network254건 중 양쪽 라벨 모두 기초 지원 | 117 |
| 설정 표적 후보1,167건 중 표적의 네 파일 기초 지원 | 1,146 |
| 설정 표적 후보에서 정상/이상 trace 기초 행 누락 | 5 / 20 |
| 설정 표적 후보의 하나 이상 trace 구간 누락 | 21 |

기초 지원은 파일별 최소 한 유효 행이라는 낮은 기준이다.
모델 준비 완료, 충분한 시계열 길이, 성공적인 인과 관측을 의미하지 않는다.
이21건을 버리자는 뜻도 아니다. 장애가 trace를 끊었을 수 있으므로
누락은 분석할 현상이며, 비교 방법에 동일한 후보·마스크 정책이 필요하다.

전체 사례에서 라벨별 최소 trace 점유율의 중앙값은
정상1.0, 이상0.875였다(10초 bin 기준). 정상보다 이상 구간에서 관측이
성기게 나타날 수 있음을 보여 주지만 수집 장애의 원인을 확정하지는 않는다.

기존 검사에 `.invalid` 표식83건이 있지만,
변환 산출물과 raw-validity 검사 계약 차이가 있어 자동 제외 근거로 쓰지 않았다.

## 6. 입력 필드와 원형 방법 호환성

기존 전수 검사에서 gauge/sum/traces 투영행692,555,650개를 읽었다.
모든 Parquet footer 합은853,150,369행이다. 행 수는 요청 수나 독립 사건 수가 아니다.
이번에는 결론27,146행을 추가 파싱했으며 logs/histograms 본문은 새로 검사하지 않았다.

- gauge48개, gauge와 sum 합집합81개 metric 이름.
- CPU user/system mode, network direction/interface, metric unit을 복구할 구분자가
  보존되지 않았다. 이름만으로 원형 Eadro7개 채널과의 동등성을 주장할 수 없다.
- gauge 비유한값2,240,156개는 기존 검사에서 확인했다. 정상값0으로 덮지 않았다.
- service_name이 없는 전역/namespace 계측을 임의 서비스의 값으로 배정하지 않는다.
- trace에는 trace/span/parent ID, 서비스, 시작 시각, duration, kind/status/HTTP 속성이 있다.
  필드 존재만으로 완전한 호출 그래프·부모 연결·물리적 시계 정합성을 보증하지 않는다.

정답과 설정 앵커에 등장하는 서비스는 각각30종이다.
이30종은 전체 관측 후보 목록이 아니다. 정답에 나온 이름만 남겨 후보를 줄이면 안 된다.
실제 candidate inventory와 instance→service/host 매핑은 모델 준비 전에 별도로 고정해야 한다.

따라서 원형 방법을 새 자료에 옮길 때 필요한 adapter와 원형 핵심 encoder를 구분해야 한다.
특히 HTTP 논리 고장이 많은 이 자료에서 오류·상태·로그 정보를 빠뜨린 채
시간 attention만 바꾸는 것으로 문제를 해결할 수 있다고 단정할 수 없다.

## 7. 시각·반복·독립성

실제 관측 구간은2025-07-17~2025-09-06 UTC다.
정상 구간은1,421건이240초, 1건이60초다.
이상 구간은60~242초이며 중앙값240초다.
모든 사례에서 injection start/end는 metadata abnormal start/end와 일치한다.
이것은 metadata 일치이며 실제 fault 활성화·해제 시각의 독립 측정은 아니다.

관측 env namespace는ts0~ts9이며 사례 수는
170/179/221/210/274/258/28/34/25/23이다.
**display_config.namespace는 전부 `ts`**라 env namespace와 다르다.
원구성/실행 배포 매핑이 확인되지 않았으므로 둘을 같은 인스턴스 키로 취급하지 않는다.
시간 대조에는 관측 env namespace를 사용했다.

| 독립성 관련 확인 | 결과 | 해석 |
|---|---:|---|
| 같은 env namespace의 사례 간 양의 관측 구간 중복 | 0쌍 | 선택된 사례에서의 결과일 뿐 |
| 같은 namespace의 정상 구간과 다른 선택 주입의 중복 | 0쌍 | 미포함 주입까지 검사한 것은 아님 |
| 다른 namespace 사이의 양의 관측 구간 중복 | 760쌍 | 공유 host·중복 관측의 증명은 아님 |
| 고장 종류+display_config의 서로 다른 구성 | 1,362 | literal 구성 기준 |
| namespace/pod_name만 정규화한 구성 | 1,322 | 의미상 반복 후보 기준 |
| 정규화 구성의 반복 그룹/포함 사례 | 59그룹/159사례 | 최대7사례, 동일 사건이라는 뜻 아님 |
| 서로 다른 task_id | 1,422 | UUID가 다르다고 독립성이 보장되지는 않음 |

기존 검사에서는 **한 사례의 정상/이상 경계에서 trace/span identity를
공유하는 사례133건**이 확인됐다. 정상 끝=이상 시작이며 포함형 조회가 사용된다.
파일명이 normal/abnormal이라고 관측이 분리된 것은 아니다.
새 입력을 만들기 전에 경계와 중복 처리 규칙을 고정해야 한다.

현재 독립 사건 수는 확정하지 않는다. 단순한 파일 중복은 기존 검사에서 없었지만
공통 workload, shared host, 구성 반복, 수집 session의 의존성은 별도 문제다.
이 분석 그룹을 train/test 분할로 자동 채택하지 않았다.

## 8. 연구에 사용할 수 있는 범위

1. **단일 설정 표적 서비스 순위:**1,167건을 검토할 근거가 생겼다.
   관측 누락21건을 포함해 다루는 방식을 정해야 하며 최종 선정은 아직 아니다.
2. **원래 gold-set 호환 평가:**전체1,422건을 대상으로 any-hit와 set recall을 구분한다.
   이 목록은 전체 실제 영향집합이 아니므로 완전한 영향 범위 복원으로 주장하지 않는다.
3. **방향 있는 network 주입 쌍:**254건을 별도 과제로 삼을 수 있다.
   이는 실제 전파의 모든 인과 edge를 복구하는 과제와 다르다.
4. **장애 탐지:**모든 사례가 선별된 장애 사례이므로,
   주입 전 구간을 무조건 완전 정상으로 간주하지 말고 음성 표본·SLI 기준을 따로 정의한다.

**이 자료는 “쓸 수 없음”도 “바로 학습 가능”도 아니다.**
서비스 표적·허용 정답·관계 표적을 나누면 활용 범위가 넓어지지만,
정답 충돌, 관측 누락, 입력 구분자 손실과 그룹 경계를 먼저 명시해야 한다.

## 9. 출처와 재검증

이전 전수 근거:
`../rcabench_assessment_20261013/{REPORT.md,QUALITY_CONTRACT.md,metadata_inventory.json,quality_audit.json}`.

공개 코드:
- fault enum:
  `https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/datasets/rcabench.py`
- 주입/정답 생성:
  `https://github.com/OperationsPAI/chaos-experiment/tree/55f9ad16818e89aeed984594434e8fbc66c5d430`
  `handler/groundtruth.go`, `handler/{http,dns,network,jvm}_chaos.go`,
  `handler/httphelpers.go`, `chaos/{http,dns,network,jvm}_chaos.go`.
- 공식 배포: `https://zenodo.org/records/17105974`.

현재 코드:
`extract_metadata.py`, `analyze_metadata.py`, `verify_analysis.py`.
추출/분석 자기검사, 실제 전체 실행, 독립 집계·source/input hash 대조 모두 PASS.
세 스크립트의 LSP 진단은 없었다. 출력은 기존 파일을 덮지 않는 방식이다.

미확인: raw SLI 재검정, 정확한 생성 revision/실제 활성화, 전체 인과 관계,
완전한 배치·workload/session provenance, 모델별 실제 성능.
새 데이터 다운로드·설치·특징 cache 생성·학습·새 분할·최종시험은 수행하지 않았다.
