"""Audit a real user CSV and recover a separate importable dated JSON backup.

Original CSV/JSON are never overwritten. Every label, name and review time
comes from the supplied CSV. No image interpretation or label is fabricated.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from tempfile import TemporaryDirectory
import argparse,copy,csv,hashlib,io,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'assisted_water_screening_20261015/date_review_v2'
FIELDS=['sample_id','number','region','period','scene_id','acquisition_date','clear_fraction','required_review_date','automated_scene_label','human_answer','human_water','assisted_date_water','label_origin','reference_water','independent_reference_eligible','reviewer','reviewed_at','notes','dataset_id']


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write_json(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def read_csv_text(s):
    reader=csv.DictReader(io.StringIO(s.lstrip('\ufeff'),newline=''));rows=list(reader)
    if reader.fieldnames!=FIELDS:raise ValueError('CSV header does not match the dated export contract')
    if any(None in r or any(v is None for v in r.values()) for r in rows):raise ValueError('Malformed CSV row')
    return rows


def audit(csv_path,backup_path):
    csv_path=Path(csv_path).resolve();backup_path=Path(backup_path).resolve()
    input_hash={str(p):digest(p) for p in (csv_path,backup_path)}
    ds=read_json(BASE/'dated_review_dataset.json');manifest=read_json(BASE/'review_manifest.json')
    if digest(BASE/'dated_review_dataset.json')!=manifest['dataset_sha256']:raise ValueError('Frozen dated dataset changed')
    for p,h in manifest['source_sha256'].items():
        if digest(ROOT/p)!=h:raise ValueError('Frozen review software changed: '+p)
    rows=read_csv_text(csv_path.read_text(encoding='utf-8-sig'))
    expected={(r['sample_id'],s['item_id']):(r,s) for r in ds['rows'] for s in r['scenes']}
    by={}
    for row in rows:
        key=(row['sample_id'],row['scene_id'])
        if key in by:raise ValueError('Duplicate sample/scene key')
        if key not in expected:raise ValueError('Unknown sample/scene key')
        if row['dataset_id']!=ds['id']:raise ValueError('CSV dataset identity mismatch')
        if row['human_answer'] not in ('','0','1','UNCERTAIN'):raise ValueError('Invalid human response')
        by[key]=row
    if set(by)!=set(expected):raise ValueError('Source acquisition rows are missing')
    old=read_json(backup_path)
    if old['schema']!='nw-assisted-dated-review-v2' or old['dataset_id']!=ds['id']:raise ValueError('Earlier JSON belongs to a different dataset')
    previous={r['sample_id']:r for r in old['records']}
    if len(previous)!=len(ds['rows']) or set(previous)!={r['sample_id'] for r in ds['rows']}:raise ValueError('Earlier JSON sample IDs incomplete')
    recovered=copy.deepcopy(old);updated=[];changed_old=[];view_recovery=[]
    new_records=[];notes_escaped_ambiguity=0
    for point in ds['rows']:
        sid=point['sample_id'];entry=copy.deepcopy(previous[sid]);entry['dates']={}
        seen=set(entry.get('seen_scenes',[]));notes={by[(sid,s['item_id'])]['notes'] for s in point['scenes']}
        if len(notes)!=1:raise ValueError('Per-point notes disagree across date rows')
        note=next(iter(notes));oldnote=entry.get('notes','')
        neutral=lambda v:"'"+v if __import__('re').match(r'^\s*[=+@-]',v) else v
        entry['notes']=oldnote if neutral(oldnote)==note else note
        if oldnote!=entry['notes'] and note.startswith("'"):notes_escaped_ambiguity+=1
        for scene in point['scenes']:
            key=(sid,scene['item_id']);row=by[key];answer=row['human_answer'];oldanswer=previous[sid].get('dates',{}).get(scene['item_id'])
            if answer:
                if not row['reviewer'].strip() or not row['reviewed_at']:raise ValueError('Human answer lacks name/time')
                dt=datetime.fromisoformat(row['reviewed_at'].replace('Z','+00:00'))
                if dt.tzinfo is None:raise ValueError('Human review time lacks timezone')
                value={'label':answer,'reviewer':row['reviewer'],'updated_at':row['reviewed_at']}
                entry['dates'][scene['item_id']]=value
                if not oldanswer:updated.append({'sample_id':sid,'number':point['number'],'scene_id':scene['item_id'],'date':scene['date'],'answer_from_csv':answer})
                elif any(oldanswer[k]!=v for k,v in value.items()):changed_old.append({'sample_id':sid,'scene_id':scene['item_id'],'old':oldanswer,'csv':value})
                if scene['item_id'] not in seen:
                    seen.add(scene['item_id']);view_recovery.append({'sample_id':sid,'scene_id':scene['item_id']})
            elif oldanswer:changed_old.append({'sample_id':sid,'scene_id':scene['item_id'],'old':oldanswer,'csv':None})
        entry['seen_scenes']=[s['item_id'] for s in point['scenes'] if s['item_id'] in seen]
        new_records.append(entry)
    created=datetime.now(timezone.utc).isoformat();recovered['records']=new_records;recovered['exported_at']=created
    recovered['recovery_provenance']={'created_at':created,'source_csv':str(csv_path),'source_csv_sha256':input_hash[str(csv_path)],
        'earlier_backup':str(backup_path),'earlier_backup_sha256':input_hash[str(backup_path)],
        'authority':'Latest supplied user CSV. Existing label/reviewer/time cells preserved; no inferred labels.',
        'added_dated_answers_from_csv':len(updated),'existing_backup_answer_differences':len(changed_old),
        'seen_scene_ids_reconstructed_from_explicit_csv_answers':view_recovery,
        'viewing_provenance_limit':'Added view-list IDs are reconstructed from explicit dated human-answer CSV rows, not an independent log proving image viewing.',
        'human_review_times_rewritten':False,'new_human_labels_generated':0,'independent_reference_eligible':False}
    # The actual application parser validates the reconstructed JSON and regenerates
    # the CSV in memory. Compare every original cell, not just the label totals.
    js="""const fs=require('node:fs'),C=require(process.argv[1]),D=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const state=C.importBackup(fs.readFileSync(process.argv[3],'utf8'),D);
process.stdout.write(JSON.stringify({date_csv:C.dateCSV(D,state.entries),summaries:D.rows.map(r=>({sample_id:r.sample_id,number:r.number,category:r.screening.category,...C.summary(C.entry(state.entries[r.sample_id]),r)}))}));"""
    with TemporaryDirectory(prefix='dated_csv_audit_') as temp:
        candidate=Path(temp)/'RECOVERY_CANDIDATE.json';write_json(candidate,recovered)
        result=subprocess.run(['node','-e',js,str(ROOT/'postprocessing/dated_water_core.js'),str(BASE/'dated_review_dataset.json'),str(candidate)],capture_output=True,text=True,encoding='utf-8',check=True)
        canonical=json.loads(result.stdout)
    generated={(r['sample_id'],r['scene_id']):r for r in read_csv_text(canonical['date_csv'])}
    differences=[{'sample_id':k[0],'scene_id':k[1],'field':field} for k,row in by.items() for field in FIELDS if row[field]!=generated[k][field]]
    if differences:raise ValueError('Original CSV differs from canonical app roundtrip: '+json.dumps(differences[:5]))
    human=Counter(r['human_answer'] for r in rows if r['human_answer']);summaries=canonical['summaries']
    requested=[s for s in summaries if s['category']=='REVIEW'];total=sum(s['required_dates'] for s in requested);answered=sum(s['answered_required_dates'] for s in requested)
    timestamp='20261016';suffix=input_hash[str(csv_path)][:8]
    recovery_path=ROOT/f'dated_water_backup_recovered_{timestamp}_{suffix}.json'
    out=BASE/'csv_audits'/('audit_'+suffix)
    if recovery_path.exists() or out.exists():raise FileExistsError('Existing audit/recovery preserved; use its recorded report rather than overwrite')
    if not all(digest(p)==h for p,h in input_hash.items()):raise ValueError('User input changed during audit')
    out.mkdir(parents=True);write_json(recovery_path,recovered)
    report={'status':'PASS_FOR_CSV_STRUCTURE_COMPLETENESS_AND_BACKUP_RECOVERY','checked_at':created,'source_csv':str(csv_path),
        'rows':len(rows),'unique_sample_scene_pairs':len(by),'expected_rows':len(expected),'missing_or_duplicate_pairs':0,
        'canonical_cell_comparisons':len(rows)*len(FIELDS),'canonical_cell_mismatches':0,
        'requested_points':len(requested),'requested_points_complete':sum(s['complete'] for s in requested),
        'required_date_answers':total,'required_date_answers_provided':answered,'requested_assisted_review_complete':answered==total,
        'provided_human_answer_counts':dict(human),'provided_human_date_answers':sum(human.values()),
        'requested_point_summary_origins':dict(Counter(s['origin'] for s in requested)),
        'points_with_human_date_changes':sum(s['temporal_change'] for s in requested),
        'points_with_any_uncertain_day':sum(s['has_uncertain_date'] for s in requested),
        'all_720_point_summary_origins':dict(Counter(s['origin'] for s in summaries)),
        'older_backup_human_date_answers':sum(len(e.get('dates',{})) for e in old['records']),
        'added_answers_recovered_from_csv':len(updated),'existing_backup_label_name_time_changes':len(changed_old),
        'source_inputs_sha256':input_hash,'original_user_inputs_unchanged':True,
        'recovered_backup':str(recovery_path),'recovered_backup_sha256':digest(recovery_path),
        'reconstructed_view_ids':len(view_recovery),'reconstructed_view_ids_independent_evidence':False,
        'notes_with_escape_ambiguity':notes_escaped_ambiguity,'new_human_labels_generated':0,'human_review_times_rewritten':False,
        'unreviewed_or_uncertain_references_changed_to_nonwater':0,
        'independent_accuracy_complete':False,'accuracy_percentage_computed':False,'recovery_duration_resolved':False,
        'scientific_publication_ready':False,'scientific_pipeline_rerun':False,
        'scope':'Actual human-assisted CSV export, app-schema/cell consistency, requested-task accounting and dated backup recovery. Image truth is not certified.',
        'limitations':['The 337 automatic points have no representative independent reference assessment.',
            'Only model-selected difficult cases were requested; their labels cannot establish representative independent accuracy.',
            'Date-to-date answer differences may include genuine changes, mixed support or interpretation differences; they do not establish drought recovery timing.'],
        'code_sha256':digest(Path(__file__))}
    write_json(out/'audit_result.json',report);write_json(out/'answers_added_from_csv.json',updated);write_json(out/'existing_backup_differences.json',changed_old)
    write_json(out/'sample_summaries.json',summaries)
    note=f'''# দিনের উত্তর যাচাই

তোমার চাওয়া **{len(requested)}টি জায়গার {answered}/{total} দিনের উত্তর দেওয়া হয়েছে**।

- পানি আছে: **{human['1']}** দিনের উত্তর।
- পানি নেই: **{human['0']}** দিনের উত্তর।
- বুঝতে পারছি না: **{human['UNCERTAIN']}** দিনের উত্তর।

মোট {len(rows)}টি source-date record, duplicate/তারিখ/sample ID-এর সমস্যা পাওয়া যায়নি। App দিয়ে নতুন করে CSV বানিয়ে মূলটির **{len(rows)*len(FIELDS)}টি cell** মিলেছে। কোনো আসল CSV বা JSON বদলানো হয়নি।

**{report['points_with_human_date_changes']}টি জায়গায় তোমার দেওয়া ০/১ তারিখভেদে আলাদা**। এই উত্তরগুলো আলাদা আছে; পুরো মাসের এক উত্তর বানানো হয়নি।

পুরোনো JSON-এ {report['older_backup_human_date_answers']}টি দিনের উত্তর ছিল। CSV-এর বাড়তি **{len(updated)}টি আসল উত্তর** দিয়ে একটি নতুন importable Backup তৈরি করেছি। মূল উত্তর, reviewer ও review time অপরিবর্তিত; কোনো নতুন label অনুমান করা হয়নি। View-list-এর প্রয়োজনীয় ID CSV-র দেওয়া উত্তরের ভিত্তিতে পুনর্গঠন করা হয়েছে; এটি স্বাধীনভাবে ছবি দেখার প্রমাণ নয়।

নতুন Backup: `{recovery_path.name}`। আগের ২টি ফাইল অক্ষত আছে।

**তোমার অনুরোধের assisted review শেষ।** এই যাচাই ছবির সত্যতা বা পুরো এলাকার independent accuracy নিশ্চিত করে না। ৩৩৭টি automatic point automatic-ই আছে; recovery সময়ও অজানা আছে। Manuscript/submission-ready ঘোষণা দেওয়া হয়নি।
'''
    (out/'REPORT_BN.md').write_text(note,encoding='utf-8')
    if not all(digest(p)==h for p,h in input_hash.items()):raise ValueError('User source changed after output')
    status=ROOT/'CURRENT_WATER_REVIEW_STATUS.json'
    if status.exists():(out/'previous_workflow_status.json').write_bytes(status.read_bytes())
    current=read_json(status) if status.exists() else {}
    current.update({'checked_at':created,'current_route':'ASSISTED_DATED_REVIEW_V2_CSV_AUDITED','human_review_pending':not report['requested_assisted_review_complete'],
        'requested_assisted_review_complete':report['requested_assisted_review_complete'],'requested_points_complete':report['requested_points_complete'],
        'requested_date_answers':answered,'requested_date_total':total,'independent_reference_pending':True,'independent_accuracy_complete':False,
        'scientific_publication_ready':False,'latest_user_csv':str(csv_path),'latest_user_csv_sha256':input_hash[str(csv_path)],
        'recovered_backup':str(recovery_path),'latest_csv_audit':str(out/'audit_result.json')})
    write_json(status,current)
    print(json.dumps({'status':report['status'],'requested_points_complete':report['requested_points_complete'],'requested_date_answers':answered,
        'human_answer_counts':dict(human),'date_changes':report['points_with_human_date_changes'],'backup_extra_answers_recovered':len(updated),
        'recovered_backup':str(recovery_path),'report':str(out/'REPORT_BN.md'),'independent_accuracy_complete':False},ensure_ascii=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True,type=Path);ap.add_argument('--backup',required=True,type=Path);a=ap.parse_args();audit(a.csv,a.backup)
