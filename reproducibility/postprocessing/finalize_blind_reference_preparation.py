"""Link completed integrity and UI checks, leaving scientific human gates pending."""
import json,subprocess,sys
from pathlib import Path
from prepare_blind_accuracy import ROOT,OUT,write_json,digest,now


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf-8'))
    checks=load(OUT/'FINAL_CHECKS.json');manifest=load(OUT/'review_manifest.json')
    qa=load(OUT/'software_ui_checks.json');sample=load(OUT/'sample_and_calibration_checks.json')
    assert checks['preparation_status']=='PASS' and qa['status']==sample['status']=='PASS'
    assert checks['point_scene_pairs']==manifest['point_scene_pairs']==3022
    assert manifest['ui_sha256']==qa['ui_sha256']==digest(ROOT/'Water_Independent_Accuracy_Review.html')
    for p,h in manifest['frozen_evaluation_inputs_sha256'].items():assert digest(OUT/p)==h
    for p,h in manifest['software_sha256'].items():assert digest(ROOT/p)==h
    assert sample['fresh_points']==720 and sample['old_exact_pixel_period_overlap']==0
    assert sample['old_user_answer_and_pilot_hashes_rechecked']>0
    reports=[]
    for command in [['node','tests/test_blind_accuracy_core.cjs'],[sys.executable,'-m','unittest','discover','-s','tests','-p','test_blind_accuracy_evaluation.py','-v']]:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        reports.append({'command':command,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        if result.returncode:raise RuntimeError('Focused reference software check failed')
    write_json(OUT/'software_test_checks.json',{'status':'PASS','checked_at':now(),'scope':'Software and numerical fixtures only, no study labels','commands':reports})
    protocol=load(OUT/'validation_protocol.json');quality=load(OUT/'quality_preflight.json')
    protocol['completed_pre_human_quality_preflight']={k:quality[k] for k in ('quality_eligible_points','quality_limited_points','strata_below_existing_minimum_even_before_human_uncertainty','all_stratum_minima_achievable_with_current_evidence')}
    protocol['existing_minimum_count_rule_preserved_despite_shortfall']=True
    protocol['pooled_estimand']='Area-time weighted agreement across the four observed monthly sampling frames, excluding old exposed cells. No random-verification/nonresponse assumption.'
    write_json(OUT/'validation_protocol.json',protocol)
    initial=dict(checks)
    write_json(OUT/'completed_integrity_audit_snapshot.json',initial)
    checks['finalized_at']=now()
    checks['ui_sha256']=manifest['ui_sha256']
    checks['sampling_reproduction_and_calibration_checks']='sample_and_calibration_checks.json'
    checks['focused_software_tests']='software_test_checks.json'
    checks['final_visual_inspection']='Desktop and mobile page screenshots inspected; legible Bangla, image dates, yellow boundary, controls and help verified. No water decisions supplied.'
    checks['integrity_evidence_rechecked_by_build']='The final build rechecked all 6044 TIFF/PNG hashes against the same evidence records; full grid/quality audit retained in completed_integrity_audit_snapshot.json.'
    files=sorted((ROOT/'postprocessing').glob('*blind_accuracy*'))+[
        ROOT/'postprocessing/check_blind_reference_sampling.py',ROOT/'postprocessing/finalize_blind_reference_preparation.py',
        ROOT/'tests/test_blind_accuracy_core.cjs',ROOT/'tests/test_blind_accuracy_evaluation.py']
    checks['code_sha256']={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files if p.is_file()}
    checks['audit_report_sha256']={p:digest(OUT/p) for p in ('completed_integrity_audit_snapshot.json','review_manifest.json','software_ui_checks.json','sample_and_calibration_checks.json','software_test_checks.json','quality_preflight.json','validation_protocol.json')}
    assert checks['human_reference_labels_created_by_software']==0
    assert checks['independent_accuracy_complete'] is False and checks['scientific_publication_ready'] is False
    write_json(OUT/'FINAL_CHECKS.json',checks)
    print(json.dumps({'preparation_status':'PASS','review_page_ready':True,'human_reference_pending':True,
        'accuracy_complete':False,'recovery_duration_known':False,'reference_count_capacity_shortfall_strata':quality['strata_below_existing_minimum_even_before_human_uncertainty']}))


if __name__=='__main__':main()
