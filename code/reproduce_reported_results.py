"""Replay reported calculations from the genuine packaged regional/export inputs.

This is a computational reproduction from exported/aggregated observations, not
an independent classification validation or a rerun of raw-pixel preprocessing.
Original scientific modules and reference tables are read without modification.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import contextlib
import hashlib
import importlib.util
import json
import shutil
import sys

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / 'code'
sys.path[:0] = [str(CODE), str(CODE / 'postprocessing')]
TABLES = ROOT / 'data/tables'
INPUTS = ROOT / 'data/inputs'
CHECKS = []


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return pd.read_csv(path)


def compare(name, actual, expected, keys):
    reference = read(expected)
    assert set(actual.columns) == set(reference.columns), (name, 'column mismatch')
    a = actual[reference.columns].sort_values(keys).reset_index(drop=True)
    b = reference.sort_values(keys).reset_index(drop=True)
    assert_frame_equal(a.isna(), b.isna(), check_dtype=False)
    a, b = a.where(a.notna(), np.nan), b.where(b.notna(), np.nan)
    # CSV round trips and supported numerical libraries can differ in their last
    # floating-point digits. Null locations and categorical values must match.
    assert_frame_equal(a, b, check_dtype=False, check_exact=False, rtol=1e-7, atol=1e-9)
    CHECKS.append({'calculation': name, 'rows': len(a), 'columns': len(a.columns),
                   'reference': expected.relative_to(ROOT).as_posix(),
                   'reference_sha256': sha(expected), 'match': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reproduced/review_run')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Choose a new output directory; completed runs are retained.'
    for name in ['code', 'data', 'figures', 'manuscript', 'provenance', 'docs', '.git']:
        protected = (ROOT / name).resolve()
        assert out != protected and not out.is_relative_to(protected), 'Output would overwrite research materials.'
    assert out != ROOT
    manifest = json.loads((ROOT / 'provenance/REPOSITORY_MANIFEST.json').read_text(encoding='utf-8'))
    scientific_payload = [r for r in manifest['files'] if r['file'].startswith(('code/', 'data/'))]
    for row in scientific_payload:
        path = (ROOT / row['file']).resolve()
        assert path.is_relative_to(ROOT) and sha(path) == row['sha256'], 'Changed or missing input: ' + row['file']
    out.mkdir(parents=True)
    try:
        run(out)
        for row in scientific_payload:
            assert sha(ROOT / row['file']) == row['sha256'], 'Protected file changed during replay: ' + row['file']
        record = {'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS',
                  'scope': 'Replay of reported statistical calculations from packaged genuine regional summaries and Earth Engine CSV exports.',
                  'independent_scientific_validation': False, 'raw_pixel_preprocessing_repeated': False,
                  'source_acquisition_started': False, 'original_results_overwritten': False,
                  'tolerances': {'relative': 1e-7, 'absolute': 1e-9},
                  'checks': CHECKS, 'python': sys.version,
                  'verified_file_count': len(scientific_payload), 'protected_files_unchanged_after_replay': True,
                  'entrypoint_sha256': sha(Path(__file__)),
                  'limitations': ['Regional raster aggregation and raw dated-crop calibration are upstream stages and are not re-executed by this command.',
                                  'Agreement remains conditional proxy agreement; recovery durations remain unidentifiable.']}
        (out / 'REPRODUCTION_REPORT.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(f'PASS: {len(CHECKS)} reproduced result tables; original files unchanged. Report: {out / "REPRODUCTION_REPORT.json"}')
    except Exception as error:
        (out / 'REPRODUCTION_REPORT.json').write_text(json.dumps({'status': 'FAIL', 'error': str(error), 'completed_checks': CHECKS}, indent=2), encoding='utf-8')
        raise


def run(out):
    from research_pipeline.common import load_config
    from research_pipeline.models import annual_trends, annual_climate_models
    from research_pipeline.drought import spi_series
    from automatic_water import analyze as radar
    from automatic_water import analyze_dw_sensitivity as dw
    from automatic_water.finalize_sensitivity_results import recovery_checks
    from postprocessing import annual_quality_sensitivity as effort
    from postprocessing.finalize_code_only_research import comparison_metrics, bootstrap_metrics

    config = load_config(CODE / 'research_pipeline/config.json')
    annual = read(TABLES / 'annual_common_support_water.csv')
    climate = read(INPUTS / 'monthly_climate.csv')
    assert len(climate) == 1200 and not climate.duplicated(['region', 'year', 'month']).any()
    assert len(annual) == 100 and not annual.duplicated(['region', 'year']).any()
    annual_out = out / 'annual'; annual_out.mkdir()
    endpoints = []
    for region, part in annual.groupby('region', sort=False):
        indexed = part.set_index('year')
        for cls in ['seasonal', 'permanent']:
            a, b = [float(indexed.loc[year, cls + '_water_area_km2']) for year in [2000, 2021]]
            endpoints.append({'region': region, 'source_class': cls, 'area_2000_km2': a,
                              'area_2021_km2': b, 'endpoint_change_km2': b-a,
                              'endpoint_change_pct': 100*(b-a)/a,
                              'scope': 'primary_2000_2021_fixed_annual_cohort'})
    endpoint_frame = pd.DataFrame(endpoints)
    endpoint_frame.to_csv(annual_out / 'primary_endpoint_changes.csv', index=False)
    compare('Annual endpoints', endpoint_frame, TABLES / 'primary_endpoint_changes.csv', ['region', 'source_class'])
    annual_trends(annual, config, annual_out)
    compare('Annual trends', read(annual_out / 'annual_trend_results.csv'), TABLES / 'annual_trend_results.csv', ['region', 'scope', 'metric'])
    annual_climate_models(annual, climate, config, annual_out)
    for name, keys in [
        ('annual_climate_model_coefficients.csv', ['region', 'scope', 'source_class', 'term']),
        ('annual_climate_model_status.csv', ['region', 'scope', 'source_class']),
        ('annual_class_climate_adjusted.csv', ['region', 'scope', 'source_class', 'year']),
        ('annual_calendar_cross_validation.csv', ['region', 'source_class', 'test_start_year'])]:
        reference = TABLES / name if (TABLES / name).exists() else TABLES / 'Extended_Diagnostics/annual_jrc' / name
        compare(name, read(annual_out / name), reference, keys)

    # Restore only the original small input layout in the new output directory.
    # This adapts I/O paths; the statistical source modules remain unchanged.
    layout = out / '_original_input_layout'
    (layout / 'NW_Bangladesh_preprocessed').mkdir(parents=True)
    shutil.copy2(INPUTS / 'monthly_climate.csv', layout / 'NW_Bangladesh_preprocessed/monthly_climate.csv')
    effort_out = out / 'observation_sensitivity'; effort_out.mkdir()
    for name in ['annual_common_support_water.csv', 'annual_observation_quality.csv']:
        shutil.copy2(TABLES / name, effort_out / name)
    old_root, old_args = effort.ROOT, sys.argv[:]
    try:
        effort.ROOT = layout
        sys.argv = ['annual_quality_sensitivity.py', '--run', str(effort_out), '--reuse-quality']
        with (effort_out / 'replay.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log): effort.main()
    finally:
        effort.ROOT, sys.argv = old_root, old_args
    name = 'annual_observation_effort_climate_sensitivity.csv'
    compare('Annual effort/processing controls', read(effort_out / name), TABLES / name, ['region', 'source_class', 'setting'])

    # Recheck the actual exported inventories, source metadata and frozen pilot.
    for folder in ['NW_Bangladesh_automatic_water_2015_2024', 'NW_Bangladesh_DW_sensitivity_2015_2024']:
        shutil.copytree(INPUTS / 'earth_engine_exports' / folder, layout / folder)
    (layout / 'automatic_water').mkdir()
    (layout / 'NW_Bangladesh_2000_2024').mkdir()
    shutil.copy2(INPUTS / 'jrc_monthly_2000.tif', layout / 'NW_Bangladesh_2000_2024/jrc_monthly_2000.tif')
    shutil.copy2(CODE / 'automatic_water/DW_SENSITIVITY_SNAPSHOT.json', layout / 'automatic_water/DW_SENSITIVITY_SNAPSHOT.json')
    shutil.copy2(INPUTS / 'dw_threshold_pilot_2024_11.csv', layout / 'dw_threshold_pilot_2024_11.csv')
    old_dw_root, old_radar_root = dw.ROOT, radar.ROOT
    try:
        dw.ROOT = radar.ROOT = layout
        exported, original, settings, _ = dw.audit_downloads(layout / 'NW_Bangladesh_DW_sensitivity_2015_2024')
    finally:
        dw.ROOT, radar.ROOT = old_dw_root, old_radar_root
    long = dw.long_evidence(exported)
    radar_out = out / 'radar'; radar_out.mkdir()
    long.to_csv(radar_out / 'dw_monthly_threshold_evidence.csv', index=False)
    compare('Threshold monthly support', long, TABLES / 'Extended_Diagnostics/radar/dw_monthly_threshold_evidence.csv', ['region', 'water_group', 'threshold', 'year', 'month'])
    pooled = dw.pooled_summary(long)
    pooled.to_csv(radar_out / 'dw_threshold_support_and_agreement.csv', index=False)
    compare('Pooled threshold agreement/support', pooled, TABLES / 'dw_threshold_support_and_agreement.csv', ['region', 'water_group', 'threshold'])

    baseline = read(INPUTS / 'baseline_climate_1981_1999.csv')
    combined = pd.concat([baseline, climate], ignore_index=True)
    rows, calibration = [], []
    for region, part in combined.groupby('region'):
        part = part.sort_values(['year', 'month'])
        index = pd.PeriodIndex(part.period, freq='M')
        assert len(part) == 528 and not index.duplicated().any()
        for scale in [3, 6]:
            values, params = spi_series(part.chirps_rainfall_mm, index, scale, 1981, 2020)
            assert params.status.eq('PASS').all()
            params['region'] = region; calibration.append(params)
            rows += [{'region': region, 'scale_months': scale, 'period': str(t), 'spi': v}
                     for t, v in values[values.index.year >= 2000].items()]
    spi = pd.DataFrame(rows)
    spi.to_csv(radar_out / 'spi_indices.csv', index=False)
    compare('SPI history', spi, TABLES / 'Extended_Diagnostics/radar/spi_indices.csv', ['region', 'scale_months', 'period'])
    params = pd.concat(calibration, ignore_index=True)
    params.to_csv(radar_out / 'spi_calibration_parameters.csv', index=False)
    compare('SPI calibration', params, TABLES / 'Extended_Diagnostics/radar/spi_calibration_parameters.csv', ['region', 'scale_months', 'calendar_month'])
    envelopes = radar.add_envelopes(original)
    radar.fit_envelope_models(envelopes, climate, radar_out)
    name = 'exploratory_climate_envelope_models.csv'
    compare('Radar endpoint regressions', read(radar_out / name), TABLES / name, ['region', 'water_group', 'envelope_endpoint'])

    # This expected primary table is used by the original function's internal
    # primary/sensitivity consistency assertion, not to calculate the events.
    shutil.copy2(TABLES / 'radar_automated_recovery_intervals.csv', radar_out / 'radar_automated_recovery_intervals.csv')
    recovery_checks(original, spi, radar_out)
    name = 'exploratory_recovery_support_sensitivity.csv'
    compare('All nine recovery specifications', read(radar_out / name), TABLES / name,
            ['coverage_gate', 'minimum_reference_count', 'region', 'water_group', 'onset_period', 'climate_end_period'])

    points = read(TABLES / 'pixel_month_comparisons.csv')
    masks = [('ALL_FOUR_MONTHS', np.ones(len(points), dtype=bool))]
    for col in ['region', 'period', 'stratum']:
        masks += [(col + ':' + str(group), points[col].eq(group).to_numpy()) for group in sorted(points[col].unique())]
    for (region, period), group in points.groupby(['region', 'period']):
        masks.append(('region_period:' + region + ':' + period, points.index.isin(group.index)))
    rows = []
    for route, field in [('AUTOMATED_S2_PROXY_ONLY', 'automated_proxy'), ('ASSISTED_S2_PROXY', 'assisted_proxy')]:
        for name, mask in masks:
            sub = points.loc[mask]
            p, q, w, s = [sub[c].to_numpy() for c in ['jrc_monthly_binary_class', field, 'design_weight_km2_month', 'stratum']]
            rows.append({'route': route, 'frame': name, **comparison_metrics(p, q, w),
                         **bootstrap_metrics(p, q, w, s), 'is_independent_accuracy': False})
    proxy = pd.DataFrame(rows)
    proxy_out = out / 'dated_comparison'; proxy_out.mkdir()
    proxy.to_csv(proxy_out / 'proxy_agreement_and_unknown_ranges.csv', index=False)
    compare('Weighted proxy comparisons and bootstrap intervals', proxy, TABLES / 'proxy_agreement_and_unknown_ranges.csv', ['route', 'frame'])
    counts = points.groupby('assisted_origin').agg(samples=('sample_id', 'size'), design_weight=('design_weight_km2_month', 'sum')).reset_index()
    counts['weighted_fraction'] = counts.design_weight / counts.design_weight.sum()
    counts.to_csv(proxy_out / 'reference_outcome_accounting.csv', index=False)
    compare('All 720 dated outcomes', counts, TABLES / 'reference_outcome_accounting.csv', ['assisted_origin'])


if __name__ == '__main__': main()
