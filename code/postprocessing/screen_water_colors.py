"""Exploratory band-based triage, not independent reference-label generation.

Uses only frozen PUBLIC sample geometry, raw Sentinel-2 crops and product XML
calibration. Never reads JRC target classes or old human answers. Numeric band
values are used instead of display RGB/PNG colors. Thresholds are heuristic,
not learned, calibrated probabilities, or validated accuracy guarantees.
"""
from pathlib import Path
from datetime import date
from collections import Counter
import csv,hashlib,json,math,sys
import numpy as np
import rasterio
from shapely.geometry import box
from prepare_blind_accuracy import ROOT,OUT as SOURCE,BANDS,digest,footprint,write_json,now

OUT=ROOT/'assisted_water_screening_20261015'
RULES={
    'version':'spectral-triage-v1',
    'units':'Dimensionless product-calibrated BOA reflectance and normalized differences',
    'quality_scl_accepted':[4,5,6], 'minimum_clear_target_fraction':.95,
    'minimum_strong_class_fraction':.95,'minimum_good_dates':2,'minimum_span_days':14,
    'water':{'mndwi_min':.20,'ndwi_min':.10,'ndvi_max':.20,'nir_max':.15,'swir_max':.08,'green_min':.01,'visible_mean_min':.012},
    'nonwater':{'mndwi_max':-.20,'ndwi_max':-.10,'nir_or_swir_min':.08,
        'vegetation_ndvi_min':.45,'vegetation_nir_min':.18,'vegetation_mndwi_max':0,'vegetation_swir_min':.08},
    'edge_guard':{'buffer_m':10,'opposite_sign_fraction_min':.10,'minimum_clear_ring_fraction':.5},
    'negative_or_extreme_reflectance_ambiguous_fraction':.05,
    'reflectance_screen_range':[0,1.2],
    'selection':'All 720 frozen public points, all 3022 prepared dates; no target/old-label inputs.',
    'interpretation':'Provisional automated screening only. Low-support points remain missing; human review is model-selected and assisted, never independent validation.'}


def normalized(a,b):
    result=np.full_like(a,np.nan,dtype='float64');den=a+b
    np.divide(a-b,den,out=result,where=np.isfinite(den)&(den>1e-6))
    return result


def spectral_masks(values):
    b,g,r,n,s=(values[k] for k in BANDS[:-1])
    mndwi=normalized(g,s);ndwi=normalized(g,n);ndvi=normalized(n,r)
    visible=(b+g+r)/3;valid=np.isfinite(np.stack([b,g,r,n,s])).all(axis=0)
    valid&=(np.stack([b,g,r,n,s])>=RULES['reflectance_screen_range'][0]).all(axis=0)
    valid&=(np.stack([b,g,r,n,s])<=RULES['reflectance_screen_range'][1]).all(axis=0)
    w=RULES['water'];d=RULES['nonwater']
    water=valid&(mndwi>=w['mndwi_min'])&(ndwi>=w['ndwi_min'])&(ndvi<=w['ndvi_max'])
    water&=(n<=w['nir_max'])&(s<=w['swir_max'])&(g>=w['green_min'])&(visible>=w['visible_mean_min'])
    dry=(mndwi<=d['mndwi_max'])&(ndwi<=d['ndwi_max'])&((n>=d['nir_or_swir_min'])|(s>=d['nir_or_swir_min']))
    vegetation=(ndvi>=d['vegetation_ndvi_min'])&(n>=d['vegetation_nir_min'])&(mndwi<=d['vegetation_mndwi_max'])&(ndwi<=d['ndwi_max'])&(s>=d['vegetation_swir_min'])
    nonwater=valid&(dry|vegetation)
    assert not (water&nonwater).any()
    return {'water':water,'nonwater':nonwater,'valid_radiometry':valid,
        'weak_water':valid&(mndwi>0)&(ndwi>0),'weak_nonwater':valid&(mndwi<0)&(ndwi<0),
        'mndwi':mndwi,'ndwi':ndwi,'ndvi':ndvi,'visible_mean':visible}


def area_weights(polygon,transform,shape0):
    weights=np.zeros(shape0,dtype='float64');left,bottom,right,top=polygon.bounds
    c0,r0=(~transform)*(left,top);c1,r1=(~transform)*(right,bottom)
    for rr in range(max(0,math.floor(r0)),min(shape0[0],math.ceil(r1))):
        for cc in range(max(0,math.floor(c0)),min(shape0[1],math.ceil(c1))):
            l,t=transform*(cc,rr);r,b=transform*(cc+1,rr+1)
            weights[rr,cc]=polygon.intersection(box(l,b,r,t)).area
    if not np.isclose(weights.sum(),polygon.area,atol=1e-5):raise ValueError('Reference crop does not cover required target/context footprint')
    return weights


def read_scene(point,public_scene,cache):
    sid=point['sample_id'];item_id=public_scene['item_id']
    rec=json.loads((SOURCE/'evidence'/sid/(item_id+'.json')).read_text(encoding='utf-8'))
    for pk,hk in [('image_path','image_sha256'),('tiff_path','tiff_sha256')]:
        if digest(SOURCE/rec[pk])!=rec[hk]:raise ValueError('Actual evidence checksum mismatch')
    if rec['sample_id']!=sid or rec['acquisition_datetime'][:10]!=public_scene['date']:raise ValueError('Evidence point/date mismatch')
    if rec['requested_asset_order']!=list(BANDS):raise ValueError('Unexpected spectral band order')
    cal_path=SOURCE/rec['calibration_path'];cal=json.loads(cal_path.read_text(encoding='utf-8'))
    if digest(cal_path.with_suffix('.xml'))!=cal['xml_sha256']:raise ValueError('Calibration source changed')
    with rasterio.open(SOURCE/rec['tiff_path']) as ds:
        if ds.count!=7 or ds.shape!=(40,40) or str(ds.crs)!=rec['crs'] or not np.allclose(ds.transform,rec['transform']):raise ValueError('Grid/band mismatch')
        raw=ds.read();transform=ds.transform
    values={}
    for i,band in enumerate(BANDS[:-1]):
        co=cal['band_coefficients'][band];a=raw[i].astype('float64')*co['scale']+co['offset']
        a[(raw[i]==0)|(raw[6]==0)]=np.nan;values[band]=a
    clear=np.isin(raw[5],RULES['quality_scl_accepted'])&(raw[6]>0)&np.all(raw[:5]>0,axis=0)
    masks=spectral_masks(values)
    key=(sid,tuple(rec['bounds']),rec['crs'])
    if key not in cache:
        target=footprint(point,rec['crs']);ring=target.buffer(RULES['edge_guard']['buffer_m']).difference(target)
        cache[key]=(area_weights(target,transform,raw.shape[1:]),area_weights(ring,transform,raw.shape[1:]))
    weights,ring=cache[key];area=weights.sum();ring_area=ring.sum()
    fraction=lambda mask:float(weights[mask].sum()/area)
    clear_fraction=fraction(clear)
    if abs(clear_fraction-public_scene['clear_fraction'])>1e-8:raise ValueError('Quality mismatch')
    wf=fraction(clear&masks['water']);nf=fraction(clear&masks['nonwater'])
    bad=fraction(clear&~masks['valid_radiometry'])
    radiometry_ok=bad<=RULES['negative_or_extreme_reflectance_ambiguous_fraction']
    label=1 if wf>=RULES['minimum_strong_class_fraction'] and radiometry_ok else 0 if nf>=RULES['minimum_strong_class_fraction'] and radiometry_ok else None
    ring_clear=float(ring[clear].sum()/ring_area)
    opposite=masks['weak_nonwater'] if label==1 else masks['weak_water'] if label==0 else np.zeros(clear.shape,dtype=bool)
    edge=label is not None and ring_clear>=RULES['edge_guard']['minimum_clear_ring_fraction'] and float(ring[clear&opposite].sum()/ring_area)>=RULES['edge_guard']['opposite_sign_fraction_min']
    medians={}
    for name in ('mndwi','ndwi','ndvi'):
        usable=clear&(weights>0)&np.isfinite(masks[name]);medians[name]=float(np.median(masks[name][usable])) if usable.any() else None
    return {'item_id':item_id,'date':public_scene['date'],'clear_fraction':min(1,max(0,clear_fraction)),
        'strong_water_target_fraction':wf,'strong_nonwater_target_fraction':nf,'uninterpretable_radiometry_fraction':bad,
        'scene_automated_label':label,'near_opposite_signal_edge':bool(edge),'median_indices_unweighted':medians,
        'tiff_sha256':rec['tiff_sha256'],'image_sha256':rec['image_sha256']}


def classify_point(scenes):
    good=[s for s in scenes if s['clear_fraction']>=RULES['minimum_clear_target_fraction']]
    days=[date.fromisoformat(s['date']) for s in good]
    if len(days)<RULES['minimum_good_dates'] or (max(days)-min(days)).days<RULES['minimum_span_days']:
        return {'category':'QUALITY_LIMITED','automated_water':None,'review_required':False,
            'reason_codes':['INSUFFICIENT_DATED_SUPPORT'],'good_dates':len(good)}
    labels={s['scene_automated_label'] for s in good};reasons=[]
    if 0 in labels and 1 in labels:reasons.append('DATE_DISAGREEMENT')
    if None in labels:reasons.append('MIXED_OR_WEAK_BANDS')
    if any(s['near_opposite_signal_edge'] for s in good):reasons.append('BOUNDARY_SENSITIVITY')
    if any(s['uninterpretable_radiometry_fraction']>RULES['negative_or_extreme_reflectance_ambiguous_fraction'] for s in good):reasons.append('RADIOMETRY_AMBIGUOUS')
    if reasons:return {'category':'REVIEW','automated_water':None,'review_required':True,'reason_codes':reasons,'good_dates':len(good)}
    label=next(iter(labels))
    if label not in (0,1):raise ValueError('Invalid automated screening label')
    return {'category':'AUTO_WATER' if label==1 else 'AUTO_NONWATER','automated_water':label,
        'review_required':False,'reason_codes':['CONSISTENT_STRONG_SPECTRAL_RULES'],'good_dates':len(good)}


def main():
    source_file=SOURCE/'public/review_dataset.json';source=json.loads(source_file.read_text(encoding='utf-8'))
    OUT.mkdir(exist_ok=True)
    if (OUT/'screening_dataset.json').exists():
        old=json.loads((OUT/'screening_dataset.json').read_text(encoding='utf-8'))
        if old['source_dataset_id']!=source['id'] or old['rules']!=RULES:raise ValueError('Existing screening dataset preserved; changed protocol needs a new version/folder')
    protected=[ROOT/'Water_Independent_Accuracy_Review.html',SOURCE/'review_manifest.json',SOURCE/'validation_protocol.json',ROOT/'water_reference_labels_user_confirmed_20261015.csv',ROOT/'water_review_backup_user_confirmed_20261015.json']
    protected_hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in protected}
    write_json(OUT/'screening_rules.json',RULES)
    rows=[];cache={};scene_count=0
    for i,point in enumerate(source['rows'],1):
        scenes=[read_scene(point,s,cache) for s in point['scenes']]
        result=classify_point(scenes);rows.append({**point,'screening':result,'spectral_evidence':scenes});scene_count+=len(scenes)
        if i%120==0:print('SCREENED',i,'/ 720',flush=True)
    identity={'schema':'nw-assisted-spectral-triage-v1','source_dataset_id':source['id'],
        'scope':'Exploratory automated triage and model-selected human review of the same four sampled JRC monthly frames. No independent accuracy certification.',
        'rules':RULES,'rows':rows}
    ds={**identity,'id':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
    assert len(rows)==720 and scene_count==3022
    forbidden=('predicted_water','population_pixels','optical_label','ai_recommendation','consensus_label')
    assert not any(s in json.dumps(ds) for s in forbidden)
    write_json(OUT/'screening_dataset.json',ds)
    counts=Counter(r['screening']['category'] for r in rows)
    report={'created_at':now(),'screening_dataset_id':ds['id'],'points':720,'actual_date_views':scene_count,'counts':dict(counts),
        'default_human_queue':counts['REVIEW'],'automatic_binary_suggestions':counts['AUTO_WATER']+counts['AUTO_NONWATER'],
        'insufficient_support_stays_missing':counts['QUALITY_LIMITED'],'human_labels_generated':0,
        'auto_labels_are_references':False,'calibrated_confidence_or_accuracy_reported':False,
        'independent_accuracy_complete':False,'publication_ready':False,
        'thresholds_tuned_on_old_or_current_human_answers':False,
        'target_predictions_or_old_human_label_values_used_for_screening':False,
        'old_label_files_hashed_only_for_preservation_not_parsed_for_classification':True,
        'prior_artifacts_sha256':protected_hashes,
        'software_sha256':digest(Path(__file__)),'input_public_dataset_sha256':digest(source_file),
        'source_evidence_manifest_sha256':digest(SOURCE/'public/evidence_manifest.json'),
        'limitations':['Heuristic thresholds can confidently misclassify shadows, turbid/shallow water, wet soil, crops and mixed pixels.',
            'Band agreement is dependent evidence, not calibrated confidence.',
            'Only reviewing model-uncertain cases cannot measure representative accuracy or errors among automatic cases.',
            'Human-assisted answers and automatic suggestions must never be imported as independent validation labels.',
            'Four sampled months and available acquisitions do not validate annual hydroperiod or every intervening day.']}
    if not all(digest(ROOT/p)==h for p,h in protected_hashes.items()):raise ValueError('Protected previous artifact changed')
    write_json(OUT/'screening_report.json',report)
    fields=['sample_id','number','region','period','category','automated_water','review_required','reason_codes','human_water','reference_quality','independent_reference_eligible']
    with (OUT/'automated_screening.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:
            s=r['screening'];writer.writerow({'sample_id':r['sample_id'],'number':r['number'],'region':r['region'],'period':r['period'],
                **{k:s[k] for k in ('category','automated_water','review_required')},'reason_codes':';'.join(s['reason_codes']),
                'human_water':'','reference_quality':'AUTO_SCREENING_ONLY' if s['automated_water'] is not None else 'UNRESOLVED','independent_reference_eligible':'false'})
    print(json.dumps({'status':'SCREENING_COMPLETED_NOT_ACCURACY','counts':dict(counts),'human_labels_generated':0}))


if __name__=='__main__':main()
