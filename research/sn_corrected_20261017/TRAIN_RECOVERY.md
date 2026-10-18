# 학습 실행 제어 복구

## 발견과 판단

단계B DAG는4개 노드가 completed라고 통지했지만,
검증 노드의 TRAIN_VERIFY.md는 실제로 FAIL이었다.
완료 통지를 성공으로 처리하지 않았고 외부평가/선택잠금은 실행하지 않았다.

- R0/R1: 잘못된 작업 디렉터리에서 상대경로 runner.py를 호출해 exit2.
  두 순환의 started표식과 run폴더가 없음을 주담당이 확인했다.
  실제 모델 학습은 시작되지 않았으므로 새 모델을 중복 학습한 것이 아니다.
- R2: 기존 모니터 mon_ZXNEXVAQTGGQJFPY의 학습이 살아 있었는데
  작업 노드가 대기 상태로 먼저 반환해 DAG의 후속 검증이 일찍 실행됐다.
  원래 child의 후속 transcript와 TRAIN_R2.md에서 최종6개FIT_PASS,
  ROTATION_DONE 2 200 및 실제 watcher exit0을 확인했다.
  R2는 재실행하지 않는다.

## 복구 조치

학습 완료 대기는 주담당의 모니터가 소유한다.
R0/R1만 아래 절대경로 명령으로 시작했고, 모델·입력·설정은 변경하지 않았다.

```text
cd /home/gnho1236/r2/research/sn_corrected_20261017
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0
/home/gnho1236/r2/.venv-eadro/bin/python -B
/home/gnho1236/r2/research/sn_corrected_20261017/runner.py
train-rotation --rotation {0 또는 1}
```

- R0: mon_7RY6DWGAZ9D7FME4, parent bash_8.
- R1: mon_D2NY7AVB2ZSWYJNS, parent bash_9.
- R2: 기존 완료 증거 TRAIN_R2.md 유지.

완료된 run에 대한 sdk.send는 node_not_continuable로 거부됐다.
새 학습을 만들지 않고 task_output의 기존 R2 후속 기록으로 완료 근거를 회수했다.

R0/R1 실제 exit0을 받은 뒤 같은 DAG run
dag_9feb01ee-b39e-4224-b709-82fb460d8ee6을 amend한다.
학습 노드는 “이미 실행된 영수증 검증”으로 변경하고
잠금 검증 노드를 다시 실행한다. 기존 FAIL기록은 삭제하지 않고 복구 PASS를 덧붙인다.
실행 중인 모니터를 확인하려고 같은 학습 명령을 다시 호출하지 않는다.
