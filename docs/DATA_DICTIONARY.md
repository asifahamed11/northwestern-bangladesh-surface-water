# Data dictionary

`table_schema.json` inventories all 38 unchanged result CSVs, their row counts, fields, parsed types, missing counts and SHA-256 hashes. It describes the delivered files, not an inferred raw-data standard.

## Domains and missing values

The annual primary domain is the fixed 1,276.41 km² observed cohort in 2000–2021. Districts and the union overlap and must not be summed as independent replicates. Radar–optical comparisons use a separate 2015–2024 historical ever-water cohort. The 720 pixel-months span four selected months and are not a random sample of every month in 25 years. Scene-level observations repeat pixel-month locations; use `sample_id` plus `scene_id` for scene joins. Do not merge records by display order.

Empty CSV cells / NaN denote unresolved, missing or inapplicable quantities. They are not zeros, dry observations or failures of water to return. Refer to the adjacent `status`, support and failure columns. Physical independent-accuracy fields and unidentified recovery durations intentionally remain missing. `is_independent_accuracy` remains false. Rates named agreement describe conditional proxy agreement; retained support and unassigned outcomes must accompany them.

Annual/monthly JRC class codes must be interpreted in their corresponding product: annual 0=no data, 1=not water, 2=seasonal, 3=permanent; monthly 0=no data, 1=not water, 2=water. Binary 0/1 proxy fields have their documented binary meaning and are not the annual source codes. A class map is not an observed-water depth or storage measurement.

Names ending `_km2` are square kilometres; `_pct` is percent; explicit `fraction` quantities are unitless fractions. `design_weight_km2_month` is area-time weight. Calendar `period` is YYYY-MM and `year`/`month` identify genuine provider dates; review/revision timestamps are provenance, not acquisition dates. Climate input rainfall/evaporation fields ending `_mm` are millimetres. Model slopes, standardized covariates, HAC intervals and bootstrap quantities must be interpreted using the documented model transformation and denominator; their units are not guessed from numeric magnitudes.

## Supplied inputs

`monthly_climate.csv`: 1,200 region-month rows for 2000–2024; `baseline_climate_1981_1999.csv`: 912 rows for the preceding 19 years. Four reporting regions include the overlapping union. Twenty-six original Earth Engine CSV exports and the frozen threshold pilot are retained byte-for-byte. `reference_sample_plan.json` and `spectral_screening_evidence.json` preserve the original sampling/spectral evidence. The dated statistical replay starts from `pixel_month_comparisons.csv`; it does not reconstruct all scene crop calibration.

The two genuine TIFFs are a reference JRC monthly raster for the native-grid audit and the frozen annual transition map. They are not the complete 2000–2024 raw raster collection. Boundaries retain original coordinates; the national context file is gzip-compressed without geometry alteration. Exact source lineage is in `provenance/REPLAY_INPUTS.json` and source/run manifests.

## Table index

| CSV | Rows | Fields |
| :-- | --: | --: |
| `actual_dated_observations.csv` | 3022 | 12 |
| `annual_climate_model_coefficients.csv` | 88 | 8 |
| `annual_common_support_water.csv` | 100 | 9 |
| `annual_observation_effort_climate_sensitivity.csv` | 24 | 17 |
| `annual_observation_quality.csv` | 100 | 9 |
| `annual_predictive_validation_summary.csv` | 8 | 6 |
| `annual_trend_results.csv` | 24 | 12 |
| `common_support_quality.csv` | 36 | 10 |
| `dw_threshold_support_and_agreement.csv` | 48 | 11 |
| `exploratory_climate_envelope_models.csv` | 24 | 11 |
| `exploratory_recovery_support_sensitivity.csv` | 972 | 15 |
| `Extended_Diagnostics/annual_jrc/annual_calendar_cross_validation.csv` | 32 | 9 |
| `Extended_Diagnostics/annual_jrc/annual_class_climate_adjusted.csv` | 376 | 9 |
| `Extended_Diagnostics/annual_jrc/annual_climate_model_status.csv` | 16 | 10 |
| `Extended_Diagnostics/annual_jrc/annual_transition_areas.csv` | 40 | 3 |
| `Extended_Diagnostics/annual_jrc/calendar_block_cross_validation.csv` | 80 | 13 |
| `Extended_Diagnostics/annual_jrc/climate_adjusted_water.csv` | 3466 | 11 |
| `Extended_Diagnostics/annual_jrc/drought_recovery_events.csv` | 297 | 11 |
| `Extended_Diagnostics/annual_jrc/drought_recovery_identifiability.csv` | 24 | 4 |
| `Extended_Diagnostics/annual_jrc/monthly_common_support_water.csv` | 10800 | 15 |
| `Extended_Diagnostics/annual_jrc/monthly_model_coefficients.csv` | 300 | 10 |
| `Extended_Diagnostics/annual_jrc/monthly_model_status.csv` | 72 | 6 |
| `Extended_Diagnostics/annual_jrc/recovery_calendar_reference_sample_sensitivity.csv` | 3 | 3 |
| `Extended_Diagnostics/annual_jrc/recovery_coverage_sensitivity_status.csv` | 6 | 4 |
| `Extended_Diagnostics/annual_jrc/recovery_failure_components.csv` | 297 | 6 |
| `Extended_Diagnostics/annual_jrc/spi_calibration_parameters.csv` | 96 | 8 |
| `Extended_Diagnostics/annual_jrc/spi_indices.csv` | 2400 | 6 |
| `Extended_Diagnostics/radar/downloaded_sensitivity_settings.csv` | 1 | 27 |
| `Extended_Diagnostics/radar/dw_monthly_threshold_evidence.csv` | 5760 | 24 |
| `Extended_Diagnostics/radar/spi_calibration_parameters.csv` | 96 | 8 |
| `Extended_Diagnostics/radar/spi_indices.csv` | 2400 | 4 |
| `monthly_predictive_validation_summary.csv` | 12 | 6 |
| `pixel_month_comparisons.csv` | 720 | 16 |
| `primary_endpoint_changes.csv` | 8 | 7 |
| `proxy_agreement_and_unknown_ranges.csv` | 88 | 26 |
| `radar_automated_recovery_intervals.csv` | 108 | 13 |
| `radar_seasonal_reference_support.csv` | 144 | 6 |
| `reference_outcome_accounting.csv` | 5 | 4 |
