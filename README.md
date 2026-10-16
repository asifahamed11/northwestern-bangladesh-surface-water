# Northwestern Bangladesh surface-water research

Code, derived results and manuscript for **Seasonal surface-water decline and limits to drought assessment in northwestern Bangladesh**.

This is a private research repository owned by Asif Ahamed. It is accessible only to authorized GitHub accounts. The repository has no public-access DOI, and storing these files does not establish independent validation or publication readiness.

## Contents

- `reproducibility/`: the byte-verified, extracted analysis archive. Python analysis modules, postprocessing and review tools, requirements, tests, frozen result tables, label-revision provenance and input/checksum manifests are retained.
- `reproducibility/code_only_final_20261016/analysis_v3_user_label144/`: the current frozen scientific run, including its Tables, Figures, RESULTS.json, STATUS.json and RUN_MANIFEST.json. Earlier diagnostic files remain historical provenance; they are not alternative final runs.
- `submission/`: the reviewed manuscript, compact supplementary methods, publication figures, 38 evidence CSVs, references and document-audit records. Read `submission/README.md` for the manuscript package contents.
- `REPOSITORY_MANIFEST.json`: file hashes for the extracted research archive and submission package.

## Reproduction

Start with `reproducibility/METHODS.md`, `reproducibility/code_only_final_20261016/README.md` and the recorded requirements. These describe the existing scientific pipeline and its source-data layout. Do not substitute the original draft or an earlier label version for the declared final run.

Large source rasters and dated satellite crops are not stored here. Source identifiers and hashes are retained; a full analysis rerun needs the genuine original inputs and the recorded environment. The archived download and audit scripts are historical project tools, not a promise of continued external service availability. The document-assembly scripts also refer to the authors' local source layout and Word environment. Opening the supplied Word documents and reading the frozen CSV results does not require rerunning the analysis.

## Interpretation

The primary annual analysis covers 2000–2021 on a retrospectively selected fixed observation footprint. The 2015–2024 radar–optical analysis uses a separate domain. Assisted dated-image comparison is proxy agreement, not independent ground-truth accuracy. Drought-recovery duration remains unidentified under the evaluated observation-support rules; missing duration is not evidence that water never returned. Climate-adjusted associations do not establish causal water-use effects.

Author contributions remain for the authors to complete. The manuscript has not been submitted through this repository workflow. This private deposit does not change repository access, invite collaborators, or grant an open-source license. Third-party datasets and publications retain their own terms and attribution requirements.
