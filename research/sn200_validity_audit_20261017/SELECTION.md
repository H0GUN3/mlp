# SN 체크포인트 선택·평가 실행 감사

## 판정

- **notfoundwithinscope** — checkpoint 선택은 전체 validation joint loss의 엄격한 최솟값이며, 동률이면 먼저 나온 epoch을 보존한다. 독립 계산한 선택 epoch/loss가 summary와 일치한다.
- **limitedevaluation** — 검증 loss로 checkpoint를 선택하므로 validation은 모델 선택에 사용된다. 소스는 test 평가를 수행하지 않으며 학습에는 train, loss/선택에는 validation을 전달한다. 다만 기존 replay 기록은 과거의 bitwise 재생성 근거이지 이번 감사에서 새로 수행한 inference가 아니다.
- 선택·평가 경로에서 **confirmeddefect**는 발견되지 않았다. 이는 실험 전체가 누출 없고 일반화 가능하다는 뜻이 아니다.

## 선택 규칙 및 독립 산술

`native_train.py:253` config는 `"strict minimum full-validation joint loss; earliest tie"`를 기록한다. `native_train.py:296-311`은 매 epoch validation prediction/loss를 계산하고 `if val_loss < best`일 때만 checkpoint와 validation prediction을 저장한다. 따라서 동률 시 앞선 checkpoint가 유지된다. `native_train.py:325-338` summary는 저장 checkpoint의 epoch/loss와 완료 epoch/update 수를 기록한다.

독립 재계산은 허용된 `history.json`만 사용했다. 재현식:

```python
best = min(history, key=lambda row: row["validation_joint_loss"])
(best["epoch"], best["validation_joint_loss"])
```

| 실행 | epochs / updates | history 최소 (epoch, validation_joint_loss) | summary `best_epoch`, `best_validation_joint_loss` | 일치 |
|---|---:|---:|---:|---|
| calibration50 seed 11 | 50 / 100 | 49, 0.31539633870124817 | 49, 0.31539633870124817 | 예 |
| calibration50 seed 23 | 50 / 100 | 48, 0.20128601789474487 | 48, 0.20128601789474487 | 예 |
| calibration50 seed 37 | 50 / 100 | 50, 0.22309668362140656 | 50, 0.22309668362140656 | 예 |
| calibration200 seed 11 | 200 / 400 | 192, 0.2565048038959503 | 192, 0.2565048038959503 | 예 |
| calibration200 seed 23 | 200 / 400 | 78, 0.12423702329397202 | 78, 0.12423702329397202 | 예 |
| calibration200 seed 37 | 200 / 400 | 200, 0.07957590371370316 | 200, 0.07957590371370316 | 예 |

경로는 `calibration{50,200}/SN/diagmlp/seed_{11,23,37}/{history,summary}.json`이다. `calibration_verification.py:102-121`의 기존 검증은 calibration200 각 실행의 설정·split/scaler 해시와 첫 50개 history 행(loss/score/update)을 calibration50과 비교한다. `sn200_verification.json`의 기존 결과는 `PASS`, 6/6 실행, 실패 없음이다. 이 verifier는 다시 실행하지 않았다. 첫 50개 history의 일치는 기존 증거로 인용하며 이번 감사에서 별도 재비교하지 않았다.

## 평가 모드·모델/산출물 연결

- `native_train.py:198-209`: validation 함수가 `model.eval()` 후 `torch.no_grad()` 안에서 logits/labels를 생성하고 joint loss를 계산한다. DiagMLP가 재사용하는 metric/trace 인코더의 `ConvNet`에는 `nn.BatchNorm1d(out_channels)`가 있다(`mlp_prerequisites/eadro_corrected_model.py:46–60,99–146`; `native_models.py:35–37,48–51`). fusion에는 LayerNorm이 있지만 전체 모델에 BatchNorm이 없는 것은 아니다. 기본 running-statistics BatchNorm과 Dropout에 eval 모드가 재귀 적용되므로 해당 validation 경로에서 BatchNorm 통계를 갱신하지 않고 Dropout도 비활성화된다. 새 모델 실행으로 검사한 것이 아니라 소스 경로 대조다.
- `native_train.py:231-238`, `286-295`: scaler는 `parts["train"]`에 fit하고, 학습용 `train`과 validation용 `validation` partition을 별도로 만든다. 학습 loop에는 `train`이, epoch 선택 loss에는 `validation`이 전달된다. checkpoint 선택은 test가 아니다.
- `native_train.py:306-311`, `315-323`: 개선된 validation loss에서 checkpoint와 validation predictions를 저장하고, 학습 종료 후 checkpoint를 다시 로드해 validation logits/labels/indices/loss를 저장 prediction과 비교한다. 과거 실행의 replay 성공은 각 summary의 `checkpoint_replay` 문자열과 기존 `sn200_verification.json`의 `"checkpoint replay evidence": passed`에 기록되어 있다. 이는 **역사적 replay 결과**이며 감사 중 새 로드·forward를 하지 않았다.
- `native_train.py:254`, `330`: `test_evaluated: false` 표시는 소스의 실행 경로와 함께 확인했다. 선택/학습 코드의 `run_training`은 test prediction/evaluation 호출을 포함하지 않는다. 다만 `load_inputs`가 입력 파일 전체를 읽는 별도 사실만으로 test가 학습에 쓰였거나 test 평가가 수행됐다고 결론 내리지 않는다.
- calibration50/200의 요청된 6개 diagmlp config 모두 같은 `source_hashes`를 기록하며, config 기록과 현재 파일 바이트의 SHA-256이 일치했다: `native_train.py`=`48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7`, `native_models.py`=`7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632`, `eadro_corrected_model.py`=`1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b`, `CALIBRATION_PROTOCOL.md`=`862aaa8ab59c0fc2b37e37b5c89c26065fa3e12c31ce36504350f6fddfc7643b`. summary `artifact_hashes` 및 기존 verifier 결과는 checkpoint/config/history/split/scaler/validation prediction 해시 검증을 기록한다. checkpoint는 역직렬화하지 않았다. 초기 문서의 protocol hash에서 빠졌던 `b` 한 글자를 정정했다.
- seed별 결과는 개별 checkpoint 선택 결과다. 세 seed의 평균은 ensemble prediction이 아니며, 이 감사는 ensemble 추론을 확인하거나 주장하지 않는다.

## 범위와 한계

읽은 범위는 요청된 SN diagmlp seed 11/23/37의 calibration50/200 JSON, `native_train.py`, `native_models.py`, `calibration_verification.py` 텍스트, 기존 SN50/SN200 검증 JSON이다. raw/input arrays, 보호 test 관측·예측은 열지 않았고 verifier/native training을 실행하지 않았다. checkpoint 재생을 새로 수행하지 않았으며 validation NPZ도 독립 재채점하지 않았다. 과거 verifier 기록과 파일 hash를 재사용했다. 따라서 이 결과는 선택 및 평가 코드 경로의 제한된 감사이며 새 성능 측정이나 전체 파이프라인 정당성 증명이 아니다.
