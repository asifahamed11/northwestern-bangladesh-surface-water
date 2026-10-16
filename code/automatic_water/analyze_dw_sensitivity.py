"""Audit all real sensitivity exports and analyze them alongside the unchanged radar data.

No threshold is selected by agreement. No independent labels are fabricated.
"""
from pathlib import Path
import argparse, hashlib, json, sys, uuid
from datetime import datetime
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from automatic_water import analyze as base
from research_pipeline.common import digest, require, write_json
from research_pipeline.drought import drought_events

METHOD='automatic_dw_sensitivity_v1'
THRESHOLDS=[50,60,70,80]
KEY=['year','month','region','water_group']
PROPERTIES=['method','year','month','period','region','water_group','sar_track','s1_images','s1_days','dw_images','dw_days','jrc_images','source_snapshot_sha256']
AREA_NAMES=['domain_area_km2','sar_observed_area_km2','sar_primary_water_area_km2','sar_cell_known_area_km2',
            'dw_observed_area_km2','jrc_observed_area_km2','jrc_water_area_km2'] + [
    f'dw_t{t}_{kind}_area_km2' for t in THRESHOLDS for kind in ['known','water','cell_known','sar_pair','sar_same','jrc_pair','jrc_same']]
FILES=[f'dw_sensitivity_{y}.csv' for y in base.YEARS]+['dw_sensitivity_settings.csv','dw_sensitivity_scene_inventory.csv']

def validate_frame(frame,old,snapshot):
    f=frame
    expected={(y,m,r,g) for y in base.YEARS for m in range(1,13) for r in base.REGIONS for g in base.GROUPS}
    require(len(f)==1440 and set(map(tuple,f[KEY].to_numpy()))==expected,'Expected 1440 unique sensitivity month/region/cohort rows')
    require(list(f.columns)==PROPERTIES+AREA_NAMES,'Unexpected sensitivity schema/order')
    require(not f.isna().any().any(),'Missing sensitivity field')
    require(f.method.eq(METHOD).all(),'Wrong sensitivity method')
    require(f.period.eq(f.year.astype(str)+'-'+f.month.astype(str).str.zfill(2)).all(),'Wrong period labels')
    require(f.sar_track.eq(snapshot['sar_track']).all(),'Radar track changed')
    require(f.source_snapshot_sha256.eq(snapshot['source_snapshot_sha256']).all(),'Wrong source snapshot')
    require(np.isfinite(f[AREA_NAMES].to_numpy(float)).all() and (f[AREA_NAMES]>=-1e-8).all().all(),'Nonfinite/negative area')
    for name in AREA_NAMES[1:]:require((f[name]<=f.domain_area_km2+1e-6).all(),'Area exceeds cohort: '+name)
    for smaller,larger in [('sar_primary_water_area_km2','sar_observed_area_km2'),('jrc_water_area_km2','jrc_observed_area_km2')]:
        require((f[smaller]<=f[larger]+1e-6).all(),'Water outside observed support')
    require((.95*f.sar_cell_known_area_km2<=f.sar_observed_area_km2+1e-6).all(),'Unsupported radar agreement cells')
    for t in THRESHOLDS:
        p=f'dw_t{t}'
        require((f[p+'_water_area_km2']<=f[p+'_known_area_km2']+1e-6).all(),'DW water exceeds known support')
        require((f[p+'_known_area_km2']<=f.dw_observed_area_km2+1e-6).all(),'DW classified area exceeds observations')
        require((.95*f[p+'_cell_known_area_km2']<=f[p+'_known_area_km2']+1e-6).all(),'Unsupported DW agreement cells')
        for sensor,other in [('sar','sar_cell_known_area_km2'),('jrc','jrc_observed_area_km2')]:
            pair=f[p+'_'+sensor+'_pair_area_km2'];same=f[p+'_'+sensor+'_same_area_km2']
            require((same<=pair+1e-6).all(),'Agreement exceeds paired area')
            require((pair<=f[p+'_cell_known_area_km2']+1e-6).all() and (pair<=f[other]+1e-6).all(),'Pair exceeds common support')
    for a,b in zip(THRESHOLDS,THRESHOLDS[1:]):
        for kind in ['known','water']:
            require((f[f'dw_t{b}_{kind}_area_km2']<=f[f'dw_t{a}_{kind}_area_km2']+1e-6).all(),'Threshold areas not nested')
    union=f[f.region=='All_districts'].set_index(['year','month','water_group'])[AREA_NAMES].sort_index()
    summed=f[f.region!='All_districts'].groupby(['year','month','water_group'])[AREA_NAMES].sum().sort_index()
    require(np.allclose(union,summed,rtol=1e-8,atol=1e-6),'District/union area reconciliation failed')
    new=f.set_index(KEY).sort_index();prior=old.set_index(KEY).sort_index()
    # These controls isolate confidence thresholds from changed masks/scenes/grid.
    comparisons={n:n for n in ['domain_area_km2','sar_observed_area_km2','dw_observed_area_km2','jrc_observed_area_km2','jrc_water_area_km2']}
    comparisons.update(sar_primary_water_area_km2='sar_m17_water_area_km2',
        dw_t80_known_area_km2='dw_known_area_km2',dw_t80_water_area_km2='dw_water_area_km2',
        dw_t80_sar_pair_area_km2='sar_dw_pair_area_km2',dw_t80_sar_same_area_km2='sar_dw_same_area_km2',
        dw_t80_jrc_pair_area_km2='dw_jrc_pair_area_km2',dw_t80_jrc_same_area_km2='dw_jrc_same_area_km2')
    for name,control in comparisons.items():
        require(np.allclose(new[name],prior[control],rtol=1e-8,atol=1e-6),'Frozen original calculation changed: '+name)
    for name in ['s1_images','s1_days','dw_images','dw_days','jrc_images']:
        require(new[name].eq(prior[name]).all(),'Original source count changed: '+name)
    return f

def audit_downloads(folder):
    snapshot=json.loads((ROOT/'automatic_water/DW_SENSITIVITY_SNAPSHOT.json').read_text(encoding='utf-8'))
    original_folder=ROOT/'NW_Bangladesh_automatic_water_2015_2024'
    old,original_settings,original_hashes=base.audit_downloads(original_folder)
    for item in snapshot['base_file_hashes']:
        require(digest(original_folder/item['filename'])==item['sha256'],'Original input changed since source snapshot')
    missing=[n for n in FILES if not (folder/n).is_file()]
    require(not missing,'Missing sensitivity exports: '+', '.join(missing))
    require(len(list(folder.glob('dw_sensitivity_20*.csv')))==10,'Duplicate/unexpected yearly sensitivity CSVs')
    settings=pd.read_csv(folder/'dw_sensitivity_settings.csv');require(len(settings)==1,'Expected one settings row')
    s=settings.iloc[0]
    constants={'method':METHOD,'base_method':base.METHOD,'start_year':2015,'end_year':2024,'sar_track':snapshot['sar_track'],
        'minimum_unique_days':2,'thresholds':'0.5,0.6,0.7,0.8','threshold_selected':'NONE_SENSITIVITY_ONLY',
        'vv_primary_db':-17,'angle_min':30,'angle_max':45,'agreement_cell_support':.95,'agreement_water_fraction':.8,
        'analysis_crs':'EPSG:4326','boundary_asset':original_settings.boundary_asset.iloc[0],
        'footprint':'retrospective_annual_ever_water_2000_2024','initial_classes':'strict_majority_2000_2004_all_five_observed',
        'annual_source_years':25,'annual_source_periods_ok':1,'source_snapshot_sha256':snapshot['source_snapshot_sha256'],
        'expected_sar_scenes':265,'expected_dw_scenes':1274,'accuracy_status':'AUTOMATED_AGREEMENT_NOT_GROUND_TRUTH','observations_imputed':0}
    for name,value in constants.items():require(name in s.index and s[name]==value,'Wrong sensitivity setting: '+name)
    require(np.allclose(json.loads(s.analysis_transform),json.loads(original_settings.analysis_transform.iloc[0]),rtol=0,atol=1e-15),'Analysis grid changed')
    require(s.source_jrc_crs==original_settings.source_jrc_crs.iloc[0] and np.isclose(s.source_jrc_nominal_scale_m,original_settings.source_jrc_nominal_scale_m.iloc[0]),'JRC native grid metadata changed')
    scenes=pd.read_csv(folder/'dw_sensitivity_scene_inventory.csv')
    require(len(scenes)==1539 and set(scenes.sensor)=={'S1','DW'},'Incomplete source scene inventory')
    canonical=[]
    for r in scenes.itertuples():
        asset,date=base.canonical_scene_id(r.sensor,r.scene_id);canonical.append(asset)
        require(date==r.date and int(date[:4])==r.year and int(date[5:7])==r.month,'Wrong source acquisition date')
        require(r.track==(snapshot['sar_track'] if r.sensor=='S1' else 'OPTICAL'),'Source track changed')
    require(len(set(canonical))==1539 and sorted(canonical)==snapshot['canonical_scene_ids'],'Source roster differs from frozen real scenes')
    original_scenes=pd.read_csv(original_folder/'auto_scene_inventory.csv')
    require(scenes.groupby(['sensor','year','month']).size().to_dict()==original_scenes.groupby(['sensor','year','month']).size().to_dict(),'Source periods changed')
    pieces=[]
    for year in base.YEARS:
        part=pd.read_csv(folder/f'dw_sensitivity_{year}.csv');require(len(part)==144 and part.year.eq(year).all(),'Incomplete/wrong yearly sensitivity export')
        pieces.append(part)
    f=validate_frame(pd.concat(pieces,ignore_index=True),old,snapshot)
    # Repeat the supplied November pilot as another independent export control.
    pilot_path=ROOT/'dw_threshold_pilot_2024_11.csv'
    require(pilot_path.is_file(),'The previously audited November pilot is missing')
    pilot=pd.read_csv(pilot_path).set_index(['region','water_group']).sort_index()
    nov=f[(f.year==2024)&(f.month==11)].set_index(['region','water_group']).sort_index()
    for t in THRESHOLDS:
        for kind in ['known','water','cell_known']:
            name=f'dw_t{t}_{kind}_area_km2'
            require(np.allclose(nov[name],pilot[name],rtol=1e-8,atol=1e-6),'November pilot was not reproduced: '+name)
    hashes=[{'path':str((folder/n).resolve()),'sha256':digest(folder/n)} for n in FILES]
    hashes += [{'path':str(original_folder/r['filename']),'sha256':r['sha256']} for r in original_hashes]
    hashes.append({'path':str(pilot_path),'sha256':digest(pilot_path)})
    return f,old,settings,hashes

def long_evidence(frame):
    rows=[]
    for t in THRESHOLDS:
        f=frame[KEY+['period','domain_area_km2','dw_observed_area_km2']].copy();p=f'dw_t{t}'
        d=f.domain_area_km2.replace(0,np.nan)
        f['threshold']=t/100;f['classified_area_km2']=frame[p+'_known_area_km2']
        f['classified_water_area_km2']=frame[p+'_water_area_km2']
        f['observed_fraction']=f.dw_observed_area_km2/d;f['classified_fraction']=f.classified_area_km2/d
        f['water_lower_fraction']=f.classified_water_area_km2/d
        f['water_upper_fraction']=(f.classified_water_area_km2+(d-f.classified_area_km2).clip(lower=0))/d
        f['unknown_observation_fraction']=(d-f.dw_observed_area_km2).clip(lower=0)/d
        f['unknown_classification_fraction']=(f.dw_observed_area_km2-f.classified_area_km2).clip(lower=0)/d
        for sensor in ['sar','jrc']:
            paired=frame[p+'_'+sensor+'_pair_area_km2'];same=frame[p+'_'+sensor+'_same_area_km2']
            f[sensor+'_pair_area_km2']=paired;f[sensor+'_same_area_km2']=same
            f[sensor+'_paired_fraction']=paired/d;f[sensor+'_conditional_agreement']=same/paired.replace(0,np.nan)
        rows.append(f)
    return pd.concat(rows,ignore_index=True)

def pooled_summary(long):
    rows=[]
    for (region,group,threshold),part in long.groupby(['region','water_group','threshold']):
        row={'region':region,'water_group':group,'threshold':threshold,
            'months_with_classified_support':int(part.classified_area_km2.gt(1e-9).sum()),
            'mean_classified_fraction':part.classified_fraction.mean()}
        for sensor in ['sar','jrc']:
            denominator=part[sensor+'_pair_area_km2'].sum()
            row[sensor+'_paired_months']=int(part[sensor+'_pair_area_km2'].gt(1e-9).sum())
            row[sensor+'_pooled_area_month_agreement']=part[sensor+'_same_area_km2'].sum()/denominator if denominator>0 else np.nan
            row[sensor+'_mean_paired_fraction']=part[sensor+'_paired_fraction'].mean()
        rows.append(row)
    return pd.DataFrame(rows)

def figures(long,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory=out/'Figures';directory.mkdir()
    f=long[(long.region=='All_districts')&(long.water_group=='all_water')]
    # Separate envelope panels avoid obscuring the broad uncertainty intervals.
    fig=plt.figure(figsize=(12,10),constrained_layout=True)
    layout=fig.add_gridspec(3,2,height_ratios=[1.15,1,1]);top=fig.add_subplot(layout[0,:])
    colors=['#2473b6','#d97a1c','#32944a','#b94c52']
    for index,(threshold,part) in enumerate(f.groupby('threshold')):
        part=part.sort_values(['year','month']);dates=pd.to_datetime(part.period);color=colors[index]
        top.plot(dates,part.classified_fraction,label=f'{threshold:.1f}',color=color)
        ax=fig.add_subplot(layout[1+index//2,index%2],sharex=top)
        ax.fill_between(dates,part.water_lower_fraction,part.water_upper_fraction,color=color,alpha=.23)
        ax.plot(dates,part.water_lower_fraction,color=color,linewidth=.8)
        ax.plot(dates,part.water_upper_fraction,color=color,linewidth=.8)
        ax.set_title(f'Candidate {threshold:.1f}: method/support envelope')
        ax.set_ylim(0,1.03);ax.grid(alpha=.15);ax.set_ylabel('Footprint fraction')
    top.set_ylabel('Classified footprint fraction');top.set_ylim(0,1.03);top.grid(alpha=.15)
    top.legend(title='Candidate threshold',ncol=4,loc='upper left')
    fig.suptitle('Dynamic World sensitivity; envelopes are not accuracy confidence intervals')
    for ext in ['png','svg']:fig.savefig(directory/f'01_dw_support_and_envelopes.{ext}',dpi=200)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(13,8),sharex=True,constrained_layout=True)
    for col,sensor in enumerate(['sar','jrc']):
        for threshold,part in f.groupby('threshold'):
            part=part.sort_values(['year','month']);dates=pd.to_datetime(part.period)
            axes[0,col].plot(dates,part[sensor+'_conditional_agreement'],label=f'{threshold:.1f}')
            axes[1,col].plot(dates,part[sensor+'_paired_fraction'],label=f'{threshold:.1f}')
        axes[0,col].set_title(sensor.upper()+' / DW');axes[0,col].set_ylabel('Conditional method agreement')
        axes[1,col].set_ylabel('Paired footprint fraction')
    for ax in axes.flat:ax.set_ylim(0,1.03);ax.grid(alpha=.15);ax.legend(ncol=4)
    fig.suptitle('Read agreement together with retained support; no independent accuracy labels')
    for ext in ['png','svg']:fig.savefig(directory/f'02_agreement_and_support.{ext}',dpi=200)
    plt.close(fig)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'NW_Bangladesh_DW_sensitivity_2015_2024')
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    if args.preflight:
        f,_,_,_=audit_downloads(args.input.resolve());print('PASS: 12 real exports, 1440 rows, frozen scenes/controls, and November pilot reproduced.');return
    out=ROOT/'automatic_water_outputs'/('sensitivity_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);out.mkdir(parents=True)
    state={'software_run_complete':False,'method':METHOD,'threshold_selected':None,'human_verified_accuracy':False,
        'scientific_publication_ready':False,'observations_imputed':False,'reference_labels_generated':False,'output':str(out)}
    try:
        f,old,settings,hashes=audit_downloads(args.input.resolve())
        write_json(out/'input_sha256.json',hashes);settings.to_csv(out/'downloaded_sensitivity_settings.csv',index=False)
        long=long_evidence(f);long.to_csv(out/'dw_monthly_threshold_evidence.csv',index=False)
        summary=pooled_summary(long);summary.to_csv(out/'dw_threshold_support_and_agreement.csv',index=False)
        # Radar recovery and climate models use only the original real radar
        # envelopes. Changing the DW confidence rule cannot fill radar gaps.
        used=[ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv',ROOT/'NW_Bangladesh_preprocessed/fixed_annual_everwater_footprint.tif',
              ROOT/'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif',ROOT/'NW_Bangladesh_2000_2024/verified_study_area.geojson',
              ROOT/'NW_Bangladesh_climate_baseline_1981_1999/baseline_source_inventory.csv']
        used+=sorted((ROOT/'NW_Bangladesh_climate_baseline_1981_1999').glob('*.tif'))
        require(len(used)==43 and all(p.is_file() for p in used),'Real climate/grid sources incomplete')
        climate_hashes=[{'path':str(p),'sha256':digest(p)} for p in used]
        write_json(out/'climate_input_sha256.json',climate_hashes)
        radar=base.add_envelopes(old);climate,spi=base.climate_and_spi(out)
        records=[];references=[]
        for (region,group),part in radar.groupby(['region','water_group']):
            lo,hi,ref=base.anomaly_envelopes(part);ref=ref.reset_index();ref['region']=region;ref['water_group']=group;references.append(ref)
            rain=spi[(spi.region==region)&(spi.scale_months==3)]
            series=pd.Series(rain.spi.to_numpy(),index=pd.PeriodIndex(rain.period,freq='M'));series=series[series.index.year>=2015]
            for event in drought_events(series):records.append({'region':region,'water_group':group,**base.interval_recovery(event,lo,hi)})
        event_columns=['region','water_group','onset_period','climate_end_period','minimum_spi','status',
            'recovery_min_months','recovery_max_months','recovery_months','pre_event_lower_anomaly','pre_event_upper_anomaly','deficit_lower','deficit_upper']
        events=pd.DataFrame(records,columns=event_columns);events.to_csv(out/'radar_automated_recovery_intervals.csv',index=False)
        pd.concat(references,ignore_index=True).to_csv(out/'radar_seasonal_reference_support.csv',index=False)
        base.fit_envelope_models(radar,climate,out);figures(long,out)
        for item in hashes+climate_hashes:require(digest(Path(item['path']))==item['sha256'],'Input changed during analysis')
        state.update(software_run_complete=True,download_audit_passed=True,monthly_export_rows=1440,
            threshold_evidence_rows=len(long),recovery_event_cohort_records=len(events),
            method_stable_timing_records=int(events.status.eq('TIMING_STABLE_WITHIN_ENVELOPE').sum()),
            method_interval_timing_records=int(events.status.eq('TIMING_INTERVAL_WITHIN_ENVELOPE').sum()))
        (out/'RESULT_BN.md').write_text(f'''# Sensitivity analysis-এর ফল

আসল ১২টি sensitivity CSV ও আগের ১৪টি study CSV audit হয়েছে।
চারটি confidence সীমায় {len(long)}টি মাস/region/cohort/threshold হিসাব হয়েছে।
কোনো best threshold নির্বাচন বা independent accuracy দাবি করা হয়নি।

Sensor comparison-এর সঙ্গে paired-footprint support পড়তে হবে। Pooled agreement
area-month weighted method agreement; independent validation accuracy নয়।
অজানা observation/classification জায়গা unknown হিসেবে envelope-এ রাখা হয়েছে।
এই envelope সব sensor error ধরে না এবং physical-water confidence interval নয়।

Radar recovery-তে একই আসল radar data, baseline ও support নিয়ম রাখা হয়েছে।
স্থিতিশীল timing record: {state['method_stable_timing_records']}।
Timing interval record: {state['method_interval_timing_records']}।
বাকি recovery records-এর কারণ CSV-তে আছে; missing observation দিয়ে সময় বানানো হয়নি।

Figures folder-এ support/envelope ও sensor agreement-এর graph আছে।
পুরো গবেষণাকে submission-ready ঘোষণা করা হয়নি।
''',encoding='utf-8')
        write_json(out/'STATUS.json',state);print('COMPLETE:',out/'RESULT_BN.md')
    except Exception as error:
        state['error']=str(error);write_json(out/'STATUS.json',state);(out/'RUN_ERROR.txt').write_text(str(error),encoding='utf-8');raise

if __name__=='__main__':main()
