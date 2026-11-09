"""Clean reader outputs: Markdown, DOCX, EPUB3 (chapters + TOC), SRT/VTT subtitles.

Content pages carry no banners. Review status is stated once, honestly, in a colophon
(title page / front matter): machine draft, partially or fully human-approved.
Every segment keeps an invisible anchor (EPUB/HTML id, optional Markdown comment) back to its source.
"""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
import uuid
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from .store import load_project, load_segments, save_text
from .review import approval_is_current

CSS = """@charset "utf-8";
body { font-family: "Noto Serif", "Source Serif", Georgia, serif; line-height: 1.6; margin: 0 5%; }
h1, h2, h3 { font-family: "Noto Sans", "Helvetica Neue", sans-serif; line-height: 1.3; page-break-after: avoid; break-after: avoid; }
h1 { font-size: 1.6em; margin: 1.5em 0 1em; } h2 { font-size: 1.3em; margin: 1.4em 0 .6em; }
p { margin: 0 0 .8em; text-indent: 0; orphans: 2; widows: 2; }
.zh { font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; color: #555; font-size: .92em;
      margin: -.4em 0 1.1em; padding-left: .8em; border-left: 2px solid #ccc; }
.missing { color: #888; font-style: italic; }
.colophon { font-size: .85em; color: #444; margin-top: 3em; }
.colophon p { margin: 0 0 .4em; }
.titlepage { text-align: center; margin-top: 20%; }
.titlepage .sub { color: #666; font-size: .95em; }"""

def strip_heading(text: str) -> str:
    return re.sub(r"^\s{0,3}#{1,6}\s+", "", text or "").strip()

def review_summary(segs: list[dict]) -> dict:
    total = len(segs)
    translated = sum(bool(s.get("translation")) for s in segs)
    approved = [s for s in segs if approval_is_current(s)]
    reviewers = sorted({s["approval"]["reviewer"] for s in approved})
    models = sorted({f"{s['model']['provider']}/{s['model']['name']}" for s in segs if s.get("model")})
    if total and len(approved) == total:
        line = f"Toàn bộ {total} đoạn đã được người duyệt ({', '.join(reviewers)}) đối chiếu với bản gốc."
    elif approved:
        line = f"Bản dịch nháp: {len(approved)}/{total} đoạn đã được người duyệt; phần còn lại chưa được kiểm tra."
    else:
        line = "Bản dịch nháp (dịch máy), chưa được người duyệt đối chiếu với bản gốc."
    if translated < total:
        line += f" Còn {total - translated} đoạn chưa dịch (giữ nguyên tiếng Trung)."
    return {"total": total, "translated": translated, "approved": len(approved), "reviewers": reviewers,
            "models": models, "status_line": line, "fully_approved": bool(total) and len(approved) == total}

def colophon_lines(project: dict, segs: list[dict]) -> list[str]:
    summary = review_summary(segs)
    prov = project.get("provenance") or {}
    origin = prov.get("url") or project["source_filename"]
    lines = [summary["status_line"], f"Nguồn: {origin}", f"SHA-256 nguồn: {project['source_sha256']}"]
    if summary["models"]:
        lines.append("Mô hình dịch: " + ", ".join(summary["models"]))
    lines.append("Bản quyền nội dung thuộc tác giả gốc; bản dịch dùng cho mục đích được phép.")
    lines.append(f"Tạo bằng HanViet Bridge, {datetime.now(timezone.utc):%Y-%m-%d}.")
    return lines

def book_title(project: dict, segs: list[dict]) -> str:
    first = next((s for s in segs if s["kind"] == "heading"), None)
    if first and first.get("translation"):
        return strip_heading(first["translation"])
    prov = project.get("provenance") or {}
    return prov.get("title") or Path(project["source_filename"]).stem

def units(segs: list[dict]):
    """(kind, vietnamese_or_None, chinese, segment) in reading order."""
    for s in segs:
        vi = s.get("translation")
        if s["kind"] == "heading":
            yield "heading", strip_heading(vi) if vi else None, strip_heading(s["source"]), s
        else:
            yield "text", vi, s["source"], s

# ---------------------------------------------------------------- Markdown
def markdown(workspace: Path, outfile: Path, bilingual=False, trace=False):
    project, segs = load_project(workspace), load_segments(workspace)
    parts = [f"# {book_title(project, segs)}", ""]
    parts += [f"> {line}" for line in colophon_lines(project, segs)] + [""]
    for kind, vi, zh, s in units(segs):
        if trace:
            parts.append(f"<!-- {s['id']} | {s['location']} | {s['status']} -->")
        if kind == "heading":
            parts.append("## " + (vi or zh))
            if bilingual and vi:
                parts.append(f"<small lang=\"zh\">{zh}</small>")
        else:
            parts.append(vi if vi else f"*[chưa dịch]* {zh}")
            if bilingual and vi:
                parts += [""] + ["> " + line for line in zh.split("\n")]
        parts.append("")
    save_text(outfile, "\n".join(parts))
    return outfile

# ---------------------------------------------------------------- DOCX
def docx(workspace: Path, outfile: Path, bilingual=False, trace=False):
    project, segs = load_project(workspace), load_segments(workspace)
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.oxml.ns import qn
    except ImportError:
        raise RuntimeError("DOCX output requires: pip install 'hanviet-bridge[docx]'") from None
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "SimSun")
    doc.add_heading(book_title(project, segs), level=0)
    for line in colophon_lines(project, segs):
        run = doc.add_paragraph().add_run(line)
        run.font.size, run.font.color.rgb = Pt(9), RGBColor(0x55, 0x55, 0x55)
    doc.add_page_break()
    def zh_para(text):
        run = doc.add_paragraph().add_run(text)
        run.font.size, run.font.color.rgb = Pt(10.5), RGBColor(0x66, 0x66, 0x66)
        run.font.name = "SimSun"
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "SimSun")
    for kind, vi, zh, s in units(segs):
        if kind == "heading":
            doc.add_heading(vi or zh, level=1)
            if bilingual and vi:
                zh_para(zh)
        else:
            if vi:
                doc.add_paragraph(vi)
                if bilingual:
                    zh_para(zh)
            else:
                zh_para("[chưa dịch] " + zh)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    doc.save(outfile)
    return outfile

# ---------------------------------------------------------------- EPUB3
def _p(text: str, cls: str | None = None, lang: str | None = None, ident: str | None = None) -> str:
    attrs = "".join(f' {k}="{v}"' for k, v in (("id", ident), ("class", cls), ("xml:lang", lang), ("lang", lang)) if v)
    return f"<p{attrs}>" + "<br/>".join(escape(line) for line in text.split("\n")) + "</p>"

def _xhtml(title: str, body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi" lang="vi">
<head><meta charset="utf-8"/><title>{escape(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
{body}
</body></html>"""

def epub(workspace: Path, outfile: Path, bilingual=False, trace=False):
    project, segs = load_project(workspace), load_segments(workspace)
    title = book_title(project, segs)
    chapters: list[tuple[str, list[str]]] = []
    current_title, current = None, []
    for kind, vi, zh, s in units(segs):
        if kind == "heading":
            if current:
                chapters.append((current_title or title, current))
            current_title, current = vi or zh, [f'<h2 id="seg-{s["id"]}">{escape(vi or zh)}</h2>']
            if bilingual and vi:
                current.append(_p(zh, "zh", "zh-Hans"))
        else:
            if vi:
                current.append(_p(vi, ident=f"seg-{s['id']}"))
                if bilingual:
                    current.append(_p(zh, "zh", "zh-Hans"))
            else:
                current.append(_p(zh, "missing", "zh-Hans", f"seg-{s['id']}"))
    if current:
        chapters.append((current_title or title, current))
    colophon = "".join(_p(line) for line in colophon_lines(project, segs))
    titlepage = (f'<section class="titlepage" epub:type="titlepage"><h1>{escape(title)}</h1>'
                 f'<p class="sub">Bản dịch tiếng Việt</p></section>'
                 f'<section class="colophon" epub:type="colophon">{colophon}</section>')
    files = {"title.xhtml": _xhtml(title, titlepage)}
    toc = []
    for n, (ch_title, body) in enumerate(chapters, 1):
        name = f"ch{n:03d}.xhtml"
        files[name] = _xhtml(ch_title, "\n".join(body))
        toc.append(f'<li><a href="{name}">{escape(ch_title)}</a></li>')
    nav = _xhtml("Mục lục", f'<nav epub:type="toc" id="toc"><h1>Mục lục</h1><ol>{"".join(toc)}</ol></nav>')
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    book_id = uuid.uuid5(uuid.NAMESPACE_URL, "hanviet:" + project["source_sha256"])
    manifest = "\n".join(f'<item id="{Path(n).stem}" href="{n}" media-type="application/xhtml+xml"/>' for n in files)
    spine = "\n".join(f'<itemref idref="{Path(n).stem}"/>' for n in files)
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="vi">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>
<dc:title>{escape(title)}</dc:title><dc:language>vi</dc:language>
<dc:source>{escape((project.get('provenance') or {}).get('url') or project['source_filename'])}</dc:source>
<dc:description>{escape(review_summary(segs)['status_line'])}</dc:description>
<meta property="dcterms:modified">{modified}</meta>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="style.css" media-type="text/css"/>
{manifest}
</manifest>
<spine>
{spine}
</spine>
</package>"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(outfile, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=ZIP_DEFLATED)
        for name, content in files.items():
            z.writestr(f"OEBPS/{name}", content, compress_type=ZIP_DEFLATED)
    return outfile

# ---------------------------------------------------------------- Subtitles
def cue_time(t: str, vtt: bool) -> str:
    """Normalize '01:02.5' / '0:01:02.500' to 'HH:MM:SS.mmm' (VTT) or 'HH:MM:SS,mmm' (SRT)."""
    clock, _, ms = t.strip().replace(",", ".").partition(".")
    parts = [int(x) for x in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    stamp = "{:02d}:{:02d}:{:02d}".format(*parts) + ("." if vtt else ",") + (ms + "000")[:3]
    return stamp

def subtitles(workspace: Path, outfile: Path, bilingual=False, trace=False):
    _, segs = load_project(workspace), load_segments(workspace)
    cues = [s for s in segs if s["kind"] == "cue"]
    if not cues:
        raise RuntimeError("This workspace has no subtitle cues (ingest a .srt/.vtt file)")
    vtt = outfile.suffix.lower() == ".vtt"
    out = ["WEBVTT", ""] if vtt else []
    for n, s in enumerate(cues, 1):
        start, end = (cue_time(t, vtt) for t in s["location"].removeprefix("cue:").split("-->"))
        if not vtt:
            out.append(str(n))
        text = s.get("translation") or s["source"]
        if bilingual and s.get("translation"):
            text += "\n" + s["source"]
        out += [f"{start} --> {end}", text, ""]
    save_text(outfile, "\n".join(out))
    return outfile
