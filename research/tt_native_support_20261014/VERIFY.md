# TT 제한 실험 검증 기록

## 실행 전 계약

PROTOCOL.md는 native-like 입력 준비 및 새 모델 fit 전에 작성했다.
기존 TT 4,069개 개발 행, 3fold×3seed×2baseline=18회,
200epoch/Adam0.001/batch256/dropout0.1/validation joint CE 선택을 고정했다.
q/zero 대조의 진입 기준도 결과 전에 고정했다.

## 부모 코드 — 완료된 검사

- `mon_4EXE5MV6QHT35EN9` / bash_11:
  `python -B -m unittest research.tt_native_support_20261014.test_experiment -v`
  6 tests PASS, exit0.
  native 두 baseline 및 q/zero branch 출력/유한 loss,
  초기 가중치·RNG 동일, q 가중치 gradient·zero control,
  보호/변경 index 거부, 사건 균등 동점·정상 제외,
  TRAIN-only scaler를 검사했다.
- 초기 baseline↔추가 zero column forward는 같은 수학 함수라도 GEMM reduction 순서가
  달라질 수 있어 synthetic 비교에만 rtol1e-5/atol1e-6을 사전 적용했다.
  **실제 checkpoint 재현은 같은 모델·같은 batch에서 np.array_equal이며 완화하지 않는다.**
- `mon_7C13TY281DRBQH8C` / bash_12:
  `python -B -m unittest research.tt_native_support_20261014.test_analysis -v`
  5 tests PASS, 이어서 부모 4개 파일 project Pyright 0 errors/0 warnings, exit0.
  사건 균등/빈 subgroup/동점 보존과 사전 gate 조건을 검사했다.
- `mon_J21FB7MSQ7GZQJ5D` / bash_13:
  실제 cache 사전 점검 CLI 추가 후 부모 4개 파일 project Pyright
  0 errors/0 warnings, exit0.
- 파일 LSP: experiment.py·analysis.py는 No diagnostics found.
  새 test_analysis.py의 workspace LSP import resolution 경고가 있었으며
  suppression하지 않았다. 명시적 project Pyright와 같은 결과라고 뭉뚱그리지 않는다.

## 입력 준비 — 완료

[PREPARATION_EVIDENCE.md](PREPARATION_EVIDENCE.md)와
`artifacts/execution_exit_evidence.json`의 실제 종료 증거를 확인했다.
producer `mon_CMSZCMS12YQ3QTBD` 및 독립 검증 `mon_GCX03WB8FWXB327H` 모두 exit0.
입력 테스트 8개 PASS, 현재 총 유효 테스트는 8+6+6=20개다.
처음의 source-pin 실패와 수정은 위 증거에 보존되어 있다.

- TT 4,069행/81사건/3fold 및 protected test1,744+unassigned1 제외 확인.
- metric/latency 원값, retained count와 reconstruction 완전 일치.
- normal reference 41,004줄 →59template/E60; 고유 span23,171/retained98,775.
- Hawkes7,845 fits, cap5,585, warning0/nonfinite0; **수렴은 미입증**.
- 실제 준비234.812초. 시간·RSS는 PREPARATION_EVIDENCE.md에 단계별 보존.
- TT.npz `2fa4ea589ae346deafb8b642a206273e7cbf6fd408481461f12103f32a67f597`
- TT.json `07c3ad8ae9331dc4d48b0e4a728e34a9d5bf2c87c985d8792d9d50220f355948`

## 실제 입력 연결 — 완료 / 기준 학습 — 진행 중

`mon_ZRKFPZ470FNRDVDJ` / bash_14: 전체 project Pyright 0 errors/0 warnings,
`experiment.py check`는 세 fold의 TRAIN/validation 실제 입력을 두 기준 모델에
연결해 `NATIVE_CACHE_CHECK_PASS`, exit0. cache_check.json에 source/input 해시와
분할 크기·정규화 범위를 보존했다.

검증 metric/trace 극값은 학습 범위보다 컸다. 값을 자르거나 scaler를 바꾸지 않고
scaler_audit.py로 fold별 최대 metric/trace 한 위치씩(총6개)만 읽기 전용 점검한다.
이는 새로운 정규화 실험이 아니다.

기준 학습 monitor `mon_DTZMRSPCE06TJQWB` / bash_15:
18회, 최대3개 동시 fresh process, 각200epoch.
restart 복원 시 자동 중복 fit을 막는 명시적 audit guard를 둔다.
초기 세 run의 첫 epoch 4.756/5.250/6.079초가 실제 관측됐다.
이후 아래와 같이 학습·재현·gate 판정까지 완료했다.

## 정규화 극값 점검 — 완료

첫 점검 `mon_TE41C43XJGQXFT7Q`는 NumPy bool_의 JSON 직렬화에서 exit1.
부분 출력 바이트는 `scaler_audit_failed.partial.txt`에 그대로 보존했다.
새 감사 코드의 boolean을 Python bool로 명시 변환한 뒤 해당 점검만 재실행:
`mon_YWFTSQJ75V4T077Y` / bash_17, `SCALER_AUDIT_PASS 6`,
focused Pyright 0 errors/0 warnings, exit0.
실험 코드·프로토콜·학습 프로세스는 변경하지 않았다.

여섯 최대 위치 모두 validation의 실제 root이고, metric은 cpu_load,
trace는 network_delay였다. TRAIN에서는 해당 root/type 조합이 빠져 있어
TRAIN 지표 범위/표준편차보다 큰 새 고장 값을 보았다.
예: fold0 notification CPU raw79.566, TRAIN max0.002793/std0.000332 →
scaled239702.6. fold0 order-other latency raw7.295s,
TRAIN max0.01581s/std0.000392 →scaled18589.8.
6개 모두 `(raw−TRAIN mean)/(TRAIN std+1e−8)`와 float32 값이 정확히 일치했다.
정답 이동/계산 오류가 아니라 이 분할의 root별 미학습 유형과 scaling 조건에서
나오는 값이며, 이것만으로 어느 오답의 인과 원인을 확정하지 않는다.

## 초기 완료 run에서 드러난 해석 문제

fold0 Eadro seed11/23은 각각 validation Top1 1.36%/3.70%, 선택 epoch1이었다.
선택 기준은 사전에 고정한 full-validation joint CE이며 결과를 보고 바꾸지 않았다.
seed23의 TRAIN online CE는 epoch1 1.88559→epoch200 0.20558로 감소했지만,
validation CE는 452.812→2841.521이었다. 따라서 “학습 update가 작동하지 않았다”와
“validation 기준이 아주 초기 checkpoint를 선택했다”를 구분해야 한다.
이는 두 초기 run의 관측이지 전체18회 결론이나 Eadro 일반 성능 주장이 아니다.
큰 validation 정규화 값과의 인과 연결도 아직 분리 실험으로 입증되지 않았다.
낮은 Eadro 결과를 유리한 약한 비교군으로 포장하지 않는다.

## 반복 평가 집계 보완 검사

`mon_2AMV445R46RD9RW7` / bash_18: 새 집계 fixture 1개 PASS,
focused Pyright 0 errors/0 warnings, exit0.
TRAIN의 동일 사건이 2fold×3seed로 반복되어도 먼저 사건 안에서 평균하고,
100창 사건과1창 사건을 최종적으로 동일 가중하는지 확인했다.
누락 seed/fold와 중복 평가도 거부한다.
기존 테스트·모델 학습 코드는 바꾸지 않았고 새 테스트만 실행했다.

## 기준18회와 진입 판정 — 완료

`mon_DTZMRSPCE06TJQWB` / bash_15:
`NATIVE_STAGE_PASS baseline 18 6561.444564784004`,
`BASELINE_RAW_EXIT=0`, 실제 process exit0.
각18개 checkpoint는 원 실행 안에서 TRAIN/validation logits·labels·indices·
event IDs와 joint loss를 저장값에 정확히 대조했다.
최종 집계 파일 watch `mon_PXR5H3W76CTVKBDT`도 create 후 정상 종료했다.

`mon_46T9V4N5BX08S1PN` / bash_19:
`NATIVE_ANALYSIS_PASS baseline runs 18 allow_next False`,
`BASELINE_ANALYSIS_RAW_EXIT=0`, 실제 exit0.
모든 사건/분할/seed와 source/input/artifact 해시를 대조했다.
사전 count0/>0 gap 조건을 충족하지 않아 q/zero stage를 실행하지 않았다.
조건을 바꾸거나 count 실험을 수행한 것처럼 완료 처리하지 않았다.

## 별도 저장-logit 검산 — 완료

`verify_results.py`는 torch·학습/모델 코드를 import하지 않고
별도 순위 계산으로 저장 예측을 검산한다.
`mon_V8RENCAKQY870B8A` / bash_20:

```text
INDEPENDENT_RESULTS_PASS 36 972 20
0 errors, 0 warnings, 0 informations
FINAL_VERIFY_RAW_EXIT=0
```

- TRAIN/validation 예측36파일, 장애 창 평가62,118회(반복 평가 포함).
- 사건×부분집합972개 및 전체/고장유형 요약20개가 1e-12 이내 일치.
- source/input/output153개 hash bindings 확인.
- seed별 support gap +0.0346868350 / −0.0299481466 / −0.1070920791 재현.
  5%p 기준을 넘는 seed가0개임을 별도 확인.
- count_runs.json과 zero_runs.json이 없음을 확인.
- 원18회에서 이미 유효한 checkpoint replay를 중복 실행하지 않았다.
- 전체 project Pyright 0 errors/0 warnings, 실제 exit0.

최종 검산 값과 해시는 verification.json에 보존했다.

## 보고서 대조

`FINAL_REPORT_QA_PASS 17`: 전체2행·유형3행·seed3행,
근거 링크8개, 실제 run inventory가 baseline18회/두 kind뿐임을 확인.
`SUPPORT_AND_COST_QA_PASS 10`: 관측 유무 표2행과 준비/학습/추론/RSS 비용8개 대조.
Eadro epoch1 선택5/9회도 실제 보고서에서 셌다.
학습에 사용한 프로토콜·모델·입력은 결과를 본 뒤 변경하지 않았다.
