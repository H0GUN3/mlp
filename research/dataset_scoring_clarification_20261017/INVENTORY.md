# RCAEval 240건 구성 확인

## 메타데이터 범위

| 자료군 | 사례 | 메타데이터 `has_traces` | 메타데이터 `has_logs` | 기존 로컬 관측 감사 |
|---|---:|---:|---:|---:|
| RE2-OB | 90 | 90 | 90 | 포함 |
| RE2-TT | 90 | 90 | 89 | 포함 |
| RE3-OB | 30 | 30 | 30 | 미포함 |
| RE3-TT | 30 | 30 | 30 | 미포함 |
| **합계** | **240** | **240** | **239** | **180 포함 / 60 미포함** |

240건은 전체 인덱스 735행 중 trace-primary 범위다. 남은 495행은 RE1-OB/SS/TT 각 125, RE2-SS 90, RE3-SS 30으로 제외된다. RE2-OB와 RE2-TT는 각각 30개 root/fault 조건에 조건당 3회 반복(각 90건)이다. RE3-OB는 10개 조건 각 3회(30건), RE3-TT는 8개 조건이 3회 4개·4회 3개·6회 1개(총 30건)로 균일 반복이 아니다. 따라서 “240”은 독립 사건 수를 뜻하지 않는다.

## 메타데이터와 관측자료 확보의 구분

인덱스의 240건은 라벨·그룹핑 및 modality flag가 확인된 **메타데이터 범위**다. 저장된 기존 획득·준비도 감사는 RE2 180건만 포함하고, RE3 60건은 로컬 사례 감사가 없다. 기존 고정 원격 파일 인벤토리에는 RE2/RE3 해당 trace 파일이 각 90/90/30/30건 기록되어 있고, 기존 다운로드 원장에는 RE2 로그 179건·trace 180건이 확인된다. 단, 파일 인벤토리나 원격 출처 기록은 로컬 획득 또는 내용 품질 확인과 같지 않다. RE2-TT 1건의 로그 flag 누락은 그 사례나 trace가 미획득이라는 뜻이 아니다.

확인 근거는 `rcaeval_trial.json`의 집계, `rcaeval-tree.json`의 고정 원격 파일 목록, `rcaeval-downloads.json`의 기존 다운로드 원장, `rcaeval-readiness.csv`의 기존 RE2 감사다. 감사 기준은 2026-10-16이다. 이후 일부 RE2 파생 준비 입력은 신규 원시 사례를 추가하지 않았으므로 180/60 집계를 바꾸지 않는다. 인덱스 전체 735행을 모두 관측 확보로 세지 않는다.

기존 OPS.md 결과도 그대로 구분해 해석한다: 197건은 ops/RCABench 메타데이터 일치이며, 8사례에서 일치한 80개 비어 있지 않은 파일 해시는 관측 바이트 일치다. 이는 197건 전체의 관측 일치를 뜻하지 않는다.

독립 반복의 root/fault 조건이 공유된다는 사실만으로 누수라고 단정할 수 없고, 기본 검증에서 조건 분할을 반드시 강제할 근거도 아니다. 조건 공유는 평가 설계에서 명시할 특성이며, 독립성·일반화 주장은 별도 근거가 필요하다. 본 확인은 모델 평가나 독립된 240건 사건 판정을 하지 않았다.

## 읽기 전용 assertion proof

저장 JSON·ledger에 대해 표준 라이브러리로 assertion을 실행했다(종료 성공). 검증식: `735 = 240 + 495`; `240 = 90 + 90 + 30 + 30`; 네 suite 각각 `has_traces_cases == cases`; `has_logs_cases == (90, 89, 30, 30)`; 기존 감사 `180 + 60 = 240`, readiness 행 수 `180`; 고정 tree의 해당 suite trace 파일 수가 각 suite 사례 수와 같음. 원장 다운로드 파일 집합은 RE2-OB (logs/traces 90/90), RE2-TT (89/90)이며 원장의 실패 건수는 0이다. 이 assertion은 저장 인덱스·경로·기존 감사의 정합성만 확인하며 파일 내용을 읽지 않는다.

해시 대조 대상은 `research/dataset_suitability_20261016/rcaeval_trial.json`, `evidence/rcaeval-tree.json`, `evidence/rcaeval-downloads.json`, `evidence/rcaeval-readiness.csv`이며 SHA-256은 각각 `025f82f0094127118faf2492417dcf35af7f2a33287ad4909f4bb373fc08a197`, `b9de51f3fdb337aeea0ae4f7bc3de1fc56901072b708cc7878bb3d0c7b2107a0`, `6d3e0145e79955e977d393e66598160f39c7846ba6c76b6b951346abd18b8ddb`, `f9fde9344623876a928d4a2bd471ff7b01a4b9a6ef300536ddb4fa9aa5d923d3`이다. 고정 원격 인벤토리 revision은 `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`다. 보호된 native/RCAEval 최종 자료, parquet 본문, checkpoint 또는 예측은 열지 않았다.
