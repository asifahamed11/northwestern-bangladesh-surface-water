/* Interpretation aids only. Colours are never automatic reference labels. */
(function () {
  'use strict';
  const box=document.getElementById('imageHelp');
  const help={
    rgb:{title:'স্বাভাবিক রং · উপরে বামে',points:[
      'হলুদ ঘরের পুরো জায়গাটি দেখো। বাইরের নদী বা পুকুর দেখে উত্তর দেবে না।',
      'গাছ, ফসল, বাড়ি বা শুকনা জমি স্পষ্ট হলে পানি নেই-এর পক্ষে সহায়ক প্রমাণ।',
      'শুধু গাঢ় রং মানেই পানি নয়। অন্য ছবির সঙ্গে মিলিয়ে দেখো।'
    ],foot:'মিশ্র বা অস্পষ্ট হলে 2 — বোঝা যাচ্ছে না।'},
    infrared:{title:'ইনফ্রারেড · উপরে ডানে',points:[
      'নীলচে বা কালো অংশ খোলা পানি হওয়ার ইঙ্গিত দিতে পারে।',
      'লাল সাধারণত গাছ/ফসল; ধূসর বা বাদামি অংশ জমি/বসতি হতে পারে।',
      'রং একাই নিশ্চিত উত্তর নয়। হলুদ ঘরটি স্বাভাবিক রং ও অন্য ছবিতে মিলিয়ে দেখো।'
    ],foot:'সংশয় হলে 2। স্বাধীন dated evidence ছাড়া VERIFIED নয়।'},
    mndwi:{title:'MNDWI · নিচে বামে',points:[
      'এই ছবিতে নীল = বেশি MNDWI; খোলা পানির ইঙ্গিত দিতে পারে।',
      'লাল/কমলা = কম MNDWI; পানি না থাকার পক্ষে সহায়ক ইঙ্গিত।',
      'সাদা/ফ্যাকাসে = সূচক প্রায় শূন্য অথবা তথ্য নেই। এটি নিশ্চিত পানির তীররেখা নয়।',
      'হলুদ ঘরে নীল-লাল মিশ্র, মেঘ বা অস্পষ্ট অংশ থাকলে 2 দাও।'
    ],foot:'শুধু নীল দেখেই 1 নয়; অন্য ছবি ও সময় মিলিয়ে দেখো।'},
    radar:{title:'Sentinel-1 VV · নিচে ডানে',points:[
      'কালো/গাঢ় ধূসর = কম radar backscatter; শান্ত খোলা পানি হতে পারে।',
      'ছায়া, মসৃণ জমি বা রাস্তাও কালো হতে পারে। তাই কালো মানেই পানি নয়।',
      'ঢেউয়ের কারণে পানিও উজ্জ্বল হতে পারে। অন্য ছবির সঙ্গে মিলিয়ে দেখো।'
    ],foot:'ছবিগুলো না মিললে বা সংশয় থাকলে 2 দাও।'}
  };
  let active=null, hideTimer=null, lastTouch=0;
  function hide(){clearTimeout(hideTimer);box.classList.add('hidden');if(active)active.setAttribute('aria-expanded','false');active=null;}
  function position(x,y){
    const w=box.offsetWidth,h=box.offsetHeight;
    let left=x+18,top=y+18;
    if(left+w>window.innerWidth-10)left=x-w-18;
    if(top+h>window.innerHeight-10)top=window.innerHeight-h-10;
    box.style.left=Math.max(10,Math.min(left,window.innerWidth-w-10))+'px';
    box.style.top=Math.max(10,top)+'px';
  }
  function show(zone,x,y){
    clearTimeout(hideTimer);const data=help[zone.dataset.help];if(!data)return;
    if(active && active!==zone)active.setAttribute('aria-expanded','false');
    active=zone;zone.setAttribute('aria-expanded','true');
    document.getElementById('imageHelpTitle').textContent=data.title;
    const list=document.getElementById('imageHelpPoints');list.replaceChildren();
    for(const point of data.points){const li=document.createElement('li');li.textContent=point;list.append(li);}
    document.getElementById('imageHelpFoot').textContent=data.foot;
    box.classList.remove('hidden');position(x,y);
  }
  function laterHide(){clearTimeout(hideTimer);hideTimer=setTimeout(()=>{if(!box.matches(':hover'))hide();},180);}
  document.querySelectorAll('.help-zone').forEach(zone=>{
    zone.addEventListener('pointerenter',e=>{if(e.pointerType==='mouse')show(zone,e.clientX,e.clientY);});
    zone.addEventListener('pointermove',e=>{if(e.pointerType==='mouse' && active===zone)position(e.clientX,e.clientY);});
    zone.addEventListener('pointerleave',e=>{if(e.pointerType==='mouse')laterHide();});
    zone.addEventListener('pointerup',e=>{if(e.pointerType!=='mouse'){lastTouch=Date.now();if(active===zone)hide();else show(zone,e.clientX,e.clientY);}});
    zone.addEventListener('focus',()=>{if(Date.now()-lastTouch>800 && zone.matches(':focus-visible')){const r=zone.getBoundingClientRect();show(zone,r.left+r.width/2,r.top+r.height/2);}});
    zone.addEventListener('blur',laterHide);
    zone.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();const r=zone.getBoundingClientRect();if(active===zone)hide();else show(zone,r.left+r.width/2,r.top+r.height/2);}});
  });
  box.addEventListener('pointerenter',()=>clearTimeout(hideTimer));box.addEventListener('pointerleave',laterHide);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});
  document.addEventListener('pointerdown',e=>{if(!e.target.closest('.help-zone,#imageHelp'))hide();});
  window.addEventListener('resize',hide);
  // A browser may scroll a lower image into view just after pointerenter.
  // Do not erase that newly opened help; leave, outside tap and Esc dismiss it.
  document.addEventListener('pointercancel',hide);
  window.imageHelpUI={hide};
})();
