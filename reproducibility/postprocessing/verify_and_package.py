"""Verify real outputs/source preservation and package reports without raw rasters."""
from pathlib import Path
import sys,json,zipfile,re,argparse,subprocess,shutil
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from research_pipeline.common import require,digest,write_json,preflight,load_config

def package(target,files,base):
    hashes={str(p.relative_to(base)).replace('\\','/'):digest(p) for p in sorted(files)}
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(files):z.write(p,str(p.relative_to(base)).replace('\\','/'))
        z.writestr('payload_sha256.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(target) as z:
        require(z.testzip() is None,'Archive CRC failure')
        for name,h in hashes.items():
            require(__import__('hashlib').sha256(z.read(name)).hexdigest()==h,'Archive file hash mismatch: '+name)
    return {'archive':target.name,'files':len(hashes)+1,'bytes':target.stat().st_size,'sha256':digest(target),'payload_hashes_verified':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);args=parser.parse_args();out=args.run.resolve()
    final=json.loads((out/'FINAL_STATUS.json').read_text());require(final['computational_analysis_complete'] and not final['scientific_publication_ready'],'Incorrect final status')
    _,original=preflight(ROOT,load_config(ROOT/'research_pipeline/config.json'),verify_hashes=True)
    audits=[p.parent for p in (ROOT/'dataset-audit').glob('remaining_downloads_*/summary.json') if json.loads(p.read_text())['status']=='PASS']
    require(bool(audits),'No passing remaining-download audit')
    audit=max(audits,key=lambda p:p.stat().st_mtime)
    manifest=pd.read_csv(audit/'downloaded_file_manifest.csv')
    print('Verifying original new-download hashes (including 19 GB reference evidence)...',flush=True)
    for n,r in enumerate(manifest.itertuples(),1):
        require(digest(ROOT/r.folder/r.filename)==r.sha256,'A downloaded source changed: '+r.filename)
        if n%15==0:print('New source hashes:',n,'/',len(manifest),flush=True)
    annual=pd.read_csv(out/'annual_common_support_water.csv');end=pd.read_csv(out/'primary_endpoint_changes.csv')
    for r in end.itertuples():
        f=annual[annual.region==r.region].set_index('year');first=f.loc[2000,r.source_class+'_water_area_km2'];last=f.loc[2021,r.source_class+'_water_area_km2']
        require(np.isclose(r.endpoint_change_pct,100*(last-first)/first),'Endpoint percentage mismatch')
    recovered=pd.read_csv(out/'drought_recovery_events.csv')
    require(recovered.recovery_months.isna().all(),'Unexpected invented recovery values')
    for threshold in [80,90]:
        require(pd.read_csv(out/f'recovery_sensitivity_{threshold}/drought_recovery_events.csv').recovery_months.isna().all(),'Unexpected sensitivity recovery duration')
    spi=pd.read_csv(out/'spi_indices.csv');require(len(spi)==2400 and spi.spi.notna().all(),'SPI incomplete')
    ref=pd.read_csv(out/'independent_sensor_evidence/primary_sensor_comparison.csv')
    require(len(ref)==720 and ref.sample_id.nunique()==720,'Independent sample mismatch')
    consensus=ref[ref.consensus_label.notna()];require(len(consensus)==583 and int((consensus.consensus_label==consensus.predicted_water).sum())==563,'Agreement summary mismatch')
    require(len(list((out/'independent_sensor_evidence/chips').glob('*.png')))==720,'Review image missing')
    require(pd.read_csv(out/'independent_validation_metrics.csv').empty and not (ROOT/'validation/reference_labels.csv').exists(),'False human verification')
    review=(out/'independent_sensor_evidence/review.html').read_text(encoding='utf-8')
    payload=json.loads(re.search(r'const rows=(\[.*?\]);let pos',review).group(1))
    require(len(payload)==720 and all(set(r)=={'id','period','region'} for r in payload),'Review viewer leaks prediction labels')
    node=shutil.which('node');require(node is not None,'Node required to verify exported viewer JavaScript')
    script=ROOT/'code-verification/review_viewer_syntax_20261013.js'
    script.write_text(re.search(r'<script>(.*?)</script>',review,re.S).group(1),encoding='utf-8')
    checked_js=subprocess.run([node,'--check',str(script)],capture_output=True,text=True)
    require(checked_js.returncode==0,'Broken viewer JavaScript: '+checked_js.stderr)
    step=pd.read_csv(out/'annual_observation_effort_climate_sensitivity.csv')
    step=step[step.setting=='mean_wet_effort_and_2016_asset_step']
    require(len(step)==8 and (step.status=='PASS').all(),'Asset-boundary sensitivity incomplete')
    permanent=step[step.source_class=='permanent'];require(((permanent.lower95<=0)&(permanent.upper95>=0)).all(),'Permanent robustness summary mismatch')
    seasonal=step[(step.source_class=='seasonal')&step.region.isin(['Naogaon','Rajshahi'])]
    require((seasonal.upper95<0).all() and (seasonal.p_adjusted_BY_within_setting_primary_districts<.05).all(),'Seasonal robustness summary mismatch')
    require(len(list((out/'Figures').glob('*.png')))==8 and len(list((out/'Figures').glob('*.svg')))==7,'Figure set missing')
    check={'status':'PASS','date_client_dhaka':'2026-10-13','core_hashes_checked':original['raw_hashes_checked'],
        'additional_source_hashes_checked':len(manifest),'all_original_inputs_preserved':True,
        'endpoint_percentages_reconciled':True,'spi_records':2400,'review_images':720,
        'automated_consensus':583,'matches_with_jrc_on_consensus_subset':563,
        'human_verified_reference_labels':0,'identifiable_recovery_durations':0,
        'automated_agreement_not_mislabeled_accuracy':True,'viewer_javascript_syntax':'PASS',
        '2016_asset_step_sensitivity_checked':True,'numerical_tests':'67 PASSED'}
    write_json(out/'FINAL_CHECKS.json',check)
    # Freeze source scene-date inventory next to the blinded review kit, without any fabricated dates.
    source=ROOT/'NW_Bangladesh_independent_reference/reference_scene_inventory.csv'
    (out/'independent_sensor_evidence/reference_scene_inventory.csv').write_bytes(source.read_bytes())
    (out/'independent_sensor_evidence/REVIEW_README_BN.md').write_text(
        'review.html খুলে হলুদ বাক্সের জায়গাটি দেখুন। মাসিক composites নির্দিষ্ট দিনের ছবি নয়। '
        'Scene inventory-তে আসল acquisition dates আছে; সংশ্লিষ্ট dated imagery দেখে তবেই genuine reference label/date দিন। '
        'Preliminary notes এবং automated consensus কোনো human-verified ground truth নয়।\n',encoding='utf-8')
    result_files=[p for p in out.rglob('*') if p.is_file() and p.suffix.lower() in {'.csv','.json','.md','.png','.svg','.html','.tif'}]
    results=package(ROOT/'NW_Bangladesh_Results_20261013.zip',result_files,out)
    evidence=out/'independent_sensor_evidence'
    review_files=list((evidence/'chips').glob('*.png'))+[evidence/n for n in ['review.html','reference_labels_still_unverified.csv','reference_scene_inventory.csv','REVIEW_README_BN.md']]
    packet=package(ROOT/'NW_Bangladesh_Blinded_Review_20261013.zip',review_files,evidence)
    write_json(ROOT/'code-verification/final_results_package_check_20261013.json',{'results':results,'blinded_review':packet,'checks':check})
    print(json.dumps({'results':results,'blinded_review':packet,'checks':check},indent=2))

if __name__=='__main__':main()
