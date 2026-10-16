# Reproducing the analysis

The reported results come from `code_only_final_20261016/analysis_v3_user_label144` in the original project. Its final run record, source hashes and results are in `provenance/`. The CSVs in `data/tables/` are unchanged copies of the paper's accompanying tables.

## Read the supplied results

The Word and PDF files open without a Python environment. CSV files can be read in Python, R or a spreadsheet application. Figures are supplied as PNG previews and RGB 320 dpi TIFFs. Table manifests record the original file hashes and sources.

## Code layout

| Path | Purpose |
| :-- | :-- |
| `code/research_pipeline/` | Spatial support, annual and monthly models, SPI, event recovery and validation routines |
| `code/automatic_water/analyze_dw_sensitivity.py` | Dynamic World threshold and paired-support analysis |
| `code/postprocessing/annual_quality_sensitivity.py` | Annual observation-effort and processing-boundary sensitivity |
| `code/postprocessing/finalize_code_only_research.py` | Final result reconciliation and design-weighted dated-proxy comparisons |
| `code/postprocessing/screen_water_colors.py` | Raw-band spectral triage and explicit undecided outcomes |
| `code/postprocessing/dated_water_core.js` | Dated-label import, validation and summary logic |
| `code/earth_engine/` | Core, baseline and radar–optical export scripts |
| `code/figure_sources/` | Original publication-figure scripts; retain the original manuscript-workspace paths |

Source code is copied without changing its numerical methods. The original requirements are retained in `code/requirements.txt` and `code/requirements-dev.txt`. Dated-crop tools also use Pillow, requests and Node.js. Figure/document scripts were run in the authors' recorded local plotting and Word environments; they are not a standalone cross-platform document builder.

## Rerun requirements

A complete rerun needs the genuine source folders listed in Supplementary Methods: `NW_Bangladesh_2000_2024`, `NW_Bangladesh_preprocessed`, `NW_Bangladesh_climate_baseline_1981_1999`, `NW_Bangladesh_automatic_water_2015_2024`, `NW_Bangladesh_DW_sensitivity_2015_2024`, and the dated crop/metadata folders. The archived run manifests record the remaining review and intermediate-input paths. These folders are not replaced with sample data.

For an exact reconstruction, extract `provenance/Reproducibility.zip` into a separate copy of the original source-data workspace. It preserves the original file names and the corrected dated-label CSV and backup. Its active-run README gives the finalization command. Choose a new output directory; existing completed runs must be retained.

The export scripts require an authenticated Earth Engine account. Downloaded files must pass the source-date, grid, mask and checksum audits before use. No new downloads or scientific model runs were performed when this repository was assembled.

## Checks

The retained tests cover model statistics, drought calculations and dated-label rules. Run Python tests from `code/` with `python -m pytest tests -q` after installing the recorded dependencies. The dated-label JavaScript test is `node tests/test_dated_water_core.cjs`. Software checks are distinct from independent scientific validation.

The manuscript reports the study's scope and limitations. Automated satellite agreement, software checks and complete file inventories do not supply independent ground truth.
