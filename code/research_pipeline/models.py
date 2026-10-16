import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit, logit
from statsmodels.stats.multitest import multipletests
from .common import fit_linear, month_number, write_table

def annual_climate_models(annual,climate,config,out):
    """Annual class shares adjusted for annual climate, separately by source class."""
    climate=climate.copy()
    import calendar as calendar_module
    climate['calendar_days']=[calendar_module.monthrange(int(y),int(m))[1] for y,m in zip(climate.year,climate.month)]
    climate['temperature_degree_days']=climate.era5_temperature_c*climate.calendar_days
    groups=climate.groupby(['region','year'])
    calendar=groups.agg(calendar_months=('month','nunique'),
        rainfall_mm=('chirps_rainfall_mm',lambda x:x.sum(min_count=12)),
        temperature_degree_days=('temperature_degree_days',lambda x:x.sum(min_count=12)),
        calendar_days=('calendar_days','sum'),
        evaporation_demand_mm=('era5_evaporation_demand_mm_sign_reversed',lambda x:x.sum(min_count=12))).reset_index()
    calendar=calendar[calendar.calendar_months==12]
    calendar['temperature_c']=calendar.temperature_degree_days/calendar.calendar_days
    merged=annual.merge(calendar,on=['region','year'],validate='one_to_one')
    statuses=[]; coefficients=[]; predictions=[]; cv=[]
    weather=['rainfall_mm','temperature_c','evaporation_demand_mm']
    for region,full in merged.groupby('region',sort=False):
        reference=full[full.year.between(config['water_calendar_reference_start'],config['water_calendar_reference_end'])][weather].median()
        for scope,last in [('primary_pre2022',config['primary_end_year']),('full_version_sensitivity',config['end_year'])]:
            selected=full[full.eligible & full.year.le(last)].dropna(subset=weather).sort_values('year').copy()
            selected['year_offset']=selected.year-config['start_year']
            features=['year_offset']+weather
            if scope=='full_version_sensitivity' and selected.year.ge(2022).any():
                selected['version_step_2022']=selected.year.ge(2022).astype(float); features.append('version_step_2022')
            for source_class in ['permanent','seasonal']:
                record={'region':region,'scope':scope,'source_class':source_class,'n':len(selected),'status':'INSUFFICIENT_DATA'}
                if len(selected)<15: statuses.append(record); continue
                fraction=selected[f'{source_class}_water_area_km2']/selected.common_support_area_km2
                response=logit(fraction.clip(1e-6,1-1e-6))
                try: fit=fit_linear(selected[features],response,selected.year,config['annual_hac_lags'])
                except ValueError as error:
                    record.update(status='MODEL_REJECTED',reason=str(error)); statuses.append(record); continue
                i=fit['names'].index('year_offset')
                record.update(status='PASS',time_coefficient_logit_per_year=fit['coefficients'][i],
                              lower95=fit['lower95'][i],upper95=fit['upper95'][i],p_value=fit['pvalues'][i])
                statuses.append(record)
                for j,term in enumerate(fit['names']):
                    coefficients.append({'region':region,'scope':scope,'source_class':source_class,'term':term,
                        'coefficient_logit_units':fit['coefficients'][j],'lower95':fit['lower95'][j],
                        'upper95':fit['upper95'][j],'p_value':fit['pvalues'][j]})
                fixed=selected[features].copy()
                for name in weather: fixed[name]=reference[name]
                observed_fit=fit['predict'](selected[features]); fixed_fit=fit['predict'](fixed)
                adjusted=expit(np.asarray(response)-(observed_fit-fixed_fit))
                for k,row in enumerate(selected.itertuples()):
                    predictions.append({'region':region,'scope':scope,'source_class':source_class,'year':row.year,
                        'observed_fraction':fraction.iloc[k],'fitted_fraction_model_derived':expit(observed_fit[k]),
                        'fixed_climate_expected_fraction_model_derived':expit(fixed_fit[k]),
                        'climate_adjusted_fraction_model_derived':adjusted[k],
                        'climate_adjusted_area_km2_model_derived':adjusted[k]*row.common_support_area_km2})
                if scope=='primary_pre2022':
                    for start in config['cv_test_start_years']:
                        train=selected[selected.year<start]; test=selected[selected.year.between(start,start+config['cv_test_years']-1)]
                        check={'region':region,'source_class':source_class,'test_start_year':start,
                               'n_train':len(train),'n_test':len(test),'status':'INSUFFICIENT_DATA'}
                        if len(train)>=12 and len(test)>=2:
                            train_y=logit((train[f'{source_class}_water_area_km2']/train.common_support_area_km2).clip(1e-6,1-1e-6))
                            try:
                                fitted=fit_linear(train[features],train_y,train.year,config['annual_hac_lags'])
                                truth=(test[f'{source_class}_water_area_km2']/test.common_support_area_km2).to_numpy()
                                predicted=expit(fitted['predict'](test[features]))
                                train_mean=float((train[f'{source_class}_water_area_km2']/train.common_support_area_km2).mean())
                                check.update(status='PASS',rmse=float(np.sqrt(np.mean((truth-predicted)**2))),
                                    training_mean_baseline_rmse=float(np.sqrt(np.mean((truth-train_mean)**2))))
                            except ValueError as error: check.update(status='MODEL_REJECTED',reason=str(error))
                        cv.append(check)
    status=pd.DataFrame(statuses); status['p_adjusted_BY_primary_districts']=np.nan
    if 'p_value' in status:
        valid=(status.scope=='primary_pre2022')&(status.region!='All_districts')&status.p_value.notna()
        if valid.any(): status.loc[valid,'p_adjusted_BY_primary_districts']=multipletests(status.loc[valid,'p_value'],method='fdr_by')[1]
    write_table(out/'annual_climate_model_status.csv',status)
    write_table(out/'annual_climate_model_coefficients.csv',coefficients,columns=['region','scope','source_class','term','coefficient_logit_units','lower95','upper95','p_value'])
    write_table(out/'annual_class_climate_adjusted.csv',predictions,columns=['region','scope','source_class','year','observed_fraction','fitted_fraction_model_derived','fixed_climate_expected_fraction_model_derived','climate_adjusted_fraction_model_derived','climate_adjusted_area_km2_model_derived'])
    write_table(out/'annual_calendar_cross_validation.csv',cv,columns=['region','source_class','test_start_year','n_train','n_test','status','rmse','training_mean_baseline_rmse','reason'])
    return status

def annual_trends(annual,config,out):
    rows=[]
    for region,frame in annual.groupby('region',sort=False):
        frame=frame[frame.eligible].sort_values('year').copy()
        frame['total_water_area_km2']=frame.seasonal_water_area_km2+frame.permanent_water_area_km2
        for scope,last in [('primary_pre2022',config['primary_end_year']),('full_version_sensitivity',config['end_year'])]:
            selected=frame[frame.year<=last]
            for metric in ['seasonal_water_area_km2','permanent_water_area_km2','total_water_area_km2']:
                record={'region':region,'scope':scope,'metric':metric,'n':len(selected),'status':'INSUFFICIENT_SUPPORT'}
                if len(selected)>=15:
                    features=pd.DataFrame({'year_offset':selected.year-config['start_year']},index=selected.index)
                    if selected.year.ge(2022).any(): features['version_step_2022']=selected.year.ge(2022).astype(float)
                    try:
                        fit=fit_linear(features,selected[metric],selected.year,config['annual_hac_lags'])
                        i=fit['names'].index('year_offset')
                        record.update(status='PASS',slope_km2_per_year=fit['coefficients'][i],
                            slope_lower95=fit['lower95'][i],slope_upper95=fit['upper95'][i],p_value=fit['pvalues'][i],
                            sen_slope_descriptive_km2_per_year=stats.theilslopes(selected[metric],selected.year).slope,
                            common_support_area_km2=float(selected.common_support_area_km2.iloc[0]))
                    except ValueError as error: record.update(status='MODEL_REJECTED',reason=str(error))
                rows.append(record)
    result=pd.DataFrame(rows)
    result['p_adjusted_BY_primary_districts']=np.nan
    group=(result.scope=='primary_pre2022')&(result.region!='All_districts')&(result.status=='PASS')&result.p_value.notna() if 'p_value' in result else np.zeros(len(result),bool)
    if np.any(group): result.loc[group,'p_adjusted_BY_primary_districts']=multipletests(result.loc[group,'p_value'],method='fdr_by')[1]
    return write_table(out/'annual_trend_results.csv',result)

def climate_features(climate):
    rows=[]
    for region,frame in climate.groupby('region',sort=False):
        frame=frame.sort_values(['year','month']).copy()
        index=pd.PeriodIndex(frame.period,freq='M')
        # Reindex BEFORE rolling: an omitted calendar month cannot be compressed.
        full=frame.set_index(index).reindex(pd.period_range(index.min(),index.max(),freq='M'))
        rain=full.chirps_rainfall_mm.rolling(3,min_periods=3).sum()
        era_rain=full.era5_precipitation_mm.rolling(3,min_periods=3).sum()
        frame['rain_3m_mm']=rain.reindex(index).to_numpy()
        frame['era_rain_3m_mm']=era_rain.reindex(index).to_numpy()
        frame['time_years']=(month_number(frame.year,frame.month)-2000*12)/12
        frame['season_sin']=np.sin(2*np.pi*(frame.month-1)/12)
        frame['season_cos']=np.cos(2*np.pi*(frame.month-1)/12)
        rows.append(frame)
    return pd.concat(rows,ignore_index=True)

def blocked_cv(frame,features,config):
    results=[]
    for start in config['cv_test_start_years']:
        first=start*12
        train=frame[month_number(frame.year,frame.month)<first-config['cv_gap_months']]
        test=frame[(frame.year>=start)&(frame.year<start+config['cv_test_years'])]
        row={'test_start_year':start,'n_train':len(train),'n_test':len(test),'status':'INSUFFICIENT_DATA',
             'last_train_period':train.period.iloc[-1] if len(train) else '',
             'first_test_period':test.period.iloc[0] if len(test) else ''}
        if len(train)>=config['minimum_cv_train'] and len(test)>=config['minimum_cv_test']:
            try:
                fit=fit_linear(train[features],train.response_logit,month_number(train.year,train.month),config['monthly_hac_lags'])
                prediction=expit(fit['predict'](test[features]))
                month_means=train.groupby('month').water_fraction.mean()
                benchmark=test.month.map(month_means).fillna(train.water_fraction.mean()).to_numpy()
                truth=test.water_fraction.to_numpy()
                row.update(status='PASS',rmse=float(np.sqrt(np.mean((prediction-truth)**2))),
                    mae=float(np.mean(abs(prediction-truth))),
                    seasonal_baseline_rmse=float(np.sqrt(np.mean((benchmark-truth)**2))))
            except ValueError as error: row.update(status='MODEL_REJECTED',reason=str(error))
        results.append(row)
    return results

def monthly_models(series,climate,config,out):
    climate=climate_features(climate)
    merged=series.merge(climate,on=['region','year','month','period'],validate='many_to_one')
    statuses=[]; coefficients=[]; predictions=[]; cv_rows=[]
    features=['time_years','season_sin','season_cos','rain_3m_mm',
              'era5_temperature_c','era5_evaporation_demand_mm_sign_reversed']
    for (threshold,region,water_group),full in merged.groupby(['threshold_pct','region','water_group'],sort=False):
        for scope,last in [('primary_pre2022',config['primary_end_year']),('full_version_sensitivity',config['end_year'])]:
            frame=full[full.eligible & full.year.le(last)].dropna(subset=features+['water_fraction']).sort_values(['year','month']).copy()
            record={'region':region,'water_group':water_group,'threshold_pct':threshold,'scope':scope,'n':len(frame),'status':'INSUFFICIENT_DATA'}
            if len(frame)<config['minimum_model_observations']:
                statuses.append(record); continue
            # Explicit numeric logit transformation; original fractions remain unchanged.
            frame['response_logit']=logit(frame.water_fraction.clip(1e-6,1-1e-6))
            current_features=features.copy()
            if scope=='full_version_sensitivity' and frame.year.ge(2022).any():
                if frame.year.ge(2022).sum()<12:
                    record.update(status='INSUFFICIENT_VERSION2_OBSERVATIONS'); statuses.append(record); continue
                frame['version_step_2022']=frame.year.ge(2022).astype(float)
                current_features.append('version_step_2022')
            try:
                fit=fit_linear(frame[current_features],frame.response_logit,month_number(frame.year,frame.month),config['monthly_hac_lags'])
            except ValueError as error:
                record.update(status='MODEL_REJECTED',reason=str(error)); statuses.append(record); continue
            record['status']='PASS'
            statuses.append(record)
            for i,name in enumerate(fit['names']):
                coefficients.append({'region':region,'water_group':water_group,'threshold_pct':threshold,'scope':scope,'term':name,
                    'coefficient_logit_units':fit['coefficients'][i],'lower95':fit['lower95'][i],
                    'upper95':fit['upper95'][i],'p_value':fit['pvalues'][i],'n':fit['n']})
            weather=['rain_3m_mm','era5_temperature_c','era5_evaporation_demand_mm_sign_reversed']
            reference=climate[(climate.region==region)&climate.year.between(config['water_calendar_reference_start'],config['water_calendar_reference_end'])].groupby('month')[weather].median()
            counterfactual=frame[current_features].copy()
            for variable in weather: counterfactual[variable]=frame.month.map(reference[variable]).to_numpy()
            current=fit['predict'](frame[current_features]); fixed=fit['predict'](counterfactual)
            adjusted=expit(frame.response_logit.to_numpy()-(current-fixed))
            for j,row in enumerate(frame.itertuples()):
                predictions.append({'region':region,'water_group':water_group,'threshold_pct':threshold,'scope':scope,'period':row.period,
                    'observed_water_fraction':row.water_fraction,'fitted_water_fraction':expit(current[j]),
                    'fixed_climate_expected_fraction':expit(fixed[j]),'climate_adjusted_fraction_model_derived':adjusted[j],
                    'common_support_area_km2':row.common_support_area_km2,
                    'climate_adjusted_area_km2_model_derived':adjusted[j]*row.common_support_area_km2})
            if scope=='primary_pre2022':
                for row in blocked_cv(frame,current_features,config):
                    cv_rows.append({'region':region,'water_group':water_group,'threshold_pct':threshold,**row})
    write_table(out/'monthly_model_status.csv',statuses)
    write_table(out/'monthly_model_coefficients.csv',coefficients,columns=['region','water_group','threshold_pct','scope','term','coefficient_logit_units','lower95','upper95','p_value','n'])
    write_table(out/'climate_adjusted_water.csv',predictions,columns=['region','water_group','threshold_pct','scope','period','observed_water_fraction','fitted_water_fraction','fixed_climate_expected_fraction','climate_adjusted_fraction_model_derived','common_support_area_km2','climate_adjusted_area_km2_model_derived'])
    write_table(out/'calendar_block_cross_validation.csv',cv_rows,columns=['region','water_group','threshold_pct','test_start_year','n_train','n_test','last_train_period','first_test_period','status','rmse','mae','seasonal_baseline_rmse','reason'])
    return pd.DataFrame(statuses)
