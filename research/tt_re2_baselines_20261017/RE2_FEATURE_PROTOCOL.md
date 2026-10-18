# RE2-OB 공통 입력 계약 — 기존 허용 분할

## 범위

기존 고정 train54/validation18을 사용한다. test18은 읽지 않는다.
같은 root×fault의 반복은 같은 파트에 있으므로 알려진 조합의 반복 분리 평가가 아니다.
추가 제안한30/30/30은미승인이고적용하지않는다.
이단계는두기준선에공통으로공급할입력준비이며새기법이아니다.

## 식별자와 그래프

TRAIN case 중간파일의 관측 식별자 union을 정렬해 공통 노드 순서를 만든다.
변환에서 명시한4개 proxy만 제외하고, 원인 라벨5개로 후보를 축소하지 않는다.
미확인 frontendservice→frontend 병합은 하지 않는다.
frontend-external도 별도 원본 식별자로 보존한다.
frontend-check/istio-init 등 배경 식별자를 앱서비스로 인증했다는 뜻은 아니다.
이는 관측 식별자 노드 기반의 명시적 적응이며, 정확한 물리서비스별 융합 재현은 아니다.
이 한계는 최종 비교 보고에 포함한다.
validation에 새로운 비proxy식별자가 있으면 자동삭제하지 않고 중단/검토한다.
TRAIN에서 관측된 호출 간선 union과 모든 노드의 self-loop로 공통 정적 그래프를 만든다.
validation의 간선으로 학습 그래프를 확장하지 않는다.

## 로그

기존 .venv-eadro의Drain3/tick와동결native_data.make_knots/fit_hawkes를재사용한다.
동결된native drain3.ini를사용하되,TRAIN54의timestamp<inject_time인
로그 message만정해진case/원본행순서로템플릿적합한다.
validation로그로템플릿을추가/수정하지않는다.
훈련후템플릿및snapshot을저장하고,cluster ID→특징순서와미지템플릿bin을고정한다.
한개입창의라벨이장애여도주입이전로그만정상참고적합에사용한다.
Hawkes는10초상대시간/decay3/default50iteration/initialbaseline0.2,
원형빈템플릿[0]및tie jitter규칙을보존한다.
로그가전혀없는노드/창은실제관측부재로0벡터이며가짜로그를만들지않는다.
사례ID·원인·고장종류를변환입력으로사용하지않기위해solver seed는공통42로고정한다.
동일상대knots/템플릿순서의반복입력은동일seed/규약아래결과cache를재사용할수있다.
iteration상한도달·warnings·실제처리시간을숨기지않는다.

## 배열·후속 정규화

metric[N,nodes,10,8]은raw값과observed mask를유지한다.
trace[N,nodes,10,2]는초단위평균지연이고두번째채널0이다.
logs[N,nodes,event_count]는Hawkesbaseline이다. root및partition은별도라벨/메타데이터다.
원본case ID,창시각,가변관측길이,제외된마지막불완전창,결측을추적한다.
stage2에서는metric결측대체/scaler를적합하지않는다.
이후모델실행기에서TRAIN-only대체·정규화계약을별도로고정한다.
검증전용범위의정보로수정/사례제외하지않는다.

## 검증

동결split와stage1manifest/hash/후보/정답대응/각case소속을검사한다.
모든허용case를포함하고보호case는0개여야한다.
stage1시계열구간의교차파트중첩을확인한다. 중첩이있으면독립관측이라
주장하지않고원본identity추가검사전학습을중단한다.
시간좌표·누락·정상참고선택·미지템플릿·Hawkes유한/비음수·
학습통계/템플릿의검증값불변fixture를사용한다.
완성해도원논문동일입력/정답활성구간의완전재현이라고부르지않는다.
