# 고정 공개 원문 확인 — 부모 직접 확인

로컬 파일 부재 때문에 보류된 GATE의 원문 근거를 보완한다.
2026-10-17 부모가 webfetch(format=text)로 아래 고정 커밋 원문을 읽었다.
파일 clone/download/install이나 연구 자료 접근은 하지 않았다.

- https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/single_process.py
- https://raw.githubusercontent.com/FeiGSSS/Eadro/7d69281a80adce60067aa858729746fc6a362f53/codes/preprocess/align.py

## 확인한 연산

single_process.deal_logs는 선택 로그를 서비스와 이벤트별로 묶고,
정렬한 이벤트 timestamp에서 창 시작 s를 뺀다. 같은 이벤트 안의 순서에
1e-5를 곱한 jitter를 더한다. 그 knots를 logHaw에 다음처럼 전달한다.

```python
paras = logHaw(knots, end_time=e+1, event_num=event_num)
model.fit(chunk_logs, end_time, baseline_start=np.ones(event_num)*ini_intensity)
```

두 번째 줄은 logHaw 내부의 호출이다. 생성 모델은 HawkesADM4이며 decay 기본3,
초기baseline 기본0.2를 쓴다. 반환은 model.baseline이다.
align.get_basic은 s와 s+chunk_lenth-1 쌍을 만들며 기본 chunk_lenth10이다.
따라서 길이10초에서 e+1=s+10이다. s는 recording의 절대시각 좌표다.
우리 native_data의 end_times=LENGTH=10과 다른 변수를 정확히 특정할 수 있다.

## 실험에서 공통으로 유지할 것

원 공개 코드의 로그선택은 timestamp>=s, timestamp<=e이고 window stride1이다.
우리 입력은 stride10, half-open [s,s+10)이다. 이 차이까지 되돌리지 않는다.
양 arm 모두 기존 선택된394창/템플릿/relative knots/seed를 그대로 사용한다.
즉 비교 변수는 end_times10 vs original_window_start+10 하나이며,
source 전체를 그대로 재실행한 결과라고 부르지 않는다.

GATE는 이 기록과 지정1차URL에서 재확인할 수 있다. repo 안에 원문이 없다는
사실만으로 출처가 미확인인 상태를 유지할 필요는 없다. 실제 비용/재생성
동등성/보호행 선택 구현은 다음 단계에서 검증해야 한다.
