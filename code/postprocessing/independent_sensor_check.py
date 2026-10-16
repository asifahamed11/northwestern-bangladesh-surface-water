"""Independent Sentinel comparison and blinded image review kit.

Fixed threshold sensitivity is a sensor-agreement benchmark, NOT ground truth.
Never writes validation/reference_labels.csv or claims human verification.
"""
from pathlib import Path
import sys,argparse,json,contextlib,hashlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research_pipeline.common import require,write_json

def clipped_overlap_weights(transform,window,bounds):
    left,bottom,right,top=bounds
    cols=np.arange(int(window.col_off),int(window.col_off+window.width))
    rows=np.arange(int(window.row_off),int(window.row_off+window.height))
    x0=transform.c+cols*transform.a; x1=x0+transform.a
    y1=transform.f+rows*transform.e; y0=y1+transform.e
    xl=np.maximum(x0,left); xr=np.maximum(xl,np.minimum(x1,right))
    yl=np.maximum(y0,bottom); yr=np.maximum(yl,np.minimum(y1,top))
    project=Transformer.from_crs(4326,6933,always_xy=True)
    px0,_=project.transform(xl,np.full(len(cols),bottom)); px1,_=project.transform(xr,np.full(len(cols),bottom))
    _,py0=project.transform(np.full(len(rows),left),yl); _,py1=project.transform(np.full(len(rows),left),yr)
    return abs(py1-py0)[:,None]*abs(px1-px0)[None,:]/1e6

def read_patch(datasets,base,window,count):
    values=np.full((count,int(window.height),int(window.width)),np.nan,dtype='float32')
    for ds in datasets:
        c=int(round((ds.transform.c-base.c)/base.a)); r=int(round((ds.transform.f-base.f)/base.e))
        left=max(c,int(window.col_off)); top=max(r,int(window.row_off))
        right=min(c+ds.width,int(window.col_off+window.width)); bottom=min(r+ds.height,int(window.row_off+window.height))
        if left>=right or top>=bottom: continue
        a=ds.read(window=Window(left-c,top-r,right-left,bottom-top)).astype('float32')
        a[(a==ds.nodata)|~np.isfinite(a)]=np.nan
        dest_r=top-int(window.row_off); dest_c=left-int(window.col_off)
        values[:,dest_r:dest_r+a.shape[1],dest_c:dest_c+a.shape[2]]=a
    return values

def threshold_label(water_fraction,support_fraction,minimum=.95):
    if not np.isfinite(water_fraction) or support_fraction<minimum: return None
    if water_fraction>=.8: return 1
    if water_fraction<=.2: return 0
    return None

def consensus_record(weights,s1,s2,mndwi_threshold,vv_threshold):
    total=weights.sum(); require(total>0,'Empty JRC pixel footprint')
    optical=np.isfinite(s2[5])&np.isfinite(s2[6])&np.isfinite(s2[7])&(s2[7]>=2)
    radar=np.isfinite(s1[0])&np.isfinite(s1[3])&(s1[3]>=2)
    o_area=weights[optical].sum(); r_area=weights[radar].sum()
    o_water=optical&(s2[6]>=mndwi_threshold)&(s2[5]>=0)
    r_water=radar&(s1[0]<=vv_threshold)
    of=float(weights[o_water].sum()/o_area) if o_area else np.nan
    rf=float(weights[r_water].sum()/r_area) if r_area else np.nan
    os=float(o_area/total); rs=float(r_area/total)
    ol=threshold_label(of,os); rl=threshold_label(rf,rs)
    same=ol is not None and rl is not None and ol==rl
    if min(os,rs)<.95: reason='INSUFFICIENT_PIXEL_SUPPORT'
    elif ol is None or rl is None: reason='MIXED_PIXEL'
    elif ol!=rl: reason='SENSOR_DISAGREEMENT'
    else: reason='AUTOMATED_CONSENSUS'
    return {'optical_water_fraction':of,'radar_water_fraction':rf,
        'optical_supported_fraction':os,'radar_supported_fraction':rs,
        'optical_label':ol,'radar_label':rl,'consensus_label':ol if same else None,'status':reason}

def chip_image(path,s1,s2,transform,window,bounds,record):
    rgb=np.moveaxis(s2[[2,1,0]],0,2); false=np.moveaxis(s2[[3,2,1]],0,2)
    rgb=np.clip(rgb/.30,0,1); false=np.clip(false/.45,0,1)
    # White marks absent image support; it is never an inferred land/water label.
    rgb=np.where(np.isfinite(rgb),rgb,1); false=np.where(np.isfinite(false),false,1)
    fig,axes=plt.subplots(2,2,figsize=(5.6,5.6),constrained_layout=True)
    axes[0,0].imshow(rgb,interpolation='nearest'); axes[0,0].set_title('Sentinel-2 natural color',fontsize=9)
    axes[0,1].imshow(false,interpolation='nearest'); axes[0,1].set_title('Sentinel-2 infrared color',fontsize=9)
    axes[1,0].imshow(np.ma.masked_invalid(s2[6]),cmap='RdBu',vmin=-1,vmax=1,interpolation='nearest');axes[1,0].set_title('MNDWI: red low / blue high',fontsize=9)
    axes[1,1].imshow(np.ma.masked_invalid(s1[0]),cmap='gray',vmin=-25,vmax=0,interpolation='nearest');axes[1,1].set_title('Sentinel-1 VV: dark low',fontsize=9)
    left,bottom,right,top=bounds
    c0,r0=(~transform)*(left,top); c1,r1=(~transform)*(right,bottom)
    for ax in axes.ravel():
        ax.add_patch(Rectangle((c0-window.col_off-.5,r0-window.row_off-.5),c1-c0,r1-r0,fill=False,edgecolor='#ffcc00',linewidth=1.6))
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f'{record.sample_id}\n{record.year}-{record.month:02} monthly composites; yellow = original pixel',fontsize=9)
    fig.savefig(path,dpi=100); plt.close(fig)

def viewer(out,records):
    data=[{'id':r.sample_id,'period':f'{r.year}-{r.month:02}','region':r.region} for r in records]
    payload=json.dumps(data)
    page=r'''<!doctype html><html lang="bn"><meta charset="utf-8"><title>Blinded satellite review</title>
<style>body{font-family:system-ui;margin:24px;background:#f4f6fa;color:#18253d}main{max-width:1050px;margin:auto}button,select,input{padding:8px;font-size:16px;margin:3px}img{width:min(560px,100%);background:white}p{line-height:1.7}.panel{background:white;padding:16px;border-radius:12px}.warn{color:#8b3a00}textarea{width:95%;height:60px}label{display:block;margin-top:12px}</style>
<main><h1>পানি আছে কি না: ছবি দেখার পাতা</h1><p>হলুদ বাক্সটিই যাচাইয়ের জায়গা। ছবিগুলো মাসের composite; একটি নির্দিষ্ট দিনের ছবি নয়। JRC-এর class দেখানো হয়নি।</p>
<p class="warn">এটি review সাহায্য। শুধু এই পাতা দেখে ground truth বা একটি acquisition date ধরে নেবেন না। যাচাই করা dated evidence ছাড়া VERIFIED label দেবেন না।</p>
<button onclick="go(-1)">আগের</button><button onclick="go(1)">পরের</button><select id="pick" onchange="show(this.selectedIndex)"></select><button onclick="download()">নিজের notes CSV</button>
<div class="panel"><h2 id="title"></h2><img id="image"><label>Preliminary interpretation <select id="label" onchange="save()"><option value="">এখনও দেখা হয়নি</option><option value="1">পানি</option><option value="0">পানি নেই</option><option value="UNCERTAIN">অনিশ্চিত / মিশ্র</option></select></label><label>Notes<textarea id="notes" oninput="save()"></textarea></label></div>
<p>এই browser-এর notes localStorage-তে থাকে। CSV export-এ preliminary_review লেখা হবে; independent verified labels হিসেবে স্বয়ংক্রিয়ভাবে ব্যবহার হবে না।</p></main>
<script>const rows=PAYLOAD;let pos=0;let notes={};try{notes=JSON.parse(localStorage.getItem('nw-blind-review')||'{}')}catch(e){};
const pick=document.getElementById('pick');rows.forEach(r=>{let o=document.createElement('option');o.textContent=r.id+' '+r.period;pick.append(o)});
function show(i){pos=Math.max(0,Math.min(rows.length-1,i));let r=rows[pos],n=notes[r.id]||{};pick.selectedIndex=pos;document.getElementById('title').textContent=(pos+1)+' / '+rows.length+' — '+r.region+' '+r.period;document.getElementById('image').src='chips/'+r.id+'.png';document.getElementById('label').value=n.label||'';document.getElementById('notes').value=n.notes||''}
function go(n){show(pos+n)}function save(){notes[rows[pos].id]={label:document.getElementById('label').value,notes:document.getElementById('notes').value};localStorage.setItem('nw-blind-review',JSON.stringify(notes))}
function csv(v){return '"'+String(v||'').replaceAll('"','""')+'"'}function download(){let lines=['sample_id,period,preliminary_review,notes'];rows.forEach(r=>{let n=notes[r.id]||{};lines.push([r.id,r.period,n.label,n.notes].map(csv).join(','))});let a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'}));a.download='preliminary_review_notes.csv';a.click();URL.revokeObjectURL(a.href)}show(0);</script></html>'''.replace('PAYLOAD',payload)
    (out/'review.html').write_text(page,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);parser.add_argument('--no-chips',action='store_true');args=parser.parse_args()
    run=args.run.resolve();out=run/'independent_sensor_evidence';require(not out.exists(),'Evidence folder exists; do not overwrite it');out.mkdir();(out/'chips').mkdir()
    blind=pd.read_csv(run/'reference_labels_to_complete.csv')
    # Shuffle the originally stratified row order; predictions remain hidden during extraction.
    blind=blind.sample(frac=1,random_state=20261013).reset_index(drop=True)
    folder=ROOT/'NW_Bangladesh_independent_reference'; rows=[]; records=[]; source_files=[]
    with rasterio.Env(GDAL_CACHEMAX=512*1024*1024),rasterio.open(ROOT/'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif') as jrc:
        for (year,month),group in blind.groupby(['year','month'],sort=True):
            with contextlib.ExitStack() as stack:
                s1paths=sorted(folder.glob(f'S1_reference_{year}_{month:02}*.tif'));s2paths=sorted(folder.glob(f'S2_reference_{year}_{month:02}*.tif'))
                source_files.extend([str(p.relative_to(ROOT)) for p in s1paths+s2paths])
                s1=[stack.enter_context(rasterio.open(p)) for p in s1paths];s2=[stack.enter_context(rasterio.open(p)) for p in s2paths]
                require(len(s1)==1 and len(s2)>0,'Reference tiles missing');base=s1[0].transform
                for n,record in enumerate(group.itertuples()):
                    jr,jc=jrc.index(record.longitude,record.latitude);left,top=jrc.transform*(jc,jr);right,bottom=jrc.transform*(jc+1,jr+1)
                    col,row=(~base)*(record.longitude,record.latitude);win=Window(int(np.floor(col))-16,int(np.floor(row))-16,32,32)
                    a1=read_patch(s1,base,win,4);a2=read_patch(s2,base,win,8);bounds=(left,bottom,right,top)
                    weights=clipped_overlap_weights(base,win,bounds)
                    for optical in [0.,.1,.2]:
                        for radar in [-15.,-17.,-19.]:
                            rows.append({'sample_id':record.sample_id,'region':record.region,'year':year,'month':month,
                                'mndwi_threshold':optical,'vv_threshold_db':radar,**consensus_record(weights,a1,a2,optical,radar)})
                    records.append(record)
                    if not args.no_chips: chip_image(out/'chips'/(record.sample_id+'.png'),a1,a2,base,win,bounds,record)
                    if (n+1)%30==0: print('Independent image review kit:',year,month,n+1,'/',len(group),flush=True)
    result=pd.DataFrame(rows);result.to_csv(out/'sentinel_threshold_evidence.csv',index=False)
    # JRC is joined only after all independent evidence/threshold outputs have been frozen.
    predictions=pd.read_csv(run/'validation_predictions_private.csv')
    merged=result.merge(predictions[['sample_id','predicted_water','stratum','population_pixels','planned_samples','pixel_area_km2']],on='sample_id',validate='many_to_one')
    merged['sample_design_weight_km2']=merged.population_pixels/merged.planned_samples*merged.pixel_area_km2
    summaries=[]
    for (o,r),frame in merged.groupby(['mndwi_threshold','vv_threshold_db']):
        consensus=frame[frame.consensus_label.notna()];agree=consensus.consensus_label==consensus.predicted_water
        denominator=consensus.sample_design_weight_km2.sum()
        summaries.append({'mndwi_threshold':o,'vv_threshold_db':r,'sample_count':len(frame),
            'consensus_samples':len(consensus),'mixed_or_disagreement_samples':len(frame)-len(consensus),
            'consensus_design_weight_coverage_pct':100*denominator/frame.sample_design_weight_km2.sum(),
            'conditional_area_weighted_jrc_agreement_pct':100*consensus.loc[agree,'sample_design_weight_km2'].sum()/denominator if denominator else np.nan,
            'interpretation':'AUTOMATED SENSOR AGREEMENT ONLY; NOT CLASSIFICATION ACCURACY'})
    summary=pd.DataFrame(summaries);summary.to_csv(out/'cross_sensor_agreement_sensitivity.csv',index=False)
    primary=merged[(merged.mndwi_threshold==.1)&(merged.vv_threshold_db==-17)]
    primary.to_csv(out/'primary_sensor_comparison.csv',index=False)
    strat=[]
    for key,f in primary.groupby(['region','year','month','predicted_water']):
        accepted=f[f.consensus_label.notna()]
        strat.append({'region':key[0],'year':key[1],'month':key[2],'jrc_predicted_water':key[3],
            'planned':len(f),'consensus_samples':len(accepted),
            'agreeing_samples':int((accepted.consensus_label==accepted.predicted_water).sum())})
    pd.DataFrame(strat).to_csv(out/'consensus_stratum_counts.csv',index=False)
    if not args.no_chips: viewer(out,records)
    pd.read_csv(run/'reference_labels_to_complete.csv').to_csv(out/'reference_labels_still_unverified.csv',index=False)
    audits=[p for p in (ROOT/'dataset-audit').glob('remaining_downloads_*/downloaded_file_manifest.csv')
            if json.loads((p.parent/'summary.json').read_text())['status']=='PASS']
    require(audits,'Run the remaining-download audit before making independent sensor reports')
    audit_path=max(audits,key=lambda p:p.stat().st_mtime_ns)
    source_manifest=pd.read_csv(audit_path);source_manifest=source_manifest[source_manifest.folder=='NW_Bangladesh_independent_reference']
    source_manifest.to_csv(out/'reference_source_hash_manifest.csv',index=False)
    settings={'method':'Prespecified two-sensor whole-JRC-pixel threshold agreement','mndwi_thresholds':[0,.1,.2],
        'vv_thresholds_db':[-15,-17,-19],'primary_mndwi':.1,'primary_vv_db':-17,'minimum_scene_count':2,
        'minimum_area_support':.95,'water_fraction_cutoff':.8,'nonwater_fraction_cutoff':.2,
        'ground_truth_generated':False,'human_verification_completed':False,'source_files':sorted(set(source_files)),
        'primary_status_counts':primary.status.value_counts().to_dict(),
        'limits':['Monthly medians cannot establish individual acquisition dates or brief within-month inundation.',
          'Export grid spacing is 10 m; SWIR originally has 20 m support. Pixel footprints remain mixed at edges.',
          'Fixed thresholds are not locally trained/validated. Consensus subset excludes ambiguous cases and is selection-biased.',
          'Do not report conditional agreement as independent accuracy or fill verified label/date fields automatically.'],
        'references':['https://www.mdpi.com/2072-4292/12/10/1614','https://pmc.ncbi.nlm.nih.gov/articles/PMC6015492/',
                      'https://www.mdpi.com/2072-4292/14/22/5721']}
    write_json(out/'method_and_status.json',settings)
    print(summary.to_string(index=False));print('Evidence and blinded review:',out)

if __name__=='__main__': main()
