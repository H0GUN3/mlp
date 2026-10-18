# OpenRCA·GAIA 추가 확인 결과

## 결론

추가 조사는 필요했고, README 추정치에서 **실제 배포 크기와 정답 후보 수**까지
확인 범위를 넓혔다. 다만 아직 신규 최종평가 데이터로 지정하지 않았다.
수 GB 관측 파일 전체는 받지 않았다. ZIP 디렉터리와 작은 정답/주입 기록,
공식 배포표만 읽었으며 모델 학습·분할 변경·최종시험은 없었다.

## 1. 공식 OpenRCA의 정확한 크기

| 파일 | 압축 바이트 | 압축 GB | 해제 파일 합계 GB |
|---|---:|---:|---:|
| Bank.zip | 2,829,139,841 | 2.829 | 26.400 |
| Market.zip | 2,865,427,796 | 2.865 | 24.594 |
| Telecom.zip | 3,071,992,930 | 3.072 | 17.659 |
| 합계 | **8,766,560,567** | **8.767** | **68.653** |

GB=10^9B. 전체 압축은 약8.164GiB다.
해제된 파일 내용 합계는68,652,646,757B이며 파일시스템 여유 공간/학습 캐시까지
포함한 설치 용량은 아니다. 따라서 공식80GB 저장공간 권고와 모순되지 않는다.

Drive 공개 viewerData의 크기, 다운로드 HEAD의 Content-Length,
실제 HTTP206 Content-Range를 서로 대조했다. 해제 크기는 ZIP 중앙 디렉터리에서
95/62/155개 항목을 합산했다. ZIP 전체를 받거나 전체 SHA256을 검증한 것은 아니다.

### 정답을 실제로 확인한 결과

record.csv4개에 고장 기록335행이 있었고 동일 정답 행의 완전 중복은0이었다.
공식 `main/generate.py`처럼 시스템/cloudbed별 Unix timestamp//1800으로 묶으면
평가 구간298개다. 단일 고장 구간261개, 복수 고장 구간37개다.
query.csv4개의335행과 각 구간의 고장 수가 전부 일치했다.
`task_index`는7가지 질문 종류이며 고장 사건 ID가 아니다.

| 자료 | 고장 기록 | 단일 고장30분 구간 | 단일 서비스로 변환 가능한 단일 고장 후보 |
|---|---:|---:|---:|
| Bank | 136 | 118 | 0: 현재 논리 서비스 매핑 미확정 |
| Market/cloudbed-1 | 70 | 44 | 27 |
| Market/cloudbed-2 | 78 | 48 | 32 |
| Telecom | 51 | 51 | 31 |
| 합계 | **335** | **261** | **90** |

90개의 구성은 원래 service 정답40개+Market pod변환31개+Telecom pod변환19개다.

- Market은 공식 문서에10개 서비스와 서비스당4개 pod가 열거되어 있다.
  `<service>-0/-1/-2`와`<service>2-0`의 문서화된 가족을 같은 서비스에 대응했다.
- Telecom은 공식24,349B 배포표를 메모리에서 CSV로 변환했다.
  docker_001..004→container_001→csf_001,
  docker_005..008→container_002→csf_002 연결을 사용했다.
- 노드 고장53개 구간은 여러 서비스에 영향을 줄 수 있어 하나로 억지 매핑하지 않았다.
- Bank118개 단일 pod 고장 구간은 별도 pod/컴포넌트 과제에는 후보가 될 수 있다.
  논리 서비스 귀속 근거가 없어 이번 서비스 수에 넣지 않았다.

추가로 Market/cloudbed-1의30분 구간1개(Unix//1800=915468)는
두 고장이 모두 emailservice로 합쳐진다. 이를 허용하면
**단일 논리 서비스 정답 구간91개**지만, 엄격한 단일 고장90개와 구분한다.
91개는91회 주입이라는 뜻이 아니다.

**90/91은 정답 단위 변환 기준의 후보 수다.** 실제 관측 행, 필수 채널,
정상 기준과 입력 구간을 검사한 실험 가능 수량은 아직 아니다.
또한 실패한 pod의 소속 서비스를 맞히는 과제로 바뀌므로, 그 서비스의 모든 replica가
실패했다는 뜻이 아니다. 원 OpenRCA의 시간·원인·컴포넌트 종합 점수와도 다르다.

## 2. GAIA MicroSS의 실제 규모

| 범위 | 배포 파일 바이트 합계 | ZIP 디렉터리상 해제 바이트 합계 |
|---|---:|---:|
| 메트릭 | 1,788,356,895 | 10,384,890,806 |
| trace | 1,610,091,805 | 8,343,966,340 |
| run/주입 기록 | 823,135 | 7,824,372 |
| 합계 | **3,399,271,835 = 3.399GB** | **18,736,681,518 = 18.737GB** |

business 로그까지 포함한 네 모달리티의 배포량은약5.759GB다.
이번에는823KB run.zip 전체와 분할 ZIP 마지막 부분의 **중앙 디렉터리만** 읽었다.
분할 trace ZIP은32조각이고, 그 안에10개의2021-07 trace CSV가 있다.
메트릭은35조각이며10,818개 디렉터리 항목을 확인했다.
8월 trace CSV는 이 고정 배포본에 없다.

### 주입 사건 수: 로그 행 수와 구분

run CSV의 실제 레코드는36,574개다. 그중 다음을 분리했다.

| 유형 | 7월 | 8월 | 합계 |
|---|---:|---:|---:|
| memory_anomalies | 652 | 715 | 1,367 |
| cpu_anomalies | 15 | 66 | 81 |
| 파일 이동 프로그램 | 43 | 36 | 79 |
| 접근 권한 예외 trigger | 15 | 20 | 35 |
| 위4유형 합계 | **725** | **837** | **1,562** |

별도로 QR 만료를 유도하는 업무 동작32,693개, 정상 메모리 해제 표식29개,
주입 실패 로그10개를 구분했다. 업무 동작을 무조건 정상이라고 판정한 것이 아니라,
자원 고장과 동일한 독립 RCA 사건으로 자동 계산하지 않은 것이다.

memory/CPU/파일 이동1,527개는 명시적 start/duration을 파싱했고,
대상·유형·시작·지속·메모리양 기준으로 완전히 같은 주입 표식은 없었다.
그렇다고 서로 독립적인1,527개 실험이라는 뜻은 아니다.

### 보수적인7월 후보 수

1. memory+파일 이동: **695개**. 모두 기록상600초이며 종료 로그와 대체로 대응한다.
2. 시간이 겹치는 이 기록들을 연결된 사건 그룹으로 묶으면595그룹.
3. 여러 대상이 함께 포함된85그룹을 분리하면 **단일 대상510그룹**.
4. CPU의 기재된 기간 또는 접근 권한 trigger+1시간과 잠재적으로 겹치는 그룹도
   보수적으로 보류하면 **411그룹**.

이411은 **주입 메타데이터에 근거한 예비 후보**다.
실제 trace/metric 행의 정확한 시간 범위·누락과 정상 기준 구간은 아직 확인하지 않았다.
대상명 dbservice1/dbservice2 등10개 식별자를 그대로 유지했으며,
숫자 접미사를 임의로 없애서 논리 서비스로 합치지 않았다.

CPU81개 중8개는 기록된 지속 시간이1일을 넘으며 최대2,684,473초다.
로그 시각은 start와 거의 같은 위치여서, 메모리/파일 이동의 종료 기록과
기록 관례가 다르다. 잘못된 기록이라고 단정하거나 단위를 임의 수정하지 않았다.
이 기간을 문자 그대로 적용하면8월 메모리/파일 이동 그룹이 모두 잠재 중첩으로
걸리는 만큼, CPU 기록 의미의 확인이 중요하다.8월은 trace도 없어 현재 후보에서 제외했다.

### 채널과 라이선스

10개 trace 대상 모두7월 메트릭 파일 목록에 CPU total/user/kernel pct,
메모리 total, network in/out bytes 후보가 있었다.
그러나 `memory_working_set`과 같은 이름은 없었다. CPU 정규화, byte counter의
차분 여부, 메모리 working-set의 의미·단위까지 같다고 확인한 것은 아니다.
따라서 기존9채널을 그대로 복사하는 어댑터는 아직 만들 수 없다.

README는Apache2라고 쓰지만 고정 commit의 실제 LICENSE는GPL2였다.
데이터에 적용되는 조건을 확정했다고 하지 않으며, 재배포 전 확인이 필요하다.
이는 자료가 무조건 사용 불가라는 법적 판정이 아니다.

## 3. 연구용 판단

- OpenRCA는 **데이터량은 충분히 크지만, 우리 과제에 바로 대응하는 정답 수는
  335보다 작다.** 먼저 Market의59개 단일 고장 서비스 후보, 또는 Telecom까지
  합친90개를 검토하는 범위가 구체화됐다.
- GAIA는 **추가 사건 후보가 상당수 있으나 annotation 정리 비용이 있다.**
  현재 가장 설명 가능한 출발점은7월 메모리/파일 이동 중심의 보수적 후보들이다.
- 둘 다 아직 독립 최종평가로 지정하지 않았다. 기존 자료 계보 중복,
  동일 사건 누출, 실제 입력 품질, 서비스/인스턴스 정답 정의를 확인해야 한다.
- 자료를 연구용으로 변환하는 것은 원 논문 공식 점수 재현과 구분한다.
  선정 기준을 먼저 고정하고, 제안 모델 점수를 본 뒤 유리한 사례만 남기지 않는다.

## 4. 확인 방법과 출처

모든 분석은표준 CSV/ZIP/XML 파서로 수행했다. Excel 배포표는 수식 실행 없이
메모리 CSV로 변환했다. 네트워크 읽기는 요청별 크기 제한과 HTTP206 범위 검증을
적용했다. ZIP의 annotation CRC, GAIA run.zip의 고정 Git blob SHA1,
OpenRCA 정답 파일 SHA256,335개 질문의 고장 수 일치를 확인했다.
원문이 긴 도구 출력은 kernel에 보존한 전체 응답에서 필요한 값을 파싱했다.

- 공식 OpenRCA/배포 링크:
  https://github.com/microsoft/OpenRCA/blob/c1bd4af7f635171a1c31cdd567c07d698dff6abc/README.md
- 공식30분 묶음 생성:
  https://github.com/microsoft/OpenRCA/blob/c1bd4af7f635171a1c31cdd567c07d698dff6abc/main/generate.py
- Market 후보·4pod/서비스:
  https://github.com/microsoft/OpenRCA/blob/c1bd4af7f635171a1c31cdd567c07d698dff6abc/rca/baseline/rca_agent/prompt/basic_prompt_Market.py
- 공식 Drive 폴더:
  https://drive.google.com/drive/folders/1wGiEnu4OkWrjPxfx5ZTROnU37-5UDoPM
- Telecom 배포표:
  https://drive.google.com/file/d/14j_z6K5vqwY9sQvkPsygksbL7Dm4bpiR/view
- GAIA 고정 README:
  https://github.com/CloudWise-OpenSource/GAIA-DataSet/blob/238a9e24ae0b69e7e05dff112652a3fa62db88fd/README.md
- GAIA 주입 기록:
  https://raw.githubusercontent.com/CloudWise-OpenSource/GAIA-DataSet/238a9e24ae0b69e7e05dff112652a3fa62db88fd/MicroSS/run/run.zip
- GAIA 실제 디렉터리를 확인한 마지막 ZIP 부분:
  https://raw.githubusercontent.com/CloudWise-OpenSource/GAIA-DataSet/238a9e24ae0b69e7e05dff112652a3fa62db88fd/MicroSS/metric/metric_split.zip
  및 같은 경로의 `MicroSS/trace/trace_split.zip`.

정확한 수치·해시·규칙은 `openrca_gaia_audit.json`.
이 문서는 앞선 `DATA_CANDIDATES.md`의 OpenRCA ZIP 크기/단일 서비스 수량,
GAIA 주입 기록 수량 미확인 부분을 갱신한다. 실제 관측자료 품질과 최종 독립성은 여전히 미확인이다.
