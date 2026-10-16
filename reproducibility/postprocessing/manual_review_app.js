(function () {
  'use strict';
  const $=id=>document.getElementById(id), C=ReviewCore;
  const dataset=JSON.parse($('review-dataset').textContent);
  const rows=dataset.rows, byID=new Map(rows.map((r,i)=>[r.id,{...r,index:i}]));
  const bn=n=>Number(n).toLocaleString('bn-BD');
  const regionNames={Naogaon:'নওগাঁ',Rajshahi:'রাজশাহী',Chapainawabganj:'চাঁপাইনবাবগঞ্জ'};
  const names={PENDING:'উত্তর বাকি',PRELIMINARY:'প্রাথমিক নোট',UNCERTAIN:'অনিশ্চিত',VERIFIED:'তারিখসহ যাচাই'};
  const marks={PENDING:'○',PRELIMINARY:'✓',UNCERTAIN:'?',VERIFIED:'✓✓'};
  const storageKey='nw-water-review-v1:'+dataset.id;
  let storageRaw=null, writeLocked=false, storageFailed=false, dirty=false, toastTimer, pendingImport=null;
  let state={entries:{},active_id:rows[0].id,revision:0,auto_next:false}, undoStack=[], mode='all', zoom=1, changesSinceBackup=0, imageOK=false;
  function fatal(message){$('fatal').textContent=message;$('fatal').classList.remove('hidden');$('app').classList.add('hidden');}
  if(!rows.length || byID.size!==rows.length || dataset.export_order.length!==rows.length || new Set(dataset.export_order).size!==rows.length || dataset.export_order.some(id=>!byID.has(id))){fatal('জায়গার ID মেলেনি। এই ফাইলে উত্তর দিও না।');return;}
  function notice(message,error=false){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').className='toast'+(error?' error':'');toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),5500);}
  function storageWarning(message){$('storageWarning').textContent=message;$('storageWarning').classList.remove('hidden');$('saveState').textContent='Backup নেওয়া দরকার';$('saveDot').style.background='#bd7d29';}
  try {storageRaw=localStorage.getItem(storageKey);}
  catch(e){storageFailed=true;storageWarning('এই browser-এ local save পাওয়া যাচ্ছে না। খোলা tab-এ কাজ করতে পারবে; বন্ধ করার আগে Backup নাও।');}
  try {
    if(storageRaw){
      const saved=JSON.parse(storageRaw);
      if(saved.schema!=='nw-water-manual-review-v1' || saved.dataset_id!==dataset.id || !Array.isArray(saved.records))throw Error('সংরক্ষিত কাজের dataset মেলেনি।');
      const entries=C.validateRecords(saved.records,dataset,true);
      state={entries,active_id:byID.has(saved.active_id)?saved.active_id:rows[0].id,revision:Number.isInteger(saved.revision)?saved.revision:0,auto_next:saved.auto_next===true};
    }
    if(!storageFailed)$('saveState').textContent=storageRaw?'আগের কাজ ফিরে এসেছে':'উত্তর দিলেই এখানে সেভ হবে';
  } catch(e) {writeLocked=true;storageWarning('Browser-এর পুরোনো সেভ পড়া যায়নি। সেটি বদলানো হয়নি। Backup থাকলে অন্য একটি নতুন browser-এ ফিরিয়ে আনো। '+e.message);}
  function current(){return byID.get(state.active_id);}
  function get(id=state.active_id){return state.entries[id] || C.blank();}
  function canEdit(){if(writeLocked){notice('এই tab-এ লেখা বন্ধ আছে। আগে Backup নাও, তারপর page reload করো।',true);return false;}return true;}
  function persist(){
    dirty=true;
    if(writeLocked)return false;
    try {
      const remote=localStorage.getItem(storageKey);
      if(remote!==storageRaw){writeLocked=true;storageWarning('একই কাজ অন্য tab-এ বদলেছে। এই tab-এ লেখা বন্ধ করা হয়েছে। এই tab-এর Backup নাও, তারপর reload করে ID মিলিয়ে import করো।');return false;}
      const data=JSON.parse(C.backup(dataset,state));data.revision=state.revision+1;data.auto_next=state.auto_next;
      const raw=JSON.stringify(data);localStorage.setItem(storageKey,raw);storageRaw=raw;state.revision++;
      dirty=false;storageFailed=false;
      $('saveState').textContent='এই browser-এ সেভ হয়েছে';$('saveDot').style.background='#36a780';$('storageWarning').classList.add('hidden');
      return true;
    } catch(e) {storageFailed=true;storageWarning('Browser-এ সেভ করা যাচ্ছে না। কাজ এই খোলা tab-এ আছে—বন্ধ করার আগে অবশ্যই Backup নাও।');return false;}
  }
  window.addEventListener('storage',e=>{if(e.key===storageKey && e.newValue!==storageRaw){writeLocked=true;storageWarning('অন্য tab-এ এই কাজ বদলেছে। একসঙ্গে দুই tab-এ লিখবে না। এই tab-এর Backup নিয়ে reload করো।');}});
  window.addEventListener('beforeunload',e=>{if(dirty || storageFailed){e.preventDefault();e.returnValue='';}});
  function saveEntry(next,undo=true){
    if(!canEdit())return false;
    const prev=C.entry(get()), updated=C.entry(next);
    if(C.comparable(prev)===C.comparable(updated))return true;
    if(undo){undoStack.push({id:state.active_id,entry:prev});if(undoStack.length>150)undoStack.shift();}
    updated.updated_at=new Date().toISOString();state.entries[state.active_id]=updated;changesSinceBackup++;
    persist();updateStats();updateStatus();
    if($('statusFilter').value)renderList();else updateListItem(state.active_id);
    $('undoBtn').disabled=!undoStack.length;
    $('backupReminder').classList.toggle('hidden',changesSinceBackup<25);
    return true;
  }
  function updateStats(){
    let done=0,uncertain=0,verified=0;
    for(const r of rows){const e=get(r.id);if(e.label!=='')done++;const s=C.status(e,r);if(s==='UNCERTAIN')uncertain++;if(s==='VERIFIED')verified++;}
    $('doneCount').textContent=bn(done);$('pendingCount').textContent=bn(rows.length-done);$('uncertainCount').textContent=bn(uncertain);$('verifiedCount').textContent=bn(verified);$('totalText').textContent=bn(rows.length)+'টি জায়গার মধ্যে';$('progressBar').style.width=(100*done/rows.length)+'%';
    $('simpleProgress').textContent=bn(done)+' / '+bn(rows.length)+' উত্তর দেওয়া';
  }
  function matches(r){
    const q=$('search').value.trim().toLowerCase(), p=$('periodFilter').value, s=$('statusFilter').value;
    return (!q || [r.id,r.region,regionNames[r.region],r.period,String(r.index+1)].some(x=>x.toLowerCase().includes(q))) && (!p || p===r.period) && (!s || s===C.status(get(r.id),r));
  }
  function renderList(){
    const list=$('sampleList');const frag=document.createDocumentFragment();let count=0;
    for(const raw of rows){const r=byID.get(raw.id);if(!matches(r))continue;count++;
      const b=document.createElement('button');b.type='button';b.className='sample'+(r.id===state.active_id?' active':'');b.dataset.id=r.id;
      const s=C.status(get(r.id),r);b.dataset.status=s;b.setAttribute('aria-label',(r.index+1)+' '+regionNames[r.region]+' '+r.period+' '+names[s]);b.setAttribute('aria-current',r.id===state.active_id?'true':'false');
      const line=document.createElement('div');line.className='row';const label=document.createElement('span');label.textContent=bn(r.index+1)+'. '+regionNames[r.region];const mark=document.createElement('span');mark.className='mark';mark.textContent=marks[s];line.append(label,mark);
      const small=document.createElement('small');small.textContent=r.period+' · '+names[s];b.append(line,small);b.addEventListener('click',()=>goID(r.id));frag.append(b);
    }
    if(!count){const p=document.createElement('p');p.className='hint';p.textContent='এই filter-এ কোনো জায়গা নেই।';frag.append(p);}
    list.replaceChildren(frag);$('listCount').textContent=bn(count)+' / '+bn(rows.length)+'টি দেখানো হচ্ছে';
  }
  function updateListItem(id){
    const b=Array.from($('sampleList').children).find(x=>x.dataset.id===id);if(!b)return;
    const r=byID.get(id),s=C.status(get(id),r);b.dataset.status=s;b.querySelector('.mark').textContent=marks[s];b.querySelector('small').textContent=r.period+' · '+names[s];
    b.setAttribute('aria-label',(r.index+1)+' '+regionNames[r.region]+' '+r.period+' '+names[s]);
  }
  function updateStatus(){
    const r=current(),e=get(),s=C.status(e,r),badge=$('recordStatus');badge.textContent=names[s];badge.className='badge'+(s==='VERIFIED'?' verified':s==='UNCERTAIN'?' uncertain':'');
    document.querySelectorAll('.answer').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.value===e.label)));
    $('reasonField').classList.toggle('hidden',e.label!=='UNCERTAIN');
    const errors=C.evidenceErrors(e,r);
    $('evidenceError').textContent=e.attested&&errors.length?'চূড়ান্ত হয়নি: '+errors.join(' '):s==='VERIFIED'?'প্রমাণের প্রয়োজনীয় তথ্য পূরণ হয়েছে। ছবি ও screenshot নিজের কাছে রাখো।':e.reference_date&&!C.dateOK(e.reference_date,r.period)?'তারিখটি target মাসের নয় অথবা সঠিক নয়।':'প্রমাণের তথ্য ছাড়া উত্তরটি প্রাথমিক নোট হিসেবেই থাকবে।';
    updateNavigation();
  }
  function navigationTarget(delta){const candidates=rows.map(r=>byID.get(r.id)).filter(r=>matches(r) && (delta>0?r.index>current().index:r.index<current().index));return delta>0?candidates[0]:candidates.at(-1);}
  function updateNavigation(){$('prevBtn').disabled=!navigationTarget(-1);$('nextBtn').disabled=!navigationTarget(1);}
  function setView(){
    const viewBoxes={all:'0 0 560 560',rgb:'22 59 237 236',infrared:'302 59 237 236',mndwi:'22 321 237 236',radar:'302 321 237 236'};
    $('imageSvg').setAttribute('viewBox',viewBoxes[mode]);
    document.querySelectorAll('.help-zone').forEach(zone=>{const visible=mode==='all'||zone.dataset.help===mode;zone.style.display=visible?'':'none';zone.setAttribute('tabindex',visible?'0':'-1');});
    window.imageHelpUI?.hide();
    const edge=Math.max(220,Math.min($('imageWell').clientWidth-2,$('imageWell').clientHeight-2))*zoom;
    $('imageSvg').style.width=edge+'px';$('imageSvg').style.height=edge+'px';$('zoomText').textContent=Math.round(zoom*100)+'%';
    document.querySelectorAll('.viewmode').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
  }
  function renderCurrent(){
    const r=current(),e=get();$('position').textContent='জায়গা '+bn(r.index+1)+' / '+bn(rows.length);$('placeTitle').textContent=regionNames[r.region]+' · '+r.period;$('sampleId').textContent=r.id;
    $('coordinates').textContent=r.latitude.toFixed(9)+', '+r.longitude.toFixed(9);$('jump').value=r.index+1;$('jump').max=rows.length;
    if($('chip').dataset.sampleId!==r.id){imageOK=false;$('chip').dataset.sampleId=r.id;$('chip').setAttribute('href',r.image);document.querySelectorAll('.answer').forEach(b=>b.disabled=true);}
    $('imageSvg').setAttribute('aria-label',r.id+' '+r.period+' '+regionNames[r.region]+' হলুদ বাক্সে পুরো pixel');
    for(const f of ['notes','reason','reference_date','reference_source','evidence_id','reviewer'])$(f).value=e[f];
    $('notePanel').open=Boolean(e.notes);
    $('attested').checked=e.attested;$('reference_date').min=r.period+'-01';
    const [y,m]=r.period.split('-').map(Number);$('reference_date').max=r.period+'-'+new Date(Date.UTC(y,m,0)).getUTCDate();
    $('dateHint').textContent='Target মাস: '+r.period+'। Timeline-এর নির্বাচন নয়, ছবির প্রকৃত acquisition date লিখবে।';
    $('prevBtn').disabled=r.index===0;$('nextBtn').disabled=r.index===rows.length-1;
    if(e.attested || e.reference_date || e.reference_source || e.evidence_id)$('evidencePanel').open=true;else $('evidencePanel').open=false;
    updateStatus();setView();
    for(const el of $('sampleList').children){const active=el.dataset.id===r.id;el.classList.toggle('active',active);el.setAttribute('aria-current',String(active));}
  }
  function goID(id){if(!byID.has(id))return;state.active_id=id;persist();zoom=1;renderCurrent();}
  function navigate(delta){const target=navigationTarget(delta);if(target)goID(target.id);}
  function setLabel(label){
    if(!imageOK){notice('ছবি লোড হয়নি। এই অবস্থায় উত্তর দিও না।',true);return;}
    const next={...get(),label};if(next.label!==get().label){next.attested=false;if(label!=='UNCERTAIN')next.reason='';}
    if(saveEntry(next)){if(state.auto_next)navigate(1);}
  }
  function downloadFile(name,text,type){
    const blob=new Blob([text],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const stamp=()=>new Date().toISOString().replace(/[:.]/g,'-');
  function backupDownload(){downloadFile('water_review_backup_'+stamp()+'.json',C.backup(dataset,state),'application/json;charset=utf-8');changesSinceBackup=0;$('backupReminder').classList.add('hidden');notice('Backup JSON নামানো হয়েছে। Downloads-এ আছে কি না দেখে নাও।');}
  function csvDownload(){downloadFile('water_reference_labels_'+stamp()+'.csv',C.csvOutput(dataset,state.entries),'text/csv;charset=utf-8');notice('৭২০টি ID মিলিয়ে CSV তৈরি হয়েছে। অনিশ্চিত জায়গাগুলোও রাখা হয়েছে।');}
  async function copyText(text){
    try {if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);else throw Error('fallback');notice('কপি হয়েছে');}
    catch(e){const t=document.createElement('textarea');t.value=text;t.style.position='fixed';t.style.left='-9999px';document.body.append(t);t.select();const ok=document.execCommand('copy');t.remove();notice(ok?'কপি হয়েছে':'কপি হয়নি—দেখানো লেখাটি বেছে Ctrl+C চাপো।',!ok);}
  }
  function pixelKML(){
    const r=current(),[left,bottom,right,top]=r.bounds;
    const coords=`${left},${bottom},0 ${right},${bottom},0 ${right},${top},0 ${left},${top},0 ${left},${bottom},0`;
    const kml=`<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${r.id} ${r.period}</name><Style id="pixel"><LineStyle><color>ff00ddff</color><width>3</width></LineStyle><PolyStyle><fill>0</fill></PolyStyle></Style><Placemark><name>${r.id} — target ${r.period}</name><description>Original sampled JRC pixel footprint. Target month ${r.period}; choose genuinely dated independent imagery. This footprint is not a water label.</description><styleUrl>#pixel</styleUrl><Polygon><outerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>`;
    downloadFile(r.id+'_'+r.period+'_pixel.kml',kml,'application/vnd.google-earth.kml+xml');notice('KML-টি Google Earth Pro-তে খোলো। এটি ওই pixel-এর পুরো সীমানা।');
  }
  function previewImport(incoming){
    pendingImport=incoming;let fresh=0,same=0,conflicts=0,empty=0;
    for(const [id,e] of Object.entries(incoming.entries)){
      if(!C.meaningful(e)){empty++;continue;}
      if(!C.meaningful(get(id)))fresh++;else if(C.comparable(get(id))===C.comparable(e))same++;else conflicts++;
    }
    $('importSummary').textContent=incoming.kind+' · নতুন '+bn(fresh)+' · একই '+bn(same)+' · আলাদা উত্তর '+bn(conflicts)+' · খালি '+bn(empty)+'। আলাদা উত্তরগুলো default-এ বর্তমান অবস্থায় থাকবে।';
    $('replaceConflicts').checked=false;$('importPreview').classList.remove('hidden');$('applyImport').disabled=false;$('importError').textContent='';
  }
  async function readImport(){
    pendingImport=null;$('applyImport').disabled=true;$('importPreview').classList.add('hidden');$('importError').textContent='';
    const f=$('importFile').files[0];if(!f)return;
    try{if(f.size>50000000)throw Error('ফাইল ৫০ MB-এর বেশি।');previewImport(C.importText(await f.text(),f.name,dataset));}
    catch(e){$('importError').textContent='কোনো উত্তর বদলানো হয়নি। '+e.message;}
  }
  function applyImport(){
    if(!pendingImport || !canEdit())return;let applied=0,kept=0;
    for(const [id,e] of Object.entries(pendingImport.entries)){
      if(!C.meaningful(e))continue;
      if(C.meaningful(get(id)) && C.comparable(get(id))!==C.comparable(e) && !$('replaceConflicts').checked){kept++;continue;}
      if(C.comparable(get(id))===C.comparable(e))continue;
      undoStack.push({id,entry:C.entry(get(id))});state.entries[id]=e;applied++;
    }
    undoStack=undoStack.slice(-150);changesSinceBackup+=applied;persist();renderList();renderCurrent();updateStats();$('undoBtn').disabled=!undoStack.length;$('importDialog').close();pendingImport=null;
    notice(bn(applied)+'টি উত্তর যুক্ত হয়েছে; '+bn(kept)+'টি আগের উত্তর রাখা হয়েছে।');
  }
  function legacyImport(){
    try{const raw=JSON.parse(localStorage.getItem('nw-blind-review')||'{}');
      const records=Object.entries(raw).map(([sample_id,e])=>({sample_id,label:e.label ?? '',notes:e.notes ?? ''}));
      previewImport({entries:C.validateRecords(records,dataset),kind:'পুরোনো browser notes — প্রাথমিক'});
    }catch(e){$('importError').textContent='কোনো উত্তর বদলানো হয়নি। '+e.message;}
  }
  function undo(){if(!undoStack.length || !canEdit())return;const last=undoStack.pop();state.active_id=last.id;state.entries[last.id]=last.entry;persist();renderCurrent();renderList();updateStats();$('undoBtn').disabled=!undoStack.length;notice('শেষ পরিবর্তন ফেরানো হয়েছে।');}
  for(const period of [...new Set(rows.map(r=>r.period))]){const o=document.createElement('option');o.value=period;o.textContent=period;$('periodFilter').append(o);}
  for(const id of ['search','periodFilter','statusFilter'])$(id).addEventListener(id==='search'?'input':'change',()=>{renderList();updateNavigation();});
  $('chip').addEventListener('load',()=>{imageOK=true;$('imageWell').classList.remove('broken');document.querySelectorAll('.answer').forEach(b=>b.disabled=false);});
  $('chip').addEventListener('error',()=>{imageOK=false;$('imageWell').classList.add('broken');document.querySelectorAll('.answer').forEach(b=>b.disabled=true);});
  for(const f of ['notes','reason','reference_date','reference_source','evidence_id','reviewer'])$(f).addEventListener(f==='reason'?'change':'input',()=>{
    if(!canEdit())return;const next={...get(),[f]:$(f).value};next.attested=false;
    saveEntry(next);$('attested').checked=next.attested;
  });
  $('attested').addEventListener('change',()=>{
    const next={...get(),attested:$('attested').checked},errors=C.evidenceErrors(next,current());
    if(next.attested&&errors.length){$('attested').checked=false;notice(errors.join(' '),true);updateStatus();return;}
    saveEntry(next);
  });
  document.querySelectorAll('.answer').forEach(b=>b.addEventListener('click',()=>setLabel(b.dataset.value)));
  document.querySelectorAll('.viewmode').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;setView();}));
  $('zoomIn').addEventListener('click',()=>{zoom=Math.min(3,zoom+.5);setView();});$('zoomOut').addEventListener('click',()=>{zoom=Math.max(1,zoom-.5);setView();});
  $('prevBtn').addEventListener('click',()=>navigate(-1));$('nextBtn').addEventListener('click',()=>navigate(1));
  function jump(){const n=Number($('jump').value);if(Number.isInteger(n)&&n>=1&&n<=rows.length)goID(rows[n-1].id);else{notice('১ থেকে '+bn(rows.length)+'-এর মধ্যে নম্বর দাও।',true);$('jump').value=current().index+1;}}
  $('jumpBtn').addEventListener('click',jump);$('jump').addEventListener('keydown',e=>{if(e.key==='Enter')jump();});
  $('copyId').addEventListener('click',()=>copyText(current().id));$('copyCoords').addEventListener('click',()=>copyText(current().latitude.toFixed(9)+', '+current().longitude.toFixed(9)));$('kmlBtn').addEventListener('click',pixelKML);
  $('backupBtn').addEventListener('click',backupDownload);$('reminderBackup').addEventListener('click',backupDownload);$('exportBtn').addEventListener('click',csvDownload);$('undoBtn').addEventListener('click',undo);
  $('autoNext').checked=state.auto_next;$('autoNext').addEventListener('change',()=>{if(!canEdit())return;state.auto_next=$('autoNext').checked;persist();});
  $('clearBtn').addEventListener('click',()=>$('confirmDialog').showModal());$('confirmClear').addEventListener('click',()=>{if(saveEntry(C.blank())){renderCurrent();$('confirmDialog').close();}});
  $('helpBtn').addEventListener('click',()=>$('helpDialog').showModal());$('aboutBtn').addEventListener('click',()=>$('aboutDialog').showModal());
  $('toolsBtn').addEventListener('click',()=>{const open=document.body.classList.toggle('tools-open');$('toolsBtn').setAttribute('aria-expanded',String(open));setView();});
  document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close).close()));
  $('importBtn').addEventListener('click',()=>{
    pendingImport=null;$('importFile').value='';$('importError').textContent='';$('importPreview').classList.add('hidden');$('applyImport').disabled=true;
    try{$('legacyBtn').classList.toggle('hidden',!localStorage.getItem('nw-blind-review'));}catch(e){}
    $('importDialog').showModal();
  });
  $('importFile').addEventListener('change',readImport);$('legacyBtn').addEventListener('click',legacyImport);$('applyImport').addEventListener('click',applyImport);
  document.addEventListener('keydown',e=>{
    if(e.altKey||e.ctrlKey||e.metaKey||e.repeat||document.querySelector('dialog[open]')||e.target.closest('input,textarea,select,[contenteditable=true]'))return;
    if(['0','1','2','ArrowLeft','ArrowRight'].includes(e.key))e.preventDefault();
    if(e.key==='0'||e.key==='1')setLabel(e.key);if(e.key==='2')setLabel('UNCERTAIN');if(e.key==='ArrowLeft')navigate(-1);if(e.key==='ArrowRight')navigate(1);
  });
  $('datasetInfo').textContent='Dataset ID: '+dataset.id+' · '+bn(rows.length)+' points · source metadata ও সব ছবির SHA-256 সংরক্ষিত';
  window.addEventListener('resize',setView);
  renderList();renderCurrent();updateStats();
  // Expose immutable identifiers for software QA, never sampling predictions.
  window.reviewReady={dataset_id:dataset.id,count:rows.length};
})();
