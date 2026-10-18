# SN Rotation 0 실행 기록

**결과: FAIL — 학습 미실행.** 요청한 명령이 프로젝트 디렉터리에서 실행되지 않아 Python이 `runner.py`를 찾지 못했다. 재시도하지 않았다.

- 원래 명령: `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B runner.py train-rotation --rotation 0`
- 작업 디렉터리: `/home/gnho1236/r2` (요청된 `/home/gnho1236/r2/research/sn_corrected_20261017`가 아님)
- 모니터 세션 ID: `bash_2`
- 실제 종료 코드: `2`
- 오류: `/home/gnho1236/r2/.venv-eadro/bin/python: can't open file 'runner.py': [Errno 2] No such file or directory`
- 센티널: `FIT_PASS`, `ROTATION_DONE` 모두 없음
- 실행 예산 선택·선택 epoch·업데이트·학습 단계 비용: 실행 전 실패하여 해당 없음
- 경고: 유효한 학습 실행 및 `rotation_0.done.json` PASS 증거가 없다. 산출물은 만들지 않았으며, 회전은 완료되지 않았다.

## RECOVERED FAIL — 독립 산출물 검증 미완료 (2026-10-17)

초기 작업 디렉터리 오류 기록은 위와 같이 보존한다. 이후 부모 실행 기록
`MAIN_TRAIN_EXECUTION.md`는 실제 회전 0 명령의 `exit_code: 0`, 여섯
`FIT_PASS`(eadro/diagmlp × seed 11/23/37), `ROTATION_DONE 0 200`을
보고한다. `TRAIN_RECOVERY.md`는 재실행 대상이 R0/R1뿐이었음을 기록하고,
`rotation_0.done.json`은 R0를 PASS로 기록한다. 최초의 경로 오류 호출은
Python이 runner를 열기 전에 종료했으므로 모델 실행 수에 포함하지 않는다.

**이 검증 영수증의 최종 판정: FAIL (필수 독립 검증 증거 미확보).**
이 검증에서 여섯 run 디렉터리의 실제 `config.json`, `history_200.json`,
`best.pt`, `last.pt`를 각각 읽어 저장된 해시와 대조하거나, history에서
validation event NLL 최소값 및 earliest-tie 선택을 독립 재계산하지 못했다.
완료 요약은 6개 모두 200 epochs / 1,000 updates, best epoch
`[1, 23, 1, 8, 3, 2]`(<180), source/input hash 일치를 보고하며 이에 따르면
연장 조건이 발생하지 않았지만, 요약만으로 파일 대조와 재계산을 증명할 수
없다. 따라서 요구된 산출물 corroboration은 미완료이고, 누락된 증거는 FAIL로
처리한다. 이 FAIL은 부모 producer의 보고된 exit 0이나 done 기록을 대체하지
않으며, 실제 학습 완료 자체가 실패했다고 단정하지도 않는다.

- producer 증거: `MAIN_TRAIN_EXECUTION.md`의 rotation 0 실제 완료 기록
  (monitor `mon_7RY6DWGAZ9D7FME4`, parent `bash_8`, exit 0).
- 기록된 요약: `rotation_0.done.json` PASS 및 여섯 run summary.
- 독립 checker 종료 코드: 없음 — 검증 명령을 실행하지 않았다.
- 추가 학습/평가/준비 실행: 없음.
