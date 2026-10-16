(function(){
  'use strict';
  const D=JSON.parse(document.getElementById('dataset').textContent),C=DatedWaterCore,el=id=>document.getElementById(id),by=new Map(D.rows.map(r=>[r.sample_id,r]));
  const key='nw-assisted-dated-water-review:'+D.id,legacyKey='nw-assisted-water-review:'+D.parent_dataset_id;
  let state={entries:{},reviewer:'',active_id:'',active_scene:''},revision=0,blocked=false,loaded=false,pendingImport=null;
  function fail(s){el('error').textContent=s;el('error').classList.remove('hidden');}
  function clear(){el('error').classList.add('hidden');}
  try{const saved=JSON.parse(localStorage.getItem(key)||'null');if(saved){state=C.importBackup(JSON.stringify(saved.backup),D);revision=Number(saved.revision)||0;}
    else{const old=JSON.parse(localStorage.getItem(legacyKey)||'null');if(old?.backup)state=C.importBackup(JSON.stringify(old.backup),D);}
  }catch(e){fail('Browser save পড়া যায়নি। নিজের Backup আনতে পারো। '+e.message);}
  el('name').value=state.reviewer;
  const entry=r=>C.entry(state.entries[r.sample_id]||{}),current=()=>by.get(state.active_id),scene=()=>current()?.scenes.find(s=>s.item_id===state.active_scene);
  function persist(){if(blocked){fail('অন্য tab-এ উত্তর বদলেছে। Backup নিয়ে reload করো।');return false;}try{
    const other=JSON.parse(localStorage.getItem(key)||'null');if(other&&other.revision>revision){blocked=true;fail('অন্য tab-এর নতুন উত্তর আছে। Backup নিয়ে reload করো।');return false;}
    revision++;localStorage.setItem(key,JSON.stringify({revision,backup:C.backup(D,state)}));el('saved').textContent='উত্তর এই browser-এ সংরক্ষিত ✓';return true;
  }catch(e){fail('Save হয়নি। এখনই Backup নামাও। '+e.message);return false;}}
  function queue(){const f=el('filter').value;return D.rows.filter(r=>f==='ALL'||f==='REVIEW'&&r.screening.category==='REVIEW'||f==='PENDING'&&r.screening.category==='REVIEW'&&!C.summary(entry(r),r).complete||f==='AUTO'&&r.screening.category.startsWith('AUTO_')||f==='QUALITY_LIMITED'&&r.screening.category==='QUALITY_LIMITED');}
  function defaultScenes(r){const good=C.required(r);return good.length?good:r.scenes;}
  function progress(){const review=D.rows.filter(r=>r.screening.category==='REVIEW');let done=0,dates=0,total=0;
    for(const r of review){const s=C.summary(entry(r),r);done+=Number(s.complete);dates+=s.answered_required_dates;total+=s.required_dates;}
    el('progress').textContent=`জায়গা: ${done}/${review.length}`;el('progress').title=`গ্রহণযোগ্য দিনের উত্তর: ${dates}/${total}`;
    const old=Object.values(state.entries).filter(e=>e.legacy_point_answer?.label).length;
    el('legacyNotice').classList.toggle('hidden',old===0);el('legacyNotice').textContent=`পুরোনো ${old}টি জায়গার উত্তর অক্ষত আছে। এগুলো আলাদা দিনের উত্তর হিসেবে বসানো হয়নি।`;
  }
  const pretty=d=>new Intl.DateTimeFormat('bn-BD',{day:'numeric',month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(d+'T00:00:00Z'));
  function renderDates(){const r=current(),e=entry(r);el('allDates').replaceChildren();for(const s of r.scenes){const b=document.createElement('button');
    b.textContent=pretty(s.date)+(s.clear_fraction<.95?' · অস্পষ্ট':'');b.dataset.item=s.item_id;b.classList.toggle('current',s.item_id===state.active_scene);b.classList.toggle('poor',s.clear_fraction<.95);b.classList.toggle('answered',!!e.dates[s.item_id]);b.onclick=()=>show(r.sample_id,s.item_id);el('allDates').append(b);}
    el('dateSummary').textContent=`সব ${r.scenes.length} দিনের তালিকা (ইচ্ছা হলে)`;
  }
  function refresh(){const r=current(),s=scene(),e=entry(r),a=e.dates[s.item_id],summary=C.summary(e,r);
    el('dateState').textContent=!a?'এই দিনের উত্তর এখনও নেই':a.label==='1'?'এই দিন: পানি আছে ✓':a.label==='0'?'এই দিন: পানি নেই ✓':'এই দিন: বোঝা যায়নি ✓';
    for(const b of document.querySelectorAll('.answers button'))b.classList.toggle('selected',b.dataset.label===a?.label);
    el('notes').value=e.notes;el('monthState').classList.toggle('change',summary.temporal_change);
    el('monthState').textContent=summary.temporal_change?'দিনভেদে বদলেছে: কোনো দিন পানি, কোনো দিন জমি। উত্তরগুলো আলাদা আছে।':summary.has_uncertain_date?'এক বা একাধিক দিন বোঝা যায়নি। নিশ্চিত উত্তর বানানো হয়নি।':summary.complete?'দেখা গ্রহণযোগ্য দিনগুলোর উত্তর দেওয়া হয়েছে।':`${summary.answered_required_dates}/${summary.required_dates} গ্রহণযোগ্য দিনের উত্তর দেওয়া হয়েছে।`;
    el('qualityHint').textContent=s.clear_fraction<.95?'এই দিনের ছবি/quality support অপর্যাপ্ত। ভালো করে বোঝা না গেলে ২ দাও; খালি রেখেও পরে যেতে পারো।':'আজকের ছবির quality support আছে। শুধু হলুদ অংশ দেখো; রংগুলো ইঙ্গিত, নিশ্চিত সত্য নয়।';
    renderDates();progress();
  }
  function show(id,item){clear();const r=by.get(id)||queue()[0];if(!r){el('workspace').classList.add('hidden');el('empty').classList.remove('hidden');progress();return;}
    el('workspace').classList.remove('hidden');el('empty').classList.add('hidden');state.active_id=r.sample_id;
    const tasks=defaultScenes(r),e=entry(r),s=r.scenes.find(s=>s.item_id===item)||tasks.find(s=>!e.dates[s.item_id])||tasks[0];state.active_scene=s.item_id;loaded=false;
    const q=queue(),pos=q.findIndex(p=>p.sample_id===r.sample_id),dayPos=tasks.findIndex(d=>d.item_id===s.item_id);
    el('pointNumber').textContent=`জায়গা ${pos>=0?pos+1:'—'}/${q.length} · মূল নং ${r.number}`;el('placeTitle').textContent=r.region+' · '+r.period;
    el('dayDate').textContent=pretty(s.date);el('answerDate').textContent=pretty(s.date);el('dateStep').textContent=dayPos<0?'অতিরিক্ত / অস্পষ্ট দিনের ছবি':`গ্রহণযোগ্য দিন ${dayPos+1}/${tasks.length}`;
    el('prevDay').disabled=dayPos<=0;el('nextDay').disabled=dayPos===tasks.length-1;el('prevPlace').disabled=pos<=0;
    el('large').href=s.image_path;el('image').alt=pretty(s.date)+' দিনের চার ধরনের আসল satellite ছবি';
    refresh();persist();
    el('image').onload=()=>{if(state.active_id!==r.sample_id||state.active_scene!==s.item_id)return;loaded=true;const e=entry(r);if(!e.seen_scenes.includes(s.item_id)){e.seen_scenes.push(s.item_id);state.entries[r.sample_id]=e;persist();}};
    el('image').onerror=()=>{loaded=false;fail('এই ছবিটি load হয়নি। এটিকে পানি নেই ধরে নিও না।');};el('image').src=s.image_path;
  }
  function nextPlace(delta=1){const q=queue(),p=q.findIndex(r=>r.sample_id===state.active_id),n=p<0?0:p+delta;
    if(n>=q.length){el('workspace').classList.add('hidden');el('empty').classList.remove('hidden');progress();return;}
    if(n>=0&&q[n])show(q[n].sample_id);
  }
  function nextDay(delta){const r=current();if(!r)return;const tasks=defaultScenes(r),p=tasks.findIndex(s=>s.item_id===state.active_scene),n=p<0?0:p+delta;if(tasks[n])show(r.sample_id,tasks[n].item_id);}
  function saveDate(label){clear();if(blocked){fail('অন্য tab-এর পরিবর্তন আছে। Backup নিয়ে reload করো।');return;}if(!loaded){fail('ছবি load হতে দাও।');return;}
    const name=el('name').value.trim();if(!name){el('name').focus();fail('আগে নিজের নাম লেখো।');return;}
    const r=current(),s=scene(),e=entry(r);e.dates[s.item_id]=C.answer({label,reviewer:name,updated_at:new Date().toISOString()});e.notes=el('notes').value;
    state.reviewer=name;state.entries[r.sample_id]=e;if(!persist())return;refresh();
    if(el('autoNext').checked){const tasks=defaultScenes(r),start=tasks.findIndex(d=>d.item_id===s.item_id),next=tasks.find((d,i)=>i>start&&!e.dates[d.item_id])||tasks.find(d=>!e.dates[d.item_id]);
      if(next)show(r.sample_id,next.item_id);else nextPlace(1);}
  }
  function renderList(){el('list').replaceChildren();for(const r of queue()){const b=document.createElement('button');const s=C.summary(entry(r),r);b.textContent=`${r.number} · ${r.region} · ${s.answered_required_dates}/${s.required_dates} দিন${s.temporal_change?' · বদলেছে':''}`;b.onclick=()=>{el('optionsDialog').close();show(r.sample_id);};el('list').append(b);}}
  function download(value,name,type){const u=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),3000);}
  const stamp=()=>new Date().toISOString().replaceAll(':','-');
  el('backup').onclick=()=>download(JSON.stringify(C.backup(D,state),null,2),'dated_water_backup_'+stamp()+'.json','application/json;charset=utf-8');
  el('csv').onclick=()=>download(C.dateCSV(D,state.entries),'dated_water_labels_'+stamp()+'.csv','text/csv;charset=utf-8');
  el('summaryCSV').onclick=()=>download(C.summaryCSV(D,state.entries),'dated_water_summary_'+stamp()+'.csv','text/csv;charset=utf-8');
  el('name').onchange=()=>{state.reviewer=el('name').value.trim();persist();};
  el('notes').onchange=()=>{const r=current();if(!r)return;const e=entry(r);e.notes=el('notes').value;state.entries[r.sample_id]=e;persist();};
  el('prevDay').onclick=()=>nextDay(-1);el('nextDay').onclick=()=>nextDay(1);el('prevPlace').onclick=()=>nextPlace(-1);el('skipPlace').onclick=()=>nextPlace(1);
  for(const b of document.querySelectorAll('.answers button'))b.onclick=()=>saveDate(b.dataset.label);
  el('options').onclick=()=>{renderList();el('optionsDialog').showModal();};el('closeOptions').onclick=()=>el('optionsDialog').close();
  el('filter').onchange=()=>{renderList();show(queue()[0]?.sample_id);};el('go').onclick=()=>{const r=D.rows.find(r=>r.number===Number(el('jump').value));if(r){el('filter').value='ALL';el('optionsDialog').close();show(r.sample_id);}};
  el('clearDate').onclick=()=>{const r=current(),s=scene();if(!r||!s)return;const e=entry(r);delete e.dates[s.item_id];state.entries[r.sample_id]=e;persist();refresh();el('optionsDialog').close();};
  el('help').onclick=()=>el('helpDialog').showModal();el('closeHelp').onclick=()=>el('helpDialog').close();
  el('restore').onclick=()=>el('file').click();el('file').onchange=async()=>{const f=el('file').files[0];if(!f)return;try{if(f.size>15000000)throw Error('Backup ১৫ MB-এর বেশি।');pendingImport=C.importBackup(await f.text(),D);el('optionsDialog').close();
    el('importInfo').textContent=pendingImport.migrated_legacy?'পুরোনো জায়গাভিত্তিক উত্তর আলাদা করে রাখা হবে। সেগুলো কোনো দিনের উত্তর হিসেবে copy হবে না। বর্তমান browser-এর dated উত্তর Backup-এর তথ্য দিয়ে বদলাবে। আগে নিজের Backup নিতে পারো।':'এই browser-এর dated উত্তর Backup দিয়ে বদলাবে। বর্তমান Backup আগে নামিয়ে রাখতে পারো।';el('importDialog').showModal();
  }catch(e){pendingImport=null;fail(e.message);}finally{el('file').value='';}};
  el('cancelImport').onclick=()=>{pendingImport=null;el('importDialog').close();};el('confirmImport').onclick=()=>{if(!pendingImport||blocked)return;state=pendingImport;pendingImport=null;el('name').value=state.reviewer;el('importDialog').close();show(state.active_id,state.active_scene);};
  const tips={rgb:'স্বাভাবিক রং\nগাঢ় নীল/সবুজ → পানির ইঙ্গিত\nসবুজ → গাছও হতে পারে\nবাদামি → মাটি বা ঘোলা পানি\nসাদা → মেঘ/বালু/বসতি; অন্য ছবিও মিলাও।',
    ir:'ইনফ্রারেড\nগাঢ় নীল/কালো → পানি বা ছায়া\nউজ্জ্বল লাল → গাছ/ফসল\nশুধু গাঢ় রং দেখে ১ দেবে না।',
    mndwi:'পানির সংকেত · MNDWI\nনীল → পানির মতো সংকেত\nকমলা/লাল → জমির মতো সংকেত\nসাদা → দুর্বল/সীমা; ধূসর → গ্রহণযোগ্য মান নেই\nমিশ্র হলে বা না বুঝলে ২ দাও।',
    quality:'ছবির মান\nফ্যাকাশে → গ্রহণযোগ্য quality support\nধূসর → মেঘ/ছায়া/নোডেটা/অগ্রহণযোগ্য\nএটি পানি বা জমির রং নয়।'};
  function hint(z,event){const tip=el('hoverTip');tip.textContent=tips[z.dataset.kind];tip.classList.remove('hidden');const rect=z.getBoundingClientRect();
    const x=event?.clientX??rect.left+rect.width/2,y=event?.clientY??rect.top+20;
    tip.style.left=Math.max(10,Math.min(innerWidth-tip.offsetWidth-10,x+12))+'px';tip.style.top=Math.max(10,Math.min(innerHeight-tip.offsetHeight-10,y+14))+'px';}
  for(const z of document.querySelectorAll('.zone')){z.title='রঙের hint দেখো';z.addEventListener('mouseenter',e=>hint(z,e));z.addEventListener('mousemove',e=>hint(z,e));z.addEventListener('focus',()=>hint(z));z.addEventListener('click',e=>{e.stopPropagation();hint(z,e);});z.addEventListener('mouseleave',()=>el('hoverTip').classList.add('hidden'));z.addEventListener('blur',()=>el('hoverTip').classList.add('hidden'));}
  document.addEventListener('click',e=>{if(!e.target.closest('.zone'))el('hoverTip').classList.add('hidden');});
  window.addEventListener('storage',e=>{if(e.key===key){blocked=true;fail('অন্য tab-এ এই dated review বদলেছে। Backup নিয়ে reload করো।');}});
  document.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)||document.querySelector('dialog[open]'))return;if(e.key==='ArrowRight')nextDay(1);if(e.key==='ArrowLeft')nextDay(-1);if(e.key==='1')saveDate('1');if(e.key==='0')saveDate('0');if(e.key==='2')saveDate('UNCERTAIN');});
  window.datedReviewReady=true;show(state.active_id||queue()[0]?.sample_id,state.active_scene);
})();
