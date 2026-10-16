import json
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
from pyproj import Transformer
from .common import REGIONS, require, write_table, write_json

WATER_GROUPS = {'all_water':None, 'baseline_seasonal':2, 'baseline_permanent':3}

def majority_class(values):
    frequencies=np.stack([(values==cls).sum(axis=0) for cls in (1,2,3)])
    return np.where(frequencies.max(axis=0)>len(values)/2,frequencies.argmax(axis=0)+1,0).astype('uint8')

def initial_class_map(grid,config,out):
    """Freeze labels using only the first five study years, without future relabeling."""
    result=np.zeros((grid.height,grid.width),dtype='uint8')
    years=range(config['start_year'],config['start_year']+5)
    handles=[rasterio.open(grid.raw/f'jrc_annual_{year}.tif') for year in years]
    try:
        for win in grid.windows:
            top=int(win.row_off); stop=top+int(win.height)
            values=np.stack([ds.read(1,window=win) for ds in handles])
            state=majority_class(values)
            state[~np.all(np.isin(values,[1,2,3]),axis=0)]=0
            result[top:stop]=state
    finally:
        for ds in handles: ds.close()
    profile=grid.profile.copy(); profile.update(count=1,dtype='uint8',nodata=255,compress='deflate')
    with rasterio.open(out/'baseline_2000_2004_hydroperiod_class.tif','w',**profile) as ds:
        ds.write(np.where(grid.labels>0,result,255).astype('uint8'),1)
        ds.set_band_description(1,'strict_majority_initial_five_years_0_ambiguous_1_nonwater_2_seasonal_3_permanent')
    return result

class Grid:
    def __init__(self,root):
        self.raw=root/'NW_Bangladesh_2000_2024'
        self.prep=root/'NW_Bangladesh_preprocessed'
        fc=json.loads((self.raw/'verified_study_area.geojson').read_text())
        self.features=sorted(fc['features'],key=lambda f:f['properties']['district'])
        with rasterio.open(self.raw/'jrc_monthly_2000.tif') as ds:
            self.profile=ds.profile.copy(); self.transform=ds.transform
            self.height,self.width=ds.height,ds.width
            self.signature=(ds.width,ds.height,str(ds.crs),tuple(ds.transform))
        self.labels=rasterize([(f['geometry'],n) for n,f in enumerate(self.features,1)],
                              out_shape=(self.height,self.width),transform=self.transform,dtype='uint8')
        self.project=Transformer.from_crs(4326,6933,always_xy=True).transform
        self.polygons=[transform(self.project,shape(f['geometry'])) for f in self.features]
        self.vector_polygons=[unary_union(self.polygons)]+self.polygons
        self.vector_areas=np.array([p.area/1e6 for p in self.vector_polygons])
        with rasterio.open(self.prep/'fixed_annual_everwater_footprint.tif') as ds:
            self.check(ds); self.fixed=ds.read(1)==1
        x0,_=self.project(self.transform.c,self.transform.f)
        x1,_=self.project(self.transform.c+self.transform.a,self.transform.f)
        lat=self.transform.f+np.arange(self.height+1)*self.transform.e
        _,y=self.project(np.full(len(lat),self.transform.c),lat)
        self.row_areas=abs(x1-x0)*abs(np.diff(y))/1e6
        self.windows=[Window(0,t,self.width,min(256,self.height-t)) for t in range(0,self.height,256)]

    def check(self,ds):
        require((ds.width,ds.height,str(ds.crs),tuple(ds.transform))==self.signature,
                'Raster grid differs: '+str(ds.name))

    def region(self,r):
        return self.labels>0 if r==0 else self.labels==r

    def area(self,mask):
        return float(mask.sum(axis=1,dtype=np.int64)@self.row_areas)

    def save_mask(self,path,mask,region=0,description='common_support'):
        profile=self.profile.copy()
        profile.update(count=1,dtype='uint8',nodata=255,compress='deflate',predictor=1)
        with rasterio.open(path,'w',**profile) as ds:
            for w in self.windows:
                top=int(w.row_off); stop=top+int(w.height)
                domain=(self.labels[top:stop]>0) if region==0 else self.labels[top:stop]==region
                ds.write(np.where(domain,mask[top:stop].astype('uint8'),255).astype('uint8'),1,window=w)
            ds.set_band_description(1,description)

def build_support(grid,monthly,config,out):
    years=range(config['start_year'],config['end_year']+1)
    frame=monthly[monthly.year.isin(years)].copy()
    candidates={}; masks={}; diagnostics=[]
    for threshold in config['coverage_thresholds']:
        for r,name in enumerate(REGIONS):
            selected=frame[(frame.region==name)&(frame.coverage_pct>=threshold-1e-8)&
                           (frame.fixed_annual_everwater_coverage_pct>=threshold-1e-8)]
            key=(threshold,r)
            candidates[key]=set(zip(selected.year,selected.month))
            masks[key]=grid.fixed & grid.region(r)
    annual_mask=grid.fixed.copy()
    for year in years:
        with rasterio.open(grid.raw/f'jrc_annual_{year}.tif') as annual, rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds:
            grid.check(annual); grid.check(ds)
            require(ds.descriptions==tuple(f'm{m:02}' for m in range(1,13)),'Monthly bands mismatch')
            for win in grid.windows:
                top=int(win.row_off); stop=top+int(win.height)
                a=annual.read(1,window=win)
                annual_mask[top:stop]&=(a>=1)&(a<=3)
                values=ds.read(window=win)
                for month in range(1,13):
                    valid=(values[month-1]==1)|(values[month-1]==2)
                    for key,mask in masks.items():
                        if (year,month) in candidates[key]: mask[top:stop]&=valid
        print('Common support:',year,flush=True)
    initial=initial_class_map(grid,config,out)
    masks={(t,r,group):(mask if cls is None else mask&(initial==cls))
           for (t,r),mask in masks.items() for group,cls in WATER_GROUPS.items()}
    candidates={(t,r,group):selected for (t,r),selected in candidates.items() for group in WATER_GROUPS}
    for key,mask in masks.items():
        threshold,r,group=key
        cls=WATER_GROUPS[group]
        reference=grid.area(grid.fixed & grid.region(r) & ((initial==cls) if cls is not None else True))
        area=grid.area(mask)
        n=len(candidates[key])
        fraction=area/reference if reference else 0
        passed=n>=config['minimum_candidate_months'] and fraction>=config['minimum_common_support_fraction']
        diagnostics.append({'region':REGIONS[r],'water_group':group,'threshold_pct':threshold,
            'candidate_months':n,'reference_footprint_area_km2':reference,
            'common_support_pixels':int(mask.sum()),'common_support_area_km2':area,
            'retained_reference_fraction':fraction,'support_status':'PASS' if passed else 'INSUFFICIENT_SUPPORT',
            'reason':'' if passed else 'Too few candidate months or too little common spatial support'})
        grid.save_mask(out/f'monthly_common_support_{threshold}_{REGIONS[r]}_{group}.tif',mask,r)
    grid.save_mask(out/'annual_common_support.tif',annual_mask,description='annual_valid_every_study_year')
    write_table(out/'common_support_quality.csv',diagnostics)
    return masks,candidates,annual_mask,pd.DataFrame(diagnostics)

def extract_support_series(grid,masks,candidates,annual_mask,diagnostics,config,out):
    monthly_rows=[]; annual_rows=[]
    areas={k:grid.area(m) for k,m in masks.items()}
    passed={(int(row.threshold_pct),REGIONS.index(row.region),row.water_group):row.support_status=='PASS'
            for row in diagnostics.itertuples()}
    annual_reference={r:grid.area(grid.fixed & grid.region(r)) for r in range(4)}
    annual_domains={r:annual_mask & grid.region(r) for r in range(4)}
    annual_areas={r:grid.area(mask) for r,mask in annual_domains.items()}
    for year in range(config['start_year'],config['end_year']+1):
        counts={k:np.zeros((12,2),dtype=np.int64) for k in masks}
        physical={k:np.zeros((12,2)) for k in masks}
        annual_physical=np.zeros((4,3))
        with rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds, rasterio.open(grid.raw/f'jrc_annual_{year}.tif') as ads:
            grid.check(ds); grid.check(ads)
            for win in grid.windows:
                top=int(win.row_off); stop=top+int(win.height)
                a=ds.read(window=win); ann=ads.read(1,window=win)
                weights=grid.row_areas[top:stop]
                for r,mask in annual_domains.items():
                    part=mask[top:stop]
                    for cls in (1,2,3):
                        annual_physical[r,cls-1]+=float(((ann==cls)&part).sum(axis=1)@weights)
                for key,mask in masks.items():
                    indices=np.flatnonzero(mask[top:stop])
                    if not len(indices): continue
                    selected=a.reshape(12,-1)[:,indices]
                    pixel_weights=weights[indices//grid.width]
                    valid=(selected==1)|(selected==2); water=selected==2
                    counts[key][:,0]+=valid.sum(axis=1); counts[key][:,1]+=water.sum(axis=1)
                    physical[key][:,0]+=valid@pixel_weights; physical[key][:,1]+=water@pixel_weights
        for key,mask in masks.items():
            threshold,r,group=key
            total=int(mask.sum()); area=areas[key]
            for m in range(12):
                complete=total>0 and counts[key][m,0]==total
                candidate=(year,m+1) in candidates[key]
                eligible=passed[key] and candidate and complete and (group=='all_water' or year>=config['cohort_analysis_start_year'])
                monthly_rows.append({'region':REGIONS[r],'water_group':group,'threshold_pct':threshold,'year':year,'month':m+1,
                    'period':f'{year}-{m+1:02}','common_support_area_km2':area,'common_support_pixels':total,
                    'observed_support_pixels':int(counts[key][m,0]),
                    'support_coverage_pct':100*physical[key][m,0]/area if area else np.nan,
                    'candidate_month':candidate,'eligible':eligible,
                    'water_area_km2':physical[key][m,1] if eligible else np.nan,
                    'water_fraction':physical[key][m,1]/area if eligible else np.nan,
                    'landsat_collection':1 if year<2022 else 2})
        for r in range(4):
            area=annual_areas[r]
            retained=area/annual_reference[r] if annual_reference[r] else 0
            eligible=area>0 and retained>=config['minimum_common_support_fraction']
            require(np.isclose(annual_physical[r].sum(),area,rtol=1e-8,atol=1e-8),'Annual common support not fully classified')
            annual_rows.append({'region':REGIONS[r],'year':year,'common_support_area_km2':area,
                'retained_reference_fraction':retained,'eligible':eligible,
                'nonwater_area_km2':annual_physical[r,0] if eligible else np.nan,
                'seasonal_water_area_km2':annual_physical[r,1] if eligible else np.nan,
                'permanent_water_area_km2':annual_physical[r,2] if eligible else np.nan,
                'landsat_collection':1 if year<2022 else 2})
        print('Support series:',year,flush=True)
    m=write_table(out/'monthly_common_support_water.csv',monthly_rows)
    a=write_table(out/'annual_common_support_water.csv',annual_rows)
    require(m.loc[m.eligible,'support_coverage_pct'].between(100-1e-7,100+1e-7).all(),'Partial support admitted')
    return m,a

def transition_map(grid,annual_mask,config,out):
    early=list(range(config['start_year'],config['start_year']+5))
    late=list(range(config['primary_end_year']-4,config['primary_end_year']+1))
    require(max(early)<min(late),'Endpoint windows overlap')
    profile=grid.profile.copy(); profile.update(count=1,dtype='int16',nodata=-9999,compress='deflate',predictor=2)
    rows=[]
    handles={y:rasterio.open(grid.raw/f'jrc_annual_{y}.tif') for y in early+late}
    try:
        with rasterio.open(out/'annual_transition_primary_pre2022.tif','w',**profile) as dst:
            for win in grid.windows:
                top=int(win.row_off); stop=top+int(win.height)
                domain=annual_mask[top:stop]
                states=[]
                for years in (early,late):
                    values=np.stack([handles[y].read(1,window=win) for y in years])
                    state=majority_class(values)
                    states.append(state)
                codes=np.where(domain,states[0]*10+states[1],-9999).astype('int16')
                codes[domain&((states[0]==0)|(states[1]==0))]=0
                dst.write(codes,1,window=win)
            dst.set_band_description(1,'strict_majority_early_to_late_class')
            dst.update_tags(early_years=','.join(map(str,early)),late_years=','.join(map(str,late)),
                coding='11..33 = start class*10+end class; 0=no strict majority; -9999=outside common support')
    finally:
        for ds in handles.values(): ds.close()
    with rasterio.open(out/'annual_transition_primary_pre2022.tif') as ds:
        for win in grid.windows:
            top=int(win.row_off); stop=top+int(win.height)
            codes=ds.read(1,window=win)
            for r,name in enumerate(REGIONS):
                region=(grid.labels[top:stop]>0) if r==0 else grid.labels[top:stop]==r
                for code in [0,11,12,13,21,22,23,31,32,33]:
                    area=float(((codes==code)&region).sum(axis=1)@grid.row_areas[top:stop])
                    rows.append({'region':name,'transition_code':code,'area_km2':area})
    write_table(out/'annual_transition_areas.csv',pd.DataFrame(rows).groupby(['region','transition_code'],as_index=False).area_km2.sum())

def climate_weights(grid,ds):
    weights=np.zeros((4,ds.height,ds.width))
    for row in range(ds.height):
        for col in range(ds.width):
            x0,y0=ds.transform*(col,row); x1,y1=ds.transform*(col+1,row+1)
            cell=transform(grid.project,box(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)))
            for r in range(1,4): weights[r,row,col]=grid.polygons[r-1].intersection(cell).area/1e6
    weights[0]=weights[1:].sum(axis=0)
    require(np.allclose(weights.sum(axis=(1,2)),grid.vector_areas,rtol=1e-7),'Climate grid does not cover domain')
    return weights
