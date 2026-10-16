"""Read-only sample-size planning; creates no labels, sample points or accuracy.

Run with the existing research interpreter. The old protocol is not amended.
Frozen sampling weights provide planning approximations, not exact census areas.
"""
from collections import defaultdict
from datetime import datetime, timezone, date
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import NormalDist
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'accuracy_sample_size_20261016'
INPUTS = [
    'independent_accuracy_20261015/private/validation_sample_plan.json',
    'independent_accuracy_20261015/private/stratum_counts.json',
    'independent_accuracy_20261015/public/review_dataset.json',
    'independent_accuracy_20261015/validation_protocol.json',
    'independent_accuracy_20261015/review_manifest.json',
    'CURRENT_WATER_REVIEW_STATUS.json',
    'assisted_water_screening_20261015/date_review_v2/csv_audits/audit_82bb0063/audit_result.json',
]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def main():
    before = {p: digest(ROOT / p) for p in INPUTS}
    plan, strata, public, protocol, manifest, status, audit = map(read, INPUTS)
    for p, expected in manifest['frozen_evaluation_inputs_sha256'].items():
        assert digest(ROOT / 'independent_accuracy_20261015' / p) == expected
    assert len(plan) == 720 and len(strata) == 24
    assert audit['required_date_answers_provided'] == audit['required_date_answers'] == 694
    assert status['requested_assisted_review_complete'] is True
    assert status['independent_accuracy_complete'] is False
    groups = defaultdict(list)
    for row in plan:
        groups[row['stratum']].append(row)
    assert set(groups) == {s['stratum'] for s in strata}
    assert all(len(v) == 30 for v in groups.values())
    areas = {h: sum(r['population_pixels'] / r['planned_samples'] * r['pixel_area_km2']
                     for r in rows) for h, rows in groups.items()}
    weights = {h: a / sum(areas.values()) for h, a in areas.items()}
    floors = {s['stratum']: s['minimum_verified'] for s in strata}
    assert set(floors.values()) == {20}
    z = NormalDist().inv_cdf(.975)

    def halfwidth(n):
        # Worst Bernoulli variance .25; no finite-population discount.
        return z * math.sqrt(.25 * sum(weights[h] ** 2 / n[h] for h in weights))

    def next_group(n):
        # Equal cost per accepted reference. Convex marginal variance reduction.
        return max(sorted(weights), key=lambda h: weights[h] ** 2 / (n[h] * (n[h] + 1)))

    allocated = floors.copy()
    previous = None
    while halfwidth(allocated) > .05:
        previous = allocated.copy()
        allocated[next_group(allocated)] += 1
    minimum = allocated.copy()
    recommended_total = math.ceil(sum(minimum.values()) / 50) * 50
    while sum(allocated.values()) < recommended_total:
        allocated[next_group(allocated)] += 1
    assert sum(minimum.values()) == 592 and sum(allocated.values()) == 600
    assert halfwidth(previous) > .05 >= halfwidth(minimum)
    assert math.isclose(sum(weights.values()), 1)

    # Capacity is descriptive only. Never use cloud-free survivors as a new frame.
    quality = {}
    for row in public['rows']:
        dates = [date.fromisoformat(s['date']) for s in row['scenes'] if s['clear_fraction'] >= .95]
        quality[row['sample_id']] = len(dates) >= 2 and (max(dates) - min(dates)).days >= 14
    assert sum(quality.values()) == 582
    assert len(quality) - sum(quality.values()) == 138
    capacity = {h: sum(quality[r['sample_id']] for r in rows) for h, rows in groups.items()}
    equal_minimum = floors.copy()
    old_equal30 = {h: 30 for h in weights}
    result = {
        'status': 'CONDITIONAL_PLANNING_CALCULATION_NOT_VALIDATION',
        'calculated_at_utc': datetime.now(timezone.utc).isoformat(),
        'target': protocol['pooled_estimand'],
        'periods': sorted({r['period'] for r in plan}),
        'confidence_level': .95, 'target_halfwidth': .05, 'z': z,
        'worst_case_stratum_correctness_proportion': .5,
        'strata': 24, 'existing_project_floor_per_stratum': 20,
        'floor_is_universal_scientific_requirement': False,
        'weight_method': 'Normalize sum(N_h/30 * sampled geodesic pixel area) per stratum; frozen project area-time planning approximation, not exact census areas.',
        'variance_formula': 'V_plan = sum(W_h^2 * 0.25 / n_h); H95 = z(.975) * sqrt(V_plan)',
        'finite_population_discount_used': False,
        'simple_random_sample_benchmark_only': math.ceil(z*z*.25/.05**2),
        'equal20_total': 480, 'equal20_halfwidth': halfwidth(equal_minimum),
        'equal30_total': 720, 'equal30_halfwidth': halfwidth(old_equal30),
        'computed_accepted_reference_total': sum(minimum.values()),
        'computed_halfwidth': halfwidth(minimum),
        'preceding_optimal_total': sum(previous.values()),
        'preceding_halfwidth': halfwidth(previous),
        'rounded_recommended_accepted_reference_total': recommended_total,
        'rounded_recommended_halfwidth': halfwidth(allocated),
        'existing_assisted_points_complete': 245,
        'existing_assisted_dated_answers_complete': 694,
        'existing_assisted_labels_credited_as_independent': 0,
        'additional_accepted_independent_reference_target': recommended_total,
        'minimum_clear_dated_decisions_for_recommended_total': 2 * recommended_total,
        'minimum_total_image_views_under_unchanged_all_prepared_views_protocol': 3 * recommended_total,
        'exact_future_image_count': None,
        'existing_quality_limited_points': 138,
        'existing_strata_below20_quality_capacity': sum(v < 20 for v in capacity.values()),
        'inputs_sha256': before,
        'script_sha256': digest(Path(__file__)),
        'allocation': [
            {'stratum': h, 'planning_area_time_weight': weights[h],
             'minimum_allocation': minimum[h], 'recommended_allocation': allocated[h],
             'old_quality_eligible_capacity_only': capacity[h]}
            for h in sorted(weights)
        ],
        'assumptions_and_limits': [
            'An explicitly chosen planning goal, not a journal rule, accuracy threshold, or publication guarantee.',
            'Approximate normal sampling precision for pooled four-month overall agreement only; not each district, year, class, annual hydroperiod, or 2000-2024 record.',
            'Requires a probability sample and operationally blinded, sufficiently dated, higher-quality independent reference interpretation; samples must not be selected for easy imagery or favorable answers.',
            'A fresh design must freeze its exact frame, census/area weights and allocation before new answers; recheck these planning weights if the frame changes. No sampling or protocol amendment performed here.',
            'This is an accepted reference target under complete valid responses; 600 attempts cannot guarantee 600 accepted references. Unknowns remain in original design-weight denominators and bounds; do not discard or silently replace them.',
            'Repeated image dates within one pixel-month are supporting observations, not independent sample units.',
            'Old protocol requires all prepared scene views and at least two acceptable dates >=14 days apart. At least 3 total prepared views per point; actual future dates/images not prepared or counted here.',
            'No fixed extra allowance for clouds is justified by these data; more imagery or broader bounds may be necessary. Exact total manual attempts cannot yet be guaranteed.',
            'No measured accuracy, new human labels, source downloads, UI modifications, or scientific pipeline reruns were produced.',
        ],
        'independent_accuracy_complete': False, 'scientific_publication_ready': False,
    }
    result['original_inputs_unchanged'] = before == {p: digest(ROOT / p) for p in INPUTS}
    assert result['original_inputs_unchanged']
    OUT.mkdir(exist_ok=True)
    (OUT / 'sample_size_calculation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    report = f'''# আরও কত manual verification: হিসাব

নির্বাচিত লক্ষ্য: চারটি নির্ধারিত মাসের pooled overall agreement-এর আনুমানিক ৯৫% confidence interval-এ ±৫ শতাংশ-পয়েন্ট sampling uncertainty। এটি ব্যবহারকারীর জন্য বেছে নেওয়া planning target; ৯৫% accuracy, journal requirement বা publication guarantee নয়।

হিসাবে **৫৯২টি গ্রহণযোগ্য স্বাধীন pixel–month reference** লাগে; কাজের পরিকল্পনার সংখ্যা গোল করে **৬০০টি**। বর্তমান ২৪টি group ও প্রতিটিতে অন্তত ২০টির project rule অক্ষত রেখে unequal area-time weights দিয়ে হিসাব করা হয়েছে। ৬৯৪টি assisted dated answer-কে ৬৯৪টি স্বাধীন sample ধরা বা এই সংখ্যা থেকে বিয়োগ করা হয়নি। আগের assisted কাজ ২৪৫/২৪৫ point এবং ৬৯৪/৬৯৪ date-এ সম্পূর্ণই আছে।

| হিসাব | মোট স্বাধীন reference | অনুমিত ৯৫% half-width |
|---|---:|---:|
| প্রতি group-এ ২০টি | ৪৮০ | ±{halfwidth(equal_minimum)*100:.2f} percentage points |
| প্রতি group-এ ৩০টি | ৭২০ | ±{halfwidth(old_equal30)*100:.2f} percentage points |
| উপরোক্ত floor রেখে variance কমিয়ে allocation | ৫৯২ | ±{halfwidth(minimum)*100:.2f} percentage points |
| একই allocation পদ্ধতিতে গোল করা প্রস্তাব | ৬০০ | ±{halfwidth(allocated)*100:.2f} percentage points |

Formula: `H95 = 1.95996398454 * sqrt(sum(W_h^2 * 0.25 / n_h))`। এখানে `W_h` frozen plan-এর district × period × class-এর normalized area-time planning weight। প্রকৃত accuracy জানা নেই বলে প্রত্যেক group-এ `p_h=0.5`, অর্থাৎ সর্বোচ্চ Bernoulli variance নেওয়া হয়েছে। অতি বৃহৎ pixel population-এর জন্য finite-population discount ব্যবহার করা হয়নি। প্রতি গ্রহণযোগ্য reference-এর cost সমান ধরে প্রতি ধাপে সর্বাধিক variance reduction পাওয়া group-এ এক sample যোগ করা হয়েছে। এই model-এ ৫৯১-এ half-width {halfwidth(previous)*100:.5f}%; ৫৯২-এ {halfwidth(minimum)*100:.5f}%।

সাধারণ SRS সূত্রে ৩৮৫ পাওয়া যায়; এটি এখানে সরাসরি ব্যবহার করা হয়নি। Project-এর minimum counts ও unequal weights মিলিয়ে আলাদা allocation দরকার। প্রতি group-এ ২০টি universal statistical law নয়। ৬০০টি যেকোনোভাবে ভাগ করলে উপরের precision হয় না; JSON-এ নির্ধারিত allocation আছে। Planning weights sampled geodesic pixel areas দিয়ে আনুমানিক; নতুন frame নিলে exact weights আগে স্থির করে হিসাব পুনরায় পরীক্ষা করতে হবে।

## আসলে কত ছবি দেখতে হবে

৬০০টি মানে ৬০০টি **pixel–month sample**, ৬০০টি ছবি নয়। আগের নিয়মে প্রতিটিতে অন্তত ১৪ দিনের ব্যবধানে দুইটি গ্রহণযোগ্য তারিখ দরকার: কমপক্ষে **১২০০টি পরিষ্কার তারিখের বিচার**। সব prepared view-ও দেখতে হবে; পুরনো নিয়মে অন্তত তিনটি prepared view থাকায় অন্তত **১৮০০টি image view** লাগবে, এবং মোট বাস্তব সংখ্যা তার বেশি হতে পারে। নতুন ছবির তালিকা প্রস্তুত হয়নি বলে এখন exact image count বলা সম্ভব নয়। একই sample-এর একাধিক দিনকে নতুন independent sample হিসেবে গোনা যাবে না।

এটি **৬০০টি গ্রহণযোগ্য independent reference-এর লক্ষ্য**, ৬০০টি click/attempt-এ কাজ শেষ হওয়ার প্রতিশ্রুতি নয়। বর্তমান ৭২০টির মধ্যে ১৩৮টির required dated support নেই; দুই group-এর support-ও আগের minimum-এর কম। অনিশ্চিত উত্তর বাদ দিয়ে বা সুবিধার নমুনা বসিয়ে লক্ষ্য পূরণ দেখানো যাবে না। Original sampling weights-সহ unknown bounds রাখতে হবে। পুরনো assisted উত্তর নতুন independent reference হয়ে যায়নি; নতুন representative blinded reference design আগে freeze করতে হবে।

এই হিসাব চার মাসের overall agreement-এর জন্য। প্রতিটি জেলা/মাস/class-এর ±৫ precision বা ২০০০–২০২৪ সালের permanent/seasonal accuracy এতে প্রতিষ্ঠিত হবে না। মেঘ, reference ভুল, registration ও within-month পরিবর্তনের uncertainty এই sampling margin-এ অন্তর্ভুক্ত নয়।

## পদ্ধতির সূত্র ও software acknowledgement

Olofsson, P., Foody, G. M., Herold, M., Stehman, S. V., Woodcock, C. E., & Wulder, M. A. (2014). Good practices for estimating area and assessing accuracy of land change. *Remote Sensing of Environment, 148*, 42–57. https://doi.org/10.1016/j.rse.2014.02.015 । Relevant full-text sections reviewed: §5.1.1–5.1.2, pp. 53–54; response uncertainty §3.5. Not a systematic review or whole-article review. The project-specific numerical result is calculated here, not a number stated in that paper.

Procedural skill acknowledgement: Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv preprint. https://doi.org/10.48550/arXiv.2609.00065 . Current metadata verified on arXiv; abstract/metadata only, not methodological evidence for this numerical calculation.

Reproduce: `C:/Users/Admin/.codex/research/environments/science/Scripts/python.exe postprocessing/calculate_accuracy_sample_size.py`। শুধু Python standard library; original inputs, labels, UI, scientific pipeline ও protocol অপরিবর্তিত। Input hashes এবং group-wise allocation: `sample_size_calculation.json`।
'''
    (OUT / 'CALCULATION_BN.md').write_text(report, encoding='utf-8')
    print(json.dumps({k: result[k] for k in (
        'computed_accepted_reference_total', 'rounded_recommended_accepted_reference_total',
        'computed_halfwidth', 'rounded_recommended_halfwidth', 'original_inputs_unchanged')}, indent=2))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
