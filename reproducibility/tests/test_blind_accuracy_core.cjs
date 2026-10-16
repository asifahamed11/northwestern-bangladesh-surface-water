// Software fixtures only. Never represents study labels or accuracy.
const assert=require('node:assert/strict');
const C=require('../postprocessing/blind_accuracy_core.js');
const r={sample_id:'TEST_ONLY',region:'Fixture',year:2020,month:11,period:'2020-11',longitude:88,latitude:24,
 scenes:[{item_id:'test_a',date:'2020-11-01',clear_fraction:1,image_path:'test_a.png'},
 {item_id:'test_b',date:'2020-11-15',clear_fraction:0,image_path:'test_b.png'},
 {item_id:'test_c',date:'2020-11-29',clear_fraction:1,image_path:'test_c.png'}]};
const D={id:'TEST_DATASET',rows:[r]};
const e={...C.blank(),label:'0',reviewer:'TEST_REVIEWER',updated_at:'2026-10-15T10:00:00Z',attested:true,seen_scenes:['test_a','test_b','test_c']};
assert.equal(C.status(e,r),'VERIFIED');
assert.equal(C.primaryDate(e,r),'2020-11-01');
assert.equal(C.status({...e,attested:false},r),'PRELIMINARY');
assert.equal(C.status({...e,reviewer:''},r),'PRELIMINARY');
assert.equal(C.status({...e,seen_scenes:['test_a']},r),'PRELIMINARY');
assert.equal(C.status({...e,updated_at:''},r),'PRELIMINARY');
const many={...r,scenes:[...r.scenes,{item_id:'test_d',date:'2020-11-30',clear_fraction:1,image_path:'test_d.png'}]};
assert.equal(C.status(e,many),'PRELIMINARY');
assert.equal(C.status({...e,seen_scenes:[...e.seen_scenes,'test_d']},many),'VERIFIED');
const poor={...r,scenes:r.scenes.map(x=>({...x,clear_fraction:0}))};
assert.equal(C.status(e,poor),'PRELIMINARY');
const close={...r,scenes:r.scenes.map((x,i)=>({...x,date:['2020-11-01','2020-11-05','2020-11-08'][i]}))};
assert.equal(C.status(e,close),'PRELIMINARY');
assert.equal(C.status({...e,label:'UNCERTAIN',attested:false},poor),'UNCERTAIN');
assert.equal(C.status({...e,label:'UNCERTAIN',seen_scenes:[]},poor),'PRELIMINARY');
const state={entries:{TEST_ONLY:e},reviewer:'TEST_REVIEWER',active_id:'TEST_ONLY'};
const saved=C.backup(D,state);
const imported=C.importBackup(JSON.stringify(saved),D);assert.deepEqual(imported.entries.TEST_ONLY,e);
for(const mutate of [
 o=>{o.dataset_id='OLD_DATASET';},o=>{o.schema='nw-water-manual-review-v1';},
 o=>{o.records.push({...o.records[0]});},o=>{o.records[0].sample_id='UNKNOWN';},
 o=>{o.records[0].seen_scenes.push('FOREIGN');},o=>{o.records[0].seen_scenes=['test_a'];},
 o=>{o.records[0].attested='true';},o=>{o.records=[];},o=>{o.records[0].updated_at='2099-01-01T00:00:00Z';}
]){const obj=structuredClone(saved);mutate(obj);assert.throws(()=>C.importBackup(JSON.stringify(obj),D));}
const csv=C.csvOutput(D,{TEST_ONLY:{...e,notes:'=FORMULA'}});
assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes('"0","2020-11-01"'));assert.ok(csv.includes("'=FORMULA"));
assert.ok(!C.csvOutput(D,{TEST_ONLY:{...e,label:'UNCERTAIN',attested:false}}).includes('"VERIFIED"'));
console.log(JSON.stringify({status:'PASS',scope:'Software-only fixtures',groups:7,tests:'zero preserved; scene/date/quality gates; human declaration; unknowns; atomic import rejection; roundtrip; CSV safety'}));
