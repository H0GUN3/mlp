# 주 에이전트의 교차 확인과 해석 범위

로컬 경로는 `/home/gnho1236/r2` 기준이다. 이 보고서 디렉터리 아래가 아니다.
특히 metadata는 `/home/gnho1236/r2/evidence/ops-lite-summary.json`,
`/home/gnho1236/r2/evidence/ops-lite-sample-audit.json`,
`/home/gnho1236/r2/evidence/ops-lite-sample.json`,
`/home/gnho1236/r2/data/ops-lite/manifest.jsonl`에 있다.

- 원문 표를 직접 대조해 DiagMLP 보고서의 GAIA/D1/D2 비교 열 오독을 수정시켰다.
- 최초 검증의 ops-lite "로그만 존재" 판정은 잘못이었다. README/기존 파일 검수
  metadata가 traces/metrics/histogram/sum/logs의 정상·장애10파일을 확인한다.
- 로컬 ops-lite 표본30개의 이름을 manifest455개의 이름과 직접 대조했다.
  metadataRows=455, sampleCases=30, missing=[], allSampleNamesInLocalManifest=true.
  모르는 것은 이 로컬 후보와 공식 논문의500건이 동일 배포인지 여부다.
- RCAEval을 DiagMLP 원 논문의 "충실한 재현 자료"로 추천하는 표현은 수정했다.
  현재 실험의 반복 실행 자료와 원 논문 재현 자료는 다르다.
- 원 논문 수치를 재현하는 것과, 핵심 방법을 보존해 새 데이터에서 공정하게
  비교하는 것도 다르다. 후자는 가능하지만 기존 논문 점수와 직접 우열 비교는 못 한다.
- 기존 방법에서 어떤 단계를 생략했다는 이유만으로 모든 비교가 무효인 것은 아니다.
  장애 시작시점을 모든 방법에 동일하게 알려주고 원인 진단만 비교한다면 BARO의
  진단 단계는 비교 대상으로 설계할 수 있다. 전체 BARO 재현과 구분하고, 점수식의
  논문/코드 차이와 구현 대응을 먼저 명시해야 한다. Eadro의 핵심 입력 인코더와
  결합 구조를 대체한 현재 실험과는 변경의 성격이 다르다.
- 기존 실험 코드/결과는 변경하지 않았다. 이번 문서는 결과의 해석 자격을 재분류한다.
