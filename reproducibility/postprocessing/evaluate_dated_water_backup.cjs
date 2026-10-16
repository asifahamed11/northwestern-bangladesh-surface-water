// Real future dated backup verification; no independent accuracy or recovery inference.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),C=require('./dated_water_core.js');
const root=path.resolve(__dirname,'..'),base=path.join(root,'assisted_water_screening_20261015','date_review_v2'),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const args=process.argv.slice(2),i=args.indexOf('--backup');if(i<0){console.log(JSON.stringify({status:'PENDING_REAL_DATED_BACKUP',actual_human_labels_created:0,accuracy_computed:false}));process.exit(0);}
if(!args[i+1])throw Error('Supply the real dated backup path after --backup');
const input=path.resolve(args[i+1]),bytes=fs.readFileSync(input),hash=sha(bytes),dataBytes=fs.readFileSync(path.join(base,'dated_review_dataset.json'));
const D=JSON.parse(dataBytes),manifest=JSON.parse(fs.readFileSync(path.join(base,'review_manifest.json'),'utf8'));
if(sha(dataBytes)!==manifest.dataset_sha256||D.id!==manifest.dataset_id)throw Error('Frozen dated dataset changed');
const state=C.importBackup(bytes.toString('utf8'),D);let dateAnswers=0,requestedAnswered=0,requestedTotal=0,completedPlaces=0,temporalChanges=0,requestedPlaces=0,legacyAnswers=0;
for(const r of D.rows){const e=C.entry(state.entries[r.sample_id]),s=C.summary(e,r);dateAnswers+=s.answered_dates;temporalChanges+=Number(s.temporal_change);legacyAnswers+=Number(!!e.legacy_point_answer?.label);
 if(r.screening.category==='REVIEW'){requestedPlaces++;requestedTotal+=s.required_dates;requestedAnswered+=s.answered_required_dates;completedPlaces+=Number(s.complete);}}
if(sha(fs.readFileSync(input))!==hash)throw Error('Human backup changed during verification');
const report={status:'DATED_ASSISTED_REVIEW_ACCOUNTED_NOT_ACCURACY',checked_at:new Date().toISOString(),human_backup_sha256:hash,dataset_id:D.id,
 actual_human_date_answers:dateAnswers,requested_date_answers:requestedAnswered,requested_date_total:requestedTotal,completed_places:completedPlaces,requested_places:requestedPlaces,
 places_with_observed_human_date_changes:temporalChanges,legacy_point_answers_retained_separately:legacyAnswers,answers_copied_across_dates:false,
 all_requested_review_complete:requestedAnswered===requestedTotal,independent_accuracy_complete:false,accuracy_computed:false,recovery_duration_resolved:false,publication_ready:false,
 limitations:['Date differences describe actual reviewed acquisitions only, not every intervening day or drought recovery duration.','This is model-selected assisted review, not representative independent accuracy.','Legacy point-level answers are retained separately and never copied to acquisition dates.']};
const out=path.join(base,'human_review_runs','run_'+new Date().toISOString().replaceAll(':','-'));fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'dated_review_result.json'),JSON.stringify(report,null,2));fs.writeFileSync(path.join(out,'dated_labels.csv'),C.dateCSV(D,state.entries));fs.writeFileSync(path.join(out,'sample_summary.csv'),C.summaryCSV(D,state.entries));
console.log(JSON.stringify({status:report.status,output:out,date_answers:dateAnswers,requested_date_total:requestedTotal,temporal_changes:temporalChanges,independent_accuracy_complete:false}));
