# RCABench 실제 자료 적합성 검수

**2026-10-14 검수 완료:** [최종 검수 보고서](REPORT.md).
실제1,422사례 중 단일 항목369개, 최소 양모달 정답 관측 지원350개를 확인했다.
독립 사건/현재9채널 직접 입력 가능 수는 미확정이며 모델 학습·튜닝·최종시험은 하지 않았다.

사용자가 `실제 사건 수 확인`을 선택했다. 앞서 설명한13.445GB 공식 아카이브의
확보 및 내부 적합성 검수까지 진행한다. 학습·튜닝·최종시험은 하지 않는다.
기존 Eadro/RCAEval 자료와 동결 실험은 수정하지 않는다.

## 획득 대상

- URL: https://zenodo.org/records/17105974/files/rcabench-absolute_anomaly.tar.gz?download=1
- 로컬 수신 파일: 이 폴더의 `rcabench-absolute_anomaly.tar.gz`
  (다운로드 중에도 이 이름을 사용하므로 파일 존재만으로 완료를 판단하지 않는다).
- 압축 크기: 13,444,974,981B (12.52GiB)
- 공식 MD5: `96d32ae290e06be7d4e251be02b36cb8`
- 사전 확인한 사용 가능 디스크 공간: 414,122,774,528B.
- 완료 전에는 다운로드 파일을 검증된 자료로 취급하지 않는다.
- 전체 압축해제는 기본 작업이 아니다. 우선 순차 목록·JSON 검수 후 관측 검사 범위를 정한다.

## 검수 순서와 판정

1. 다운로드 완료와 배포 크기·체크섬 일치를 확인한다.
2. 사례별 정답, 정상·고장 구간, 필수 파일 목록을 집계한다.
3. 실제 스키마·필수 채널·시간 coverage·중복 가능성을 확인한다.
4. 총 사례, 단일 서비스 사례, 관측 조건 충족 사례와 제외 이유를 구분한다.
   수집 독립성이 확인되지 않은 사례를 독립 사건으로 확정하지 않는다.

현재 상태(2026-10-14): 다운로드가 종료 코드0으로 완료됐고,
로컬 파일 크기는 공식 값13,444,974,981B와 일치한다.
기존 검수 도구의 MD5 확인과 사례 메타데이터 순차 집계가 종료 코드0으로 완료됐다.
후속 변환자료 census도 완료했다. 실제 측정 범위와 남은 한계는 위 최종 보고서를 따른다.
독립적으로 사용 가능한 사건 수와 고정9채널 동등성은 확정하지 않았다.

## 1차 실제 인벤토리 결과

- 공식 MD5 `96d32ae290e06be7d4e251be02b36cb8` 일치.
- 실제 사례 폴더: **1,422개**. 논문의 1,430개 구성과 동일하다고 가정하지 않는다.
- `injection.ground_truth.service`가 단일 항목인 사례: **369개**.
- 두 항목인 사례: **1,053개**. 여러 독립 주입이 있었다는 뜻은 아니다.
- 정답·기간·필수 파일의 메타데이터 관문을 통과한 단일 항목 후보: **369개**.
- 같은 정답·기간·고장유형 조합의 중복 그룹: 0개. 수집 독립성이나 관측 파일 중복의 증명은 아니다.
- `.finished`: 1,422개. `.invalid`: 83개이며 그중 단일 항목 후보는 38개.
  표식의 계약이 다를 수 있어 38개를 곧바로 제외하지 않는다.
- 해제 파일 내용 총합: **13,635,126,699B (13.635127GB / 12.698701GiB)**.
  이는 변환된 Parquet/JSON 등의 합계이며, 중복 제거된 고유 원자료 용량은 아니다.

기계 판독 결과: `metadata_inventory.json`.
현재 `independent_usable_incidents`는 `null`이다.
369개를 검증된 추가 사건 수로 인용하지 않는다.

## 표식·정답 계약 대조

공식 FSE 소스에서 `.invalid`는 파일 유효성 검사 캐시, `.finished`는 변환 완료 캐시다.
raw-pack 검사기는 변환 폴더가 내보내지 않는 `k8s.json`과 `*_trace_id_ts.parquet`도 요구한다.
따라서 변환 폴더에 대한 잘못된 계약 적용이 `.invalid`의 원인일 가능성이 있으나,
각 표식의 실제 생성 이력은 확인하지 못했다. 실제 Parquet 검사를 대신할 수 없다.

`absolute_anomaly` export는 해당 tag의 이름과 변환 폴더 존재만으로 포함 대상을 정하며,
이 두 표식이나 `valid()`를 검사하지 않는다.
ground-truth 목록은 주입 구성의 expected-impact 규칙에서 생성된다.
HTTP·DNS·network·JVM-MySQL 등에서 endpoint/database 두 항목이 의도적으로 들어갈 수 있다.
별도 `labels()` 함수는 network 외에는 이름에서 service를 뽑으므로,
이를 injection 목록과 무조건 같은 정답 계약으로 취급하지 않는다.

소스 근거:
- [파일 검사와 캐시](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/datasets/rcabench.py#L249-L337)
- [변환 출력과 별도 labels](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/sources/rcabench.py#L446-L495)
- [export 선택](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/export.py)
- [ground truth 구성](https://github.com/OperationsPAI/chaos-experiment/blob/55f9ad16818e89aeed984594434e8fbc66c5d430/handler/groundtruth.go)

해당 코드가 아카이브의 모든 파일을 실제 생성한 정확한 버전이라는 증명은 아직 없다.

전송 중 점검: 최초 약11분51초에130MiB, 평균약188KiB/s로 표시됐으며
당시 예상 총 소요는약19시간이었다. 공식 API content 주소도1MiB 범위 요청에
206응답,1,048,576B,7.080472초(148,094B/s)로 비슷하게 느렸다.
별도 URL이 빠르다는 근거가 없어 기존 받은 내용을 유지하고 이어받기로 전환했다.
현재 `curl --continue-at - --max-time 86400`의 지속 모니터가 완료를 기다린다.
기존30분 제한 다운로드는 전환을 위해 의도적으로 종료했다. 실패한 새 검수가 아니다.
예상시간은 관측 속도의 외삽이며 완료 시각 보장이 아니다.

후속 대기 채널 점검에서 기존 `bash_9`의 실제 전송 화면을 확인했다.
curl 표시 기준 전송 경과 `4:50:45`, 진행률 `44%`, 수신량 `5593M`,
평균 속도 `328k`, 현재 속도 `362k`, 예상 잔여 `6:07:36`이었다.
이는 이어받기 구간의 curl 화면 값이며, 전체 아카이브의 검증된 바이트 수나 완료 판정이 아니다.
초기 관측보다 수신량이 증가했고 현재 전송도 진행돼, 정지·고아 세션으로 판단하지 않았다.
기존 지속 모니터를 유지하며 중복 다운로드·미완료 아카이브 검수는 시작하지 않았다.
