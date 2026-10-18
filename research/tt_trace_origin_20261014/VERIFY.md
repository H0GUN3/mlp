# 좁은 TT 원자료 추적 검증

## 1단계: metadata gate

명령:

```sh
cd /home/gnho1236/r2 &&
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B \
  -m unittest research.tt_trace_origin_20261014.test_labels -v &&
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B \
  -m research.tt_trace_origin_20261014.labels
```

Monitor `mon_4TV2MTQ6QG9K96ZH`, bash_7: 3 tests PASS, producer exit0.
`METADATA_PASS 9 460`.
선정 창은 fault01 46(전체 주입구간 안44), fault02 43(41), fault04 45(43).
원 장애 metadata SHA256은 기존 TT 개발 manifest의 pin과 일치한다.
labels.py LSP No diagnostics found.

## 2단계: 원자료 복원

명령:

```sh
cd /home/gnho1236/r2 &&
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B \
  -m unittest research.tt_trace_origin_20261014.test_trace -v &&
PYTHONDONTWRITEBYTECODE=1 .venv-eadro/bin/python -B \
  -m research.tt_trace_origin_20261014.trace
```

Monitor `mon_FSPX9VEKH0MCHQMG`, bash_8: 3 tests PASS, producer exit0.

```text
TRACE_CASE ...:fault01 windows 46 root_spans 0 root_logs 0
TRACE_CASE ...:fault02 windows 43 root_spans 0 root_logs 1
TRACE_CASE ...:fault04 windows 45 root_spans 145 root_logs 102
TRACE_ORIGIN_PASS 134
```

134창×27서비스×10초=36,180 위치에서 count·latency·observed 세 배열 모두
`np.array_equal` 통과. 기존 trace producer를 다시 호출하지 않고
허용 초→창의 직접 lookup으로 원 span을 독립 집계했다.
중복 span weighting은 원 계약대로 유지하고 고유 ID 수도 별도 집계했다.
fixture에서 허용 창 밖 span은 duration/process 없이도 제외되는지 확인했다.
원자료 JSON 전체 바이트를 해시/파싱하지만 선택 창 밖의 관측은 분석하지 않는다.

metadata/span 파일은 기존 raw hash pin, 로그는 이번 시작/종료 snapshot이다.
모든 소비 파일은 읽기 전후 해시가 같고 source hash도 산출물에 보존한다.
로그 snapshot은 원 배포자의 서명이나 기존 배포 pin 검증으로 부르지 않는다.
trace.py LSP No diagnostics found.

## 전체 정적 검사

`pyright --project research/tt_trace_origin_20261014/pyrightconfig.json`
Monitor `mon_VDP23B1SJM8W6S2E`, bash_9: exit0,
0 errors, 0 warnings, 0 informations.
총 6개 집중 테스트 PASS. 유효한 테스트를 반복 실행하지 않았다.

## 3단계: 한 창의 저장 예측 대조

추가 raw 스캔이나 checkpoint 추론 없이 persistent Python kernel에서
기존 `errors.Inputs`의 hash-bound NPZ 읽기를 사용했다.
`trace.json/cases[1]/root_log_examples`가 정확히 1개인지 assert하고
그 `original_index=183`만 TT bundle 및 세 저장 prediction에서 찾았다.
각 선택 행의 root/event/index가 일치하고 유일한지 assert했다.

예측 파일:
`relationship_cv_20261014/results/TT/fold_1/seed_{11,23,37}/directed/predictions.npz`.
root는 ts-food-service, event는 첫 recording의 fault02다.
순위는 `1 + count(logits > root_logit)`, 동점 수는 `count(logits == root_logit)`.
값: seed11 4위/동점1, seed23 6위/동점1, seed37 4위/동점1.
1위 서비스는 REPORT.md 표에 보존했다.
6개 입력 binding을 재검증했고 모두 Top1 실패라는 assert를 통과했다.
최종 보고서 검사는 세 사건 표·전체 창/위치 수·근거 링크 6개에 대해
`TT_REPORT_QA_PASS 10`, 예측 표 3행과 로그 시각의 주입 구간 포함에 대해
`TT_CASE_QA_PASS`를 통과했다.

현재 manifest의 18 feature_names를 전부 확인했다:
7개 metric+latency+span count 각각 signed-log-z mean과 abs-z>2 fraction.
로그 채널은 없다. 이것은 해당 로그의 직접 미사용 근거이지
다른 채널로 같은 장애를 알 수 없다는 증명이 아니다.

## 한계

하나의 기록·3사건·134개 허용 창만 검사했다.
명목 주입 정합성, 원자료 부재, 로그 단서 제외를 확인했지만,
물리적 fault 활성화/수집 실패/무요청/로그 추가 효과를 확정하지 않았다.
원 입력·모델·checkpoint·분할·기존 산출물은 변경하지 않았다.
