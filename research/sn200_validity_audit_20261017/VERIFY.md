# SN200 감사 보고서 교차 검증

## 최종 판정

**감사 coverage: PASS — 부모의 최종 문서 정정 포함.** 독립 검증에서 네 축의 기술적 검사·근거는 확인했고, 접근 기록 문구 불일치 1건 때문에 당시에는 FAIL이었다. 부모가 BOUNDARY의 해당 문구를 “경계 계산은 metadata만 사용, 전체 감사의 다른 단계에서는 raw.npz 바이트 해시 확인, 배열 decode·분석 없음”으로 정정하고 PREPROCESSING에도 같은 접근 정정을 명시했다. 기존 수치·실험 코드·판정 근거는 변경하지 않았다. 이 마지막 문구 대조는 부모 확인이며 별도 독립 재실행으로 주장하지 않는다. PASS는 감사 범위의 증거·보고 일치이며, 실험 전체 무결성이나 incident 일반화 증명이 아니다.

| 축 | 감사 coverage | 결론 강도 및 근거 |
|---|---|---|
| 경계·중복 (`BOUNDARY.md`) | **PASS** | index/partition 교집합 0, 창 identity 중복 0/564, train-validation 구간 겹침 0쌍은 메타데이터 기반 `notfoundwithinscope`. 반면 event 28개와 recording 4/4를 공유하므로 incident/recording 독립 평가는 `limitedevaluation`. raw record identity의 분할 간 중복은 `unknown`. 창 중복과 사건 공유를 구분했다. |
| 전처리·정보 흐름 (`PREPROCESSING.md`) | **PASS** | `native_train.py:47–58`은 split 전 `raw.npz`의 네 배열(라벨 포함)을 메모리에 읽는다. 별개로 `:158–188, 231–238`은 scaler를 train partition으로 적합하고 train/validation만 만든다. test 전체 로드는 확인된 구현 사실이나 test가 fit/model 입력/평가에 쓰였다는 증거는 아니다. Drain은 별도 정상 reference, Hawkes는 각 창 로그를 쓰는 창 로컬 계산이다. 요청 범위의 label→feature 경로 결함은 `notfoundwithinscope`; held-out 창 관측 사용 및 shared-event 평가는 `limitedevaluation`. |
| checkpoint 선택·평가 (`SELECTION.md`) | **PASS** | `native_train.py:198–209, 286–311`은 eval/no-grad validation과 strict `<` 최소 loss 선택을 보인다. history의 6개 실행(epoch 50/200 × seed 11/23/37) 최소값과 summary `best_epoch`/loss가 모두 일치한다(세부 수치는 `SELECTION.md`). validation을 모델 선택에 사용한 것은 `limitedevaluation`; test 평가 호출은 없고 `test_evaluated:false`. 기록된 replay는 과거 bitwise 결과의 재사용이지 이번 감사의 fresh replay/inference가 아니다. |
| 라벨·점수 (`SCORING.md`) | **PASS** | 허용된 세 validation NPZ에서 split index 순서, 78행, logits `78×12`/`78×2`, 라벨 및 서비스 순서를 대조했다. 각 seed fault/normal은 65/13. conditional Top-1은 seed 11/23/37 각각 92.307692/98.461538/95.384615%; 평균 95.384615%. Detection F1은 96.923077/97.709924/100%. 오류 5+1+3=9, 분모 65×3=195이므로 `1−9/195=95.384615%`. 산출물 hash도 summary와 일치한다. 이는 기존 독립 validation 채점 결과의 재사용이며 ensemble 또는 test 점수가 아니다. |

경계 산술의 핵심 재현식(세 split JSON은 동일 SHA-256):

```python
parts = {k: set(split["indices"][k])
         for k in ("train", "validation", "test", "unassigned")}
sum(map(len, parts.values())), len(set.union(*parts.values()))
# (564, 564)
len(parts["train"] & parts["validation"])
# 0
len({(w["run_id"], w["start"], w["end"]) for w in metadata["windows"]})
# 564
```

경계 보고서의 전체 쌍별 교집합·half-open interval 계산 결과는 모두 0이다. 반면 공유 event 28개와 4/4 run은 partition 간 provenance 공유 수치이지 raw window 중복 수가 아니다. `metadata.json:span_audit.counts`의 전체 중복 occurrence 수만으로 train-validation raw identity 교차를 추론할 수 없다.

점수 계산은 scoring 보고서의 명시된 정의를 따른다: fault-only root credit는 정답 logit보다 큰 값이 없을 때 `1/tie_count`, detection은 `argmax==1`, gated 점수는 fault-only credit에 detection 결과를 곱한 평균, F1은 TP/FP/FN으로 계산. 세 seed 점수의 평균이지 logits를 합친 ensemble이 아니다. 따라서 95.38% 산술만으로 타당성을 주장하지 않으며, validation 배열의 index·label·열 대응 및 독립 채점 근거와 함께 제한적으로 확인한다. `23.59 vs 95.38` 차이의 원인은 이 감사에서 입증되지 않았다.

## 분류

- **confirmeddefect:** 초기 감사 문서의 사실 오류 2건이 확인되어 정정됐다: SELECTION의 “BatchNorm 없음” 주장은 원본 `research/mlp_prerequisites/eadro_corrected_model.py:46–60`의 `nn.BatchNorm1d` 및 `native_models.py:35–37`의 원본 metric/trace encoder 보존과 모순이었다. `SELECTION.md`가 이를 바로잡았다. 기존 protocol SHA-256 표기에서 빠진 `b`도 교정됐다. 이는 감사 문서 결함이며, producer/model 결함으로 확대하지 않는다.
- **limitedevaluation:** train/validation이 같은 28 event와 4 recording을 공유; validation loss가 checkpoint 선택에 사용됨; 역사적 loader가 split 전에 test 포함 전체 raw arrays를 메모리에 읽음; Hawkes validation feature는 그 window의 로그 관측으로 계산됨. 어느 항목도 그 자체로 성능 오염 또는 누출을 증명하지 않는다.
- **notfoundwithinscope:** 보고된 인덱스·창·시간 중복, 요청 범위의 target→feature 경로, checkpoint 최소손실/동률 선택, validation label·출력 열 대응에서 결함을 찾지 못했다. “문제 없음”은 해당 검사 범위로 한정한다.
- **unknown:** raw metric/log/trace record identity의 train-validation 교차 중복과 원본 paper split manifest와 DiagMLP split의 정확한 대응은 확인 불가. raw 값의 우연한 동등성만으로 identity 누출이라 할 수 없다. test 성능 및 신규 incident 일반화도 평가하지 않았다.

## 상충·정정 소유자

| 기존 상충/주의점 | 원본 대조 및 현 상태 | 정정 담당 |
|---|---|---|
| SELECTION의 protocol hash에 `b` 누락 | 현재 문서의 `862aaa8ab59c0fc2b37e37b5c89c26065fa3e12c31ce36504350f6fddfc7643b`가 원본 protocol의 SHA-256과 일치 | SELECTION 작성자 |
| SELECTION의 no-BatchNorm 주장 | 원본 `ConvNet`은 `BatchNorm1d`; native wrapper가 metric/trace encoder를 유지. 현재 SELECTION은 정정 | SELECTION 작성자 |
| BOUNDARY의 interval 표기 | inclusive sample end `start+9`와 half-open interval `[start,start+10)`를 구별하도록 수정 | BOUNDARY 작성자 |
| BOUNDARY의 raw 파일 접근 문구 | 초기 문서의 전체 감사 접근 부정은 부정확했다. 부모가 경계 계산의 metadata 접근과 전체 감사의 raw 바이트 해시 접근을 분리해 정정했다. 배열 decode·분석은 하지 않음 | 부모 최종 문서 정정 |
| PREPROCESSING의 raw hash/동일값 해석 | byte hashing은 파일 바이트 읽기이지 NPZ decode가 아님; 값이 같다는 사실만으로 record leakage를 입증하지 않는다고 명시 | PREPROCESSING 작성자 |

현재 source hash 대조는 문서의 네 값과 일치했다: `native_train.py` `48cad93d937cc113d54ea865b87bf5e2e562bdf48efc845c3de6af21c89ddec7`, `native_models.py` `7d082ffff66ede01d00698fe762c1f7f5379a24d1cdb0fa1dc8f8e04ed0d1632`, `eadro_corrected_model.py` `1e6579d4656d0a040ef2cf3e3375a11e75cfd9b90cac2736bfb61998d8d12b0b`, protocol `862aaa8ab59c0fc2b37e37b5c89c26065fa3e12c31ce36504350f6fddfc7643b`. **남은 source hash 불일치는 없다.** `sn200_verification.json`의 `status=PASS`, `runs_checked=6`, `failures=[]` 및 첫 50 epoch 일치 결과는 기존 검증 기록이지 전체 파이프라인의 독립 정당성 증명이 아니다. 분류·수치 주장에는 추가 상충을 찾지 못했으나, 위 raw 접근 문구 상충 때문에 보고서 coverage는 FAIL이다.

## 접근·실행 범위

`BRIEF.md` 접근 경계를 따랐다. 이번 VERIFY 검토는 텍스트·코드·기존 요약만 읽었고 학습/추론/verifier를 실행하거나 import하지 않았으며 새 split도 만들지 않았다. 앞선 감사에서 허용된 세 `calibration200/SN/diagmlp/seed_{11,23,37}/validation_predictions.npz`만 `allow_pickle=False`로 decode해 채점했다는 `SCORING.md` 기록을 재사용했다. `raw.npz`는 기존 기록상 SHA-256을 위해 **바이트 읽기**만 했고 decode하지 않았다. `inputs.npz` 및 보호 관측·예측은 열지 않았다. 따라서 “raw 파일에 전혀 접근하지 않았다”고 주장하지 않는다. 보호된 SN169+1/TT1744+1/RE2는 닫힌 상태다.

별도 수치 재검사/추가 산출물은 필요하지 않다. 위 과거 FAIL의 접근 문구는 부모 정정으로 해소됐으며, 이전 절의 “미해결/coverage FAIL” 표현은 정정 전 이력이다. 결론은 저장 산출물과 명시된 source/metadata/validation 예측 범위의 감사이며, 새로운 모델 성능 결과가 아니다.
