from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ['All_districts', 'Naogaon', 'Chapainawabganj', 'Rajshahi']

def require(condition, message):
    if not condition:
        raise ValueError(message)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def write_json(path, value):
    def safe(v):
        if isinstance(v, dict): return {str(k):safe(x) for k,x in v.items()}
        if isinstance(v, (tuple,list)): return [safe(x) for x in v]
        if isinstance(v, np.ndarray): return safe(v.tolist())
        if isinstance(v, np.integer): return int(v)
        if isinstance(v, np.bool_): return bool(v)
        if isinstance(v, (float,np.floating)): return float(v) if np.isfinite(v) else None
        if isinstance(v, Path): return str(v)
        return v
    Path(path).write_text(json.dumps(safe(value),indent=2,allow_nan=False),encoding='utf-8')

def write_table(path, rows, columns=None):
    frame = rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows,columns=columns)
    frame.to_csv(path,index=False,na_rep='')
    return frame

def bool_values(values):
    mapped = values.astype(str).str.lower().map({'true':True,'false':False,'1':True,'0':False})
    require(mapped.notna().all(),'Invalid Boolean value in source table')
    return mapped.astype(bool)

def load_config(path):
    c=json.loads(Path(path).read_text(encoding='utf-8'))
    require(2000<=c['start_year']<=c['primary_end_year']<2022<=c['end_year']<=2024,'Invalid study/version years')
    require(c['primary_threshold'] in c['coverage_thresholds'],'Primary threshold not in sensitivity thresholds')
    require(c['cohort_analysis_start_year']>=c['start_year']+5 and c['cohort_analysis_start_year']<=c['primary_end_year'],'Cohort analysis must follow its five-year label window')
    require(all(0<t<=100 for t in c['coverage_thresholds']),'Invalid coverage threshold')
    require(0<c['minimum_common_support_fraction']<=1,'Invalid common support fraction')
    require(c['spi_baseline_end']-c['spi_baseline_start']+1>=30,'SPI calibration shorter than 30 years')
    require(c['spi_minimum_baseline_samples_per_calendar_month']>=30,'SPI sample gate must be at least 30')
    require(c['recovery_spi_scale'] in c['spi_scales'],'Recovery SPI scale unavailable')
    require(c['recovery_confirmation_months']>=2 and c['recovery_baseline_months']>=1,'Invalid recovery window')
    require(c['recovery_tolerance_fraction']>=0,'Negative recovery tolerance')
    require(len(set(c['coverage_thresholds']))==len(c['coverage_thresholds']),'Duplicate thresholds')
    require(all(isinstance(s,int) and s>0 for s in c['spi_scales']),'Invalid SPI scale')
    require(c['drought_onset_spi']<c['drought_end_spi'],'Drought thresholds are reversed')
    require(c['cv_gap_months']>=0 and c['monthly_hac_lags']>=0 and c['annual_hac_lags']>=0,'Negative calendar lag')
    require(c['validation_bootstrap_replicates']>=1,'Bootstrap replicates must be positive')
    require(c['validation_samples_per_district_class_period']>=c['validation_minimum_verified_samples_per_stratum']>=1,'Validation sampling target too small')
    require(c['recovery_horizon_months']>=c['recovery_confirmation_months']-1,'Recovery confirmation exceeds horizon')
    return c

def preflight(root, config, verify_hashes=True):
    root=Path(root)
    raw=root/'NW_Bangladesh_2000_2024'
    prep=root/'NW_Bangladesh_preprocessed'
    require(raw.is_dir() and prep.is_dir(),'Raw/preprocessed folders missing; run preprocessing first')
    m=pd.read_csv(prep/'monthly_analysis_table.csv')
    require(set(m.region)==set(REGIONS),'Unexpected/missing regions')
    require(len(m)==1200 and not m.duplicated(['region','year','month']).any(),'Monthly records missing or duplicated')
    expected={(r,y,n) for r in REGIONS for y in range(2000,2025) for n in range(1,13)}
    require(set(zip(m.region,m.year,m.month))==expected,'Incorrect monthly period roster')
    require((m.period==m.year.astype(str)+'-'+m.month.astype(str).str.zfill(2)).all(),'Period labels disagree with year/month')
    for col in ['coverage_pct','fixed_annual_everwater_coverage_pct','chirps_spatial_coverage_pct','era5_spatial_coverage_pct_min_across_variables']:
        require(m[col].between(0,100+1e-6).all(),f'Invalid {col}')
    require(m.loc[m.observed_pixels==0,'observed_water_area_km2'].isna().all(),'No-observation month was replaced with water area')
    require(np.allclose(m.observed_area_km2+m.unobserved_area_km2,m.raster_domain_area_km2),'Observation areas do not reconcile')
    require((m.chirps_rainfall_mm>=0).all(),'Negative/missing CHIRPS precipitation')
    for col in ['era5_temperature_c','era5_evaporation_demand_mm_sign_reversed']:
        require(np.isfinite(m[col]).all(),f'Nonfinite climate variable: {col}')
    inv=pd.read_csv(raw/'core_source_inventory_v2_2000_2024.csv')
    expected_inv={(kind,y,n) for y in range(2000,2025) for kind in ['JRC_ANNUAL','JRC_MONTHLY','CHIRPS_PENTAD','ERA5_LAND_MONTHLY'] for n in ([0] if kind=='JRC_ANNUAL' else range(1,13))}
    require(len(inv)==925 and set(zip(inv.dataset,inv.year,inv.month))==expected_inv,'Source inventory periods missing/duplicated')
    require((inv.period_count_ok==1).all() and (inv.actual_images==inv.expected_images).all() and (inv.unique_period_keys==inv.expected_images).all(),'Source inventory failed')
    checked=0
    if verify_hashes:
        manifest=pd.read_csv(prep/'input_manifest.csv')
        require(len(manifest)==129 and not manifest.filename.duplicated().any(),'Incomplete source manifest')
        for row in manifest.itertuples():
            p=raw/row.filename
            require(p.is_file() and digest(p)==row.sha256_after,f'Source changed since preprocessing: {row.filename}')
            checked+=1
    require((prep/'fixed_annual_everwater_footprint.tif').is_file(),'Fixed QC footprint missing')
    return m, {'status':'PASS','monthly_records':len(m),'raw_hashes_checked':checked,
               'baseline_present':(root/'NW_Bangladesh_climate_baseline_1981_1999').is_dir(),
               'reference_labels_present':(root/'validation/reference_labels.csv').is_file()}

def month_number(year, month):
    return np.asarray(year,dtype=int)*12+np.asarray(month,dtype=int)-1

def calendar_hac_covariance(x, residuals, clock, maxlags):
    """Bartlett HAC using actual calendar distances, never compressed gap rows."""
    x=np.asarray(x,float); e=np.asarray(residuals,float); clock=np.asarray(clock,int)
    n,p=x.shape
    require(len(e)==n and len(clock)==n and maxlags>=0,'Invalid covariance dimensions/lags')
    require(n>p and len(np.unique(clock))==n,'Invalid regression time axis')
    require(np.all(np.diff(clock)>0),'Regression clock must be strictly increasing')
    scores=x*e[:,None]
    meat=scores.T@scores
    location={t:i for i,t in enumerate(clock)}
    for lag in range(1,maxlags+1):
        left=[]; right=[]
        for i,t in enumerate(clock):
            if t-lag in location: left.append(i); right.append(location[t-lag])
        if left:
            cross=scores[left].T@scores[right]
            meat+=(1-lag/(maxlags+1))*(cross+cross.T)
    bread=np.linalg.inv(x.T@x)
    return bread@meat@bread*(n/(n-p))

def fit_linear(features, response, clock, maxlags):
    names=list(features.columns)
    values=features.to_numpy(float)
    y=np.asarray(response,float)
    require(np.isfinite(values).all() and np.isfinite(y).all(),'Missing regression inputs')
    center=values.mean(axis=0); scale=values.std(axis=0)
    require((scale>1e-10).all(),'Constant regression feature')
    x=np.column_stack([np.ones(len(y)),(values-center)/scale])
    require(len(y)>x.shape[1]+3,'Too few regression observations')
    require(np.linalg.matrix_rank(x)==x.shape[1] and np.linalg.cond(x)<1e8,'Rank-deficient/unstable regression')
    beta=np.linalg.lstsq(x,y,rcond=None)[0]
    covariance=calendar_hac_covariance(x,y-x@beta,clock,maxlags)
    conversion=np.eye(len(beta)); conversion[0,1:]=-center/scale
    conversion[1:,1:]=np.diag(1/scale)
    raw_beta=conversion@beta
    raw_cov=conversion@covariance@conversion.T
    se=np.sqrt(np.maximum(0,np.diag(raw_cov)))
    degrees=len(y)-len(beta)
    critical=stats.t.ppf(.975,degrees)
    pvalues=np.full(len(beta),np.nan)
    nonzero=se>1e-14
    pvalues[nonzero]=2*stats.t.sf(abs(raw_beta[nonzero]/se[nonzero]),degrees)
    require(np.isfinite(raw_beta).all(),'Nonfinite regression result')
    return {'names':['intercept']+names,'coefficients':raw_beta,'standard_errors':se,
            'lower95':raw_beta-critical*se,'upper95':raw_beta+critical*se,'pvalues':pvalues,
            'n':len(y),'df':degrees,'predict':lambda f: np.column_stack([np.ones(len(f)),f[names].to_numpy(float)])@raw_beta}
