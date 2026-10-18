# Goal — 기존 변경 하나의 효과 대조

사용자 최신 mass-ulw 요청은 현재 결과 보존→변경 하나 대조→점수와 새 정오
변화 확인이다. 이전 분석 전용/실험 중지 범위를 이 대조에 한해 갱신한다.
현재 후보 X는 로그 Hawkes 관측 horizon: 우리 relative10 vs 공개 수리 포크의
relative knots + absolute e+1이다. 입력값·학습·선택·예측의 변경을 확인하되,
DiagMLP 저자 실험을 복구했거나 독립 제안법을 입증했다고 부르지 않는다.
새 이름·원인·유리한 효과를 미리 확정하지 않는다.

옛 goal 도구는 중단된 미완료 실험으로 묶여 새 등록이 거절된 기록이 있다.
이를 거짓 완료하지 않는다. 본 Goal과 최신 사용자 범위가 이번 DAG들을 제한한다.

## 전체 결과물

1. 변경 전후 설정표: source commit, 모든 공통 조건과 X만의 차이.
2. 실제 입력값 차이: 형태·finite·희소성·분포·노드/창별 대응. metric/trace,
   labels/index/services/template order는 같아야 한다.
3. seed11/23/37 성능·학습이력·선택 epoch 표. SN200 기준 200epochs/Adam.001/
   batch256/동일 shuffle/초기값/joint loss/min validation loss 정책 유지.
4. 동일 validation 표본에서 새 정답/새 오답/양쪽정답/양쪽오답 목록과
   창·사건·seed의 구분. conditional windowTop1 주, Top3/gated·탐지 보조.
5. 실제 exit0, focusedtests, 독립채점/선택·예측 대응, 변경된 경로만 재검증.

## phase 1 — 보존·대조 가능성 검증 (현재 run)

세 병렬 조사 → 통합 GATE.md. 현재 phase는 코드/JSON metadata/기존 증거만 읽는다.
새 실제 입력 적합·학습·예측 생성은 이 gate 후 별도 DAG phase에서 시작한다.
- registry quick → REGISTRY.md: 기존 baseline조건과 재사용 파일/해시 연결.
- contrast quick → CONTRAST.md: 소스 horizon의 정확한 의미와 단일 변수 규약.
- access unspecified-low → ACCESS.md: 보호값 decode 없이 선택 입력/로그만
  재사용할 수 있는 구체 경로와 제약. 코드를 연결해 판단하므로 이 분류.
- gate unspecified-low (세 보고 의존) → GATE.md: 시작 가능한 계약/차단조건 판정.
쓰기 소유 범위는 각 Markdown 하나다. 추가 자식 에이전트 생성 금지.

## phase 2 — 허용 입력 생성·대조 학습 (아직 미시작)

gate PASS 확인 뒤 그 결과에 맞춰 새 DAG를 정의한다. 새 독점 디렉터리 내
선택 loader+변경 horizon 특징 생성+focusedtests → seed별 대조 학습 → 실행검증.
합리적인 소규모 비용 probe와 상대horizon 재생성 일치 검사를 먼저 수행한다.
native_data/native_train.load_inputs/load_prepared는 full raw/prepared를
decode하므로 직접 호출하지 않는다.
기준 relative arm은 유효한 기존 SN200 결과를 재사용한다. 호환성을 확인하지
못하면 원인을 보고하며 근거 없이 같은 arm을 중복 학습하지 않는다.

## phase 3 — 독립 결과 분석 (아직 미시작)

새 run으로 independent scoring/paired error analysis/한국어 report를 수행한다.
판정은 유리/불리/효과 미확인 모두 허용. 버그 동작 대조는 역사적 처리의
교정 효과 점검이지, 잘못된 평가를 baseline에만 적용한 성능 경쟁이 아니다.
TT 확대·새 데이터·추가 모듈은 결과 보고 후 별도 판단하며 자동 추가하지 않는다.

## 고정 경계

- 시스템 SN, 기존 train316/validation78(장애65)만 사용. test169+unassigned1
  관측/예측은 decode·분석하지 않는다. TT/RE2 관측도 접근하지 않는다.
- 메타데이터의 index/시각/shape/기존hash는 접근 가능. 보호 배열이 섞인
  파일은 행 선택 전에 전체 ndarray로 적재하지 않는다. 스트림 byte skip은
  관측값 해석/decode와 분리해 기록하며, 읽기 범위를 거짓 주장하지 않는다.
- phase1은 metadata/source/text만. full raw/NPZ/events나 checkpoint 역직렬화 금지.
- 원본·동결 코드·기존 결과를 수정/덮어쓰기하지 않는다. 새 파일은 apply_patch.
- 설치·다운로드·프로젝트 commit·다른 연구 재개 금지.
- fittedDrain templates/정규화는 기존 합법적 TRAIN 정상참조/통계를 고정한다.
- knots·dummy[0]·jitter·seed42+originalWindow*N+node·decay3/defaultsolver50/
  initialbaseline.2·빈 그룹0·10초 half-open선택은 동일. 차이는 end_times뿐이다.
  실제 source 전체 처리의 재현이 아니라 horizon-only대조로 명시한다.
- 선택을 새 horizon에서 안정시키려 clipping·재정규화·학습률 변경을 몰래
  추가하지 않는다. finite실패/시간상한이면 실제 실패를 보존하고 보고한다.
- 긴 실행은 monitor timeout_ms1800000 명시. 최대3모델동시/CPU2threads;
  Hawkes최대2worker/각1thread. 비싼 full실행 전 probe 비용 확인.

## 근거

공개 source:
FeiGSSS/Eadro 7d69281a80adce60067aa858729746fc6a362f53
codes/preprocess/single_process.py의 deal_logs/logHaw: knots=timestamp-s, end_time=e+1.
우리 native_data.py:456–507: 같은 relative knot 기준 end_times=LENGTH(10).
SN50→SN200 +5.64%p는 완료 근거이며 재실험하지 않는다.
기존 감사의 raw전체선로딩과현재보호경계를혼동하지않는다.

## 현재 run

phase1 run_id: `dag_4d199123-c59f-4622-a480-79bcbdfb011a`
key: `sn-hawkes-horizon-preservation-20261017-v1`
4노드, warnings0. 종료시 GATE/근거 확인 후 phase2를 새run으로 정의한다.
전체 사용자 요청은 실제 대조 결과까지이며, phase1 문서 완료로 끝내지 않는다.
