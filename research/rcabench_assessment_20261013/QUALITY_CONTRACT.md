# RCABench 변환자료 품질 감사의 판정 경계

이 문서는 `quality_audit.py`가 실행하는 기존 조건을 설명한다.
학습·특징 생성·실험용 분할·원자료 전체 추출은 하지 않는다.
기존 native/RCAEval 자료나 동결 모델에는 접근하지 않는다.

## 단계별 의미

1. **메타데이터 후보:** 공식 MD5가 맞고, 필요한 파일과 해석 가능한 기간·정답 목록이 있다.
   단일 항목 정답은369사례다. 이 수를 독립 유효 사건 수로 부르지 않는다.
2. **실제 변환자료 검사:** 모든 파일을 한 번 순회하며 파일별 SHA256과 Parquet footer를 읽는다.
   정상/이상 gauge·sum·trace의 필요한 열은 실제 행으로 읽어 타입·null·유한값·기간을 확인한다.
   로그·histogram·conclusion은 footer만 검사하며 본문 품질을 검증했다고 하지 않는다.
3. **최소 정답 관측 지원:** 네 core 파일(정상/이상 gauge·trace)이 읽히고 비어 있지 않으며,
   정답 서비스에 유효 행이 각 파일에서 적어도1개 있어야 한다.
   유효 행은 UTC timestamp, 해당 기간 안의 시각, 빈 문자열이 아닌 service,
   메트릭의 유한 value·이름 또는 trace의 비음수 duration·비어 있지 않은 trace/span ID를 요구한다.
   이것은 유용한 진단 신호나 충분한 coverage가 있다는 보장이 아니다.
4. **현재9채널 입력 정합성·독립 사건 판정:** 위 조건만으로 통과시키지 않는다.
   정확한 물리량·단위·원시 구분 정보, 호출 연결·시계 의미, 수집 이력은 별도 조건이다.

`.invalid`는 자동 제외 기준이 아니다. raw-pack 검사와 변환 출력 계약이 다를 수 있다.
불리한 사례도 census에 포함하고 표식과 관측 결과를 별도로 남긴다.
`profile_error`는 미검증 상태이며, 파서/환경 문제와 원자료 문제를 확인하기 전
그 자체를 데이터 불량의 확정으로 사용하지 않는다.

## 시간과 coverage

공식 추출 SQL은 `BETWEEN start AND end`로 양 끝을 포함한다.
모든1,422사례의 metadata에서 NORMAL_END와 ABNORMAL_START가 같다.
따라서 정확히 그 시각의 관측은 정상·이상 파일 양쪽에 포함될 가능성이 있다.
검사기는 양쪽 경계에서 공유되는 `(trace_id, span_id)` 수를 별도로 집계한다.

기간 적합성 검사는 이 소스 계약대로 닫힌 구간을 사용한다.
10초 bin의 관측 개수는 상한 시각을 제외한 반열린 구간에서 계산한다.
“관측된 bin 수”는 원래 있어야 할 모든 관측이 수집됐다는 collector coverage가 아니다.
timestamp는 실제 Arrow 단위로 계산하고, 큰 정수 tick은 문자열로 기록해 JSON 소비자의
부동소수점 반올림을 피한다. duration의 ns 해석은 공식 분석기 계약에 근거한다.

parent ID 열을 읽는 것과 parent 참조를 전부 복원하는 것은 다르다.
이번 census는 참조 해소율·중복 span의 내용 충돌·critical path·self-time·물리적 clock
정합성·창 종료 시점의 duration 가용성을 확정하지 않는다.

## 중복과 사건 수

- 모든 파일 내용의 SHA256으로 변환 페이로드의 바이트 단위 중복을 집계한다.
- 네 core 관측 파일이 모두 같은 사례 묶음도 별도로 기록한다.
- 동일 관측 파일은 데이터 공유의 근거이지 주입 사건의 자동 병합 규칙은 아니다.
- 파일이 서로 달라도 수집 세션·부하·고장 구성이 독립이라는 증거가 되지 않는다.
- 단일 항목369사례에는129개의 `(service, fault_type)` 조합이 있다.
  같은 조합이라도 강도·매개변수가 같거나 독립적인 반복이라는 보장은 없다.
- 사례 이름의 접두사 `ts0`–`ts9`를 발견했지만 이것을 수집 세션 ID라고 단정하지 않는다.

## 현재 메트릭 계약과의 차이

첫 사례에서 gauge에는 `container.cpu.usage`, `container.memory.usage`,
`container.memory.working_set` 등이, sum에는 `container.cpu.time`,
`k8s.pod.network.io` 등이 있었다. 실제 time은 `timestamp[ns, tz=UTC]`,
trace duration은 `uint64`였다. 이 표본만으로 전체 사례에 일반화하지 않는다.

공식 FSE 변환 코드의 gauge/sum allowlist에는 `MetricUnit`/`Unit`이 없다.
Attributes는 destination/source workload와 destination/source만 남기며,
resource 속성은 Kubernetes 식별 정보만 남긴다.
따라서 CPU user/system mode나 network direction/interface가 상류에 있었더라도
이 변환 경로에서는 보존되지 않는다. 원래 수집됐는지 자체는 이 코드로 확정할 수 없다.

이름이 비슷한 JVM system/process CPU 메트릭을 native Eadro의 kernel/user CPU와
같은 물리량으로 취급하지 않는다. 총 network I/O를 임의로 rx/tx로 나누지도 않는다.
현재7메트릭+2trace 채널을 충실히 재구성할 수 있다는 검증 없이,
369개 또는 최소 관측 지원 수를 현재 모델에 바로 투입 가능한 사건 수로 표시하지 않는다.

## 환경과 자원

resident kernel의 NumPy2.2.6과 기존 user-site Arrow 사이에서 ABI 오류가 발생했다.
공용 환경이나 패키지를 바꾸지 않고, 기존 `.venv-mlp`의
NumPy1.26.4 / Arrow19.0.1이 실제 로딩됨을 확인해 사용한다. 새 설치는 없다.
확인한 가용 page 메모리는 약105GB, 가장 큰 저장 member는8,235,968B다.
전체 자료를 메모리에 올리지 않고 파일 하나씩 처리한다.
Arrow CPU/I/O 스레드는 각각2개로 제한한다.

추가 검사4개는 유한값·기간 경계·빈 ID·없는 정답 관측·`.invalid`의 비자동 제외를 확인한다.
검사 종료코드0(`Ran 4 tests in 0.009s`, `OK`)을 확인했으며
두 새 Python 파일의 LSP 오류 진단도 없다.

## 재현

```text
cd /home/gnho1236/r2/research/rcabench_assessment_20261013
../../.venv-mlp/bin/python -B -m unittest -v test_quality_audit
../../.venv-mlp/bin/python -B quality_audit.py --report quality_audit.json
```

보고서가 이미 있으면 덮어쓰지 않는다. 변경 없는 검사를 반복 실행하지 않는다.

## 소스 근거

- [변환 열 선택과 속성 allowlist](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/sources/rcabench.py#L31-L92)
- [gauge·sum 추출과 MetricUnit](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/prepare_inputs.py#L43-L112)
- [trace 추출](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/prepare_inputs.py#L185-L207)
- [연속 기간 계약](https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/cli/prepare_inputs.py#L279-L297)

소스 리비전과 실제 아카이브 생성 버전의 완전한 일치는 미확인이다.
