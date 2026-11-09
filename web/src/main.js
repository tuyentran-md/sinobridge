import '@fontsource/be-vietnam-pro/400.css';
import '@fontsource/be-vietnam-pro/500.css';
import '@fontsource/be-vietnam-pro/600.css';
import '@fontsource/be-vietnam-pro/700.css';
import './style.css';
import {extractFile,syntheticSample} from './parse.js';
import {listProjects,loadProject,saveProject,saveCheckpoints} from './database.js';
import {exportProject} from './export.js';
import {PROVIDERS,KeyError,translateProject,listModels,preferredModel,bridge,bridgeInfo} from './engine.js';

const el=id=>document.getElementById(id);
const PAGE=200;
const LIB_SHORT=4;
const state={project:null,projects:[],working:false,controller:null,gpu:null,bridge:null,libraryOpen:false,importing:false,home:true,page:0,inlay:null,busy:new Set(),polish:new Set()};
const prefs={get:k=>{try{return localStorage.getItem('sb-'+k);}catch{return null;}},set:(k,v)=>{try{v==null?localStorage.removeItem('sb-'+k):localStorage.setItem('sb-'+k,v);}catch{}}};
const memoryKeys={};

function status(message,type=''){el('status').textContent=message;el('status').className='status '+type;}
const count=p=>p.done||0;
const target=()=>document.querySelector('input[name=target]:checked').value;
function setTarget(v){const r=document.querySelector('input[name=target][value="'+v+'"]');if(r)r.checked=true;}
const provider=()=>el('provider').value;
const apiKey=()=>el('api-key').value.trim();
const needsKey=()=>{const p=PROVIDERS[provider()];return !p.local&&!p.bridge;};
const bridgeReady=p=>Boolean(state.bridge&&state.bridge.accounts&&state.bridge.accounts[p.bridge]);

/* ---------- rendering ---------- */
function renderInlay(p){
  const box=el('inlay');
  if(!p){state.inlay=null;box.replaceChildren();box.setAttribute('aria-valuenow','0');return;}
  const n=p.segments.length;
  if(state.inlay?.p!==p){
    const per=Math.ceil(n/Math.min(n,224)),counts=[],sizes=[];
    p.segments.forEach((s,i)=>{const t=Math.floor(i/per);sizes[t]=(sizes[t]||0)+1;counts[t]=(counts[t]||0)+(s.translation?1:0);});
    state.inlay={p,per,counts,sizes};
    box.replaceChildren(...sizes.map(()=>document.createElement('i')));
  }
  const {per,counts,sizes}=state.inlay;
  const working=new Set([...state.busy].map(i=>Math.floor(i/per)));
  [...box.children].forEach((tile,t)=>{tile.className=working.has(t)?'work':counts[t]===sizes[t]?'done':counts[t]?'part':'';});
  box.setAttribute('aria-valuenow',String(Math.round(100*count(p)/n)));
}
function checkpointNote(){
  const p=state.project,box=el('checkpoint');
  box.hidden=!p;
  if(p)box.textContent=p.savedAt?'Đã lưu '+count(p)+'/'+p.segments.length+' đoạn trên máy · '+new Date(p.savedAt).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):count(p)?'Đã lưu '+count(p)+'/'+p.segments.length+' đoạn trên trình duyệt này.':'Đã lưu tài liệu trên trình duyệt này. Chưa có đoạn dịch.';
}

function rowFor(s,i){
  const row=document.createElement('div');
  row.className='row'+(s.heading?' heading':'')+(s.translation?' done':'')+(state.busy.has(i)?' work':'')+(state.polish.has(i)?' polish':'');
  row.dataset.i=i;
  const zh=document.createElement('div');zh.className='zh';zh.lang='zh';zh.textContent=s.source.replace(/^#{1,6}\s+/,'');
  const spine=document.createElement('div');spine.className='spine';spine.setAttribute('aria-hidden','true');
  const tr=document.createElement('div');tr.className='tr'+(s.translation?'':' pending');
  tr.textContent=s.translation?s.translation.replace(/^#{1,6}\s+/,''):state.busy.has(i)?'Đang dịch…':'Chưa dịch';
  row.append(zh,spine,tr);
  return row;
}
function renderRows(){
  const p=state.project,box=el('preview');
  if(!p||state.home){box.replaceChildren();return;}
  const pages=Math.ceil(p.segments.length/PAGE);
  state.page=Math.max(0,Math.min(state.page,pages-1));
  const start=state.page*PAGE,frag=document.createDocumentFragment();
  p.segments.slice(start,start+PAGE).forEach((s,i)=>frag.append(rowFor(s,start+i)));
  box.replaceChildren(frag);
  el('page-number').value=state.page+1;el('page-number').max=pages;
  el('page-count').textContent='/ '+pages;
  el('reader-range').textContent='Đoạn '+(start+1)+'–'+Math.min(start+PAGE,p.segments.length)+' / '+p.segments.length;
  el('page-prev').disabled=state.page===0;
  el('show-more').disabled=state.page===pages-1;
}
function readingPage(page){state.page=Math.trunc(page);renderRows();el('reader').scrollTop=0;el('pane').scrollIntoView({block:'start'});}
function goHome(event){
  event?.preventDefault();
  state.home=true;
  if(!state.working)state.project=null;
  view();el('reader').scrollTop=0;window.scrollTo({top:0});
  if(!state.working)status('Chọn tài liệu trong thư viện để đọc hoặc dịch tiếp; hoặc thêm file mới.');
}

function updateRow(i){
  const old=el('preview').querySelector('.row[data-i="'+i+'"]');
  if(old)old.replaceWith(rowFor(state.project.segments[i],i));
}
function renderLibrary(){
  const lib=el('library'),p=state.project;
  const all=state.projects.slice().sort((a,b)=>b.created-a.created);
  const more=el('library-more');
  more.hidden=all.length<=LIB_SHORT;
  more.textContent=state.libraryOpen?'Thu gọn':'Xem tất cả ('+all.length+')';
  lib.replaceChildren();
  if(!all.length){const e=document.createElement('p');e.className='library-empty';e.textContent='Chưa có tài liệu nào.';lib.append(e);return;}
  for(const project of state.libraryOpen?all:all.slice(0,LIB_SHORT)){
    const item=document.createElement('div');item.className='library-item'+(p&&p.id===project.id?' active':'');
    item.setAttribute('role','button');item.tabIndex=0;
    const name=document.createElement('strong');name.textContent=project.name;
    const detail=document.createElement('small');detail.textContent=count(project)+'/'+project.total+' · '+(project.target==='en'?'EN':'VI');
    item.append(name,detail);
    const open=async()=>{
      if(state.working&&state.project?.id!==project.id)return;
      try{
        const p=state.project?.id===project.id?state.project:await loadProject(project.id);
        if(!p)throw new Error('Không tìm thấy tài liệu đã lưu.');
        state.project=p;state.home=false;state.page=0;setTarget(p.target);view();
        if(!state.working)status('Đã mở '+p.name+' · '+count(p)+'/'+p.segments.length+' đoạn đã dịch.','ok');
      }catch(e){status('Không mở được tài liệu: '+e.message,'error');}
    };
    item.addEventListener('click',open);
    item.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
    lib.append(item);
  }
}
function controls(){
  const p=state.project,working=state.working||state.importing,done=p?count(p):0,complete=p&&done===p.segments.length;
  const prov=PROVIDERS[provider()];
  const ready=prov.bridge?bridgeReady(prov):prov.local?state.gpu===true:Boolean(apiKey());
  el('start').disabled=!p||working||complete||!ready||!el('model').value.trim();
  el('start').textContent=working?'Đang dịch…':complete?'Đã dịch xong':done?'Dịch tiếp':'Bắt đầu dịch';
  el('stop').hidden=!state.working;
  for(const b of document.querySelectorAll('[data-export]'))b.disabled=!p||!done;
  for(const c of [el('provider'),el('api-key'),el('model'),el('bridge-port'),el('bridge-check'),...document.querySelectorAll('input[name=target]')])c.disabled=working;
  el('pick').disabled=working;
}
function view(){
  const p=state.project;
  el('current').hidden=!p;
  if(p)el('current').textContent=p.name+' · '+p.segments.length+' đoạn';
  el('welcome').hidden=!state.home;
  el('pane').hidden=state.home||!p;
  if(p){
    el('done-count').textContent=count(p)+'/'+p.segments.length;
    el('target-label').textContent=p.target==='en'?'Bản dịch · English':'Bản dịch · Tiếng Việt';
  }
  renderRows();renderInlay(p);renderLibrary();controls();checkpointNote();
}

/* ---------- model settings ---------- */
function storedKey(name){return memoryKeys[name]??prefs.get('key-'+name)??'';}
async function refreshModels(){
  const name=provider(),p=PROVIDERS[name],list=el('model-list');
  const fill=ids=>{list.replaceChildren(...ids.map(id=>{const o=document.createElement('option');o.value=id;return o;}));};
  fill(p.models);
  if(p.local||(p.bridge?!bridgeReady(p):!apiKey()))return;
  try{
    const ids=await listModels(name,apiKey());
    if(provider()!==name||!ids.length)return;
    fill(ids);
    const current=el('model').value.trim();
    if(!current||!ids.includes(current)){el('model').value=preferredModel(name,ids);prefs.set('model-'+name,el('model').value);}
    note();
  }catch(e){if(e instanceof KeyError&&provider()===name)note(e.message,true);}
}
function note(message,warn=false){
  const p=PROVIDERS[provider()],box=el('model-note');
  box.className='note'+(warn?' warn':'');
  if(message){box.textContent=message;return;}
  if(p.local){
    box.textContent=state.gpu===true?'Model tải về máy ở lần đầu (vài trăm MB đến vài GB). Dịch chậm và kém hơn model cloud.':
      state.gpu===false?'Trình duyệt này không chạy được model trên máy (thiếu WebGPU). Hãy dùng Chrome hoặc Edge mới, hoặc chọn Gemini.':'Đang kiểm tra trình duyệt…';
    box.className='note'+(state.gpu===false?' warn':'');
  }else if(p.bridge){
    const b=state.bridge;
    const warn=!b||b.refused||!bridgeReady(p);
    box.className='note'+(warn?' warn':' ok');
    box.textContent=b===null?'Chưa thấy app SinoBridge trên máy này. Mở app (Start SinoBridge.command) rồi bấm Kiểm tra lại.':
      b==='checking'?'Đang tìm app SinoBridge trên máy…':
      b.refused?'App trên máy từ chối trang này. Hãy cập nhật app SinoBridge.':
      !bridgeReady(p)?'App đã mở nhưng máy chưa cài '+p.tool+'. Cài và đăng nhập '+p.tool+' một lần, rồi bấm Kiểm tra lại.':
      'Đã kết nối app trên máy. Dịch bằng tài khoản '+p.owner+' của bạn qua '+p.tool+', không cần key.'+(p.bridge==='chatgpt'?' Để "default" nếu muốn dùng model mặc định của tài khoản.':'');
  }else box.textContent='Key chỉ gửi thẳng tới '+p.owner+', không qua máy chủ nào khác.';
}
function applyProvider(){
  const name=provider(),p=PROVIDERS[name];
  prefs.set('provider',name);
  el('key-block').hidden=Boolean(p.local||p.bridge);
  el('account-block').hidden=!p.bridge;
  if(!p.local&&!p.bridge){
    el('key-link').href=p.keyUrl;
    el('key-link').firstChild.textContent=p.keyLabel;
    el('api-key').value=storedKey(name);
    el('remember').checked=Boolean(prefs.get('key-'+name));
  }
  el('model').value=prefs.get('model-'+name)||p.models[0];
  note();controls();refreshModels();
  if(p.local&&state.gpu===null)testGPU();
  if(p.bridge)checkBridge();
}
async function checkBridge(){
  state.bridge='checking';note();controls();
  const info=await bridgeInfo();
  state.bridge=info&&(info.refused||info.app==='sinobridge')?info:null;
  note();controls();refreshModels();
}
async function testGPU(){
  try{state.gpu=Boolean(navigator.gpu&&await navigator.gpu.requestAdapter());}catch{state.gpu=false;}
  note();controls();
}

/* ---------- actions ---------- */
function updateLibrary(info){
  const idx=state.projects.findIndex(x=>x.id===info.id);
  if(idx<0)state.projects.push(info);else state.projects[idx]=info;
}
async function updateProject(p){
  const info=await saveProject(p);
  state.project=p;state.home=false;state.page=0;
  updateLibrary(info);
}

async function acceptFile(file){
  if(!file||state.working||state.importing)return;
  state.importing=true;controls();
  try{
    status('Đang đọc tài liệu…');
    await new Promise(resolve=>setTimeout(resolve,0));
    const project=await extractFile(file,text=>status(text));
    project.target=target();
    state.page=0;
    await updateProject(project);view();
    status('Đã thêm '+project.segments.length+' đoạn. '+(el('start').disabled&&needsKey()&&!apiKey()?'Dán API key rồi bấm Bắt đầu dịch.':'Bấm Bắt đầu dịch khi sẵn sàng.'),'ok');
  }catch(e){status('Không mở được file: '+e.message,'error');}
  finally{state.importing=false;controls();}
}
async function translate(){
  const p=state.project;
  if(!p||state.working)return;
  const name=provider(),model=el('model').value.trim();
  prefs.set('model-'+name,model);
  state.working=true;state.controller=new AbortController();controls();
  const start=count(p),t0=Date.now();
  let checkpointing=Promise.resolve();
  const tick=()=>{
    const done=count(p),rate=(done-start)/Math.max(1,(Date.now()-t0)/1000),left=p.segments.length-done;
    const eta=rate>0&&done-start>=2?' · còn khoảng '+Math.max(1,Math.round(left/rate/60))+' phút':'';
    status('Đang dịch '+done+'/'+p.segments.length+' đoạn'+eta);
    el('done-count').textContent=done+'/'+p.segments.length;
  };
  status(PROVIDERS[name].local?'Đang chuẩn bị model trên máy…':'Đang gửi tới '+PROVIDERS[name].label+'…');
  try{
    await translateProject({
      project:p,provider:name,key:apiKey(),model,signal:state.controller.signal,
      onStatus:(text,fraction)=>status(text+(fraction?' '+Math.round(fraction*100)+'%':'')),
      onWorking:(indices,on)=>{
        indices.forEach(i=>on?state.busy.add(i):state.busy.delete(i));
        indices.forEach(updateRow);renderInlay(p);if(!on)tick();
      },
      onCheckpoint:indices=>{
        checkpointing=checkpointing.then(async()=>{
          const info=await saveCheckpoints(p,indices,count(p)+indices.length);
          p.done=info.done;p.savedAt=info.savedAt;updateLibrary(info);checkpointNote();
        });
        return checkpointing.catch(()=>{
          indices.forEach(i=>{p.segments[i].translation='';p.segments[i].status='pending';});
          throw new Error('Không lưu được checkpoint. Đã dừng dịch; hãy kiểm tra dung lượng hoặc quyền lưu của trình duyệt.');
        });
      },
      onDone:i=>{
        if(state.inlay?.p===p)state.inlay.counts[Math.floor(i/state.inlay.per)]++;
        state.polish.add(i);updateRow(i);state.polish.delete(i);
      },
    });
    status(state.controller.signal.aborted?'Đã dừng ở '+count(p)+'/'+p.segments.length+' đoạn. Bấm Dịch tiếp bất cứ lúc nào.':
      'Xong '+count(p)+'/'+p.segments.length+' đoạn. Tải EPUB hoặc Word ở cột bên trái.','ok');
  }catch(e){
    const msg=e?.name==='AbortError'?'Đã dừng.':(e?.message||String(e));
    status(msg+(e instanceof KeyError?'':' Các đoạn đã xong vẫn được lưu.'),'error');
    if(e instanceof KeyError)note(e.message,true);
  }finally{
    state.busy.clear();state.working=false;state.controller=null;
    view();
  }
}

function setupDrop(){
  const picker=el('file'),open=()=>{if(!state.working&&!state.importing)picker.click();};
  el('pick').addEventListener('click',open);
  const drop=el('drop');
  drop.addEventListener('click',e=>{if(!e.target.closest('#try-sample'))open();});
  drop.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
  picker.addEventListener('change',e=>{acceptFile(e.target.files?.[0]);picker.value='';});
  let depth=0;
  window.addEventListener('dragenter',e=>{if(e.dataTransfer?.types?.includes('Files')){depth++;document.body.classList.add('dragging');}});
  window.addEventListener('dragleave',()=>{depth=Math.max(0,depth-1);if(!depth)document.body.classList.remove('dragging');});
  window.addEventListener('dragover',e=>e.preventDefault());
  window.addEventListener('drop',e=>{e.preventDefault();depth=0;document.body.classList.remove('dragging');acceptFile(e.dataTransfer?.files?.[0]);});
}
async function init(){
  setupDrop();
  el('home').addEventListener('click',goHome);
  el('back-home').addEventListener('click',goHome);
  el('reading-mode').value=['bilingual','translation','original'].includes(prefs.get('reading-mode'))?prefs.get('reading-mode'):'bilingual';
  const readingMode=()=>{el('pane').dataset.mode=el('reading-mode').value;prefs.set('reading-mode',el('reading-mode').value);};
  el('reading-mode').addEventListener('change',readingMode);readingMode();
  el('page-prev').addEventListener('click',()=>readingPage(state.page-1));
  el('page-number').addEventListener('change',()=>readingPage((Number(el('page-number').value)||1)-1));
  const themeIcon=()=>el('theme').querySelector('use').setAttribute('href',document.documentElement.dataset.theme==='dark'?'#i-sun':'#i-moon');
  themeIcon();
  el('theme').addEventListener('click',()=>{const dark=document.documentElement.dataset.theme!=='dark';if(dark)document.documentElement.dataset.theme='dark';else delete document.documentElement.dataset.theme;prefs.set('theme',dark?'dark':null);themeIcon();});
  el('try-sample').addEventListener('click',async e=>{
    e.stopPropagation();
    if(state.working||state.importing)return;
    state.page=0;
    try{
      await updateProject(syntheticSample(target()));view();
      status('Đã thêm đoạn mẫu. '+(!needsKey()||apiKey()?'Bấm Bắt đầu dịch để thử.':'Dán API key rồi bấm Bắt đầu dịch.'),'ok');
    }catch(e){status('Không lưu được tài liệu: '+e.message,'error');}
  });
  for(const radio of document.querySelectorAll('input[name=target]'))radio.addEventListener('change',async()=>{
    const p=state.project;
    if(p&&count(p)){setTarget(p.target);status('Tài liệu này đã dịch một phần. Muốn đổi ngôn ngữ, hãy thêm lại file.','error');return;}
    if(p){const previous=p.target;p.target=target();try{await updateProject(p);view();}catch(e){p.target=previous;setTarget(previous);status('Không lưu được thay đổi: '+e.message,'error');}}
  });
  el('provider').addEventListener('change',applyProvider);
  const port=Number(prefs.get('bridge-port'));
  if(port>=1024&&port<=65535)bridge.port=port;
  el('bridge-port').value=bridge.port;
  el('bridge-port').addEventListener('change',()=>{const v=Number(el('bridge-port').value);if(v>=1024&&v<=65535){bridge.port=v;prefs.set('bridge-port',String(v));}else el('bridge-port').value=bridge.port;checkBridge();});
  el('bridge-check').addEventListener('click',checkBridge);
  let typing;
  el('api-key').addEventListener('input',()=>{
    const name=provider();memoryKeys[name]=apiKey();
    if(el('remember').checked)prefs.set('key-'+name,apiKey()||null);
    note();controls();clearTimeout(typing);typing=setTimeout(refreshModels,600);
  });
  el('remember').addEventListener('change',()=>prefs.set('key-'+provider(),el('remember').checked&&apiKey()?apiKey():null));
  el('model').addEventListener('input',controls);
  el('model').addEventListener('change',()=>prefs.set('model-'+provider(),el('model').value.trim()));
  el('start').addEventListener('click',translate);
  el('stop').addEventListener('click',()=>{state.controller?.abort();el('stop').hidden=true;status('Đang dừng…');});
  el('library-more').addEventListener('click',()=>{state.libraryOpen=!state.libraryOpen;renderLibrary();});
  el('show-more').addEventListener('click',()=>readingPage(state.page+1));
  document.querySelectorAll('[data-export]').forEach(btn=>btn.addEventListener('click',async()=>{
    if(!state.project)return;
    try{btn.disabled=true;await exportProject(state.project,btn.dataset.export,el('bilingual').checked);status('Đã tải file '+btn.dataset.export.toUpperCase()+'.','ok');}
    catch(e){status('Không tạo được file: '+e.message,'error');}
    finally{controls();}
  }));
  const saved=prefs.get('provider');
  if(saved&&PROVIDERS[saved])el('provider').value=saved;
  try{
    state.projects=await listProjects();
  }catch(e){status('Không đọc được thư viện của trình duyệt: '+e.message,'error');}
  applyProvider();
  view();
  const p=state.project;
  if(p){const d=count(p);status(d===p.segments.length?'Đã dịch xong '+d+'/'+d+' đoạn.':d?'Đã dịch '+d+'/'+p.segments.length+' đoạn. Bấm Dịch tiếp để làm nốt.':'Sẵn sàng dịch '+p.segments.length+' đoạn.',d?'ok':'');}
}
init();
