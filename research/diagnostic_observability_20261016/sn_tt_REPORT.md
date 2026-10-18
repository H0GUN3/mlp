# SN/TT 허용 개발 관측·18특징 정보 손실 감사

2026-10-16. RCABench 작업과 독립된 **개발 자료 감사**다. 새 학습·추론·최종시험은 없다.

## 1. 문제 상황과 감사 목적

목표는 같은 시스템의 미학습 장애 사건에서 원인 서비스를 찾는 것이다.
그 전에 **후보 서비스가 실제로 무엇을 관측했는지**, 18개 요약 특징이
무엇을 지웠는지, 사건을 나눠도 무엇이 공유되는지 구분해야 한다.
필드 존재 → 관측 범위 → 구별 단서 → 인과적 확정은 같은 주장이 아니다.

핵심 결과:

- TT 27개 후보 중 **14개 서비스는 허용 개발 구간 전체에 trace 지연 관측이 0**이다.
  이들 역시 root 정답으로 등장한다: 42사건, 1,779개 장애 창.
- SN 394개·TT 4,069개 실제 창 모두 비상수다. 원인 서비스만 보아도
  SN 325/325·TT 3,451/3,451개 장애 창이 비상수다.
  이들을 역순·순열로 바꾸면 관측은 바뀌지만 **18특징·mask·coverage는 불변**이다
  (부동소수점 허용오차 아래). 따라서 시간 순서 손실은 실제 자료에서도 확인된다.
- 이것은 **표현의 비단사성** 증명이다. 지워진 순서가 원인을 식별하거나
  성능을 개선한다는 증거는 아니다.
- 모든 서비스는 주입 사건 3개만 갖고 root×장애종류 조합마다 1사건뿐이다.
  13개 recording 모두 holdout하면 root 3개가 동시에 cold-root가 된다.
  따라서 recording holdout으로 환경 변화만 분리할 수 없다.

## 2. 입력·출처·경계

직접 연 관측은 다음 네 파일뿐이다.

| 시스템 | 허용 NPZ SHA-256 | 관측 배열 |
|---|---|---|
| SN | `1519a69e10aaa402fb88bf0fbe027502610bfaaa0dfd4c7b37ff4f44f3400efb` | `values/observed`: 394×12×10×9 |
| TT | `4e568299514f10f247c0b2496e3392a6457825844e2145ad3df36b13c9cd9cff` | `values/observed`: 4069×27×10×9 |

경로는 `research/relationship_smoke_20261013/artifacts/{SN,TT}.{npz,json}`.
NPZ에는 `values, observed, x, mask, coverage, adjacency, indices, labels,
event_ids, episode_ids, fold_ids, partition`이 있다.
`x/mask/coverage`는 각각 창×서비스×18, adjacency는 창×caller×callee다.
기존 JSON의 NPZ hash와 고정 hash를 모두 검사했다.

그 밖에 지정된 `trace_preflight.json`, `PREFLIGHT_REPORT.md`,
`relationship_diagnosis_20261014`의 보고서/metadata,
`method_mlp_20261013`의 features/ranker 코드·특성 구현 기록만 이용했다.
`sn_tt_audit.json.inputs_sha256`는 읽은 입력들의 SHA-256,
각 시스템의 `bundle_provenance/source_hashes_recorded/raw_hashes_recorded_only_not_reopened`는
기존 출처 사슬을 보존한다. **기록된 원자료 hash를 재검증하려고 원자료를 열지 않았다.**
NPZ의 original index가 기존 seed42 TRAIN+validation에만 속함을 metadata로 검사했다.
원 native test/unassigned 관측, 전체 stream, `native_inputs/raw.npz`,
RCAEval/RCABench 관측은 열지 않았다.

## 3. 실제 채널 관측의 이질성

9개 채널 순서:
`cpu_usage_system, cpu_usage_total, cpu_usage_user, memory_usage,
memory_working_set, rx_bytes, tx_bytes, trace_mean_duration_seconds, retained_span_count`.

- **7개 metric:** 모든 서비스·허용 초에서 observed=true. 원래 준비 코드의
  유한 수치·연속 초·전체 recording coverage 검증 계약을 물려받는다.
  이번에는 해당 CSV를 다시 열지 않았다. 관측 mask가 모두 참이라는 사실은
  계측기 완전성·고장 민감도를 입증하지 않는다. 0은 결측으로 바꾸지 않았다.
- **latency:** retained count>0인 초만 observed. 서비스별 편차가 크다.
  전체 초 기준 SN 14,332/47,280(30.31%), TT 7,910/1,098,630(0.7200%).
  span 있는 서비스×창은 SN 3,635/4,728, TT 7,692/109,863.
- **count:** 모든 초 observed이며 0도 유효한 retained occurrence 집계다.
  요청 수·수집기 건강을 뜻하지 않는다. TT의 위 14개 서비스는 count도 항상 0이다.
- **정상 참조:** fold0 정상 TRAIN으로 계산한 참조를 기존 JSON과 정확히 대조했다.
  SN은 9채널 모두 참조 가능. TT는 위 14개 서비스의 latency 참조만 없다.
  따라서 해당 두 latency 요약 특징은 항상 mask=false, x=0이다.
  count=0 참조는 존재하므로 latency 미관측과 count 결측을 혼동하지 않는다.
- `sn_tt_audit.json.services`에는 모든 서비스의 9채널별 관측 초 수,
  관측된 0의 수, 비상수 창 수, 참조 mask와 18개 유효특징 창 수가 있다.

아래 표의 root in/out은 root 정답인 창에서 관측된 incoming/outgoing edge의 존재 횟수다.
양방향 창은 양쪽에 들어가므로 두 수를 합쳐 union으로 쓰면 안 된다.
모든 서비스의 root 사건 수는 각각 3개다.

### SN

| 서비스 | 지연 관측 초/가능 초 | span 있는 창/전체 창 | root 창: 지연 있음/전체 | root in/out 창 |
|---|---:|---:|---:|---:|
| social-graph-service | 2115/3940 | 358/394 | 20/25 | 18/12 |
| compose-post-service | 786/3940 | 283/394 | 21/28 | 19/19 |
| post-storage-service | 1219/3940 | 311/394 | 21/31 | 21/0 |
| user-timeline-service | 710/3940 | 271/394 | 16/25 | 12/0 |
| url-shorten-service | 690/3940 | 266/394 | 13/23 | 13/0 |
| user-service | 2257/3940 | 378/394 | 20/25 | 18/0 |
| media-service | 693/3940 | 266/394 | 19/27 | 18/0 |
| text-service | 698/3940 | 269/394 | 17/26 | 16/16 |
| unique-id-service | 687/3940 | 264/394 | 21/30 | 21/0 |
| user-mention-service | 699/3940 | 270/394 | 24/28 | 23/0 |
| home-timeline-service | 1228/3940 | 316/394 | 12/27 | 12/7 |
| nginx-web-server | 2550/3940 | 383/394 | 21/30 | 0/17 |

### TT

| 서비스 | 지연 관측 초/가능 초 | span 있는 창/전체 창 | root 창: 지연 있음/전체 | root in/out 창 |
|---|---:|---:|---:|---:|
| ts-assurance-service | 553/40690 | 553/4069 | 12/131 | 0/0 |
| ts-auth-service | 574/40690 | 571/4069 | 16/127 | 0/10 |
| ts-basic-service | 591/40690 | 587/4069 | 21/122 | 18/18 |
| ts-cancel-service | 0/40690 | 0/4069 | 0/134 | 0/0 |
| ts-config-service | 0/40690 | 0/4069 | 0/121 | 0/0 |
| ts-contacts-service | 617/40690 | 600/4069 | 18/129 | 10/0 |
| ts-food-map-service | 0/40690 | 0/4069 | 0/127 | 0/0 |
| ts-food-service | 0/40690 | 0/4069 | 0/129 | 0/0 |
| ts-inside-payment-service | 0/40690 | 0/4069 | 0/138 | 0/0 |
| ts-notification-service | 0/40690 | 0/4069 | 0/118 | 0/0 |
| ts-order-other-service | 567/40690 | 567/4069 | 17/129 | 12/0 |
| ts-order-service | 624/40690 | 604/4069 | 21/139 | 9/8 |
| ts-payment-service | 0/40690 | 0/4069 | 0/127 | 0/0 |
| ts-preserve-service | 604/40690 | 595/4069 | 24/132 | 0/16 |
| ts-price-service | 0/40690 | 0/4069 | 0/135 | 0/0 |
| ts-route-plan-service | 0/40690 | 0/4069 | 0/135 | 0/0 |
| ts-route-service | 614/40690 | 591/4069 | 28/125 | 26/0 |
| ts-seat-service | 0/40690 | 0/4069 | 0/132 | 0/0 |
| ts-security-service | 585/40690 | 580/4069 | 17/128 | 9/8 |
| ts-station-service | 717/40690 | 638/4069 | 16/127 | 15/0 |
| ts-ticketinfo-service | 596/40690 | 589/4069 | 16/122 | 13/13 |
| ts-train-service | 0/40690 | 0/4069 | 0/109 | 0/0 |
| ts-travel-plan-service | 0/40690 | 0/4069 | 0/125 | 0/0 |
| ts-travel-service | 680/40690 | 639/4069 | 31/129 | 0/19 |
| ts-travel2-service | 0/40690 | 0/4069 | 0/121 | 0/0 |
| ts-user-service | 0/40690 | 0/4069 | 0/128 | 0/0 |
| ts-verification-code-service | 588/40690 | 578/4069 | 17/132 | 11/0 |

## 4. root–caller/비root 대비에서 가능한 것과 불가능한 것

graph는 **같은 허용 10초 창 안에 시작하는 CHILD_OF caller→callee**의
binary 서비스 관계다. span identity 중복은 graph에서 제거하지만 duration/count에는
기존 중복 가중치가 남는다. 다른 창의 parent, 관측되지 않은 호출, edge별 지연·상태는
이 graph에 없다. edge 부재는 호출 부재나 인과관계 부재를 뜻하지 않는다.

| 장애 창 대비 | SN | TT |
|---|---:|---:|
| root latency 있는 창 | 225/325 | 254/3451 |
| root incoming 있는 창 | 191/325 | 123/3451 |
| root outgoing 있는 창 | 71/325 | 92/3451 |
| 양방향 창 | 51 | 42 |
| root 인접 edge union | 211/325 | 173/3451 |
| 사건 동등가중 root 인접 비율 | 64.5700% | 4.9780% |
| 사건 동등가중 root latency 존재 비율 | 68.9191% | 7.2719% |

union 횟수는 기존 `errors_root_context.json`의 117사건과 재대조했다.
원인 서비스 이외 후보의 **피해 여부 라벨은 없다**. 따라서 실제 caller/callee를
기술할 수는 있지만 비root=피해 서비스라고 확정하거나 전파 인과를 부여할 수 없다.

보조 대조로 각 서비스의 7개 metric signed-log-z 평균 특징의 절댓값 평균을 계산했다.
root 값이 최강 비root 값 이상인 창의 **사건 동등가중 비율**은
SN 40.2525%, TT 47.7804%다(동점 포함). 각 창의 root·최강 비root 크기,
caller/callee 목록 및 그 metric 크기 평균은 JSON `root_contrasts.windows`에 남겼다.
이는 fold0 QA 참조를 쓴 사후 기술량이지 새로운 진단기·성능 평가가 아니다.
root가 가장 크게 흔들리는지와 원인인지가 같지 않다는 문제를 살피는 대비이며,
비root의 큰 변화가 실제 피해라는 주장도 하지 않는다.

## 5. 18특징이 실제로 지우는 시간정보

기존 `features.py.fit_reference/window_features`를 AST로 추출해 사용했다.
모듈 전체를 import하면 native helper를 불러오므로 원본 로더는 실행하지 않는다.
정상 TRAIN 관측만으로 median과
`scale=max(IQR, 0.05*abs(median), 1e-8)`를 재계산했다.
참조의 median/scale/count/mask와 저장된 fold0 JSON은 **모두 정확히 일치**했고,
원래 `x/mask/coverage`도 **정확히 재현**했다. 모델 적합은 없다.

채널별로 유효 관측만 사용해 다음 두 수를 만든다.

```text
z(t) = (value(t) - normal_train_median) / normal_train_scale
change = mean(sign(z(t)) * log(1+abs(z(t))))
persistence = fraction(abs(z(t)) > 2)
9채널 × 2요약 = 서비스당 18수치
mask = 현재 관측 존재 AND 정상 TRAIN 참조 존재
coverage = 관측 초 수 / 10
```

시간 인덱스에 대한 합과 개수뿐이므로, 값과 observed를 함께 순열하면 같은 결과다.
90개 값→18개 값이라는 것은 **수치 슬롯 수** 비교이며 정보량 bit/손실률이 아니다.
mask와 coverage도 별도 입력이다. 이들 역시 순열불변이므로 순서를 복원하지 못한다.

비상수는 관측 초가 2개 이상이며 그 값의 max>min인 서비스×채널×창이다.
결측의 0 padding과 실제 값 차이를 비상수로 세지 않았다.

| 실제 수량 | SN | TT |
|---|---:|---:|
| 비상수 서비스×채널×창 | 30,556/42,552 | 365,172/988,767 |
| 비상수 시스템 창 | 394/394 | 4069/4069 |
| 비상수 장애 시스템 창 | 325/325 | 3451/3451 |
| 비상수 원인 서비스 창 | 325/325 | 3451/3451 |
| 비상수 원인 채널×창 | 2274/2925 | 14711/31059 |
| 원인 latency 자체가 비상수인 창 | 141 | 13 |
| 원인 latency 관측 위치가 부분적인 창 | 213 | 254 |

아래 세 QA 변환을 모든 실제 창에 수행했다.

| 변환 | 원관측이 달라진 시스템 창 SN/TT | 원인 관측이 달라진 장애 창 SN/TT | x 최대 절대차 SN/TT |
|---|---|---|---|
| 시간 역순 | 394 / 4069 | 325 / 3451 | 4.44e-17 / 3.47e-19 |
| 고정 seed의 공통 시간 순열 | 394 / 4069 | 325 / 3451 | 2.22e-17 / 1.73e-19 |
| 창·서비스·채널별 독립 시간 순열 | 394 / 4069 | 325 / 3451 | 2.22e-17 / 1.73e-19 |

모든 창의 x가 `rtol=atol=1e-6` 검사에 통과했고 mask·coverage는 정확히 같았다.
seed는 `20261016`, 순열 hash는 JSON에 있다.
단순 상수 fixture만의 결과가 아니라 **원인 서비스까지 실제로 달라지는 창 전수**다.
역순은 상승/하강 방향을, 일반 순열은 onset·연속 지속·burst 위치를 구분하지 못하게 한다.
독립 순열은 채널·서비스 간 동시성/선후 관계도 18특징에서 식별할 수 없음을 보여준다.
전체 trace graph를 물리적으로 일관되게 재생성한 실험은 아니다. adjacency는 고정해 두었고,
위 주장은 `x/mask/coverage` 표현에만 적용한다.

따라서 현재 Local/Relative `ranker.py`가 x·mask·coverage를 조합하더라도
이 순서를 되살릴 수 없다. 이 ranker는 공개 DiagMLP 구현이 아니다.
**순서의 손실은 확인됐지만, 순서를 보존하면 원인 식별이 좋아진다는 가설은 미검증**이다.
다양한 순열이 실제 가능한 다른 장애라는 주장도 하지 않는다.

## 6. upstream에서 이미 없어진 정보

18개 시간 요약 단계와, 그 이전의 span→서비스·초 집계를 구분한다.
아래 원자료 측 수치는 이번에 재개방한 관측이 아니라 **기존 trace preflight의 집계**다.
선택 창 수·retained count 합·span 있는 칸 수와 span 원파일의 기록된 hash가
이번 bundle과 일치함을 확인했다.

| 항목 | 기존 preflight가 확인한 SN / TT | 허용 bundle 및 18특징에서의 상태 |
|---|---|---|
| error 또는 status 태그가 있는 span occurrence | 50,182/394,075 / 98,767/98,775 | values 9채널에 status/error 채널 없음 |
| 명시적 error=True / HTTP500 | SN 24,898 / 24,898; TT 10 / 14 | error rate·edge outcome 복원 불가 |
| span.kind | SN 집계 없음; TT client 44,582, server 54,185 | 구분 채널 없음 |
| parent reference | SN CHILD_OF 368,984; TT CHILD_OF 89,136, FOLLOWS_FROM 8 | same-window binary 서비스 CHILD_OF만 adjacency에 남음 |
| span identity | SN distinct 70,396; TT 23,171 | duration/count 중복 가중치는 남고 per-span identity는 없음 |
| 함수/operation label | 이번 preflight 집계에 존재 여부·빈도 항목 없음 | `reconstruct_trace`는 process→service, startTime, duration만 집계; 서비스 내 함수 구분은 출력에 없음 |
| 로그/Hawkes | 지정한 trace preflight는 로그 감사가 아님 | 허용 NPZ에 logs/Hawkes 없음; `prepare_system`도 로그를 로드하지 않음 |

`features.py.reconstruct_trace/prepare_system`에서 서비스·초별 평균 duration과
retained count만 만든 후 7 metric과 결합한다. 따라서 같은 초 안의 duration 분포,
상태와 어느 span의 지연이 짝지어졌는지, 호출 함수별 구분은 **18요약 전에 이미 없다**.
함수/operation label이 실제 원파일에 있었다고 새로 주장하지 않는다.
로그가 원자료에 없거나 무용하다는 결론도 내리지 않는다.

기존 preflight의 중복 제거 span 수 histogram에서 TT의 관측 서비스×10초 칸은
모두 서로 다른 span identity가 10개 미만이다. p95/p99를 안정적 tail로 간주하기 어렵다.
SN 302를 모두 오류로 바꾸거나 태그 부재를 오류 0으로 채우지 않는다.
잔여 시간은 parent-child 연결·시간 정합·비동기·완전성 조건이 추가로 필요하다.

## 7. 사건·episode·recording 지원과 평가 제한

| 지원 | SN | TT |
|---|---:|---:|
| recording | 4 | 9 |
| 주입 사건 / root 후보 | 36 / 12 | 81 / 27 |
| root당 사건 | 3 | 3 |
| root×장애종류 조합당 사건 | 1 | 1 |
| 허용 장애 창 / 정상 창 | 325 / 69 | 3451 / 618 |
| episode | 36 | 81 |
| fold당 held 사건 / 나머지 사건 | 12 / 24 | 27 / 54 |
| fold0/1/2 정상 held 창 | 24 / 24 / 21 | 207 / 195 / 216 |
| 장애 주입 경계를 걸친 장애 창 | 37/325 | 101/3451 |

각 episode의 정상/장애 창은 동일 fold이며 fold0 TRAIN/validation 교집합은 없다.
선택 창은 recording 내 비중첩 10초 창이다. 정상 창 중 주입 구간과 겹치는 창은 0이었다.
경계를 걸친 장애 창은 JSON에 수량을 별도로 남겼다. 원래 라벨을 바꾸지 않았다.
다음 평가는 label 포함 규칙과 판정 시점을 고정해야 한다.
span 시작으로 전체 duration을 넣는 기존 방식은 창 이후 종료 span을 포함할 수 있으므로,
즉시 온라인 진단 성능으로 부르면 안 된다.

각 fold에서 TRAIN과 held 모두 모든 root 및 세 종류
`cpu_load/network_delay/network_loss`를 지원한다.
하지만 같은 root×종류의 반복 사건은 없다.
**동일 root·동일 장애종류의 새 반복 사건 일반화**를 분리해서 추정할 수 없다.
원래 window-random split과 달리 사건은 분리하지만 recording 환경은 공유한다.
이미 연구에 쓰인 117사건이므로 새 최종시험 자료가 아니다.

### Recording holdout의 정확한 혼입

각 recording은 서로 다른 root 3개×세 종류=9사건이며,
root는 다른 recording에서 정답으로 재등장하지 않는다.
따라서 **13개 holdout 전부 cold-root 3개**를 포함한다.
후보 목록에는 해당 서비스가 그대로 남으며 다른 TRAIN 입력에도 관측될 수 있다.
root 정답 감독 부재와 후보 미등장은 다르다.

SN의 recording holdout별 TRAIN 사건은 모두 27, 정상 TRAIN 창은
51/53/53/50개다. TT는 모두 72사건, 정상 TRAIN 창은
545/549/553/554/551/549/543/550/550개다(recording 시간순).
모든 recording별 root 이름·사건 목록·창 분모는 JSON `recording_holdouts`에 보존했다.
이 실험은 환경 shift+root 감독 shift의 스트레스 평가로만 부를 수 있다.

## 8. 가장 작은 과학적으로 충분한 교정 프로토콜 — 실행하지 않음

1. **과제·관측 시점:** 이미 알려진 장애 사건의 root-service 조건부 진단으로 고정한다.
   탐지·예측·새 장애종류 발견을 추가하지 않는다. 이 bundle으로는 retrospective
   10초 창 평가이며 실제 온라인 가용성은 별도 검증 사항이다.
2. **분할:** 기존 episode/fold와 후보 12/27개를 동결한다.
   외부 평가 f, validation (f+1)%3, TRAIN (f+2)%3의 순환 세 구성을 쓰면
   SN은 각각 12사건, TT는 각각 27사건으로 TRAIN/validation/query가 분리되고,
   각 root가 각 부분에서 한 사건씩 지원된다. 모든 사건은 외부 query로 한 번만 집계한다.
   validation과 query를 합쳐 epoch/특성을 선택하지 않는다.
   정상 창도 원 episode와 함께 이동시킨다.
3. **TRAIN-only 전처리:** 해당 TRAIN의 정상 참조·표준화·log template/Hawkes,
   학습 encoder·공유 graph 등의 적합 범위를 고정한다.
   저장 fold0 x를 재분할해 쓰지 않는다. 이번 QA fold0 참조도 새 분할 학습용이 아니다.
4. **원 Eadro 앞단 보존:** metric·log·trace 인코딩과 시간 정렬을 보존하고,
   서비스 순서·라벨·native static graph 및 detector/localization 경계를 명시한다.
   bundle의 count를 원 Eadro trace의 두 번째 채널로 끼워 넣지 않는다:
   기존 `features.py.load_selected`의 native trace 계약은 두 번째 채널 0이다.
   18특징 MLP/GAT adaptation을 원 Eadro라고 부르지 않는다.
5. **DiagMLP 방정식 기반 재구성:** 부모 작업에서 확인한
   `native_models.py::EquationDiagEncoder`와 `SOURCE_EADRO_DIAG.md`의 기존 재구성을
   통제 비교에 사용할 수 있다. native modality encoder를 보존하고,
   앞단·입력·후보·분할을 공유해 fusion/관계 처리의 차이를 비교한다.
   저자의 정확한 통합 구현은 복구되지 않았으므로 **방정식 기반 재구성**임을 명시하고,
   코드·출처 hash와 임베딩 폭·concatenation·fusion/head 경계·서비스 위치 mapping의
   선택을 고정·공개한다. 임의의 32→16 Local ranker나 단순 mean pooling과 구분하며,
   저자 구현의 확보를 필수 조건으로 삼거나 논문 점수의 정확한 재현이라고 주장하지 않는다.
6. **최소 비교·평가:** 원 Eadro와 같은 native 앞단을 보존한 위 DiagMLP 방정식 기반
   재구성을 우선 두 비교군으로 둔다.
   현재18특징 모델은 별도 adapted 기준이며 필요할 때만 같은 분할로 추가한다.
   각 구현의 정당한 validation 선택 예산·중단·paired seed를 사전 동결한다.
   창/seed를 사건 안에서 먼저 평균하고 사건 동등가중 Top1/Top3/MRR,
   동점 균등 credit, 사건별 paired 차이를 남긴다.
   작은 root별 사건 수와 recording 공유를 명시하고 seed/창을 독립 사건처럼 세지 않는다.
   전처리·학습·query 준비·추론 비용을 구분해 포함한다.
7. **시간순서 가설 검증은 그 다음:** 위 기준선으로 확인된 실패를 바탕으로
   동일 정보·앞단에서 요약/시간보존 대조 하나를 고정해 평가해야 한다.
   현재 invariance 결과만으로 새 시간 모듈의 효과나 원인 설명력을 주장하지 않는다.

**현 접근 경계에서는 이 전체 pipeline 실행에 필요한 자료가 부족하다.**
허용 9채널 bundle에는 native logs/Hawkes·원 native static graph·원 세 modality embedding이
없으므로, 원 Eadro 앞단 입력을 준비할 승인된 개발 자료와 준비 범위가 여전히 필요하다.
부모가 확인한 기존 방정식 기반 재구성은 위 선언과 hash·경계 선택을 고정해 사용할 수 있으며,
별도의 저자 통합 구현 확보는 실행의 필수 관문이 아니다. 이번 문구 수정에서는 해당 소스를
추가로 열거나 충실도를 새로 검증하지 않았다. native-input 준비 범위가 확보되기 전에는
0으로 가짜 로그를 만들거나 현재 18특징을 원 입력이라 이름 붙여 fits를 실행하면 안 된다.
이번 요청대로 모델 적합은 수행하지 않았다.

## 9. 재현 명령·검증·현재 상태

```sh
cd /home/gnho1236/r2
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B research/diagnostic_observability_20261016/sn_tt_audit.py --self-check
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B research/diagnostic_observability_20261016/sn_tt_audit.py
```

모니터 실제 결과:

```text
SN_TT_SELF_CHECK_PASS (order, constancy, missing reference, TRAIN-only)
SN_TT_SELF_CHECK_PASS (order, constancy, missing reference, TRAIN-only)
SN_TT_SYSTEM_PASS SN
SN_TT_SYSTEM_PASS TT
SN_TT_AUDIT_PASS sn_tt_audit.json sha256=503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3
watcher completed (exit code 0)
```

Python 3.8.20 / NumPy 1.21.5. 자기검사는 실제 특성 함수를 사용하며 역순,
상수·비상수, 부분 관측/참조 부재, validation 값을 바꿔도 TRAIN 참조 불변을 검사한다.
실제 입력 schema/hash·fold·episode·count 합·기존 root union·재현·세 순열 검사가 통과했다.
입력 hash는 실행 전후 동일했다. LSP diagnostics: **없음**.
완료 후 보고서의 39개 서비스 행·union·분모·코드/결과 hash 등을 독립 대조한
87개 검사가 `SN_TT_FINAL_CROSSCHECK_PASS`였다.
기존 결과가 있는 상태의 실제 재실행도 입력을 재개방하기 전 `FileExistsError`로 거부했고,
이를 예상 결과로 검사한 모니터가 `SN_TT_EXCLUSIVE_OUTPUT_PASS`, **exit 0**으로 끝났다.

- 코드 SHA-256: `36e098e3dad8b835914b7263ab419606d3f5310591350e7dc03ffdaa5b28a807`
- 결과 SHA-256: `503742bd7e97e7bea6bb78727e71171f1a4e52dc0a2bb27b5f707a06902aece3`
- 출력은 `open("x")` 독점 생성이며 기본 명령을 다시 실행하면 덮어쓰지 않고 거부한다.
  재현 시 `--output sn_tt_replay.json`처럼 **아직 없는** 접두사 파일을 지정한다.

현재 완료한 것은 관측 범위·표현 손실·분할 지원 감사다.
원 stream 독립 재검수, 공개 fusion code 검증, 모델 학습/성능 개선,
수집기 완전성·피해 라벨·전파 인과 및 깨끗한 최종시험 독립성은 미확인이다.
기존 자료·코드·모델·분할을 변경하지 않았고 다운로드·설치·commit·자식 작업 생성은 없다.
