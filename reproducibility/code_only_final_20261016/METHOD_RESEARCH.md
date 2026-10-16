# Method decision before the final computational analysis

This is a bounded methods scan, not a systematic review or a novelty assessment. Public primary sources and current official product documentation were searched before implementing the new analysis. Source metadata, access failures and claim locators are recorded in `research/`.

The selected route is an observation-uncertainty and product-sensitivity study. No extra manual reference campaign will be initiated under this instruction. Existing genuine human answers are preserved as assisted interpretation. Code-generated labels are explicitly product proxies.

1. **Reference quality and sampling:** Olofsson et al. (2014), sections 3.2-3.5 and 5.1, distinguish reference labeling from map comparison and require sampling-aware estimation. Use the entire frozen sampling frame, weights and unknown outcomes; do not turn selected clear cases into population accuracy. https://doi.org/10.1016/j.rse.2014.02.015
2. **Independence and imperfect references:** Stehman and Foody (2019), publisher abstract/highlights only, emphasize response design, probability sampling and imperfect reference data. This source was not reviewed in full. https://doi.org/10.1016/j.rse.2019.05.018
3. **Dependent optical evidence:** Brown et al. (2022), Methods, training-data collection and held-out annotation description, identify Dynamic World as Sentinel-2 model output. Our Sentinel-2 spectral rules and Dynamic World share optical input; their agreement is not an additional independent ground-truth vote. Global validation does not transfer a local accuracy number to our Bangladesh data. https://doi.org/10.1038/s41597-022-01307-4
4. **Current source discontinuities:** JRC's official data-access documentation states the 2016-2021 Seasonality/YearlyHistory correction and the 2022-2024 Landsat Collection 2 extension. It also warns about spatially variable co-registration offsets and unequal validation of updates. Keep the pre-2022 primary analysis and version sensitivity separate. https://global-surface-water.appspot.com/download
5. **Local relevance of divergence:** Saunders et al. (2025), Abstract and sections 2 and 5, study Bangladesh flood-insurance indices. They use divergence among evidence streams to reveal uncertainty. Their insurance estimands and outcomes differ from this study and are not imported here. https://doi.org/10.1029/2025EF005966
6. **Recent challenge paper:** Webb et al. (2026), *Discrepancies in Arctic-boreal lake area trends driven by sensitivity to dry conditions*, was found and its identifier/metadata checked. Publisher/PMC full-text retrieval was blocked. It is retained as a relevant recent reading candidate, not as reviewed evidence or proof about Bangladesh. https://doi.org/10.1038/s41598-026-35981-w

## Statistical choices

Report conditional product-label agreement together with the design-weighted assigned support. Keep all unassigned comparisons in an explicit binary-completion range; this is an algebraic range for completing the proxy comparison, not a physical-water accuracy interval. Use the original 24 strata in a pixel-month bootstrap. Repeated acquisition dates are never additional independent units. Sampling intervals do not include reference error, image timing, source-version mismatch or geolocation uncertainty.

Preserve all four probability thresholds, all districts/cohorts, null results and all nine recovery sensitivity specifications. No threshold is selected by the largest agreement. Do not add interpolation to manufacture recovery observations. Where no defensible duration is identifiable, report non-identifiability as a limitation and observation-design result.

The final report may support beginning Methods and Results writing in this narrower scope. Independent accuracy, causal attribution and recovery timing remain unsupported claims rather than new mandatory manual tasks.
