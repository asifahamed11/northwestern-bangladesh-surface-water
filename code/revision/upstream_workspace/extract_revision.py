"""Genuine raster re-extraction for the frozen 19 October revision protocol.

Original files remain read-only. Missing classes remain zero in the cache and
are excluded explicitly from observed denominators, never interpreted as dry.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0,str(ROOT))
from research_pipeline.spatial import Grid
from research_pipeline.common import REGIONS

CACHE = OUT/'cache'; CACHE.mkdir(exist_ok=True)
TABLES = OUT/'tables'; TABLES.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(name, obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')

def areas(mask, labels, weights):
    counts = np.bincount(labels[mask],weights=weights[mask],minlength=4)
    return np.r_[counts[1:].sum(),counts[1:]]

def main():
    assert not (OUT/'EXTRACTION_COMPLETE.json').exists(), 'Retain completed run.'
    grid = Grid(ROOT)
    print('Grid:',grid.signature,flush=True)
    manifest = pd.read_csv(ROOT/'NW_Bangladesh_preprocessed/input_manifest.csv')
    originals=[]
    for kind in ['annual','monthly']:
        for year in range(2000,2025):
            p=grid.raw/f'jrc_{kind}_{year}.tif'
            expected=manifest.loc[manifest.filename.eq(p.name),'sha256_after'].iloc[0]
            actual=sha(p)
            assert actual==expected, 'Source hash changed: '+p.name
            with rasterio.open(p) as ds:
                grid.check(ds)
                assert ds.count==(1 if kind=='annual' else 12)
                if kind=='monthly': assert ds.descriptions==tuple(f'm{m:02d}' for m in range(1,13))
            originals.append({'file':str(p.relative_to(ROOT)),'sha256':actual,'bytes':p.stat().st_size})
    save('source_raster_audit.json',{'sources':originals,'same_native_grid':True,'missing_not_dry':True})
    flat=np.flatnonzero(grid.labels.ravel()>0)
    labels=grid.labels.ravel()[flat]
    weights=grid.row_areas[flat//grid.width]
    annual=np.lib.format.open_memmap(CACHE/'annual_classes.npy',mode='w+',dtype='uint8',shape=(25,len(flat)))
    for j,year in enumerate(range(2000,2025)):
        with rasterio.open(grid.raw/f'jrc_annual_{year}.tif') as ds:
            raw=ds.read(1).ravel()[flat]
            assert np.isin(raw,[-9999,0,1,2,3]).all()
            annual[j]=np.where((raw>=1)&(raw<=3),raw,0).astype('uint8')
        print('Annual source extraction',year,flush=True)
    annual.flush()
    v22=(annual[:22]>=1).sum(axis=0)
    ew25=np.any(annual>=2,axis=0)
    ew22=np.any(annual[:22]>=2,axis=0)
    baseline=np.all(annual[:5]>=1,axis=0)&np.any(annual[:5]>=2,axis=0)
    original=ew25&np.all(annual>=1,axis=0)
    expected=grid.fixed.ravel()[flat]&np.all(annual>=1,axis=0)
    assert np.array_equal(original,expected),'Original ever-water cache differs from raw reconstruction.'
    masks={
      'original_everwater_2000_2024_complete_2000_2024':original,
      'everwater_2000_2024_complete_2000_2021':ew25&(v22==22),
      'everwater_2000_2021_complete_2000_2021':ew22&(v22==22),
      'baseline_anywater_2000_2004_complete_2000_2021':baseline&(v22==22),
      'baseline_anywater_2000_2004_available_each_year':baseline,
      'everwater_2000_2021_at_least_20_valid_years':ew22&(v22>=20),
      'district_complete_2000_2021':v22==22}
    protocol=json.loads((OUT/'FROZEN_REVISION_PROTOCOL.json').read_text(encoding='utf-8'))
    assert list(masks)==protocol['cohorts']
    np.save(CACHE/'native_flat_indices.npy',flat)
    np.save(CACHE/'region_labels.npy',labels)
    np.save(CACHE/'pixel_areas_km2.npy',weights)
    np.savez_compressed(CACHE/'cohort_masks.npz',**masks)
    domain={k:areas(v,labels,weights) for k,v in masks.items()}
    annual_rows=[]
    for cohort,mask in masks.items():
        for j,year in enumerate(range(2000,2025)):
            valid=mask&(annual[j]>=1)
            vv=areas(valid,labels,weights)
            cls={c:areas(mask&(annual[j]==c),labels,weights) for c in [1,2,3]}
            for r,name in enumerate(REGIONS):
                d=domain[cohort][r]; observed=vv[r]; missing=max(0.,d-observed)
                row={'cohort':cohort,'region':name,'year':year,'reference_area_km2':d,'observed_annual_area_km2':observed,
                     'missing_annual_area_km2':missing,'coverage_fraction':observed/d if d else np.nan,
                     'eligible':bool(d>0 and observed/d>=.95-1e-10),
                     'nonwater_area_km2':cls[1][r],'seasonal_water_area_km2':cls[2][r],'permanent_water_area_km2':cls[3][r]}
                assert abs(sum(cls[c][r] for c in cls)-observed)<1e-6
                for name2,c in [('seasonal',2),('permanent',3)]:
                    row[name2+'_fraction_of_observed']=cls[c][r]/observed if observed else np.nan
                    row[name2+'_reference_lower_fraction']=cls[c][r]/d if d else np.nan
                    row[name2+'_reference_upper_fraction']=(cls[c][r]+missing)/d if d else np.nan
                annual_rows.append(row)
    frame=pd.DataFrame(annual_rows)
    reference=pd.read_csv(ROOT/'github_repository/northwestern-bangladesh-surface-water/data/tables/annual_common_support_water.csv')
    comp=frame[frame.cohort.eq(protocol['cohorts'][0])].merge(reference,on=['region','year'],suffixes=('_new','_old'),validate='one_to_one')
    assert len(comp)==100
    errors={name:float(np.max(np.abs(comp[name+'_new']-comp[name+'_old']))) for name in ['nonwater_area_km2','seasonal_water_area_km2','permanent_water_area_km2']}
    assert max(errors.values())<1e-6,errors
    save('original_extraction_comparison.json',{'status':'PASS','rows':100,'maximum_absolute_area_error_km2':errors,'scope':'Same actual raw rasters, pixel-center regions and EPSG:6933 pixel areas.'})
    frame.to_csv(TABLES/'annual_cohort_sensitivity.csv',index=False)
    print('Original annual results reproduced:',errors,flush=True)

    base_positions=np.flatnonzero(baseline)
    base_labels=labels[base_positions]; base_weights=weights[base_positions]
    base_months=np.lib.format.open_memmap(CACHE/'baseline_monthly_classes.npy',mode='w+',dtype='uint8',shape=(264,len(base_positions)))
    common=np.ones((12,len(base_positions)),dtype=bool)
    quality=[]; monthly=[]
    for j,year in enumerate(range(2000,2025)):
        observed_count=np.zeros(len(flat),dtype='uint8')
        wet_count=np.zeros(len(flat),dtype='uint8')
        ym_valid=np.zeros((12,4)); ym_water=np.zeros((12,4))
        with rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds:
            for top in range(0,grid.height,256):
                stop=min(top+256,grid.height)
                lo,hi=np.searchsorted(flat,[top*grid.width,stop*grid.width])
                if lo==hi: continue
                local=flat[lo:hi]-top*grid.width
                raw=ds.read(window=Window(0,top,grid.width,stop-top)).reshape(12,-1)[:,local]
                assert np.isin(raw,[-9999,0,1,2]).all()
                valid=(raw>=1)&(raw<=2)
                observed_count[lo:hi]=valid.sum(axis=0)
                wet_count[lo:hi]=valid[5:9].sum(axis=0)
                bl,bh=np.searchsorted(base_positions,[lo,hi])
                if bl==bh: continue
                chosen=base_positions[bl:bh]-lo
                v=valid[:,chosen]
                values=np.where(v,raw[:,chosen],0).astype('uint8')
                if j<22:
                    base_months[j*12:(j+1)*12,bl:bh]=values
                    common[:,bl:bh]&=v
                for m in range(12):
                    ym_valid[m]+=areas(v[m],base_labels[bl:bh],base_weights[bl:bh])
                    ym_water[m]+=areas(values[m]==2,base_labels[bl:bh],base_weights[bl:bh])
        for cohort,mask in masks.items():
            total=domain[cohort]
            counts=np.bincount(labels[mask],weights=weights[mask]*observed_count[mask],minlength=4)
            wet=np.bincount(labels[mask],weights=weights[mask]*wet_count[mask],minlength=4)
            counts=np.r_[counts[1:].sum(),counts[1:]]; wet=np.r_[wet[1:].sum(),wet[1:]]
            full=areas(mask&(observed_count==12),labels,weights)
            for r,name in enumerate(REGIONS):
                d=total[r]
                quality.append({'cohort':cohort,'region':name,'year':year,'cohort_area_km2':d,
                    'mean_observed_calendar_months':counts[r]/d if d else np.nan,
                    'mean_observed_jun_sep_months':wet[r]/d if d else np.nan,
                    'all_12_months_observed_area_fraction':full[r]/d if d else np.nan})
        for m in range(12):
            for r,name in enumerate(REGIONS):
                d=domain['baseline_anywater_2000_2004_available_each_year'][r]
                v=ym_valid[m,r]; w=ym_water[m,r]
                monthly.append({'region':name,'year':year,'month':m+1,'reference_area_km2':d,'observed_area_km2':v,'water_area_km2':w,
                                'water_fraction_of_observed':w/v if v else np.nan,'reference_water_lower_fraction':w/d if d else np.nan,
                                'reference_water_upper_fraction':(w+d-v)/d if d else np.nan})
        print('Monthly observation extraction',year,flush=True)
    base_months.flush()
    np.save(CACHE/'baseline_calendar_common_masks.npy',common)
    np.save(CACHE/'baseline_positions.npy',base_positions)
    qual=pd.DataFrame(quality)
    oq=pd.read_csv(ROOT/'github_repository/northwestern-bangladesh-surface-water/data/tables/annual_observation_quality.csv')
    cq=qual[qual.cohort.eq(protocol['cohorts'][0])].merge(oq,on=['region','year'],suffixes=('_new','_old'))
    qerrors={name:float(np.max(np.abs(cq[name+'_new']-cq[name+'_old']))) for name in ['mean_observed_calendar_months','mean_observed_jun_sep_months','all_12_months_observed_area_fraction']}
    assert max(qerrors.values())<1e-6,qerrors
    qual.to_csv(TABLES/'annual_cohort_observation_quality.csv',index=False)
    pd.DataFrame(monthly).to_csv(TABLES/'baseline_monthly_observed_support.csv',index=False)
    calendar_rows=[]; calendar_support=[]
    for m in range(12):
        area=areas(common[m],base_labels,base_weights)
        for r,name in enumerate(REGIONS):
            reference=domain['baseline_anywater_2000_2004_available_each_year'][r]
            retained=area[r]/reference if reference else 0
            calendar_support.append({'region':name,'month':m+1,'fixed_month_area_km2':area[r],'baseline_reference_area_km2':reference,
                                     'retained_fraction':retained,'eligible':bool(retained>=.2 and area[r]>0)})
        for j,year in enumerate(range(2000,2022)):
            values=base_months[j*12+m]
            assert (values[common[m]]>=1).all()
            water=areas(common[m]&(values==2),base_labels,base_weights)
            for r,name in enumerate(REGIONS):
                retained=area[r]/domain['baseline_anywater_2000_2004_available_each_year'][r]
                calendar_rows.append({'region':name,'year':year,'month':m+1,'fixed_month_area_km2':area[r],
                    'retained_fraction':retained,'eligible':bool(retained>=.2 and area[r]>0),'water_area_km2':water[r] if area[r] else np.nan,
                    'water_fraction':water[r]/area[r] if area[r] else np.nan})
    pd.DataFrame(calendar_support).to_csv(TABLES/'calendar_matched_support.csv',index=False)
    pd.DataFrame(calendar_rows).to_csv(TABLES/'calendar_matched_monthly_water.csv',index=False)
    save('EXTRACTION_COMPLETE.json',{'completed_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS',
        'original_annual_rows_reproduced':len(comp),'original_quality_maximum_errors':qerrors,
        'cohorts':list(masks),'years':25,'raw_rasters_hash_verified':50,'original_files_changed':False,
        'native_grid_signature':list(grid.signature),'monthly_matching_is_not_annual_hydroperiod_validation':True})
    print('PASS: seven genuine cohort extractions and matched-calendar observations.',flush=True)

if __name__=='__main__': main()
