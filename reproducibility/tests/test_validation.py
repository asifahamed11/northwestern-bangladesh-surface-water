"""Reference-label fixtures are tests, never independent scientific evidence."""
import numpy as np
import pandas as pd
import pytest
from research_pipeline.validation import evaluate_reference

@pytest.fixture
def plan():
    return pd.DataFrame({'sample_id':['a','b','c','d'],'stratum':['dry','dry','wet','wet'],
        'population_pixels':[900,900,100,100],'planned_samples':2,'pixel_area_km2':1.,
        'predicted_water':[0,0,1,1],'year':2020,'month':11})

@pytest.fixture
def config():
    return {'validation_minimum_verified_samples_per_stratum':2,'validation_bootstrap_replicates':20,'random_seed':9}

def labels(plan):
    return pd.DataFrame({'sample_id':plan.sample_id,'reference_water':[0,0,0,0],
        'reference_date':'2020-11-15','reference_source':'Sentinel-2 scene xyz',
        'reference_quality':'VERIFIED'})

def test_design_weights_correct_unequal_class_sampling(tmp_path,plan,config):
    path=tmp_path/'labels.csv'; labels(plan).to_csv(path,index=False)
    result=evaluate_reference(plan,path,config,tmp_path)
    metrics=pd.read_csv(tmp_path/'independent_validation_metrics.csv').iloc[0]
    assert result['status']=='METRICS_COMPUTED'
    assert metrics.overall_area_time_weighted_accuracy==pytest.approx(.9)
    assert metrics.lower95_bootstrap==pytest.approx(.9)

@pytest.mark.parametrize('failure',['unknown','duplicate','bad_value','bad_date','missing_date','self_reference','missing_source'])
def test_bad_independent_labels_rejected(tmp_path,plan,config,failure):
    data=labels(plan)
    if failure=='unknown': data.loc[0,'sample_id']='unknown'
    if failure=='duplicate': data.loc[0,'sample_id']='b'
    if failure=='bad_value': data.loc[0,'reference_water']=2
    if failure=='bad_date': data.loc[0,'reference_date']='2021-11-15'
    if failure=='missing_date': data.loc[0,'reference_date']=''
    if failure=='self_reference': data.loc[0,'reference_source']='JRC GSW'
    if failure=='missing_source': data.loc[0,'reference_source']=''
    path=tmp_path/'labels.csv'; data.to_csv(path,index=False)
    with pytest.raises(ValueError): evaluate_reference(plan,path,config,tmp_path)

def test_incomplete_stratum_never_reports_overall_accuracy(tmp_path,plan,config):
    path=tmp_path/'labels.csv'; labels(plan).iloc[:3].to_csv(path,index=False)
    result=evaluate_reference(plan,path,config,tmp_path)
    assert result['status']=='INCOMPLETE_REFERENCE_LABELS'
    assert pd.read_csv(tmp_path/'independent_validation_metrics.csv').empty

def test_missing_labels_are_explicit(tmp_path,plan,config):
    result=evaluate_reference(plan,tmp_path/'absent.csv',config,tmp_path)
    assert result['status']=='MISSING_REFERENCE_LABELS'
