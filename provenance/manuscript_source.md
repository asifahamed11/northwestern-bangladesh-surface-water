---
lang: en-US
---

# Seasonal surface-water decline and limits to drought assessment in northwestern Bangladesh

Asif Ahamed^1^, Md. Tanvir Hasan^1^, Most. Alisa Tabassum^1^, Ahammad Hossain^1^*, Md. Kamruzzaman^2^, Jayanta Das^3^ and A.H.M. Rahmatullah Imon^4^

^1^ Department of Computer Science & Engineering, Varendra University, Bangladesh

^2^ Institute of Bangladesh Studies, University of Rajshahi, Bangladesh

^3^ Department of Geography, Rampurhat College, West Bengal, India

^4^ Center for Interdisciplinary Research (CIR), Varendra University, Bangladesh

*Correspondence: Ahammad Hossain; ahammadstatru@gmail.com

Article type: Original Research | Running title: Surface water and observation uncertainty

Main text: {{WORD_COUNT}} words | Figures: 12 | Tables: 3

## Abstract

Surface-water monitoring can inform climate-resilient water management only when changes in mapped water are distinguished from changes in observation support. We assessed annual seasonal and permanent surface-water source classes in Naogaon, Chapainawabganj and Rajshahi, northwestern Bangladesh, using Joint Research Centre water histories and gridded climate data. The primary analysis covered 2000–2021 on a fixed, retrospectively selected, annually observed footprint of 1,276.41 km²; 2000–2024 results were retained as a source-version sensitivity. Separate 2015–2024 Sentinel-1 and Dynamic World analyses examined threshold sensitivity, paired support and drought-recovery identifiability. A stratified four-month comparison retained all 720 sampled pixel-months, including unresolved references. Seasonal source-class area declined from 938.53 to 699.91 km² between 2000 and 2021, a decrease of 25.42%. Negative seasonal time coefficients persisted in Naogaon and Rajshahi after adjustment for annual climate, observation effort and a 2016 processing-boundary indicator, whereas the corresponding Chapainawabganj interval included zero. Permanent source-class area increased by 41.04% between the endpoints, but its adjusted time-coefficient intervals included zero after the processing-boundary control. Increasing the Dynamic World confidence threshold from 0.5 to 0.7 raised conditional radar–optical agreement from 89.04% to 98.71%, while mean paired support fell from 11.07% to 3.29% of the separate analysis footprint. Assisted dated interpretation assigned comparison labels to 76.54% of design-weighted sampled area-time; conditional agreement was 98.56%, without establishing independent accuracy. Recovery duration remained unidentified in all nine support/reference specifications. These results support targeted investigation of declining seasonal water in the retained footprint and show why agreement, spatial support and temporal continuity should be reported together before using satellite products to assess drought resilience. The analysis does not estimate district-wide water storage, validate annual hydroperiod classes independently or attribute residual changes to groundwater abstraction.

Keywords: seasonal surface water; climate adjustment; observation support; drought monitoring; remote sensing uncertainty; Barind Tract; Bangladesh

## 1 Introduction

Seasonal surface water connects rainfall variability with the timing and location of usable water. For water managers, a contraction in mapped seasonal water can indicate a place requiring investigation, but its interpretation depends on what the satellite actually observed. A water map summarizes a classification process, a spatial footprint and a set of acquisition dates. Changes in any of these can affect the apparent hydrological signal. The Landsat-based Global Surface Water record provides a consistent framework for examining long-term water occurrence and annual source classes [@Pekel2016]. Its application to local water-management questions nevertheless requires attention to missing observations, class definitions and updates to the underlying archive.

These concerns are relevant to northwestern Bangladesh. The Barind region has pronounced seasonal water stress and substantial dependence on groundwater-supported agriculture. Recent station-based research documented spatially heterogeneous rainfall trends across Naogaon, Chapainawabganj and Rajshahi during 2000–2024 [@Rainfall2026]. Work in the high Barind has also examined heatwaves, rainfall, vegetation, soil moisture and groundwater jointly [@Barind2025]. These studies motivate a surface-water assessment that retains local differences and distinguishes measured water classifications from possible climatic and management mechanisms. Administrative districts provide reporting units for such an assessment, although their boundaries do not define hydrological catchments.

Existing evidence also cautions against assuming one direction of surface-water change throughout Bangladesh. In the southwestern Bengal delta, a Landsat time-series study examined strong seasonality and reported expansion in mapped surface water alongside changing local water management [@Huda2021]. Those findings concern another region and observation design. They cannot establish the trajectory of seasonal water in the northwest, but they show why the period, water class and spatial domain of a trend need to be explicit. At the much larger Indus–Ganges–Brahmaputra scale, hydrological modeling has separated the components contributing to total water-storage change [@Girotto2025]. Surface-water class area alone does not provide that decomposition.

Combining sensors offers additional evidence, but agreement between products is conditional on where both can assign labels. Dynamic World provides Sentinel-2-derived land-cover probabilities at 10 m [@Brown2022]. Radar can supply observations under cloud conditions that restrict optical mapping, while remaining sensitive to vegetation, surface roughness and the water-detection method. A multi-site comparison of Sentinel-1 and Sentinel-2 explicitly separated open and vegetated water and evaluated both against higher-resolution imagery [@Vanderhoof2023]. In Senegal, field, satellite and modeled pond observations revealed both the value and the limitations of remotely sensed water availability [@Slinski2025]. These examples support reporting complementary evidence without treating another satellite product as error-free truth. Research on index-based flood insurance in Bangladesh further shows that data choice can affect the timing and uncertainty of water-related decisions [@Saunders2025].

Drought resilience introduces a stricter temporal requirement. A rainfall deficit can propagate through water stores with delays and persistence, so the end of meteorological drought need not coincide with hydrological recovery [@VanLoon2015]. Estimating a recovery duration requires observations before, during and after the event. A complete collection of monthly files can still lack the continuous, interpretable pixel observations needed for this calculation. Similarly, a large number of human image interpretations does not establish independent accuracy when the reviewed samples were selected by a model or the reviewer saw model suggestions. Sampling design, reference quality and analysis must be considered together [@Olofsson2014; @Stehman2019].

We therefore ask three related questions: how did seasonal and permanent source-class areas change within a fixed observed footprint; which annual associations persist after climate, observation-effort and processing-boundary controls; and how much spatial and temporal evidence remains available for sensor comparison and drought-recovery assessment? The contribution is an integrated regional assessment with explicit limits on its estimands, rather than a new classification algorithm. We retain null results, unsupported months and unresolved interpretations throughout. This provides a practical basis for deciding which mapped changes merit local investigation and which resilience claims require additional observations.

## 2 Materials and methods

### 2.1 Study area and analytical design

The study covers Naogaon, Chapainawabganj and Rajshahi in northwestern Bangladesh (Figure 1). The reporting boundary was obtained from geoBoundaries Bangladesh ADM2, boundary identifier BGD-ADM2-16705992, representing 2020 and citing Bangladesh Bureau of Statistics and OCHA ROAP as source organizations. The archived source names Chapainawabganj as Nawabganj; we harmonized its reporting name while preserving the geometry and source identifiers. Boundary metadata, licensing and download identifiers are retained in the reproducibility materials. District estimates and their union are reported separately; the union overlaps all three districts and is not an independent replicate.

INLINEFIGURE01

Figure 1. Study location and analytical design. (A) Location of the study districts within Bangladesh. (B) The three district reporting boundaries; Chapainawabganj is harmonized from the source name Nawabganj. (C) The primary annual analysis, separate radar–optical analysis and four-month dated comparison. Maps use a WGS84 transverse Mercator projection centered on 90°E; scale bars and north arrows are geodesic. Boundaries: geoBoundaries gbOpen BGD ADM2, BGD-ADM2-16705992; underlying sources Bangladesh Bureau of Statistics and OCHA ROAP, CC BY 3.0 IGO. Boundaries are shown for analysis and imply no position on legal status.

The design has three linked but distinct components. The primary component describes annual Joint Research Centre (JRC) source classes during 2000–2021 within a fixed annual-observation footprint. A 2000–2024 extension assesses source-version sensitivity. A complementary component uses Sentinel-1 and Dynamic World during 2015–2024 on separately constructed historical water cohorts. Finally, a stratified sample in four selected months compares JRC binary labels with dated Sentinel-2 proxies and assisted human interpretation. These components differ in period, spatial support and outcome; their trend estimates are not pooled.

### 2.2 Data sources, versions and preprocessing

Table 1 summarizes the data. Water and climate products were exported from Google Earth Engine [@Gorelick2017], then audited locally for source periods, duplicate records, masks, units, grid metadata and checksums. JRC annual classes were retained as no observations (0), nonwater (1), seasonal water (2) and permanent water (3). Monthly classes were retained as no observations (0), nonwater (1) and water (2). Masked export values were nodata, not evidence of dry land. Pixel areas and climate-polygon intersections in the primary local analysis were evaluated in the equal-area coordinate system EPSG:6933, while native source grids were preserved.

Table 1. Data sources and their roles. Resolution denotes product/grid spacing, rather than independently resolved hydrological detail. Components use different spatial domains.

| Source | Period used | Product spacing | Purpose and limitation |
| --- | --- | --- | --- |
| JRC Global Surface Water | 2000–2021 primary; 2022–2024 sensitivity | 30 m | Annual source classes and monthly observations; corrected 2016–2021 assets and a collection change after 2021 |
| CHIRPS version 3 | 1981–2024 | 0.05° | Rainfall and fixed-baseline SPI; complete six-pentad monthly sums |
| ERA5-Land monthly aggregated | 2000–2024 | Approximately 0.1° grid | Temperature and model-specific evaporation demand; no measured groundwater or reference ET₀ |
| Sentinel-1 GRD | 2015–2024 | 10 m nominal product grid | One descending orbit; monthly VV benchmark classes and method envelopes |
| Dynamic World version 1 | 2015–2024; availability from June 2015 | 10 m | Four confidence thresholds; unclassified support retained |
| Sentinel-2 Level-2A | Four sampled months | 10 m display; B11/SCL native 20 m | Actual dated crop values and assisted interpretation; not independent ground truth |
| geoBoundaries gbOpen ADM2 | Represented year 2020 | Vector district polygons | Fixed reporting boundaries; administrative districts are not catchments |

Annual data use the historical JRC collection through 2015, corrected 2016–2021 YearlyHistory assets, and separate 2022–2024 assets. The provider reports that the recent extension uses Landsat Collection 2, whereas the earlier record uses Collection 1. Residual co-registration differences can be spatially variable and can reach or exceed one 30 m pixel. The provider also documents corrections to 2016–2021 seasonality and yearly-history layers.^[JRC Global Surface Water data access and update notes, accessed 16 October 2026: https://global-surface-water.appspot.com/download.] Consequently, the primary trend period ends in 2021. The extended analysis includes a 2022 source-version indicator, and a separate pre-2022 sensitivity includes a 2016 corrected-asset indicator. Neither indicator establishes that a coincident physical change is an artifact.

Rainfall was obtained from CHIRPS version 3 pentads at 0.05° [@Funk2026]. A monthly value required all six actual pentads to be valid at a pixel; annual rainfall required all twelve monthly values. Regional climate summaries used exact cell-intersection areas and finite-data support. ERA5-Land monthly aggregated fields supplied 2 m temperature and potential evaporation [@Munoz2021]. Kelvin was converted to degrees Celsius, accumulated fluxes from meters to millimeters, and annual temperature was weighted by calendar-month days. The original signed evaporation flux and its sign-reversed demand proxy were stored separately. ERA5-Land potential evaporation is a model-specific evaporative-demand measure; it was not interpreted as FAO reference evapotranspiration.^[ECMWF ERA5-Land documentation: https://confluence.ecmwf.int/spaces/CKB/pages/140385202/ERA5-Land+data+documentation. Earth Engine monthly aggregation: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_MONTHLY_AGGR.]

### 2.3 Fixed footprints, observation effort and annual outcomes

The retrospective reference footprint contains pixels classified as seasonal or permanent water in at least one year during 2000–2024. The annual comparison footprint is its subset with a valid annual class in every one of those 25 years. Although primary outcomes stop in 2021, footprint construction therefore uses subsequent observation availability and water classification. This restriction is intentional and retrospective; it does not represent an independently defined wetland inventory or an operational forecasting domain. Within each region and year, seasonal and permanent areas are sums of pixel areas assigned the corresponding annual source class on that fixed footprint.

A separate transition diagnostic compared strict five-year majority classes in 2000–2004 and 2017–2021 on the same annual footprint. All five annual observations were required in each window, and at least three occurrences defined the majority class. A window without a strict majority remained ambiguous. These transitions describe source-class assignments and do not validate land-use or storage change.

Observation-effort summaries include the area-weighted number of observed calendar months, the number observed during June–September, and the area fraction observed in all twelve months. These diagnostics distinguish annual class availability from a fully observed annual water cycle. Permanent source classification is not treated as independent confirmation that water was visible in every month. For the original monthly JRC analysis, candidate months required coverage thresholds of 80%, 90% or 95% on both the district raster domain and the retrospective footprint. The common monthly cohort intersects valid pixels across all candidate months. A retained outcome required complete observation on that cohort, at least 48 candidate months and at least 20% footprint retention. All support failures remain in Supplementary Data.

Initial seasonal and permanent cohorts required all five annual observations in 2000–2004 and at least three occurrences of the respective class. Ambiguous and initially nonwater pixels were excluded from these two cohorts. Original monthly JRC inference for initial-class cohorts began in 2005, while the all-water series began in 2000. A monthly detection on an initial permanent cohort does not relabel that cohort as a new permanent class each month. The all-water common footprint retained 2.46%, 17.36% and 50.35% of its reference area under the 80%, 90% and 95% candidate-month gates, respectively. These rules select different restricted cohorts; their differences are not a coverage-treatment effect.

### 2.4 Annual trend, climate and observation models

Unadjusted annual class areas were regressed on year; descriptive Theil–Sen slopes were also retained. Climate models used the logit of each class's share of the fixed footprint. With year measured from 2000, the annual model is given in Equation (1):

$$\operatorname{logit}(p_t)=\alpha+\beta_t(t-2000)+\beta_P P_t+\beta_T T_t+\beta_E E_t+\boldsymbol{\gamma}^{\mathsf{T}}\mathbf{O}_t+\delta I(t\geq2016)+\varepsilon_t. \qquad (1)$$

Here, $P_t$ is annual rainfall, $T_t$ is day-weighted mean temperature, $E_t$ is annual sign-reversed potential evaporation, and $\mathbf{O}_t$ contains observation-effort terms. The baseline climate model omitted observation and processing terms. Three exploratory sensitivities added, sequentially, mean annual observed months; annual plus June–September observed months; and those observation terms plus the 2016 indicator. The final specification contains both observation terms and the processing-boundary indicator. The 2000–2024 sensitivity uses the relevant 2022 version indicator separately.

Fractions were clipped to [10^−6^, 1−10^−6^] solely for logit fitting; stored observations were unchanged. Predictors were centered and scaled during fitting, with coefficients transformed back to original units. Rank and condition-number checks rejected unusable designs. Conditional 95% coefficient intervals used Student-t critical values and finite-sample-corrected Bartlett heteroskedasticity- and autocorrelation-consistent covariance, with annual lag 2 [@NeweyWest1987]. Lag matching used actual calendar distances. District-level p-values were adjusted by Benjamini–Yekutieli within each annual class-trend or climate-model family, and across the six district-by-class tests within each observation-sensitivity specification [@BY2001]. The union was descriptive and excluded from those district testing families. Intervals shown in figures are pointwise; these families do not correct for every exploratory choice in the study.

Model acceptance required enough usable observations beyond the number of parameters, finite and nonconstant features, full design rank and a scaled condition number below 10^8^. The rank and condition checks assess numerical usability rather than correctness of the regression specification.

The time coefficient is a conditional change in logit class share per year. It is not an area-loss rate or an estimate of human water use. Fixed-climate displays hold weather at regional 2000–2021 medians. Separate modeled seasonal and permanent shares are not summed into a compositional prediction. Temporal validation used two-year calendar test blocks beginning in 2009, 2013, 2017 and 2020, requiring at least twelve earlier training years and two test years for annual fits. Thus, three annual folds were accepted. Feature estimation was confined to training data. A training-only mean class fraction provided the annual benchmark. The resulting errors assess conditional hindcast performance on the retained footprint, not water-classification accuracy.

Original monthly checks used one annual sine/cosine harmonic, three-calendar-month rainfall, monthly temperature and evaporation demand. Monthly folds required 36 training observations and six test observations, with the preceding three calendar months excluded from training. Scaling was estimated within each training set, and the monthly benchmark used training calendar-month means. Every accepted and rejected fold and null model outcome remains in the extended diagnostic tables.

### 2.5 Radar–optical analysis and support-sensitive agreement

The 2015–2024 radar–optical analysis reconstructed its own retrospective annual ever-water footprint on a fixed approximately 30 m angular grid. Two additional frozen cohorts required all five initial annual classes to be observed and a strict majority of seasonal or permanent source classes during 2000–2004. These historical cohorts retained their initial labels throughout the radar analysis. They are distinct from the annual comparison footprint.

Sentinel-1 GRD scenes were restricted to interferometric wide swath, VV/VH availability, incidence angles of 30–45° and one pass/relative-orbit track. A deterministic metadata-based ranking selected descending relative orbit 48 before water-result comparisons. Selection considered a footprint proxy from at most the first six scenes, then temporal scene availability, scene count and lexical ties; it did not measure valid pixel coverage. Actual support was evaluated subsequently. Input scenes were placed on a common EPSG:32645 10 m working grid. Scenes on the same acquisition date were mosaicked, and a monthly pixel required at least two unique acquisition dates. Median VV, already in decibels, was classified at −19, −17 and −15 dB. These are strict, central and loose benchmark specifications without local independent calibration; no additional speckle filter was applied.

For track ranking only, the metadata footprint calculation simplified the boundary by 1,000 m and quantized the footprint proxy to 0.001; actual water summaries retained the original boundary. Dynamic World land evidence used trees, grass, crops, shrub_and_scrub, built, bare and snow_and_ice. Component-wise temporal medians of water and maximum-land scores were not assumed to form one probability distribution summing to one. The mean paired-footprint fraction includes all 120 months, including zero-support months, whereas pooled agreement divides summed agreeing area-time by summed paired area-time.

For Dynamic World, daily mosaics supplied monthly median water probability and median maximum probability among the seven selected land classes. Flooded vegetation was excluded from the land maximum. At least two unique dates were required. At each threshold $q\in\{0.5,0.6,0.7,0.8\}$, water evidence required water probability at least $q$; nonwater evidence required land probability at least $q$ and water probability at most $1-q$. Other pixels remained unclassified. These model scores were not treated as calibrated local probabilities of correctness. Dynamic World shares Sentinel-2 optical lineage with the dated interpretation component, so the optical comparisons are dependent [@Brown2022].

Overlap-weighted supported and water fractions were aggregated from the working grid to the fixed coarse grid. A coarse comparison cell required at least 95% supported footprint and a water fraction of at least 80% or at most 20% of its supported area. Agreement was the summed agreeing area-time divided by summed paired area-time; retained paired footprint was reported alongside it. Monthly composites may represent different acquisition dates between sensors, adding genuine within-month change to classification and registration differences. No confidence threshold was selected by maximizing agreement.

Radar method envelopes retained both threshold and observation uncertainty. If $D$ is fixed cohort area, $V$ is supported area and $W_{19}$ and $W_{15}$ are water areas under the strict and loose VV specifications, respectively, Equation (2) defines the envelope:

$$[L,U]=\left[\frac{W_{19}}{D},\ \frac{W_{15}+D-V}{D}\right]. \qquad (2)$$

The upper endpoint allocates unsupported area to water. This range does not encompass all physical classification errors and is not a confidence interval for true water area. Exploratory endpoint regressions included time, one annual sine/cosine harmonic, three-month rainfall, temperature, evaporation demand and, where variable, radar coverage and acquisition-day count. Calendar-distance HAC lag 12 and separate district testing families for lower and upper endpoints were used. All region/cohort results, including unsupported findings, were retained.

### 2.6 Drought definition and recovery identifiability

SPI-3 and SPI-6 were calculated from complete-calendar rolling CHIRPS rainfall totals, using a fixed 1981–2020 calibration. Calendar-month-specific gamma maximum likelihood fixed location at zero and estimated zero probability separately, followed by a normal-quantile transformation. Calibration required at least 30 usable accumulations and ten positive accumulations for each calendar month. Failed fits remained missing. This is a precipitation-only drought index, without a validated precipitation–evapotranspiration index.^[SPI guidance: https://climatedataguide.ucar.edu/climate-data/standardized-precipitation-index-spi.]

An SPI-3 event began at ≤−1 and ended at the first subsequent month with SPI ≥0; missing climate data censored active events. For radar recovery, eligible monthly envelopes required at least 95% supported area. Calendar-month reference envelopes were estimated from eligible 2015–2021 observations, with at least five reference observations. Subtracting the upper reference from the current lower endpoint, and the lower reference from the current upper endpoint, gave a conservative anomaly envelope. The pre-event reference required three consecutive observed months. A detectable drought deficit had to exceed 0.02 of cohort area; recovery required a return within 0.02 of the pre-event anomaly for two consecutive observed months, with up to 24 months of follow-up.

For numerical stability, cumulative probabilities were bounded away from 0 and 1 at 10^−8^. In the recovery calculation, the drought deficit excludes the first non-drought termination month. All event records retain their original missing-support status. Neither repeated dates within a sample nor overlapping event–cohort records are independent replicates.

Possible and confirmed recovery times were sought separately from the anomaly endpoints. Missing pre-event, drought-phase or follow-up evidence prevented a duration estimate. No interpolation bridged gaps. Sensitivity crossed coverage gates of 80%, 90% and 95% with minimum calendar-month reference counts of three, four and five. The resulting event–cohort records overlap across districts, union and cohorts. They are accounting records, not independent drought replicates. Original JRC recovery diagnostics were retained separately because their calendar reference and observation domains differ.

### 2.7 Dated sample comparison and assisted interpretation

The frozen comparison frame comprised March 2018, November 2020, March 2023 and November 2024. Within each district, month and observed JRC binary class, 30 pixels were sampled without replacement, giving 24 strata and 720 pixel-months. Previously exposed review cells were excluded before this new sample was drawn. The design therefore applies to this eligible four-month population, rather than every pixel or year in the annual study. The frozen sampling seed and stratum populations are retained in the source records.

Actual Sentinel-2 Level-2A crop values and product XML calibration supported an initial spectral triage. The rules used modified normalized difference water index [@Xu2006], normalized green–near-infrared difference, vegetation index and reflectance screens. At least 95% of the target footprint had to be clear and strongly classified on at least two dates spanning fourteen days. A boundary diagnostic flagged opposite spectral evidence in a 10 m surrounding ring. These deliberately restrictive heuristic rules were not trained or locally validated as an accuracy model. Although displays used a 10 m grid, the shortwave-infrared band and scene-classification layer retained their coarser native information content.

The spectral indices used in the triage are defined in Equation (3), where $G$, $N$, $R$ and $S$ denote green, near-infrared, red and shortwave-infrared reflectance, respectively:

$$\begin{aligned}\mathrm{MNDWI}&=(G-S)/(G+S),\\\mathrm{NDWI}&=(G-N)/(G+N),\\\mathrm{NDVI}&=(N-R)/(N+R).\end{aligned}\qquad (3)$$

Only finite reflectance within [0,1.2] was screenable, and invalid or near-zero denominators remained unavailable. Accepted scene-classification values were 4, 5 and 6; this operational clear-pixel screen does not exclude every residual cloud or shadow error. Strong water required MNDWI ≥0.20, NDWI ≥0.10, NDVI ≤0.20, near-infrared reflectance ≤0.15, shortwave-infrared reflectance ≤0.08, green reflectance ≥0.01 and mean visible reflectance ≥0.012. Strong nonwater required either MNDWI ≤−0.20 and NDWI ≤−0.10 with near-infrared or shortwave-infrared reflectance ≥0.08; or NDVI ≥0.45, near-infrared reflectance ≥0.18, MNDWI ≤0, NDWI ≤−0.10 and shortwave-infrared reflectance ≥0.08.

At least 95% of target area had to pass both the clear-pixel and strong-class requirements for a dated rule label. More than 5% radiometrically uninterpretable target area prevented acceptance. Fractions used the actual target footprint intersected with crop cells. The surrounding 10 m ring triggered a boundary flag if at least half of the ring was clear and at least 10% of its area had the opposite weak index sign. Monthly automatic assignment required at least two accepted dates spanning fourteen days, no conflicting or ambiguous dated rule and no boundary flag. Raw crops comprised five reflectance layers, scene classification and support on a 40×40 display grid; each reflectance band used its actual product XML scale and offset.

Difficult cases selected by the triage were reviewed date by date with image assistance. A monthly comparison label was retained only when its accepted dated interpretations were consistently binary; temporal changes, uncertain dates and inadequate support remained unresolved. Repeated dates were evidence within one pixel-month, not additional independent samples. One dated answer was subsequently revised from nonwater to water at the reviewer's direction after the rule output was disclosed. Original and revised files were preserved. Accordingly, this component measures assisted proxy agreement, without claiming blinded independent validation. The thresholds and revision procedure are specified above; Supplementary Methods retain the exact revision identifiers.

Human dated answers were joined by sample_id and scene_id, never by display row. The original export contained 429 water, 237 nonwater and 28 uncertain answers. The documented correction changed one answer from nonwater to water, yielding the current totals reported below. Its timestamp records a revision after rule output was shown, not a new independent image inspection. The original CSV, backup and cell-difference record remain preserved; exact product and sample identifiers are retained in Supplementary Methods, Section S2.

For sampled pixel $i$ in stratum $h$, the design weight was $w_i=(N_h/30)a_i$, where $N_h$ is the eligible population pixel count and $a_i$ is sampled geodesic pixel area. Normalized weights approximate area-time ratios; they are not a full census. Let $A$ denote assigned samples and $M$ assigned samples matching JRC. We report assigned weight, conditional agreement $\sum_{i\in M}w_i/\sum_{i\in A}w_i$, and the binary-completion range in Equation (4):

$$\left[\frac{\sum_{i\in M}w_i}{\sum_iw_i},\ \frac{\sum_{i\in M}w_i+\sum_{i\notin A}w_i}{\sum_iw_i}\right]. \qquad (4)$$

This range permits arbitrary agreement or disagreement for unresolved labels. It bounds completion of the proxy comparison, not physical-water accuracy. Approximate sampling intervals used 2,000 pixel-month bootstrap replicates within the original strata, with seed 20261016. These intervals omit reference, timing, radiometric, registration and spatial-clustering errors. Degenerate conditional bootstrap intervals were left unavailable rather than presented as certainty.

The stratified percentile bootstrap did not use a finite-population correction or a spatial-cluster model. Its intervals concern approximate pixel-month sampling variation and exclude reference error, temporal misalignment and nonrandom missingness. A conditional bootstrap with no empirical variation remained unavailable instead of being presented as a zero-width accuracy interval.

### 2.8 Reproducibility and analytical scope

The completed computational audit verified 9,393 source-file checksums and reconciled the downloaded export inventories and reported numerical tables. The active analysis retains the corrected dated-label version and its history. Manuscript preparation read these frozen results without refitting the scientific models. Figure inputs, table copies and their SHA-256 hashes are recorded separately. The analysis environment used Python 3.12, NumPy 2.3.5, pandas 2.3.3, statsmodels 0.14.5 and rasterio 1.5.0. Software checks establish reproducibility properties; they do not establish environmental accuracy. The overall design is exploratory, and results were known when the final restricted scope was documented.

## 3 Results

### 3.1 Seasonal source-class decline on a restricted footprint

The fixed annual footprint was 1,276.41 km², retaining 79.30% of the retrospective ever-water reference area. District contributions were 473.82 km² in Naogaon, 358.88 km² in Chapainawabganj and 443.71 km² in Rajshahi. These areas define the estimand for the primary annual results; they do not cover the complete districts.

Between 2000 and 2021, union seasonal source-class area decreased from 938.53 to 699.91 km², a loss of 238.62 km² or 25.42% relative to the initial seasonal class area (Figure 2; Table 2). The largest district endpoint loss was in Naogaon: 145.96 km², or 37.84%. Rajshahi lost 73.38 km², or 24.46%, and Chapainawabganj lost 19.28 km², or 7.62%. The unadjusted union seasonal linear slope was −8.42 km² year^−1^ (95% interval −12.79 to −4.05; 22 annual observations). Endpoint differences and the fitted slope summarize different aspects of the trajectory.

INLINEFIGURE02

Figure 2. Annual source classes and observation effort on the fixed 1,276.41 km² annual footprint during 2000–2021. (A) Seasonal-class area. (B) Permanent-class area, with its own vertical scale. (C) Area-weighted observed months out of twelve. (D) Observed June–September months out of four. The union overlaps the district series. Annual classes do not certify complete observation of the year. Source: EC JRC/Google; derived from the frozen annual class and observation-quality tables.

Table 2. Annual source-class endpoint changes within the fixed annual-observation footprint, 2000–2021. Percent change is relative to each class's 2000 area. Districts sum to the union; the union is not an independent replicate. These are classified areas, not water volumes or independently validated hydroperiod areas.

| Region | Source class | 2000 (km²) | 2021 (km²) | Change (km²) | Change (%) |
| --- | --- | --- | --- | --- | --- |
| Union | Seasonal | 938.53 | 699.91 | -238.62 | -25.42 |
| Union | Permanent | 65.49 | 92.37 | +26.88 | +41.04 |
| Naogaon | Seasonal | 385.72 | 239.76 | -145.96 | -37.84 |
| Naogaon | Permanent | 4.52 | 4.66 | +0.14 | +3.08 |
| Chapainawabganj | Seasonal | 252.84 | 233.56 | -19.28 | -7.62 |
| Chapainawabganj | Permanent | 22.81 | 32.80 | +9.99 | +43.79 |
| Rajshahi | Seasonal | 299.98 | 226.60 | -73.38 | -24.46 |
| Rajshahi | Permanent | 38.16 | 54.91 | +16.75 | +43.90 |

Permanent source-class area increased from 65.49 to 92.37 km² across the same endpoints, a gain of 26.88 km² or 41.04%. Most of that endpoint increase occurred in Rajshahi and Chapainawabganj; Naogaon's permanent-class area changed by only 0.14 km² (Table 2). These descriptive gains do not establish continuous permanent-water expansion after accounting for observation and processing changes.

The corresponding strict-majority transition map is shown in Figure 3. It distinguishes stable classes, gains, losses and seasonal/permanent transitions while preserving ambiguous windows; the mapped classes do not establish a physical mechanism.

INLINEFIGURE03

Figure 3. Source-class transitions between strict five-year majority classes in 2000–2004 and 2017–2021, on the fixed annual footprint. Source: EC JRC/Google. Class transitions are not independently validated land-use or storage changes.

### 3.2 Observation and processing controls change the permanent-water interpretation

Annual class availability concealed substantial variation in within-year observation effort. On the union footprint during 2000–2021, the area-weighted observed-month count ranged from 5.30 to 10.25 months per year. June–September effort ranged from 0.17 to 2.87 of four months. The footprint fraction observed in every calendar month ranged from 0% to 16.15% (Figure 2). Thus, the annual dataset did not provide a fully observed twelve-month water cycle over most of the retained area.

Seasonal time coefficients remained negative in the union across the observation-control specifications (Figure 4). With climate, annual and wet-season observation effort, and the 2016 indicator included, the union coefficient was −0.0607 logit share year^−1^ (95% interval −0.0814 to −0.0399). District coefficients were −0.1154 in Naogaon (−0.1602 to −0.0706; adjusted p=0.00109), −0.0480 in Rajshahi (−0.0714 to −0.0245; adjusted p=0.00454) and −0.0350 in Chapainawabganj (−0.0720 to 0.0020; adjusted p=0.302). The district distinction is material: the final specification supported a continuing seasonal decline in two districts, while uncertainty included zero in the third.

INLINEFIGURE04

Figure 4. Sensitivity of annual climate-adjusted time coefficients to observation effort and the 2016 corrected-asset boundary. (A) Seasonal class. (B) Permanent class. Points and bars show coefficients and pointwise 95% calendar-distance HAC intervals from 22 annual observations. All specifications contain annual rainfall, temperature and evaporation demand. Additional terms are identified in the legend. District multiplicity-adjusted p-values are reported in the text and underlying table. A processing indicator can also absorb a genuine physical discontinuity.

All permanent-class time-coefficient intervals included zero after the 2016 processing-boundary indicator was added. The union coefficient was 0.0060 logit share year^−1^ (−0.0046 to 0.0165). Positive permanent trends from simpler specifications were therefore sensitive to this control. A step indicator can absorb a genuine hydrological discontinuity as well as a processing-related one, so this result does not identify the source of that sensitivity.

The annual seasonal climate model also had limited predictive benefit. Mean fold RMSE was higher than the training-only mean benchmark in every district and the union. For the union, model RMSE was 0.0898 of footprint fraction, compared with 0.0862 for the benchmark. Permanent-class mean fold errors were lower than the corresponding benchmarks, but only three annual folds were available in each case. Climate-adjusted associations should therefore be interpreted without a general claim of improved prediction. Full coefficients, fold summaries and the separate 2000–2024 sensitivity are provided in Supplementary Data.

Figure 5 places the observed class areas beside the baseline fixed-climate model expectations. The smooth expected curves are model-derived summaries, not replacement observations or validation of the class assignments. Their interpretation remains subject to the processing and observation sensitivities in Figure 4.

INLINEFIGURE05

Figure 5. Primary annual fixed-climate expectations, 2000–2021, from separate class-share models. These baseline climate-model curves should be read alongside the observation/processing sensitivities in Figure 4. Model-derived curves are not missing-observation replacements.

### 3.3 Higher automated agreement coincides with lower paired support

The radar–optical analysis reconciled 1,440 monthly region/cohort rows and 5,760 threshold-specific rows. Its scene inventory contained 265 Sentinel-1 scenes and 1,274 Dynamic World scenes, totaling 1,539 unique source identifiers. These complete exports did not imply complete pixel observations in every month.

For the union historical ever-water cohort, increasing the Dynamic World threshold from 0.5 to 0.7 reduced the number of months with any classified support from 76 to 74 of 120. Mean classified support fell from 17.94% to 4.45% of the fixed cohort. Conditional Sentinel-1–Dynamic World agreement increased from 89.04% to 98.71%, while mean paired support decreased from 11.07% to 3.29% (Figure 6). At 0.6, agreement was 95.94% on mean paired support of 5.88%. Threshold 0.8 yielded no classified or paired support. Its missing agreement value indicates absence of comparison evidence.

INLINEFIGURE06

Figure 6. Dynamic World confidence sensitivity on the separate 2015–2024 union historical ever-water cohort. (A) Mean classified and SAR–Dynamic World paired footprint fractions, including months with zero support. (B) Agreement pooled by paired area-time. Threshold 0.8 has no comparison support and no agreement estimate. The changing paired population prevents interpreting the highest agreement as independently validated accuracy. All four thresholds were retained without selecting a best threshold.

JRC–Dynamic World agreement followed the same conditional pattern, increasing from 92.48% at 0.5 to 98.70% at 0.7. The evidence does not identify a best threshold: both the compared population and its size change with the threshold. In particular, 98.71% radar–optical agreement describes the small paired area-time subset, without estimating study-wide accuracy.

The full monthly support and method-envelope series are displayed in Figure 7. The high-threshold ranges remain wide because omitted support enters the upper endpoint; a narrow assigned subset does not constrain the water state of the rest of the cohort.

INLINEFIGURE07

Figure 7. Dynamic World threshold-specific support and method envelopes, 2015–2024, for the union historical ever-water cohort. Unclassified support enters the upper endpoint; envelopes do not include all physical classification errors.

Radar endpoint regressions used 90 supported monthly observations per region/cohort. Positive time coefficients for both envelope endpoints survived the separate district adjustments for Rajshahi's initial seasonal cohort: 0.0582 logit fraction year^−1^ for the lower endpoint (95% interval 0.0236–0.0929; adjusted p=0.0161) and 0.0396 for the upper endpoint (0.0124–0.0669; adjusted p=0.0312). Other district/cohort combinations were not uniformly supported. These later-period radar cohort outcomes and the primary annual seasonal-class loss concern different estimands; they cannot be interpreted as cancelling trends.

Figure 8 shows both endpoints for all three districts and all three historical cohorts, including intervals crossing zero. This retains the unsupported combinations alongside the highlighted Rajshahi result.

INLINEFIGURE08

Figure 8. Exploratory radar envelope time coefficients for the three districts, all three cohorts and both endpoints. Filled markers indicate district-family BY-adjusted p < 0.05. These 2015–2024 cohort outcomes differ from annual JRC class areas; nulls are retained.

### 3.4 Assisted dated evidence leaves a substantial unresolved comparison frame

The 720 sampled pixel-months had 3,022 actual scene-point views from 69 source scenes. Initial triage assigned 337 automatic proxies, selected 245 difficult points for dated human review, and left 138 points without sufficient dated support. Human review recorded 694 date-specific answers: 430 water, 236 nonwater and 28 uncertain. After preserving date conflicts and the single documented correction, 194 reviewed points had consistent binary dates, 35 showed temporal change and 16 had uncertain dated evidence (Figure 9; Table 3).

INLINEFIGURE09

Figure 9. Dated proxy evidence and unknown comparisons for all 720 stratified pixel-month samples. (A) Design-weighted outcome shares; annotations give sample counts. (B) Dots indicate conditional agreement on assigned labels; grey segments show algebraic ranges under arbitrary binary completion of unresolved comparisons. These are not physical-accuracy bounds. Repeated scene dates are within-sample evidence, and selected human review was assisted. Counts and weights use the corrected active label version, with original interpretations preserved.

Table 3. Outcomes and comparison accounting for all 720 sampled pixel-months. In panel A, weight is the share of all sampled area-time for each outcome; in panel B, it is the assigned share for each comparison route. Agreement uses assigned weight only. Completion ranges arbitrarily assign unresolved comparisons to agreement or disagreement; they are neither confidence intervals nor physical-water accuracy bounds. The assisted conditional sampling interval is 96.85–99.87%; the automatic conditional bootstrap is degenerate and omitted. Dashes denote inapplicable quantities.

| Outcome or comparison route | Pixel-months (n) | Weight (%) | Agreement (%) | Completion range (%) |
| --- | --- | --- | --- | --- |
| A. Outcomes for all sampled pixel-months |  |  |  |  |
| Automatic proxy assigned | 337 | 58.43 | — | — |
| Consistent human dates assigned | 194 | 18.11 | — | — |
| Temporal change: unresolved | 35 | 1.38 | — | — |
| Uncertain dates: unresolved | 16 | 1.80 | — | — |
| Insufficient dated support: unresolved | 138 | 20.28 | — | — |
| Total | 720 | 100.00 | — | — |
| B. Assigned comparison routes |  |  |  |  |
| Automatic only | 337 | 58.43 | 100.00 | 58.43–100.00 |
| Assisted proxy | 531 | 76.54 | 98.56 | 75.44–98.90 |

Combining automatic proxies with consistent human dates assigned 531 pixel-months; 189 remained unresolved. Assigned points represented 76.54% of design-weighted area-time, compared with 58.43% under automatic screening alone. Assisted conditional JRC/proxy agreement was 98.56%, with an approximate stratified sampling interval of 96.85–99.87%. The corresponding binary-completion range across all sampled weight was 75.44–98.90% (Table 3). Its width reflects unresolved comparison weight; it is not a confidence interval for true-water accuracy.

The automatic-only assigned subset had no observed JRC disagreement, but 41.57% of design weight remained unassigned. Its conditional bootstrap was degenerate and was not reported as an informative uncertainty interval. Human selection and assistance, shared optical information, repeated dates and the documented feedback correction also preclude an independent-accuracy interpretation. The four selected months do not validate every historical year or the annual distinction between seasonal and permanent classes.

### 3.5 Drought recovery duration remains unidentified

The meteorological drought history is shown in Figure 10. SPI-3 describes rainfall deficits, so its return to zero does not itself establish surface-water recovery.

INLINEFIGURE10

Figure 10. SPI-3 history from CHIRPS version 3 with fixed 1981–2020 calibration. A meteorological drought event is distinct from an observed surface-water deficit.

The monthly JRC observation/reference diagnostic in Figure 11 shows why the original optical record cannot provide a continuous recovery sequence under the stated support rules. The JRC and radar recovery domains remain separate.

INLINEFIGURE11

Figure 11. Original monthly JRC water-observation and recovery-gap diagnostics. Observation exclusions remain gaps, and this domain/reference differs from the radar recovery analysis.

Under the primary radar recovery specification, none of the 108 event–cohort records yielded an identifiable duration. Eighty-four failed the pre-event support/reference requirement and 24 failed drought-phase support/reference requirements. Across the nine coverage/reference settings, all 972 records remained without a recovery duration: 702 had pre-event/reference gaps, 144 had drought-phase/reference gaps and 126 had a deficit uncertain within the method envelope (Figure 12).

INLINEFIGURE12

Figure 12. Reasons that drought recovery was not identifiable across nine coverage/reference settings. Each row retains the same 108 overlapping event–cohort records; row labels combine minimum supported-area fraction and minimum calendar-month reference count. Across all 972 records, 702 have pre-event/reference gaps, 144 drought-phase/reference gaps and 126 an uncertain deficit within the method envelope. No setting provides an identifiable duration. Missing timing is not evidence that water failed to return.

No minimum, maximum or scalar recovery time was available under these settings. Relaxing coverage and reference counts changed the reason for non-identification in some records, without producing reliable timing. Because records overlap and observational censoring can be informative, these counts do not estimate the proportion of independent droughts that failed to recover. The finding concerns the inability of the available sequence and method envelope to identify recovery; ecological recovery itself remains unresolved.

## 4 Discussion

### 4.1 Seasonal decline is a monitoring signal with a defined spatial scope

The seasonal source class contracted within the fixed annual footprint. Its direction persisted in the union, and the climate/observation/processing sensitivity retained negative district coefficients in Naogaon and Rajshahi. This combination supports prioritizing those retained areas for closer hydrological and land-management investigation. The smaller Chapainawabganj endpoint decrease and its final interval spanning zero argue against applying one uniform district-level trend claim to the entire region.

Several mechanisms remain compatible with the observed seasonal-class loss. Water occurrence may have changed, pixels may have moved between seasonal and permanent classes, or the interaction of observation timing and processing may have affected annual assignment. The fixed footprint removes changes in which pixels enter each annual area sum, but it does not remove class error or uneven seasonal sampling. Neither a persistent time coefficient nor a climate-adjusted residual identifies irrigation abstraction, land conversion, river management or an ecological mechanism.

Regional evidence of rainfall heterogeneity [@Rainfall2026] and coupled climatic and groundwater stress [@Barind2025] makes those mechanisms relevant hypotheses. Testing them would require matched observations of groundwater levels, abstraction, river regulation, land use and waterbody management. Basin-scale separation of storage components uses different evidence, including process models and gravity observations [@Girotto2025]. Our classified areas do not supply equivalent information about water volume. Likewise, the surface-water expansion reported in southwestern Bangladesh [@Huda2021] is compatible with a different regional trajectory; neither result should be generalized across the country without harmonizing domains and definitions.

The permanent class illustrates the risk of interpreting endpoints as a robust process trend. Its 41.04% endpoint increase is a valid description of source classifications on the retained footprint. However, the annual time coefficients lost clear positive support after the 2016 indicator. The appropriate interpretation retains both findings. A continuous increase in physically permanent water, an increase in storage, and improved dry-season water security are not established by this record.

### 4.2 Agreement should be evaluated together with the area it represents

Raising the Dynamic World threshold removed much of the classification and paired footprint while increasing agreement. This is consistent with selecting clearer, more homogeneous cases, although the present analysis does not isolate the causes of selection. High agreement on that subset cannot describe the omitted mixed, cloudy or weak-probability areas. Threshold 0.8 is particularly instructive: an apparently demanding confidence rule produced no comparison support for this implementation and domain. Treating its missing results as dry land would reverse their meaning.

The assisted sample has a related support limitation. The hybrid comparison expanded assigned support beyond the highly selected automatic subset, while some interpretations remained unresolved. Reporting 76.54% assigned area-time alongside 98.56% conditional agreement makes the coverage limitation visible. The binary-completion range additionally shows the influence of unresolved weight without assuming random missingness or inventing labels. It still depends on the assigned proxy labels and cannot account for their possible errors. Accuracy-assessment literature requires reference quality and sample design to be evaluated separately [@Olofsson2014; @Stehman2019]. Our assisted route meets a different purpose: documenting available evidence and unresolved support.

Cross-sensor studies with external reference imagery [@Vanderhoof2023] and monitoring studies incorporating field observations [@Slinski2025] provide stronger designs for future validation. Their reported performance cannot be transferred to the thresholds or wetland settings used here. The Bangladesh flood-insurance comparison similarly concerns a different outcome, but its finding that data choice affects decision performance [@Saunders2025] supports the practical value of retaining divergence and support information. For district monitoring, agreement should accompany explicit maps or summaries of the population actually compared.

### 4.3 Climate association and drought resilience require different evidence

Climate adjustment addressed a limited statistical question: how annual class shares co-varied with time after the specified weather and observation terms were included. The short annual series, approximate uncertainty estimates and seasonal hindcast performance constrain its use. Seasonal models did not outperform a training-only mean in average fold RMSE, despite retaining negative time coefficients in parts of the study area. This combination supports reporting associations while avoiding a claim that the model provides an improved operational forecast.

Recovery timing requires more than an annual association or several well-interpreted dates. The pre-event baseline, full drought phase and successive recovery observations must be connected on an interpretable calendar. Here, gaps and uncertain deficits prevented that chain under every examined setting. Hydrological drought can persist beyond a rainfall deficit because of storage and seasonal processes [@VanLoon2015], but this analysis cannot quantify that persistence. It also cannot rank the districts by recovery speed.

The negative identifiability result is useful for monitoring design. Additional observations should be targeted to missing parts of an event sequence, especially pre-event conditions and successive months around climatic drought termination. Reprocessing more isolated clear images may improve an annual map without resolving those event-level gaps. A future recovery study would benefit from a predefined network of sentinel waterbodies with repeated dated imagery and water-level observations, coupled to a stable reference method. Such a network is a proposed next study, not an intervention evaluated here.

### 4.4 Implications for sustainable water management

For the target districts, the results support a staged use of satellite evidence. Seasonal-class losses on the retained footprint can identify areas for field or higher-resolution investigation. Before using those areas to prioritize storage restoration or water allocation, managers would need to determine whether the signal reflects persistent inundation change, land use, channel movement or classification behavior. The present district aggregates do not locate a validated restoration site or quantify a water-supply benefit.

A practical district dashboard could report four quantities together: source-class area, observation effort, the fraction of the intended footprint with a usable comparison, and the continuity of evidence around drought events. This would preserve the distinction between a complete download, a classified pixel and a continuous hydrological record. The results give empirical reasons for each item: restricted annual coverage, sparse wet-season observations, threshold-dependent paired support and unidentified recovery duration.

This approach is relevant to monitoring the extent of water-related ecosystems and to climate-adaptation planning. It is not a complete official assessment of Sustainable Development Goal indicator 6.6.1, which has its own ecosystem definitions, reporting dimensions and national implementation requirements.^[UNEP description and methodology for indicator 6.6.1: https://www.unep.org/en/goal-6-clean-water-and-sanitation/indicator-661.] Water quality, groundwater storage, biodiversity outcomes, household water access and the effects of management interventions were not measured. The management contribution is therefore better-specified evidence for investigation and monitoring, without claiming observed improvements in water security.

### 4.5 Limitations and transferability

Retrospective selection is the main spatial limitation. The ever-water footprint uses the full 2000–2024 annual record, and the annual common footprint also requires future-year validity. Transient monthly-only water and poorly observed pixels can be excluded. Equal inclusion of retained pixels across years improves comparability within that subset, but it does not make the subset representative of the entire districts. Raster-center district assignment in the local annual analysis also differs from the radar analysis's geometry-weighted area accounting.

Source classification and alignment remain important. Corrected annual products, Landsat collection differences, mixed boundary pixels, SAR threshold behavior, wet soil, rice and vegetation can all affect water estimates. The method envelopes cover specified thresholds and unknown support, while excluding some systematic errors. Dynamic World and the dated optical proxy have related inputs, and monthly sensor composites do not necessarily represent the same day. Independent annual seasonal/permanent accuracy remains unmeasured.

Statistical uncertainty is also incomplete. Twenty-two annual observations provide limited information for models with multiple climate, effort and processing terms. HAC intervals are approximate and pointwise. Reported adjustment families cover specified district tests, not the entire exploratory workflow; spatial dependence and unobserved drivers remain. Retrospective cohorts make the temporal checks conditional hindcasts. The four-month proxy bootstrap addresses sampled pixel-month variation, without resolving nonrandom reference failure or spatial clustering. The lack of independent labels is explicit and prevents presenting proxy agreement as accuracy.

These limitations bound transferability to similar monitoring problems. Estimates should be reported together with their spatial, temporal and reference support. The numerical trends and thresholds themselves remain specific to the declared products, domains and periods in northwestern Bangladesh.

## 5 Conclusion

Seasonal JRC source-class area declined by 25.42% between 2000 and 2021 within a fixed 1,276.41 km² annual-observation footprint in northwestern Bangladesh. Negative seasonal time associations persisted in Naogaon and Rajshahi after the specified climate, observation-effort and processing-boundary controls. Permanent-class endpoint gains were sensitive to the processing control and do not establish a robust continuing increase.

The complementary analyses identify limits that matter for water-management interpretation. Higher radar–optical agreement occurred on a smaller paired footprint; assisted dated interpretation left 23.46% of sampled design weight unresolved; and no drought-recovery duration was identifiable across nine support/reference specifications. Satellite-based climate-resilience assessment should therefore retain observation density, paired support and event continuity alongside mapped change. These results guide further investigation and monitoring design while leaving causal drivers, independent accuracy and ecological recovery unresolved.

## Data and code availability

Derived results and complete comparison/support tables accompany the manuscript as Supplementary Data. The four v0.2.0-review archives—Supplementary Code, Supplementary Data Tables, Supplementary Data Grid and Supplementary Data Context—contain analysis code, genuine exported/aggregated inputs, result tables, metadata and checksums. They support statistical replay without GitHub access; full raw-pixel processing is not repeated. Public source products are identified in Table 1; exact assets are retained in Supplementary Methods, Section S1. The full source-raster history and dated image crops are not duplicated. Development materials are stored in the private GitHub repository [https://github.com/asifahamed11/northwestern-bangladesh-surface-water](https://github.com/asifahamed11/northwestern-bangladesh-surface-water); access is restricted to authorized GitHub accounts.

## Author contributions

<!-- Intentionally left blank at the authors' request. -->

## Conflict of interest

The authors report no financial or commercial conflicts of interest. Md. Kamruzzaman and Jayanta Das are Topic Editors of the Research Topic to which this work is intended to be submitted. An independent handling editor is requested.

## Funding

The authors report no funding for this research.

## Acknowledgments and generative AI use

We acknowledge the organizations providing the water, climate, satellite and administrative-boundary products used in this study. OpenAI Codex, based on GPT-6 (OpenAI; accessed October 2026), assisted with programming, evidence organization, manuscript drafting and editing. Procedural research guidance included Scientific Agent Skills [@ScientificSkills], an arXiv preprint and associated software resource. Figures were plotted from the recorded data using conventional scientific plotting tools. Responsibility for scientific interpretation, authorship and the final submitted content rests with the human authors.

## Supplementary material

Supplementary Methods contain compact asset, grid, revision-provenance and reproduction notes. All diagnostic figures and essential support, triage and recovery rules are included in the main manuscript. Supplementary Data retain 18 frozen main-result tables plus 20 extended diagnostic CSVs, including null fits, failed support, dated evidence and unresolved comparisons.

## References

::: {#refs}
:::
