(function (root) {
  'use strict';
  const fields = ['label','notes','reason','reference_date','reference_source','evidence_id','reviewer','attested','updated_at'];
  const blank = () => ({label:'',notes:'',reason:'',reference_date:'',reference_source:'',evidence_id:'',reviewer:'',attested:false,updated_at:''});
  function entry(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('উত্তরের গঠন ঠিক নেই।');
    const r = blank();
    for (const k of fields) if (k !== 'attested' && value[k] != null) {
      if (typeof value[k] !== 'string' || value[k].length > 20000) throw Error('উত্তরের লেখা ঠিক নেই: '+k);
      r[k] = value[k];
    }
    if (!['','0','1','UNCERTAIN'].includes(r.label)) throw Error('পানির উত্তরটি গ্রহণযোগ্য নয়।');
    if (value.attested !== undefined && typeof value.attested !== 'boolean') throw Error('যাচাইয়ের চিহ্ন ঠিক নেই।');
    r.attested = value.attested === true;
    return r;
  }
  function dateOK(date, period) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date.slice(0,7)!==period) return false;
    const d = new Date(date+'T12:00:00Z');
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0,10)===date;
  }
  function evidenceErrors(e, row) {
    const errors=[];
    if (!['0','1'].includes(e.label)) errors.push('পানি আছে অথবা পানি নেই—একটি নিশ্চিত উত্তর লাগবে।');
    if (!dateOK(e.reference_date,row.period)) errors.push('ছবির প্রকৃত তারিখ '+row.period+' মাসের হতে হবে।');
    if (!e.reference_source.trim()) errors.push('ছবির উৎস লিখতে হবে।');
    if (/\bJRC\b|\bGSW\b|global[ ._-]*surface[ ._-]*water/i.test(e.reference_source)) errors.push('JRC/GSW map-কে তার নিজের reference করা যাবে না।');
    if (!e.evidence_id.trim()) errors.push('ব্যবহৃত দৃশ্যের ID অথবা সংরক্ষিত screenshot-এর নাম লিখুন।');
    if (!e.reviewer.trim()) errors.push('যিনি ছবি যাচাই করেছেন তাঁর নাম লিখুন।');
    return errors;
  }
  function status(e,row) {
    if (e.attested && evidenceErrors(e,row).length===0) return 'VERIFIED';
    if (e.label==='UNCERTAIN') return 'UNCERTAIN';
    return e.label!=='' ? 'PRELIMINARY' : 'PENDING';
  }
  function meaningful(e) {return fields.some(k=>k!=='updated_at' && (k==='attested' ? e[k] : Boolean(e[k])));}
  function comparable(e) {return JSON.stringify(fields.filter(k=>k!=='updated_at').map(k=>e[k]));}
  function parseCSV(input) {
    const text=input.replace(/^\uFEFF/,'');
    const rows=[]; let row=[], cell='', quoted=false, closed=false;
    for(let i=0;i<text.length;i++) {
      const c=text[i];
      if(quoted) {if(c==='"') {if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=c;continue;}
      if(c==='"') {if(cell || closed) throw Error('CSV-তে quote-এর গঠন ঠিক নেই।');quoted=true;continue;}
      if(c===',' || c==='\r' || c==='\n') {
        row.push(cell);cell='';closed=false;
        if(c!==','){if(c==='\r' && text[i+1]==='\n')i++; if(row.some(v=>v!==''))rows.push(row);row=[];}
        continue;
      }
      if(closed) throw Error('CSV-তে বন্ধ quote-এর পরে বাড়তি লেখা আছে।');
      cell+=c;
    }
    if(quoted) throw Error('CSV-তে একটি quote বন্ধ হয়নি।');
    if(cell!=='' || row.length || closed){row.push(cell);if(row.some(v=>v!==''))rows.push(row);}
    if(!rows.length)throw Error('CSV খালি।');
    const headers=rows.shift();
    if(new Set(headers).size!==headers.length || !headers.includes('sample_id'))throw Error('CSV-তে unique sample_id column লাগবে।');
    return rows.map(values=>{if(values.length!==headers.length)throw Error('CSV-র column সংখ্যা মেলেনি।');return Object.fromEntries(headers.map((h,i)=>[h,values[i]]));});
  }
  function neutral(v) {const s=String(v ?? '');return /^[\t\r\n ]*[=+@-]/.test(s) ? "'"+s : s;}
  function csvCell(v) {return '"'+String(v ?? '').replaceAll('"','""')+'"';}
  function csvOutput(dataset,entries) {
    const byID=new Map(dataset.rows.map(r=>[r.id,r]));
    const headers=['sample_id','region','year','month','longitude','latitude','reference_water','reference_date','reference_source','reference_quality','notes','preliminary_review','evidence_id','reviewer','evidence_attested','reviewed_at','dataset_id','uncertainty_reason'];
    const lines=[headers.join(',')];
    for(const id of dataset.export_order) {
      const r=byID.get(id), e=entry(entries[id] || {}), s=status(e,r);
      const values=[id,r.region,r.year,r.month,r.longitude,r.latitude,s==='VERIFIED'?e.label:'',e.reference_date,neutral(e.reference_source),s==='PENDING'?'':s,neutral(e.notes),e.label,neutral(e.evidence_id),neutral(e.reviewer),s==='VERIFIED'?'true':'false',e.updated_at,dataset.id,neutral(e.reason)];
      lines.push(values.map(csvCell).join(','));
    }
    return '\uFEFF'+lines.join('\r\n');
  }
  function validateRecords(records,dataset,checkMetadata=false) {
    const byID=new Map(dataset.rows.map(r=>[r.id,r])), seen=new Set(), output={};
    for(const record of records) {
      const id=record.sample_id;
      if(!byID.has(id))throw Error('অচেনা sample_id: '+String(id));
      if(seen.has(id))throw Error('একই sample_id একাধিকবার আছে: '+id);seen.add(id);
      const row=byID.get(id);
      if(checkMetadata) {
        const checks={period:row.period,region:row.region,year:String(row.year),month:String(row.month),dataset_id:dataset.id};
        for(const [k,v] of Object.entries(checks))if(record[k]!==undefined && record[k]!=='' && String(record[k])!==v)throw Error('ID-এর সঙ্গে '+k+' মেলেনি: '+id);
        for(const k of ['latitude','longitude'])if(record[k]!==undefined && record[k]!=='' && (!Number.isFinite(Number(record[k])) || Math.abs(Number(record[k])-row[k])>1e-8))throw Error('ID-এর সঙ্গে coordinates মেলেনি: '+id);
      }
      output[id]=entry(record);
    }
    return output;
  }
  function importText(text,name,dataset) {
    if(text.length>50000000)throw Error('ফাইল ৫০ MB-এর বেশি।');
    if(/\.json$/i.test(name) || text.trim().startsWith('{')) {
      const obj=JSON.parse(text.replace(/^\uFEFF/,''));
      if(obj.schema!=='nw-water-manual-review-v1' || obj.dataset_id!==dataset.id || !Array.isArray(obj.records))throw Error('এই backup অন্য dataset-এর অথবা format ঠিক নেই।');
      return {entries:validateRecords(obj.records,dataset,true),kind:'JSON backup'};
    }
    const records=parseCSV(text).map(r=>{
      let label=r.preliminary_review ?? r.reference_water ?? '';
      // CSV is an exchange table; only a valid JSON backup restores attestation.
      if(label==='' && ['0','1'].includes(r.reference_water))label=r.reference_water;
      if(label==='' && r.reference_quality==='UNCERTAIN')label='UNCERTAIN';
      return {...r,label,reason:r.uncertainty_reason || '',attested:false,updated_at:r.reviewed_at || ''};
    });
    return {entries:validateRecords(records,dataset,true),kind:'CSV — যাচাইয়ের ঘোষণা আবার দিতে হবে'};
  }
  function backup(dataset,state) {
    return JSON.stringify({schema:'nw-water-manual-review-v1',dataset_id:dataset.id,exported_at:new Date().toISOString(),active_id:state.active_id,records:dataset.rows.map(r=>({sample_id:r.id,...entry(state.entries[r.id] || {})}))},null,2);
  }
  const api={blank,entry,dateOK,evidenceErrors,status,meaningful,comparable,parseCSV,csvOutput,importText,validateRecords,backup};
  root.ReviewCore=api;
  if(typeof module!=='undefined' && module.exports)module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);
