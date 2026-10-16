# Surface-water change in northwestern Bangladesh

Research materials for *Seasonal surface-water decline and limits to drought assessment in northwestern Bangladesh*.

[Read the paper](manuscript/manuscript.pdf) · [Download Word](manuscript/manuscript.docx) · [Result tables](data/tables) · [Analysis code](code) · [Reproduction notes](docs/REPRODUCING.md)

<img src="figures/Figure_01_study_area_and_design.png" alt="Study districts in northwestern Bangladesh and the three analysis domains" width="900">

The study follows seasonal and permanent surface-water classes in Naogaon, Chapainawabganj and Rajshahi. The main annual comparison covers 2000–2021 on a fixed observed footprint of 1,276.41 km². A separate 2015–2024 radar–optical analysis examines how confidence thresholds change the area available for comparison. Dated image interpretation covers 720 sampled pixel-months in four selected months.

## Find a file

| Folder | Contents |
| :-- | :-- |
| [manuscript](manuscript) | Current paper and compact supplementary methods, in Word and PDF |
| [data/tables](data/tables) | 18 main-result CSVs and 20 extended diagnostic CSVs |
| [figures](figures) | All 12 numbered figures, with PNG previews and 320 dpi RGB TIFFs |
| [code](code) | Analysis modules, export scripts, figure source code and selected tests |
| [provenance](provenance) | Final run records, source hashes, label-revision record and original reproducibility snapshot |

Start with the [paper](manuscript/manuscript.pdf). To inspect the main annual results, open [annual_common_support_water.csv](data/tables/annual_common_support_water.csv) and [primary_endpoint_changes.csv](data/tables/primary_endpoint_changes.csv). The [proxy comparison table](data/tables/proxy_agreement_and_unknown_ranges.csv) retains unresolved labels. The [recovery support table](data/tables/exploratory_recovery_support_sensitivity.csv) records why recovery durations could not be identified.

## Using the results

Seasonal source-class area declined within the retained observation footprint. Climate-adjusted coefficients describe associations. Assisted image comparison measures proxy agreement; independent classification accuracy remains unmeasured. Recovery duration could not be estimated under the evaluated support rules, so a missing duration should not be read as a failure of water to return.

Large source rasters and dated satellite crops are referenced by manifests and are not duplicated here. See [data sources](docs/DATA_SOURCES.md) and [reproduction notes](docs/REPRODUCING.md) before running the analysis. The code retains the source project's directory names; some steps require its original inputs and folder layout.

This repository is private. Access is limited to authorized GitHub accounts. The manuscript is an author-review draft; its author-contribution section remains for the authors to complete. Third-party data retain their source licenses.
