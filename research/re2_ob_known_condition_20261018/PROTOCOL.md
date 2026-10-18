# RE2-OB 알려진 조건의 새 실행: DiagMLP 기준선·오류 분석

## 승인과 종료 범위

2026-10-18 사용자가 명시적으로 RE2-OB 개발72건의 기준선 실행과 오류 분석 재개를 승인했다.
보호 시험18건은 봉인한다. 표현 변경, 특징 추가, 요청 짝 교란, RE2-TT 확장,
Eadro-TT 재학습, 최종시험은 이번 단계에서 하지 않는다.
이번 실행은 미접촉 최종 성능이 아니라 다음 가설을 검토하는 **개발 실험**이다.

> 학습에서 본 서비스·장애 조합의 다른 실행에서도 DiagMLP가 비슷한 혼동을 보이는가?
> 그렇다면 실제 허용 관측에 그 혼동을 구분할 단서가 있는가?

모든 오답을 호출 관계 문제로 해석하지 않는다. 실패·단서가 확인되지 않으면
“후속 표현 대조를 진행할 근거를 얻지 못했다”로 보고하고 종료한다.
이를 연구 전체의 가능성 부정으로 확대하지 않는다.

## 1. 확정 분할

기존 `research/mlp_prerequisites/split.json`의 RE2-OB90행 메타데이터만 확인했다.
기존 train54+validation18은24개 `(root_cause_service, fault)` 조합×반복1/2/3이다.
기존 test18은 다른6개 조합×3회다. 기존 파일은 수정하지 않는다.

각 개발 조합의 문자열 키는 `root_cause_service + "|" + fault`.
검증 repetition은 다음의 결과 전에 고정한 규칙으로 정한다.

```
1 + int(SHA256("re2-ob-known-20261018|" + group_key), 16) % 3
```

각 조합에서 선택한 반복1건은 validation, 나머지2건은 TRAIN이다.
결과: **TRAIN48 / validation24 / protected18**.
검증 repetition1/2/3 선택 조합 수는12/9/3이다. 균형을 맞추려고 다시 seed를 찾지 않는다.
한 실행의 정상·장애 창과 로그는 같은 파트에 둔다. 조합별2/1, 사례 비중첩,
보호18건 미포함, 절대 관측 시간/파일 중복의 교차 파트 위험을 검사한다.
충돌이 있으면 자동 사례 삭제·분할 변경 대신 중단하고 보고한다.

검증의 모든 원인 서비스·장애 종류뿐 아니라 **서비스×장애 조합**이 TRAIN에 존재한다.
이는 사건의 독립 수집이나 수집 환경 변화까지 증명하는 것은 아니다.
보호18건은 미학습 조합 과제이며, 알려진 조합의 새 실행에 대한 최종시험이 아니다.

## 2. 입력·전처리 계약

### 승인된 역할별 제외 — 2026-10-18

사용자는 `frontend-check`를 초기화용 보조 구성요소로 분류해 독립 진단 서비스에서
제외하도록 명시적으로 승인했다. 이는 정답에 없거나 validation에만 나타나서
삭제하는 규칙이 아니라 **구성요소 역할에 근거한 서비스 식별 범위 정리**다.
분류 근거와 데이터 매핑의 확인 범위는 [UNKNOWN_NODE.md](UNKNOWN_NODE.md)에 보존한다.

- 정확히 `frontend-check`라는 이름의 독립 서비스 후보와 특징 노드만 제외한다.
- 실제 `frontend`, `frontendservice`, `frontend-external` 및 다른 서비스의
  로그·span·관측값을 삭제하거나 별칭 병합하지 않는다.
- 48/24 사건, 각 사건의 정상·장애 창, 보호18건 및 원본은 그대로 보존한다.
- 제외된 메트릭 셀/관측 창, 로그 행, trace 관측, 관련 간선의 수를 별도로 기록한다.
  다른 서비스 소유 span이 이 이름과 연결됐다는 이유로 함께 삭제하지 않는다.
- 고정 이름 규칙을 TRAIN/validation 양쪽에 동일 적용하고 최종 후보 목록을 저장한다.
- 후속 비교에서도 동일 규칙을 적용해야 한다. 이번 처리를 별도 개선 가설이나
  노벨티·성능 개선 실험으로 해석하지 않는다.

### 허용 재사용

`tt_re2_baselines_20261017/re2_stage1/`의 허용72건은 통계 적합 전의
사례별 관측 변환이다. metadata/input 해시·변환 규칙·모달 식별자를 확인한 뒤 재사용한다.
원래 partition 표시는 출처로만 보존하고 새 분할로 명시적으로 대체한다.
기존54/18의 템플릿·노드통계·Hawkes 캐시·정규화·모델 가중치를 새48/24에 재사용하지 않는다.
단순 중간 자료만 재사용하며, 기존 파일은 모두 읽기 전용이다.

### 새 TRAIN48에서 적합

- 노드 목록: TRAIN48 stage1의 관측 식별자 합집합에서 기존4proxy와
  사용자 승인 초기화 구성요소 `frontend-check`의 독립 노드만 제외.
  정답5서비스만 후보로 축소하지 않는다. 미확인 별칭 병합을 하지 않는다.
  이 고정 제외 규칙에 해당하지 않는 validation 미등록 노드는 계속 중단·보고한다.
- 정적 간선: TRAIN 관측 호출 간선 합집합+self-loop. DiagMLP의 입력 API 유지용이다.
  이 노드가 그래프를 전달받는다고 새 GNN을 제안하는 것이 아니다.
- 메트릭: 기존8계열
  `cpu,diskio,error,latency-50,latency-90,mem,socket,workload`.
- 트레이스: 초별 평균 지연과 기존 두 번째0채널. 새 count/상태 특징을 추가하지 않는다.
- 로그: 기존 Drain 설정, TRAIN48의 주입 전 로그만으로 템플릿을 적합하고 동결.
  validation 템플릿 학습 금지. 미지 템플릿 bin을 별도 유지한다.
- Hawkes: 상대 window timestamp, 종료10초, decay3, 기존 fit_hawkes 및
  iteration50/initialbaseline0.2/solver seed42 규약과 빈 템플릿 처리를 유지한다.
  새 템플릿에 대한 매칭/특징을 계산한다. 동일 상대입력의 캐시는 이 새 실행 안에서만 허용.
  경고·iteration 상한·처리 비용을 숨기지 않는다.
- 메트릭 결측: TRAIN의 관측값 평균으로 대체. TRAIN에서 미지원인 node/channel은0,
  결측 및 가려진 validation 관측 수를 별도로 기록한다.
- 메트릭/trace 정규화: TRAIN 정상+장애 전체 창만으로 기존 평균/표준편차
  및 epsilon1e-8 규약, clipping 없음. 로그는 기존 경로 그대로.
  검증자료 값 변경에 TRAIN 통계·템플릿이 변하지 않는지 검사한다.

시계열 창은 기존 stage1의10초 경계와 주입 전후 라벨 규약을 유지한다.
이는 실제 장애 종료 시각의 완전한 복원이 아니다.
그 외 네트워크·오류·요청 관계 표현 변경은 없다.

### 저장 입력 인터페이스

새 `artifacts/bundle.npz`:
- `metrics`: float32 `[N,nodes,10,8]` 원값; `metric_observed`: bool 같은 크기.
- `traces`: float32 `[N,nodes,10,2]`; `logs`: float32 `[N,nodes,event_count]`.
- `labels`: int64 정상=-1/장애=root노드index.
- `case_ids`: 문자열 `[N]`, `starts`: int64 epoch초 `[N]`,
  `partition`: train/validation 문자열 `[N]`, `indices`: int64 `[N]` 고유 로컬행.
- `edge_pairs`: int64 `[E,2]`, TRAIN간선+self-loop.

`artifacts/input.json`: services/event_count/families, 정렬된행 provenance,
각case 원본해시, new split SHA256, bundle SHA256, 템플릿 출처/해시,
정상·장애·미지원수, 비용과 소프트웨어 버전, 보호 open guard 근거.
raw metric 결측은 mask와 함께 보존하되 모델 입력은 runner에서 TRAIN-only 처리한다.

## 3. 기준선 학습 — 결과 전 고정

- 기존 `native_models.NativeReference("diagmlp", ...)` 수식 기반 복원본.
  metric_count8, length10, 고유 입력 차원의 나머지 구조와 dropout0.1 유지.
  원저자 비공개 통합 설정까지 완전 재현했다고 하지 않는다.
- **seed11/23/37, 각200epoch 상한, 정확히3회 fit**, Adam lr0.001,
  기존 weight decay 기본값, batch256, 기존 joint_loss(alpha0.5).
  정상 detection과 장애 root 손실의 기존 정의를 유지한다.
- TRAIN은 기존 창 단위 샘플링, seed별 고정 셔플. 예산 내 조기 종료·자동 연장·LR 탐색 없음.
- checkpoint 선택: **validation 전체 창 기준 joint loss 최소**, 정확한 동률은 이른 epoch.
  전체 validation에서 계산한 detection CE 및 장애창 root CE로 loss를 계산한다.
- 매 epoch TRAIN 온라인 joint loss, validation loss/rootNLL/detection,
  사건/창 Top1, 경과시간을 기록한다.
- 선택 checkpoint와 마지막200epoch checkpoint의 TRAIN/validation
  root/detection logits, 원래 case/행/시간/정답을 저장한다.
  총3seeds×2checkpoint×2part=12개 prediction 묶음.
- 초기·선택·최종 모델/config/source/input 해시와 update 횟수를 기록한다.
- CPU2 threads/run, 최대3seed 병렬, GPU없음. 비용·메모리 실측.

200epoch를 실행했다는 사실만으로 충분히 학습됐다고 인증하지 않는다.
최선 선택 시점, 후반 loss, TRAIN/validation 간 차이, seed변동으로 예산·학습 상태를 설명한다.
예산 끝에서 계속 좋아지거나 수치 문제가 있으면 그 한계를 보고하고 임의 연장하지 않는다.

## 4. 채점과 오류 분석

### 주지표

장애창의 동점 기대 Top1/Top3/MRR를 각 검증 사건 안에서 평균하고
24사건을 균등 평균한다. seed별 결과와 사건별3seed평균을 함께 제시한다.
최고확률을 창에 걸쳐 평균한 뒤 사건을 단일 분류하는 것으로 바꾸지 않는다.
정상창은 원인 순위 분모에서 제외한다.
창 가중 결과, detector gating 포함 지표, detectionP/R/F1과rootNLL는 보조다.
validation은 선택+오류분석에 사용됐으므로 최종일반화 점수가 아니다.

### 전체 사례부터 확인

모든24사건의 서비스·장애·창 수·점수·선택epoch·주요 오답 후보·seed변동을 남긴다.
정확히0/1/부분점수 사건을 구분하며 seed3개를 독립 사건3개로 세지 않는다.
서로 다른 사건에서 같은 root→wrong 혼동이 나타나는지, 그 사건들이 어떤 조합인지 기록한다.
조합당 검증사건이1개이므로 같은조합의 여러 신규실행 반복실패를 주장하지 않는다.

### 요청 단서 분석의 조건

저장 예측에서 실제 오답이 확인된 사건에만 원래 허용validation trace의 필요한 열을 읽는다.
전체24사건 중 오답이 있는 것의 수와 조사한 관계 수를 보고해 선택 범위를 밝힌다.
주입설정·라벨은 사후대조에만 쓰며 새 입력/진단 모델을 만들지 않는다.

같은 `(traceID,parentSpanID)`를 실제 `(traceID,spanID)`에 연결한다.
같은시간/다른요청이라는 이유로 짝짓지 않는다.
중복span ID, 미해소parent, 빈ID, 동일서비스edge, cross-case상충, 시각/지속시간
정합성, 상태값의실제의미/알려진비율을 검사한다.
direct caller/callee span이 있다는 것과 같은 RPC양끝이라는 것은 다르므로
span kind/요청 속성이 부족하면 “동일 trace의 부모·자식” 수준으로만 표현한다.
범용statusCode를 HTTP500/200으로 단정하지 않는다. gRPC/OTel상태/HTTP의미를
현자료와원출처에서 확인할 수 없으면 숫자코드의 관계로만 기록한다.

root·주요wrong 주변 대응이 실제오답창에서존재하는지, 어떤상태/지연차이가 있는지
기술적으로 확인한다. 이것만으로 대응정보가 정답을식별하거나성능을개선한다고하지않는다.
연관근거가 없으면 관측없음/짝불명/관계무관을 구분해 후속대조근거부족으로보고한다.

## 5. 검증과 복구

학습 전: split24×2/1과봉인18,case/시간중복,노드/라벨정렬,TRAIN-only적합,
source/inputhash,유한모델입력,작은합성검사,명시적Pyright를 확인한다.
학습 후: 각seed 실제exit0·200history,선택최저loss/동률,동일shape/예산,
별도프로세스12prediction재추론,독립채점·모든사건보존,원본해시불변을확인한다.

작업은 새 폴더 안에서만 수행한다. 기존 stage1/2/학습/프로토콜을 수정하지 않는다.
JSON/실행폴더는 exclusive-create한다. 실패 산출물은 보존하고 실패 원인·재개 조건을 기록한다.
명령은 monitor로 실행하고 실제exit와경고를기록한다. 종료시간초과는수렴실패가아니다.
계약을 바꿔야 하는 실제 입력충돌은 주담당에 보고하고 임의feature삭제/분할재선택을 금지한다.

## 6. 단계별 DAG

한 단계가 끝난 증거를 읽고 다음 run을 정의한다. 마지막보고까지 이번승인목표에 포함한다.

### 입력 준비 단계

- `split`(quick): split.py/test_split.py, split.json, SPLIT.md.
- `runner`(deep-low): runner.py/test_runner.py, RUNNER.md; 위입력인터페이스로구현,
  합성검사만실행하고실자료학습은하지않음.
- `inputs`(deep-low, split 의존): prepare.py/test_prepare.py, artifacts/, INPUTS.md.
- `input-verify`(unspecified-low, split/runner/inputs 의존): INPUT_VERIFY.md.

최초wave2: split과runner의쓰기범위분리. inputs는split결과가필수이므로선행할수없다.
다음wave inputs+runner 최대2. 모델/템플릿/관측정렬이맞물리는구현은deep-low,
기계적분할은quick,서로다른증거를연결하는검증은unspecified-low.

### 학습·분석 단계 — 입력검증 통과 후

세seed학습(각quick,독립run폴더)→재추론/독립채점→전체사건오류/조건부요청단서분석
→한국어보고→보고수치대조. 모든알려진단계를그run의dependsOn으로선언한다.
표현대조나시스템확장노드는없다.

## 종료 판단

강한 기준선에서 남은 오답과 그 반복 범위, 학습 상태, 허용관측의 구별 단서를 보고한다.
“동일 요청 대응 정보 보존”의 후속 비교를 해볼 근거가 있는지, 아직 부족한지 구분한다.
새로운신경망노벨티/DiagMLP일반불가능/인과식별을증명했다고하지않는다.
모든증거를보고한뒤멈추며추가표현대조는사용자검토후결정한다.
