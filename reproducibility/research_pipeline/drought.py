import numpy as np
import pandas as pd
from scipy import stats
from .common import require, write_table

def spi_series(rain,index,scale,start,end,minimum=30,positive_minimum=10):
    index=pd.PeriodIndex(index,freq='M')
    require(not index.duplicated().any(),'Duplicate precipitation calendar months')
    require(np.all(np.asarray(rain)>=0),'Negative/missing precipitation')
    series=pd.Series(np.asarray(rain,float),index=index).sort_index()
    series=series.reindex(pd.period_range(series.index.min(),series.index.max(),freq='M'))
    accumulated=series.rolling(scale,min_periods=scale).sum()
    result=pd.Series(np.nan,index=series.index); parameters=[]
    for month in range(1,13):
        ref=accumulated[(accumulated.index.year>=start)&(accumulated.index.year<=end)&(accumulated.index.month==month)].dropna()
        row={'scale_months':scale,'calendar_month':month,'baseline_n':len(ref),'status':'INSUFFICIENT_BASELINE'}
        positive=ref[ref>0]
        if len(ref)>=minimum and len(positive)>=positive_minimum and positive.std()>1e-10:
            try:
                shape,_,theta=stats.gamma.fit(positive,floc=0)
                require(np.isfinite([shape,theta]).all() and shape>0 and theta>0,'Invalid gamma calibration')
                q=float((ref==0).mean())
                target=accumulated[accumulated.index.month==month].dropna()
                probabilities=q+(1-q)*stats.gamma.cdf(target,shape,loc=0,scale=theta)
                result.loc[target.index]=stats.norm.ppf(np.clip(probabilities,1e-8,1-1e-8))
                row.update(status='PASS',gamma_shape=shape,gamma_scale=theta,zero_probability=q)
            except (ValueError,RuntimeError,FloatingPointError) as error: row.update(status='CALIBRATION_FAILED',reason=str(error))
        parameters.append(row)
    return result,pd.DataFrame(parameters)

def drought_events(spi,onset=-1,end=0):
    """Drought starts at SPI<=onset and ends at the first SPI>=end.

    Missing calibration/precipitation months censor an active episode.
    """
    spi=spi.sort_index(); active=None; events=[]
    for period,value in spi.items():
        if not np.isfinite(value):
            if active:
                active.update(end_period=None,status='CLIMATE_GAP_CENSORED'); events.append(active); active=None
            continue
        if active is None and value<=onset:
            previous=spi.get(period-1,np.nan)
            active={'onset_period':period,'minimum_spi':float(value),
                    'left_censored':not np.isfinite(previous),'status':'ACTIVE'}
        if active:
            active['minimum_spi']=min(active['minimum_spi'],float(value))
            if value>=end:
                active.update(end_period=period,status='CLIMATE_EPISODE_COMPLETE'); events.append(active); active=None
    if active:
        active.update(end_period=None,status='CLIMATE_STUDY_END_CENSORED'); events.append(active)
    return events

def recovery_event(event,water,version,config):
    onset=event['onset_period']; end=event.get('end_period')
    result={'onset_period':str(onset),'climate_end_period':str(end) if end is not None else '',
            'minimum_spi':event['minimum_spi'],'recovery_months':np.nan,'status':event['status']}
    if event['left_censored']:
        result['status']='ONSET_LEFT_CENSORED'; return result
    if end is None: return result
    pre=pd.period_range(onset-config['recovery_baseline_months'],onset-1,freq='M')
    baseline=water.reindex(pre)
    if baseline.isna().any(): result['status']='PRE_EVENT_WATER_GAP'; return result
    phase=pd.period_range(onset,end-1,freq='M')
    affected=water.reindex(phase)
    if len(affected)==0 or affected.isna().any(): result['status']='DROUGHT_WATER_GAP'; return result
    if not np.isfinite(water.get(end,np.nan)):
        result['status']='CLIMATE_END_WATER_GAP'; return result
    versions=version.reindex(pd.period_range(pre[0],end,freq='M'))
    if versions.isna().any() or versions.nunique()!=1:
        result['status']='VERSION_BOUNDARY_CENSORED'; return result
    before=float(baseline.mean()); impact=before-float(affected.min())
    result.update(pre_event_water_anomaly=before,impact_fraction_points=impact)
    if impact<=config['recovery_tolerance_fraction']:
        result['status']='NO_DETECTABLE_WATER_DEFICIT'; return result
    required=config['recovery_confirmation_months']; count=0; first=None
    initial_version=versions.iloc[0]
    for offset in range(0,config['recovery_horizon_months']+1):
        period=end+offset
        if period not in water.index:
            result.update(status='WATER_STUDY_END_CENSORED',followup_months=offset-1); return result
        if version.get(period,np.nan)!=initial_version:
            result.update(status='VERSION_BOUNDARY_CENSORED',followup_months=offset-1); return result
        value=water.get(period,np.nan)
        if not np.isfinite(value):
            result.update(status='FOLLOWUP_WATER_GAP_CENSORED',followup_months=offset-1); return result
        if value>=before-config['recovery_tolerance_fraction']:
            if count==0: first=offset
            count+=1
            if count>=required:
                result.update(status='RECOVERY_CONFIRMED',recovery_months=first,
                              confirmed_after_months=offset,followup_months=offset); return result
        else: count=0; first=None
    result.update(status='RECOVERY_HORIZON_CENSORED',followup_months=config['recovery_horizon_months'])
    return result

def run_drought(climate,baseline,support,config,out):
    spi_columns=['region','scale_months','year','month','period','spi']
    event_columns=['region','water_group','onset_period','climate_end_period','minimum_spi','recovery_months','status','pre_event_water_anomaly','impact_fraction_points','followup_months','confirmed_after_months']
    if baseline is None:
        write_table(out/'spi_indices.csv',[],spi_columns)
        write_table(out/'spi_calibration_parameters.csv',[],['region','scale_months','calendar_month','baseline_n','status','gamma_shape','gamma_scale','zero_probability'])
        write_table(out/'drought_recovery_events.csv',[],event_columns)
        return {'status':'MISSING_BASELINE','reason':'SPI/recovery not computed: complete 1981-1999 calibration inputs required'}
    joined=pd.concat([baseline,climate],ignore_index=True)
    require(not joined.duplicated(['region','year','month']).any(),'Overlapping baseline/study climate records')
    spi_rows=[]; parameter_rows=[]; event_rows=[]
    primary=support[support.threshold_pct==config['primary_threshold']]
    for region,frame in joined.groupby('region',sort=False):
        frame=frame.sort_values(['year','month'])
        for scale in config['spi_scales']:
            spi,parameters=spi_series(frame.chirps_rainfall_mm,pd.PeriodIndex(frame.period,freq='M'),scale,
                config['spi_baseline_start'],config['spi_baseline_end'],
                config['spi_minimum_baseline_samples_per_calendar_month'],config['spi_minimum_positive_samples'])
            parameters['region']=region; parameter_rows+=parameters.to_dict('records')
            for period,value in spi.items():
                if config['start_year']<=period.year<=config['end_year']:
                    spi_rows.append({'region':region,'scale_months':scale,'year':period.year,'month':period.month,'period':str(period),'spi':value})
            if scale!=config['recovery_spi_scale']: continue
            for water_group,observed in primary[primary.region==region].groupby('water_group'):
                observed=observed.sort_values(['year','month']).copy()
                observed.index=pd.PeriodIndex(observed.period,freq='M')
                reference=observed[observed.year.between(config['water_calendar_reference_start'],config['water_calendar_reference_end'])].groupby('month').water_fraction.agg(['mean','count'])
                reference.loc[reference['count']<config['minimum_water_reference_samples'],'mean']=np.nan
                anomalies=observed.water_fraction-observed.month.map(reference['mean']).to_numpy()
                # Complete 300-month index is retained; no gap is dropped or filled.
                version=observed.landsat_collection
                for event in drought_events(spi,config['drought_onset_spi'],config['drought_end_spi']):
                    if config['start_year']<=event['onset_period'].year<=config['end_year']:
                        event_rows.append({'region':region,'water_group':water_group,**recovery_event(event,anomalies,version,config)})
    write_table(out/'spi_indices.csv',spi_rows,spi_columns)
    write_table(out/'spi_calibration_parameters.csv',parameter_rows)
    write_table(out/'drought_recovery_events.csv',event_rows,event_columns)
    failed=sum(row['status']!='PASS' for row in parameter_rows)
    return {'status':'PARTIAL_CALIBRATION' if failed else 'COMPUTED_WITH_EVENT_CENSORING','failed_calibration_parameters':failed,'spi_records':len(spi_rows),'event_records':len(event_rows),
            'confirmed_recoveries':sum(row['status']=='RECOVERY_CONFIRMED' for row in event_rows)}
