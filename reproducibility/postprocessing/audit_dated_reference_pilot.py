"""Audit this bounded acquisition and report bundle; no accuracy metrics."""
import csv, json, sys, zipfile
from pathlib import Path
import numpy as np
import rasterio
from dated_reference_pilot import OUT, ROOT, BANDS, frozen_plan, sha, dump, now


def main():
    plan=frozen_plan()
    schedule=json.loads((OUT/'pilot_retrieval_schedule.json').read_text(encoding='utf-8'))['selected']
    summary=json.loads((OUT/'download_summary.json').read_text(encoding='utf-8'))
    assert summary['expected_scene_point_pairs']==summary['completed_scene_point_pairs']==15
    assert not summary['errors']
    manifest=[]
    accepted_dirs=set()
    for s in schedule:
        p=next(p for p in plan['points'] if p['number']==s['number'])
        directory=OUT/f"point_{s['number']:03d}"/s['item_id']
        accepted_dirs.add(directory)
        r=json.loads((directory/'retrieval.json').read_text(encoding='utf-8'))
        item=json.loads((directory/'item.json').read_text(encoding='utf-8'))
        assert r['acquisition_datetime']==s['datetime']==item['properties']['datetime']
        assert r['acquisition_datetime'][:7]==p['period']
        assert r['sample_id']==p['id'] and r['reference_water'] is None
        assert sorted(a['band'] for a in r['assets'])==sorted(BANDS)
        for a in r['assets']:
            path=directory/a['local_path']
            assert sha(path)==a['sha256']
            assert np.isclose(a['whole_pixel_coverage_fraction'],1,rtol=0,atol=1e-5)
            with rasterio.open(path) as ds:
                expected=20 if a['band'] in ('scl','swir16') else 10
                assert ds.crs.to_epsg()==32645 and ds.res==(expected,expected)
                assert ds.nodata==0 and ds.count==1
                values=ds.read(1)
                assert list(values.shape)==a['shape']
                assert ds.tags()['ACQUISITION_DATETIME']==r['acquisition_datetime']
            manifest.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':a['sha256'],'band':a['band'],'acquisition_datetime':r['acquisition_datetime']})
    assert len(manifest)==90
    stats=json.loads((OUT/'dated_scene_evidence.json').read_text(encoding='utf-8'))
    reviews=json.loads((OUT/'ai_visual_review.json').read_text(encoding='utf-8'))
    assert len(stats)==15 and len(reviews)==5
    for k,r in reviews.items():
        assert r['reference_water'] is None and not r['human_attestation'] and not r['accuracy_eligible']
        assert sum('\u0980'<=c<='\u09ff' for c in r['explanation_bn'])>40
        assert r['explanation_bn'].count('?')==0
    assert reviews['541']['tentative_image_interpretation'] is None
    assert reviews['720']['tentative_image_interpretation'] is None
    for s in stats:
        assert s['reference_water'] is None and 0<=s['valid_MNDWI_area_fraction']<=1+1e-9
        if s['valid_MNDWI_area_fraction']==0:
            assert s['mndwi_min'] is None and s['mndwi_max'] is None
    source_rows=[json.loads(line) for line in (OUT/'sources.jsonl').read_text(encoding='utf-8').splitlines()]
    claims=json.loads((OUT/'claims.json').read_text(encoding='utf-8'))
    ids=[s['source_id'] for s in source_rows]
    urls=[s['url'] for s in source_rows]
    assert len(ids)==len(set(ids)) and len(urls)==len(set(urls))
    for s in source_rows:
        assert s['title'] and s['authors'] and s['retrieved_at'] and s['review_level'] and s['locator']
        assert s['crossref_metadata_verified'] is None
    for c in claims:
        assert c['source_ids'] and set(c['source_ids'])<=set(ids)
        assert c['support_reviewed'] and c['locator']
    dump(OUT/'evidence_audit.json',{'status':'PASS','scope':'Bounded acquisition/method evidence audit; no systematic literature or accuracy claim','sources':len(source_rows),'claims':len(claims),'duplicate_source_urls':0,'unsupported_recorded_claims':[],'doi_used':False,'crossref_audit':'Not applicable to these official corporate/data-provider documents; not falsely marked verified','limitations':['Three dates do not establish whole-month temporal stability','AI review is not an independent human attestation','SCL is an automated quality cue','Prior Sentinel-2 composite and automated feedback mean these are not new blind ground-truth labels','Legacy 2018 baseline and v1 2023 PB05.09 retained as explicit product-version limitations','Co-registration/VHR/field verification not completed']})
    qa=json.loads((OUT/'REPORT_QA.json').read_text(encoding='utf-8'))
    assert qa['status']=='PASS'
    dump(OUT/'accepted_cutout_manifest.json',manifest)
    result={'status':'PASS','scope':'Real dated evidence acquisition and software checks; independent accuracy remains incomplete','checked_at':now(),'locations':5,'scheduled_point_scene_pairs':15,'distinct_source_item_ids':len({s['item_id'] for s in schedule}),'accepted_native_cutouts':90,'whole_pixel_grid_date_and_checksum_checks':'PASS','input_files_unchanged':list(plan['input_sha256']),'ai_visual_reviews':5,'human_verified_labels_generated':0,'independent_accuracy_computed':False,'drought_recovery_problem_resolved':False,'software_transport_calibration_tests':4,'fully_accepted_SCL_footprints':sum(s['clear_SCL_area_fraction']>=.95 for s in stats),'uncertain_SCL_footprints':sum(s['clear_SCL_area_fraction']<.95 for s in stats),'entire_remote_source_file_checksums_verified':False,'checksum_scope':'Local native-resolution cutouts, not whole cloud objects; HTTP byte ranges validated and ETag stable within each read.'}
    dump(OUT/'FINAL_CHECKS.json',result)
    files=[ROOT/'Water_Dated_5_Point_Review.html',ROOT/'dated_reference_pilot_20261015'/'README_BN.md']
    files.extend(path for path in OUT.rglob('*') if path.is_file() and path.name!='package_file_manifest.json' and (path.parent==OUT or path.parent in accepted_dirs or (path.parent.name.startswith('point_') and path.suffix in ('.json','.png'))))
    files.extend(ROOT/'postprocessing'/name for name in ('dated_reference_pilot.py','http_range_raster.py','render_dated_reference_pilot.py','audit_dated_reference_pilot.py','dated_pilot_explanations_bn.json'))
    files.extend(ROOT/'tests'/name for name in ('test_dated_reference_ranges.py','check_dated_pilot_report.py'))
    files=sorted(set(files))
    manifest_all={str(path.relative_to(ROOT)).replace('\\','/'):sha(path) for path in files}
    dump(OUT/'package_file_manifest.json',manifest_all)
    files.append(OUT/'package_file_manifest.json')
    zip_path=ROOT/'Water_Dated_5_Point_Review_20261015.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for path in files:z.write(path,str(path.relative_to(ROOT)).replace('\\','/'))
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        import hashlib
        for name,digest in manifest_all.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
        assert len([name for name in z.namelist() if name.endswith('.tif')])==90
    dump(ROOT/'Water_Dated_5_Point_Review_20261015.zip.checks.json',{'status':'PASS','sha256':sha(zip_path),'bytes':zip_path.stat().st_size,'file_count':len(files),'accepted_TIFFs':90,'independent_accuracy_computed':False})
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
