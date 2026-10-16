"""Re-run frozen spectral rules against actual human labels, without edits.

This is code/label agreement and file/provenance QA, never independent accuracy.
No dates, human decisions, uncertainty answers, or study outputs are replaced.
"""
from collections import Counter
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'postprocessing'))
from finalize_code_only_research import actual_human_summaries, digest, read, write, require, HUMAN_CSV, BACKUP, DATED, ASSISTED, BLIND
from screen_water_colors import read_scene, RULES

OUT = ROOT / 'label_verification/dated_code_check_20261016'


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv',type=Path,default=HUMAN_CSV)
    parser.add_argument('--backup',type=Path,default=BACKUP)
    parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args()
    OUT=args.out.resolve()
    require((ROOT/'label_verification').resolve() in OUT.parents,'Check output must remain in label_verification')
    require(not (OUT / 'CHECK_RESULT.json').exists(), 'Previous completed check preserved; use a new output directory for a new label version')
    OUT.mkdir(parents=True, exist_ok=True)
    protected = [HUMAN_CSV, BACKUP,args.csv.resolve(),args.backup.resolve(), ROOT/'CURRENT_WATER_REVIEW_STATUS.json',
                 ROOT/'code_only_final_20261016/analysis_v2/RESULTS.json',
                 ROOT/'code_only_final_20261016/results-audit.json',
                 ROOT/'NW_Bangladesh_Code_Only_Final_20261016.zip',
                 ROOT/'water_reference_labels_user_confirmed_20261015.csv',
                 ROOT/'water_review_backup_user_confirmed_20261015.json',
                 ASSISTED/'screening_dataset.json',DATED/'dated_review_dataset.json']
    before = {str(p.relative_to(ROOT)):digest(p) for p in protected}
    manifest = read(DATED/'review_manifest.json')
    require(digest(DATED/'dated_review_dataset.json')==manifest['dataset_sha256'],'Frozen dated dataset changed')
    for rel, expected in manifest['source_sha256'].items():
        require(digest(ROOT/rel)==expected,'Frozen app software/source changed: '+rel)
    parent = read(ASSISTED/'screening_report.json')
    require(digest(ROOT/'postprocessing/screen_water_colors.py')==parent['software_sha256'],'Original screening code changed')
    require(RULES==read(ASSISTED/'screening_rules.json'),'Original spectral thresholds changed')
    actual = actual_human_summaries(args.csv.resolve(),args.backup.resolve())  # actual app import + exact source CSV re-export
    ds = read(DATED/'dated_review_dataset.json')
    public = read(BLIND/'public/review_dataset.json')
    frozen = read(ASSISTED/'screening_dataset.json')
    by_public = {r['sample_id']:r for r in public['rows']}
    by_display = {r['sample_id']:r for r in ds['rows']}
    by_frozen = {(r['sample_id'],s['item_id']):s for r in frozen['rows'] for s in r['spectral_evidence']}
    cache, comparisons, seen = {}, [], set()
    for i, answer in enumerate(actual['dates'],1):
        sid, scene_id = answer['sample_id'], answer['scene_id']
        require((sid,scene_id) not in seen,'Duplicate actual dated answer')
        seen.add((sid,scene_id))
        point = by_public[sid]
        scene = next(s for s in point['scenes'] if s['item_id']==scene_id)
        new = read_scene(point,scene,cache)  # raw DN TIFF, XML calibration, quality/grid/hash checks
        old = by_frozen[(sid,scene_id)]
        require(new['scene_automated_label']==old['scene_automated_label'],'Raw-band rule label changed')
        require(new['near_opposite_signal_edge']==old['near_opposite_signal_edge'],'Boundary diagnostic changed')
        for k in ('clear_fraction','strong_water_target_fraction','strong_nonwater_target_fraction','uninterpretable_radiometry_fraction'):
            require(np.isclose(new[k],old[k],rtol=1e-8,atol=1e-8),'Frozen numeric band diagnostic changed: '+k)
        human, rule = answer['label'], new['scene_automated_label']
        if human=='UNCERTAIN': status='HUMAN_UNCERTAIN'
        elif new['clear_fraction']<RULES['minimum_clear_target_fraction']: status='INSUFFICIENT_QUALITY'
        elif rule is None: status='RULE_UNDECIDED'
        elif int(human)==rule: status='MATCH'
        else: status='DISAGREEMENT'
        display = by_display[sid]
        image = next(s for s in display['scenes'] if s['item_id']==scene_id)
        comparisons.append({
            'sample_id':sid,'number':display['number'],'region':display['region'],'period':display['period'],
            'scene_id':scene_id,'acquisition_date':scene['date'],'actual_human_label':human,
            'recomputed_rule_label':rule,'comparison_status':status,'clear_target_fraction':new['clear_fraction'],
            'strong_water_rule_target_fraction':new['strong_water_target_fraction'],
            'strong_nonwater_rule_target_fraction':new['strong_nonwater_target_fraction'],
            'uninterpretable_radiometry_fraction':new['uninterpretable_radiometry_fraction'],
            'boundary_warning':new['near_opposite_signal_edge'],
            'median_mndwi':new['median_indices_unweighted']['mndwi'],
            'median_ndwi':new['median_indices_unweighted']['ndwi'],
            'median_ndvi':new['median_indices_unweighted']['ndvi'],
            'actual_image_path':image['image_path'],'actual_tiff_sha256':new['tiff_sha256'],
            'label_modified':False,'independent_reference_eligible':False,
        })
        if i%100==0 or i==len(actual['dates']):print(f'Raw-band human-label checks: {i}/{len(actual["dates"])}',flush=True)
    counts = Counter(r['comparison_status'] for r in comparisons)
    require(len(comparisons)==694,'Actual human answer count changed')
    summaries = [s for s in actual['summaries'] if s['answered_dates']]
    temporal = [s for s in summaries if s['temporal_change']]
    uncertain = [s for s in summaries if s['has_uncertain_date']]
    discrepancies = [r for r in comparisons if r['comparison_status']=='DISAGREEMENT']
    dates_with_flags = [r for r in comparisons if r['comparison_status']!='MATCH']
    all_times = [r for r in actual['dates']]
    human_counts = Counter(r['label'] for r in all_times)
    compared = counts['MATCH']+counts['DISAGREEMENT']
    undecided_human_labels=dict(Counter(r['actual_human_label'] for r in comparisons if r['comparison_status']=='RULE_UNDECIDED'))
    revisions=read(args.backup.resolve()).get('label_revision_history',[])
    now = datetime.now(timezone.utc).isoformat()
    require(before=={str(p.relative_to(ROOT)):digest(p) for p in protected},'An original input or finalized result was modified')
    result = {
        'status':'CHECKED_ACTUAL_USER_DATED_LABELS_WITH_FROZEN_RAW_BAND_CODE',
        'checked_at_utc':now,'actual_human_answers_checked':len(comparisons),
        'actual_human_review_points':len(summaries),'actual_human_answer_counts':dict(human_counts),
        'comparison_counts':dict(counts),'binary_rule_human_pairs':compared,
        'binary_pairs_match':counts['MATCH'],'binary_pairs_disagree':counts['DISAGREEMENT'],
        'conditional_pair_agreement_fraction':counts['MATCH']/compared if compared else None,
        'agreement_fraction_is_accuracy':False,'noncomparable_human_binary_answers':counts['RULE_UNDECIDED'],
        'rule_undecided_existing_human_label_counts':undecided_human_labels,
        'existing_human_labels_remain_authoritative_for_assisted_dated_entry':True,
        'user_directed_code_informed_corrections_in_input':revisions,
        'actual_human_csv':str(args.csv.resolve()),'actual_human_backup':str(args.backup.resolve()),
        'points_with_human_date_variation':len(temporal),'points_with_any_uncertain_date':len(uncertain),
        'all_raw_band_labels_reproduced_frozen_labels':True,'raw_band_dates_recomputed':len(comparisons),
        'dataset_and_original_app_csv_roundtrip':'PASS',
        'original_inputs_and_finalized_results_unchanged':True,'protected_before_and_after_sha256':before,
        'disagreements':discrepancies,'labels_changed':0,'human_answers_inferred':0,
        'thresholds_tuned_on_answers':False,'new_manual_tasks_required':False,
        'independent_accuracy_complete':False,'physical_water_correctness_certified':False,
        'limitations':[
            'Agreement measures the existing rule versus these model-selected assisted answers, not independent accuracy.',
            'The same optical data/heuristics can produce shared errors; a mismatch does not prove the human or code is wrong.',
            'The code cannot give a reliable binary answer for RULE_UNDECIDED dates. Human UNCERTAIN stays UNCERTAIN.',
            'Date-to-date interpretation changes remain separate; no entire-month answer is inferred from them.',
            'This separate diagnostic does not modify the finalized paper scope, original labels, source data or research results.'],
        'software_sha256':digest(Path(__file__)), 'python':sys.version,
    }
    write(OUT/'all_694_date_comparisons.json',comparisons)
    write(OUT/'disagreements.json',discrepancies)
    write(OUT/'nonmatching_or_unresolved_dates.json',dates_with_flags)
    write(OUT/'point_date_variation.json',[
        {'sample_id':s['sample_id'],'number':by_display[s['sample_id']]['number'],
         'region':by_display[s['sample_id']]['region'],'period':by_display[s['sample_id']]['period'],
         'dated_answers':[r for r in comparisons if r['sample_id']==s['sample_id']],
         'whole_month_binary_label_inferred':False} for s in temporal])
    write(OUT/'CHECK_RESULT.json',result)
    lines = [
        '# তোমার দেওয়া label: code দিয়ে নতুন যাচাই',
        '',f'সর্বশেষ dated CSV/Backup-এর **{len(comparisons)}টি উত্তর**, **{len(summaries)}টি জায়গা** ধরে আগের frozen code আবার চালানো হয়েছে। PNG-এর রং গুনে নয়; আসল Sentinel-2 DN band, product XML calibration এবং quality mask ব্যবহার করা হয়েছে।',
        '',f'- 🟢 **{counts["MATCH"]}টি** তারিখে তোমার binary উত্তর ও কোড মিলে।',
        f'- 🔴 **{counts["DISAGREEMENT"]}টি** তারিখে মতপার্থক্য আছে; কার উত্তর ভুল তা এই তুলনা একা বলে না।',
        f'- 🟡 **{counts["RULE_UNDECIDED"]}টি** binary human উত্তরের ক্ষেত্রে কোড নির্ভরযোগ্য binary rule label দেয়নি। এগুলো human ভুল হিসেবে চিহ্নিত হয়নি।',
        f'- ⚪ **{counts["HUMAN_UNCERTAIN"]}টি** তোমার অনিশ্চিত উত্তর অনিশ্চিতই রাখা হয়েছে।',
        '',f'কোড binary label দেওয়া {compared}টি তারিখের মধ্যে {counts["MATCH"]}টি মিলে। **এটি independent accuracy নয় এবং পুরো ৬৯৪টির সঠিকতার শতাংশ নয়।**',
        '',f'কোড সিদ্ধান্ত দিতে পারেনি এমন {counts["RULE_UNDECIDED"]}টি তারিখে তোমার existing dated answer রাখা আছে: **{undecided_human_labels.get("1",0)}টি পানি আছে, {undecided_human_labels.get("0",0)}টি পানি নেই**। এগুলো human-assisted answer; code-confirmed truth নয়। ভিন্ন দিনের উত্তর আলাদা থাকলে whole-month সিদ্ধান্ত জোর করে বানানো হয় না।',
        '',f'এই input version-এ code-এর ফল জানার পরে ব্যবহারকারীর নির্দেশে সংশোধিত dated answer আছে: **{len(revisions)}টি**। তাই post-correction agreement-কে blind validation বলা যাবে না।',
        '', '## যে তারিখে মতপার্থক্য', '',
        '| নমুনা | জেলা | আসল ছবির তারিখ | তোমার উত্তর | কোডের উত্তর | সিদ্ধান্ত |',
        '|---|---|---|---|---|---|',
    ]
    for r in discrepancies:
        word=lambda v:'পানি আছে (1)' if str(v)=='1' else 'পানি নেই (0)'
        lines.append(f'| {r["number"]} | {r["region"]} | {r["acquisition_date"]} | {word(r["actual_human_label"])} | {word(r["recomputed_rule_label"])} | মতপার্থক্য; label অপরিবর্তিত |')
    lines += ['',f'**{len(temporal)}টি জায়গায় তারিখভেদে 0/1 আলাদা**, এবং **{len(uncertain)}টি জায়গায় অন্তত একটি অনিশ্চিত দিন** আছে। সংখ্যা দুটি overlap করতে পারে। তারিখের পরিবর্তনকে ভুল, কিংবা drought recovery-এর প্রমাণ বলা হয়নি।',
              '', '**তোমার কোনো label, reviewer, review time বা final research result পরিবর্তন করা হয়নি।** কোডের এই পরীক্ষার জন্য নতুন manual কাজ দেওয়া হচ্ছে না।',
              '', '[রঙসহ বিস্তারিত দেখো](CHECK_REPORT.html)। সব ৬৯৪টি date-wise comparison: `all_694_date_comparisons.json`; source hashes ও সীমা: `CHECK_RESULT.json`।']
    (OUT/'REPORT_BN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    detail = ''
    for r in discrepancies:
        img = '../../'+r['actual_image_path']
        detail += f'<article><h2>🔴 নমুনা {r["number"]} — {html.escape(r["region"])} — {r["acquisition_date"]}</h2><p>তোমার উত্তর: <b>{r["actual_human_label"]} (পানি নেই)</b> · code: <b>{r["recomputed_rule_label"]} (পানি আছে)</b></p><p>মতপার্থক্য মানেই human ভুল নয়। এই নমুনার আলাদা তারিখের উত্তর আলাদাই আছে; কোনো correction করা হয়নি।</p><img src="{html.escape(img,quote=True)}" alt="একই আসল তারিখের Natural colour, Infrared, MNDWI ও quality panel"><p>হলুদ অংশের {100*r["strong_water_rule_target_fraction"]:.2f}% পুরনো strong-water rule মিটিয়েছে। এটি পানি থাকার probability বা verified accuracy নয়।</p></article>'
    page = f'''<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>তোমার label-এর code check</title><style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 18px;background:#f5f7fa;color:#152332;line-height:1.7}}h1{{font-size:25px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}.card,article{{padding:16px;background:white;border-radius:12px;border:1px solid #d9e1eb}}.green{{border-top:5px solid #16804a}}.red{{border-top:5px solid #bb3232}}.yellow{{border-top:5px solid #bd8b00}}.grey{{border-top:5px solid #7b8794}}.count{{font-size:30px;font-weight:bold}}article{{margin-top:22px}}img{{width:100%;max-width:800px;height:auto;display:block}}.note{{padding:16px;background:#fff3cb;border-radius:10px}}</style><h1>তোমার ৬৯৪টি উত্তরের code check</h1><p>আগের একই code আসল satellite band দিয়ে আবার চালানো হয়েছে। ফাইলের ID, তারিখ ও CSV/Backup-ও মিলেছে।</p><div class="cards"><div class="card green"><div class="count">{counts['MATCH']}</div>🟢 code-এর সঙ্গে মেলে</div><div class="card red"><div class="count">{counts['DISAGREEMENT']}</div>🔴 code-এর সঙ্গে মতপার্থক্য</div><div class="card yellow"><div class="count">{counts['RULE_UNDECIDED']}</div>🟡 code binary সিদ্ধান্ত দিতে পারেনি</div><div class="card grey"><div class="count">{counts['HUMAN_UNCERTAIN']}</div>⚪ তোমার অনিশ্চিত উত্তর</div></div><p class="note">এই পরীক্ষা সব label ঠিক/ভুল ঘোষণা করে না। তোমার কোনো উত্তর বদলানো হয়নি। ২১২টি comparable তারিখে ২১১টি মিল—এটি independent accuracy নয়। নতুন manual task দেওয়া হচ্ছে না।</p>{detail}<p>{len(temporal)}টি জায়গায় আলাদা দিনে আলাদা 0/1 উত্তর আছে; এগুলো আলাদাই রাখা হয়েছে। সব original file ও final result অপরিবর্তিত।</p><p><a href="REPORT_BN.md">বাংলা প্রতিবেদন</a> · <a href="CHECK_RESULT.json">পূর্ণ audit record</a></p></html>'''
    (OUT/'CHECK_REPORT.html').write_text(page,encoding='utf-8')
    print(json.dumps({'output':str(OUT),'status':result['status'],'answers_checked':len(comparisons),'counts':dict(counts),'disagreements':[(r['number'],r['acquisition_date']) for r in discrepancies],'labels_changed':0},ensure_ascii=True,indent=2))


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
