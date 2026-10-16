(function(root){
  'use strict';
  const SCHEMA='nw-assisted-spectral-triage-v1';
  const blank=()=>({label:'',reviewer:'',notes:'',updated_at:'',seen_scenes:[]});
  function entry(raw={}){
    if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('উত্তরের গঠন ঠিক নেই।');
    const e=blank();for(const k of ['label','reviewer','notes','updated_at']){if(raw[k]!=null){if(typeof raw[k]!=='string'||raw[k].length>10000)throw Error('উত্তরের লেখা ঠিক নেই।');e[k]=raw[k];}}
    if(!['','0','1','UNCERTAIN'].includes(e.label))throw Error('উত্তর ০, ১ বা অনিশ্চিত হতে হবে।');
    if(raw.seen_scenes!==undefined){if(!Array.isArray(raw.seen_scenes)||raw.seen_scenes.some(s=>typeof s!=='string')||new Set(raw.seen_scenes).size!==raw.seen_scenes.length)throw Error('দেখা ছবির ID ঠিক নেই।');e.seen_scenes=[...raw.seen_scenes];}
    if(e.updated_at&&!Number.isFinite(Date.parse(e.updated_at)))throw Error('সময় ঠিক নেই।');
    return e;
  }
  function errors(e,row){
    const result=[];if(!e.reviewer.trim())result.push('আগে নিজের নাম লেখো।');
    if(!e.updated_at)result.push('উত্তর সংরক্ষণের সময় নেই।');
    if(!e.label)result.push('উত্তর বেছে নাও।');
    if(e.seen_scenes.some(id=>!row.scenes.some(s=>s.item_id===id)))result.push('এই নমুনার বাইরের ছবির ID আছে।');
    if(row.scenes.some(s=>!e.seen_scenes.includes(s.item_id)))result.push('প্রস্তুত সব তারিখের ছবিই আগে দেখো।');
    return result;
  }
  function humanStatus(e,row){if(!e.label)return 'PENDING';if(errors(e,row).length)return 'PRELIMINARY';return e.label==='UNCERTAIN'?'HUMAN_UNCERTAIN':'HUMAN_ASSISTED';}
  function outcome(e,row){
    const status=humanStatus(e,row);
    if(status==='HUMAN_ASSISTED')return {water:e.label,origin:row.screening.category==='QUALITY_LIMITED'?'HUMAN_ASSISTED_LOW_SUPPORT':'HUMAN_ASSISTED',independent:false};
    if(status==='HUMAN_UNCERTAIN')return {water:'',origin:'HUMAN_UNCERTAIN',independent:false};
    if(e.label)return {water:'',origin:'INCOMPLETE_HUMAN_REVIEW',independent:false};
    const v=row.screening.automated_water;
    return {water:v===0||v===1?String(v):'',origin:v===0||v===1?'AUTO_SCREENED':row.screening.category==='QUALITY_LIMITED'?'UNRESOLVED_QUALITY':'REVIEW_PENDING',independent:false};
  }
  function backup(dataset,state){return {schema:SCHEMA,dataset_id:dataset.id,exported_at:new Date().toISOString(),independent_reference_eligible:false,
    reviewer:state.reviewer||'',active_id:state.active_id||dataset.rows[0].sample_id,
    records:dataset.rows.map(r=>({sample_id:r.sample_id,...entry(state.entries[r.sample_id]||{})})),
    scope:'Model-selected assisted review. Automatic or assisted answers are not independent accuracy references.'};}
  function importBackup(text,dataset){
    const o=JSON.parse(text.replace(/^\uFEFF/,''));
    if(o.schema!==SCHEMA||o.dataset_id!==dataset.id||o.independent_reference_eligible!==false)throw Error('এটি এই assisted review-এর Backup নয়। আগের/স্বাধীন review-এর ফাইল এখানে আসবে না।');
    if(!Array.isArray(o.records)||o.records.length!==dataset.rows.length||!Number.isFinite(Date.parse(o.exported_at)))throw Error('সম্পূর্ণ Backup ও সঠিক সময় লাগবে।');
    const by=new Map(dataset.rows.map(r=>[r.sample_id,r])),entries={};
    for(const raw of o.records){if(!by.has(raw.sample_id)||Object.hasOwn(entries,raw.sample_id))throw Error('অচেনা বা duplicate sample ID আছে।');
      const e=entry(raw);if(e.seen_scenes.some(id=>!by.get(raw.sample_id).scenes.some(s=>s.item_id===id)))throw Error('অন্য নমুনার ছবির ID আছে।');
      if(e.updated_at&&Date.parse(e.updated_at)>Date.parse(o.exported_at))throw Error('উত্তরের সময় Backup-এর পরের।');
      entries[raw.sample_id]=e;
    }
    if(!by.has(o.active_id)||typeof o.reviewer!=='string')throw Error('Backup-এর বর্তমান নমুনা বা নাম ভুল।');
    return {entries,reviewer:o.reviewer,active_id:o.active_id};
  }
  function csv(dataset,entries){
    const neutral=s=>/^[\s]*[=+@-]/.test(String(s))?"'"+s:s;
    const cell=s=>'"'+String(s??'').replaceAll('"','""')+'"';
    const fields=['sample_id','number','region','period','automated_water','human_water','assisted_water','label_origin','human_review_status','reference_water','reference_quality','independent_reference_eligible','reviewer','notes','reviewed_at','seen_scene_ids','source_dates','source_scene_ids','screening_reason_codes','dataset_id'];
    const lines=[fields.join(',')];for(const r of dataset.rows){const e=entry(entries[r.sample_id]||{}),o=outcome(e,r),s=humanStatus(e,r);
      const v=[r.sample_id,r.number,r.region,r.period,r.screening.automated_water,['HUMAN_ASSISTED'].includes(s)?e.label:'',o.water,o.origin,s,'',o.origin,'false',neutral(e.reviewer),neutral(e.notes),e.updated_at,e.seen_scenes.join(';'),r.scenes.map(s=>s.date).join(';'),r.scenes.map(s=>s.item_id).join(';'),r.screening.reason_codes.join(';'),dataset.id];
      lines.push(v.map(cell).join(','));}
    return '\uFEFF'+lines.join('\r\n');
  }
  const api={SCHEMA,blank,entry,errors,humanStatus,outcome,backup,importBackup,csv};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.AssistedWaterCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
