"""CLI: python -m research_pipeline.run --preflight, or run without flags."""
from pathlib import Path
import argparse
from datetime import datetime,timezone,timedelta
import json
import sys
import traceback
import uuid
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import rasterio
from .common import ROOT,load_config,preflight,require,write_json,digest
from .spatial import Grid,build_support,extract_support_series,transition_map
from .models import annual_trends,monthly_models,annual_climate_models
from .baseline import prepare_baseline
from .drought import run_drought
from .validation import sample_plan,evaluate_reference

def plots(annual,monthly,out):
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    for ax,(region,frame) in zip(axes.ravel(),annual.groupby('region',sort=False)):
        frame=frame.sort_values('year')
        for col,label in [('permanent_water_area_km2','Permanent'),('seasonal_water_area_km2','Seasonal')]:
            ax.plot(frame.year,frame[col],label=label)
        ax.axvline(2021.5,color='grey',linestyle='--',linewidth=1)
        ax.set_title(region.replace('_',' ')); ax.set_ylabel('Water area on fixed common support (km2)')
        ax.set_xlabel('Year'); ax.legend(fontsize=8)
    fig.suptitle('Annual source water classes on a stable classified footprint')
    fig.savefig(out/'annual_water_common_support.png',dpi=180); plt.close(fig)
    with rasterio.open(out/'annual_transition_primary_pre2022.tif') as ds:
        a=ds.read(1,out_shape=(max(1,ds.height//4),max(1,ds.width//4)),resampling=rasterio.enums.Resampling.nearest)
        codes=np.full(a.shape,-1)
        groups=[[0],[11],[22],[33],[12,13],[21,31],[23],[32]]
        for n,values in enumerate(groups): codes[np.isin(a,values)]=n
        colors=['#eee3c8','#cccccc','#68b5dc','#164c8c','#369e64','#d44b43','#9458bc','#e79635']
        labels=['No strict majority','Stable nonwater','Stable seasonal','Stable permanent',
                'Water gain','Water loss','Seasonal to permanent','Permanent to seasonal']
        fig,ax=plt.subplots(figsize=(8,8))
        ax.imshow(np.ma.masked_less(codes,0),cmap=ListedColormap(colors),vmin=-.5,vmax=7.5,
                  extent=[ds.bounds.left,ds.bounds.right,ds.bounds.bottom,ds.bounds.top],interpolation='nearest')
        ax.set_aspect(1/np.cos(np.deg2rad(24.6)))
        ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
        ax.set_title('Five-year annual-class majority transitions, pre-2022')
        ax.legend(handles=[Patch(color=color,label=label) for color,label in zip(colors,labels)],
                  loc='upper center',bbox_to_anchor=(.5,-.10),ncol=2,fontsize=8)
        fig.tight_layout(); fig.savefig(out/'annual_transition_primary_pre2022.png',dpi=180,bbox_inches='tight'); plt.close(fig)

def summary_report(out,stages,config,quality,trends,model_status):
    passed=int((model_status.status=='PASS').sum()) if len(model_status) else 0
    eligible=quality[(quality.threshold_pct==config['primary_threshold'])]
    support='\n'.join(f'| {r.region} / {r.water_group} | {r.candidate_months} | {r.retained_reference_fraction:.3f} | {r.support_status} |' for r in eligible.itertuples())
    status='\n'.join(f'| {name} | {record.get("status", "COMPLETED")} | {record.get("reason", "")} |' for name,record in stages.items())
    text=f'''# Research run report

This run computes reproducible results from the real local data. Scientific publication readiness is not inferred from software completion.

## Stage status

| Stage | Status | Details |
|---|---|---|
{status}

## Primary common spatial support

Coverage threshold: {config['primary_threshold']}%. Candidate months must meet both district and fixed annual ever-water footprint coverage. Each accepted monthly outcome uses the exact same pixel cohort for its region/threshold and requires every cohort pixel to be observed. The union series has its own cohort and is not a fourth independent district.

| Region | Candidate months | Retained reference footprint fraction | Status |
|---|---:|---:|---|
{support}

Monthly models passing numerical/data checks across primary and sensitivity settings: {passed}. These checks do not validate causal attribution, sampling representativeness, or independent classification accuracy.

## Methods and interpretation

Annual trends use fixed annual support, a primary pre-2022 analysis, and full-period sensitivity with a version-step term. Separate annual permanent/seasonal logit-share models adjust for annual rain, day-weighted temperature, and annual evaporation demand. Annual class models are separate binary share models, so their adjusted estimates must not be added as a compositional total. Calendar-aware Bartlett HAC uncertainty preserves actual month/year gaps. Theil-Sen slopes are descriptive. BY multiple-testing adjustments apply to primary district trend tests; the overlapping union is excluded.

Monthly models use logit-transformed fractions (numeric boundary clip 1e-6), calendar harmonics, three-month precipitation, temperature, model potential evaporation, and a time term. Monthly responses/recovery are separate for all water and pixels labeled seasonal/permanent by a strict initial-five-year majority with all five annual observations available. These frozen labels describe initial hydroperiod cohorts, not monthly class changes. Coefficients are associations. Fixed-climate and adjusted-water outputs are explicitly model-derived estimates, never replacement observations. Pre-2022 calendar-block validation scales/fits only the training records and reports a training-only seasonal-mean comparator. The full-period version-step sensitivity does not fix spatial co-registration.

SPI uses true accumulated monthly rainfall, a 1981-2020 calendar-specific zero-adjusted gamma calibration, and minimum 30 samples per calendar month. No short-baseline substitute is generated. Recovery requires an observed pre-event baseline, observed drought-phase water anomalies, and consecutive observed confirmation months. Missingness, study endpoints, and version changes censor events. Censored recovery duration is blank.

Independent monthly binary validation uses blinded real sample locations and externally supplied verified labels. Unknown/uncertain references are excluded and incomplete strata prevent an overall accuracy estimate. This does not independently validate annual hydroperiod classes. The fixed retrospective QC footprint can exclude transient monthly water and is not a pre-existing independent wetland inventory.

Input hashes, config, source periods and package versions are recorded in run_manifest.json. Native grids are retained. No missing observations are interpolated or filled. All external-input requirements are stated in stage status.

## Main outputs

- annual_trend_results.csv, annual_common_support_water.csv
- annual_class_climate_adjusted.csv, annual_climate_model_status.csv
- monthly_common_support_water.csv, common_support_quality.csv
- climate_adjusted_water.csv, monthly_model_coefficients.csv, calendar_block_cross_validation.csv
- spi_indices.csv, drought_recovery_events.csv
- validation_points_blinded.geojson, reference_labels_to_complete.csv, independent_validation_metrics.csv
- annual transition GeoTIFF/PNG and annual common-support figure

See the code README and METHODS.md for external-input acquisition, units, assumptions, and source references. A final scientific interpretation still requires validation and methodological review.
'''
    (out/'RUN_REPORT.md').write_text(text,encoding='utf-8')

def main(argv=None):
    parser=argparse.ArgumentParser(description='NW Bangladesh research analysis; no imputation')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    parser.add_argument('--preflight',action='store_true',help='Check real inputs and hashes without analysis outputs')
    parser.add_argument('--output',type=Path,help='A NEW output directory; existing directories are never overwritten')
    args=parser.parse_args(argv)
    root=args.root.resolve(); config=load_config(args.config)
    monthly,input_status=preflight(root,config,verify_hashes=True)
    if args.preflight:
        print(json.dumps(input_status,indent=2)); return 0
    now=datetime.now(timezone(timedelta(hours=6)))
    out=args.output.resolve() if args.output else root/'research_outputs'/('run_'+now.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    for protected in ['NW_Bangladesh_2000_2024','NW_Bangladesh_preprocessed','NW_Bangladesh_climate_baseline_1981_1999','validation','research_pipeline']:
        require(not out.is_relative_to(root/protected),'Output points into a protected input/code directory')
    require(not out.exists(),'Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    from importlib.metadata import version
    stages={'input_preflight':input_status}
    manifest={'pipeline_version':'1.0.0','run_time_dhaka':now.isoformat(),'config':config,
        'config_sha256':__import__('hashlib').sha256(args.config.read_bytes()).hexdigest(),
        'input_preprocessing_manifest':str(root/'NW_Bangladesh_preprocessed/input_manifest.csv'),
        'versions':{n:version(n) for n in ['numpy','pandas','scipy','statsmodels','rasterio','shapely','pyproj','matplotlib']},
        'stages':stages,'software_run_complete':False,'scientific_publication_ready':False}
    write_json(out/'run_manifest.json',manifest)
    try:
        provenance_files=sorted(set(list((root/'NW_Bangladesh_preprocessed').glob('*'))+
            list((root/'research_pipeline').glob('*.py'))+list((root/'research_pipeline').glob('*.json'))+
            list((root/'NW_Bangladesh_climate_baseline_1981_1999').glob('*'))+
            ([root/'validation/reference_labels.csv'] if (root/'validation/reference_labels.csv').is_file() else [])))
        manifest['additional_input_and_code_hashes']={str(p.relative_to(root)):digest(p) for p in provenance_files if p.is_file()}
        print('Building native-grid common spatial support...',flush=True)
        grid=Grid(root)
        masks,candidates,annual_mask,quality=build_support(grid,monthly,config,out)
        support,annual=extract_support_series(grid,masks,candidates,annual_mask,quality,config,out)
        stages['common_support']={'status':'COMPLETED_WITH_STATUS_RECORDS','accepted_primary_region_groups':int(((quality.threshold_pct==config['primary_threshold'])&(quality.support_status=='PASS')).sum())}
        transition_map(grid,annual_mask,config,out)
        trends=annual_trends(annual,config,out)
        stages['annual_trends']={'status':'COMPLETED','numerically_accepted_models':int((trends.status=='PASS').sum())}
        climate=pd.read_csv(root/'NW_Bangladesh_preprocessed/monthly_climate.csv')
        print('Fitting annual and monthly climate models...',flush=True)
        annual_status=annual_climate_models(annual,climate,config,out)
        stages['annual_class_climate_models']={'status':'COMPLETED_WITH_STATUS_RECORDS','accepted_models':int((annual_status.status=='PASS').sum())}
        model_status=monthly_models(support,climate,config,out)
        stages['monthly_climate_models']={'status':'COMPLETED_WITH_STATUS_RECORDS','accepted_models':int((model_status.status=='PASS').sum())}
        try: baseline,baseline_status=prepare_baseline(root,grid,out)
        except ValueError as error: baseline=None; baseline_status={'status':'INPUT_REJECTED','reason':str(error)}
        stages['baseline_calibration_inputs']=baseline_status
        stages['drought_recovery']=run_drought(climate,baseline,support,config,out)
        plan=sample_plan(grid,config,out)
        stages['independent_validation']=evaluate_reference(plan,root/'validation/reference_labels.csv',config,out)
        plots(annual,support,out)
        summary_report(out,stages,config,quality,trends,model_status)
        require(all(digest(root/p)==h for p,h in manifest['additional_input_and_code_hashes'].items()),'An input/code file changed during this run')
        _,final_status=preflight(root,config,verify_hashes=True)
        stages['final_raw_hash_check']={'status':'PASS','raw_hashes_checked':final_status['raw_hashes_checked']}
        manifest['software_run_complete']=True
        write_json(out/'run_manifest.json',manifest)
        print('Run complete:',out)
        print('Review RUN_REPORT.md: missing external inputs are not successful scientific validation.')
        return 0
    except Exception as error:
        manifest['runtime_error']=str(error)
        write_json(out/'run_manifest.json',manifest)
        (out/'RUNTIME_ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,FileNotFoundError) as error:
        print('STOP:',error,file=sys.stderr); sys.exit(1)
