# SN Hawkes horizon 대조 — 기준선 registry

## 목적과 범위

이 문서는 기존 SN200 DiagMLP relative-horizon 기준선을 보존하고, 공개
Eadro fork의 Hawkes horizon만 다른 arm을 만들 때 기존 산출물을 재사용할 수
있는지 기록한다. 새 학습·입력 생성·채점은 수행하지 않았다. 여기서 말하는
contrast는 공개 fork의 처리 대 우리 relative horizon이며, **DiagMLP 저자
구현 재현이나 신규 방법의 증명이 아니다.** SN50→SN200 완료 결과는 기존
진행 기록이지 새로운 비교의 효과량이 아니다.

범위: JSON 및 텍스트 metadata/source만 읽었다. raw/prepared NPZ, event
arrays, checkpoint는 열거나 역직렬화하지 않았고 보호 SN test 169개 및
unassigned 1개 관측과 TT/RE2 관측에는 접근하지 않았다. 기존 결과는
불변으로 두며 이 단계에서 fits를 수행하지 않았다.

## 권위 있는 기존 산출물

기준 디렉터리:
`/home/gnho1236/r2/research/native_reproduction_20261013/calibration200/SN/diagmlp/`

| seed | config / split / history / summary | 선택 결과 (기존 summary와 history 최소) |
|---:|---|---|
| 11 | `seed_11/{config,split,history,summary}.json` | 200 epochs, 400 updates; epoch 192; validation joint loss `0.2565048038959503` |
| 23 | `seed_23/{config,split,history,summary}.json` | 200 epochs, 400 updates; epoch 78; validation joint loss `0.12423702329397202` |
| 37 | `seed_37/{config,split,history,summary}.json` | 200 epochs, 400 updates; epoch 200; validation joint loss `0.07957590371370316` |

완전 경로는 위 디렉터리와 각 seed 상대 경로의 결합이다. 파일별 SHA-256은
각 `summary.json`의 `artifact_hashes`에 기록되어 있고, 아래에 모델 비교에
필요한 연결 필드를 보존했다. Checkpoint replay는 기존 summary에 bitwise
equal validation logits/labels/indices/loss로 표기된 과거 증거이지, 이
registry 작성 중 새로 수행한 replay가 아니다.

## 공통 manifest와 재사용 해시

기존 검증 기록
`/home/gnho1236/r2/research/native_reproduction_20261013/sn200_verification.json`
은 SN 6개 calibration200 실행을 PASS, failures 0으로 기록하고 아래 공통
해시를 제공한다. 해당 기록은 다시 실행하지 않았다.

| 종류 | 경로 | 해시 필드 | SHA-256 |
|---|---|---|---|
| 원 입력 패키지 | `/home/gnho1236/r2/research/native_reproduction_20261013/native_inputs/SN/raw.npz` | verifier `common_manifest.input_hashes.raw.npz` | `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8` |
| 입력 metadata | `/home/gnho1236/r2/research/native_reproduction_20261013/native_inputs/SN/metadata.json` | verifier `common_manifest.input_hashes.metadata.json` | `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4` |
| split | 각 seed의 `split.json` | `summary.artifact_hashes["split.json"]`; verifier `common_manifest.split_hash` | `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d` |
| scaler | 각 seed의 `scaler.npz` | `summary.artifact_hashes["scaler.npz"]`; verifier `common_manifest.scaler_hash` | `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1` |

세 seed summary 모두 같은 split/scaler 해시를 기록한다. split은 seed 42,
NumPy `RandomState/MT19937`, train/validation/test/unassigned 각각
316/78/169/1이며 validation은 seed42 trainval permutation의 마지막
`floor(.2*trainval)`이다. 세 seed 간 metadata의 ordered service 및 split
설정 일치는 기존 `sn200_verification.json`의 공통 manifest/검증 기록으로
뒷받침된다. 이 수치는 test 관측 열람을 뜻하지 않는다.

각 seed의 나머지 artifact SHA-256:

| seed | config.json | history.json | checkpoint.pt | validation_predictions.npz |
|---:|---|---|---|---|
| 11 | `84e6f67dd9518a950a95f57407aac66d107c7fa593008e65823c542940c30b51` | `ccae1afd97517b7b0fed2eec226cfa0d0da33962f0aa3137071e5865b1157abf` | `7b1dfb97306165ddb534ef9ff61a2ce4aaac90c1b99f9366fb8ada950113a911` | `1e48e85005008de75fdfd271df80bfb0daabc47c082757515b6e483614308d5d` |
| 23 | `de19917e74d9804202ec941e3c3b86adb31dd963d730d33b0e3bcf9077df8623` | `9b28377b357523a16cd2c80a0b45d24f6249bea71dc2e79a653d73bf24156a81` | `5c5a463d17f0f09bc79eae092a3d746659bc89ad9ab7a4ff4cd2b96466ecc060` | `6271867b109a6336ad511d2a7b9125e50ed5d90d9a6d33afb759ed224e3c5987` |
| 37 | `314e2efface4b110eaa22c80a69d3e5653ed2ec43dced2923334758a5cbe245a` | `d4269531e504fdac69e0708322664a0badd9e3f576b744651d2d0739ceb1c888` | `be53ab5b3b3eb8997f66dc209abde0835e6d379a1e7e623ddbe729b2707ab869` | `7fb0ad414aede85ce4770a944058f0453ef4d51536f7fbca5d2ea843d8d64b55` |

이 artifact hash들은 seed별 `summary.json`의 동일 이름 필드에서 옮겼으며
이 단계에서 파일 바이트를 재해시하지 않았다. 검증 JSON은 기존
검증 당시의 파일 존재/hash 일치 결과를 기록한다.

## 학습·모델 기준 조건

세 `config.json`에서 공통으로 확인한 조건:

| 설정 | 기준선 값 |
|---|---|
| 방법/데이터 | `kind=diagmlp`, system `SN`, CPU, float32 |
| 최적화 | Adam, lr `0.001`, betas `(0.9, 0.999)`, eps `1e-8`, weight decay `0`, AMSGrad false |
| 반복 | 200 epochs, batch size 256, 400 optimizer updates |
| thread/determinism | intra-op 2, inter-op 1, `torch.use_deterministic_algorithms(True)` |
| seed/순서 | model seed는 각 실행 11/23/37. Python/NumPy/Torch seed 설정은 `native_train.py:191–198`; epoch별 shuffle은 seed별 NumPy `RandomState(model seed).permutation` |
| 선택 | 전체 validation joint loss의 strict minimum; 동률이면 최초 epoch 유지 |
| split/scaler | seed42 split; scaler는 train partition만 fit. SN200 공통 split/scaler hash 위 표 참조 |
| architecture | 12 nodes, 7 events, 7 metrics, window length 10, dropout 0.1, alpha 0.5; modality widths `[64,16,64]`, position/modal/output widths 각 64 |
| heads/encoder | `native_models.py:17–41,51–68`: 공개 Eadro fork의 metric/trace/log modality encoders를 보존하고 EquationDiagEncoder의 position+modal MLP 및 node MLP로 감싼 뒤 core locator/detector heads를 사용 |
| 서비스 순서 | seed config의 `services` 배열. SN ordered 12-service inventory이며 기존 검증 기록은 실행 간 순서 동일을 확인 |

기록된 source provenance:

| 파일/원천 | 출처/기록 |
|---|---|
| 학습 실행 | `/home/gnho1236/r2/research/native_reproduction_20261013/native_train.py`; `run_training` seeds/determinism `191–198`, epoch shuffle/training `278–311`, validation-loss 선택 `296–311` |
| 모델 | `/home/gnho1236/r2/research/native_reproduction_20261013/native_models.py`; `SOURCE_BLOB=d0cf0560a4a2ad0f5d9814f7d6118fc6d989bbbc`; encoder/head 연결 위 참조 |
| encoder source | `/home/gnho1236/r2/research/mlp_prerequisites/eadro_corrected_model.py`; config의 `source_hashes`는 실제 SHA-256을 보존 |
| 원 공개 전처리 근거 | `FeiGSSS/Eadro`, commit `7d69281a80adce60067aa858729746fc6a362f53`, `codes/preprocess/single_process.py`의 `deal_logs/logHaw`; 이는 Hawkes horizon 변경의 공개-fork provenance이지 실제 DiagMLP 저자 학습 설정이 아님 |
| config source hashes | 각 seed `config.json`의 `source_hashes`; SN200 감사에서 공통 기록: `native_train.py` `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7`; `native_models.py` `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632`; `eadro_corrected_model.py` `1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b`; `CALIBRATION_PROTOCOL.md` `862aaa8ab59c0fc2b37e37b5c89c26065fa3e12c31ce36504350f6fddfc7643b` |

세 config의 `versions`는 동일하다: Python `3.8.20` (Clang 18.1.8),
Torch `1.12.1+cpu`, DGL `0.9.1`, NumPy `1.21.5`. 새 arm에서 이 버전이
유지되는지는 아직 확인되지 않았다. `sn200_verification.json`이 기록하는 `common_manifest`는
입력/split/scaler의 공통성이지 모델 RNG 초기 가중치 자체의 hash는 아니다.
모델 초기화의 동일성은 seed별 같은 seed 정책과 동일 source/config로
간접 규정될 뿐, 초기 state hash가 보존되었다고 주장하지 않는다.

## 재사용 판정과 다음 단계 호환성 조건

**기준선 arm 재사용 가능(조건부):** 기존 SN200 seed 11/23/37의
`validation_predictions.npz`, `history.json`, `summary.json`, `config.json`,
`split.json`, `scaler.npz`는 기존 점수/선택/공통 설정의 provenance로
재사용할 수 있다. 이 phase에서 배열을 열지는 않았다. 기존 결과를 새
relative arm으로 다시 학습할 필요가 없다는 판단은 세 seed의 manifest와
SN200 감사/검증 기록을 전제로 한다.

새 horizon arm을 시작하기 전 아래를 metadata/source/code-level로 확인해야
하며, 결과 없이는 세 seed fairness를 확정하지 않는다.

1. 새 실행이 같은 input metadata/raw identity, 동일 316/78 split index와
   ordering, train-only 같은 scaler 통계/정책 및 같은 scaler hash를 사용함.
   Horizon 변경 외의 입력 차이가 생기면 단일 변수 contrast가 아니다.
2. seed별 Python/NumPy/Torch seed, 모델 생성 시점과 초기화 순서, epoch별
   shuffle generator가 기준 구현과 동일한지 확인. Config seed 문자열만으로
   초기 tensor가 같다고 간주하지 않는다. 가능하면 생성된 상태의 안전한
   hash/equality를 검증하되, 이 phase에서는 생성/비교하지 않았다.
3. 동일 native source/config hash 또는 horizon loader 외 변경이 없는
   source diff, 동일 encoder/locator/detector head와 parameter shapes,
   dropout `0.1`, train/eval mode, optimizer, loss, batch size, epochs,
   dtype, deterministic algorithms 및 runtime library versions 확인.
4. validation에서 동일 78 indices/order와 동일한 validation-loss 기반
   earliest strict-minimum checkpoint selection을 유지. 최종 선택 epoch는
   horizon 효과로 달라질 수 있으나 선택 규칙은 달라지면 안 된다.
5. 계획된 공개-fork horizon 처리의 실제 end-time 값/분포가 기준 relative
   arm과 다른 값은 `end_times`뿐인지, 그리고 입력 생성 source가
   `deal_logs/logHaw`의 relative knots `timestamp-s` 및 absolute end
   `e+1` 규칙인지 다음 phase에서 검증. 현재 코드가 이 값과 완전히
   호환되리라 미리 가정하지 않는다.
6. 기준 config와 새 arm의 Python/Torch/DGL/NumPy 실제 버전을 대조해
   동일성을 확인.

이 조건들이 맞으면 새로운 arm은 최대 3 fits(seed 11/23/37)이며 기존
relative 기준선 fit을 반복하지 않는다. 확인 실패 시 차이를 기록하고
fairness/원인 귀속을 보류한다. Contrast는 공개-fork horizon-only 대조이며
DiagMLP 원저자 구현의 복원, 새 방법의 독립적 신규성 또는 성능 우월성을
주장하지 않는다.

## 기존 SN50→SN200 결과

기존 calibration50→calibration200 verifier 기록은 설정/split/scaler
일치 및 첫 50개 history의 loss/score/update 일치, 이후 200-epoch 완료를
기록한다. `sn200_verification.json`: PASS, 6/6 실행, failures 없음;
late-epoch trigger는 있었으나 extension은 실행되지 않았다. 기존 validity
audit의 상대 성능 변화 `+5.64%p`는 그 완료 비교의 기록이며, 본 제안
horizon contrast의 효과가 아니다. 새 재실험/확대 근거로 사용하지 않는다.

## 출처 문서와 누락 항목

- `/home/gnho1236/r2/research/sn200_validity_audit_20261017/REPORT.md`
- `/home/gnho1236/r2/research/sn200_validity_audit_20261017/SELECTION.md`
- `/home/gnho1236/r2/research/sn200_validity_audit_20261017/SCORING.md`
- `/home/gnho1236/r2/research/native_reproduction_20261013/sn200_verification.json`
- `/home/gnho1236/r2/research/native_reproduction_20261013/calibration200/SN/diagmlp/seed_{11,23,37}/{config,summary,split,history}.json`

요청에 지정된 `/home/gnho1236/r2/research/sn200_validity_audit_20261017/followup_gate.md`
는 해당 경로에서 찾을 수 없어 읽지 못했다. 기존 보고서들이 언급한
`sn200_error_windows.json`은 이 registry에 필요한 설정/해시 확인을 위해
열지 않았다. 초기 state hash는 미확인이다.
