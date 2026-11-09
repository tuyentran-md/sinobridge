#!/usr/bin/env python3
"""Regenerate docs/images/*.png from the synthetic demo (needs: pip install playwright; playwright install chromium)."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sinobridge.ingest import ingest  # noqa: E402
from sinobridge.store import load_segments, save_segments  # noqa: E402
from sinobridge import terms, review, export, hanviet  # noqa: E402
from sinobridge.qa import audit  # noqa: E402

OUT = ROOT / "docs" / "images"

def build_demo(tmp: Path, target: str = "vi") -> Path:
    ws = tmp / f"ws-{target}"
    ingest(ROOT / "examples" / "demo_article_zh.md", ws, "article", target=target)
    demo = json.loads((ROOT / "examples" / f"demo_article_{target}.json").read_text(encoding="utf-8"))
    segs = load_segments(ws)
    for seg, vi in zip(segs, demo["translations"]):
        seg.update(translation=vi, status="DRAFT", model={"provider": "demo", "name": "hand-written"})
    segs[-1]["translation"] = demo["first_draft_of_last"]
    save_segments(ws, segs)
    terms.record(ws, segs[1]["id"], demo["entities"], target)
    reason = "因果关系 = quan hệ nhân quả" if target == "vi" else "因果关系 = causal relationship"
    review.revise(ws, segs[-1]["id"], demo["translations"][-1], "Lan", reason, "MEDIUM", "G1")
    review.approve(ws, segs[1]["id"], "Lan", "Đối chiếu bản gốc" if target == "vi" else "Checked against source")
    audit(ws)
    return ws

TERMINAL = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#0d1117;font:15px/1.55 ui-monospace,Menlo,Consolas,monospace;color:#c9d1d9}
.t{padding:18px 22px}.p{color:#7ee787}.c{color:#79c0ff}.m{color:#8b949e}.w{color:#e3b341}.b{color:#fff;font-weight:600}
.bar{background:#161b22;padding:8px 14px;color:#8b949e;font:12px system-ui}.bar i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}
</style></head><body><div class="bar"><i style="background:#ff5f56"></i><i style="background:#ffbd2e"></i><i style="background:#27c93f"></i>terminal</div><div class="t">
__BODY__</div></body></html>"""

def terminal_html() -> str:
    lines = []
    for zh in ["诸葛亮", "毛泽东", "四川省", "重庆", "张明华", "乐山"]:
        r = hanviet.transliterate(zh)
        flag = ""
        if r["ambiguous"]:
            flag = f' <span class="w">⚠ chữ đa âm: {"".join(r["ambiguous"])} ({", ".join(p["hanviet"] + "/" + "/".join(p["alternatives"][:1]) for p in r["pieces"] if p.get("zh") in r["ambiguous"])})</span>'
        src = '<span class="m">từ điển</span>' if r["exact"] else '<span class="m">ghép âm</span>'
        lines.append(f'<span class="b">{zh}</span>  →  <span class="c">{r["hanviet"]}</span>  {src}{flag}')
    lines.append('<span class="m"># tên nước ngoài viết bằng chữ Hán (特朗普) không phiên Hán Việt khi dịch: giữ “Trump”</span>')
    return TERMINAL.replace("__BODY__", '<span class="p">$</span> sinobridge hanviet 诸葛亮 毛泽东 四川省 重庆 张明华 乐山<br>' + "<br>".join(lines))

def terminal_en_html() -> str:
    from sinobridge.names import english
    lines = []
    for zh, kind in [("诸葛亮", "person"), ("孔子", "person"), ("张明华", "person"), ("欧阳明", "person"),
                     ("西安", "place"), ("四川省", "place"), ("长江", "place")]:
        r = english(zh, kind)
        src = '<span class="m">dictionary</span>' if r["exact"] else '<span class="m">pinyin rules</span>'
        lines.append(f'<span class="b">{zh}</span>  →  <span class="c">{r["render"]}</span>  {src}')
    cmd = '<span class="p">$</span> sinobridge name 诸葛亮 孔子 张明华 欧阳明 --to en   <span class="m"># + places with --type place</span><br>'
    return TERMINAL.replace("__BODY__", cmd + "<br>".join(lines))

def gui_shots(browser):
    """Screenshots of the drag-and-drop app (gui-vi.png, gui-en.png) with the demo article."""
    import threading
    from sinobridge.webapp import create_server
    for lang in ("en", "vi"):
        data = Path(tempfile.mkdtemp())
        srv = create_server(data, 8799)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 1000}, device_scale_factor=2,
                                      locale="vi-VN" if lang == "vi" else "en-US")
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:8799/")
            pg.select_option("#target", lang)
            pg.set_input_files("#fileinput", str(ROOT / "examples" / "demo_article_zh.md"))
            pg.wait_for_selector("#selected:not(.hidden)")
            uid = next(d for d in data.iterdir() if d.is_dir())
            demo = json.loads((ROOT / "examples" / f"demo_article_{lang}.json").read_text(encoding="utf-8"))
            segs = load_segments(uid)
            for seg, text in zip(segs, demo["translations"]):
                seg.update(translation=text, status="DRAFT")
            save_segments(uid, segs)
            terms.record(uid, segs[1]["id"], demo["entities"], lang)
            audit(uid)
            pg.reload()
            pg.wait_for_timeout(1000)
            pg.evaluate("window.scrollTo(0, 0)")
            pg.screenshot(path=str(OUT / f"gui-{lang}.png"))
            ctx.close()
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(data, ignore_errors=True)

def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    try:
        ws = build_demo(tmp)
        page_file = review.review_html(ws, tmp / "review.html")
        epub_file = export.epub(ws, tmp / "demo.epub", bilingual=True)
        with zipfile.ZipFile(epub_file) as z:
            z.extractall(tmp / "epub")
        (tmp / "term.html").write_text(terminal_html(), encoding="utf-8")
        segs = load_segments(ws)
        ws_en = build_demo(tmp, "en")
        page_en = review.review_html(ws_en, tmp / "review-en.html")
        (tmp / "term-en.html").write_text(terminal_en_html(), encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page(viewport={"width": 1280, "height": 760}, device_scale_factor=2)
            pg.goto(page_file.as_uri() + "#" + segs[3]["id"])
            pg.hover("#side .zh .hv >> text=北")
            pg.screenshot(path=str(OUT / "review-page.png"))
            pg = browser.new_page(viewport={"width": 1280, "height": 760}, device_scale_factor=2)
            pg.goto(page_en.as_uri() + "#" + segs[3]["id"])
            pg.hover("#side .zh .hv >> text=北")
            pg.screenshot(path=str(OUT / "review-page-en.png"))
            pg = browser.new_page(viewport={"width": 900, "height": 300}, device_scale_factor=2)
            pg.goto((tmp / "term-en.html").as_uri())
            pg.screenshot(path=str(OUT / "names-en-cli.png"), full_page=True)
            pg = browser.new_page(viewport={"width": 460, "height": 820}, device_scale_factor=2)
            pg.goto((tmp / "epub" / "OEBPS" / "ch001.xhtml").as_uri())
            pg.screenshot(path=str(OUT / "epub-bilingual.png"))
            pg = browser.new_page(viewport={"width": 900, "height": 300}, device_scale_factor=2)
            pg.goto((tmp / "term.html").as_uri())
            pg.screenshot(path=str(OUT / "hanviet-cli.png"), full_page=True)
            gui_shots(browser)
            browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", *sorted(p.name for p in OUT.glob("*.png")))

if __name__ == "__main__":
    main()
