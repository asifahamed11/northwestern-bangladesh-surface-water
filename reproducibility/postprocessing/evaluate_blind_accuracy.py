"""Evaluate real, blinded human reference backups without discarding unknowns.

Never fabricates reference labels. Class predictions are joined only after
freezing the supplied human-backup digest. The primary estimand is agreement
with human-interpreted Sentinel-2 references for four observed JRC months.
Unknown-reference bounds and verified-support conditional accuracy are
separate. They do not certify all-year, annual-class, or physical ground truth.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import argparse,csv,hashlib,json,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research_pipeline.common import digest

BASE=ROOT/'independent_accuracy_20261015'
SCHEMA='nw-independent-dated-review-v1'


def read_json(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate JSON key: '+k)
            result[k]=v
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique)


def decision(e,row):
    if e.get('label','') not in ('','0','1','UNCERTAIN'):raise ValueError('Unknown answer')
    if not isinstance(e.get('attested',False),bool):raise ValueError('Attestation must be boolean')
    if any(not isinstance(e.get(k,''),str) for k in ('label','reviewer','notes','reason','updated_at')):raise ValueError('Reference text type mismatch')
    seen=e.get('seen_scenes',[])
    if not isinstance(seen,list) or any(not isinstance(s,str) for s in seen) or len(seen)!=len(set(seen)):raise ValueError('Seen scene IDs are not unique strings')
    expected={s['item_id'] for s in row['scenes']}
    if set(seen)-expected:raise ValueError('Foreign scene IDs in human backup')
    if e.get('updated_at'):
        dt=datetime.fromisoformat(e['updated_at'].replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError('Review timestamp lacks timezone')
    label=e.get('label','')
    if not label:return 'PENDING',None
    if not e.get('reviewer','').strip() or not e.get('updated_at'):return 'PRELIMINARY',None
    if label=='UNCERTAIN':return ('UNCERTAIN',None) if set(seen)==expected else ('PRELIMINARY',None)
    usable=[s for s in row['scenes'] if s['item_id'] in seen and s['clear_fraction']>=.95]
    dates=[datetime.fromisoformat(s['date']) for s in usable]
    ok=len(row['scenes'])>=3 and set(seen)==expected and len(dates)>=2 and (max(dates)-min(dates)).days>=14
    ok=ok and all(s['date'][:7]==row['period'] for s in row['scenes'])
    if e.get('attested') and not ok:raise ValueError('Invalid VERIFIED declaration')
    return ('VERIFIED',int(label)) if e.get('attested') and ok else ('PRELIMINARY',None)


def summarize(predictions,references,weights):
    p=np.asarray(predictions,dtype=float);r=np.asarray(references,dtype=float);w=np.asarray(weights,dtype=float)
    if len(p)!=len(r) or len(p)!=len(w) or not np.isfinite(w).all() or np.any(w<=0):raise ValueError('Invalid paired arrays or design weights')
    if not np.isin(p,[0,1]).all():raise ValueError('Invalid map prediction')
    p=p.astype(int)
    if np.isinf(r).any():raise ValueError('Infinite reference is invalid, not missing')
    if not np.isin(r[np.isfinite(r)],[0,1]).all():raise ValueError('Invalid reference class')
    known=np.isfinite(r);total=float(w.sum());known_w=float(w[known].sum());unknown_w=total-known_w
    correct=float(w[known & (p==r)].sum())
    cm=np.zeros((2,2),dtype=float)
    for rr in (0,1):
        for pp in (0,1):cm[rr,pp]=w[known & (r==rr) & (p==pp)].sum()
    return {'n':len(p),'n_verified_binary':int(known.sum()),'n_unknown_reference':int((~known).sum()),
        'design_weight_total':total,'verified_reference_weight_fraction':known_w/total if total else None,
        'unknown_reference_weight_fraction':unknown_w/total if total else None,
        'conditional_accuracy_on_verified_support':correct/known_w if known_w else None,
        'accuracy_identification_lower':correct/total if total else None,
        'accuracy_identification_upper':(correct+unknown_w)/total if total else None,
        'conditional_water_producer_accuracy':float(cm[1,1]/cm[1,:].sum()) if cm[1,:].sum() else None,
        'conditional_water_user_accuracy':float(cm[1,1]/cm[:,1].sum()) if cm[:,1].sum() else None,
        'verified_support_confusion_weights':cm.tolist()}


def bootstrap(pred,references,weights,strata,replicates=1000,seed=20261022):
    rng=np.random.default_rng(seed);groups=[np.flatnonzero(strata==s) for s in sorted(set(strata))]
    conditional=[];lo=[];hi=[]
    for _ in range(replicates):
        indices=np.concatenate([rng.choice(g,size=len(g),replace=True) for g in groups])
        m=summarize(pred[indices],references[indices],weights[indices])
        if m['conditional_accuracy_on_verified_support'] is not None:conditional.append(m['conditional_accuracy_on_verified_support'])
        lo.append(m['accuracy_identification_lower']);hi.append(m['accuracy_identification_upper'])
    return {'method':'1000 within-stratum unit bootstrap replicates, fixed seed; with-replacement approximation to SRSWOR. Sampling uncertainty conditional on the fixed map/frame, not reference or geolocation truth.',
        'replicates':replicates,'seed':seed,
        'estimand':'Area-time weighted agreement across the four sampled monthly observed-pixel frames, excluding previous exposed sample cells; not the entire historical record.',
        'conditional_accuracy_interval95':list(map(float,np.quantile(conditional,[.025,.975]))) if conditional else None,
        'identification_bounds_outer_sampling_interval95':[float(np.quantile(lo,.025)),float(np.quantile(hi,.975))],
        'reference_error_or_temporal_mismatch_included_in_interval':False}


def evaluate(backup_path,base=BASE,out=None):
    backup_path=Path(backup_path)
    # Freeze human file identity before opening target predictions.
    human_hash=digest(backup_path);backup=read_json(backup_path)
    dataset=read_json(base/'public/review_dataset.json')
    identity={k:v for k,v in dataset.items() if k!='id'}
    expected=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if dataset['id']!=expected or backup.get('schema')!=SCHEMA or backup.get('dataset_id')!=expected:raise ValueError('Dataset/backup identity mismatch')
    exported=datetime.fromisoformat(backup.get('exported_at','').replace('Z','+00:00'))
    if exported.tzinfo is None:raise ValueError('Backup exported_at lacks timezone')
    rows={r['sample_id']:r for r in dataset['rows']};entries={}
    for entry in backup.get('records',[]):
        sid=entry.get('sample_id')
        if sid not in rows or sid in entries:raise ValueError('Duplicate/unknown sample ID')
        if entry.get('updated_at') and datetime.fromisoformat(entry['updated_at'].replace('Z','+00:00'))>exported:raise ValueError('Answer timestamp is after backup export')
        entries[sid]=entry
    if set(entries)!=set(rows):raise ValueError('Full backup must contain every planned sample ID')
    status_and_labels={sid:decision(e,rows[sid]) for sid,e in entries.items()}
    manifest=read_json(base/'review_manifest.json')
    if manifest['dataset_id']!=expected:raise ValueError('Review manifest identity mismatch')
    for relative,expected_hash in manifest['frozen_evaluation_inputs_sha256'].items():
        if digest(base/relative)!=expected_hash:raise ValueError('Frozen evaluation input changed: '+relative)
    target=read_json(base/'private/validation_sample_plan.json')
    if len(target)!=len(rows) or {p['sample_id'] for p in target}!=set(rows):raise ValueError('Private plan / human sample mismatch')
    strat_info=read_json(base/'private/stratum_counts.json')
    predictions=[];references=[];weights=[];strata=[];status=[]
    for p in target:
        s,label=status_and_labels[p['sample_id']]
        predictions.append(p['predicted_water']);references.append(np.nan if label is None else label)
        weights.append(p['population_pixels']/p['planned_samples']*p['pixel_area_km2']);strata.append(p['stratum']);status.append(s)
    pred=np.asarray(predictions);ref=np.asarray(references);w=np.asarray(weights);group=np.asarray(strata);states=np.asarray(status)
    table=[]
    for s in strat_info:
        mask=group==s['stratum'];known=np.isfinite(ref[mask]).sum()
        table.append({'stratum':s['stratum'],'sampled':int(mask.sum()),'verified_binary':int(known),
          'uncertain':int((states[mask]=='UNCERTAIN').sum()),'pending_or_preliminary':int(np.isin(states[mask],['PENDING','PRELIMINARY']).sum()),
          'minimum_verified':s['minimum_verified'],'count_gate_pass':bool(known>=s['minimum_verified'])})
    all_reviewed=not np.isin(states,['PENDING','PRELIMINARY']).any()
    all_counts=all(s['count_gate_pass'] for s in table)
    metrics=summarize(pred,ref,w)
    inference=bootstrap(pred,ref,w,group) if all_reviewed and all_counts else None
    result={'status':'EVALUATED_WITH_UNCERTAINTY' if all_reviewed and all_counts else 'INCOMPLETE_HUMAN_REFERENCE_REVIEW',
      'checked_at':datetime.now(timezone.utc).isoformat(),'human_backup_sha256':human_hash,
      'human_backup_source':str(backup_path.resolve()),'counts':dict(Counter(status)),
      'all_planned_samples_reviewed':bool(all_reviewed),'all_stratum_minimum_counts_met':bool(all_counts),
      'scope':'Area-time weighted agreement with human-interpreted dated Sentinel-2 references for four observed JRC monthly maps in three districts; exposed prior sample cells excluded.',
      'metrics':metrics if np.isfinite(ref).any() else None,'sampling_uncertainty':inference,
      'uncertain_and_unreviewed_samples_dropped':False,'global_accuracy_point_estimate_assuming_random_nonresponse_reported':False,
      'physical_ground_truth_accuracy_certified':False,'annual_hydroperiod_accuracy_validated':False,'all_historical_years_validated':False,
      'recovery_duration_resolved':False,'scientific_publication_ready':False,
      'prewriting_reference_collection_gate_pass':bool(all_reviewed and all_counts),
      'limitations':['Human/reference interpretation, co-registration and within-month timing errors remain.','Prepared acquisitions do not cover every day.','Conditional accuracy refers only to verified reference support; unknowns remain in identification bounds.','Bootstrap intervals are approximate design-based sampling uncertainty, not a guarantee of correctness.','Operational blinding and human attestations are not secure-isolation proof.']}
    if out is None:out=base/'evaluations'/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'validation_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    with (out/'stratum_completeness.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    (out/'input_sha256.json').write_text(json.dumps({str(backup_path.resolve()):human_hash,str(base/'public/review_dataset.json'):digest(base/'public/review_dataset.json'),str(base/'private/validation_sample_plan.json'):digest(base/'private/validation_sample_plan.json')},indent=2),encoding='utf-8')
    if digest(backup_path)!=human_hash:raise ValueError('Human input changed during evaluation')
    return result,out


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--backup',type=Path);ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if not args.backup:
        print(json.dumps({'status':'PENDING_HUMAN_REFERENCE_BACKUP','accuracy_computed':False,'reason':'Export the new independent review JSON after real human decisions. No old guided answers or synthetic labels will be substituted.'}))
    else:
        result,out=evaluate(args.backup,out=args.out)
        print(json.dumps({'status':result['status'],'output':str(out),'counts':result['counts'],'prewriting_reference_collection_gate_pass':result['prewriting_reference_collection_gate_pass']},ensure_ascii=True))
