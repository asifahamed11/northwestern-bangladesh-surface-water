// Validate real future human assisted backups. Never emits independent accuracy.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const C=require('./assisted_water_core.js');
const root=path.resolve(__dirname,'..'),base=path.join(root,'assisted_water_screening_20261015');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const args=process.argv.slice(2),i=args.indexOf('--backup');
if(i<0){console.log(JSON.stringify({status:'PENDING_REAL_ASSISTED_BACKUP',human_answers_created:0,accuracy_computed:false}));process.exit(0);}
if(!args[i+1])throw Error('Provide the real assisted backup file path after --backup');
const input=path.resolve(args[i+1]),bytes=fs.readFileSync(input),hash=sha(bytes);
const datasetPath=path.join(base,'screening_dataset.json'),datasetBytes=fs.readFileSync(datasetPath),D=JSON.parse(datasetBytes),manifest=JSON.parse(fs.readFileSync(path.join(base,'review_manifest.json'),'utf8'));
if(sha(datasetBytes)!==manifest.dataset_sha256||D.id!==manifest.dataset_id)throw Error('Frozen screening dataset changed');
const state=C.importBackup(bytes.toString('utf8'),D),counts={},human={},category={};let completedReview=0;
for(const r of D.rows){const e=C.entry(state.entries[r.sample_id]),s=C.humanStatus(e,r),o=C.outcome(e,r);counts[o.origin]=(counts[o.origin]||0)+1;human[s]=(human[s]||0)+1;category[r.screening.category]=(category[r.screening.category]||0)+1;
 if(r.screening.category==='REVIEW'&&['HUMAN_ASSISTED','HUMAN_UNCERTAIN'].includes(s))completedReview++;}
if(sha(fs.readFileSync(input))!==hash)throw Error('Human input changed during verification');
const report={status:'ASSISTED_REVIEW_ACCOUNTED_NOT_INDEPENDENT_ACCURACY',checked_at:new Date().toISOString(),human_backup_sha256:hash,dataset_id:D.id,
 input_path:input,all_720_sample_ids_preserved:D.rows.length===720,categories:category,label_origins:counts,human_status_counts:human,
 required_review_completed:completedReview,required_review_total:category.REVIEW||0,all_requested_review_complete:completedReview===(category.REVIEW||0),
 automatic_cases_independently_verified:false,independent_accuracy_complete:false,accuracy_computed:false,publication_ready:false,
 limitations:['Only model-selected unclear cases were requested. Their review cannot measure errors among automatic cases or representative accuracy.','Unknown and low-support cases remain explicit.','Assisted labels are never independent reference labels.']};
const out=path.join(base,'human_review_runs','run_'+new Date().toISOString().replaceAll(':','-'));
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'assisted_review_result.json'),JSON.stringify(report,null,2));fs.writeFileSync(path.join(out,'assisted_labels.csv'),C.csv(D,state.entries));
console.log(JSON.stringify({status:report.status,output:out,required_review_completed:completedReview,required_review_total:category.REVIEW||0,independent_accuracy_complete:false}));
