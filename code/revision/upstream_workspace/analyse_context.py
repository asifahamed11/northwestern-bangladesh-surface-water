"""Static river/cropland context, not historical land-use or causal attribution."""
from pathlib import Path
from zipfile import ZipFile
import io,json,hashlib,sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject,Resampling
import shapefile
from shapely.geometry import shape,mapping,box
from shapely.ops import unary_union,transform
from pyproj import Transformer
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[3];sys.path.insert(0,str(ROOT))
from research_pipeline.spatial import Grid
from research_pipeline.common import REGIONS,write_json
D=OUT/'external_sources';C=OUT/'cache';T=OUT/'tables'
spec=json.loads((OUT/'CONTEXT_PROTOCOL_ADDENDUM.json').read_text(encoding='utf-8'))
g=Grid(ROOT); crs=g.profile['crs']
flat=np.load(C/'native_flat_indices.npy');labels=np.load(C/'region_labels.npy');weights=np.load(C/'pixel_areas_km2.npy')
annual=np.load(C/'annual_classes.npy',mmap_mode='r');cohorts=np.load(C/'cohort_masks.npz')
with rasterio.open(D/'ESA_WorldCover_10m_2020_v100_N24E087_Map.tif') as src:
 assert src.count==1 and src.crs.to_epsg()==4326 and src.dtypes[0]=='uint8'
 lc=np.zeros((g.height,g.width),dtype='uint8')
 reproject(source=rasterio.band(src,1),destination=lc,dst_transform=g.transform,dst_crs=crs,
  src_nodata=0,dst_nodata=0,resampling=Resampling.mode,warp_mem_limit=128,num_threads=2)
 src_metadata=dict(crs=str(src.crs),transform=list(src.transform),width=src.width,height=src.height,
                   categorical_resampling='GDAL mode to native JRC grid; not ground truth')
 lcv=lc.ravel()[flat]
 assert np.isin(lcv,[0,10,20,30,40,50,60,70,80,90,95,100]).all()
 coverage=float(weights[lcv!=0].sum()/weights.sum())
 assert coverage>=.99,'Landcover context coverage insufficient'
 with rasterio.open(C/'worldcover2020_modal_source_grid.tif','w',driver='GTiff',width=g.width,height=g.height,
   count=1,dtype='uint8',crs=crs,transform=g.transform,nodata=0,compress='deflate') as ds:ds.write(lc,1)
print('WorldCover genuine coverage:',coverage,flush=True)
bounds=(g.transform.c,g.transform.f+g.height*g.transform.e,g.transform.c+g.width*g.transform.a,g.transform.f)
features=[]
with ZipFile(D/'hydrorivers_asia.zip') as z:
 stem='HydroRIVERS_v10_as_shp/HydroRIVERS_v10_as'
 reader=shapefile.Reader(shp=io.BytesIO(z.read(stem+'.shp')),shx=io.BytesIO(z.read(stem+'.shx')),dbf=io.BytesIO(z.read(stem+'.dbf')))
 query=(bounds[0]-.03,bounds[1]-.03,bounds[2]+.03,bounds[3]+.03)
 for f in reader.iterShapeRecords(bbox=query):
  geom=shape(f.shape.__geo_interface__)
  if not geom.intersects(box(*query)):continue
  features.append(dict(type='Feature',geometry=mapping(geom),properties=f.record.as_dict()))
 assert features,'No river lines found'
(D/'hydrorivers_local_subset.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features)),encoding='utf-8')
to_m=Transformer.from_crs(4326,32645,always_xy=True).transform
to_deg=Transformer.from_crs(32645,4326,always_xy=True).transform
river_m=unary_union([transform(to_m,shape(f['geometry'])) for f in features])
print('HydroRIVERS local reaches:',len(features),flush=True)
def aggregate(mask):
 a=np.bincount(labels[mask],weights=weights[mask],minlength=4)
 return np.r_[a[1:].sum(),a[1:]]
maj=[]
for window in [annual[:5],annual[17:22]]:
 count=np.vstack([np.sum(window==k,axis=0) for k in [1,2,3]])
 winner=count.argmax(axis=0)+1;winner[count.max(axis=0)<3]=0
 maj.append(winner)
rows=[];trans=[];groupsizes=[]
for buffer in spec['river_buffers_m']:
 corridor=transform(to_deg,river_m.buffer(buffer))
 near=rasterize([(mapping(corridor),1)],out_shape=(g.height,g.width),transform=g.transform,fill=0,dtype='uint8').ravel()[flat]>0
 group=np.select([near,(~near)&(lcv==40),(~near)&(lcv!=0)], [1,2,3],default=4)
 np.save(C/f'context_group_{buffer}m.npy',group.astype('uint8'))
 for cohort in spec['cohorts']:
  base=cohorts[cohort]
  assert np.all(annual[:22,base]>=1),'Context calculation requires full annual source-class support'
  total=aggregate(base)
  for gi,name in enumerate(spec['groups'],1):
   mask=base&(group==gi);area=aggregate(mask)
   for r,region in enumerate(REGIONS):groupsizes.append(dict(cohort=cohort,buffer_m=buffer,region=region,context=name,area_km2=area[r],cohort_area_km2=total[r]))
   for width in [1,5]:
    first=annual[:width];last=annual[22-width:22]
    for cls,k in [('nonwater',1),('seasonal',2),('permanent',3)]:
     first_area=sum(aggregate(mask&(y==k)) for y in first)/width
     last_area=sum(aggregate(mask&(y==k)) for y in last)/width
     for r,region in enumerate(REGIONS):
      a=first_area[r];b=last_area[r]
      rows.append(dict(cohort=cohort,buffer_m=buffer,region=region,context=name,source_class=cls,window_years=width,
          context_area_km2=area[r],first_mean_km2=a,last_mean_km2=b,change_km2=b-a,percent_change=100*(b/a-1) if a else np.nan))
   for old in [0,1,2,3]:
    for new in [0,1,2,3]:
     aa=aggregate(mask&(maj[0]==old)&(maj[1]==new))
     for r,region in enumerate(REGIONS):trans.append(dict(cohort=cohort,buffer_m=buffer,region=region,context=name,
             first_majority_class=old,last_majority_class=new,area_km2=aa[r]))
pd.DataFrame(rows).to_csv(T/'static_context_window_changes.csv',index=False)
pd.DataFrame(trans).to_csv(T/'static_context_majority_transitions.csv',index=False)
sizes=pd.DataFrame(groupsizes);sizes.to_csv(T/'static_context_areas.csv',index=False)
for _,q in sizes.groupby(['cohort','buffer_m','region']):assert abs(q.area_km2.sum()-q.cohort_area_km2.iloc[0])<1e-6
write_json(OUT/'CONTEXT_COMPLETE.json',dict(status='COMPUTATION_COMPLETED',river_reaches=len(features),
    worldcover_coverage_fraction=coverage,worldcover_metadata=src_metadata,
    caveat='Distance to mapped river centreline and 2020 land-cover label are static context; no cause, historical land-use class or pond identity established.'))
print('PASS: static-context partitions and full ambiguous transitions reconcile.',flush=True)
