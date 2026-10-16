"""Create truthful study reports/figures from completed real analysis outputs."""
from pathlib import Path
import sys,argparse,json,shutil,zipfile,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_pipeline.common import require,write_json,digest

REGIONS=['All_districts','Naogaon','Chapainawabganj','Rajshahi']
LABELS={'All_districts':'Three-district union','Naogaon':'Naogaon','Chapainawabganj':'Chapainawabganj','Rajshahi':'Rajshahi'}

def table(frame,decimals=4):
    f=frame.copy()
    for c in f.select_dtypes(include='number'):f[c]=f[c].map(lambda v:'' if pd.isna(v) else f'{v:.{decimals}f}')
    return '\n'.join(['| '+' | '.join(map(str,f.columns))+' |','| '+' | '.join(['---']*len(f.columns))+' |']+
        ['| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in f.itertuples(index=False,name=None)])

def save(fig,path):
    fig.savefig(path.with_suffix('.png'),dpi=220,bbox_inches='tight')
    fig.savefig(path.with_suffix('.svg'),bbox_inches='tight');plt.close(fig)

def figures(out,annual,adjusted,spi,events,quality,effort,models,support,comparison):
    directory=out/'Figures';directory.mkdir(exist_ok=True)
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    for ax,region in zip(axes.ravel(),REGIONS):
        f=annual[(annual.region==region)&(annual.year<=2021)].sort_values('year')
        ax.plot(f.year,f.seasonal_water_area_km2,label='Source seasonal class',color='#16808a')
        ax.plot(f.year,f.permanent_water_area_km2,label='Source permanent class',color='#7755ad')
        ax.set_title(LABELS[region]);ax.set_xlabel('Year');ax.set_ylabel('Fixed-cohort area (km²)');ax.grid(alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Observed annual source classes, 2000–2021; restricted stable footprint')
    save(fig,directory/'01_annual_source_classes_primary')
    fig,axes=plt.subplots(2,4,figsize=(14,7),constrained_layout=True)
    for col,region in enumerate(REGIONS):
        for row,cls in enumerate(['seasonal','permanent']):
            ax=axes[row,col];f=adjusted[(adjusted.region==region)&(adjusted.scope=='primary_pre2022')&(adjusted.source_class==cls)].sort_values('year')
            area=float(annual[annual.region==region].common_support_area_km2.iloc[0])
            ax.plot(f.year,f.observed_fraction*area,label='Observed source class',color='#525969',alpha=.75)
            ax.plot(f.year,f.fixed_climate_expected_fraction_model_derived*area,label='Fixed-climate model expectation',color='#b36518')
            ax.set_title(LABELS[region]+'\n'+cls.title());ax.set_xlabel('Year');ax.set_ylabel('Fixed-cohort area (km²)');ax.grid(alpha=.15)
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=2)
    fig.suptitle('Annual weather-adjusted associations; expected lines are model-derived')
    save(fig,directory/'02_annual_fixed_climate_expectations')
    fig,axes=plt.subplots(1,2,figsize=(11,6),constrained_layout=True)
    for ax,cls in zip(axes,['seasonal','permanent']):
        for i,region in enumerate(REGIONS):
            raw=models[(models.region==region)&(models.source_class==cls)&(models.scope=='primary_pre2022')].iloc[0]
            extra=effort[(effort.region==region)&(effort.source_class==cls)&(effort.setting=='mean_and_wet_observation_effort')].iloc[0]
            step=effort[(effort.region==region)&(effort.source_class==cls)&(effort.setting=='mean_wet_effort_and_2016_asset_step')].iloc[0]
            for offset,r,color in [(-.2,raw,'#b36518'),(0,extra,'#16808a'),(.2,step,'#7755ad')]:
                x=r.time_coefficient_logit_per_year
                ax.errorbar(x,i+offset,xerr=[[x-r.lower95],[r.upper95-x]],fmt='o',color=color,capsize=3)
        ax.axvline(0,color='black',linestyle='--',linewidth=.8)
        ax.set_yticks(range(4),[LABELS[r] for r in REGIONS]);ax.invert_yaxis();ax.set_title(cls.title())
        ax.set_xlabel('Time coefficient: logit class share / year (95% interval)');ax.grid(axis='x',alpha=.15)
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5));ax.tick_params(axis='x',labelsize=9)
    fig.legend(handles=[Line2D([0],[0],marker='o',color='#b36518',label='Primary: climate only'),
        Line2D([0],[0],marker='o',color='#16808a',label='Exploratory: climate + mean/wet observation effort'),
        Line2D([0],[0],marker='o',color='#7755ad',label='Exploratory: climate + effort + 2016 asset-boundary step')],loc='outside lower center',ncol=1)
    fig.suptitle('Observation and source-boundary sensitivity; union overlaps districts')
    save(fig,directory/'03_climate_and_observation_effort_sensitivity')
    fig,axes=plt.subplots(4,1,figsize=(12,9),sharex=True,constrained_layout=True)
    for ax,region in zip(axes,REGIONS):
        f=spi[(spi.region==region)&(spi.scale_months==3)].sort_values(['year','month']);x=pd.to_datetime(f.period)
        ax.plot(x,f.spi,color='#315f9e',linewidth=.8);ax.fill_between(x,f.spi,-1,where=f.spi<=-1,color='#ba5d4d',alpha=.45)
        ax.axhline(0,color='grey',linewidth=.6);ax.axhline(-1,color='#ba5d4d',linestyle='--',linewidth=.6)
        ax.set_ylabel('SPI-3');ax.set_title(LABELS[region],loc='left');ax.set_ylim(-3.8,3.8)
    fig.suptitle('Meteorological drought: 1981–2020 gamma calibration, 2000–2024 outputs')
    save(fig,directory/'04_spi3_drought_history')
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for ax,region in zip(axes.ravel(),REGIONS):
        f=support[(support.region==region)&(support.threshold_pct==95)&(support.water_group=='all_water')].copy()
        reference=f[f.year<=2021].groupby('month').water_fraction.count()
        usable=f.water_fraction.notna()&f.month.map(reference).ge(5)
        matrix=np.zeros((12,25),dtype=int)
        for y,m,u in zip(f.year,f.month,usable):matrix[m-1,y-2000]=int(u)
        ax.imshow(matrix,cmap=ListedColormap(['#edf0f4','#2879a4']),vmin=0,vmax=1,aspect='auto',interpolation='nearest',origin='upper')
        e=events[(events.region==region)&(events.water_group=='all_water')]
        onset=pd.PeriodIndex(e.onset_period,freq='M')
        ax.scatter(onset.year-2000,onset.month-1,facecolors='none',edgecolors='#b94431',s=36,linewidths=1)
        ax.set_xticks([0,5,10,15,20,24],[2000,2005,2010,2015,2020,2024]);ax.set_yticks(range(12),['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
        ax.set_title(LABELS[region]);ax.set_xlabel('Year')
    fig.legend(handles=[Line2D([0],[0],marker='s',color='#2879a4',linestyle='none',label='Usable observed monthly anomaly'),
        Line2D([0],[0],marker='s',color='#edf0f4',linestyle='none',label='Unavailable'),
        Line2D([0],[0],marker='o',color='#b94431',markerfacecolor='none',linestyle='none',label='SPI-3 episode onset')],loc='outside lower center',ncol=3)
    fig.suptitle('Why event recovery cannot be estimated: observations are seasonally incomplete')
    save(fig,directory/'05_monthly_recovery_observation_gaps')
    fig,ax=plt.subplots(figsize=(11,5),constrained_layout=True)
    for region in REGIONS:
        f=quality[quality.region==region].sort_values('year');ax.plot(f.year,f.mean_observed_calendar_months,label=LABELS[region])
    ax.set_xlabel('Year');ax.set_ylabel('Area-weighted observed months / year');ax.set_ylim(0,12);ax.legend(ncol=2);ax.grid(alpha=.15)
    ax.set_title('Observation opportunity changes over time on the fixed annual cohort')
    save(fig,directory/'06_annual_observation_effort')
    fig,ax=plt.subplots(figsize=(9,5),constrained_layout=True)
    statuses=['AUTOMATED_CONSENSUS','MIXED_PIXEL','SENSOR_DISAGREEMENT','INSUFFICIENT_PIXEL_SUPPORT']
    counts=comparison.status.value_counts().reindex(statuses,fill_value=0)
    bars=ax.bar(['Two-sensor consensus','Mixed pixel','Sensor disagreement','Low scene/support'],counts,color=['#2879a4','#d9ab44','#bf6150','#9299a7'])
    ax.bar_label(bars,padding=3);ax.set_ylabel('Sample locations');ax.set_ylim(0,max(counts)*1.17)
    ax.set_title('720 real locations: automated evidence, not verified classification accuracy')
    save(fig,directory/'07_independent_sensor_evidence_status')
    for name in ['annual_transition_primary_pre2022.png','annual_transition_primary_pre2022.tif']:
        shutil.copy2(out/name,directory/('08_'+name))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args();out=args.run.resolve()
    manifest=json.loads((out/'run_manifest.json').read_text());require(manifest['software_run_complete'],'Run incomplete')
    cfg=manifest['config']
    require((cfg['start_year'],cfg['primary_end_year'],cfg['end_year'],cfg['primary_threshold'])==(2000,2021,2024,95),
            'This report template requires the documented 2000-2024/95% primary design')
    annual=pd.read_csv(out/'annual_common_support_water.csv');trends=pd.read_csv(out/'annual_trend_results.csv')
    adjusted=pd.read_csv(out/'annual_class_climate_adjusted.csv');models=pd.read_csv(out/'annual_climate_model_status.csv')
    spi=pd.read_csv(out/'spi_indices.csv');params=pd.read_csv(out/'spi_calibration_parameters.csv');events=pd.read_csv(out/'drought_recovery_events.csv')
    quality=pd.read_csv(out/'annual_observation_quality.csv');effort=pd.read_csv(out/'annual_observation_effort_climate_sensitivity.csv')
    support=pd.read_csv(out/'monthly_common_support_water.csv');comparison=pd.read_csv(out/'independent_sensor_evidence/primary_sensor_comparison.csv')
    sensor_sensitivity=pd.read_csv(out/'independent_sensor_evidence/cross_sensor_agreement_sensitivity.csv')
    # Independently verify source-output relationships and absence of fabricated recovery/reference results.
    require(len(annual)==100 and len(spi)==2400 and len(params)==96 and (params.status=='PASS').all(),'Incomplete real analysis')
    require(annual.eligible.all() and np.allclose(annual[['nonwater_area_km2','seasonal_water_area_km2','permanent_water_area_km2']].sum(axis=1),annual.common_support_area_km2),'Annual cohort reconciliation failed')
    require(len(comparison)==720 and comparison.sample_id.nunique()==720,'Sensor sample roster invalid')
    require(events.loc[events.status!='RECOVERY_CONFIRMED','recovery_months'].isna().all(),'Censored duration was filled')
    require(pd.read_csv(out/'independent_validation_metrics.csv').empty,'Unexpected verified accuracy without labels')
    endpoint=[]
    for region in REGIONS:
        frame=annual[annual.region==region].set_index('year')
        for cls in ['seasonal','permanent']:
            first=float(frame.loc[2000,f'{cls}_water_area_km2']);last=float(frame.loc[2021,f'{cls}_water_area_km2'])
            endpoint.append({'region':region,'source_class':cls,'area_2000_km2':first,'area_2021_km2':last,
                'endpoint_change_km2':last-first,'endpoint_change_pct':100*(last-first)/first,'scope':'primary_2000_2021_fixed_annual_cohort'})
    endpoints=pd.DataFrame(endpoint);endpoints.to_csv(out/'primary_endpoint_changes.csv',index=False)
    regional=events.drop_duplicates(['region','onset_period'])
    primary_recovery=events.groupby(['region','water_group','status']).size().rename('event_group_records').reset_index()
    primary_recovery.to_csv(out/'drought_recovery_identifiability.csv',index=False)
    failures=[]
    for (region,group),frame in support[support.threshold_pct==95].groupby(['region','water_group']):
        frame=frame.sort_values(['year','month']).copy();frame.index=pd.PeriodIndex(frame.period,freq='M')
        ref=frame[frame.year<=2021].groupby('month').water_fraction.count()
        for e in events[(events.region==region)&(events.water_group==group)].itertuples():
            onset=pd.Period(e.onset_period,freq='M');pre=pd.period_range(onset-3,onset-1,freq='M')
            values=frame.water_fraction.reindex(pre)
            fails={'region':region,'water_group':group,'onset_period':e.onset_period,'status':e.status,
                'raw_pre_event_water_observations':int(values.notna().sum()),
                'pre_event_calendar_months_with_reference_n_ge_5':int((ref.reindex(pre.month).fillna(0)>=5).sum())}
            failures.append(fails)
    pd.DataFrame(failures).to_csv(out/'recovery_failure_components.csv',index=False)
    sensitivity=[]
    for threshold,path in [(95,out),(90,out/'recovery_sensitivity_90'),(80,out/'recovery_sensitivity_80')]:
        f=pd.read_csv(path/'drought_recovery_events.csv')
        for status,n in f.status.value_counts().items():sensitivity.append({'threshold_pct':threshold,'status':status,'records':int(n),'confirmed_recoveries':int((f.status=='RECOVERY_CONFIRMED').sum())})
    recovery_sensitivity=pd.DataFrame(sensitivity);recovery_sensitivity.to_csv(out/'recovery_coverage_sensitivity_status.csv',index=False)
    cv=pd.read_csv(out/'annual_calendar_cross_validation.csv');cv=cv[cv.status=='PASS']
    cv['model_better_than_training_mean']=cv.rmse<cv.training_mean_baseline_rmse
    cv_summary=cv.groupby(['region','source_class']).agg(accepted_folds=('rmse','size'),
        mean_fold_rmse=('rmse','mean'),mean_fold_baseline_rmse=('training_mean_baseline_rmse','mean'),
        folds_model_better=('model_better_than_training_mean','sum')).reset_index()
    cv_summary.to_csv(out/'annual_predictive_validation_summary.csv',index=False)
    mcv=pd.read_csv(out/'calendar_block_cross_validation.csv');mcv=mcv[(mcv.status=='PASS')&(mcv.threshold_pct==95)].copy()
    mcv['model_better']=mcv.rmse<mcv.seasonal_baseline_rmse
    monthly_cv=mcv.groupby(['region','water_group']).agg(accepted_folds=('rmse','size'),mean_fold_rmse=('rmse','mean'),
        mean_fold_baseline_rmse=('seasonal_baseline_rmse','mean'),folds_model_better=('model_better','sum')).reset_index()
    monthly_cv.to_csv(out/'monthly_predictive_validation_summary.csv',index=False)
    figures(out,annual,adjusted,spi,events,quality,effort,models,support,comparison)
    union=endpoints[endpoints.region=='All_districts'].set_index('source_class')
    seasonal=union.loc['seasonal'];permanent=union.loc['permanent']
    total_first=float(annual[(annual.region=='All_districts')&(annual.year==2000)][['seasonal_water_area_km2','permanent_water_area_km2']].sum(axis=1).iloc[0])
    total_last=float(annual[(annual.region=='All_districts')&(annual.year==2021)][['seasonal_water_area_km2','permanent_water_area_km2']].sum(axis=1).iloc[0])
    agreed=comparison[comparison.consensus_label.notna()];matching=int((agreed.consensus_label==agreed.predicted_water).sum())
    counts=comparison.status.value_counts().to_dict()
    result={'analysis_date_client_dhaka':'2026-10-13','computational_analysis_complete':True,'scientific_publication_ready':False,
        'primary_period':[2000,2021],'full_period_sensitivity':[2000,2024],
        'fixed_annual_water_reference_cohort_km2':float(annual[annual.region=='All_districts'].common_support_area_km2.iloc[0]),
        'seasonal_class_endpoint_change_pct':float(seasonal.endpoint_change_pct),
        'permanent_class_endpoint_change_pct':float(permanent.endpoint_change_pct),
        'total_observed_source_water_endpoint_change_pct':100*(total_last-total_first)/total_first,
        'spi_output_records':len(spi),'calibration_parameters_passed':len(params),
        'regional_drought_episodes_including_overlapping_union':len(regional),
        'district_episode_records_excluding_union':int((regional.region!='All_districts').sum()),
        'recovery_cohort_event_records':len(events),'confirmed_recovery_times':int((events.status=='RECOVERY_CONFIRMED').sum()),
        'reason_no_recovery_duration':'Every event-group record fails required pre-event or drought-phase observed water support; not evidence of non-recovery.',
        'automated_sensor_consensus_locations':len(agreed),'ambiguous_or_insufficient_locations':len(comparison)-len(agreed),
        'jrc_matching_consensus_locations':matching,'independent_human_verified_labels':0,
        'permanent_linear_trend_robust_to_2016_asset_step':False,
        '2016_step_sensitivity_is_exploratory_and_not_proof_of_artefact':True,
        'source_data_modified':False,'method_scripts':['postprocessing/independent_sensor_check.py','postprocessing/annual_quality_sensitivity.py','postprocessing/summarize_results.py']}
    write_json(out/'FINAL_STATUS.json',result)
    primary_trends=trends[trends.scope=='primary_pre2022'][['region','metric','slope_km2_per_year','slope_lower95','slope_upper95','p_adjusted_BY_primary_districts']]
    primary_models=models[models.scope=='primary_pre2022'][['region','source_class','time_coefficient_logit_per_year','lower95','upper95','p_adjusted_BY_primary_districts']]
    effort_selected=effort[effort.setting=='mean_and_wet_observation_effort'][['region','source_class','time_coefficient_logit_per_year','lower95','upper95','p_adjusted_BY_within_setting_primary_districts']]
    step_selected=effort[effort.setting=='mean_wet_effort_and_2016_asset_step'][['region','source_class','time_coefficient_logit_per_year','lower95','upper95','p_adjusted_BY_within_setting_primary_districts','asset_step_coefficient_logit']]
    require(len(step_selected)==8 and (effort.status=='PASS').all(),'Incomplete source-boundary sensitivity')
    text=f'''# Results report — completed available-data analysis, 13 October 2026

## Status and principal interpretation

The computational analysis is complete using the actual audited local downloads. It is **not a publication-ready, independently accuracy-validated study**. Genuine dated human-reviewed labels are absent; monthly optical observations cannot identify the requested recovery durations under the configured rules.

The strongest supported descriptive result is a decline in source-class seasonal surface-water area within a stable retrospectively selected water footprint. Permanent-class area rises between the endpoints, but its fitted linear time association is not robust to a supplementary 2016 asset-boundary step in the union or any district. Source labels are not proof of ecological improvement, water volume, or twelve directly observed wet months.

Primary trend period is **2000–2021**; Collection 2 (2022–2024) is a separate version-step sensitivity. The fixed annual cohort covers **{result['fixed_annual_water_reference_cohort_km2']:.2f} km²**, about 79.3% of the retrospective annual ever-water reference footprint, not the full districts. Its selection conditions on future observation availability and historical water occurrence.

## 1. Observed source-class endpoint changes

For the overlapping three-district union: seasonal class **{seasonal.area_2000_km2:.2f} → {seasonal.area_2021_km2:.2f} km² ({seasonal.endpoint_change_pct:.2f}%)**; permanent class **{permanent.area_2000_km2:.2f} → {permanent.area_2021_km2:.2f} km² (+{permanent.endpoint_change_pct:.2f}%)**. Observed combined source water area is **{total_first:.2f} → {total_last:.2f} km² ({result['total_observed_source_water_endpoint_change_pct']:.2f}%)**. These endpoint comparisons are descriptive; fitted annual slopes and uncertainty are separate.

{table(endpoints.drop(columns=['scope']),2)}

## 2. Primary trend tests

{table(primary_trends)}

Seasonal negative slopes are supported in Naogaon and Rajshahi after the declared BY district-test correction; the primary Chapainawabganj seasonal slope interval includes zero. Permanent positive unadjusted slopes are supported in Naogaon and Chapainawabganj after correction; Rajshahi's adjusted p-value is above 0.05. The union is descriptive and excluded from independent-district multiplicity correction.

## 3. Annual climate-adjusted associations

{table(primary_models)}

The climate-only models retain a negative seasonal time association in Naogaon and Rajshahi and a positive permanent association in each district after the model-family BY adjustment. Chapainawabganj's seasonal association is inconclusive in the primary model. Effects are logit share per year, not km²/year, and do not identify pumping, land use, or human causation.

Annual source-class fractions are modeled separately. Their adjusted values must not be summed as a compositional total. Reference-weather expectations are model-derived, not reconstructed observations.

## 4. Observation-effort sensitivity

Mean calendar-month observation effort on the union cohort changes from **{quality[(quality.region=='All_districts')&(quality.year==2000)].mean_observed_calendar_months.iloc[0]:.2f} months in 2000** to **{quality[(quality.region=='All_districts')&(quality.year==2021)].mean_observed_calendar_months.iloc[0]:.2f} in 2021**. Monthly history shows that even source-class permanent pixels need not have all twelve months directly observed. Thus source class and observed hydroperiod must remain distinct.

An **exploratory**, unpreregistered sensitivity adds annual mean observation effort and June–September observation effort to the same climate/time models. These covariates address opportunity/seasonal selection partially, without proving bias removal. District-test adjustments are within each supplementary model family.

{table(effort_selected)}

Seasonal decline remains negative in these models, including Chapainawabganj; Naogaon's permanent time interval now includes zero. Report this loss of robustness rather than claiming uniformly strong permanent gains across districts.

### Exploratory 2016 source-asset boundary control

The [official JRC release notes](https://global-surface-water.appspot.com/download) state that 2016–2021 seasonality and derived YearlyHistory were recomputed. Our annual input switches to these corrected assets in 2016. This boundary is distinct from the 2022 Landsat Collection 2 transition. To check whether a smooth time association depends on this junction, a further **exploratory, unpreregistered** model adds an indicator for years ≥2016 to climate and observation-effort controls. It retains the same 22 annual observations and calendar HAC, with fewer residual degrees of freedom.

{table(step_selected)}

All permanent time-coefficient intervals now include zero, including the union. Seasonal decline remains supported in Naogaon and Rajshahi after within-family BY correction, whereas Chapainawabganj is inconclusive. Thus the observed +41.04% permanent endpoint difference does **not** establish a robust smooth permanent-water increase. The step may absorb real abrupt hydrological change as well as processing differences; these data cannot distinguish them. This is not proof that the gain is an artefact. Primary model results are retained transparently, rather than replacing them after examining the estimates.

## 5. Predictive checking

Annual calendar-block folds:

{table(cv_summary)}

Primary 95% monthly calendar-block folds:

{table(monthly_cv)}

Annual permanent models beat the training-mean baseline on mean fold RMSE for all regions; seasonal climate models do not. Monthly predictive results vary and several models are worse than the training-only seasonal baseline. Do not claim climate adjustment improves prediction generally. These checks concern conditional hindcast fit, not independent water-classification accuracy; folds have few test observations and spatial cohorts were retrospectively chosen.

## 6. SPI and recovery identifiability

All **96** calendar-specific gamma calibration parameters pass; **2,400** SPI rows represent 300 months × four regions × two scales. There are **{len(regional)} regional SPI-3 episode records**, including the overlapping union; **{result['district_episode_records_excluding_union']}** district episode records exclude the union. These are not independent countrywide drought events.

The three water cohorts generate **{len(events)} event-group records**. At primary 95%, **269** lack a valid three-consecutive-month pre-event observed anomaly baseline and **28** lack complete drought-phase water observations. **Zero recovery durations are identifiable.** This does not mean zero recovery, infinite recovery time, or that water did not return.

Anomaly availability combines actual raw observation support and the configured minimum five historical reference observations per calendar month. `recovery_failure_components.csv` separates these components; do not equate every anomaly failure with a physically absent raw image.

The prespecified 80% and 90% coverage sensitivities also identify no durations:

{table(recovery_sensitivity,0)}

An exploratory calendar-reference adequacy check using minimum 3, 5, or 8 observations per month also identifies zero durations. In the primary baseline failures, 264 event-group records lack three complete raw pre-event observations; another 5 have raw observations but fail the seasonal-reference sample requirement.

Filling gaps or removing the baseline/confirmation requirement after seeing these results would manufacture unsupported recovery estimates. A defensible next analysis needs a continuous monthly all-weather surface-water record (for example a separately validated Sentinel-1 series for its available period), with independent reference evidence and a clearly shorter recovery study interval. The existing four Sentinel target months cannot supply that time series. Annual source classes cannot resolve monthly recovery times.

## 7. Independent Sentinel evidence

All **720** JRC sample centers have some S1/S2 imagery, but the full original-pixel support rule requires at least two observations and 95% usable area. A predeclared threshold benchmark (MNDWI ≥0.1 and NDWI ≥0; VV ≤−17 dB; at least 80% water or at most 20% water within the footprint) gives **{len(agreed)} two-sensor consensus cases**, **{counts.get('MIXED_PIXEL',0)} mixed pixels**, **{counts.get('SENSOR_DISAGREEMENT',0)} sensor disagreements**, and **{counts.get('INSUFFICIENT_PIXEL_SUPPORT',0)} insufficient-support cases**.

Among the consensus subset, JRC agrees in **{matching}/{len(agreed)}** locations. This is **automated conditional sensor agreement, not human-verified accuracy**. Consensus retention differs by JRC stratum (342/360 predicted nonwater versus 241/360 predicted water). Ambiguous cases are disproportionately water/edge cases. Area weighting heavily favors the more extensive nonwater class; consequently high weighted conditional agreement can be misleading as a general accuracy claim.

All nine fixed threshold combinations, without tuning against JRC:

{table(sensor_sensitivity.drop(columns=['interpretation']),2)}

The 720 blinded four-panel image chips and offline `independent_sensor_evidence/review.html` help genuine review. They contain monthly medians; individual acquisition dates cannot be invented. No `validation/reference_labels.csv` was generated or marked VERIFIED. Final independent confusion/accuracy tables intentionally remain empty.

Thresholds vary by setting and must not be assumed universal: [wetland water detection](https://www.mdpi.com/2072-4292/12/10/1614), [monthly SAR mapping](https://pmc.ncbi.nlm.nih.gov/articles/PMC6015492/), [Sentinel water mapping and temporal comparability](https://www.mdpi.com/2072-4292/14/22/5721). These studies justify a sensitivity benchmark, not local ground-truth status.

## 8. Practical value and study positioning

The evidence can support prioritizing review of shrinking seasonal-water areas and identifying where observation gaps prevent credible drought-recovery comparisons. It does not calculate water-storage volume, economic benefits, groundwater change, or intervention effectiveness. Permanent/seasonal source-class shifts are not inherently ecological improvement.

The current title's promise of class-specific drought recovery cannot be substantiated from these inputs. A more accurate **provisional** framing is **“Climate-adjusted surface-water hydroperiod change and limits to drought-recovery estimation in northwestern Bangladesh.”** The defensible contribution combines class-specific trends, climate/observation-effort checks, explicit observational limits, and independent sensor evidence. It is not a new algorithm or an established first-ever study; full literature comparison and actual reference review remain necessary.

## Reproducibility and files

Primary outputs: original `run_manifest.json`, `annual_trend_results.csv`, `annual_class_climate_adjusted.csv`, `monthly_model_coefficients.csv`, `spi_indices.csv`, `drought_recovery_events.csv`. Supplementary code/outputs are recorded separately in `postprocessing_manifest.json`. Inputs remain unchanged; all raw core hashes passed before/after the main run. New-download hashes and full TIFF decoding are in `dataset-audit/remaining_downloads_20261013_b8fa5b`.

Figures 01–08 are standalone PNG/SVG (map also native GeoTIFF). `FINAL_STATUS.json` separates computational completion from scientific readiness. No missing raw water observations or reference labels were imputed. The main run report's “COMPUTED_WITH_EVENT_CENSORING” means computation ran, not successful identification of recovery durations.
'''
    (out/'RESULTS_REPORT_EN.md').write_text(text,encoding='utf-8')
    bangla=f'''# কী ফল পাওয়া গেল — ১৩ অক্টোবর ২০২৬

## সহজ উত্তর

বাস্তব downloaded data দিয়ে হিসাব শেষ হয়েছে। **যেসব একই জায়গায় সব বছরের annual class পাওয়া গেছে, সেই সীমিত জায়গাগুলোতে মৌসুমি পানিযুক্ত এলাকা কমেছে।** Permanent হিসেবে classified এলাকা মোট হিসাবে বেড়েছে, তবে এটি পানি বেশি গভীর হয়েছে বা পরিবেশ ভালো হয়েছে—এমন প্রমাণ নয়।

মূল তুলনা **২০০০–২০২১**। ২০২২–২০২৪-এ satellite source-এর version বদলেছে, তাই পুরো ২০০০–২০২৪ ফল আলাদা sensitivity। নিচের সংখ্যাগুলো পুরো জেলার সব জলাশয়ের হিসাব নয়; একই **{result['fixed_annual_water_reference_cohort_km2']:.2f} km²** নির্বাচিত জায়গার হিসাব।

| পানির ধরন | ২০০০ সালে | ২০২১ সালে | পরিবর্তন |
|---|---:|---:|---:|
| Seasonal source class | {seasonal.area_2000_km2:.2f} km² | {seasonal.area_2021_km2:.2f} km² | {abs(seasonal.endpoint_change_pct):.1f}% কম |
| Permanent source class | {permanent.area_2000_km2:.2f} km² | {permanent.area_2021_km2:.2f} km² | {permanent.endpoint_change_pct:.1f}% বেশি |
| দুই class-এর observed যোগফল | {total_first:.2f} km² | {total_last:.2f} km² | {abs(result['total_observed_source_water_endpoint_change_pct']):.1f}% কম |

## আবহাওয়ার হিসাব ধরলে কী হলো?

বৃষ্টি, তাপমাত্রা ও evaporation demand-এর হিসাব ধরার পরও নওগাঁ ও রাজশাহীতে মৌসুমি class কমার প্রবণতা থাকে। চাঁপাইনবাবগঞ্জের মূল model-এ এই কমার প্রমাণ দুর্বল। কত মাস satellite দেখতে পেরেছে সেটাও ধরলে seasonal কমার ফল থাকে; নওগাঁয় permanent বৃদ্ধির প্রমাণ তখন দুর্বল হয়। তাই সব জেলায় একই নিশ্চিত কথা বলা ঠিক হবে না। মানুষের কাজই কারণ—সেটিও এই model প্রমাণ করে না।

## Dataset-এর ২০১৬ সালের সংশোধন ধরলে কী হয়?

Permanent-class-এর এলাকা দুই বছরের তুলনায় বেড়েছে। কিন্তু dataset-এর ২০১৬ সালের সংশোধনের সীমানা আলাদা করে model-এ ধরলে তিন জেলা ও একসঙ্গে হিসাব—কোনোটিতেই নিয়মিত permanent বৃদ্ধির নিশ্চিত প্রমাণ থাকে না। মৌসুমি পানি কমার ফল নওগাঁ ও রাজশাহীতে তখনও থাকে। তাই **স্থায়ী পানি সত্যিই নিয়মিত বাড়ছে—এমন সিদ্ধান্ত এখন নেওয়া যাবে না**। এই অতিরিক্ত পরীক্ষা বাস্তব আকস্মিক পরিবর্তনও শোষণ করতে পারে; dataset-এর ভুলই কারণ, সেটিও প্রমাণ হয়নি।

## খরার পরে পানি ফিরতে কত মাস লাগল?

**এখনকার data দিয়ে বিশ্বাসযোগ্য সময় বের করা যায়নি।** বৃষ্টির পুরোনো data ঠিক আছে; SPI-এর ৯৬টি calibration check pass। কিন্তু খরার আগের ও খরা চলাকালীন দরকারি consecutive পানির observation নেই। ৮০%, ৯০%, ৯৫% তিন setting-এও সময় নিশ্চিত হয়নি।

এর মানে পানি ফেরেনি নয়। এর মানে **যথেষ্ট ছবি দেখে নিশ্চিত করা যায়নি**। সময় পেতে continuous মাসিক radar-water series এবং তার যাচাই লাগবে; এখনকার চার মাসের Sentinel ছবি দিয়ে বহু বছরের মাসিক gap পূরণ করা যায় না। বানানো সংখ্যা বা interpolation বসাইনি।

## ছবিতে পানি সত্যি আছে কি না যাচাই

৭২০টি আসল জায়গায় দুই ধরনের Sentinel evidence মিলিয়েছি। ৫৮৩টিতে স্বয়ংক্রিয় দুই-sensor সিদ্ধান্ত মেলে; ১৩৭টি মিশ্র/বিরোধপূর্ণ/অপর্যাপ্ত রেখেছি। সেই ৫৮৩টির মধ্যে JRC-এর সঙ্গে ৫৬৩টি মেলে। **এটি verified accuracy নয়**—অনিশ্চিত জায়গা বাদ গেছে এবং মানুষের dated-image যাচাই হয়নি।

প্রতিটি sample-এর দেখার ছবি তৈরি করেছি। খুলবে: **[ছবি দেখার পাতা](independent_sensor_evidence/review.html)**। হলুদ বাক্সটি original pixel। Ground-truth label/date বানিয়ে পূরণ করিনি; independent accuracy table তাই ফাঁকা।

## আমাদের কাজে লাভ কী?

কোথায় মৌসুমি পানির এলাকা কমছে, কোন দাবি observation-এর ঘাটতিতে দুর্বল, আর কোন খরার recovery বলা যাচ্ছে না—এগুলো প্রমাণসহ জানা গেল। জলাশয় সংরক্ষণ ও monitoring-এর অগ্রাধিকার নিয়ে কাজে লাগতে পারে। পানির গভীরতা, মোট আয়তন/volume, groundwater বা লাভের টাকা হিসাব হয়নি।

## কোন কাজ শেষ, কোনটি হয়নি?

- Data audit, baseline processing, annual/monthly climate models, SPI, recovery eligibility checks, sensitivity, maps/graphs ও ফলের report তৈরি শেষ।
- ৭২০টি blinded review image ও automated cross-sensor comparison তৈরি শেষ।
- মানুষের genuine dated-reference যাচাই এবং বিশ্বাসযোগ্য monthly recovery durations এখনও পাওয়া যায়নি।
- তাই **গবেষণার হিসাব শেষ; পুরো topic-এর সব দাবি প্রমাণিত বা paper submission-ready বলা যাবে না**। বর্তমান ফল অনুযায়ী title-এ “drought recovery time” নিশ্চিত ফল হিসেবে রাখা উচিত নয়।

বিস্তারিত numbers ও সীমা: [English results report](RESULTS_REPORT_EN.md)। Graphs: `Figures` folder। Software status: `FINAL_STATUS.json`।
'''
    (out/'FINAL_RESULT_BN.md').write_text(bangla,encoding='utf-8')
    hashes={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'postprocessing').glob('*.py'))}
    supplemental={'client_date':'2026-10-13','method_script_sha256':hashes,'primary_run_manifest_sha256':digest(out/'run_manifest.json'),
        'postprocessing_outputs_sha256':{str(p.relative_to(out)):digest(p) for p in out.glob('*.csv')},
        'tests':'See FINAL_CHECKS.json and code-verification/package_check.json for completed test results','scientific_publication_ready':False,
        'scope':'Primary methods unchanged; observation-effort, 2016 asset-boundary and automatic Sentinel comparisons are explicit supplementary analyses'}
    write_json(out/'postprocessing_manifest.json',supplemental)
    print(json.dumps(result,indent=2));print('Read:',out/'FINAL_RESULT_BN.md')

if __name__=='__main__':main()
