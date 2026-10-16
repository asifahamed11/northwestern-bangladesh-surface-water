"""Negative checks use copies of the genuine result tables; originals stay read-only."""
import pandas as pd
import pytest
from reproduce_reported_results import compare, TABLES


def test_changed_endpoint_is_rejected():
    path = TABLES / 'primary_endpoint_changes.csv'
    frame = pd.read_csv(path)
    frame.loc[0, 'endpoint_change_km2'] += 1
    with pytest.raises(AssertionError): compare('tampered endpoint', frame, path, ['region', 'source_class'])


def test_unknown_accuracy_cannot_be_replaced_with_zero():
    path = TABLES / 'proxy_agreement_and_unknown_ranges.csv'
    frame = pd.read_csv(path)
    assert pd.isna(frame.loc[0, 'physical_accuracy_lower'])
    frame.loc[0, 'physical_accuracy_lower'] = 0
    with pytest.raises(AssertionError): compare('missing is not zero', frame, path, ['route', 'frame'])


def test_missing_outcome_row_is_rejected():
    path = TABLES / 'reference_outcome_accounting.csv'
    frame = pd.read_csv(path).iloc[1:].copy()
    with pytest.raises(AssertionError): compare('missing outcome', frame, path, ['assisted_origin'])
