# Post-build checks

27 PASS / 0 FAIL

| result | check | detail |
|---|---|---|
| PASS | `raw.sha256_unchanged` | 13459 raw files verified; 0 mismatched/missing |
| PASS | `hourly.unique_timestamps` |  |
| PASS | `hourly.regular_1h_grid` |  |
| PASS | `hourly.local_date_matches_tz` |  |
| PASS | `hourly.no_sentinel_or_error_in_qc` |  |
| PASS | `hourly.contaminated_window_voided` |  |
| PASS | `daily.unique_dates` |  |
| PASS | `daily.contiguous` |  |
| PASS | `daily.n_hours_le_24` |  |
| PASS | `daily.target_nan_when_incomplete` |  |
| PASS | `daily.dangerous_rule_epa_trunc` |  |
| PASS | `features.issue_unique_increasing` |  |
| PASS | `features.target_is_issue_plus_h` |  |
| PASS | `features.target_not_imputed_equals_daily` |  |
| PASS | `features.pm_lag1_is_issue_day` |  |
| PASS | `leakage.features_use_only_past` | 25 random issue days recomputed with all data after D removed; 0 differ [] |
| PASS | `splits.train_before_validation_with_embargo` | last train target 2021-06-30, first validation target 2021-07-15, gap 14 d |
| PASS | `splits.train_validation_no_shared_rows` |  |
| PASS | `splits.validation_before_test_with_embargo` | last validation target 2022-06-30, first test target 2022-07-15, gap 14 d |
| PASS | `splits.validation_test_no_shared_rows` |  |
| PASS | `splits.no_target_in_contaminated_window` |  |
| PASS | `splits.train_targets_all_valid` | 565 rows |
| PASS | `splits.validation_targets_all_valid` | 267 rows |
| PASS | `splits.test_targets_all_valid` | 190 rows |
| PASS | `preprocess.medians_from_train` | 79 columns |
| PASS | `preprocess.train_standardised` |  |
| PASS | `preprocess.no_nan_in_model_matrices` |  |
