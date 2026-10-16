"""Audit manual-review CSV/JSON and colour-related satellite cues.

This checker NEVER edits labels, promotes them to VERIFIED, computes map
accuracy, or uses the private JRC predictions. Raster cross-checks reproduce
the existing fixed benchmark; agreement is not ground truth.

Run in the project folder: python verify_water_labels.py
Optional quick run: python verify_water_labels.py --raster-check none
"""
from pathlib import Path
import argparse
import base64
import collections
import csv
from datetime import date, datetime, timezone
import hashlib
import html
import json
import math
import re
import sys

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'research_outputs/analysis_20261013_completed_data'
EVIDENCE=RUN/'independent_sensor_evidence'
SCHEMA='nw-water-manual-review-v1'
CSV_COLUMNS=['sample_id','region','year','month','longitude','latitude','reference_water','reference_date','reference_source','reference_quality','notes','preliminary_review','evidence_id','reviewer','evidence_attested','reviewed_at','dataset_id','uncertainty_reason']
ENTRY_FIELDS=['label','notes','reason','reference_date','reference_source','evidence_id','reviewer','attested','updated_at']
LABELS={'','0','1','UNCERTAIN'}
CHECK_NAMES={'CUE_AGREEMENT':'সহায়ক ইঙ্গিতের সঙ্গে মিল','CUE_CONFLICT':'দুই ইঙ্গিতের বিপরীত — আবার দেখো','MIXED_PIXEL':'পানি-মাটি মিশ্র ইঙ্গিত','SENSOR_DISAGREEMENT':'দুই সেন্সরের ইঙ্গিত আলাদা','INSUFFICIENT_PIXEL_SUPPORT':'পর্যাপ্ত পর্যবেক্ষণ নেই','HUMAN_UNCERTAIN':'তোমার উত্তর অনিশ্চিত','PENDING':'উত্তর বাকি'}
PRIORITY={'CUE_CONFLICT':0,'INSUFFICIENT_PIXEL_SUPPORT':1,'SENSOR_DISAGREEMENT':2,'MIXED_PIXEL':3,'HUMAN_UNCERTAIN':4,'PENDING':5,'CUE_AGREEMENT':6}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def csv_read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f,strict=True);headers=next(reader)
        if len(headers)!=len(set(headers)):raise ValueError('Duplicate CSV column names')
        rows=[]
        for values in reader:
            if not values:continue
            if len(values)!=len(headers):raise ValueError(f'Column-count mismatch at CSV line {reader.line_num}')
            rows.append(dict(zip(headers,values)))
    return headers,rows


def unique_json_pairs(pairs):
    d={}
    for key,value in pairs:
        if key in d:raise ValueError('Duplicate JSON key: '+key)
        d[key]=value
    return d


def json_read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_json_pairs)


def neutral(value):
    return "'"+value if re.match(r'^[\t\r\n ]*[=+@-]',value) else value


def date_ok(value,period):
    try:return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',value)) and date.fromisoformat(value).strftime('%Y-%m')==period
    except (ValueError,TypeError):return False


def parse_time(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        if d.tzinfo is None:return None
        return d.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None


def evidence_errors(entry,row):
    errors=[]
    if entry.get('label') not in ['0','1']:errors.append('binary label missing')
    if not date_ok(entry.get('reference_date',''),row['period']):errors.append('actual date missing or outside target month')
    source=entry.get('reference_source','')
    if not isinstance(source,str) or not source.strip():errors.append('independent source missing')
    elif re.search(r'\bJRC\b|\bGSW\b|global[ ._-]*surface[ ._-]*water',source,re.I):errors.append('JRC/GSW self-reference')
    for key in ['evidence_id','reviewer']:
        if not isinstance(entry.get(key,''),str) or not entry.get(key,'').strip():errors.append(key+' missing')
    return errors


def status(entry,row):
    if entry.get('attested') is True and not evidence_errors(entry,row):return 'VERIFIED'
    if entry.get('label')=='UNCERTAIN':return 'UNCERTAIN'
    return 'PRELIMINARY' if entry.get('label') in ['0','1'] else 'PENDING'


def read_viewer(path):
    path=Path(path);manifest=json_read(path.with_suffix('.manifest.json'))
    if sha(path)!=manifest['output_sha256']:raise ValueError('Viewer checksum differs from its manifest')
    text=path.read_text(encoding='utf-8')
    match=re.search(r'<script id="review-dataset" type="application/json">(.*?)</script>',text,re.S)
    if not match:raise ValueError('Canonical viewer dataset not found')
    data=json.loads(match[1],object_pairs_hook=unique_json_pairs)
    ids=[r['id'] for r in data['rows']]
    if len(ids)!=len(set(ids)) or set(ids)!=set(data['export_order']):raise ValueError('Canonical dataset IDs are not one-to-one')
    identity={'rows':[{k:v for k,v in r.items() if k!='image'} for r in data['rows']], 'export_order':data['export_order'],'source_grid':data['source_grid']}
    expected=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if expected!=data['id'] or data['id']!=manifest['dataset_id']:raise ValueError('Canonical dataset identity mismatch')
    return data,manifest


def audit_pair(headers,rows,backup,data):
    """Independently reproduce the documented export contract, joined by ID."""
    issues=[]
    def problem(code,message,sample_id=''):issues.append({'code':code,'sample_id':sample_id,'message':message})
    canonical={r['id']:r for r in data['rows']};csv_ids=[r.get('sample_id','') for r in rows]
    if set(CSV_COLUMNS)-set(headers):problem('CSV_SCHEMA','Missing columns: '+','.join(sorted(set(CSV_COLUMNS)-set(headers))))
    if not isinstance(backup,dict) or backup.get('schema')!=SCHEMA:problem('JSON_SCHEMA','Unknown backup schema')
    if backup.get('dataset_id')!=data['id']:problem('DATASET_ID','Backup belongs to a different dataset')
    records=backup.get('records',[])
    if not isinstance(records,list):records=[];problem('JSON_RECORDS','Backup records must be a list')
    json_ids=[r.get('sample_id','') if isinstance(r,dict) else '' for r in records]
    for label,ids in [('CSV',csv_ids),('JSON',json_ids)]:
        if len(ids)!=len(canonical):problem(label+'_COUNT',f'{len(ids)} records; expected {len(canonical)}')
        for sid,n in collections.Counter(ids).items():
            if n>1:problem(label+'_DUPLICATE',f'{n} records with the same ID',sid)
        for sid in set(ids)-set(canonical):problem(label+'_UNKNOWN','Unknown sample ID',sid)
        for sid in set(canonical)-set(ids):problem(label+'_MISSING','Missing sample ID',sid)
    if backup.get('active_id') not in canonical:problem('ACTIVE_ID','Backup active_id is unknown')
    exported=parse_time(backup.get('exported_at',''))
    if not exported:problem('EXPORT_TIME','Backup exported_at is invalid')
    csv_by={r.get('sample_id'):r for r in rows};json_by={r.get('sample_id'):r for r in records if isinstance(r,dict)}
    comparisons=0;missing_evidence=collections.Counter();computed_status=collections.Counter()
    for sid,row in canonical.items():
        c=csv_by.get(sid);e=json_by.get(sid)
        if not c or not e:continue
        for k in ['region','year','month','dataset_id']:
            expected=data['id'] if k=='dataset_id' else str(row[k])
            if c.get(k)!=expected:problem('METADATA',k+' does not match canonical ID',sid)
        for k in ['longitude','latitude']:
            try:ok=math.isfinite(float(c.get(k,''))) and abs(float(c[k])-row[k])<1e-8
            except (ValueError,TypeError):ok=False
            if not ok:problem('COORDINATES',k+' does not match canonical ID',sid)
        for k in ENTRY_FIELDS:
            if k not in e:problem('JSON_FIELD','Missing backup field '+k,sid)
            elif k=='attested':
                if not isinstance(e[k],bool):problem('TYPE','attested must be boolean',sid)
            elif not isinstance(e[k],str):problem('TYPE',k+' must be text',sid)
        if e.get('label') not in LABELS:problem('LABEL','Unknown backup label',sid)
        if c.get('preliminary_review') not in LABELS:problem('LABEL','Unknown CSV label',sid)
        if any(not isinstance(e.get(k,''),str) for k in ENTRY_FIELDS if k!='attested'):continue
        errs=evidence_errors(e,row);s=status(e,row);computed_status[s]+=1
        if e.get('label') in ['0','1']:
            for field in ['reference_date','reference_source','evidence_id','reviewer']:
                if not e.get(field,'').strip():missing_evidence[field]+=1
        if e.get('attested') and errs:problem('INVALID_VERIFIED_DECLARATION','; '.join(errs),sid)
        expected={'reference_water':e['label'] if s=='VERIFIED' else '',
                  'reference_date':e.get('reference_date',''),'reference_source':neutral(e.get('reference_source','')),
                  'reference_quality':'' if s=='PENDING' else s,'notes':neutral(e.get('notes','')),
                  'preliminary_review':e.get('label',''),'evidence_id':neutral(e.get('evidence_id','')),
                  'reviewer':neutral(e.get('reviewer','')),'evidence_attested':'true' if s=='VERIFIED' else 'false',
                  'reviewed_at':e.get('updated_at',''),'uncertainty_reason':neutral(e.get('reason',''))}
        for k,value in expected.items():
            comparisons+=1
            if c.get(k)!=value:problem('CSV_JSON_MISMATCH',f'{k}: CSV/JSON differ',sid)
        if e.get('label')!='' or e.get('updated_at'):
            updated=parse_time(e.get('updated_at',''))
            if not updated:problem('REVIEW_TIME','Answered point has no valid reviewed timestamp',sid)
            elif exported and updated>exported:problem('REVIEW_AFTER_BACKUP','Answer timestamp is after backup export',sid)
    return {'status':'PASS' if not issues else 'FAIL','issues':issues,'expected_points':len(canonical),
            'csv_rows':len(rows),'json_rows':len(records),'field_comparisons':comparisons,
            'label_counts':dict(collections.Counter(r.get('preliminary_review','') for r in rows)),
            'status_counts':dict(computed_status),'missing_evidence_for_binary_answers':dict(missing_evidence),
            'csv_in_original_order':csv_ids==data['export_order'],
            'json_in_display_order':json_ids==[r['id'] for r in data['rows']],
            'independent_accuracy_ready':False,
            'readiness_reason':'Evidence and representativeness still require review; this checker never certifies image truth.'}


def optional_float(value):
    if value=='':return None
    result=float(value)
    if not math.isfinite(result):raise ValueError('Nonfinite benchmark number')
    return result


def cue_label(fraction,support):
    if fraction is None or support<.95:return None
    return 1 if fraction>=.8 else 0 if fraction<=.2 else None


def recompute_cue(row):
    o,r=row['optical_water_fraction'],row['radar_water_fraction'];os,rs=row['optical_supported_fraction'],row['radar_supported_fraction']
    for f in [o,r,os,rs]:
        if f is not None and not -1e-7<=f<=1+1e-7:raise ValueError('Benchmark fraction outside 0-1')
    if os is None or rs is None:raise ValueError('Observation support is missing')
    ol,rl=cue_label(o,os),cue_label(r,rs)
    if min(os,rs)<.95:s='INSUFFICIENT_PIXEL_SUPPORT'
    elif ol is None or rl is None:s='MIXED_PIXEL'
    elif ol!=rl:s='SENSOR_DISAGREEMENT'
    else:s='AUTOMATED_CONSENSUS'
    return {'optical_label':ol,'radar_label':rl,'consensus_label':ol if ol is not None and ol==rl else None,'status':s}


def load_cues(path,data):
    _,raw=csv_read(path);by_id={r['id']:r for r in data['rows']};out={};combos={(m,v) for m in [0.,.1,.2] for v in [-15.,-17.,-19.]}
    numeric=['optical_water_fraction','radar_water_fraction','optical_supported_fraction','radar_supported_fraction','optical_label','radar_label','consensus_label']
    for r in raw:
        sid=r['sample_id'];key=(float(r['mndwi_threshold']),float(r['vv_threshold_db']))
        if sid not in by_id or key not in combos or key in out.get(sid,{}):raise ValueError('Unknown/duplicate benchmark ID or threshold')
        row=by_id[sid]
        if r['region']!=row['region'] or int(r['year'])!=row['year'] or int(r['month'])!=row['month']:raise ValueError('Benchmark metadata mismatch')
        r={**r,**{k:optional_float(r[k]) for k in numeric}}
        for k,value in recompute_cue(r).items():
            if r[k]!=value:raise ValueError('Benchmark label/status disagrees with its fractions: '+sid+' '+k)
        out.setdefault(sid,{})[key]=r
    if set(out)!=set(by_id) or any(set(group)!=combos for group in out.values()):raise ValueError('Incomplete benchmark: all 9 thresholds for every real ID are required')
    return out


def compare_cues(data,rows,cues):
    by_id={r['sample_id']:r for r in rows};details=[]
    for index,row in enumerate(data['rows'],1):
        c=by_id[row['id']];label=c['preliminary_review'];primary=cues[row['id']][(.1,-17.)]
        if label=='':key='PENDING'
        elif label=='UNCERTAIN':key='HUMAN_UNCERTAIN'
        elif primary['status']!='AUTOMATED_CONSENSUS':key=primary['status']
        elif int(label)==primary['consensus_label']:key='CUE_AGREEMENT'
        else:key='CUE_CONFLICT'
        agree=oppose=ambiguous=0
        for cue in cues[row['id']].values():
            if label not in ['0','1'] or cue['status']!='AUTOMATED_CONSENSUS':ambiguous+=1
            elif int(label)==cue['consensus_label']:agree+=1
            else:oppose+=1
        details.append({'sample_id':row['id'],'viewer_number':index,'region':row['region'],'period':row['period'],
                        'human_label':label,'file_quality':c['reference_quality'],'check':key,
                        'check_bn':CHECK_NAMES[key],'primary_sensor_status':primary['status'],
                        'primary_optical_water_fraction':primary['optical_water_fraction'],'primary_radar_water_fraction':primary['radar_water_fraction'],
                        'optical_observed_fraction':primary['optical_supported_fraction'],'radar_observed_fraction':primary['radar_supported_fraction'],
                        'primary_two_sensor_cue':primary['consensus_label'] if primary['status']=='AUTOMATED_CONSENSUS' else None,
                        'threshold_agree_count':agree,'threshold_opposite_count':oppose,'threshold_ambiguous_count':ambiguous})
    return details


def raster_check(data,cues,details,mode,progress=print):
    if mode=='none':return {'status':'NOT_RUN','reason':'Existing whole-pixel numeric benchmark used; fresh raster windows not re-read.'}
    import contextlib
    import numpy as np
    import rasterio
    from rasterio.windows import Window
    from postprocessing.independent_sensor_check import read_patch,clipped_overlap_weights,consensus_record
    chosen={r['sample_id'] for r in details if mode=='all' or r['check']=='CUE_CONFLICT'}
    groups=collections.defaultdict(list)
    for row in data['rows']:
        if row['id'] in chosen:groups[(row['year'],row['month'])].append(row)
    fields=['optical_water_fraction','radar_water_fraction','optical_supported_fraction','radar_supported_fraction','optical_label','radar_label','consensus_label','status']
    mismatches=[];comparisons=0;rasters={}
    with rasterio.Env(GDAL_CACHEMAX=512*1024*1024):
        for (year,month),group in sorted(groups.items()):
            with contextlib.ExitStack() as stack:
                folder=ROOT/'NW_Bangladesh_independent_reference'
                s1paths=sorted(folder.glob(f'S1_reference_{year}_{month:02}*.tif'));s2paths=sorted(folder.glob(f'S2_reference_{year}_{month:02}*.tif'))
                if len(s1paths)!=1 or not s2paths:raise ValueError('Real raster evidence missing')
                s1=[stack.enter_context(rasterio.open(p)) for p in s1paths];s2=[stack.enter_context(rasterio.open(p)) for p in s2paths];base=s1[0].transform
                for ds in s1+s2:
                    if ds.crs.to_epsg()!=4326 or ds.count not in [4,8] or ds.nodata!=-9999:raise ValueError('Unexpected raster CRS/band/nodata metadata')
                    if not np.isclose(ds.transform.a,base.a) or not np.isclose(ds.transform.e,base.e):raise ValueError('Raster resolution mismatch')
                    for offset in [(ds.transform.c-base.c)/base.a,(ds.transform.f-base.f)/base.e]:
                        if abs(offset-round(offset))>1e-6:raise ValueError('Raster grid alignment mismatch')
                    rasters[str(Path(ds.name).relative_to(ROOT))]={'bytes':Path(ds.name).stat().st_size,'crs':str(ds.crs),'bands':ds.count,'nodata':ds.nodata,'transform':list(ds.transform)}
                for n,row in enumerate(group,1):
                    col,line=(~base)*(row['longitude'],row['latitude']);win=Window(int(np.floor(col))-16,int(np.floor(line))-16,32,32)
                    a1=read_patch(s1,base,win,4);a2=read_patch(s2,base,win,8);weights=clipped_overlap_weights(base,win,row['bounds'])
                    for (m,v),cached in cues[row['id']].items():
                        fresh=consensus_record(weights,a1,a2,m,v)
                        for field in fields:
                            comparisons+=1;a,b=fresh[field],cached[field]
                            if isinstance(a,(int,float)) and not math.isfinite(a):a=None
                            same=(a is None and b is None) or (isinstance(a,str) and a==b) or (isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isclose(a,b,abs_tol=1e-8,rel_tol=1e-7))
                            if not same:mismatches.append({'sample_id':row['id'],'threshold':[m,v],'field':field,'fresh':a,'cached':b})
                    if n%30==0 or n==len(group):progress(f'Raster windows {year}-{month:02}: {n}/{len(group)}')
    return {'status':'PASS' if not mismatches else 'FAIL','points_rechecked':len(chosen),'threshold_records_rechecked':len(chosen)*9,'field_comparisons':comparisons,'mismatches':mismatches,'raster_headers':rasters,
            'scope':'Fresh sampled raster windows and all nine existing thresholds; source helper reused; not independent validation or a full-raster checksum audit.'}


def write_csv(path,rows):
    if not rows:return
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def report_html(audit,details,data,raw_status):
    esc=lambda x:html.escape(str(x),quote=True)
    rows_by={r['id']:r for r in data['rows']};counts=collections.Counter(r['check'] for r in details)
    pct=lambda x:'তথ্য নেই' if x is None else f'{100*x:.1f}%'
    label=lambda x:{'1':'পানি আছে','0':'পানি নেই','UNCERTAIN':'অনিশ্চিত','':'উত্তর বাকি'}.get(str(x),'?')
    cards=[]
    for r in details:
        if r['check']!='CUE_CONFLICT':continue
        item=rows_by[r['sample_id']]
        cards.append(f'''<article class="suspect"><div><b>জায়গা {r['viewer_number']} · {esc(r['region'])} · {esc(r['period'])}</b><p class="mono">{esc(r['sample_id'])}</p><p>তোমার উত্তর: <b>{label(r['human_label'])}</b> · নির্ধারিত দুই sensor cue: <b>{label(str(int(r['primary_two_sensor_cue'])))}</b></p><p>MNDWI/NDWI নিয়মে পানির অংশ: {pct(r['primary_optical_water_fraction'])}<br>রাডার নিয়মে পানির অংশ: {pct(r['primary_radar_water_fraction'])}</p><p>৯টি threshold জোড়ার মধ্যে মিল {r['threshold_agree_count']}, বিপরীত {r['threshold_opposite_count']}, অস্পষ্ট {r['threshold_ambiguous_count']}।</p><p class="note">এটি আবার দেখার কারণ; তোমার উত্তর ভুল প্রমাণিত হয়নি। হলুদ ঘর ও স্বাধীন dated evidence দেখো।</p></div><img src="{item['image']}" alt="{esc(r['sample_id'])} চারটি সহায়ক মাসিক ছবি"></article>''')
    table=[]
    for r in sorted(details,key=lambda r:(PRIORITY[r['check']],r['viewer_number'])):
        table.append(f'''<tr data-check="{r['check']}" class="{r['check']}"><td>{r['viewer_number']}</td><td class="mono">{esc(r['sample_id'])}</td><td>{esc(r['region'])}<br>{esc(r['period'])}</td><td>{label(r['human_label'])}</td><td><span class="tag">{esc(r['check_bn'])}</span></td><td>{pct(r['primary_optical_water_fraction'])}</td><td>{pct(r['primary_radar_water_fraction'])}</td><td>{r['threshold_agree_count']} / {r['threshold_opposite_count']} / {r['threshold_ambiguous_count']}</td></tr>''')
    legend=''.join(f'<option value="{k}">{CHECK_NAMES[k]} ({counts[k]})</option>' for k in PRIORITY if counts[k])
    errors=''.join(f'<li>{esc(r["code"])} {esc(r["sample_id"])}: {esc(r["message"])}</li>' for r in audit['issues'])
    status_text='ফাইলের গঠন ও ID মিল ঠিক আছে' if audit['status']=='PASS' else 'ফাইলে সমস্যা আছে — নিচের তালিকা দেখো'
    stats=f'''<div class="stats"><div><b>{audit['csv_rows']}</b> মোট উত্তর</div><div><b>{counts['CUE_AGREEMENT']}</b> দুই cue-র সঙ্গে মিল</div><div><b>{counts['CUE_CONFLICT']}</b> দুই cue-র বিপরীত</div><div><b>{audit['status_counts'].get('VERIFIED',0)}</b> তারিখসহ VERIFIED</div></div>'''
    return f'''<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>লেবেল যাচাইয়ের ফল</title><style>
body{{font-family:'Nirmala UI','Segoe UI',sans-serif;background:#f4f7f5;color:#193b3a;margin:0;line-height:1.7}}main{{max-width:1180px;margin:auto;padding:26px}}h1{{font-size:25px;margin:0 0 8px}}h2{{font-size:19px;margin-top:27px}}.box,.suspect{{background:#fff;border:1px solid #d9e6df;border-radius:13px;padding:19px;margin:15px 0}}.status{{border-left:5px solid {'#187748' if audit['status']=='PASS' else '#a24024'}}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}}.stats div{{background:white;padding:16px;border:1px solid #dce6df;border-radius:10px;font-size:12px}}.stats b{{display:block;font-size:27px}}.suspect{{display:grid;grid-template-columns:1fr 420px;gap:20px;border-left:5px solid #ad4b30}}.suspect img{{width:100%;max-width:560px}}p{{margin:7px 0}}.mono{{font-family:Consolas,monospace;font-size:12px;overflow-wrap:anywhere}}.note{{font-size:12px;color:#74511b}}table{{width:100%;border-collapse:collapse;background:white;font-size:12px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e3ebe5;vertical-align:top}}th{{background:#eaf1ed;position:sticky;top:0}}.tablewrap{{overflow:auto;max-height:650px;border:1px solid #d9e6df;border-radius:10px}}.tag{{padding:4px 7px;border-radius:5px;display:inline-block}}.CUE_AGREEMENT .tag{{background:#dff2e6;color:#205e3c}}.CUE_CONFLICT .tag{{background:#fbe4de;color:#8a321e}}.MIXED_PIXEL .tag,.SENSOR_DISAGREEMENT .tag{{background:#fff0cc;color:#79500a}}.INSUFFICIENT_PIXEL_SUPPORT .tag,.HUMAN_UNCERTAIN .tag,.PENDING .tag{{background:#e9edf0;color:#495c69}}input,select{{font:inherit;padding:9px;border:1px solid #c7d8cf;border-radius:7px;background:white;margin:8px 5px 12px 0}}.hidden{{display:none}}details{{background:white;padding:12px 17px;border:1px solid #d9e6df;border-radius:10px}}summary{{cursor:pointer}}@media(max-width:760px){{main{{padding:14px}}.stats{{grid-template-columns:1fr 1fr}}.suspect{{grid-template-columns:1fr}}.suspect img{{max-width:100%}}}}
</style><main><h1>তোমার ৭২০টি উত্তরের যাচাই</h1><p>মূল CSV ও Backup অপরিবর্তিত। সব মিল sample_id দিয়ে করা হয়েছে।</p><section class="box status"><b>{status_text}</b><p>CSV/JSON field তুলনা: {audit['field_comparisons']} · raw raster cross-check: {esc(raw_status['status'])}</p><ul>{errors}</ul></section>{stats}
<section class="box"><b>রঙ কী বোঝায়?</b><p>সবুজ = তোমার উত্তরের সঙ্গে দুই সহায়ক cue মেলে। লাল = উল্টো ইঙ্গিত, আবার দেখার অগ্রাধিকার। হলুদ = মিশ্র বা দুই sensor-এর অমিল। ধূসর = অনিশ্চিত / পর্যবেক্ষণ কম।</p><p><b>সবুজ মানে সত্য প্রমাণিত নয়; লাল মানে ভুল প্রমাণিত নয়।</b> এগুলো একই মাসিক sensor evidence-এর সঙ্গে consistency check। নির্ভরযোগ্য স্বাধীন dated reference ছাড়া accuracy মাপা হয়নি।</p><p>Optical cue-তে MNDWI ≥ 0.1 এবং NDWI ≥ 0; radar cue-তে VV ≤ −17 dB। পুরো sampled pixel-এর পর্যবেক্ষিত অংশে পানির fraction ≥80% হলে water cue, ≤20% হলে nonwater cue; দুই sensor-এ ≥95% observation support লাগবে। অন্য ৮টি threshold জোড়া sensitivity check। RGB/infrared-এর রং আলাদাভাবে নির্ভুল truth classifier হিসেবে ব্যবহার করা হয়নি।</p></section>
<h2>প্রথমে এই {counts['CUE_CONFLICT']}টি জায়গা আবার দেখো</h2>{''.join(cards) or '<p>প্রধান দুই-cue নিয়মে নিশ্চিত বিপরীত পাওয়া যায়নি। এটি সব উত্তরের সত্যতার প্রমাণ নয়।</p>'}
<h2>সব জায়গার তালিকা</h2><p>মোট: {len(details)} · মিশ্র {counts['MIXED_PIXEL']} · sensor অমিল {counts['SENSOR_DISAGREEMENT']} · support কম {counts['INSUFFICIENT_PIXEL_SUPPORT']} · তোমার অনিশ্চিত {counts['HUMAN_UNCERTAIN']}।</p><input id="search" placeholder="ID / জেলা / মাস খোঁজো" aria-label="খুঁজুন"><select id="filter" aria-label="অবস্থা"><option value="">সব জায়গা</option>{legend}</select><div class="tablewrap"><table><thead><tr><th>পাতার নম্বর</th><th>ID</th><th>জেলা / মাস</th><th>তোমার উত্তর</th><th>সহায়ক পরীক্ষা</th><th>Optical water fraction</th><th>Radar water fraction</th><th>৯ জোড়ায় মিল / বিপরীত / অস্পষ্ট</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<details style="margin-top:20px"><summary>ব্যাখ্যা ও সীমা</summary><p>কোনো label সংশোধন বা VERIFIED করা হয়নি। মাসিক composite নির্দিষ্ট দিনের সত্য নয়। গাছ/ছায়া/মসৃণ জমি/ঢেউয়ে cue ভুল হতে পারে। Optical index-এর native SWIR support 20 m; 10 m display নতুন resolution তৈরি করে না। Raw re-read পুরোনো fixed algorithm-ই পুনরায় চালায়, স্বাধীন ground truth নয়। Threshold মিলের জন্য label বদলালে সেটি algorithm-guided revision হিসেবে নথিভুক্ত করো; স্বাধীন accuracy হিসেবে দাবি করো না। মূল snapshot-এর checksums JSON report-এ আছে।</p></details></main><script>function filter(){{const q=document.getElementById('search').value.toLowerCase(),s=document.getElementById('filter').value;document.querySelectorAll('tbody tr').forEach(r=>r.classList.toggle('hidden',(s&&r.dataset.check!==s)||!r.textContent.toLowerCase().includes(q)));}}document.getElementById('search').addEventListener('input',filter);document.getElementById('filter').addEventListener('change',filter);</script></html>'''


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv',type=Path,default=ROOT/'water_reference_labels_2026-10-15T09-00-32-461Z.csv')
    ap.add_argument('--backup',type=Path,default=ROOT/'water_review_backup_2026-10-15T09-00-37-140Z.json')
    ap.add_argument('--viewer',type=Path,default=ROOT/'Water_Review.html')
    ap.add_argument('--evidence',type=Path,default=EVIDENCE/'sentinel_threshold_evidence.csv')
    ap.add_argument('--raster-check',choices=['none','flagged','all'],default='all')
    ap.add_argument('--out',type=Path)
    ap.add_argument('--no-color',action='store_true')
    args=ap.parse_args(argv)
    try:
        sources=[args.csv,args.backup,args.viewer,args.viewer.with_suffix('.manifest.json'),args.evidence,Path(__file__),ROOT/'postprocessing/independent_sensor_check.py',ROOT/'dataset-download/download_independent_reference.js']
        before={str(p.resolve()):sha(p) for p in sources}
        headers,rows=csv_read(args.csv);backup=json_read(args.backup);data,viewer_manifest=read_viewer(args.viewer)
        audit=audit_pair(headers,rows,backup,data)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        out=(args.out or ROOT/'label_verification'/('check_'+stamp)).resolve()
        if out.exists():raise FileExistsError('Output folder already exists; choose a new folder')
        out.mkdir(parents=True)
        details=[];raw={'status':'NOT_RUN','reason':'File audit failed'}
        if audit['status']=='PASS':
            cues=load_cues(args.evidence,data);details=compare_cues(data,rows,cues)
            raw=raster_check(data,cues,details,args.raster_check,progress=lambda s:print(s,flush=True))
        after={p:sha(Path(p)) for p in before}
        if before!=after:raise ValueError('Input/source changed during verification')
        for row in data['rows']:
            if hashlib.sha256(base64.b64decode(row['image'].split(',',1)[1],validate=True)).hexdigest()!=row['image_sha256']:raise ValueError('Embedded chip checksum mismatch')
        counts=dict(collections.Counter(r['check'] for r in details))
        summary={'file_audit':audit,'color_cue_counts':counts,'raster_crosscheck':raw,'dataset_id':data['id'],
                 'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':before,'inputs_unchanged':True,
                 'labels_modified':False,'genuine_reference_labels_generated':False,'verified_accuracy_computed':False,
                 'limitations':['Color/sensor consistency is not independent accuracy.','Raw checks reuse the existing threshold method and do not establish truth.','Monthly composite timing, external evidence and representativeness need independent review.']}
        (out/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        write_csv(out/'all_label_checks.csv',details)
        if details:write_csv(out/'priority_recheck.csv',[r for r in details if r['check']=='CUE_CONFLICT'])
        (out/'report.html').write_text(report_html(audit,details,data,raw),encoding='utf-8')
        report_lines=[f"File audit: {audit['status']}",f"Answered: {sum(audit['label_counts'].get(k,0) for k in ['0','1','UNCERTAIN'])}/{len(data['rows'])}",f"Verified dated labels: {audit['status_counts'].get('VERIFIED',0)}",f"Color/sensor cue counts: {counts}",f"Raster cross-check: {raw['status']}","These checks do not establish scientific accuracy.",f"Report: {out/'report.html'}"]
        (out/'RESULT.txt').write_text('\n'.join(report_lines)+'\n',encoding='utf-8')
        color=not args.no_color and sys.stdout.isatty()
        for line in report_lines:
            code='31' if 'FAIL' in line else '33' if 'Verified dated labels: 0' in line or 'not establish' in line else '32'
            print(f'\033[{code}m{line}\033[0m' if color else line)
        return 0 if audit['status']=='PASS' and raw['status']!='FAIL' else 2
    except Exception as e:
        print('VERIFICATION FAILED: '+str(e),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
