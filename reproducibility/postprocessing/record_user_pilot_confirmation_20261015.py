"""Record explicit user confirmation of five dated, AI-guided pilot reviews.

Preserves all previous input snapshots. This is a human-confirmed guided
review, not a newly blind independent validation set or monthly ground truth.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy, csv, html, json, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import verify_water_labels as V

PILOT=ROOT/'dated_reference_pilot_20261015/v2_validated_ranges'
LOG=ROOT/'label_verification/user_pilot_confirmation_20261015'
DECISIONS={1:'0',181:'0',361:'1',541:'UNCERTAIN',720:'UNCERTAIN'}
QUESTION='তুমি কি ৫টি জায়গার তারিখসহ ছবি দেখে এই ফলগুলো নিশ্চিত করেছ: ১ ও ১৮১ = পানি নেই; ৩৬১ = পানি আছে; ৫৪১ ও ৭২০ = অনিশ্চিত?'
ANSWER='হ্যাঁ, এই ফলগুলোই নিশ্চিত করেছি'


def write_json_new(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)


def main():
    source_csv=ROOT/'water_reference_labels_corrected_20261015.csv'
    source_json=ROOT/'water_review_backup_corrected_20261015.json'
    target_csv=ROOT/'water_reference_labels_user_confirmed_20261015.csv'
    target_json=ROOT/'water_review_backup_user_confirmed_20261015.json'
    target_patch=ROOT/'water_review_5_confirmations_20261015.json'
    report=ROOT/'Water_Review_User_Confirmed_20261015.html'
    for path in (target_csv,target_json,target_patch,report,LOG):
        if path.exists():raise FileExistsError('Existing output preserved: '+str(path))
    evidence_files=[PILOT/name for name in ('pilot_plan.json','pilot_retrieval_schedule.json','ai_visual_review.json','dated_scene_evidence.json','accepted_cutout_manifest.json','FINAL_CHECKS.json')]
    source_paths=[source_csv,source_json,ROOT/'Water_Review.html',ROOT/'Water_Review.manifest.json',ROOT/'Water_Dated_5_Point_Review.html',*evidence_files]
    input_hashes={str(p):V.sha(p) for p in source_paths}
    data,_=V.read_viewer(ROOT/'Water_Review.html')
    headers,old_rows=V.csv_read(source_csv)
    old_backup=V.json_read(source_json)
    if V.audit_pair(headers,old_rows,old_backup,data)['status']!='PASS':raise ValueError('Existing label pair failed integrity audit')
    plan=V.json_read(PILOT/'pilot_plan.json')
    for name,digest in plan['input_sha256'].items():
        if V.sha(ROOT/name)!=digest:raise ValueError('Pilot source snapshot changed: '+name)
    ai=V.json_read(PILOT/'ai_visual_review.json')
    scenes=V.json_read(PILOT/'dated_scene_evidence.json')
    now=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    revised=copy.deepcopy(old_backup)
    by_id={r['sample_id']:r for r in revised['records']}
    canonical={r['id']:r for r in data['rows']}
    changed=[]; confirmations=[]
    for number,label in DECISIONS.items():
        point=data['rows'][number-1]
        sid=point['id']
        if ai[str(number)]['sample_id']!=sid:raise ValueError('Viewer number/ID does not match dated pilot')
        entry=by_id[sid]
        old=copy.deepcopy(entry)
        available=sorted((s for s in scenes if s['sample_id']==sid),key=lambda s:s['acquisition_datetime'])
        if len(available)!=3:raise ValueError('Expected three scheduled dated scenes')
        usable=[s for s in available if s['valid_MNDWI_area_fraction']>=.95]
        if label in ('0','1') and len(usable)<2:raise ValueError('Binary confirmation lacks planned dated support')
        # This date is an actual usable acquisition, never the chat timestamp.
        primary_date=usable[0]['acquisition_datetime'][:10] if label in ('0','1') else ''
        scene_ids=[s['item_id'] for s in available]
        evidence_paths=[str(PILOT.relative_to(ROOT)).replace('\\','/')+'/'+s['evidence_png'] for s in available]
        source='Sentinel-2 via Earth Search; '+ '; '.join(scene_ids)
        note=('ব্যবহারকারী তারিখসহ ৫টি জায়গার report দেখে চ্যাটে এই উত্তরটি নিশ্চিত করেছেন: '+
              ('পানি নেই' if label=='0' else 'পানি আছে' if label=='1' else 'অনিশ্চিত')+'। '+
              'আসল ছবির তারিখ: '+', '.join(s['acquisition_datetime'][:10] for s in available)+'। '+
              'AI-এর ব্যাখ্যা দেখার পরে guided review; blind independent reference বা পুরো মাসের স্থিতিশীলতার ঘোষণা নয়। '+
              'ব্যবহারকারীর নাম ও প্রকৃত review time দেওয়া হয়নি; updated_at কেবল নথিভুক্ত করার সময়।')
        entry.update(label=label,attested=False,updated_at=now,reference_date=primary_date,
                     reference_source=source,evidence_id='; '.join(evidence_paths),
                     reviewer='Current workspace user; confirmed in chat; name not supplied',
                     reason='পানি-মাটি মিশ্র' if label=='UNCERTAIN' else '')
        entry['notes']=(old['notes']+'\n' if old['notes'] else '')+note
        changed.append({'viewer_number':number,'sample_id':sid,'old':old,'new':copy.deepcopy(entry)})
        confirmations.append({'viewer_number':number,'sample_id':sid,'period':point['period'],
            'confirmed_interpretation':int(label) if label in ('0','1') else None,
            'decision':'UNCERTAIN' if label=='UNCERTAIN' else 'NONWATER' if label=='0' else 'WATER',
            'status':'USER_CONFIRMED_GUIDED_PILOT','user_confirmation':True,
            'reviewer_identity':'Current conversation user','reviewer_name':None,'actual_review_time':None,
            'recorded_at_utc':now,'acquisition_dates':[s['acquisition_datetime'][:10] for s in available],
            'scene_ids':scene_ids,'evidence_paths':evidence_paths,'primary_usable_date':primary_date or None,
            'monthly_stability_established':False,'blind_independent_review':False,
            'independent_accuracy_eligible':False})
    revised['exported_at']=now
    revised['revision_context']={'kind':'USER_CONFIRMED_DATED_GUIDED_PILOT','confirmed_ids':[c['sample_id'] for c in confirmations],
        'source_backup_sha256':input_hashes[str(source_json)],'previous_revision_context':old_backup.get('revision_context'),
        'human_confirmed_points':5,'independent_reference_attestation':False,'monthly_stability_established':False}
    patch={k:v for k,v in revised.items() if k!='records'}
    patch['records']=[copy.deepcopy(by_id[c['sample_id']]) for c in confirmations]
    csv_by={r['sample_id']:copy.deepcopy(r) for r in old_rows}
    expected_ids={c['sample_id'] for c in confirmations}
    for sid in expected_ids:
        e=by_id[sid];row=csv_by[sid];quality=V.status(e,canonical[sid])
        row.update(reference_water=e['label'] if quality=='VERIFIED' else '',reference_date=e['reference_date'],
            reference_source=V.neutral(e['reference_source']),reference_quality=quality,notes=V.neutral(e['notes']),
            preliminary_review=e['label'],evidence_id=V.neutral(e['evidence_id']),reviewer=V.neutral(e['reviewer']),
            evidence_attested='false',reviewed_at=e['updated_at'],uncertainty_reason=V.neutral(e['reason']))
    rows=[csv_by[r['sample_id']] for r in old_rows]
    old_by={r['sample_id']:r for r in old_rows};old_entries={r['sample_id']:r for r in old_backup['records']}
    assert {sid for sid,r in csv_by.items() if r!=old_by[sid]}==expected_ids
    assert {sid for sid,r in by_id.items() if r!=old_entries[sid]}==expected_ids
    audit=V.audit_pair(headers,rows,revised,data)
    if audit['status']!='PASS':raise ValueError(audit['issues'])
    assert audit['status_counts'].get('VERIFIED',0)==0
    LOG.mkdir(parents=True)
    event={'kind':'EXPLICIT_USER_CONFIRMATION','recorded_at_utc':now,
        'question_item_id':'["request_user_input_async","call_23e5d26d1bc34290b213764a39fd0736",0]',
        'question':QUESTION,'answer':ANSWER,'reviewer_name':None,'confirmation_scope':'Five displayed dated pilot interpretations only',
        'records':confirmations,'independent_accuracy_computed':False,'all_720_dated_reviews_completed':False,
        'limitations':['User saw AI interpretations before confirmation; not blind.',
          'Three chosen acquisitions do not establish the whole month.',
          'Five points do not cover the full sampling design.','541 and 720 remain uncertain.',
          'Actual reviewer name and exact review time were not supplied.']}
    write_json_new(LOG/'user_confirmation.json',event)
    with target_csv.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
    write_json_new(target_json,revised);write_json_new(target_patch,patch)
    columns=['viewer_number','sample_id','period','decision','confirmed_interpretation','status','user_confirmation','recorded_at_utc','primary_usable_date','independent_accuracy_eligible']
    with (LOG/'confirmed_pilot.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(confirmations)
    table=''.join('<tr><td>'+str(c['viewer_number'])+'</td><td>'+c['period']+'</td><td>'+('পানি নেই' if c['decision']=='NONWATER' else 'পানি আছে' if c['decision']=='WATER' else 'অনিশ্চিত')+'</td><td><a href="Water_Dated_5_Point_Review.html#point'+str(c['viewer_number'])+'">তারিখসহ ছবি</a></td></tr>' for c in confirmations)
    page='''<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>তোমার নিশ্চিত করা ৫টি ফল</title><style>body{font-family:system-ui,"Nirmala UI",sans-serif;background:#f1f6f7;color:#183a43;margin:0;line-height:1.9}main{max-width:850px;margin:25px auto;padding:24px;background:white;border-radius:18px}h1{font-size:26px}.note{background:#fff4db;padding:15px;border-radius:10px}table{width:100%;border-collapse:collapse;margin:20px 0}th,td{text-align:left;padding:10px;border-bottom:1px solid #dce6e8}a{color:#12638c}li{margin:10px 0}@media(max-width:500px){main{margin:10px;padding:15px}td,th{padding:6px;font-size:14px}}</style><main><h1>তোমার নিশ্চিত করা ৫টি ফল সংরক্ষিত</h1><p>তুমি তারিখসহ report দেখে এই ৫টি ফল নিশ্চিত করেছ। ৫৪১ নম্বরের আগের “পানি নেই” উত্তরটি “অনিশ্চিত” করা হয়েছে। বাকি চারটির উত্তর একই আছে। অন্য ৭১৫টি record অপরিবর্তিত।</p><table><thead><tr><th>ছবি নং</th><th>মাস</th><th>তোমার উত্তর</th><th>প্রমাণ</th></tr></thead><tbody>TABLE_ROWS</tbody></table><p class="note">মানুষের নিশ্চিতকরণ নথিভুক্ত হয়েছে। এটি AI-এর ব্যাখ্যা দেখার পরে guided review; পুরো মাসের অবস্থা বা পুরো ৭২০টির স্বাধীন accuracy সম্পন্ন হয়েছে বলা যাবে না। তাই সাধারণ CSV-তে binary উত্তরগুলো PRELIMINARY, অনিশ্চিত দুটো UNCERTAIN; আলাদা confirmation log-এ তোমার নিশ্চিতকরণ আছে।</p><ul><li><a href="water_reference_labels_user_confirmed_20261015.csv">সর্বশেষ ৭২০টি উত্তরের CSV</a></li><li><a href="water_review_backup_user_confirmed_20261015.json">সর্বশেষ সম্পূর্ণ Backup</a></li><li><a href="water_review_5_confirmations_20261015.json">শুধু এই ৫টির Import file</a> — মূল review page-এ প্রয়োজন হলে import করা যাবে।</li><li><a href="label_verification/user_pilot_confirmation_20261015/user_confirmation.json">তোমার নিশ্চিতকরণের রেকর্ড</a></li></ul><p>আগের সব label file, backup, ছবির evidence ও scientific result অক্ষত আছে।</p></main></html>'''.replace('TABLE_ROWS',table)
    with report.open('x',encoding='utf-8') as f:f.write(page)
    h,r=V.csv_read(target_csv);readback=V.audit_pair(h,r,V.json_read(target_json),data)
    assert readback['status']=='PASS'
    assert all(V.sha(Path(name))==digest for name,digest in input_hashes.items())
    checks={'status':'PASS','recorded_at_utc':now,'user_confirmed_points':5,'binary_confirmations':3,'uncertain_confirmations':2,
        'changed_records':5,'unchanged_records':715,'label_value_changes':[{'number':c['viewer_number'],'old':c['old']['label'],'new':c['new']['label']} for c in changed if c['old']['label']!=c['new']['label']],
        'input_sha256':input_hashes,'output_sha256':{str(p):V.sha(p) for p in (target_csv,target_json,target_patch,report)},
        'audit':readback,'old_and_new_records':changed,'independent_verified_reference_labels':0,
        'independent_accuracy_computed':False,'original_files_unchanged':True}
    write_json_new(LOG/'CONFIRMATION_CHECKS.json',checks)
    print(json.dumps({k:checks[k] for k in ('status','user_confirmed_points','binary_confirmations','uncertain_confirmations','unchanged_records','label_value_changes')},ensure_ascii=True))
    print(json.dumps({'label_counts':readback['label_counts'],'status_counts':readback['status_counts']},ensure_ascii=True))


if __name__=='__main__':main()
