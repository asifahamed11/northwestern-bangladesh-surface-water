import numpy as np
import pandas as pd
from research_pipeline.models import annual_climate_models,monthly_models
from research_pipeline.common import load_config,ROOT

def test_annual_class_models_preserve_observations_and_produce_finite_fractions(tmp_path):
    config=load_config(ROOT/'research_pipeline/config.json')
    years=np.arange(2000,2025); rng=np.random.default_rng(42)
    annual=pd.DataFrame({'region':'Naogaon','year':years,'eligible':True,'common_support_area_km2':100.,
                         'permanent_water_area_km2':20+.1*(years-2000)+rng.normal(0,.1,25),
                         'seasonal_water_area_km2':50-.2*(years-2000)+rng.normal(0,.1,25)})
    records=[]
    for year in years:
        for month in range(1,13):
            records.append({'region':'Naogaon','year':year,'month':month,
                'chirps_rainfall_mm':max(0,rng.normal(100,40)),
                'era5_temperature_c':rng.normal(25,2),
                'era5_evaporation_demand_mm_sign_reversed':rng.normal(80,20)})
    original=annual.copy(deep=True)
    status=annual_climate_models(annual,pd.DataFrame(records),config,tmp_path)
    assert (status.status=='PASS').all()
    result=pd.read_csv(tmp_path/'annual_class_climate_adjusted.csv')
    assert result.climate_adjusted_fraction_model_derived.between(0,1).all()
    pd.testing.assert_frame_equal(annual,original)
    assert len(status)==4 and len(result)==94

def test_monthly_models_keep_hydroperiod_groups_separate(tmp_path):
    config=load_config(ROOT/'research_pipeline/config.json')
    idx=pd.period_range('2000-01','2024-12',freq='M'); rng=np.random.default_rng(99)
    climate=pd.DataFrame({'region':'Naogaon','period':idx.astype(str),'year':idx.year,'month':idx.month,
        'chirps_rainfall_mm':rng.gamma(2,50,len(idx)),'era5_precipitation_mm':rng.gamma(2,50,len(idx)),
        'era5_temperature_c':rng.normal(25,3,len(idx)),
        'era5_evaporation_demand_mm_sign_reversed':rng.gamma(2,30,len(idx))})
    groups=[]
    for group,mean in [('all_water',.4),('baseline_seasonal',.3),('baseline_permanent',.8)]:
        groups.append(pd.DataFrame({'region':'Naogaon','water_group':group,'threshold_pct':95,
            'period':idx.astype(str),'year':idx.year,'month':idx.month,'eligible':True,
            'water_fraction':np.clip(mean+rng.normal(0,.03,len(idx)),0,1),'common_support_area_km2':10.}))
    series=pd.concat(groups,ignore_index=True)
    status=monthly_models(series,climate,config,tmp_path)
    assert len(status)==6 and (status.status=='PASS').all()
    result=pd.read_csv(tmp_path/'climate_adjusted_water.csv')
    assert result.climate_adjusted_fraction_model_derived.between(0,1).all()
    assert set(result.water_group)=={'all_water','baseline_seasonal','baseline_permanent'}
