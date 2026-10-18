# 독립 분석 검증 — PASS

## 현재 판정

**PASS — `analysis_v2/`의 저장 분석을 여섯 validation prediction archive에서 독립 계산해 확인했다.** 독립 재계산한 Top-1 점수, primary/secondary paired partition, 전체 paired 행, 사례목록, 예측 해시, history 선택 및 요청된 분석 산출물이 일치한다. 이 판정은 저장된 SN validation 분석에만 해당한다.

비교 방향은 `relative-after − absolute-before`다. Absolute-before는 `runs/absolute_seed_{11,23,37}/`; relative-after는 기존 `/home/gnho1236/r2/research/native_reproduction_20261013/calibration200/SN/diagmlp/seed_{11,23,37}/`다. 모든 seed·arm에서 fault 65개, normal 13개, 전체 78개를 확인했다. Conditional root 지표는 normal을 제외한다. Root/detection의 정확 동률은 균등 기대 credit으로 계산했으며, gated credit은 root credit과 fault-detection credit의 곱이다. 평균은 세 seed의 비가중 평균이고, 195 window-seed 기록을 독립 사건으로 취급하지 않는다.

## 독립 수치 재계산

Producer/analyzer 함수를 호출하지 않고 여섯 `validation_predictions.npz`만 `allow_pickle=False`로 열었다. 정답 logit보다 큰 후보 수와 동률 후보 수로 Top-k의 기대 순위 credit을 직접 계산하고, 두 arm의 배열 인덱스와 라벨 순서가 같은지 확인했다. Metadata의 `original_indices`/`validation_positions`를 이용해 각 예측을 창과 root에 대응했다. 저장 점수는 아래 독립 계산과 일치한다.

| Seed | Conditional root Top-1: absolute → relative | Conditional root Top-3: absolute → relative |
|---:|---:|---:|
| 11 | 63/65 → 60/65 | 65/65 → 63/65 |
| 23 | 63/65 → 64/65 | 64/65 → 64/65 |
| 37 | 60/65 → 62/65 | 65/65 → 65/65 |
| 세 seed 평균 | **95.384615% → 95.384615%** | 99.487179% → 98.461538% |

Primary metric인 root Top-1의 독립 paired partition은 **183 both-correct / 6 both-wrong / 3 new-correct / 3 new-wrong (총 195)**다. 별도 secondary gated-joint Top-1 partition은 **181 / 8 / 3 / 3 (총 195)**다. 두 지표는 서로 다른 partition이며 혼용하지 않았다. `paired_summary.json`의 `conditional_root_partition` 및 `gated_joint_partition` count와 일치한다.

`paired_fault_windows.csv`의 195행 모두를 seed와 원본 index로 찾아 root 정답 credit, detection credit, gated credit, Top-3 credit, 원본 index, event ID, start, root fault group/name을 다시 계산·비교했다. **모든 비교 필드가 일치했고 누락·중복 paired key 및 metadata/label 불일치는 없었다.** CSV의 `before_*`/`after_*`는 위에 정의한 absolute-before/relative-after arm이다. 저장된 `root_new_correct.csv`와 `root_new_wrong.csv`는 각각 독립적으로 만든 전체 사례 집합과 정확히 같으며 모두 seed, `original_index`, event ID, start, root group/name 및 양 arm의 credit을 갖는다.

| Root Top-1 사례 | Seed | Original index | Event | Root group / 정답 root |
|---|---:|---:|---|---|
| 새 정답 | 23 | 136 | `SN.2022-04-17T181245D2022-04-17T183616:fault08` | `media-service|network_loss` / media-service |
| 새 정답 | 37 | 346 | `SN.2022-04-17T190213D2022-04-17T192544:fault04` | `unique-id-service|network_delay` / unique-id-service |
| 새 정답 | 37 | 136 | `SN.2022-04-17T181245D2022-04-17T183616:fault08` | `media-service|network_loss` / media-service |
| 새 오답 | 11 | 129 | `SN.2022-04-17T181245D2022-04-17T183616:fault08` | `media-service|network_loss` / media-service |
| 새 오답 | 11 | 112 | `SN.2022-04-17T181245D2022-04-17T183616:fault07` | `media-service|network_delay` / media-service |
| 새 오답 | 11 | 258 | `SN.2022-04-17T183729D2022-04-17T190100:fault07` | `url-shorten-service|network_delay` / url-shorten-service |

Gated partition도 fault label이 있는 195행에 대해서만 별도 재구성했다. Normal label `-1`인 13행/seed는 root fault partition에서 제외되며, 세 seed의 normal detection 변화는 별도 `normal_detection_changes.csv` 3행에 기록돼 있다. Root 및 gated 사례목록은 각각 독립 계산된 사례와 동일하다. Paired summary의 distinct-event/window 집계도 기록 단위와 구분해 보고하며, seed 독립성 주장은 하지 않는다.

## 해시, history, 입력 및 실행 근거

여섯 prediction archive의 실제 SHA-256은 다음과 같고, 각각 `analysis_v2/input_audit.json` 및 **동일 arm/seed의** `summary.json.artifact_hashes["validation_predictions.npz"]` 값과 일치한다.

| Seed | Absolute-before SHA-256 | Relative-after SHA-256 |
|---:|---|---|
| 11 | `0f45452113bf34bbce87458be49c5dbfbadf75611a228ff32254f004a58d9b6b` | `1e48e85005008de75fdfd271df80bfb0daabc47c082757515b6e483614308d5d` |
| 23 | `dc6e038caf47175f8e681a458918bf22f81c620f843be003b5810377a1fa97a6` | `6271867b109a6336ad511d2a7b9125e50ed5d90d9a6d33afb759ed224e3c5987` |
| 37 | `af678df5966fac884ac25eff08583fe692c01d11fff45590563884f24cb4add4` | `7fb0ad414aede85ce4770a944058f0453ef4d51536f7fbca5d2ea843d8d64b55` |

각 arm/seed의 실제 config, history, prediction SHA-256도 해당 summary의 자체 `artifact_hashes`와 모두 일치했다. Absolute와 relative config hash가 서로 다른 것은 arm별 설정·경로 차이와 일치한다. `HASH_CLARIFICATION.md`의 absolute config 실제 해시도 각 absolute summary와 일치한다. 따라서 이전 분석 노드의 arm 간 config hash 혼동은 데이터 불일치가 아니며, 현재 검증은 cross-arm 해시 동일성을 요구하지 않았다.

각 6개 history는 200 epoch이며 strict minimum validation joint loss가 summary의 `best_epoch`/`best_validation_joint_loss`와 일치한다.

| Seed | Absolute-before 선택 epoch; 최소 loss | Relative-after 선택 epoch; 최소 loss |
|---:|---|---|
| 11 | 190; 0.171455979347229 | 192; 0.2565048038959503 |
| 23 | 115; 0.10320687294006348 | 78; 0.12423702329397202 |
| 37 | 164; 0.06605657935142517 | 200; 0.07957590371370316 |

`history_metrics.csv` 24개 행(epoch 1/50/200/selected × 6 arm-seed 조합)의 validation loss 및 선택 epoch를 저장 history/summary와 대조해 모두 일치했다. `analysis_v2/analysis-run.log`에는 `ANALYSIS_PASS ... root_partition=195 joint_partition=195` 및 `ACTUAL_EXIT_CODE=0`이 있다. 독립 검증에서는 분석, 학습, inference, preprocessing, replay, test를 재실행하지 않았다. Phase 2의 최종 PASS 및 세 absolute fit의 exit-0/replay 기록, validation 순서·라벨 재사용, 준비 단계의 relative solver exact-equivalence 증거는 `EXECUTION_VERIFY.md`의 기록을 재사용했다. Checkpoint를 다시 열지 않았다.

`analysis_v2/input_difference.json`은 `inputs/preparation.json.input_difference`와 구조 및 값이 완전히 동일하다. 입력 차이 결과를 새 telemetry로 재생산하지 않았다. 준비 기록은 394개 허용 창에서 absolute `original_window_start + 10`과 relative `10`의 관측 horizon 차이를 보고한다. 로그 차이와 예측 점수 변화는 관측 사실이며, 이 분석만으로 구체적인 오류 메커니즘·최적 수렴·일반화 또는 인과 효과를 주장하지 않는다.

## 산출물 및 보존된 실패 이력

요청된 네 산출물 묶음은 `analysis_v2/`에 실제 비어 있지 않은 파일로 존재한다: (1) `settings.csv`, (2) `input_difference.json`, (3) seed별·평균 지표가 든 `scores.json`, (4) 전체 `root_new_correct.csv` 및 `root_new_wrong.csv`. 추가로 195행 전체 근거 CSV, 별도 joint 사례목록, normal detection CSV, history 표, input audit, paired summary 및 exit-0 실행 로그가 존재한다. `analysis_v2`를 현재 결과로 사용했으며, 기존 `analysis/`의 이전 산출물은 현재 판정 근거로 혼용하지 않았다.

실패 이력은 다음과 같이 구분해 보존한다.

- `EXECUTION_VERIFY.md`의 seed-23 최초 19/200 epoch·38/400 update 미완료 FAIL 및 summary/exit-0 부재는 역사적 partial attempt다. `runs/absolute_seed_23_interrupted_attempt1/`은 분석 입력이 아니며, 이후 canonical `runs/absolute_seed_23/` 실행은 exit 0, 200 epoch/400 update, 선택 epoch 115의 PASS다.
- `analysis/analysis-attempt-1.log`의 `'seed'` KeyError / exit 1은 점수를 산출하지 못한 과거 실패다. 이전 분석 노드의 arm 간 config 해시 비교 중단도 `HASH_CLARIFICATION.md`에서 실제 absolute 해시와 각 자체 summary 해시가 일치하는 것으로 정정됐다. 최종 현재 분석은 별도 `analysis_v2/analysis-run.log`의 exit 0이다.
- Phase-2 기록의 이전 NOTREADY preflight 및 최초 pyright 실패는 후속 corrected PASS와 구분해 남아 있다. 재실행하거나 실패 기록을 삭제하지 않았다. Phase-2에 기록된 `EXECUTION_PROTOCOL.md` 문서 fingerprint drift도 provenance caveat이며, 데이터·실행 코드 변경으로 귀속하지 않는다.
- Hawkes solver iteration cap 도달 기록은 relative 387 / absolute 470 groups다. 상한 도달은 수렴 증거가 아니므로 수렴 주장을 하지 않는다.

## 주장 범위

결과는 고정된 SN validation의 horizon contrast에 한정된다. Primary Top-1 평균은 두 arm에서 동일하게 95.384615%이고, 사례 변화는 유리 3건/불리 3건이다. 이를 효과 입증, 원저자 DiagMLP 전체 실험 재현, 다른 seed의 독립 반복 증거, 또는 TT/RE2 일반화로 확대하지 않는다. TT/RE2 및 보호된 SN test/unassigned 관측값은 이 검증에서 열거나 분석하지 않았다.
