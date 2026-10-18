# 방법론 반증: 문제에서 해법까지의 증거 사슬

## 판정
**현재 특정 기여는 보류; RCAEval에서의 인과-edge/피해 서비스 주장은 폐기.** RCA의 일반적 중요성을 부정하는 판정은 아니다. RCAEval의 root-service 정답은 원인 서비스 순위 평가만 지원한다. 현재 결과는 왜 새 방법, 특히 LLM이나 호출관계 선별이 필요한지 입증하지 못한다. 순위는 `research/ADVERSARIAL_CRITERIA.md`를 따른다.

## 치명적 우려
### F1. 정답 단위와 주장 불일치: 인과-edge 감독 부재
- **증거:** `research/verification/data-readiness.md`, `research/SMOKE_PROTOCOL.md`는 gold가 `root_cause_service`뿐이며 propagation-edge 정답은 없다고 명시한다. `scripts/smoke.py`도 호출을 검증된 전파가 아니라고 설명한다.
- **무효화:** root-service Top-k는 채점 가능하지만, 오답 후보를 피해 서비스로 해석하거나 “원인-피해 혼동”·전파 방향·edge-F1을 개선했다는 주장은 검증 불가다. caller→callee span 관계는 인과 gold가 아니다.
- **최소 검사:** 기여를 root-service 진단으로 제한한다. edge 인과가 필수라면 독립 검수된 propagation-edge/victim gold로 별도 평가하고, 확보 못 하면 edge 주장을 중단한다.

### F2. 추론 오류와 입력 증거 부재 미분리
- **증거:** `research/smoke/summary.json`: 카드만/전체 호출/규칙/무작위 Top-1은 각각 1/12, 1/12, 2/12, 1/12. 합성 sanity 2/2는 synthetic 반응 검사다. `research/verification/data-readiness.md`: 전체 모달리티 쌍은 180건 중 178건 완비. smoke 카드 trace 항목 487개 중 290개는 `[0,0,null]`; 로그도 제외했다.
- **무효화:** 관측되지 않은 정보를 추론기가 복구할 수는 없다. 반대로 한 Qwen3:8b 설정의 낮은 점수는 모든 LLM이 불필요하다는 증거도 아니다. 결측/표현 손실과 모델 추론 실패가 섞여 있다.
- **최소 검사:** 오류를 관측 가능성으로 층화하고, 입력에 root 판별 신호가 있는지 독립 판정한다. 완전 관측 사례에서만 동일 증거를 주는 비LLM과 비교한다.

## 주요 우려
### M1. 강한 수치 통제가 제안 방법의 필요성을 약화
- **증거:** `research/baselines/results/summary.json`, `baseline-audit.md`: 개발 36건 중 median-change Top-1 30/36, Top-3 35/36; 지연 1/6, 메모리 5/6, 나머지 고장군 각각 6/6. smoke 12건의 단순 이상순위는 11/12로 모든 LLM 조건보다 높다.
- **무효화:** 낮은 LLM 점수는 복잡한 추론 필요의 증거가 아니라 이 모델·입력·프롬프트가 단순 수치 통제를 못 넘은 결과다. 30/36은 어려운 문제가 광범위하다는 뜻이 아니라 개발 자료에서 오답 6건, 특히 지연 실패가 있다는 탐색 신호다.
- **최소 검사:** 6개 오답(지연 실패 포함)을 사례별 분해하고 구현·전처리 오류를 배제한다. 이후 그룹 보존 독립 평가에서 같은 입력·후보의 수치 기준과 짝비교한다. 반복 개선이 없으면 특정 진단기 기여를 중단한다.

### M2. LLM 수치 판독 역할은 입증되지 않음
- **증거:** `research/smoke/summary.json`: 규칙선별 대 카드만/전체호출/무작위는 각 1승·0패·11동률. `SMOKE_POSTCHECK.md`는 카드만에서 `[S01,S02,S03]` 반복 응답을 기록한다. 비LLM 수치 순위는 11/12.
- **무효화:** 텍스트 카드 입력에서의 실패가 일반 RCA 난도인지 수치 순위 작업의 모델 약점인지 분리되지 않았다. 호출 선별 또는 LLM 추가가치 신호가 없다.
- **최소 검사:** 동일 카드·후보·시작시각·토큰/시간 예산에서 고정 수치기, 필요시 비LLM 학습기, LLM을 비교한다. LLM 역할을 구체화하고 같은 정보를 쓰는 비LLM보다 정확도 이득일 때만 남긴다. 자연어 설명만으로는 부족하다.

### M3. 시작 시각 oracle은 운영 RCA가 아님
- **증거:** `SMOKE_PROTOCOL.md`, `BASELINE_PROTOCOL.md`, `scripts/smoke.py::build_features`는 주입 시각으로 정상/장애 창을 나눈다.
- **무효화:** 이는 알려진 시작점의 오프라인 순위이지 장애 탐지·온라인 복구가 아니다. 모든 방법에 같은 oracle을 준 것은 내부 비교 공정성이지 운영 타당성의 증거가 아니다.
- **최소 검사:** 현 주장은 알려진 시작 시각으로 제한한다. 운영 주장을 원하면 탐지기를 고정하고 탐지 지연·오탐을 포함하며 같은 탐지 결과를 모든 비교기에 준다.

### M4. 36건은 독립 시험표본이 아님
- **증거:** `research/baselines/results/metadata.json`, `verification.json`: 12개 system/root/fault 그룹마다 3회 반복. smoke 원본 12건도 개발 36건에 포함. `data-readiness.md`에 최종 test 분할 없음.
- **무효화:** 3회 반복을 독립 3건으로 세거나 결과를 본 뒤 고른 규칙을 시험 성능이라 하면 의사반복·누출이다. 수치는 재현 가능한 개발 결과일 뿐 일반화·유의성 결과가 아니다.
- **최소 검사:** 모델/규칙 선택 전 그룹 단위 분할 manifest를 고정하고 반복 그룹 전체를 한 partition에 둔다. 36건은 test로 재사용하지 않고 불확실성도 그룹 단위로 보고한다.

### M5. 30/36 대 10/36은 BARO/SOTA 우월성 주장이 아님
- **증거:** 개발 결과는 median-change 30/36, `baro_signed` 10/36. `method-note.md`, `baseline-contract.md`는 BARO 원본 실행이 아니라 NumPy 점수 경로의 코드 정렬 재구현이라 명시한다. 알려진 시작 시각, 별도 결측 처리·상수열/공통 지표 필터·IQR 처리이고 BOCPD 및 전체 파이프라인은 제외했다.
- **무효화:** 이는 개발 반복군에서 단순 기준이 이 특정 BARO 적응 점수기보다 높았다는 뜻뿐이다. 전처리·후보·창·구현을 포함한 묶음 비교여서 점수식 효과를 분리하지 못하며, 출판 BARO보다 성능이 낮다는 뜻도 아니다.
- **최소 검사:** 논문 우월성 주장이 필요할 때만 원본 BARO를 고정 어댑터로 실행해 입력·시작점·후보·평가를 대조한다. 그 전에는 “BARO 코드 정렬 점수기”라 부른다.

### M6. 부호→절댓값 수정은 Top-1 실패 원인을 설명하지 않음
- **증거:** `results/summary.json`: signed와 absolute 모두 Top-1 10/36, Top-3 30/36, 36건의 Top-1 결과 동일. MRR만 0.557253 대 0.557001. 같은 전처리에서 부호 처리만 변경했다.
- **무효화:** 절댓값이 성능을 높여 BARO 문제를 해결했다는 주장은 관측과 반대다. 일부 내부 순위 변화는 있을 수 있지만 Top-1 개선은 없다. 아주 작은 MRR 하락도 개선이 아니다.
- **최소 검사:** 사전 고정된 사례별 순위 변화와 방향만 보고한다. Top-1 이득이 없으면 설명을 미입증으로 두고 사후 승리를 만들지 않는다.

### M7. 관계 선별과 정보량 효과가 혼재
- **증거:** `SMOKE_PROTOCOL.md`, `scripts/smoke.py`: 카드-only/전체/규칙 최대 8개/동일 수 무작위 비교. 선택 조건의 연결 수는 같지만 토큰은 평균 2603/2836/2668/2668. 규칙-무작위도 연결 개수만 맞고 예산·정보 내용은 같지 않다.
- **무효화:** 12건의 1건 차이로 선별 원리·관계 유무·정보량·모델 변동을 구분 못한다. paired 결과도 규칙선별이 각 대조에 1승·0패·11동률이다.
- **최소 검사:** 같은 관계 수뿐 아니라 추가 토큰/정보 예산을 맞춰 선택·무작위·sham 대조를 둔다. 후보·카드·시작시각·질의/모델 설정을 고정하고 독립 그룹 시험에서 paired 평가한다.

### M8. 주입 장애 분포를 운영 결함으로 일반화할 수 없음
- **증거:** `SMOKE_PROTOCOL.md`: 고정 RCAEval RE2-OB/RE2-TT 주입 사례. 개발 자료는 두 시스템, 여섯 장애유형, 12개 반복 그룹이다.
- **무효화:** 운영/코드 결함·미지 장애·다른 환경 일반화 근거가 없다. 고정 벤치마크 신호의 점수를 보편 RCA로 승격하지 않는다.
- **최소 검사:** 주장을 이 분포로 제한하거나 별도 환경·고장 생성 과정의 그룹 분리 평가를 사전 지정한다.

## 경미하지만 차단해야 할 과장
1. `research/smoke/summary.json`의 12건은 탐색 smoke, synthetic 2/2는 실제 RCA 성능이 아니다. Qwen3:8b Q4_K_M 단일 프롬프트 실패를 모든 LLM의 실패로 일반화하지 않는다.
2. signed/absolute의 Top-1·Top-3가 같아도 다른 순위 변화는 가능하다. 그러나 현재 10/36 양쪽 모두이며 MRR도 미세 하락이라 개선 근거가 아니다.
3. `research/verification/baseline-contract.md`는 MicroHECL/TopoEvo/EG-RCA의 직접 중복 가능성, TORAI/EviRCA 미실행·어댑터 필요성을 기록한다. 미실행법을 이겼다고 쓰지 말고 연산·감독 정답·비용·실패조건 차이 없이 후보/근거 선별을 신규성이라 하지 않는다.

## 조건부 후속 계획 — 전체 확장 전 최소 관문
1. **질문 고정:** root-service Top-k로 한정한다. edge/victim 인과가 필수면 RCAEval 경로를 중단하고 edge gold부터 확보한다.
2. **실패 확인:** 개발 36건의 median-change 오답 6건을 그룹별 검토하고 결측·창·단위·전처리·동점 버그를 배제한다. 관측 불가와 관측됐으나 오순위인 경우를 분리한다. 상위 비원인을 피해 서비스로 사후 라벨링하지 않는다.
3. **방법 필요성:** 반복되는 실패와 입력에 관측 가능한 판별 증거가 함께 있을 때만 그 실패에 필요한 최소 연산을 정의한다. 동일 정보·토큰/시간 예산의 비LLM 대조를 넘기 전 LLM은 넣지 않는다.
4. **시험 잠금:** 모델·규칙 선택 전에 그룹 단위 split, 독립 test, primary metric, paired 비교·중단 기준을 고정한다. 개발 36건은 held-out가 아니다. 나머지 144건도 test로 이미 확정된 것이 아니므로 분할 설계 전까지 보호한다.
5. **비교 명칭:** 원본/전체 BARO 미실행이면 코드 정렬 점수기, 일부 규칙이면 inspired라 표기한다. 정보·평가 조건이 다른 논문 수치를 우월성 표에 섞지 않는다.

**중단 조건:** 구현/전처리 수정으로 실패가 사라짐, 입력 정보가 없어 실패함, 동일정보 비LLM 기준을 못 넘음, 또는 독립 그룹 시험에서 사전 지정 개선이 재현 안 됨 중 하나면 현 특정 기여를 중단·재정의한다. RCA 일반론의 중요성은 예외가 아니다.

## 근거 앵커
- `research/ADVERSARIAL_CRITERIA.md`; `research/SMOKE_PROTOCOL.md`; `research/SMOKE_POSTCHECK.md`; `research/BASELINE_PROTOCOL.md`
- `research/smoke/summary.json`; `research/smoke/model-metadata.json`; `scripts/smoke.py`
- `research/baselines/method-note.md`; `research/baselines/baseline-audit.md`; `research/baselines/verification.json`; `research/baselines/results/{metadata,summary}.json`
- `research/verification/{smoke-audit,data-readiness,baseline-contract}.md`
