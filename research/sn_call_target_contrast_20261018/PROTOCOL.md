# SN 호출 대상 귀속 단일 대조 — 실행 전 고정

2026-10-18. 사용자가 승인한 후보 한 가지의 개발 대조다.

## 질문과 선택한 변경

호출 지연을 기록한 서비스와 호출 대상을 구분해 **호출 대상에 귀속**하면,
같은 학습 예산에서 SN 네트워크 지연 장애의 원인 진단이 개선되는가?

원시 index112에서 compose의 `compose_media_client`가 media의
`compose_media_server`를 직접 CHILD_OF로 연결한다. client duration은
5.990747초, server duration은12μs다. index115의 client duration6.008163초는
호출자 관측 경과시간이며 media 내부 처리시간이라고 부르지 않는다.
`attribution_cases.json`에 실제 ID·reference·시각을 보존했다.

공개 고정 parser와 로컬 구현은 모두 span의 process.serviceName에 집계한다.
논문에는 callee별 평균이 서술돼 있지만 실제 target 해석 방법까지 확정하지
못했다. 따라서 **로컬만의 코딩 오류 수정이나 저자 전체 구현 복원이라고
주장하지 않는다**. 현재 대조는 근거 있는 호출 대상 귀속 변형이다.

유일한 처리 변경:

```
destination(span) = frozen_map[(owner_service, exact_operation)]
                    if this key has admissible TRAIN linkage
                    else owner_service
```

각 기존 span occurrence는 정확히 한 번만 집계한다. caller/server occurrence를
추가·삭제·합치거나 deduplicate하지 않는다. 해당 서비스의 같은1초 bin에서
duration의 산술평균을 사용한다. 귀속에 따라 숫자·분모·빈 bin 위치는 변하지만
평균 estimator와 zero-fill 규칙은 바꾸지 않는다.

새 채널을 활성화하거나 caller/target 두 값을 추가하는 대안은 채택하지 않는다.
trace shape `(394,12,10,2)`, channel1=0을 유지한다.

## 대상 사전: TRAIN에서만 도출하고 먼저 동결

- 기존 SN seed42 TRAIN316의 원본 인덱스만 사용한다.
- 같은 trace의 정확한 `(traceID,spanID)` CHILD_OF 연결에서 parent와 child의
  시작 bin이 **둘 다 TRAIN**인 경우만 도출 근거로 사용한다.
- parent operation이 `_client`로 끝나고, child의 process.serviceName이
  parent와 다른 기존12서비스일 때만 candidate key를 수집한다.
  suffix나 service adjacency, 장애 정답만으로 target을 추측하지 않는다.
- 키는 `(owner_service, exact_operation)`이며 실제 child service가 target이다.
  같은 키에 복수 target이 확인되면 준비를 중단한다. 임의 다수결·첫값 선택 금지.
- 근거 ID는 중복 제거해 증거 수를 세되, 실제 feature의 occurrence 가중은 보존한다.
- validation의 확인된 index112/115 사례는 가설의 근거일 뿐 사전 구축이나
  모호성 해소에 사용하지 않는다. validation/test child로 TRAIN 연결을 완성하지 않는다.
- TRAIN 근거로 `compose-post-service / compose_media_client → media-service`가
  확인되지 않으면 이 후보의 실행을 중단한다.
- `mapping.json`을 기록·hash 동결한 뒤에만 validation의 duration/operation을
  사용해 새 입력을 만든다. unknown key는 owner fallback, 대상 추정 추가 금지.
- TRAIN/validation별 mapped/unmapped client 및 전체 occurrence 수,
  키별 지원량과 원래 owner→destination 이동량을 공개한다.

## 입력·보호 경계

- 허용 입력은 기존 native SN TRAIN316+validation78=394창이다.
  test169+unassigned1은 모델 관측값으로 열지 않는다.
- `sn_hawkes_horizon_contrast_20261017/inputs/selected.npz`의 검증된
  metrics/logs/labels/indices를 그대로 재사용한다. Hawkes relative horizon10 유지,
  새 Drain/Hawkes 적합 없음.
- 원시 SN 네 recording의 spans만 필요한 범위에서 시각 라우팅한다.
  공유 JSON 전체의 바이트·구조 파싱 및 timestamp 라우팅을 숨기지 않는다.
  TRAIN 사전 단계는 TRAIN 관측만, 입력 단계는 허용394창만 수치 처리한다.
- source의 기존 hash를 대조한다. 같은 라우팅에서 재생성한 기존 owner trace가
  허용 cache trace와 **원소별 정확히 같아야** 한다. 불일치하면 학습하지 않는다.
- 새 trace만 교체하고 metrics/logs/labels/indices는 원소별 정확히 보존한다.
  원본 및 기존 실험 산출물을 수정하지 않는다.
- 정규화는 기존 `fit_scaler`를 같은 TRAIN 순서에 적용한다. metric 통계는
  기존과 정확히 같아야 한다. trace 계수는 새 TRAIN 입력에서 재계산되지만
  mean/std·epsilon1e-8·no clipping이라는 규칙은 변경하지 않는다.

## 학습과 선택

- DiagMLP 기존 수식 복원본,12서비스/7로그이벤트,75,810파라미터.
  encoders·fusion·heads·dropout0.1·jointloss alpha0.5·정적 metadata 모두 유지한다.
- seed11/23/37, 기존 random/NumPy/Torch 초기화와 shuffle,
  Adam lr0.001/betas(.9,.999)/eps1e-8/weight_decay0, batch256.
- 각 seed200epoch, epoch당2update, 총400update. 연장·튜닝·다른 후보 없음.
- 최대3개 프로세스 병렬, CPU2threads/process, 기존 `.venv-eadro` runtime.
- validation joint loss strict minimum, 동일값이면 이른 epoch.
- 첫50 범위의 선택 checkpoint·validation logits를 별도 보존한다.
  이어서 동일 학습 경로를200까지 진행하고 전체 범위 선택본도 보존한다.
  50에서 재시작하거나 입력·optimizer를 바꾸지 않는다.
- 기존 SN50/SN200 6개 실행은 `BASELINE.json`42개 hash로 고정해 재사용한다.
  baseline 선택 모델을 다시 학습하지 않는다.
- 시작 전 모델/optimizer/runtime/source/분할·정규화 경계와 최소 fixture 검사를 통과한다.
  각 후보50/200 선택 checkpoint의 저장 예측은 재추론으로 정확 대조한다.
  실패·부분 실행은 보존하며 기존 디렉터리를 삭제하거나 덮어쓰지 않는다.

## 평가: 두 예산 모두 보고

- 주 관심 지표: 각 budget에서 네트워크 지연 조건부 root Top-1의3seed 평균 차이.
- 반드시 함께: 전체 및 CPU/지연/손실 Top-1/Top-3, fault NLL,
  detection/gated 보조 지표와 실제 선택 epoch/update.
- 정상13창은 root 분모에서 제외. validation 장애65창/28고유사건,
  seed별65회이며195개 독립 사건이 아니다.
- 같은 seed·original index로 새 정답·새 오답·지속 오답·동시 정답을 전수 대응.
  고유 창·전역 event_id·recording을 별도로 센다. category 간 고유 수는
  다른 seed에서 중복될 수 있으므로 합산하지 않는다.
- 각 사건의 window-hit 평균을3seed 평균한 기술적 요약을 함께 제시한다.
  원래 창 점수를 사건 pooling 순위로 바꾸거나 baseline 점수를 대체하지 않는다.
- 여러 event_id에 이득이 생겨도 동일 recording 및 TRAIN/validation 사건 공유가
  있으므로 독립 사건 일반화로 부풀리지 않는다.
- 방향이 seed·종류별로 엇갈리거나200에서 악화되면 그대로 보고한다.
  50 개선/200 동률이면 초기 학습 개선과 최종 동률을 분리한다.
  사후 threshold·seed 제외·추가 fit으로 효과를 만들지 않는다.

## 비용·판정 및 종료

- 사전 도출, trace 재집계, 전체 입력 준비의 실제 wall time을 기록한다.
- 각 seed의 첫50까지/200까지 학습+validation wall time과 별도 replay 시간을 기록한다.
  병렬 전체 경과시간과 프로세스 시간 합을 구분한다.
- 기존 baseline의 기록된 시간을 함께 제공하되 실행 시기·부하·기록비용이
  다른 비동시 비교라는 한계를 명시한다. 정확도 개선만으로 처리 효율을 주장하지 않는다.
- 효과가 없으면 이 고정 조건에서 후보를 지지하지 않는 근거로 종료한다.
  효과가 있어도 호출 지연 정보 활용 자체는 Eadro/MicroHECL 선행 개념이다.
  새로운 방법의 novelty나 보편적 인과 개선을 주장하지 않는다.
- TT 성능 유지·다른 사건 검증·RE2 확장은 이번 범위 밖이며 자동 실행하지 않는다.
