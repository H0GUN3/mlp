# 사건 단위 개발 데이터 계약

> **실행 상태:** 후속 스모크 요청으로 fold0의 실제 SN/TT 개발 산출물을
> `../relationship_smoke_20261013/artifacts/`에 생성하고 검증했다.
> 원9채널 재구성, 정상 TRAIN 전용 참조, 사건 비중첩, native test 제외,
> 재로딩·해시·validation 변경 불변 검사가 통과했다.
> 새모델 실행은3모드×2자료·각5epoch·seed11로 제한했다.
> fold1/2의 모델 실행, few-shot A/B 학습, 새 최종평가는 하지 않았다.
> 상세 조건·시간 가용성 한계·실제 결과는 `../relationship_smoke_20261013/REPORT.md`를 따른다.

> **후속 메타데이터 감사:** `../relationship_split_audit_20261013/README.md`에서
> 실제 허용 SN/TT 창을 대상으로 세 fold와 few-shot A/B의 사건·행 비중첩을 확인했다.
> 원본 인덱스 목록은 같은 폴더의 `fold_metadata_audit.json`에 있다.
> 이 검사는 fold1/2의 정상 참조·특징 재적합이나 모델 교차검증을 뜻하지 않는다.

## 입력 경계

기존 `method_mlp_20261013/features.py`의 검증된 원자료 로더/trace 복구 함수를 재사용한다.
예전 정상 참조를 적용한 x를 그대로 재분할하면 새 validation 사건의 정상 구간이
참조 계산에 들어갈 수 있으므로 **9채널 원 관측에서 fold별 정상 참조를 다시 계산**한다.
기존 native seed42 TRAIN+validation 창만 허용하며 native test/unassigned는 제외한다.
RCAEval 원자료 접근은 없다. 기존 파일은 변경하지 않는다.

## 독립 단위와 분할

1. 기존 metadata의 event_id를 한 고장 주입 사건으로 사용한다.
   복합/모호한 event_id나 서비스당3종×각1회 계약 불일치는 오류로 남긴다.
2. 정상 창은 동일 recording에서 가장 가까운 고장 구간에 귀속한다.
   창과 고장 구간의 시간 간격을 사용하고 동점이면 더 이른 사건으로 결정한다.
   모든 귀속을 manifest에 기록하며 정답 서비스는 특징으로 전달하지 않는다.
3. 시스템마다 서비스 이름을 고정 seed20261013과 함께 SHA256한 순서로 정렬한다.
   고장 종류는 사전식 정렬3개를 고정한다.
   서비스 순서 j, 고장 종류 순서 k인 사건의 validation fold는 (j+k)%3.
   SN12/TT27은3의 배수이므로 fold마다 종류별 사건 수도 균형이다.
4. fold0/1/2를 각각 validation으로 하고 나머지 사건을 train으로 한다.
   고장 창과 그 사건에 귀속된 정상 창은 같은 fold 배치를 따른다.
   각 fold의 TRAIN/validation에 모든 원인 서비스가 지원된다.
5. 한 recording의 다른 사건은 분할 간 공유될 수 있다. 따라서 사건 비중첩이지
   recording·날짜·시스템 독립 평가가 아니다.
6. 사건들은 이미 과거 개발에서 관측됐다. 새 최종시험이나 새 수집 자료가 아니다.

## 적은 라벨 부분집합

각 validation fold에서, 서비스별 held-out 종류 k를 기준으로
(k+1)%3 사건만 택한 subset A와 (k+2)%3 사건만 택한 subset B를 만든다.
각 subset은 서비스당1사건이며 모든 서비스/고장 종류가 지원되고 서로 보완적이다.
전체 train은 서비스당2사건이다. 각 fold의 정상 TRAIN 창은 두 subset에 공통 제공한다.
부분집합은 모델 성능을 보지 않고 만든다. 미래 실행기의 특징 표준화도
해당 subset의 선택된 TRAIN 관측에서만 학습해야 한다.

## 출력

- 시스템별 허용된 원 관측 묶음: values/observed [rows,N,10,9],
  labels, original_indices, event_ids, episode_ids, window_start/run_id.
- fold별 `x/mask/coverage` [rows,N,18]와 partition, 라벨/원본 인덱스.
  fold의 정상 TRAIN만으로 median/IQR을 새로 적합하며 모델용 추가 표준화는 하지 않는다.
- fold별 reference, train/validation 원본 인덱스, few-shot A/B 및 전체 train 사건
  목록/행 목록, 입력·소스·산출물 해시, 원시 바이트 크기와 압축 파일 크기.
- 검증 결과: 사건/창 비중첩, test 제외, 모든 후보/라벨 보존, 종류/서비스 지원,
  정상 참조 TRAIN 전용, validation 값 변경에 TRAIN 참조 불변,
  old-frozen 산출물 미수정, 파일 해시·재로딩 일치.

이 묶음은 현재 자체 모델의 메트릭+trace 실험용이다. 로그/Hawkes가 필요한
문헌 원형의 완전한 전처리 결과를 대신하지 않는다. 같은 사건 manifest를
다른 방법의 고유 전처리에 적용하는 연결점과 필요한 추가 작업을 README에 명시한다.
파일 존재/검증은 학습 완료나 경량성·성능 향상의 증거가 아니다.

## 합성 사건으로 확인한 설계 조건

실제 관측·정답 파일을 읽지 않고 서비스 인덱스12개/27개×고장 유형3개의
합성 사건 목록에 위 `(j+k)%3` 규칙을 적용했다.
각 시스템의3개 fold 모두 아래 수량과 비중첩 조건을 통과했다.

| 합성 구성 | 전체 사건 | fold별 TRAIN | fold별 validation | few-shot A/B 각각 | validation 유형별 |
|---|---:|---:|---:|---:|---:|
| SN 형태: 12×3 | 36 | 24 | 12 | 12 | 4 |
| TT 형태: 27×3 | 81 | 54 | 27 | 27 | 9 |

assert 검사: TRAIN/validation 사건 교집합 없음, 모든 사건이 정확히 한 번
validation에 포함, 각 역할의 서비스·유형별 수량 균형,
few-shot A/B 교집합 없음 및 합집합이 전체 TRAIN과 일치.
결과는6개 fold 모두 PASS다. 해시로 서비스 순서를 바꾸더라도 그 순서의
인덱스0부터N−1에 적용하는 수량 조건은 같다.

이 절의 PASS는 **설계 산술 검증**이다. 이후 fold0 실제 실행에서 허용 창의 사건 지원,
계약에 따른 정상 창 귀속, TRAIN 전용 기준값, native test 제외와 산출물 재로딩도 확인했다.
하지만 실제 시계의 물리적 정합성이나 수집 세션 독립성을 입증한 것은 아니다.
합성 검사 자체를 실제 자료 검수나 다른 fold의 모델 실행으로 읽지 않는다.

또한 이 설계는 모든 원인 서비스가 TRAIN에도 나타나는 **미관측 사건 조건**이다.
`연구문제_재검토.md`에서 제안한 **원인 라벨이 없던 서비스 조건(cold-root)**과 다르다.
후자를 채택한다면 서비스별 원인 사건 전체를 제외하는 별도 계약이 필요하며,
현재 문서의 PASS를 cold-root 일반화 근거로 사용할 수 없다.
