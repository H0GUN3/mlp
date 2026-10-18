# 비교 모델 선행조건 검증

[결과 중심 설명](결과_보고서.md)

## 범위

이 디렉터리는 문헌 구조의 공통입력 비교 모델, 평가기, 고정 분할 및 실행 증거를 담는다.
제안 방법의 성능 실험, 원 논문 수치 재현, 최종 시험 결과가 아니다.
세부 구분은 `MODEL_PROVENANCE.md`, 사전 명세는 `PROTOCOL.md`,
실행 중 해결한 문제는 `EXECUTION_NOTES.md`에 기록한다.
검증에서 발견된 프록시 내부 식별자의 공통 처리는 `CANDIDATE_CONTRACT.md`에
근거와 함께 고정했다. 실제 서비스의 미등록 이름은 여전히 오류다.

## 주요 증거

- `split.json`, `split.lock.json`: 학습108/검증36/최종시험36의 사고 그룹 분할.
- `model_checks.json`: DiagMLP 구조 재구현, 원 Eadro 모듈, 원본/수정본 전체 모델의 합성 실행 결과.
- `features.json`: 학습·검증144건만의 공통 특징과 입력 접근 기록. 최종시험은 제외.
- `training_results.json`: 2시스템×2모델×3seed 학습 이력과 선택 checkpoint/검증 예측.
- `checkpoints/`: validation loss로 선택한 실제 모델 상태.
- `verification.json`: 저장 모델 재로딩, 예측 일치, 별도 순위 계산 및 접근 경계 검증.
- `baro_validation.json`: 동일 검증셋에서 기존 BARO signed 점수 경로 재구현의 결과.

결과 파일은 해당 단계가 성공해야 생성된다. 파일 부재를 성공으로 간주하지 않는다.

## 기존 결과 재검증

작업 위치: `/home/gnho1236/r2`.

```sh
.venv-mlp/bin/python scripts/test_mlp_readiness.py
.venv-mlp/bin/python scripts/check_mlp_models.py
.venv-mlp/bin/python scripts/verify_mlp_readiness.py
pyright --project pyrightconfig.json scripts/mlp_readiness.py scripts/mlp_reference.py \
  scripts/test_mlp_readiness.py scripts/check_mlp_models.py scripts/verify_mlp_readiness.py
```

검증 명령은 기존 증거를 덮어쓰지 않는다. 새 검증 결과가 저장된 결과와 다르면 실패한다.
기존 언어 서버 세션이 새 가상환경을 놓치는 경우에도 위 새 Pyright 프로세스로
격리 환경 기준 진단을 확인할 수 있다.

## 처음 실행할 때만

이미 존재하는 split/결과를 삭제하거나 덮어쓰지 않는다. 아래 생성 명령은 기존 결과가
없는 새 작업 복사본에서, 동일한 원자료·metadata·개발 cache가 확보됐을 때 사용한다.

```sh
python3 -m venv .venv-mlp
.venv-mlp/bin/python -m pip install -r research/mlp_prerequisites/requirements.lock.txt
.venv-mlp/bin/python scripts/mlp_readiness.py prepare
.venv-mlp/bin/python scripts/test_mlp_readiness.py
.venv-mlp/bin/python scripts/check_mlp_models.py
.venv-mlp/bin/python scripts/mlp_readiness.py extract
.venv-mlp/bin/python scripts/mlp_readiness.py run
.venv-mlp/bin/python scripts/verify_mlp_readiness.py
```

`extract` 중단 시 동일 버전의 완성된 사례별 cache를 재사용할 수 있다.
`run` 완료 결과나 checkpoint를 조용히 교체하지 않는다. 시험 실행 모드는 없다.
