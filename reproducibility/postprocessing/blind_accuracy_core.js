(function(root){
  'use strict';
  const SCHEMA='nw-independent-dated-review-v1';
  const textFields=['label','reviewer','notes','reason','updated_at'];
  const blank=()=>({label:'',reviewer:'',notes:'',reason:'',updated_at:'',attested:false,seen_scenes:[]});
  function entry(raw={}){
    if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('উত্তরের গঠন ঠিক নেই।');
    const e=blank();
    for(const k of textFields){if(raw[k]!=null){if(typeof raw[k]!=='string'||raw[k].length>10000)throw Error('অগ্রহণযোগ্য লেখা: '+k);e[k]=raw[k];}}
    if(!['','0','1','UNCERTAIN'].includes(e.label))throw Error('পানির উত্তর ঠিক নেই।');
    if(raw.attested!==undefined&&typeof raw.attested!=='boolean')throw Error('ঘোষণার চিহ্ন ঠিক নেই।');
    e.attested=raw.attested===true;
    if(raw.seen_scenes!==undefined){
      if(!Array.isArray(raw.seen_scenes)||raw.seen_scenes.some(s=>typeof s!=='string')||new Set(raw.seen_scenes).size!==raw.seen_scenes.length)throw Error('দেখা ছবির তালিকা ঠিক নেই।');
      e.seen_scenes=[...raw.seen_scenes];
    }
    return e;
  }
  function rowErrors(e,row){
    const errors=[];const ids=row.scenes.map(s=>s.item_id);
    if(e.seen_scenes.some(id=>!ids.includes(id)))errors.push('এই জায়গার বাইরের scene ID আছে।');
    if(e.updated_at&&!Number.isFinite(Date.parse(e.updated_at)))errors.push('নথির সময় ঠিক নেই।');
    return errors;
  }
  function evidenceErrors(e,row){
    const errors=rowErrors(e,row);
    if(!['0','1'].includes(e.label))errors.push('নিশ্চিত binary উত্তর নেই।');
    if(!e.reviewer.trim())errors.push('তোমার নাম লিখতে হবে।');
    if(!e.updated_at||!Number.isFinite(Date.parse(e.updated_at)))errors.push('উত্তর সংরক্ষণের সময় নেই।');
    if(row.scenes.length<3||row.scenes.some(s=>!e.seen_scenes.includes(s.item_id)))errors.push('প্রস্তুত সব তারিখের ছবিই খুলে দেখতে হবে।');
    const usable=row.scenes.filter(s=>e.seen_scenes.includes(s.item_id)&&s.clear_fraction>=.95);
    if(usable.length<2)errors.push('অন্তত দুই দিনের গ্রহণযোগ্য image support নেই; অনিশ্চিত রাখো।');
    else {
      const times=usable.map(s=>Date.parse(s.date+'T00:00:00Z'));
      if((Math.max(...times)-Math.min(...times))/86400000<14)errors.push('গ্রহণযোগ্য দিনগুলো যথেষ্ট ব্যবধানে নেই; অনিশ্চয়তা রাখো।');
    }
    if(row.scenes.some(s=>s.date.slice(0,7)!==row.period))errors.push('তারিখ target মাসে নেই।');
    return errors;
  }
  function status(e,row){
    if(e.label==='UNCERTAIN')return e.reviewer.trim()&&e.updated_at&&Number.isFinite(Date.parse(e.updated_at))&&row.scenes.every(s=>e.seen_scenes.includes(s.item_id))?'UNCERTAIN':'PRELIMINARY';
    if(!e.label)return 'PENDING';
    return e.attested&&evidenceErrors(e,row).length===0?'VERIFIED':'PRELIMINARY';
  }
  function primaryDate(e,row){
    if(status(e,row)!=='VERIFIED')return '';
    return row.scenes.filter(s=>s.clear_fraction>=.95).map(s=>s.date).sort()[0];
  }
  function neutral(v){const s=String(v??'');return /^[\t\r\n ]*[=+@-]/.test(s)?"'"+s:s;}
  const csvCell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  function csvOutput(dataset,entries){
    const fields=['sample_id','region','year','month','longitude','latitude','reference_water','reference_date','reference_source','reference_quality','notes','preliminary_review','evidence_id','reviewer','evidence_attested','reviewed_at','dataset_id','uncertainty_reason','seen_scene_ids','reference_dates'];
    const lines=[fields.join(',')];
    for(const r of dataset.rows){
      const e=entry(entries[r.sample_id]||{}),s=status(e,r);
      const values=[r.sample_id,r.region,r.year,r.month,r.longitude,r.latitude,s==='VERIFIED'?e.label:'',primaryDate(e,r),
        'Sentinel-2 L2A / Microsoft Planetary Computer: '+r.scenes.map(x=>x.item_id).join('; '),s,
        neutral(e.notes),e.label,r.scenes.map(x=>x.image_path).join('; '),neutral(e.reviewer),s==='VERIFIED'?'true':'false',e.updated_at,
        dataset.id,neutral(e.reason),e.seen_scenes.join('; '),r.scenes.map(x=>x.date).join('; ')];
      lines.push(values.map(csvCell).join(','));
    }
    return '\uFEFF'+lines.join('\r\n');
  }
  function backup(dataset,state){
    return {schema:SCHEMA,dataset_id:dataset.id,exported_at:new Date().toISOString(),reviewer:state.reviewer||'',active_id:state.active_id||dataset.rows[0].sample_id,
      records:dataset.rows.map(r=>({sample_id:r.sample_id,...entry(state.entries[r.sample_id]||{})})),
      scope:'Human-interpreted dated Sentinel-2 references for four sampled JRC monthly maps; no universal ground-truth or annual-hydroperiod validation claim.'};
  }
  function importBackup(text,dataset){
    const obj=JSON.parse(text.replace(/^\uFEFF/,''));
    if(obj.schema!==SCHEMA||obj.dataset_id!==dataset.id||!Array.isArray(obj.records))throw Error('এই backup অন্য dataset-এর। পুরোনো ৭২০টির ফাইল এখানে import হবে না।');
    if(!Number.isFinite(Date.parse(obj.exported_at)))throw Error('Backup-এর সময় ঠিক নেই।');
    const by=new Map(dataset.rows.map(r=>[r.sample_id,r])),seen=new Set(),entries={};
    for(const raw of obj.records){
      const id=raw.sample_id;if(!by.has(id)||seen.has(id))throw Error('অচেনা বা duplicate sample ID আছে।');seen.add(id);
      const e=entry(raw),errors=rowErrors(e,by.get(id));
      if(errors.length)throw Error(errors.join(' '));
      if(e.updated_at&&Date.parse(e.updated_at)>Date.parse(obj.exported_at))throw Error('উত্তরের সময় Backup-এর পরের।');
      if(e.attested&&evidenceErrors(e,by.get(id)).length)throw Error('অসমর্থিত VERIFIED ঘোষণা আছে।');
      entries[id]=e;
    }
    if(seen.size!==dataset.rows.length)throw Error('সম্পূর্ণ backup-এ সব sample ID থাকতে হবে।');
    if(!by.has(obj.active_id))throw Error('বর্তমান sample ID ভুল।');
    if(typeof obj.reviewer!=='string')throw Error('Reviewer name ঠিক নেই।');
    return {entries,reviewer:obj.reviewer,active_id:obj.active_id};
  }
  const api={SCHEMA,blank,entry,rowErrors,evidenceErrors,status,primaryDate,csvOutput,backup,importBackup};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.BlindAccuracyCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
