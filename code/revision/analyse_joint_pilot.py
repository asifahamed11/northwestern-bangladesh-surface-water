"""Audit frozen quarter exports and describe paired-product joint areas.

No reference labels or physical accuracy estimates are produced. Units of summed
monthly areas are km2-month; overlapping cohorts/union are never added together.
"""
from pathlib import Path
import argparse, hashlib, itertools, json
import numpy as np
import pandas as pd

KEY = ['year', 'month', 'region', 'water_group']
SNAPSHOT = '75b455d1c5b8722aaf1baae98bba3fa785129b888a8ca72aa2b2134b88ef56e5'
REGIONS = ['All_districts', 'Naogaon', 'Chapainawabganj', 'Rajshahi']
GROUPS = ['all_water', 'baseline_seasonal', 'baseline_permanent']
CELLS = ['a1_b1', 'a1_b0', 'a0_b1', 'a0_b0']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run(raw, original, out):
    out.mkdir(parents=True, exist_ok=False)
    frames, inputs = [], []
    for year, quarter in itertools.product([2018, 2024], range(1, 5)):
        path = raw / f'review_joint_cells_{year}_Q{quarter}.csv'
        x = pd.read_csv(path)
        assert len(x) == 36, (path.name, len(x))
        assert set(x.year) == {year}
        assert set(x.month) == set(range(quarter*3-2, quarter*3+1))
        frames.append(x)
        inputs.append({'path': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path), 'rows': len(x)})
    x = pd.concat(frames, ignore_index=True).sort_values(KEY).reset_index(drop=True)
    assert len(x) == 288 and not x.duplicated(KEY).any()
    assert set(x.region) == set(REGIONS), sorted(x.region.unique())
    assert set(x.water_group) == set(GROUPS), sorted(x.water_group.unique())
    expected = set(itertools.product([2018,2024], range(1,13),REGIONS,GROUPS))
    assert set(x[KEY].itertuples(index=False, name=None)) == expected
    assert (x.period == x.year.astype(str)+'-'+x.month.astype(str).str.zfill(2)).all()
    assert set(x.source_snapshot_sha256) == {SNAPSHOT}
    assert set(x.sar_track) == {'DESCENDING_48'}
    originals=[]
    for year in [2018,2024]:
        p=original/f'dw_sensitivity_{year}.csv'
        originals.append(pd.read_csv(p))
        inputs.append({'path':p.name,'sha256':sha(p),'role':'frozen comparator'})
    y=pd.concat(originals).sort_values(KEY).reset_index(drop=True)
    assert len(y)==288 and not y.duplicated(KEY).any()
    assert x[KEY].equals(y[KEY])
    area_cols=[c for c in y if c.endswith('_km2')]
    delta=np.abs(x[area_cols].to_numpy()-y[area_cols].to_numpy())
    assert np.isfinite(delta).all() and delta.max() <= 1e-6
    metadata=[c for c in y if c not in area_cols+['method']]
    for c in metadata:
        assert x[c].equals(y[c]), c
    records=[]
    max_partition=max_diagonal=0.
    for q, comparison in itertools.product([50,60,70,80],['sar','jrc']):
        prefix=f'dw_t{q}_{comparison}'
        a=x[[prefix+'_'+c+'_km2' for c in CELLS]].to_numpy()
        assert np.isfinite(a).all() and (a>=0).all()
        pair=x[prefix+'_pair_area_km2'].to_numpy()
        diag=x[prefix+'_same_area_km2'].to_numpy()
        max_partition=max(max_partition,float(np.max(np.abs(a.sum(1)-pair))))
        max_diagonal=max(max_diagonal,float(np.max(np.abs(a[:,0]+a[:,3]-diag))))
        assert np.allclose(a.sum(1),pair,rtol=0,atol=1e-6)
        assert np.allclose(a[:,0]+a[:,3],diag,rtol=0,atol=1e-6)
        assert (pair<=x.domain_area_km2+1e-6).all()
        for k, row in x.iterrows():
            vals=dict(zip(CELLS,a[k]))
            records.append({**{c:row[c] for c in KEY}, 'period':row.period,
                'comparison':comparison,'threshold':q/100,
                'a_product':'SAR' if comparison=='sar' else 'DW',
                'b_product':'DW' if comparison=='sar' else 'JRC',
                'domain_km2':row.domain_area_km2,**vals})
    z=pd.DataFrame(records)
    z['season']=np.where(z.month.between(6,9),'JJAS','other_months')
    def summarize(keys):
        ans=[]
        for key,g in z.groupby(keys,sort=True):
            key=key if isinstance(key,tuple) else (key,)
            a,b,c,d=g[CELLS].sum().to_numpy()
            pair=a+b+c+d
            divide=lambda n,d:float(n/d) if d>0 else np.nan
            ans.append({**dict(zip(keys,key)),'months_expected':len(g),
                'months_with_pair':int((g[CELLS].sum(axis=1)>0).sum()),
                'domain_km2_month':float(g.domain_km2.sum()),
                'pair_km2_month':float(pair),'a1_b1_km2_month':a,'a1_b0_km2_month':b,
                'a0_b1_km2_month':c,'a0_b0_km2_month':d,
                'pair_fraction':divide(pair,g.domain_km2.sum()),
                'pooled_agreement':divide(a+d,pair),
                'a_water_prevalence':divide(a+b,pair),'b_water_prevalence':divide(a+c,pair),
                'positive_agreement':divide(2*a,2*a+b+c),
                'negative_agreement':divide(2*d,2*d+b+c)})
        return pd.DataFrame(ans)
    base=['region','water_group','comparison','threshold']
    tables={'joint_pilot_monthly_cells':z,
            'joint_pilot_by_year':summarize(['year']+base),
            'joint_pilot_by_season':summarize(['year','season']+base),
            'joint_pilot_pooled':summarize(base)}
    for name,df in tables.items():df.to_csv(out/(name+'.csv'),index=False)
    audit={'status':'internally_consistent_only','rows':len(x),'quarters':8,
        'periods':24,'source_area_columns':len(area_cols),
        'max_original_area_difference_km2':float(delta.max()),
        'max_partition_difference_km2':max_partition,
        'max_diagonal_difference_km2':max_diagonal,
        'metadata_exact_match':metadata,'no_missing_or_duplicate_keys':True,
        'inputs':inputs,'source_snapshot_sha256':SNAPSHOT,
        'scope':'2018 and 2024 frozen pilot; all months, four thresholds, all strata retained',
        'interpretation':'Paired-product agreement; no independent reference or accuracy estimate. Summed areas have units km2-month. Cohorts overlap and union must not be added to districts.',
        'outputs':{name+'.csv':sha(out/(name+'.csv')) for name in tables}}
    (out/'joint_pilot_audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:audit[k] for k in ['status','rows','quarters','source_area_columns','max_original_area_difference_km2','max_partition_difference_km2','max_diagonal_difference_km2']}))
    view=tables['joint_pilot_pooled']
    print(view[view.region.eq('All_districts')&view.water_group.eq('all_water')].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw',type=Path,required=True);p.add_argument('--original',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.raw,a.original,a.output)
