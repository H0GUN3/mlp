# 선택 입력·paired Hawkes 준비 검증

## 판정

**PASS — 입력 준비만 완료. 학습·점수·효과 검증은 실행하지 않았다.**

`inputs/selected.npz`, `inputs/metadata.json`, `inputs/preparation.json`을
실제로 생성했다. 준비 프로세스의 실제 exit 0을 확인한 뒤 별도 finalize
프로세스가 원본/산출물 해시와 선택 입력 read-roundtrip을 다시 검사하고
PASS manifest를 발행했다. finalize도 실제 exit 0이다. 두 producer 및
Hawkes worker는 종료되었다.

이번 작업의 쓰기 소유권은 `selective_loader.py`, `test_selective_loader.py`,
`prepare_horizon.py`, `test_prepare_horizon.py`, `pyright_prep.json`,
이 문서와 `inputs/` 안의 생성물뿐이다. 다른 작업자가 생성한 runner·계약
파일은 수정하지 않았다. 설치·다운로드·commit·추가 에이전트·학습은 없다.

## 보호 경계와 구현

- 실제 seed42 split의 train316/validation78만 선택했다. 원본 오름차순
  `indices:int64`와 기존 split 순서의 `train_positions`/
  `validation_positions`를 보존했다. test169/unassigned1의 관측값을
  ndarray로 만들거나 수치 해석하지 않았다. TT/RE2 입력에 접근하지 않았다.
- **비선택 압축 바이트도 순차 압축 해제 스트림을 통과했다.** 비선택
  observation byte block은 버렸으며 “파일/바이트를 읽지 않았다”는 주장을
  하지 않는다. `log_window` 전체만 구조적 인덱스로 해석했다.
- `zipfile`과 `numpy.lib.format` NPY header로 C-order/plain numeric,
  shape/dtype/멤버 크기를 검사한다. object/Fortran/예상 외 shape는 거부한다.
  observation의 `np.frombuffer` 호출에는 선택 행 byte block만 전달한다.
- raw 네 멤버마다 394행 해석/170행 byte-skip. ragged index 40,708개에서
  선택 사건 28,566개를 골랐다. node/template/timestamp마다 12,142개 사건
  값은 해석하지 않았다. 상세 byte 수는 `metadata.json.access_audit`.
- 기존 `load_inputs`, `load_prepared`, native `run_training`은 호출하지 않았다.
  동결 `native_data.make_knots`와 `native_data.fit_hawkes`만 실제 계산에
  사용했다. 모듈 import는 함수 정의·라이브러리 import만 수행한다.
- 양쪽에 같은 half-open 사건 집합, 원본 template 순서 E7, dummy `[0]`,
  jitter `1e-5`, 원본 seed `42+original_window*12+node`를 사용했다.
  ADM4 decay3/default solver/baseline .2는 그대로이며 absolute에서
  `end_times`만 `10`에서 `original_window_start+10`으로 바뀐다.
  clipping·재정규화·solver 변경은 없다.
- 모든 nonempty relative 결과의 exact-match 및 전체 `(394,12,7)` 로그
  비교를 통과한 다음에만 입력을 발행했다. 자체 NPZ partial을 읽어 byte-exact
  roundtrip한 뒤 exclusive hard-link로 발행한다. 기존 출력/partial은
  거부하고 실패를 덮어쓰지 않는다. PASS는 준비 프로세스 종료 전에는 없다.

## 실제 명령과 종료

작업 디렉터리는 이 문서의 디렉터리다. Python 명령은 모두 기존
`/home/gnho1236/r2/.venv-eadro/bin/python -B`를 사용했다.
숫자 연산 환경은 `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`이다.
모든 긴 명령은 `tool.monitor(timeout_ms:1800000)`으로 실행했다.

| 실행 | 실제 종료 | 로그/결과 |
|---|---:|---|
| `python -B -m unittest -v test_selective_loader test_prepare_horizon` 최초 | 0 | `inputs/focused-tests-01.log`, 14 tests OK |
| `pyright --project pyright_prep.json --pythonpath /home/gnho1236/r2/.venv-eadro/bin/python` 최초 | 1 | `inputs/pyright-01.log`, 아래 오류 보존 |
| 같은 focused tests, 타입 경계 수정 후 | 0 | `inputs/focused-tests-02.log`, 14 tests OK, 1.094초 |
| 같은 CLI pyright, 수정 후 | 0 | `inputs/pyright-02.log`, 0 errors/0 warnings/0 informations |
| `python -B prepare_horizon.py --prepare` | 0 | `inputs/preparation-run.log` |
| `python -B prepare_horizon.py --finalize --producer-exit-code 0` | 0 | `inputs/finalization.log`, `PREPARATION_PASS` |

최초 CLI 오류 원문:

```text
/home/gnho1236/r2/research/sn_hawkes_horizon_contrast_20261017/test_selective_loader.py:97:54 - error: Argument of type "list[int] | list[float]" cannot be assigned to parameter "rows" of type "Iterable[int]" in function "read_rows"
1 error, 0 warnings, 0 informations
```

의도적으로 잘못된 인덱스를 주는 경계 테스트에 맞춰 reader의 외부 입력
타입을 `Iterable[Any]`로 바꾸고 내부 정수/중복/범위 검증은 유지했다.
타입 진단을 ignore/disable하지 않았다. 프로젝트 밖 환경을 쓰는 workspace
LSP의 import/NumPy 진단을 무경고라고 주장하지 않는다. 지정 Python3.8
환경과 소유 config를 쓰는 실제 CLI 결과가 위 검증 근거다.

테스트는 금지 sentinel 전후 선택, 비어 있는 선택의 무해석, 요청 행 순서,
ragged 사건 필터, labels/split 순서, object/Fortran/shape/잘린 payload/중복
멤버 거부, template/dummy/jitter/half-open 경계, 양 arm의 같은 RNG/knots/
solver 인자와 horizon-only 차이, mismatch 시 absolute fit 차단,
NaN/음수 실패, writer partial/덮어쓰기 거부를 검사했다.

경고도 보존했다:

```text
DeprecationWarning: Please use `toeplitz` from the `scipy.linalg` namespace, the `scipy.linalg.special_matrices` namespace is deprecated.
```

이는 tick import에서 나온 테스트 로그의 경고다. 실제 solver 경고 집계는
양 arm 모두 `{}`이다. 경고가 없다는 것과 수렴했다는 것은 다르다.

## 실제 비용·동등성·입력 차이

최대 2 Hawkes worker, 각 숫자 라이브러리 1 thread로 실행했다.

| 원본 window,node | 실제 사건 수 | knot 수(dummy 포함) | paired 초 |
|---|---:|---:|---:|
| 68,1 | 1 | 7 | 0.061559 |
| 2,1 | 18 | 24 | 0.052320 |
| 132,0 | 35 | 40 | 0.010639 |
| 151,0 | 52 | 57 | 0.057406 |
| 154,0 | 75 | 80 | 0.058026 |

5개 실제 probe 모두 relative exact-match. 결과는 각각
`inputs/probe_WINDOW_NODE.npz/.json`에 보존하고 full 준비에 재사용했다.
probe 합계 0.239951초. 보수적 full 추정은
`max(paired 초)*1415*1.5/2 = 65.329829초`이며 당시 경과 1.819430초를
더해도 1500초 예산 이내였다. 준비 본체 기록은 27.858544초
(`preparation_seconds`, 후속 read-roundtrip/finalize 제외)다.

- nonempty 1,415개 모두 상대 baseline과 exact equality.
- 전체 4,728 window-node 중 empty 3,313개는 양쪽 모두 정확히 0.
- relative/absolute 모두 `(394,12,7)` float64, finite, 비음수.
- relative solver iteration counts: `{11:697,21:310,31:13,41:8,50:387}`.
- absolute solver iteration counts: `{11:738,21:203,31:3,41:1,50:470}`.
- **상한 도달 relative387/absolute470회. 수렴을 주장하지 않는다.**
- `metrics`, `traces`, `logs`(기존 relative), `labels`, `indices`는 원본 선택
  결과와 dtype/bytes exact. services/edges/template order와 선택 window/
  split order도 보존했다. 준비 직후와 실제 exit 이후 read-roundtrip 통과.

| 로그 요약 | relative | absolute |
|---|---:|---:|
| nonzero 셀 | 9,789 | 8,557 |
| min | 0 | 0 |
| max | 2.4454429171311354 | 6.059801117024349e-10 |
| mean | 0.07271589281038983 | 1.424314364976545e-10 |
| std | 0.26431247955880505 | 2.5695086821173186e-10 |

변경 셀 9,789개, 변경 그룹 1,415개, 변경 window394개.
delta 범위 `[-2.4454429171311354, 2.9759868959553906e-161]`.
전체 분포/quantile와 원본 창별·노드별 nonzero/차이는
`preparation.json.input_difference`에 있다. absolute의 매우 작은 값과 0도
실제 solver 출력이며 clipping하지 않았다. 이는 horizon-only 공개 포크
대조의 입력 변화이지, 정확도 향상·원인·저자 구현 재현의 증거가 아니다.

## 실제 버전과 해시

Python3.8.20 / NumPy1.21.5 / pandas1.4.2 / tick0.7.0.1 /
Drain3 0.9.11 / SciPy1.10.1 / CLI pyright1.1.408.

메타데이터 필드와 실제 파일 hash를 연결했다. `native_data_source_sha256`는
역사적 extraction 시점 값 `3ef8683a7c2941b21224cb37a7232da446abb76efe8643eb9b39c1cac7aad1b2`이고,
현재 코드와 일치하는 raw metadata의 `feature_build_source_sha256`는
`05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986`이다.
둘을 같은 필드로 취급하거나 문서의 prose를 hash 근거로 복사하지 않았다.

주요 입력 SHA256(준비 전/후 및 finalize 재검사에서 동일):

| 원본 | SHA256 |
|---|---|
| SN/raw.npz | `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8` |
| SN_prepared.npz | `34b26cfab2f76971c2517a0a8a3d970327a48347f6bb4845684f9408b08c765f` |
| SN/metadata.json | `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4` |
| SN_metadata.json | `64802ec617d5c3ad3697902a1a3652032edc7fef9ce5744496a57c21486ea26d` |
| seed11/split.json | `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d` |

동결 source·계약·metadata 등 14개 파일의 정확한 경로와 전후 hash는
`preparation.json.input_source_hashes_before/after`에 모두 있다.
기존 결과/원본은 덮어쓰지 않았고 baseline200 재학습도 하지 않았다.

| 코드/config | SHA256 |
|---|---|
| selective_loader.py | `a138edf213eb917c9272c5d25b304a0a73b6d16aadbff0c28cf74cad5cff883e` |
| prepare_horizon.py | `0cec3387d8402761cf275e86795c5fa93948a39e86173ff9a531fe99ea09174e` |
| test_selective_loader.py | `d2d480a7436a5711a78efcd16ee0998b8b999a4217d7eb818aa6743f0b231be9` |
| test_prepare_horizon.py | `239abf02e5f481fb9ab4d782eb07aee49fffbf110a665ae411e0dd15dd110939` |
| pyright_prep.json | `67778824874bf63ba33d9334230771c43f2dda9033a84da5690af38b6b02e24e` |

| 생성물/로그 | SHA256 |
|---|---|
| inputs/selected.npz | `6439a210ae51f08df3da6f2d1fd3521cac344914fb9de174411ab0e708106fcc` |
| inputs/metadata.json | `b69b9fa5880d45c73934b30294268b8c540455e0cb427f3ff726b12f60093250` |
| inputs/preparation.json | `e7b6fde7e2591cbfb2f49315162b254e3e1d06a714d0f3a5bfec8b58fb4da711` |
| inputs/relative_rebuilt.npz | `fe046e7198da9f0bd97079ce892b957278ccc7584f93a2a7f5b416186aa710f2` |
| inputs/preparation-run.log | `f52bce8745c2b52c24a4595c20b17c4ed9a5902df917d1e01a1eb6f7851e11b6` |
| inputs/finalization.log | `777d64c2fdca37e1da967e1a8390206bb4dfeba1080f9e34b3e8a45321928161` |
| inputs/focused-tests-01.log | `8c4bac050a966da707d172d8984caa3f5d7161cead5af41bbe1d819be39d44ee` |
| inputs/focused-tests-02.log | `38e803302fc3cc5f4a82e8b2148aea1ac885356df51950ada802362a880f801d` |
| inputs/pyright-01.log(실패 보존) | `99d1b86c7aa978b41599ffb25a343a5ebc8c6fdf2dc7dc043565ec3104ffff53` |
| inputs/pyright-02.log | `6d88a1b220adb7a3d62092b6e38431f0b3fe8babe9864fab90e5849766260332` |

## 끝낸 범위

요청한 preparation 계약까지만 완료했다. 학습/성능 비교/보호 관측 검사는
하지 않았다. 반복 상한과 absolute 값의 극소화는 후속 해석 시 반드시
유지해야 할 주의점이다. 성공 산출물, 실패 로그, probe 결과는 덮어쓰지 않는다.
