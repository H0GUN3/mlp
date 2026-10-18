# 검증 기록

2026-10-16. **요청된 설명·자료 분석: PASS. 새 연구 설정 확정이나 모델 성능 검증은 아니다.**

## 실행 근거

| 항목 | 실제 결과 |
|---|---|
| metadata 추출 자기검사 | PASS |
| 기존 archive 전체 순회 | `METADATA_EXTRACTION_PASS`, exit0 |
| 분석 자기검사 | `METADATA_ANALYSIS_SELF_TEST_PASS` |
| 전체 metadata 분석 | `METADATA_ANALYSIS_PASS 1422 types 25 SLI flagged 1422`, exit0 |
| 독립 대조 | `RCAB_METADATA_VERIFICATION_PASS 1167 1146 760`, exit0 |
| 세 Python 스크립트 LSP | 진단 없음 |
| 보고서 18개 질문 순서·누락 검사 | `REPORT_QA_PASS`, 18개 모두 존재 |
| 로컬 근거 경로 검사 | 14개 모두 존재 |
| 고장 종류 표의 ID·이름·건수 대조 | `FAULT_TABLE_QA_PASS`, 25행 모두 일치 |

분석 monitor `mon_A0WBJYGQTRSQBJ76`와 독립 대조
`mon_YNH1XSE7NT9BPTQB`의 실제 종료 이벤트에서 exit0을 받았다.
오래 기다리거나 결과를 추정한 상태가 아니다.

## 정합성

- 원 metadata, 기존 inventory, quality, 새 분석의 사례 집합1,422개 일치.
- 25종류 건수 합과 5개 설정 범위 건수 합이 각각1,422.
- 원라벨 cardinality369/1,053을 원 JSON에서 독립 대조.
- 원 Issues JSON으로 모든1,422건의 source SLI flag를 다시 집계.
- 같은 namespace의 양의 관측 중복0쌍을 별도 완전 쌍대 비교로 대조.
- 단일 설정 표적 검토 후보1,167건과 기초 관측 지원1,146건을 별도 집계.
- 기존 관측 file hash와 추출된 metadata member hash 일치.
  archive 전체 MD5는 이번에 다시 계산하지 않았다.
- `verification.json`에 입력과 스크립트 sha256을 보존.

주요 source hash:

```text
analyze_metadata.py
47ce982f2d38da153e5ca76ed766bfe820966d78ffa6a3d523bdf1bdbb75d7e4

verify_analysis.py
ab2147915a9d6c8f060d462980ba0e386377af8b21c1560ba70c06b3ddd15712
```

## 설명 검증

실제 로컬 시간 풀링·DiagMLP 결합·공유 상대 점수·채점 코드를 대조했다.
원문 Eadro/DiagMLP/TVDiag/DeepHunt/Transformer/RCABench와 연결했고,
재현본·자체 처리·원문 주장·조건부 예상·실측을 구분했다.
시각의 `int()` 처리를 반올림이 아니라 소수부를 버리는 정수화로 바로잡았다.
RCABench 원문은 확인한 v2의 §4.7을 인용했다.

## 실행 경계

이 작업의 파일 생성은 새 분석 폴더에 한정했다. 기존 원자료·분할·모델은 변경하지 않았다.
허용된 metadata/결론 요약과 기존 품질 결과를 사용했고,
보호된 RCAEval 최종36건·native 최종 관측은 열지 않았다.
새 설치·데이터 다운로드·모델 특징 cache·학습·새 분할·최종 성능평가는 하지 않았다.

아직 확인하지 않은 것은 raw SLI 재검정, 실제 fault 활성화/정확한 생성 revision,
전체 후보/배치 관계와 독립 수집 경계, 새 모델의 성능이다.
따라서1,167건은 합의된 학습 수가 아니며 Transformer/상대 모델의 향상도 주장하지 않는다.
