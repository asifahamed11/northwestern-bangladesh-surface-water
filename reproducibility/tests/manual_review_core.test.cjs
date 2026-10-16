/* Software fixtures only. They are never genuine reference labels. */
const test=require('node:test'),assert=require('node:assert/strict');
const C=require('../postprocessing/manual_review_core.js');
const dataset={id:'fixture',rows:[
 {id:'b',period:'2020-11',year:2020,month:11,region:'Naogaon',longitude:88.1,latitude:25.1},
 {id:'a',period:'2018-03',year:2018,month:3,region:'Rajshahi',longitude:88.5,latitude:24.5}],export_order:['a','b']};
test('ID join survives different display and export order; 0 is preserved',()=>{
 const csv=C.csvOutput(dataset,{b:{...C.blank(),label:'0'},a:{...C.blank(),label:'1'}});
 const r=C.parseCSV(csv);assert.deepEqual(r.map(x=>x.sample_id),['a','b']);
 assert.equal(r[1].preliminary_review,'0');assert.equal(r[1].reference_water,'');assert.equal(r[1].reference_quality,'PRELIMINARY');
 const loaded=C.importText(csv,'labels.csv',dataset).entries;assert.equal(loaded.b.label,'0');assert.equal(loaded.a.label,'1');
});
test('only complete dated independent evidence plus explicit declaration is VERIFIED',()=>{
 const row=dataset.rows[0];let e={...C.blank(),label:'1'};assert.equal(C.status(e,row),'PRELIMINARY');
 e={...e,reference_date:'2020-11-12',reference_source:'Independent imagery fixture',evidence_id:'TEST_ONLY',reviewer:'Test fixture'};
 assert.equal(C.status(e,row),'PRELIMINARY');e.attested=true;assert.equal(C.status(e,row),'VERIFIED');
 for(const patch of [{reference_date:'2020-10-12'},{reference_date:'2020-11-31'},{reference_source:'JRC GSW'},{reference_source:''},{evidence_id:''},{reviewer:''},{label:'UNCERTAIN'}])assert.notEqual(C.status({...e,...patch},row),'VERIFIED');
 const r=C.parseCSV(C.csvOutput(dataset,{b:e})).find(r=>r.sample_id==='b');assert.equal(r.reference_water,'1');assert.equal(r.reference_quality,'VERIFIED');
 // CSV import never silently restores the declaration.
 assert.equal(C.importText(C.csvOutput(dataset,{b:e}),'labels.csv',dataset).entries.b.attested,false);
 assert.equal(C.importText(C.backup(dataset,{entries:{b:e},active_id:'b'}),'backup.json',dataset).entries.b.attested,true);
});
test('CSV handles newline, comma, quote, Bengali, zero and Excel formula neutralization',()=>{
 const notes='পানি নেই, "ভালো"\nদ্বিতীয় লাইন';const csv=C.csvOutput(dataset,{b:{...C.blank(),label:'0',notes}});
 assert.equal(C.parseCSV(csv)[2-1].notes,notes);
 const r=C.parseCSV(C.csvOutput(dataset,{a:{...C.blank(),notes:'=1+2'}}));assert.equal(r[0].notes,"'=1+2");
 assert.throws(()=>C.parseCSV('sample_id,notes\na,"unfinished'));
 assert.throws(()=>C.parseCSV('sample_id,sample_id\na,b'));
});
test('legacy notes are matched by ID and never promoted to verified',()=>{
 const r=C.importText('sample_id,period,preliminary_review,notes\nb,2020-11,0,note\na,2018-03,UNCERTAIN,cloud','old.csv',dataset).entries;
 assert.equal(r.b.label,'0');assert.equal(r.a.label,'UNCERTAIN');assert.equal(C.status(r.b,dataset.rows[0]),'PRELIMINARY');
});
test('unknown, duplicate, shifted metadata and foreign backup reject atomically',()=>{
 for(const csv of [
 'sample_id,preliminary_review\na,1\nz,0',
 'sample_id,preliminary_review\na,1\na,0',
 'sample_id,period,preliminary_review\na,2020-11,1',
 'sample_id,latitude,preliminary_review\na,25.1,1',
 'sample_id,preliminary_review\na,2'])assert.throws(()=>C.importText(csv,'old.csv',dataset));
 assert.throws(()=>C.importText('{"schema":"nw-water-manual-review-v1","dataset_id":"other","records":[]}','bad.json',dataset));
});
test('empty is pending, uncertainty remains missing, and real calendar dates are enforced',()=>{
 assert.equal(C.status(C.blank(),dataset.rows[0]),'PENDING');
 assert.equal(C.status({...C.blank(),notes:'not yet interpreted'},dataset.rows[0]),'PENDING');
 const r=C.parseCSV(C.csvOutput(dataset,{b:{...C.blank(),label:'UNCERTAIN'}}))[1];assert.equal(r.reference_water,'');assert.equal(r.reference_quality,'UNCERTAIN');
 assert(C.dateOK('2020-02-29','2020-02'));assert(!C.dateOK('2019-02-29','2019-02'));assert(!C.dateOK('2020-11-31','2020-11'));assert(!C.dateOK('2020-11-02','2020-10'));
});
