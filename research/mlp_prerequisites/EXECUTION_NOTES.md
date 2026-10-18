# 실행 중 확인 및 수정 내역

아래 수정은 모델 학습/성능 측정 **이전**에 이루어졌다.
원래 PROTOCOL.md와 split.json/lock은 변경하지 않았다.

- DGL1.1.3이 packaging 의존성을 누락하여 import가 실패했다. 격리 환경에
  packaging24.2를 추가한 뒤 torch2.5.1+cpu/DGL1.1.3 import 성공을 확인했다.
- 최초 특징 추출은 도구 시간 제한으로 106/144건 뒤 종료됐다. 모델 학습은 없었다.
  변환 내용은 그대로 두고 사례별 배타 생성 cache와 extractor fingerprint를 추가했다.
  재시도는 완성된 동일 버전 cache를 재사용하며 원자료나 기존 결과를 덮어쓰지 않는다.
- 원 Eadro `preprocess/util.py`의 topology에는 self loop가 포함되어 있다.
  공통 입력 GAT에 관측 호출만 주면 고립 노드/말단 노드의 자체 특징이 사라질 수 있어
  **관측된 각 노드의 계산용 self loop**를 추가했다. 호출 방향을 뒤집거나 다른
  서비스 간 연결을 만들지는 않는다. Self loop를 장애 전파 근거라고 해석하지 않는다.
  저자 GraphModel 소스와 원본 전체 MainModel 오류는 그대로 보존한다.
- 지표 유효성/trace 유효성/service-present 등 이진 mask는 표준화하지 않고 0/1로
  유지한다. 수치 특징의 중심/척도만 학습 자료로 결정한다. 검증 통계는 사용하지 않는다.
- 도구의 기존 LSP 세션이 새 환경을 인식하지 못하는 진단과 별도로,
  project pyrightconfig 및 새 Pyright 프로세스로 정적 검사를 수행한다.
- 첫 학습 명령은 모델 생성/학습 이전에 후보 어휘 검사에서 중단됐다.
  Istio의 `PassthroughCluster`, `InboundPassthroughClusterIpv4`가 실제 서비스로
  섞여 있었다. 공식 정의에 근거한 4개 내부 클러스터의 공통 제외를
  `CANDIDATE_CONTRACT.md`에 따로 고정했고, 새로운 실제 서비스는 계속 실패시키는
  회귀 검사를 추가했다. 원 분할과 추출 특징은 유지했다.

Topology source:
https://github.com/BEbillionaireUSD/Eadro/blob/82ff9c9a7a58a9cd2b713aa78754a73c543a15db/codes/preprocess/util.py
