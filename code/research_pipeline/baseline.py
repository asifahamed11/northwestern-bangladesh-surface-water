import numpy as np
import pandas as pd
import rasterio
from .common import REGIONS, require, write_table
from .spatial import climate_weights

ERA=['potential_evaporation_sum','temperature_2m','dewpoint_temperature_2m',
     'total_precipitation_sum','u_component_of_wind_10m','v_component_of_wind_10m']

def prepare_baseline(root,grid,out):
    folder=root/'NW_Bangladesh_climate_baseline_1981_1999'
    if not folder.is_dir(): return None,{'status':'MISSING_INPUT','reason':'Download the 1981-1999 calibration exports with the supplied GEE script'}
    expected={(kind,y,m) for y in range(1981,2000) for kind in ['CHIRPS_PENTAD','ERA5_LAND_MONTHLY'] for m in range(1,13)}
    inventory=folder/'baseline_source_inventory.csv'
    require(inventory.is_file(),'Baseline source inventory missing')
    inv=pd.read_csv(inventory)
    require(len(inv)==456 and set(zip(inv.dataset,inv.year,inv.month))==expected,'Baseline periods missing or duplicated')
    require((inv.period_count_ok==1).all() and (inv.actual_images==inv.expected_images).all() and (inv.unique_timestamps==inv.expected_images).all(),'Baseline source query failed')
    require('source_asset' in inv and (inv.loc[inv.dataset=='CHIRPS_PENTAD','source_asset']=='UCSB-CHC/CHIRPS/V3/PENTAD').all()
            and (inv.loc[inv.dataset=='ERA5_LAND_MONTHLY','source_asset']=='ECMWF/ERA5_LAND/MONTHLY_AGGR').all(),'Baseline source version mismatch')
    for year in range(1981,2000):
        for group in ['chirps_v3_monthly','era5land_monthly']:
            require((folder/f'{group}_{year}.tif').is_file(),f'Missing calibration raster: {group}_{year}')
    rows=[]; cached={}
    for year in range(1981,2000):
        with rasterio.open(folder/f'chirps_v3_monthly_{year}.tif') as rain, rasterio.open(folder/f'era5land_monthly_{year}.tif') as era:
            require(rain.descriptions==tuple(f'm{m:02}_rainfall_mm' for m in range(1,13)),'Baseline CHIRPS bands mismatch')
            require(era.descriptions==tuple(f'm{m:02}_{v}' for m in range(1,13) for v in ERA),'Baseline ERA bands mismatch')
            weights=[]
            for ds in [rain,era]:
                require(str(ds.crs)=='EPSG:4326','Baseline climate CRS mismatch')
                study_name='chirps_v3_monthly_2000.tif' if ds is rain else 'era5land_monthly_2000.tif'
                with rasterio.open(grid.raw/study_name) as study:
                    require((ds.width,ds.height,tuple(ds.transform))==(study.width,study.height,tuple(study.transform)),
                            'Baseline and study native climate grids differ')
                key=(ds.width,ds.height,tuple(ds.transform))
                if key not in cached: cached[key]=climate_weights(grid,ds)
                weights.append(cached[key])
            ra,ea=rain.read(),era.read()
            for m in range(12):
                for r,region in enumerate(REGIONS):
                    means=[]; fractions=[]
                    for values,w,nodata in [(ra[m],weights[0][r],rain.nodata)]+[(ea[m*6+n],weights[1][r],era.nodata) for n in range(6)]:
                        valid=np.isfinite(values)&(values!=nodata)&(w>0)
                        area=w[valid].sum()
                        require(area>0 and area/grid.vector_areas[r]>=.99,'Incomplete calibration spatial coverage')
                        means.append(float(np.sum(values[valid]*w[valid])/area)); fractions.append(100*area/grid.vector_areas[r])
                    rainfall,pev,temp,dew,precip,u,v=means
                    require(rainfall>=0 and precip>=0,'Negative calibration precipitation')
                    require(dew<=temp+1e-4,'Calibration dewpoint exceeds temperature')
                    rows.append({'region':region,'year':year,'month':m+1,'period':f'{year}-{m+1:02}',
                        'chirps_rainfall_mm':rainfall,'era5_temperature_c':temp-273.15,'era5_dewpoint_c':dew-273.15,
                        'era5_precipitation_mm':precip*1000,'era5_potential_evaporation_mm_signed':pev*1000,
                        'era5_evaporation_demand_mm_sign_reversed':-pev*1000,'era5_u_wind_ms':u,'era5_v_wind_ms':v,
                        'chirps_spatial_coverage_pct':fractions[0],
                        'era5_spatial_coverage_pct_min_across_variables':min(fractions[1:])})
    result=write_table(out/'baseline_climate_1981_1999.csv',rows)
    return result,{'status':'PASS','records':len(result),'source_inventory_rows':len(inv)}
