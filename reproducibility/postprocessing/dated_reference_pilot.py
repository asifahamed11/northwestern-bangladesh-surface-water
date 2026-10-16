"""Retrieve actual-dated Sentinel-2 cutouts for a frozen five-location pilot.

This creates an evidence bundle, never reference labels or human attestations.
All acquisitions returned for the target month are retained, including clouded
ones. Nothing from the private JRC prediction table is read.
"""
from __future__ import annotations
import argparse, calendar, csv, hashlib, json, math, platform, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
import rasterio
from rasterio.windows import Window, from_bounds
from pyproj import Transformer
from shapely.geometry import Polygon, box
from http_range_raster import HTTPRangeReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import verify_water_labels as V

API = 'https://earth-search.aws.element84.com/v1'
POSITIONS = (1, 181, 361, 541, 720)
BANDS = ('blue', 'green', 'red', 'nir', 'swir16', 'scl')
OUT = ROOT / 'dated_reference_pilot_20261015' / 'v2_validated_ranges'


def collection(p):
    # Collection 1 returned no 2018-03 scenes at point 1. Legacy baseline 00.01
    # has zero offset; the other dates use C1 with calibration in the TIFF header.
    return 'sentinel-2-l2a' if p['year']==2018 else 'sentinel-2-c1-l2a'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def get_json(url, method='GET', payload=None):
    response = requests.request(method, url, json=payload, timeout=(20, 60))
    response.raise_for_status()
    return response.json()


def frozen_plan():
    OUT.mkdir(parents=True,exist_ok=True)
    path = OUT / 'pilot_plan.json'
    if path.exists():
        p = json.loads(path.read_text(encoding='utf-8'))
        for name, expected in p['input_sha256'].items():
            if sha(ROOT / name) != expected:
                raise ValueError('Frozen source changed: ' + name)
        return p
    viewer, _ = V.read_viewer(ROOT / 'Water_Review.html')
    p = {
        'created_at': now(),
        'selection': 'Fixed original viewer positions 1,181,361,541 plus explicitly unresolved 720; chosen before retrieving dated pixel values. Coverage pilot only, not a representative accuracy sample.',
        'points': [dict(number=n, **{k: v for k, v in viewer['rows'][n-1].items() if k != 'image'}) for n in POSITIONS],
        'input_sha256': {name: sha(ROOT / name) for name in (
            'Water_Review.html', 'Water_Review.manifest.json',
            'water_reference_labels_corrected_20261015.csv',
            'water_review_backup_corrected_20261015.json')},
        'protocol': {
            'collection': 'Legacy sentinel-2-l2a for 2018-03 (C1 unavailable there); sentinel-2-c1-l2a for 2020/2023/2024. No cross-baseline water trend calculated.', 'period': 'Exact original target calendar month, UTC',
            'scene_filter': 'All returned point-intersecting acquisitions; no cloud-cover preselection. Fetch six native-resolution bands for every acquisition.',
            'context_half_width_m': 300,
            'clear_SCL_classes': [4, 5, 6],
            'quality_caution': 'SCL is an imperfect algorithmic quality cue. Classes 2 and 7 conservatively excluded. No-data/shadow/cloud never becomes dry land.',
            'scale': 'Use each asset raster:bands scale/offset; preserve original DN and native grid. Reject unknown scale/offset.',
            'display': 'Nearest-neighbor only for 20m SWIR/SCL on a 10m display; original support remains 20m. Fixed RGB 0..0.30 and IR 0..0.45.',
            'reference_scope': 'Dated Sentinel-2 evidence independent of JRC Landsat inputs, but not independent of prior Sentinel-2 composites or algorithm feedback. AI review is not a human attestation.',
            'reference_labels_written': False, 'accuracy_computed': False,
            'revision_reason': 'v1 GDAL HTTPS reads failed with truncated TIFF tiles. v2 uses explicitly validated byte ranges and avoids legacy post-2022 BOA offset ambiguity. Original partial retrieval folder preserved; not an accepted evidence run.',
        }
    }
    dump(path, p)
    return p


def metadata(plan):
    for name in sorted({collection(p) for p in plan['points']}):
        colpath = OUT / (name + '_collection.json')
        if not colpath.exists():
            dump(colpath, get_json(API + '/collections/'+name))
    for p in plan['points']:
        directory = OUT / f"point_{p['number']:03d}"
        target = directory / 'search.json'
        if target.exists():
            continue
        y, m = p['year'], p['month']
        query = {
            'collections': [collection(p)],
            'intersects': {'type': 'Point', 'coordinates': [p['longitude'], p['latitude']]},
            'datetime': f'{y}-{m:02d}-01T00:00:00Z/{y}-{m:02d}-{calendar.monthrange(y,m)[1]:02d}T23:59:59Z',
            'limit': 100,
        }
        dump(directory / 'request.json', {'url': API+'/search', 'method': 'POST', 'json': query, 'retrieved_at': now()})
        result = get_json(API + '/search', 'POST', query)
        page=result
        features=list(page['features'])
        dump(directory / 'search_page_01.json',page)
        pages=1
        while page['features']:
            links=[link for link in page.get('links',[]) if link.get('rel')=='next']
            if not links:
                break
            link=links[0]
            if link['href'] != API+'/search' or pages>=20:
                raise ValueError('Unexpected pagination destination or page count')
            page=get_json(link['href'],link.get('method','GET'),link.get('body'))
            pages+=1
            dump(directory / f'search_page_{pages:02d}.json',page)
            features.extend(page['features'])
        if result.get('numberMatched',len(features)) != len(features):
            raise ValueError('Incomplete STAC pagination')
        result=dict(result,features=features,numberReturned=len(features),retrieved_pages=pages,links=[link for link in result.get('links',[]) if link.get('rel')!='next'])
        ids = [f['id'] for f in result['features']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate item IDs')
        for f in result['features']:
            if f['properties']['datetime'][:7] != p['period']:
                raise ValueError('Acquisition outside exact target month')
            dump(directory / f['id'] / 'item.json', f)
        dump(target, result)
        print('SEARCH', p['number'], p['period'], len(ids), flush=True)


def target_polygon(p, epsg):
    left, bottom, right, top = p['bounds']
    tx = Transformer.from_crs(4326, epsg, always_xy=True)
    # Densify the original geographic pixel edges before projection.
    vertices = []
    corners = [(left,bottom),(right,bottom),(right,top),(left,top),(left,bottom)]
    for (x0,y0),(x1,y1) in zip(corners[:-1],corners[1:]):
        for t in np.linspace(0, 1, 9, endpoint=False):
            vertices.append(tx.transform(x0+(x1-x0)*t, y0+(y1-y0)*t))
    return Polygon(vertices)


def overlap_weights(ds, target):
    weights = np.zeros((ds.height, ds.width), dtype='float64')
    w = from_bounds(*target.bounds, ds.transform)
    for row in range(max(0,math.floor(w.row_off)), min(ds.height,math.ceil(w.row_off+w.height))):
        for col in range(max(0,math.floor(w.col_off)), min(ds.width,math.ceil(w.col_off+w.width))):
            left, top = ds.transform * (col, row)
            right, bottom = ds.transform * (col+1, row+1)
            weights[row,col] = target.intersection(box(left,bottom,right,top)).area
    return weights


def retrieve_scene(p, feature):
    itemdir = OUT / f"point_{p['number']:03d}" / feature['id']
    done = itemdir / 'retrieval.json'
    if done.exists():
        record = json.loads(done.read_text(encoding='utf-8'))
        for b in record['assets']:
            if sha(itemdir / b['local_path']) != b['sha256']:
                raise ValueError('Cached cutout checksum mismatch')
        return record
    epsg = feature['properties']['proj:epsg']
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(p['longitude'], p['latitude'])
    target = target_polygon(p, epsg)
    records = []
    # Thread-local GDAL environment, native-grid reads, no AWS credentials.
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_TIMEOUT=45, GDAL_HTTP_MAX_RETRY=2, GDAL_HTTP_RETRY_DELAY=1):
        for band in BANDS:
            asset = feature['assets'][band]
            url = asset['href']
            if not url.startswith(('https://sentinel-cogs.s3.us-west-2.amazonaws.com/','https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/')):
                raise ValueError('Unexpected public asset host')
            local = itemdir / (band + '.tif')
            rb = asset['raster:bands'][0]
            if band != 'scl' and ('scale' not in rb or 'offset' not in rb):
                raise ValueError('Unknown reflectance calibration')
            if not local.exists():
                virtual_name=feature['id']+'_'+str(p['number'])+'_'+band+'.tif'
                def opener(name,mode='rb'):
                    if str(name)!=virtual_name:
                        raise FileNotFoundError(name)
                    return HTTPRangeReader(url)
                with rasterio.open(virtual_name,opener=opener) as src:
                    if src.crs.to_epsg() != epsg:
                        raise ValueError('STAC/raster CRS mismatch')
                    if feature['collection']=='sentinel-2-c1-l2a' and band!='scl':
                        if not np.isclose(src.scales[0],rb['scale']) or not np.isclose(src.offsets[0],rb['offset']):
                            raise ValueError('C1 asset/header calibration mismatch')
                    if feature['collection']=='sentinel-2-l2a' and rb.get('offset',0)!=0:
                        raise ValueError('Do not interpret ambiguous legacy BOA offsets')
                    w = from_bounds(x-300,y-300,x+300,y+300,src.transform)
                    c0,r0 = math.floor(w.col_off),math.floor(w.row_off)
                    c1,r1 = math.ceil(w.col_off+w.width),math.ceil(w.row_off+w.height)
                    window = Window(c0,r0,c1-c0,r1-r0).intersection(Window(0,0,src.width,src.height))
                    a = src.read(1,window=window)
                    profile = src.profile.copy()
                    profile.update(driver='GTiff',height=a.shape[0],width=a.shape[1],count=1,transform=src.window_transform(window),compress='deflate')
                    for key in ('blockxsize','blockysize','tiled','photometric'):
                        profile.pop(key, None)
                    temporary = local.with_suffix('.partial.tif')
                    with rasterio.open(temporary,'w',**profile) as dst:
                        dst.write(a,1)
                        dst.set_band_description(1,band)
                        dst.update_tags(SOURCE_URL=url,STAC_ITEM_ID=feature['id'],ACQUISITION_DATETIME=feature['properties']['datetime'],STAC_SCALE=str(rb.get('scale',1)),STAC_OFFSET=str(rb.get('offset',0)))
                    temporary.replace(local)
            with rasterio.open(local) as ds:
                weights=overlap_weights(ds,target)
                if abs(weights.sum()/target.area-1) > 1e-5:
                    raise ValueError('Native cutout does not cover whole target pixel')
                info={'band':band,'url':url,'local_path':local.name,'sha256':sha(local),'crs':ds.crs.to_string(),'transform':list(ds.transform),'shape':[ds.height,ds.width],'native_resolution_m':list(ds.res),'nodata':ds.nodata,'scale':rb.get('scale',1),'offset':rb.get('offset',0),'whole_pixel_coverage_fraction':float(weights.sum()/target.area)}
                if band=='scl':
                    a=ds.read(1)
                    info['whole_pixel_class_fractions']={str(int(c)):float(weights[a==c].sum()/target.area) for c in np.unique(a[weights>0])}
                    info['whole_pixel_conservative_clear_fraction']=float(weights[np.isin(a,[4,5,6])].sum()/target.area)
                records.append(info)
    result={'number':p['number'],'sample_id':p['id'],'period':p['period'],'collection':feature['collection'],'item_id':feature['id'],'acquisition_datetime':feature['properties']['datetime'],'retrieved_at':now(),'processing_baseline':feature['properties'].get('s2:processing_baseline'),'boa_offset_applied':feature['properties'].get('earthsearch:boa_offset_applied'),'tile_cloud_cover_percent':feature['properties'].get('eo:cloud_cover'),'assets':records,'status':'ACTUAL_DATED_CUTOUTS_RETRIEVED','reference_quality':'NOT_ATTESTED','reference_water':None}
    dump(done,result)
    print('RETRIEVED',p['number'],feature['id'],flush=True)
    return result


def download(plan):
    jobs=[]
    for p in plan['points']:
        features=json.loads((OUT/f"point_{p['number']:03d}"/'search.json').read_text(encoding='utf-8'))['features']
        ordered=sorted(features,key=lambda f:f['properties']['datetime'])
        # A bounded temporal pilot, selected before viewing imagery, not an
        # exhaustive month reconstruction. All search metadata remain intact.
        indices=sorted({0,len(ordered)//2,len(ordered)-1}) if ordered else []
        jobs.extend((p,ordered[i]) for i in indices)
    schedule={'created_at':now(),'reason':'Bounded five-location feasibility pilot. Retrieve earliest, middle-index and latest catalog acquisition per location before any visual interpretation. All monthly metadata preserved. Unseen acquisitions cannot establish monthly stability. This supersedes v2 initial all-scenes retrieval proposal, not the fixed point selection.','selection_uses_water_values':False,'selected':[{'number':p['number'],'item_id':f['id'],'datetime':f['properties']['datetime']} for p,f in jobs]}
    schedule_path=OUT/'pilot_retrieval_schedule.json'
    if schedule_path.exists():
        if json.loads(schedule_path.read_text(encoding='utf-8'))['selected']!=schedule['selected']:
            raise ValueError('Frozen retrieval schedule mismatch')
    else:
        dump(schedule_path,schedule)
    jobs.sort(key=lambda pf:(pf[1]['properties']['datetime'][8:10],pf[0]['number']))
    errors=[]
    results=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(retrieve_scene,p,f):(p['number'],f['id']) for p,f in jobs}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append({'point_and_item':futures[future],'exception':type(exc).__name__,'message':str(exc)})
                print('ERROR',futures[future],type(exc).__name__,str(exc)[:160],flush=True)
    dump(OUT/'download_summary.json',{'expected_scene_point_pairs':len(jobs),'completed_scene_point_pairs':len(results),'errors':errors,'checked_at':now(),'human_verified_labels_generated':0,'accuracy_computed':False})
    if errors:
        raise SystemExit('Some downloads failed; no completion claim. Rerun resumes cached cutouts.')


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--metadata-only',action='store_true')
    args=ap.parse_args()
    plan=frozen_plan()
    metadata(plan)
    dump(OUT/'environment.json',{'python':sys.version,'platform':platform.platform(),'requests':requests.__version__,'rasterio':rasterio.__version__,'numpy':np.__version__,'gdal':rasterio.__gdal_version__,'code_sha256':sha(__file__)})
    if not args.metadata_only:
        download(plan)
