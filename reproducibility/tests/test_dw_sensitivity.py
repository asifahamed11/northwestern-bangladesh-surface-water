"""Temporary algorithm fixtures only; never exported as study/reference data."""
import numpy as np
import pandas as pd
import pytest
from test_automatic_water import roster
from automatic_water.analyze_dw_sensitivity import (
    METHOD,AREA_NAMES,PROPERTIES,validate_frame,long_evidence,pooled_summary)

def fixture():
    old=roster();snapshot={'sar_track':'DESCENDING_1','source_snapshot_sha256':'test-only-metadata'}
    f=old[[n for n in PROPERTIES if n not in ['source_snapshot_sha256']]].copy()
    f['method']=METHOD;f['source_snapshot_sha256']=snapshot['source_snapshot_sha256']
    f=f[PROPERTIES]
    for name in AREA_NAMES:f[name]=old.domain_area_km2 if name=='domain_area_km2' else 0.
    return f,old,snapshot

def test_no_observations_remain_unknown_and_agreement_unavailable():
    f,old,snapshot=fixture();validate_frame(f,old,snapshot)
    evidence=long_evidence(f)
    assert evidence.water_lower_fraction.eq(0).all()
    assert evidence.water_upper_fraction.eq(1).all()
    assert evidence.unknown_observation_fraction.eq(1).all()
    assert evidence.sar_conditional_agreement.isna().all()
    summary=pooled_summary(evidence)
    assert summary.sar_pooled_area_month_agreement.isna().all()

def test_unknown_classification_stays_in_upper_envelope():
    f,_,_=fixture();f=f.head(1).copy();domain=float(f.domain_area_km2.iloc[0])
    f['dw_observed_area_km2']=domain
    for t in [50,60,70,80]:
        f[f'dw_t{t}_known_area_km2']=.2*domain;f[f'dw_t{t}_water_area_km2']=.1*domain
    evidence=long_evidence(f)
    assert np.allclose(evidence.water_lower_fraction,.1)
    assert np.allclose(evidence.water_upper_fraction,.9)
    assert np.allclose(evidence.unknown_classification_fraction,.8)

@pytest.mark.parametrize('change',['source','original_radar','pair','nested'])
def test_invalid_controlled_comparison_is_rejected(change):
    f,old,snapshot=fixture()
    if change=='source':f.loc[0,'source_snapshot_sha256']='different'
    elif change=='original_radar':
        f['sar_observed_area_km2']=f.domain_area_km2*.5
    elif change=='pair':f.loc[0,'dw_t50_sar_same_area_km2']=1
    else:
        f['dw_observed_area_km2']=f.domain_area_km2
        f['dw_t60_known_area_km2']=f.domain_area_km2*.1
    with pytest.raises(ValueError):validate_frame(f,old,snapshot)

def test_missing_exports_stop_before_analysis(tmp_path):
    from automatic_water.analyze_dw_sensitivity import audit_downloads
    # The real original checkout may be unavailable in a packaged test run.
    # This check is integration-only and requires its authentic original data.
    from automatic_water.analyze_dw_sensitivity import ROOT
    if not (ROOT/'NW_Bangladesh_automatic_water_2015_2024/auto_settings.csv').is_file():
        pytest.skip('Real original sources not packaged with code')
    with pytest.raises(ValueError,match='Missing sensitivity exports'):
        audit_downloads(tmp_path)
