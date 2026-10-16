"""Build a fully local blinded UI only from completed real evidence files."""
from pathlib import Path
import hashlib,json,re,sys
from prepare_blind_accuracy import ROOT,OUT,BANDS,write_json,now
from research_pipeline.common import digest


def main():
    points=json.loads((OUT/'public/sample_manifest.json').read_text(encoding='utf-8'))
    schedule=json.loads((OUT/'public/reference_schedule.json').read_text(encoding='utf-8'))
    by={s['sample_id']:s for s in schedule}
    rows=[];missing=[];evidence_hashes={}
    prefix=str(OUT.relative_to(ROOT)).replace('\\','/')+'/'
    for p in points:
        scenes=[]
        for item_id in by[p['sample_id']]['selected_item_ids']:
            record_path=OUT/'evidence'/p['sample_id']/f'{item_id}.json'
            if not record_path.exists():missing.append(str(record_path.relative_to(OUT)));continue
            rec=json.loads(record_path.read_text(encoding='utf-8'))
            for path_key,hash_key in [('image_path','image_sha256'),('tiff_path','tiff_sha256')]:
                if digest(OUT/rec[path_key])!=rec[hash_key]:raise ValueError('Evidence checksum mismatch')
                evidence_hashes[rec[path_key]]=rec[hash_key]
            if rec['sample_id']!=p['sample_id'] or rec['acquisition_datetime'][:7]!=p['period']:raise ValueError('Point/date mismatch')
            scenes.append({'item_id':item_id,'date':rec['acquisition_datetime'][:10],
                'image_path':prefix+rec['image_path'],'image_sha256':rec['image_sha256'],
                'clear_fraction':rec['conservative_clear_pixel_fraction'],
                'processing_baseline':rec['processing_baseline'],'original_swir_resolution_m':20})
        rows.append({**p,'scenes':scenes})
    if missing:
        write_json(OUT/'UI_NOT_READY.json',{'missing_evidence_records':len(missing),'expected':sum(len(s['selected_item_ids']) for s in schedule),'examples':missing[:4],'human_review_page_generated':False})
        raise SystemExit(f'Reference retrieval incomplete: {len(missing)} scene-point records missing. No incomplete viewer released.')
    if any(len(r['scenes'])<3 for r in rows):raise ValueError('At least three actual dates required per point')
    identity={'schema':'nw-independent-dated-review-v1','rows':rows,'scope':'Four sampled months, observed JRC-valid pixels excluding earlier exposed pixels; human-interpreted dated Sentinel-2 references.'}
    dataset={**identity,'id':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
    encoded=json.dumps(dataset,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    forbidden=['predicted_water','stratum','population_pixels','optical_label','consensus_label','tentative_image_interpretation','ai_recommendation']
    if any(term in encoded for term in forbidden):raise ValueError('Private target information entered public UI')
    assets=[ROOT/'postprocessing'/f for f in ('blind_accuracy_review.html','blind_accuracy_core.js','blind_accuracy_app.js')]
    page=assets[0].read_text(encoding='utf-8')
    # The pre-human quality preflight added more real dates at limited sites.
    # Keep all dates visible; do not discard cloudy frames from the audit trail.
    for before,after in [
        ('তিনটি তারিখই দেখবে','প্রস্তুত সব তারিখই দেখবে'),
        ('তিন দিনের ছবি পাল্টে দেখো','উপলব্ধ সব দিনের ছবি পাল্টে দেখো'),
        ('আমি তিন দিনের ছবি দেখে','আমি সব প্রস্তুত দিনের ছবি দেখে'),
        ('একই নমুনার তিনটি তারিখে','একই নমুনার সব প্রস্তুত তারিখে'),
        ('তিনটি দিন দিয়ে','এই কয়েকটি দিন দিয়ে')]:
        page=page.replace(before,after)
    for token,value in [('__DATASET__',encoded),('__CORE__',assets[1].read_text(encoding='utf-8')),('__APP__',assets[2].read_text(encoding='utf-8'))]:
        if page.count(token)!=1:raise ValueError('Template marker mismatch')
        page=page.replace(token,value)
    target=ROOT/'Water_Independent_Accuracy_Review.html'
    target.write_text(page,encoding='utf-8')
    write_json(OUT/'public/review_dataset.json',dataset)
    write_json(OUT/'public/evidence_manifest.json',evidence_hashes)
    write_json(OUT/'review_manifest.json',{'created_at':now(),'dataset_id':dataset['id'],'points':len(rows),'actual_dated_images':len(evidence_hashes)//2,
        'point_scene_pairs':sum(len(r['scenes']) for r in rows),'source_file_checksums_pass':True,
        'ui_sha256':digest(target),'public_dataset_sha256':digest(OUT/'public/review_dataset.json'),
        'frozen_evaluation_inputs_sha256':{s:digest(OUT/s) for s in ('private/validation_sample_plan.json','private/stratum_counts.json','public/review_dataset.json')},
        'software_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in assets+[Path(__file__)]},
        'public_target_prediction_leak':False,'initial_human_labels':0,'independent_accuracy_complete':False,
        'quality_support_not_accuracy':True,'blinding':'Operational UI blinding, not secure filesystem isolation or proof of reviewer conduct'})
    print('READY:',len(rows),'fresh points,',sum(len(r['scenes']) for r in rows),'actual-date views; no previous answers or target classes in review page.')


if __name__=='__main__':main()
