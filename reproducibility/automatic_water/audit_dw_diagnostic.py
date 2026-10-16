"""Audit real probability-probe CSV without changing any source observations."""
from pathlib import Path
import argparse
import hashlib
import json
import uuid
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PERIODS = [(2018, 3), (2020, 11), (2023, 3), (2024, 11)]
DISTRICTS = ['Naogaon', 'Nawabganj', 'Rajshahi']
PROBS = ['first_scene_water', 'direct_median_water', 'direct_median_land',
         'legacy_median_water', 'legacy_median_land', 'float_branch_water', 'float_branch_land']
COLUMNS = ['district', 'year', 'month', 'jrc_class', 'source_scenes', 'source_unique_days'] + PROBS + [
    'unique_clear_days', 'legacy_water_decision', 'legacy_land_decision',
    'probe_version', 'interpretation', 'missing_marker']

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(frame):
    require(list(frame.columns) == COLUMNS, 'Unexpected diagnostic columns/order')
    require(len(frame) == 120, 'Expected 120 sampled records')
    require(not frame.isna().any().any(), 'Blank/nonparseable field')
    require(frame.probe_version.eq('dw_probability_diagnostic_v2').all(), 'Wrong probe version')
    require(frame.interpretation.eq('QUALITY_PROBE_NOT_GROUND_TRUTH').all(), 'Wrong interpretation')
    require(frame.missing_marker.eq(-9999).all(), 'Missing-value marker changed')
    expected = {(y, m, district, klass): 5 for y, m in PERIODS for district in DISTRICTS for klass in [1, 2]}
    require(frame.groupby(['year', 'month', 'district', 'jrc_class']).size().to_dict() == expected,
            'Missing/unexpected period, district, class, or stratum count')
    numeric = frame[PROBS + ['source_scenes', 'source_unique_days', 'unique_clear_days',
                           'legacy_water_decision', 'legacy_land_decision']].to_numpy(float)
    require(np.isfinite(numeric).all(), 'Nonfinite diagnostic value')
    for column in PROBS:
        values = frame[column]
        require((values.eq(-9999) | values.between(0, 1)).all(), 'Invalid probability: ' + column)
    for column in ['source_scenes', 'source_unique_days', 'unique_clear_days']:
        values = frame[column]
        require(((values >= 0) & values.eq(np.floor(values))).all(), 'Invalid observation count: ' + column)
    require((frame.source_unique_days <= frame.source_scenes).all(), 'More source days than scenes')
    require((frame.unique_clear_days <= frame.source_unique_days).all(), 'More local days than source days')
    for column in ['source_scenes', 'source_unique_days']:
        require(frame.groupby(['year', 'month'])[column].nunique().eq(1).all(), 'Inconsistent global ' + column)
    for column in ['legacy_water_decision', 'legacy_land_decision']:
        require(frame[column].isin([0, 1, -9999]).all(), 'Invalid decision value')
    # Only rows with genuine median values may be tested against the old rule.
    usable = frame[PROBS[1:]].ne(-9999).all(axis=1)
    observed = frame.unique_clear_days.ge(2)
    water = observed & frame.legacy_median_water.ge(.8)
    land = observed & frame.legacy_median_land.ge(.8) & frame.legacy_median_water.le(.2)
    require(frame.loc[usable, 'legacy_water_decision'].eq(water[usable].astype(int)).all(),
            'Water decision disagrees with old 0.8 rule')
    require(frame.loc[usable, 'legacy_land_decision'].eq(land[usable].astype(int)).all(),
            'Land decision disagrees with old 0.8 rule')
    return usable

def audit(path, inventory_path):
    original_bytes = path.read_bytes()
    frame = pd.read_csv(path)
    usable = validate(frame)
    inventory = pd.read_csv(inventory_path)
    for y, m in PERIODS:
        part = inventory[(inventory.dataset == 'DW') & (inventory.year == y) & (inventory.month == m)]
        require(len(part) == 1, 'Missing/duplicate DW source-inventory period')
        probe = frame[(frame.year == y) & (frame.month == m)].iloc[0]
        require(probe.source_scenes == part.actual_images.iloc[0] and
                probe.source_unique_days == part.unique_days.iloc[0], 'Source counts changed since full export')
    sensitivity = []
    for threshold in [.5, .6, .7, .75, .8]:
        eligible = usable & frame.unique_clear_days.ge(2)
        water = eligible & frame.direct_median_water.ge(threshold)
        land = eligible & frame.direct_median_land.ge(threshold) & frame.direct_median_water.le(1-threshold)
        sensitivity.append({'threshold': threshold, 'usable_samples': int(eligible.sum()),
            'water_samples': int(water.sum()), 'nonwater_samples': int(land.sum()),
            'ambiguous_samples': int((eligible & ~(water | land)).sum()),
            'not_observed_samples': int((~eligible).sum()),
            'water_samples_with_jrc_class_2': int((water & frame.jrc_class.eq(2)).sum()),
            'water_samples_with_jrc_class_1': int((water & frame.jrc_class.eq(1)).sum())})
    differences = {}
    for a, b in [('direct_median_water', 'legacy_median_water'), ('direct_median_land', 'legacy_median_land'),
                 ('direct_median_water', 'float_branch_water'), ('direct_median_land', 'float_branch_land')]:
        keep = frame[a].ne(-9999) & frame[b].ne(-9999)
        differences[a + '__' + b] = float((frame.loc[keep, a]-frame.loc[keep, b]).abs().max())
    require(path.read_bytes() == original_bytes, 'Input changed during audit')
    return {'download_structure': 'PASS', 'source_inventory_match': 'PASS',
        'input_path': str(path), 'input_sha256': hashlib.sha256(original_bytes).hexdigest(),
        'rows': len(frame), 'columns': len(frame.columns),
        'usable_monthly_probability_samples': int(usable.sum()),
        'single_first_scene_missing_samples': int(frame.first_scene_water.eq(-9999).sum()),
        'clear_day_min': int(frame.unique_clear_days.min()), 'clear_day_max': int(frame.unique_clear_days.max()),
        'sample_max_water_probability': float(frame.direct_median_water.max()),
        'sample_max_nonwater_probability': float(frame.direct_median_land.max()),
        'branch_max_absolute_differences': differences,
        'sample_old_08_water_decisions': int(frame.legacy_water_decision.eq(1).sum()),
        'sample_old_08_nonwater_decisions': int(frame.legacy_land_decision.eq(1).sum()),
        'threshold_sensitivity': sensitivity,
        'numeric_observations_modified': False,
        'ground_truth_labels_generated': False, 'verified_accuracy': False,
        'full_automatic_analysis_ready': False, 'publication_ready': False,
        'inference': f"The old 0.8 rule classifies {int((frame.legacy_water_decision.eq(1) | frame.legacy_land_decision.eq(1)).sum())} "
            f"of {len(frame)} sampled observations. Maximum median branch differences: {differences}. "
            'This is not proof of a global probability ceiling or calibrated threshold.',
        'limitations': ['JRC strata are automated samples, not independent reference labels.',
            'The 120 samples are not an area-representative accuracy estimate.',
            'No exported point IDs/coordinates; spatial uniqueness cannot be independently checked.',
            'First-scene missing values do not mean monthly missing values.',
            'Whole-domain threshold support must be checked before a revised full export.']}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'auto_dw_probability_diagnostic_v2.csv')
    args = parser.parse_args()
    report = audit(args.input.resolve(), ROOT/'NW_Bangladesh_automatic_water_2015_2024/auto_source_inventory.csv')
    out = ROOT/'dataset-audit'/('dw_probability_diagnostic_' + datetime.now().strftime('%Y%m%d') + '_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    lines = ['# Dynamic World diagnostic যাচাই', '',
        'CSV-তে ১২০টি sample ও ১৯টি column আছে। সব ২৪টি district/period/JRC-class stratum-এ ৫টি করে row আছে।',
        'Source scene/day count আগের downloaded source inventory-এর সঙ্গে মিলে গেছে।', '',
        f"Usable monthly probability sample: {report['usable_monthly_probability_samples']}; clear observation {report['clear_day_min']}–{report['clear_day_max']} দিন।",
        'Direct/conditional/float median-এর সর্বোচ্চ পার্থক্য: '+str(report['branch_max_absolute_differences']),
        f"প্রথম একটি scene-এ {report['single_first_scene_missing_samples']}টি sample missing। Monthly তথ্য আলাদাভাবে যাচাই করা হয়েছে।", '',
        f"Sample-এ সর্বোচ্চ water probability {report['sample_max_water_probability']:.9f}।",
        f"সর্বোচ্চ nonwater-class probability {report['sample_max_nonwater_probability']:.9f}।",
        f"আগের ০.৮ নিয়মে water sample {report['sample_old_08_water_decisions']}; nonwater sample {report['sample_old_08_nonwater_decisions']}।", '',
        '| Probability সীমা | Water sample | Nonwater sample | Ambiguous sample |',
        '|---|---:|---:|---:|']
    for row in report['threshold_sensitivity']:
        lines.append(f"| {row['threshold']:.2f} | {row['water_samples']} | {row['nonwater_samples']} | {row['ambiguous_samples']} |")
    lines += ['', 'এগুলো sensitivity diagnostic; verified accuracy, পুরো এলাকার water area বা খরার recovery ফল নয়।',
        'JRC class দিয়ে sample নেওয়া হয়েছে; এটিকে independent reference label বলা যাবে না।',
        'Threshold-এর পরে selected sample-এর JRC stratum counts summary.json-এ আছে; এই তুলনা accuracy calibration নয়।',
        '০.৮ সীমা পুরো এলাকার জন্য অকার্যকর কি না এবং বিকল্প সীমায় কত support থাকে তা ছোট pilot export-এ যাচাই বাকি।',
        'মূল CSV, main model-এর threshold ও আগের ১৪টি study CSV পরিবর্তন করা হয়নি।', '',
        'Provider documentation: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1',
        'The catalog describes class probabilities and thresholding, but does not prescribe our original 0.8 threshold.',
        'Model paper: https://www.nature.com/articles/s41597-022-01307-4', '',
        'Input SHA256: '+report['input_sha256']]
    (out/'AUDIT_BN.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'report_dir': str(out), **report}, indent=2))

if __name__ == '__main__':
    main()
