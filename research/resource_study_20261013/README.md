# 현재 연구 준비 산출물

## 현재 사용자 경계

초기에는 데이터 선정 평가를 우선해 새 전처리·학습을 보류했다.
이후 사용자가 **원인 진단 정확도 중심의 연구 구체화와 스모크 테스트**를 요청하여,
SN/TT의 허용 개발 자료로 새 사건 분리 bundle과 공유 관계 원형을 만들고
각5epoch·1seed·fold0의 제한된 실행까지 완료했다.
이는 전체 성능 실험·사후 튜닝·최종시험의 재개를 뜻하지 않는다.
후속 선택에서 사용자가 **RCABench 실제 사건 수 확인**을 골라, 해당13.445GB 아카이브
확보와 내부 적합성 검수는 진행한다. 상태는 `../rcabench_assessment_20261013/README.md`에 기록한다.
RCABench 선택 자체는 학습 승인이 아니며 위 스모크와도 별도 작업이다.
RCABench 확보·검수는 후속 지시에 따라 후순위 백그라운드로 진행했다.
2026-10-14 해당 확보·검수를 완료했다. [실제 검수 보고서](../rcabench_assessment_20261013/REPORT.md)의
1,422/369/350은 각각 전체 사례/단일 항목 정답/최소 관측 지원 수이며 독립 최종 사건 수가 아니다.
이 폴더의 문서/metadata 점검 결과는 실험 완료나 최종 데이터 선정 승인이 아니다.
RCAEval 최종36건과 native test 창은 새 개발 산출물에 포함시키지 않는다.

## 준비된 자료

- **[최신 논문형 스모크 보고서](../relationship_smoke_20261013/REPORT.md)**:
  실제 사건 분리,3모드×2자료의5epoch 실행,24개 검사와 checkpoint 재실행 결과.
- [새 개발 산출물·실행 안내](../relationship_smoke_20261013/README.md):
  `artifacts/`와`runs/`, 원수치·재현 명령.
- [실제 3-fold 분할 메타데이터 검증](../relationship_split_audit_20261013/README.md):
  SN/TT의 여섯 사건 분할·few-shot 목록 검증 PASS. 새 특징 적합이나 모델 학습은 하지 않았다.
  각 fold에서 SN 4개/TT 9개 recording은 양쪽에 공유된다.
- [요청 경로·지연 분해 선행연구 대조](REQUEST_PATH_PRIOR_ART.md):
  CRISP·MicroHECL의 기제와 입력 요구, 벽시계 잔여·critical-path 귀속·CPU 시간의 차이.
  실제 자기 시간 특징이나 추가 모델 실험을 실행한 결과는 아니다.
- [선택적 진단 방향 제안 — 보류](PAPER_DIRECTION.md):
  사용자가 이후 정확도 중심을 선택했으므로 현재 주제가 아니다.
- [문제·차별성 재설계](RESEARCH_REDESIGN.md): 공유 분석기+관계 정보의 기존 연구,
  실제 관측 근거, 좁은 문제 후보·가설·중단 기준. 새 모델·실험은 미실행.
- [원인 미학습 대상과 DéjàVu의 중복 검토](COLD_ROOT_PRIOR_ART.md):
  앞서 제안한 조건은 새로운 문제라고 확정할 수 없으며, 공유 점수기·미관측 unit 평가의 선행 근거가 있다.
- [연구 문제·선행연구·실용성 재검토](연구문제_재검토.md): 사용자8개 질문에 대한
  도메인/문제 범위/문헌 평가/개선 가능성/미관측 장애/다음 방향 검토. 제안이며 새 실험은 미실행.
- [교수님 보고 초안](교수님_보고초안.md): 기존 성능 근거, 비교군·비용 계획,
  데이터 부족과 미입증 주장을 구분한 내부 문서. 외부 발송하지 않았다.
- [데이터 선정 점수 초안v2](DATA_SELECTION_SCORECARD.md): 현재 확인한10개 후보, 용도별 제한.
- [RCABench·LEMMA-RCA 신규 평가](NEW_CANDIDATE_EVALUATION.md):
  초기 공식 metadata 평가와 후속 실제 검수 연결. RCABench 초기70점은 현재 선정 판단에서 보류.
  RCABench 코드 ZIP 약2MB의 후속 검수로 배포 선택 규칙과 복수 서비스 정답 가능성을 확인했다.
  실제 사례 수는 확인했지만, 단일 원인/현재9채널/독립성 관문은 별도다.
- [RCABench 1차 인벤토리 도구](RCABENCH_INVENTORY.md):
  로컬 파일의 정답·기간·필수 파일 집계용. 실제1,422사례를 집계했으며 다운로드 기능은 없다.
- [OpenRCA·GAIA 실제 metadata 검수](OPENRCA_GAIA_FINDINGS.md):
  압축/해제 크기, 단일 서비스 변환과 주입 사건 후보 수.
- [실제 trace 사전점검](PREFLIGHT_REPORT.md): 부모 연결, 시간 불일치, 오류와 관측 밀도.
- [비교 연구5축 재선별](METHODS.md): DiagMLP/BARO/PRISM/Eadro/TORAI/통제MLP 연구.
- [비용 평가 설계안](COST_PROTOCOL.md): 세 평가축과 측정 경계. 숫자 한도는 미동결 제안.
- [추가 문헌·데이터 연결](NEW_LITERATURE_LEADS.md): 두 신규 후보의 최초 발견 기록.
- [이전 DiagMLP/relative MLP 흐름도](../../generated-images/ig_024168a3126a5a77016ace50f2640c87d09b512f8fba639f44.png):
  이전3,457파라미터 자체 모델의 개요이며 DiagMLP 저자 구현과 완전 동일하다는 주장이 아니다.
  그림의 x는 모델에 전달하는 특징이다. 실제 실행에서는 TRAIN 유효값으로 적합한
  특징 표준화를 적용한 뒤 상대 평균을 계산한다.
- [새 공유 관계 원형 구조도](../../generated-images/ig_024168a3126a5a77016ace7fefd85887d0baf17cb5bc2e8285.png):
  3,361파라미터의 별도 원형이다. 그림의 경계조건 설명은 최신 보고서 캡션을 따른다.

이전 보고 초안·재검토 문서는 작성 당시 상태를 기록한다.
최신 구현·실행 여부는 위 스모크 보고서를 기준으로 읽는다.

## 아직 하지 않은 것

- `DATA_CONTRACT.md`의fold0 개발 산출물은 `../relationship_smoke_20261013/artifacts/`에 생성·검증했다.
  나머지fold의모델실행·few-shot부분집합학습은 하지 않았다.
- 기존 특징을 그대로 재분할하지 않고 원9채널에서 정상 TRAIN 기준을 다시 계산했다.
- RCABench의 gauge/sum/trace 주요 열을 전체 사례에서 검수했다.
  모든 로그 본문·graph/time 인과 정합성·새 독립 최종 사건 확정·본실험은 하지 않았다.
- A/B 일반화/전이, 새 self-time·오류·순위 특징, 앙상블 효과는 미검증이다.
- 비용과 성능의 우위도 아직 미입증이다.

문서가 존재하거나 synthetic/metadata 검사가 통과했다는 사실을
실제 모델 성능과 혼동하지 않는다.
