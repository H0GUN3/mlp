# 독립 최종평가 자료 후보 — 읽기 전용 사전점검

**현재 판정:** 신규 최종평가 세트로 확정된 후보는 없다.
다운로드하지 않은 파일, 다른 압축 형식, 다른 배포 사이트만으로 새 사건이라고 할 수 없다.
현재 SN36/TT81 사건은 모두 이전 모델 학습에 들어갔다.
추가 자료의 독립성·채널 정합성·최종 평가 경계는 점수 확인 전에 결정해야 한다.

## 후보 비교

| 후보 | 규모/형식 | 현재 유리한 점 | 남은 제한 |
|---|---|---|---|
| RCAEval RE3-OB/TT | 60사건. 원본ZIP432,553,753B=0.433GB. 고정 HF 파일299,519,748B=0.300GB | 공개 서비스 정답, 메트릭·trace, parentSpanID/statusCode 명시. 가장 작은 추가 후보 | 코드 수준 고장으로 기존 CPU/네트워크 주입과 분포가 다름. 원인 서비스 OB4개/TT2개뿐. 교차 suite 사건 중복과9채널 단위 정합성 미확인 |
| GAIA MicroSS | 배포 트리의 metric+trace+run 파일3,399,271,835B=3.399GB. business 로그 포함 MicroSS5,759,354,692B=5.759GB | 다른 QR-login 시스템. parent_id/start/end/status_code와 주입 기록 문서화 | 유효 단일 원인 사건 수 미확인.8월 trace 미배포. README Apache2와 LICENSE GPL2 표기 충돌. 배포 파일량이지 해제 후 원자료 크기가 아님 |
| 공식 OpenRCA | 논문335고장. 공식 설명68GB 초과 telemetry, README80GB 저장공간 권고. 정확한ZIP 크기 미확인 | 저자 연결 공개 배포, Bank/Telecom/Market의 실제 스키마 문서화 | node/pod/service 및 다중 고장 정답을 서비스 단일 원인으로 변환해야 함. Drive size 조회403. 데이터별 별도 이용조건/9채널 의미 미확인 |

RE3의 ZIP과 HF Parquet는 같은 벤치마크의 다른 표현이다.
GAIA와 DiagFusion D1도 같은 자료 계보이며 독립 두 데이터셋으로 세지 않는다.
GAIA의6500여 지표/700만 로그나 DiagFusion의`demo_1100`은 고장 사건 수가 아니다.
OpenRCA의 자연어 질문 수 역시 독립 고장 수가 아니다.

## 현재 입력 계약에 맞지 않거나 보류한 후보

- RE1은 메트릭 전용이다.
- RE2-SS와 RE3-SS는 고정 HF/저자 자료 표에서 trace 없음으로 명시된다.
  메트릭+trace 방법의 직접 검증 후보로 추천하지 않는다.
  trace 없는 별도 과제를 사전 정의하면 사용할 수 있다.
- 일부 Figshare 설명의 Sock Shop trace 언급은 구체적 배포 카드와 충돌한다.
  빈 파일을 유효 trace라고 세지 않는다.
- OpenRCA2 원문은500사례지만 저자 연결 공개500사례 배포본은 이번 점검에서
  확보되지 않았다. 로컬 ops-lite455목록/30telemetry와 동일시하지 않는다.
  공식335사례 OpenRCA와도 다른 자료다.

## 최종평가 선택 전에 필요한 것

1. 기존 자료/개발 결과와 사건ID·수집 실행·시간 범위·원본 계보를 대조한다.
   형식 변환본과 논문 간 재사용 자료를 새로운 사례로 세지 않는다.
2. 전체60개 등 후보를 먼저 선언한다. 정답 종류나 입력 품질을 보고 유리한 사건만
   마지막에 남기지 않는다. 스키마 점검이 필요하면 그 용도의 개발 사건을 미리 별도 배정한다.
3. 필수9채널과 추가 self-time/error 특징의 단위·의미·결측 정책을 확인한다.
   CPU라는 열 이름이나 parent ID 존재만으로 호환성을 확정하지 않는다.
4. 새 최종 자료의 root 정답을 특징·서비스별 prior·모델 선택에 사용하지 않는다.
   목표 시스템 정상 자료 보정 여부도 미리 정한다.
5. RE3/GAIA는 현재 SN/TT와 같은 분포의 새 반복 사건이 아니다.
   전이/새 고장 조건 평가(B)와 동일 조건의 미관측 사건 평가(A)를 혼동하지 않는다.
   A를 엄격히 주장하려면 SN/TT의 새로운 독립 실행/반복 또는 적절한 동계열 자료가 필요하다.

**권장 순서:** RE3-OB/TT의 계보·스키마 적합성 점검 → GAIA의 라이선스 및
주입 사건/trace 교집합 확인 → 더 큰 OpenRCA의 단일 서비스 정답 변환 검토.
이는 다운로드 또는 최종 세트 지정 승인이 아니다.

## 근거

- RCAEval 고정 카드/스키마:
  https://huggingface.co/datasets/phamquiluan/RCAEval/blob/afeacb11bcc94dadfd1c8f483ee4377b2b8b614e/README.md
- 원본 파일/라이선스:
  https://zenodo.org/records/14590730
  및 로컬 `evidence/rcaeval-zenodo-14590730.json`(CC-BY-4.0).
  이번 부모 live API 호출은 연결 timeout; 저장 공식 명세의 바이트 수를 사용했다.
- HF 파일별 정확한 크기: 로컬 `evidence/rcaeval-tree.json`, 위와 동일 커밋(MIT 표기).
  전송하지 않고 항목 합산. 전체파일3,442,007,684B.
- GAIA 설명:
  https://github.com/CloudWise-OpenSource/GAIA-DataSet/blob/238a9e24ae0b69e7e05dff112652a3fa62db88fd/README.md
  / 파일크기 https://api.github.com/repos/CloudWise-OpenSource/GAIA-DataSet/git/trees/238a9e24ae0b69e7e05dff112652a3fa62db88fd?recursive=1
  / 실제 LICENSE https://github.com/CloudWise-OpenSource/GAIA-DataSet/blob/238a9e24ae0b69e7e05dff112652a3fa62db88fd/LICENSE
- DiagFusion D1 연결:
  https://github.com/AIOps-Lab-NKU/DiagFusion/blob/9ec3f73ad3de15cb7bbd51d02fde90af0af26514/README.md
- OpenRCA 배포/평가:
  https://github.com/microsoft/OpenRCA/blob/c1bd4af7f635171a1c31cdd567c07d698dff6abc/README.md
  / 논문 https://openreview.net/forum?id=M4qNIzQYpd
- OpenRCA2 공개 조건/정답 범위:
  https://arxiv.org/html/2606.27154v2#A1

GAIA 파일 합산·라이선스 및 OpenRCA 후보 상세는 읽기 전용 자료조사 작업
`st_01a13579`의 고정 commit/API 관측이다. 부모는 핵심 README/입력 스키마 설명을
다시 확인했고, RCAEval의 정확한 크기는 저장 공식/고정 명세로 별도 합산했다.
원자료 다운로드·설치·모델 실행·sealed RCAEval 원자료 열람은 없었다.
