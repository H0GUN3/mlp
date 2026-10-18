# 검증 기록 — 2026-10-18

## 판정

- **대표 수치 비교: PASS (5/5).**
- **집중 테스트 및 Pyright: PASS.**
- **엄격한 전체 요청 프로토콜: FAIL/불완전.** 첫 원형 profile 실행은 fit 후 `pandas imported` assertion에서 exit 1이었고 profile/baseline 산출물이 저장되지 않았다. 실패 기록은 보존되어 있으며 재실행하지 않았다.
- **전체 80,028개 동등성 및 운영 rollout: 미확인, 승인 불가.**
- **2시간 비용 기준: FAIL.** 저장 표본의 후보 평균으로 계산한 네 worker 이상적 외삽도 약 45.71시간이다.

## 독립 비교 방법 및 결과

각 원형은 저장된 세 Hawkes NPZ의 `baseline` 배열과 두 교차 사례의 저장 reference JSON에서 직접 읽었다. 후보 다섯 개도 각각 저장 JSON에서 읽었다. 어떤 solver fit도 실행하지 않았다. 원형·후보 모두 길이 1,025인지 확인한 뒤 `float64` 원형 값을 `float32`로 변환하고 `np.array_equal` 및 바이트 일치를 확인했다. 다섯 모두 두 비교를 통과했고 mismatch index는 없었다. iteration과 warning list도 다섯 모두 일치했다.

| index | exact knot key | knot JSON SHA256 확인 | 원형=후보 iteration | 경고 동일 | float32 동일 | float64 동일 |
|---:|---|---|---:|---|---|---|
| 0 | `02da892953b24a791b942ca0957f01146803ffbd4cb15c90649bd821420ea769` | 예 | 11=11 | 예 (`[]`) | 예 | 예 |
| 1 | `8ec3888e3d3f4a338ef633f9ff119eed95604cbf2c2807e353dec762003240c6` | 예 | 21=21 | 예 (`[]`) | 예 | 아니오 |
| 2 | `a28ca4be74f07bed0c393a3bc88deb773caa1e618c5b4b39add372759990dbb1` | 예 | 50=50 | 예 (`[]`) | 예 | 아니오 |
| 3 | `256ced53930466b4aae8c50dfb20e03dcebd1d42b5e8bad35b0522a86a7d0f3f` | 예 | 31=31 | 예 (`[]`) | 예 | 아니오 |
| 4 | `c7a77521fb6a18c0fde4af23045c1b905d523d2a2e0b9918434a3391556500a5` | 예 | 21=21 | 예 (`[]`) | 예 | 아니오 |

모든 입력은 고정 selection에 기록된 1,025개 knot, seed 42, baseline 시작값 0.2, decay 3, horizon 10, native uniform(.5,.9) adjacency, native zero ADMM 시작, `max_iter=50`, `tol=1e-5`, EM max 30, single thread 및 기록 설정을 유지했다. 다섯 knot 파일의 저장 SHA256을 독립 재계산해 모두 일치시켰고, reference/candidate 기록의 key도 선택 key와 맞았다. float64 차이는 허용오차로 숨기지 않았다. 실제 특징 판정은 사전 계약된 최종 float32 배열의 정확한 동일성이다.

## 캐시·고유 입력 산술

- 프로파일 수치: 91,060 nonempty + 52,762 empty = 143,822 전체 위치.
- 정확한 knot-key 고유 입력 80,028개. `91,060 − 80,028 = 11,032` 중복 위치는 기존 그룹화에서 이미 제거된다.
- 세 기존 캐시 각각에서 NPZ SHA256, JSON key, split/input-binding/snapshot provenance, seed 42, event_count 1,025, 단일 `baseline` 필드, (1025,) float64 배열, finite·nonnegative 조건을 독립 확인했다. 남은 고유 입력은 `80,028 − 3 = 80,025`다.
- 비용 재산술: 원형 세 시간 평균 23.0715646초. 후보 첫 사례 세 시간 평균 8.2245901초. `80,028 × 후보평균 / 4 / 3,600 = 45.70816시간`; 세 cache hit 제외 시 45.70645시간. 16-worker 완벽 선형분할은 11.42704시간이다. 2시간 대비 각각 약 22.85배, 5.71배다. 병렬 속도는 실측이 아니다.

## 실행한 검사

- 집중 단위 검사:
  `.venv-eadro/bin/python -B -m unittest discover -s research/re2_ob_known_condition_20261018/cost_preservation -p test_equivalent_backend.py -v`
  **exit 0, 10 tests / 0.147초 / OK.** 테스트 중 설치된 SciPy의 `special_matrices` deprecation warning이 한 번 출력됐으나 테스트는 통과했다. solver 비교에서 저장된 경고 목록은 원형·후보 모두 빈 목록이었다.
- 명시적 Pyright:
  `pyright --project research/re2_ob_known_condition_20261018/pyrightconfig.json research/re2_ob_known_condition_20261018/cost_preservation/equivalent_backend.py research/re2_ob_known_condition_20261018/cost_preservation/test_equivalent_backend.py research/re2_ob_known_condition_20261018/cost_preservation/benchmark.py research/re2_ob_known_condition_20261018/cost_preservation/probes/native_runtime.py`
  **exit 0, errors 0 / warnings 0 / informations 0.**
- 실제 benchmark exit와 profile은 저장된 `benchmark.json`, `NUMERICS.md`, `probes/reference-3.json` 및 completion records를 재사용했다. benchmark, 원형 producer, 전체 preparation, neural fit은 재실행하지 않았다.
- 선택 manifest의 `immutable_before`에 기록된 31개 원본 코드·설치 tick 소스·캐시·입력 artifact를 현재 SHA256과 대조했다. 누락/불일치 0개. 세 기존 cache NPZ와 metadata도 위 항목별로 재검산했다. 이 범위 밖 파일 전체까지 해시 검증했다고 주장하지 않는다.

## 한계와 남은 프로토콜 실패

원형 세 cache 결과와 두 저장 cross-reference를 후보 다섯 결과와 대조한 것은 대표 다섯 입력 검증이다. 80,028개 전체의 float32 bitwise 동등성·수렴·경고·비용을 인증하지 않는다. 첫 profile 실패는 후속 cross-profile 성공으로 상쇄되지 않으며, 그 첫 사례 profile 수치도 복구했다고 주장하지 않는다. 비용 외삽 표본에는 전체 입력 분포의 신뢰구간이 없고, 이상적 worker 나눗셈을 실제 처리시간으로 해석할 수 없다.

전체 rollout 검증에는 별도 승인을 받아 모든 고유 입력의 원형/후보 결과를 고정 계약 아래 비교하고, 전체 provenance, iteration, warning, 실패 복구, 실제 병렬 처리량·메모리를 확인해야 한다. 본 검증은 그 후속 단계에 착수하지 않았으며, 템플릿 상한을 자동 설정하거나 입력·solver·운영 코드를 변경하지 않았다.
