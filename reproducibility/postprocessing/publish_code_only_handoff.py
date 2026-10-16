"""Publish a bounded writing handoff after real analysis, tests and visual QA.

Does not run a scientific pipeline or manufacture missing scientific checks.
"""
from copy import deepcopy
import argparse
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'code_only_final_20261016'
OUT = PACK / 'analysis_v2'
sys.path.insert(0, str(ROOT))
from postprocessing.finalize_code_only_research import digest, read, write, require


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis',type=Path,default=OUT)
    parser.add_argument('--label-revision',type=Path)
    args=parser.parse_args()
    OUT=args.analysis.resolve()
    require(PACK.resolve() in OUT.parents,'Active analysis must remain inside the final package')
    active_rel=OUT.relative_to(PACK).as_posix()
    result, run = read(OUT / 'RESULTS.json'), read(OUT / 'RUN_MANIFEST.json')
    require(result['status'] == 'COMPUTATIONAL_ANALYSIS_COMPLETE_WITH_RESTRICTED_CLAIMS', 'Analysis not complete')
    require(run['script_sha256'] == digest(ROOT / 'postprocessing/finalize_code_only_research.py'), 'Analysis code changed after run')
    tests = read(PACK / 'SOFTWARE_TESTS.json')
    visual = read(PACK / 'qa/visual_review.json')
    research = read(PACK / 'research/source_claim_audit.json')
    require(tests['python']['exit_code'] == tests['node']['exit_code'] == 0, 'Software tests not successful')
    require(visual['new_figure_full_size_reviewed'] and visual['contact_sheet_figures_reviewed'] == 12, 'Visual review incomplete')
    require(all(research['checks'].values()), 'Recorded method-source checks not complete')
    for rel, h in run['protected_inputs_sha256'].items():
        if rel == 'CURRENT_WATER_REVIEW_STATUS.json':
            snapshot=OUT/'workflow_status_at_analysis_start.json'
            if not snapshot.exists():snapshot=PACK/'workflow_status_before_code_only_final.json'
            require(digest(snapshot) == h, 'Original workflow snapshot changed')
            continue
        require(digest(ROOT / rel) == h, 'Protected artifact changed before handoff: ' + rel)
    points = pd.read_csv(OUT / 'Tables/pixel_month_comparisons.csv')
    summaries = pd.read_csv(OUT / 'Tables/proxy_agreement_and_unknown_ranges.csv')
    require(len(points) == 720 and points.sample_id.nunique() == 720 and len(summaries) == 88, 'Full-frame or subgroup accounting changed')
    for proxy, route in [('automated_proxy','AUTOMATED_S2_PROXY_ONLY'),('assisted_proxy','ASSISTED_S2_PROXY')]:
        p = points[proxy].notna()
        total = math.fsum(points.design_weight_km2_month)
        known = math.fsum(points.loc[p,'design_weight_km2_month'])
        matching = math.fsum(points.loc[p & points[proxy].eq(points.jrc_monthly_binary_class),'design_weight_km2_month'])
        r = summaries[summaries.route.eq(route) & summaries.frame.eq('ALL_FOUR_MONTHS')].iloc[0]
        require(math.isclose(r.conditional_label_agreement, matching/known, rel_tol=1e-12), 'Direct conditional ratio check failed')
        require(math.isclose(r.binary_completion_lower, matching/total, rel_tol=1e-12), 'Direct lower range check failed')
        require(math.isclose(r.binary_completion_upper, (matching+total-known)/total, rel_tol=1e-12), 'Direct upper range check failed')
    require(points.independent_reference_water.isna().all(), 'False independent references in output')
    hybrid = next(r for r in result['proxy_comparison'] if r['route'] == 'ASSISTED_S2_PROXY')
    previous = result['previous_results_reconciled']
    outcome_counts={r['assisted_origin']:int(r['samples']) for r in result['all_point_outcome_counts']}
    human_counts=result['human_assisted_review']['human_answer_counts']
    label_revision=read(args.label_revision) if args.label_revision else None
    if label_revision:
        require(digest(Path(label_revision['new_csv']))==label_revision['new_csv_sha256'],'Corrected CSV changed after authorized revision')
        require(digest(Path(label_revision['new_backup']))==label_revision['new_backup_sha256'],'Corrected backup changed after authorized revision')
        require(Path(run['actual_human_csv']).resolve()==Path(label_revision['new_csv']).resolve(),'Analysis did not use revised CSV')
        require(Path(run['actual_human_backup']).resolve()==Path(label_revision['new_backup']).resolve(),'Analysis did not use revised Backup')
        write(PACK/'LATEST_LABEL_REVISION.json',label_revision)
    seasonal = next(r for r in previous['annual_endpoints_union'] if r['source_class'] == 'seasonal')
    permanent = next(r for r in previous['annual_endpoints_union'] if r['source_class'] == 'permanent')
    cv = pd.read_csv(OUT / 'Tables/annual_predictive_validation_summary.csv')
    scv = cv[cv.source_class.eq('seasonal')]
    require(len(scv) == 4 and scv.mean_fold_rmse.gt(scv.mean_fold_baseline_rmse).all(), 'Predictive model limitation changed')
    now = datetime.now(timezone.utc).isoformat()
    decision = {
        'paper_id':'nw-bangladesh-climate-adjusted-water', 'recorded_at':now,
        'working_title':read(PACK / 'protocol.json')['working_title'],
        'authorization':'Current user explicitly asks to finish and finalize the work achievable by code, then notify them to begin writing.',
        'prior_manual_sample_size_plan':'accuracy_sample_size_20261016/sample_size_calculation.json',
        'prior_600_reference_plan_status':'Optional independent-accuracy planning scenario, not executed and not required for this code-only manuscript scope.',
        'chosen_scope':'Source-class changes, exploratory climate-adjusted associations, automated product agreement, threshold/observation uncertainty and recovery non-identifiability.',
        'independent_reference_accuracy_claim':'Excluded; not established by these computations.',
        'recovery_time_claim':'Excluded; observed support cannot identify durations.',
        'manual_actions_required_for_chosen_scope':[], 'new_downloads_required_for_completed_computations':[],
        'assisted_review_preserved':True, 'independent_accuracy_complete':False,
        'recovery_duration_resolved':False, 'scientific_publication_ready':False,
        'manuscript_writing_ready_within_scope':True,
        'writing_readiness_means':'Begin a manuscript with these exact bounded results and limitations; external scientific review and journal fit are not certified.',
        'prior_scope_artifact_preserved':'paper_scope_20261015/paper_scope.json',
    }
    write(PACK / 'scope_decision.json', decision)
    claims = [
        ('ANNUAL-SEASONAL', 'Seasonal source-class area fell by 25.42% between 2000 and 2021 on the 1276.41 km2 common-observation footprint.',
         'supports_exploratory_follow_up', 'exploratory', 'Tables/primary_endpoint_changes.csv',
         'Source-class endpoint difference, not error-adjusted true water extent or whole administrative district area.'),
        ('CLIMATE-ASSOCIATION', 'The negative annual seasonal-class time coefficient in Naogaon and Rajshahi remains in the exploratory observation-effort and 2016 asset-boundary specification.',
         'supports_exploratory_follow_up', 'exploratory', 'Tables/annual_observation_effort_climate_sensitivity.csv',
         'Conditional exploratory association, n=22 annual records; not causal pumping attribution. Seasonal prediction does not improve mean CV RMSE over its training-mean benchmark.'),
        ('PERMANENT-ROBUST-RISE', 'The permanent-class endpoint increase establishes a robust continuing physical-water increase.',
         'does_not_support_claim', 'none', 'Tables/annual_observation_effort_climate_sensitivity.csv',
         'All permanent time-coefficient intervals include zero after the 2016-boundary sensitivity. A boundary control can absorb real hydrological steps too.'),
        ('RADAR-ENVELOPE', 'Both Rajshahi baseline-seasonal radar-envelope endpoint time coefficients are positive in the specified 2015-2024 exploratory models.',
         'supports_exploratory_follow_up', 'exploratory', 'Tables/exploratory_climate_envelope_models.csv',
         'Logit method-envelope fraction/year, n=90. Different period, support, class cohort and sensor than the primary annual analysis; not true-water area or causal effect.'),
        ('AGREEMENT-SUPPORT', 'The four fixed DW threshold comparisons exhibit increasing conditional SAR/DW agreement alongside decreasing paired footprint.',
         'supports_exploratory_follow_up', 'exploratory', 'Tables/dw_threshold_support_and_agreement.csv',
         'No threshold was selected. The denominator is paired area-month, with shared optical dependence and SAR classification error remaining.'),
        ('PROXY-UNKNOWNS', 'The final 720-point comparison retains all unknowns and quantifies conditional proxy agreement plus a binary-completion range.',
         'supports_exploratory_follow_up', 'exploratory', 'Tables/proxy_agreement_and_unknown_ranges.csv',
         'Four frozen months only; assisted labels are selected, automatic labels are heuristic, ranges are not physical-accuracy intervals.'),
        ('INDEPENDENT-ACCURACY', 'Code-generated or model-assisted labels establish representative independent water-classification accuracy.',
         'does_not_support_claim', 'none', 'Tables/pixel_month_comparisons.csv',
         'No separate representative independent references exist. No accuracy percentage is certified; the manual protocol was not silently relaxed.'),
        ('RECOVERY-DURATION', 'The available observations identify a reliable time to water recovery after drought.',
         'does_not_support_claim', 'none', 'Tables/exploratory_recovery_support_sensitivity.csv',
         'All 108 primary event-cohort records and all nine sensitivity specifications lack identifiable duration. This is not no recovery or zero recovery time.'),
    ]
    audits = []
    check_names = ['protocol_integrity','metric_validity','baseline_fairness','outcome_accounting','inferential_support','confound_control','provenance','snapshot_continuity','independence']
    evidence_base = [PACK / 'protocol.json', OUT / 'RESULTS.json', OUT / 'RUN_MANIFEST.json', PACK / 'research/source_claim_audit.json']
    for cid, claim, verdict, assurance, table, limitation in claims:
        artifacts = evidence_base + [OUT / table]
        paths = [str(p.relative_to(ROOT)).replace('\\','/') for p in artifacts]
        unsupported = verdict == 'does_not_support_claim'
        statuses = {
            'protocol_integrity':('pass','Protocol, source frames, post-outcome exploratory status and no-new-label route are explicit.'),
            'metric_validity':('fail' if unsupported else 'pass', limitation),
            'baseline_fairness':('pass' if cid=='CLIMATE-ASSOCIATION' else 'not_assessed', 'Existing chronological CV benchmark is retained; no superiority claim or best-threshold selection is made.'),
            'outcome_accounting':('pass','All sampled points, unknowns, thresholds, subgroups and recovery specification outcomes are retained.'),
            'inferential_support':('inconclusive' if unsupported else 'pass','Only the displayed estimand and reported uncertainty are supported; no physical-truth validation is inferred. '+limitation),
            'confound_control':('inconclusive','Measured climate/effort/version sensitivities cannot remove all reference, timing, cohort-selection or causal confounding.'),
            'provenance':('pass',f"{result['source_files_verified']} declared source/evidence hashes verified; actual acquisition IDs and versioned human decisions retained. Explicit user-directed revisions are recorded separately from image-view attestations."),
            'snapshot_continuity':('pass','Original source/result hashes and protected labels verified; first same-data run retained as a superseded numerical draft.'),
            'independence':('fail','Same-assistant audit and implementation; labels/model selection remain assisted and no independent evaluation authority exists.'),
        }
        audits.append({
            'audit_id':'FINAL-'+cid+'-20261016','claim_id':cid,'claim_text':claim,
            'scope':'Exact period/cohort/estimator described in the cited table and frozen protocol; no extrapolation to other years, domains or physical truth.',
            'source_mode':'standalone','requested_assurance_class':'exploratory','attained_assurance_class':assurance,
            'verdict':verdict,'audited_claim_effect':'kill' if unsupported else 'strengthen', 'source_runs':[],
            'run_selection':{'selection_rule':'Include completed annual analysis, complete DW sensitivity run and this entire final 720-point secondary analysis; do not select favorable thresholds or districts.',
                             'excluded_runs':[{'run_id':'CODE_ONLY_INITIAL_NUMERICAL_DRAFT','rationale':'Same-data preliminary analysis retained in analysis/. Superseded by analysis_v2 with explicit degenerate-bootstrap handling, roundoff clipping and all recovery interval-column checks; no threshold, sample or human answer changed.'}]},
            'evidence_artifacts':[{'path':path,'kind':'actual result, protocol or provenance','source':'experiment','digest':digest(p)} for path,p in zip(paths,artifacts)],
            'check_results':[{'check_id':name,'status':statuses[name][0],'rationale':statuses[name][1],'evidence_paths':paths} for name in check_names],
            'independence':{'self_review':True,'dimensions':[],'evidence':'Same-assistant computation, source reading and result audit; no separate advancement or evaluation authority.'},
            'limitations':[limitation, 'Exploratory evidence; no publication guarantee, physical-water accuracy certification or first-study claim.'],
            'predecessor_failures':[
                {'failure_id':'INDEPENDENT-REFERENCE-GAP','status':'accepted_with_narrowing','rationale':'Gap remains scientific uncertainty. User authorizes code-only scope; independent-accuracy claim is excluded rather than falsely completed.'},
                {'failure_id':'RECOVERY-OBSERVATION-GAP','status':'accepted_with_narrowing','rationale':'All sensitivity records retain missing timing. Recovery duration is removed from supported result claims.'}],
            'minimum_corrective_action':'Keep the exact bounded claim and limitation. Stronger physical accuracy or recovery claims require new suitable independent/continuous observations, which are not required user tasks in this chosen scope.',
            'narrative_anchor':'## Audit FINAL-'+cid+'-20261016',
        })
    audit = {'schema_version':'1.0','paper_id':'nw-bangladesh-climate-adjusted-water','identity_version':1,'status':'complete','audits':audits}
    write(PACK / 'results-audit.json',audit)
    narrative = '# Results audit\n\nSame-assistant, standalone evidence audit. Structural checks do not constitute independent scientific verification.\n\n'
    for a in audits:
        narrative += f"{a['narrative_anchor']}\n\n- Claim ID: {a['claim_id']}\n- Bounded verdict: {a['verdict']}\n- Attained assurance class: {a['attained_assurance_class']}\n\n{a['claim_text']}\n\n{a['limitations'][0]}\n\n"
    (PACK / 'results-audit.md').write_text(narrative,encoding='utf-8')
    validator = Path('C:/Users/Admin/.codex/skills/research-results-auditor/scripts/validate_results_audit.py')
    checked = subprocess.run([sys.executable,str(validator),'--audit',str(PACK/'results-audit.json'),'--narrative',str(PACK/'results-audit.md')],capture_output=True,text=True,encoding='utf-8')
    (PACK / 'result_audit_validator.txt').write_text(checked.stdout+checked.stderr,encoding='utf-8')
    require(checked.returncode == 0,'Result audit structural validator failed: '+checked.stdout+checked.stderr)
    # Close the temporary writing-readiness state in the numerical run only
    # after the actual post-analysis gates above have completed.
    result.update(manuscript_writing_ready=True, manuscript_writing_scope='Restricted proxy/source-class and observation-uncertainty manuscript only; not submission readiness')
    result.pop('writing_readiness_pending',None)
    write(OUT / 'RESULTS.json',result)
    write(OUT / 'STATUS.json',{'status':result['status'],'manuscript_writing_ready':True,'scientific_publication_ready':False,
                              'final_handoff':'../PAPER_HANDOFF.md'})
    for a in audit['audits']:
        for artifact in a['evidence_artifacts']:
            if artifact['path'].endswith(active_rel+'/RESULTS.json'):
                artifact['digest']=digest(OUT / 'RESULTS.json')
    write(PACK / 'results-audit.json',audit)
    refreshed = subprocess.run([sys.executable,str(validator),'--audit',str(PACK/'results-audit.json'),'--narrative',str(PACK/'results-audit.md')],capture_output=True,text=True,encoding='utf-8')
    (PACK / 'result_audit_validator.txt').write_text(refreshed.stdout+refreshed.stderr,encoding='utf-8')
    require(refreshed.returncode == 0, 'Final updated audit failed validation')
    write(PACK / 'claim_evidence_map.json',[
        {'claim_id':cid,'claim':claim,'disposition':'excluded_from_positive_results' if verdict=='does_not_support_claim' else 'allowed_with_scope',
         'evidence_table':active_rel+'/'+table,'scope_limit':limit,'audit_id':'FINAL-'+cid+'-20261016'}
        for cid,claim,verdict,assurance,table,limit in claims])
    report = f'''# কোড দিয়ে চূড়ান্ত বিশ্লেষণ: সহজ ফল

**এই নির্ধারিত scope-এ paper লেখা শুরু করা যাবে। নতুন manual label বা নতুন download এখন প্রয়োজন নেই।** এটি সীমিত ফল নিয়ে লেখার অনুমতি-সংক্রান্ত workflow সিদ্ধান্ত; submission বা publication readiness-এর সনদ নয়।

শিরোনাম: **Climate-adjusted surface-water changes and observation uncertainty in northwestern Bangladesh**

## কী পাওয়া গেছে

১. ২০০০–২০২১-এর একই {previous['annual_common_support_km2']:.2f} km² common-observation footprint-এ seasonal source-class এলাকা {seasonal['area_2000_km2']:.2f} থেকে {seasonal['area_2021_km2']:.2f} km² হয়েছে: **{abs(seasonal['endpoint_change_pct']):.2f}% কম**। এটি পুরো তিন জেলার সব পানির error-adjusted হিসাব নয়।

২. নওগাঁ ও রাজশাহীর seasonal-class-এর negative time association climate, observation effort ও ২০১৬ processing-boundary sensitivity-তেও থাকে। তবে seasonal climate models-এর mean fold RMSE চারটি region/union summary-তেই training-mean baseline-এর চেয়ে খারাপ। তাই model-কে ভালো forecasting system বা মানুষের কাজের causal প্রমাণ বলা যাবে না।

৩. Permanent source-class-এর দুই endpoint-এর পার্থক্য +{permanent['endpoint_change_pct']:.2f}% হলেও processing-boundary sensitivity-এর পরে নিয়মিত বৃদ্ধির পরিষ্কার প্রমাণ নেই। এটি স্থায়ী পানির নিশ্চিত বৃদ্ধি হিসেবে paper-এর headline হবে না।

৪. ২০১৫–২০২৪-এর আলাদা radar cohort-এ রাজশাহীর seasonal-envelope endpoint-এর positive association আছে। এটি annual JRC seasonal decline-কে বাতিল করে না: period, footprint, sensor ও measured quantity আলাদা। সব district, cohort ও threshold-এর ফল রাখা হয়েছে।

## আগের manual কাজ কী হলো

তোমার **২৪৫টি জায়গার ৬৯৪টি dated answer সম্পূর্ণ** আছে। {human_counts.get('1',0)}টি পানি, {human_counts.get('0',0)}টি পানি নেই, {human_counts.get('UNCERTAIN',0)}টি অনিশ্চিত। একই তারিখের উত্তর অন্য তারিখে কপি করা হয়নি।

পুরো ৭২০টি sample-এর মধ্যে **{outcome_counts.get('AUTO_SCREENED',0)}টি automatic proxy + {outcome_counts.get('HUMAN_DATES_CONSISTENT',0)}টি consistent assisted interpretation = {hybrid['assigned_samples']}টি assigned sample**। বাকি **{hybrid['unassigned_samples']}টি** অনির্ধারিত: {outcome_counts.get('UNRESOLVED_QUALITY',0)}টির পর্যাপ্ত dated support নেই, {outcome_counts.get('HUMAN_TEMPORAL_CHANGE',0)}টির বিভিন্ন তারিখের উত্তর আলাদা, {outcome_counts.get('HUMAN_UNCERTAIN_DATES',0)}টির উত্তর অনিশ্চিত। অনির্ধারিতগুলোকে শুকনা জমি বানানো হয়নি।

Sampling weights ধরলে assigned comparison চারটি নির্ধারিত মাসের frame-এর **{100*hybrid['assigned_design_weight_fraction']:.2f}%**। ওই assigned অংশে JRC/proxy label agreement **{100*hybrid['conditional_label_agreement']:.2f}%**। এই সংখ্যা independent accuracy নয়। সব unknown comparison weight রাখলে binary-completion agreement range **{100*hybrid['binary_completion_lower']:.2f}–{100*hybrid['binary_completion_upper']:.2f}%**; এটি physical-water accuracy interval নয়।

Automatic-only subset-এ সব assigned label JRC-এর সঙ্গে মিলে গেলেও সেটি সীমিত selected support। Empirical bootstrap-এ variation না থাকলে [100,100] confidence বলে দেখাইনি; interval unavailable ও degenerate flag রাখা হয়েছে। ২০০০ bootstrap-এ pixel–month-ই unit, ছবির তারিখ নয়।

## খরার পরে পানি ফেরার সময়

**নির্ভরযোগ্য সময় পাওয়া যায়নি।** ১০৮টি primary event–cohort record এবং ৯টি sensitivity specification-এর সব duration খালি আছে। অর্থ পানি ফেরেনি নয়। বর্তমান paper-এ এই observation limitation থাকবে, recovery-time estimate বা causal recovery claim থাকবে না।

## যাচাই ও ফাইল

{result['source_files_verified']}টি declared source/evidence file-এর hash মিলেছে। নতুন ১,৪৪০ export row থেকে ৫,৭৬০ threshold row আবার হিসাব করে আগের ফল মিলেছে। {tests['python']['passed']}টি Python test ও {tests['node']['passed']}টি Node test pass; এগুলো software checks, ground truth নয়। ১২টি figure-এর contact sheet ও নতুন figure দেখা হয়েছে। Original labels, source data ও পূর্বের protocol সংরক্ষিত; ব্যবহারকারীর নির্দেশের সংশোধন থাকলে তা আলাদা version-এ আছে।

Methods-এর bounded research note: [METHOD_RESEARCH.md](METHOD_RESEARCH.md)। পদ্ধতিগত article-এ [Olofsson et al. 2014](https://doi.org/10.1016/j.rse.2014.02.015), [Brown et al. 2022](https://doi.org/10.1038/s41597-022-01307-4) এবং প্রাসঙ্গিক [Saunders et al. 2025](https://doi.org/10.1029/2025EF005966) ব্যবহৃত হয়েছে। এগুলো স্থানীয় accuracy সংখ্যা দেয়নি। Metadata/source access ও claim locators `research/`-এ; ব্যবহৃত procedural skill-এর software acknowledgement-ও সেখানে রাখা হয়েছে।

লেখার পরিকল্পনা ও কোন দাবি ব্যবহার করা যাবে: [PAPER_HANDOFF.md](PAPER_HANDOFF.md)। সব numerical result: `analysis_v2/RESULTS.json`; Tables ও Figures একই directory-তে। কোনো target journal, novelty priority বা acceptance guarantee পরীক্ষা করা হয়নি।
'''
    if label_revision:
        report+='\n## ব্যবহারকারীর নির্দেশের সংশোধন\n\nনমুনা ১৪৪-এর ২০২৩-০৩-৩০ তারিখের উত্তর 0 থেকে 1 হয়েছে। এটি code-এর ফল জানার পরে ব্যবহারকারীর explicit correction; নতুন independent image verification নয়। Original CSV ও Backup অক্ষত। কোডের undecided ৪৫৪টি তারিখে existing human answer-ই আছে: ৩১৩টি পানি, ১৪১টি পানি নেই; code ওই label-গুলোকে স্বাধীনভাবে নিশ্চিত করেনি।\n'
    (PACK / 'FINAL_RESULT_BN.md').write_text(report.replace('analysis_v2/',active_rel+'/'),encoding='utf-8')
    handoff = '''# Manuscript writing handoff

Working title: **Climate-adjusted surface-water changes and observation uncertainty in northwestern Bangladesh**.

This package closes the currently requested computational route. Begin writing Methods and Results with `claim_evidence_map.json` and `results-audit.json`. Independent accuracy is not established; it is outside the positive claims of this chosen scope. The earlier optional 600-reference planning scenario has not been executed and is not a required next user task. A manuscript has not been drafted, journal fit has not been evaluated, and submission readiness is not certified.

## Paper structure and exact evidence

1. **Study area and data:** Naogaon, Chapainawabganj and Rajshahi. Primary JRC source-class analysis: 2000-2021 common-observation footprint. The source-version sensitivity extends to 2024. SAR/DW supplement: 2015-2024, different retrospective ever-water/cohort domains. Do not combine these into a single water trend. Preserve asset IDs, processing steps, source versions, real scene dates and hashes from original METHODS.md, run manifests and the archived download inventories.
2. **Primary results:** `analysis_v2/Tables/primary_endpoint_changes.csv`, `annual_common_support_water.csv` and `annual_trend_results.csv`. State the exact 1276.41 km2 restricted annual footprint; distinguish endpoint class-area change from physical-water area, volume, hydroperiod and causal attribution.
3. **Climate association and controls:** `annual_climate_model_coefficients.csv` and `annual_observation_effort_climate_sensitivity.csv`. Include all regions, permanent-class non-robustness after the 2016 step, pointwise intervals, district-family multiplicity adjustment and the weakness of seasonal predictive performance in `annual_predictive_validation_summary.csv`. CV compares against a training-only mean, not an independently observed water truth. Use original METHODS.md for model terms, logit transformation, annual HAC lag 2 and limitations of 22 annual observations.
4. **Automated product sensitivity:** `dw_threshold_support_and_agreement.csv` plus `exploratory_climate_envelope_models.csv`; keep all four thresholds and all cohorts, including no-support cases. Explain probability support, paired-support denominators and logit fraction/year units. The 0.7 threshold's 98.71% SAR/DW agreement occurs on a mean paired footprint near 3.29%; do not present it as study accuracy. DW and S2 rules share optical lineage. No threshold is declared best.
5. **Four-month comparison:** `pixel_month_comparisons.csv`, `actual_dated_observations.csv`, `reference_outcome_accounting.csv`, `proxy_agreement_and_unknown_ranges.csv`. Keep all 720 original pixel-months, use the original 24 strata and design weights N_h/30 times sampled geodesic pixel area. This is an approximate area-time ratio estimate, not exact census area. Repeated source dates are within-sample evidence. All unknowns remain in the planned denominator. Report assigned support beside conditional agreement; optional binary-completion ranges describe completing the proxy comparison, not true-water accuracy. The 2000 fixed-seed within-stratum percentile bootstrap concerns sampling uncertainty only; degenerate conditional intervals are left unavailable. Do not label the selected human interpretations independent validation.
6. **Observation limitation:** retain `radar_automated_recovery_intervals.csv` and every row in `exploratory_recovery_support_sensitivity.csv`. There are 108 overlapping event-cohort records, not 108 independent droughts. No timing is identifiable under any of nine settings. Report non-identifiability, not failure of ecological recovery or zero recovery time.
7. **Discussion:** characterize the actual observed source-class changes and the sensitivity/coverage limits. Climate residuals do not identify pumping. No surface-water storage, groundwater extraction or ecosystem benefit was measured. Existing results do not establish first-study novelty or superiority. The bounded methods scan is not sufficient for a full Introduction or a systematic novelty claim; verify manuscript-specific literature and journal fit during writing.

## Figures

`analysis_v2/Figures/` contains 12 PNG figures plus vector versions and the source-transition raster. `CAPTIONS.md` and `analysis_v2/figure_sources.json` describe provenance. The earlier 720-point consensus figure is not carried into this new sample's account. New figure: `new_reference_support_and_agreement`. Layout is provisional, with no target-journal specification yet.

## Reproducibility and availability

Actual human CSV and Backup remain at their original workspace paths. No independent reference CSV is fabricated. Original source inputs are not all bundled into the results archive; they remain in this workspace and are identified by `verified_source_hashes.json` and original manifests. Reproduction uses the original project data, the scripts, frozen protocol and recorded environments. The optional science environment computed the new analysis; the pre-existing Python 3.12 project environment ran the complete pytest suite. Neither environment was modified or installed into. No new remote Earth Engine task or manual campaign was started.

Software/procedural acknowledgements are in `research/tooling_reference.json`; reviewed methods citations and access levels are in `research/sources.jsonl`. Authorship, declarations, disclosures and eventual submission remain author-controlled. The Word manuscript should later be created as manuscript.docx using the workspace document workflow, with a Figures directory retained in its submission package.
'''
    handoff=handoff.replace('analysis_v2/',active_rel+'/').replace('The optional science environment computed the new analysis; the pre-existing Python 3.12 project environment ran the complete pytest suite.','The actual recorded interpreter computed the active analysis; the pre-existing Python 3.12 project environment ran the complete pytest suite.')
    if label_revision:
        handoff+='\n## Explicit user-directed label revision\n\nLATEST_LABEL_REVISION.json records the sole dated correction (sample 144, 2023-03-30, 0 to 1). It followed disclosure of the rule result, so post-correction agreement is not blind validation. The revised CSV and Backup are the canonical active human inputs recorded in RUN_MANIFEST.json; original exports remain intact. Code-undecided binary dates retain 313 existing human water and 141 human nonwater answers. Neither those answers nor new agreement are independent truth.\n'
    (PACK / 'PAPER_HANDOFF.md').write_text(handoff,encoding='utf-8')
    (PACK / 'README.md').write_text(f'# Final code-only research package\n\nStart with FINAL_RESULT_BN.md and PAPER_HANDOFF.md. Active numerical run: {active_rel}/. '
        'Earlier analysis directories are preserved historical versions; only the named active run supplies the current human-label summary. '
        'Original data and prior labels remain unchanged. This is ready to begin writing within a restricted scope, not a publication or independent-accuracy certificate.\n\n'
        'To reproduce in the original workspace, run the existing scientific Python interpreter on postprocessing/finalize_code_only_research.py '
        f"with --out code_only_final_20261016/<new-run-name> --csv {Path(run.get('actual_human_csv','dated_water_labels_2026-10-15T18-04-25.751Z.csv')).name} --backup {Path(run.get('actual_human_backup','dated_water_backup_recovered_20261016_82bb0063.json')).name}. The command refuses to overwrite an existing run. "
        'Requires original datasets/evidence folders; they are not downloaded again or included in the small results archive. '
        'For software checks, use the already installed project Python: python -m pytest tests -q. '
        'New code, original dependency metadata and tests accompany the archive.\n',encoding='utf-8')
    checks = {
        'status':'PASS_FOR_RESTRICTED_COMPUTATIONAL_FINALIZATION_AND_WRITING_HANDOFF', 'checked_at':now,
        'source_files_hash_verified':result['source_files_verified'], 'all720_samples_retained':True,
        'actual_dated_observations':3022, 'original_human_dates_completed':694,
        'weighted_ratios_recomputed_with_math_fsum':True, 'all_unknowns_retained_in_denominators':True,
        'actual_app_csv_backup_roundtrip_match':True, 'all_four_thresholds_and_nine_recovery_settings_retained':True,
        'python_tests_passed':tests['python']['passed'], 'node_tests_passed':tests['node']['passed'],
        'figure_count':12, 'figure_review':visual, 'result_audit_structural_validator_passed':True,
        'bounded_method_source_audit_passed':True, 'old_inputs_and_labels_unchanged':True,
        'new_human_labels_created':0, 'new_manual_review_requested':False,
        'independent_accuracy_complete':False, 'recovery_duration_resolved':False,
        'manuscript_writing_ready_within_scope':True, 'scientific_publication_ready':False,
        'self_review':True, 'automated_agreement_not_physical_truth':True,
    }
    write(PACK / 'FINAL_CHECKS.json',checks)
    # Only the active pointer is updated; the earlier scientific scope and
    # human data are preserved verbatim in their existing locations.
    current = ROOT / 'CURRENT_WATER_REVIEW_STATUS.json'
    snapshot = PACK / 'workflow_status_before_code_only_final.json'
    if not snapshot.exists(): shutil.copy2(current,snapshot)
    state = read(current)
    state.update(checked_at=now,current_route='CODE_ONLY_FINALIZED_WITH_LIMITATIONS',
                 code_only_package=str(PACK),active_analysis=str(OUT),scope_decision=str(PACK/'scope_decision.json'),
                 new_manual_review_requested=False,required_user_actions=[],
                 independent_accuracy_required_for_current_scope=False,
                 independent_reference_pending_is_future_work_only=True,
                 manuscript_writing_ready_within_scope=True,scientific_publication_ready=False)
    if label_revision:
        state.update(latest_user_csv=label_revision['new_csv'],latest_user_csv_sha256=label_revision['new_csv_sha256'],
                     recovered_backup=label_revision['new_backup'],latest_csv_audit=str(args.label_revision.resolve()),
                     latest_label_code_check=str(ROOT/'label_verification/dated_code_check_20261016_corrected144/CHECK_RESULT.json'),
                     user_requested_dated_corrections=1)
    write(current,state)
    write(PACK/'WORKFLOW_STATUS.json',state)
    # Stable payload layout mirrors the workspace. No raw data or mutable
    # personal browser/session state is bundled.
    archive = ROOT / 'NW_Bangladesh_Code_Only_Final_20261016.zip'
    files = [p for p in PACK.rglob('*') if p.is_file() and p.name != 'ARCHIVE_CHECK.json' and 'qa' not in p.relative_to(PACK).parts
             and 'revision_history' not in p.relative_to(PACK).parts
             and (not p.relative_to(PACK).parts[0].startswith('analysis') or p.relative_to(PACK).parts[0]==active_rel)]
    if label_revision:
        files += [Path(label_revision['new_csv']),Path(label_revision['new_backup']),args.label_revision.resolve()]
        checks_dir=ROOT/'label_verification/dated_code_check_20261016_corrected144'
        files += [p for p in checks_dir.glob('*') if p.is_file()]
    files += [p for p in (ROOT/'postprocessing').iterdir() if p.is_file() and p.suffix in ('.py','.js','.cjs','.html','.json')]
    files += list((ROOT/'research_pipeline').glob('*.py')) + list((ROOT/'automatic_water').glob('*.py'))
    files += [ROOT/'research_pipeline/config.json',ROOT/'requirements.txt',ROOT/'requirements-dev.txt',ROOT/'METHODS.md'] + list((ROOT/'automatic_water').glob('*.json'))
    files += list((ROOT/'tests').glob('test_*.py')) + list((ROOT/'tests').glob('*.cjs'))
    files = sorted(set(files))
    payload = {str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files: z.write(p,str(p.relative_to(ROOT)).replace('\\','/'))
        z.writestr('PACKAGE_SHA256.json',json.dumps(payload,indent=2))
    with zipfile.ZipFile(archive) as z:
        require(z.testzip() is None, 'Archive CRC failed')
        require(all(hashlib.sha256(z.read(name)).hexdigest()==h for name,h in payload.items()), 'Archive file integrity mismatch')
    (archive.with_suffix('.sha256')).write_text(digest(archive)+'  '+archive.name+'\n',encoding='ascii')
    write(PACK/'ARCHIVE_CHECK.json',{'archive':str(archive),'sha256':digest(archive),'files':len(payload),'bytes':archive.stat().st_size,'all_payload_hashes_and_crc_verified':True,
          'raw_datasets_bundled':False,'superseded_initial_run_bundled':False})
    print(json.dumps({'status':checks['status'],'manuscript_writing_ready_within_scope':True,'independent_accuracy_complete':False,
                      'scientific_publication_ready':False,'archive':str(archive),'archive_bytes':archive.stat().st_size},indent=2))


if __name__=='__main__': main()
