// Numerical/provenance software fixtures only. Never study reference labels.
const assert=require('node:assert/strict'),C=require('../postprocessing/dated_water_core.js');
const r={sample_id:'TEST',number:1,region:'TEST',period:'2020-11',screening:{category:'REVIEW',automated_water:null},scenes:[
 {item_id:'a',date:'2020-11-01',clear_fraction:1},{item_id:'b',date:'2020-11-15',clear_fraction:1},{item_id:'c',date:'2020-11-29',clear_fraction:0}]};
const D={id:'TEST_DATASET',parent_dataset_id:'TEST_PARENT',rows:[r]};
const a=label=>({label,reviewer:'TEST_REVIEWER',updated_at:'2026-10-15T10:00:00Z'});
let e={...C.blank(),seen_scenes:['a'],dates:{a:a('0')}};
assert.equal(C.summary(e,r).complete,false);assert.equal(C.summary(e,r).water,'');assert.equal(C.dateOutcome(e,r,r.scenes[0]).water,'0');
assert.equal(C.dateOutcome(e,r,r.scenes[1]).human_answer,'');assert.equal(C.dateOutcome(e,r,r.scenes[2]).water,'');
e={...e,seen_scenes:['a','b'],dates:{a:a('0'),b:a('1')}};
assert.equal(C.summary(e,r).complete,true);assert.equal(C.summary(e,r).temporal_change,true);assert.equal(C.summary(e,r).water,'');
assert.equal(C.summary(e,r).origin,'HUMAN_TEMPORAL_CHANGE');
const same={...e,dates:{a:a('0'),b:a('0')}};assert.equal(C.summary(same,r).water,'0');
const unsure={...e,dates:{a:a('0'),b:a('UNCERTAIN')}};assert.equal(C.summary(unsure,r).water,'');assert.equal(C.summary(unsure,r).has_uncertain_date,true);
const low={...r,screening:{category:'QUALITY_LIMITED',automated_water:null}};assert.equal(C.summary(same,low).water,'');
const saved=C.backup(D,{entries:{TEST:e},reviewer:'TEST_REVIEWER',active_id:'TEST',active_scene:'b'});
assert.equal(C.importBackup(JSON.stringify(saved),D).entries.TEST.dates.b.label,'1');
const legacy={schema:'nw-assisted-spectral-triage-v1',dataset_id:'TEST_PARENT',exported_at:'2026-10-15T11:00:00Z',independent_reference_eligible:false,reviewer:'TEST_REVIEWER',active_id:'TEST',records:[{sample_id:'TEST',label:'0',reviewer:'TEST_REVIEWER',notes:'OLD_NOTE',updated_at:'2026-10-15T10:00:00Z',seen_scenes:['a','b','c']}]};
const migrated=C.importBackup(JSON.stringify(legacy),D);assert.deepEqual(migrated.entries.TEST.dates,{});assert.equal(migrated.entries.TEST.legacy_point_answer.label,'0');assert.equal(C.summary(migrated.entries.TEST,r).water,'');
for(const mutate of [o=>o.dataset_id='FOREIGN',o=>o.records[0].dates.a.updated_at='2099-01-01T00:00:00Z',o=>o.records[0].dates.FOREIGN=a('1'),o=>o.records[0].seen_scenes=[],o=>o.records.push(o.records[0]),o=>o.independent_reference_eligible=true]){const bad=structuredClone(saved);mutate(bad);assert.throws(()=>C.importBackup(JSON.stringify(bad),D));}
const csv=C.dateCSV(D,{TEST:{...e,notes:'=TEST_FORMULA'}});assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes("'=TEST_FORMULA"));assert.ok(!csv.includes('VERIFIED'));assert.equal(csv.split('\r\n').length,4);
const summary=C.summaryCSV(D,{TEST:e});assert.ok(summary.includes('HUMAN_TEMPORAL_CHANGE'));assert.ok(summary.includes('"true"'));
console.log(JSON.stringify({status:'PASS',scope:'Software fixtures',tests:'date-wise zero and one; no cross-date propagation; temporal change not collapsed; uncertain and low-support preserved; legacy migration isolated; foreign or forged import rejected; CSV provenance'}));
