# 분석 차단 원인 정정 — 서로 다른 arm의 config 해시 혼동

분석 노드는 기존 relative seed11 config의 SHA를 새 absolute seed11 config에
적용하려다가 실제 해시 계산 없이 중단했다. 이는 파일 손상 발견이 아니다.
두 arm의 config는 입력·출력 경로와 horizon이 다르므로 서로 다른 해시가 정상이다.

부모가 2026-10-17 각 실제 config 바이트를 SHA-256으로 계산하고,
각 absolute arm의 자체 summary.artifact_hashes["config.json"]과 대조했다.
3개 모두 일치했다. 연구 데이터 재생성·모델 재실행은 하지 않았다.

| seed | 기존 relative config | 새 absolute config | 새 config와 자체 summary |
|---|---|---|---|
|11|84e6f67dd9518a950a95f57407aac66d107c7fa593008e65823c542940c30b51|f3edfbfd0b9266dd2334cdf387a25725fc77aef90211947b140fdd5de2d4937c|일치|
|23|de19917e74d9804202ec941e3c3b86adb31dd963d730d33b0e3bcf9077df8623|5b73db88329ec8b8c72576c86c7e0f4b908746e3fead50c1521fae5c70476395|일치|
|37|314e2efface4b110eaa22c80a69d3e5653ed2ec43dced2923334758a5cbe245a|b58e79cefa1837b85d2befe5d40b50a0ab988ee29406169405245ed117d04411|일치|

분석은 각 arm의 저장 예측을 **그 arm의 summary** 해시로 검사한다.
실제 값/라벨/인덱스 동일성은 해시가 아니라 두 예측 배열의 대응 검사다.
현재 승인된 저장 예측 채점 범위 안의 처리이므로 추가 승인 질문은 필요 없다.
학습/입력준비/preflight는 완료돼 있으며 재실행하지 않는다.
