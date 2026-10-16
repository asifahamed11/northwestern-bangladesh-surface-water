"""Audit actual reference acquisition and scope; never assigns human labels."""
from pathlib import Path
from datetime import date
from collections import Counter
import csv,json,math,sys
import numpy as np
import rasterio
from PIL import Image
from shapely.geometry import box,shape

from prepare_blind_accuracy import ROOT,OUT,BANDS,digest,footprint,write_json,now


def load(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    audit=load(OUT/'sample_audit.json');manifest=load(OUT/'review_manifest.json')
    samples=load(OUT/'public/sample_manifest.json');dataset=load(OUT/'public/review_dataset.json')
    plan=load(OUT/'private/validation_sample_plan.json');by={p['sample_id']:p for p in plan}
    schedule=load(OUT/'public/reference_schedule.json');scheduled={p['sample_id']:p for p in schedule}
    inputs={**audit['input_sha256'],**load(ROOT/'paper_scope_20261015/paper_scope.json')['input_sha256']}
    assert all(digest(ROOT/p)==h for p,h in inputs.items()),'Prior scientific input changed'
    assert len(samples)==len(plan)==len(scheduled)==720
    assert len(by)==720 and set(by)=={p['sample_id'] for p in samples}
    assert len(Counter(p['stratum'] for p in plan))==24
    assert set(Counter(p['stratum'] for p in plan).values())=={30}
    assert audit['exact_prior_pixel_period_overlap']==0
    assert all(digest(OUT/p)==h for p,h in manifest['frozen_evaluation_inputs_sha256'].items())
    assert digest(ROOT/'Water_Independent_Accuracy_Review.html')==manifest['ui_sha256']
    rows={p['sample_id']:p for p in dataset['rows']}
    assert set(rows)==set(by)
    forbidden={'predicted_water','stratum','population_pixels','optical_label','consensus_label','tentative_image_interpretation','ai_recommendation'}
    def walk(v):
        if isinstance(v,dict):
            assert not forbidden.intersection(v),'Private answer leaked into public data'
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(dataset)
    evidence={};calibrations={};counts=Counter();capacity=Counter();views=0
    scene_counts=Counter();weights_cache={}
    for point in samples:
        sid=point['sample_id'];ids=scheduled[sid]['selected_item_ids']
        assert len(ids)>=3 and len(ids)==len(set(ids))
        assert ids==[s['item_id'] for s in rows[sid]['scenes']]
        dates=[];usable=[]
        for item_id in ids:
            rec=load(OUT/'evidence'/sid/(item_id+'.json'))
            item=load(OUT/'sources/items'/(item_id+'.json'))
            assert rec['sample_id']==sid and rec['item_id']==item_id
            assert item['id']==item_id and rec['acquisition_datetime']==item['properties']['datetime']
            day=date.fromisoformat(rec['acquisition_datetime'][:10]);dates.append(day)
            assert day.strftime('%Y-%m')==point['period']
            assert shape(item['geometry']).covers(box(*point['bounds']))
            assert rec['requested_asset_order']==list(BANDS)
            assert rec['quality_is_ground_truth'] is False
            for path_key,hash_key in [('tiff_path','tiff_sha256'),('image_path','image_sha256')]:
                assert digest(OUT/rec[path_key])==rec[hash_key]
                evidence[rec[path_key]]=rec[hash_key]
            with Image.open(OUT/rec['image_path']) as image:
                assert image.size==(800,870);image.verify()
            with rasterio.open(OUT/rec['tiff_path']) as ds:
                assert ds.count==7 and ds.shape==(40,40) and ds.res==(10,10)
                assert str(ds.crs)==rec['crs'] and np.allclose(ds.transform,rec['transform'])
                assert np.allclose(ds.bounds,rec['bounds'])
                raw=ds.read();transform=ds.transform
            key=(sid,rec['crs'],tuple(rec['bounds']))
            if key not in weights_cache:
                polygon=footprint(point,rec['crs']);weights=np.zeros((40,40))
                l,b,r,t=polygon.bounds
                c0,r0=(~transform)*(l,t);c1,r1=(~transform)*(r,b)
                for rr in range(max(0,math.floor(r0)),min(40,math.ceil(r1))):
                    for cc in range(max(0,math.floor(c0)),min(40,math.ceil(c1))):
                        left,top=transform*(cc,rr);right,bottom=transform*(cc+1,rr+1)
                        weights[rr,cc]=polygon.intersection(box(left,bottom,right,top)).area
                assert np.isclose(weights.sum(),polygon.area)
                weights_cache[key]=(weights,polygon.area)
            weights,area=weights_cache[key]
            clear=np.isin(raw[5],[4,5,6])&(raw[6]>0)&np.all(raw[:5]>0,axis=0)
            fraction=min(1,max(0,float(weights[clear].sum()/area)))
            assert abs(fraction-rec['conservative_clear_pixel_fraction'])<1e-8
            public_scene=next(s for s in rows[sid]['scenes'] if s['item_id']==item_id)
            assert abs(fraction-public_scene['clear_fraction'])<1e-8 and public_scene['date']==str(day)
            if fraction>=.95:usable.append(day)
            if item_id not in calibrations:
                cal=load(OUT/rec['calibration_path'])
                xml=(OUT/rec['calibration_path']).with_suffix('.xml')
                assert digest(xml)==cal['xml_sha256']
                assert cal['quantification_value']>0 and cal['api_unscale'] is False
                assert set(cal['band_coefficients'])==set(BANDS[:-1])
                calibrations[item_id]=cal
            views+=1
        assert len(dates)==len(set(dates))
        good=len(usable)>=2 and (max(usable)-min(usable)).days>=14
        counts['quality_eligible' if good else 'quality_limited']+=1
        capacity[by[sid]['stratum']]+=int(good);scene_counts[len(ids)]+=1
        if views%200==0:print('AUDITED',views,flush=True)
    assert evidence==load(OUT/'public/evidence_manifest.json')
    assert views==3022 and len(evidence)==6044
    progress=load(OUT/'download_progress.json')
    assert progress['entire_validation_set_downloaded'] and not progress['errors']
    strata=load(OUT/'private/stratum_counts.json');table=[]
    for group in strata:
        maximum=capacity[group['stratum']]
        table.append({'stratum':group['stratum'],'sampled':group['sampled'],
            'quality_eligible_binary_ceiling':maximum,'human_binary_labels':0,
            'minimum_verified':group['minimum_verified'],
            'minimum_possible_with_current_evidence':maximum>=group['minimum_verified']})
    with (OUT/'private/quality_capacity_by_stratum.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    limited=sum(not t['minimum_possible_with_current_evidence'] for t in table)
    quality={'checked_at':now(),'points':720,'actual_date_views':views,
        'quality_eligible_points':counts['quality_eligible'],'quality_limited_points':counts['quality_limited'],
        'strata':24,'strata_below_existing_minimum_even_before_human_uncertainty':limited,
        'all_stratum_minima_achievable_with_current_evidence':limited==0,
        'points_by_prepared_scene_count':dict(scene_counts),
        'quality_support_is_human_verification':False,'actual_human_labels':0,
        'criteria_or_samples_changed_to_pass':False,
        'disposition':'Current evidence cannot meet every pre-existing minimum-count rule. Retain unknowns; any later claim/scope or reference-design amendment needs a transparent record, never silent threshold relaxation.'}
    write_json(OUT/'quality_preflight.json',quality)
    sources=[json.loads(s) for s in (OUT/'sources.jsonl').read_text(encoding='utf-8').splitlines()]
    claims=load(OUT/'claims.json');source_ids={s['source_id'] for s in sources}
    assert len(source_ids)==len(sources)==len({s['url'] for s in sources})
    assert all(s.get('review_level') and s.get('retrieved_at') and s.get('locator') and s['support_reviewed'] for s in sources)
    assert all(set(c['source_ids'])<=source_ids and c['locator'] and c['support_reviewed'] for c in claims)
    assert load(OUT/'data_api_band_order_check.json')['status']=='PASS'
    qa=load(OUT/'software_ui_checks.json') if (OUT/'software_ui_checks.json').exists() else {'status':'NOT_RUN'}
    checks={'checked_at':now(),'preparation_status':'PASS' if qa['status']=='PASS' else 'DATA_PASS_UI_QA_PENDING',
        'actual_dated_downloads_complete':True,'point_scene_pairs':views,'source_scene_count':len(calibrations),
        'evidence_hashes_and_grids_pass':True,'all_quality_fractions_recomputed_from_raw_files':True,
        'source_metadata_calibration_and_band_order_pass':True,'public_data_target_leak_found':False,
        'earlier_scientific_inputs_unchanged':True,'original_review_and_answer_inputs_preserved':True,
        'source_ledger_duplicates':0,'unsupported_method_claims_found_in_bounded_ledger':0,
        'human_reference_labels_created_by_software':0,'independent_accuracy_complete':False,
        'reference_minimum_counts_currently_possible':limited==0,'limited_strata':limited,
        'human_review_pending':True,'accuracy_computed':False,'recovery_duration_resolved':False,
        'scope_decision_recorded':True,'manuscript_started':False,'scientific_publication_ready':False,
        'software_ui_qa_status':qa['status'],
        'evidence_assurance':'Same-process acquisition/software/data-integrity QA, not an independent scientific verifier or ground-truth certification.',
        'code_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in sorted((ROOT/'postprocessing').glob('*blind_accuracy*')) if p.is_file()}}
    write_json(OUT/'FINAL_CHECKS.json',checks)
    write_json(OUT/'WORKFLOW_STATUS.json',{'checked_at':now(),'review_page_ready':qa['status']=='PASS',
        'review_page':'../Water_Independent_Accuracy_Review.html','new_samples':720,'dated_views':views,
        'actual_human_labels':0,'paper_title_and_claim_scope_recorded':True,'recovery_duration_known':False,
        'independent_accuracy_finished':False,'human_review_pending':True,
        'pre_existing_reference_count_gate_possible_with_current_evidence':limited==0,
        'scientific_publication_ready':False,'manuscript_started':False})
    print(json.dumps({'status':checks['preparation_status'],'views':views,'points':720,
        'quality_eligible':counts['quality_eligible'],'limited_strata':limited,'human_labels':0}))


if __name__=='__main__':main()
