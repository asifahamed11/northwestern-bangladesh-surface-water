# Review revision status after satellite pilot completion

This author-review revision addresses the seven requested workstreams with measured results or explicit evidence limits. It does not establish independent accuracy, measured drought recovery or causal water-use attribution. Original labels and the original manuscript remain unchanged.

| Workstream | Evidence and revision | Status |
| :-- | :-- | :-- |
| 1 Observation quality | Fifty source rasters checked; seven overlapping water/validity cohorts; identical calendar-month support | Computed; only November passes the union 20% retention gate, so complete annual hydroperiod control remains unavailable |
| 2 Endpoint sensitivity | One/three/five-year windows and whole-series fits | Computed; seasonal endpoint -25.42%, original-footprint five-year -14.70%, baseline-complete five-year -18.79% |
| 3 Climate models | Simpler monsoon/antecedent models, HAC lags 0/2, block lengths 2/3/4, all leave-one-year-out fits and matched-fold hindcasts | Computed; short-series and selection limits retained; constant-step folds rejected |
| 4 Sensor comparison | Ten-year support/score audit and completed 2018/2024 pilot: all eight quarter CSVs, four directional joint cells per pair/threshold, 288 rows | Completed and reconciled; 0.7 selects almost entirely water, with lower nonwater agreement; independent accuracy remains unmeasured |
| 5 Drought recovery | Actual failures retained at nine settings; 25,920 synthetic scenarios preserving real gaps and widths | Diagnostic completed; actual recovery remains unidentified and no tested positive pulse was confirmed |
| 6 Independent accuracy | External human-reference discovery and eligibility/access audit | Unresolved: blocked download and no acquired eligible independent local labels; existing assisted labels not renamed as truth |
| 7 Hydrological context | Actual HydroRIVERS Asia v1 and ESA WorldCover 2020 v100; 200/500/1,000 m river buffers and static cropland groups | Static context completed; local gauge/groundwater drivers unmeasured, no causal interpretation |

## Manuscript changes

The title now matches mapped seasonal decline under changing observation support. Methods explicitly define seven cohorts, simpler models, approximate uncertainty, chronological test folds, static landscape context and simulations. Results retain the original endpoint numbers while adding multi-year alternatives. Five figures (3, 4, 5, 8, 12) were replaced; all twelve figures and three tables remain inline. Twenty-two references, every numbered figure/table and all four displayed equations have in-text calls. Native math, original notes and all Tables 2/3 values are retained. The 27-page Word document and one-page supplement were rendered with native Word and inspected. Contributions remain blank by request.

## Verification actually run

- Original annual extraction reproduced within 1e-6 km2, with all fifty source-raster hashes checked.
- 856 computational/document assertions passed; an alternative statsmodels implementation checked OLS/HAC coefficients and standard errors on the real inputs.
- Existing repository tests: 53 passed.
- Portable revision replay: eleven tables matched at the declared tolerances.
- Five revision figures redrew with identical rendered pixels.
- New reference identities matched exact Crossref/DataCite records; all twenty-two in-text author/year calls and bibliography entries were accounted for. This is not full-text or accountable-author verification of every source.

An initial bootstrap implementation compressed calendar gaps and had a scope-key collision. Those outputs were withdrawn, the implementation corrected, and the analysis rerun. Failed access, duplicate batch submissions, rejected fits and unavailable results remain in provenance. Technical replay is not independent environmental validation.

## Completed batch pilot on 21 October

All seven formerly queued jobs were observed as Completed in the authenticated Task Manager. Individual CSV downloads succeeded after a canceled bulk archive and a browser loop timeout; no duplicate export was submitted. Together with the previously audited Q1 file, all eight quarters provide 288 unique region/cohort/month rows for 2018 and 2024. Original 35 area columns and source metadata reconciled; joint-cell sums and diagonals match the original pair/agreement areas. Only one of the earlier three Q1 copies is counted.

The union historical-water pilot shows SAR–Dynamic World pooled agreement of 88.92% at 0.5 and 99.45% at 0.7 on 12.91% and 3.34% paired area-time. At 0.7, water agreement is 99.72% but nonwater agreement 72.14%; Dynamic World classifies 99.29% of the paired area as water. Dynamic World–JRC water/nonwater agreement is 99.01%/42.02% at 0.7 on 3.89% support. Threshold 0.8 has no pairs. These two-year product comparisons do not measure independent accuracy or establish ten-year class-specific accuracy. All cohorts, thresholds, seasons and disagreement cells are retained.

Figure 8D, the methods, results, discussion and abstract now include that evidence. Three original tables, all 28 native math objects and original notes remain intact. The main text is 8,309 words under the existing counting rule; the final Word manuscript has 27 pages and the shortened supplement one page. All pages were inspected. The original annual tables, original dated labels, October 20 delivery and historical v0.2.0 release are preserved.

## Remaining limits

The batch-pilot task is complete. Independent local truth and a continuous interpretable drought-recovery sequence were not added by these exports. Neither independent physical-water accuracy nor actual recovery duration can be reported. Authors retain responsibility for source verification, contributions, final approval and any eventual submission. No journal submission, public exposure or new reuse license was made.
