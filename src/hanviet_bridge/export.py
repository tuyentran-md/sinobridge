"""Draft text, DOCX, and minimal EPUB3 export. Not a professional typesetting engine."""
from __future__ import annotations
from html import escape
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from xml.sax.saxutils import escape as xml_escape
from .store import load_project, load_segments, save_text

CSS = """body { font-family: serif; font-size: 1em; line-height: 1.55; margin: 5%; }
h1, h2 { font-family: sans-serif; line-height: 1.3; page-break-after: avoid; }
p { margin: 0 0 0.7em; orphans: 2; widows: 2; }
.source { font-size: 0.8em; opacity: 0.7; margin-top: 1.2em; }
table { width: 100%; border-collapse: collapse; }"""

def checked(workspace: Path, draft: bool):
    segs = load_segments(workspace)
    if not draft:
        raise RuntimeError("Public/release export is not implemented; use --draft only for internal review.")
    return load_project(workspace), segs

def segment_text(s, bilingual=False):
    return (s["translation"] or "[TRANSLATION MISSING]") if not bilingual else (
        f"Source {s['location']}\n{s['source']}\n\nVietnamese draft\n"
        + (s["translation"] or "[TRANSLATION MISSING]"))

def markdown(workspace: Path, outfile: Path, bilingual=False, draft=False):
    project, segs = checked(workspace, draft)
    parts = [f"<!-- DRAFT ONLY — source SHA256 {project['source_sha256']}; no editorial clearance -->", ""]
    for s in segs:
        val = segment_text(s, bilingual)
        if s["kind"] == "heading" and not bilingual:
            parts.append(val if val.lstrip().startswith("#") else "# "+val)
        else:
            parts.append(f"<!-- {s['id']} | {s['location']} | {s['status']} -->\n{val}")
        parts.append("")
    save_text(outfile, "\n".join(parts))
    return outfile

def docx(workspace: Path, outfile: Path, bilingual=False, draft=False):
    _, segs = checked(workspace, draft)
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("DOCX output requires: pip install python-docx") from None
    doc = Document()
    doc.add_paragraph("DRAFT — NOT QUALITY APPROVED", style="Subtitle")
    for s in segs:
        val = segment_text(s, bilingual)
        if s["kind"] == "heading" and not bilingual:
            doc.add_heading(val.lstrip("# ").strip(), level=1)
        else:
            doc.add_paragraph(val)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    doc.save(outfile)
    return outfile

def epub(workspace: Path, outfile: Path, bilingual=False, draft=False):
    project, segs = checked(workspace, draft)
    title = "Vietnamese draft of "+Path(project["source_filename"]).stem
    paragraphs = []
    for s in segs:
        content = segment_text(s, bilingual)
        htag = "h2" if s["kind"] == "heading" else "p"
        # XML escape all source and target text, preserve newlines (not rich formatting).
        paragraphs.append(f'<{htag} id="seg-{s["id"]}">{escape(content).replace(chr(10), "&#10;")}</{htag}>')
    body = "\n".join(paragraphs)
    xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">
<head><title>{xml_escape(title)}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>
<body><h1>{xml_escape(title)}</h1><p><strong>DRAFT — NOT QUALITY APPROVED</strong></p>{body}</body></html>"""
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi">
<head><title>Contents</title></head><body><nav epub:type="toc" id="toc"><h1>Contents</h1>
<ol><li><a href="chapter.xhtml">{xml_escape(title)}</a></li></ol></nav></body></html>"""
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="vi">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">urn:sha256:{project['source_sha256']}</dc:identifier>
<dc:title>{xml_escape(title)}</dc:title><dc:language>vi</dc:language>
<meta property="dcterms:modified">{__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</meta>
</metadata><manifest>
<item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="css" href="style.css" media-type="text/css"/>
</manifest><spine><itemref idref="chapter"/></spine></package>"""
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
        z.writestr("OEBPS/chapter.xhtml", xhtml, compress_type=ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=ZIP_DEFLATED)
    return outfile
