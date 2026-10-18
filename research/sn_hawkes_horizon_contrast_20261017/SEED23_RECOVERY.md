# Seed23 중단 복구 — 같은 조건 재시작

FIT_23.md의 실제 기록: 과거 “대기하지 마” 지시를 하위 에이전트가
현재 승인된 monitor 실행에 잘못 적용해 producer를 중단했다.
19epoch/38updates의 partial이며 실제 정상 종료가 아니다.
과거 중지는 이번 명시적 실험 요청으로 이 범위에서 갱신됐으므로, 현재
실행이 오래 걸린다는 이유로 취소하지 않는다.

부모가 다음 디렉터리를 원자적 rename으로 보존했다. 파일 내용은 바꾸지 않았다.
`runs/absolute_seed_23` → `runs/absolute_seed_23_interrupted_attempt1`
config/history/checkpoint/validation_predictions 네 파일을 보존했다.
summary는 없음을 확인한 뒤에만 이동했다. 목적 경로가 있으면 중단하도록 했다.

동일 script/hash·inputs·preflight·seed23·초기화·200epoch 조건으로
`runs/absolute_seed_23`을 새로 생성해 다시 실행한다.
이 재시작은 중단된 부분 실행의 복구이며 새 실험 조건이 아니다.
완료 seed11/37, 입력 preparation, preflight는 재실행하지 않는다.

완료 후 두 이력의 첫19epoch 수치(시간 필드 제외)를 대조한다.
새 결과가 정상 exit0/200epoch/400update/선택·replay 검증을 통과하기 전에는
phase3로 넘어가지 않는다. 최초 중단 기록은 FIT_23에 이력으로 남긴다.
