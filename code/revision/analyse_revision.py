"""Exploratory, frozen-specification reanalysis of genuine local source rasters.

No new labels, gap filling, recovery measurements, or causal effects are created.
Run extraction first. The fixed-design residual bootstrap is approximate.
"""
from pathlib import Path
import calendar
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from statsmodels.stats.multitest import multipletests

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/revision'
sys.path.insert(0,str(ROOT))
from research_pipeline.common import fit_linear,write_json
T=OUT/'tables'
P=json.loads((OUT/'FROZEN_REVISION_PROTOCOL.json').read_text(encoding='utf-8'))

def seed_for(key):
    return (P['inference']['seed']+int(hashlib.sha256(str(key).encode()).hexdigest()[:8],16))%2**32

def climate_table():
    c=pd.concat([pd.read_csv(ROOT/'research_outputs/analysis_20261013_completed_data/baseline_climate_1981_1999.csv'),
                 pd.read_csv(ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv')],ignore_index=True)
    assert not c.duplicated(['region','year','month']).any()
    c['days']=[calendar.monthrange(int(y),int(m))[1] for y,m in zip(c.year,c.month)]
    c['degree_days']=c.days*c.era5_temperature_c
    rows=[]
    for (r,y),g in c.groupby(['region','year']):
        if y<2000: continue
        assert set(g.month)==set(range(1,13))
        antecedent=c[c.region.eq(r)&(((c.year==y-1)&c.month.ge(10))|((c.year==y)&c.month.le(5)))]
        assert len(antecedent)==8
        rows.append(dict(region=r,year=y,year_offset=y-2000,asset_step_2016=float(y>=2016),
             rain_annual_mm=g.chirps_rainfall_mm.sum(),
             rain_jjas_mm=g.loc[g.month.between(6,9),'chirps_rainfall_mm'].sum(),
             rain_oct_may_mm=antecedent.chirps_rainfall_mm.sum(),
             temperature_c=g.degree_days.sum()/g.days.sum(),
             evaporation_demand_mm=g.era5_evaporation_demand_mm_sign_reversed.sum()))
    result=pd.DataFrame(rows)
    result.to_csv(T/'annual_climate_features_revision.csv',index=False)
    return result

def design(frame,features):
    a=frame[features].to_numpy(float)
    return np.column_stack([np.ones(len(a)),(a-a.mean(axis=0))/a.std(axis=0)])

def checked_fit(frame,y,features,lag=2):
    if len(frame)-(len(features)+1)<P['inference']['minimum_residual_df']:
        raise ValueError('Residual degrees of freedom below frozen minimum')
    return fit_linear(frame[features],y,frame.year,lag)

def bootstrap(frame,y,features,key):
    """Circular residual blocks preserve local order; design stays fixed.

    This is not a finite-sample coverage guarantee. No trend or step is
    scrambled. Innovations are centered before circular block resampling.
    """
    if not np.all(np.diff(frame.year.to_numpy())==1):
        return [dict(block_length=b,replicates=0,lower95=np.nan,upper95=np.nan,
                     interval_status='UNAVAILABLE_calendar_gaps',
                     interval_scope='Selected annual years have calendar gaps; no compressed-row block resampling')
                for b in P['inference']['residual_circular_block_bootstrap_lengths']]
    x=design(frame,features); pinv=np.linalg.pinv(x)
    beta=pinv@y; fitted=x@beta; residual=y-fitted
    residual-=residual.mean()
    n=len(y); j=1+features.index('year_offset')
    scale=frame[features].to_numpy(float).std(axis=0)[features.index('year_offset')]
    out=[]
    for block in P['inference']['residual_circular_block_bootstrap_lengths']:
        rng=np.random.default_rng(seed_for((key,block)))
        starts=rng.integers(0,n,size=(P['inference']['bootstrap_replicates'],int(np.ceil(n/block))))
        inds=((starts[:,:,None]+np.arange(block))%n).reshape(len(starts),-1)[:,:n]
        slopes=(fitted[None,:]+residual[inds])@pinv[j]/scale
        lo,hi=np.quantile(slopes,[.025,.975])
        out.append(dict(block_length=block,replicates=len(slopes),lower95=lo,upper95=hi,
                        interval_status='COMPUTED',interval_scope='approximate pointwise fixed-design residual bootstrap'))
    return out

def annual_analysis(frame):
    status=[]; coeff=[]; boot=[]; influence=[]; validation=[]; predictions=[]; area=[]
    for (cohort,region),full in frame.groupby(['cohort','region'],sort=False):
        primary=full[full.year.between(2000,2021)&full.eligible].sort_values('year')
        print('Models:',cohort,region,len(primary),flush=True)
        for cls in ['seasonal','permanent']:
            for scope,selection in [('primary',primary),('2013_2021',primary[primary.year.ge(2013)])]:
                y=logit(selection[f'{cls}_fraction_of_observed'].clip(1e-6,1-1e-6)).to_numpy()
                models=P['models'] if scope=='primary' else {k:P['models'][k] for k in ['trend','monsoon']}
                for model,features in models.items():
                    key=dict(cohort=cohort,region=region,source_class=cls,scope=scope,model=model)
                    for lag in P['inference']['HAC_calendar_lags']:
                        rec={**key,'hac_lag':lag,'n':len(selection),'status':'REJECTED'}
                        try:
                            fit=checked_fit(selection,y,features,lag)
                            j=fit['names'].index('year_offset')
                            x=design(selection,features)
                            pred=fit['predict'](selection[features])
                            rss=np.sum((y-pred)**2); total=np.sum((y-y.mean())**2)
                            rec.update(status='PASS',df=fit['df'],slope=fit['coefficients'][j],
                                lower95=fit['lower95'][j],upper95=fit['upper95'][j],p_value=fit['pvalues'][j],
                                scaled_condition_number=np.linalg.cond(x),r_squared=1-rss/total if total else np.nan,
                                clipped_fractions=int(((selection[f'{cls}_fraction_of_observed']<1e-6)|(selection[f'{cls}_fraction_of_observed']>1-1e-6)).sum()))
                            for j2,term in enumerate(fit['names']):
                                coeff.append({**key,'hac_lag':lag,'term':term,'coefficient':fit['coefficients'][j2],
                                     'lower95':fit['lower95'][j2],'upper95':fit['upper95'][j2],'p_value':fit['pvalues'][j2]})
                            if lag==2:
                                for b in bootstrap(selection,y,features,str(key)): boot.append({**key,**b})
                                for dropyear in selection.year:
                                    keep=selection.year.ne(dropyear).to_numpy()
                                    d={**key,'dropped_year':dropyear,'status':'REJECTED'}
                                    try:
                                        f=checked_fit(selection[keep],y[keep],features)
                                        j3=f['names'].index('year_offset')
                                        d.update(status='PASS',slope=f['coefficients'][j3],lower95=f['lower95'][j3],upper95=f['upper95'][j3])
                                    except ValueError as e: d['reason']=str(e)
                                    influence.append(d)
                                for yr,truth,pr in zip(selection.year,expit(y),expit(pred)):
                                    predictions.append({**key,'year':yr,'source_fraction':truth,'fitted_fraction':pr})
                        except ValueError as e: rec['reason']=str(e)
                        status.append(rec)
            # Area slope remains descriptive on changing observed support.
            for lag in [0,2]:
                f=checked_fit(primary,primary[f'{cls}_water_area_km2'].to_numpy(),['year_offset'],lag)
                j=f['names'].index('year_offset')
                area.append(dict(cohort=cohort,region=region,source_class=cls,hac_lag=lag,n=len(primary),
                    slope_km2_per_year=f['coefficients'][j],lower95=f['lower95'][j],upper95=f['upper95'][j],
                    p_value=f['pvalues'][j],denominator_scope='observed source-class area'))
            # Every fold uses training-only coefficients/centering. No refitting on test.
            folds=[('two_year',y,2) for y in P['validation']['two_year_test_starts']]
            folds += [('rolling_one_year',y,1) for y in P['validation']['rolling_one_year_test_years']]
            for fold,start,width in folds:
                train=primary[primary.year.lt(start)]; test=primary[primary.year.between(start,start+width-1)]
                truth=test[f'{cls}_fraction_of_observed'].to_numpy()
                yt=logit(train[f'{cls}_fraction_of_observed'].clip(1e-6,1-1e-6)).to_numpy()
                for model,features in {'training_mean':[],**P['models']}.items():
                    rec=dict(cohort=cohort,region=region,source_class=cls,fold=fold,test_start=start,model=model,
                             n_train=len(train),n_test=len(test),status='REJECTED')
                    try:
                        if len(train)<12 or len(test)!=width: raise ValueError('Insufficient training/test years')
                        if not features: pred=np.full(len(test),train[f'{cls}_fraction_of_observed'].mean())
                        else:
                            fitted=checked_fit(train,yt,features)
                            pred=expit(fitted['predict'](test[features]))
                        rec.update(status='PASS',squared_error_sum=float(np.sum((truth-pred)**2)),
                            absolute_error_sum=float(np.sum(abs(truth-pred))),rmse=float(np.sqrt(np.mean((truth-pred)**2))))
                    except ValueError as e: rec['reason']=str(e)
                    validation.append(rec)
    s=pd.DataFrame(status);s['p_adjusted_BY_six_district_class_tests']=np.nan
    for _,ind in s[(s.region!='All_districts')&s.status.eq('PASS')].groupby(['cohort','scope','model','hac_lag']).groups.items():
        if len(ind)==6: s.loc[ind,'p_adjusted_BY_six_district_class_tests']=multipletests(s.loc[ind,'p_value'],method='fdr_by')[1]
    for name,data in [('model_status_revision',s),('model_coefficients_revision',coeff),('block_bootstrap_revision',boot),
                      ('leave_one_year_out_revision',influence),('chronological_cv_revision',validation),
                      ('annual_fitted_revision',predictions),('area_trends_revision',area)]:
        pd.DataFrame(data).to_csv(T/(name+'.csv'),index=False)

def windows(frame):
    out=[]
    for (cohort,region),g in frame.groupby(['cohort','region'],sort=False):
        for cls in ['seasonal','permanent']:
            for width in [1,3,5]:
                first=g[g.year.between(2000,2000+width-1)]
                last=g[g.year.between(2022-width,2021)]
                ok=len(first)==width and len(last)==width and first.eligible.all() and last.eligible.all()
                rec=dict(cohort=cohort,region=region,source_class=cls,window_years=width,
                    first_start=2000,first_end=2000+width-1,last_start=2022-width,last_end=2021,status='PASS' if ok else 'INSUFFICIENT')
                if ok:
                    a=first[f'{cls}_water_area_km2'].mean();b=last[f'{cls}_water_area_km2'].mean()
                    rec.update(first_mean_km2=a,last_mean_km2=b,change_km2=b-a,percent_change=100*(b/a-1) if a else np.nan,
                        mean_fraction_change=last[f'{cls}_fraction_of_observed'].mean()-first[f'{cls}_fraction_of_observed'].mean())
                out.append(rec)
    pd.DataFrame(out).to_csv(T/'endpoint_window_changes_revision.csv',index=False)

def monthly_matching():
    m=pd.read_csv(T/'calendar_matched_monthly_water.csv')
    rows=[]
    for (r,month),g in m.groupby(['region','month']):
        rec=dict(region=r,month=month,retained_fraction=g.retained_fraction.iloc[0],
                 fixed_month_area_km2=g.fixed_month_area_km2.iloc[0],status='INSUFFICIENT_SUPPORT')
        if g.eligible.all():
            g=g.sort_values('year').assign(year_offset=lambda d:d.year-2000)
            y=logit(g.water_fraction.clip(1e-6,1-1e-6)).to_numpy()
            fit=checked_fit(g,y,['year_offset'])
            rec.update(status='PASS',slope=fit['coefficients'][1],lower95=fit['lower95'][1],upper95=fit['upper95'][1])
        rows.append(rec)
    pd.DataFrame(rows).to_csv(T/'calendar_matched_trends_revision.csv',index=False)

def main():
    assert (OUT/'EXTRACTION_COMPLETE.json').is_file()
    assert not (OUT/'ANALYSIS_COMPLETE.json').exists(),'Preserve finished run'
    a=pd.read_csv(T/'annual_cohort_sensitivity.csv')
    q=pd.read_csv(T/'annual_cohort_observation_quality.csv')
    c=climate_table()
    merged=a.merge(q,on=['cohort','region','year'],validate='one_to_one').merge(c,on=['region','year'],validate='many_to_one')
    assert len(merged)==700
    merged.to_csv(T/'annual_model_inputs_revision.csv',index=False)
    windows(merged);monthly_matching();annual_analysis(merged)
    write_json(OUT/'ANALYSIS_COMPLETE.json',dict(status='COMPUTATION_COMPLETED',exploratory=True,
        protocol_sha256=hashlib.sha256((OUT/'FROZEN_REVISION_PROTOCOL.json').read_bytes()).hexdigest(),
        original_inputs_unchanged=True,independent_accuracy_established=False,
        caveat='Numerical execution is not independent scientific validation.'))
    print('PASS: all frozen annual and matched-month computations completed.',flush=True)

if __name__=='__main__': main()
