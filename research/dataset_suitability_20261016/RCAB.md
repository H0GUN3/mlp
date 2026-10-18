# RCABench 활용 적합성 진단 및 분할 스트레스 검사

실행일: **2026-10-16 UTC**. 최종 상태: **RCAB_SUITABILITY_PASS / 실제 CLI exit 0**.

## 1. 무엇을 확인했는가

HTTP 오류가 큰 관측 서비스를 명목 설정 표적으로 찾을 수 있는지, 그리고 같은 점수를
서로 다른 정답 계약으로 평가하면 얼마나 달라지는지 확인했다. 또한 반복 설정을
같은 fold에 묶을 때 학습 측 원인 서비스·고장 종류 지원이 유지되는지 검사했다.
이는 주어진 장애 시간창을 사용하는 **오프라인 자료 진단**이지 인과 원인 입증,
신경망 학습, 논문 기준선 재현 또는 최종 평가가 아니다.

기존 HTTP796건 감사는 관측 가용성의 근거로만 재사용했다. 대부분 정답 표적의 상세
프로필만 저장한 기존 수치로 순위를 만들지 않았다. 새 점수는 사전 선택한 **173건**의
모든 후보에 대해 trace 네 열에서 다시 집계했다. 나머지 HTTP623건과 비HTTP626건에는
새 진단 순위를 계산하지 않았다.

### 현재 판정

- **통과한 활용 조건:** 정답 비의존 후보 구성, 네 고정 점수, 결측·동점 처리 및 두
  정답 계약의 별도 평가를 재현할 수 있다. 반복 semantic 설정을 fold 사이에 섞지 않는
  메타데이터 분할도 구성할 수 있다.
- **반증된 강한 주장:** “HTTP 오류가 가장 큰 서비스는 항상 설정 표적이다”는 성립하지
  않는다. 장애 HTTP오류 비율에서 명목 표적 Top1 확률이 정확히 0인 사례가 **83/173**이다.
  같은 점수라도 정답 집합을 바꾸면 수치가 크게 달라져 두 평가 질문을 혼용할 수 없다.
- **아직 미확인:** 물리적 인과 식별, 전체 HTTP796건 성능, 비HTTP 진단 성능,
  학습 후 일반화, 수집 사건의 독립성.
- **권장 역할:** 전체 후보·정답 계약·시간창을 명시한 개발용 진단 자료와 분할 검토 자료.
  이번 결과만으로 주 데이터 또는 최종 분할을 자동 채택하지 않는다. 단순 점수의 낮은
  성능만으로 데이터 전체를 부적합하다고 판정하지 않는다.

## 2. 점수 이전에 고정한 선택

각 HTTP종류에서 semantic 설정 그룹을
`sha256("suitability-pilot-20261016:" + group)` 오름차순으로 정렬해
앞 `ceil(0.2 * 그룹수)`를 선택하고, 이전 HTTP 정밀 표본12건이 속한 그룹을 합쳤다.
모든 그룹 구성원을 포함했다. **점수·관측 밀도에 따른 선택, 누락 사례 제거 또는
구제 규칙은 없다.**

`rcab_selection.json`은 trace 처리 전에 exclusive-create됐다.
초기155그룹에 정밀 표본의 추가9그룹을 합친 **164/759그룹, 173/796사례**다.
선택하지 않은595그룹/623사례와 semantic 그룹 중복은 0이다.

| HTTP종류 | 전체 사례 | 전체 그룹 | 최초20% 그룹 | 정밀 표본 포함 그룹¹ | 최종 그룹 | 최종 사례 |
|---|---:|---:|---:|---:|---:|---:|
| HTTPRequestAbort | 60 | 58 | 12 | 1 | 13 | 13 |
| HTTPRequestDelay | 88 | 88 | 18 | 1 | 19 | 19 |
| HTTPRequestReplaceMethod | 190 | 171 | 35 | 2 | 37 | 43 |
| HTTPRequestReplacePath | 39 | 38 | 8 | 1 | 9 | 9 |
| HTTPResponseAbort | 44 | 44 | 9 | 1 | 10 | 10 |
| HTTPResponseDelay | 89 | 89 | 18 | 1 | 19 | 19 |
| HTTPResponsePatchBody | 4 | 4 | 1 | 1 | 1 | 1 |
| HTTPResponseReplaceBody | 51 | 45 | 9 | 1 | 10 | 13 |
| HTTPResponseReplaceCode | 231 | 222 | 45 | 3 | 46 | 46 |

¹ 최초 선택과 겹칠 수 있으므로 단순 덧셈하지 않는다.

이미 알려진 설정 표적의 장애 trace 누락2건도 그대로 포함했다.

- `ts2-ts-basic-service-request-replace-method-v6gzn8`
- `ts3-ts-basic-service-response-replace-code-ws6vpb`

정밀 표본을 추가했으므로 이 결과는 단순 무작위20% 표본도, HTTP796건 전체 성능도 아니다.
보류623건도 과거 관측 감사를 받았으므로 완전 미접촉 최종자료라고 부르지 않는다.

## 3. 후보·집계·정답 계약

각 사례의 정상/장애 `metrics.parquet`와 `traces.parquet` 네 core 파일에 저장된
**전체 `services` 목록의 합집합**에서 빈 이름만 제외했다. 정답·`targets` 프로필은
후보를 만드는 데 쓰지 않았다. loadgenerator 이름도 유지했다.
이번 선택173건은 모두 **49후보**, 후보-사례 쌍은 **8,477개**다.

archive에서 읽은 열은 다음 네 개뿐이다.

```text
service_name
time
attr.http.response.status_code
attr.status_code
```

HTTP known은100–599, HTTP error는400–599, span Error는 문자열 `Error`다.
Unset/null/범위 밖 상태를 정상 HTTP로 치환하지 않았다.
정상 `[normal_start, normal_end)`, 장애 `[abnormal_start, abnormal_end)`를 사용했다.
Client/Server span을 합치거나 요청으로 중복 제거하지 않고 **배포된 span 행**을 그대로 셌다.

| 기간 | 읽은 span 행 | 포함 행 | 끝 경계 제외 | 그 외 구간 밖 | null 시간 | 시작 경계 포함 |
|---|---:|---:|---:|---:|---:|---:|
| 정상 | 23,101,590 | 23,101,568 | 22 | 0 | 0 | 8 |
| 장애 | 15,018,625 | 15,018,618 | 7 | 0 | 0 | 22 |

포함된 빈 서비스명 행은 두 기간 모두0이다. 공통 경계는 정상에서 제외하고 장애에서
포함했다. 원래 행 수 = 포함 + 끝 경계 제외 + 그 외 구간 밖 + null 시간으로 대조했다.

점수 함수 `score_counts`에는 서비스별 두 기간 **count만** 전달된다.
사례명·고장 종류·정답 인자는 없다. 네 기준은 사전 고정했다.

| 기준 | 계산 | 전체 결측 후보-사례 쌍 | 결측 명목 표적 |
|---|---|---:|---:|
| uniform | 모든 후보0, 지원됨 | 0 | 0 |
| abnormal_http_error_fraction | 장애 HTTP error / 장애 HTTP known | 3,637 | 2 |
| http_error_fraction_increase | 장애 비율 − 정상 비율 | 3,647 | 2 |
| abnormal_span_error_fraction | 장애 span Error / 장애 span 행 | 3,635 | 2 |

분모가 없으면 JSON `score: null, supported: false, missing: true`다.
결측 후보는 삭제하거나 정상0점으로 바꾸지 않고 모든 지원 점수 뒤의 한 동점 tier에 둔다.
전부 결측이면 전체 동점이다. 음수의 지원 점수도 결측보다 앞선다.
지표 계산은 동일 점수를 (1) 명목 설정 표적 하나, (2) 배포본의 원래 허용 정답 서비스
집합에 각각 적용했다.

동점은 정확히 같은 수치의 tier에서 균등 무작위 순서를 가정한다. 첫 정답 tier 앞 후보가
`b`, tier 크기가 `t`, 그 tier의 허용 정답이 `m`개일 때
`P(첫 정답의 tier 내부 순위=j)=C(t-j,m-1)/C(t,m)`를 사용했다.
Top-k는 해당 tier의 앞 `min(t,max(0,k-b))`자리에 하나 이상 정답이 있을 확률이다.
ERR은 이 분포에서 `1/(b+j)`의 기대값이다. 여기서 ERR은
`expected_reciprocal_first_accepted_rank`이며 임의 정렬의 reciprocal rank가 아니다.

후보에 없는 정답은 추가하지 않는다. 허용 정답이 하나도 후보에 없으면 해당 계약의
모든 지표는0이다. 복수 정답 중 일부만 없으면 없는 항목을 보고하고 존재하는 허용
정답 중 첫 순위로 평가한다. 이번 pilot은 두 계약 모두 **후보 밖 정답0건**이다.
trace 행 누락은 이와 다르다. 명목 표적2건은 metric census 후보에는 남아 있으나
장애 trace 점수가 결측이다. 원래 정답 집합의 장애 trace 부분 누락 사례는3건이다.

## 4. 개발 pilot 결과

사례 균등 평균. 아래는 비율이며 소수점 여섯 자리로만 표시했다.
JSON에는 원래 float와 각 사례의 동점 tier 증거를 보존했다.

| 기준 | 명목 Top1 | 명목 Top3 | 명목 ERR | 원래집합 Top1 | 원래집합 Top3 | 원래집합 ERR |
|---|---:|---:|---:|---:|---:|---:|
| uniform | 0.020408 | 0.061224 | 0.091412 | 0.040816 | 0.119898 | 0.144967 |
| 장애 HTTP오류 비율 | 0.480987 | 0.814256 | 0.656739 | 0.609373 | 0.842064 | 0.742138 |
| HTTP오류 비율 증가 | 0.486767 | 0.814256 | 0.659630 | 0.615153 | 0.842064 | 0.745028 |
| 장애 span Error 비율 | 0.566474 | 0.807362 | 0.699179 | 0.572254 | 0.816558 | 0.708507 |

같은 점수에서 `원래집합 − 명목표적`의 사례별 paired difference 평균:

| 기준 | ΔTop1 | ΔTop3 | ΔERR |
|---|---:|---:|---:|
| uniform | 0.020408 | 0.058673 | 0.053555 |
| 장애 HTTP오류 비율 | 0.128386 | 0.027808 | 0.085399 |
| HTTP오류 비율 증가 | 0.128386 | 0.027808 | 0.085399 |
| 장애 span Error 비율 | 0.005780 | 0.009196 | 0.009328 |

이 차이는 개선된 방법의 이득이 아니라 **정답 계약을 바꾼 효과**다.

유형별 요약(Top1):

| 유형 | n | HTTP비율 명목 | HTTP비율 원래집합 | span Error 명목 | span Error 원래집합 |
|---|---:|---:|---:|---:|---:|
| HTTPRequestAbort | 13 | 0.692308 | 0.692308 | 0.615385 | 0.615385 |
| HTTPRequestDelay | 19 | 0.477379 | 0.481073 | 0.473684 | 0.473684 |
| HTTPRequestReplaceMethod | 43 | 0.360465 | 0.767442 | 0.465116 | 0.488372 |
| HTTPRequestReplacePath | 9 | 0.500000 | 1.000000 | 0.888889 | 0.888889 |
| HTTPResponseAbort | 10 | 0.500000 | 0.500000 | 0.600000 | 0.600000 |
| HTTPResponseDelay | 19 | 0.375819 | 0.383218 | 0.526316 | 0.526316 |
| HTTPResponsePatchBody | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| HTTPResponseReplaceBody | 13 | 0.153846 | 0.153846 | 0.615385 | 0.615385 |
| HTTPResponseReplaceCode | 46 | 0.673913 | 0.673913 | 0.630435 | 0.630435 |

다른 기준과 Top3/ERR도 JSON의 `pilot_summary.by_fault_type`에 모두 있다.
PatchBody는1건이므로 유형 전체의 성능 추론에 사용하지 않는다.

### 지지 근거와 반례

- 명목 Top1은 네 기준 중 span Error가0.566474로 균등0.020408보다 높았다.
  이는 **이번 고정 개발 표본에서의 관측 연관성**이며 인과 식별을 뜻하지 않는다.
- HTTP비율에서 명목 Top1이0인 사례83건, 증가량82건, span Error75건을 전부
  `counterexample_cases_anchor_top1_zero`에 보존했다.
- `ts1-ts-food-service-response-patch-body-qjhx5h`에서 표적 `ts-food-service`의
  HTTP error/known은1/832(0.001201923...), 반면 최상위 `ts-consign-service`는
  0.616161616...이다. 표적은3위여서 Top1=0, Top3=1, ERR=1/3이다.
- trace 누락2건은 모두 계속 평가됐다. HTTP비율 명목 Top1/Top3는0이며,
  결측 tier(앞25후보, tier24후보)의 ERR은 각각0.027635298357329925다.
  결측을 후보 밖 정답으로 오인해 삭제하거나0점 정상으로 바꾸지 않았다.
- 장애 trace에 명목 표적이 있는171건의 HTTP비율 명목 Top1/Top3/ERR은
  0.486613/0.823780/0.664097이다. 이 층화는 보고용이며 사례를 제거한 새 주 결과가 아니다.

## 5. 전체1,422건 분할 스트레스 검사

모든25종류를 포함했다. 비network1,168건 중 설정-정답 충돌
`ts4-ts-food-service-container-kill-lv5htg` 하나를 제외한 **1,167건**은
명목 설정 표적 검토 후보이지 입증된 물리적 원인 사건 또는 승인된 학습 집합이 아니다.
HTTP796건과 network pair254건의 지원을 별도로 계산했다.

분할은 `int(sha256("suitability-20261016:" + key),16) % 3`이다.
key를 case ID 또는 semantic 설정 hash로 바꾸어 비교했다. **건식 검사일 뿐 최종 분할은 아니다.**

| 분할 | fold0/1/2 사례 | 여러 fold로 흩어진 반복 그룹 | 그 그룹의 사례 |
|---|---|---:|---:|
| case hash | 477 / 477 / 468 | 45 | 130 |
| semantic group hash | 494 / 480 / 448 | 0 | 0 |

전체 semantic 그룹은1,322개, 반복 그룹은59개/159사례다.
같은 설정 hash의 중복을 막는 효과는 확인됐지만 독립 수집 사건이라는 증명은 아니다.

각 subset 내부에서 나머지 두 fold만 TRAIN으로 삼은 지원 검사:
아래의 세 숫자는 fold0/1/2 순서다. network는 원래 정답의 각 endpoint 지원을 검사한다.

| 분할 | subset | heldout 수 | TRAIN 원인 지원 없는 사례 | TRAIN 유형 지원 없는 사례 |
|---|---|---|---|---|
| case | 전체 metadata의 명목 anchor(기술용) | 477/477/468 | 0/0/0 | 2/2/1 |
| group | 전체 metadata의 명목 anchor(기술용) | 494/480/448 | 0/0/0 | 0/3/2 |
| case | 비network 명목 후보1,167 | 396/394/377 | 0/0/0 | 2/2/1 |
| group | 비network 명목 후보1,167 | 406/393/368 | 2/0/0 | 0/3/2 |
| case | HTTP796 | 262/273/261 | 0/0/0 | 0/0/0 |
| group | HTTP796 | 282/269/245 | 0/0/0 | 0/0/0 |
| case | network pair254 | 81/83/90 | 0/0/0 | 0/0/0 |
| group | network pair254 | 88/86/80 | 0/0/0 | 0/0/0 |

group fold0의 비network 원인 미지원2건은
`ts2-ts-verification-code-service-container-kill-2lmcml`과
`ts5-ts-verification-code-service-container-kill-g22rpg`이며, 둘 다
`ts-verification-code-service`다. 전체 metadata에서 보이는 지원을 비network 후보의
학습 지원으로 대체하지 않았다.

case 분할의 유형 미지원5건은 JVMCPUStress2/JVMMySQLLatency2/DNSRandom1이다.
group 분할에서는 DNSRandom1/JVMCPUStress2/TimeSkew2다.
network에서 개별 endpoint 지원은 모두 있지만 **동일 원래 정답 집합**의 TRAIN 사례가
없는 heldout 수는 case9/6/7, group13/6/0이다. endpoint를 안다는 것과 같은 pair를
학습했다는 것은 구별했다.

namespace10개 모두 두 분할에서 각각 세 fold에 나타난다.
전체 `[normal_start, abnormal_end)`의 양의 시간 중첩은760쌍이며 같은 namespace 중첩은0,
다른 namespace 중첩은760이다. 두 분할 모두 그중502쌍이 cross-fold다.
namespace·시간 공유와 group hash만으로 독립성을 인증하지 않는다.

## 6. 실제 자원·경계·보존 증거

- 실행 구간: `2026-10-16T17:27:24.587767+00:00` →
  `2026-10-16T17:30:32.281650+00:00`.
- 본문 타이머 **187.6939055660041초**, 최대 RSS **507,040 KiB**.
  타이머는 최종 JSON 직렬화·최종 해시 출력 직전까지다.
- trace **346파일 / 38,120,215행**, payload **1,109,207,335바이트**.
  archive regular member19,991개의 헤더를 한 번 순회했으며 선택된 trace만 extract/Parquet
  처리했다. 다른 파일 본문을 분석하거나 전체 압축을 풀지 않았다.
- 파일당16MiB/2,000,000행 제한. 선택 파일 최대 **7,821,526바이트 / 278,014행**.
  모든 선택 member를 inventory 크기, quality 행 수·SHA256 및 기존 census SHA256과 대조했다.
- 사전 RAM probe: **61,390,647,296바이트**, 출력 파일시스템 여유370,418,364,416바이트.
  한 member씩 네 열만 메모리에 두었다. archive 프로세스1개, Arrow CPU/I/O 스레드 각각2개.
  `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=2`.
- archive 압축13,444,974,981바이트를 같은 순회에서 전부 hash했다. archive 재열람은 없다.
  SHA256 `f6f593c053dcfa3f1447aaad0b978f01fc8a770a7f1fa838d0ab124be62ecfb0`.
  MD5 `96d32ae290e06be7d4e251be02b36cb8`도 기존 identity와 일치한다.
- archive stat은 선택 전/순회 전/후 동일:

```json
{"st_dev":2050,"st_ino":79954416,"st_size":13444974981,
 "st_mtime_ns":1791941867732793225,"st_ctime_ns":1791941867732793225,
 "st_mode":33204}
```

atime은 읽기에 의해 변할 수 있어 unchanged 판정에 사용하지 않았다.
소비한 metadata·소스·프로토콜·설정과 아래 핵심 software hash는 실행 전후 대조했다.
기존 결과를 수정하지 않았으며 새 JSON 두 개는 `open("x")`, finite JSON, flush/fsync로 작성했다.

## 7. 정확한 명령과 원래 프로세스 기록

작업 세션: `st_01a145b8`.
thread: `01a145b8-644a-7e6d-83d2-384460d40459`.
도구는 monitor ID를 그대로 `bash_output`의 **bash_id/session handle**로 반환한다.
별도 숫자 bash ID는 제공하지 않았다. 아래 인용은 해당 handle에 대한 **실제
`bash_output` 응답 원문**이며 재구성한 성공 메시지가 아니다.

| 검사 | monitor ID = bash_id | definitive filter | exit |
|---|---|---|---:|
| 초기 소스 Pyright | `mon_ARSP3F68ATA79FTX` | `(error\|warning\|RCAB_PYRIGHT_EXIT\|files? analyzed)` | 0 |
| 최종 소스 Pyright | `mon_H5MZ9JCR9DJC3JZP` | `(error\|warning\|RCAB_PYRIGHT_EXIT)` | 0 |
| package-qualified 테스트 | `mon_6T6APH8237N6B2PZ` | `(test_\|Ran \|OK\|FAILED\|ERROR\|FAIL\|RCAB_TEST_EXIT)` | 0 |
| 저장소 루트 discovery | `mon_H9SQR9A0FGS9KP8J` | `(test_\|Ran \|OK\|FAILED\|ERROR\|FAIL\|RCAB_DISCOVERY_EXIT)` | 0 |
| 단 한 번의 실제 CLI | `mon_2BXX0SZJ24S502BC` | `^(RCAB_SELECTION_FROZEN\|RCAB_RESULT_SHA256\|RCAB_SUITABILITY_PASS\|RCAB_CLI_EXIT=\|Traceback\|.*Error:)` | 0 |

Pyright deadline120,000ms, 테스트180,000ms, 실제 실행1,800,000ms로 monitor를 등록했다.
테스트는4후보에 대해 점수 `{None,-1,0,1}`의256조합 × 정답의 비어 있지 않은15부분집합,
총3,840조건을 각 tier의 모든 순열 oracle과 비교했다. 복수 정답의 서로 다른 tier,
모두 결측, 지원 음수/결측 순서, 후보 구성 정답 비의존성, 이름·정답 순열 불변성,
half-open 경계·상태 범위, 누락 정답, 선택·그룹 결정성/비중첩, 실제1422건 분할,
exclusive-create 보호, gzip-tar 단일 순회 hash를 포함한다.

### 7.1 Pyright (실제 실행 전)

초기/최종 모두 같은 명령:

```sh
cd /home/gnho1236/r2 && pyright -p research/dataset_suitability_20261016/pyrightconfig.json research/dataset_suitability_20261016/rcab_trial.py research/dataset_suitability_20261016/test_rcab_trial.py; rc=$?; printf "RCAB_PYRIGHT_EXIT=%s\n" "$rc"; exit "$rc"
```

최종 handle `mon_H5MZ9JCR9DJC3JZP`의 retained response:

```text
status: completed exit_code: 0
0 errors, 0 warnings, 0 informations
RCAB_PYRIGHT_EXIT=0
```

초기 `mon_ARSP3F68ATA79FTX`도 정확히 같은 응답이었다.
에디터 LSP는 테스트의 absolute namespace import를 unresolved로 표시했지만,
parent 소유 설정을 지정한 CLI Pyright에서는 두 파일 모두 error/warning0이었다.
실제 package/discovery import도 아래에서 모두 통과했다. ignore나 설정 변경으로 숨기지 않았다.

### 7.2 Package-qualified 집중 테스트

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m unittest -v research.dataset_suitability_20261016.test_rcab_trial; rc=$?; printf "RCAB_TEST_EXIT=%s\n" "$rc"; exit "$rc"
```

handle `mon_6T6APH8237N6B2PZ`의 retained response:

```text
status: completed exit_code: 0
test_candidate_construction_independent_of_targets (research.dataset_suitability_20261016.test_rcab_trial.CountTests) ... ok
test_halfopen_and_status_ranges_and_as_published_rows (research.dataset_suitability_20261016.test_rcab_trial.CountTests) ... ok
test_missing_denominators_not_zero_or_dropped (research.dataset_suitability_20261016.test_rcab_trial.CountTests) ... ok
test_exclusive_write_protection_and_finite_json (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_fold_exact_hash_and_training_support (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_selection_determinism_whole_groups_prior_and_disjointness (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_single_pass_gzip_tar_with_hashing_reader (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_streamed_archive_hash (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_whole_metadata_selection_and_group_split_reconciliation (research.dataset_suitability_20261016.test_rcab_trial.SelectionAndSafetyTests) ... ok
test_all_missing_is_all_tied (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok
test_exhaustive_permutation_oracle_all_gold_subsets (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok
test_label_and_name_permutation_invariance (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok
test_missing_gold_not_added_or_rescued (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok
test_nonfinite_rejected (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok
test_supported_negative_before_missing (research.dataset_suitability_20261016.test_rcab_trial.TieTests) ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.756s

OK
RCAB_TEST_EXIT=0
```

이 응답을 최초 보존한 tool output의 archive locator:

```text
/home/gnho1236/.omo/agent/projects/r2-b89a818648f9/senpi-task/children/st_01a145b8/sessions/st_01a145b8/2026-10-16T17-17-53.347Z_0b740839-6d31-4f9e-b29b-f2b78ec145f4-artifacts/eval-9006ed69-7ef0-43d1-876a-4bbfe8e2a4c5.log
```

### 7.3 저장소 루트 discovery

다른 작업자의 테스트나 보호 관측을 실행하지 않도록 이번 파일만 discovery했다.

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m unittest discover -v -s research/dataset_suitability_20261016 -p test_rcab_trial.py; rc=$?; printf "RCAB_DISCOVERY_EXIT=%s\n" "$rc"; exit "$rc"
```

handle `mon_H9SQR9A0FGS9KP8J`의 retained response:

```text
status: completed exit_code: 0
test_candidate_construction_independent_of_targets (test_rcab_trial.CountTests) ... ok
test_halfopen_and_status_ranges_and_as_published_rows (test_rcab_trial.CountTests) ... ok
test_missing_denominators_not_zero_or_dropped (test_rcab_trial.CountTests) ... ok
test_exclusive_write_protection_and_finite_json (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_fold_exact_hash_and_training_support (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_selection_determinism_whole_groups_prior_and_disjointness (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_single_pass_gzip_tar_with_hashing_reader (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_streamed_archive_hash (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_whole_metadata_selection_and_group_split_reconciliation (test_rcab_trial.SelectionAndSafetyTests) ... ok
test_all_missing_is_all_tied (test_rcab_trial.TieTests) ... ok
test_exhaustive_permutation_oracle_all_gold_subsets (test_rcab_trial.TieTests) ... ok
test_label_and_name_permutation_invariance (test_rcab_trial.TieTests) ... ok
test_missing_gold_not_added_or_rescued (test_rcab_trial.TieTests) ... ok
test_nonfinite_rejected (test_rcab_trial.TieTests) ... ok
test_supported_negative_before_missing (test_rcab_trial.TieTests) ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.791s

OK
RCAB_DISCOVERY_EXIT=0
```

### 7.4 실제 CLI — 재실행하지 않음

```sh
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m research.dataset_suitability_20261016.rcab_trial; rc=$?; printf "RCAB_CLI_EXIT=%s\n" "$rc"; exit "$rc"
```

handle `mon_2BXX0SZJ24S502BC`의 retained response 원문:

```text
status: completed exit_code: 0
RCAB_SELECTION_FROZEN cases=173 sha256=2c00110435d5365b6b0fadc6446a9d6a74b65affe21f4f05d8ad42970e2124d5
RCAB_RESULT_SHA256 98eccf62060e398c691242aca1f532c444646f93bc9c239d7a3c4ac0e7d64b00
RCAB_SUITABILITY_PASS
RCAB_CLI_EXIT=0
```

monitor 완료 알림도 같은 sentinel들과 `watcher completed (exit code 0)`를 전달했다.
파일 존재만으로 성공을 판정하지 않았다.

### 7.5 Archive 재열람 없는 JSON 독립 대조

실제 실행 후 resident Python eval에서 `read`로 두 결과 JSON을 읽고, producer 함수를
import하지 않은 `verify_saved_trial(trial, selection)`을 실행했다. 이는 shell 프로세스가
아니므로 별도 exit code를 만들지 않았다. 모든 assert가 통과한 실제 반환값:

```text
{'cases': 173, 'candidate_criterion_scores': 33908, 'label_metric_values': 4152, 'metadata_rows': 1422, 'status': 'RCAB_JSON_RECONCILIATION_PASS'}
```

대조 범위는 전체 후보 census 일치, count에서33,908점수 및 support/missing 재계산,
행/경계 합계와 member hash, 두 계약의4,152개 지표, 사례별 paired difference,
전체·모든 유형의 평균, 모든 fold 할당·반복 그룹 cross-fold 목록,
네 subset의 모든 heldout 사례에 대한 TRAIN 원인/유형/원래정답집합 지원 수다.
동점은 producer의 조합식 대신 각 위치에서 남은 정답 수/남은 자리 수로
first-hit 확률을 누적하는 독립 계산으로 대조했다(절대 오차1e-12).
소비 metadata·소스 hash도 다시 일치했다.

## 8. SHA256 결속

아래 입력 경로는 `/home/gnho1236/r2/` 기준이다. 해시는 선택 전에 저장했고 실제 실행
종료 전 전부 재검사했다. raw provenance에 적힌 다른 데이터 경로를 따라가지 않았다.

| 입력·소스 | SHA256 |
|---|---|
| research/dataset_suitability_20261016/PROTOCOL.md | `569703d983be487c7c752a25610b63db2b5fbd7775c541881e13416284057352` |
| research/dataset_suitability_20261016/pyrightconfig.json | `9c66a048a4b8490572992b35a8f0247c960aa2072a9ce769c189706bd02b7826` |
| research/dataset_suitability_20261016/rcab_trial.py | `0d500e3f4971adaa4807017eb14c5c411f29cff7ef7bfbcc8466fe1208d6892c` |
| research/dataset_suitability_20261016/test_rcab_trial.py | `09d3f79456ece271209fd7bbb1cb1092c4b6829ab38f1ba9f2cb236ca9aeadd1` |
| research/research_reset_review_20261016/metadata_analysis.json | `f51fe67b76e3692fbcb99652dd4ef3004c8dd95b1dc427ce1dcf6c6dacac1b9b` |
| research/research_reset_review_20261016/metadata_details.json | `19af17173882177dbc211461bda6a4a796341f42d8527cfc1a14176176595648` |
| research/research_reset_review_20261016/verification.json | `3e2231d643f0986893d5cdaf1c26f95471883b4dea7755f95005a6b609f7fe0d` |
| research/diagnostic_observability_20261016/rcab_sample_manifest.json | `1dd319d3b0ff3be42f44fa8da5950441243483b4b1b770c618d5b745cbe90cfe` |
| research/diagnostic_observability_20261016/rcab_observability.json | `9cedc38e7a795b509995538b010a4e3b6d990ff515008c357c11d389a4652347` |
| research/diagnostic_observability_20261016/verified_summary.json | `1b203c4cc89798960ca9087423719cf01671deb01398228d88c788ad5cb81476` |
| research/rcabench_assessment_20261013/quality_audit.json | `fd39f1c126ce780546ff8c7b3eed9cba3fed219151e484299ede0ab22246a8e5` |
| research/rcabench_assessment_20261013/metadata_inventory.json | `fb20d845667818671c50da2f83b36c83674f03bbddd12b545084fdfe780e6b2c` |

| 새 결과 | SHA256 |
|---|---|
| rcab_selection.json | `2c00110435d5365b6b0fadc6446a9d6a74b65affe21f4f05d8ad42970e2124d5` |
| rcab_trial.json | `98eccf62060e398c691242aca1f532c444646f93bc9c239d7a3c4ac0e7d64b00` |

런타임: Python3.10.12, NumPy1.26.4, PyArrow19.0.1,
Linux6.8.0-138-generic x86_64/glibc2.35.
아래 package 경로는 `/home/gnho1236/r2/.venv-mlp/lib/python3.10/site-packages/` 기준이다.
인터프리터·핵심 수치/Parquet binary·명시 entry module의 SHA256이며, OS 동적 라이브러리
전체의 전이적 증명은 아니다.

| software | SHA256 |
|---|---|
| /usr/bin/python3.10 | `a2f33a6e006989270f4340528eb61f8f97366e00a5d1b602ac8672ea44fc56ae` |
| numpy/__init__.py | `22cd1535fa14d74ef6f457cca149ffdc80875f460be313b8f895273f78bc402e` |
| numpy/core/_multiarray_umath.cpython-310-x86_64-linux-gnu.so | `fe5efe31c55326b072c8fb239a225819211826cb45cd3c74ed0af0030e70f3a1` |
| pyarrow/__init__.py | `f1e8b3129f5abc31d57e8708fd818d888d2e1e90f6b6b4ebf879c6cd060f3f42` |
| pyarrow/_parquet.cpython-310-x86_64-linux-gnu.so | `456b8ea20d0b107ce02db4eeb20d2b9e021f74012bfa94ef5da37f0017211125` |
| pyarrow/lib.cpython-310-x86_64-linux-gnu.so | `f0222f01a10d9fb87f3129c7307a0a8f995fffeaff37bdbcfbe9b0f90b5f858b` |
| /usr/lib/python3.10/gzip.py | `fb131d4bbe711c410f54c7f0b3c2c64292e1279199fd04c53837db03e542a907` |
| /usr/lib/python3.10/hashlib.py | `9d56ebad0263a48ac94e0b2b7a3723625f2ff4dc7707d1156580e008d40bc790` |
| /usr/lib/python3.10/json/__init__.py | `d5d41e2c29049515d295d81a6d40b4890fbec8d8482cfb401630f8ef2f77e4d5` |
| /usr/lib/python3.10/tarfile.py | `6df0c56bd2c4df395300369f87f2c1733732aefc09756d76d878cb3a934fdc6f` |

## 9. 독립 검증자가 사용할 결과 구조와 한계

추가 archive 열람 없이 다음 경로로 재계산할 수 있다.

- `rcab_selection.json`: 모든 HTTP 그룹 구성원·선택 hash·선택 이유·보류 목록,
  원자료/소스/software hash, 사전 예산, 선택 시각과 archive stat.
- `rcab_trial.json.pilot_cases[case]`: 전체 후보, 정상/장애 네 count, criterion별 원래
  float/null·support·missing, 두 계약의 정답과 모든 지표·동점 tier,
  계약별 paired difference, 표적/정답 trace 누락, 파일별 member 이름·크기·SHA256·
  projection·half-open 행 감사.
- `pilot_summary`: 사례 균등 전체·유형별·표적 trace 누락 층화, 결측 수, 누락 목록,
  반례 사례 목록.
- `whole_metadata_split_stress`: 전체1422 `metadata_case_rows`, 전체 그룹 구성원,
  두 split의 모든 case→fold, 반복 그룹 cross-fold 목록, namespace/시간 중첩,
  네 subset의 fold별 TRAIN 분포와 모든 heldout 사례의 원인/유형/정답집합 지원.
- `trace_run`, `runtime`, `source_sha256_before_and_after`: archive 변경 없음,
  압축 archive SHA256, 파일/행 수, 시간/RSS, 입력 보존 근거.

이 결과는 후보·점수·정답 계약의 **계산 가능성**을 확인한다. 데이터가 인과적으로
충분하다거나 모델을 학습하면 일반화된다는 보장은 아니다. 오류 비율의 span 행은
독립 요청/사건 표본이 아니며, 시간창은 알려져 있다. 그룹 분할에서도 namespace와 시간이
공유된다. 새로운 모델·bootstrap·분류기·구제 규칙은 실행하지 않았다.

원본·기존 결과·parent 소유 `PROTOCOL.md`/`pyrightconfig.json`을 변경하지 않았다.
neural training/checkpoint/inference, native test/unassigned 및 RCAEval 최종 관측·예측,
설치·다운로드·commit·root/공용계정·omo-native·Notion 작업은 하지 않았다.
이 작업이 새로 만든 인계 파일은 요청된 다섯 개뿐이다.

결과가 이미 있으므로 같은 CLI를 다시 실행하면 덮어쓰지 않고 `FileExistsError`로 중단한다.
최초 실제 실행의 성공 근거는 위 exit0/sentinel 기록이다. 실패나 부분 JSON이 생겼을 때도
자동 삭제/덮어쓰기하지 않는다. 재실행이 필요하면 소유자가 새 출력 위치/새 revision을
명시적으로 승인해야 한다. 이번에는 실패한 실제 실행이나 부분 결과가 없다.
