const DATABASE='sinobridge-browser-v1';
const STORE='projects';
const VERSION=1;

function open() {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open(DATABASE,VERSION);
    request.onupgradeneeded=()=>{ if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE,{keyPath:'id'}); };
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
  });
}
async function operation(mode,fn) {
  const db=await open();
  try {
    return await new Promise((resolve,reject)=>{
      const tx=db.transaction(STORE,mode);
      let result;
      const req=fn(tx.objectStore(STORE));
      req.onsuccess=()=>{result=req.result;};
      req.onerror=()=>reject(req.error);
      tx.oncomplete=()=>resolve(result);
      tx.onerror=()=>reject(tx.error);
      tx.onabort=()=>reject(tx.error);
    });
  } finally {db.close();}
}
export const saveProject=p=>operation('readwrite',s=>s.put(p));
export const listProjects=()=>operation('readonly',s=>s.getAll());
export const deleteProject=id=>operation('readwrite',s=>s.delete(id));
