# Surface-water change in northwestern Bangladesh

Research materials for *Mapped seasonal surface water decline under changing observation support in northwestern Bangladesh*.

[Paper](manuscript/manuscript.pdf) · [Word manuscript](manuscript/manuscript.docx) · [Revision results](data/revision/tables) | [Revision guide](docs/REVISION_20261020.md) · [Reproduction guide](docs/REPRODUCING.md) · [Review downloads](https://github.com/asifahamed11/northwestern-bangladesh-surface-water/releases/tag/v0.2.0-review)

<img src="figures/Figure_01_study_area_and_design.png" alt="Study districts in northwestern Bangladesh and the three analysis domains" width="900">

The study examines seasonal and permanent surface-water classes in Naogaon, Chapainawabganj and Rajshahi. The primary annual comparison covers 2000–2021 on a fixed observed footprint of 1,276.41 km². A separate 2015–2024 radar–optical analysis examines how confidence thresholds change the area available for comparison. Dated image interpretation covers 720 sampled pixel-months in four selected months.

## Run the reported calculations

Use Python 3.12. From this folder:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r code/requirements-dev.txt
.venv\Scripts\python code/reproduce_revision.py --output reproduced/revision_results
.venv\Scripts\python code/reproduce_reported_results.py --output reproduced/results
.venv\Scripts\python code/reproduce_figures.py --output reproduced/figures
.venv\Scripts\python -m pytest -q
```

The revision command refits the declared annual sensitivities from genuine derived inputs and checks eleven tables. The figure command redraws Figures 3, 4, 5, 8 and 12 and compares their pixels with the delivered versions. The older result command retains the original fifteen-table replay. All write to new folders. Full raw-pixel aggregation and pending exports are separate upstream work; see the [revision guide](docs/REVISION_20261020.md).

## Find a file

| Folder | Contents |
| :-- | :-- |
| [manuscript](manuscript) | Current author-review manuscript and compact supplementary methods, in Word and PDF |
| [data/revision](data/revision) | Frozen protocols, new result tables and audited completed batch downloads |
| [data/tables](data/tables) | 18 main-result CSVs and 20 extended diagnostic CSVs |
| [data/inputs](data/inputs) | Genuine climate summaries, 26 exported CSVs, dated evidence and two required rasters |
| [data/boundaries](data/boundaries) | Study boundary, losslessly compressed national context and source metadata |
| [figures](figures) | All 12 figures, with PNG previews and 320 dpi RGB TIFFs |
| [code](code) | Portable replay commands, original analysis modules, export scripts and tests |
| [provenance](provenance) | Input hashes, final run records, label revision and replay checks |

Open [primary_endpoint_changes.csv](data/tables/primary_endpoint_changes.csv) for the annual endpoints, [proxy_agreement_and_unknown_ranges.csv](data/tables/proxy_agreement_and_unknown_ranges.csv) for conditional agreement and unresolved labels, and [exploratory_recovery_support_sensitivity.csv](data/tables/exploratory_recovery_support_sensitivity.csv) for recovery support failures. The [data dictionary](docs/DATA_DICTIONARY.md) describes units, missing values and table schemas.

## Interpretation and review access

Climate-adjusted coefficients describe associations. Assisted image comparison measures proxy agreement; independent classification accuracy remains unmeasured. Recovery duration could not be estimated under the evaluated support rules. A missing duration does not mean that water failed to return.

The October 20 revision adds cohort/window comparisons, simpler models, matched-fold benchmarks, static river/cropland context and synthetic detectability checks. The original endpoint decline is 25.42%; the five-year-mean comparison on the same footprint is 14.70%. These are different summaries. The repository remains private. The original **v0.2.0-review** release is preserved as a historical version and does not reproduce the new figures/models by itself. No journal submission has been made.

The manuscript is an author-review draft. Author contributions and all-author approval remain for the authors to complete. [Reuse and source-license notes](docs/REUSE_AND_ACCESS.md) distinguish author materials from third-party products.

The [journal repository review](docs/JOURNAL_REPOSITORY_REVIEW.md) records the policy findings and fixes. [Recorded replay checks](provenance/replay_audit) include the actual extracted-archive test and unchanged scientific-file hashes.
