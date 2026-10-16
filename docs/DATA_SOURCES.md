# Data sources

Data-source roles and observation rules are reported in Table 1 and Sections 2.2–2.7 of the main manuscript. Exact annual Earth Engine assets are `JRC/GSW1_4/YearlyHistory` for 2000–2015, `projects/global-surface-water/assets/GSW1_5/YearlyHistory_2016_2021` for corrected 2016–2021, and `projects/global-surface-water/assets/GSW1_5/YearlyHistory_2022_2024` thereafter. Monthly assets are `JRC/GSW1_4/MonthlyHistory` through 2021 and `projects/JRC/GSW1_5/MonthlyHistory_2022_2024` thereafter. The latter lacks system:time_start; genuine provider index/year/month metadata were used. Empty date-filter results were not dry observations.

Climate assets are `UCSB-CHC/CHIRPS/V3/PENTAD` and `ECMWF/ERA5_LAND/MONTHLY_AGGR`; radar and Dynamic World assets are `COPERNICUS/S1_GRD` and `GOOGLE/DYNAMICWORLD/V1`. The older monthly display used `COPERNICUS/S2_SR_HARMONIZED`. The later raw-value triage used archived Level-2A crop values and each product XML calibration, rather than reading display colors as reflectance.

The primary local raster grid preserves downloaded JRC alignment; climate intersections use EPSG:6933. The separate radar cohort grid uses EPSG:4326 with affine transform [0.00026949458523585647, 0, 0, 0, −0.00026949458523585647, 0]; its 10 m working grid is EPSG:32645. Categorical inputs use nearest-neighbor alignment and supported/water fractions use overlap-weighted aggregation. Reprojection does not add native detail or correct co-registration.

Boundary metadata are geoBoundaries gbOpen BGD ADM2, BGD-ADM2-16705992, represented year 2020, underlying Bangladesh Bureau of Statistics/OCHA ROAP, build 12 December 2023, source update 19 January 2023 and geoBoundaries commit 9469f09. The upstream license is CC BY 3.0 IGO. The original Nawabganj geometry is reported as Chapainawabganj.

The verified three-district boundary is included in `data/boundaries/study_area.geojson`. The national context boundary used in Figure 1 is referenced by its original hash in `provenance/figure_1_cartography.json`; it is omitted from this compact repository.
