# RCAEval metadata-only feasibility trial

**Result:** metadata supports a leakage-aware feasibility dry run over 240 RE2/RE3
Online Boutique and Train Ticket cases. It does **not** establish telemetry
quality or RCA performance. No case telemetry, final observations, predictions,
or protected native test/unassigned data were read.

## Scope and metadata checks

The fixed RCAEval index has 735 rows. The relevant trace-primary scope is 240:
RE2-OB 90, RE2-TT 90, RE3-OB 30, and RE3-TT 30. The other 495 rows are excluded:
RE1-OB/SS/TT 125 each, RE2-SS 90, and RE3-SS 30. This preserves the protocol’s
exclusion of metric-only RE1 and untraced Sock Shop.

For all 240 cases, index `has_logs`/`has_traces` flags agree with the pinned
source-file manifest. The existing local readiness/audit metadata covers 180
RE2-OB/TT cases; the other 60 relevant cases are RE3-OB/TT and have no local
case audit in the allowed evidence. In the 180 local cases, file presence and
positive row counts for metrics/logs/traces were checked against the existing
audit metadata; flags and readiness row counts agree. This reuses stored audit
results and does not reopen any telemetry.

| Suite | Cases | Root/fault conditions | Repetitions per condition | Root-service cases | Fault-type cases | Logs | Traces |
|---|---:|---:|---|---|---|---:|---:|
| RE2-OB | 90 | 30 | all 3 | 5 roots × 18 | 6 faults × 15 | 90 | 90 |
| RE2-TT | 90 | 30 | all 3 | 5 roots × 18 | 6 faults × 15 | 89 | 90 |
| RE3-OB | 30 | 10 | all 3 | adservice 9, cartservice 3, currencyservice 3, emailservice 15 | f1 9, f2 3, f3 6, f4 6, f5 6 | 30 | 30 |
| RE3-TT | 30 | 8 | 3×4 conditions, 4×3 conditions, 6×1 condition | ts-auth-service 15, ts-route-service 15 | f1 7, f2 7, f3 10, f4 6 | 30 | 30 |

RE3 is not a uniform repetition grid. RE3-TT’s exact root/fault repetitions
are `ts-auth-service`: f1=4, f2=4, f3=4, f4=3; `ts-route-service`: f1=3,
f2=3, f3=6, f4=3. RE3-OB has three repetitions for each of its ten conditions,
but its service and fault marginal counts are uneven as shown above.

## Hypothetical grouped three-folds

This independent metadata-only dry run groups by `(system, root_cause_service,
fault)`. A compact UTF-8 JSON array of the tuple is the canonical group string;
fold is `int(SHA256("suitability-20261016:" + canonical_group)) mod 3`.
All 78 groups stay intact, with zero group overlap between each train and
held-out partition. These are hypothetical feasibility folds, not a replacement
for the declared split.

| Fold held out | Train cases / groups | Held-out cases / groups | Train root support | Held-out root support | Train fault support | Held-out fault support |
|---:|---:|---:|---|---|---|---|
| 0 | 158 / 52 | 82 / 26 | all 12 labels | 10: all except cartservice, currencyservice | all 11 labels | 8: cpu, delay, disk, f3, f5, loss, mem, socket |
| 1 | 136 / 44 | 104 / 34 | 11: all except cartservice | all 12 labels | 10: all except f1 | all 11 labels |
| 2 | 186 / 60 | 54 / 18 | all 12 labels | 10: all except adservice, cartservice | all 11 labels | 8: cpu, delay, disk, f2, f4, loss, mem, socket |

The 12 root labels are the five Online Boutique and five Train Ticket RE2
services plus `adservice` and `cartservice`. The 11 fault labels are RE2’s six
fault labels and RE3’s `f1`–`f5`. “Support” is the union over both systems;
it is not a per-system guarantee. For contrast only, assigning individual case
IDs by the same hash separates repetitions in 67 of 78 repeated conditions.
That case-level split leaks condition identity by construction and is not a
performance comparison.

## RE2-to-RE3 transfer feasibility (index-label comparison only)

| System | RE2 root-label candidate proxy | RE3 roots | Root overlap | RE3 roots absent from proxy | RE3 root/fault pairs new to RE2 |
|---|---|---|---:|---|---:|
| OB | checkoutservice, currencyservice, emailservice, productcatalogservice, recommendationservice | adservice, cartservice, currencyservice, emailservice | currencyservice, emailservice (2) | adservice, cartservice (2) | 10/10 |
| TT | ts-auth-service, ts-order-service, ts-route-service, ts-train-service, ts-travel-service | ts-auth-service, ts-route-service | ts-auth-service, ts-route-service (2) | none | 8/8 |

No RE3 root/fault label pair exactly overlaps an RE2 pair. This is a literal
index-label comparison, not a claim that RE3’s `f*` taxonomy is mapped to RE2’s
fault taxonomy. The “candidate proxy” is only the set of root labels occurring
in RE2’s case index; it is **not** an inventory of all services visible in
telemetry or a verified candidate list.

## Existing split boundary and interpretation

The read-only `research/reassessment_20261013/adequacy.md` and `data_catalog.md`
describe the existing fixed RE2 split as, per system, 54 train / 18 validation /
18 final-test cases and 18 / 6 / 6 system-root-fault scenarios. That boundary
is left unchanged. Its underlying manifest was not read for this trial, so the
mapping of that split to the full 240-case RE2+RE3 scope is not established.
The hypothetical folds above must not be used to reassign existing final cases.

**Metadata-ready:** 240 indexed OB/TT RE2+RE3 cases have usable grouping,
root/fault labels, and metadata modality flags; an index-only grouped-fold and
RE2→RE3 feasibility comparison is possible.

**Raw-coverage-unverified:** only the existing 180-case RE2 audit has local
file-row evidence here. The 60 RE3 cases were not downloaded or opened, and
index/source-manifest flags do not prove valid or sufficient telemetry,
service-level observability, or root-cause evidence. No ranking/model,
candidate-service inventory, or final performance claim was produced.

Future processing would require an approved policy for the missing RE3 files,
raw coverage checks without opening protected final observations, a measured
telemetry-derived candidate inventory, explicit fault-taxonomy mapping, and
confirmation that any new development/evaluation split respects the existing
final boundary. None of that processing is performed here.

## Reproducibility and run evidence

Command:

```bash
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m research.dataset_suitability_20261016.rcaeval_trial
```

Runtime: Python 3.10.12, NumPy 1.26.4, PyArrow 19.0.1; elapsed 0.126338 s;
maximum RSS 277336 KiB. The output JSON records full input and source-code
SHA-256 values. Read-only protocol/split-document hashes:

| Input | SHA-256 |
|---|---|
| `research/dataset_suitability_20261016/PROTOCOL.md` | `569703d983be487c7c752a25610b63db2b5fbd7775c541881e13416284057352` |
| `research/reassessment_20261013/data_catalog.md` | `e22c06ddab89d88d770338a5dbacad2468d3c3ec51f472519265f6c4785c7d35` |
| `research/reassessment_20261013/adequacy.md` | `49fb25aeb186c55c8835442d3f5fd6275c976da1b840bd8572704ff3a298384e` |

The focused tests passed in package-qualified and repository-root discovery
modes (6 tests in each invocation). The test monitor was
`mon_RDG0F36EHAKJP7JG` (session `bash_2`).

Test commands:

```bash
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m unittest -v research.dataset_suitability_20261016.test_rcaeval_trial
cd /home/gnho1236/r2 && OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv-mlp/bin/python -B -m unittest discover -s research/dataset_suitability_20261016 -p test_rcaeval_trial.py -v
```

Exact retained `bash_output` response for the test monitor:

```text
status: completed exit_code: 0
test_case_level_contrast_exposes_within_condition_split (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok
test_group_folds_keep_condition_repetitions_together (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok
test_nonuniform_repetitions_are_preserved (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok
test_relevant_scope_excludes_re1_and_sock_shop (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok
test_transfer_finds_unseen_root_and_fault_conditions (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok
test_validation_rejects_bad_metadata_and_flag_mismatch (research.dataset_suitability_20261016.test_rcaeval_trial.MetadataTests) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
test_case_level_contrast_exposes_within_condition_split (test_rcaeval_trial.MetadataTests) ... ok
test_group_folds_keep_condition_repetitions_together (test_rcaeval_trial.MetadataTests) ... ok
test_nonuniform_repetitions_are_preserved (test_rcaeval_trial.MetadataTests) ... ok
test_relevant_scope_excludes_re1_and_sock_shop (test_rcaeval_trial.MetadataTests) ... ok
test_transfer_finds_unseen_root_and_fault_conditions (test_rcaeval_trial.MetadataTests) ... ok
test_validation_rejects_bad_metadata_and_flag_mismatch (test_rcaeval_trial.MetadataTests) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
RCAEVAL_TESTS_PASS
```

Exact retained `bash_output` response for the actual CLI:

```text
status: completed exit_code: 0
RCAEVAL_SUITABILITY_PASS cases=240 groups=78 local=180
```

The monitor completion also reported:

```text
RCAEVAL_SUITABILITY_PASS cases=240 groups=78 local=180
watcher completed (exit code 0)
```

The actual CLI monitor was `mon_P0F5FF2HMKMBMM23` (session `bash_3`).

Diagnostics found no source-code errors. Pyright could not resolve the absolute
package import in this new test (and reports the same issue in the existing
`test_eadro_trial.py` and `test_rcab_trial.py`); the parent-owned
`pyrightconfig.json` was not changed. Both requested unittest invocation modes
did import and pass.
