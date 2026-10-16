"""Render downloaded actual-date evidence, preserving uncertainty and labels."""
from __future__ import annotations
import base64, csv, html, json, re, sys
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Polygon as PlotPolygon
from PIL import Image, ImageDraw

from dated_reference_pilot import OUT, ROOT, BANDS, frozen_plan, target_polygon, overlap_weights, sha, dump, now

SCL_COLORS = ['#000000','#ff0000','#2f2f2f','#643200','#00a000','#ffe65a',
              '#0000ff','#808080','#c0c0c0','#ffffff','#64c8ff','#ff96ff']


def read_band(path, asset):
    with rasterio.open(path) as ds:
        raw=ds.read(1)
        info={'crs':ds.crs,'transform':ds.transform,'shape':raw.shape,
              'extent':[ds.bounds.left,ds.bounds.right,ds.bounds.bottom,ds.bounds.top],
              'weights':None}
        valid=raw!=ds.nodata if ds.nodata is not None else np.ones(raw.shape,dtype=bool)
    a=raw.astype('float32')*asset['scale']+asset['offset']
    a[~valid]=np.nan
    return a,info


def resample(a,src,dst,method=Resampling.average):
    result=np.full(dst['shape'],np.nan,dtype='float32')
    reproject(a,result,src_transform=src['transform'],src_crs=src['crs'],
              dst_transform=dst['transform'],dst_crs=dst['crs'],
              src_nodata=np.nan,dst_nodata=np.nan,resampling=method)
    return result


def scene_image(p,directory):
    record=json.loads((directory/'retrieval.json').read_text(encoding='utf-8'))
    values={}; infos={}
    for asset in record['assets']:
        path=directory/asset['local_path']
        if sha(path)!=asset['sha256']: raise ValueError('Cutout checksum mismatch')
        values[asset['band']],infos[asset['band']]=read_band(path,asset)
    for band in ('green','red','nir'):
        if infos[band]['transform']!=infos['blue']['transform'] or infos[band]['shape']!=infos['blue']['shape']:
            raise ValueError('10m band alignment mismatch')
    if infos['scl']['transform']!=infos['swir16']['transform'] or infos['scl']['shape']!=infos['swir16']['shape']:
        raise ValueError('20m SCL/SWIR alignment mismatch')
    green20=resample(values['green'],infos['green'],infos['swir16'])
    swir=values['swir16']; scl=values['scl']
    clear=np.isin(scl,[4,5,6])
    valid=clear & np.isfinite(green20) & np.isfinite(swir) & (green20>=0) & (swir>=0) & ((green20+swir)>1e-6)
    mndwi=np.full(swir.shape,np.nan,dtype='float32')
    mndwi[valid]=(green20[valid]-swir[valid])/(green20[valid]+swir[valid])
    polygon=target_polygon(p,infos['blue']['crs'])
    with rasterio.open(directory/'scl.tif') as ds:
        weights=overlap_weights(ds,polygon)
    support=float(weights[valid].sum()/polygon.area)
    def area_stat(mask): return float(weights[mask].sum()/polygon.area)
    stats={
        'number':p['number'],'sample_id':p['id'],'period':p['period'],
        'item_id':record['item_id'],'collection':record['collection'],
        'acquisition_datetime':record['acquisition_datetime'],
        'clear_SCL_area_fraction':area_stat(clear),'valid_MNDWI_area_fraction':support,
        'mndwi_min':float(mndwi[(weights>0)&valid].min()) if np.any((weights>0)&valid) else None,
        'mndwi_max':float(mndwi[(weights>0)&valid].max()) if np.any((weights>0)&valid) else None,
        'mndwi_positive_area_fraction_of_original_pixel':area_stat(valid&(mndwi>=0)),
        'quality_assessment':'ALGORITHMIC_CLEAR_CUE_ONLY' if support>=.95 else 'INCOMPLETE_OR_AMBIGUOUS_PIXEL_SUPPORT',
        'reference_quality':'NOT_ATTESTED','reference_water':None,
        'evidence_png':str((directory/'dated_evidence.png').relative_to(OUT)).replace('\\','/'),
    }
    rgb=np.stack([values[b] for b in ('red','green','blue')],axis=-1)
    nir=np.stack([values[b] for b in ('nir','red','green')],axis=-1)
    rgb=np.where(np.isfinite(rgb),np.clip(rgb/.30,0,1),1)
    nir=np.where(np.isfinite(nir),np.clip(nir/.45,0,1),1)
    x,y=Transformer.from_crs(4326,infos['blue']['crs'],always_xy=True).transform(p['longitude'],p['latitude'])
    fig,axes=plt.subplots(2,2,figsize=(8.4,8.8),layout='constrained')
    axes[0,0].imshow(rgb,extent=infos['blue']['extent'],interpolation='nearest',origin='upper')
    axes[0,0].set_title('Natural color (10 m)')
    axes[0,1].imshow(nir,extent=infos['nir']['extent'],interpolation='nearest',origin='upper')
    axes[0,1].set_title('Infrared: NIR / red / green (10 m)')
    cmap=plt.get_cmap('RdBu').copy(); cmap.set_bad('#a8a8a8')
    im=axes[1,0].imshow(np.ma.masked_invalid(mndwi),extent=infos['swir16']['extent'],interpolation='nearest',origin='upper',cmap=cmap,vmin=-1,vmax=1)
    axes[1,0].set_title('MNDWI (20 m): grey missing; white near 0')
    fig.colorbar(im,ax=axes[1,0],shrink=.65,ticks=[-1,0,1])
    axes[1,1].imshow(scl,extent=infos['scl']['extent'],interpolation='nearest',origin='upper',cmap=ListedColormap(SCL_COLORS),norm=BoundaryNorm(np.arange(-.5,12.5),12))
    axes[1,1].set_title('SCL quality cue (20 m), NOT reference truth')
    for ax in axes.ravel():
        ax.add_patch(PlotPolygon(np.array(polygon.exterior.coords),closed=True,fill=False,edgecolor='black',linewidth=3.5))
        ax.add_patch(PlotPolygon(np.array(polygon.exterior.coords),closed=True,fill=False,edgecolor='#ffcc00',linewidth=1.7))
        ax.set_xlim(x-100,x+100); ax.set_ylim(y-100,y+100)
        ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"Point {p['number']} | {p['region']} | {record['acquisition_datetime'][:10]} UTC\nYellow outline = entire original pixel; view width 200 m; north up",fontsize=11)
    fig.supxlabel(f"SCL clear cue {stats['clear_SCL_area_fraction']:.0%} | valid index support {support:.0%}\nContains modified Copernicus Sentinel data {p['year']}. AI evidence review; no human attestation.",fontsize=9)
    fig.savefig(directory/'dated_evidence.png',dpi=140)
    plt.close(fig)
    dump(directory/'display_and_quality.json',stats)
    return stats


def make_contact_sheet(p,stats):
    """Three selected dates, actual figures reduced without adding detail."""
    thumbs=[]
    for s in stats:
        image=Image.open(OUT/s['evidence_png']).convert('RGB')
        image.thumbnail((588,616),Image.Resampling.LANCZOS)
        thumbs.append(image)
    sheet=Image.new('RGB',(588*len(thumbs),640),'#ffffff')
    for i,im in enumerate(thumbs):sheet.paste(im,(i*588,0))
    path=OUT/f"point_{p['number']:03d}"/'contact_sheet.png'
    sheet.save(path)


def build_report(plan,stats):
    findings_path=OUT/'ai_visual_review.json'
    findings=json.loads(findings_path.read_text(encoding='utf-8')) if findings_path.exists() else {}
    cards=[]
    for p in plan['points']:
        rows=sorted([s for s in stats if s['number']==p['number']],key=lambda s:s['acquisition_datetime'])
        finding=findings.get(str(p['number']),{})
        tiles=[]
        for s in rows:
            png=OUT/s['evidence_png']
            uri='data:image/png;base64,'+base64.b64encode(png.read_bytes()).decode('ascii')
            quality='ছবি দেখো' if s['clear_SCL_area_fraction']>=.95 else 'ছবির মান নিয়ে অনিশ্চয়তা আছে'
            tiles.append(f'<details><summary>{s["acquisition_datetime"][:10]} — {quality}</summary><img loading="lazy" src="{uri}" alt="Point {p["number"]} on {s["acquisition_datetime"][:10]}"><p><code>{html.escape(s["item_id"])}</code></p><a href="{s["evidence_png"]}" target="_blank">বড় করে ছবি খোলো</a></details>')
        assessment=html.escape(finding.get('explanation_bn','ছবি সংগ্রহ হয়েছে; visual review এখনও লেখা হয়নি।'))
        cards.append(f'<section id="point{p["number"]}"><h2>ছবি {p["number"]} · {html.escape(p["region"])} · {p["period"]}</h2><p class="assessment">{assessment}</p><p>স্থান: {p["latitude"]:.7f}, {p["longitude"]:.7f} · <code>{p["id"]}</code></p>{"".join(tiles)}</section>')
    total=len(stats)
    page='''<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>তারিখসহ ৫টি জায়গার যাচাই</title><style>body{font-family:system-ui,"Nirmala UI",sans-serif;background:#f2f5f9;color:#172b42;margin:0;line-height:1.8}main{max-width:1050px;margin:auto;padding:24px}section,.intro{padding:22px;background:white;border-radius:16px;margin:18px 0;border:1px solid #dce5ef}h1{font-size:28px}h2{font-size:22px}.note{background:#fff3d8;padding:14px;border-radius:12px}.assessment{font-weight:600;color:#185e70}summary{cursor:pointer;padding:13px;font-weight:600;background:#eaf2fa;border-radius:8px;margin:8px 0}img{display:block;max-width:100%;height:auto;margin:auto}code{overflow-wrap:anywhere;font-size:12px}a{color:#145caa}nav a{margin-right:18px;display:inline-block}</style><main><h1>আসল তারিখের ছবি: ৫টি জায়গার ছোট যাচাই</h1><div class="intro"><p>মোট SCENE_COUNTটি দিনের ছবি-জায়গা জোড়া দেখানো হয়েছে। এগুলো এক দিনের satellite acquisition; মাসের composite নয়। হলুদ সীমানার পুরো জায়গাটি দেখো। একই জায়গায় মাসের শুরুর, মাঝের ও শেষের একটি করে ছবি আছে।</p><p class="note"><b>স্বাধীন accuracy এখনও সম্পন্ন হয়নি।</b> এটি AI-এর সাহায্যে dated evidence review। Sentinel-2 ছবিই আগের composite-এ ছিল; নতুন এই source থেকে শুধু ছবি পেলেই আগের review স্বাধীন বা blind হয়ে যায় না। মানুষের VERIFIED ঘোষণা বা accuracy সংখ্যা তৈরি করা হয়নি। ৫টি জায়গা দিয়ে ৭২০টির ফল বলা যাবে না।</p><p>RGB/Infrared মূলত ১০ মিটার; MNDWI/SCL ২০ মিটার। বড় করে দেখালেও নতুন সূক্ষ্ম তথ্য তৈরি হয় না। SCL একটি automated cue; নীল রং নিজে ground truth নয়। মেঘ বা missing থাকলে পানি নেই বলা যাবে না। মাত্র তিন দিন দেখে মাঝের সব দিনের অবস্থা জানা যায় না।</p><nav>NAVIGATION</nav></div>CARDS<section><h2>পদ্ধতি ও উৎস</h2><p>কোনো পুরোনো label বদলানো হয়নি। প্রতিটি ছবির scene ID, আসল UTC acquisition date, native-grid cutout, calibration, mask, SHA-256 এবং search response এই folder-এ আছে। বিস্তারিত: <a href="pilot_plan.json">স্থির point plan</a>, <a href="pilot_retrieval_schedule.json">দিন বাছাইয়ের নিয়ম</a>, <a href="dated_scene_evidence.csv">ছবির তালিকা</a>, <a href="sources.jsonl">উৎসের খাতা</a>।</p><p>API: <a href="https://github.com/Element84/earth-search">Element 84 Earth Search</a>। <a href="https://github.com/Element84/earth-search/blob/main/docs/collections/sentinel-2-l2a.md">Collection/version তথ্য</a>। <a href="https://custom-scripts.sentinel-hub.com/sentinel-2/scene-classification/">SCL-এর রঙ</a>। <a href="https://cds.climate.copernicus.eu/licences/ec-sentinel">Copernicus Sentinel data licence</a>।</p><p>Contains modified Copernicus Sentinel data 2018, 2020, 2023, 2024.</p></section></main></html>'''
    page=page.replace('SCENE_COUNT',str(total)).replace('NAVIGATION',''.join(f'<a href="#point{p["number"]}">{p["number"]} নং</a>' for p in plan['points'])).replace('CARDS',''.join(cards))
    (OUT/'report.html').write_text(page,encoding='utf-8')
    relative=str(OUT.relative_to(ROOT)).replace('\\','/')+'/'
    root_page=re.sub(r'href="(?!https?:|#)([^"]+)"',lambda m:'href="'+relative+m.group(1)+'"',page)
    (ROOT/'Water_Dated_5_Point_Review.html').write_text(root_page,encoding='utf-8')


def main():
    plan=frozen_plan()
    findings_path=OUT/'ai_visual_review.json'
    if findings_path.exists():
        findings=json.loads(findings_path.read_text(encoding='utf-8'))
        explanations=json.loads((ROOT/'postprocessing'/'dated_pilot_explanations_bn.json').read_text(encoding='utf-8'))
        for key,value in findings.items():
            value['explanation_bn']=explanations[key]
        dump(findings_path,findings)
        fields=['number','sample_id','status','tentative_image_interpretation','reference_water','reference_quality','human_attestation','accuracy_eligible','reviewer','reviewed_at','explanation_bn','reason']
        with (OUT/'ai_pilot_interpretations.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(findings.values())
    schedule=json.loads((OUT/'pilot_retrieval_schedule.json').read_text(encoding='utf-8'))['selected']
    stats=[]
    for p in plan['points']:
        point_stats=[]
        for s in schedule:
            if s['number']!=p['number']:continue
            directory=OUT/f"point_{p['number']:03d}"/s['item_id']
            if not (directory/'retrieval.json').exists():raise ValueError('Scheduled acquisition has not downloaded completely: '+s['item_id'])
            stat=scene_image(p,directory)
            point_stats.append(stat);stats.append(stat)
        make_contact_sheet(p,sorted(point_stats,key=lambda s:s['acquisition_datetime']))
    fields=list(stats[0])
    with (OUT/'dated_scene_evidence.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(stats)
    dump(OUT/'dated_scene_evidence.json',stats)
    build_report(plan,stats)
    print('Rendered',len(stats),'actual-dated point-scene pairs. Human verified labels generated: 0.')


if __name__=='__main__':main()
