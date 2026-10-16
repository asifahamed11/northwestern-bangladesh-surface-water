"""Software fixtures only; never independent labels or study observations."""
import copy
import csv
import json
import pytest
import verify_water_labels as V


@pytest.fixture
def pair():
    data={'id':'TEST_DATASET','rows':[
        {'id':'b','region':'Naogaon','year':2020,'month':11,'period':'2020-11','longitude':88.1,'latitude':25.1},
        {'id':'a','region':'Rajshahi','year':2018,'month':3,'period':'2018-03','longitude':88.5,'latitude':24.5}], 'export_order':['a','b']}
    entries=[];rows=[]
    for r,label in zip(data['rows'],['0','1']):
        e={'sample_id':r['id'],'label':label,'notes':'','reason':'','reference_date':'','reference_source':'','evidence_id':'','reviewer':'','attested':False,'updated_at':'2026-10-15T08:00:00.000Z'}
        entries.append(e)
        c=dict.fromkeys(V.CSV_COLUMNS,'');c.update(sample_id=r['id'],region=r['region'],year=str(r['year']),month=str(r['month']),longitude=str(r['longitude']),latitude=str(r['latitude']),reference_quality='PRELIMINARY',preliminary_review=label,evidence_attested='false',reviewed_at=e['updated_at'],dataset_id=data['id']);rows.append(c)
    backup={'schema':V.SCHEMA,'dataset_id':data['id'],'exported_at':'2026-10-15T09:00:00Z','active_id':'b','records':entries}
    return data,list(V.CSV_COLUMNS),rows[::-1],backup


def test_independent_id_join_and_zero(pair):
    d,h,c,b=pair;r=V.audit_pair(h,c,b,d)
    assert r['status']=='PASS' and r['csv_in_original_order'] and r['json_in_display_order']
    assert r['label_counts']=={'1':1,'0':1} and r['status_counts']=={'PRELIMINARY':2}
    assert not r['independent_accuracy_ready'] and r['missing_evidence_for_binary_answers']['reference_date']==2


@pytest.mark.parametrize('change',['duplicate','unknown','coordinate','dataset','forged_verified','answer_shift','date_shift','invalid_label','timestamp_after_export','non_boolean'])
def test_corrupt_inputs_fail_without_editing(pair,change):
    d,h,c,b=pair
    if change=='duplicate':c[0]['sample_id']=c[1]['sample_id']
    if change=='unknown':b['records'][0]['sample_id']='foreign'
    if change=='coordinate':c[0]['longitude']='89.9'
    if change=='dataset':b['dataset_id']='other'
    if change=='forged_verified':c[0]['reference_quality']='VERIFIED';c[0]['reference_water']='1'
    if change=='answer_shift':c[0]['preliminary_review']='0'
    if change=='date_shift':c[0]['reference_date']='2018-04-01'
    if change=='invalid_label':b['records'][0]['label']='3'
    if change=='timestamp_after_export':b['records'][0]['updated_at']='2026-10-15T10:00:00Z'
    if change=='non_boolean':b['records'][0]['attested']='false'
    frozen=copy.deepcopy((d,h,c,b));r=V.audit_pair(h,c,b,d)
    assert r['status']=='FAIL' and r['issues']
    assert (d,h,c,b)==frozen


def test_real_date_and_self_reference_controls():
    e={'label':'1','reference_date':'2020-11-12','reference_source':'TEST independent source','evidence_id':'TEST_ONLY','reviewer':'TEST ONLY','attested':True};r={'period':'2020-11'}
    assert V.status(e,r)=='VERIFIED'
    for patch in [{'reference_date':'2020-11-31'},{'reference_date':'2020-10-12'},{'reference_source':'JRC GSW'},{'evidence_id':''},{'reviewer':''}]:
        assert V.status({**e,**patch},r)!='VERIFIED'
    assert V.status({**e,'attested':False},r)=='PRELIMINARY'


@pytest.mark.parametrize('fraction,support,expected',[(.8,.95,1),(.2,.95,0),(.5,1,None),(.9,.949,None),(None,1,None)])
def test_numeric_cue_boundaries(fraction,support,expected):
    assert V.cue_label(fraction,support)==expected


def test_color_cue_disagreement_and_uncertainty_are_not_truth():
    fields={'optical_water_fraction':.95,'radar_water_fraction':.01,'optical_supported_fraction':1.,'radar_supported_fraction':1.}
    r=V.recompute_cue(fields);assert r['status']=='SENSOR_DISAGREEMENT' and r['consensus_label'] is None
    r=V.recompute_cue({**fields,'optical_water_fraction':.5});assert r['status']=='MIXED_PIXEL'
    r=V.recompute_cue({**fields,'optical_supported_fraction':.3});assert r['status']=='INSUFFICIENT_PIXEL_SUPPORT'


def test_duplicate_json_keys_and_csv_headers_rejected(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"label":"0","label":"1"}')
    with pytest.raises(ValueError):V.json_read(p)
    p=tmp_path/'bad.csv';p.write_text('sample_id,sample_id\na,b')
    with pytest.raises(ValueError):V.csv_read(p)
