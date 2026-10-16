"""Temporary numerical fixtures test algorithms, never act as study/reference data."""
import numpy as np
import pandas as pd
import pytest
from automatic_water.analyze import AREA_NAMES, GROUPS, REGIONS, METHOD, validate_areas, add_envelopes, interval_recovery, anomaly_envelopes, same_grid_alignment, canonical_scene_id, observation_quality


def roster():
    rows=[]
    for year in range(2015,2025):
        for month in range(1,13):
            for region in REGIONS:
                for group in GROUPS:
                    domain=(30 if region=='All_districts' else 10)*(1 if group=='all_water' else .3)
                    r={name:0. for name in AREA_NAMES}
                    r.update(domain_area_km2=domain,method=METHOD,year=year,month=month,period=f'{year}-{month:02}',region=region,water_group=group,
                        sar_track='DESCENDING_1',s1_images=0,s1_days=0,dw_images=0,dw_days=0,jrc_images=1)
                    rows.append(r)
    return pd.DataFrame(rows)


def test_cropped_native_grid_origin_is_allowed_but_half_cell_shift_is_not():
    original=[.01,0,-180,0,-.01,90]
    cropped=[.01,0,88,0,-.01,25]
    assert same_grid_alignment(original,cropped)
    cropped[2]+=.005
    assert not same_grid_alignment(original,cropped)


def test_zero_observations_remain_unknown_not_dry_water_fraction():
    frame=add_envelopes(validate_areas(roster()))
    assert (frame.radar_envelope_lower_fraction==0).all()
    assert (frame.radar_envelope_upper_fraction==1).all()
    assert not frame.eligible_for_recovery.any()
    assert frame.sar_dw_conditional_agreement.isna().all()


@pytest.mark.parametrize('problem',['duplicate','changing_cohort','impossible_water','observations_without_days'])
def test_invalid_exports_are_rejected(problem):
    frame=roster()
    if problem=='duplicate':frame=pd.concat([frame,frame.iloc[[0]]],ignore_index=True)
    elif problem=='changing_cohort':frame.loc[0,'domain_area_km2']+=1
    elif problem=='impossible_water':frame.loc[0,'sar_m17_water_area_km2']=2
    else:frame.loc[0,'sar_observed_area_km2']=1
    with pytest.raises(ValueError):validate_areas(frame)


def event_and_water():
    dates=pd.period_range('2017-01','2017-12',freq='M')
    values=pd.Series([0,0,0,-.2,-.2,-.2,-.2,0,0,0,0,0],index=dates,dtype=float)
    event={'onset_period':pd.Period('2017-04',freq='M'),'end_period':pd.Period('2017-06',freq='M'),
           'minimum_spi':-1.5,'left_censored':False,'status':'CLIMATE_EPISODE_COMPLETE'}
    return event,values


def test_exact_recovery_only_when_interval_endpoints_coincide():
    event,water=event_and_water();r=interval_recovery(event,water,water)
    assert r['status']=='TIMING_STABLE_WITHIN_ENVELOPE'
    assert r['recovery_months']==r['recovery_min_months']==r['recovery_max_months']==2


def test_ambiguous_recovery_reports_range_not_invented_scalar():
    event,lower=event_and_water();upper=lower.copy()
    upper.loc['2017-06':'2017-07']=0
    r=interval_recovery(event,lower,upper)
    assert r['status']=='TIMING_INTERVAL_WITHIN_ENVELOPE'
    assert r['recovery_min_months']==0 and r['recovery_max_months']==2
    assert np.isnan(r['recovery_months'])


@pytest.mark.parametrize('missing,status',[('2017-03','PRE_EVENT_SUPPORT_OR_REFERENCE_GAP'),('2017-05','DROUGHT_SUPPORT_OR_REFERENCE_GAP'),('2017-07','FOLLOWUP_SUPPORT_OR_REFERENCE_GAP_CENSORED')])
def test_missing_month_censors_without_recovery_duration(missing,status):
    event,water=event_and_water();water.loc[missing]=np.nan;r=interval_recovery(event,water,water)
    assert r['status']==status and np.isnan(r['recovery_months']) and np.isnan(r['recovery_max_months'])


def test_uncertain_deficit_does_not_generate_recovery():
    event,lower=event_and_water();upper=lower.copy();upper.loc['2017-04':'2017-05']=0
    r=interval_recovery(event,lower,upper)
    assert r['status']=='DEFICIT_UNCERTAIN_WITHIN_ENVELOPE' and np.isnan(r['recovery_months'])


def test_seasonal_reference_adequacy_is_not_replaced_by_filled_months():
    part=add_envelopes(roster());part=part[(part.region=='Naogaon')&(part.water_group=='all_water')].copy()
    part['eligible_for_recovery']=True;part['radar_envelope_lower_fraction']=.3;part['radar_envelope_upper_fraction']=.4
    part.loc[(part.month==6)&part.year.le(2017),'eligible_for_recovery']=False
    lo,hi,ref=anomaly_envelopes(part)
    assert ref.loc[6,'n']==4
    assert lo[lo.index.month==6].isna().all() and hi[hi.index.month==6].isna().all()
    assert np.allclose(lo[lo.index.month==7],-.1) and np.allclose(hi[hi.index.month==7],.1)


def export_fixture(tmp_path,monkeypatch):
    """Temporary CSV/GeoTIFF schema fixtures, not downloaded/reference evidence."""
    import json,rasterio
    from rasterio.transform import Affine
    import automatic_water.analyze as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    raw=tmp_path/'NW_Bangladesh_2000_2024';raw.mkdir()
    affine=[.00026949458523585647,0,0,0,-.00026949458523585647,0]
    with rasterio.open(raw/'jrc_monthly_2000.tif','w',driver='GTiff',height=1,width=1,count=1,dtype='uint8',crs='EPSG:4326',transform=Affine(*affine)) as ds:
        ds.write(np.zeros((1,1),dtype='uint8'),1)
    folder=tmp_path/'exports';folder.mkdir();f=roster();f['s1_images']=2;f['s1_days']=2
    for year in range(2015,2025):f[f.year==year].to_csv(folder/f'auto_monthly_{year}.csv',index=False)
    inv=[];scenes=[]
    for year in range(2000,2025):
        asset='JRC/GSW1_4/YearlyHistory' if year<2016 else ('projects/global-surface-water/assets/GSW1_5/YearlyHistory_2016_2021' if year<2022 else 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2022_2024')
        inv.append({'dataset':'JRC_ANNUAL','year':year,'month':0,'asset':asset,'actual_images':1,'unique_days':-1})
    for year in range(2015,2025):
        for month in range(1,13):
            for kind,asset,n in [('S1','COPERNICUS/S1_GRD',2),('DW','GOOGLE/DYNAMICWORLD/V1',0),('JRC_MONTHLY','JRC/GSW1_4/MonthlyHistory' if year<2022 else 'projects/JRC/GSW1_5/MonthlyHistory_2022_2024',1)]:
                inv.append({'dataset':kind,'year':year,'month':month,'asset':asset,'actual_images':n,'unique_days':n if kind!='JRC_MONTHLY' else -1})
            for day in [1,15]:scenes.append({'sensor':'S1','scene_id':f'COPERNICUS/S1_GRD/S1A_IW_GRDH_1SDV_{year}{month:02}{day:02}T000000_{year}{month:02}{day:02}T000025_000001_000001_0001',
                'date':f'{year}-{month:02}-{day:02}','year':year,'month':month,'track':'DESCENDING_1'})
    pd.DataFrame(inv).to_csv(folder/'auto_source_inventory.csv',index=False)
    pd.DataFrame(scenes).to_csv(folder/'auto_scene_inventory.csv',index=False)
    pd.DataFrame([{'track':'DESCENDING_1','footprint_proxy_fraction':1,'quantized_footprint_proxy':1000,'months_with_any_scene':120,'scene_count':240,'rank_score':1000120000240,
                   'representative_scenes':6,'ranking_rule':module.ORBIT_RULE,'sort_key':f'{1000120000240:016d}_DESCENDING_1'}]).to_csv(folder/'auto_orbit_audit.csv',index=False)
    settings={'method':METHOD,'start_year':2015,'end_year':2024,'sar_track':'DESCENDING_1','minimum_unique_days':2,'dw_confidence':.8,
        'vv_primary_db':-17,'vv_loose_db':-15,'vv_strict_db':-19,'angle_min':30,'angle_max':45,'agreement_cell_support':.95,'agreement_water_fraction':.8,
        'analysis_crs':'EPSG:4326','analysis_transform':json.dumps(affine),'source_jrc_crs':'EPSG:4326','source_jrc_nominal_scale_m':30,
        'orbit_ranking_rule':module.ORBIT_RULE,'orbit_proxy_max_scenes':6,
        'boundary_asset':'projects/gen-lang-client-0603076418/assets/NW_Bangladesh_3districts',
        'footprint':'retrospective_annual_ever_water_2000_2024','initial_classes':'strict_majority_2000_2004_all_five_observed',
        'accuracy_status':'AUTOMATED_AGREEMENT_NOT_GROUND_TRUTH','observations_imputed':0}
    pd.DataFrame([settings]).to_csv(folder/'auto_settings.csv',index=False)
    return folder,module


def test_complete_schema_audit_including_realistic_zero_optical_availability(tmp_path,monkeypatch):
    folder,module=export_fixture(tmp_path,monkeypatch)
    frame,settings,hashes=module.audit_downloads(folder)
    assert len(frame)==1440 and len(hashes)==14
    assert frame.dw_days.eq(0).all()
    assert not module.add_envelopes(frame).eligible_for_recovery.any()


@pytest.mark.parametrize('problem',['missing_file','scene_date','source_count','imputed_setting','orbit_changed','old_orbit_rule'])
def test_export_audit_rejects_corrupt_provenance_or_missing_source(tmp_path,monkeypatch,problem):
    folder,module=export_fixture(tmp_path,monkeypatch)
    if problem=='missing_file':(folder/'auto_monthly_2024.csv').rename(folder/'temporarily_missing.csv')
    else:
        name={'scene_date':'auto_scene_inventory.csv','source_count':'auto_source_inventory.csv','imputed_setting':'auto_settings.csv','orbit_changed':'auto_monthly_2015.csv','old_orbit_rule':'auto_settings.csv'}[problem]
        f=pd.read_csv(folder/name)
        if problem=='scene_date':f.loc[0,'date']='2016-01-01'
        elif problem=='source_count':f.loc[f.dataset=='S1','actual_images']=1
        elif problem=='imputed_setting':f.loc[0,'observations_imputed']=1
        elif problem=='old_orbit_rule':f.loc[0,'orbit_ranking_rule']='old_pixel_coverage_rule_v1'
        else:f.loc[0,'sar_track']='ASCENDING_2'
        f.to_csv(folder/name,index=False)
    with pytest.raises(ValueError):module.audit_downloads(folder)


@pytest.mark.parametrize('sensor,index,prefix',[
    ('S1','S1A_IW_GRDH_1SDV_20150101T000305_20150101T000330_003970_004C79_3BE7','COPERNICUS/S1_GRD/'),
    ('DW','20160101T044212_20160101T044851_T45QXG','GOOGLE/DYNAMICWORLD/V1/')])
def test_real_provider_relative_and_full_ids_resolve_to_same_asset(sensor,index,prefix):
    short=canonical_scene_id(sensor,index)
    assert short==canonical_scene_id(sensor,prefix+index)
    assert short==canonical_scene_id(sensor,'projects/earthengine-public/assets/'+prefix+index)
    assert short[1]==('2015-01-01' if sensor=='S1' else '2016-01-01')


@pytest.mark.parametrize('sensor,value',[('S1','GOOGLE/DYNAMICWORLD/V1/20160101T044212_20160101T044851_T45QXG'),('DW','arbitrary_label'),('S1','')])
def test_unrelated_or_absent_provenance_is_not_accepted(sensor,value):
    with pytest.raises(ValueError):canonical_scene_id(sensor,value)


def test_file_roster_completeness_does_not_imply_classification_or_comparison_readiness():
    f=roster();f['s1_images']=f['s1_days']=3;f['dw_images']=f['dw_days']=3
    f['sar_observed_area_km2']=f.domain_area_km2
    f['dw_observed_area_km2']=f.domain_area_km2
    result=observation_quality(f)
    assert result['radar_eligible_months']==120 and result['dw_months_with_observed_pixels']==120
    assert result['dw_months_with_classified_pixels']==0
    assert not result['ready_for_full_automatic_analysis']
