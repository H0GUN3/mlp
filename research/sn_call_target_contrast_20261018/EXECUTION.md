# 실행 영수증

## 입력 준비·학습 진입

- 원시 caller→callee 확인: `mon_2Z04JDF10AHM96WC`, exit0,
  `attribution_cases.json`. 확인 코드는 LSP 진단 없음.
- 입력 준비: `PREPARATION.md`와 `inputs/preparation.json`의 최종 PASS,
  실제 producer exit0. 최초 source-member guard 실패는 보존됐으며
  동결 사전을 재생성하지 않고 아직 하지 않은 집계만 복구했다.
- 부모가 mapping.json의 6,622개 직접 연결 모두의 parent/child original index가
  기존 TRAIN316 안에 있음을 독립 확인했다. 11개 singleton key, media602개 근거.
- 기존 owner trace 394창 exact, metrics/logs/labels/indices exact,
  span occurrence394,075회와 각1초의 정수 duration 합 보존.
- runner fixture3개: `mon_Q2MFZJ0GXDAXPP30`, exit0.
- 평가 fixture3개 및 지정 환경 Pyright:
  `mon_Z70XCTZAPHF7AQGZ`, exit0,0errors/0warnings.
- 실제 입력 모델 사전 검사:
  `mon_7GCTW0RSG4R51M0T`, exit0, `CALL_TARGET_PREFLIGHT_PASS`.
  `preflight.json`의 source/input/model/runtime hashes가 학습 gate다.

일반 workspace LSP는 기본 `.venv-mlp` 환경으로 `dgl` import를 못 찾았다.
진단을 억제하지 않았다. 명시적 `pyright --project pyrightconfig.json`은
실제 `.venv-eadro`/Python3.8 환경에서0errors/0warnings로 통과했다.

## 고정 학습 시작

아래 세 실행을 각각 한 번 시작했다. CPU2threads/process, 최대3개 병렬.
시작 영수증은 완료 증거가 아니다. 완료 exit0 및 두 budget checkpoint replay를
확인한 뒤 최종 결과를 채택한다.

| seed | monitor | 시작 상태 |
|---|---|---|
| 11 | mon_ZPDQX43Z17RJPW1N | 시작됨 |
| 23 | mon_9B6MQM1V5F9EGGF8 | 시작됨 |
| 37 | mon_15BJ5FJ0JYPRFF17 | 시작됨 |

각 실행 명령에서 SEED는11/23/37이다.

```sh
cd /home/gnho1236/r2
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 \
  .venv-eadro/bin/python -B research/sn_call_target_contrast_20261018/runner.py --seed SEED
```

선택 규칙·입력·소스·모델·예산은 `PROTOCOL.md` 및 `preflight.json`대로 동결했다.
학습 시작 이후 해당 동결 소스는 수정하지 않는다.

## 최종 완료 영수증

위 세 monitor 모두 실제 **exit0**과 `CALL_TARGET_FIT_PASS 11/23/37`을
반환했다. 각 실행200epoch/400update이며 연장·재시도·추가 fit은 없었다.
각 seed의 `summary.json`은50/200 선택본 모두 저장 logits·labels·indices의
bitwise replay 및 선택 loss의 exact replay를 확인한 뒤 생성됐다.

독립 NumPy 평가:

```sh
cd /home/gnho1236/r2
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  /usr/bin/python3 -B research/sn_call_target_contrast_20261018/evaluate.py
```

`mon_XKVSHD5WSK2A5AVC`, `bash_13`: **exit0 /
CALL_TARGET_EVALUATION_PASS 390**. Python3.10/NumPy2.2.6에서 생성한
`RESULTS.json`과 독립 프로세스의 재계산 결과가 정확히 같다.
기존6개·신규6개 budget별 예측을 같은 index/label로 대응했고, 원형 기준선
42개 hash 및 새 실행의 동결 source/input·checkpoint·예측 hash를 확인했다.
일부 예측만 뽑거나 seed를 제외하지 않았다.

모든 요청된 실험과 검증은 완료했다. 결과 해석과 비용은 최종 `REPORT.md`에 있다.
