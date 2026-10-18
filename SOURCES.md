# 출처와 신뢰 수준

확인일: 2026-10-12. 파일의 공개 여부, 저자와의 연결, 정답의 타당성은 별개의 판단이다.

## 1. RCAEval

- 논문: <https://arxiv.org/html/2412.17015v4>
- 출판 DOI: <https://doi.org/10.1145/3701716.3715290>
  - WWW Companion 2025, pp. 777–780. WWW 본회의 장문 논문으로 표기하지 않는다.
  - 장애 사례별 원인 서비스·원인 지표를 제공하는 벤치마크이다.
- 저자 코드: <https://github.com/phamquiluan/RCAEval>
  - README에서 아래 Hugging Face 배포본을 명시적으로 추천한다.
- 확보 배포본: <https://huggingface.co/datasets/phamquiluan/RCAEval>
  - 고정 커밋: `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`
  - 카드: MIT. 원본 파일을 Parquet로 변환한 배포본이며, 변환의 무손실성은
    배포자 설명이다. 이번 검사에서 과거 JSON/CSV 전체와 대조한 것은 아니다.
- 이전 공식 배포: <https://zenodo.org/records/14590730>
  - DOI `10.5281/zenodo.14590730`; API의 라이선스는 CC-BY-4.0.
  - Hugging Face의 MIT 표기와 다르다. 두 곳의 조건이 동일하다고 단정하지 않는다.
    연구에서 논문·원 배포·사용 버전을 모두 인용하고, 재배포 시 적용 조건을 확인한다.

## 2. OpenRCA 2.0 논문과 ops-lite 후보

- 논문: <https://arxiv.org/html/2606.27154v2>
  - v1과 최신 v2를 확인했다. arXiv에 `work in progress`로 표시된 프리프린트이다.
  - 500건, 시스템별 320/38/142건을 기술한다.
  - A.5는 과정 보상 모델 학습 가능성을 제시하지만, 평가 대상 에이전트를
    같은 벤치마크로 학습하면 시험 데이터 누출이라고 경고한다.
  - A.6는 데이터 CC-BY-SA-4.0, 파이프라인 코드 Apache-2.0이라고 설명한다.
  - 논문 자체의 arXiv 문서 라이선스와 데이터 라이선스를 혼동하지 않는다.
- 별도로 확보한 후보: <https://huggingface.co/datasets/anon-ops/ops-lite>
  - 고정 커밋: `581eba39d0bfd2d397eded6cd7cbe3303255521a`
  - 카드에는 OpenRCA 2.0이라는 이름, 455건, Apache-2.0이 기재되어 있다.
  - 논문과 사례 수·시스템별 구성·라이선스가 다르다. 이름이 같다는 이유만으로
    논문의 최종 공식 500건과 동일시하지 않는다.
  - `label.json`의 required/optional/not_effective를 구분한다.
    `injection.json`의 모든 주입 대상을 원인 정답으로 쓰지 않는다.
  - `causal_graph.json`은 배포자가 검증했다고 기술한 그래프이다. 파일 간
    일관성 검사만으로 실제 인과관계의 정확성을 독립 입증할 수는 없다.
  - 학습/평가 입력에서 env/injection/label/causal_graph 및 사례명 등 정답 단서를 제외한다.
- 이전 대화의 다른 후보:
  <https://huggingface.co/datasets/lincyaw/openrca2-lite-v1>,
  <https://huggingface.co/datasets/lincyaw/openrca2-lite-v2>
  - 공개 API 접근에서 인증 오류 응답을 직접 확인했다. 현재 공개 다운로드를
    확보하지 못했으며, 비공개/삭제/이름 변경 중 무엇인지 단정할 수 없다.
  - 확인한 논문·저자 자료에서 이 정확한 URL들 또는 `anon-ops/ops-lite`를
    공식 배포본으로 지정한 연결은 찾지 못했다. 이는 비공식임의 증명은 아니다.

## 보관된 근거

- `evidence/rcaeval-paper-v4.html`
- `evidence/openrca2-paper-v1.html`
- `evidence/openrca2-paper-v2.html`
- `evidence/rcaeval-zenodo-14590730.json`
- `evidence/rcaeval-author-README.md`
- 각 데이터 디렉터리의 고정 버전 `README.md`
- `evidence/*-tree.json`: 고정 버전 배포 파일 목록과 크기/해시
- `evidence/*-downloads.json`: 확보 파일별 원본 URL·해시·검증 결과

온라인 출처는 앞으로 변경될 수 있다. 보고서의 수치는 고정 커밋과 실제 로컬 검수에
한정되며, 다른 버전·데이터 전체·다른 시스템으로 일반화하지 않는다.
