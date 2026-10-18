# 공유 분석기와 호출 방향 문맥 — 개발 스모크 계약

## 사용자 범위와 연구 질문

사용자는 원인 진단 정확도 중심의 연구 구체화와 스모크 테스트,
논문 형태의 한국어 보고서를 요청했다. 선택적 진단 제안은 이번 주제가 아니다.
기존 모델과 실험을 변경하지 않고 이 폴더에만 새 결과를 저장한다.

질문: 같은 서비스별 관측에서 **전체 서비스 평균 문맥 대신 실제 호출 방향별 문맥**을
사용하는 공유 점수기를 구성하고, 사건 비중첩 개발 평가를 끝까지 실행할 수 있는가?
정확도 개선은 후속 검증 가설이며, 이번 짧은 실행의 완료 조건이 아니다.
공유 점수기·방향성·graph aggregation 자체의 신규성이나 인과적 원인 식별을 주장하지 않는다.

## DAG와 영향 범위

`기존 코드·자료 계약 확인 → 사건 분할/관측 준비`와
`모델·단위검사 구현`을 독립 진행한 뒤,
`입력/누출 검사 → 제한된 학습·재실행 → 논문형 보고`로 합류한다.
동결 native 및 기존 method_mlp 코드는 읽기 전용 재사용한다.
원 논문 test/unassigned 창은 새 산출물에서 제외하고 RCAEval 자료에는 접근하지 않는다.
재사용 함수와 입력·새 코드의 SHA256을 결과에 기록한다.

## 데이터 계약

- SN/TT의 기존 seed42 TRAIN+validation 창만 사용한다.
- 기존 `features.load_selected`의 build/raw/metadata/prepared/split 해시 검사를 재사용한다.
- NPZ 구조상 전체 member가 해제된 뒤 허용 행만 남는다. test 값의 통계·학습·출력은 하지 않는다.
- 원 메트릭7채널과 허용 창의 trace 평균 지연·retained span count2채널을 사용한다.
- 기존 `x`를 재분할하지 않는다. 새 fold의 정상 TRAIN에서 median/IQR을 다시 적합한다.
- 기존 중복 레코드의 latency/count 가중치는 보존하되, 관계는 고유 span ID로 중복 제거한다.
  retained count를 독립 요청 수라고 부르지 않는다.

사건 분할은 `../resource_study_20261013/DATA_CONTRACT.md`의 규칙을 사용한다.
서비스를 `SHA256("20261013:"+service_name)` 순으로 정렬하고 고장3종은 사전식 정렬한다.
순서j,k의 validation fold는 `(j+k)%3`; 이번 실행은 **fold0만** 사용한다.
정상 창은 같은 recording에서 가장 가까운 고장 구간에 귀속하며 동점이면 앞 사건이다.
정상 창과 고장 창의 episode가 같은 분할을 따른다.
같은 recording의 다른 사건이 양쪽에 남을 수 있으며 기존 사용 사건이므로 개발 평가다.

### 관계 생성

- 원 Jaeger의 `CHILD_OF`만 사용하고 parent service→child service를 방향으로 둔다.
- **부모와 자식 시작점이 모두 같은 허용10초 창에 있을 때만** cross-service edge를 만든다.
- 원 metadata의 전역 `edges`는 사용하지 않는다.
- ref가 다른 trace를 가리키거나 parent가 없거나 창이 다르면 연결하지 않고 수량을 기록한다.
- 자기 연결은 제외, 중복 edge는 boolean으로 합친다.
- 동일 span ID의 service/time/duration/reference 충돌은 오류로 남긴다.
- 실제 호출 관계나 인과 그래프의 완전성은 보장하지 않는다.
- 기존 지연 특징은 span 시작점으로 창에 배정하고 전체 duration을 사용한다.
  창 끝 이후 종료된 span 수를 기록하며,10초 종료 즉시 이용 가능한 online 입력이라고 주장하지 않는다.
- self-time, p95/p99, 오류율을 이번에 추가하지 않는다. 기존 시간/coverage 문제를 숨기지 않는다.

## 모델 계약

3개 내부 대조군을 같은 구조로 만든다. 이번에 문헌 경쟁자를 대체하는 것은 아니다.

1. `local`: 자기 서비스 정보만 사용.
2. `global`: 관측된 전체 서비스의 공유 표현 평균을 문맥으로 사용.
3. `directed`: 관측된 caller/callee 이웃의 공유 표현 평균을 각각 사용.

18차원 특징x, mask, coverage를 이어 붙인54차원을
공유 `Linear(54,32)→ReLU` 분석기로 변환한다.
문맥은 `mask.any(feature)`가 참인 이웃만 포함하며 없는 문맥은0과 별도 표시로 표현한다.
`[자기표현32, caller문맥32, callee문맥32, 두 문맥 존재표시]`98차원을
공유 `Linear(98,16)→ReLU→Linear(16,1)`로 점수화한다.
global은 두 문맥 칸에 같은 전체 평균, local은 두 칸과 문맥 표시를0으로 둔다.
서비스 이름·위치 embedding·고장 유형·정답은 모델 입력에 넣지 않는다.
방향별 평균 집계를 쓰는 한 단계 message-passing 모델이며 “새로운 비그래프 모델”이라고 하지 않는다.

설계상 각3,361파라미터이며 실행으로 확인한다.
같은 총 파라미터 수라도 local의0칸이나 global의 중복 문맥 때문에 유효 용량이 같다는 주장은 하지 않는다.
현재 기존3,457파라미터 relative MLP와 같은 모델도 아니다.

## 고정 스모크 설정

- 두 시스템×3모드, fold0, seed11, 각5epochs만 실행한다.
- 새 특징은 TRAIN 유효값으로만 추가 표준화하고 모든 모드에 동일하게 제공한다.
- Adam lr1e-3, weight_decay1e-4, batch32, CPU2스레드, GPU 없음.
- 사건별 역빈도 가중 CE,5epoch 중 validation 사건 균등 CE가 가장 작은 checkpoint를 저장한다.
- 초기 가중치와 batch 순서는 모드 간 동일하다.
- feature/분할/epoch/seed를 결과에 맞춰 바꾸지 않는다.
- 저장 checkpoint 재추론 일치, 독립 채점, 사건별 Top1/Top3/MRR을 확인한다.
- 동점은 가능한 순위에서 균등 credit으로 계산한다. 창 수나 seed를 독립 사건 수로 부풀리지 않는다.
- 학습 시간은 실행 기록이며 공정한 end-to-end 비용 우위 측정으로 사용하지 않는다.

## 필요한 검사

- 정상 참조·표준화 TRAIN 전용, validation 값 변경에 TRAIN 통계 불변.
- train/validation 사건·episode 교집합 없음, 원래 test/unassigned 인덱스 비포함.
- 모든 원인 서비스와 고장3종의 분할 지원 확인; label/원본 인덱스 보존.
- graph 방향·같은 창 조건·중복·미해결 parent 처리.
- 순열에 따른 점수 대응, local/global의graph비의존, 빈 graph의local fallback.
- 결측 placeholder 불변, finite loss/gradient, checkpoint replay 일치.
- 새 결과 재로딩·해시 일치와 읽기 전용 재사용 파일의 미변경 확인.

## 판정과 복구

통과는 **원형과 검증 경로가 실행됐다**는 뜻이다.
한fold·한seed·5epoch로 개선·수렴·일반화·신규성을 판정하지 않는다.
문헌 방법의 동일 사건 재실행, 여러seed/fold, 요소 제거, 최종평가는 미실행으로 남긴다.
오류가 나면 원인을 고치고 영향을 받는 검사만 다시 실행하며 실패 기록을 보존한다.
이미 완료된 결과는 덮어쓰지 않고, 불완전 산출물도 정상 완료로 취급하지 않는다.
