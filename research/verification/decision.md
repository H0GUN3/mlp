# 다음 문서화 단계 연구 게이트 판정

기준일: 2026-10-12. 이는 현재 증거에 대한 사실 판정이며, 최종 방법 선택이나 추가 실험 실행의 승인이 아니다.

## 판정 요약

| 게이트 | 판정 | 근거와 의미 |
|---|---|---|
| 기술 | **PASS (범위 한정)** | `research/verification/smoke-checks.json`: 실제 `scripts/verify_smoke.py` 종료 코드 0, 15개 검사 통과. 고정 스모크 산출물의 일관성과 파이프라인 통과를 확인했을 뿐 진단 성능을 보증하지 않는다. |
| 효능 | **HOLD** | `research/SMOKE_PROTOCOL.md`, `research/smoke/summary.json`, `research/verification/smoke-audit.md`: 사전 정의한 기술적 Top-1 비교는 충족했지만, 유효성·효과·확장 준비를 입증하지 못한다. |
| 신규성 | **HOLD** | `research/verification/baseline-contract.md`: 후보 선별/제한 그래프는 TopoEvo·EG-RCA와 직접 겹친다. 차별화된 기여나 이들 대비 비교 결과는 아직 입증되지 않았다. |
| 데이터 | **HOLD (최종 평가용)** | `research/verification/data-readiness.md`: RCAEval의 `root_cause_service`는 root-service 감독 진단을 지원하지만 final-test 분할은 없고, causal-edge gold도 없다. |

## 기술 게이트 — PASS, 제한적

요청된 명령 `cd /home/gnho1236/r2 && .venv/bin/python scripts/verify_smoke.py`를 실행해 실제 종료 코드 0과 `VERIFY_SMOKE_PASSED`를 확인했다. 검증기는 12개 고유 사례, 48개 고유 예측, 순위·정답 재계산, 조건 집계, 출처 해시 등 15개 검사를 모두 통과했다 (`smoke-checks.json`). 따라서 보고된 스모크 수치를 아래에서 사용할 수 있다. 이는 스모크 실행의 재현성·기술적 무결성 판정이지 외부 타당도나 효능 판정이 아니다.

## 효능 게이트 — HOLD

- 사전등록 기준의 문자 그대로의 비교는 만족한다: 규칙 선별은 Top-1 **2/12**, 전체 호출과 같은 개수 무작위는 각각 **1/12**다. 따라서 규칙 조건이 각 조건보다 관측상 1건 많다는 기술적 신호는 참이다 (`SMOKE_PROTOCOL.md`; 검증 재계산 `smoke-checks.json`).
- 이를 효과 입증으로 해석할 수는 없다. paired 비교에서 세 대조군 각각에 대해 규칙 조건의 승리는 **1건**, 패배 0건, 동률 **11건**이다 (`summary.json`). 표본은 12건이며 통계적 효능 증거나 일반화 근거가 아니다.
- 단순 이상점수 기준은 Top-1 **11/12**, Top-3 **12/12**로 훨씬 강하다. 규칙 조건 Top-3는 **8/12**, 전체 호출·무작위는 각각 **5/12**, 카드만은 **1/12**다 (`smoke-checks.json`). 규칙 조건이 일부 LLM 조건보다 나은 서술적 비교와, 단순 기준점보다 훨씬 약한 관측 결과를 함께 보존한다. 성능 향상 주장은 불가하다.
- 따라서 사전등록된 좁은 비교를 거짓으로 고치지 않되, 이 신호는 한 쌍의 승리에 그치며 full-study 준비를 뜻하지 않는다. 합성 sanity **2/2**는 합성 입력에서 지정 서비스를 1위로 낸 것만 확인한다 (`posthoc-synthetic-sanity.json`); 실제 telemetry를 근거로 한 추론 능력을 인증하지 않는다.

## 신규성 게이트 — HOLD

`baseline-contract.md`에 따르면 제한 그래프/후보 축소 주장은 TopoEvo 및 EG-RCA의 연구 방향과 직접 겹친다. BARO, TORAI, MicroHECL, EviRCA 관련 비교도 아직 계획·참고·미실행이거나 미검증 어댑터 상태이며, 스모크 4조건은 이 논문 방법들의 재현이 아니다. 따라서 현재는 novelty나 기존 방법 대비 우월성을 주장할 수 없다. 문서화 단계에서는 주장 가능한 연구 질문과 비교 범위를 정리하되, 이를 최종 차별성이나 방법론의 확정으로 간주하지 않는다.

LLM은 필수 구성요소로 정당화되지 않았다. 선택적으로 다중 서비스 근거와 관측 호출을 받아 원인 서비스 순위를 내는 역할을 시험할 수는 있으나, 그 추가 가치가 단순 이상점수보다 낮은 현재 관측 때문에 별도 효용 근거가 필요하다. RCA 목표는 복구·remediation이 아니라 **root-service 진단**이다.

## 데이터 게이트 — HOLD (full study); 제한적 root-supervised 경로는 가능

- `data-readiness.md`는 RCAEval RE2 180건 모두 지표 쌍 사용 가능, `root_cause_service` 라벨 존재를 보고한다. 이는 root-service 감독 진단 설계의 기반이다. 다만 smoke의 12건은 장애 유형별 고정 탐색 표본이며, 같은 원인 그룹 반복 사례는 개발용 예약이다.
- final-test split은 아직 없고 manifest에도 시험 목록이 없다. 반복 그룹 누출을 막는 분할 및 예약 개발 36건과 최종 시험의 분리가 문서화·검증되기 전에는 정식 평가를 시작할 준비가 안 됐다.
- **정정:** `cases_with_all_null_metric_columns: 12`는 전체 감사 RCAEval **180건 중 12건**에 대한 집계다. 이는 각 사례에서 일부 메트릭 열이 모두 null이라는 뜻이지, 모든 메트릭 열 전체가 결측이라는 뜻이 아니다. 이 집계를 smoke 12건의 상태로 옮기거나 smoke 영향 건수를 추론하지 않는다.
- RCAEval에는 causal-edge gold가 없다. 트레이스에서 관측한 호출 관계는 호출 후보일 뿐 인과 edge 정답이 아니며, 방향도 전파 방향을 보장하지 않는다. 따라서 causal-edge supervision, edge-F1, 인과 전파 정확도 주장은 지원되지 않는다. 12건이 weak-cause/strong-victim 난제를 대표한다고도 입증되지 않았다.
- ops-lite의 출처·버전·라이선스 동등성은 확인되지 않았으며 보조 데이터로 확정하지 않는다. 이 보류는 RCAEval의 root-service 연구 가능성과 별개다.

## 다음 단계 우선순위 (문서화·판정 작업)

1. **첫 병목 조사:** 사례별 결과를 대조해 단순 이상점수 11/12와 규칙 LLM 2/12의 큰 격차가 생긴 실패 유형을 정리한다. 특히 이 12건이 weak-cause/strong-victim 구도를 실제로 포함하는지 확인 가능한 증거를 구분하고, 확인 불가한 구성개념은 미입증으로 남긴다. 지금 자료만으로 원인을 확정하거나 새 실험을 수행하지 않는다.
2. 범위·주장표를 root-service 진단으로 한정하고, “관측 호출”과 “인과 edge 정답”을 분리한다. Top-1/Top-3, paired 사례 수, 단순 기준점, 작은 표본의 한계를 함께 기록한다.
3. 데이터 준비 문서에서 반복 그룹 단위 분할, 개발 예약 36건과 final-test의 비중복, 누출 방지 및 final-test 구성 필요성을 명시한다. 이는 다음 합의 단계의 준비 항목이지 이 문서가 승인하는 실험 지시가 아니다.
4. 연구 방법·비교 기준·LLM 사용 여부의 최종 선택은 공동 이해가 정리된 뒤 별도 합의한다. full-study 확장은 **보류**한다. 현재 허용되는 것은 사실과 미해결 질문을 문서화하는 다음 단계뿐이며, 추가 실험은 승인하지 않는다.

## 근거 파일

- `research/verification/smoke-checks.json`, `research/smoke/summary.json`, `research/smoke/posthoc-synthetic-sanity.json`
- `research/verification/smoke-audit.md`, `research/verification/data-readiness.md`, `research/verification/baseline-contract.md`
- `research/SMOKE_PROTOCOL.md`
