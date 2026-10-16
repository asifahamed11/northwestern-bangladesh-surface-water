(function(){
  'use strict';
  const D=JSON.parse(document.getElementById('dataset').textContent),C=AssistedWaterCore,el=id=>document.getElementById(id);
  const key='nw-assisted-water-review:'+D.id,by=new Map(D.rows.map(r=>[r.sample_id,r]));
  let state={entries:{},reviewer:'',active_id:''},revision=0,blocked=false,currentId='',sceneIndex=0,loaded=false,pendingImport=null;
  function fail(s){el('error').textContent=s;el('error').classList.remove('hidden');}
  function clear(){el('error').classList.add('hidden');}
  try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved){state=C.importBackup(JSON.stringify(saved.backup),D);revision=Number(saved.revision)||0;}}catch(e){fail('Browser save পড়া যায়নি। Backup আনো। '+e.message);}
  el('name').value=state.reviewer;
  const entry=r=>C.entry(state.entries[r.sample_id]||{});
  function persist(){if(blocked){fail('অন্য tab-এ উত্তর বদলেছে। Backup নিয়ে reload করো।');return false;}try{
    const outside=JSON.parse(localStorage.getItem(key)||'null');if(outside&&outside.revision>revision){blocked=true;fail('অন্য tab-এর নতুন উত্তর আছে। Backup নিয়ে reload করো।');return false;}
    revision++;localStorage.setItem(key,JSON.stringify({revision,backup:C.backup(D,state)}));el('saveState').textContent='সংরক্ষিত ✓';return true;
  }catch(e){fail('Browser-এ save হয়নি। এখনই Backup নামাও। '+e.message);return false;}}
  const complete=(e,r)=>['HUMAN_ASSISTED','HUMAN_UNCERTAIN'].includes(C.humanStatus(e,r));
  function queue(){const f=el('filter').value;return D.rows.filter(r=>f==='ALL'||f==='REVIEW'&&r.screening.category==='REVIEW'||f==='PENDING'&&r.screening.category==='REVIEW'&&!complete(entry(r),r)||f==='AUTO'&&r.screening.category.startsWith('AUTO_')||f==='QUALITY_LIMITED'&&r.screening.category==='QUALITY_LIMITED');}
  function counts(){const auto=D.rows.filter(r=>r.screening.category.startsWith('AUTO_')).length,review=D.rows.filter(r=>r.screening.category==='REVIEW');
    el('autoCount').textContent=auto;el('reviewCount').textContent=review.length;el('missingCount').textContent=D.rows.length-auto-review.length;
    const done=review.filter(r=>complete(entry(r),r)).length;el('progress').textContent=`তোমার যাচাই: ${done}/${review.length}`;el('queueCount').textContent=`এই তালিকায় ${queue().length}টি নমুনা`;
    if(!el('listPanel').classList.contains('hidden'))renderList();}
  const reasonMap={DATE_DISAGREEMENT:'আলাদা দিনে আলাদা সংকেত',MIXED_OR_WEAK_BANDS:'পানি/জমির সংকেত অস্পষ্ট বা মিশ্র',BOUNDARY_SENSITIVITY:'পানি-মাটির ধার কাছাকাছি; pixel-এর অবস্থানে অনিশ্চয়তা',RADIOMETRY_AMBIGUOUS:'খুব কম/অস্বাভাবিক band signal',INSUFFICIENT_DATED_SUPPORT:'পর্যাপ্ত পরিষ্কার ও ব্যবধানযুক্ত দিনের ছবি নেই',CONSISTENT_STRONG_SPECTRAL_RULES:'ব্যবহারযোগ্য দিনগুলোতে কোডের নিয়ম একমত'};
  function refresh(){const r=by.get(currentId);if(!r)return;const e=entry(r),s=C.humanStatus(e,r);
    el('humanState').textContent={PENDING:'তোমার উত্তর এখনও নেই',PRELIMINARY:'উত্তর আছে; সব তারিখ দেখা/তথ্য দেওয়া বাকি',HUMAN_ASSISTED:'তোমার assisted উত্তর সংরক্ষিত',HUMAN_UNCERTAIN:'অনিশ্চিত হিসেবে সংরক্ষিত'}[s];
    for(const b of document.querySelectorAll('.answers button'))b.classList.toggle('selected',b.dataset.label===e.label);
    el('notes').value=e.notes;el('hint').textContent=e.label?C.errors(e,r).join(' ')||'সব তারিখ দেখা হয়েছে। উত্তর সংরক্ষিত আছে।':'সব তারিখের ছবি দেখে নিজের উত্তর দাও।';
    for(const b of el('dates').querySelectorAll('button'))b.classList.toggle('seen',e.seen_scenes.includes(b.dataset.item));
  }
  function loadScene(i){clear();loaded=false;sceneIndex=i;const r=by.get(currentId),s=r.scenes[i];
    el('dateInfo').textContent=`আসল তারিখ ${s.date} UTC · ${i+1}/${r.scenes.length} · ${s.clear_fraction>=.95?'quality support আছে':'ছবির মান নিয়ে অনিশ্চয়তা'}`;
    for(const [j,b] of [...el('dates').querySelectorAll('button')].entries())b.classList.toggle('active',j===i);
    el('large').href=s.image_path;
    el('image').onload=()=>{if(currentId!==r.sample_id||sceneIndex!==i)return;loaded=true;const e=entry(r);if(!e.seen_scenes.includes(s.item_id)){e.seen_scenes.push(s.item_id);state.entries[r.sample_id]=e;persist();}refresh();counts();};
    el('image').onerror=()=>{loaded=false;fail('ছবি load হয়নি। এটিকে পানি নেই ধরে নিও না।');};el('image').src=s.image_path;
  }
  function show(id){const q=queue();const r=by.get(id)||q[0];if(!r){currentId='';el('workspace').classList.add('hidden');el('empty').classList.remove('hidden');counts();return;}
    currentId=r.sample_id;state.active_id=currentId;el('workspace').classList.remove('hidden');el('empty').classList.add('hidden');
    const pos=q.findIndex(x=>x.sample_id===currentId);el('position').textContent=`মূল নমুনা ${r.number} · তালিকায় ${pos>=0?pos+1:'—'}/${q.length}`;
    el('prev').disabled=pos<=0;el('next').disabled=pos===q.length-1&&pos>=0;
    el('title').textContent=r.region+' · '+r.period;el('meta').textContent=r.sample_id+' · '+r.latitude.toFixed(6)+', '+r.longitude.toFixed(6);
    el('reason').textContent=r.screening.reason_codes.map(c=>reasonMap[c]||c).join('। ');
    if(r.screening.category.startsWith('AUTO_'))el('reason').textContent+=`। কোডের প্রাথমিক অনুমান: ${r.screening.automated_water===1?'পানি আছে':'পানি নেই'} — মানুষের যাচাই নয়।`;
    el('dates').replaceChildren();r.scenes.forEach((s,i)=>{const b=document.createElement('button');b.textContent=s.date;b.dataset.item=s.item_id;b.onclick=()=>loadScene(i);el('dates').append(b);});refresh();counts();persist();loadScene(0);
  }
  function navigate(delta){const q=queue(),p=q.findIndex(r=>r.sample_id===currentId);if(q.length)show(q[Math.max(0,Math.min(q.length-1,p<0?0:p+delta))].sample_id);}
  function answer(label){clear();if(blocked){fail('অন্য tab-এর পরিবর্তন আছে। Backup নিয়ে reload করো।');return;}if(!loaded){fail('ছবি load হতে দাও।');return;}
    const name=el('name').value.trim();if(!name){el('name').focus();fail('আগে নিজের নাম লেখো।');return;}
    const r=by.get(currentId),e=entry(r);e.reviewer=name;e.label=label;e.notes=el('notes').value;e.updated_at=new Date().toISOString();
    const problems=C.errors(e,r);if(problems.length){fail(problems.join(' '));return;}
    state.reviewer=name;state.entries[r.sample_id]=e;if(!persist())return;refresh();counts();
    if(el('autoNext').checked){if(el('filter').value==='PENDING')show(queue()[0]?.sample_id);else navigate(1);}
  }
  function renderList(){el('list').replaceChildren();for(const r of queue()){const b=document.createElement('button');b.textContent=`${r.number} · ${r.region} · ${r.period}${complete(entry(r),r)?' ✓':''}`;b.onclick=()=>show(r.sample_id);el('list').append(b);}}
  function download(value,name,type){const u=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),3000);}
  const stamp=()=>new Date().toISOString().replaceAll(':','-');
  el('backup').onclick=()=>download(JSON.stringify(C.backup(D,state),null,2),'assisted_water_backup_'+stamp()+'.json','application/json;charset=utf-8');
  el('csv').onclick=()=>download(C.csv(D,state.entries),'assisted_water_labels_'+stamp()+'.csv','text/csv;charset=utf-8');
  el('name').onchange=()=>{state.reviewer=el('name').value.trim();persist();};
  el('notes').onchange=()=>{const r=by.get(currentId);if(!r)return;const e=entry(r);e.notes=el('notes').value;e.updated_at=new Date().toISOString();state.entries[r.sample_id]=e;persist();};
  el('filter').onchange=()=>show(queue()[0]?.sample_id);el('prev').onclick=()=>navigate(-1);el('next').onclick=()=>navigate(1);
  for(const b of document.querySelectorAll('.answers button'))b.onclick=()=>answer(b.dataset.label);
  el('toggleList').onclick=()=>{el('listPanel').classList.toggle('hidden');renderList();};
  el('go').onclick=()=>{const n=Number(el('jump').value),r=D.rows.find(r=>r.number===n);if(r){el('filter').value='ALL';show(r.sample_id);}};
  el('help').onclick=()=>el('helpDialog').showModal();el('closeHelp').onclick=()=>el('helpDialog').close();
  el('restore').onclick=()=>el('file').click();el('file').onchange=async()=>{const f=el('file').files[0];if(!f)return;try{if(f.size>10000000)throw Error('Backup ১০ MB-এর বেশি।');pendingImport=C.importBackup(await f.text(),D);el('importDialog').showModal();}catch(e){pendingImport=null;fail(e.message);}finally{el('file').value='';}};
  el('cancelImport').onclick=()=>{pendingImport=null;el('importDialog').close();};el('confirmImport').onclick=()=>{if(!pendingImport||blocked)return;state=pendingImport;pendingImport=null;el('name').value=state.reviewer;el('importDialog').close();el('filter').value='REVIEW';show(state.active_id);};
  const tips={rgb:'স্বাভাবিক রং: হলুদ পুরো অংশে পানি, গাছ বা জমির আকৃতি দেখো। বাইরে পানি থাকলেই ভিতরের উত্তর পানি নয়।',ir:'ইনফ্রারেড: গাঢ় অংশ পানি বা ছায়া হতে পারে। লাল অংশ গাছ/ফসলের সংকেত। অন্য ছবির সঙ্গেও মিলিয়ে দেখো।',swir:'SWIR/NIR/green: অন্য band-এর সমন্বয়। SWIR মূলত ২০ মিটার; বড় করলে নতুন detail আসে না।',quality:'Quality: ধূসর অংশ পরিষ্কার quality support পায়নি। ফ্যাকাশে অংশও পানি/জমির উত্তর নয়।'};
  for(const z of document.querySelectorAll('.zone')){z.title=tips[z.dataset.kind];z.onmouseenter=z.onfocus=z.onclick=()=>el('tip').textContent=tips[z.dataset.kind];}
  window.addEventListener('storage',ev=>{if(ev.key===key){blocked=true;fail('অন্য tab-এ এই review বদলেছে। Backup নিয়ে reload করো।');}});
  document.addEventListener('keydown',ev=>{if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)||document.querySelector('dialog[open]'))return;if(ev.key==='ArrowRight')navigate(1);if(ev.key==='ArrowLeft')navigate(-1);if(ev.key==='1')answer('1');if(ev.key==='0')answer('0');if(ev.key==='2')answer('UNCERTAIN');});
  window.assistedReviewReady=true;show(state.active_id||queue()[0]?.sample_id);
})();
