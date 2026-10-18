# 정확도 중심 연구 원형과 개발 스모크

- [논문형 보고서](REPORT.md): 문제·관련연구·방법·실험·실제 결과·한계·재현 명령.
- [실행 전 계약](PROTOCOL.md): 허용 자료, 사건 fold, 모델과5epoch 범위.
- [원수치](smoke_results.json): 6회 실행 결과. 성능 우위가 입증됐다는 뜻은 아니다.
- `artifacts/`: 원9채널과fold0 특징·관계·사건 매니페스트.
- `runs/`: local/global/directed의checkpoint·예측·학습 기록.

24개 검사와 명시적 프로젝트 Pyright를 통과했고,
SN/TT×3모드, 각5epoch·seed11의 스모크 및 별도 프로세스 재실행을 완료했다.
기존 native test/unassigned 창은 산출물·학습·채점에서 제외했고 RCAEval 자료에는 접근하지 않았다.

자료는 기존에 개발에 사용한 사건이다. 새 독립 사건이나 최종시험으로 부르지 않는다.
완료된 artifact/run을 덮어쓰지 않으며, 현재 결과 확인은 `smoke.py verify`로 한다.
