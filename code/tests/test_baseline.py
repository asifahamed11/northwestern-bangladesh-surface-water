"""Tiny synthetic test rasters stay in pytest's temporary directory only."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from research_pipeline.baseline import prepare_baseline,ERA

@pytest.fixture
def baseline_fixture(tmp_path,monkeypatch):
    folder=tmp_path/'NW_Bangladesh_climate_baseline_1981_1999'; folder.mkdir()
    raw=tmp_path/'NW_Bangladesh_2000_2024'; raw.mkdir()
    out=tmp_path/'out'; out.mkdir()
    profile={'driver':'GTiff','height':2,'width':2,'dtype':'float32','nodata':-9999,
             'crs':'EPSG:4326','transform':from_origin(88,25,.05,.05)}
    for year in list(range(1981,2000))+[2000]:
        target=raw if year==2000 else folder
        rain=np.stack([np.full((2,2),100+m) for m in range(1,13)]).astype('float32')
        values=[-.1,300.,290.,.2,3.,4.]
        era=np.stack([np.full((2,2),v) for m in range(12) for v in values]).astype('float32')
        for name,data,bands in [('chirps_v3_monthly',rain,[f'm{m:02}_rainfall_mm' for m in range(1,13)]),
                                ('era5land_monthly',era,[f'm{m:02}_{v}' for m in range(1,13) for v in ERA])]:
            with rasterio.open(target/f'{name}_{year}.tif','w',count=len(data),**profile) as ds:
                ds.write(data)
                for n,band in enumerate(bands,1): ds.set_band_description(n,band)
    records=[]
    for y in range(1981,2000):
        for m in range(1,13):
            for kind,count,source in [('CHIRPS_PENTAD',6,'UCSB-CHC/CHIRPS/V3/PENTAD'),
                                      ('ERA5_LAND_MONTHLY',1,'ECMWF/ERA5_LAND/MONTHLY_AGGR')]:
                records.append({'dataset':kind,'source_asset':source,'year':y,'month':m,'expected_images':count,
                    'actual_images':count,'unique_timestamps':count,'period_count_ok':1})
    pd.DataFrame(records).to_csv(folder/'baseline_source_inventory.csv',index=False)
    weights=np.ones((4,2,2)); weights[0]=3
    monkeypatch.setattr('research_pipeline.baseline.climate_weights',lambda grid,ds:weights)
    grid=SimpleNamespace(raw=raw,vector_areas=np.array([12.,4.,4.,4.]))
    return tmp_path,grid,out,folder

def test_baseline_real_schema_units_and_full_roster(baseline_fixture):
    root,grid,out,folder=baseline_fixture
    frame,status=prepare_baseline(root,grid,out)
    assert status['status']=='PASS' and len(frame)==912
    assert not frame.duplicated(['region','year','month']).any()
    record=frame[(frame.region=='Naogaon')&(frame.year==1981)&(frame.month==1)].iloc[0]
    assert record.chirps_rainfall_mm==pytest.approx(101)
    assert record.era5_temperature_c==pytest.approx(26.85)
    assert record.era5_precipitation_mm==pytest.approx(200,rel=1e-6)
    assert record.era5_potential_evaporation_mm_signed==pytest.approx(-100,rel=1e-6)
    assert record.era5_evaporation_demand_mm_sign_reversed==pytest.approx(100,rel=1e-6)

@pytest.mark.parametrize('failure',['period','source','timestamps','band','spatial_gap','grid'])
def test_baseline_rejects_incomplete_or_incompatible_input(baseline_fixture,failure):
    root,grid,out,folder=baseline_fixture
    inv=folder/'baseline_source_inventory.csv'; records=pd.read_csv(inv)
    if failure=='period': records=records.iloc[:-1]
    if failure=='source': records.loc[0,'source_asset']='wrong/version'
    if failure=='timestamps': records.loc[0,'unique_timestamps']=0
    records.to_csv(inv,index=False)
    if failure in ['band','spatial_gap','grid']:
        with rasterio.open(folder/'chirps_v3_monthly_1981.tif','r+') as ds:
            if failure=='band': ds.set_band_description(1,'bad_name')
            if failure=='spatial_gap':
                a=ds.read(1); a[0,0]=-9999; ds.write(a,1)
            if failure=='grid': ds.transform=from_origin(88,25,.1,.1)
    with pytest.raises(ValueError): prepare_baseline(root,grid,out)

def test_missing_calibration_is_explicit(tmp_path):
    frame,status=prepare_baseline(tmp_path,None,tmp_path)
    assert frame is None and status['status']=='MISSING_INPUT'
