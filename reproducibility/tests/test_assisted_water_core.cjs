// Synthetic software fixtures only. No study answers are created.
const assert=require('node:assert/strict'),C=require('../postprocessing/assisted_water_core.js');
const row=(id,category,automatic)=>({sample_id:id,number:id,region:'TEST',period:'2020-11',screening:{category,automated_water:automatic,reason_codes:['TEST']},scenes:['a','b','c'].map((s,i)=>({item_id:s,date:'2020-11-'+['01','15','29'][i]}))});
const a=row('TEST_A','AUTO_NONWATER',0),b=row('TEST_B','REVIEW',null),q=row('TEST_C','QUALITY_LIMITED',null),D={id:'TEST_DATASET',rows:[a,b,q]};
assert.deepEqual(C.outcome(C.blank(),a),{water:'0',origin:'AUTO_SCREENED',independent:false});
assert.equal(C.outcome(C.blank(),q).water,'');assert.equal(C.outcome(C.blank(),b).water,'');
const human={...C.blank(),label:'0',reviewer:'TEST_ONLY',updated_at:'2026-10-15T10:00:00Z',seen_scenes:['a','b','c'],notes:'=TEST_FORMULA'};
assert.equal(C.humanStatus(human,b),'HUMAN_ASSISTED');assert.equal(C.outcome(human,b).water,'0');
assert.equal(C.outcome({...human,label:'UNCERTAIN'},a).water,'');
assert.equal(C.humanStatus({...human,seen_scenes:['a']},b),'PRELIMINARY');
assert.equal(C.humanStatus({...human,reviewer:''},b),'PRELIMINARY');
assert.equal(C.outcome(human,q).origin,'HUMAN_ASSISTED_LOW_SUPPORT');
const saved=C.backup(D,{entries:{TEST_B:human},reviewer:'TEST_ONLY',active_id:'TEST_B'});
assert.equal(saved.independent_reference_eligible,false);assert.equal(saved.records.length,3);
assert.equal(C.importBackup(JSON.stringify(saved),D).entries.TEST_B.label,'0');
for(const change of [o=>o.schema='nw-independent-dated-review-v1',o=>o.dataset_id='FOREIGN',o=>o.independent_reference_eligible=true,o=>o.records.push(o.records[0]),o=>o.records[0].sample_id='FOREIGN',o=>o.records[0].seen_scenes=['FOREIGN'],o=>o.records[0].updated_at='2099-01-01',o=>o.records=[]]){const o=structuredClone(saved);change(o);assert.throws(()=>C.importBackup(JSON.stringify(o),D));}
const csv=C.csv(D,{TEST_B:human});assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes("'=TEST_FORMULA"));assert.ok(!csv.includes('VERIFIED'));assert.ok(csv.includes('"HUMAN_ASSISTED"'));
console.log(JSON.stringify({status:'PASS',scope:'Software fixtures, not study labels',checks:'zero preserved; unknowns not dry; provenance and low-support flags; assisted backup isolation; complete ID set; CSV safety'}));
