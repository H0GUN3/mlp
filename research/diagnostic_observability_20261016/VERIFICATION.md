# 관측 감사 검증과 실행 경계

2026-10-16. **감사 PASS, 교정 학습·평가 미실행.**

## 실제 완료 근거

| 실행 | 실제 완료 |
|---|---|
| `rcab_audit.py --self-test` | `OBSERVABILITY_SELF_TEST_PASS` |
| HTTP전수+14사례정밀감사 | `OBSERVABILITY_PASS 3220 287611229`, exit0 |
| 같은요청추가대조 | `FOCUSED_LINK_SELF_TEST_PASS`, `FOCUSED_LINK_PASS 4`, exit0 |
| 결과독립대조 | `OBSERVABILITY_RECONCILIATION_PASS 796 14 287611229`, exit0 |
| SN/TT허용개발감사 | `SN_TT_AUDIT_PASS`, exit0; 별도87개대조 PASS |
| 보고서수치·범위대조 | `REPORT_EVIDENCE_PASS` |

HTTP전수 monitor: `mon_SN0JVKXXR572S3PH`.
추가대조 monitor: `mon_JPP5SZCRS3812B90`.
독립대조 monitor: `mon_7T6BVS257H54HZQ8`.
모두 종료 이벤트로 실제 exit0을 확인했다. 실행 중인 감사는 없다.

## 실패와 수정

초기 LSP에서 pyarrow의 동적 compute 함수 속성과 sibling namespace import를
해석하지 못했다. 기존 감사의 `call_function` 방식과 기존 프로젝트의
명시적 파일 기반 module 로딩 패턴으로 수정했다. 타입검사를 끄거나 ignore하지 않았다.
수정 후 `rcab_audit.py`, `rcab_focused.py`, `verify_observability.py` 진단 없음.
SN/TT 담당도 `sn_tt_audit.py`의 진단 없음을 확인했다.

초기 비용 metadata 확인의 상대경로는 기준 폴더를 잘못 지정해 ENOENT였다.
native_reproduction 폴더를 기준으로 바로잡고 기존 SN200의 실제 비용을 읽었다.
기존 결과·원자료는 수정하지 않았다.

## 감사 계약 검사

- 원래 archive member 경로·크기·sha256과 새로 읽은 파일을 대조.
- 전체 HTTP796사례 및 사전선정14사례의 필수 파일 완전성 검사.
- 새결과 파일 수/행 수, HTTP알려짐/오류 분모, 시간경계 분모 확인.
- parent연결/Client-Server쌍/로그연결 분모와 상하한 확인.
- 추가4파일의hash 및 연결결과를 본감사와 대조.
- 코드와 결과 SHA-256을 JSON에 기록.
- 정상/장애의 구분, Error/Unset/HTTP상태, 중복ID충돌, 0코드미확인, 비유한metric,
  로그의 ID없는행을 자기검사로 확인.
- 출력은 독점생성이며 기존결과를 덮어쓰지 않는다.

## 문헌과 해석

Eadro/DiagMLP, TVDiag/DeepHunt/원GraphRAG의 원문을 대조했다.
원문 정의와 공개 포크·로컬 복원본을 구분했다.
정확한 DiagMLP 저자 통합코드를 확보한 것으로 쓰지 않았다.
명시적 수식기반 복원으로 통제 비교는 가능하되 정확한 논문 점수 재현은 아니다.

시간순서 손실은 실제 자료로 증명했지만 그 손실의 정확도 효과는 검증하지 않았다.
같은요청 UI500/backend200은 실제 관측이며 전체 인과 식별의 보증이 아니다.
14표본결과,796HTTP전수결과,기존1422metadata결과의분모를섞지않았다.

## 미완료와 다음 조건

요청된 교정 분할 평가를 완료했다고 주장하지 않는다.
첫 평가자료에 대한 필수 선택 질문(`corrected_evaluation_dataset`)이 열려 있다.
답변 전 새 학습·분할 할당·보호된 최종 관측 접근은 하지 않는다.
GraphRAG, 새Transformer, 상대공유방법의 추가 실험도 하지 않았다.
