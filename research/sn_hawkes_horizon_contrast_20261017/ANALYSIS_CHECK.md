# Saved-prediction horizon analysis

## Scope and provenance

This is the phase-3 analysis of the fixed SN validation predictions only. It
performed no fitting, inference, preprocessing, installation, download, or
ensemble scoring. It did not open `selected.npz`, checkpoints, raw/prepared
arrays, protected SN test/unassigned observations, or TT/RE2 data. Prediction
archives were loaded with `allow_pickle=False`.

Direction is **after relative − before absolute**: `before_absolute` is
`runs/absolute_seed_{11,23,37}/`; `after_relative` is the existing
`native_reproduction_20261013/calibration200/SN/diagmlp/seed_{11,23,37}/`.
Each prediction, config, and history SHA-256 matched the corresponding
artifact hash in that same arm's `summary.json`. Absolute and relative config
hashes intentionally differ; only common settings were compared semantically.
All six prediction archives had 78 ordered indices/labels, 12 root logits and
2 detection logits per row. Across arms and seeds, validation indices and
labels exactly matched metadata's 78 validation positions and original-index
order. Each seed had 65 fault and 13 normal labels.

Verified prediction SHA-256 values (also recorded in
`analysis_v2/input_audit.json`):

| Seed | Absolute | Relative |
|---:|---|---|
| 11 | `0f45452113bf34bbce87458be49c5dbfbadf75611a228ff32254f004a58d9b6b` | `1e48e85005008de75fdfd271df80bfb0daabc47c082757515b6e483614308d5d` |
| 23 | `dc6e038caf47175f8e681a458918bf22f81c620f843be003b5810377a1fa97a6` | `6271867b109a6336ad511d2a7b9125e50ed5d90d9a6d33afb759ed224e3c5987` |
| 37 | `af678df5966fac884ac25eff08583fe692c01d11fff45590563884f24cb4add4` | `7fb0ad414aede85ce4770a944058f0453ef4d51536f7fbca5d2ea843d8d64b55` |

## Main results

Primary outcome is **conditional root Top-1**, excluding normal windows.
Exact root-logit ties receive expected uniform-ranking credit. Root Top-3 uses
the same tie rule. Detection uses expected half-credit on exact binary-logit
ties; gated joint Top-1/Top-3 multiply root credit by fault-detection credit.
Denominators are faults 65, normals 13, and all windows 78 as applicable.
Per-seed values and unweighted three-seed means are in
`analysis_v2/scores.json`; every delta is relative-after minus
absolute-before.

| Seed | Absolute conditional root Top-1 | Relative conditional root Top-1 | Difference |
|---:|---:|---:|---:|
| 11 | 63/65 (96.92%) | 60/65 (92.31%) | −3/65 |
| 23 | 63/65 (96.92%) | 64/65 (98.46%) | +1/65 |
| 37 | 60/65 (92.31%) | 62/65 (95.38%) | +2/65 |
| Mean | 62/65 (95.38%) | 62/65 (95.38%) | 0 |

The exact primary paired partition over 195 fault-window/seed rows is
183 both-correct, 6 both-wrong, 3 newly correct, and 3 newly wrong. The
separately named **secondary gated-joint** partition is 181, 8, 3, and 3.
These are not independent events. `analysis_v2/paired_summary.json` includes
record, distinct-window, distinct-event, and seed-record counts. The complete
traceable fault-window/seed table is `paired_fault_windows.csv`; primary
conditional-root case lists are `root_new_correct.csv` and `root_new_wrong.csv`.
Joint-metric case lists are separately named `joint_*.csv`. Normal-window
detection changes are in `normal_detection_changes.csv`.

The analyzer also reports fault-only conditional root NLL. It does not infer a
prediction-derived joint loss because equivalence to the trainer's joint-loss
definition is not established. `history_metrics.csv` reuses stored train and
validation joint losses/metrics at epochs 1, 50, 200 and each selected epoch;
selected epoch/minimum loss are checked against each summary. Settings and
service ordering/config hashes are in `settings.csv`. `input_difference.json`
copies the recorded `inputs/preparation.json` difference summary; it describes
the observed input change, not a causal explanation of score changes.

Hawkes solver cap counts remain relative 387 and absolute 470. Cap hits are
not convergence evidence; no convergence or causal-effect claim is made.
The initial seed-23 incomplete-run FAIL, subsequent recovery, and all other
execution failure history remain recorded in `EXECUTION_VERIFY.md` and fit
receipts.

## Checks and outputs

- `python -B -m unittest -v test_analyze_horizon`: 1 test passed. Fixtures
  cover exact ties, normal exclusion, order rejection, four paired outcomes,
  and a root-correct/detector-wrong separation.
- `analyze_horizon.py --self-check`: `SELF_CHECK_PASS`.
- `pyright --project optionalpyright_analysis.json`: exit 0, 0 errors,
  warnings, or informations; LSP diagnostics reported no diagnostics.
- Actual saved-prediction analysis: exit 0, recorded as
  `ANALYSIS_PASS ... root_partition=195 joint_partition=195` and
  `ACTUAL_EXIT_CODE=0` in `analysis_v2/analysis-run.log`.
- Output roundtrip assertions passed: 195 paired rows; 3 primary new-correct
  and 3 primary new-wrong rows; both partitions sum to 195.

Corrected outputs are owned under `analysis_v2/`. Existing `analysis/` outputs
were left unchanged, including its earlier joint-gated partition. The
analyzer, fixture, this check, and generated `analysis_v2/` are the only
analysis deliverables changed.
