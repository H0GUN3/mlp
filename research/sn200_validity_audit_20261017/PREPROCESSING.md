# SN200 preprocessing·적합 범위 및 target 정보 흐름 감사

## 판정 요약

**고득점이나 전체 raw 로드만으로 누출을 판정하지 않았다.** 코드상 scaler는 train-only이고, root/event/injection 메타데이터는 feature graph에 전달되지 않는다. Drain 템플릿은 별도 정상 로그로 고정 학습하며, Hawkes는 각 입력 window 로그에서 feature를 계산한다. 이는 held-out 관측에 의존하는 창 로컬 변환이지, train 통계로 오인하지 않았다.

| 항목 | 관찰·근거 | 판정 |
|---|---|---|
| Metric/trace scaler | `native_train.py:158–174, 227–236`; train index만 평균·표준편차에 사용, 같은 값을 train/validation에 적용. `config.json`의 `scaler.fit_partition=train`, `axes=window,time per node/channel`, `ddof=0`, `epsilon=1e-8`와 일치. SN constant channel은 metric `[]`, trace `[node 0..11, channel 1]`; constant는 `std=0`, 첫 train 값으로 mean 고정, 분모에 epsilon, clipping 없음. | `notfoundwithinscope` |
| Drain template/reference | `native_data.py:163–171, 200–225, 325–351`; SN metadata `template_training`은 지정된 no-fault 3개 세션의 53,522 lines를 명시. 학습은 `add_log_message`; 기록 window에는 `miner.match`만 호출. 6개 템플릿 + unseen index 0 = event_count 7. 보조 정상 로그는 window split 이전에 별도 reference로 쓰이며, fault label로 선택되지 않는다. | `notfoundwithinscope`; offline normal-reference 조건은 `limitedevaluation` |
| Hawkes baseline | `native_data.py:456–507, 554–601`; 로그가 있는 각 `(window,node)`별 fit, SN build 기록은 2,027 fit. 각 event knot는 그 window의 timestamp에서 window start를 빼고, 동률에 `1e-5` jitter; horizon 10초, `HawkesADM4(3)`, baseline start `.2`. Seed는 `42 + window_index*node_count + node`; memoization disabled. `labels`, injection `event_id/group`는 task 입력에 없다. | `notfoundwithinscope`; 창 로컬 관측 변환임을 명시 |
| Label→feature/candidate 경로 | `native_data.py:135–146, 351–388, 602–625`; fault interval overlap으로 root label 및 provenance를 별도 생성. `native_train.py:191–199`; graph에는 metrics/traces/logs와 정적 edge만 넣고 labels는 별도 반환. `native_models.py:48–55, 58–103`; encoder는 세 modality와 위치 임베딩을 사용하고 labels는 `joint_loss`의 detection/root supervision에만 쓰임. candidate는 root별 필터가 아니라 고정 author SN service 12개 (`root_logits` 12열). | `notfoundwithinscope` |
| 전체 raw 선로딩 | `native_train.py:47–58`은 split 전에 `np.load(raw.npz)` 후 네 key 전체를 배열로 복사한다. 따라서 역사적 학습 경로는 test feature와 label도 메모리에 읽는다. 이후 scaler는 train만, `scaled_partition`/model 전달은 train·validation만 (`:234–236, 191–215`); test는 저장 split 대상이고 test 평가 호출은 없음 (`config.test_evaluated=false`). | 전체 읽기는 **확인된 구현 사실**; 그것만으로 fit/score 누출은 입증되지 않음 (`notfoundwithinscope`) |
| Split 독립성 | `native_train.py:75–122, 124–155`; seed42 window permutation: train 316, validation 78, test 169, unassigned 1. `split.json.shared_event_counts`: train/validation 28, train/test 36, validation/test 28; 각 split이 각각 36/28/36 injection event를 포함. `disjoint_indices=true`; window는 recording 내 비중첩으로 검사됨. 서로 다른 window가 같은 run/injection을 공유하므로 독립 incident 성능으로 해석할 수 없다. | `limitedevaluation`; raw-value overlap으로 확대 해석하지 않음 |

## 재현 가능한 산식 및 해석 경계

Scaler (`native_train.py:158–188`):

```python
train = arrays[key][train_indices].astype(np.float64)  # key: metrics, traces
mean = train.mean(axis=(0, 2))
std = train.std(axis=(0, 2), ddof=0)
constant = np.all(train == train[:1, :, :1, :], axis=(0, 2))
z = (value - mean[None, :, None, :]) / (std[None, :, None, :] + 1e-8)
```

constant에서 `std=0`, mean은 첫 train window/time의 값이다. SN config에서 이에 해당하는 trace channel 1은 12개 node 전부이며 metric constant channel은 없다. `logs`는 scaler 없이 float32로 전달된다. scaler NPZ는 역직렬화하지 않았다.

Hawkes는
`group(log_window, log_node) → make_knots(log_timestamp, log_template, window_start) → fit_hawkes`
경로다 (`native_data.py:495–507`). 따라서 validation/test의 **자기 로그 관측**이 해당 창의 baseline feature 계산에 쓰인다. 이는 훈련 집합에서 학습한 전역 통계가 아니며 label/event metadata 경로도 아니다. 별도 입력으로 바뀌지 않은 각 held-out window를 쓴다는 점은 평가 조건으로 남긴다. `metadata.json.repairs`의 `memoization=disabled`와 source 구현에 cache 경로가 없음을 확인했다.

Injection label은 `window_labels`에서 fault endpoint와 window overlap으로 계산한다. raw metadata의 `event_id`, `root_fault_group`, `run_id`, 시간은 split provenance/겹침 요약에 남지만 `graph_batch`의 node data key가 아니며, candidate 집합은 모든 SN 서비스로 고정된다. feature `logs`의 event index는 **Drain 로그 템플릿 ID**이므로 injection `event_id`와 다르다.

## 산출물 정합성과 재사용 근거

`calibration200/SN/diagmlp/seed_{11,23,37}/config.json`은 공통으로 다음을 기록한다: raw `1a01dbacc9b69a6fb931182012eb93c7bec336e1c310815f7717e6bed73d7df8`, metadata `d5c0cc77895b7b46d4dd908cc12b173a56bbf3b0d27526536232896ad3dbe1b4`, split `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d`, scaler `b9a6a566d4f64d8bf8a2e35a7e2ae086f6a506f6c691c972a851c6914fb34fb1`. 세 config의 `source_hashes`도 동일하다. 허용된 파일의 SHA-256을 독립 재계산한 결과 현재 `native_train.py=48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7`, `native_models.py=7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632`, `eadro_corrected_model.py=1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b`, `CALIBRATION_PROTOCOL.md=862aaa8ab59c0fc2b37e37b5c89c26065fa3e12c31ce36504350f6fddfc7643b`, SN metadata 및 raw archive가 config/common manifest의 hash와 각각 일치했다. raw archive는 hash만 계산했고 열거나 역직렬화하지 않았다.

기존 `sn200_verification.json`은 `status=PASS`, `runs_checked=6`, `failures=[]`이며 각 run의 checkpoint replay·산출물 hash 및 validation prediction index 점검을 기록한다. 200-epoch 결과가 50-epoch 설정/산출물과 맞고 첫 50 epoch history가 일치한다는 기존 검증도 재사용했다. 이는 **기존 기록의 근거**이며 verifier를 실행하거나 import하지 않았다. 본 감사는 정적 source/manifest 대조이며, numeric prediction 재채점이나 raw feature/scaler 재계산은 하지 않았다.

## 한계와 결론

접근 기록 정정: 위 “raw archive는 hash만 계산했고 열거나 역직렬화하지 않았다”에서
“열지 않았다”는 잘못된 표현이다. 해시 계산은 파일을 바이트로 읽는 작업이며,
수행하지 않은 것은 NPZ 배열 역직렬화와 관측값 분석이다. 이후의 범위 설명은
이 구분을 따른다.

- 이 window split은 같은 injection을 partition 간 공유하므로 독립 incident 일반화를 입증하지 않는다. 이는 raw window/index/time 중복과 다른 제한이다.
- raw/inputs 배열 및 test 관측·예측은 역직렬화하거나 분석하지 않았다. raw archive의 hash는 파일 바이트를 읽어 계산했으므로 “파일을 전혀 열지 않았다”는 뜻은 아니다. 메타데이터와 split JSON만으로는 동일한 원시 metric/log/trace 레코드가 여러 partition에 들어갔는지 판정할 수 없으므로 그 수준의 중복은 **unknown**이다. 값이 우연히 같거나 서로 상관된다는 사실만으로 관측 누출을 판정하지 않는다. 기존 span 요약이나 전체 로드 사실만으로 raw overlap을 단정하지 않는다.
- 결론은 “요청 범위의 target→feature 누출 결함을 찾지 못함”이지 실험 전체 정당성 또는 논문 재현 판정이 아니다. 검증 JSON의 PASS는 artifact/기록 검증이지 파이프라인 모든 가정의 독립 증명이 아니다.
