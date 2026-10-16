# Journal repository review

Reviewed 16 October 2026 for Frontiers in Earth Science, Hydrosphere, Original Research, Research Topic 83484. This is a focused repository/access review, not a new literature or independent scientific review. Exact official source URLs and reviewed headings are in `provenance/journal_policy_sources.json`.

## Policy findings

Frontiers requires accessible supporting data and an accurate availability statement; it strongly encourages sharing statistical code. Its Earth Science guide accepts ZIP supplementary data and describes publication of supplementary files through Figshare. The general submission guide lists a 30 MB additional-file limit. These policies support supplying reviewer code/data archives alongside the paper. They do not prescribe this folder layout or establish a blanket MIT-license or GitHub-DOI requirement for this Original Research article.

Sources: [data and code policy](https://www.frontiersin.org/guidelines/policies-and-publication-ethics), [supplementary-material guidance](https://www.frontiersin.org/journals/earth-science/for-authors/author-guidelines), [file upload guide](https://www.frontiersin.org/for-authors/submitting-research/how-to-submit-an-article-to-our-journals).

## Findings and corrections

| Finding in the first repository | Correction | Evidence / remaining boundary |
| :-- | :-- | :-- |
| Some real calculation inputs were absent | Added genuine climate summaries, all 26 required CSV exports, pilot, real reference-grid raster and transition raster | SHA-256 input manifest; no dummy data or new downloads |
| Legacy scripts depended on author-local folders | Added portable commands which call the original functions in a fresh temporary layout | 15 result-table comparisons, including nulls; original scientific modules retained |
| Figure 1 national context was referenced but omitted | Added the original national boundary using lossless gzip and verified its uncompressed hash | Three selected figures replayed; not a claim that all 12 were replotted |
| Missing data and measurement scopes were easy to misread | Added table schemas, cohort/missing-value rules and file-to-display map | Null accuracy and recovery estimates retained |
| Private GitHub alone did not establish reviewer access | Prepared clean code/data supplementary ZIPs which merge into one runnable folder | These files still need actual journal upload; GitHub remains private |
| A moving main branch lacked a clear review version | Added versioned citation metadata, input/output hashes and a review release | The release is private, has no DOI and is not publication |
| Original provenance archive duplicated development history | Removed it from the current working tree; preserved the local archive and earlier private Git history; excluded manuscript backups from the journal archives | Clean archive allowlist and checksum receipts |
| Rights were not clear | Documented third-party source rights and the unresolved author-code license decision | No unrequested copyright grant |

## Assurance boundary

The replay establishes computational consistency from genuine exported/aggregated inputs and frozen per-pixel comparison records. It does not independently validate physical water labels, repeat all source-pixel aggregation, establish drought-recovery duration or identify causal water-use effects. The supplied raw-grid raster is a required real audit input, not a complete raw raster history.

The initial replay attempt stopped because the original export audit required that genuine grid raster. It was added, and the full replay then passed. This technical retry is disclosed in the audit; it is not independent replication. No result was selected because it became more favorable.

## Items retained for the authors

Upload the exact supplementary files with the manuscript and confirm their portal names match the availability statement. Complete author contributions, obtain all-author approval and retain the existing AI-use/editor-conflict declarations. If a publicly reusable code release is desired, agree a code license and a clean public release separately. A DOI archive is useful but has not been created or claimed. [GitHub's Zenodo integration](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content) requires a public repository; changing this private repository is an author decision.

Repository corrections do not establish journal acceptance or remove the scientific limitations already reported in the paper.
