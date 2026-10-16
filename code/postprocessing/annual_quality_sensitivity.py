"""Exploratory annual observation-effort controls, without changing primary models."""
from pathlib import Path
import sys,argparse
import numpy as np
import pandas as pd
import rasterio
from scipy.special import logit,expit
from statsmodels.stats.multitest import multipletests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_pipeline.spatial import Grid
from research_pipeline.common import REGIONS,require,fit_linear,load_config

def observation_quality(out):
    grid=Grid(ROOT)
    with rasterio.open(out/'annual_common_support.tif') as ds: common=ds.read(1)==1
    records=[]
    for year in range(2000,2025):
        sums=np.zeros((4,10))
        with rasterio.open(grid.raw/f'jrc_annual_{year}.tif') as ann,rasterio.open(grid.raw/f'jrc_valid_months_{year}.tif') as qa,rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as monthly:
            for win in grid.windows:
                top=int(win.row_off);stop=top+int(win.height)
                a=ann.read(1,window=win); q=qa.read(1,window=win)
                wet=monthly.read([6,7,8,9],window=win);wet_count=np.isin(wet,[1,2]).sum(axis=0)
                for r in range(4):
                    domain=common[top:stop]&(grid.labels[top:stop]>0 if r==0 else grid.labels[top:stop]==r)
                    w=np.broadcast_to(grid.row_areas[top:stop,None],domain.shape)
                    area=float(w[domain].sum()); sums[r,0]+=area
                    sums[r,1]+=float((q[domain]*w[domain]).sum())
                    sums[r,2]+=float((wet_count[domain]*w[domain]).sum())
                    sums[r,3]+=float(w[domain&(q==12)].sum())
                    for cls,n in [(2,4),(3,6)]:
                        part=domain&(a==cls);sums[r,n]+=float(w[part].sum());sums[r,n+1]+=float((q[part]*w[part]).sum())
                        if cls==3: sums[r,8]+=float(w[part&(q<12)].sum())
            for r,name in enumerate(REGIONS):
                s=sums[r];records.append({'region':name,'year':year,'cohort_area_km2':s[0],
                    'mean_observed_calendar_months':s[1]/s[0],
                    'mean_observed_jun_sep_months':s[2]/s[0],
                    'all_12_months_observed_area_fraction':s[3]/s[0],
                    'mean_observed_months_on_seasonal_class':s[5]/s[4] if s[4] else np.nan,
                    'mean_observed_months_on_permanent_class':s[7]/s[6] if s[6] else np.nan,
                    'permanent_class_area_with_less_than_12_observed_months_fraction':s[8]/s[6] if s[6] else np.nan})
        print('Annual observation effort:',year,flush=True)
    quality=pd.DataFrame(records);quality.to_csv(out/'annual_observation_quality.csv',index=False)
    return quality

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--reuse-quality',action='store_true',help='Reuse existing real-raster observation summaries')
    args=parser.parse_args();out=args.run.resolve()
    quality=pd.read_csv(out/'annual_observation_quality.csv') if args.reuse_quality else observation_quality(out)
    require(len(quality)==100 and set(zip(quality.region,quality.year))=={(r,y) for r in REGIONS for y in range(2000,2025)},'Incomplete annual observation summary')
    # Recreate annual weather aggregations independently from the primary output.
    climate=pd.read_csv(ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv')
    import calendar
    climate['days']=[calendar.monthrange(y,m)[1] for y,m in zip(climate.year,climate.month)]
    climate['degree_days']=climate.days*climate.era5_temperature_c
    weather=climate.groupby(['region','year']).agg(rainfall_mm=('chirps_rainfall_mm','sum'),
        degree_days=('degree_days','sum'),days=('days','sum'),
        evaporation_demand_mm=('era5_evaporation_demand_mm_sign_reversed','sum')).reset_index()
    weather['temperature_c']=weather.degree_days/weather.days
    annual=pd.read_csv(out/'annual_common_support_water.csv').merge(quality,on=['region','year'],validate='one_to_one').merge(weather,on=['region','year'],validate='one_to_one')
    statuses=[];predictions=[]
    for region,full in annual.groupby('region',sort=False):
        frame=full[full.year<=2021].sort_values('year').copy();frame['year_offset']=frame.year-2000
        frame['corrected_2016_asset_step']=(frame.year>=2016).astype(int)
        for setting,extra in [('mean_observation_effort',['mean_observed_calendar_months']),
                              ('mean_and_wet_observation_effort',['mean_observed_calendar_months','mean_observed_jun_sep_months']),
                              ('mean_wet_effort_and_2016_asset_step',['mean_observed_calendar_months','mean_observed_jun_sep_months','corrected_2016_asset_step'])]:
            features=['year_offset','rainfall_mm','temperature_c','evaporation_demand_mm']+extra
            for source_class in ['permanent','seasonal']:
                response=logit((frame[f'{source_class}_water_area_km2']/frame.common_support_area_km2).clip(1e-6,1-1e-6))
                record={'region':region,'source_class':source_class,'setting':setting,'scope':'exploratory_pre2022','n':len(frame)}
                try:
                    fit=fit_linear(frame[features],response,frame.year,2);i=fit['names'].index('year_offset')
                    record.update(status='PASS',time_coefficient_logit_per_year=fit['coefficients'][i],lower95=fit['lower95'][i],upper95=fit['upper95'][i],p_value=fit['pvalues'][i])
                    if 'corrected_2016_asset_step' in features:
                        j=fit['names'].index('corrected_2016_asset_step')
                        record.update(asset_step_coefficient_logit=fit['coefficients'][j],asset_step_lower95=fit['lower95'][j],asset_step_upper95=fit['upper95'][j],
                            interpretation='Exploratory processing-boundary control; a real hydrological step may also be absorbed. Not proof of an artefact.')
                    held=frame[features].copy()
                    for variable in features[1:]:held[variable]=frame[variable].median()
                    fixed=expit(fit['predict'](held));area=frame.common_support_area_km2.to_numpy()
                    record.update(fixed_climate_effort_expected_area_2000_km2=fixed[0]*area[0],
                        fixed_climate_effort_expected_area_2021_km2=fixed[-1]*area[-1])
                except ValueError as error:record.update(status='MODEL_REJECTED',reason=str(error))
                statuses.append(record)
    result=pd.DataFrame(statuses);result['p_adjusted_BY_within_setting_primary_districts']=np.nan
    for setting,f in result.groupby('setting'):
        ids=f[(f.region!='All_districts')&(f.status=='PASS')&f.p_value.notna()].index
        if len(ids):result.loc[ids,'p_adjusted_BY_within_setting_primary_districts']=multipletests(result.loc[ids,'p_value'],method='fdr_by')[1]
    result.to_csv(out/'annual_observation_effort_climate_sensitivity.csv',index=False)
    print(result.to_string(index=False))

if __name__=='__main__': main()
