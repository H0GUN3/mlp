# RE2-OB known-condition split handoff

## 실제 복구 실행 결과 — 2026-10-18

**PASS.** 최초 child는 합성 fixture의 보호/검증 조합을 잘못 만들어 테스트가
실패했고 split.json을 생성하지 못했다. 주 담당이 실제 메타데이터의6개 보호 조합과
6개 기존 validation 조합으로 fixture를 정정했다. 테스트 조건이나 실제 분할은 약화·변경하지 않았다.
첫 실제 CLI에서는 metadata 파일에 자기 자신의 해시가 있을 것이라고 가정한
loader 오류가 발견됐다. 파일 내용을 한 번 읽어 외부 manifest SHA256과 대조한 뒤
그 검증값만 메모리 구조에 넣도록 수정했다. metadata를 열기 전에72건 허용목록을
대조하는 경계도 추가하고 두 회귀 검사를 작성했다.

실제 명령:

```text
cd /home/gnho1236/r2 &&
.venv-eadro/bin/python -B -m unittest -v research.re2_ob_known_condition_20261018.test_split &&
/home/gnho1236/.local/bin/pyright --project research/re2_ob_known_condition_20261018 &&
.venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.split
```

원래 monitor `mon_RP477XAM1S1HM5WE` / 부모 `bash_4`의 완료 알림:

```text
Ran 7 tests in 0.013s
OK
0 errors, 0 warnings, 0 informations
KNOWN_SPLIT_PASS
watcher completed (exit code 0)
```

생성 결과를 직접 대조해 TRAIN48 / validation24 / protected18,
24조합의2/1배치와 검증반복12/9/3을 확인했다. 원래 split SHA256은 불변이다.
최종 해시:
- `split.json`: `3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2`
- `split.py`: `92d27aa5c9ab57a27ed270c788a113c4205a1a755e4025d46524bdc4c63d8f95`
- `test_split.py`: `397fbb90da659f6e8e52753a030344c5a485242fccdcab1c0de864f54445b6c0`

시간 구간 검증은 아래 명시한 대로 아직 별도이며, 입력 준비 단계에서
허용 stage1의 시작시각 배열을 읽어 확인한다. 모델 학습은 아직 하지 않았다.

The deterministic assignment is fixed before baseline fitting. For each of the
24 development `(root_cause_service, fault)` groups, one repetition is selected
by the protocol SHA-256 rule; its other two repetitions go to TRAIN.

## Run

From `/home/gnho1236/r2`:

```sh
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  .venv-eadro/bin/python -B -m research.re2_ob_known_condition_20261018.split
```

Expected exit: `0`; expected sentinel: `KNOWN_SPLIT_PASS`. The command refuses
to overwrite an existing `split.json` and creates only that file.

Focused test command:

```sh
.venv-eadro/bin/python -B -m unittest research.re2_ob_known_condition_20261018.test_split
```

Expected exit: `0`.

## Input evidence

- Original split: `research/mlp_prerequisites/split.json`, SHA-256
  `1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`.
- Stage1 manifest: `research/tt_re2_baselines_20261017/RE2_STAGE1_MANIFEST.json`,
  SHA-256 `7f1c7de45db8e36726279a2ba879823c360755718a29600b7999226b6e004d72`.
- Stage1 case metadata hashes were checked against all 72 manifest entries;
  each case reported `PASS_UNSCALED_CASE`, and the manifest reported
  `PASS_UNSCALED_ONLY`.
- The existing RE2-OB split has 90 cases: TRAIN54, validation18, protected
  test18; 24 development groups × three repeats and six protected groups.
- Result: TRAIN48, validation24, protected names18. Chosen validation repeat
  counts are repetition 1:12 groups, 2:9, 3:3.
- All 24 development service-fault combinations are represented in both
  TRAIN and validation. Stage1 metadata raw hashes were compared per modality;
  no identical raw file hash crossed the new partitions.
- Approved metadata does not contain absolute observation-window intervals;
  temporal interval overlap is therefore **unverified**, not asserted absent.
  The protected case files were not opened.

`split.json` records row provenance, original and new partitions, selected
repetition, stage1 metadata hash, source/raw hashes, aggregate counts, and the
overlap-check limitation. No old split or fitted artifacts are modified.

## Recovery confirmation — 2026-10-18

**PASS.** Rechecked the recovered files without regenerating the split: 48
TRAIN, 24 validation, and 18 protected cases; each of 24 development groups
has a 2/1 train/validation allocation, with selected repetitions 12/9/3.
Hashes match the recorded values for `split.json`
(`3cf224eaabcdf8ddc122f0f922d669702ce0a2e7fd6e25b8534aa4741df3acf2`),
`split.py`
(`92d27aa5c9ab57a27ed270c788a113c4205a1a755e4025d46524bdc4c63d8f95`),
and `test_split.py`
(`397fbb90da659f6e8e52753a030344c5a485242fccdcab1c0de864f54445b6c0`).
The original split remains unchanged at SHA256
`1644bb875d061884b8dff37203b07761bd5f11ae3f3e9ed7f8f44687eb3142e5`.
The earlier failed child attempt and subsequent fixture/metadata-loader
corrections remain documented above. This confirmation relies on the captured
7-test, Pyright, and actual CLI exit-0 evidence above; those commands were not
rerun. Temporal interval overlap remains unverified; training has not begun.
