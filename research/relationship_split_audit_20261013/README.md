# 실제 개발 창의 3-fold 분할 메타데이터 검증

기존 `relationship_smoke_20261013/artifacts/`의 허용 개발 묶음만 입력으로 사용한다.
관측·특징 배열은 로딩하지 않고 `indices`, `labels`, `event_ids`, `episode_ids`,
`fold_ids`, `partition`만 읽는다. 압축 NPZ 전체 바이트는 입력 hash 확인에 사용한다.
원래 native 자료·RCAEval 원자료·checkpoint를 읽거나 수정하지 않는다.

## 실제 결과

2026-10-13, Python3.8.20 / NumPy1.21.5에서 여섯 분할 모두 PASS, exit0.
명시적 프로젝트 Pyright는 오류·경고 0건, 새 단위검사 5개는 0.014초에 통과했다.
세션 LSP 도구에는 `research.*` import 미해결 진단 3건이 남아 있었으므로
LSP 도구까지 무진단이라고 보고하지 않는다. 명시적 프로젝트 검사와 실제 Python import는 통과했다.

| 자료 | fold | TRAIN 고장 창 | TRAIN 정상 창 | validation 고장 창 | validation 정상 창 |
|---|---:|---:|---:|---:|---:|
| SN | 0 | 217 | 45 | 108 | 24 |
| SN | 1 | 227 | 45 | 98 | 24 |
| SN | 2 | 206 | 48 | 119 | 21 |
| TT | 0 | 2,292 | 411 | 1,159 | 207 |
| TT | 1 | 2,278 | 423 | 1,173 | 195 |
| TT | 2 | 2,332 | 402 | 1,119 | 216 |

SN의 36사건/394창, TT의 81사건/4,069창 모두 정확히 한 번 validation에 배정된다.
각 fold의 TRAIN/validation 사건 수는 SN 24/12, TT 54/27이다.
few-shot A/B는 각각 SN 12사건, TT 27사건이며 TRAIN 고장 사건의 비중첩 보완 부분집합이다.
그러나 모든 fold에서 **SN 4개, TT 9개 recording이 TRAIN/validation 양쪽에 나타난다.**
사건 분리와 recording 독립은 다르다는 기존 한계를 실제 목록으로 확인했다.

[기계 판독 결과 및 인덱스 목록](fold_metadata_audit.json)

## 검사와 산출물

`audit.py`는 동결된 `data.event_partition`을 재사용하고 다음 조건을 추가 대조한다.

- 기존 native TRAIN+validation 원본 행과 순서가 정확히 일치하고 test/unassigned는 제외.
- 세 fold에서 TRAIN/validation의 사건·정상 episode 비중첩.
- 동일 recording 내 선택 창의 시간 구간 비중첩.
- 서비스·고장 종류별 사건 수 균형, 각 사건·행의 validation 편입이 정확히 한 번.
- A/B가 서비스당 1사건인 TRAIN 고장 부분집합이며, 서로 겹치지 않고 합치면 전체 TRAIN 고장 사건.
- fold별 정상 TRAIN 창 존재와 기존 fold0 매니페스트 일치.

`fold_metadata_audit.json`에는 여섯 분할의 원본 TRAIN/validation 인덱스,
공통 정상 TRAIN 인덱스, A/B 사건·고장 행 목록과 입력/소스 hash가 기록된다.
이미 존재하는 결과 파일은 덮어쓰지 않는다.

## 재현

프로젝트 루트 `/home/gnho1236/r2`에서:

```text
/home/gnho1236/.local/bin/pyright --project research/relationship_split_audit_20261013
.venv-eadro/bin/python -B -m unittest -v research.relationship_split_audit_20261013.test_audit
.venv-eadro/bin/python -B research/relationship_split_audit_20261013/audit.py --report research/relationship_split_audit_20261013/fold_metadata_audit.json
```

실제 실행에서는 OMP/MKL/OPENBLAS 스레드를 각각 2로 제한한다.
기존 결과가 있을 때 마지막 명령을 무조건 반복하지 않는다.
불변인 기존 모델 검사는 재실행하지 않는다.

## 검사 과정에서 발견한 문제

- 기존 합성 fixture는 정상 창이 마지막 고장 주변에 몰려 있었다. 모든 fold의 정상
  TRAIN 지원을 검사하자 한 fold에서 올바르게 거부됐다. 통과용 fixture는 고장을
  시간상 분산했고, 원래 fixture의 정상 TRAIN 부족을 거부하는 테스트도 유지했다.
- Python3.8로 기존 준비기를 실행했을 때 소스 키 `data.py`가 상대 경로로 기록됐다.
  새 검사기의 절대 경로와 직접 비교해 실패했으나, 실제 소스 4개의 해시는 모두 동일했다.
  새 검사기에서 원래 준비기 폴더 기준으로 경로를 정규화하고, 중복 별칭은 거부한다.
  다른 해시를 허용하지 않으며 기존 매니페스트나 소스를 수정하지 않았다.

## 반드시 구분할 것

**이 결과는 분할 메타데이터 검증이지 3-fold 모델 교차검증 성능이 아니다.**
fold1/2의 정상 참조·특징·표준화는 이번에 계산하거나 검증하지 않았다.
fold0의 `x`, 정상 참조, 학습된 표준화를 다른 fold로 그대로 가져가면 안 된다.
추후 실행한다면 해당 fold의 정상 TRAIN으로 참조를 새로 적합해야 한다.

A/B가 비중첩이라는 뜻은 **고장 사건/행**에 관한 것이다.
계약에 따라 정상 TRAIN 참조 풀은 두 부분집합에 공통이다.
모델용 특징 표준화에는 선택한 고장 부분집합과 허용 정상 TRAIN만 포함해야 한다.

한 recording의 서로 다른 사건은 TRAIN/validation 양쪽에 있을 수 있다.
따라서 recording 독립·시간 순방향·새 시스템·cold-root 검증이 아니다.
창 인덱스/구간 비중첩은 span 완료 시각 가용성이나 물리적 clock 정합성을 증명하지 않는다.
이미 개발에 사용했던 사건이며 새 미접촉 최종평가로 취급하지 않는다.

## 설정 탐색과 최종평가의 역할

| 자료/결과 | 현재 역할 | 금지할 해석·행동 |
|---|---|---|
| 현재 SN/TT의 세 fold와 few-shot A/B | 개발·설정 탐색용 분할 목록 | 이미 사용한 사건을 새로운 최종 사건이라고 부르지 않음 |
| 완료된 fold0 스모크 | 제한된 개발 실행·결과 | 사후 설정 선택에 쓴 결과를 독립 최종평가로 재명명하지 않음 |
| 원래 native test/unassigned 창 | 이번 추가 검증에서도 제외 | 원래 창 단위 분할을 새 독립 사건 최종평가로 취급하지 않음 |
| RCAEval 최종36건 | 기존 봉인 유지 | 원자료 접근·전처리·튜닝·평가 미실행 |
| RCABench | 확보·적합성 검수 대상, 실험 역할 미정 | 확인 전 유효 사건 수나 최종평가 적합성을 확정하지 않음 |

새 최종 자료의 선정·분할·실행 승인은 이 감사에서 수행한 일이 아니다.
추후 final 역할을 정하기 전에 사건 중복·수집 조건·입력 적합성을 확인해야 한다.
