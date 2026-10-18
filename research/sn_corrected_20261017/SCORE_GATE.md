# Event scoring gate

**Result: PASS** — required suite passed in the specified training environment.

## Environment

Command:

```sh
/home/gnho1236/r2/.venv-eadro/bin/python -B -c 'import sys,numpy; print(sys.version); print(numpy.__version__)'
```

Actual output:

```text
3.8.20 (default, Oct  2 2024, 16:34:12)
[Clang 18.1.8 ]
1.21.5
```

This matches Python 3.8 and NumPy 1.21.5.

## Required test run

Command:

```sh
cd /home/gnho1236/r2/research/sn_corrected_20261017 && /home/gnho1236/r2/.venv-eadro/bin/python -B -m unittest -v test_scores
```

Actual output:

```text
test_adding_correct_normal_windows_changes_nothing (test_scores.EventMetricsTests) ... ok
test_bad_labels_and_event_ids_rejected (test_scores.EventMetricsTests) ... ok
test_bad_shapes_rejected (test_scores.EventMetricsTests) ... ok
test_events_have_equal_weight_not_windows (test_scores.EventMetricsTests) ... ok
test_extreme_logits_keep_uncapped_log_ranking (test_scores.EventMetricsTests) ... ok
test_extreme_logits_pool_without_probability_underflow (test_scores.EventMetricsTests) ... ok
test_float32_input_uses_float64_computation (test_scores.EventMetricsTests) ... ok
test_inconsistent_roots_rejected (test_scores.EventMetricsTests) ... ok
test_no_fault_events_rejected (test_scores.EventMetricsTests) ... ok
test_no_rounding_to_create_ties (test_scores.EventMetricsTests) ... ok
test_nonfinite_and_nonreal_logits_rejected_even_for_normals (test_scores.EventMetricsTests) ... ok
test_partial_tie_crossing_top_three_boundary (test_scores.EventMetricsTests) ... ok
test_probability_pooling_not_mean_logits_or_window_hits (test_scores.EventMetricsTests) ... ok
test_return_contract_and_no_input_mutation (test_scores.EventMetricsTests) ... ok
test_twelve_way_ties (test_scores.EventMetricsTests) ... ok
test_window_candidate_permutations_and_sorted_events (test_scores.EventMetricsTests) ... ok
test_constant_differences_and_one_sample (test_scores.PairedClusterBootstrapTests) ... ok
test_defaults_reproducibility_and_order (test_scores.PairedClusterBootstrapTests) ... ok
test_invalid_differences_and_recordings (test_scores.PairedClusterBootstrapTests) ... ok
test_invalid_samples_and_seed (test_scores.PairedClusterBootstrapTests) ... ok
test_matches_explicit_cluster_resampling_with_unequal_sizes (test_scores.PairedClusterBootstrapTests) ... ok
test_single_cluster_keeps_all_events (test_scores.PairedClusterBootstrapTests) ... ok

----------------------------------------------------------------------
Ran 22 tests in 0.302s

OK
```

**Exit code: 0.**

## Required scoring checks

- Event aggregation averages window probabilities (equivalently uses log-mean-exp of normalized log probabilities), not mean logits or window-hit accuracy.
- Normal windows are excluded from event root ranking.
- Exact 12-candidate ties yield expected Top-1 `1/12` and Top-3 `3/12` credit.
- Event NLL and ranking retain stable, uncapped log probabilities for extreme logits.
- Bootstrap resamples recording clusters with replacement while retaining event weighting and fixed predictions. Its four-cluster range is explicitly exploratory and conditional on shared training and the observed environment, not population-level significance evidence.

These are covered by the passing synthetic tests and match the frozen choices in `PLAN.md`. No concrete scoring failure was observed; no scoring source or test changes were made. LSP diagnostics reported “No diagnostics found” for both scoped Python files.

## Source hashes

SHA-256, captured after the test run:

```text
9dc141146b364c04d0502cd8c3005522edeaf22b3976b397e28096c54799670c  scores.py
efe65a9b0342a32282fd43f8996002809e33afe2c66fdca627cbfaaeca36680f  test_scores.py
```

No real data, models, downloads, package installs, or commits were used. The supplied workspace paths are not inside a Git repository, so Git status could not be obtained.
