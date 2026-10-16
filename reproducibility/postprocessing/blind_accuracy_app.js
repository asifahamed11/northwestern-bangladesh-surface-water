(function(){
  'use strict';
  const D=JSON.parse(document.getElementById('blind-review-dataset').textContent),C=BlindAccuracyCore;
  const el=id=>document.getElementById(id),key='nw-independent-dated-review:'+D.id;
  const byID=new Map(D.rows.map((r,i)=>[r.sample_id,i]));
  let state={entries:{},reviewer:'',active_id:D.rows[0].sample_id},pos=0,scenePos=0,loaded=false,blocked=false,pendingImport=null,revision=0;
  function fail(message){el('error').textContent=message;el('error').classList.remove('hidden');}
  function clearError(){el('error').classList.add('hidden');el('error').textContent='';}
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'null');
    if(saved){state=C.importBackup(JSON.stringify(saved.backup),D);revision=Number(saved.revision)||0;}
  }catch(e){fail('পুরোনো browser save পড়া যায়নি। সংরক্ষিত Backup থাকলে import করো। '+e.message);}
  pos=byID.get(state.active_id)||0;el('reviewer').value=state.reviewer;
  function current(){const r=D.rows[pos];return [r,C.entry(state.entries[r.sample_id]||{})];}
  function persist(){
    if(blocked){fail('অন্য tab-এ উত্তর বদলেছে। নিজের Backup নিয়ে page reload করো।');return false;}
    try{
      const external=JSON.parse(localStorage.getItem(key)||'null');
      if(external&&external.revision>revision){blocked=true;fail('অন্য tab-এ নতুন উত্তর আছে। নিজের Backup নিয়ে page reload করো।');return false;}
      revision++;
      localStorage.setItem(key,JSON.stringify({revision,backup:C.backup(D,state)}));
      el('saved').textContent='Browser-এ সংরক্ষিত ✓';return true;
    }catch(e){fail('Browser-এ save হয়নি। এখনই Backup নামাও। '+e.message);return false;}
  }
  function statusText(s){return {PENDING:'এখনও উত্তর দেওয়া হয়নি',PRELIMINARY:'উত্তর আছে; যাচাইয়ের তথ্য অসম্পূর্ণ',VERIFIED:'তোমার dated binary reference সংরক্ষিত',UNCERTAIN:'অনিশ্চিত — জোর করে ০/১ দেওয়া হয়নি'}[s];}
  function counts(){
    const tally={PENDING:0,PRELIMINARY:0,VERIFIED:0,UNCERTAIN:0};
    for(const r of D.rows)tally[C.status(C.entry(state.entries[r.sample_id]||{}),r)]++;
    el('counts').textContent=`উত্তর: ${D.rows.length-tally.PENDING}/${D.rows.length} · যাচাই করা binary: ${tally.VERIFIED} · অনিশ্চিত: ${tally.UNCERTAIN}`;
    if(!el('listPanel').classList.contains('hidden'))renderList();
  }
  function refreshEntry(){
    const [r,e]=current(),s=C.status(e,r);
    el('state').textContent=statusText(s);
    el('attested').checked=e.attested;el('notes').value=e.notes;el('reason').value=e.reason;
    el('reasonField').classList.toggle('hidden',e.label!=='UNCERTAIN');
    for(const b of document.querySelectorAll('.answer button'))b.classList.toggle('selected',b.dataset.label===e.label);
    const test={...e,label:['0','1'].includes(e.label)?e.label:'0',reviewer:state.reviewer||e.reviewer};
    const errors=C.evidenceErrors(test,r);
    el('evidenceHint').textContent=!e.label?'প্রথমে প্রস্তুত সব তারিখের ছবি দেখো। তারপর নিজের সিদ্ধান্ত দাও।':e.label==='UNCERTAIN'?'অনিশ্চিত রাখা ঠিক আছে। চাইলে নিচে কারণ বেছে নিতে পারো।':errors.length?errors.join(' '):'ছবির দিন/মানের নিয়ম মিলে গেছে। সঠিক ব্যাখ্যার দায়িত্ব তোমার নিজের যাচাইয়ে।';
    for(const b of el('dates').querySelectorAll('button'))b.classList.toggle('seen',e.seen_scenes.includes(b.dataset.item));
  }
  function loadScene(i){
    clearError();loaded=false;scenePos=i;const [r]=current(),s=r.scenes[i];
    el('imageError').classList.add('hidden');
    el('dateInfo').textContent=`আসল ছবি: ${s.date} UTC · ${i+1}/${r.scenes.length} · ${s.clear_fraction>=.95?'হলুদ অংশ quality mask-এ গ্রহণযোগ্য':'ছবির মান/coverage নিয়ে অনিশ্চয়তা আছে'}`;
    for(const [j,b] of [...el('dates').querySelectorAll('button')].entries())b.classList.toggle('active',j===i);
    el('largeImage').href=s.image_path;el('image').alt=`নমুনা ${r.number}, ${s.date} তারিখের আসল ছবি`;
    el('image').onload=()=>{
      if(D.rows[pos].sample_id!==r.sample_id||scenePos!==i)return;
      loaded=true;const e=C.entry(state.entries[r.sample_id]||{});
      if(!e.seen_scenes.includes(s.item_id)){e.seen_scenes.push(s.item_id);state.entries[r.sample_id]=e;persist();}
      refreshEntry();counts();
    };
    el('image').onerror=()=>{loaded=false;el('imageError').classList.remove('hidden');fail('ছবি load হয়নি। এটিকে পানি নেই ধরে নেবে না।');};
    el('image').src=s.image_path;
  }
  function show(n){
    pos=Math.max(0,Math.min(D.rows.length-1,n));scenePos=0;const [r]=current();state.active_id=r.sample_id;
    el('position').textContent=`${r.number} / ${D.rows.length}`;el('pointTitle').textContent=r.region+' · '+r.period;
    el('pointMeta').textContent=`${r.sample_id} · ${r.latitude.toFixed(6)}, ${r.longitude.toFixed(6)}`;
    el('dates').replaceChildren();
    r.scenes.forEach((s,i)=>{const b=document.createElement('button');b.textContent=s.date;b.dataset.item=s.item_id;b.onclick=()=>loadScene(i);el('dates').append(b);});
    el('prev').disabled=pos===0;el('next').disabled=pos===D.rows.length-1;
    refreshEntry();counts();persist();loadScene(0);
  }
  function saveAnswer(label){
    clearError();if(blocked){fail('অন্য tab-এর পরিবর্তন আছে। Backup নিয়ে reload করো।');return;}
    const reviewer=el('reviewer').value.trim();
    if(!reviewer){el('reviewer').focus();fail('আগে উপরে নিজের নাম লিখো।');return;}
    if(!loaded){fail('ছবি load হওয়া পর্যন্ত অপেক্ষা করো।');return;}
    const [r,e]=current();state.reviewer=reviewer;e.reviewer=reviewer;e.label=label;
    e.notes=el('notes').value;e.reason=label==='UNCERTAIN'?el('reason').value:'';
    e.attested=label!=='UNCERTAIN'&&el('attested').checked;e.updated_at=new Date().toISOString();
    if(e.attested){const errors=C.evidenceErrors(e,r);if(errors.length){fail(errors.join(' '));return;}}
    state.entries[r.sample_id]=e;persist();refreshEntry();counts();
    if(el('autoNext').checked&&pos<D.rows.length-1)show(pos+1);
  }
  function saveNotes(){
    const [r,e]=current();e.notes=el('notes').value;e.reason=e.label==='UNCERTAIN'?el('reason').value:'';e.updated_at=new Date().toISOString();state.entries[r.sample_id]=e;persist();
  }
  function renderList(){
    const filter=el('filter').value;el('list').replaceChildren();
    D.rows.forEach((r,i)=>{const s=C.status(C.entry(state.entries[r.sample_id]||{}),r);if(filter!=='all'&&filter!==s)return;
      const b=document.createElement('button');b.textContent=`${r.number} · ${r.region} · ${r.period} · ${statusText(s)}`;b.onclick=()=>show(i);el('list').append(b);});
  }
  function download(text,name,type){const blob=new Blob([text],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);}
  el('backup').onclick=()=>download(JSON.stringify(C.backup(D,state),null,2),'independent_water_review_backup_'+new Date().toISOString().replaceAll(':','-')+'.json','application/json;charset=utf-8');
  el('csv').onclick=()=>download(C.csvOutput(D,state.entries),'independent_water_reference_'+new Date().toISOString().replaceAll(':','-')+'.csv','text/csv;charset=utf-8');
  el('reviewer').onchange=()=>{state.reviewer=el('reviewer').value.trim();persist();};
  el('prev').onclick=()=>show(pos-1);el('next').onclick=()=>show(pos+1);
  for(const b of document.querySelectorAll('.answer button'))b.onclick=()=>saveAnswer(b.dataset.label);
  el('attested').onchange=()=>{const [r,e]=current();if(e.label&&e.label!=='UNCERTAIN'){if(el('attested').checked&&C.evidenceErrors({...e,reviewer:state.reviewer||e.reviewer},r).length){el('attested').checked=false;fail(C.evidenceErrors({...e,reviewer:state.reviewer||e.reviewer},r).join(' '));return;}e.attested=el('attested').checked;e.updated_at=new Date().toISOString();state.entries[r.sample_id]=e;persist();refreshEntry();counts();}};
  el('notes').onchange=saveNotes;el('reason').onchange=saveNotes;
  el('toggleList').onclick=()=>{el('listPanel').classList.toggle('hidden');renderList();};el('filter').onchange=renderList;
  el('goJump').onclick=()=>{const n=Number(el('jump').value);if(Number.isInteger(n)&&n>=1&&n<=D.rows.length)show(n-1);};
  el('help').onclick=()=>el('helpDialog').showModal();el('closeHelp').onclick=()=>el('helpDialog').close();
  el('import').onclick=()=>el('importFile').click();
  el('importFile').onchange=async()=>{const f=el('importFile').files[0];if(!f)return;try{if(f.size>10000000)throw Error('ফাইল ১০ MB-এর বেশি।');pendingImport=C.importBackup(await f.text(),D);el('importDialog').showModal();}catch(e){pendingImport=null;fail(e.message);}finally{el('importFile').value='';}};
  el('cancelImport').onclick=()=>{pendingImport=null;el('importDialog').close();};
  el('confirmImport').onclick=()=>{if(!pendingImport||blocked)return;state=pendingImport;pendingImport=null;el('reviewer').value=state.reviewer;el('importDialog').close();show(byID.get(state.active_id));};
  const tips={rgb:'স্বাভাবিক রং: জায়গার আকৃতি ও দৃশ্যমান গাছ/জমি/জলভাগ দেখো। পাশের অংশের বদলে পুরো হলুদ অংশ বিচার করো।',ir:'ইনফ্রারেড: অন্য band-এর ছবি। গাঢ় অংশ পানি বা ছায়া হতে পারে; একা এই রং দিয়ে নিশ্চিত হবে না।',swir:'SWIR/NIR/green: আরেক ধরনের band সমন্বয়। SWIR মূলত ২০ মিটার; বড় করে দেখালে নতুন detail তৈরি হয় না।',quality:'ছবির মান: ধূসর অংশ গ্রহণযোগ্য quality support পায়নি। ফ্যাকাশে অংশও নিজে পানি/জমির উত্তর নয়।'};
  for(const z of document.querySelectorAll('.zone')){z.title=tips[z.dataset.kind];z.onmouseenter=z.onfocus=z.onclick=()=>{el('tip').textContent=tips[z.dataset.kind];};}
  window.addEventListener('storage',ev=>{if(ev.key===key){blocked=true;fail('অন্য tab-এ একই dataset-এর উত্তর বদলেছে। নিজের Backup নিয়ে reload করো।');}});
  document.addEventListener('keydown',ev=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)||document.querySelector('dialog[open]'))return;if(ev.key==='ArrowRight')show(pos+1);if(ev.key==='ArrowLeft')show(pos-1);if(ev.key==='1')saveAnswer('1');if(ev.key==='0')saveAnswer('0');if(ev.key==='2')saveAnswer('UNCERTAIN');});
  window.blindReviewReady=true;show(pos);
})();
