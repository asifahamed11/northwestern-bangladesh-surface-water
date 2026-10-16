"""Reproduce the available-data analysis and supplementary reports in a new run."""
from pathlib import Path
import sys,argparse,subprocess,json,uuid
from datetime import datetime,timezone,timedelta
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_pipeline.common import require,load_config,write_json
from research_pipeline.drought import run_drought

def command(*args):
    result=subprocess.run([sys.executable,*map(str,args)],cwd=ROOT)
    require(result.returncode==0,'Stopped at: '+' '.join(map(str,args)))

def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group()
    group.add_argument('--output',type=Path,help='New run folder')
    group.add_argument('--resume',type=Path,help='Completed main run; reuse already-created supplements')
    args=parser.parse_args()
    require((ROOT/'NW_Bangladesh_climate_baseline_1981_1999').is_dir(),'Complete analysis requires the actual historical climate downloads')
    require((ROOT/'NW_Bangladesh_independent_reference').is_dir(),'Complete evidence reports require the actual Sentinel downloads')
    audits=[p for p in (ROOT/'dataset-audit').glob('remaining_downloads_*/summary.json') if json.loads(p.read_text())['status']=='PASS']
    if not audits:command('dataset-audit/audit_remaining_downloads.py')
    if args.resume:
        out=args.resume.resolve();manifest=json.loads((out/'run_manifest.json').read_text())
        require(manifest['software_run_complete'] and manifest['stages']['baseline_calibration_inputs']['status']=='PASS','Resume requires a completed main run with real baseline data')
    else:
        now=datetime.now(timezone(timedelta(hours=6)))
        out=args.output.resolve() if args.output else ROOT/'research_outputs'/('complete_'+now.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        require(not out.exists(),'Output already exists; use a new directory')
        command('-m','research_pipeline.run','--output',out)
    if not (out/'annual_observation_effort_climate_sensitivity.csv').is_file():
        command('postprocessing/annual_quality_sensitivity.py','--run',out)
    elif 'mean_wet_effort_and_2016_asset_step' not in set(pd.read_csv(out/'annual_observation_effort_climate_sensitivity.csv').setting):
        command('postprocessing/annual_quality_sensitivity.py','--run',out,'--reuse-quality')
    if not (out/'independent_sensor_evidence/method_and_status.json').is_file():
        command('postprocessing/independent_sensor_check.py','--run',out)
    support=pd.read_csv(out/'monthly_common_support_water.csv');climate=pd.read_csv(ROOT/'NW_Bangladesh_preprocessed/monthly_climate.csv');baseline=pd.read_csv(out/'baseline_climate_1981_1999.csv')
    config=load_config(ROOT/'research_pipeline/config.json');records=[]
    for threshold in [80,90]:
        target=out/f'recovery_sensitivity_{threshold}';target.mkdir(exist_ok=True)
        settings=config.copy();settings['primary_threshold']=threshold
        write_json(target/'sensitivity_config.json',settings)
        run_drought(climate,baseline,support,settings,target)
    for minimum in [3,5,8]:
        if minimum==5:
            frame=pd.read_csv(out/'drought_recovery_events.csv')
        else:
            target=out/f'recovery_reference_count_sensitivity_{minimum}';target.mkdir(exist_ok=True)
            settings=config.copy();settings['minimum_water_reference_samples']=minimum
            write_json(target/'sensitivity_config.json',settings)
            run_drought(climate,baseline,support,settings,target)
            frame=pd.read_csv(target/'drought_recovery_events.csv')
        records.append({'minimum_water_reference_samples':minimum,'event_group_records':len(frame),
            'confirmed_recoveries':int((frame.status=='RECOVERY_CONFIRMED').sum())})
    pd.DataFrame(records).to_csv(out/'recovery_calendar_reference_sample_sensitivity.csv',index=False)
    command('postprocessing/summarize_results.py','--run',out)
    print('Available-data study report complete:',out/'FINAL_RESULT_BN.md')
    print('Independent dated human labels and identifiable recovery durations are scientific evidence requirements, not software success flags.')

if __name__=='__main__':main()
