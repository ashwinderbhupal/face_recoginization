"use strict";
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => [...r.querySelectorAll(s)];
const API = "/api";

const fmtTime = ts => new Date(ts*1000).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"});
const fmtAgo  = ts => { const s=Math.max(0,Date.now()/1000-ts);
  if(s<60)return `${s|0}s ago`; if(s<3600)return `${s/60|0}m ago`;
  if(s<86400)return `${s/3600|0}h ago`; return `${s/86400|0}d ago`; };
const snapURL = s => s ? `${API}/snapshots/${encodeURIComponent(s)}` : "";

function toast(msg, isAlert=false){
  const t=$("#toast"); t.textContent=msg; t.className="toast show"+(isAlert?" alert":"");
  clearTimeout(t._t); t._t=setTimeout(()=>t.className="toast",2800);
}
async function getJSON(u){ const r=await fetch(u); return r.json(); }
async function postJSON(u,b){ const r=await fetch(u,{method:"POST",
  headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})}); return r.json(); }
async function del(u){ const r=await fetch(u,{method:"DELETE"}); return r.json(); }

/* ---------------- routing ---------------- */
const TITLES={dashboard:["Dashboard","Live recognition & analytics"],
  people:["People","Manage enrolled identities"],events:["Events","Sighting history"],
  enroll:["Enroll","Add new people"],settings:["Settings","Camera, matching & alerts"]};
function go(sec){
  $$(".nav a").forEach(a=>a.classList.toggle("active",a.dataset.sec===sec));
  $$(".section").forEach(s=>s.classList.toggle("active",s.id==="sec-"+sec));
  $("#pageTitle").textContent=TITLES[sec][0]; $("#pageSub").textContent=TITLES[sec][1];
  if(sec==="people")loadPeople();
  if(sec==="events")loadEvents();
  if(sec==="settings")loadAlertNames();
  if(sec==="dashboard")refreshCharts();
}
$("#nav").onclick=e=>{const a=e.target.closest("a"); if(a)go(a.dataset.sec);};

/* ---------------- source picker ---------------- */
const RKEY="facewatch_rtsp_base";
function buildSource(val){
  if(val==="custom") return $("#customSrc").value.trim();
  if(val==="stream1"||val==="stream2"){
    const base=$("#rtspBase").value.trim(); localStorage.setItem(RKEY,base);
    if(!base){toast("Set the RTSP base in Settings first",true); return null;}
    return `rtsp://${base}:554/${val}`;
  }
  return val; // "0" or ""
}
async function applySource(val){
  const src=buildSource(val); if(src===null)return;
  const r=await postJSON(`${API}/source`,{source:src}); toast(r.message||"");
}
$("#quickApply").onclick=()=>applySource($("#quickSrc").value);
$("#setSrcApply").onclick=()=>applySource($("#setSrc").value);
function syncCustom(){const v=$("#setSrc").value;
  $("#customWrap").style.display=v==="custom"?"block":"none";
  $("#rtspWrap").style.display=(v==="stream1"||v==="stream2")?"block":"none";}
$("#setSrc").onchange=syncCustom;

/* ---------------- matching ---------------- */
$("#thr").oninput=e=>$("#thrVal").textContent=(+e.target.value).toFixed(2);
$("#thr").onchange=e=>postJSON(`${API}/threshold`,{threshold:e.target.value});
$("#recogOn").onchange=e=>postJSON(`${API}/recognize_toggle`,{on:e.target.checked});

/* ---------------- alerts ---------------- */
async function loadAlertNames(){
  const ppl=await getJSON(`${API}/gallery`);
  const sel=$("#alNames"); const chosen=new Set([...sel.selectedOptions].map(o=>o.value));
  sel.innerHTML="";
  ppl.forEach(p=>{const o=document.createElement("option");o.value=p.name;o.textContent=p.name;
    if(chosen.has(p.name))o.selected=true; sel.appendChild(o);});
}
$("#cooldown").oninput=e=>$("#cdVal").textContent=e.target.value;
$("#alApply").onclick=async()=>{
  const names=[...$("#alNames").selectedOptions].map(o=>o.value);
  const r=await postJSON(`${API}/alerts`,{on_unknown:$("#alUnknown").checked,
    names, cooldown:+$("#cooldown").value});
  toast(`Alerts saved (${r.names.length} named)`);
};
$("#clearDb").onclick=async()=>{
  if(!confirm("Clear the entire recognition database? Photos on disk are kept."))return;
  const r=await postJSON(`${API}/db/clear`,{}); toast(r.message); loadPeople();
};

/* ---------------- enroll ---------------- */
$("#capBtn").onclick=async()=>{
  const name=$("#enrollName").value.trim(); if(!name)return toast("Enter a name",true);
  const r=await postJSON(`${API}/enroll/capture`,{name}); toast(r.message,!r.ok);
};
$("#upBtn").onclick=async()=>{
  const name=$("#upName").value.trim(); if(!name)return toast("Enter a name",true);
  const files=$("#upFiles").files; if(!files.length)return toast("Pick images",true);
  const fd=new FormData(); fd.append("name",name);
  for(const f of files)fd.append("images",f);
  const r=await fetch(`${API}/enroll/upload`,{method:"POST",body:fd}).then(x=>x.json());
  toast(r.message,!r.ok);
};

/* ---------------- people gallery ---------------- */
async function loadPeople(){
  const ppl=await getJSON(`${API}/gallery`); const g=$("#peopleGrid"); g.innerHTML="";
  if(!ppl.length){g.innerHTML='<div class="faint">No one enrolled yet. Use the Enroll tab.</div>';return;}
  ppl.forEach(p=>{
    const thumb=p.thumbnails[0]?`background-image:url(${API}/photos/${encodeURIComponent(p.name)}/${encodeURIComponent(p.thumbnails[0])})`:"";
    const el=document.createElement("div"); el.className="person";
    el.innerHTML=`<div class="thumb" style="${thumb}">${p.thumbnails[0]?"":"☻"}</div>
      <div class="info"><b>${p.name}</b><div class="c">${p.photo_count} photo(s) · ${p.db_count} encoding(s)</div></div>`;
    el.onclick=()=>openPerson(p.name); g.appendChild(el);
  });
}

/* ---------------- person modal ---------------- */
let curPerson=null;
async function openPerson(name){
  curPerson=name; $("#pmName").textContent=name;
  const d=await getJSON(`${API}/gallery/${encodeURIComponent(name)}`);
  $("#pmCounts").textContent=`${d.photos.length} photo(s) · ${d.db_count} encoding(s)`;
  const pg=$("#pmPhotos"); pg.innerHTML="";
  d.photos.forEach(fn=>{
    const ph=document.createElement("div"); ph.className="ph";
    ph.innerHTML=`<img src="${API}/photos/${encodeURIComponent(name)}/${encodeURIComponent(fn)}">
      <button title="delete">✕</button>`;
    ph.querySelector("button").onclick=async()=>{
      const r=await del(`${API}/gallery/${encodeURIComponent(name)}/photo/${encodeURIComponent(fn)}`);
      if(r.ok){toast("Photo deleted");openPerson(name);} };
    pg.appendChild(ph);
  });
  $("#personModal").classList.add("show");
}
$("#pmClose").onclick=()=>$("#personModal").classList.remove("show");
$("#personModal").onclick=e=>{if(e.target.id==="personModal")$("#personModal").classList.remove("show");};
$("#pmUpload").onclick=async()=>{
  const files=$("#pmFiles").files; if(!files.length)return toast("Pick images",true);
  const fd=new FormData(); for(const f of files)fd.append("images",f);
  const r=await fetch(`${API}/gallery/${encodeURIComponent(curPerson)}/upload`,{method:"POST",body:fd}).then(x=>x.json());
  toast(r.message,!r.ok); openPerson(curPerson);
};
$("#pmRename").onclick=async()=>{
  const nn=prompt("Rename person to:",curPerson); if(!nn||nn===curPerson)return;
  const r=await postJSON(`${API}/gallery/${encodeURIComponent(curPerson)}/rename`,{new:nn});
  toast(r.message,!r.ok); if(r.ok){$("#personModal").classList.remove("show");loadPeople();}
};
$("#pmDelete").onclick=async()=>{
  if(!confirm(`Delete ${curPerson} (photos + encodings)?`))return;
  const r=await del(`${API}/gallery/${encodeURIComponent(curPerson)}`);
  toast(r.message,!r.ok); $("#personModal").classList.remove("show"); loadPeople();
};

/* ---------------- events history ---------------- */
async function loadEvents(){
  const ev=await getJSON(`${API}/events/recent?limit=200`); const b=$("#eventsBody"); b.innerHTML="";
  if(!ev.length){b.innerHTML='<tr><td colspan="6" class="faint">No sightings recorded yet.</td></tr>';return;}
  ev.forEach(e=>{
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${e.snapshot?`<img class="snap" src="${snapURL(e.snapshot)}">`:""}</td>
      <td><b>${e.name}</b></td><td>${e.confidence}%</td>
      <td>${badge(e)}</td><td class="muted">${e.source||"—"}</td>
      <td class="muted" title="${fmtTime(e.ts)}">${fmtAgo(e.ts)}</td>`;
    b.appendChild(tr);
  });
}
function badge(e){
  if(e.alert)return '<span class="badge alert">Alert</span>';
  return e.known?'<span class="badge known">Known</span>':'<span class="badge unknown">Unknown</span>';
}
$("#clearEvents").onclick=async()=>{
  if(!confirm("Clear all sighting history?"))return;
  await postJSON(`${API}/events/clear`,{}); loadEvents(); refreshCharts(); toast("History cleared");
};

/* ---------------- live feed (SSE) ---------------- */
function feedRow(e){
  const row=document.createElement("div"); row.className="row"+(e.alert?" alert":"");
  row.innerHTML=`${e.snapshot?`<img src="${snapURL(e.snapshot)}">`:'<div style="width:42px;height:42px"></div>'}
    <div><div class="nm">${e.name}</div><div class="meta">${e.confidence}% · ${fmtTime(e.ts)}</div></div>
    <div class="spacer"></div>${badge(e)}`;
  return row;
}
function pushFeed(e){
  const f=$("#liveFeed"); if(f.querySelector(".faint"))f.innerHTML="";
  f.prepend(feedRow(e)); while(f.children.length>40)f.removeChild(f.lastChild);
  if(e.alert)showAlert(e);
}
function showAlert(e){
  const b=$("#alertBanner");
  $("#alertImg").src=snapURL(e.snapshot)||""; $("#alertImg").style.display=e.snapshot?"block":"none";
  $("#alertText").textContent=e.known?`Alert: ${e.name} seen`:"Alert: Unknown face detected";
  $("#alertSub").textContent=`${e.confidence}% · ${fmtTime(e.ts)} · ${e.source||""}`;
  b.classList.add("show"); toast($("#alertText").textContent,true);
}
function connectSSE(){
  const es=new EventSource(`${API}/events/stream`);
  es.onmessage=ev=>{ try{const e=JSON.parse(ev.data); pushFeed(e);
    clearTimeout(window._chartT); window._chartT=setTimeout(refreshCharts,1200);}catch(_){} };
  es.onerror=()=>{/* browser auto-reconnects */};
}

/* ---------------- charts ---------------- */
let chT=null, chP=null;
function baseOpts(){return {responsive:true,plugins:{legend:{display:false}},
  scales:{x:{ticks:{color:"#98a2b6"},grid:{color:"#262c3b"}},
          y:{ticks:{color:"#98a2b6"},grid:{color:"#262c3b"},beginAtZero:true}}};}
async function refreshCharts(){
  if(typeof Chart==="undefined")return;
  const st=await getJSON(`${API}/events/stats?hours=24`);
  $("#kToday").textContent=st.total; $("#kUnknown").textContent=st.unknown;
  const tl=st.timeline||[];
  const labels=tl.map(t=>`${(t.hour%24).toString().padStart(2,"0")}:00`);
  const data=tl.map(t=>t.count);
  if(!chT)chT=new Chart($("#chartTimeline"),{type:"line",
    data:{labels,datasets:[{data,borderColor:"#5b8cff",backgroundColor:"rgba(91,140,255,.15)",
      fill:true,tension:.35,pointRadius:2}]},options:baseOpts()});
  else{chT.data.labels=labels;chT.data.datasets[0].data=data;chT.update();}
  const pp=(st.per_person||[]).slice(0,8);
  const pl=pp.map(p=>p.name), pd=pp.map(p=>p.c);
  if(!chP)chP=new Chart($("#chartPeople"),{type:"bar",
    data:{labels:pl,datasets:[{data:pd,backgroundColor:"#7c5bff",borderRadius:6}]},options:baseOpts()});
  else{chP.data.labels=pl;chP.data.datasets[0].data=pd;chP.update();}
}

/* ---------------- status polling ---------------- */
let settingsLoaded=false;
async function poll(){
  try{
    const s=await getJSON(`${API}/status`);
    $("#topFps").textContent=s.fps; $("#vFps").textContent=s.fps+" FPS";
    $("#vFaces").textContent=s.faces+" faces";
    $("#kFaces").textContent=s.faces; $("#kKnown").textContent=s.known;
    const src=s.source||"no source";
    $("#topSrc").textContent=src; $("#sideSrc").textContent=src;
    $("#topDot").classList.toggle("live",s.live);
    $("#sideDot").classList.toggle("live",s.live);
    $("#sideStatus").textContent=s.live?"live":"offline";
    if(!settingsLoaded){
      $("#thr").value=s.threshold; $("#thrVal").textContent=(+s.threshold).toFixed(2);
      $("#recogOn").checked=s.recognize_on;
      $("#alUnknown").checked=s.alerts.on_unknown;
      $("#cooldown").value=s.alerts.cooldown; $("#cdVal").textContent=s.alerts.cooldown;
      settingsLoaded=true;
    }
    if(s.active_alert)showAlert(s.active_alert);
  }catch(_){}
}

/* ---------------- boot ---------------- */
$("#rtspBase").value=localStorage.getItem(RKEY)||"";
syncCustom();
connectSSE();
poll(); setInterval(poll,1500);
refreshCharts(); setInterval(refreshCharts,30000);
