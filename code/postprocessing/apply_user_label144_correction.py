"""One explicit user-directed dated correction, preserving original exports."""
from copy import deepcopy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from postprocessing.finalize_code_only_research import read,write,digest,require,DATED,HUMAN_CSV,BACKUP

SID='b_0a0e34935c6e74d9804cd2'
SCENE='S2B_MSIL2A_20230330T043709_R033_T45RXH_20240824T175150'
BASE=ROOT/'label_verification/user_correction_sample144_20261016'
NEW_CSV=ROOT/'dated_water_labels_corrected_sample144_20261016.csv'
NEW_BACKUP=ROOT/'dated_water_backup_corrected_sample144_20261016.json'


def revise_answer(backup,sid,scene_id,new_label,recorded_at):
    require(new_label in ('0','1','UNCERTAIN'),'Invalid explicit user decision')
    copied=deepcopy(backup)
    candidates=[r for r in copied['records'] if r['sample_id']==sid]
    require(len(candidates)==1 and scene_id in candidates[0]['dates'],'Exact sample/date not found')
    current=candidates[0]['dates'][scene_id]
    old=deepcopy(current)
    require(old['label']!=new_label,'Already has this decision; no new correction is needed')
    current['label']=new_label
    current['updated_at']=recorded_at
    # This is the time the chat-directed correction was recorded, not evidence
    # that the user opened the image again at this time.
    copied['exported_at']=recorded_at
    return copied,old,deepcopy(current)


def main():
    require(not NEW_CSV.exists() and not NEW_BACKUP.exists(),'Existing corrected exports are preserved')
    BASE.mkdir(parents=True,exist_ok=True)
    original_hashes={str(p.relative_to(ROOT)):digest(p) for p in (HUMAN_CSV,BACKUP,ROOT/'CURRENT_WATER_REVIEW_STATUS.json')}
    data=read(DATED/'dated_review_dataset.json')
    point=next(r for r in data['rows'] if r['sample_id']==SID)
    require(point['number']==144,'Displayed sample number no longer matches exact ID')
    require(next(s for s in point['scenes'] if s['item_id']==SCENE)['date']=='2023-03-30','Wrong acquisition date')
    now=datetime.now(timezone.utc).isoformat()
    before=read(BACKUP)
    corrected,old,new=revise_answer(before,SID,SCENE,'1',now)
    require(old['label']=='0','Unexpected earlier human decision')
    change={'sample_id':SID,'display_number':144,'scene_id':SCENE,'acquisition_date':'2023-03-30',
            'old_answer':old,'new_answer':new,'recorded_at':now,
            'authority':'User explicitly requested correction to 1 after seeing the code result in this chat',
            'source_user_instruction':'code: 1 (পানি আছে) hobe fix kore deo',
            'new_image_view_attested':False,'correction_time_is_not_image_view_proof':True,
            'independent_reference_eligible':False}
    corrected.setdefault('label_revision_history',[]).append(change)
    corrected['scope']='Actual assisted labels with one explicitly user-directed, code-informed correction; not independent accuracy.'
    write(NEW_BACKUP,corrected)
    js=r"""const fs=require('fs'),path=require('path'),root=process.argv[1];
const C=require(path.join(root,'postprocessing/dated_water_core.js'));
const D=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const state=C.importBackup(fs.readFileSync(process.argv[3],'utf8'),D);
process.stdout.write(JSON.stringify({csv:C.dateCSV(D,state.entries),summary:C.summaryCSV(D,state.entries),summaries:D.rows.map(r=>({sample_id:r.sample_id,...C.summary(C.entry(state.entries[r.sample_id]),r)}))}));"""
    parsed=subprocess.run(['node','-e',js,str(ROOT),str(DATED/'dated_review_dataset.json'),str(NEW_BACKUP)],capture_output=True,text=True,encoding='utf-8',check=True)
    exported=json.loads(parsed.stdout)
    NEW_CSV.write_bytes(exported['csv'].encode('utf-8'))
    (BASE/'corrected_point_summaries.csv').write_bytes(exported['summary'].encode('utf-8'))
    original_rows=list(csv.DictReader(io.StringIO(HUMAN_CSV.read_text(encoding='utf-8-sig'))))
    new_rows=list(csv.DictReader(io.StringIO(exported['csv'].lstrip('\ufeff'))))
    require(len(original_rows)==len(new_rows)==3022,'Source acquisition row count changed')
    differences=[]
    for a,b in zip(original_rows,new_rows):
        require((a['sample_id'],a['scene_id'])==(b['sample_id'],b['scene_id']),'CSV row identities shifted')
        for field in a:
            if a[field]!=b[field]:differences.append({'sample_id':a['sample_id'],'scene_id':a['scene_id'],'field':field,'before':a[field],'after':b[field]})
    require({(r['sample_id'],r['scene_id']) for r in differences}=={(SID,SCENE)},'Another dated answer changed')
    require({r['field'] for r in differences}=={'human_answer','human_water','assisted_date_water','reviewed_at'},'Unexpected CSV change')
    for a,b in zip(before['records'],corrected['records']):
        require(a['sample_id']==b['sample_id'],'Backup sample ordering changed')
        if a['sample_id']!=SID:require(a==b,'Another point record changed')
        else:
            for scene,answer in a['dates'].items():
                if scene!=SCENE:require(answer==b['dates'][scene],'Another acquisition answer changed')
    target=next(s for s in exported['summaries'] if s['sample_id']==SID)
    require(target['origin']=='HUMAN_DATES_CONSISTENT' and target['water']=='1' and not target['temporal_change'],'Corrected point is not consistently water on its answered dates')
    require(original_hashes=={str(p.relative_to(ROOT)):digest(p) for p in (HUMAN_CSV,BACKUP,ROOT/'CURRENT_WATER_REVIEW_STATUS.json')},'Original input modified')
    check={
        'status':'ONE_EXPLICIT_USER_DATED_CORRECTION_APPLIED_TO_NEW_VERSION', 'change':change,
        'changed_dated_answers':1,'changed_csv_cells':len(differences),'other_answers_changed':0,
        'csv_app_roundtrip':'PASS','new_csv':str(NEW_CSV),'new_csv_sha256':digest(NEW_CSV),
        'new_backup':str(NEW_BACKUP),'new_backup_sha256':digest(NEW_BACKUP),
        'old_inputs_preserved_sha256':original_hashes,'manual_labels_automatically_inferred':0,
        'other_454_answers_overridden':False,'independent_accuracy_complete':False,
        'downstream_refresh_required':True,'new_image_review_or_independence_claimed':False,
    }
    write(BASE/'CORRECTION.json',check)
    write(BASE/'csv_cell_differences.json',differences)
    print(json.dumps({k:check[k] for k in ('status','changed_dated_answers','changed_csv_cells','other_answers_changed','new_csv','new_backup')},indent=2))


if __name__=='__main__':main()
