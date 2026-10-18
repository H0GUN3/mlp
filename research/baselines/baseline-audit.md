# Baseline verification and bounded failure analysis

**Status: reproducibility PASS.** Independent checks passed for the frozen 36-case
development artifact. This is not a held-out result, nor evidence of statistical
significance, novelty, efficacy beyond these cases, or generalization.

## Scope and integrity

- 36 unique reserved cases in 12 scenario groups, three repetitions per group.
- The original 12 heuristic rankings match the frozen smoke feature rankings exactly:
  **11/12 Top-1, 12/12 Top-3**.
- BARO scores/rankings were independently recomputed from raw metrics for reserved
  cases only. The frozen formula uses whole windows, past-only forward fill then zero
  for leading missing values, excludes latency-50, renames latency-90, removes
  per-window constants, converts memory to MB, and applies signed/absolute max
  normalized changes with the specified near-zero-IQR fallback.
- Protected 144 telemetry was not read; no traces were read. Data access was restricted
  to `metrics.parquet` for the reserved 36. Source/hash provenance checked as recorded
  in `verification.json`; telemetry hashes for non-metric files were not reopened.

## Exact results

| Method | Top-1 | Top-3 | MRR | Root omitted from ranking | Gold candidate omitted |
|---|---:|---:|---:|---:|---:|
| `median_change` | 30/36 | 35/36 | 0.888889 | 0 | 0 |
| `baro_signed` | 10/36 | 30/36 | 0.557253 | 0 | 0 |
| `baro_absolute_variant` | 10/36 | 30/36 | 0.557001 | 0 | 0 |

### By system

| Method | System | n | Top-1 | Top-3 | MRR |
|---|---|---:|---:|---:|---:|
| `median_change` | RE2-OB | 18 | 15/18 | 18/18 | 0.888889 |
| `median_change` | RE2-TT | 18 | 15/18 | 17/18 | 0.888889 |
| `baro_signed` | RE2-OB | 18 | 1/18 | 16/18 | 0.472222 |
| `baro_signed` | RE2-TT | 18 | 9/18 | 14/18 | 0.642284 |
| `baro_absolute_variant` | RE2-OB | 18 | 1/18 | 16/18 | 0.472222 |
| `baro_absolute_variant` | RE2-TT | 18 | 9/18 | 14/18 | 0.641779 |

### By fault type

| Method | Fault | n | Top-1 | Top-3 | MRR |
|---|---|---:|---:|---:|---:|
| `median_change` | cpu | 6 | 6/6 | 6/6 | 1.000000 |
| `median_change` | delay | 6 | 1/6 | 5/6 | 0.416667 |
| `median_change` | disk | 6 | 6/6 | 6/6 | 1.000000 |
| `median_change` | loss | 6 | 6/6 | 6/6 | 1.000000 |
| `median_change` | mem | 6 | 5/6 | 6/6 | 0.916667 |
| `median_change` | socket | 6 | 6/6 | 6/6 | 1.000000 |
| `baro_signed` | cpu | 6 | 2/6 | 6/6 | 0.638889 |
| `baro_signed` | delay | 6 | 0/6 | 1/6 | 0.190741 |
| `baro_signed` | disk | 6 | 3/6 | 6/6 | 0.750000 |
| `baro_signed` | loss | 6 | 2/6 | 6/6 | 0.611111 |
| `baro_signed` | mem | 6 | 3/6 | 6/6 | 0.750000 |
| `baro_signed` | socket | 6 | 0/6 | 5/6 | 0.402778 |
| `baro_absolute_variant` | cpu | 6 | 2/6 | 6/6 | 0.638889 |
| `baro_absolute_variant` | delay | 6 | 0/6 | 1/6 | 0.189226 |
| `baro_absolute_variant` | disk | 6 | 3/6 | 6/6 | 0.750000 |
| `baro_absolute_variant` | loss | 6 | 2/6 | 6/6 | 0.611111 |
| `baro_absolute_variant` | mem | 6 | 3/6 | 6/6 | 0.750000 |
| `baro_absolute_variant` | socket | 6 | 0/6 | 5/6 | 0.402778 |

### Paired case outcomes (Top-1)

| Pair | Left wins | Right wins | Ties |
|---|---:|---:|---:|
| `median_change_vs_baro_signed` | 21 | 1 | 14 |
| `median_change_vs_baro_absolute_variant` | 21 | 1 | 14 |
| `baro_signed_vs_baro_absolute_variant` | 0 | 0 | 36 |

## Per-method root misses and case evidence

Every listed non-Top-1 outcome is a ranking failure against the dataset's
recorded root-cause label; it does not identify a causal victim. Candidate metrics
are correlates in these windows, not verified propagation or causal evidence.
An omitted root means it was not ranked among the method's candidates.

### `median_change` — 6 non-Top-1 outcomes; 0 candidate omissions

- `re2ob_checkoutservice_delay_1` (RE2-OB/delay): root rank 3; preceding candidates: S04 (rank 1), S07 (rank 2).
- `re2ob_checkoutservice_delay_2` (RE2-OB/delay): root rank 3; preceding candidates: S03 (rank 1), S08 (rank 2).
- `re2ob_checkoutservice_delay_3` (RE2-OB/delay): root rank 3; preceding candidates: S01 (rank 1), S06 (rank 2).
- `re2tt_ts-train-service_mem_3` (RE2-TT/mem): root rank 2; preceding candidates: S04 (rank 1).
- `re2tt_ts-travel-service_delay_1` (RE2-TT/delay): root rank 6; preceding candidates: S06 (rank 1), S13 (rank 2), S19 (rank 3), S43 (rank 4), S48 (rank 5).
- `re2tt_ts-travel-service_delay_3` (RE2-TT/delay): root rank 3; preceding candidates: S07 (rank 1), S18 (rank 2).

### `baro_signed` — 26 non-Top-1 outcomes; 0 candidate omissions

- `re2ob_checkoutservice_delay_1` (RE2-OB/delay): root rank 4; preceding candidates: S13 (rank 1), S04 (rank 2), S07 (rank 3).
- `re2ob_checkoutservice_delay_2` (RE2-OB/delay): root rank 4; preceding candidates: S04 (rank 1), S12 (rank 2), S03 (rank 3).
- `re2ob_checkoutservice_delay_3` (RE2-OB/delay): root rank 3; preceding candidates: S12 (rank 1), S13 (rank 2).
- `re2ob_checkoutservice_loss_1` (RE2-OB/loss): root rank 2; preceding candidates: S12 (rank 1).
- `re2ob_checkoutservice_loss_2` (RE2-OB/loss): root rank 3; preceding candidates: S11 (rank 1), S01 (rank 2).
- `re2ob_checkoutservice_loss_3` (RE2-OB/loss): root rank 2; preceding candidates: S07 (rank 1).
- `re2ob_checkoutservice_mem_1` (RE2-OB/mem): root rank 2; preceding candidates: S02 (rank 1).
- `re2ob_checkoutservice_mem_2` (RE2-OB/mem): root rank 2; preceding candidates: S09 (rank 1).
- `re2ob_checkoutservice_socket_1` (RE2-OB/socket): root rank 2; preceding candidates: S13 (rank 1).
- `re2ob_checkoutservice_socket_2` (RE2-OB/socket): root rank 2; preceding candidates: S03 (rank 1).
- `re2ob_checkoutservice_socket_3` (RE2-OB/socket): root rank 2; preceding candidates: S06 (rank 1).
- `re2ob_emailservice_cpu_1` (RE2-OB/cpu): root rank 3; preceding candidates: S08 (rank 1), S01 (rank 2).
- `re2ob_emailservice_cpu_2` (RE2-OB/cpu): root rank 2; preceding candidates: S03 (rank 1).
- `re2ob_emailservice_cpu_3` (RE2-OB/cpu): root rank 2; preceding candidates: S06 (rank 1).
- `re2ob_recommendationservice_disk_1` (RE2-OB/disk): root rank 2; preceding candidates: S04 (rank 1).
- `re2ob_recommendationservice_disk_2` (RE2-OB/disk): root rank 2; preceding candidates: S04 (rank 1).
- `re2ob_recommendationservice_disk_3` (RE2-OB/disk): root rank 2; preceding candidates: S02 (rank 1).
- `re2tt_ts-auth-service_socket_1` (RE2-TT/socket): root rank 3; preceding candidates: S25 (rank 1), S50 (rank 2).
- `re2tt_ts-auth-service_socket_2` (RE2-TT/socket): root rank 4; preceding candidates: S41 (rank 1), S68 (rank 2), S24 (rank 3).
- `re2tt_ts-auth-service_socket_3` (RE2-TT/socket): root rank 3; preceding candidates: S58 (rank 1), S05 (rank 2).
- `re2tt_ts-route-service_cpu_2` (RE2-TT/cpu): root rank 2; preceding candidates: S39 (rank 1).
- `re2tt_ts-route-service_loss_2` (RE2-TT/loss): root rank 3; preceding candidates: S13 (rank 1), S07 (rank 2).
- `re2tt_ts-train-service_mem_2` (RE2-TT/mem): root rank 2; preceding candidates: S03 (rank 1).
- `re2tt_ts-travel-service_delay_1` (RE2-TT/delay): root rank 10; preceding candidates: S50 (rank 1), S65 (rank 2), S48 (rank 3), S06 (rank 4), S13 (rank 5), S66 (rank 6), S24 (rank 7), S41 (rank 8), S32 (rank 9).
- `re2tt_ts-travel-service_delay_2` (RE2-TT/delay): root rank 9; preceding candidates: S41 (rank 1), S26 (rank 2), S19 (rank 3), S04 (rank 4), S30 (rank 5), S67 (rank 6), S62 (rank 7), S05 (rank 8).
- `re2tt_ts-travel-service_delay_3` (RE2-TT/delay): root rank 10; preceding candidates: S40 (rank 1), S07 (rank 2), S18 (rank 3), S42 (rank 4), S15 (rank 5), S34 (rank 6), S36 (rank 7), S24 (rank 8), S46 (rank 9).

### `baro_absolute_variant` — 26 non-Top-1 outcomes; 0 candidate omissions

- `re2ob_checkoutservice_delay_1` (RE2-OB/delay): root rank 4; preceding candidates: S13 (rank 1), S04 (rank 2), S07 (rank 3).
- `re2ob_checkoutservice_delay_2` (RE2-OB/delay): root rank 4; preceding candidates: S04 (rank 1), S12 (rank 2), S03 (rank 3).
- `re2ob_checkoutservice_delay_3` (RE2-OB/delay): root rank 3; preceding candidates: S12 (rank 1), S13 (rank 2).
- `re2ob_checkoutservice_loss_1` (RE2-OB/loss): root rank 2; preceding candidates: S12 (rank 1).
- `re2ob_checkoutservice_loss_2` (RE2-OB/loss): root rank 3; preceding candidates: S11 (rank 1), S01 (rank 2).
- `re2ob_checkoutservice_loss_3` (RE2-OB/loss): root rank 2; preceding candidates: S07 (rank 1).
- `re2ob_checkoutservice_mem_1` (RE2-OB/mem): root rank 2; preceding candidates: S02 (rank 1).
- `re2ob_checkoutservice_mem_2` (RE2-OB/mem): root rank 2; preceding candidates: S09 (rank 1).
- `re2ob_checkoutservice_socket_1` (RE2-OB/socket): root rank 2; preceding candidates: S13 (rank 1).
- `re2ob_checkoutservice_socket_2` (RE2-OB/socket): root rank 2; preceding candidates: S03 (rank 1).
- `re2ob_checkoutservice_socket_3` (RE2-OB/socket): root rank 2; preceding candidates: S06 (rank 1).
- `re2ob_emailservice_cpu_1` (RE2-OB/cpu): root rank 3; preceding candidates: S08 (rank 1), S01 (rank 2).
- `re2ob_emailservice_cpu_2` (RE2-OB/cpu): root rank 2; preceding candidates: S03 (rank 1).
- `re2ob_emailservice_cpu_3` (RE2-OB/cpu): root rank 2; preceding candidates: S06 (rank 1).
- `re2ob_recommendationservice_disk_1` (RE2-OB/disk): root rank 2; preceding candidates: S04 (rank 1).
- `re2ob_recommendationservice_disk_2` (RE2-OB/disk): root rank 2; preceding candidates: S04 (rank 1).
- `re2ob_recommendationservice_disk_3` (RE2-OB/disk): root rank 2; preceding candidates: S02 (rank 1).
- `re2tt_ts-auth-service_socket_1` (RE2-TT/socket): root rank 3; preceding candidates: S25 (rank 1), S50 (rank 2).
- `re2tt_ts-auth-service_socket_2` (RE2-TT/socket): root rank 4; preceding candidates: S41 (rank 1), S68 (rank 2), S24 (rank 3).
- `re2tt_ts-auth-service_socket_3` (RE2-TT/socket): root rank 3; preceding candidates: S58 (rank 1), S05 (rank 2).
- `re2tt_ts-route-service_cpu_2` (RE2-TT/cpu): root rank 2; preceding candidates: S39 (rank 1).
- `re2tt_ts-route-service_loss_2` (RE2-TT/loss): root rank 3; preceding candidates: S13 (rank 1), S07 (rank 2).
- `re2tt_ts-train-service_mem_2` (RE2-TT/mem): root rank 2; preceding candidates: S03 (rank 1).
- `re2tt_ts-travel-service_delay_1` (RE2-TT/delay): root rank 10; preceding candidates: S50 (rank 1), S65 (rank 2), S48 (rank 3), S06 (rank 4), S13 (rank 5), S66 (rank 6), S24 (rank 7), S41 (rank 8), S32 (rank 9).
- `re2tt_ts-travel-service_delay_2` (RE2-TT/delay): root rank 9; preceding candidates: S41 (rank 1), S26 (rank 2), S19 (rank 3), S04 (rank 4), S30 (rank 5), S67 (rank 6), S62 (rank 7), S05 (rank 8).
- `re2tt_ts-travel-service_delay_3` (RE2-TT/delay): root rank 11; preceding candidates: S40 (rank 1), S07 (rank 2), S18 (rank 3), S42 (rank 4), S15 (rank 5), S34 (rank 6), S36 (rank 7), S24 (rank 8), S46 (rank 9), S59 (rank 10).

## What the misses demonstrate—and do not

The counts establish reproducible rank disagreements on this fixed development set.
They can motivate focused follow-up on where the ranking rules diverge, including
the lower BARO scores on these cases and the close signed/absolute variant comparison.
They do not establish that a leading non-root service was harmed, that a specific
root/victim confusion caused the miss, or that an LLM (or any other added component)
is necessary. The three repetitions per group are repeated observations of 12
scenario groups, not 36 independent conditions. No tuning or repairs were made.

Exact machine-readable rankings, group counts, paired Top-1/Top-3/MRR results,
and failure evidence are in `verification.json`.
