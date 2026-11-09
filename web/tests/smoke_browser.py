"""Browser smoke test for the public demo. Never downloads model weights."""
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from playwright.sync_api import sync_playwright

WEB=pathlib.Path(__file__).resolve().parents[1]
ROOT=WEB.parent
PORT=18871
URL=f"http://127.0.0.1:{PORT}/"
server=subprocess.Popen(["npm","run","dev","--","--port",str(PORT),"--strictPort"],
                        cwd=WEB,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(URL,timeout=0.5)
            break
        except Exception:
            time.sleep(.15)
    else:
        raise RuntimeError('Vite dev server failed to start')

    with tempfile.TemporaryDirectory() as d, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        ctx=browser.new_context(accept_downloads=True)
        page=ctx.new_page()
        errors=[]
        page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.goto(URL,wait_until='domcontentloaded')
        assert "SinoBridge" in page.title()
        assert page.get_by_role('heading',name='Dịch tài liệu tiếng Trung',exact=True).is_visible()
        page.locator('#file').set_input_files(str(ROOT/'examples'/'synthetic_zh.md'))
        page.locator('#current').wait_for(state='visible')
        assert 'synthetic_zh.md' in page.locator('#current').inner_text()
        assert 'đoạn' in page.locator('#current').inner_text()
        assert page.locator('#preview .frag').count()>0
        assert page.locator('[data-export="epub"]').is_disabled()

        # Inject a mock translation into IndexedDB; test downloads without calling any model.
        page.evaluate("""async () => {
          const req=indexedDB.open('sinobridge-browser-v1',1);
          const db=await new Promise((resolve,reject)=>{req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
          const tx=db.transaction('projects','readwrite');
          const store=tx.objectStore('projects');
          const get=store.getAll();
          const projects=await new Promise((resolve,reject)=>{get.onsuccess=()=>resolve(get.result);get.onerror=()=>reject(get.error);});
          for(const p of projects){p.segments.forEach(s=>{s.translation='Bản dịch kiểm thử';s.status='draft';});store.put(p);}
          await new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
          db.close();
        }""")
        page.reload(wait_until='domcontentloaded')
        page.locator('#current').wait_for(state='visible')
        assert page.locator('[data-export="epub"]').is_enabled()
        for format in ('epub','docx','html','txt'):
            with page.expect_download() as download:
                page.locator('[data-export="'+format+'"]').click()
            dest=pathlib.Path(d)/('out.'+format)
            download.value.save_as(str(dest))
            assert dest.stat().st_size>100, format
            if format=='epub':
                with zipfile.ZipFile(dest) as z:
                    assert z.namelist()[0]=='mimetype'
                    assert z.read('mimetype')==b'application/epub+zip'
                    assert 'Bản dịch kiểm thử' in z.read('OEBPS/main.xhtml').decode()
            if format=='docx':
                with zipfile.ZipFile(dest) as z: assert 'word/document.xml' in z.namelist()
            if format=='html':
                assert 'Bản dịch kiểm thử' in dest.read_text()
        assert not errors, errors
        # Import the generated EPUB and DOCX back into the browser.
        for fmt in ('epub','docx'):
            page.locator('#file').set_input_files(str(pathlib.Path(d)/('out.'+fmt)))
            page.locator('#current').wait_for(state='visible')
            page.wait_for_function('document.querySelector("#current").textContent.includes("out.'+fmt+'")',timeout=15000)
            assert page.locator('#preview .frag').count()>0, fmt
        ctx2=browser.new_context()
        p2=ctx2.new_page()
        p2.goto(URL,wait_until='domcontentloaded')
        p2.locator('#try-sample').click()
        p2.locator('#current').wait_for(state='visible')
        assert 'Ví dụ tiếng Trung' in p2.locator('#current').inner_text()
        ctx2.close();ctx.close();browser.close()
    print('BROWSER_SMOKE_PASS: import, persistence, 4 exports, sample, no model calls')
finally:
    import signal
    try:
        os.killpg(server.pid,signal.SIGTERM)
    except ProcessLookupError:
        pass
    server.wait(timeout=10)
