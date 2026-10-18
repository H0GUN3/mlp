# phase3 — 독립 채점과 사례 변화

## Goal

phase2 EXECUTION_VERIFY의 최종 PASS와 실제3개exit0를 부모가 확인했다.
이 phase는 저장 validation예측 분석이며 새학습/추론/전처리는 없다.
사용자4산출물: 설정표, 입력차이요약, seed점수표, 새정답/새오답목록을 완성한다.
phase1/2의 유효증거는 재사용하며 실패이력과 수렴미확인 경고를 보존한다.

## 대조 방향

- before_absolute: 이번 runs/absolute_seed_{11,23,37}/.
- after_relative: 기존 native_reproduction_20261013/calibration200/SN/diagmlp/
  seed_{11,23,37}/.
- delta=relative-absolute. before는 source horizon의 국소 대조이며 실제
  원저자 전체구현이나 이전 연구의 평가결과를 뜻하지 않는다.
- selected checkpoint는 양쪽 동일한 validation joint loss 최소/이른동률.
  학습예산200epoch400update, 같은 windowlabels/services/seed/shuffle/scaler.

## 분석

1. 6개의 validation_predictions.npz만 allow_pickle=False로 열고 hash/indices/
   labels/order를 대조한다. selectedinputs를 다시 열 필요는 없다.
2. fault65/normal13을 구분하여 conditionalTop1/3, gatedTop1/3, 탐지P/R/F1.
   동률은 균등기대credit, ensemble금지. seed별과3seed평균, 각분모명시.
3. 각faultwindow와seed별 absolute/relative root후보·정답credit·탐지·joint
   변화. 4정오조합, tie있으면fractional변화별도. 195window-seed는독립사건아님.
4. validation 원본index를metadata의허용창/event/start/root/fault에매핑.
   새정답/새오답전체CSV, distinctwindow/event/seed집계, 동일사건seed일관성.
   사건확률평균으로새주지표를만들지않는다. normal탐지변화는별도.
5. history의epoch1/50/200·선택epoch·최소jointloss를서로비교하고,
   모델선택범위와oldbaseline실행환경동등성은phase2증거를인용한다.
6. 입력차이는existinginputs/preparation.json의요약·경고·상한도달을활용.
   로그feature변경과출력변경은사실,구체오류원인/최적수렴/일반화는추가증거없이단정금지.

## DAG와 소유

- analyze unspecified-low: analyze_horizon.py, test_analyze_horizon.py,
  analysis/JSON·CSV·실행로그, ANALYSIS_CHECK.md.
  동일6예측에서점수와사례를함께계산해중복생산을피한다.
- verify unspecified-low (analyze의존): ANALYSIS_VERIFY.md.
  생산코드를호출하지않고별도단순계산/원근거로주점수와pairedcount독립확인.
- report writing (verify의존): REPORT.md.
  PASS근거와남은한계를한국어로설명. 유리/불리/효과미확인모두허용.
총3노드의실제의존DAG. 추가에이전트·주제확대금지.

최소fixture: 정확동률/정상제외/순서틀림거부/paired4조합.
새분석코드CLI진단과실제exit0확인. 기존학습재실행금지.
artifacthash재검은선택예측·config/history/summary만;원본rawhash재순회불필요.
실제데이터접근은6validation예측과작은메타/요약으로한정한다.

run_id: `dag_d82f42a8-b7f1-4f41-907e-2d1c9e502845`
key: `sn-hawkes-horizon-analysis-20261017-v1`
3노드 시작, warnings0. 종료시 ANALYSIS_VERIFY와 REPORT를 부모가 확인한다.
