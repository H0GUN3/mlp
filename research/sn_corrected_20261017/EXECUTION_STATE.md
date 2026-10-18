# 실행 상태 — 재시작 인계

사용자는 SN 선택 후 “진행해줘”, 이어서 mass-ulw를 명시했다.
PLAN.md를 재작성하거나 dataset 선택을 다시 묻지 않는다.
계획 hash: 5cae521d5fc32ba0b6878df5eaba9c40be17342beb0180c990f29f5d31c6b470.

## 완료한 입력

기존 child st_01a148db가 producer를1회 실행했다.
inputs.npz: ac91c3d72b750382644415f80f121873bd8a6716cce5d5f993790f7b973e8e8e.
입력394행/36episode, 보호170행은 opaque skip이며 ndarray해석0.
INPUT_VERIFY.md에15테스트,실제prepare,별도verify/sha 및exit0근거가 있다.
이 producer는 다시 실행하지 않는다. `load_inputs()`는선택cache검사로사용가능.
scores.py/test_scores.py는st_01a148dc완료. 22테스트의초기환경은Python3.10/NumPy2.2였으므로
아래DAG가실제.venv-eadro/Python3.8/NumPy1.21.5로검증한다.

## 활성 DAG

- 단계A key: sn-corrected-20261017-pretrain-v1
- run ID: dag_5e8428e6-daab-4663-b6a1-600ae47f1257
- 구성: input-receipt + score-check + runner-integration → pretrain-verify
- 시작 warning0. 완료통지는증거검토전PASS가아니다.
- input-receipt는INPUT_GATE.md,score-check는SCORE_GATE.md,
  runner-integration은RUNNER_GATE.md를인계한다.
- pretrain-verify는실제전체검사/환경/경계검증후PRETRAIN_CHECKS.json과PRETRAIN_VERIFY.md를작성한다.

단계A는4/4완료 후 주담당이 PRETRAIN_VERIFY.md, PRETRAIN_CHECKS.json,
RUNNER_GATE.md 및 실제 test_runner.py를 읽어 요구조건과 대조했다.
43테스트/실제환경(Py3.8.20,NumPy1.21.5,torch1.12.1+cpu,DGL0.9.1),CLI Pyright0오류/경고,
모두exit0. native 단일파일 LSP의 환경해석 차이는 RUNNER_GATE.md에 남아 있으며
“모든진단면이깨끗하다”고 주장하지 않는다. 재검사나 입력 재생성 없이 단계B로 진행한다.

runner.py/test_runner.py/pyrightconfig.json의 통합은 끝났고 runtime source가 잠겼다.
runner SHA-256: 025a8c94574719183a063ca422bbe722028ebbc661aefffafe099e6ce311b777.
학습 중 소스를 수정하지 않는다.
runner는train-rotation/lock/evaluate API로통합됐으며,
순환별6실행직렬×3순환병렬로최대3모델프로세스/CPU각2thread.
RUNNER_GATE의 실제CLI/파일명/검증을 읽고 단계B를 정의했다.

## 활성 학습 단계B

- key: sn-corrected-20261017-training-v1
- run ID: dag_9feb01ee-b39e-4224-b709-82fb460d8ee6
- 구성: train-r0 + train-r1 + train-r2 → lock-verify
- 시작 warning0. 각 node는자기순환만1회 실행한다.
- 명령: .venv-eadro/bin/python -B runner.py train-rotation --rotation f
- 인계: TRAIN_R0.md / TRAIN_R1.md / TRAIN_R2.md → TRAIN_VERIFY.md
- 실제 각 rotation exit0 및18개checkpoint/history/hash 검증 후에만 selection.lock.json을 허용.
- 아직 외부평가를 시작하지 않았다.

단계B 최초 completed통지는 실제성공이 아니었다. TRAIN_VERIFY.md의FAIL을 읽고 복구했다.
R0/R1은cwd오류로시작전exit2였으며,부모의절대경로monitors로최초실제학습을수행했다.
mon_7RY6DWGAZ9D7FME4(parentbash_8),mon_D2NY7AVB2ZSWYJNS(parentbash_9)
둘다실제exit0/ROTATION_DONE0,1을확인했다.
R2의원래모니터는나중에정상종료했으며TRAIN_R2.md/후속transcript에서exit0확인.
3순환18개모델모두200epoch; 재학습·400연장없음.
MAIN_TRAIN_EXECUTION.md와TRAIN_RECOVERY.md에증거보존.
다음은동일run의R0/R1영수증검증과lock노드를amend하여복구PASS를확인한다.
동일run의generation2를시작했다. R0/R1노드는이제학습을실행하지않고
MAIN_TRAIN_EXECUTION.md와산출물의영수증을검증한다.
R2정의는그대로두어완료캐시를재사용한다. lock-verify는복구된실제exit0근거를읽고
runner.py lock을절대경로로실행한뒤TRAIN_VERIFY.md에최종검증결과를덧붙인다.
새모델실행이나source변경은없으며아직외부평가미실행이다.

generation2의최신TRAIN_VERIFY도FAIL이었다. 부모가작성한명령끝의불필요한`.`때문
argparse exit2였고잠금파일을만들지않았다. R0/R1의receipt-only노드도
독립hash/history검사를마치지못해FAIL을남겼다. producer의18학습완료는유효하다.
generation3은같은run의lock-verify만수정했다. 전체18실행의독립대조가필요하여
unspecified-low로배정했고,명령을정확히`runner.py lock`으로수정했다.
학습노드는캐시재사용,학습/입력준비/외부평가재실행없음.
최신TRAIN_VERIFY의실제exit0/18선택/독립검사가통과해야다음DAG를시작한다.

평가단계는 evaluate → independent-verify → analyze → report → report-check의
의존체인으로구성한다(각wave1개,공유산출물을순서대로소비하므로병렬분리하지않음).
evaluate는quick,독립재추론/다른채점구현은여러파일대조가필요한unspecified-low,
오류·관측·학습상태판단은deep-low,한국어보고서는writing,
보고서수치/해석통합검증은unspecified-low로배정한다.
각노드는자기산출물만쓰고,기존runtime source와checkpoint는수정하지않는다.

generation3 잠금검증 PASS를 주담당이 최신TRAIN_VERIFY.md와 대조했다.
실제명령exit0/SELECTION_LOCKED18,모니터mon_1SB5H0H5A9HPF2ZT.
선택잠금SHA256:82b3c7897378690ef0526bd10d20fe7b728217e72a605035b96f27ba099281fa.
budgetsSHA256:3ff0fd51a236e4a74cda0ed857d9de8db2c3e6421897b1e9935300a9e24eb193.
18개고유실행/전체history최소NLL·이른동률/공통초기화/각부분12사건/
1000·1000·800업데이트/각run·입력·source해시대조PASS.
순환별최대선택epoch23/70/15로연장없고모든budget_bound=false.
이전FAIL기록은보존되며최신PASS가복구결과다.

## 활성 평가 단계C

- key: sn-corrected-20261017-evaluation-v1
- run ID: dag_7e7af41b-fc9b-416a-9d8b-eeae3efd19d1
- 구성: evaluate → independent-verify → analyze → report → report-check
- 시작warning0. 산출물: EVAL_EXECUTION.md → VERIFY.md/json →
  ANALYSIS.md/json → REPORT.md → REPORT_CHECK.md.
- 선택된18모델의3부분54예측을저장하고,모두재추론및독립집계한다.
- SN관측감사의root_latency_seconds는관측된1초bin수이며지연값이아니다.
  기존metric_magnitude는예전fold0QA기준이므로설명용으로만해석한다.
- 평가점수·보고서는아직미완료.최종검증PASS후주담당이증거를읽어판정한다.

단계C evaluate(st_01a14912)는54NPZ/evaluation.json과해시정합을확인했지만,
EVALUATION_PASS18 뒤 FileExistsError/exit1 기록의모순으로EVAL_EXECUTION.md FAIL.
같은child를task_send로되살려원래toolcall/종료증거만복구중이다.
평가재실행·출력덮어쓰기·재학습은금지. eval원본의실제exit을추정하지않는다.
독립검증st_01a14913에는원본증거복구와병렬로54예측의읽기전용재추론/독립채점을
진행하도록지시했다. 최종PASS에는숫자검사와producer증거를구분해야한다.
VERIFY.md 최초생성은PENDING이므로완료증거가아니다.
원본영수증변경은mon_SF53KBT96BN84DQ6으로구독했다.
JSsnEvalSettled의sdk.wait가detach되어단계C완료를기다리는중이다.

평가원본증거복구완료: EVAL_EXECUTION.md 마지막Correction절을읽고PASS확인.
첫Python cell에서`await tool.monitor(...)`는동기tool호출을먼저실행한뒤
dict를await하다TypeError였다. child가이를미실행으로오인하여두번째실행을요청했다.
원래child의bash_1은실제completed/exit_code0/EVALUATION_PASS18이며,
bash_2는exist_ok=False보호에서추론전exit1;첫출력덮어쓰기없음.
기존실패판정은역사로보존했고,새평가없이기존bash_output읽기로원인해소.
독립검증child에게최신PASS근거를전달했으며재추론/독립집계계속진행중.

독립검증완료: VERIFY.md/VERIFY.json/verify_results.py를주담당이읽어대조했다.
5fixture테스트exit0,18개checkpoint의54예측재현exit0/VERIFY_PASS18 54.
root/detection logits bitwise일치,labels/event_ids/indices일치,학습전용scaler일치,
독립stable pooling 최대오차2.842170943040401e-14(<1e-12),Top1/3정확히일치.
모델/seed당외부36사건과정상제외/해시/보호경계PASS.
VERIFY영수증에실제명령문과새코드diagnostics근거가빠져child를되살려보완지시했다.
이미통과한재추론과테스트를다시돌리지않는다.
todo30/32완료:남은것은사건별분석및최종보고.
ANALYSIS.md생성대기는mon_9RR69ZSB2RNNV9NT(persistent).

단계C generation1 완료 후 REPORT_CHECK.md/REPORT.md/ANALYSIS.md를읽었다.
분석11테스트/CLI진단0오류경고/ANALYSIS_PASS36 모두실제exit0,
최종검증노드의수치·hash·프로토콜대조PASS. verifier새파일LSP도0건확인됨.
3seed평균 Top1/Top3: Eadro9.2593%/28.7037%,DiagMLP25%/50%,prior8.3333%/25%.
차이(D-E)15.7407pp/21.2963pp;W/T/L12/22/2와17/14/5.
분석은Eadro의검증손실폭증및이른선택,network_delay양방법Top1=2.7778%를확인.
scaling범위밖입력동반가설은후속읽기전용진단제안일뿐아직미실행.

주담당최종읽기에서 REPORT.md의“독립적인 유효 표본36”과“trace가 모두관측”
표현이과도함을발견했다. 사건36개는채점단위지만독립성미확립,
CPU는각장애창에적어도일부trace존재이지전시간bin관측이아니다.
초기R0/R1cwd실패도짧게명시하도록동일phaseC run을generation2로amend했다.
report와report-check만재실행;앞선3노드는완료캐시유지.
수치·source·예측은변경없고테스트/재추론재실행도금지했다.
todo31/32완료,최종보고1개만진행중. 최신REPORT_CHECK추가절통과후완료처리한다.

## 최종 완료 — 2026-10-17

단계C generation2 종료 후 REPORT_CHECK.md의Latest focused report interpretation
check PASS를읽고최신REPORT.md문구와대조했다. 사건독립성·trace관측범위·
초기학습실패공개3건모두수정됐고기존수치검증PASS를재사용했다.
수치·예측·학습을다시실행하지않았다. 미해결산출물결함없음.
최종보고서는 REPORT.md, 상세사건/학습/관측분석은 ANALYSIS.md/json,
전체검증은 REPORT_CHECK.md 및 VERIFY.md/json에있다.
요청된교정평가·실패분석·보고를완료했다.
후속표준화극단값진단과추가모델/학습은제안만남겼으며실행하지않았다.

## 다음 단계

단계A PASS후새DAG:
train-r0 + train-r1 + train-r2 → lock-verify.
각순환내부에서200epoch검증선택이180이상인실행이있으면그순환6개전부400으로1회연장.
선택잠금이후새DAG:
evaluate → independent-verify → analyze → report → report-check.
DAG_PLAN.md의범위와검증계약을따른다. 준비/학습단계전체를한run으로합치지않는다.

기존등록목표는SN선택대기로blocked표시가남아있지만사용자선택과실행지시로사유해소.
create_goal은미완료기존목표때문거부됐다. 기존목표를완료로가장하거나새선택질문을하지않는다.
현재DAG는기존등록목표에결합되어정상시작했다.
실제학습/평가/검증/보고를마칠때해당목표완료를처리한다.

JS kernel: snDagSdk, snGateDag, snGateRun, snTrainDag, snTrainRun, snGateBase, snExecRoot, snExecPlanHash.
재시작시같은run을attach/snapshot하고완료노드는캐시를재사용한다.
