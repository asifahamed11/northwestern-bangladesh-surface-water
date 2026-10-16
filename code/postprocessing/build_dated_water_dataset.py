"""Render measured MNDWI and prepare separate per-acquisition review metadata.

Only local frozen Sentinel data are used. Old displays, labels, thresholds and
scientific results are preserved. The palette is a display aid, not truth.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter
import hashlib,json
import numpy as np
import rasterio
from PIL import Image,ImageDraw
from screen_water_colors import ROOT,SOURCE,OUT as PARENT,BANDS,normalized,digest,footprint,write_json,now

OUT=PARENT/'date_review_v2'
SCHEMA='nw-assisted-dated-review-v2'
PALETTE={'index':'(B03-B11)/(B03+B11), product-calibrated reflectance',
    'positions':[-1,-.3,-.03,.03,.3,1],
    'colors':[[172,45,32],[238,144,74],[250,250,245],[250,250,245],[116,183,234],[15,66,160]],
    'invalid_color':[145,145,145],
    'index_validity':'Accepted source quality, finite positive denominator, green/SWIR reflectance between 0 and 1.2. Other ratio support is conservatively grey, not water or dry land.',
    'interpretation':'Blue positive water-like signal; orange/red negative land-like signal; white weak/near zero; grey masked/unsupported. No color guarantees water or nonwater.'}


def color_mndwi(index,valid):
    a=np.where(np.isfinite(index),np.clip(index,-1,1),0)
    rgb=np.stack([np.interp(a,PALETTE['positions'],np.array(PALETTE['colors'])[:,k]) for k in range(3)],axis=-1).astype('uint8')
    rgb[~valid]=PALETTE['invalid_color'];return rgb


def render(point,scene,cal):
    item=scene['item_id'];rec=json.loads((SOURCE/'evidence'/point['sample_id']/(item+'.json')).read_text(encoding='utf-8'))
    if digest(SOURCE/rec['tiff_path'])!=rec['tiff_sha256']:raise ValueError('Frozen real raster changed')
    with rasterio.open(SOURCE/rec['tiff_path']) as ds:
        assert ds.count==7 and ds.shape==(40,40) and str(ds.crs)==rec['crs']
        raw=ds.read();transform=ds.transform
    value={}
    for i,band in enumerate(BANDS[:-1]):
        co=cal['band_coefficients'][band];a=raw[i].astype('float64')*co['scale']+co['offset']
        a[(raw[i]==0)|(raw[6]==0)]=np.nan;value[band]=a
    clear=np.isin(raw[5],[4,5,6])&(raw[6]>0)&np.all(raw[:5]>0,axis=0)
    index=normalized(value['B03'],value['B11']);valid=clear&np.isfinite(index)&(value['B03']>=0)&(value['B11']>=0)&(value['B03']<=1.2)&(value['B11']<=1.2)
    rgb=np.stack([value[b] for b in ('B04','B03','B02')],axis=-1)/.30
    ir=np.stack([value[b] for b in ('B08','B04','B03')],axis=-1)/.45
    scaled=lambda a:(np.where(np.isfinite(a),np.clip(a,0,1),145/255)*255).astype('uint8')
    quality=np.where(clear[...,None],np.array([239,245,246]),np.array(PALETTE['invalid_color'])).astype('uint8')
    panels=[scaled(rgb),scaled(ir),color_mndwi(index,valid),quality]
    canvas=Image.new('RGB',(800,870),'white');draw=ImageDraw.Draw(canvas);polygon=footprint(point,rec['crs'])
    labels=['Natural color | 10m','Infrared | 10m','MNDWI | blue + / orange - | SWIR 20m','Quality | grey: not accepted']
    for k,a in enumerate(panels):
        x=5+(k%2)*400;y=45+(k//2)*410
        canvas.paste(Image.fromarray(a).resize((390,390),Image.Resampling.NEAREST),(x,y));draw.text((x,y-17),labels[k],fill='black')
        vertices=[]
        for px,py in polygon.exterior.coords:
            col,row=(~transform)*(px,py);vertices.append((x+col*390/40,y+row*390/40))
        draw.line(vertices,fill='black',width=5);draw.line(vertices,fill='#ffcc00',width=2)
    draw.text((8,5),f'Sample {point["number"]} | actual date {scene["date"]} UTC | north up',fill='black')
    draw.text((8,850),f'Yellow: original pixel. 400m view. Contains modified Copernicus Sentinel data {point["year"]}.',fill='black')
    target=OUT/'evidence'/point['sample_id']/(item+'.png');target.parent.mkdir(parents=True,exist_ok=True);canvas.save(target)
    return point['sample_id'],item,{'image_path':str(target.relative_to(ROOT)).replace('\\','/'),'image_sha256':digest(target),
        'source_tiff_sha256':rec['tiff_sha256'],'calibration_xml_sha256':cal['xml_sha256']}


def main():
    parent=json.loads((PARENT/'screening_dataset.json').read_text(encoding='utf-8'))
    protected={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in [PARENT/'screening_dataset.json',PARENT/'review_manifest.json',PARENT/'screening_report.json',ROOT/'Water_Only_Confused_Review.html',ROOT/'Water_Independent_Accuracy_Review.html']}
    OUT.mkdir(exist_ok=True);ids={s['item_id'] for r in parent['rows'] for s in r['scenes']}
    calibrations={}
    for item in ids:
        p=SOURCE/'sources/calibration'/(item+'.json');cal=json.loads(p.read_text(encoding='utf-8'))
        assert digest(p.with_suffix('.xml'))==cal['xml_sha256'];calibrations[item]=cal
    displays={};jobs=[(r,s) for r in parent['rows'] for s in r['scenes']]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(render,r,s,calibrations[s['item_id']]) for r,s in jobs]
        for n,f in enumerate(as_completed(futures),1):
            sid,item,display=f.result();displays[(sid,item)]=display
            if n%500==0 or n==len(jobs):print('DATED_DISPLAYS',n,'/',len(jobs),flush=True)
    rows=[]
    for r in parent['rows']:
        scenes=[]
        for s in r['scenes']:
            spectral=next(e for e in r['spectral_evidence'] if e['item_id']==s['item_id'])
            scenes.append({**s,**displays[(r['sample_id'],s['item_id'])],
                'source_original_image_path':s['image_path'],'automated_scene_label':spectral['scene_automated_label']})
        rows.append({k:v for k,v in {**r,'scenes':scenes}.items() if k!='spectral_evidence'})
    identity={'schema':SCHEMA,'parent_dataset_id':parent['id'],'source_dataset_id':parent['source_dataset_id'],
        'scope':'Assisted per-acquisition human interpretation. Different dates retain different labels; no whole-month state is inferred from one date.',
        'palette':PALETTE,'default_required_dates':'All quality-supported dates >=95 percent at the same selected 245 review points; poor dates remain available in More and missing in exports unless explicitly answered.',
        'rows':rows}
    ds={**identity,'id':hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
    write_json(OUT/'dated_review_dataset.json',ds)
    count=sum(s['clear_fraction']>=.95 for r in rows if r['screening']['category']=='REVIEW' for s in r['scenes'])
    assert len(rows)==720 and len(displays)==3022 and count==694
    assert all(digest(ROOT/p)==h for p,h in protected.items())
    write_json(OUT/'display_build_checks.json',{'status':'PASS_FOR_DISPLAY_PREPARATION','created_at':now(),'points':720,'display_images':3022,
        'requested_review_points':245,'default_clear_date_tasks':count,'old_files_sha256':protected,'old_files_unchanged':True,
        'dataset_sha256':digest(OUT/'dated_review_dataset.json'),'actual_human_labels_created':0,'palette_is_ground_truth':False,
        'new_downloads_required':False,'source_raw_files_preserved':True,'code_sha256':digest(Path(__file__))})
    print(json.dumps({'status':'DATED_DISPLAY_DATASET_READY','review_points':245,'clear_date_tasks':count,'human_labels_created':0}))


if __name__=='__main__':main()
