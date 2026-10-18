# 현재 로그 feature 차원 1,025의 출처

## 요약

현재 `event_count=1025`는 **Drain 설정 상한 1,024개를 다 채운 동결 snapshot의 템플릿 feature 1,024개와 미매칭용 unknown bin 1개(인덱스 0)**의 합이다. 모델 이론이 요구하는 고정 차원이나 데이터의 고유 로그 종류 총수가 아니다.

## 근거와 계산

- `research/native_reproduction_20261013/native_inputs/drain3.ini:22-26`의 `[DRAIN]` 설정은 `sim_th=0.9`, `depth=4`, `max_children=100`, `max_clusters=1024`다. `research/tt_re2_baselines_20261017/re2_stage2.py:32,202-205`에서 이 파일을 읽어 Drain miner를 만든다.
- 현재 준비 코드 `research/re2_ob_known_condition_20261018/prepare.py:374-405`는 TRAIN 행만 순회하고, 각 행을 `timestamp < injection` 조건으로 miner에 넣는다. 최종 보유 cluster를 `clusters`로 모은 뒤 `event_count = len(clusters) + 1`, `unknown_bin = 0`으로 기록하고, retained cluster마다 feature 번호를 1부터 배정한다. `prepare.py:409-410`은 생성 수와 퇴출 수를 기록한다. 매칭되지 않은 로그는 `research/tt_re2_baselines_20261017/re2_stage2.py:290-292`에서 0이 된다. 같은 파일 `:350,455,497`은 이 `event_count`를 Hawkes knot 생성 및 `logs` 배열의 마지막 축 크기로 사용한다.
- 저장된 현재 증거 `research/re2_ob_known_condition_20261018/artifacts/templates.json`은 48개 TRAIN source의 엄격한 주입 전 로그 합계가 4,237,203행임을 기록한다 (`:6155,6161-6399`). 저장된 cluster 수는 1,024이고, feature map 항목도 1,024개다. `:6150-6155,6403-6404`의 metadata는 `clusters_created=339038`, `clusters_evicted=338014`, `event_count=1025`, `lines=4237203`, `unknown_bin=0`, `validation_fit_lines=0`을 기록한다.
- resident 산술 확인: `339038 − 338014 = 1024`; `len(clusters)=1024`; `1024 + 1 = 1025`. 현재 보유 1,024개 template 문자열은 1,024개로 서로 다르다. 그러나 **339,038은 실행 중 발생한 cluster 생성 횟수**이지, 전체 이력에서 중복 문자열을 제거한 고유 semantic template 수가 아니다.

## LRU와 257차원 점검의 경계

1,024는 Drain의 설정된 `max_clusters`이자 LRU가 유지할 수 있는 상한이다. 기록은 4,237,203개의 strictly-preinject TRAIN 행을 처리하면서 그 상한에 도달했고, 이후 생성된 cluster 중 일부가 퇴출되었음을 보여준다. 최종 snapshot은 LRU 생존자이지, 과거 전체 cluster를 빈도순 정렬한 목록이 아니다. 퇴출 cluster의 완전한 이력이나 최종 1,024개 밖에 남은 과거 template 집합은 이 metadata로 복원할 수 없다.

따라서 BRIEF의 257차원 계획은 **동결된 1,024 생존자 안에서** TRAIN 매칭 빈도 상위 256개를 고르는 것이다. 이는 과거 생성된 339,038개 전체에서 top-256을 뽑는 것이 아니며, 이미 퇴출된 cluster는 후보가 될 수 없다. 이 문서는 비용 점검용 계획만 설명하며 새 매칭·집계·fit을 수행하지 않았다.

## 기존 기록과 근거의 한계

이전 데이터 기준을 기록한 `research/native_reproduction_20261013/rca_native_cost.md:7-12`는 OB의 4,771,132 normal rows, 생성 376,565 clusters 및 intrinsic eviction을 보고한다. 이는 현재 48 TRAIN source의 strictly-preinject 4,237,203행 및 339,038회 생성과 **다른 기존 기록·집계 기준**이다. 두 수치를 같은 표본이나 동일한 행 수로 취급하지 않는다. 같은 보고서 `:11`과 `research/native_reproduction_20261013/rca_port_audit_gate.md:9`는 상한을 intrinsic LRU로 기술하고, `research/native_reproduction_20261013/RCA_PARSER_TRANSFER_CHECK.md:4,19-20`은 상한을 유지할 설정으로 다룬다.

확인한 코드·설정·산출물·기존 비용/감사 기록에는 **왜 1,024를 선택했는지**에 대한 이론적 유도나 독립된 경험적 선택 절차가 없다. 확인되는 사실은 설정값, 상한 도달, LRU 퇴출, 그리고 그 결과의 차원뿐이다. 그러므로 1,024가 최적이거나 과학적으로 필수라고 결론내릴 수 없다. 또한 `research/native_reproduction_20261013/native_models.py:59-76,95`의 참조 모델은 `event_count`를 인자로 받아 입력 크기를 구성하므로, 1,025가 모델 구조에 내장된 필수 상수라는 근거도 없다.

## 확인 범위와 해시

해시는 이 기록 작성 시 읽은 파일의 SHA-256이다. 전체 템플릿 본문은 보고하지 않았다.

| 경로 | SHA-256 |
|---|---|
| `research/re2_ob_known_condition_20261018/prepare.py` | `16054c56d643db7e6046b0e2ef1789bf3a12172d239a064c0ecf837c5e35c7c3` |
| `research/re2_ob_known_condition_20261018/artifacts/templates.json` | `8fbdd0cf419679294fe645cea1d3c66f81484ff1be7d59f6deb330d73b2b6b53` |
| `research/native_reproduction_20261013/native_inputs/drain3.ini` | `d106ce127611fc0607871a08e7825edae7c24651b8e4c3dbafe836550f40c86c` |
| `research/tt_re2_baselines_20261017/re2_stage2.py` | `f63a2633ea1a9e8778876ec899816bd1d70618a801bd91cbc6dbc11c25fbdae8` |
| `research/native_reproduction_20261013/rca_native_cost.md` | `aece660c800ee85c60874c68c59cdda66c5646832563b60b2e60d0fdc4eab655` |
| `research/native_reproduction_20261013/rca_port_audit_gate.md` | `ddf1641ca78944c606325bcaefce736c66fb361789e4f599536e8a95522808df` |
| `research/native_reproduction_20261013/RCA_PARSER_TRANSFER_CHECK.md` | `a24a6b2c876b8b81f98c22cccb195d2ae73762f2ceca0ecefafed56578c6f10e` |

`templates.json`에는 split SHA-256 `3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2`, input-binding SHA-256 `e65db027735a564075197173189bc7bdfb2672dd42401aae23370e5a7f8e534c`, snapshot SHA-256 `70c77a932c150cf47488a7fd3b1a0efc9abfde11856c30090c7584e1925b3072`, 설정 SHA-256 `d106ce127611fc0607871a08e7825edae7c24651b8e4c3dbafe836550f40c86c`가 기록되어 있다.

범위는 이 문서에 인용한 코드·설정·기존 문서와 `templates.json`의 metadata 요약이다. observation NPZ, 원문 로그, 보호 사례, solver 실행은 열지 않았다. `cost_257`에는 확인 시점에 `BRIEF.md`만 있었으며, 257차원 결과 산출물은 아직 기록되어 있지 않았다.
