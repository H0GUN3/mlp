# 재선별 중 추가로 확인한 자료 — 최초 발견 기록

> **후속 평가 완료:** 아래는 평가 범위 확대 전의 최초 확인 기록이다.
> 현재 결과는 `NEW_CANDIDATE_EVALUATION.md`와 평가표v2를 기준으로 한다.
> RCABench70점, LEMMA IT47점의 조건부 평가를 추가했으며 관측자료는 다운로드하지 않았다.

## 왜 추가했나

`DATA_SELECTION_SCORECARD.md`는 당시에 직접 검수한8개 후보의 초안이지
전체 공개 RCA자료 중 최적 순위가 아니다.
선행연구를 다시 읽으며 아래의 직접 관련 자료를 확인했다.
기존 점수표의 범위를 숨기거나 새 후보를 근거 없이 높은 점수로 넣지 않는다.

## Fault Propagation-Aware Benchmark / RCABench

- 논문: *Rethinking the Evaluation of Microservice RCA with a Fault Propagation-Aware Benchmark*,
  공개arXiv v2는 FSE2026 채택을 명시한다.
- 저자 보고: 9,152주입에서 SLI영향을 검증한1,430고장,
  6범주25종류, 동적부하, 서비스부터코드까지의계층정답.
- 이는 논문 보고이며 다운로드 원자료의 사건 수를 우리가 검수한 결과는 아니다.
- 우리 전파/증상 구분 가설에 직접 관련돼 데이터 후보 평가에 포함할 가치가 있다.

공식 Zenodo17105974의 export/json에서 확인한 공개파일:

| 파일 | 바이트 | 현재 해석 |
|---|---:|---|
| rcabench-absolute_anomaly.tar.gz | 13,444,974,981 | 자료아카이브; 실제 내부 사건/스키마는 미검수 |
| rcabench-fse-26.zip | 1,436,695 | 코드명 아카이브; 내용 미검수 |
| rcabench-platform-feat-fse26.zip | 557,891 | 플랫폼명 아카이브; 내용 미검수 |

총13,446,969,567B, metadata라이선스CC-BY-4.0.
**13.445GB 아카이브가 논문의1,430사례 전부라는 연결은 아직 검증하지 않았다.**
현재는 주입별manifest, 단일 서비스 정답 단위, 부모-child trace,
정상 구간/관측기간, 중복·원자료정합성과 전처리비용을 확인하기 전이다.
점수는 미정이며 선정·다운로드하지 않았다.

접근 기록: 일반API는504, project page는인증서검증실패,
동일공식기록의 `export/json`은200으로회수했다. TLS검증을끄지않았다.

출처:
- https://arxiv.org/abs/2510.04711
- https://zenodo.org/records/17105974
- https://zenodo.org/records/17105974/export/json

## LEMMA-RCA

2026년8월 공개v4는 CIKM2026 채택과 마이크로서비스·수처리/배수 등
IT/OT 다중영역 자료임을 명시한다. 모든부분을서비스 RCA자료로세지않는다.
이번에는 논문초록/공식접근연결만확인했다. Zenodo20516735 API는504였고
정확한 IT부분의 크기·사건·trace와 정답단위를 확인하지못했다.
따라서 아직 점수를 매기거나 사용가능한 자료로 약속하지 않는다.

- https://arxiv.org/abs/2406.05375
- https://www.lemmarca.info/
- https://doi.org/10.5281/zenodo.20516735

## 다음 조건

이 문서는 새 자료를 처리하자는 결정이 아니다.
사용자의 '데이터선정평가부터' 지시를 유지하며,
위 후보까지 평가 범위를 늘릴지 정한 뒤 metadata 수준의 확인부터 수행한다.
이후 사용자가 두 후보 평가를 선택하여 metadata 검토까지 완료했다.
최초 기록의 미확인 항목 중 무엇이 해소됐는지는 위 후속 평가 문서에 구분했다.
