"""Apply only the seven corrections explicitly supplied by the user in chat.

Original CSV/JSON are preserved. These are cue-informed preliminary revisions,
not newly acquired dated independent reference labels.
"""
from pathlib import Path
import copy
import csv
from datetime import datetime,timezone
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import verify_water_labels as V

CORRECTIONS={
    76:('s_4abe0e25cd7ad6ca2b8e','0'),
    96:('s_137c641421ea690104ff','0'),
    279:('s_b6201626a41753c45f4a','0'),
    542:('s_4a31d81f7b35520779df','0'),
    573:('s_99126c53059ff80c4a03','0'),
    707:('s_fb26066bd6f4d76fb18e','0'),
    720:('s_7fefcde1edc28feecdfc','UNCERTAIN'),
}


def apply():
    source_csv=ROOT/'water_reference_labels_2026-10-15T09-00-32-461Z.csv'
    source_json=ROOT/'water_review_backup_2026-10-15T09-00-37-140Z.json'
    output_csv=ROOT/'water_reference_labels_corrected_20261015.csv'
    output_json=ROOT/'water_review_backup_corrected_20261015.json'
    patch_json=ROOT/'water_review_7_corrections_20261015.json'
    log_json=ROOT/'label_verification/user_corrections_20261015.json'
    for path in [output_csv,output_json,patch_json,log_json]:
        if path.exists():raise FileExistsError('Existing output preserved: '+str(path))
    before={str(p):V.sha(p) for p in [source_csv,source_json,ROOT/'Water_Review.html',ROOT/'Water_Review.manifest.json']}
    headers,original_rows=V.csv_read(source_csv);original=V.json_read(source_json)
    data,_=V.read_viewer(ROOT/'Water_Review.html')
    audit=V.audit_pair(headers,original_rows,original,data)
    if audit['status']!='PASS':raise ValueError('Original pair failed integrity audit')
    previous=V.json_read(ROOT/'label_verification/review_20261015_090032/verification.json')
    for path,digest in before.items():
        if previous['input_sha256'].get(path)!=digest:raise ValueError('Original checked snapshot changed')
    revised=copy.deepcopy(original);entries={e['sample_id']:e for e in revised['records']}
    stamp=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    changes=[]
    for number,(sid,label) in CORRECTIONS.items():
        if data['rows'][number-1]['id']!=sid:raise ValueError('Display number/ID mismatch')
        entry=entries[sid]
        if entry['label']!='1' or entry['attested']:raise ValueError('Unexpected original answer or verification declaration')
        old=copy.deepcopy(entry)
        entry['label']=label;entry['attested']=False;entry['updated_at']=stamp
        entry['reason']='অন্য কারণ' if label=='UNCERTAIN' else ''
        note=('ব্যবহারকারীর পুনঃপর্যালোচনা: এখনও সংশয় আছে; অনিশ্চিত রাখা হলো।' if label=='UNCERTAIN'
              else 'ব্যবহারকারীর পুনঃপর্যালোচনা: পানি নেই।')
        note+=' অটোমেটেড ইঙ্গিতের report দেখার পরে চ্যাটে দেওয়া সংশোধন; স্বাধীন dated evidence যোগ হয়নি।'
        entry['notes']=entry['notes']+'\n'+note if entry['notes'] else note
        changes.append({'viewer_number':number,'sample_id':sid,'old':old,'new':copy.deepcopy(entry),
                        'authorization':'Explicit user correction in current chat; confused at point 720 interpreted as UNCERTAIN'})
    revised['exported_at']=stamp
    revised['revision_context']={'kind':'USER_CORRECTION_AFTER_AUTOMATED_CUE_FEEDBACK','corrected_ids':list(CORRECTIONS[n][0] for n in CORRECTIONS),
                                 'source_backup_sha256':before[str(source_json)],'new_independent_dated_evidence':False}
    patch={k:v for k,v in revised.items() if k!='records'}
    patch['records']=[copy.deepcopy(entries[sid]) for sid,_ in CORRECTIONS.values()]
    csv_by={r['sample_id']:copy.deepcopy(r) for r in original_rows};canonical={r['id']:r for r in data['rows']}
    for sid,entry in entries.items():
        row=csv_by[sid];quality=V.status(entry,canonical[sid])
        row.update(reference_water=entry['label'] if quality=='VERIFIED' else '',reference_date=entry['reference_date'],
                   reference_source=V.neutral(entry['reference_source']),reference_quality='' if quality=='PENDING' else quality,
                   notes=V.neutral(entry['notes']),preliminary_review=entry['label'],evidence_id=V.neutral(entry['evidence_id']),
                   reviewer=V.neutral(entry['reviewer']),evidence_attested='true' if quality=='VERIFIED' else 'false',
                   reviewed_at=entry['updated_at'],uncertainty_reason=V.neutral(entry['reason']))
    new_rows=[csv_by[sid] for sid in data['export_order']]
    audit=V.audit_pair(headers,new_rows,revised,data)
    if audit['status']!='PASS':raise ValueError(audit['issues'])
    original_entries={e['sample_id']:e for e in original['records']}
    changed_json={sid for sid,e in entries.items() if e!=original_entries[sid]}
    original_csv_by={r['sample_id']:r for r in original_rows}
    changed_csv={r['sample_id'] for r in new_rows if r!=original_csv_by[r['sample_id']]}
    expected_ids={sid for sid,_ in CORRECTIONS.values()}
    if changed_json!=changed_csv or changed_json!=expected_ids:raise ValueError('Changes outside the seven authorized IDs')
    for sid in expected_ids:
        if entries[sid]['reference_date'] or entries[sid]['reference_source'] or csv_by[sid]['reference_water'] or csv_by[sid]['evidence_attested']!='false':
            raise ValueError('Unsupported independent verification introduced')
    with output_csv.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(new_rows)
    for path,obj in [(output_json,revised),(patch_json,patch)]:
        with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
    reread_headers,reread_rows=V.csv_read(output_csv)
    reread_audit=V.audit_pair(reread_headers,reread_rows,V.json_read(output_json),data)
    if reread_audit['status']!='PASS':raise ValueError('Saved file readback failed')
    if any(V.sha(Path(path))!=digest for path,digest in before.items()):raise ValueError('Original file changed')
    record={'status':'PASS','created_utc':stamp,'source_sha256':before,
            'output_sha256':{str(p):V.sha(p) for p in [output_csv,output_json,patch_json]},
            'changed_ids':sorted(expected_ids),'unchanged_ids':len(data['rows'])-len(expected_ids),
            'changes':changes,'audit':reread_audit,'original_files_unchanged':True,
            'independent_accuracy_computed':False,'guided_revision_is_not_a_blind_test':True}
    with log_json.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':'PASS','changed_ids':len(expected_ids),'unchanged_ids':record['unchanged_ids'],
                      'labels':reread_audit['label_counts'],'qualities':reread_audit['status_counts'],
                      'csv':str(output_csv),'backup':str(output_json),'seven_record_import':str(patch_json)},ensure_ascii=False,indent=2))


if __name__=='__main__':apply()
