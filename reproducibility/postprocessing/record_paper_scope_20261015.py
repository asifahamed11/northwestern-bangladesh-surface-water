"""Record the user-authorized claim narrowing; do not draft a manuscript."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'paper_scope_20261015'


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    if (OUT/'paper_scope.json').exists():
        print('Existing scope record preserved.');return
    OUT.mkdir(exist_ok=True)
    sources=[ROOT/'research_pipeline/config.json',
        ROOT/'automatic_water_outputs/sensitivity_20261015_115522_c3ef05/FINAL_FINDINGS_BN.md',
        ROOT/'automatic_water_outputs/sensitivity_20261015_115522_c3ef05/FINAL_CHECKS.json',
        ROOT/'research_outputs/analysis_20261013_completed_data/FINAL_CHECKS.json',
        ROOT/'label_verification/user_pilot_confirmation_20261015/user_confirmation.json']
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sources}
    scope={
        'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'paper_id':'nw-bangladesh-climate-adjusted-water','identity_change':'D2: narrow an unidentifiable recovery claim while preserving the water-change study',
        'original_title':'Climate-adjusted changes and drought recovery of permanent and seasonal surface water in northwestern Bangladesh',
        'working_title':'Climate-adjusted surface-water changes and observation uncertainty in northwestern Bangladesh',
        'authorization':'User accepted the proposed easier route: finish reference validation and narrow title/claims to existing evidence, then start writing; explicit chat: okay kore deo; later continue.',
        'study_area':['Naogaon','Chapainawabganj','Rajshahi'],
        'primary_period':'JRC version-aware 2000-2021; 2000-2024 source-version sensitivity separately',
        'supplementary_period':'Sentinel-1/Dynamic World 2015-2024; distinct fixed cohorts, estimands and spatial support',
        'retained_scientific_scope':['Permanent/seasonal source classes and their observation support','Climate-adjusted associations in observed water proxies','Sensor/threshold/observation uncertainty'],
        'recovery_disposition':'No defensible recovery duration was identified. Preserve the 108 event-cohort records and nine sensitivity specifications as a limitation/negative identifiability result; do not replace missing timing with zero, no-recovery, or a fabricated duration.',
        'recovery_scope_decision_resolved':True,'recovery_duration_scientifically_resolved':False,
        'reference_validation_status':'PENDING_NEW_BLINDED_HUMAN_REFERENCE_REVIEW',
        'manuscript_started':False,'scientific_publication_ready':False,
        'authors_or_declarations_modified':False,'raw_data_or_prior_results_modified':False,
        'input_sha256':hashes,
        'workflow_mode':'Standalone bounded implementation; no claim of orchestrator enforcement or independent automated verification.'}
    claims=[
        {'id':'WATER_CHANGE','status':'SUPPORTED_WITH_STATED_SENSOR_MODEL_SUPPORT_LIMITS',
         'claim':'Report only the changes and confidence intervals actually supported by the separate annual and radar analyses; do not equate their opposite-sign results across unlike periods/cohorts.',
         'evidence':['research_outputs/analysis_20261013_completed_data/FINAL_RESULT_BN.md','automatic_water_outputs/sensitivity_20261015_115522_c3ef05/FINAL_FINDINGS_BN.md']},
        {'id':'OBSERVATION_UNCERTAINTY','status':'SUPPORTED_FOR_EXISTING_ANALYSES',
         'claim':'Threshold agreement depends on classified/paired support; agreement on the paired subset is not independent map accuracy.',
         'evidence':['automatic_water_outputs/sensitivity_20261015_115522_c3ef05/FINAL_CHECKS.json']},
        {'id':'RECOVERY_DURATION','status':'UNRESOLVED_NOT_A_POSITIVE_CLAIM',
         'claim':'No recovery timing is identifiable under the declared primary and exploratory specifications; the finding does not mean water never returned.',
         'evidence':['automatic_water_outputs/sensitivity_20261015_115522_c3ef05/radar_automated_recovery_intervals.csv','automatic_water_outputs/sensitivity_20261015_115522_c3ef05/exploratory_recovery_support_sensitivity.csv']},
        {'id':'INDEPENDENT_ACCURACY','status':'PENDING_HUMAN_REFERENCE_DATA_AND_EVALUATION',
         'claim':'Five guided user confirmations are retained as pilot evidence. They do not constitute the full stratified blinded accuracy evaluation.',
         'evidence':['label_verification/user_pilot_confirmation_20261015/user_confirmation.json']},
        {'id':'ANTI_CLAIMS','status':'PROHIBITED_WITH_CURRENT_EVIDENCE',
         'claims':['100 percent accuracy','Publication acceptance or submission readiness','Causal attribution to pumping or land use from adjusted residuals alone','Recovery duration in months','Independent accuracy for every year or annual hydroperiod classes from four monthly reference periods','Unverified first-study or novelty priority claims']}
    ]
    (OUT/'paper_scope.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'claim_evidence_map.json').write_text(json.dumps(claims,ensure_ascii=False,indent=2),encoding='utf-8')
    text='''# পেপার লেখার আগের সিদ্ধান্ত

নতুন working title:

**Climate-adjusted surface-water changes and observation uncertainty in northwestern Bangladesh**

মূল গবেষণা একই তিন জেলার পানির পরিবর্তন নিয়ে। স্থায়ী/মৌসুমি source-class বিশ্লেষণ থাকবে। খরার পরে কত মাসে পানি ফিরেছে—এমন ফল পাওয়া যায়নি, তাই শিরোনামে recovery time-এর প্রতিশ্রুতি রাখা হচ্ছে না।

Recovery-এর আগের ১০৮টি event–cohort record ও ৯টি sensitivity check সংরক্ষিত। সময় নির্ধারণ করা যায়নি—এটি সীমাবদ্ধতা/অনিষ্পন্ন প্রশ্ন হিসেবে থাকবে। এর অর্থ পানি ফেরেনি নয়। শিরোনাম বদলানো recovery সময় বের করার বিকল্প প্রমাণ নয়।

আগের সব download, analysis, figure ও label সংরক্ষিত। কোনো manuscript, author list বা declaration তৈরি/বদলানো হয়নি।

পরের কাজ হলো নতুন, prediction-লুকানো dated reference review। এই কাজ মানুষের উত্তর ছাড়া স্বয়ংক্রিয়ভাবে সম্পন্ন হবে না। আগের ৭২০টি প্রাথমিক label ও ৫টির guided confirmation আলাদা থাকবে।

এই reference plan কেবল চারটি নির্ধারিত মাসে observed JRC binary water/nonwater মানচিত্রের সীমিত validation। এটি নিজে annual permanent/seasonal class, ২০০০–২০২৪-এর সব বছর, বা নতুন radar/Dynamic World ফলের পূর্ণ accuracy যাচাই নয়। পেপারের দাবি সেই সীমার মধ্যে রাখতে হবে; বিস্তৃত দাবি চাইলে তার উপযুক্ত অতিরিক্ত reference design লাগবে।

Accuracy evaluation-এ অনিশ্চিত/উত্তর না দেওয়া নমুনার সংখ্যা ও ওজন প্রকাশ করতে হবে। কেবল পরিষ্কার সহজ নমুনা রেখে পুরো এলাকার accuracy বলা যাবে না। Minimum sample count একটি project rule, সঠিকতার নিশ্চয়তা নয়।

মানব যাচাইয়ের পরে coverage, ভুলের ধরন, uncertainty ও claim-evidence audit মিলিয়ে paper লেখা শুরুর অবস্থা নির্ধারণ করব। স্বাধীন accuracy এখনো সম্পন্ন নয়; submission-ready ঘোষণা দেওয়া হয়নি।
'''
    (OUT/'DECISION_BN.md').write_text(text,encoding='utf-8')
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    (OUT/'SCOPE_CHECKS.json').write_text(json.dumps({'status':'PASS','scope_decision_recorded':True,'recovery_duration_resolved':False,'independent_accuracy_complete':False,'prior_inputs_unchanged':True,'manuscript_started':False,'evidence_files_exist':all((ROOT/f).exists() for c in claims for f in c.get('evidence',[]))},indent=2),encoding='utf-8')
    print('Scope narrowing recorded; recovery data/result and independent validation not falsely marked complete.')


if __name__=='__main__':main()
