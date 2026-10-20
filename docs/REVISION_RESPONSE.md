# Review revision status

This author-review revision addresses the seven requested workstreams with measured results or explicit evidence limits. It does not establish independent accuracy, measured drought recovery or causal water-use attribution. Original labels and the original manuscript remain unchanged.

| Workstream | Evidence and revision | Status |
| :-- | :-- | :-- |
| 1 Observation quality | Fifty source rasters checked; seven overlapping water/validity cohorts; identical calendar-month support | Computed; only November passes the union 20% retention gate, so complete annual hydroperiod control remains unavailable |
| 2 Endpoint sensitivity | One/three/five-year windows and whole-series fits | Computed; seasonal endpoint -25.42%, original-footprint five-year -14.70%, baseline-complete five-year -18.79% |
| 3 Climate models | Simpler monsoon/antecedent models, HAC lags 0/2, block lengths 2/3/4, all leave-one-year-out fits and matched-fold hindcasts | Computed; short-series and selection limits retained; constant-step folds rejected |
| 4 Sensor comparison | Wet-season support, assisted positive/negative class agreement, bounded score-stage probes, genuine 2018 Q1 joint-cell audit | Partial batch pilot: Q1 matches 35 original area columns within 6.83e-13 km2; seven other quarter exports are still queued |
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

## Remaining work

The seven queued exports must complete and their downloaded joint cells must pass the same partition/source reconciliation as Q1. No result from a queued task is reported. The paper's actual recovery and independent-accuracy limits cannot be removed by formatting, automation or simulated data. Authors still control source verification, contributions, disclosure, final approval and submission. No journal submission or public repository exposure has occurred.
