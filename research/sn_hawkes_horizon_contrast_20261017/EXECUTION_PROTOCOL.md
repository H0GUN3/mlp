# 실행 계약 — 실제 효과 확인 전 고정

## 범위

GATE READY와 사용자 최신 대조 실행 요청에 따른 phase2다.
원본 불변, SN train316/validation78만 해석·사용한다. test169+unassigned1과
TT/RE2 관측은 decode하지 않는다. 원 NPZ stream의 비선택 바이트를 건너뛰는
것과 배열로 해석하는 것을 구분해 접근 증거에 기록한다.

## 두 arm

- relative: 기존 SN200 DiagMLP seed11/23/37의 선택 모델·예측·이력 재사용.
- absolute: 같은 relative knots에 end_times=original_window_start+10.
- 양쪽 seed42+original_window*12+node, 길이10, 동일 half-open event set,
  7템플릿/빈bin[0]/jitter1e-5/decay3/baseline.2/defaultmax_iter50.
- 입력의 metrics/traces/labels와 services/graph/split은 동일하다.
- 빈 로그 그룹은0. 출력 finite/비음수/shape 검사, 경고·상한 도달을 기록.
  상한 도달 자체는 기존 허용 동작이므로 실패로 위장하지 않되 수렴 주장 금지.
  NaN/음수/입력 경계 오류는 중단. clipping/scaler 추가/solver 변경 금지.

## 입력 인터페이스 (고정)

새 output만 `inputs/`에 생성:
- selected.npz: metrics/traces/logs/labels, logs는 기존relative값;
  indices(int64 원본정렬), log_absolute(동일 W,N,E shape).
- metadata.json: 원래 services/edges/event_count, 허용 windows 및 original_indices,
  train_positions/validation_positions(기존 split 순서의 새 배열 위치),
  original_split_sha256, 입력/출력/소스 해시와 선택/skip 증거.
- preparation.json: status PASS, actual probe시간/총량예상, 모든 허용 relative
  nonemptygroup의 exact equivalence, absolute finite/warning/cap, 보호경계와
  unchanged array 검사, input-difference summary.
출력은 완성·검증 후에만 발행하고, 실패/부분 출력은 덮어쓰지 않는다.

## 실행기와 학습

새 run_horizon.py의 CLI:
- `--self-check`: 합성 fixture만.
- `--preflight`: 위 입력/기준config·split·scaler·환경·초기화/순서 확인.
- `--seed 11|23|37`: `runs/absolute_seed_SEED/`에 새 학습.
native_train의 안전한 pure/model helper는 import해도 되지만 load_inputs와
load_prepared/main/run_training(기존 wholeload)는 호출하지 않는다.

각 모델은 원래 NativeReference(kind=diagmlp,N12,E7), float32 CPU,
Adam.001/betas.9,.999/eps1e-8/weight_decay0, batch256,200epoch400updates.
Python/NumPy/Torch seed, 동일 초기화 호출 순서, RandomState(seed) shuffle,
학습/검증 원래 행 순서, joint CE .5/.5, strict-min validation joint loss/
earliest tie를 보존한다. Torch2threads/interop1/deterministic.
TRAIN-only scaler 수치는 기존 scaler.npz와 array-exact 비교한다.
기존 checkpoint는 학습 입력이 아니며 기존 결과를 덮어쓰지 않는다.
**새 own checkpoint** 저장/역직렬화/허용validation replay는 실행 검증을 위해
허용한다. phase1의 checkpoint 금지를 새 학습 산출물 검사 금지로 확대하지 않는다.

runner parity의 최소 검사로 seed11 상대 입력의 1epoch를 메모리에서 재생해
기존 history[0]의 loss/score/update와 비교할 수 있다. 이는 runner변경 경로의
검증이며 기존 relative200epoch 재학습이 아니다. 필요하지 않은 추가 arm 금지.
parity 실패시 새3fits를 실행하지 않고 원인을 기록한다.

각 seed 결과: config/history/summary JSON, checkpoint.pt,
validation_predictions.npz(indices는 original_indices),
필요시 train prediction은 허용train만. 최소 validation bitwise replay와
최소손실 선택 검사 필수. 기존baseline validation과 공통indices/labels확인.
학습 전후 초기 tensor 비교는 같은 source와seed재생으로 확인하고 과거 저장되지
않은 초기 hash가 존재한다고 주장하지 않는다.

## 자원·보호·검증

- Hawkes최대2worker,각1thread. 초기에 서로 다른 크기5group 정도 실제pairedprobe,
  결과재사용. 보수적 feature예산1500초 이내일 때만 전체생성.
- 모델최대3개동시,각CPU2thread. 긴명령 monitor timeout_ms1800000 명시.
- CLI/Python3.8은 기존 /home/gnho1236/r2/.venv-eadro/bin/python -B.
- tests·진단 후 실제프로세스exit0까지 확인. producer가live인채 완료응답 금지.
- 실패시 로그보존, 같은출력을 덮어쓰는 자동retry 금지.
- baseline 및원본hash불변, noinstall/download/gitcommit, 보호자료미decode 확인.
- 새 코드는 apply_patch로 작성; 프로그램 출력은 owned inputs/runs 아래만 생성.

## phase2 DAG

prep deep-low(압축멤버 선택·ragged로그·solver결정성 결합),
runner unspecified-low(기존helper를 이용한 동일훈련 경로),
contract quick(계약의 source/field 일치):
세 producer → preflight quick → fit11/23/37 quick → verify unspecified-low.
최대3개 producer/fit 병렬, 총8노드. 각각소유범위는prompt에명시.
다음 phase3는 실제 exit/inputs/predictions가 확보된 뒤 새run으로
독립점수·paired사례·보고를 수행한다. 모든실험완료와혼동하지않는다.

실행 run_id: `dag_16f6fc1f-81f1-464b-9cd5-539e09785fa3`
key: `sn-hawkes-horizon-execution-20261017-v1`
8노드 시작, 정의 warnings0. 부모가 EXECUTION_VERIFY와 원 근거를 읽고
phase3로 넘어간다. 실패 노드는 같은 run에서 수정하며 완료 producer는 재사용한다.

## 실행 연결 정정

입력 producer는 PASS이며 전체 입력을 다시 만들지 않는다. 첫 preflight 노드는
prompt의 runtimepreflight.json과 runner의 preflight.json/status 이름 차이로
명령 자체를 실행하지 않았다. 이는 기존 권한 안의 파일 연결 문제다.
- preflight 소유권: PREFLIGHT_CHECK.md, preflight.json, preflight.status,
  logs/preflight-* 실행 로그. 이전 runtimepreflight.json NOTREADY 이력 보존.
- runner 실제 학습 경로는 runs/absolute_seed_SEED로 통일. newruns 미채택.
- artifact_hashes 등은 실제 summary/config/manifest 필드에서 검증하며,
  예상 필드가 없다고 검사를 생략하지 않는다.
- runner 노드는 완성된 허용 inputs의 schema를 읽고 통합 fixture·테스트를
  보완할 수 있다. 실제 3개 학습은 preflight PASS 후에만 진행한다.
