# Goal

사용자가 승인한 제한된 개발 후속 실험을 실제 실행하고, 결과를 증거로 검증한 뒤
관계 문맥 방향을 더 확장할 가치가 있는지 한국어로 보고한다.
상세 실행 범위와 판정은 결과 확인 전에 작성한 [PROTOCOL.md](PROTOCOL.md)를 따른다.

기존 thread goal은 RCABench 검수 종료 후 보류 로드맵 처리 결정을 기다리는 blocked 상태였다.
새 goal 등록은 unfinished goal 때문에 도구가 거절했다. 이를 완료로 허위 전환하지 않는다.
이번 사용자 추가 지시와 이 계약을 기존 등록 목표의 후속 범위로 기록하고,
이전 로드맵은 DEFERRED.md로 보존한다. 기존 goal의 새 학습 금지는 이번에 명시한
54개 제한 실행에 한해서만 사용자의 진행 지시로 갱신한다.

## 실행 phase: 위상과 소유권

최상위 구성요소는 ①학습 실행 ②독립 재추론 검증 ③통계 집계다.
기존 집계 구현 child가 맡은 analysis.py/test_analysis.py 작업은 중복 생성하지 않는다.

| wave | 노드 | category | 의존성 | 쓰기 범위 |
|---|---|---|---|---|
| 1 | fit | quick | 없음 | 실행기가 생성하는 results/ 학습 산출물, FIT_EVIDENCE.md |
| 2 | replay | quick | fit | 실행기가 생성하는 results/verification.json, REPLAY_EVIDENCE.md |
| 2 | summarize | quick | fit | 집계기가 생성하는 results/analysis.json, ANALYSIS_EVIDENCE.md |
| 3 | verify | unspecified-low | fit, replay, summarize | VERIFY_EVIDENCE.md |

최대 wave 폭2로 기본 동시 실행 한도5 이내다. wave2의 두 경로는 파일 쓰기가 겹치지 않는다.
첫 wave는 단일 학습 실행을 원자적으로 보존하려고 분할하지 않는다.
verify는 체크포인트 재생·집계 provenance·고정 판정이 서로 맞는지 판단해야 하므로
기계적 단일 명령보다 한 단계 높은 unspecified-low를 사용한다.
전체 연구 로드맵은 이 run에 포함하지 않는다. 보고서는 이 run의 근거 확인 후 작성한다.

## RESULT VERIFICATION

노드나 run의 완료 주장은 아래 근거를 대조하기 전에는 사실로 취급하지 않는다.

1. 실제 집중 테스트 PASS와 명시적 Pyright exit0.
2. 학습 명령 exit0, `CV_RUN_COMPLETE 54`, 유일한54개(system,fold,seed,mode),
   각5epoch, 원본·소스 hash 불변, 보호자료 접근 플래그 false.
3. 별도 프로세스 exit0, `CV_VERIFY_COMPLETE 54`, predictions와 checkpoint 재추론
   및 독립 Top1 scorer 일치; verification.json source/input hashes 일치.
4. 통계 집계 명령 exit0, analysis의 입력 runs.json 및 집계 코드 hash 일치,
   사건수 SN36/TT81(시드로 증식하지 않음), recording수4/9,
   고정 판정 기준과 저장 수치 일치.
5. 보고서 숫자는 저장 JSON에서 가져오며 개발 한계·생략 범위를 명시한다.

실패하면 해당 노드의 증거를 읽고 필요한 노드만 retry/amend한다.
이미 생성된 학습 결과는 덮어쓰지 않는다. 단순 시간 경과로 중복 실행하지 않는다.
