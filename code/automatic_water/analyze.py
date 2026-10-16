"""Analyze actual automatic_water CSV exports without fabricating reference labels.

The envelopes cover declared thresholds and unknown pixel support. They are NOT
ground-truth confidence intervals and do not account for all sensor/systematic errors.
"""
from pathlib import Path
import argparse, json, sys, uuid, re
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from scipy.special import logit
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_pipeline.common import require, digest, write_json, fit_linear, month_number, REGIONS, load_config
from research_pipeline.baseline import prepare_baseline
from research_pipeline.spatial import Grid
from research_pipeline.drought import spi_series, drought_events
from research_pipeline.models import climate_features

METHOD = 'automatic_open_water_v2'
ORBIT_RULE = 'first_6_footprints_then_months_then_scenes_lexical_v2'
GROUPS = ['all_water', 'baseline_seasonal', 'baseline_permanent']
YEARS = list(range(2015, 2025))
AREA_NAMES = ['domain_area_km2', 'sar_observed_area_km2', 'sar_m15_water_area_km2', 'sar_m17_water_area_km2', 'sar_m19_water_area_km2',
              'dw_observed_area_km2', 'dw_known_area_km2', 'dw_water_area_km2', 'jrc_observed_area_km2', 'jrc_water_area_km2',
              'sar_dw_pair_area_km2', 'sar_dw_same_area_km2', 'sar_jrc_pair_area_km2', 'sar_jrc_same_area_km2', 'dw_jrc_pair_area_km2', 'dw_jrc_same_area_km2']
FILES = [f'auto_monthly_{y}.csv' for y in YEARS] + ['auto_source_inventory.csv', 'auto_orbit_audit.csv', 'auto_scene_inventory.csv', 'auto_settings.csv']


def canonical_scene_id(sensor,value):
    """GEE Image.id may be a collection-relative index, not the full asset path.

    Resolve only recognized provider scene names. Do not change the input CSV
    or invent a date. The encoded acquisition date is checked against inventory.
    """
    prefixes={'S1':'COPERNICUS/S1_GRD/','DW':'GOOGLE/DYNAMICWORLD/V1/'}
    require(sensor in prefixes,'Unknown reference sensor')
    require(isinstance(value,str) and value.strip(),'Empty scene ID')
    prefix=prefixes[sensor];value=value.strip()
    if value.startswith('projects/earthengine-public/assets/'):
        value=value.removeprefix('projects/earthengine-public/assets/')
    index=value[len(prefix):] if value.startswith(prefix) else value
    pattern=(r'S1[A-D]_IW_GRDH_1SDV_(\d{8})T\d{6}_\d{8}T\d{6}_\d{6}_[0-9A-F]{6}_[0-9A-F]{4}'
             if sensor=='S1' else r'(\d{8})T\d{6}_\d{8}T\d{6}_T\d{2}[A-Z]{3}')
    match=re.fullmatch(pattern,index)
    require(match is not None,'Unrecognized source scene identifier: '+sensor)
    date=pd.to_datetime(match.group(1),format='%Y%m%d',errors='raise').strftime('%Y-%m-%d')
    return prefix+index,date


def same_grid_alignment(global_affine,local_affine):
    """A cropped TIFF has a different origin but must retain native cell alignment."""
    a=np.asarray(global_affine,float);b=np.asarray(local_affine,float)
    if a.shape!=(6,) or b.shape!=(6,) or not np.isfinite(a).all():return False
    if not np.allclose(a[[0,1,3,4]],b[[0,1,3,4]],rtol=0,atol=1e-12):return False
    matrix=np.array([[a[0],a[1]],[a[3],a[4]]])
    try:offset=np.linalg.solve(matrix,b[[2,5]]-a[[2,5]])
    except np.linalg.LinAlgError:return False
    return bool(np.allclose(offset,np.round(offset),rtol=0,atol=1e-5))


def validate_areas(frame):
    """Reject varying cohorts, impossible areas, duplicated months, or partial rosters."""
    f = frame.copy()
    required = set(AREA_NAMES + ['method', 'year', 'month', 'period', 'region', 'water_group', 'sar_track', 's1_images', 's1_days', 'dw_images', 'dw_days', 'jrc_images'])
    require(required.issubset(f.columns), 'Monthly CSV columns missing: ' + str(sorted(required-set(f.columns))))
    expected = {(r,g,y,m) for r in REGIONS for g in GROUPS for y in YEARS for m in range(1,13)}
    require(len(f)==1440 and set(zip(f.region,f.water_group,f.year,f.month))==expected, 'Expected exactly 1,440 unique month/region/cohort rows')
    require((f.method==METHOD).all(), 'Wrong method version')
    require((f.period==f.year.astype(str)+'-'+f.month.astype(str).str.zfill(2)).all(), 'Period/year/month mismatch')
    require(np.isfinite(f[AREA_NAMES].to_numpy(float)).all(), 'Missing/nonfinite area sums')
    require((f[AREA_NAMES]>=-1e-9).all().all(), 'Negative area')
    for name in AREA_NAMES[1:]:
        require((f[name]<=f.domain_area_km2+1e-6).all(), 'Area exceeds cohort: '+name)
    for smaller,larger in [('sar_m19_water_area_km2','sar_m17_water_area_km2'),('sar_m17_water_area_km2','sar_m15_water_area_km2'),
                           ('sar_m15_water_area_km2','sar_observed_area_km2'),('dw_water_area_km2','dw_known_area_km2'),
                           ('dw_known_area_km2','dw_observed_area_km2'),('jrc_water_area_km2','jrc_observed_area_km2')]:
        require((f[smaller]<=f[larger]+1e-6).all(), 'Non-nested support/threshold areas: '+smaller)
    for pair in ['sar_dw','sar_jrc','dw_jrc']:
        require((f[pair+'_same_area_km2']<=f[pair+'_pair_area_km2']+1e-6).all(), 'Agreement exceeds paired support')
    for (region,group),part in f.groupby(['region','water_group']):
        require(part.domain_area_km2.max()-part.domain_area_km2.min()<1e-6, 'Spatial cohort changes across months: '+region+'/'+group)
    key=['year','month','water_group']
    union=f[f.region=='All_districts'].set_index(key)[AREA_NAMES].sort_index()
    districts=f[f.region!='All_districts'].groupby(key)[AREA_NAMES].sum().sort_index()
    require(np.allclose(union,districts,rtol=1e-8,atol=1e-6), 'Union does not reconcile with three districts')
    domain=f.pivot(index=['region','year','month'],columns='water_group',values='domain_area_km2')
    require((domain.baseline_seasonal+domain.baseline_permanent<=domain.all_water+1e-6).all(), 'Initial cohorts exceed water footprint')
    for name in ['s1_images','s1_days','dw_images','dw_days','jrc_images']:
        require(np.isfinite(f[name]).all() and (f[name]>=0).all() and np.allclose(f[name],np.round(f[name])), 'Invalid scene/day counts')
    require((f.s1_days<=f.s1_images).all() and (f.dw_days<=f.dw_images).all() and (f.jrc_images==1).all(), 'Scene-day/source inventory inconsistency')
    for sensor in ['sar','dw','jrc']:
        count='s1_days' if sensor=='sar' else ('dw_days' if sensor=='dw' else 'jrc_images')
        limit=2 if sensor!='jrc' else 1
        require((f.loc[f[count]<limit,sensor+'_observed_area_km2']<=1e-9).all(), 'Unsupported observations represented as valid '+sensor)
    return f.sort_values(['region','water_group','year','month']).reset_index(drop=True)


def audit_downloads(folder):
    missing=[name for name in FILES if not (folder/name).is_file()]
    require(not missing, 'NEW DOWNLOADS MISSING: '+', '.join(missing))
    extras=list(folder.glob('auto_monthly*.csv'))
    require(len(extras)==10, 'Duplicate/unexpected monthly CSVs. Keep one original export per year.')
    settings=pd.read_csv(folder/'auto_settings.csv')
    require(len(settings)==1, 'Settings must have one row')
    s=settings.iloc[0]
    constants={'method':METHOD,'start_year':2015,'end_year':2024,'minimum_unique_days':2,'dw_confidence':.8,
               'vv_primary_db':-17,'vv_loose_db':-15,'vv_strict_db':-19,'angle_min':30,'angle_max':45,
               'agreement_cell_support':.95,'agreement_water_fraction':.8,'observations_imputed':0,
               'accuracy_status':'AUTOMATED_AGREEMENT_NOT_GROUND_TRUTH','footprint':'retrospective_annual_ever_water_2000_2024',
               'initial_classes':'strict_majority_2000_2004_all_five_observed',
               'boundary_asset':'projects/gen-lang-client-0603076418/assets/NW_Bangladesh_3districts',
               'orbit_ranking_rule':ORBIT_RULE,'orbit_proxy_max_scenes':6}
    for name,value in constants.items():
        require(name in settings and (np.isclose(float(s[name]),value) if isinstance(value,(int,float)) else s[name]==value), 'Altered/missing method setting: '+name)
    with __import__('rasterio').open(ROOT/'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif') as ds:
        affine=[ds.transform.a,ds.transform.b,ds.transform.c,ds.transform.d,ds.transform.e,ds.transform.f]
        require(str(ds.crs)==s.analysis_crs and same_grid_alignment(json.loads(s.analysis_transform),affine), 'Analysis grid differs from the audited local export grid')
    require(s.source_jrc_crs=='EPSG:4326' and np.isfinite(s.source_jrc_nominal_scale_m) and 29<=s.source_jrc_nominal_scale_m<=31, 'Source projection metadata missing or unexpected')
    parts=[]
    for year in YEARS:
        part=pd.read_csv(folder/f'auto_monthly_{year}.csv')
        require(len(part)==144 and (part.year==year).all(), 'Incomplete/wrong yearly export: '+str(year))
        parts.append(part)
    frame=validate_areas(pd.concat(parts,ignore_index=True))
    require((frame.sar_track==s.sar_track).all(), 'Radar orbit changes between rows')
    inv=pd.read_csv(folder/'auto_source_inventory.csv')
    expected={('JRC_ANNUAL',y,0) for y in range(2000,2025)}|{(k,y,m) for k in ['S1','DW','JRC_MONTHLY'] for y in YEARS for m in range(1,13)}
    require(len(inv)==385 and set(zip(inv.dataset,inv.year,inv.month))==expected, 'Incomplete/duplicate source inventory')
    require(np.isfinite(inv.actual_images).all() and (inv.actual_images>=0).all() and np.allclose(inv.actual_images,np.round(inv.actual_images)), 'Invalid source counts')
    require((inv.loc[inv.dataset.str.startswith('JRC'),'actual_images']==1).all(), 'JRC source missing or duplicated')
    assets={'S1':'COPERNICUS/S1_GRD','DW':'GOOGLE/DYNAMICWORLD/V1'}
    for r in inv.itertuples():
        if r.dataset in assets: asset=assets[r.dataset]
        elif r.dataset=='JRC_MONTHLY': asset='JRC/GSW1_4/MonthlyHistory' if r.year<2022 else 'projects/JRC/GSW1_5/MonthlyHistory_2022_2024'
        else: asset='JRC/GSW1_4/YearlyHistory' if r.year<2016 else ('projects/global-surface-water/assets/GSW1_5/YearlyHistory_2016_2021' if r.year<2022 else 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2022_2024')
        require(r.asset==asset, 'Wrong source asset: '+r.dataset)
    orbit=pd.read_csv(folder/'auto_orbit_audit.csv')
    require(len(orbit)>0 and orbit.track.nunique()==len(orbit) and np.isfinite(orbit.rank_score).all(), 'Invalid orbit audit')
    chosen=orbit[orbit.track==s.sar_track]
    require(len(chosen)==1 and s.sar_track==orbit.sort_values(['rank_score','track']).iloc[-1].track, 'Chosen orbit violates declared outcome-blind ranking/tie rule')
    require(orbit.footprint_proxy_fraction.between(0,1+1e-8).all() and orbit.months_with_any_scene.between(0,120).all(), 'Invalid orbit footprint-proxy audit')
    require((orbit.ranking_rule==ORBIT_RULE).all() and (orbit.representative_scenes==orbit.scene_count.clip(upper=6)).all(), 'Wrong orbit proxy method/representative scene count')
    q=orbit.quantized_footprint_proxy
    require(q.between(0,1000).all() and np.allclose(q,np.round(q)), 'Invalid proxy quantization')
    require(((orbit.footprint_proxy_fraction>=q/1000-1e-12)&(orbit.footprint_proxy_fraction<=(q+1)/1000+1e-12)).all(), 'Proxy fraction and exported quantization disagree')
    expected_scores=q*1e9+orbit.months_with_any_scene*1e6+orbit.scene_count
    require(np.allclose(orbit.rank_score,expected_scores,rtol=0,atol=1e-3), 'Orbit ranking score does not match declared rule')
    expected_keys=orbit.apply(lambda r:f'{int(round(r.rank_score)):016d}_{r.track}',axis=1)
    require((orbit.sort_key==expected_keys).all(),'Orbit deterministic tie-break key mismatch')
    sar_inv=inv[inv.dataset=='S1']
    require(chosen.scene_count.iloc[0]==sar_inv.actual_images.sum() and chosen.months_with_any_scene.iloc[0]==(sar_inv.actual_images>0).sum(), 'Chosen orbit audit disagrees with monthly inventory')
    scenes=pd.read_csv(folder/'auto_scene_inventory.csv')
    require(set(scenes.sensor).issubset({'S1','DW'}) and not scenes.duplicated(['sensor','scene_id']).any(), 'Invalid or duplicate scene IDs')
    dates=pd.to_datetime(scenes.date,format='%Y-%m-%d',errors='raise')
    require(dates.notna().all() and (dates.dt.year==scenes.year).all() and (dates.dt.month==scenes.month).all() and scenes.year.between(2015,2024).all(), 'Scene date outside declared month/record')
    require((scenes.loc[scenes.sensor=='S1','track']==s.sar_track).all(), 'Scene inventory mixes radar tracks')
    resolved=[canonical_scene_id(r.sensor,r.scene_id) for r in scenes.itertuples()]
    require(all(date==r.date for r,(_,date) in zip(scenes.itertuples(),resolved)), 'Encoded scene acquisition date disagrees with inventory')
    canonical=[asset for asset,_ in resolved]
    require(len(canonical)==len(set(canonical)), 'Duplicate scene represented by relative and full asset IDs')
    for r in inv[inv.dataset.isin(['S1','DW'])].itertuples():
        part=scenes[(scenes.sensor==r.dataset)&(scenes.year==r.year)&(scenes.month==r.month)]
        require(len(part)==r.actual_images and part.date.nunique()==r.unique_days, 'Scene inventory count/date mismatch')
        f=frame[(frame.year==r.year)&(frame.month==r.month)]
        image_col='s1_images' if r.dataset=='S1' else 'dw_images';day_col='s1_days' if r.dataset=='S1' else 'dw_days'
        require((f[image_col]==r.actual_images).all() and (f[day_col]==r.unique_days).all(), 'Monthly statistics use inconsistent scene inventory')
    hashes=[{'filename':name,'bytes':(folder/name).stat().st_size,'sha256':digest(folder/name)} for name in FILES]
    return frame,settings,hashes


def add_envelopes(frame):
    f=frame.copy();d=f.domain_area_km2.replace(0,np.nan)
    f['sar_coverage_fraction']=f.sar_observed_area_km2/d
    f['radar_envelope_lower_fraction']=f.sar_m19_water_area_km2/d
    f['radar_envelope_upper_fraction']=(f.sar_m15_water_area_km2+(f.domain_area_km2-f.sar_observed_area_km2).clip(lower=0))/d
    f['eligible_for_recovery']=d.notna()&f.sar_coverage_fraction.ge(.95-1e-8)
    f['dw_classification_coverage_fraction']=f.dw_known_area_km2/d
    f['dw_envelope_lower_fraction']=f.dw_water_area_km2/d
    f['dw_envelope_upper_fraction']=(f.dw_water_area_km2+(f.domain_area_km2-f.dw_known_area_km2).clip(lower=0))/d
    for pair in ['sar_dw','sar_jrc','dw_jrc']:
        f[pair+'_conditional_agreement']=f[pair+'_same_area_km2']/f[pair+'_pair_area_km2'].replace(0,np.nan)
        f[pair+'_paired_footprint_fraction']=f[pair+'_pair_area_km2']/d
    return f


def observation_quality(frame):
    """Separate complete file/metadata exports from adequate analytical support."""
    f=add_envelopes(frame) if 'eligible_for_recovery' not in frame else frame
    union=f[(f.region=='All_districts')&(f.water_group=='all_water')].sort_values(['year','month'])
    optical=bool((union.dw_known_area_km2>1e-9).any())
    paired=bool((union.sar_dw_pair_area_km2>1e-9).any())
    return {'monthly_periods':len(union),'radar_eligible_months':int(union.eligible_for_recovery.sum()),
        'radar_below_support_gate_months':union.loc[~union.eligible_for_recovery,'period'].tolist(),
        'radar_no_scene_months':union.loc[union.s1_images.eq(0),'period'].tolist(),
        'dw_months_with_observed_pixels':int((union.dw_observed_area_km2>1e-9).sum()),
        'dw_months_with_classified_pixels':int((union.dw_known_area_km2>1e-9).sum()),
        'dw_months_with_no_source_scene':union.loc[union.dw_images.eq(0),'period'].tolist(),
        'dw_classification_support_available':optical,'radar_dw_comparison_support_available':paired,
        'ready_for_full_automatic_analysis':optical and paired,
        'reason':'' if optical and paired else 'No usable Dynamic World classification/paired support. This does not mean no water. Diagnose probabilities/masks/threshold implementation before claiming optical comparison.',
        'recovery_availability_requires_event_by_event_checks':True}


def anomaly_envelopes(frame,minimum_reference=5):
    f=frame.sort_values(['year','month']).copy();index=pd.PeriodIndex(f.period,freq='M')
    low=f.radar_envelope_lower_fraction.copy()
    high=f.radar_envelope_upper_fraction.copy()
    low=low.where(f.eligible_for_recovery);high=high.where(f.eligible_for_recovery)
    ref=pd.DataFrame({'month':f.month,'lo':low,'hi':high,'year':f.year})
    ref=ref[ref.year.between(2015,2021)].groupby('month').agg(lower=('lo','mean'),upper=('hi','mean'),n=('lo','count'))
    adequate=f.month.map(ref.n).ge(minimum_reference)
    lo=(low-f.month.map(ref.upper)).where(adequate)
    hi=(high-f.month.map(ref.lower)).where(adequate)
    return pd.Series(lo.to_numpy(),index=index),pd.Series(hi.to_numpy(),index=index),ref


def interval_recovery(event,lower,upper,tolerance=.02,horizon=24,baseline_months=3,confirmation=2):
    """Possible/confirmed timing interval within the specified method envelope.

    No scalar duration unless both endpoints coincide. Missing followup censors
    the event; a timing interval is not an independently verified physical truth.
    """
    onset=event['onset_period'];end=event.get('end_period')
    result={'onset_period':str(onset),'climate_end_period':str(end) if end is not None else '',
            'minimum_spi':event['minimum_spi'],'status':event['status'],
            'recovery_min_months':np.nan,'recovery_max_months':np.nan,'recovery_months':np.nan}
    if event['left_censored']:result['status']='ONSET_LEFT_CENSORED';return result
    if end is None:return result
    pre=pd.period_range(onset-baseline_months,onset-1,freq='M')
    phase=pd.period_range(onset,end,freq='M')
    prelo=lower.reindex(pre);prehi=upper.reindex(pre)
    if prelo.isna().any() or prehi.isna().any():result['status']='PRE_EVENT_SUPPORT_OR_REFERENCE_GAP';return result
    plo=lower.reindex(phase);phi=upper.reindex(phase)
    if plo.isna().any() or phi.isna().any():result['status']='DROUGHT_SUPPORT_OR_REFERENCE_GAP';return result
    beforelo=float(prelo.mean());beforehi=float(prehi.mean())
    # Drought-phase deficit excludes the first non-drought climate-end month.
    affectedhi=phi.iloc[:-1];affectedlo=plo.iloc[:-1]
    if len(affectedhi)==0:result['status']='NO_DROUGHT_PHASE';return result
    deficitlo=beforelo-float(affectedhi.min());deficithi=beforehi-float(affectedlo.min())
    result.update(pre_event_lower_anomaly=beforelo,pre_event_upper_anomaly=beforehi,deficit_lower=deficitlo,deficit_upper=deficithi)
    if deficithi<=tolerance:result['status']='NO_DETECTABLE_DEFICIT_WITHIN_ENVELOPE';return result
    if deficitlo<=tolerance:result['status']='DEFICIT_UNCERTAIN_WITHIN_ENVELOPE';return result
    possible_run=confirmed_run=0;earliest=None
    for offset in range(horizon+1):
        date=end+offset
        if date not in lower.index:result['status']='FOLLOWUP_STUDY_END_CENSORED';return result
        lo=lower.get(date,np.nan);hi=upper.get(date,np.nan)
        if not np.isfinite([lo,hi]).all():result['status']='FOLLOWUP_SUPPORT_OR_REFERENCE_GAP_CENSORED';return result
        possible_run=possible_run+1 if hi>=beforelo-tolerance else 0
        confirmed_run=confirmed_run+1 if lo>=beforehi-tolerance else 0
        if possible_run>=confirmation and earliest is None:earliest=offset-confirmation+1
        if confirmed_run>=confirmation:
            latest=offset-confirmation+1
            require(earliest is not None and earliest<=latest,'Timing interval inconsistency')
            result.update(recovery_min_months=earliest,recovery_max_months=latest,
                recovery_months=latest if earliest==latest else np.nan,
                status='TIMING_STABLE_WITHIN_ENVELOPE' if earliest==latest else 'TIMING_INTERVAL_WITHIN_ENVELOPE')
            return result
    result['status']='TIMING_NOT_RESOLVED_WITHIN_HORIZON';return result


def climate_and_spi(out):
    climate=pd.read_csv(ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv')
    expected={(r,y,m) for r in REGIONS for y in range(2000,2025) for m in range(1,13)}
    require(len(climate)==1200 and set(zip(climate.region,climate.year,climate.month))==expected,'Incomplete real study climate table')
    require((climate.period==climate.year.astype(str)+'-'+climate.month.astype(str).str.zfill(2)).all(),'Climate period labels disagree')
    columns=['chirps_rainfall_mm','era5_temperature_c','era5_evaporation_demand_mm_sign_reversed']
    require(np.isfinite(climate[columns].to_numpy()).all() and (climate.chirps_rainfall_mm>=0).all(),'Incomplete/invalid real climate values')
    baseline,check=prepare_baseline(ROOT,Grid(ROOT),out)
    require(baseline is not None and check['status']=='PASS','Real 1981-1999 baseline calibration inputs required')
    combined=pd.concat([baseline,climate],ignore_index=True);rows=[];calibration=[]
    for region,part in combined.groupby('region'):
        part=part.sort_values(['year','month']);index=pd.PeriodIndex(part.period,freq='M')
        require(len(part)==528 and not index.duplicated().any(), '1981-2024 climate history incomplete')
        for scale in [3,6]:
            spi,params=spi_series(part.chirps_rainfall_mm,index,scale,1981,2020)
            require((params.status=='PASS').all(),'SPI calibration failed')
            params['region']=region;calibration.append(params)
            for period,value in spi[spi.index.year>=2000].items():rows.append({'region':region,'scale_months':scale,'period':str(period),'spi':value})
    result=pd.DataFrame(rows);result.to_csv(out/'spi_indices.csv',index=False)
    pd.concat(calibration,ignore_index=True).to_csv(out/'spi_calibration_parameters.csv',index=False)
    require(len(result)==2400 and result.spi.notna().all(),'Incomplete empirical SPI results')
    return climate,result


def fit_envelope_models(frame,climate,out):
    merged=frame.merge(climate_features(climate),on=['region','year','month','period'],validate='many_to_one')
    features=['time_years','season_sin','season_cos','rain_3m_mm','era5_temperature_c','era5_evaporation_demand_mm_sign_reversed']
    records=[]
    for (region,group),part in merged.groupby(['region','water_group']):
        f=part[part.eligible_for_recovery].dropna(subset=features).sort_values(['year','month']).copy()
        selected=features.copy()
        if f.sar_coverage_fraction.std()>1e-10:selected.append('sar_coverage_fraction')
        if f.s1_days.std()>1e-10:selected.append('s1_days')
        for bound in ['lower','upper']:
            row={'region':region,'water_group':group,'envelope_endpoint':bound,'n':len(f),'status':'INSUFFICIENT_OBSERVED_MONTHS',
                 'interpretation':'Exploratory regression of method-envelope endpoints; not observed ground-truth trend or causal attribution.'}
            if len(f)>=48:
                try:
                    fit=fit_linear(f[selected],logit(f['radar_envelope_'+bound+'_fraction'].clip(1e-6,1-1e-6)),month_number(f.year,f.month),12)
                    i=fit['names'].index('time_years')
                    row.update(status='PASS',time_coefficient_logit_per_year=fit['coefficients'][i],lower95=fit['lower95'][i],upper95=fit['upper95'][i],p_value=fit['pvalues'][i])
                except ValueError as error:row.update(status='MODEL_REJECTED',reason=str(error))
            records.append(row)
    models=pd.DataFrame(records);models['p_adjusted_BY_district_family']=np.nan
    if 'p_value' in models:
        for bound in ['lower','upper']:
            ids=models[(models.envelope_endpoint==bound)&(models.region!='All_districts')&models.p_value.notna()].index
            if len(ids):models.loc[ids,'p_adjusted_BY_district_family']=multipletests(models.loc[ids,'p_value'],method='fdr_by')[1]
    models.to_csv(out/'exploratory_climate_envelope_models.csv',index=False)
    return models


def make_figures(frame,events,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory=out/'Figures';directory.mkdir()
    fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True,constrained_layout=True)
    for ax,group in zip(axes,GROUPS):
        f=frame[(frame.region=='All_districts')&(frame.water_group==group)].sort_values(['year','month']);date=pd.to_datetime(f.period)
        lower=f.radar_envelope_lower_fraction.where(f.eligible_for_recovery)*f.domain_area_km2
        upper=f.radar_envelope_upper_fraction.where(f.eligible_for_recovery)*f.domain_area_km2
        ax.fill_between(date,lower,upper,color='#4382a7',alpha=.4)
        ax.set_title(group.replace('_',' '));ax.set_ylabel('Method-envelope area (km²)');ax.grid(alpha=.15)
    fig.suptitle('Automated radar threshold/support envelopes — not ground-truth confidence intervals')
    fig.savefig(directory/'01_automated_water_envelopes.png',dpi=200);fig.savefig(directory/'01_automated_water_envelopes.svg');plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,constrained_layout=True)
    f=frame[(frame.region=='All_districts')&(frame.water_group=='all_water')].sort_values(['year','month']);date=pd.to_datetime(f.period)
    for pair in ['sar_dw','sar_jrc','dw_jrc']:
        axes[0].plot(date,f[pair+'_conditional_agreement'],label=pair.replace('_',' / '))
        axes[1].plot(date,f[pair+'_paired_footprint_fraction'],label=pair.replace('_',' / '))
    for ax in axes:ax.set_ylim(0,1.03);ax.grid(alpha=.15);ax.legend(ncol=3)
    axes[0].set_ylabel('Conditional agreement');axes[1].set_ylabel('Paired footprint fraction')
    fig.suptitle('Agreement and retained support must be read together; neither is verified accuracy')
    fig.savefig(directory/'02_sensor_agreement_and_support.png',dpi=200);fig.savefig(directory/'02_sensor_agreement_and_support.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,6),constrained_layout=True)
    counts=events.status.value_counts().sort_values();ax.barh(counts.index,counts.values,color='#4382a7');ax.set_xlabel('Event-cohort records (overlapping union included)')
    ax.set_title('Recovery support and method-envelope identifiability')
    fig.savefig(directory/'03_recovery_status.png',dpi=200);fig.savefig(directory/'03_recovery_status.svg');plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'NW_Bangladesh_automatic_water_2015_2024')
    parser.add_argument('--output',type=Path);parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    if args.preflight:
        frame,settings,hashes=audit_downloads(args.input.resolve())
        print('DOWNLOAD/METADATA PASS: 14 CSV exports, 1440 rows, source dates, fixed areas, grid, orbit, and support reconciled.')
        quality=observation_quality(frame)
        print(json.dumps(quality,indent=2))
        require(quality['ready_for_full_automatic_analysis'],'OBSERVATION QUALITY BLOCKED: '+quality['reason']);return
    now=datetime.now(timezone(timedelta(hours=6)))
    out=args.output.resolve() if args.output else ROOT/'automatic_water_outputs'/('run_'+now.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    require(not out.exists(),'Output exists; use a fresh directory');out.mkdir(parents=True)
    state={'method':METHOD,'software_run_complete':False,'human_verified_accuracy':False,'scientific_publication_ready':False,
           'observations_imputed':False,'reference_labels_generated':False,'output':str(out)}
    try:
        frame,settings,hashes=audit_downloads(args.input.resolve());pd.DataFrame(hashes).to_csv(out/'input_sha256.csv',index=False)
        settings.to_csv(out/'downloaded_method_settings.csv',index=False)
        frame=add_envelopes(frame);frame.to_csv(out/'monthly_automated_evidence.csv',index=False)
        quality=observation_quality(frame);write_json(out/'OBSERVATION_QUALITY.json',quality)
        state.update(download_metadata_audit_passed=True,observation_quality=quality)
        require(quality['ready_for_full_automatic_analysis'],'OBSERVATION QUALITY BLOCKED: '+quality['reason'])
        used=[ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv',ROOT/'NW_Bangladesh_preprocessed/fixed_annual_everwater_footprint.tif',
              ROOT/'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif',ROOT/'NW_Bangladesh_2000_2024/verified_study_area.geojson',
              ROOT/'NW_Bangladesh_climate_baseline_1981_1999/baseline_source_inventory.csv']
        used+=sorted((ROOT/'NW_Bangladesh_climate_baseline_1981_1999').glob('*.tif'))
        require(len(used)==43 and all(p.is_file() for p in used),'Real climate/grid source files missing or duplicated')
        climate_hashes=[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in used]
        pd.DataFrame(climate_hashes).to_csv(out/'climate_and_grid_input_sha256.csv',index=False)
        climate,spi=climate_and_spi(out);records=[];references=[]
        for (region,group),part in frame.groupby(['region','water_group']):
            lower,upper,reference=anomaly_envelopes(part)
            reference['region']=region;reference['water_group']=group;references.append(reference.reset_index())
            rain=spi[(spi.region==region)&(spi.scale_months==3)]
            series=pd.Series(rain.spi.to_numpy(),index=pd.PeriodIndex(rain.period,freq='M'))
            series=series[series.index.year>=2015]
            for event in drought_events(series):
                records.append({'region':region,'water_group':group,**interval_recovery(event,lower,upper)})
        event_columns=['region','water_group','onset_period','climate_end_period','minimum_spi','status','recovery_min_months','recovery_max_months','recovery_months',
                       'pre_event_lower_anomaly','pre_event_upper_anomaly','deficit_lower','deficit_upper']
        events=pd.DataFrame(records,columns=event_columns);events.to_csv(out/'automated_recovery_intervals.csv',index=False)
        pd.concat(references,ignore_index=True).to_csv(out/'water_seasonal_reference_support.csv',index=False)
        models=fit_envelope_models(frame,climate,out);make_figures(frame,events,out)
        stable=int((events.status=='TIMING_STABLE_WITHIN_ENVELOPE').sum());intervals=int((events.status=='TIMING_INTERVAL_WITHIN_ENVELOPE').sum())
        state.update(software_run_complete=True,actual_export_rows=len(frame),recovery_event_cohort_records=len(events),
                     method_stable_timing_records=stable,method_interval_timing_records=intervals,
                     note='Timing endpoints concern specified automated-method envelopes; they are not independently validated recovery times.')
        report=f'''# স্বয়ংক্রিয় গবেষণার ফল

আসল downloaded CSV থেকে হিসাব হয়েছে। হাতে reference label তৈরি করা হয়নি।

- মাসিক হিসাব: {len(frame)} row; ২০১৫–২০২৪, তিন জেলা ও overlapping union, তিনটি fixed cohort।
- ঘোষিত threshold/অজানা জায়গার সীমার মধ্যে এক মাসে মেলা recovery সময়: {stable}টি event-cohort record।
- একই সীমার মধ্যে recovery সময়ের range: {intervals}টি record।
- বাকি ঘটনাগুলোর সময় নির্ভরযোগ্যভাবে নির্ধারণ হয়নি; কারণ `automated_recovery_intervals.csv`-এ।

**এগুলো automated model-এর হিসাব। Verified accuracy, ground truth বা ১০০% নিশ্চয়তা নয়।**
একই satellite input থেকে তৈরি optical ফল পুরোপুরি স্বাধীন নয়। Agreement শুধু দুই method একই কথা বলছে কি না দেখায়।
মাসিক median নির্দিষ্ট দিনের পানি নয়। Radar open-water estimate ধানক্ষেত/ভেজা মাটি/গাছের নিচের পানিতে ভুল করতে পারে।
Envelope কেবল ঘোষিত threshold ও missing-support extremes ধরে; sensor-এর সব ভুল এই range-এর মধ্যে থাকার নিশ্চয়তা নেই।

Graphs: `Figures`। মাসিক মিলের সঙ্গে paired-footprint fraction-ও দেখুন; uncertain জায়গা বাদ দিলে agreement বেশি দেখাতে পারে।
Climate regression-এর interval-endpoint coefficients exploratory association; pumping-এর কারণ বা true-water trend নয়।
Annual JRC-এর ২০১৬ সংশোধন এবং ২০২২ Collection transition আগের report-এর সীমাসহ বহাল আছে।
এই নতুন ফল পুরোনো annual trend report-কে overwrite বা পুরো গবেষণাকে submission-ready করে না।
'''
        (out/'RESULT_BN.md').write_text(report,encoding='utf-8')
        # All exported inputs must still match after analysis.
        for item in hashes:require(digest(args.input/item['filename'])==item['sha256'],'Downloaded CSV changed during analysis')
        for item in climate_hashes:require(digest(ROOT/item['path'])==item['sha256'],'Climate/grid source changed during analysis')
        write_json(out/'STATUS.json',state);print('COMPLETE:',out/'RESULT_BN.md')
    except Exception as error:
        state.update(error_type=type(error).__name__,error=str(error));write_json(out/'STATUS.json',state)
        (out/'RUN_ERROR.txt').write_text(str(error),encoding='utf-8');raise


if __name__=='__main__':main()
