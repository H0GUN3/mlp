# 조사·설계 검증 기록

## 사용자 다섯 항목과 산출물

| 요구 | 산출물 |
|---|---|
| 승인된 상위 과제 확정 | SCOPE.md, REPORT.md §1 |
| 기존 방법·유사 비교군·문제점 조사 | METHODS.md, REPORT.md §2/4/6 |
| 개선 모델/모듈 설계 | DESIGN.md, REPORT.md §7 |
| DiagMLP 전체 방법·GNN 비교 구조·결과 설명 | DIAGMLP.md, REPORT.md §3/5 |
| 좁은 개선 기회와 정량 검증/기각 경로 | DESIGN.md §4–7, REPORT.md §8 |

두 독립 조사 child가 각각 DIAGMLP.md와 METHODS.md만 작성했다.
부모가 두 문서를 읽고 설계·종합을 수정했다.
전체 AIOps나 수십 개 모델로 조사 범위를 확장하지 않았다.

## 논문·공개 코드 확인

- DiagMLP v2의 Eq.(2)–(3), Table I–IV, §IV–V를 확인했다.
  별도 worker가 원 HTML 표의 rowspan을 풀어 Table IV의 15행×6모델=90개
  결과 셀 및 ±/미보고 셀과 인용 mapping을 대조했다.
- 최종 보고서에 쓰는 직접 비교 Top1 평균 차이는 부모가 별도 산술로 확인:
  SN+38.4, TT+7.4, GAIA+1.2, D1 0.0, D2+0.1 percentage points.
  SD나 p-value를 계산한 것이 아니며 재학습·재평가 결과가 아니다.
- 원문 TT Top3>Top5, D1 본문 모델 매핑 오류를 숨기지 않았다.
  일부 지표의 열세·동률도 상세 보고서에 보존했다.
- Eadro 인코더·GLU·GAT 및 TVDiag/DeepHunt의 선행 구성을 원문/공개 소스에서 대조했다.
  정확한 링크·revision·본문 절은 METHODS.md/DIAGMLP.md에 있다.
- 부모가 pinned FeiGSSS/Eadro `7d69281a80adce60067aa858729746fc6a362f53`의
  `codes/preprocess/single_process.py::deal_traces`와 `align.py::get_chunks`를
  raw source에서 직접 확인했다. `invok` count는 계산·cache되지만
  model-facing chunk에는 `traces["latency"][idx]`만 전달된다.
  source method를 실행한 것이 아니라 구조를 읽고 대조했다.

## 합성 정보 보존 확인

부모 Python kernel에서 실제 데이터/모델 없이:

```text
A: 10초, 각 초마다 서로 다른 10ms span 1개 → 고유 span 10개
B: 10초, 각 초마다 서로 다른 10ms span 10개 → 고유 span 100개
각 초별 평균 latency(A) == latency(B): np.array_equal PASS
```

`SYNTHETIC_SUPPORT_WITNESS_PASS`.
이는 mean만으로 count를 복원할 수 없다는 좁은 표현상의 사실이다.
실제 baseline 오류나 count 추가의 성능 효과를 검증한 결과가 아니다.

## 설계 수정과 중복 확인

- Eadro의 GLU, TVDiag의 공유 scorer/관측 비활성화, DeepHunt의 request count/
  feature masking/ranking을 새 발명으로 주장하지 않는다.
- 최초 q=[unique count, occupied-second ratio] 초안을 조사 결과로 축소:
  최종 DESIGN.md는 **q=log(1+unique span count) 한 항목**이다.
  METHODS.md 후반의 두 항목 q는 당시 잠정안을 대조한 기록이다.
- occupancy는 양수 duration일 때 표준화 전 latency에서 유도될 수 있어
  새 정보라고 볼 수 없다는 반론을 반영했다.
- count 활용도 DeepHunt와 상당 부분 겹친다. 이번에 선택한 것은
  특정 Eadro-compatible 경로에서의 검증 후보이지 신규성·성능의 확정이 아니다.
- “관측 count = 수집 신뢰도/독립 요청 수”라는 잘못된 해석을 금지했다.

## 확인하지 않은 것

원 저자의 정확한 backbone별 wiring/config/split, 모델의 실제 효과·비용,
우리 조건의 native-like 기준 모델 오류, 통계적 유의성·새 사건 일반화는 미확인이다.
현재 자체 모델의 짧은 학습 결과와 원논문 결과를 혼합하지 않았다.

모델 구현·훈련·튜닝·원자료 재처리·보호 평가자료 접근·설치·프로젝트 커밋 없음.
이번 산출물은 문서이므로 build/type test를 연구 효과의 검증으로 대체하지 않았다.

## 최종 문서 QA

`METHODOLOGY_REPORT_QA_PASS`:
상세 DiagMLP 표에서 최종 REPORT의 직접 Top1 비교 5행을 재구성해 모두 일치,
최종 DESIGN의 count 단일 항 및 h개 추가 가중치 계약 확인,
6개 문서의 로컬 근거 링크 13개 파일 존재 확인.
검증 전 가설과 실행하지 않은 실험을 완료 성능으로 표현하지 않았는지 마지막으로 대조했다.
