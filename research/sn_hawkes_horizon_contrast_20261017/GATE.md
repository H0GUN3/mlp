# 보존·실행 가능성 게이트

**결정: READY — 제한된 단일 horizon 대조 구현 phase를 시작할 수 있다.**

이 판정은 phase 2의 안전한 입력 선택/재생성, focused test, 제한된 비용
probe 및 relative-arm 동등성 검사를 시작할 허가다. **실제 fit, 전체 학습,
점수 산출 또는 연구 완료를 뜻하지 않는다.** phase 2의 선행검사가 통과하지
못하면 전체 contrast로 진행하지 않는다. 대조는 공개 Eadro 수리 fork의
Hawkes horizon 동작을 비교할 뿐, DiagMLP 저자 구현 재현이나 신규 방법
증명으로 해석하지 않는다.

## 이진 게이트 및 추적성

| 기준 | 결과 | 근거와 경계 |
|---|---|---|
| 보존/허용 범위가 기록됨 | READY | `BRIEF.md` §§고정 경계, phase 1; `REGISTRY.md` 목적; 이번 검토는 text/JSON metadata와 공개 Python 원문만 확인. raw/prepared NPZ, event arrays, checkpoint를 열지 않았고 SN test 169+unassigned 1 및 TT/RE2 관측을 접근하지 않음. |
| 필수 보고서 존재 | READY | 실험 디렉터리의 `REGISTRY.md`, `CONTRAST.md`, `ACCESS.md`를 읽음. 새 `SOURCE_EVIDENCE.md`와 고정 원문 대조 결과도 확인함. |
| 단일 horizon 차이가 구체적임 | READY | `CONTRAST.md` 표 및 `SOURCE_EVIDENCE.md`: 동일 상대 knot에 local `end_times=10` 대 공개 규칙 `end_time=e+1`. `align.py::get_basic`은 `(s,s+chunk_lenth-1)`을 구성하므로 chunk length 10에서 `e+1=s+10`. 실제 차이는 **`10` 대 `window_start+10`**임. |
| event selection이 양 arm에서 동일함 | READY | 양 arm 모두 기존 394개 local stride-10 window와 `[s,s+10)` half-open event selection을 고정한다. 공개 원본의 `deal_logs`는 `timestamp>=s` 및 `timestamp<=e`, stride-1 경로이므로 이를 contrast에 끌어오지 않는다. 전체 원본 pipeline 재현이라 주장하지 않는다. |
| 나머지 전처리/solver 통제가 명시됨 | READY | `CONTRAST.md`; pinned `single_process.py::deal_logs/logHaw`: relative knots, template별 정렬/jitter, HawkesADM4 decay 3, baseline start 0.2 및 baseline 반환. local `native_data.py::make_knots/fit_hawkes`: dummy `[0]`, jitter/seed 규칙 및 local solver 조건. phase 2에서 실제 구현과 양 arm 동등성을 확인해야 하며 공개 코드와 완전 동일하다고 가정하지 않음. |
| 기준 arm 재사용 근거 존재 | READY | `REGISTRY.md`의 기존 SN200 seed 11/23/37 결과, 공통 split/scaler/config/history 및 summary metadata. 기록된 verifier는 `/home/gnho1236/r2/research/native_reproduction_20261013/sn200_verification.json`; `common_manifest.input_hashes.raw.npz`, `common_manifest.input_hashes.metadata.json`, `common_manifest.split_hash`, `common_manifest.scaler_hash`. 해시는 기록값을 인용했으며 이 gate에서 파일을 재해시하거나 checkpoint를 읽지 않음. |
| 선택 입력 경로와 보호조건 구체화 | READY (필수 phase 2 check) | `ACCESS.md`: 허용 train+validation 394개 원본 window만 선택하고 원래 window ID/order 보존. `native_data.py::load_prepared`, `native_train.py::load_inputs`, `features.py::load_selected`는 전체 멤버 materialize 가능성이 있어 직접 호출 금지. 새 selective reader와 fixture 경계 test가 phase 2 필수. 압축 stream 통과와 값 decode/materialize를 구분해 정확히 기록. |
| 입력 생성의 실행 가능성 확정 | phase 2 선행조건 | 아직 실행하지 않음: selective-reader fixture test, metadata/hash preflight, 원본 인덱스의 결정성, 허용 행 이외 값 비노출 확인. 해시 식별 필드: 기존 metadata에 명시된 `raw_npz_sha256`, `prepared_npz_sha256`, `native_data_source_sha256`, `feature_build_source_sha256`; 각각 해당 metadata 문맥에서 취급하고 실제 hash preflight 결과를 새 manifest에 기록. |
| relative-arm equivalence와 비용 | phase 2 선행조건 | 아직 fit/probe하지 않음. 허용된 각 원본 `(window,node)`에서 local horizon arm의 기존 `logs` 값과 exact-match 재생성 여부를 먼저 검증하고, 비용 probe와 보수적 총량 추정을 기록. 실패/예산초과면 보존 후 중지; 이 gate가 성공을 선취하지 않음. |
| templates/config/학습 선택 규약 고정 | READY (필수 phase 2 check) | fitted Drain template/order와 정상-reference normalization 통계, knots/jitter, 원본 인덱스 seed `42 + original_window*12 + node`, decay 3/default solver 50/initial baseline 0.2, 빈 그룹 0, 10초 half-open 선택 고정. seed 11/23/37, 동일 모델 초기화·shuffle·학습/optimizer·200 epochs·batch 256·loss·동일 validation 78/order 및 earliest strict-minimum validation joint loss 선택을 유지. horizon 외 차이는 허용하지 않음. |
| 출처 의미 직접 확인 | READY | 고정 raw URL 두 파일을 text로 확인: `https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py`의 `deal_logs`, `logHaw`; 같은 commit의 `codes/preprocess/align.py::get_basic`. 이는 공개 포크의 source provenance이며 저자 구현 근거가 아님. |
| 효과/원인/확대 주장 제한 | READY | 비방향 가설이며 호/불리/미확인 모두 가능. 결과는 고정된 contrast 내 연관 차이로 보고; 인과·우월성 주장 금지. TT/RE2 자동 확장 금지. |

## 정확한 실행 제약

1. 새 산출물은 이 실험 디렉터리 안에만 둔다. 원본·동결 코드·기존 결과는
   읽기 전용으로 보존하고 덮어쓰지 않는다. 생성/수정은 사용자 지정 방식대로
   `apply_patch`만 사용한다. 설치, 추가 다운로드, git 변경/commit 금지.
2. phase 2에서도 보호 배열이 든 NPZ 전체를 행 선택 전에 ndarray로 만들지
   않는다. test 169/unassigned 1의 관측값 및 TT/RE2 관측, checkpoint
   역직렬화 금지. 선택 외 행을 압축 해제 byte stream으로 지나갔다면
   “읽지 않았다”고 하지 말고 stream 처리와 값 해석 여부를 구분한다.
3. 양 arm은 같은 394 local windows, half-open event selection, labels,
   template identity/order, knots/jitter, solver, seeds, 모델/학습/선택,
   scoring을 유지한다. 바뀌는 유일 변수는 horizon `10` 대
   `original_window_start+10`. clipping, 재정규화, solver 변경/비용상한
   상향, feature 추가 금지.
4. phase 2는 안전한 선택 입력 준비와 fixture/focused test를 먼저 완료하고,
   그다음 최대 3개 seed(11/23/37) fit으로 진행한다. 전체 fit 전 비용 probe
   와 relative 재생성 equivalence가 통과해야 한다. 기존 SN200 relative
   결과는 적합성 검증을 통과한 경우에만 재사용하며 중복 fit하지 않는다.
   실패 원인과 artifact를 보존하고 이유 없이 재시도/조건 변경하지 않는다.
5. 모든 중요한 입력·source·artifact hash는 실제 metadata 필드명과 정확한
   경로를 manifest에 연결한다. 설정, 코드 diff, split/order, template,
   초기화·shuffle·solver·selection policy, runtime이 horizon 외에 다르면
   single-variable contrast의 fairness가 성립하지 않으므로 phase를 멈춘다.

## 허용되는 다음 topology

**Phase 2 (새 phase/run, 아직 시작 안 함):**

`safe input preparation + focused tests` → (통과 후) `3-seed fit` →
`verification (exit status, frozen config/diff, outputs, probe/equivalence,
artifact preservation)`.

입력 준비/test가 fit보다 먼저여야 한다. fit은 최대 3개 모델 동시, CPU
thread 제한과 brief의 Hawkes worker/thread 상한을 지킨다. verifier와 기존
source evidence가 확인되지 않은 동작은 결과처럼 쓰지 않는다.

**Phase 3 (별도 후속 phase, 아직 시작 안 함):**

새 run 결과를 대상으로 독립 scoring → 동일 validation 표본의 paired
오류분석(창/사건/seed 구분; conditional window Top-1 주, Top-3/gated 및
detection 보조) → 한국어 결과 보고. 점수와 입력 변화는 분리해 제시하고
호/불리/효과 미확인 어느 결과도 허용한다. phase 3도 TT/RE2 확대나 새
데이터·모듈 추가를 자동 승인하지 않는다.

## 게이트 경계

이번 결정은 보존/feasibility 문서 phase의 종료와 **phase 2를 새로 정의할
수 있음**만 승인한다. 어떤 array decode, feature generation, solver probe,
fit, score, 독립 분석도 이 phase에서 수행하지 않았다. 후속 실행에서 위
선행조건 중 하나라도 실패하거나 material한 공통성 불확실성이 발견되면
부모에게 `NOTREADY` 사유와 증거를 보고하고 중지한다.
