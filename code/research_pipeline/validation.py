import json
import hashlib
import numpy as np
import pandas as pd
import rasterio
from .common import REGIONS, require, write_table

def sample_plan(grid,config,out):
    rng=np.random.default_rng(config['random_seed'])
    private=[]; blind=[]; geo=[]
    for year,month in config['validation_periods']:
        with rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds:
            grid.check(ds); values=ds.read(month)
        for r,region in enumerate(REGIONS[1:],1):
            for predicted in [0,1]:
                population=np.flatnonzero((grid.labels==r)&(values==(2 if predicted else 1)))
                n=min(config['validation_samples_per_district_class_period'],len(population))
                if n==0: continue
                chosen=rng.choice(population,size=n,replace=False)
                for order,flat in enumerate(chosen):
                    row,col=divmod(int(flat),grid.width)
                    lon,lat=grid.transform*(col+.5,row+.5)
                    sample='s_'+hashlib.sha256(f'{config["random_seed"]}:{year}:{month}:{r}:{flat}'.encode()).hexdigest()[:20]
                    shared={'sample_id':sample,'region':region,'year':year,'month':month,
                            'longitude':lon,'latitude':lat}
                    private.append({**shared,'predicted_water':predicted,
                        'stratum':f'{year}-{month:02}_{r}_{predicted}',
                        'population_pixels':len(population),'planned_samples':n,
                        'pixel_area_km2':grid.row_areas[row]})
                    blind.append({**shared,'reference_water':'','reference_date':'',
                        'reference_source':'','reference_quality':'','notes':''})
                    geo.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':shared})
    plan=write_table(out/'validation_predictions_private.csv',private)
    write_table(out/'reference_labels_to_complete.csv',blind)
    (out/'validation_points_blinded.geojson').write_text(json.dumps({'type':'FeatureCollection','features':geo}),encoding='utf-8')
    return plan

def evaluate_reference(plan,path,config,out):
    columns=['scope','n_verified','overall_area_time_weighted_accuracy','water_producer_accuracy','water_user_accuracy','lower95_bootstrap','upper95_bootstrap']
    if not path.is_file():
        write_table(out/'independent_validation_metrics.csv',[],columns)
        return {'status':'MISSING_REFERENCE_LABELS','reason':'Complete genuine independent labels; blank planned labels are not data'}
    labels=pd.read_csv(path)
    needed=['sample_id','reference_water','reference_date','reference_source','reference_quality']
    require(set(needed).issubset(labels.columns),'Reference label schema incomplete')
    require(not labels.sample_id.duplicated().any(),'Duplicate reference sample IDs')
    require(set(labels.sample_id).issubset(set(plan.sample_id)),'Unknown sample ID in reference labels')
    joined=plan.merge(labels[needed],on='sample_id',how='left',validate='one_to_one')
    quality=joined.reference_quality.fillna('').astype(str).str.upper()
    verified=joined[quality=='VERIFIED'].copy()
    verified['reference_water']=pd.to_numeric(verified.reference_water,errors='raise')
    require(verified.reference_water.isin([0,1]).all(),'Verified labels must be 0 or 1')
    require(verified.reference_source.fillna('').str.strip().ne('').all(),'Verified source provenance missing')
    require(~verified.reference_source.str.contains(r'\bJRC\b|\bGSW\b|global.surface.water',case=False,regex=True).any(),
            'JRC/GSW cannot be its own independent reference')
    dates=pd.to_datetime(verified.reference_date,errors='raise')
    require(dates.notna().all() and (dates.dt.year==verified.year).all() and (dates.dt.month==verified.month).all(),'Reference date missing/outside target month')
    per_stratum=[]; complete=True
    for stratum,group in plan.groupby('stratum'):
        n=int((verified.stratum==stratum).sum()); N=int(group.population_pixels.iloc[0])
        required=min(config['validation_minimum_verified_samples_per_stratum'],N)
        good=n>=required
        complete=complete and good
        per_stratum.append({'stratum':stratum,'population_pixels':N,'planned_samples':len(group),
                            'verified_labels':n,'minimum_required':required,'status':'PASS' if good else 'INSUFFICIENT_LABELS'})
    write_table(out/'validation_stratum_completeness.csv',per_stratum)
    if not complete or len(verified)==0:
        write_table(out/'independent_validation_metrics.csv',[],columns)
        return {'status':'INCOMPLETE_REFERENCE_LABELS','verified':len(verified),'reason':'Every planned population stratum must meet its minimum'}
    counts=verified.groupby('stratum').size()
    verified['design_weight_km2']=verified.population_pixels/verified.stratum.map(counts)*verified.pixel_area_km2
    def metrics(frame):
        confusion=np.zeros((2,2))
        for reference in [0,1]:
            for predicted in [0,1]:
                confusion[reference,predicted]=frame.loc[(frame.reference_water==reference)&(frame.predicted_water==predicted),'design_weight_km2'].sum()
        overall=np.trace(confusion)/confusion.sum()
        producer=confusion[1,1]/confusion[1].sum() if confusion[1].sum() else np.nan
        user=confusion[1,1]/confusion[:,1].sum() if confusion[:,1].sum() else np.nan
        return overall,producer,user,confusion
    overall,producer,user,confusion=metrics(verified)
    rng=np.random.default_rng(config['random_seed'])
    groups=[group for _,group in verified.groupby('stratum')]
    boot=[]
    for _ in range(config['validation_bootstrap_replicates']):
        draw=pd.concat([g.iloc[rng.integers(0,len(g),len(g))] for g in groups],ignore_index=True)
        boot.append(metrics(draw)[0])
    low,high=np.quantile(boot,[.025,.975])
    write_table(out/'independent_validation_metrics.csv',[{'scope':'sampled_months_observed_district_pixels',
        'n_verified':len(verified),'overall_area_time_weighted_accuracy':overall,'water_producer_accuracy':producer,
        'water_user_accuracy':user,'lower95_bootstrap':low,'upper95_bootstrap':high}],columns)
    write_table(out/'validation_weighted_confusion.csv',[{'reference_water':r,'predicted_water':p,
        'estimated_area_time_weight_km2':confusion[r,p]} for r in [0,1] for p in [0,1]])
    return {'status':'METRICS_COMPUTED','verified':len(verified),
            'scope':'Binary monthly classification only; does not validate annual hydroperiod classes or geolocation consistency'}
