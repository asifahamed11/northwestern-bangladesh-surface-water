"""Download public provider-linked context and independent-label metadata only."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import requests,json,hashlib
OUT=Path(__file__).resolve().parent
D=OUT/'external_sources';D.mkdir(exist_ok=True)
spec={'frozen_before_context_outcomes_utc':datetime.now(timezone.utc).isoformat(),
 'river_buffers_m':[200,500,1000], 'primary_buffer_m':500,
 'river_distance_crs':'EPSG:32645',
 'landcover':'ESA WorldCover 2020 v100, categorical modal resampling to source grid; static 2020 context only',
 'groups':['near_mapped_river','far_2020_cropland','far_2020_other','missing_context'],
 'cohorts':['original_everwater_2000_2024_complete_2000_2024','baseline_anywater_2000_2004_complete_2000_2021'],
 'comparisons':'single endpoints and 5-year mean areas; strict 3-of-5 majority gross transitions, ambiguous retained',
 'caveats':'No 2000 crop backcast, pond identity, pumping attribution, or observed discharge inferred from static context.'}
if not (OUT/'CONTEXT_PROTOCOL_ADDENDUM.json').exists():
 (OUT/'CONTEXT_PROTOCOL_ADDENDUM.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
jobs=[
 ('hydrorivers_asia.zip','https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_as_shp.zip'),
 ('worldcover_grid_2020.geojson','https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/esa_worldcover_2020_grid.geojson'),
 ('planet_stac_index.html','https://data.cyverse.org/dav-anon/iplant/home/shared/commons_repo/curated/Rohit_GlobalSurfaceWaterDataset_2024/stac_catalog/'),
 ('planet_readme.txt','https://data.cyverse.org/dav-anon/iplant/home/shared/commons_repo/curated/Rohit_GlobalSurfaceWaterDataset_2024/README.txt')]
def fetch(job):
 name,url=job; p=D/name; r={'name':name,'url':url,'retrieved_utc':datetime.now(timezone.utc).isoformat()}
 try:
  if p.exists(): r.update(status='EXISTING',bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest());return r
  with requests.get(url,stream=True,timeout=(12,40)) as response:
   r.update(http_status=response.status_code,final_url=response.url)
   response.raise_for_status()
   temp=p.with_suffix(p.suffix+'.partial'); h=hashlib.sha256();n=0
   with temp.open('wb') as f:
    for block in response.iter_content(1024*1024):
     if block:f.write(block);h.update(block);n+=len(block)
   temp.rename(p);r.update(status='DOWNLOADED',bytes=n,sha256=h.hexdigest())
 except Exception as e:r.update(status='ACCESS_FAILED',error_type=type(e).__name__,error=str(e))
 print(json.dumps(r),flush=True)
 return r
with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,jobs))
(D/'context_acquisition_log.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
