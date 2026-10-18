# ops-lite metadata 및 중복 스트레스 검사

## 질문과 범위

ops-lite 전체 455건의 정답 메타데이터가 현재 30건 표본을 얼마나 대표하는지, 그리고 RCABench 메타데이터·보존된 실제 관측 파일 해시와 겹치는지를 확인했다. 목적은 모델 성능 평가가 아니라 표본 선택 편향과 자료 독립성의 근거를 확인하는 것이다.

허용된 ops-lite `README.md`, manifest와 각 사례의 `label/injection/env/causal_graph.json`, 기존 evidence ledger, 기존 RCABench metadata/quality 감사만 사용했다. Parquet 본문, RCABench archive, 표본 밖 425건의 telemetry를 열거나 새로 받지 않았다. 따라서 metadata가 있다는 사실은 telemetry 지원·품질을 뜻하지 않는다.

## 전체 메타데이터와 현재 표본

`manifest.jsonl` 455건 모두에 네 허용 JSON 파일이 있었다. manifest의 시스템 수와 현재 표본은 다음과 같다.

| 시스템 | 전체 metadata | 현재 표본 |
|---|---:|---:|
| TrainTicket (`ts`) | 275 | 10 |
| Hotel Reservation (`hs`) | 148 | 10 |
| OpenTelemetry Demo (`otel-demo`) | 32 | 10 |
| **합계** | **455** | **30** |

현재 표본은 원래 조건인 “required fault 항목 정확히 1개이며 propagation/service edge가 1개 이상”인 419건 중 30건이다. 기존 표본 선택에는 시스템당 10건과 `process_applicable` 조건도 있었다. 그러므로 시스템 구성은 의도적으로 균등하고 전체 구성(특히 `ts` 275건, `otel-demo` 32건)과 다르다. 이는 대표성 또는 성능 비교가 아니다.

| 지표 | 전체 455 | 현재 30 |
|---|---:|---:|
| required fault 항목 수 분포 | 1개: 437건, 2개: 18건 | 1개: 30건 |
| 서로 다른 required root service 수 분포 | 1개: 438건, 2개: 17건 | 1개: 30건 |
| fault role 항목 | required 473, optional 81, not_effective 77 | required 30, optional 12, not_effective 3 |

Fault type은 주입 항목 기준으로 전체에서 `PodFailure` 118, `NetworkDelay` 68, `JVMRuntimeMutator` 61, `NetworkPartition` 54, `MemoryStress` 46, `CPUStress` 45, `NetworkLoss` 34, `JVMLatency` 31, `ContainerKill`/`NetworkCorrupt` 각 27 등 26종이었다. 표본에서는 `PodFailure` 11, `NetworkDelay` 8, `CPUStress` 8, `MemoryStress` 4, `NetworkPartition` 4 등 11종이 나타났다. 전체·표본의 전체 fault-type 빈도는 JSON의 `metadata_distribution.whole/selected.fault_item_counts`에 보존했다.

Required fault 항목 수와 고유 root service 수는 같은 값이 아니다. 전체에는 required 항목이 2개지만 동일 service인 사례 1건이 있어, required 항목 437/18건과 root service 438/17건의 분포가 다르다. 따라서 단일 required fault를 단일 고장 service와 혼동하지 않았다.

시스템·fault type·required root 조합으로만 만든 반복 메타데이터 그룹은 전체 231개 signature 중 104개 반복 그룹(그룹 내 328건), 표본은 27개 중 3개 반복 그룹(6건)이었다. 이는 설명용 반복 패턴이며 동일 사건 또는 중복 관측의 증거가 아니다.

## RCABench와 중복 비교

정규화 규칙과 모든 일치 사례/경로는 `ops_trial.json`의 `cross_corpus`에 보존했다.

- **사례명:** 정확히 일치하는 ops/RCABench 사례 쌍 197개.
- **task ID:** 양쪽 모두 해당 ID가 있는 항목(ops 455/455, RCAB 1,422/1,422) 중 정확한 문자열 일치 197개.
- **숫자 injection ID:** ops 452개, RCAB 1,405개에서 204개 숫자 ID가 교차했다. 그중 196개만 사례명도 일치했고, 8개는 서로 다른 사례명끼리 ID가 겹쳤다. JSON은 이 8개 경로를 전부 기록한다. 숫자 ID 단독으로 중복 판정하지 않았다.
- **시간:** ISO 시간을 UTC로 바꾸고 epoch 문자열은 문자열 그대로 비교한 exact signature 197개. 이는 exact 사례명/task ID 일치와 맞물린 메타데이터 증거이지 별도 독립 사건 수가 아니다.
- **시스템/root metadata:** 소문자화, 양끝 공백 제거, `_`→`-`, 공백 축약 후 system과 고유 required-root 이름만 비교했다. RCAB의 숫자 fault-type ID를 ops 이름에 매핑하지 않았다. 부분 signature가 맞는 ops 266건, 가능한 ops–RCAB 쌍 3,852개로 비특이적이어서 incident duplicate 판정에 사용하지 않았다.
- **관측 바이트 SHA-256:** 저장된 ops 다운로드 ledger에서 비어 있지 않은 표본 telemetry와 RCAB quality ledger의 비어 있지 않은 telemetry만 비교했다. ops 291개, RCAB 15,642개의 고유 비어 있지 않은 hash 중 **80개 hash 그룹**이 같았다. JSON `telemetry_byte_hashes.cross_corpus_hash_matches`에는 모든 hash와 양쪽 전체 파일 경로가 있다. 빈 파일·metadata hash는 telemetry 중복 근거로 쓰지 않았다.
- **설정:** ops `engine_config_summary`와 RCAB `engine_config`는 저장 계약이 다르고 동등성 mapping이 검증되지 않았다. exact serialized match가 없다는 결과를 “공통 설정 없음”으로 해석하지 않고 **미확인/비교 불가**로 남겼다.

사례명, task ID, 시간, 실제 관측 바이트 일치가 확인되어 두 corpus 전체를 독립이라고 볼 수 없다. 다만 exact match가 없는 나머지 사례도 재포맷·시간 이동 중복을 배제하지 않으므로 독립성의 증명은 아니다.

## 출처와 활용 준비도

기존 `SOURCES.md`의 범위에서 후보 README는 455건 및 Apache-2.0을 표기하고, 연결된 OpenRCA 2.0 논문 설명은 500건 및 CC-BY-SA-4.0 데이터를 기술한다고 기록되어 있다. 그 자료에는 `anon-ops/ops-lite`가 저자/공식 배포라고 확인된 연결이 없다. 따라서 공식 논문 배포와 동일시하지 않고, 출처·라이선스는 추가 확인이 필요한 상태다. 새 문헌 조사는 하지 않았다.

**통과한 조건:** 전체 정답 metadata census, 원 표본 조건의 지원 규모, 시스템/role/root/type 구성 비교, 저장된 표본 telemetry audit 분리, cross-corpus 정확 일치 근거를 정량화했다.

**확장 잠재력:** 나머지 425건의 metadata는 분포·층화 및 후보 선정에 쓸 수 있다. 시스템당 10건인 현재 표본은 전체 시스템 구성과 다르며 fault-type 지원도 좁다. 확장 후의 실제 telemetry 품질은 별도로 확인해야 한다.

**준비도/미확인:** metadata 기반 후보 검토에는 사용 가능하다. 30건 외 관측 품질, 재포맷/시간 이동 중복, publisher-author linkage 및 라이선스 적합성은 확인되지 않았으므로 모델 학습/독립 최종 평가 자료로 승인한 결과가 아니다.

## 재현, 무결성, 실행 증거

명령:

```sh
cd /home/gnho1236/r2 &&
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
.venv-mlp/bin/python -B -m research.dataset_suitability_20261016.ops_trial
```

실행 환경은 Python 3.10.12, Linux 6.8.0-138-generic, 1.598371초, 최대 RSS 593,360 KiB였다. input 각 파일, ops metadata JSON 1,820개, producer/test 코드의 SHA-256은 `ops_trial.json`에 기록했다. 주요 입력 SHA-256:

- manifest: `b73137ea8daf0e86b7728250d32a48c3334a70f07a0e0028917d31c62d988a0e`
- ops sample audit: `e6ef035c4028e052a4d90340df391d09fa3dc96a11bc4f0b38a9b6b366d8e36d`
- RCAB inventory: `fb20d845667818671c50da2f83b36c83674f03bbddd12b545084fdfe780e6b2c`
- RCAB quality: `fd39f1c126ce780546ff8c7b3eed9cba3fed219151e484299ede0ab22246a8e5`
- 결과 JSON: `69b18b041fc71f130909bf80f377651385f913da51744ba82b73a8dd2354389c`

실제 실행은 monitor `mon_VP5WEZX6E1YS6JAM`, bash session `bash_11`에서 완료됐다. 보존된 `bash_output` 응답:

```text
{ text: 'status: completed exit_code: 0\nOPS_SUITABILITY_PASS' }
```

테스트 명령:

```sh
cd /home/gnho1236/r2 &&
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
.venv-mlp/bin/python -B -m unittest -v research.dataset_suitability_20261016.test_ops_trial

cd /home/gnho1236/r2 &&
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
.venv-mlp/bin/python -B -m unittest discover \
  -s research/dataset_suitability_20261016 -p test_ops_trial.py -v
```

각 실행은 7개 테스트 `OK`로 완료됐다. 테스트는 빈 hash 무시, 이름이 다른 파일의 같은 hash, 정규화 충돌, timezone 정규화, 동일 service의 복수 required fault, 전체 metadata와 telemetry 표본 지원 분리를 다룬다.
