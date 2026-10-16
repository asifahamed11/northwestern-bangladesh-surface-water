(function(root){
  'use strict';
  const SCHEMA='nw-assisted-dated-review-v2',LEGACY='nw-assisted-spectral-triage-v1';
  const blank=()=>({dates:{},notes:'',seen_scenes:[],legacy_point_answer:null});
  const validTime=t=>typeof t==='string'&&Number.isFinite(Date.parse(t))&&/(Z|[+-]\d\d:\d\d)$/.test(t);
  const text=(v,max=10000)=>{if(typeof v!=='string'||v.length>max)throw Error('উত্তরের লেখা ঠিক নেই।');return v;};
  function answer(raw){if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('দিনের উত্তরের গঠন ঠিক নেই।');
    if(!['0','1','UNCERTAIN'].includes(raw.label))throw Error('দিনের উত্তর ০, ১ বা অনিশ্চিত হতে হবে।');
    const a={label:raw.label,reviewer:text(raw.reviewer),updated_at:text(raw.updated_at)};
    if(!a.reviewer.trim()||!validTime(a.updated_at))throw Error('দিনের উত্তরে নাম ও সঠিক সময় লাগবে।');return a;}
  function entry(raw={}){if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('উত্তরের গঠন ঠিক নেই।');const e=blank();
    if(raw.notes!==undefined)e.notes=text(raw.notes);
    if(raw.seen_scenes!==undefined){if(!Array.isArray(raw.seen_scenes)||raw.seen_scenes.some(s=>typeof s!=='string')||new Set(raw.seen_scenes).size!==raw.seen_scenes.length)throw Error('দেখা দিনের ID ঠিক নেই।');e.seen_scenes=[...raw.seen_scenes];}
    if(raw.dates!==undefined){if(!raw.dates||typeof raw.dates!=='object'||Array.isArray(raw.dates))throw Error('দিনের তালিকা ঠিক নেই।');for(const [id,a] of Object.entries(raw.dates))e.dates[id]=answer(a);}
    if(raw.legacy_point_answer!=null){const a=raw.legacy_point_answer;if(!a||!['','0','1','UNCERTAIN'].includes(a.label))throw Error('পুরোনো উত্তরের গঠন ঠিক নেই।');e.legacy_point_answer={label:a.label,reviewer:text(a.reviewer||''),notes:text(a.notes||''),updated_at:text(a.updated_at||'')};}
    return e;
  }
  function validateRow(e,r){const ids=r.scenes.map(s=>s.item_id);if(e.seen_scenes.some(id=>!ids.includes(id))||Object.keys(e.dates).some(id=>!ids.includes(id)))throw Error('অন্য জায়গার দিনের ID আছে।');
    if(Object.keys(e.dates).some(id=>!e.seen_scenes.includes(id)))throw Error('উত্তর দেওয়া দিনের ছবি দেখা হয়নি।');}
  const required=r=>r.scenes.filter(s=>s.clear_fraction>=.95);
  function summary(e,r){validateRow(e,r);const tasks=required(r),provided=Object.values(e.dates),labels=new Set(provided.filter(a=>a.label!=='UNCERTAIN').map(a=>a.label));
    const completed=tasks.filter(s=>e.dates[s.item_id]).length,done=tasks.length>0&&completed===tasks.length;
    const temporal_change=labels.has('0')&&labels.has('1'),unknown=provided.some(a=>a.label==='UNCERTAIN');
    let water='',origin='DATE_REVIEW_PENDING';
    if(provided.length){origin=!done?'PARTIAL_DATED_REVIEW':temporal_change?'HUMAN_TEMPORAL_CHANGE':unknown?'HUMAN_UNCERTAIN_DATES':'HUMAN_DATES_CONSISTENT';
      if(done&&!temporal_change&&!unknown&&r.screening.category!=='QUALITY_LIMITED')water=provided[0].label;
      if(r.screening.category==='QUALITY_LIMITED'&&!temporal_change)origin='HUMAN_DATES_LOW_SUPPORT';
    }else if(e.legacy_point_answer?.label)origin='LEGACY_POINT_ONLY';
    else if(r.screening.automated_water===0||r.screening.automated_water===1){water=String(r.screening.automated_water);origin='AUTO_SCREENED';}
    else if(r.screening.category==='QUALITY_LIMITED')origin='UNRESOLVED_QUALITY';
    return {water,origin,temporal_change,has_uncertain_date:unknown,required_dates:tasks.length,answered_required_dates:completed,
      answered_dates:provided.length,complete:done,independent:false};
  }
  function dateOutcome(e,r,s){const a=e.dates[s.item_id];if(a)return {water:a.label==='UNCERTAIN'?'':a.label,human_answer:a.label,origin:a.label==='UNCERTAIN'?'HUMAN_UNCERTAIN_DATE':s.clear_fraction>=.95?'HUMAN_ASSISTED_DATE':'HUMAN_DATE_LOW_SUPPORT'};
    if(s.clear_fraction>=.95&&(r.screening.automated_water===0||r.screening.automated_water===1))return {water:String(r.screening.automated_water),human_answer:'',origin:'AUTO_SCREENED_DATE'};
    return {water:'',human_answer:'',origin:s.clear_fraction>=.95?'DATE_REVIEW_PENDING':'UNRESOLVED_QUALITY_DATE'};
  }
  function backup(D,state){return {schema:SCHEMA,dataset_id:D.id,parent_dataset_id:D.parent_dataset_id,exported_at:new Date().toISOString(),
    independent_reference_eligible:false,reviewer:state.reviewer||'',active_id:state.active_id||D.rows[0].sample_id,active_scene:state.active_scene||'',
    records:D.rows.map(r=>({sample_id:r.sample_id,...entry(state.entries[r.sample_id]||{})})),
    scope:'Per-acquisition assisted answers; no propagation across dates; not independent accuracy references.'};}
  function importBackup(string,D){const o=JSON.parse(string.replace(/^\uFEFF/,'')),legacy=o.schema===LEGACY;
    if(o.independent_reference_eligible!==false||!(legacy?o.dataset_id===D.parent_dataset_id:o.schema===SCHEMA&&o.dataset_id===D.id))throw Error('এই review-এর Backup লাগবে। অন্য dataset-এর উত্তর মেশানো যাবে না।');
    if(!Array.isArray(o.records)||o.records.length!==D.rows.length||!validTime(o.exported_at))throw Error('সব নমুনা ও সঠিক সময়সহ Backup লাগবে।');
    const by=new Map(D.rows.map(r=>[r.sample_id,r])),entries={};
    for(const raw of o.records){const r=by.get(raw.sample_id);if(!r||Object.hasOwn(entries,raw.sample_id))throw Error('অচেনা বা duplicate sample ID আছে।');
      let e;if(legacy){if(!['','0','1','UNCERTAIN'].includes(raw.label||''))throw Error('পুরোনো উত্তর ঠিক নেই।');e=entry({notes:raw.notes||'',seen_scenes:raw.seen_scenes||[],
        legacy_point_answer:{label:raw.label||'',reviewer:raw.reviewer||'',notes:raw.notes||'',updated_at:raw.updated_at||''}});
      }else e=entry(raw);validateRow(e,r);
      if(Object.values(e.dates).some(a=>Date.parse(a.updated_at)>Date.parse(o.exported_at)))throw Error('দিনের উত্তর Backup-এর পরের সময়ের।');entries[r.sample_id]=e;
    }
    if(!by.has(o.active_id)||typeof o.reviewer!=='string')throw Error('Backup-এর নাম/বর্তমান জায়গা ঠিক নেই।');
    const scene=legacy?'':o.active_scene||'';if(scene&&!by.get(o.active_id).scenes.some(s=>s.item_id===scene))throw Error('বর্তমান দিনের ID ঠিক নেই।');
    return {entries,reviewer:o.reviewer,active_id:o.active_id,active_scene:scene,migrated_legacy:legacy};
  }
  const neutral=s=>/^[\s]*[=+@-]/.test(String(s))?"'"+s:s;
  const cell=s=>'"'+String(s??'').replaceAll('"','""')+'"';
  function dateCSV(D,entries){const lines=[['sample_id','number','region','period','scene_id','acquisition_date','clear_fraction','required_review_date','automated_scene_label','human_answer','human_water','assisted_date_water','label_origin','reference_water','independent_reference_eligible','reviewer','reviewed_at','notes','dataset_id'].join(',')];
    for(const r of D.rows){const e=entry(entries[r.sample_id]||{});validateRow(e,r);for(const s of r.scenes){const a=e.dates[s.item_id],o=dateOutcome(e,r,s);lines.push([r.sample_id,r.number,r.region,r.period,s.item_id,s.date,s.clear_fraction,r.screening.category==='REVIEW'&&s.clear_fraction>=.95?'true':'false',s.automated_scene_label,
      o.human_answer,a&&a.label!=='UNCERTAIN'?a.label:'',o.water,o.origin,'','false',neutral(a?.reviewer||''),a?.updated_at||'',neutral(e.notes),D.id].map(cell).join(','));}}
    return '\uFEFF'+lines.join('\r\n');}
  function summaryCSV(D,entries){const lines=[['sample_id','number','region','period','automated_water','assisted_water','label_origin','temporal_change_observed','has_uncertain_date','required_dates','answered_required_dates','legacy_sample_label','reference_water','independent_reference_eligible','dataset_id'].join(',')];
    for(const r of D.rows){const e=entry(entries[r.sample_id]||{}),s=summary(e,r);lines.push([r.sample_id,r.number,r.region,r.period,r.screening.automated_water,s.water,s.origin,String(s.temporal_change),String(s.has_uncertain_date),s.required_dates,s.answered_required_dates,e.legacy_point_answer?.label||'','','false',D.id].map(cell).join(','));}
    return '\uFEFF'+lines.join('\r\n');}
  const api={SCHEMA,blank,answer,entry,validateRow,required,summary,dateOutcome,backup,importBackup,dateCSV,summaryCSV};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.DatedWaterCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
