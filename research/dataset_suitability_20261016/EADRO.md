# Eadro 개발 묶음의 분할 역할 점검

## 결론과 활용 역할

허용된 SN·TT 개발 묶음의 메타데이터로 기존 사건 3-fold, recording holdout,
fault-type holdout을 비교했다. 세 정책 모두 메타데이터 계산과 검사를 통과했지만,
**새 최종 분할을 채택하거나 모델 정확도를 시험한 결과는 아니다.**

- **권장:** 기존 사건 3-fold는 이미 수집된 장애 사건에서 알려진 원인 서비스를
  개발·설정 탐색하는 역할에 한정한다. 고장 root는 모든 fold에서 알려져 있지만
  같은 recording을 TRAIN과 heldout이 공유한다.
- **별도 스트레스 점검:** recording holdout은 새 수집 recording을 남겼을 때의
  표적 손실을 드러낸다. 매 holdout마다 TRAIN에서 root 세 개의 고장 사례가
  완전히 빠지지만, 후보 서비스 목록은 그대로다. 이를 root 일반화 평가로
  부르거나 이 자료에서 새 root 최종평가를 주장할 수는 없다.
- **고장 종류 확장 점검:** fault-type holdout은 기존 root를 유지하고 한 종류의
  장애를 통째로 heldout한다. 정상 창도 그 창이 연결된 episode의 고장 종류에
  따라 같이 배정된다. recording은 양쪽에 공유되며 모델 성능은 측정하지 않았다.

따라서 SN 36건·TT 81건이라는 수만으로 MLP 학습 불가나 자료 부적합을 말할 수 없다.
세 종류의 고장과 root×종류 조합은 갖춰져 있으나, 조합별 관측은 한 번뿐이다.
이전에 사용된 개발 사건이므로 pristine final evidence가 아니며, 이 실행은
독립적인 새 recording·새 root에 대한 성능 근거를 제공하지 않는다.

## 확인한 자료와 보호 경계

분할 구성에는 `relationship_smoke_20261013/artifacts/{SN,TT}.json/.npz`를 사용하고,
기존 `fold_metadata_audit.json`은 사건-fold counts 대조에만 사용했다.
압축 배열에서 읽은 항목은 `indices`, `labels`, `event_ids`, `episode_ids`,
`fold_ids`, `partition` 여섯 개뿐이다. 별도 crosscheck는 허용된 native profile의
집계 metadata만 읽었다. 특징/관측값, 원 native stream, 모델, checkpoint, 예측은
읽거나 만들지 않았다. 보호된 native test/unassigned와 RCAEval 최종 관측·예측은
접근하지 않았다.

허용된 기존 metadata 감사를 대조한 결과:

| 자료 | fault 사건 | fault recording | root 수 | fault 종류 | root×종류 조합 |
|---|---:|---:|---:|---:|---:|
| SN | 36 | 4 | 12 | 3 | 36, 각 1회 |
| TT | 81 | 9 | 27 | 3 | 81, 각 1회 |

각 fault recording은 9개 사건, root 3개, fault 종류 3개를 포함한다.
기존 native profile은 두 자료 모두 추가 normal-only archive recording이 3개임을
기록한다. 이 archive들은 라벨된 fault 사건을 늘리지 않으므로 fault 사건 수는
각각 36/81로 유지된다. 이 profile의 SN 7개·TT 12개 전체 recording 수에는
fault recording과 normal-only recording이 함께 포함된다.

기존 `fold_metadata_audit.json`에 기록된 event-fold 창/사건 수와 새 계산을
대조했다. 기존 `recordings.json` 및 native profile을 recording/원인 분포의
메타데이터 근거로 사용했으며 raw provenance 경로를 따라 다른 자료를 열지 않았다.
이번 2026-10-16 실행에서 새로 만든 것은 세 정책의 정확한 membership 및 지원 집계다.
36/81 사건, 추가 normal-only recording, 기존 fold counts는 이전 metadata 감사에서
가져와 대조한 역사적 근거이며, 원자료 permutation test나 이전 학습은 재실행하지 않았다.

## 정책별 실제 결과

TRAIN/heldout은 해당 임시 정책의 구성원을 뜻한다. JSON에는 각 분할의 원래
창 인덱스와 사건 ID가 정확히 보존되어 있다.

### 사건 3-fold

행 단위 분할은 기존 `fold_ids`를 사용한다. 정상 창도 지정된 fault episode의
fold를 따른다. 모든 fold에서 사건 ID 중복은 0이고, 모든 root와 세 종류의
고장이 TRAIN·heldout 양쪽에 지원된다.

| 자료 | fold | TRAIN 창 (fault/normal) | TRAIN 사건 | heldout 창 (fault/normal) | heldout 사건 | 공유 recording |
|---|---:|---:|---:|---:|---:|---:|
| SN | 0 | 262 (217/45) | 24 | 132 (108/24) | 12 | 4/4 |
| SN | 1 | 272 (227/45) | 24 | 122 (98/24) | 12 | 4/4 |
| SN | 2 | 254 (206/48) | 24 | 140 (119/21) | 12 | 4/4 |
| TT | 0 | 2,703 (2,292/411) | 54 | 1,366 (1,159/207) | 27 | 9/9 |
| TT | 1 | 2,701 (2,278/423) | 54 | 1,368 (1,173/195) | 27 | 9/9 |
| TT | 2 | 2,734 (2,332/402) | 54 | 1,335 (1,119/216) | 27 | 9/9 |

이는 사건 holdout이지 recording-disjoint 평가가 아니다. 기존 fold 감사 수치와
일치하며 모델의 교차검증 정확도를 뜻하지 않는다.

### Recording holdout

각 fault recording을 한 번씩 통째로 heldout했다. SN의 각 TRAIN/heldout은 각각
27/9 사건, TT는 72/9 사건이다. 각 holdout에서 정확히 세 root의 TRAIN 고장
사례가 사라지지만 전체 후보 inventory는 각각 12/27 root로 유지된다.
각 recording별 인덱스·사건 구성 및 제거된 root는 JSON에서 확인할 수 있다.
모든 recording holdout은 TRAIN과 heldout 사이 recording 중복이 없고, 두 부분 모두
normal episode가 세 fault type 전체에 지원된다.

| 자료 | TRAIN 창 범위 (fault/normal) | heldout 창 범위 (fault/normal) | 매 holdout 제거 root | 후보 inventory |
|---|---:|---:|---:|---:|
| SN | 293–299 (240–246 / 50–53) | 95–101 (79–85 / 16–19) | 3 | 12 유지 |
| TT | 3,603–3,627 (3,050–3,077 / 543–554) | 442–466 (374–401 / 64–75) | 3 | 27 유지 |

이 결과는 수집 recording을 바꾸면 원인 target coverage가 달라질 수 있음을
보인다. 후보 목록의 유지와 학습 target의 지원은 서로 다른 조건이다.

### Fault-type holdout

각 fault 종류를 하나씩 heldout했다. 매 경우 TRAIN 사건은 SN 24/TT 54,
heldout 사건은 SN 12/TT 27이며 전체 root는 두 부분 모두에서 알려져 있다.
TRAIN의 root당 두 종류와 heldout의 root당 한 종류는 지원되지만, TRAIN 정상 창에는
heldout 종류에 배정된 episode가 없고 heldout 정상 창에는 다른 두 종류의 episode가
없다. 이는 정상 창의 episode 할당 규칙에 따른 의도된 support 차이다.
세 fault-type 정책 모두 TRAIN과 heldout이 SN 4/4, TT 9/9 recording을 공유한다.

| 자료 | heldout 종류 | TRAIN 창 (fault/normal) | heldout 창 (fault/normal) | TRAIN 정상의 종류 support | heldout 정상의 종류 support |
|---|---|---:|---:|---|---|
| SN | cpu_load | 274 (218/56) | 120 (107/13) | delay, loss | cpu_load |
| SN | network_delay | 254 (212/42) | 140 (113/27) | cpu_load, loss | network_delay |
| SN | network_loss | 260 (220/40) | 134 (105/29) | cpu_load, delay | network_loss |
| TT | cpu_load | 2,729 (2,281/448) | 1,340 (1,170/170) | delay, loss | cpu_load |
| TT | network_delay | 2,744 (2,326/418) | 1,325 (1,125/200) | cpu_load, loss | network_delay |
| TT | network_loss | 2,665 (2,295/370) | 1,404 (1,156/248) | cpu_load, delay | network_loss |

숫자는 메타데이터 지원 수일 뿐, 새 fault type으로의 성능 일반화를 증명하지 않는다.

## 연구 주장 정정과 미확인 사항

이전 자체 5-epoch probe에서 나온 “CPU는 쉽고 network는 어렵다”는 표현은
그 probe에만 한정해야 한다. 이후 native-like TT DiagMLP 개발 결과는
network fault의 validation Top1이 약 91% (보고값 90.94%)였으므로,
일반 baseline weakness라는 주장은 지지되지 않는다. 이 시험에서는 그 모델이나
어떤 모델도 다시 실행하지 않았다.

아직 확인되지 않은 것은 새로운 recording/root에 대한 최종 성능, 각 조건의 반복
변동, 이 메타데이터가 모델 학습에 충분한지 여부다. final split은 채택하지 않았다.

## 재현 및 실행 증거

요청된 명령:

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m research.dataset_suitability_20261016.eadro_trial
```

실행 환경은 Python 3.10.12 / NumPy 1.26.4, 분석 경과 0.1102초,
최대 RSS 758,892 KiB였다. JSON의 `input_sha256`에는 두 bundle의 JSON/NPZ와
재사용한 fold audit가, `source_sha256`에는 실행 스크립트가 기록되어 있다.
스크립트 hash는 결과의 hash와 사후 대조해 일치했다.

최종 actual-run monitor ID `mon_9JCN7Q3NT8WXFPVR`, bash session ID `bash_15`.
저장된 `bash_output` 응답:

```text
status: completed exit_code: 0
EADRO_METADATA_SPLITS SN 36 4
EADRO_METADATA_SPLITS TT 81 9
EADRO_SUITABILITY_PASS
```

최종 단위검사 5개는 통과했고 package import와 repo-root discovery를 각각
실행했다. `eadro_trial.py`·`test_eadro_trial.py` 대상 Pyright는
0 errors/warnings/informations였다. 전체 폴더 Pyright 호출은 이 범위 밖인
`rcab_trial.py`의 3개 오류로 실패했으며 해당 파일은 수정하지 않았다.
LSP 진단은 실행 스크립트에서 발견 사항이 없었다.

재사용 metadata 근거 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `native_data_profile.json` | `94b6ad69cce0a277d4c05ec5aab3d137428f06115aecbb08eba138ff17df91ea` |
| `relationship_diagnosis_20261014/recordings.json` | `651fb4bbda6e8034290cca87ba4ddf325fb39f72c92a87593c4d6ccc913b4f9f` |
| `diagnostic_observability_20261016/sn_tt_audit.json` | `503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3` |
| `tt_native_support_20261014/REPORT.md` | `da82eb000cf3a54c898f384831c1ed0b5b67111b86869e38b3e46dcb50afa47d` |

기계 판독 가능한 전체 membership·support·hash는 [`eadro_trial.json`](eadro_trial.json)에 있다.
