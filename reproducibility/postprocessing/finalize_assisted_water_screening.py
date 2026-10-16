"""Evidence/accounting audit of triage; explicitly rejects independent accuracy."""
from pathlib import Path
from collections import Counter
import hashlib,html,importlib.metadata,json,re,sys
import xml.etree.ElementTree as ET
from screen_water_colors import ROOT,SOURCE,OUT,RULES,classify_point,digest,write_json,now


def load(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    ds=load(OUT/'screening_dataset.json');report=load(OUT/'screening_report.json');ui=load(OUT/'review_manifest.json');qa=load(OUT/'software_ui_checks.json')
    identity={k:v for k,v in ds.items() if k!='id'}
    assert ds['id']==hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    assert ui['dataset_sha256']==digest(OUT/'screening_dataset.json')
    assert qa['status']=='PASS' and qa['ui_sha256']==ui['ui_sha256']==digest(ROOT/'Water_Only_Confused_Review.html')
    assert report['input_public_dataset_sha256']==digest(SOURCE/'public/review_dataset.json')
    assert report['source_evidence_manifest_sha256']==digest(SOURCE/'public/evidence_manifest.json')
    assert ds['rules']==RULES==load(OUT/'screening_rules.json')
    assert report['software_sha256']==digest(ROOT/'postprocessing/screen_water_colors.py')
    assert len(ds['rows'])==len({r['sample_id'] for r in ds['rows']})==720
    assert all(digest(ROOT/p)==h for p,h in report['prior_artifacts_sha256'].items())
    evidence=load(SOURCE/'public/evidence_manifest.json');calibrations=set();views=0
    for row in ds['rows']:
        assert row['screening']==classify_point(row['spectral_evidence'])
        assert len(row['scenes'])==len(row['spectral_evidence'])
        assert row['screening']['category']!='QUALITY_LIMITED' or row['screening']['automated_water'] is None
        for scene,spectral in zip(row['scenes'],row['spectral_evidence']):
            assert scene['item_id']==spectral['item_id'] and scene['date']==spectral['date']
            image_path=scene['image_path'].split('independent_accuracy_20261015/',1)[1]
            tiff_path=image_path.rsplit('.',1)[0]+'.tif'
            assert spectral['image_sha256']==scene['image_sha256']==evidence[image_path]
            assert spectral['tiff_sha256']==evidence[tiff_path]
            assert digest(SOURCE/image_path)==evidence[image_path] and digest(SOURCE/tiff_path)==evidence[tiff_path]
            calibrations.add(scene['item_id']);views+=1
    for item in calibrations:
        cal=load(SOURCE/'sources/calibration'/(item+'.json'));xml_path=SOURCE/'sources/calibration'/(item+'.xml')
        assert digest(xml_path)==cal['xml_sha256']
        xml=ET.fromstring(xml_path.read_bytes());quant=[float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_QUANTIFICATION_VALUE']
        offsets={e.attrib['band_id']:float(e.text) for e in xml.iter() if e.tag.split('}')[-1]=='BOA_ADD_OFFSET'}
        assert len(quant)==1 and quant[0]==cal['quantification_value']
        for band,band_id in {'B02':'1','B03':'2','B04':'3','B08':'7','B11':'11'}.items():
            assert cal['band_coefficients'][band]=={'scale':1/quant[0],'offset':offsets.get(band_id,0)/quant[0]}
    counts=Counter(r['screening']['category'] for r in ds['rows'])
    assert dict(counts)==report['counts'] and views==3022
    sources=[json.loads(s) for s in (OUT/'sources.jsonl').read_text(encoding='utf-8').splitlines()]
    for s in sources:
        content=(OUT/'sources'/(s['source_id']+'.html')).read_bytes()
        s['provenance']={'url':s['url'],'retrieved_at':s['retrieved_at'],'sha256':hashlib.sha256(content).hexdigest()}
        page_title=re.search(r'<title[^>]*>(.*?)</title>',content.decode('utf-8',errors='replace'),flags=re.I|re.S)
        assert page_title is not None
        s['retrieved_document_title']=html.unescape(re.sub(r'\s+',' ',page_title[1])).strip()
        assert s['title'].lower() in s['retrieved_document_title'].lower()
        s['metadata_verification']='Official organization URL, actual retrieved title and saved page; DOI/Crossref not applicable to this documentation.'
        s['doi']=None
    (OUT/'sources.jsonl').write_text('\n'.join(json.dumps(s,ensure_ascii=False) for s in sources)+'\n',encoding='utf-8')
    # The generic helper assumes Crossref article records, unlike these URL docs.
    # Preserve its non-applicable failure; never mark invented Crossref checks true.
    write_json(OUT/'generic_crossref_linter_attempt.json',{'status':'NOT_APPLICABLE_TO_URL_DOCUMENTATION',
        'observed_original_issues':['3 official web-document records lack crossref_metadata_verified','Retrieval was top-level rather than the helper nested provenance field','A project-defined heuristic-method statement had no external citations'],
        'resolution':'Preserve actual URL metadata with nested provenance. Keep only externally supported formula claims in the citation ledger; disclose project thresholds separately. Do not fabricate DOI or Crossref verification.',
        'failed_retrieval_attempt':'Sentinel Hub MNDWI endpoint unavailable through web tool. Official Esri formula documentation was retrieved and reviewed instead.'})
    claims=load(OUT/'claims.json');claims=[c for c in claims if c['id']!='HEURISTICS_UNVALIDATED'];write_json(OUT/'claims.json',claims)
    ids={s['source_id'] for s in sources};assert len(ids)==len(sources)==len({s['url'] for s in sources})==3
    assert all(c['source_ids'] and set(c['source_ids'])<=ids and c['support_reviewed'] and c['locator'] for c in claims)
    write_json(OUT/'source_claim_audit.json',{'status':'PASS_WITH_BOUNDED_URL_SCOPE','checked_at':now(),'sources':3,'duplicate_sources':0,
        'formula_claims_with_reviewed_locators':len(claims),'unsupported_external_claims':0,
        'project_thresholds_independently_validated':False,'DOI_Crossref_verification':'Not applicable: official web method documentation, no research-article metadata claim.',
        'complete_article_full_text_review_claimed':False,'threshold_accuracy_guarantee_supported':False,
        'limits':'Source structure/metadata checked locally; relevant formula support reviewed by the same assistant. Not independent scientific verification.'})
    write_json(OUT/'assisted_request_decision.json',{'recorded_at':now(),'authorization':'User requested color/band-based automatic screening and manual verification of confused cases only.',
        'current_route':'ASSISTED_MODEL_SELECTED_REVIEW','source_dataset_id':ds['source_dataset_id'],'screening_dataset_id':ds['id'],
        'previous_blinded_protocol_modified':False,'previous_label_or_scientific_output_files_modified':False,
        'same_720_sample_ids_used_for_assistance':True,
        'independence_disposition':'After model-selection/prediction exposure, subsequent review of these same samples must not be presumed blind independent. Dataset identity/schema guard prevents assisted backups entering independent evaluation.',
        'independent_reference_validation_complete':False,'recovery_duration_resolved':False,'manuscript_started':False,'publication_ready':False,
        'minimum_corrective_action_for_independent_accuracy':'Separately obtain a representative genuinely independent reference assessment of automatic and difficult cases with appropriate sampling/weights; do not calculate whole-frame accuracy from the selected difficult-case answers.'})
    artifacts=['screening_dataset.json','screening_rules.json','screening_report.json','review_manifest.json','software_ui_checks.json','source_claim_audit.json','assisted_request_decision.json']
    evidence_artifacts=[{'path':str((OUT/p).relative_to(ROOT)).replace('\\','/'),'kind':'triage data or bounded software/method evidence','source':'experiment','digest':digest(OUT/p)} for p in artifacts]
    evidence_paths=[e['path'] for e in evidence_artifacts]
    reasons={
        'protocol_integrity':('pass','All cases and thresholds are explicit, missing support is retained, and the change to assisted selection is recorded.'),
        'metric_validity':('fail','Triage counts are not accuracy. No representative independent reference denominator exists.'),
        'baseline_fairness':('not_assessed','No comparative performance or superiority experiment was requested or conducted.'),
        'outcome_accounting':('pass','All 720 samples, 3022 prepared views, all four categories and missing outcomes remain accounted for.'),
        'inferential_support':('fail','No independent labels or sampling uncertainty are available for automatic-case errors.'),
        'confound_control':('fail','Model-selected difficult-case review is selection-biased for whole-frame accuracy; image/band evidence is dependent.'),
        'provenance':('pass','Actual raw crops, native support, product calibration, acquisition dates, checksums and formula documentation retained.'),
        'snapshot_continuity':('pass','Earlier independent-review files, labels and frozen protocols retain original checksums. This is a new versioned route.'),
        'independence':('fail','Self-developed heuristic, self-QA and model-selected assisted interpretation provide no independent verification authority.')}
    audit_id='ASSISTED-TRIAGE-20261015'
    audit={'audit_id':audit_id,'claim_id':'ASSISTED_AS_REPRESENTATIVE_INDEPENDENT_ACCURACY',
        'claim_text':'Reviewing only model-uncertain cases can establish representative independent accuracy for all 720 sampled points or the wider study area.',
        'scope':'Four sampled monthly public frames and exploratory spectral triage v1; 337 automatic, 245 requested-review and 138 low-support points.',
        'source_mode':'standalone','requested_assurance_class':'exploratory','attained_assurance_class':'none',
        'verdict':'does_not_support_claim','audited_claim_effect':'kill','source_runs':[],
        'run_selection':{'selection_rule':'Include the single complete local spectral-triage-v1 dataset and its complete four-way outcome accounting. No orchestrator run/independent verifier exists.','excluded_runs':[],
            'included_local_artifact_run':ds['id']},'evidence_artifacts':evidence_artifacts,
        'check_results':[{'check_id':k,'status':s,'rationale':r,'evidence_paths':evidence_paths} for k,(s,r) in reasons.items()],
        'independence':{'self_review':True,'dimensions':[],'evidence':'Same-assistant implementation, local raw-data checks and isolated software QA; human review is selected using the model.'},
        'limitations':report['limitations'],
        'predecessor_failures':[{'failure_id':'REFERENCE-GAP','status':'open','rationale':'Independent human accuracy remains incomplete; assisted screening reduces workload without resolving this gap.'},
            {'failure_id':'UI-QA-AUTONEXT-ASSUMPTION','status':'resolved','rationale':'First QA assertion read the next sample after a page reload reset the auto-next checkbox. The test explicitly disabled auto-next for inspection; final UI QA passed. No research outcome was changed.'},
            {'failure_id':'GENERIC-CROSSREF-LINTER','status':'accepted_with_narrowing','rationale':'The generic helper expects Crossref article records. Official documentation was audited by actual URL/title/page hash and locators instead; no Crossref verification fabricated.'}],
        'minimum_corrective_action':'For independent accuracy, add a separately designed representative independent reference evaluation, including automatic cases. Treat this route as assisted screening/correction only.',
        'narrative_anchor':'## Audit '+audit_id}
    write_json(OUT/'results-audit.json',{'schema_version':'1.0','paper_id':'nw-bangladesh-climate-adjusted-water','identity_version':1,'status':'complete','audits':[audit]})
    narrative='\n'.join(['# Assisted triage result audit','',audit['narrative_anchor'],'','- Bounded verdict: does_not_support_claim',
        '- Claim: '+audit['claim_text'],'- Requested assurance: exploratory; attained assurance: none.','',
        'The software/data-preparation checks passed for a workload-reduction tool. They do not support the independent-accuracy claim. All 720 points remain represented; automatic guesses and human-assisted answers are separate. Human answers are currently absent.','',
        '## Required checks','']+[f'- {k}: {s}. {r}' for k,(s,r) in reasons.items()]+['',
        'Self-review is disclosed. The 337 automatic cases have no independent reference checks. The 245-case queue is model-selected, so its reviewed error distribution cannot be extended to the full frame. The 138 unsupported cases remain missing, never dry land.','',
        'The earlier blinded protocol files are preserved, but after assisted exposure the same cases must not be presumed blind. Recovery duration remains unknown. No manuscript or submission-readiness result was created.','',
        'Corrective action: '+audit['minimum_corrective_action'],''])
    (OUT/'results-audit.md').write_text(narrative,encoding='utf-8')
    distributions=['numpy','rasterio','shapely','pyproj','Pillow','playwright']
    write_json(OUT/'environment.json',{'python':sys.version,'executable':sys.executable,'packages':{name:importlib.metadata.version(name) for name in distributions},'existing_environment_preserved':True})
    files=[ROOT/'postprocessing'/s for s in ('screen_water_colors.py','assisted_water_core.js','assisted_water_app.js','assisted_water_review.html','build_assisted_water_review.py','evaluate_assisted_water_backup.cjs','qa_assisted_water_review.py','finalize_assisted_water_screening.py')]
    checks={'status':'PASS_FOR_SOFTWARE_AND_EXPLORATORY_TRIAGE_ONLY','checked_at':now(),'points':720,'actual_date_views':views,
        'counts':dict(counts),'all_raw_and_image_hashes_match_frozen_source_manifest':True,'calibration_xml_files_checked':len(calibrations),
        'quality_limited_cases_turned_to_nonwater':0,'previous_artifacts_unchanged':True,'ui_checks':qa['status'],
        'focused_tests_observed':'Seven Python numerical/triage fixtures and Node provenance/import/export fixtures passed in this task; isolated UI QA passed eight checks.',
        'software_tests_are_real_human_labels':False,'actual_human_labels_created':0,'independent_accuracy_complete':False,
        'representative_accuracy_from_selected_queue_supported':False,'scientific_publication_ready':False,
        'code_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files},
        'output_sha256':{p:digest(OUT/p) for p in artifacts+['results-audit.json','results-audit.md']}}
    write_json(OUT/'FINAL_CHECKS.json',checks)
    status={'checked_at':now(),'current_route':'ASSISTED_SPECTRAL_TRIAGE','review_page':'Water_Only_Confused_Review.html','default_human_queue':245,
        'automated_suggestions':337,'insufficient_support_missing':138,'human_review_pending':True,
        'independent_accuracy_complete':False,'scientific_publication_ready':False,'decision':'assisted_water_screening_20261015/assisted_request_decision.json'}
    write_json(ROOT/'CURRENT_WATER_REVIEW_STATUS.json',status)
    print(json.dumps({'preparation_status':checks['status'],'counts':dict(counts),'prior_inputs_preserved':True,'actual_human_labels_created':0}))


if __name__=='__main__':main()
