# 분석 체크포인트와 출처

## 실제 실행
- `extract_metadata.py --self-test` 통과.
- 19,991개 archive member를 단일 순회; injection/env/conclusion4,266파일,
  1,422사례, 파싱15,090,330bytes.42.928초, peakRSS292,564KiB. 실제exit0.
- 대상파일sha256은기존전수quality검사의값과모두일치.
- 센서metrics/logs/traces Parquet 본문은재파싱하지않고기존quality_audit.json을재사용.
- `analyze_metadata.py --self-test` 및전체분석통과,1.308초,실제exit0.
- 두분석스크립트LSP진단없음. 새학습·추론·분할할당없음.

## 주입·정답
실제25개fault type,10개env namespace.2025-07-17~2025-09-06 UTC.
single_application369,HTTP endpoint796,DNS endpoint1,DB operation2,network pair254.
원정답은1항목369/2항목1053. 구성앵커30종.
label-set 규칙 불일치1:
`ts4-ts-food-service-container-kill-lv5htg`는display_config가food-service,
ground_truth가config-service다. 실제어느컨테이너에실행됐는지미확인;임의수정/삭제안함.

## SLI
결론요약27,146행,모든1,422사례에적어도하나의`slo_violated=true` 기록.
JSON Issues 파싱오류0,요약값비유한/누락0.
이는export된저자생성요약의검사이며rawrequest/Z-test/지연threshold를재계산한것아님.
사례별최대API성공률하락의중앙값0.8588039867,
사례별최대API평균지연비율의중앙값26.7123111.
시스템전체평균의변화나우리모델성능으로쓰지않는다.

실제예:
`ts5-ts-order-service-stress-svfvxk`:JVM메모리주입설정,
order.service.OrderServiceImpl.getOrderPrice, 정상/이상4분.
`POST .../orderservice/order/refresh` 성공률1.0→0.7363796134, SLOflagtrue.
같은사례의verifycode API는1.0→1.0이며Issues{}.
‘장애사례’라고모든서비스/모든API가실패한것은아님.

## 관측·반복·시간
기존quality와결합:모든라벨대상의최소양모달지원1258/1422.
정답의trace기초행이없는사례:정상139,이상163.
network pair254중양쪽지원117. 자동제외근거가아님.
같은namespace의선택된사례간양의시간중복0;
다른선택주입과정상구간의양의중복0.
그러나공유호스트·미포함주입·같은설정등독립성은별도.
엄격구성1362그룹;namespace/pod명만정규화한구성1322그룹,
59반복그룹,최대7사례. 모든task_id1422개는서로다름.
구성반복은동일사건/중복파일의증명아님.
같은사례내normal/abnormal 경계span공유133사례는기존관측검사에서확인됨.

## 원문·코드 확인
- Eadro v1§V-E:주입된창을abnormal로표시,그외normal.
  response-time SLOthreshold가그정답을정의하는것은아님.
- TVDiag v3:metric3sigma/traceIsolationForest/logevent규칙은alert추출단계.
  지도target은root-instance/type;alert자체가사용자실패정답은아님.
- DeepHunt§2.3:장애탐지범위밖,장애가주어졌을때위치진단.
- Transformer기초:Vaswani2017§3.2의scaled dot-product/multihead/position.
- pinned fault enum:
  `https://github.com/OperationsPAI/rcabench-platform/blob/5a463bd2bfaecda1b26aed9fe3f018859196bb0e/src/rcabench_platform/v2/datasets/rcabench.py`
- pinned injection generator:
  `https://github.com/OperationsPAI/chaos-experiment/tree/55f9ad16818e89aeed984594434e8fbc66c5d430`
  HTTP:handler/http_chaos.go,chaos/http_chaos.go,handler/httphelpers.go.
  DNS:handler/dns_chaos.go,chaos/dns_chaos.go.
  JVM-MySQL:handler/jvm_chaos.go,chaos/jvm_chaos.go.
  Network:handler/network_chaos.go,chaos/network_chaos.go.

공개코드상HTTP/DNS/JVM-MySQL은app_name의pods에동작을설정한다.
HTTP의server_address는실제host필터에사용되지않는다.
Network는source/target/direction을모두설정하므로source만유일한물리적원인이라할수없다.
이정적코드가각archive사례의정확실행revision인지와실제활성화는미확인.
비network 구성은1168사례이며충돌1건제외1167이단일설정표적검토후보다.
이수는선정된학습자료/검증된인과정답수아님.
