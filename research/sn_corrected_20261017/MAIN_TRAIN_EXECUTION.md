# 부모가 회수한 실제 학습 종료 근거

R0/R1은 경로오류로 프로그램 시작 전에 끝났던 두 호출만 바로잡았다.
frozen runner·입력·hyperparameter를 변경하지 않았다.
각 실제 model run은 한 번씩 실행됐으며 R2는 재실행하지 않았다.

## Rotation 0

- monitor: mon_7RY6DWGAZ9D7FME4; parent bash_8.
- 실제 완료 알림과 완료 후 bash_output 모두 `exit_code: 0`.
- 실행 경로는 TRAIN_RECOVERY.md의 절대 runner.py 경로.

```text
status: completed exit_code: 0
FIT_PASS 0 eadro 11 200
FIT_PASS 0 eadro 23 200
FIT_PASS 0 eadro 37 200
FIT_PASS 0 diagmlp 11 200
FIT_PASS 0 diagmlp 23 200
FIT_PASS 0 diagmlp 37 200
ROTATION_DONE 0 200
SN_ROTATION_0_RAW_EXIT=0
```

## Rotation 1

- monitor: mon_D2NY7AVB2ZSWYJNS; parent bash_9.
- 실제 완료 알림과 완료 후 bash_output 모두 `exit_code: 0`.

```text
status: completed exit_code: 0
FIT_PASS 1 eadro 11 200
FIT_PASS 1 eadro 23 200
FIT_PASS 1 eadro 37 200
FIT_PASS 1 diagmlp 11 200
FIT_PASS 1 diagmlp 23 200
FIT_PASS 1 diagmlp 37 200
ROTATION_DONE 1 200
SN_ROTATION_1_RAW_EXIT=0
```

## Rotation 2

원래 producer st_01a148f9의 후속 transcript와 TRAIN_R2.md를 읽었다.
mon_ZXNEXVAQTGGQJFPY가 여섯 FIT_PASS, ROTATION_DONE 2 200,
watcher completed(exit code0)을 전달했다.
초기 DAG node output은 “실행 중”인 과거 상태였고, 실제 완료는 그 뒤였다.
TRAIN_R2.md의 현재 PASS와 원래 실행을 재사용한다.

세순환 모두200epoch에서 종료됐으며400연장은 발생하지 않았다.
이는 실제학습완료 근거이지 외부평가 성능이 아니다.
같은DAG를학습영수증검증으로amend한 뒤 runner lock을 실행한다.
