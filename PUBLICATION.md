# 공개 코드 범위와 모델 구성

## 모델은 어떻게 나뉘는가?

모델 종류별 구현과 학습 인스턴스는 구분된다. 다만 모델마다 파일을 복제한 구조는 아니다.

| 구분 | 코드 | 선택 방법 |
|---|---|---|
| DiagMLP / Eadro native 비교 | `research/native_reproduction_20261013/native_models.py` | `NativeReference("diagmlp", ...)` / `NativeReference("eadro", ...)` |
| 공통 수치 입력 비교 | `scripts/mlp_reference.py` | `DiagMLPCommonInput` / `EadroGATCommonInput` |
| 자체 서비스 순위 MLP | `research/method_mlp_20261013/ranker.py` | `Ranker`의 `local` / `relative` 모드 |
| 관계 기반 서비스 순위 MLP | `research/relationship_smoke_20261013/relation_model.py` | `RelationRanker`의 `local` / `global` / `directed` 모드 |

DiagMLP는 논문 수식에 근거한 재구현이며 저자 코드라고 주장하지 않는다.
Eadro는 고정된 외부 원본을 참조한다. 공통 입력 변형과 native 비교는 서로 다른
실험이므로 같은 재현 수준으로 해석하면 안 된다.
자세한 변경·한계는 `research/mlp_prerequisites/MODEL_PROVENANCE.md`를 참고한다.

학습된 `.pt` 파일은 로컬에서 데이터셋·모델·seed·fold/rotation별 디렉터리로
분리돼 있다. 중단 실행이나 합성 테스트 파일도 있으므로 파일 존재가 학습 완료를
뜻하지 않는다. 가중치는 이번 소스 공개에 포함하지 않는다.

## 포함 / 제외

- 포함: 연구 Python 코드, 테스트, Markdown 연구 기록, 요구사항 잠금 파일,
  타입 검사 설정, Drain 설정.
- 제외: 원본 데이터, 전처리 배열, 체크포인트, 생성 JSON/CSV 결과, 로그,
  다운로드 압축 파일, Ollama 모델, 가상환경, 개인 도구 설정.
- 외부 코드 네 파일은 재게시하지 않고 아래의 원본 출처에서 별도로 준비한다.
  로컬 원본 파일은 삭제하거나 수정하지 않았다.
- 기존 연구 기록의 경로와 결과 링크는 보존한다. 제외한 결과 파일에 대한 링크는
  공개 저장소에서 열리지 않는다.
- 일부 실험은 `/home/gnho1236/r2` 또는 별도 로컬 데이터 경로를 사용한다.
  다른 시스템에서는 해당 실행 파일의 경로 설정을 확인해야 한다.
- 이 공개는 저장된 연구 코드의 보존이며, 모든 실험의 재학습이나 성능 재검증을
  수행했다는 의미가 아니다. 중단된 연구 실행을 자동으로 재개하지 않는다.

## 외부 모델 / 기준선 준비

Eadro 두 저장소의 GitHub 라이선스 필드는 확인 당시 비어 있었다.
이 저장소는 외부 원본의 재배포 권리를 부여하지 않는다. 원본 사용 조건을 확인하고
필요한 경우 권리자의 허가를 받아 다음 경로에 준비한다.
바이트 해시를 검사하는 코드가 있으므로 파일을 임의 수정하지 않는다.

| 로컬 경로 | 원본과 고정 버전 |
|---|---|
| `research/mlp_prerequisites/eadro_model.py` | `BEbillionaireUSD/Eadro`, commit `82ff9c9a7a58a9cd2b713aa78754a73c543a15db`, `codes/model.py` |
| `research/mlp_prerequisites/eadro_corrected_model.py` | `FeiGSSS/Eadro`, commit `7d69281a80adce60067aa858729746fc6a362f53`, `codes/model.py` |
| `research/baselines/reference/baro-root-cause-analysis.py` | `phamquiluan/baro`, tag `0.2.0`, `baro/root_cause_analysis.py` |
| `research/baselines/reference/baro-utility.py` | `phamquiluan/baro`, tag `0.2.0`, `baro/utility.py` |

원본 출처:

- https://github.com/BEbillionaireUSD/Eadro/tree/82ff9c9a7a58a9cd2b713aa78754a73c543a15db
- https://github.com/FeiGSSS/Eadro/tree/7d69281a80adce60067aa858729746fc6a362f53
- https://github.com/phamquiluan/baro/tree/0.2.0

## 환경과 최소 검사

기존 공통 입력 비교 환경의 잠금 파일은
`research/mlp_prerequisites/requirements.lock.txt`다.
native 전처리에는 별도로 `tick`, `drain3`, `pandas`, `scikit-learn` 등이 필요하다.
이 잠금 파일 하나가 전체 연구 환경을 설치해 주는 것은 아니다.

기존 프로젝트 환경에서 데이터나 전체 학습 없이 모델 동작을 확인하는 명령:

```sh
OMP_NUM_THREADS=1 .venv-eadro/bin/python -B research/method_mlp_20261013/ranker_tests.py
OMP_NUM_THREADS=1 .venv-eadro/bin/python -B research/relationship_smoke_20261013/test_relation_model.py
# 아래 두 명령은 위의 Eadro 원본 두 파일을 준비한 뒤 실행한다.
DGLBACKEND=pytorch OMP_NUM_THREADS=1 .venv-mlp/bin/python -B scripts/mlp_reference.py
DGLBACKEND=pytorch OMP_NUM_THREADS=1 .venv-eadro/bin/python -B research/native_reproduction_20261013/native_models.py
```

원본 Eadro `MainModel`의 알려진 결함은 원본 그대로 보존하며,
`mlp_reference.py`의 원본 모델 검사는 `blocked_upstream`으로 보고될 수 있다.
이는 별도 공개 수정본이나 자체 MLP 검사 통과와 구별한다.

## 게시 전 확인 (2026-10-18)

- 업로드 대상 Python 158개 파일의 구문 분석 및 포함 JSON 설정 파싱 통과.
- 위 네 검사 명령 모두 종료 코드 0. 자체 MLP 두 테스트, 공통 입력 어댑터,
  공개 수정본 Eadro, native DiagMLP/Eadro의 합성 forward/backward 검사 통과.
- 원본 Eadro 전체 모델은 기존 `trace_dropout` 미정의 결함을
  `blocked_upstream`으로 보고했다. 결함을 수정하거나 통과로 바꾸지 않았다.
- 업로드 대상의 토큰·개인키 패턴 검사에서 검출 없음.
- 기존 Markdown의 줄 끝 공백과 마지막 빈 줄에 대한 `git diff --check` 경고는
  원문 보존을 위해 수정하지 않았다. 전체 실험 재학습은 실행하지 않았다.
