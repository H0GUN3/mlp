# 자체 기준선과 제안 모델

논문 모델을 고친 것이 아니라, 제안 방법론으로 만든 두 모델이다.

- **local:** 각 서비스가 평소와 얼마나 달라졌는지와 관측 가능 여부를 본다.
- **relative:** 같은 정보에 ‘다른 서비스들과 비교하면 얼마나 다른가’를 추가한다.
- 둘 다 같은 크기의 공유 MLP이며 서비스 이름·위치 번호·호출 그래프를 입력하지 않는다.
- 관측되지 않은 값은 별도 표시한다. 데이터가 없는 상태를 정상 값 0으로 취급하지 않는다.

## 파일

- `PROTOCOL.md`: 학습 전에 고정한 자료·특징·비교 조건과 해석 한계.
- `features.py`, `features/`: 양쪽 공통의 정상 대비 변화량·관측 정보.
- `ranker.py`: 자체 기준선과 제안 모델.
- `train.py`, `runs/`: 동일 조건의 12회 학습과 저장 모델.
- `verify.py`: 저장 모델 재실행 및 별도 점수 계산.
- `verification.json`, `결과.md`: 전체 실행과 검증이 끝난 뒤 생성되는 결과.

SN은 소셜 네트워크, TT는 기차표 예매 서비스 자료다. 논문 복원본은
별도의 외부 비교 대상으로만 사용하며 기존 구현·결과를 바꾸지 않는다.

## 확인 명령

저장소 루트 `/home/gnho1236/r2`에서 실행한다.

```sh
pyright --project research/method_mlp_20261013/pyrightconfig.json
.venv-eadro/bin/python -B -m research.method_mlp_20261013.features_tests --real
.venv-eadro/bin/python -B research/method_mlp_20261013/ranker_tests.py
.venv-eadro/bin/python -B research/method_mlp_20261013/train_tests.py
.venv-eadro/bin/python -B research/method_mlp_20261013/verify.py
```

최초 학습 명령은 `train.py --run-all`이다. 완료된 실행을 덮어쓰지 않도록
동일 실행 폴더가 있으면 거부한다. 검증만 하려면 `verify.py`를 사용한다.
RCAEval 최종시험36건 및 원 논문 자료의 test 예측은 이번 개발에 사용하지 않는다.
같은 고장 사건의 다른 시간 구간이 학습과 검증에 함께 있을 수 있으므로,
완전히 새로운 사고에 대한 정확도를 입증하는 실험은 아니다.
