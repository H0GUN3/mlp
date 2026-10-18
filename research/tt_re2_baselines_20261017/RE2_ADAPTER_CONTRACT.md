# RE2-OB 입력 변환 계약 — 준비 단계

## 승인 범위와 평가 조건

기존 split.json/hash를 유지한다. train54/validation18만허용하며test18은열지않는다.
30/30/30 반복별새분할은추가승인대상이고아직채택하지않았다.
현재고정분할은root×fault조합별3반복이같은파트에있으므로,
알려진동일조합의다른반복평가라고부르지않는다.
새분할승인과무관한기존허용범위의스키마/변환코드작업은진행할수있다.

## 실제 스키마 확인

inspect_re2_schema.py가72개허용사례의216개Parquet footer/schema를검사했다.
mon_ZW3BMTYD3ZCY10W3:CLI0errors/0warnings,
RE2_SCHEMA_PASS54 18 PROTECTED_OPENED_0 ROWS_DECODED_0,실제exit0.
관측행은0개디코딩했고템플릿/scaler/그래프적합도하지않았다.

- metric: `time` + `{service}_{family}`열. TRAIN/validation 모두8family:
  cpu,diskio,error,latency-50,latency-90,mem,socket,workload.
  Eadro의7채널과동일한물리량이라고하지않고NativeReference.metric_count로구성한다.
- logs: timestamp(int64),container_name(large_string),message(large_string).
- traces: time(string),traceID/spanID/serviceName/methodName/operationName/
  parentSpanID(string),startTimeMillis/startTime/duration/statusCode(int64).
- metric행수는사례별상이하다(예:1441과930). 모든사례를1441행이라고가정하지않는다.

TRAIN metric헤더식별자14개:
adservice,cartservice,checkoutservice,currencyservice,emailservice,frontend,
frontend-check,frontend-external,istio-init,paymentservice,productcatalogservice,
recommendationservice,redis,shippingservice.
이는아직최종서비스후보목록이아니다. 로그/trace식별자와서비스별관측을추가대조해야한다.
validation에서만나타난metric헤더식별자는
InboundPassthroughClusterIpv4,PassthroughCluster이며둘다기존명시된proxy제외목록이다.
그밖의새서비스를조용히버리지않고발견시계약을재검토한다.
원인라벨5개만으로후보를축소하지않는다.

## 최소 구현 원칙

1. 원래허용case를먼저확인한뒤그case의파일만읽는다. 입력case ID는출처/분할용이며
   모델특징에넣지않는다.
2. .venv-mlp의기존Arrow로Parquet를읽고원형시계열/로그이벤트/호출관계를보존한다.
   한사례씩처리하며파일크기·가용메모리를보고projection/batch읽기를선택한다.
3. .venv-eadro의기존Drain3/tick로TRAIN nominal-normal 로그만템플릿적합,
   고정템플릿으로각10초창의Hawkes입력을만든다. 새설치없음.
   두환경사이에는명시적dtype·단위·서비스명·시간출처가있는중간파일을사용한다.
4. metric[N,10,M]과trace[N,10,2]시간열을보존한다. trace둘째채널은0.
   17/18특징요약이나로그count벡터로원형encoder입력을대체하지않는다.
5. 누락은누락으로기록한다. 학습전용통계에따른보간/대체규칙을적합전에고정하고,
   결측이관측된0이라는주장을하지않는다. 원인후보와실패사례를삭제하지않는다.
6. 정규화·후보사전·그래프/템플릿적합은TRAIN에한정한다.
   사례별순수변환과분할의존적적합을구분하여분할변경시후자를재사용하지않는다.
7. inject_time전후는공개benchmark의nominal-normal/fault-label규약이다.
   실제활성/회복시각이검증됐다고하지않는다. 주목표는조건부원인진단이며
   jointdetector를그대로학습할경우이규약에따른부가과제임을명시한다.
8. 시작/지속시간단위는필드명만으로추정하지않고출처와좌표일치로확인한다.
   시계열경계·중복identity·교차사례관측중복검사를다음단계에포함한다.

## 아직 미완료

관측값기반서비스매핑/단위확인,순수변환코드/fixture,
Drain/Hawkes·scaler적합,모델학습은아직하지않았다.
이파일과스키마PASS는“RE2모델입력이준비됐다”는증거가아니다.

## 순수 변환의 실제 확인

기존 TRAIN `re2ob_checkoutservice_delay_1`에서관측값을확인했다.
mon_TQQ9T2AKJ6JKW5M1:CLI0/RE2_VALUE_PROBE_PASS/실제exit0.
metric1441행은1초간격,로그177868행은초단위timestamp,
trace405229행은startTime//1000==startTimeMillis가전부성립했다.
Jaeger JSON Span의StartTime/Duration은각각EpochMicroseconds/Microseconds이며,
변환은duration/1e6초를사용한다:
https://pkg.go.dev/github.com/jaegertracing/jaeger/model/json#Span
모든사례의단위가이미검증됐다고확대하지않고변환때마다좌표를검사한다.

실제이름차이:metric/log의frontend와trace의frontendservice.
근거없이합치지않고현재중간파일에서는원래식별자를보존했다.
frontend-external도별도원본식별자다. 이것은최종융합매핑완료가아니다.
원인라벨5개는이frontend별칭문제와별개로원본이름을유지한다.

re2_stage1.py/test_re2_stage1.py:
mon_YBVS3T74CQSCD9AF의5fixture/CLI0/RE2_CASE_PASS/실제exit0.
첫사례144개10초창,177765로그이벤트의중간파일생성·roundtrip검증PASS.
metrics의NaN과observed mask를보존하고대체/정규화하지않는다.
trace는초별평균초단위지연,두번째채널0,빈초count0을별도보존한다.
전체10초창뒤남은부분의로그103행/span1행은고정경계규칙으로제외했다.
이는오답/고장유형에따른제외가아니다.
nominal window label은window_end>=inject_time이면root,그전이면-1이며
실제고장활성지속증명이아닌공개benchmark규약의명시적창변환이다.

기존허용72사례의순수변환은4worker,Arrow/BLAS각1thread로진행한다.
첫검증사례는hash확인후재사용하며미완료파일을덮어쓰지않는다.
source/split/outputhash와각사례의실제처리시간을보존한다.
템플릿·scaler·학습그래프적합은아직하지않는다.
