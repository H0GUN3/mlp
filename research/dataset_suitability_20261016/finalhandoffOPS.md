# ops-lite 실험 인계

2026-10-16 기준, 배정된 ops-lite metadata census와 cross-corpus duplicate stress checks를 마쳤다. `ops_trial.py` 및 테스트, exclusive-create 결과 JSON, 결과 보고서, 본 인계서만 신규 작성했다.

핵심 결론은 두 가지다. (1) 455건 metadata 중 현재 표본은 30건이고, 원 조건을 만족하는 metadata 후보는 419건이다. 현재 30건은 시스템당 10건으로 균등해 전체 system mix를 대표하지 않으며, 30건 이외 425건의 telemetry 품질은 알려져 있지 않다. (2) RCABench와 사례명/task ID/time 197개 쌍 및 실제 비어 있지 않은 telemetry SHA-256 일치 80개가 확인됐다. 따라서 corpus 간 독립성 주장은 지지되지 않는다. 숫자 injection ID는 204개가 겹쳤으나 8개는 서로 다른 사례명이므로 ID 단독 판정은 위험하다. 시간 이동/재포맷된 중복은 미확인이다.

`ops_trial.json`은 각 입력 및 코드 SHA-256, ops metadata JSON 1,820개별 SHA-256, 전체 상세 분포, 197개 name/task/time 연결, 204개 숫자 ID 연결, 80개 관측 hash별 양쪽 모든 경로, 실행 runtime과 result counts를 보존한다. RCAB 설정 schema는 comparable하다고 전제하지 않았으며 결과는 unknown으로 남겼다. README/논문 간 455/500건 및 라이선스 차이와 publisher-author 연결 미확인은 `OPS.md`에 제한사항으로 적었다.

검증:

- Package-qualified unit test 및 repo-root discovery: 각각 7 tests, `OK`.
- Diagnostics: `ops_trial.py`, `test_ops_trial.py` 모두 diagnostics 없음.
- 실제 CLI: monitor `mon_VP5WEZX6E1YS6JAM`; bash session `bash_11`.
- 정확한 완료 응답:

```text
{ text: 'status: completed exit_code: 0\nOPS_SUITABILITY_PASS' }
```

권장 다음 단계는 telemetry 대량 수집이 아니라, publisher/저자 배포 연결과 라이선스를 먼저 확인하고, 필요한 경우에만 별도 허가·계획으로 표본 밖 telemetry의 품질 및 재포맷/시간 이동 중복을 평가하는 것이다. 이 실험에서는 다운로드, 학습, 추론 또는 최종시험을 하지 않았다.
