"""Tiny algorithm fixtures only; these are never reference labels or study data."""
import numpy as np
import pytest
from rasterio.transform import from_origin
from rasterio.windows import Window
from postprocessing.independent_sensor_check import clipped_overlap_weights,consensus_record,threshold_label

def test_generated_review_viewer_javascript_parses_and_hides_predictions(tmp_path):
    import re,subprocess,shutil,json
    from types import SimpleNamespace
    from postprocessing.independent_sensor_check import viewer
    node=shutil.which('node')
    if node is None:pytest.skip('Node is optional; required here for browser-script syntax check')
    viewer(tmp_path,[SimpleNamespace(sample_id='opaque_id',year=2020,month=11,region='Naogaon')])
    text=(tmp_path/'review.html').read_text(encoding='utf-8')
    script=re.search(r'<script>(.*?)</script>',text,re.S).group(1)
    payload=json.loads(re.search(r'const rows=(\[.*?\]);let pos',script).group(1))
    assert set(payload[0])=={'id','period','region'}
    code=tmp_path/'viewer.js';code.write_text(script,encoding='utf-8')
    result=subprocess.run([node,'--check',str(code)],text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    # Exercise the export with browser-like DOM/storage stubs: a zero label and
    # a multiline note must survive, without acquiring a VERIFIED designation.
    harness=tmp_path/'browser_logic.js'
    harness.write_text(r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements={};for(const name of ['pick','title','image','label','notes'])elements[name]={append(){}};
let exported='',clicked=false;const memory=new Map();
const context={document:{getElementById:n=>elements[n],createElement:n=>({click(){clicked=true}})},
localStorage:{getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)},
Blob:class{constructor(parts){this.parts=parts}},URL:{createObjectURL:b=>{exported=b.parts.join('');return 'local:csv'},revokeObjectURL(){}}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
elements.label.value='0';elements.notes.value='line1\nline2';vm.runInContext('save();download()',context);
assert(clicked);assert(exported.startsWith('\ufeffsample_id,period,preliminary_review,notes'));
assert(exported.includes('"opaque_id","2020-11","0"'));assert(!exported.includes('VERIFIED'));
assert(exported.includes('"line1\nline2"'));
assert(JSON.parse(memory.get('nw-blind-review')).opaque_id.label==='0');
''',encoding='utf-8')
    result=subprocess.run([node,str(harness),str(code)],text=True,capture_output=True)
    assert result.returncode==0,result.stderr

def test_whole_pixel_overlap_is_conserved_across_partial_cells():
    t=from_origin(88,25,.001,.001);win=Window(0,0,5,5)
    weights=clipped_overlap_weights(t,win,(88.0005,24.9975,88.0035,24.9995))
    assert np.count_nonzero(weights)==12 and weights.sum()>0
    a=clipped_overlap_weights(t,win,(88.0005,24.9975,88.002,24.9995))
    b=clipped_overlap_weights(t,win,(88.002,24.9975,88.0035,24.9995))
    np.testing.assert_allclose(weights,a+b,rtol=1e-10,atol=1e-12)

@pytest.mark.parametrize('fraction,support,expected',[(.9,1,1),(.1,1,0),(.5,1,None),(.9,.5,None),(np.nan,1,None)])
def test_ambiguous_or_missing_support_is_not_verified(fraction,support,expected):
    assert threshold_label(fraction,support)==expected

def test_two_sensor_consensus_requires_both_sensors():
    s1=np.full((4,3,3),-20.);s1[3]=3
    s2=np.full((8,3,3),.2);s2[7]=3
    result=consensus_record(np.ones((3,3)),s1,s2,.1,-17)
    assert result['consensus_label']==1 and result['status']=='AUTOMATED_CONSENSUS'
    s1[0]=0
    result=consensus_record(np.ones((3,3)),s1,s2,.1,-17)
    assert result['consensus_label'] is None and result['status']=='SENSOR_DISAGREEMENT'

def test_one_image_scene_is_insufficient_evidence():
    s1=np.full((4,3,3),-20.);s1[3]=1
    s2=np.full((8,3,3),.2);s2[7]=3
    result=consensus_record(np.ones((3,3)),s1,s2,.1,-17)
    assert result['consensus_label'] is None and result['status']=='INSUFFICIENT_PIXEL_SUPPORT'
