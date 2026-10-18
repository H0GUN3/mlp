# 정본 실행 경로와 중복 방지 — 2026-10-18

이 폴더는 요청 직후 작성한 근거 확인 메모다.
새 DAG, 원시 재검사, 전처리, 모델 학습은 이 폴더에서 시작하지 않았다.

같은 사용자 요청의 단일 대조가 다른 담당 세션에서 이미 준비 중임을 확인했다.
**정본 실행 경로는 `../sn_call_target_contrast_20261018`이다.**
이 폴더의 첫 DAG 초안은 별도로 실행하지 않으며 정본 프로토콜을 대체하지 않는다.
정본 source·protocol·input·runner 파일은 수정하지 않는다.

## 읽기 전용으로 확인한 근거

- PROTOCOL.md: TRAIN CHILD_OF로 확인한 `(owner, exact operation)`의
  destination만 바꾸고 unknown/nonclient는 owner에 유지한다.
  새 채널·span 삭제·추가·dedup·duration/time 변경은 없다.
- attribution_cases.json: index112의 compose client와 media server가 같은
  trace에서 직접 CHILD_OF로 연결된다. index115는 같은 창의 server child가
  없어 직접 연결을 확인하지 못했다. 둘을 동일한 증거 수준으로 쓰지 않는다.
- attribution_sources/AUDIT.md: 논문의 callee 평균 명세와 공개 수정 포크의
  owner 집계, 원저자 전처리 확인 한계를 구분한다.
- inputs/preparation.json: 읽은 시점의 status PASS, producer exit0.
  TRAIN mapping 동결 후 validation 집계, media TRAIN support,
  모든394행 기존 owner trace exact 재현, metrics/logs/labels/indices 보존,
  occurrence·duration sum 보존, channel1=0, protected model rows0를 기록한다.
  공유 raw JSON의 바이트·구조 파싱은 접근 disclosure와 별개로 구분한다.

이것은 정본 입력 준비 산출물의 확인이며,
후속 model preflight·학습·재추론·독립 점수 검증 완료를 의미하지 않는다.

## 소유권과 알림

정본 담당이 candidate preflight와 seed11/23/37의200epoch 학습을 소유한다.
이 세션에서 중복 producer·runner·fit을 시작하지 않는다.
다른 세션의 child `st_01a14e87`는 이 세션에서 조회할 수 없었고,
교차 세션 메시지도 resident session 부재로 전달되지 않았다.
따라서 그 child를 재생성하거나 수정하지 않는다.

정본 REPORT.md 발행 알림:
`mon_5BV7GCZ2KJR0YK7J` / `watch_3` (읽기 전용 create watch).
알림이 오면 실제 결과와 검증 증거를 읽는다. 파일 생성 자체를 성공으로
취급하지 않고, 기존 담당이 완료하지 않은 일을 완료했다고 보고하지 않는다.

RE2 보류, 기존 SN50/SN200 보존, 단일 변경·고정 예산·추가 실험 금지 경계는 유지한다.

## 최종 완료 증거 확인

REPORT.md 생성 알림 후 정본 REPORT.md와 EXECUTION.md를 읽었다.
세 seed 모두 실제 exit0,200epoch/400update,50/200 선택본6개의 bitwise
예측 replay와 exact loss replay가 기록돼 있다.
독립 평가 `mon_XKVSHD5WSK2A5AVC`는 실제exit0과
`CALL_TARGET_EVALUATION_PASS 390`을 기록했다.
RESULTS.json status PASS와390개 대응 기록, 모든 종류별 Top1/Top3,
정오답 전환 및 사건별 window-hit 변화 수를 보고서와 대조했다.
이 세션에서 학습·추론·재채점은 재실행하지 않았다.

핵심 결과는50epoch 전체Top1 89.74→90.26%, 지연80.56→83.33%;
200epoch 전체95.38→95.38%, 지연93.06→91.67%다.
50의 지연 순증은 한 seed에만 있고,200에서는 지연 정답이 감소했다.
일부 media 사례의 개선은 다른 사례의 악화로 상쇄됐다.
이 destination-only 후보를 일관된 개선법으로 채택할 근거는 부족하다.
호출 정보의 모든 활용이 무효라는 결론은 아니다.

정본 보고서는 결과와 검증을 완료했으며 이 단회 대조는 종료한다.
위 watch는 파일 생성으로 정상 완료됐다. 새 monitor·worker·후속 실험은 시작하지 않는다.
