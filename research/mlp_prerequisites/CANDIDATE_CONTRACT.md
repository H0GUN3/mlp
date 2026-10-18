# 원인 서비스 후보의 정규화 — 첫 학습 이전 확정

## 관측된 실패

첫 `run`은 입력 검사에서 중단됐다. 검증의
`re2ob_checkoutservice_cpu_2`에만 보인 `InboundPassthroughClusterIpv4`,
`PassthroughCluster`가 학습 어휘에 없었다.
이 시점에는 어떤 모델의 학습이나 검증 정확도 측정도 수행되지 않았다.

## 근거와 적용 규칙

Istio 공식 문서는 PassthroughCluster를 Envoy 설정의 **virtual cluster**로
정의하며 `destination_service_name`에 이 내부 식별자가 나타날 수 있음을 설명한다.
Istio 1.22.0 소스는 아래 네 이름을 networking util 상수로 정의한다.

- BlackHoleCluster
- PassthroughCluster
- InboundPassthroughClusterIpv4
- InboundPassthroughClusterIpv6

이번 과제의 정답 단위는 애플리케이션 **원인 서비스**다.
위 네 프록시 내부 클러스터 이름은 모든 시스템/사고/방법에서 동일하게
후보 및 노드 입력에서 제외한다. 그 노드에 접한 관계도 제외하되, 우회 관계를
새로 만들어 연결하지 않는다. 원 추출 특징은 수정하지 않고 제외 목록을 결과에 기록한다.

이는 “검증에서 모르는 이름이면 삭제” 규칙이 아니다.
새로운 실제 서비스가 나타나면 여전히 오류로 중단한다.
위 이름이 정답으로 지정돼 있다면 정답을 바꾸거나 사례를 버리지 않고 오류 처리한다.
case/root/fault label을 보고 예외 목록을 선택하지 않는다.

원 분할·사전 명세·raw/cache는 변경하지 않았다. 이 추가 계약의 hash를 학습 결과에
기록하며, 모델 성능을 확인한 뒤 바꾼 규칙이 아님을 명시한다.
프록시 관측을 버리는 만큼 인프라 장애 진단이나 외부 서비스 일반화까지 주장하지 않는다.

## 출처

- https://istio.io/latest/blog/2019/monitoring-external-service-traffic/
- https://github.com/istio/istio/blob/1.22.0/pilot/pkg/networking/util/util.go
