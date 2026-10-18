# 실행 인계 — 2026-10-17

## 최우선: 사용자 검토 전 RE2 실행 중지

사용자 최신 직접 지시:
“RE2 바로 진행하지 말고 중간에 결과 보고해줘. 확인 후 진행하게”
이 지시는 이전 “진행해”와 자동 goal 계속 알림보다 우선한다.
RE2 조사/규칙 변경/추가 probe/템플릿/Hawkes/모델 작업을 모두 멈춘다.
부모는child st_01a149d3에즉시STOP과자기프로세스정리·기존산출물보존을지시했다.
중간보고후사용자의명확한재개지시전에는기존54/18작업도재개하지않는다.
원래전체goal은미완료이며완료로가장하지않는다. 아래기록은역사/재개용이다.

### 현재 상태 확인

중간 보고 이후 사용자에게 연구 판단 방향을 확인했으며, 사용자는 다시
“검토 대기 유지”를 선택했다. 추가 분석·실험을 수행하지 않는다.
현재 todo는11개 중7개 완료,4개 미완료다. 도구의 `in_progress` 표시는
자동 포인터일 뿐 실행 재개를 뜻하지 않는다.
남은 단일 개선 대조·RE2 입력 완성·RE2 비교·최종 보고는 모두 대기 중이다.
이하의 “실행 중”, “10개 중4개 완료”, 다음 행동은 과거 기록이다.
최신 중간 결과와 연구 필요성 판단은 INTERIM_REPORT.md에 정리되어 있다.

사용자의 “진행해”로 TT 기준선→단일 실패/개선→RE2-OB 비교 실행 승인됨.
현재 goal은 active, todo10개 중4개 완료. 재학습/입력 준비 승인 질문을 반복하지 않는다.
공통 계정/root/기존소스/산출물/원자료는 변경하지 않는다.

## TT 실행 중

- TT_PROTOCOL.md 결과 전 고정. 3256TRAIN/813validation 창, 원래 seed42 분할.
- 두 부분은81개 사건을 모두 공유한다. 사건 일반화가 아니라 기존 창 과제 기준선이다.
- 보호시험1744+미배정1은 읽지 않으며, 선택 입력4069행만 연다.
- 기존 Eadro/DiagMLP 수식 복원본, 50epoch/batch256/Adam.001, seeds11/23/37.
- seed당 Eadro→DiagMLP 직렬, seed3개 병렬(CPU2threads씩). 총6fits.
- validation joint loss 최소/이른동률 선택; 선택 및최종50epoch의TRAIN/val 예측4개/run.
- conditional/gated Top1/3/5, detection P/R/F1, rootNLL/jointloss.
- 모델·선택·원논문split identity가완전재현됐다고주장하지않는다.

실제 학습 모니터:

| seed | monitor | parent bash |
|---|---|---|
| 11 | mon_X5AAM5N8JB1P8PQ1 | bash_14 |
| 23 | mon_2F0XQPMEPC5Z5XAQ | bash_15 |
| 37 | mon_QP9B7YX840BY7BEM | bash_16 |

각 명령은절대경로 tt_runner.py fit --kind eadro --seed S 후
성공한경우만diagmlp를실행한다. TT_FIT_PASS둘과실제exit0을확인한다.
살아있는프로세스/기존run폴더를확인없이재실행하지않는다.
완료전요약파일/성능/성공을발명하지않는다.

## 실행 전 검증

- 최초mon_6S9V6VA1ZNGT7FV1:5tests/CLIpyright0은통과했으나
  입력검사JSON에numpy.int64를쓰다exit1. 학습실행전실패다.
- root_support를Python int목록으로변환하고dump는JSON직렬화를파일열기전에하도록수정.
  실패산출물TT_INPUT_CHECK.failed.partial을보존했다.
- mon_HP14VG6XRCKJ527N:6tests/CLIpyright0errors0warnings0informations/
  TT_INPUT_PASS4069 27 및실제exit0.
- TT_INPUT_CHECK.json PASS를직접읽어확인:
  TRAIN fault2765/normal491,validation fault686/normal127;양쪽root27/events81.
  원형scaler상수metric5/trace41.
- native단일파일LSP는환경import해석경고가남지만owned-projectCLI와실제실행은PASS.
  진단무시/환경설치/기존config변경없음.
- 현재tt_runner.py hash bdc3a3ae88359f73448f88d16edb36a258ea147dff4c4869bbcef7309d292a1f.
  학습중runner/test/TT_PROTOCOL/native sources를편집하지않는다.

## RE2-OB — 분할 결정 대기, TT와 독립

읽기전용child st_01a14999 완료. 기존split.json/lock은54train/18val/18test,
같은(system,root,fault)의3반복을전부한파트에넣는다.
이것은“알려진고장조건의다른반복시험”과다르다.
따라서사용자에게직접질문했다:
조건별3반복을train/val/test에1개씩넣는30/30/30새manifest를만들어도되는가?
기존보호18일부가train/val로이동하므로명확한승인필요. 기존manifest는보존한다.
답변전에는새분할관측/템플릿/scaler/그래프적합을진행하지않는다.
TT학습및분석은계속가능하다.

기존helper scripts/mlp_readiness.py: load_split/allow_read/NON_SERVICE_NODES.
후보는TRAIN관측서비스union에서지정된4proxy만제외,root5개로후보를축소하지않음.
기존17특징extractor는nativeadapter가아니다. temporal metric[N,10,M],
trace[N,10,2]둘째0,Drain/Hawkeslogs를새adapter로준비해야한다.
공식inject_time의before/after는명시적인benchmarklabel규약으로사용가능하나,
실제활성종료시각의증명으로부르지않는다. 기존원형공동탐지의완전재현아님.
case별확률평균을사용자요구라고단정하지말것:주지표는창별conditionalroot,
case별평균은별도보조로설계한다.

## 다음 행동

학습완료알림→실제exit/6summary/650updates/선택최소/공통초기화/독립NumPy채점확인.
그후TRAIN/val/최종학습손실과입력단서를대조해실패하나를선정한다.
RE2-OB 분할답변은먼저반영한다. 보호최종시험성능없이검증성능을최종이라고부르지않는다.
JS ttRunRoot/ttTrainMonitors, Python tt_preflight_mon/tt_preflight_fixed가유지된다.

## 시간 제한 복구 — 현재 활성 상태

최초3monitor가default시간제한으로timed_out/exit1. pgrep으로tt_runner.py
프로세스가없음을확인했다. seed11은45epoch,23은47epoch에서중단;
둘다optimizer재개상태와last.pt가없으므로동일seed처음부터재실행해야한다.
seed37은50epoch/last.pt/history.json이이미완성됐고추론보고단계만중단됐다.

동결tt_runner.py/test/TT_PROTOCOL/native sources는수정하지않았다.
새recover_tt.py는실행산출물만보존·복구한다.
- 11/23 부분디렉터리를interrupted_attempts/eadro/seed_S로이동하고
  모든파일hash일치를검사한뒤같은원래경로에새시도를시작했다.
  TT_INTERRUPTION_ARCHIVED11 45 /23 47 실제sentinel확인.
- 37은기존best/last가중치만재추론해summary를완성했다.
  TT_RECOVERED_POSTPROCESS eadro37 50 확인. 학습재실행없음.
  비용은epoch별기록시간합으로복구됐으며checkpointIO오버헤드를포함하지않는다.
- 새복구script/verify CLIpyright0errors0warnings0informations.
  verify_tt.py는추가로원래중단구간의config와epoch기록(시간필드제외)이
  동일seed재실행에서정확히재현됐는지도검사한다.

현재3실행(명시적timeout_ms1800000):

| seed | monitor | parent bash | 작업 |
|---|---|---|---|
| 11 | mon_PFD1H8N5ABR0DP7J | bash_22 | archive→Eadro재시도→Diag최초 |
| 23 | mon_FP88Z2C4WD8FM7KP | bash_21 | archive→Eadro재시도→Diag최초 |
| 37 | mon_5H31W46VJWB97P28 | bash_20 | 기존Eadro후처리완료→Diag최초 |

첫시도실패는실패로남기고실제완료6fits와중단2시도를구분한다.
새monitor완료전재실행금지.
mon_N8PEW5NE245R0K5M/bash_17은6summary파일이생기면
CLI진단후verify_tt.py를실행하는독립검증gate이며30분한도로대기중이다.
마지막TT_VERIFIED6 24/실제exit0을확인하고그전성공으로종료하지않는다.
JS ttTimeoutEvidence/ttRecoveryMonitors/ttCompletionGate에현재증거·handle존재.
RE2분할질문은아직사용자답변없으며자동goal계속알림은승인이아니다.

## 최신 진행

- seed37 복구monitor mon_5H31W46VJWB97P28 실제exit0:
  Eadro기존50epoch후처리복구 + DiagMLP최초50epoch TT_FIT_PASS.
  두summary를읽었다. 다른seed와독립검증이끝나기전전체성능으로보고하지않는다.
- seed23/11은Eadro50epoch TT_FIT_PASS수신,각자의DiagMLP학습은계속중.
- 새diagnose_tt.py는TT_RESULTS PASS이후에만실행한다.
  저장된선택validation예측의고장종류/서비스별오답,roottrace존재,
  TRAIN범위밖입력과오답의동반여부,선택/최종손실을분석한다.
  재학습·예측선택변경·보호관측접근없음. 독립동률fixture와LSP0.
- 진단gate mon_NV9WA6KWKF1DA913/bash_23은TT_RESULTS.json생성후
  CLI진단→diagnose_tt.py를실행하며TT_DIAGNOSIS_PASS6 686/exit0필요.
  timeout_ms1800000. JS ttDiagnosisGate에handle존재.

## TT 기준선·진단 완료 — RE2 승인 대기

복구모니터3개모두실제exit0를bash_output으로확인했다.
mon_N8PEW5NE245R0K5M은TT_VERIFIED6 24/exit0:
6run/24예측독립채점/선택최소/해시/초기값/중단prefix정확재현모두PASS.
mon_NV9WA6KWKF1DA913은TT_DIAGNOSIS_PASS6 686/exit0.
TT_RESULTS.json/TT_DIAGNOSIS.json을전체파싱하고요약값을검토했다.
TRAIN/validation평균Top1: Eadro83.90597/79.64043%,DiagMLP99.63834/98.63946%.
validationTop3:Eadro98.97959%,Diag100%. 선택epoch E48/50/46,D27/23/24.
검증에서선택한점수이지보호최종시험아니다. 원래창분할공유81사건한계유지.

TT_BASELINE_REPORT.md에완료수치/실패/검증/시간초과복구이력을정리했다.
Eadro는학습Top1부터84%이고예산끝선택이라최고성능/구조원인확정불가.
DiagMLP오답8/9/11창의metric/trace는모두각TRAIN범위안에있어
극단값으로현재TT오답을전반설명하는가설은지지부족이다.
주된travel/food혼동의호출수가다른지probe_tt_confusion.py로검사:
mon_32DG6085YKF4PRHX CLI0/TT_CONFUSION_PROBE_PASS/실제exit0.
24seed-window오답=15고유창,13창은두후보count모두0,차이2창.
후보별count추가로이혼동을해소한다는단일가설은지지부족.
새count채널이나구조학습을실행하지않았다. 전체count활용의무효주장도아니다.

todo6/10완료. 단일개선검증은근거가확보된경우에만실행하며아직미수행.
RE2새분할30/30/30질문에실제사용자답변은아직없다.
현재학습/검증모니터는모두완료;재실행하지않는다.
기존환경확인: .venv-eadro에는tick/drain3/torch/dgl있고pyarrow없음,
.venv-mlp에는pyarrow/torch/dgl있고tick/drain3없음.
새설치없이RE2준비시Arrow읽기와nativeHawkes를두환경으로분리해야한다.
새RE2관측/변환적합은분할승인전진행하지않았다.
Python tt_result_doc/tt_diagnosis_doc에현재전체결과가상주한다.

## RE2 독립 준비 진행

새분할질문과무관하게기존허용범위의스키마/변환코드확인은승인된작업이다.
이를전부중단할필요는없다. 새30/30/30manifest나보호관측접근은여전히미승인.
inspect_re2_schema.py/pyright_re2.json을추가했다.
mon_ZW3BMTYD3ZCY10W3 실제exit0/CLI진단0/
RE2_SCHEMA_PASS54 18 PROTECTED_OPENED_0 ROWS_DECODED_0.
72허용case의216Parquet footer/schema만확인;관측행디코딩0.
RE2_SCHEMA_CHECK.json을전체파싱하여필드를확인했다.
TRAINmetric헤더14식별자,8family. validation전용2식별자는기존proxy제외목록.
logs/traces는72case에서각각같은schema다. metric행수1441만있는것은아니다.
RE2_ADAPTER_CONTRACT.md에실제필드·두환경브리지·TRAIN-only적합·보호경계를정리했다.
아직raw값단위/서비스명대조,변환함수fixture,템플릿/Hawkes/scaler/모델은미실행.
Python re2_schema_doc에전체메타결과상주.
다음은기존허용사례에대한관측단위/서비스대응과순수변환함수구현이며,
새분할선택이나보호접근을가정하지않는다. TT실험은다시돌리지않는다.

## RE2 stage1 완료, stage2 진행

기존 TRAIN checkoutservice_delay_1의 실제 값 대조:
mon_TQQ9T2AKJ6JKW5M1/RE2_VALUE_PROBE_PASS/exit0.
metric 1초간격, 로그 timestamp 초, span startTime//1000==startTimeMillis 전부일치.
Jaeger 공식 JSON 타입의 duration microseconds 규약을 확인했다.
소스 unit 근거: https://pkg.go.dev/github.com/jaegertracing/jaeger/model/json#Span.

re2_stage1.py/test_re2_stage1.py, pyright_re2.json:
mon_YBVS3T74CQSCD9AF에서5fixture/CLI0/첫허용case변환/실제exit0.
첫case144개10초창,177765로그,원형metric NaN/mask·지연초열·count·간선 보존.
그후 re2_stage1_batch.py는검증된첫case재사용,71개를4worker/각1thread로변환.
mon_VV7N6MMN51WC6PEB 실제exit0. RE2_STAGE1_MANIFEST.json을읽었다:
PASS_UNSCALED_ONLY,72case,10273windows(TRAIN7732/validation2541),98.738초.
보호case0,템플릿/scaler/학습그래프적합없음,model_ready=false.
stage1 source SHA46436d014378babea7a430ed5f677399bbc751d5ee0ac0ec34044a3ea109a719.
stage1 중간파일은동결하고재변환하지않는다.

이름 매핑 읽기전용child st_01a149cb 완료:
frontendservice→frontend는가능성있지만직접확인된정확release별칭은아니다.
frontend-external은공식배포의별도K8sService,frontend-check/istio-init은init계열.
정확한자료수집revision은미확보. 따라서임의병합없이raw식별자를보존한다.
원인라벨5개는기존이름대로매핑하고,배경식별자까지물리앱서비스라고인증하지않는다.
RE2_FEATURE_PROTOCOL.md에이적응범위·TRAIN-only집합/그래프/Drain/Hawkes를고정했다.
새30/30/30승인없이기존54/18허용범위의공통입력준비를계속한다.
새분할이나보호접근은하지않는다.

활성child st_01a149d3(deep-low):
소유 re2_stage2.py,test_re2_stage2.py,pyright_stage2.json(optional),
RE2_STAGE2_CHECK.md,re2_stage2/ 생성출력만. 부모는이파일을동시수정하지않는다.
staged72case만사용,원본raw/test접근금지. TRAIN<inject_time로그만Drain적합,
native make_knots/fit_hawkes seed42·10초·default50iteration,동일knots cache허용.
max8worker/각1thread,먼저실제cost probe. tool.monitor timeout_ms1800000 명시,
Python동기tool에await금지,생성프로세스종료전최종응답금지 지시.
stage2는rawmetric NaN+mask 유지,imputer/scaler와모델학습은아직하지않음.

합의된hand-off:
re2_stage2/inputs.npz keys metrics(W,N,10,8),metric_observed,traces(W,N,10,2),
logs(W,N,E),labels,partition,case_ids,event_ids,starts,indices.
metadata.json은system/services/edges/event_count/input_npz_sha256/split_sha256/
stage1_manifest_sha256/case/template/protection/source/cost 증거를포함한다.
완료시실제exit·fixture·CLI·bundle검증을읽고다음모델실행기작업으로이어간다.
Python re2_stage1_manifest, re2_schema_doc 상주. TT결과/진단도상주.

## Stage2 현재 확인사항 / 수정 지시

st_01a149d3의중간응답을완료로취급하지않는다.
원형bundle은아직미완료이고TRAIN템플릿producer가실행중이다.
RE2_STAGE2_CHECK.md와re2_stage2.py를읽었다:
실제72사례hash검사/교차파트시간중복0/전체사례시간중복0/노드15확인.
합성fixture6개와CLI진단은PASS라고기록되어있지만실제bundle완료증거는아니다.
첫TRAIN사례만으로Drain max_clusters1024에닿았다는보고가있다.
전체nativeHawkes를아직실행했다고주장하지않는다.

부모가child에게다음2개를교정/조사하도록task_send했다.
1. metadata.edges는Kx2 pair목록이어야한다. native_train.graph_batch는
   `src,dst=zip(*metadata["edges"])`다. child의2xK주장/구현은틀렸다.
   자기builder/test/docs만수정하고동결nativecode는수정하지말것.
2. 첫사례1024template는실제형식/비용위험이다. 이미staged TRAIN의
   message가구조화JSON/RFC시간/traceID등의envelope인지소량으로확인하고,
   TT전용mask가놓치는변동필드근거와실제E1025비용을보고할것.
   원문민감내용출력/무단config변경/중복Drain시작금지.
   기존producer/snapshot과실패이력은보존한다.

RE2_TRAINING_PROTOCOL.md를결과전에고정했다:
기존54/18,raw식별자노드,8metric+trace2+Hawkes,TRAIN-onlymeanimpute,
TRAIN전부미관측채널은unsupported로기록하여전부분0입력,
대체후기존TRAIN평균/std+epsilon1e-8/no clipping,50epoch/batch256/3seeds,
validationjoint최소선택,조건부/gatedwindow지표,원인빈도기준선.
아직RE2모델실행기는구현/실행하지않았다. child의입력완료/비용판정이선행한다.

## Stage2 형식 문제 확인 / 후속 작업

RE2_STAGE2_CHECK.md 최신 stop evidence를읽었다.
첫TRAIN사례89795줄에서7260cluster생성/1024유지,
7사례623356줄에서49482생성/1024유지로심한eviction/churn.
12000줄TRAIN표본은현재mask후1050종류,진단용digit-bearing토큰정규화후40종류,
IPv4미정규화149줄. 메시지는top-levelJSON이아니라plain/logfmt형식이다.
단순한시간초과가아니라TT전용mask의RE2형식부적합으로producer를중단했다.
Hawkes실제fit0,전체bundle없음. 원래producer가완료됐다고주장하지않는다.
partial_progress와preflight만보존됐고snapshot은원래프로그램이마지막에만쓰므로없다.
그래프Kx2수정과3edgefixture는완료. focused7tests/CLI0.

st_01a149d3를run_epoch5로다시이어갔다.
요청범위는이미inspectedTRAIN의sanitized정적문맥/변동필드증거와
상태코드·severity·예외명·실질event문장을보존하는최소RE2전용preformat제안이다.
단순모든digit-token제거를그대로채택하지않으며새54사례fit은아직재시작하지않는다.
원래stoppedmonitor/session의실제종료증거도요청했다.
현재child의부분완료/과거completed알림을새bundle완료로취급하지말것.
형식규칙은부모가명시적으로고정한뒤에만적용한다.
기존동결native모델/config와TT결과는건드리지않는다.

부모독립작업 re2_preprocessing.py/test_re2_preprocessing.py 완료.
mon_GA23VS0V65ZPHNWD:4tests OK/CLI0errors0warnings0informations/실제exit0.
TRAIN-only평균결측대체·unsupported채널0·원형scaler불변성을검증했고,
실제RE2배열에는아직적용하지않았다. 상수채널epsilon정책을몰래clip하지않는다.
현재미완료는올바른로그변환/실제입력bundle/RE2학습/최종보고이며,
새기법은근거없이추가하지않는다.
