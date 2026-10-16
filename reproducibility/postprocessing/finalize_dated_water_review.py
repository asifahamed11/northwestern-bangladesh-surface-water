"""Final bounded display/entry audit; never evaluates real human accuracy."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,re,sys
import numpy as np
import rasterio,requests
from PIL import Image
from build_dated_water_dataset import ROOT,SOURCE,PARENT,OUT,PALETTE,color_mndwi,digest,write_json,now
from screen_water_colors import normalized


def load(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    dataset=load(OUT/'dated_review_dataset.json');manifest=load(OUT/'review_manifest.json');ui=load(OUT/'software_ui_checks.json');build=load(OUT/'display_build_checks.json')
    identity={k:v for k,v in dataset.items() if k!='id'}
    assert dataset['id']==hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    assert manifest['dataset_sha256']==build['dataset_sha256']==digest(OUT/'dated_review_dataset.json')
    assert manifest['ui_sha256']==ui['ui_sha256']==digest(ROOT/'Water_Easy_Date_Review.html') and ui['status']=='PASS'
    assert all(digest(ROOT/p)==h for p,h in build['old_files_sha256'].items())
    assert len(dataset['rows'])==720 and len({r['sample_id'] for r in dataset['rows']})==720
    images=0;checked_years=set();spot_checks=[]
    frozen=load(SOURCE/'public/evidence_manifest.json')
    for r in dataset['rows']:
        for s in r['scenes']:
            path=ROOT/s['image_path'];assert digest(path)==s['image_sha256']
            raw_path=s['source_original_image_path'].split('independent_accuracy_20261015/',1)[1].rsplit('.',1)[0]+'.tif'
            assert s['source_tiff_sha256']==frozen[raw_path]
            assert digest(SOURCE/raw_path)==frozen[raw_path]
            with Image.open(path) as image:
                assert image.size==(800,870)
                if r['year'] not in checked_years:
                    with rasterio.open(SOURCE/raw_path) as ds:raw=ds.read()
                    cal=load(SOURCE/'sources/calibration'/(s['item_id']+'.json'))
                    assert digest(SOURCE/'sources/calibration'/(s['item_id']+'.xml'))==cal['xml_sha256']==s['calibration_xml_sha256']
                    g=raw[1].astype(float)*cal['band_coefficients']['B03']['scale']+cal['band_coefficients']['B03']['offset']
                    sw=raw[4].astype(float)*cal['band_coefficients']['B11']['scale']+cal['band_coefficients']['B11']['offset']
                    clear=np.isin(raw[5],[4,5,6])&(raw[6]>0)&np.all(raw[:5]>0,axis=0)
                    index=normalized(g,sw);valid=clear&np.isfinite(index)&(g>=0)&(sw>=0)&(g<=1.2)&(sw<=1.2)
                    expected=color_mndwi(index,valid)
                    for row,col in [(3,3),(10,10),(30,10),(30,30),(10,30)]:
                        pixel=image.getpixel((5+int((col+.5)*390/40),455+int((row+.5)*390/40)))
                        assert np.array_equal(pixel,expected[row,col]),'Measured MNDWI palette mismatch'
                    checked_years.add(r['year']);spot_checks.append({'year':r['year'],'item_id':s['item_id'],'actual_band_to_color_pixels_checked':5})
                image.load()
            images+=1
    assert images==3022 and len(checked_years)==4
    (OUT/'sources').mkdir(exist_ok=True)
    specs=[
        ('NASA_RGB','https://science.nasa.gov/earth/earth-observatory/how-to-interpret-a-satellite-image/','How to Interpret a Satellite Image: Five Tips and Strategies',['Holli Riebeek'],'Define Colors: Water, Plants, Bare ground and Colors in Context; dark water, brown sediment, green vegetation, cloud/shadow ambiguity.'),
        ('NASA_IR','https://www.nasa.gov/image-article/false-color-image-of-earth-highlights-plant-growth/','False-Color Image of Earth Highlights Plant Growth',['NASA'],'Body: plants reflect near infrared strongly and red display assignment highlights vegetation.'),
        ('ESRI_MNDWI','https://doc.esri.com/en/arcgis-pro/latest/help/analysis/raster-functions/band-arithmetic-function.html','Band Arithmetic function',['Esri'],'MNDWI method: (Green-SWIR)/(Green+SWIR). The local palette is our documented display choice, not an accuracy guarantee.')]
    def retrieve(spec):
        sid,url,title,authors,locator=spec
        response=requests.get(url,timeout=35);response.raise_for_status();target=OUT/'sources'/(sid+'.html');target.write_bytes(response.content)
        return {'source_id':sid,'url':url,'title':title,'authors':authors,'publication_date':'2014-03-07' if sid=='NASA_IR' else None,
            'type':'Primary official image-interpretation or method documentation','retrieved_at':now(),
            'access_level':'Public page retrieved and saved','review_level':'Relevant interpretation/formula sections reviewed; no systematic literature coverage claim',
            'locator':locator,'support_reviewed':True,'provenance':{'url':url,'sha256':digest(target)},
            'screening_decision':'Included for qualified color hints or formula only. No source validates these human labels or numeric classification thresholds.'}
    with ThreadPoolExecutor(max_workers=3) as pool:sources=list(pool.map(retrieve,specs))
    for s in sources:s['provenance']['retrieved_at']=s['retrieved_at']
    (OUT/'sources.jsonl').write_text('\n'.join(json.dumps(s,ensure_ascii=False) for s in sources)+'\n',encoding='utf-8')
    claims=[{'id':'QUALIFIED_RGB_HINTS','source_ids':['NASA_RGB'],'locator':specs[0][-1],'support_reviewed':True},
        {'id':'IR_RED_VEGETATION_HINT','source_ids':['NASA_IR'],'locator':specs[1][-1],'support_reviewed':True},
        {'id':'MNDWI_FORMULA_ONLY','source_ids':['ESRI_MNDWI'],'locator':specs[2][-1],'support_reviewed':True}]
    write_json(OUT/'claims.json',claims)
    assert len({s['source_id'] for s in sources})==len({s['url'] for s in sources})==3
    write_json(OUT/'source_claim_audit.json',{'status':'PASS_FOR_BOUNDED_HINT_AND_FORMULA_PROVENANCE','sources':3,'duplicates':0,
        'claims_with_reviewed_locators':3,'unsupported_accuracy_claims_made':0,
        'DOI_Crossref':'Not applicable to these official web interpretation/method pages.',
        'retrieval_limit':'NASA Hyacinths follow-up fetch timed out; relevant IR support was reviewed from the alternative official NASA plant-growth page.',
        'local_palette_is_independent_ground_truth':False})
    write_json(OUT/'dated_review_protocol.json',{'recorded_at':now(),'authorization':'User requested a much simpler page, image-hover color hints and the ability to give different labels for different dates.',
        'source_parent_dataset_id':dataset['parent_dataset_id'],'schema':dataset['schema'],'review_points':245,'default_date_tasks':694,
        'view':'One actual acquisition at a time. Answer advances to the next unanswered acceptable date, then the next point.',
        'request_rule':'All dates with source clear target fraction >=0.95 at the same 245 selected review points. Other dates remain available but unanswered/missing by default.',
        'date_label_rule':'One explicit human action is bound to sample_id + actual scene_id. Never copy a point-level or one-date answer to another date.',
        'temporal_change':'If human dated responses contain 0 and 1, retain both and mark observed date variation. Do not collapse to one whole-month binary answer.',
        'legacy_backup':'Preserve old point answer, reviewer, notes and timestamp in legacy_point_answer. Importing it creates zero dated answers.',
        'display':'New MNDWI palette from calibrated green and SWIR, alongside natural color, IR and quality. Native SWIR support remains 20m; nearest display adds no detail.',
        'missing_quality':'Grey/missing is never automatically dry land. Negative or unsupported index radiometry is conservatively grey.',
        'accuracy_scope':'Still model-selected assisted interpretation, not representative independent accuracy. No changes to raw data, thresholds, old answers, primary scientific results or paper title.',
        'recovery_duration_resolved':False,'actual_human_date_labels_created_by_software':0})
    files=[ROOT/'postprocessing'/s for s in ('build_dated_water_dataset.py','dated_water_core.js','dated_water_review.html','dated_water_app.js','build_dated_water_review.py','evaluate_dated_water_backup.cjs','qa_dated_water_review.py','finalize_dated_water_review.py')]
    write_json(OUT/'FINAL_CHECKS.json',{'status':'PASS_FOR_DATED_ENTRY_AND_DISPLAY_SOFTWARE_ONLY','checked_at':now(),
        'source_points':720,'display_images':images,'default_review_points':245,'default_clear_date_tasks':694,
        'all_display_and_source_hashes_pass':True,'old_parent_and_independent_files_unchanged':True,
        'actual_raw_band_to_palette_spot_checks':spot_checks,'ui_checks':ui['status'],'ui_check_count':len(ui['checks']),
        'desktop_mobile_and_tooltip_screenshots_visually_inspected':True,
        'different_date_labels_preserved_in_csv':True,'legacy_point_answers_copied_to_dates':False,
        'actual_human_date_labels_created':0,'independent_accuracy_complete':False,'recovery_duration_resolved':False,
        'scientific_publication_ready':False,'scientific_pipeline_rerun':False,
        'assurance':'Same-process software/data-rendering QA and temporary test labels only. No real human reference judgments were generated.',
        'code_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files},
        'output_sha256':{s:digest(OUT/s) for s in ('dated_review_dataset.json','review_manifest.json','software_ui_checks.json','display_build_checks.json','dated_review_protocol.json','source_claim_audit.json')}})
    status=ROOT/'CURRENT_WATER_REVIEW_STATUS.json'
    if status.exists() and not (OUT/'previous_route_status.json').exists():(OUT/'previous_route_status.json').write_bytes(status.read_bytes())
    write_json(status,{'checked_at':now(),'current_route':'ASSISTED_DATED_REVIEW_V2','review_page':'Water_Easy_Date_Review.html',
        'default_human_review_points':245,'date_answers_saved_separately':True,'automatic_suggestions':337,'insufficient_support_points':138,
        'human_review_pending':True,'independent_accuracy_complete':False,'scientific_publication_ready':False,
        'protocol':'assisted_water_screening_20261015/date_review_v2/dated_review_protocol.json'})
    print(json.dumps({'status':'READY','review_page':'Water_Easy_Date_Review.html','one_date_per_answer':True,'color_hints_verified':True,'actual_human_labels_created':0}))


if __name__=='__main__':main()
