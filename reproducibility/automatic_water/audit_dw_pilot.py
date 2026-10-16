"""Read-only validation of the actual one-month threshold-support pilot."""
from pathlib import Path
import argparse, hashlib, json, uuid
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGIONS = ['Naogaon', 'Chapainawabganj', 'Rajshahi', 'All_districts']
GROUPS = ['all_water', 'baseline_seasonal', 'baseline_permanent']
THRESHOLDS = [50, 60, 70, 80]
AREA_NAMES = ['domain_area_km2', 'dw_observed_area_km2'] + [
    f'dw_t{t}_{suffix}_area_km2' for t in THRESHOLDS for suffix in ['known', 'water', 'cell_known']]
META = ['pilot_version', 'year', 'month', 'period', 'region', 'water_group', 'dw_images', 'dw_days',
        'minimum_unique_days', 'thresholds', 'annual_source_years', 'annual_source_periods_ok',
        'analysis_crs', 'analysis_transform', 'interpretation']
TRANSFORM = [0.00026949458523585647, 0, 0, 0, -0.00026949458523585647, 0]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(frame, baseline, source_inventory):
    f = frame
    require(list(f.columns) == META + AREA_NAMES, 'Unexpected pilot columns')
    require(len(f) == 12 and set(zip(f.region, f.water_group)) == {(r,g) for r in REGIONS for g in GROUPS},
            'Expected exactly 12 unique region/cohort rows')
    require(not f.isna().any().any(), 'Missing pilot value')
    constants = {'pilot_version': 'dw_threshold_support_pilot_v1', 'year': 2024, 'month': 11, 'period': '2024-11',
        'minimum_unique_days': 2, 'thresholds': '0.5,0.6,0.7,0.8', 'annual_source_years': 25,
        'annual_source_periods_ok': 1, 'analysis_crs': 'EPSG:4326', 'interpretation': 'THRESHOLD_SUPPORT_NOT_GROUND_TRUTH'}
    for column, value in constants.items():
        require(f[column].eq(value).all(), 'Wrong pilot parameter: '+column)
    for value in f.analysis_transform:
        require(np.allclose(json.loads(value), TRANSFORM, rtol=0, atol=1e-15), 'Changed analysis grid')
    require(np.isfinite(f[AREA_NAMES].to_numpy(float)).all(), 'Nonfinite area')
    require((f[AREA_NAMES] >= -1e-8).all().all(), 'Negative area')
    for name in AREA_NAMES[1:]:
        require((f[name] <= f.domain_area_km2+1e-6).all(), 'Area outside cohort: '+name)
    for t in THRESHOLDS:
        known, wet, cell = [f[f'dw_t{t}_{k}_area_km2'] for k in ['known','water','cell_known']]
        require((wet <= known+1e-6).all() and (known <= f.dw_observed_area_km2+1e-6).all(), 'Classification exceeds support')
        require((.95*cell <= known+1e-6).all(), 'Agreement-cell coverage exceeds valid 10-m support')
    for a,b in zip(THRESHOLDS, THRESHOLDS[1:]):
        for kind in ['known','water']:
            require((f[f'dw_t{b}_{kind}_area_km2'] <= f[f'dw_t{a}_{kind}_area_km2']+1e-6).all(), 'Threshold areas not nested')
    union=f[f.region=='All_districts'].set_index('water_group')[AREA_NAMES].sort_index()
    parts=f[f.region!='All_districts'].groupby('water_group')[AREA_NAMES].sum().sort_index()
    require(np.allclose(union,parts,rtol=1e-8,atol=1e-6), 'District sums do not reconcile')
    ref=baseline[baseline.month==11].set_index(['region','water_group']).sort_index()
    current=f.set_index(['region','water_group']).sort_index()
    for name in ['domain_area_km2','dw_observed_area_km2']:
        require(np.allclose(current[name],ref[name],rtol=1e-8,atol=1e-6), 'Different baseline domain/observations: '+name)
    for name in ['dw_images','dw_days']:
        require(current[name].eq(ref[name]).all(), 'Different source count: '+name)
    for new, old in [('dw_t80_known_area_km2','dw_known_area_km2'),('dw_t80_water_area_km2','dw_water_area_km2')]:
        require(np.allclose(current[new],ref[old],rtol=1e-8,atol=1e-6), 'Old 0.8 calculation did not reproduce')
    row=source_inventory[(source_inventory.dataset=='DW')&(source_inventory.year==2024)&(source_inventory.month==11)]
    require(len(row)==1, 'Missing/duplicate source-inventory month')
    require(f.dw_images.eq(row.actual_images.iloc[0]).all() and f.dw_days.eq(row.unique_days.iloc[0]).all(), 'Source-inventory mismatch')
    return f

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'dw_threshold_pilot_2024_11.csv');args=parser.parse_args()
    path=args.input.resolve();original=path.read_bytes()
    base=pd.read_csv(ROOT/'NW_Bangladesh_automatic_water_2015_2024/auto_monthly_2024.csv')
    inventory=pd.read_csv(ROOT/'NW_Bangladesh_automatic_water_2015_2024/auto_source_inventory.csv')
    f=validate(pd.read_csv(path),base,inventory)
    # Deliberately invalid in-memory controls never become study datasets.
    for column,value in [('annual_source_periods_ok',0),('dw_t50_water_area_km2',1e9)]:
        changed=f.copy();changed.loc[0,column]=value
        try:validate(changed,base,inventory)
        except ValueError:pass
        else:raise AssertionError('Invalid control accepted: '+column)
    rows=[]
    for r in f[f.region=='All_districts'].itertuples():
        for t in THRESHOLDS:
            known=getattr(r,f'dw_t{t}_known_area_km2');wet=getattr(r,f'dw_t{t}_water_area_km2')
            rows.append({'water_group':r.water_group,'threshold':t/100,'domain_area_km2':r.domain_area_km2,
                'observed_fraction':r.dw_observed_area_km2/r.domain_area_km2,'classified_fraction':known/r.domain_area_km2,
                'classified_water_area_km2':wet,'agreement_cell_fraction':getattr(r,f'dw_t{t}_cell_known_area_km2')/r.domain_area_km2})
    require(path.read_bytes()==original,'Input changed during audit')
    report={'status':'PASS','rows':12,'columns':29,'input':str(path),'sha256':hashlib.sha256(original).hexdigest(),
        'baseline_domain_and_observation_match':True,'source_counts_match':True,'threshold_area_nesting_pass':True,
        'district_union_reconciliation_pass':True,'legacy_08_result_reproduced':True,'negative_controls_rejected':True,
        'union_threshold_support':rows,'threshold_selected':None,'verified_accuracy':False,'publication_ready':False,
        'note':'One month supports the threshold-failure diagnosis, but cannot calibrate accuracy or establish ten-year support.'}
    out=ROOT/'dataset-audit'/('dw_threshold_pilot_'+datetime.now().strftime('%Y%m%d')+'_'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    text=['# November 2024 threshold pilot যাচাই','','১২টি row, ২৯টি column; audit PASS।',
        'Study domain, observation area, scene/day counts আগের study CSV-এর সঙ্গে মিলে গেছে।',
        'পুরোনো ০.৮ result পুনরায় একই পাওয়া গেছে। সব জেলা/union ও threshold-area হিসাব মিলে গেছে।','',
        '| Cohort | সীমা | Classified support | Agreement-cell support |','|---|---:|---:|---:|']
    for r in rows:text.append(f"| {r['water_group']} | {r['threshold']:.1f} | {100*r['classified_fraction']:.2f}% | {100*r['agreement_cell_fraction']:.2f}% |")
    text+=['','Classified support হলো পানি/স্থল আলাদা করা যায় এমন footprint; এটি water area বা accuracy নয়।',
        'সীমা কমালে বেশি support থাকে, কিন্তু তা বেশি accuracy প্রমাণ করে না। কোনো best threshold নির্বাচন হয়নি।',
        'পরের কাজ: একই fixed study cohort ও source scenes ধরে ২০১৫–২০২৪-এর সব threshold এবং sensor agreement তুলনা।',
        'পুরোনো ১৪টি CSV রাখা হবে। নতুন sensitivity exports আলাদা folder-এ থাকবে।',
        'Source CSV ও original model-এর threshold পরিবর্তন করা হয়নি।']
    (out/'AUDIT_BN.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps({'report_dir':str(out),**report},indent=2))

if __name__=='__main__':main()
