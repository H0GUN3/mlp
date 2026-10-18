# SN 입력 준비 검증

2026-10-17. **입력 준비 PASS**. Python **3.8.20**, NumPy **1.21.5**,
기존 `.venv-eadro`만 사용했다. 학습·스케일러 적합·다운로드·설치·commit·자식 작업 없음.
작성 파일은 `input_bundle.py`, `test_input_bundle.py`, `inputs.npz`,
`input_manifest.json`, 이 문서뿐이다. 기존 계획·자료·코드·분할·결과는 수정하지 않았다.

## 부모 실행기 인터페이스

```python
from input_bundle import load_inputs, split_indices

arrays, manifest = load_inputs()
parts = split_indices(arrays, rotation=0)
train_metrics = arrays["metrics"][parts["train"]]
```

`load_inputs()`는 소스 SHA-256, manifest 정규 JSON payload SHA-256,
생성 NPZ SHA-256을 검증한 뒤 `(arrays, manifest)`를 반환한다.
입력 준비 소스나 테스트를 수정하면 이전 manifest와의 해시 불일치로 중단한다.
`prepare`는 기존 생성물을 덮어쓰지 않으며, 출력은 exclusive 생성한다.

NPZ의 키는 **아래 8개만** 존재한다. 모든 행은 허용된 기존 SN bundle 순서다.

| 키 | shape | dtype / 의미 |
|---|---|---|
| metrics | `[394,12,10,7]` | float64, 비정규화 원형 metric |
| traces | `[394,12,10,2]` | float64, 채널0은 서비스/초당 평균 duration(초), 채널1은 0 |
| logs | `[394,12,7]` | float64, 원형 per-window Hawkes baseline |
| labels | `[394]` | int64, 정상 -1 / 원인 서비스 0..11 |
| indices | `[394]` | int64, 원본 564행 캐시에서의 original index |
| fold_ids | `[394]` | int64, G0/G1/G2 |
| episode_ids | `[394]` | Unicode, 정상 창도 소속 장애 episode를 가짐 |
| event_ids | `[394]` | Unicode, 정상은 빈 문자열 |

`split_indices()`는 **394행 배열의 행 위치**를 반환한다. 원본 `indices`가 아니다.
반환 키는 `train`, `validation`, `evaluation`이다.

| rotation | train | validation | evaluation |
|---|---|---|---|
| 0 | G2:140 | G1:122 | G0:132 |
| 1 | G0:132 | G2:140 | G1:122 |
| 2 | G1:122 | G0:132 | G2:140 |

정상 창을 포함한 episode와 비정상 event의 fold 교차를 거부한다.
각 fold는 장애 사건12개, root12개, 종류별4개다. 전체 장애325 / 정상69,
episode36개이며 기존 배정·순서를 바꾸지 않았다.

manifest는 최상위 `services`(원형 순서12), `edges`(정적24쌍),
`event_count`(로그 채널 E=7), `windows`(순서대로394개), `faults`(사건36개),
`source_hashes`, `input_npz_sha256`, `protection`, `loader_audit`를 노출한다.
`faults[event_id]`는 `service`, `root`, `fault_type`, `run_id`, 주입 시작/끝을 포함한다.
`windows`에는 원래 `run_id/start/end/event_id/root_fault_group`과
`original_index/label/episode_id/fold_id`가 있다. 정상 window의 JSON event_id는 null이다.
사건·정답·고장 종류·주입 설정은 분할/채점용이며 모델 입력으로 넣지 않는다.

## 보호 경계와 실제 값 대조

- 허용 SN NPZ/JSON의 해시를 먼저 확인한 뒤 그 394개 original index만 사용한다.
  기존 selected-index 해시의 canonical JSON 직렬화도 대조했다.
- 혼재 `native_inputs/SN/raw.npz`를 `np.load`하지 않았다. `ZipExtFile`에서
  NPY 1.0/2.0 header를 읽어 알려진 shape, C order, 정확한 numeric dtype,
  nonobject/비구조화 조건을 확인한다.
- 원본 순서로 스트리밍하며 제외된 **시험169 + 미배정1행**의 payload를
  바이트 블록으로 버린다. 해당 행의 ndarray 생성·수치 검사·reduction·값 기록은 없다.
  허용행만 `np.frombuffer`로 디코딩하고 원래 허용 bundle 순서로 복원한다.
- 압축 소스 전체의 SHA-256 계산과 ZIP decompression/CRC의 바이트 순회는
  보호 관측 해석과 다르다. 압축 해시는 허용되지만 보호행 값은 해석하지 않았다.
- 멤버별 실제 감사는 모두 **decoded394 / opaque-skipped170**이다.

| 멤버 | 디코딩 payload bytes | 불투명 건너뜀 payload bytes |
|---|---:|---:|
| metrics | 2,647,680 | 1,142,400 |
| traces | 756,480 | 326,400 |
| logs | 264,768 | 114,240 |
| labels | 3,152 | 1,360 |

선택 labels, 7개 metrics, trace 평균 채널을 허용 bundle의 원시 `values`와
**정확히 일치**시켰다. 18개 요약 특징이나 span count를 대체 입력으로 쓰지 않았다.
trace 둘째 채널은 전부0이다. 실제 logs는 유한·비음수이며, 채널별 nonzero 수는
`[1415,1414,1380,1414,1415,1337,1414]`다. 가짜0로그는 사용하지 않았다.

## 재사용 출처와 재검사 범위

`input_manifest.json/source_hashes`의 15개 소스는 생성 전후 및 재로딩 시 검증한다.
native raw/metadata/build, 허용 SN bundle, 기존 native 검증 보고서,
관측 audit, 관련 생성/identity 검사 코드 및 PLAN에 해시가 연결된다.
상세 해시와 원자료 해시 기록은 manifest에 보존한다.

- native metadata와 build 계약은 **UNNORMALIZED**다. 서비스 순서12,
  정적 간선24, metric 순서7, 로그 E7을 고정 값과 대조했다.
- Drain 템플릿은 별도 `no fault/SN.*` 정상 recording **3개·53,522줄**로만
  학습했다는 기존 metadata와 build 보고서를 대조했다. 이 세 recording은 모든
  rotation에 공통 제공되는 외부 정상 참고자료다. 이번에 다시 학습하지 않았다.
- tick **0.7.0.1**의 원형 `HawkesADM4(decay=3)`를 창별로 적용한 캐시다.
  horizon10, baseline_start0.2, C1000, lasso_nuclear_ratio0.5,
  max_iter50, tol1e-5, rho0.1, em_max_iter30, em_tol=None, approx0,
  solver thread1, seed `42+original_window_index*12+node`, memoization 없음.
  half-open 로그 창, 상대 시간, absent-bin `[0]`, bin별 1e-5 jitter를 유지한다.
- 허용 window의 run/시각/라벨/원인/종류를 source metadata 및 fault map과 대조했다.
  정상 창의 기존 nearest-episode 귀속도 재계산해 확인했다.
  허용 시각 구간은 겹치지 않는다. 기존 주입경계 장애37창을 삭제하지 않았으며
  해당 boundary audit를 manifest에 보존한다.
- 기존 audit의 selected identity 충돌0과 start/duration signature 검사,
  bundle 해시 일치·episode 분리·선택창 비중첩 근거를 재사용했다.
  원시 metric/span/log 스트림이나 정상 로그 archive를 다시 스캔하지 않았다.

## 실행 증거

아래 명령은 `/home/gnho1236/r2`에서 실행했다. 긴 실행은 monitor로 감시했다.

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv-eadro/bin/python -B research/sn_corrected_20261017/test_input_bundle.py

pyright --project research/sn_corrected_20261017/pyrightconfig.json

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv-eadro/bin/python -B research/sn_corrected_20261017/input_bundle.py prepare
```

- 단위 테스트 **15개 PASS, exit0**. unsafe dtype/shape/order, 잘못되거나 중복된 index,
  허용 순서 복원, 보호 sentinel의 decoder 미진입, truncated/trailing payload,
  ZIP 멤버, labels scalar행, 세 순환 및 정상 episode 격리, 해시/덮어쓰기 거부 포함.
- 실제 준비 **exit0**:
  `PASS INPUT_PREPARATION rows=394 fault=325 normal=69 episodes=36 folds=132/122/140`
  및 `PASS PROTECTION decoded=394 opaque_skipped=170 per_member; protected_decoded=0`.
- 준비 과정에서 생성 NPZ를 `load_inputs()`로 다시 읽어 모든 배열의 정확한 일치를 확인했다.
- 두 소스의 LSP 진단0건. 전체 프로젝트 Pyright **0 errors, 0 warnings,
  0 informations, exit0**. 초기 standalone 테스트 import 경로 LSP 오류는
  실제 파일을 importlib로 로딩하도록 고쳐 해결했으며 진단을 억제하지 않았다.

생성 NPZ SHA-256:
`ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e`

manifest canonical payload SHA-256:
`290dd02afad9249af5acc25d325cf6ff83ab33012cab707089c0e36cd26a49d6`

manifest 파일 자체 SHA-256:
`50169ccbf81bcb1485f0a837fe164cd95628cf3c6161ec7c43f8b78c887ee2d0`

### Monitor 원문과 종료 증거

producer `prepare`는 **실제로 한 번만** 실행했다. 이 handoff는 아래 실제
테스트/준비 exit0 알림을 받은 뒤 작성했다. DAG receipt는 producer를 재실행하지 말고
기존 파일 및 `load_inputs()`를 검증한다. 독립 재로딩 명령은 `prepare`가 아닌
`input_bundle.py verify`였으며 새 출력을 만들지 않았다.

| 실행 | monitor ID | 세션 | exit |
|---|---|---|---:|
| 최종 15개 테스트 && 실제 prepare | `mon_ZNVN0Z2146XWKXQ6` | `bash_9` | 0 |
| 전체 프로젝트 Pyright | `mon_SAGPQS203V4ZXAEQ` | `bash_8` | 0 |
| 생성 번들 verify && 독립 sha256sum | `mon_4NGAWX1A6A7ZWK2D` | `bash_10` | 0 |

최종 테스트와 실제 준비 monitor의 원문:

```text
Ran 15 tests in 0.019s
OK
PASS INPUT_PREPARATION rows=394 fault=325 normal=69 episodes=36 folds=132/122/140
PASS PROTECTION decoded=394 opaque_skipped=170 per_member; protected_decoded=0
PASS INPUT_NPZ_SHA256 ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e
watcher completed (exit code 0)
```

전체 프로젝트 진단 monitor의 원문:

```text
0 errors, 0 warnings, 0 informations
watcher completed (exit code 0)
```

독립 재로딩/해시 monitor의 관련 원문:

```text
PASS INPUT_VERIFY rows=394 sha256=ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e
ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e  research/sn_corrected_20261017/inputs.npz
50169ccbf81bcb1485f0a837fe164cd95628cf3c6161ec7c43f8b78c887ee2d0  research/sn_corrected_20261017/input_manifest.json
5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470  research/sn_corrected_20261017/PLAN.md
4327924c4c6c3ffe030d72bffa62f8f6332916bd71939cadd0a1a7eb6fa432a5  research/sn_corrected_20261017/PLAN_CHECKS.json
watcher completed (exit code 0)
```

### 소스 해시 영수증

아래 경로는 `/home/gnho1236/r2` 기준이다. `source_hashes`와 동일한 15개 항목이다.
raw NPZ 항목은 압축 파일 바이트 해시이며 보호행의 수치 해석을 뜻하지 않는다.

```text
503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3  research/diagnostic_observability_20261016/sn_tt_audit.json
05cdb7edae34cb31677169adef9d9c1a9ef13b6ee3228a9770a7c6fa6094e986  research/native_reproduction_20261013/native_data.py
30285605c55634ca29912f9855875afc8040c60bae79aff367395067c970b455  research/native_reproduction_20261013/native_data_build.json
d1352bf1b8ec32cae6b970baccfac5a97ba1494daac0a0fda3685ba3974df6b2  research/native_reproduction_20261013/native_data_build.md
86d323810f70e732d945e25358d8488df619f0d9a445697f1b77b82fbfbaaa00  research/native_reproduction_20261013/native_data_profile.py
d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4  research/native_reproduction_20261013/native_inputs/SN/metadata.json
1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8  research/native_reproduction_20261013/native_inputs/SN/raw.npz
31728994c3aeb41ad9c4dfb401d5d15047a21f055bf81e52c80d8a2acff9e207  research/native_reproduction_20261013/native_inputs/SN_build.json
1956804ecec5f191b02ccf52aa189e9529acb6cd256ddde2a24c02caf3e2ae93  research/relationship_smoke_20261013/artifacts/SN.json
1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb  research/relationship_smoke_20261013/artifacts/SN.npz
cb6f035cefaaf8c3c67bde91c733d0d0b234a4857cd6cd88ee80a368bc34ec85  research/relationship_smoke_20261013/data.py
27cff85c74e628aadc518cde48047ad314932aea230f537abd5f9bf79d7a9ab7  research/resource_study_20261013/trace_preflight.py
5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470  research/sn_corrected_20261017/PLAN.md
e94a261509979157b4ec41f7558822c826e8038524aa3258d34686f743ae624d  research/sn_corrected_20261017/input_bundle.py
1234861d053b38bdac6b5651b1d53350563dca3b6fddd327c4f8ef672b19c35a  research/sn_corrected_20261017/test_input_bundle.py
```

## 남은 경계

스케일러·모델·loss·metric 선택은 변경하지 않았다. 순환별 학습행만으로 스케일러를
적합하고 held 값 변경 불변성을 검사하는 일은 부모 실행기 범위다.
로그는 허용 bundle에 별도 정답 배열이 없어 hash-bound native cache 및 생성 출처를
검증했으며, raw 로그에서 독립 재계산하지 않았다. 기존 native 보고서의 SN solver
상한50 도달549회는 과거 전체 build 기록으로, 허용394행만의 신규 수렴 검증이 아니다.
새로운 수렴·recording 독립성·맹검 최종시험 성능은 주장하지 않는다.
