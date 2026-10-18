# 입력 보존·선택 재사용 검토

## 판정

**가능하지만 기존 `np.load` 경로를 재사용하면 안 된다.** 안전한 경로는
기존 seed-42 split에서 허용된 394개 원본 창(train 316 + validation 78)만
먼저 정하고, NPZ의 각 `.npy` 멤버를 순차적으로 압축 해제하면서 선택 행만
배열 값으로 해석·보관하는 새 reader다. 선택되지 않은 행은 압축 스트림을
통과시키되 해당 값의 ndarray 구성·수치 검증·특징화는 하지 않는다. 따라서
“test 값을 읽지 않았다”는 표현은 쓰지 말고, “압축 바이트/스트림을 순차
처리했지만 선택 외 행의 압축 해제 결과는 해석·보관하지 않았다”고 기록한다.

이 단계에서는 NPZ, raw feature, event 값 또는 checkpoint를 열지 않았다.
아래 판정은 소스와 JSON metadata에 한정된다.

## 허용 행 선택

- 대상은 SN 564개 원본 창이다. `native_train.py::make_split` 및
  `method_mlp_20261013/features.py::original_split`은 `RandomState(42)` 순열,
  `trainval=floor(.7*564)=394`, `validation=floor(.2*394)=78`을 사용한다.
  원래 위치를 유지한 train 316개와 validation 78개만 허용한다.
- 구현은 train/validation 원본 인덱스의 합집합으로 원본 564행을 선택한다.
  선택 후 배열 순서를 바꾸거나 행 번호를 새로 부여하지 않는다. 선택된
  행의 순서를 학습용으로 바꾸더라도 모든 solver seed는 반드시 원본
  `window` 위치로 `42 + original_window * 12 + node`를 계산한다.
- split 증거: `research/native_reproduction_20261013/calibration200/SN/eadro/seed_11/split.json`,
  seed 42, counts 316/78/169/1, SHA-256
  `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d`.
  허용 위치 합의 기록된 SHA-256은
  `b92f51b324927e9b968cd038d5152d6cf57f3f99ebba7b4d4a6cbeb8d6af147a`.
  test 169개와 unassigned 1개는 metadata의 개수만 경계 확인에 쓴다.
  해당 행의 값은 허용 입력도, 검증 대상도 아니다.

## 정확한 소스 배열과 재사용 조건

| 용도 | 정확한 기존 경로 / 배열 | metadata 근거와 취급 |
|---|---|---|
| 기존 모델 입력 | `research/native_reproduction_20261013/native_inputs/SN/raw.npz`: `metrics`, `traces`, `logs`, `labels` | `research/native_reproduction_20261013/native_inputs/SN/metadata.json`; 564개 창, 12개 서비스, 10초, event_count 7. `metrics`는 `(W,12,10,7)`, `traces` `(W,12,10,2)`, `logs` `(W,12,7)`, `labels` `(W,)`로 `native_data.py::validate_arrays`/`native_train.py::validate_inputs`가 규정. 선택된 394 원본행만 재사용한다. |
| 사건 시각·template 매핑 | `research/native_reproduction_20261013/native_inputs/SN_prepared.npz` (정확한 실제 파일명은 `native_data.py::prepare`가 `SN_prepared.npz`로 저장): `log_window`, `log_node`, `log_template`, `log_timestamp`, `window_start` | `research/native_reproduction_20261013/native_inputs/SN_metadata.json`의 `prepared_npz_sha256`. `log_window`/`log_node`는 허용 원본창의 사건 행을 고르는 정수 매핑으로만 처리한다. timestamp/template 값은 허용 창의 행에서만 해석한다. `labels`, event provenance 등 필요하지 않은 배열은 읽지 않는다. |
| 기존 파생 cache (대체 불가) | `research/method_mlp_20261013/features/SN.npz`: `x`, `mask`, `coverage`, `labels`, `indices`, `event_ids`, `partition` | train/validation 394행만 든 파생 MLP 입력이며 18개 engineered feature다. metric/trace raw tensor나 Hawkes event knots가 아니고 logs도 읽지 않아 이번 contrast 입력으로 대체할 수 없다. |

NPZ의 일반 `np.load(...)[key][indices]`는 선택 전에 해당 멤버 전체를
ndarray로 만든다. 따라서 다음 기존 함수는 금지한다.

- `native_data.py::load_prepared`: 모든 prepared 멤버를 `source[key]`로 읽음.
- `native_train.py::load_inputs`: `metrics`, `traces`, `logs`, `labels` 전체를
  읽고 나서 split을 적용함.
- `method_mlp_20261013/features.py::load_selected`: split 인덱스는 먼저
  계산하지만 NPZ 멤버 `metrics`, `traces`, `labels` 전체를 ndarray로 만든
  다음 행 선택함(함수 주석도 “NPZ members decode whole arrays”라고 명시).

`tt_re2_baselines_20261017/tt_runner.py::load_selected` 역시 이 문제를
해결하는 SN reader가 아니다. 그 reader는 별도로 큐레이션된 TT cache를
사용하며 이 작업에서는 TT/RE2 입력에 접근하지 않는다.

## 정확성·불변 조건

- `native_data.py::make_knots`가 하는 기존 relative knot 계산(창 시작 차감,
  template별 정렬, 동시 사건당 `1e-5` jitter, 빈 template `[0]`)을 바꾸지
  않는다. 원본 template 순서와 7개 차원, labels, metric/trace 행 값과 원본
  창 대응을 유지한다.
- relative-arm 결과를 기존 `raw.npz["logs"]`와 비교하기 전, 허용된 각
  `(original_window,node)`에서 원래 seed `42 + original_window*12 + node`,
  decay 3, `end_times=10`, `baseline_start=.2`, 기본 solver 설정으로
  baseline을 재생성하고 정확히 일치하는지 확인한다. seed를 선택 배열의
  새 행 번호로 다시 매기지 않는다. 이 검사는 checkpoint 역직렬화나
  학습이 아니라 허용 입력의 재계산 대조다.
- 반대 arm은 같은 knots에 horizon만 source convention `end_time=e+1`
  (상대 knot + 절대 종료시각)로 바꾼다. 이는 공개 포크의 horizon-only
  대조이며 저자 DiagMLP 구현 복원이나 새 방법 증명이 아니다.
- `raw.npz`의 기존 `logs`는 기존 상대 horizon의 feature cache라 재사용
  가능성이 있지만, 그 값도 선택 reader를 통해 허용 행만 보관하고 위의
  seed별 exact-match 검증을 통과해야 한다. mismatch면 기존 cache를 신뢰하지
  말고 원인을 보고한다.

## 소스·hash 연결

- 기준 공개 소스: FeiGSSS/Eadro
  `7d69281a80adce60067aa858729746fc6a362f53`; metadata의 source functions는
  `single_process.logHaw`, `single_process.deal_traces`,
  `align.get_basic` 등이다.
- 실제 extractor: `research/native_reproduction_20261013/native_data.py`;
  recorded `native_data_source_sha256`는
  `3ef8683a7c2941b21224cb37a7232da446abb76efe8643eb9b39c1cac7aad1b2`.
  `features/SN.json`의 later verified source field
  `feature_build_source_sha256`는 `05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986`.
  이 두 필드는 서로 다른 metadata 산출 문맥이므로 실행 전 실제 파일과
  그 산출물을 각각 대조해야 한다.
- Raw bundle: `features/SN.json`에 기록된
  `raw_npz_sha256=1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8`,
  `metadata` SHA-256
  `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4`.
- Prepared bundle: `SN_metadata.json`의 `prepared_npz_sha256`는
  `34b26cfab2f76971c2517a0a8a3d970327a48347f6bb4845684f9408b08c765f`.
  실행 전 metadata 파일 자체의 hash도 기록하고 embedded hash와 실제 NPZ
  전체 hash를 일치시킨다. 해시 계산은 값 해석이 아니라 파일 무결성 확인이며,
  raw 값 접근으로 오인하지 않도록 입력/출력 기록에 분리한다.

## Import·기존 reader 주의

`native_data.py`는 모듈 import 시 라이브러리와 함수 정의를 불러오며 실제
prepare/build는 `if __name__ == "__main__"` 아래에서만 실행한다. 단, `tick`,
Drain3, NumPy/Pandas의 import 자체는 일어난다. `features.py` import는
`sys.path`를 수정하고 `native_data_profile`을 import하지만 feature 데이터는
`load_selected` 호출 시 읽는다. 선택 경계가 명시되지 않은 `load_prepared`,
`load_inputs`, `load_selected`를 다음 단계에서 호출하지 않는다. 독립적인
새 reader에서 import 부작용과 archive member 처리를 눈에 보이게 제한한다.

## 다음 단계만을 위한 범위 제안

다음 phase의 소유 파일(이 디렉터리 안에 새로 생성; 이번 단계에서는 만들지
않음):

1. `research/sn_hawkes_horizon_contrast_20261017/selective_loader.py` —
   metadata/hash preflight, 허용 394행 선택, stream/skip reader, 원본
   window id 보존.
2. `research/sn_hawkes_horizon_contrast_20261017/test_selective_loader.py` —
   합성 NPZ에서 허용·금지 행을 구분하고, 금지 행 sentinel이 값 해석·출력에
   나타나지 않는 fixture 경계 테스트.
3. 새로 생성될 `selected_inputs.npz`, `relative_rebuilt.npz`,
   `selection_manifest.json` — 모두 이 실험 디렉터리에만 저장; 기존 cache는
   변경 금지. manifest에는 정확한 input/source/hash, 394 원본 인덱스,
   skipped/decompressed-byte 처리 의미, solver seed의 원본 window 기준을 기록.

허용 입력 파일 allowlist는 다음으로 한정한다: 위 raw NPZ와
`SN/metadata.json`, `SN_build.json`; `SN_prepared.npz`와
`SN_metadata.json`; seed42 split metadata; `native_data.py`,
`native_data_profile.py`, `native_train.py`, `method_mlp_20261013/features.py`;
실험 Brief와 공개 포크 source 설명. metadata와 `.npy` header는 shape/dtype/
index/hash 확인에만 쓴다. archive 내 observation 멤버의 허용 외 행은 값으로
해석하지 않는다. TT/RE2, `test`/`unassigned` 관측, checkpoint는 allowlist 밖.

진행 전 필요한 증거: fixture test가 허용 원본행의 값·순서·labels 및 knot
생성이 기존 정의와 일치하고 금지행 sentinel을 노출하지 않음; metadata/hash
검증 통과; 허용 train+validation의 seed별 relative baseline이 기존 `logs`
와 exact match; 새 cache·manifest만 생성되고 기존 파일 hash가 전후 동일함.
불일치나 stream reader가 선택 외 값을 해석하게 되는 경우 이 cache 경로는
중단하고, 이미 허용 train+validation만 포함한다고 독립 검증된 기존 cache가
있는지 확인한다. 현재 확인한 `features/SN.npz`는 raw 입력도 logs도 아니라
그 대안에 해당하지 않는다.

## 범위·미확인

지정된 `research/sn_corrected_20261017/prepare.py`와 작업 프롬프트의
`research/native_inputs/...` 경로는 존재하지 않았다. 실제 준비 코드는
`research/native_reproduction_20261013/native_data.py`이며 실제 metadata/
cache 경로는 위 표에 적었다. 이번 검토는 압축 archive header/codec, 실제
배열의 저장 순서·dtype·압축 member 이름을 확인하지 않았다. 다음 phase는
metadata/header 단계에서 이를 확인하되, 불허 행의 observation 값을
materialize하면 안 된다. 본 결론은 실제 array selection이나 model fitting을
수행했다는 뜻이 아니다.
