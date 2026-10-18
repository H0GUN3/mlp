# MLP 기반 RCA 연구 코드

2026-10-18까지의 연구 코드·테스트·프로토콜을 보존한 소스 저장소입니다.
**모델 구성, 실행 준비, 공개 범위는 [PUBLICATION.md](PUBLICATION.md)를 먼저 확인하세요.**

- DiagMLP/Eadro 비교: `research/native_reproduction_20261013/native_models.py`
- 자체 local/relative MLP: `research/method_mlp_20261013/ranker.py`
- 관계 기반 local/global/directed MLP: `research/relationship_smoke_20261013/relation_model.py`
- 최근 실험: `research/sn_corrected_20261017/`,
  `research/sn_hawkes_horizon_contrast_20261017/`,
  `research/sn_call_target_contrast_20261018/`,
  `research/re2_ob_known_condition_20261018/`

원본 데이터, 학습 가중치, 생성 결과, 가상환경은 업로드하지 않습니다.
아래 및 개별 연구 문서는 당시 실행 기록이므로 로컬 산출물 링크가 포함돼 있고,
이 저장소만 복제해서 기존 결과 검증이나 전체 학습을 바로 실행할 수는 없습니다.
과거 보고서의 “현재 방향”은 해당 문서 작성 당시의 상태입니다.

## 최초 데이터 확보·검수 기록

- **먼저 읽기:** [연구 방향 및 진행 보고서](연구_방향_및_진행보고서.md)
- [확보·검수 보고서](데이터_확보_검수_보고서.md)
- [공식 출처와 라이선스 대조](SOURCES.md)
- [범위·절차](ACQUISITION_PLAN.md)
- [RCAEval 사례별 사용 가능 목록](evidence/rcaeval-readiness.csv)

## 연구 진행 자료

- [관련 연구의 배경·문제·방법·결론](research/관련연구_분석.md)
- [첫 스모크 사전 명세](research/SMOKE_PROTOCOL.md)
- [첫 스모크 결과 JSON](research/smoke/summary.json)
- [원본 응답·채점 독립 검증](research/verification/smoke-audit.md)
- [합의한 방향과 개발용 기준점 명세](research/BASELINE_PROTOCOL.md)
- [연구 가치·문제·방법론 반증 기준](research/ADVERSARIAL_CRITERIA.md)
- [두 단계 실험의 실제 결과](research/실험_결과.md)
- [연구 타당성 압박평가와 중단 조건](research/연구_타당성_압박평가.md)

첫 스모크는 Qwen3:8b 로컬 실행의 12건×4조건 탐색 실험이다. 기존 논문 방법의
재현이나 LLM의 일반적인 유효성 검증이 아니다. 사용자와 합의한 현재 방향은
단일 원인 서비스 진단의 정확도 개선이며, LLM은 필요성이 입증될 때만 채택한다.
개발용으로 예약한 36건 외 144건의 관측자료는 후속 기준점 단계에서 사용하지 않는다.

## 기존 연구 결과의 오프라인 검증

새 모델 요청이나 첫 결과 덮어쓰기 없이 저장 결과를 검사한다.
각 명령은 파생 검증 보고서를 갱신하지만 원본 데이터·모델 응답·첫 점수 결과는 바꾸지 않는다.

```sh
.venv/bin/python scripts/verify_smoke.py
.venv/bin/python scripts/verify_development_split.py
.venv/bin/python scripts/verify_baselines.py
```

성공 표지는 각각 `VERIFY_SMOKE_PASSED`, `SPLIT_GUARD_PASSED`,
`VERIFY_BASELINES_PASSED`다. 검증 성공은 계산·기록 일치이며 과학적 효과의 인증이 아니다.

## 최초 실행을 재현할 때

원래 결과가 없는 별도 작업공간에서만 다음 순서를 사용한다. 기존 `research/smoke/`나
`research/baselines/results/`를 지워 재실행하지 않는다. 두 실행 스크립트는 첫 결과가
있으면 덮어쓰기를 거부한다.

1. 동일 고정 데이터와 환경을 준비한다.
2. `research/SMOKE_PROTOCOL.md`와 `research/BASELINE_PROTOCOL.md`의 고정 조건을 확인한다.
3. 사용자 계정의 별도 터미널에서 아래 로컬 서버를 실행한다.

```sh
OLLAMA_HOST=127.0.0.1:11435 \
OLLAMA_MODELS="$PWD/models" OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 CUDA_VISIBLE_DEVICES=0 ollama serve
```

4. 다른 터미널에서 실행한다.

```sh
OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3:8b
.venv/bin/python scripts/smoke.py prepare
.venv/bin/python scripts/smoke.py run
.venv/bin/python scripts/baseline_dev.py
```

`prepare`는 한 번만 실행한다.
`qwen3:8b` 태그는 미래에 바뀔 수 있으므로 원래 `model-metadata.json`의 digest와
실제 모델을 대조한다. 원 실행은 Ollama 0.9.0, Q4_K_M이며 다른 환경에서 비트 단위의
동일 출력을 보장하지 않는다. 사후 합성 `sanity` 검사는 본 평가와 별도로 기록한다.
사용이 끝나면 자신이 시작한 모델 서버만 종료한다. 공용 서비스나 다른 사용자의 프로세스는 건드리지 않는다.

## 재현

프로젝트 전용 Python 환경에서 실행한다. root 권한이나 공용 패키지 변경은 필요 없다.

```sh
uv venv .venv
uv pip install --python .venv/bin/python pyarrow==19.0.1 numpy==2.2.6
python3 scripts/acquire.py rcaeval
python3 scripts/acquire.py ops-lite
.venv/bin/python scripts/audit.py rcaeval
.venv/bin/python scripts/audit.py ops-lite
```

이미 `.venv`가 있으면 환경 생성은 생략한다. 다운로드 대상과 커밋은
`scripts/acquire.py`에 고정되어 있다. 유효한 기존 파일은 재사용하며
실패가 하나라도 남으면 비정상 종료한다. 429 제한에는 서버의 대기시간을 따르므로
재시도가 오래 걸릴 수 있다. 최초 실패 기록은 재시도 전 증거 파일로 보존한다.

검사는 확보 완료 명세를 전제로 한다. Parquet의 메타데이터만 읽는 것이 아니라
전체 열과 행을 해독·검증한다. 결과 JSON/CSV는 `evidence/`에 생성하고 원본은
수정하지 않는다. 그래프 검사·호출 추출의 기본 동작은 스크립트 내 self-check로 확인한다.

## 데이터/정답 분리

- `data/rcaeval/`: 180건 관측자료와 전체 735건의 인덱스. **735건의 관측자료를
  모두 확보한 것이 아니다.**
- `data/ops-lite/`: 455건 정답·메타데이터, 그중 고정 표본 30건의 관측자료.
  **455건 전체 관측자료를 확보한 것이 아니다.**
- 경로명·인덱스·정답·주입 정보는 검수용이다. 디렉터리 전체를 LLM이나
  학습 특징 생성기에 노출하지 않는다.
- 해시 일치는 내려받은 내용의 무결성 검사다. 실제 인과 정답의 독립 검증이나
  과거 다른 배포판과의 동등성 증명은 아니다.
