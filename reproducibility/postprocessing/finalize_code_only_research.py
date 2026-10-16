"""Finalize real computational evidence without manufacturing reference truth.

Uses existing isolated research dependencies and frozen project inputs. No remote
Earth Engine calls, new labels, threshold optimization, or gap interpolation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'code_only_final_20261016'
ANNUAL = ROOT / 'research_outputs/analysis_20261013_completed_data'
SENS = ROOT / 'automatic_water_outputs/sensitivity_20261015_115522_c3ef05'
BLIND = ROOT / 'independent_accuracy_20261015'
ASSISTED = ROOT / 'assisted_water_screening_20261015'
DATED = ASSISTED / 'date_review_v2'
BACKUP = ROOT / 'dated_water_backup_recovered_20261016_82bb0063.json'
HUMAN_CSV = ROOT / 'dated_water_labels_2026-10-15T18-04-25.751Z.csv'
SEED, REPLICATES = 20261016, 2000
ROUTES = ('AUTOMATED_S2_PROXY_ONLY', 'ASSISTED_S2_PROXY')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('Duplicate JSON key: ' + k)
            out[k] = v
        return out
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write(path, value):
    Path(path).write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def csv_table(path):
    return pd.read_csv(path)


def comparison_metrics(prediction, proxy, weights):
    p, q, w = np.asarray(prediction), np.asarray(proxy, dtype=float), np.asarray(weights, dtype=float)
    require(p.ndim == q.ndim == w.ndim == 1 and len(p) == len(q) == len(w) > 0, 'Incompatible comparison arrays')
    require(np.isin(p, [0, 1]).all(), 'Invalid target binary class')
    require(np.isfinite(w).all() and (w > 0).all(), 'Invalid design weights')
    require(not np.isinf(q).any() and np.isin(q[np.isfinite(q)], [0, 1]).all(), 'Invalid proxy class; missing is NaN')
    known = np.isfinite(q)
    same = known & (p == q)
    total, assigned = w.sum(), w[known].sum()
    unknown, matching = w[~known].sum(), w[same].sum()
    bounded = lambda value: float(np.clip(value, 0, 1))
    return {
        'planned_samples': len(p), 'assigned_samples': int(known.sum()),
        'unassigned_samples': int((~known).sum()), 'matching_assigned_samples': int(same.sum()),
        'total_design_weight_km2_month': total,
        'assigned_design_weight_fraction': bounded(assigned / total),
        'unassigned_design_weight_fraction': bounded(unknown / total),
        'conditional_label_agreement': bounded(matching / assigned) if assigned else None,
        'binary_completion_lower': bounded(matching / total),
        'binary_completion_upper': bounded((matching + unknown) / total),
        'physical_accuracy_lower': None, 'physical_accuracy_upper': None,
        'independent_reference_accuracy': None,
    }


def bootstrap_metrics(prediction, proxy, weights, strata, replicates=REPLICATES, seed=SEED):
    """Unit resampling is pixel-month within original strata, never scene-date."""
    p, q, w, s = map(np.asarray, (prediction, proxy, weights, strata))
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(s == h) for h in sorted(set(s))]
    ix = np.concatenate([rng.choice(g, size=(replicates, len(g)), replace=True) for g in groups], axis=1)
    wb, qb, pb = w[ix], q[ix], p[ix]
    known = np.isfinite(qb)
    same = known & (pb == qb)
    total = wb.sum(axis=1)
    known_w = (wb * known).sum(axis=1)
    same_w = (wb * same).sum(axis=1)
    unknown_w = (wb * ~known).sum(axis=1)
    conditional = np.full(replicates, np.nan)
    np.divide(same_w, known_w, out=conditional, where=known_w > 0)
    finite = conditional[np.isfinite(conditional)]
    degenerate = bool(finite.size and np.ptp(finite) < 1e-12)
    ci = np.quantile(finite, [.025, .975]).tolist() if finite.size and not degenerate else [None, None]
    return {
        'conditional_agreement_bootstrap_lower95': ci[0], 'conditional_agreement_bootstrap_upper95': ci[1],
        'completion_range_outer_bootstrap_lower95': float(np.clip(np.quantile(same_w / total, .025), 0, 1)),
        'completion_range_outer_bootstrap_upper95': float(np.clip(np.quantile((same_w + unknown_w) / total, .975), 0, 1)),
        'conditional_percentile_bootstrap_degenerate': degenerate,
        'conditional_interval_note': 'Not reported when no assigned pairs exist or empirical resampling has no variation. Sample-perfect agreement does not prove zero population disagreement.',
        'bootstrap_replicates': replicates, 'bootstrap_seed': seed,
        'bootstrap_unit': 'pixel-month within original 24 strata; dates are not resampled as independent units',
        'interval_scope': 'Approximate sampling uncertainty only; does not cover reference truth, timing, radiometry or registration',
    }


def declared_hashes():
    expected = {}

    def add(path, value):
        path = Path(path).resolve()
        if path in expected:
            require(expected[path] == value, 'Conflicting frozen hashes: ' + str(path))
        expected[path] = value

    with (ROOT / 'NW_Bangladesh_preprocessed/input_manifest.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            require(r['sha256_before'] == r['sha256_after'], 'Original preprocessing mutated input')
            add(ROOT / 'NW_Bangladesh_2000_2024' / r['filename'], r['sha256_after'])
    run = read(ANNUAL / 'run_manifest.json')
    for rel, h in run['additional_input_and_code_hashes'].items():
        add(ROOT / rel, h)
    post = read(ANNUAL / 'postprocessing_manifest.json')
    for rel, h in post['postprocessing_outputs_sha256'].items():
        add(ANNUAL / rel, h)
    add(ANNUAL / 'run_manifest.json', post['primary_run_manifest_sha256'])
    for filename in ('input_sha256.json', 'climate_input_sha256.json'):
        for r in read(SENS / filename):
            add(r['path'], r['sha256'])
    for rel, h in read(BLIND / 'review_manifest.json')['frozen_evaluation_inputs_sha256'].items():
        add(BLIND / rel, h)
    dated_manifest = read(DATED / 'review_manifest.json')
    add(DATED / 'dated_review_dataset.json', dated_manifest['dataset_sha256'])
    audit = read(DATED / 'csv_audits/audit_82bb0063/audit_result.json')
    for rel, h in audit['source_inputs_sha256'].items():
        add(rel, h)
    add(BACKUP, audit['recovered_backup_sha256'])
    # Recheck actual small TIFF/PNG/XML evidence, not just presence of a manifest.
    for point in read(DATED / 'dated_review_dataset.json')['rows']:
        for s in point['scenes']:
            add(ROOT / s['image_path'], s['image_sha256'])
            add(ROOT / s['source_original_image_path'], s['image_sha256'] if s['image_path'] == s['source_original_image_path'] else
                read(BLIND / 'evidence' / point['sample_id'] / (s['item_id'] + '.json'))['image_sha256'])
            meta = read(BLIND / 'evidence' / point['sample_id'] / (s['item_id'] + '.json'))
            add(BLIND / meta['tiff_path'], s['source_tiff_sha256'])
            cal = BLIND / meta['calibration_path']
            add(cal.with_suffix('.xml'), s['calibration_xml_sha256'])
    return expected


def verify_hashes(expected, output):
    records = []
    print(f'Verifying {len(expected)} frozen files ({sum(p.stat().st_size for p in expected)/1e9:.2f} GB)...', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(digest, p): (p, h) for p, h in expected.items()}
        for i, future in enumerate(as_completed(jobs), 1):
            p, h = jobs[future]
            actual = future.result()
            require(actual == h, 'Frozen input checksum mismatch: ' + str(p))
            records.append({'path': str(p.relative_to(ROOT)), 'sha256': actual, 'bytes': p.stat().st_size})
            if i % 500 == 0 or i == len(expected):
                print(f'Frozen checksums: {i}/{len(expected)}', flush=True)
    write(output / 'verified_source_hashes.json', sorted(records, key=lambda r: r['path']))
    return records


def actual_human_summaries(csv_path=HUMAN_CSV, backup_path=BACKUP):
    js = r"""
const fs=require('fs'),path=require('path');
const root=process.argv[1],D=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const C=require(path.join(root,'postprocessing','dated_water_core.js'));
const state=C.importBackup(fs.readFileSync(process.argv[3],'utf8'),D);
const summaries=D.rows.map(r=>({sample_id:r.sample_id,...C.summary(C.entry(state.entries[r.sample_id]),r)}));
const dates=D.rows.flatMap(r=>Object.entries(state.entries[r.sample_id].dates).map(([scene_id,a])=>({sample_id:r.sample_id,scene_id,label:a.label})));
process.stdout.write(JSON.stringify({summaries,dates,canonical_csv:C.dateCSV(D,state.entries)}));
"""
    node = shutil.which('node')
    require(node is not None, 'Node required for the actual label-app parser')
    result = subprocess.run([node, '-e', js, str(ROOT), str(DATED / 'dated_review_dataset.json'), str(backup_path)], capture_output=True, text=True, encoding='utf-8', check=True)
    data = json.loads(result.stdout)
    exported = list(csv.reader(io.StringIO(data.pop('canonical_csv').lstrip('\ufeff'))))
    with Path(csv_path).open(encoding='utf-8-sig', newline='') as f:
        human = list(csv.reader(f))
    require(exported == human, 'Actual user CSV does not match actual backup/app re-export')
    require(len(data['dates']) == 694, 'Unexpected actual dated answer count')
    return data


def build_comparisons(output, human):
    screen = read(ASSISTED / 'screening_dataset.json')
    plan = read(BLIND / 'private/validation_sample_plan.json')
    by_id = {r['sample_id']: r for r in screen['rows']}
    hs = {r['sample_id']: r for r in human['summaries']}
    ha = {(r['sample_id'], r['scene_id']): r['label'] for r in human['dates']}
    require(len(by_id) == len(hs) == len(plan) == 720, 'Full original frame not retained')
    rows, dates = [], []
    for p in plan:
        sid = p['sample_id']
        s, h = by_id[sid], hs[sid]
        automated = s['screening']['automated_water']
        assigned_human = int(h['water']) if h['origin'] == 'HUMAN_DATES_CONSISTENT' and h['water'] in ('0', '1') else None
        hybrid = automated if automated is not None else assigned_human
        rows.append({
            'sample_id': sid, 'region': p['region'], 'period': p['period'], 'stratum': p['stratum'],
            'jrc_monthly_binary_class': p['predicted_water'],
            'design_weight_km2_month': p['population_pixels'] / p['planned_samples'] * p['pixel_area_km2'],
            'automated_proxy': automated, 'assisted_proxy': hybrid,
            'screening_origin': s['screening']['category'], 'assisted_origin': h['origin'],
            'temporal_variation_in_human_answers': h['temporal_change'],
            'uncertain_human_date_present': h['has_uncertain_date'],
            'required_dates': h['required_dates'], 'human_dates_answered': h['answered_dates'],
            'independent_reference_water': None, 'independent_reference_eligible': False,
        })
        for scene in s['spectral_evidence']:
            label = ha.get((sid, scene['item_id']))
            dates.append({
                'sample_id': sid, 'region': p['region'], 'period': p['period'], 'scene_id': scene['item_id'],
                'acquisition_date': scene['date'], 'clear_fraction': scene['clear_fraction'],
                'spectral_rule_proxy': scene['scene_automated_label'], 'actual_human_answer': label,
                'human_binary_answer': int(label) if label in ('0', '1') else None,
                'mndwi_median_display_diagnostic_only': scene['median_indices_unweighted']['mndwi'],
                'uninterpretable_radiometry_fraction': scene['uninterpretable_radiometry_fraction'],
                'independent_reference_water': None,
            })
    points, dated = pd.DataFrame(rows), pd.DataFrame(dates)
    require(len(points) == 720 and points.sample_id.nunique() == 720, 'Missing or duplicate sample')
    require(len(dated) == 3022 and not dated.duplicated(['sample_id', 'scene_id']).any(), 'Missing or duplicate acquisition')
    expected_assigned=sum(r['automated_proxy'] is not None or r['assisted_origin']=='HUMAN_DATES_CONSISTENT' for r in rows)
    require(points.assisted_proxy.notna().sum() == expected_assigned and points.automated_proxy.notna().sum() == 337, 'Assisted outcome accounting does not match actual versioned answers')
    require(points[points.temporal_variation_in_human_answers].assisted_proxy.isna().all(), 'Temporal label conflicts collapsed')
    require(points[points.screening_origin == 'QUALITY_LIMITED'].assisted_proxy.isna().all(), 'Quality-limited samples imputed')
    points.to_csv(output / 'Tables/pixel_month_comparisons.csv', index=False)
    dated.to_csv(output / 'Tables/actual_dated_observations.csv', index=False)
    masks = [('ALL_FOUR_MONTHS', np.ones(len(points), dtype=bool))]
    for col in ('region', 'period', 'stratum'):
        masks += [(col + ':' + str(g), points[col].eq(g).to_numpy()) for g in sorted(points[col].unique())]
    for (r, t), group in points.groupby(['region', 'period']):
        masks.append(('region_period:' + r + ':' + t, points.index.isin(group.index)))
    summaries = []
    for route, field in zip(ROUTES, ('automated_proxy', 'assisted_proxy')):
        for name, mask in masks:
            subset = points.loc[mask]
            p, q, w, s = [subset[c].to_numpy() for c in ('jrc_monthly_binary_class', field, 'design_weight_km2_month', 'stratum')]
            summaries.append({'route': route, 'frame': name, **comparison_metrics(p, q, w),
                              **bootstrap_metrics(p, q, w, s), 'is_independent_accuracy': False})
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / 'Tables/proxy_agreement_and_unknown_ranges.csv', index=False)
    counts = points.groupby('assisted_origin').agg(samples=('sample_id', 'size'), design_weight=('design_weight_km2_month', 'sum')).reset_index()
    counts['weighted_fraction'] = counts.design_weight / counts.design_weight.sum()
    counts.to_csv(output / 'Tables/reference_outcome_accounting.csv', index=False)
    paired = dated[dated.human_binary_answer.notna() & dated.spectral_rule_proxy.notna() & dated.clear_fraction.ge(.95)]
    pair_summary = {
        'actual_human_date_answers': len(ha), 'human_answer_counts': dict(Counter(ha.values())),
        'selected_human_review_points': int(points.human_dates_answered.gt(0).sum()),
        'scene_rule_human_paired_binary_dates': len(paired), 'paired_points': paired.sample_id.nunique(),
        'paired_matching_dates': int(paired.human_binary_answer.eq(paired.spectral_rule_proxy).sum()),
        'paired_date_matching_fraction': float(paired.human_binary_answer.eq(paired.spectral_rule_proxy).mean()) if len(paired) else None,
        'scope': 'Descriptive comparison on model-selected difficult dates only. Not representative accuracy; repeated dates are dependent.',
    }
    write(output / 'human_assisted_descriptives.json', pair_summary)
    return points, summary, counts, pair_summary


def reconcile_previous_results(output):
    """Recompute key numbers from actual tables and audited exports; no refitting."""
    sys.path.insert(0, str(ROOT))
    from automatic_water.analyze_dw_sensitivity import audit_downloads, long_evidence, pooled_summary
    f, _, _, _ = audit_downloads(ROOT / 'NW_Bangladesh_DW_sensitivity_2015_2024')
    fresh_long = long_evidence(f)
    prior_long = csv_table(SENS / 'dw_monthly_threshold_evidence.csv')
    require(fresh_long.shape == prior_long.shape and list(fresh_long) == list(prior_long), 'Threshold evidence layout changed')
    for c in fresh_long:
        if pd.api.types.is_numeric_dtype(fresh_long[c]):
            require(np.allclose(fresh_long[c], prior_long[c], rtol=1e-8, atol=1e-8, equal_nan=True), 'Threshold recalculation differs: ' + c)
        else:
            require(fresh_long[c].fillna('').astype(str).equals(prior_long[c].fillna('').astype(str)), 'Threshold labels differ: ' + c)
    pooled = pooled_summary(fresh_long)
    pooled.to_csv(output / 'Tables/dw_threshold_support_and_agreement.csv', index=False)
    annual = csv_table(ANNUAL / 'annual_common_support_water.csv')
    endpoints = csv_table(ANNUAL / 'primary_endpoint_changes.csv')
    for r in endpoints.itertuples():
        a = annual[annual.region == r.region].set_index('year')[r.source_class + '_water_area_km2']
        require(np.isclose(r.area_2000_km2, a[2000]) and np.isclose(r.area_2021_km2, a[2021]), 'Annual endpoint mismatch')
        require(np.isclose(r.endpoint_change_pct, 100 * (a[2021] - a[2000]) / a[2000]), 'Endpoint percentage mismatch')
    effort = csv_table(ANNUAL / 'annual_observation_effort_climate_sensitivity.csv')
    step = effort[effort.setting.eq('mean_wet_effort_and_2016_asset_step')]
    require(len(step) == 8 and step.status.eq('PASS').all(), 'Incomplete annual source-boundary sensitivity')
    permanent = step[step.source_class.eq('permanent')]
    require((permanent.lower95.le(0) & permanent.upper95.ge(0)).all(), 'Permanent source-boundary limitation changed')
    seasonal = step[step.source_class.eq('seasonal') & step.region.isin(['Naogaon', 'Rajshahi'])]
    require(seasonal.upper95.lt(0).all() and seasonal.p_adjusted_BY_within_setting_primary_districts.lt(.05).all(), 'Bounded seasonal trend claim changed')
    radar = csv_table(SENS / 'exploratory_climate_envelope_models.csv')
    events = csv_table(SENS / 'radar_automated_recovery_intervals.csv')
    sensitivity = csv_table(SENS / 'exploratory_recovery_support_sensitivity.csv')
    print('Recovery columns:', ', '.join(events.columns), flush=True)
    # Exact stored statuses are checked without reclassifying any missing duration.
    require(len(events) == 108, 'Radar recovery record count changed')
    require(Counter(events.status) == {'PRE_EVENT_SUPPORT_OR_REFERENCE_GAP': 84, 'DROUGHT_SUPPORT_OR_REFERENCE_GAP': 24}, 'Recovery support status changed')
    require(len(sensitivity) == 972, 'All nine recovery specifications must be retained')
    duration_columns = ['recovery_min_months', 'recovery_max_months', 'recovery_months']
    require(events[duration_columns].isna().all().all(), 'Unexpected resolved primary recovery')
    require(sensitivity[duration_columns].isna().all().all(), 'Unexpected resolved sensitivity recovery')
    require(sensitivity.groupby(['coverage_gate', 'minimum_reference_count']).size().eq(108).all()
            and sensitivity.groupby(['coverage_gate', 'minimum_reference_count']).ngroups == 9, 'Incomplete nine-specification recovery accounting')
    for src, names in ((ANNUAL, ['primary_endpoint_changes.csv', 'annual_common_support_water.csv', 'annual_trend_results.csv',
        'annual_observation_effort_climate_sensitivity.csv', 'annual_climate_model_coefficients.csv', 'annual_observation_quality.csv',
        'annual_predictive_validation_summary.csv', 'monthly_predictive_validation_summary.csv', 'common_support_quality.csv']),
        (SENS, ['exploratory_climate_envelope_models.csv', 'radar_automated_recovery_intervals.csv',
        'exploratory_recovery_support_sensitivity.csv', 'radar_seasonal_reference_support.csv'])):
        for name in names:
            shutil.copy2(src / name, output / 'Tables' / name)
    return {
        'annual_common_support_km2': float(annual[annual.region.eq('All_districts')].common_support_area_km2.iloc[0]),
        'annual_endpoints_union': endpoints[endpoints.region.eq('All_districts')].to_dict('records'),
        'annual_step_sensitivity_all_district_rows': step.to_dict('records'),
        'radar_climate_models_all_rows': radar.to_dict('records'),
        'threshold_export_rows_recomputed': len(f), 'threshold_evidence_rows_recomputed': len(fresh_long),
        'threshold_summary_all_rows': pooled.to_dict('records'),
        'recovery_primary_record_count': len(events), 'recovery_primary_status_counts': dict(Counter(events.status)),
        'recovery_sensitivity_records': len(sensitivity), 'recovery_duration_identified': False,
        'independent_accuracy_established': False,
    }


def plot_evidence(output, points, summary, counts):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # Two discrete sources remain explicitly separate. No old 720-point viewer
    # figure is relabeled as the newer 720-point sample.
    mapping = []
    for src, prefix, names in [
        (ANNUAL / 'Figures', 'annual_', ['01_annual_source_classes_primary', '02_annual_fixed_climate_expectations',
         '03_climate_and_observation_effort_sensitivity', '04_spi3_drought_history', '05_monthly_recovery_observation_gaps',
         '06_annual_observation_effort', '08_annual_transition_primary_pre2022']),
        (SENS / 'Figures', 'radar_', ['01_dw_support_and_envelopes', '02_agreement_and_support', '03_climate_envelope_models', '04_recovery_identifiability'])]:
        for name in names:
            for p in src.glob(name + '.*'):
                dst = output / 'Figures' / (prefix + p.name)
                shutil.copy2(p, dst)
                mapping.append({'destination': str(dst.relative_to(output)), 'source': str(p.relative_to(ROOT)), 'sha256': digest(p)})
    origins = ['AUTO_SCREENED', 'HUMAN_DATES_CONSISTENT', 'HUMAN_TEMPORAL_CHANGE', 'HUMAN_UNCERTAIN_DATES', 'UNRESOLVED_QUALITY']
    labels = ['Automatic proxy', 'Consistent assisted dates', 'Different dated answers', 'Uncertain dated answers', 'Insufficient dated support']
    colors = ['#0072B2', '#009E73', '#D55E00', '#E69F00', '#999999']
    table = counts.set_index('assisted_origin')
    with plt.rc_context({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'}):
        fig, ax = plt.subplots(1, 3, figsize=(12.0, 4.4), layout='constrained')
        values = [int(table.loc[o, 'samples']) for o in origins]
        ax[0].barh(labels, values, color=colors)
        for y, v in enumerate(values): ax[0].text(v + 4, y, str(v), va='center')
        ax[0].invert_yaxis(); ax[0].set(xlabel='Pixel-month samples (total 720)', xlim=(0, 390), title='A. All original outcomes retained')
        weights = [100 * table.loc[o, 'weighted_fraction'] for o in origins]
        ax[1].barh(labels, weights, color=colors)
        for y, v in enumerate(weights): ax[1].text(v + .7, y, f'{v:.1f}%', va='center')
        ax[1].invert_yaxis(); ax[1].set(xlabel='Design-weighted frame (%)', xlim=(0, 100), title='B. Unequal area-time weights')
        ax[1].set_yticklabels([])
        pooled = summary[summary.frame.eq('ALL_FOUR_MONTHS')].set_index('route')
        for y, route in enumerate(ROUTES):
            r = pooled.loc[route]
            ax[2].plot([100*r.binary_completion_lower, 100*r.binary_completion_upper], [y, y], lw=8, color='#BBBBBB', solid_capstyle='butt')
            ax[2].plot(100*r.conditional_label_agreement, y, 'o', color='#0072B2')
        ax[2].set(yticks=[0, 1], yticklabels=['Automatic only', 'Assisted combination'], ylim=(-.7, 1.7), xlim=(-2, 102), xticks=[0, 20, 40, 60, 80, 100],
                  xlabel='JRC / proxy label agreement (%)', title='C. Assigned support and unknowns')
        ax[2].invert_yaxis()
        ax[2].text(.01, .03, 'Dot: conditional agreement\nGrey: binary-completion range\nNeither is independent accuracy', transform=ax[2].transAxes, fontsize=8, va='bottom')
        fig.suptitle('Four sampled months: proxy agreement with unresolved comparisons retained', fontsize=11)
        for ext in ('png', 'svg', 'pdf'):
            fig.savefig(output / 'Figures' / ('new_reference_support_and_agreement.' + ext), dpi=300)
        plt.close(fig)
    write(output / 'figure_sources.json', mapping)
    (output / 'Figures/CAPTIONS.md').write_text(
        '# Figure provenance and caption\n\nThe annual and radar figures retain their original, different periods, cohorts, variables and units. '
        'They were copied byte-for-byte and are not new replications. `figure_sources.json` gives their original locations and digests. '
        'The earlier consensus-viewer figure is excluded because it describes a different 720-point sample.\n\n'
        '**New figure:** All 720 frozen pixel-month samples, four selected months. Counts (A) differ from design-weighted area-time fractions (B). '
        'In C, dots show agreement conditional on assigned proxy labels. Grey ranges retain all unassigned comparison weight under arbitrary binary completion. '
        'These ranges are algebraic, not confidence intervals or physical-accuracy bounds. Approximate within-stratum bootstrap intervals are provided in the underlying table; '
        'scene-date repeats are not independent units. User-provided human labels were assisted and model-selected. Source: Tables/pixel_month_comparisons.csv, '
        'Tables/proxy_agreement_and_unknown_ranges.csv and Tables/reference_outcome_accounting.csv. General-purpose provisional layout; no journal-specific compliance claimed.\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=PACKAGE / 'analysis')
    parser.add_argument('--csv', type=Path, default=HUMAN_CSV)
    parser.add_argument('--backup', type=Path, default=BACKUP)
    args = parser.parse_args()
    output = args.out.resolve()
    require(PACKAGE.resolve() in output.parents, 'Output must remain inside the dedicated code-only package')
    require(not output.exists(), 'Existing analysis is preserved; supply a new --out subdirectory')
    output.mkdir(parents=True)
    for name in ('Tables', 'Figures'):
        (output / name).mkdir()
    shutil.copy2(ROOT/'CURRENT_WATER_REVIEW_STATUS.json',output/'workflow_status_at_analysis_start.json')
    protected = [ROOT / 'CURRENT_WATER_REVIEW_STATUS.json', ROOT / 'paper_scope_20261015/paper_scope.json',
                 ROOT / 'water_reference_labels_user_confirmed_20261015.csv', ROOT / 'water_review_backup_user_confirmed_20261015.json',
                 HUMAN_CSV, BACKUP, args.csv.resolve(),args.backup.resolve(), PACKAGE / 'protocol.json', ASSISTED / 'screening_dataset.json', DATED / 'review_manifest.json']
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    write(output / 'STATUS.json', {'status': 'RUNNING', 'scientific_publication_ready': False})
    try:
        declared=declared_hashes()
        for p in (args.csv.resolve(),args.backup.resolve()):declared[p]=digest(p)
        source_hashes = verify_hashes(declared, output)
        print('Validating actual human backup with original app and exact CSV comparison...', flush=True)
        human = actual_human_summaries(args.csv.resolve(),args.backup.resolve())
        print('Computing all-sample weighted comparisons and stratified uncertainty...', flush=True)
        points, summary, counts, pair = build_comparisons(output, human)
        print('Re-auditing source exports and reconciling prior scientific tables...', flush=True)
        previous = reconcile_previous_results(output)
        plot_evidence(output, points, summary, counts)
        result = {
            'status': 'COMPUTATIONAL_ANALYSIS_COMPLETE_WITH_RESTRICTED_CLAIMS',
            'completed_utc': datetime.now(timezone.utc).isoformat(),
            'protocol_sha256': digest(PACKAGE / 'protocol.json'), 'source_files_verified': len(source_hashes),
            'proxy_comparison': summary[summary.frame.eq('ALL_FOUR_MONTHS')].to_dict('records'),
            'all_point_outcome_counts': counts.to_dict('records'), 'human_assisted_review': pair,
            'previous_results_reconciled': previous,
            'all_720_samples_retained': True, 'actual_scene_point_observations': 3022,
            'thresholds_tuned': False, 'observations_imputed': False, 'new_human_labels_created': 0,
            'independent_accuracy_complete': False, 'recovery_duration_resolved': False,
            'scientific_publication_ready': False, 'manuscript_writing_ready': False,
            'writing_readiness_pending': 'Post-analysis tests, result/claim audit and actual figure inspection must pass before the separate final handoff is published.',
        }
        write(output / 'RESULTS.json', result)
        after = {str(p.relative_to(ROOT)): digest(p) for p in protected}
        require(before == after, 'A protected input or earlier workflow artifact was modified')
        write(output / 'RUN_MANIFEST.json', {
            'python': sys.version, 'numpy': np.__version__, 'pandas': pd.__version__,
            'script_sha256': digest(Path(__file__)), 'protected_inputs_sha256': before,
            'actual_human_csv':str(args.csv.resolve()),'actual_human_backup':str(args.backup.resolve()),
            'protected_inputs_unchanged': before == after, 'seed': SEED, 'bootstrap_replicates': REPLICATES,
            'original_scientific_pipeline_refit': False, 'remote_exports_started': False,
            'scope': 'New weighted secondary proxy comparisons plus current checksum/inventory/numerical audit of prior completed analyses.',
        })
        write(output / 'STATUS.json', {'status': result['status'], 'scientific_publication_ready': False, 'manuscript_writing_ready': False})
        print(json.dumps({'output': str(output), 'status': result['status'], 'source_files_verified': len(source_hashes)}, indent=2))
    except Exception as error:
        write(output / 'STATUS.json', {'status': 'FAILED_NOT_FINALIZED', 'error': str(error), 'scientific_publication_ready': False, 'manuscript_writing_ready': False})
        raise


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    main()
