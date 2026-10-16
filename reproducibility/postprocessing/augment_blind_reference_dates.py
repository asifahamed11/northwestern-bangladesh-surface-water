"""Add all other available dates to quality/spacing-limited fixed samples.

Applied before any human labels exist. No target classes, human outcomes or
water-index predictions are consulted. The primary sample frame is unchanged;
all poor/unknown cases remain in the eventual response/bounds accounting.
"""
from pathlib import Path
from datetime import date
import json,shutil
from collections import Counter
from shapely.geometry import shape,box
from prepare_blind_accuracy import OUT,PERIODS,write_json,now


def main():
    amendment=OUT/'reference_date_amendment.json'
    if amendment.exists():print('Existing before-label amendment preserved.');return
    if (OUT/'public/review_dataset.json').exists():raise ValueError('Do not change frozen evidence after a human review page has been issued')
    points=json.loads((OUT/'public/sample_manifest.json').read_text(encoding='utf-8'))
    path=OUT/'public/reference_schedule.json';schedule=json.loads(path.read_text(encoding='utf-8'))
    by={s['sample_id']:s for s in schedule};catalog={}
    for y,m in PERIODS:
        raw=json.loads((OUT/f'sources/search_{y}_{m:02}.json').read_text(encoding='utf-8'))['features']
        catalog[(y,m)]=[(f,shape(f['geometry'])) for f in raw]
    revised=[];added_items={};limited=0;added_pairs=0
    for p in points:
        record=by[p['sample_id']]
        files=[OUT/'evidence'/p['sample_id']/f'{i}.json' for i in record['selected_item_ids']]
        if not all(f.exists() for f in files):raise ValueError('Finish the initial real evidence batch before preflight amendment')
        existing=[json.loads(f.read_text(encoding='utf-8')) for f in files]
        clear_days=[date.fromisoformat(r['acquisition_datetime'][:10]) for r in existing if r['conservative_clear_pixel_fraction']>=.95]
        eligible=len(clear_days)>=2 and (max(clear_days)-min(clear_days)).days>=14
        new=dict(record,initial_selected_item_ids=list(record['selected_item_ids']))
        if not eligible:
            limited+=1;by_day={}
            candidates=[f for f,g in catalog[(p['year'],p['month'])] if g.covers(box(*p['bounds']))]
            for f in sorted(candidates,key=lambda f:(float(f['properties'].get('s2:processing_baseline','0')),f['id']),reverse=True):by_day.setdefault(f['properties']['datetime'][:10],f)
            selected=[by_day[d] for d in sorted(by_day)]
            old_ids=set(record['selected_item_ids'])
            if not old_ids<=set(f['id'] for f in selected):raise ValueError('Initial acquisition unexpectedly removed')
            new['selected_item_ids']=[f['id'] for f in selected]
            new['selection']='Initial three dates retained. All other catalogued dates added because two >=95% quality-supported dates spanning >=14 days were unavailable. Before human labels; no target/reference class consulted.'
            for f in selected:
                if f['id'] not in old_ids:
                    added_items[f['id']]=f;added_pairs+=1
        revised.append(new)
    shutil.copyfile(path,OUT/'public/reference_schedule_initial_three_dates.json')
    if (OUT/'download_progress.json').exists():shutil.copyfile(OUT/'download_progress.json',OUT/'initial_three_date_download_progress.json')
    for item_id,item in added_items.items():
        itempath=OUT/'sources/items'/f'{item_id}.json'
        if not itempath.exists():write_json(itempath,item)
    write_json(path,revised)
    write_json(amendment,{'recorded_at':now(),'stage':'PRE_HUMAN_LABEL_NONVACUITY_PREFLIGHT',
        'primary_points_unchanged':720,'initial_point_scene_pairs':2160,'initial_quality_eligible_points':720-limited,
        'quality_or_spacing_limited_points':limited,'additional_point_scene_pairs':added_pairs,
        'new_total_point_scene_pairs':sum(len(s['selected_item_ids']) for s in revised),
        'target_classes_consulted_for_date_augmentation':False,'human_labels_consulted':False,
        'points_discarded_or_replaced':0,'source_quality_threshold_or_temporal_spacing_relaxed':False,
        'reason':'Three fixed acquisition dates often fell on clouds/unclassified imagery or insufficient temporal span. Obtain further real evidence for the same points before asking humans to review; retain all initial images and all uncertain samples.',
        'temporal_limit':'Extra acquisitions improve observed-date evidence but do not observe every day or establish physical truth.'})
    print('Added all other dates to',limited,'quality-limited fixed points;',added_pairs,'additional real scene-point views planned.')


if __name__=='__main__':main()
