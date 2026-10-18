# SN 회전 2 학습 영수증

- 결과: **PASS**. `rotation_2.done.json`의 상태와 6개 실행이 모두 PASS이며, `rotation_process_exit: 0`.
- 실행 명령 (작업 디렉터리: `/home/gnho1236/r2/research/sn_corrected_20261017`):
  ```sh
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTHONOPTIMIZE=0 /home/gnho1236/r2/.venv-eadro/bin/python -B runner.py train-rotation --rotation 2
  ```
- 모니터: `mon_ZXNEXVAQTGGQJFPY`; 실제 감시기 완료 출력 `watcher completed (exit code 0)`.
- 완료 sentinel: `FIT_PASS 2 {eadro,diagmlp} {11,23,37} 200` 각 1회, `ROTATION_DONE 2 200`.
- 예산 결정: 6개 실행 모두 200 epoch. 200→400 연장 조건(어느 best epoch든 ≥180)은 충족하지 않아 추가 학습 없음.
- 검증 선택 best epoch:

  | 방법 | seed 11 | seed 23 | seed 37 |
  |---|---:|---:|---:|
  | Eadro | 1 | 1 | 1 |
  | DiagMLP | 15 | 11 | 15 |

- 각 실행 800 updates, 합계 4,800 updates. runner 기록 stage cost 합계 약 194.80초 (Eadro: 111.52초, DiagMLP: 83.27초).
- runner 소유 산출물: `rotation_2.started.json`, `rotation_2.budget.json`, `rotation_2.done.json`; `runs/rotation_2/` 아래 방법×seed 6개 디렉터리에 config, scaler, history, epoch log, stage receipt, best/last checkpoint 존재. Manifest에 기록된 해시 검증은 PASS.
- 경고: PyTorch가 CUDA 사용 불가로 autocast를 비활성화했다는 경고가 출력됨. 학습은 CPU 환경에서 종료 코드 0으로 완료.
- 평가 예측은 열지 않음 (`evaluation_opened: false`).
