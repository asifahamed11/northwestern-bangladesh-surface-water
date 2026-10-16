"""Recompute frozen sampling and calibration contracts from real source files."""
from pathlib import Path
from collections import Counter
import json,math,sys,xml.etree.ElementTree as ET
import numpy as np
import rasterio
from prepare_blind_accuracy import ROOT,OUT,PERIODS,SEED,BANDS,digest,write_json,now
from research_pipeline.spatial import Grid
from research_pipeline.common import REGIONS
import verify_water_labels as V


def main():
    grid=Grid(ROOT);old,_=V.read_viewer(ROOT/'Water_Review.html')
    excluded={}
    for p in old['rows']:
        col,row=(~grid.transform)*(p['longitude'],p['latitude'])
        excluded.setdefault((p['year'],p['month']),set()).add(math.floor(row)*grid.width+math.floor(col))
    plan=json.loads((OUT/'private/validation_sample_plan.json').read_text(encoding='utf-8'))
    rng=np.random.default_rng(SEED);checked=0
    for year,month in PERIODS:
        with rasterio.open(grid.raw/f'jrc_monthly_{year}.tif') as ds:
            grid.check(ds);values=ds.read(month)
        for region_index,region in enumerate(REGIONS[1:],1):
            for predicted in (0,1):
                population=np.flatnonzero((grid.labels==region_index)&(values==(2 if predicted else 1)))
                population=np.setdiff1d(population,np.array(sorted(excluded[(year,month)]),dtype='int64'),assume_unique=False)
                chosen=rng.choice(population,size=30,replace=False)
                points=[p for p in plan if p['year']==year and p['month']==month and p['region']==region and p['predicted_water']==predicted]
                actual=np.array([p['row']*grid.width+p['col'] for p in points])
                assert np.array_equal(actual,chosen),'Frozen random sample does not reproduce'
                for p in points:
                    assert p['population_pixels']==len(population) and p['planned_samples']==30
                    assert p['row']*grid.width+p['col'] not in excluded[(year,month)]
                    assert grid.row_areas[p['row']]==p['pixel_area_km2']
                    assert np.allclose(grid.transform*(p['col']+.5,p['row']+.5),(p['longitude'],p['latitude']))
                    checked+=1
    public=json.loads((OUT/'public/sample_manifest.json').read_text(encoding='utf-8'))
    shuffled=[p['sample_id'] for p in plan];rng.shuffle(shuffled)
    assert shuffled==[p['sample_id'] for p in public]
    calibrated=0
    for path in sorted((OUT/'sources/calibration').glob('*.json')):
        cal=json.loads(path.read_text(encoding='utf-8'));xml_path=path.with_suffix('.xml')
        assert digest(xml_path)==cal['xml_sha256']
        xml=ET.fromstring(xml_path.read_bytes())
        q=[float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_QUANTIFICATION_VALUE']
        offset={e.attrib['band_id']:float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_ADD_OFFSET'}
        assert len(q)==1 and q[0]==cal['quantification_value']
        if float(cal['processing_baseline'])>=4:assert offset
        for band,idx in {'B02':'1','B03':'2','B04':'3','B08':'7','B11':'11'}.items():
            assert cal['band_coefficients'][band]=={'scale':1/q[0],'offset':offset.get(idx,0)/q[0]}
        calibrated+=1
    # Check existing recorded answer snapshots against their own frozen manifest.
    report_dir=ROOT/'label_verification/user_pilot_confirmation_20261015'
    confirmation_checks=json.loads((report_dir/'CONFIRMATION_CHECKS.json').read_text(encoding='utf-8'))
    old_hashes={**confirmation_checks['input_sha256'],**confirmation_checks['output_sha256']}
    assert all(digest(Path(p))==h for p,h in old_hashes.items()),'Existing user answer or pilot evidence snapshot changed'
    result={'status':'PASS','checked_at':now(),'fresh_points':checked,'random_sample_reproduced':True,
        'display_shuffle_reproduced':True,'population_sizes_design_weights_grid_checked':True,
        'old_exact_pixel_period_overlap':0,'calibration_xml_files_checked':calibrated,
        'coefficients_recomputed_from_actual_product_xml':True,'old_user_answer_and_pilot_hashes_rechecked':len(old_hashes),
        'human_reference_labels_generated':0,'scope':'Same-process reproducibility/data QA, not independent reference validity.'}
    write_json(OUT/'sample_and_calibration_checks.json',result)
    print(json.dumps(result))


if __name__=='__main__':main()
