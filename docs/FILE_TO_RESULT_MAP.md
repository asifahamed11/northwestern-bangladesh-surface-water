# Files behind the manuscript displays

Paths below are relative to the repository. Tables are unchanged observations/results; figure captions and source hashes are in `provenance/figure_manifest.json`. This map distinguishes a supplied plotting source from a portable redraw actually checked.

| Display | Evidence input | Relevant code / replay status |
| :-- | :-- | :-- |
| Table 1 | `docs/DATA_SOURCES.md`, source manifests, `data/boundaries/source_metadata.json` | Source roles, periods and cohort definitions; no new statistical calculation |
| Table 2 | `data/tables/primary_endpoint_changes.csv`, annual climate and observation-sensitivity CSVs | `research_pipeline/models.py`, `postprocessing/annual_quality_sensitivity.py`; statistical replay |
| Table 3A/B | `reference_outcome_accounting.csv`, `proxy_agreement_and_unknown_ranges.csv` | `postprocessing/finalize_code_only_research.py`; statistical replay |
| Figure 1 | Study and national boundary GeoJSONs | `figure_sources/redesign_figure1.py`; portable redraw and exact-pixel check |
| Figure 2 | `annual_common_support_water.csv`, `annual_observation_quality.csv` | `figure_sources/prepare_artifacts.py`; delivered image and original plotting source |
| Figure 3 | `data/inputs/annual_transition_primary_pre2022.tif` | `figure_sources/redraw_promoted.py`; portable redraw and exact-pixel check |
| Figure 4 | `annual_observation_effort_climate_sensitivity.csv` | `figure_sources/prepare_artifacts.py`; delivered image and original plotting source |
| Figure 5 | `Extended_Diagnostics/annual_jrc/annual_class_climate_adjusted.csv` | `figure_sources/redraw_promoted.py`; portable redraw and exact-pixel check |
| Figure 6 | `dw_threshold_support_and_agreement.csv` | `figure_sources/prepare_artifacts.py`; delivered image; pooled input table replay |
| Figure 7 | `Extended_Diagnostics/radar/dw_monthly_threshold_evidence.csv` | `automatic_water/analyze_dw_sensitivity.py`; delivered image; monthly threshold table replay |
| Figure 8 | `exploratory_climate_envelope_models.csv` | `automatic_water/finalize_sensitivity_results.py`; delivered image; endpoint-regression table replay |
| Figure 9 | `proxy_agreement_and_unknown_ranges.csv`, `reference_outcome_accounting.csv` | `figure_sources/prepare_artifacts.py`; delivered image; comparison/outcome table replay |

