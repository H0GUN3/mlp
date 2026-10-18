# SN200 train/validation 경계 감사

**판정:** 창/인덱스/시간 구간은 train과 validation 사이 중복 없음(`notfoundwithinscope`). 사건 ID와 recording은 공유되어 독립 사건·recording 검증으로 해석할 수 없는 평가 한계(`limitedevaluation`). 원시 관측 identity의 교차분할 중복은 미확인(`unknown`); 창 메타데이터만으로 이를 단정하지 않음.

## 근거 및 재현 가능한 수치

입력은 `calibration200/SN/diagmlp/seed_{11,23,37}/{split.json,config.json}` 및 `native_inputs/SN/metadata.json`뿐이다. 세 seed의 `config.json`에서 `split_seed=42`, split artifact SHA-256은 모두 `c38959d0fbe4a86486f6d497b28eb3a68e675e0e9d58ccd1f98e97bf4aee018d`. 각 split JSON의 `counts`는 train 316, validation 78, test 169, unassigned 1이며 합계 564. 각 split의 인덱스는 내부 중복 0, 파티션 쌍 교집합은 모두 0, 합집합 564다. `metadata.json`의 `window_count=564`, `window_length=10`, `stride=10`과 일치한다.

허용된 JSON을 `json`/표준 라이브러리로 읽어 아래처럼 계산했다(세 split 파일이 같은 SHA-256이므로 인덱스 결과 동일).

```python
parts = {k: set(split["indices"][k]) for k in ("train","validation","test","unassigned")}
sum(map(len, parts.values())), len(set.union(*parts.values()))
# (564, 564)
{(a,b): len(parts[a] & parts[b]) for ...}  # 모든 파티션 쌍
# 0
```

`metadata.json:windows[i]`를 split index와 대응시켰다. 메타데이터의 각 창은 `run_id`, `start`, `end`, `event_id`를 제공한다. `end_convention`은 정수 샘플의 inclusive end=`start+9`, 로그 구간은 `[start,start+10)`이다. 창 identity를 `(run_id,start,end)`로 정의하면 전체 564개 중 고유 564개, 중복 0이다. train-validation의 동일 identity 교집합 0이다. half-open 구간 `[start,start+10)` 기준 교차분할 겹침 쌍도 0이다(모든 창이 10초 stride로 정렬).

동일 계산의 핵심:

```python
W = metadata["windows"]
tr = [W[i] for i in split["indices"]["train"]]
va = [W[i] for i in split["indices"]["validation"]]
I = lambda w: (w["run_id"], w["start"], w["end"])
overlap = lambda a,b: a["start"] < b["start"] + 10 and b["start"] < a["start"] + 10
len({I(w) for w in W}), len(W)-len({I(w) for w in W})
# (564, 0)
len({I(w) for w in tr} & {I(w) for w in va})
# 0
sum(overlap(a,b) for a in tr for b in va)
# 0
```

그러나 train과 validation은 **28개 event ID를 공유**하며, **4/4 recording을 모두 공유**한다. validation 라벨은 메타데이터 기준 fault 65, normal 13 (78개). 따라서 창 자체의 중복은 없지만 같은 주입 사건/recording에서 나온 창이 양쪽 분할에 있어 사건·recording 독립성은 확보되지 않았다. 이는 공유 사건의 평가 한계이지, 동일 raw window가 중복되었다는 증거가 아니다.

`metadata.json:runs`에는 4개 run이 각 141창씩 있고, 모든 run 시간 범위의 교차는 0쌍이다. 즉 recording 간 시간대는 분리되어 있으나 각 recording이 train/validation에 함께 배정된 사실은 변하지 않는다. `metadata.json:windows`의 전체 identity 계산은 raw telemetry identity 검사가 아니다.

## 원시 identity 및 기존 증거의 범위

`native_data.py:window_starts`는 길이 10, stride 10 창을 만들고, `window_labels`는 창의 시간과 fault 구간 교차로 event ID를 붙인다. 이 생성 규칙은 메타데이터의 10초 half-open 창과 일치한다. `native_data.py`의 `SpanAudit`는 원천 span ID 중복을 전체 추출 요약으로 셌지만, 이 요약은 **train/validation 창별 raw-span 소속 교차표가 아니다**. `metadata.json:span_audit.counts`에는 원시 span identity 전체 중복 occurrence 520,300 및 유지 occurrence 중복 468,969가 기록되어 있어 데이터 전체에 반복 span identity가 있음을 보인다. 다만 이 값만으로 분할 간 raw identity 교차 수를 계산할 수 없다.

따라서 raw 관측/준비 배열 identity의 train-validation 중복은 `unknown`. 이 경계 계산은 저장 split과 metadata만 사용했고, 기존 verifier/native training 코드를 실행·import하지 않았다. 전체 감사의 다른 단계에서는 `raw.npz`를 해시 계산 목적으로 바이트 단위로 읽었으나 배열은 역직렬화·분석하지 않았다. 따라서 전체 감사에 대해 “raw 파일을 전혀 열지 않았다”고 주장하지 않는다. `inputs.npz` 및 원시 관측 레코드 분석은 수행하지 않았다. **원본 paper split과 DiagMLP split의 정확한 manifest 대응은 알 수 없음**(이번 허용 파일에서 별도 원본 manifest를 확인하지 않음); 564개 배열 partition 합계 및 동일 split hash는 재현 구성의 내부 일관성을 보여줄 뿐 원본 manifest 동일성을 증명하지 않는다.

**범위:** 보호된 SN169+1, TT1744+1, RE2는 접근하지 않았다. 새 분할·학습·추론·설치·다운로드·프로젝트 커밋은 없었다. 결론은 저장 메타데이터/소스 범위의 경계 감사이며 raw identity 증명이나 신규 일반화 평가가 아니다.
