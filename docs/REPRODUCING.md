# Reproducing the reported calculations

The frozen original run is `code_only_final_20261016/analysis_v3_user_label144`. Its tables and labels are unchanged. Separate revision commands refit the annual sensitivity models and replay the completed 2018/2024 satellite pilot. See [the annual revision](REVISION_20261020.md) and [the completed pilot](REVISION_20261021.md) for their distinct scopes.

## Environment

The tested runtime is Python 3.12.0 on Windows with the pinned libraries in `code/requirements.txt`. Install `code/requirements-dev.txt` for tests. Node.js 24.15.0 was used for the optional dated-label JavaScript test. A virtual environment keeps these dependencies separate from other projects. Word and an Earth Engine login are unnecessary for the commands below.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r code/requirements-dev.txt
.venv\Scripts\python code/reproduce_reported_results.py --output reproduced/results
.venv\Scripts\python code/reproduce_revision.py --output reproduced/revision_results
.venv\Scripts\python code/reproduce_joint_pilot.py --output reproduced/joint_pilot
.venv\Scripts\python code/reproduce_figures.py --output reproduced/figures
.venv\Scripts\python -m pytest -q
node code/tests/test_dated_water_core.cjs
```

Use a fresh output directory each time. On Linux/macOS, use `.venv/bin/python` instead of `.venv\Scripts\python`. Numerical replay has been executed on the recorded Windows runtime; cross-platform pixel equality is not guaranteed because fonts and rendering libraries can differ.

## What is recalculated

The results command checks genuine code/data hashes, then compares 15 recalculated CSV tables with frozen references: annual endpoints and trends; climate coefficients, model status, fitted series and calendar validation; observation/processing controls; monthly and pooled Dynamic World threshold evidence; SPI history and calibration; radar endpoint regressions; nine recovery settings; weighted proxy comparisons with fixed-seed bootstrap intervals; and all 720 outcome counts. Every column, category and null location is compared, with relative numeric tolerance `1e-7` and absolute tolerance `1e-9`. Hashes are checked again after the run. The report is `REPRODUCTION_REPORT.json`.

The current figure command redraws Figures 3, 4, 5, 8 and 12 from the supplied revision tables and compares rendered RGB pixels with the delivered PNGs. Figure 8D includes the completed two-year pilot. The historical command `reproduce_figures_v020.py` instead redraws the original Figures 1, 3 and 5 against their historical reference images. Both write `FIGURE_REPLAY_REPORT.json`; neither redraws all twelve figures. Original plotting sources and all twelve delivered images remain available.

The table guards deliberately alter in-memory copies of genuine results to ensure a changed estimate, an omitted category or a missing accuracy value replaced with zero is rejected. These software tests do not establish scientific accuracy.

## Journal archive route

Extract all four `v0.2.0-review` supplementary ZIPs into the same empty directory. Each contains a shared `water_research_review_v0.2.0/` folder; allow those folders to merge. Run the same commands from that folder. No private manuscript archive or GitHub account is required. The Code archive contains the three reference PNGs used for pixel comparison. See `JOURNAL_BUNDLE_MANIFEST.json` and the archive-level checksum file supplied beside the ZIPs.

## What remains upstream

The commands start from real exported regional observations and frozen per-pixel comparison records. They do not rerun the 25-year raster aggregation or recalibrate all raw dated Sentinel-2 crops. The supplied `jrc_monthly_2000.tif` is a genuine raster required by the original grid audit, not a replacement for the full raster history. `spectral_screening_evidence.json` retains the original spectral evidence, while `pixel_month_comparisons.csv` is the input to statistical proxy comparison. This is computational replay from exported/aggregated observations, not independent classification validation.

Full raw-stage reconstruction requires the genuine source folders identified in the original manifests: `NW_Bangladesh_2000_2024`, `NW_Bangladesh_preprocessed`, `NW_Bangladesh_climate_baseline_1981_1999`, both radar–optical export directories, and dated raw crops/product XML. Original export and processing modules retain their author-workspace paths. The replay commands provide a portable route for the bounded calculations above; they do not make every legacy script a standalone CLI. The bulky historical `Reproducibility.zip` is retained in the authors' local project and earlier private Git history, rather than duplicated in the current working tree or clean journal archives.

Earth Engine scripts require an authenticated account and completed exports. Source-date, grid, mask and observation-density audits must pass before using fresh data. Missing observations remain missing. No satellite export or new source acquisition is initiated by the replay commands.
