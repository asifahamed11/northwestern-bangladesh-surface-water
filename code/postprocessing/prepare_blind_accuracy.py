"""Fresh, stratified JRC monthly validation samples and actual-date imagery.

No human labels are generated. Target classes stay in private/ and are not
rendered, printed by point, or used to select reference dates/clear images.
This is a separate validation frame, excluding the previous 720 exposed cells.
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import argparse, calendar, csv, hashlib, io, json, math, sys, time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import threading

import numpy as np
import requests
import rasterio
from rasterio.features import rasterize
from shapely.geometry import shape, Point, Polygon, box
from pyproj import Transformer
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research_pipeline.spatial import Grid
from research_pipeline.common import REGIONS, digest

OUT=ROOT/'independent_accuracy_20261015'
API='https://planetarycomputer.microsoft.com/api'
PERIODS=((2018,3),(2020,11),(2023,3),(2024,11))
SEED=20261015
BANDS=('B02','B03','B04','B08','B11','SCL')
TOKEN_CACHE={}
TOKEN_LOCK=threading.Lock()


def now():return datetime.now(timezone.utc).isoformat()


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(path)


def http(method,url,**kwargs):
    for attempt in range(4):
        try:
            r=requests.request(method,url,timeout=(15,65),**kwargs)
            if r.status_code in (429,500,502,503,504) and attempt<3:
                pause=min(20,max(1,int(r.headers.get('Retry-After','2'))))
                time.sleep(pause);continue
            r.raise_for_status();return r
        except requests.RequestException:
            if attempt==3:raise
    raise RuntimeError('Request failed')


def sample():
    manifest=OUT/'public/sample_manifest.json'
    if manifest.exists():
        audit=json.loads((OUT/'sample_audit.json').read_text(encoding='utf-8'))
        for path,digest0 in audit['input_sha256'].items():
            if digest(ROOT/path)!=digest0:raise ValueError('Frozen input changed: '+path)
        return json.loads(manifest.read_text(encoding='utf-8'))
    config=json.loads((ROOT/'research_pipeline/config.json').read_text())
    grid=Grid(ROOT)
    # Public previous sample coordinates only; never load previous target values.
    old=json.loads((ROOT/'dated_reference_pilot_20261015/v2_validated_ranges/pilot_plan.json').read_text())
    import verify_water_labels as V
    previous,_=V.read_viewer(ROOT/'Water_Review.html')
    excluded={}
    for p in previous['rows']:
        col,row=(~grid.transform)*(p['longitude'],p['latitude'])
        excluded.setdefault((p['year'],p['month']),set()).add(int(math.floor(row))*grid.width+int(math.floor(col)))
    inputs=[ROOT/'research_pipeline/config.json',ROOT/'Water_Review.html',ROOT/'Water_Review.manifest.json',grid.raw/'verified_study_area.geojson',grid.prep/'fixed_annual_everwater_footprint.tif']
    inputs.extend(grid.raw/f'jrc_monthly_{y}.tif' for y,m in PERIODS)
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in inputs}
    rng=np.random.default_rng(SEED);private=[];public=[];counts=[]
    for year,month in PERIODS:
        with rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds:
            grid.check(ds);values=ds.read(month)
        for region_index,region in enumerate(REGIONS[1:],1):
            for prediction in (0,1):
                population=np.flatnonzero((grid.labels==region_index)&(values==(2 if prediction else 1)))
                initial_count=len(population)
                population=np.setdiff1d(population,np.fromiter(excluded[(year,month)],dtype='int64'),assume_unique=False)
                n=min(config['validation_samples_per_district_class_period'],len(population))
                chosen=rng.choice(population,size=n,replace=False)
                stratum=f'{year}-{month:02}_{region_index}_{prediction}'
                counts.append({'stratum':stratum,'initial_population':initial_count,'eligible_population':len(population),'sampled':n,'minimum_verified':min(config['validation_minimum_verified_samples_per_stratum'],len(population))})
                for flat in chosen:
                    row,col=divmod(int(flat),grid.width)
                    lon,lat=grid.transform*(col+.5,row+.5)
                    left,top=grid.transform*(col,row);right,bottom=grid.transform*(col+1,row+1)
                    sid='b_'+hashlib.sha256(f'{SEED}:{year}:{month}:{region_index}:{flat}'.encode()).hexdigest()[:22]
                    item={'sample_id':sid,'region':region,'year':year,'month':month,'period':f'{year}-{month:02}',
                          'longitude':lon,'latitude':lat,'bounds':[left,bottom,right,top]}
                    public.append(item)
                    private.append({**item,'predicted_water':prediction,'stratum':stratum,'population_pixels':len(population),
                                    'planned_samples':n,'pixel_area_km2':float(grid.row_areas[row]),'row':row,'col':col})
    rng.shuffle(public)
    for i,p in enumerate(public,1):p['number']=i
    if len(public)!=720 or len({p['sample_id'] for p in public})!=720:raise ValueError('Expected 720 unique fresh real sampled pixels')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'private').mkdir(exist_ok=True)
    write_json(OUT/'private/validation_sample_plan.json',private)
    write_json(OUT/'private/stratum_counts.json',counts)
    write_json(OUT/'public/sample_manifest.json',public)
    write_json(OUT/'sample_audit.json',{'created_at':now(),'seed':SEED,'sample_count':len(public),'strata':len(counts),
        'per_stratum_target':30,'per_stratum_minimum_existing_protocol':20,'minimum_count_not_accuracy_guarantee':True,
        'previous_sample_pixels_excluded':720,'exact_prior_pixel_period_overlap':0,'frame':'JRC-valid observed district pixels in four fixed months, excluding exposed prior sample cells. Not annual hydroperiod or all-year validation.',
        'selection_uses_reference_values':False,'public_manifest_has_target_predictions':False,
        'input_sha256':hashes,'source_grid':{'crs':'EPSG:4326','transform':list(grid.transform),'width':grid.width,'height':grid.height},
        'sampling_design':'Separate simple random samples without replacement in district x period x JRC binary class strata; independently shuffled display. Private classes used only for sampling/evaluation, not reference-image selection.',
        'independence_limit':'Operational blinding only; private files are locally accessible and must not be opened by the human reviewer. New points can be spatially close to prior image contexts. Same-process QA is not independent verification.'})
    print('FROZEN_SAMPLE',len(public),'24 strata; previous pixel-period overlap 0',flush=True)
    return public


def catalog(points):
    col=OUT/'sources/collection.json'
    if not col.exists():write_json(col,http('GET',API+'/stac/v1/collections/sentinel-2-l2a').json())
    spec=OUT/'sources/data_api_openapi.json'
    if not spec.exists():write_json(spec,http('GET',API+'/data/v1/openapi.json').json())
    entries={}
    # Whole study bounding box from the frozen real raster, not a guessed area.
    with rasterio.open(ROOT/'NW_Bangladesh_2000_2024/jrc_monthly_2018.tif') as ds:bbox=list(ds.bounds)
    for year,month in PERIODS:
        path=OUT/f'sources/search_{year}_{month:02}.json'
        if path.exists():result=json.loads(path.read_text(encoding='utf-8'))
        else:
            query={'collections':['sentinel-2-l2a'],'bbox':bbox,
                   'datetime':f'{year}-{month:02}-01T00:00:00Z/{year}-{month:02}-{calendar.monthrange(year,month)[1]:02}T23:59:59Z','limit':100}
            result=http('POST',API+'/stac/v1/search',json=query).json();page=result;all_features=list(page['features']);pages=1
            while page['features']:
                nxt=next((l for l in page.get('links',[]) if l['rel']=='next'),None)
                if not nxt:break
                if not nxt['href'].startswith(API+'/stac/v1/') or pages>20:raise ValueError('Unexpected pagination')
                method=nxt.get('method','GET');kwargs={'json':nxt['body']} if 'body' in nxt else {}
                page=http(method,nxt['href'],**kwargs).json();all_features.extend(page['features']);pages+=1
            result=dict(result,features=all_features,retrieved_pages=pages,retrieved_at=now(),query=query)
            write_json(path,result)
        entries[(year,month)]=result['features']
        print('CATALOG',year,month,len(result['features']),flush=True)
    schedule_path=OUT/'public/reference_schedule.json'
    if schedule_path.exists():return json.loads(schedule_path.read_text(encoding='utf-8'))
    schedule=[];unique_items={}
    geometries={f['id']:shape(f['geometry']) for group in entries.values() for f in group}
    for p in points:
        candidates=[f for f in entries[(p['year'],p['month'])] if geometries[f['id']].covers(box(*p['bounds']))]
        # Deduplicate processing versions/overlap tiles by acquisition date;
        # prefer highest declared processing baseline, then deterministic item ID.
        by_day={}
        for f in sorted(candidates,key=lambda f:(float(f['properties'].get('s2:processing_baseline','0')),f['id']),reverse=True):
            by_day.setdefault(f['properties']['datetime'][:10],f)
        days=sorted(by_day)
        selected=[days[i] for i in sorted({0,len(days)//2,len(days)-1})] if days else []
        item_ids=[]
        for day in selected:
            f=by_day[day];unique_items[f['id']]=f;item_ids.append(f['id'])
        schedule.append({'sample_id':p['sample_id'],'number':p['number'],'catalog_acquisition_dates':days,
                         'selected_item_ids':item_ids,'selection':'Earliest, middle-index and latest available acquisition date; fixed before any pixel values or human labels. No cloud/class preselection.'})
    for item_id,item in unique_items.items():write_json(OUT/'sources/items'/f'{item_id}.json',item)
    write_json(schedule_path,schedule)
    write_json(OUT/'catalog_audit.json',{'created_at':now(),'points':len(points),'points_with_three_dates':sum(len(s['selected_item_ids'])==3 for s in schedule),
        'unique_selected_items':len(unique_items),'point_scene_pairs':sum(len(s['selected_item_ids']) for s in schedule),
        'all_acquisitions_inventoried':True,'all_acquisitions_downloaded':False,
        'dates_selection_water_blind':True,'missing_reference_is_not_nonwater':True,
        'temporal_limit':'Three selected dates do not establish every intervening day or transient inundation. Human labels are dated sensor references, with temporal uncertainty retained.'})
    return schedule


def calibration(item):
    path=OUT/'sources/calibration'/f"{item['id']}.json"
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    raw_url=item['assets']['product-metadata']['href']
    parsed=urlparse(raw_url)
    account=parsed.hostname.split('.')[0];container=parsed.path.strip('/').split('/')[0]
    token_key=(account,container)
    with TOKEN_LOCK:
        if token_key not in TOKEN_CACHE:
            TOKEN_CACHE[token_key]=http('GET',API+f'/sas/v1/token/{account}/{container}').json()['token']
        signed=raw_url+'?'+TOKEN_CACHE[token_key]
    # The public, expiring read token is used only in memory, never persisted.
    content=http('GET',signed).content
    xml=ET.fromstring(content)
    quantities=[float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_QUANTIFICATION_VALUE']
    if len(quantities)!=1:raise ValueError('Unknown BOA quantification metadata')
    offsets={e.attrib['band_id']:float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_ADD_OFFSET'}
    baseline=float(item['properties'].get('s2:processing_baseline','0'))
    if baseline>=4 and not offsets:raise ValueError('Missing post-baseline-04 offset metadata')
    band_ids={'B02':'1','B03':'2','B04':'3','B08':'7','B11':'11'}
    coeff={b:{'scale':1/quantities[0],'offset':offsets.get(idx,0)/quantities[0]} for b,idx in band_ids.items()}
    xml_path=path.with_suffix('.xml');xml_path.parent.mkdir(parents=True,exist_ok=True);xml_path.write_bytes(content)
    result={'item_id':item['id'],'unsigned_metadata_url':raw_url,'processing_baseline':str(baseline),
        'quantification_value':quantities[0],'band_coefficients':coeff,'xml_sha256':digest(xml_path),
        'api_unscale':False,'source_encoding':'Original Sentinel DN; nodata DN=0 excluded before scale/offset','retrieved_at':now()}
    write_json(path,result);return result


def footprint(p,crs):
    t=Transformer.from_crs(4326,crs,always_xy=True)
    l,b,r,u=p['bounds']
    return Polygon([t.transform(l,b),t.transform(r,b),t.transform(r,u),t.transform(l,u)])


def scene(p,item_id,cal):
    directory=OUT/'evidence'/p['sample_id'];done=directory/f'{item_id}.json'
    if done.exists():
        rec=json.loads(done.read_text(encoding='utf-8'))
        if digest(OUT/rec['image_path'])!=rec['image_sha256'] or digest(OUT/rec['tiff_path'])!=rec['tiff_sha256']:raise ValueError('Cached evidence hash mismatch')
        return rec
    item=json.loads((OUT/'sources/items'/f'{item_id}.json').read_text(encoding='utf-8'))
    epsg=item['properties']['proj:epsg']
    x,y=Transformer.from_crs(4326,epsg,always_xy=True).transform(p['longitude'],p['latitude'])
    x0=math.floor(x/20)*20-200;y0=math.floor(y/20)*20-200
    bounds=[x0,y0,x0+400,y0+400]
    url=API+f'/data/v1/item/bbox/{x0},{y0},{x0+400},{y0+400}/40x40.tif'
    params=[('collection','sentinel-2-l2a'),('item',item_id),('coord_crs',f'EPSG:{epsg}'),('dst_crs',f'EPSG:{epsg}'),
            ('unscale','false'),('resampling','nearest'),('reproject','nearest'),('return_mask','true')]+[('assets',b) for b in BANDS]
    response=http('GET',url,params=params)
    with rasterio.io.MemoryFile(response.content) as mem,mem.open() as ds:
        if ds.count!=7 or ds.shape!=(40,40) or ds.crs.to_epsg()!=epsg or ds.res!=(10,10):raise ValueError('Unexpected crop grid/bands')
        if not np.allclose(ds.bounds,bounds):raise ValueError('Returned crop bounds mismatch')
        raw=ds.read();transform=ds.transform
    values={}
    for i,b in enumerate(BANDS[:-1]):
        coef=cal['band_coefficients'][b]
        a=raw[i].astype('float32')*coef['scale']+coef['offset'];a[(raw[i]==0)|(raw[6]==0)]=np.nan;values[b]=a
    scl=raw[5];polygon=footprint(p,epsg)
    weights=np.zeros((40,40),dtype='float64')
    for rr in range(40):
        for cc in range(40):
            l,u=transform*(cc,rr);r,b=transform*(cc+1,rr+1)
            if polygon.intersects(box(l,b,r,u)):weights[rr,cc]=polygon.intersection(box(l,b,r,u)).area
    if not np.isclose(weights.sum()/polygon.area,1,atol=1e-6):raise ValueError('Target footprint not fully covered')
    clear=np.isin(scl,[4,5,6])&(raw[6]>0)&np.all(raw[:5]>0,axis=0)
    support=float(weights[clear].sum()/polygon.area)
    # Four visual panels, no threshold/class prediction or SCL water labels.
    rgb=np.stack([values[b] for b in ('B04','B03','B02')],axis=-1)
    ir=np.stack([values[b] for b in ('B08','B04','B03')],axis=-1)
    swir=np.stack([values[b] for b in ('B11','B08','B03')],axis=-1)
    quality=np.where(clear[...,None],np.array([239,245,246]),np.array([118,118,118])).astype('uint8')
    panels=[rgb/.30,ir/.45,swir/.45,quality/255]
    canvas=Image.new('RGB',(800,870),'white');draw=ImageDraw.Draw(canvas)
    names=['Natural color | 10 m','Infrared | 10 m','SWIR / NIR / green | SWIR 20 m','Quality only | grey: not accepted']
    for k,a in enumerate(panels):
        a=np.where(np.isfinite(a),np.clip(a,0,1),1)
        img=Image.fromarray((a*255).astype('uint8')).resize((390,390),Image.Resampling.NEAREST)
        xx=5+(k%2)*400;yy=45+(k//2)*410
        canvas.paste(img,(xx,yy));draw.text((xx,yy-17),names[k],fill='black')
        coords=[]
        for px,py in polygon.exterior.coords:
            col,row=(~transform)*(px,py);coords.append((xx+col*390/40,yy+row*390/40))
        draw.line(coords,fill='black',width=5);draw.line(coords,fill='#ffcc00',width=2)
    date=item['properties']['datetime'][:10]
    draw.text((8,5),f'Sample {p["number"]} | {p["period"]} | acquisition {date} UTC | north up',fill='black')
    draw.text((8,850),f'Yellow: original pixel. 400 m view. Contains modified Copernicus Sentinel data {p["year"]}.',fill='black')
    directory.mkdir(parents=True,exist_ok=True)
    tiff=directory/f'{item_id}.tif';png=directory/f'{item_id}.png'
    tiff.write_bytes(response.content);canvas.save(png)
    rec={'sample_id':p['sample_id'],'item_id':item_id,'acquisition_datetime':item['properties']['datetime'],
         'processing_baseline':item['properties'].get('s2:processing_baseline'),'api_url':url,'api_parameters':params,
         'source_assets':{b:item['assets'][b]['href'] for b in BANDS},'calibration_path':str((OUT/'sources/calibration'/f'{item_id}.json').relative_to(OUT)),
         'tiff_path':str(tiff.relative_to(OUT)).replace('\\','/'),'image_path':str(png.relative_to(OUT)).replace('\\','/'),
         'tiff_sha256':digest(tiff),'image_sha256':digest(png),'crs':f'EPSG:{epsg}','transform':list(transform),'bounds':bounds,
         'requested_asset_order':list(BANDS),'tiff_band_7':'shared data mask','display_grid_resolution_m':10,
         'original_resolution_m':{'B02':10,'B03':10,'B04':10,'B08':10,'B11':20,'SCL':20},
         'resampling':'nearest; 20m bands have not gained detail','conservative_clear_pixel_fraction':min(1.0,max(0.0,support)),
         'quality_is_ground_truth':False,'retrieved_at':now()}
    write_json(done,rec);return rec


def download(points,schedule,limit=None,workers=6):
    selected=points[:limit] if limit else points
    by={s['sample_id']:s for s in schedule}
    ids={item_id for p in selected for item_id in by[p['sample_id']]['selected_item_ids']}
    coefficients={};errors=[]
    def get_cal(i):return i,calibration(json.loads((OUT/'sources/items'/f'{i}.json').read_text(encoding='utf-8')))
    with ThreadPoolExecutor(max_workers=min(workers,4)) as pool:
        for future in as_completed([pool.submit(get_cal,i) for i in ids]):
            try:
                i,cal=future.result();coefficients[i]=cal
            except Exception as exc:errors.append({'stage':'calibration','error':type(exc).__name__,'message':str(exc)[:140]})
    if errors:
        write_json(OUT/'download_errors.json',errors);raise SystemExit('Calibration failures; refuse unknown units/offsets')
    jobs=[(p,item_id) for p in selected for item_id in by[p['sample_id']]['selected_item_ids']]
    completed=0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(scene,p,i,coefficients[i]):(p['number'],i) for p,i in jobs}
        for future in as_completed(futures):
            try:future.result();completed+=1
            except Exception as exc:errors.append({'stage':'crop','number':futures[future][0],'error':type(exc).__name__,'message':str(exc)[:160]})
            if completed%30==0 or completed==len(jobs):print('CROPS',completed,'/',len(jobs),'errors',len(errors),flush=True)
    write_json(OUT/'download_progress.json',{'checked_at':now(),'requested_points':len(selected),'planned_total_points':len(points),
        'expected_point_scene_pairs':len(jobs),'completed_point_scene_pairs':completed,'errors':errors,
        'human_labels_generated':0,'all_selected_reference_files_complete':not errors and completed==len(jobs),
        'entire_validation_set_downloaded':not limit and not errors and completed==len(jobs)})
    if errors:raise SystemExit('Incomplete downloads retained for resumable retrieval; not ready.')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--metadata-only',action='store_true');ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=6)
    args=ap.parse_args();points=sample();schedule=catalog(points)
    if not args.metadata_only:download(points,schedule,args.limit,args.workers)
