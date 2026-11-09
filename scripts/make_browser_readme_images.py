#!/usr/bin/env python3
"""Capture the current web UI with synthetic sample translations; no model calls.

Requires npm ci in web/ and Playwright with Chromium. Legacy CLI/export screenshots
are generated separately by make_readme_images.py.
"""
from pathlib import Path
import os
import signal
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/images'
URL='http://127.0.0.1:18874/'
TRANSLATIONS={
    'vi':[
        'Một đoạn ví dụ',
        'Trung Quốc có rất nhiều nền văn hóa địa phương khác nhau. Thành Đô nổi tiếng với ẩm thực và nhịp sống thong thả.',
        'Đoạn văn ngắn này chỉ nhằm minh họa tính năng dịch thuật. Nguyên văn gồm có hai đoạn, không chứa bất kỳ lời khuyên y khoa hay dữ liệu nghiên cứu thực tế nào.',
    ],
    'en':[
        'A sample passage',
        'China has many distinct regional cultures. Chengdu is known for its food and relaxed pace of life.',
        'This short text only demonstrates the translation feature. The original has two paragraphs and contains no medical advice or real research data.',
    ],
}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    server=subprocess.Popen(['npm','run','dev','--','--port','18874','--strictPort'],cwd=ROOT/'web',
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        for _ in range(80):
            try:urllib.request.urlopen(URL,timeout=.5);break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Vite did not start')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for target,translations in TRANSLATIONS.items():
                ctx=browser.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
                # Screenshots cannot send content or credentials to an external service.
                ctx.route('**/*',lambda route:route.continue_() if urlsplit(route.request.url).hostname=='127.0.0.1' else route.abort())
                page=ctx.new_page();page.goto(URL,wait_until='networkidle');page.evaluate('document.fonts.ready')
                assert page.locator('#welcome').is_visible()
                if target=='vi':page.screenshot(path=str(OUT/'browser-home.png'))
                page.evaluate('''async({target,translations})=>{
                    const {syntheticSample}=await import('/src/parse.js');
                    const {saveProject,saveCheckpoints}=await import('/src/database.js');
                    const p=syntheticSample(target);
                    if(p.segments.length!==translations.length)throw new Error('Sample fixture changed');
                    await saveProject(p);
                    p.segments.forEach((s,i)=>{s.translation=translations[i];s.status='draft';});
                    await saveCheckpoints(p,p.segments.map((_,i)=>i),p.segments.length);
                }''',{'target':target,'translations':translations})
                page.reload(wait_until='networkidle');page.locator('#library .library-item').click()
                page.locator('#pane').wait_for(state='visible');page.select_option('#reading-mode','bilingual')
                assert page.locator('#done-count').inner_text()=='3/3'
                assert page.locator('#preview .zh').first.is_visible()
                assert page.locator('#preview .tr').last.inner_text()==translations[-1]
                page.evaluate('document.fonts.ready')
                page.screenshot(path=str(OUT/f'browser-reader-{target}.png'))
                ctx.close()
            browser.close()
    finally:
        try:os.killpg(server.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        server.wait(timeout=10)
    print('Captured current homepage and VI/EN bilingual readers; synthetic fixture only, no model calls.')

if __name__=='__main__':main()
