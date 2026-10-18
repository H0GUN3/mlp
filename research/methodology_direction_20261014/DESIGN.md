# 좁은 설계 후보: trace 관측 지원 정보를 보존하는 입력 모듈

상태: **문헌 대조 후 축소한 검증 전 설계 후보**.
새 모델을 구현하거나 효과를 확인한 문서가 아니다.
초안의 occupied-second 항은 기존 latency에서 유도될 수 있어 제외했다.
관측 개수 하나를 보존하는 변경만 우선 검증하고, 근거가 없으면 기각한다.

## 1. 과제와 구체적 질문

상위 과제는 마이크로서비스 장애의 원인 서비스 순위 개선이다.
네트워크 장애에 분야를 한정하거나 AIOps 전체 시스템을 만들지 않는다.

후보 질문:

> 같은 평균 지연이라도 관측된 span의 개수가 다른데,
> 이 차이를 명시적으로 보존하면 기존 다중 자료 MLP의 원인 순위가 개선되는가?

다중 자료 결합 자체, GLU/gating, MLP 사용, 그래프 제거는 이미 있는 방법이다.
이 설계는 그 자체를 새 기여로 주장하지 않는다.

## 2. 근거의 수준

- DiagMLP §III-C는 기존 metric/log/trace embedding을 받아 모달·노드 fusion을 한다.
  즉 원자료를 어떻게 요약했는지가 중요하다.
- 고정 공개 repair fork `7d69281...`의 `single_process.py::deal_traces`는
  service/second별 평균 latency와 `invok` count를 모두 계산한다.
  그러나 `align.py::get_chunks`는 latency만 모델 입력에 전달한다.
  채널 1은 0이며 채널 0은 표준화된다. 따라서 모델 입력의 0을 그대로
  미관측이라고 해석하면 안 된다.
  count 미전달은 **확인한 공개 경로의 사실**이지 임의의 DiagMLP backbone 전체의
  결함도, 이미 입증한 정확도 손실도 아니다.
- DeepHunt §4.2.1은 이미 request count를 사용한다. 관측 개수의 도입 자체는
  새 원리가 아니다. 정확한 unique-span 집계와 시간 해상도 차이가 있다고 해서
  곧바로 신규성이 생기지도 않는다.
- 합성 확인: 10초 동안 초당 10ms span이 각각 1개 또는 10개 있는 두 입력은
  같은 10개 평균 latency 값이 된다. 고유 span 수는 10 대 100이다.
  실제 데이터·모델 없이 이 일치를 assert로 확인했다.
- 로컬 개발 자료에서 trace 희소성을 확인했지만, 그 결과는 원 DiagMLP의 실패를
  입증하지 않는다. **먼저 적절히 학습한 원형에 가까운 기준 모델의 오류를 확인해야 한다.**

## 3. 모듈의 입·출력

기존 metric/log/trace 인코더, 서비스 위치 embedding, Node Fusion, root head는 유지한다.
주입 정답이나 원인 서비스 이름을 이용해 관측 지표를 만들지 않는다.

서비스 i, 고정 길이 T초의 관측 창에서:

- `u_i`: `(traceID, spanID)`로 중복 제거한 span 수.
- `q_i = log(1 + u_i)`.

초안의 `v_i = span이 기록된 초의 수 / T`는 제거했다.
duration이 양수인 조건에서는 표준화 전 zero-padded latency의 nonzero 비율로
유도되므로 독립된 새 정보라고 주장할 수 없고, 현재 질문을 불필요하게 늘린다.
그 요약을 별도 주는 효과는 다른 가설이며 이번 pilot에 섞지 않는다.

`q_i`는 수집기 신뢰도나 독립 표본 수가 아니라 **관측된 자료의 양 요약**이다.
트레이스가 0개라는 사실을 정상, 서비스 미호출, 수집 실패 중 하나로 단정하지 않는다.
유효한 0 duration과 미관측도 임의로 같은 의미로 부르지 않는다.
로그가 비어 있다는 이유만으로 로그 수집 실패 mask를 만들지 않는다.

DiagMLP의 기존 모달 결합 직전에 한 수를 추가한다:

```text
기존: [metric embedding | log embedding | trace embedding | position]
제안: [metric embedding | log embedding | trace embedding | position | q_i]
          ↓ 기존과 같은 단층 Modal Fusion MLP
          ↓ 기존과 같은 서비스 전체 결합 및 Node Fusion MLP
          ↓ 기존과 같은 root-service head
```

이것은 **입력 표현 보완 모듈**이다. 복잡한 graph/gate/attention을 새로 붙이지 않는다.
모달 fusion 출력 폭이 h라면 첫 Linear 가중치는 h개 늘어난다.
예를 들어 h=64일 때 64개이며, 64는 설명용 값이지 논문 고정 설정 주장이 아니다.
span 중복 제거·집계 시간과 메모리도 비용에 포함한다.
원 baseline의 latency 중복 weighting은 바꾸지 않는다. 고유 개수 계산은 q에만 적용한다.
중복 여부를 잃은 cache의 `invok`를 unique count로 재명명하지 않는다.
현재 raw 자료/접근 범위에서 identity가 없으면 이 계약을 실행할 수 없다고 명시한다.

## 4. 비교 설계: 무엇이 개선됐는지를 분리

우선 기준은 Eadro의 입력 인코더를 유지한 DiagMLP 방정식 기반 복원이다.
그것을 현재의 18개 수치 특징을 받는 자체 MLP와 혼동하지 않는다.

최소 paired pilot:

1. 기준: 원 입력 표현 + 기존 DiagMLP.
2. 제안: 동일 원자료·사건·분할·인코더·학습 기회에서 q_i만 보완.

추가 정보가 생긴 것이므로 이 비교를 “동일 정보에서 더 좋은 모델”이라고 부르지 않는다.
비교 질문은 **같은 원자료에서 버리던 관측 정보를 보존한 효과**다.

효과가 있어 다음 단계로 넘어갈 때만:

- 같은 h 가중치를 추가하되 q_i=0으로 고정한 용량 대조.
- Eadro 등 문헌 비교군에도 q_i를 제공하는 대조로 정보 효과와 모델 종류 효과 분리.
- 필요하면 서비스별 관측량 분포는 유지하고 시간 대응만 깨뜨리는 대조로
  서비스/recording의 고정 패턴 이용과 사건별 관측 상태 이용을 구분.
  이는 사전 고정한 추가 진단이지 결과를 보고 유리한 대조를 선택하는 것이 아니다.

## 5. 데이터·학습 조건

- 원형에 가까운 baseline이 실제로 해당 조건에서 실패하는지 먼저 확인한다.
  기존 5epoch 자체 모델 결과를 그 증거로 쓰지 않는다.
- 주입 사건을 분할 단위로 유지하고 모든 파생 특징·scaler·template 선택은 TRAIN에서만.
- root 후보와 task head, 입력 시간 범위, detector/onset 제공 조건은 동일하게 유지한다.
- 동일 epoch만을 공정한 학습 기회로 간주하지 않는다.
  허용 계산/탐색 예산, checkpoint 기준, seed, 학습 정지 규칙을 사전에 기록한다.
- 현 개발 사건/recording은 이미 반복 사용했다. 여기서의 개선은 개발 근거이며
  새 사건·새 환경 일반화나 최종 평가 결과가 아니다.
- 관측량 subgroup은 정답 root를 써서 사후 해석할 수 있지만 실제 모델 입력·분기는
  정답 없이 모든 서비스에 같은 규칙으로 계산해야 한다.

## 6. 평가와 기각 기준

주 평가: 사건 균등 Top1. 보조: Top3/MRR, 고장 유형별 결과, trace 관측량별 결과,
전처리+추론 시간, peak memory, seed별 paired 차이.
자료가 비어 있는 창에서 얻은 이득과 충분히 관측된 창에서의 손해를 모두 보고한다.
사건 내부 상관과 공유 recording을 무시해 창 수를 독립 표본 수로 부풀리지 않는다.

다음이면 주장을 중단/축소한다:

- 원형 baseline에서 관측 지원과 관련된 의미 있는 오류를 확인하지 못함.
- q_i가 다른 보존 특징과 중복이고 추가 성능/비용 가치가 없음.
- 개선이 없거나 CPU 등 다른 조건의 악화/추가 비용이 이득을 상쇄함.
- 용량 대조와 구분되지 않거나 고정 서비스·recording 패턴으로만 설명됨.
- 관측량으로 설명할 수 없는 누락 정보가 핵심인 경우.
  없는 trace 내용을 q_i가 복구한다고 주장하지 않는다.

최소 실용 개선 폭과 허용 비용은 실행 전에 수치로 고정해야 한다.
그 값을 아직 측정 결과처럼 만들어 쓰지 않는다.
기본 판단은 paired 효과의 크기·불확실성·퇴행·비용을 함께 보는 것이다.

## 7. 이 후보가 아닌 것

- “로그를 추가하면 해결”이라는 앞선 한 사례의 일반화가 아니다.
  Eadro 계열 baseline은 이미 로그를 쓰므로 그 단서가 원래 입력에 없는지도 다시 확인한다.
- “GNN은 필요 없다”, “서비스 ID를 쓰면 잘못이다”, “통계 방법보다 무조건 좋다”가 아니다.
- 관측 수를 추가하는 것만으로 논문 기여가 충분하다는 주장도 아니다.
  유사 방법과의 중복 조사 및 실제 실패→기제→정량 효과 연결이 남아 있다.
- “기존 연구는 개수를 모두 버린다”는 주장도 아니다.
  DeepHunt는 count를 사용한다. Eadro-compatible 경로의 표현 개선 실험과
  일반적인 방법론 신규성은 분리한다.

## 출처

- [DiagMLP §III-C/D](https://arxiv.org/html/2501.02766v2#S3.SS3)
- [Eadro §IV](https://arxiv.org/html/2302.05092#S4)
- [고정 fork: count와 latency 집계](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py)
- [고정 fork: latency만 chunk에 전달](https://github.com/FeiGSSS/Eadro/blob/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/align.py)
- [DeepHunt §4.2.1: 기존 request count](https://nkcs.iops.ai/wp-content/uploads/2025/07/deephunt.pdf)
- [방법론·중복 대조](METHODS.md)
- [로컬 native input 보존/수정 계약](../native_reproduction_20261013/CALIBRATION_PROTOCOL.md)
- [로컬 trace_series](../native_reproduction_20261013/native_data.py)
- [현재 자체 모델의 실패 진단](../failure_causes_20261014/REPORT.md)
- [제한된 원자료 추적](../tt_trace_origin_20261014/REPORT.md)
