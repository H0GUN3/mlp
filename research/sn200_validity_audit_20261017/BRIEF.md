# Goal — SN200 기준선의 실험 타당성 감사

사용자가 mass-ulw로 요청한 네 항목에 한정한다. 이는 새 감사 권한이며
이전 효율/오류 개선 실험의 재개가 아니다. 새 학습·추론·전처리·수정은 금지.
기존 goal은 중단된 옛 실험의 unfinished 상태여서 새 등록이 거절된 기록이 있다.
이를 거짓 완료 처리하지 않는다. 이 Goal 블록과 최신 감사 요청이 실행 범위다.

## 요구와 완료 기준

1. 학습/검증 index·창 identity·시간구간 중복, 같은 사건/recording 공유를
   각각 수치와 근거로 구분한다. 메타데이터로 증명 가능한 범위와 원시
   identity를 다시 보지 않아 미확인인 범위를 분리한다.
2. scaler/Drain/특징 적합이 무엇을 사용하는지 추적한다. 평가 창 자체의
   관측을 사용하는 결정적/창 로컬 특징 계산과 전체 학습 통계 적합을 구분한다.
   정답·사건/주입 설정이 관측값·candidate 선택·feature/model로 들어가는지 확인한다.
3. checkpoint와 config/history/summary/hash의 연결, 엄격한 validation
   최소손실/동률 정책, SN50/200 첫50epoch 근거, eval/no_grad 경로,
   test의 선택/평가 여부를 확인한다. 유효한 기존 replay 증거는 재사용한다.
4. 서비스 이름/정답 번호/출력 열,78검증행 중65장애행,seed별 평균과
   ensemble의 구분, conditional/gated/정상분모, 누락/중복을 대조한다.
   필요한 경우 명시적으로 허용한 저장 validation_predictions.npz를 독립 채점한다.
5. 최종 분류: 확인된 구현/프로토콜 오류, 의도한 평가의 한계, 검사 범위에서
   문제 미확인, 추가 자료가 필요한 미확인 항목. 높은 점수 자체를 오류로
   판단하지 않고 23.59 vs95.38 차이를 누출 탓으로 단정하지 않는다.
6. 기존6요구PASS는 문서 검증이지 실제 파이프라인 전체 정당성 증명이
   아니었음을 명확히 한다. 감사 결과는 새 모델 성과나 최종시험 성능이 아니다.

## 접근 허용과 금지

읽기 허용:
- research/native_reproduction_20261013/의 소스·Markdown·검증/오류 요약 JSON.
- native_inputs/SN/metadata.json 등 스키마·서비스·창·사건 메타데이터만.
  보호행의 index/시간메타를 경계 검사에 사용할 수 있으나 관측값은 금지.
- calibration200/SN/diagmlp/seed_{11,23,37}/의 config/history/summary/split JSON,
  명시적 validation_predictions.npz. calibration50의 대응 JSON/기존 검증 증거.
- 명시된 모델 산출물의 파일 hash 계산은 가능. checkpoint 역직렬화/추론은
  하지 않고 기존 bitwise replay 검증을 재사용한다.

금지:
- raw.npz, inputs.npz, raw telemetry, 보호 시험 관측/예측, RE2 관측 열기.
- native_train.load_inputs 또는 기존 전체 verifier 실행: 보호행까지 읽는 경로가
  있으므로 실행하지 않는다. 기존 연구 Python 모듈 import 금지.
- 학습·재추론·재전처리·모델/분할/원본 수정·다운로드/설치·project commit.
- 스코어가 높다는 이유로 새 사건분할이나 신규일반화 목표를 채택하는 것.
- 하위 에이전트 추가 생성.

검증 NPZ 독립 채점이 필요하면 정확한 파일 allowlist와 allow_pickle=False를
쓰고 indices를 해당 split.validation과 대조한 뒤 numpy로만 계산한다.
수치 예측 열람은 read가 지원하지 않는 형식이므로 이 지정 파일만 파싱 가능.
모든 텍스트/코드는 read로 검사하고 새 파일은 apply_patch로 만든다.
단순 JSON/metadata 산술은 메모리에서 가능하며 수행식·결과·한계를 문서에 남긴다.
신규 검사 실패는 숨기지 않고 연구 코드 변경 없이 보고한다.

역사적 native_train.load_inputs가 full raw.npz를 읽는 동작과,
fit_scaler의 train index 선택, train/validation만 실제 model에 전달되는지를
분리한다. 과거 test 행 메모리 접근 없음이라는 표현을 근거 없이 반복하지
않는다. 전체 로딩만으로 학습 누출/점수 오염이 증명되는 것도 아니다.

## DAG와 파일 소유

4개 병렬(최대4) → verify → report. 6노드, 한 감사 단계.
- boundary quick: BOUNDARY.md
- preprocessing unspecified-low: PREPROCESSING.md (원천에서 모델까지 적합/정보경로)
- selection quick: SELECTION.md
- scoring quick: SCORING.md
- verify unspecified-low: VERIFY.md (네 결과의 교차 모순·근거 범위를 통합 판단)
- report writing: REPORT.md (검증된 사실만 한국어로 설명)
생산파일은 각 소유자만 쓴다. 검증자는 수정하지 않고 정확한 소유자에게 FAIL을 낸다.
최종 report는 VERIFY의 PASS뿐 아니라 논쟁/미확인도 보존한다.
부모가 VERIFY/REPORT를 읽고 완료를 판정한다. 실제 결함 발견은 감사 실패가
아니며, 결함을 숨기거나 검사했다고 거짓 주장하는 것은 감사 실패다.

## 실행

run_id: `dag_cd42f909-bdf4-4f2b-a081-d4591ab9d2f5`
key: `sn200-validity-audit-20261017-v1`
6노드 정의 검사 warnings0. 종료 알림 후 VERIFY/REPORT를 확인한다.
동일 DAG를 중복 시작하거나 이전 실험을 재개하지 않는다.
