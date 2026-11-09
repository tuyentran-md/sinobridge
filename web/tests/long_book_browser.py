"""Synthetic long-book, resume, storage migration and storage-failure regression tests.

No real account, API key or model calls. Run from any directory with Playwright installed.
"""
import json
import os
import pathlib
import re
import signal
import subprocess
import time
import urllib.request
from playwright.sync_api import sync_playwright

WEB=pathlib.Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:18873/'
GEMINI='https://generativelanguage.googleapis.com/**'
server=subprocess.Popen(['npm','run','dev','--','--port','18873','--strictPort'],cwd=WEB,
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

class Model:
    def __init__(self):
        self.seen=[]
    def __call__(self,route,request):
        headers={'access-control-allow-origin':'*','access-control-allow-headers':'authorization,content-type'}
        if request.method=='OPTIONS':
            return route.fulfill(status=204,headers=headers)
        if request.url.endswith('/models'):
            body={'data':[{'id':'gemini-2.5-flash'}]}
        else:
            payload=json.loads(request.post_data)
            assert payload['model']=='gemini-2.5-flash'
            passages=payload['messages'][-1]['content'].split('Passages:',1)[1]
            pairs=re.findall(r'⟦(\d+)⟧\s*段落(\d+)',passages)
            if pairs:
                self.seen.extend(int(source) for _,source in pairs)
                answer='\n'.join(f'⟦{number}⟧ Bản dịch {source}' for number,source in pairs)
            else:
                numbers=re.findall(r'⟦(\d+)⟧',passages)
                answer='\n'.join(f'⟦{n}⟧ Bản dịch thử' for n in numbers)
            time.sleep(.06)
            body={'choices':[{'message':{'content':answer}}]}
        route.fulfill(status=200,headers=headers,content_type='application/json',body=json.dumps(body))

def synthetic_pdf(pages, text=''):
    resources=f' /Resources << /Font << /F1 {pages+3} 0 R >> >> /Contents {pages+4} 0 R' if text else ''
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',
             ('<< /Type /Pages /Count '+str(pages)+' /Kids ['+' '.join(f'{i} 0 R' for i in range(3,pages+3))+'] >>').encode()]
    objects += [('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]'+resources+' >>').encode()]*pages
    if text:
        stream=('BT /F1 12 Tf 50 700 Td ('+text+') Tj ET').encode()
        objects.extend([b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                        f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream'])
    pdf=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(pdf));pdf.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(pdf);pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:pdf.extend(f'{offset:010} 00000 n \n'.encode())
    pdf.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF'.encode())
    return bytes(pdf)

LOAD="""async id=>{const db=await import('/src/database.js');return await db.loadProject(id)}"""
CHECKPOINTS="""async id=>new Promise((resolve,reject)=>{
 const r=indexedDB.open('sinobridge-browser-v1');r.onerror=()=>reject(r.error);
 r.onsuccess=()=>{const db=r.result,tx=db.transaction(['projects','checkpoints'],'readonly'),result={};
 tx.objectStore('projects').get(id).onsuccess=e=>result.original=e.target.result;
 tx.objectStore('checkpoints').index('project').getAll(id).onsuccess=e=>result.records=e.target.result;
 tx.oncomplete=()=>{db.close();resolve(result)};
 }})"""
try:
    for _ in range(80):
        try:
            urllib.request.urlopen(URL,timeout=.5);break
        except Exception:
            time.sleep(.1)
    else:
        raise RuntimeError('Vite did not start')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        # Upgrade an existing large v1 book, keeping original translations intact.
        ctx=browser.new_context(viewport={'width':1440,'height':900})
        ctx.route('**/src/main.js',lambda route:route.fulfill(body='',content_type='text/javascript'))
        page=ctx.new_page();page.goto(URL,wait_until='networkidle')
        page.evaluate("""async()=>new Promise((resolve,reject)=>{
          const r=indexedDB.open('sinobridge-browser-v1',1);
          r.onupgradeneeded=()=>r.result.createObjectStore('projects',{keyPath:'id'});
          r.onsuccess=()=>{const db=r.result,tx=db.transaction('projects','readwrite');
            tx.objectStore('projects').put({id:'legacy-book',name:'Large synthetic book',kind:'txt',target:'vi',created:1,
              segments:Array.from({length:24001},(_,i)=>({source:'原文'+i+'。这是用于测试的虚构内容。',translation:i<2?'Bản cũ '+i:'',status:i<2?'draft':'pending',heading:false}))});
            tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error);
          };r.onerror=()=>reject(r.error);
        })""")
        ctx.unroute('**/src/main.js')
        page.reload(wait_until='networkidle')
        assert page.locator('#welcome').is_visible()
        assert '2/24001' in page.locator('#library').inner_text()
        page.locator('#library .library-item').click()
        page.locator('#pane').wait_for(state='visible')
        assert page.locator('#preview .row').count()==200
        assert page.locator('#preview .tr').first.inner_text()=='Bản cũ 0'
        assert '2/24001' in page.locator('#checkpoint').inner_text()
        for n in (121,17,1):
            page.locator('#page-number').fill(str(n));page.locator('#page-number').press('Tab')
            assert page.locator('#preview .row').count()==(1 if n==121 else 200)
            assert page.locator('#preview .row').first.get_attribute('data-i')==str((n-1)*200)
        page.select_option('#reading-mode','original')
        assert page.locator('#preview .zh').first.is_visible() and page.locator('#preview .tr').first.is_hidden()
        page.select_option('#reading-mode','bilingual')
        assert page.locator('#preview .zh').first.is_visible() and page.locator('#preview .tr').first.is_visible()
        page.select_option('#reading-mode','translation')
        assert page.locator('#preview .zh').first.is_hidden() and page.locator('#preview .tr').first.is_visible()
        page.locator('#back-home').click();assert page.locator('#welcome').is_visible()
        page.reload(wait_until='networkidle');assert page.locator('#welcome').is_visible()
        original=page.evaluate(LOAD,'legacy-book')
        assert original['done']==2 and original['segments'][1]['translation']=='Bản cũ 1'
        ctx.close()

        # Stop, return home during a run, reload and resume without resending saved passages.
        ctx=browser.new_context(viewport={'width':1440,'height':900});model=Model();ctx.route(GEMINI,model)
        ctx.add_init_script("""window.projectWrites=0;const put=IDBObjectStore.prototype.put;
          IDBObjectStore.prototype.put=function(...args){if(this.name==='projects')window.projectWrites++;return put.apply(this,args)};""")
        page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(URL,wait_until='networkidle')
        raw='\n\n'.join(f'段落{i:05d}。这是测试翻译、暂停和继续的虚构句子。' for i in range(481))
        page.locator('#file').set_input_files({'name':'resume-book.txt','mimeType':'text/plain','buffer':raw.encode()})
        page.locator('#current').wait_for(state='visible')
        page.locator('#api-key').fill('synthetic-key')
        page.wait_for_function("!document.querySelector('#start').disabled")
        page.locator('#start').click()
        page.wait_for_function("document.querySelector('#checkpoint').textContent.includes('đoạn trên máy')")
        page.locator('#home').click();assert page.locator('#welcome').is_visible()
        page.locator('#library .library-item').click()
        page.locator('#stop').click()
        page.wait_for_function("document.querySelector('#stop').hidden")
        info=page.evaluate("async()=>{const db=await import('/src/database.js');return (await db.listProjects())[0]}")
        saved=page.evaluate(LOAD,info['id'])
        assert 0<saved['done']<481,saved['done']
        saved_ids={int(s['source'][2:7]) for s in saved['segments'] if s['translation']}
        records=page.evaluate(CHECKPOINTS,info['id'])
        assert len(records['records'])==saved['done']
        assert all(not s['translation'] for s in records['original']['segments']), 'checkpoint rewrote the original book'
        assert page.evaluate('window.projectWrites')==1,'a full-book write happened after import'
        before=len(model.seen)
        page.reload(wait_until='networkidle');assert page.locator('#welcome').is_visible()
        page.locator('#library .library-item').click()
        page.locator('#api-key').fill('synthetic-key')
        page.wait_for_function("!document.querySelector('#start').disabled")
        assert page.locator('#start').inner_text()=='Dịch tiếp'
        page.locator('#start').click()
        page.wait_for_function("document.querySelector('#status').textContent.startsWith('Xong')",timeout=30000)
        assert saved_ids.isdisjoint(set(model.seen[before:])), 'saved passages were sent again'
        complete=page.evaluate(LOAD,info['id']);assert complete['done']==481
        assert all(s['translation'] for s in complete['segments'])
        assert page.locator('#preview .row').count()==200
        assert page.evaluate('window.projectWrites')==0,'resume rewrote the whole book'
        page.locator('#show-more').click();assert page.locator('#preview .row').first.get_attribute('data-i')=='200'
        assert page.locator('#preview .row').count()==200
        page.locator('#show-more').click();assert page.locator('#preview .row').count()==81
        assert page.locator('#show-more').is_disabled()
        assert not errors,errors
        for size in ({'width':390,'height':844},{'width':1024,'height':768}):
            page.set_viewport_size(size)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),size
        # A many-page PDF is rejected before extraction without losing the current book.
        page.locator('#file').set_input_files({'name':'901-pages.pdf','mimeType':'application/pdf','buffer':synthetic_pdf(901)})
        page.wait_for_function("document.querySelector('#status').textContent.includes('hơn 900 trang')",timeout=20000)
        assert len(page.evaluate(LOAD,info['id'])['segments'])==481
        page.locator('#file').set_input_files({'name':'scan.pdf','mimeType':'application/pdf','buffer':synthetic_pdf(1)})
        page.wait_for_function("document.querySelector('#status').textContent.includes('OCR')")
        page.locator('#file').set_input_files({'name':'text.pdf','mimeType':'application/pdf','buffer':synthetic_pdf(1,'Synthetic PDF text for testing import and cleanup of a document.')})
        page.wait_for_function("document.querySelector('#current').textContent.includes('text.pdf')")
        assert page.locator('#preview .row').count()>0
        assert not errors,errors
        ctx.close()

        # A failed storage write must stop translation and must not claim a saved checkpoint.
        ctx=browser.new_context();ctx.route(GEMINI,Model());page=ctx.new_page()
        page.goto(URL,wait_until='networkidle');page.locator('#try-sample').click()
        page.locator('#current').wait_for(state='visible');page.locator('#api-key').fill('synthetic-key')
        page.wait_for_function("!document.querySelector('#start').disabled")
        page.evaluate("""()=>{const put=IDBObjectStore.prototype.put;let writes=0;
          IDBObjectStore.prototype.put=function(...args){if(this.name==='checkpoints'&&++writes===2)throw new DOMException('Full','QuotaExceededError');return put.apply(this,args)};}""")
        page.locator('#start').click()
        page.wait_for_function("document.querySelector('#status').classList.contains('error')")
        assert 'Không lưu được checkpoint' in page.locator('#status').inner_text()
        info=page.evaluate("async()=>{const db=await import('/src/database.js');return (await db.listProjects())[0]}")
        assert info['done']==0
        restored=page.evaluate(LOAD,info['id']);assert restored['done']==0
        assert not page.evaluate(CHECKPOINTS,info['id'])['records'], 'a failed batch partially committed'
        assert page.locator('#preview .row.done').count()==0
        ctx.close();browser.close()
    print('LONG_BOOK_PASS: 24,001 passages, v1 migration, bounded pages, 3 reading modes, home, pause/reload/resume, delta checkpoints, storage failure, mobile/tablet; no real model calls')
finally:
    try:os.killpg(server.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    server.wait(timeout=10)
