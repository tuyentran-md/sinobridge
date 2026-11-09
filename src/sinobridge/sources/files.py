"""Local file extractors. Every block keeps a location that points back into the original file."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from .html_text import html_blocks, decode_html

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
OPF_NS = {"opf": "http://www.idpf.org/2007/opf"}

def extract_markdown(path: Path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    blocks, acc, start = [], [], 1
    def flush():
        nonlocal acc
        if acc:
            text = "\n".join(acc).strip()
            if text:
                blocks.append((f"line:{start}", "paragraph", text))
            acc = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            flush()
        elif re.match(r"^\s{0,3}#{1,6}\s+", line):
            flush()
            blocks.append((f"line:{i}", "heading", line.strip()))
        elif line.lstrip().startswith("|") and acc and not acc[0].lstrip().startswith("|"):
            flush()
            start = i
            acc.append(line)
        else:
            if not acc:
                start = i
            acc.append(line)
    flush()
    return blocks, []

def extract_docx(path: Path):
    blocks = []
    with ZipFile(path) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(f"{WORD_NS}body")
        if body is None:
            return [], ["DOCX missing body"]
        for i, child in enumerate(body):
            if child.tag == WORD_NS + "p":
                text = "".join((n.text or "") for n in child.iter(WORD_NS + "t"))
                style = child.find(f"{WORD_NS}pPr/{WORD_NS}pStyle")
                is_heading = style is not None and re.match(r"(?i)(heading|title|标题)",
                                                            style.get(WORD_NS + "val") or "")
                if text.strip():
                    blocks.append((f"paragraph:{i+1}", "heading" if is_heading else "paragraph", text))
            elif child.tag == WORD_NS + "tbl":
                for j, row in enumerate(child.iter(WORD_NS + "tr")):
                    cells = ["".join((n.text or "") for n in c.iter(WORD_NS + "t"))
                             for c in row if c.tag == WORD_NS + "tc"]
                    if any(cells):
                        blocks.append((f"table:{i+1}:row:{j+1}", "table", " | ".join(cells)))
    return blocks, ["DOCX notes, tracked changes, graphics and complex tables require manual comparison"]

def extract_epub(path: Path):
    blocks = []
    warnings = ["EPUB figures, styles, footnotes and hyperlinks require manual comparison"]
    with ZipFile(path) as z:
        names = set(z.namelist())
        opf = next((n for n in z.namelist() if n.lower().endswith(".opf")), None)
        if opf:
            root = ET.fromstring(z.read(opf))
            manifest = {el.get("id"): el.get("href") for el in root.findall(".//opf:manifest/opf:item", OPF_NS)}
            spine = [el.get("idref") for el in root.findall(".//opf:spine/opf:itemref", OPF_NS)]
            base = PurePosixPath(opf).parent
            paths = [str(base / manifest[i]) if str(base) != "." else manifest[i] for i in spine if i in manifest]
        else:
            warnings.append("EPUB OPF package not found; fallback to filename order")
            paths = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))
        for name in paths:
            if name not in names or not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            chapter, _ = html_blocks(z.read(name).decode("utf-8", errors="replace"), f"{name}#",
                                     detect_container=False)
            blocks.extend(chapter)
    return blocks, warnings

def extract_pdf(path: Path):
    try:
        import fitz  # type: ignore
    except ImportError:
        raise RuntimeError("PDF support needs: pip install 'sinobridge[pdf]'") from None
    blocks = []
    with fitz.open(path) as doc:
        for p, page in enumerate(doc, 1):
            for i, block in enumerate(page.get_text("blocks", sort=True), 1):
                if len(block) > 4 and isinstance(block[4], str) and block[4].strip():
                    blocks.append((f"page:{p}:block:{i}", "paragraph", block[4].strip()))
    warnings = ["PDF reading order, scanned pages, equations, figures and tables require human inspection; OCR is not automatic"]
    if not blocks:
        warnings.append("No text layer found: this PDF is probably scanned. Run OCR first (e.g. ocrmypdf -l chi_sim).")
    return blocks, warnings

def extract_html(path: Path):
    blocks, title = html_blocks(decode_html(path.read_bytes()))
    warnings = ["Saved web page: verify that the article body (not comments/ads) was captured"]
    return blocks, warnings + ([f"Page title: {title}"] if title else [])

TIME = r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}[,.]\d{1,3})"
CUE = re.compile(TIME + r"\s*-->\s*" + TIME)

def extract_subtitles(path: Path):
    """SRT / WebVTT cues (e.g. subtitles exported from Bilibili, Douyin, YouTube)."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    blocks = []
    for chunk in re.split(r"\n\s*\n", text):
        lines = [l for l in chunk.strip().split("\n") if l.strip()]
        for k, line in enumerate(lines):
            m = CUE.search(line)
            if m:
                body = "\n".join(re.sub(r"<[^>]+>", "", l) for l in lines[k + 1:]).strip()
                if body:
                    start, end = (t.replace(",", ".") for t in m.groups())
                    blocks.append((f"cue:{start}-->{end}", "cue", body))
                break
    return blocks, [] if blocks else ["No subtitle cues found"]

EXTRACTORS = {
    ".txt": extract_markdown, ".md": extract_markdown, ".markdown": extract_markdown,
    ".docx": extract_docx, ".epub": extract_epub, ".pdf": extract_pdf,
    ".html": extract_html, ".htm": extract_html, ".mhtml": None,
    ".srt": extract_subtitles, ".vtt": extract_subtitles,
}

def extract_file(path: Path):
    ext = path.suffix.lower()
    fn = EXTRACTORS.get(ext)
    if ext == ".caj":
        raise ValueError("CNKI .caj is a proprietary format: download the PDF version, or convert with CAJViewer, then ingest the PDF")
    if fn is None:
        supported = ", ".join(sorted(k for k, v in EXTRACTORS.items() if v))
        raise ValueError(f"Unsupported input {ext or '(none)'}; supported: {supported}")
    return fn(path)
