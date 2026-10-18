# 검증 기록

## 입력 진단 — 완료

- 명령: `.venv-eadro/bin/python -m unittest research.failure_causes_20261014.test_signals -v`
  및 `.venv-eadro/bin/python -m research.failure_causes_20261014.signals`
- 첫 실행 `mon_W089SPBKZN9G15Y5` / `bash_2`: exit1.
  기존 train.py의 unqualified ranker import에 필요한 경로가 새 진단 모듈에서 빠졌다.
  새 모듈만 기존 관례에 맞게 수정했다. 기존 파일과 테스트는 변경하지 않았다.
  실행 전 점검에서 saved standardizer의 counts 복수형 키도 바로잡았다.
- 재실행 `mon_V63FCP5WTSKV1FAR` / `bash_3`: 7 tests PASS, producer exit0.
  `SIGNALS_SYSTEM SN 36 325`, `SIGNALS_SYSTEM TT 81 3451`, `SIGNALS_PASS 117`.
- 입력·원본 source 해시를 읽기 전후 검증하고 signals.json/input_hashes에 기록.
  Directed 18개 저장 예측에서 모든 사건의 Top1을 원래 CV report에 대조.
- 별도 JS 집계로 signals.json의 117개 사건을 기존 errors.json과 대조:
  사건별 Directed Top1 차이 >1e-12 또는 창 개수 차이 0건.
  사건 균등 Top1 SN 0.6403556063278286 / TT 0.5424494601819166.
- LSP: signals.py, test_signals.py 각각 No diagnostics found.
- 명시적 Pyright: `pyright --project research/failure_causes_20261014/pyrightconfig.json
  research/failure_causes_20261014/signals.py research/failure_causes_20261014/test_signals.py`
  (`mon_9160HF2WYC6M7Z0A` / `bash_5`): 0 errors, 0 warnings, 0 informations, exit0.
- 별도 JS 검사: 117사건×5 probe의
  `(probe만 정답 credit − 모델만 정답 credit) = probe Top1 − 모델 Top1`
  585개 항등식 전부 오차 1e-12 이내.

## 학습 진단 — 완료

- [TRAINING_EVIDENCE.md](TRAINING_EVIDENCE.md)의 원 process 증거:
  `mon_YBQ5XND4Z82XQGNM` tests 4 PASS + producer exit0.
  테스트·producer의 재실행으로 원 증거를 대체하지 않았다.
- 54/54 validation logits 완전 일치, 1,053개 run-event 및
  351개 seed 평균 event metrics 기존 결과와 대조.
- 117개 사건 모두 커버. TRAIN은 사건마다 2fold×3seed=6회 평가를 사건 안에서 평균해
  독립 사건 수를 늘리지 않았다. validation은 1fold×3seed=3회.
- 240개 입력/source 해시 불변. 고정 checkpoint 추론만 수행했고 재학습하지 않았다.
- Child focused Pyright: `mon_54RQWPRMYK47AQ6C` exit0,
  0 errors, 0 warnings, 0 informations.
  초기 test import native-LSP 경고는 증거 문서에 보존했으며 suppression하지 않았다.

## 통합 정적 검사 — 완료

최종 명령:
`pyright --project research/failure_causes_20261014/pyrightconfig.json`
(`mon_ZPEV5GPNXCRAVYZR` / `bash_6`): exit0,
0 errors, 0 warnings, 0 informations.

최종 코드의 테스트는 입력 진단 7개 + 학습 진단 4개 = 11개 PASS.
검사 대상 코드가 변하지 않았으므로 이미 유효한 테스트를 중복 실행하지 않았다.
최종 REPORT_QA_PASS 22:
probe/학습 표의 12개 수치 행을 각 JSON에서 재구성해 일치 확인,
두 진단의 시스템별 네트워크 validation Top1 대조 2개,
모든 근거 링크 8개 파일 존재 확인을 통과했다.
