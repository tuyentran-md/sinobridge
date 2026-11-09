const DATABASE='sinobridge-browser-v1';
const VERSION=2;

const summary=p=>({id:p.id,name:p.name,kind:p.kind,target:p.target,created:p.created,
  total:p.segments.length,done:p.segments.filter(s=>Boolean(s.translation)).length,savedAt:p.savedAt||null});

function open(){
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open(DATABASE,VERSION);
    request.onupgradeneeded=()=>{
      const db=request.result,tx=request.transaction;
      if(!db.objectStoreNames.contains('projects'))db.createObjectStore('projects',{keyPath:'id'});
      db.createObjectStore('library',{keyPath:'id'});
      db.createObjectStore('checkpoints',{keyPath:['projectId','index']}).createIndex('project','projectId');
      // Retain existing books and translations; only build a lightweight library index.
      tx.objectStore('projects').openCursor().onsuccess=event=>{
        const cursor=event.target.result;
        if(cursor){tx.objectStore('library').put(summary(cursor.value));cursor.continue();}
      };
    };
    request.onsuccess=()=>{request.result.onversionchange=()=>request.result.close();resolve(request.result);};
    request.onerror=()=>reject(request.error);
    request.onblocked=()=>reject(new Error('Hãy đóng các tab SinoBridge cũ rồi mở lại để cập nhật bộ nhớ.'));
  });
}
async function operation(stores,mode,fn){
  const db=await open();
  try{
    return await new Promise((resolve,reject)=>{
      const tx=db.transaction(stores,mode);
      let result;
      tx.oncomplete=()=>resolve(result);
      tx.onerror=()=>reject(tx.error);
      tx.onabort=()=>reject(tx.error||new Error('Không ghi được bộ nhớ trình duyệt.'));
      try{result=fn(tx);}catch(error){tx.abort();reject(error);}
    });
  }finally{db.close();}
}
export async function saveProject(p){
  const info=summary(p);
  await operation(['projects','library'],'readwrite',tx=>{
    tx.objectStore('projects').put(p);tx.objectStore('library').put(info);
  });
  Object.assign(p,{done:info.done,total:info.total});
  return info;
}
export async function listProjects(){
  const result=await operation(['library'],'readonly',tx=>{
    const result={items:[]};
    tx.objectStore('library').getAll().onsuccess=e=>{result.items=e.target.result;};
    return result;
  });
  return result.items;
}
export async function loadProject(id){
  const result=await operation(['projects','checkpoints'],'readonly',tx=>{
    const result={project:null,checkpoints:[]};
    tx.objectStore('projects').get(id).onsuccess=e=>{result.project=e.target.result;};
    tx.objectStore('checkpoints').index('project').getAll(id).onsuccess=e=>{result.checkpoints=e.target.result;};
    return result;
  });
  const p=result.project;
  if(!p)return null;
  for(const checkpoint of result.checkpoints){
    const segment=p.segments[checkpoint.index];
    if(segment)Object.assign(segment,{translation:checkpoint.translation,status:'draft'});
    p.savedAt=Math.max(p.savedAt||0,checkpoint.savedAt);
  }
  Object.assign(p,{done:p.segments.filter(s=>Boolean(s.translation)).length,total:p.segments.length});
  return p;
}
export async function saveCheckpoints(p,indices,done){
  const savedAt=Date.now();
  const info={id:p.id,name:p.name,kind:p.kind,target:p.target,created:p.created,total:p.segments.length,done,savedAt};
  const records=indices.map(index=>({projectId:p.id,index,translation:p.segments[index].translation,savedAt}));
  await operation(['checkpoints','library'],'readwrite',tx=>{
    for(const record of records)tx.objectStore('checkpoints').put(record);
    tx.objectStore('library').put(info);
  });
  return info;
}
export const deleteProject=id=>operation(['projects','library','checkpoints'],'readwrite',tx=>{
  tx.objectStore('projects').delete(id);tx.objectStore('library').delete(id);
  tx.objectStore('checkpoints').index('project').openKeyCursor(IDBKeyRange.only(id)).onsuccess=e=>{
    const cursor=e.target.result;
    if(cursor){tx.objectStore('checkpoints').delete(cursor.primaryKey);cursor.continue();}
  };
});
