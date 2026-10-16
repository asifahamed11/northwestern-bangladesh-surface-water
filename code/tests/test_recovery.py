"""Artificial unit vectors exercise censoring; no synthetic research results."""
import numpy as np
import pandas as pd
import pytest
from research_pipeline.drought import drought_events,recovery_event,run_drought
from research_pipeline.common import ROOT,load_config

@pytest.fixture
def setup_event():
    idx=pd.period_range('2000-01','2001-12',freq='M')
    water=pd.Series(0.,index=idx); water.loc['2000-05':'2000-08']=-.25
    version=pd.Series(1,index=idx)
    event={'onset_period':pd.Period('2000-05','M'),'end_period':pd.Period('2000-08','M'),
           'minimum_spi':-2,'left_censored':False,'status':'CLIMATE_EPISODE_COMPLETE'}
    config={'recovery_baseline_months':3,'recovery_confirmation_months':2,
            'recovery_horizon_months':12,'recovery_tolerance_fraction':.02}
    return event,water,version,config

def test_two_consecutive_observations_confirm_recovery(setup_event):
    result=recovery_event(*setup_event)
    assert result['status']=='RECOVERY_CONFIRMED'
    assert result['recovery_months']==1 and result['confirmed_after_months']==2

def test_water_recovered_at_climate_end_can_have_zero_lag(setup_event):
    event,water,version,config=setup_event; water.loc['2000-08']=0
    result=recovery_event(event,water,version,config)
    assert result['recovery_months']==0 and result['confirmed_after_months']==1

@pytest.mark.parametrize('period,status',[('2000-03','PRE_EVENT_WATER_GAP'),('2000-06','DROUGHT_WATER_GAP'),
    ('2000-08','CLIMATE_END_WATER_GAP'),('2000-09','FOLLOWUP_WATER_GAP_CENSORED')])
def test_missing_observations_censor_without_filled_recovery(setup_event,period,status):
    event,water,version,config=setup_event; water.loc[period]=np.nan
    result=recovery_event(event,water,version,config)
    assert result['status']==status and np.isnan(result['recovery_months'])

@pytest.mark.parametrize('period',['2000-06','2000-08','2000-09'])
def test_sensor_version_boundary_censors_recovery(setup_event,period):
    event,water,version,config=setup_event; version.loc[period:]=2
    result=recovery_event(event,water,version,config)
    assert result['status']=='VERSION_BOUNDARY_CENSORED' and np.isnan(result['recovery_months'])

def test_recovery_confirmation_resets_after_deficit(setup_event):
    event,water,version,config=setup_event; water.loc['2000-10']=-.2
    result=recovery_event(event,water,version,config)
    assert result['recovery_months']==3 and result['confirmed_after_months']==4

def test_no_deficit_is_not_called_recovery(setup_event):
    event,water,version,config=setup_event; water[:]=0
    result=recovery_event(event,water,version,config)
    assert result['status']=='NO_DETECTABLE_WATER_DEFICIT' and np.isnan(result['recovery_months'])

def test_horizon_censor_is_not_a_duration(setup_event):
    event,water,version,config=setup_event; water.loc['2000-09':]=-.4
    result=recovery_event(event,water,version,config)
    assert result['status']=='RECOVERY_HORIZON_CENSORED' and np.isnan(result['recovery_months'])

def test_study_end_is_censored(setup_event):
    event,water,version,config=setup_event
    result=recovery_event(event,water.loc[:'2000-09'],version,config)
    assert result['status']=='WATER_STUDY_END_CENSORED'

def test_climate_missing_month_censors_episode():
    idx=pd.period_range('2000-01','2000-06',freq='M')
    events=drought_events(pd.Series([0,-1.2,-2,np.nan,-1.1,0],index=idx))
    assert events[0]['status']=='CLIMATE_GAP_CENSORED'
    assert events[1]['left_censored']

def test_climate_study_end_is_censored():
    idx=pd.period_range('2000-01','2000-03',freq='M')
    assert drought_events(pd.Series([0,-2,-1],index=idx))[0]['status']=='CLIMATE_STUDY_END_CENSORED'

def test_missing_baseline_writes_headers_without_results(tmp_path):
    result=run_drought(None,None,None,{},tmp_path)
    assert result['status']=='MISSING_BASELINE'
    assert pd.read_csv(tmp_path/'spi_indices.csv').empty
    assert pd.read_csv(tmp_path/'drought_recovery_events.csv').empty

def test_complete_calibration_branch_separates_three_recovery_cohorts(tmp_path):
    config=load_config(ROOT/'research_pipeline/config.json')
    idx=pd.period_range('1981-01','2024-12',freq='M')
    rain=np.random.default_rng(75).gamma(2,30,len(idx))
    climate=pd.DataFrame({'region':'Naogaon','period':idx.astype(str),'year':idx.year,'month':idx.month,'chirps_rainfall_mm':rain})
    baseline=climate[climate.year<2000].copy(); study=climate[climate.year>=2000].copy()
    records=[]
    for group in ['all_water','baseline_seasonal','baseline_permanent']:
        frame=study[['region','period','year','month']].copy()
        frame['water_group']=group; frame['threshold_pct']=95; frame['landsat_collection']=np.where(frame.year<2022,1,2)
        frame['water_fraction']=.5
        if group!='all_water': frame.loc[frame.year<2005,'water_fraction']=np.nan
        records.append(frame)
    status=run_drought(study,baseline,pd.concat(records,ignore_index=True),config,tmp_path)
    assert status['status']=='COMPUTED_WITH_EVENT_CENSORING' and status['spi_records']==600
    parameters=pd.read_csv(tmp_path/'spi_calibration_parameters.csv')
    assert len(parameters)==24 and (parameters.status=='PASS').all()
    events=pd.read_csv(tmp_path/'drought_recovery_events.csv')
    assert set(events.water_group)=={'all_water','baseline_seasonal','baseline_permanent'}
    assert events.recovery_months.isna().all()  # Constant water has no observed deficit.
