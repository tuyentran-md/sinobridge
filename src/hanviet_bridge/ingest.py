"""Text extraction preserving source locations and declaring extraction limits."""
from __future__ import annotations
import datetime as dt
from html.parser import HTMLParser
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from .store import sha256, save_json, save_segments, load_project

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_NS = {"opf": "http://www.idpf.org/2007/opf"}

class BlockHTMLParser(HTMLParser):
    BLOCKS = {"h1", "h2", "h3", "h4", "p", "li", "blockquote", "td", "th"}
    IGNORE = {"script", "style", "nav"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ignored = 0
        self.active = None
        self.buffer = []
        self.blocks = []
    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORE:
            self.ignored += 1
        if self.ignored:
            return
        if tag in self.BLOCKS and self.active is None:
            self.active = tag
            self.buffer = []
        elif tag == "br" and self.active:
            self.buffer.append("\n")
    def handle_endtag(self, tag):
        if tag in self.IGNORE:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag == self.active:
            value = "".join(self.buffer).strip()
            if value:
                self.blocks.append(("heading" if tag.startswith("h") else "paragraph", value))
            self.active, self.buffer = None, []
    def handle_data(self, data):
        if self.active and not self.ignored:
            self.buffer.append(data)

def extract_markdown(path: Path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    blocks, acc, start = [], [], 1
    def flush():
        nonlocal acc
        if acc:
            t = "\n".join(acc).strip()
            if t:
                blocks.append((f"line:{start}", "paragraph", t))
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
            if child.tag == WORD_NS+"p":
                text = "".join((n.text or "") for n in child.iter(WORD_NS+"t"))
                if text.strip():
                    blocks.append((f"paragraph:{i+1}", "paragraph", text))
            elif child.tag == WORD_NS+"tbl":
                for j, row in enumerate(child.iter(WORD_NS+"tr")):
                    cells = ["".join((n.text or "") for n in c.iter(WORD_NS+"t"))
                             for c in row if c.tag == WORD_NS+"tc"]
                    if any(cells):
                        blocks.append((f"table:{i+1}:row:{j+1}", "table", " | ".join(cells)))
    return blocks, ["DOCX notes, tracked changes, graphics and complex tables require manual comparison"]

def extract_epub(path: Path):
    blocks = []
    warnings = ["EPUB non-text figures, styles, footnotes and hyperlinks require manual comparison"]
    with ZipFile(path) as z:
        opf = next((name for name in z.namelist() if name.lower().endswith(".opf")), None)
        paths = []
        if opf:
            root = ET.fromstring(z.read(opf))
            manifest = {el.get("id"): el.get("href") for el in root.findall(".//opf:manifest/opf:item", XML_NS)}
            spine = [item.get("idref") for item in root.findall(".//opf:spine/opf:itemref", XML_NS)]
            paths = [(Path(opf).parent / manifest[item]).as_posix() for item in spine if item in manifest]
        else:
            warnings.append("EPUB OPF package not found; fallback to filename order")
            paths = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html")))
        for name in paths:
            if name not in z.namelist() or not name.lower().endswith((".xhtml", ".html")):
                continue
            parser = BlockHTMLParser()
            parser.feed(z.read(name).decode("utf-8", errors="replace"))
            for i, (kind, text) in enumerate(parser.blocks, 1):
                blocks.append((f"{name}#block:{i}", kind, text))
    return blocks, warnings

def extract_pdf(path: Path):
    try:
        import fitz  # type: ignore
    except ImportError:
        raise RuntimeError("PDF support needs: pip install 'hanviet-bridge[pdf]'") from None
    blocks = []
    with fitz.open(path) as doc:
        for p, page in enumerate(doc, 1):
            for i, block in enumerate(page.get_text("blocks", sort=True), 1):
                if len(block) > 4 and isinstance(block[4], str) and block[4].strip():
                    blocks.append((f"page:{p}:block:{i}", "paragraph", block[4].strip()))
    return blocks, ["PDF reading order, scanned pages, equations, figures and tables require human inspection; OCR is not automatic"]

def extract(path: Path):
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".markdown"):
        return extract_markdown(path)
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".epub":
        return extract_epub(path)
    if ext == ".pdf":
        return extract_pdf(path)
    raise ValueError("Supported inputs: .txt, .md, .markdown, .docx, .epub, .pdf")

def ingest(path: Path, workspace: Path, kind: str) -> dict:
    path = path.expanduser().resolve()
    workspace = workspace.expanduser().resolve()
    if kind not in ("book", "paper"):
        raise ValueError("--kind must be book or paper")
    checksum = sha256(path.read_bytes())
    if (workspace / "project.json").exists():
        old = load_project(workspace)
        if old["source_sha256"] != checksum or old["kind"] != kind:
            raise RuntimeError("Workspace has a different source/revision; choose a NEW workspace to protect existing translations")
        return old
    blocks, warnings = extract(path)
    if not blocks:
        raise RuntimeError("No text blocks extracted. Check scanned document/OCR and source format.")
    entries = []
    for location, block_kind, source in blocks:
        entries.append({
            "id": sha256((location+"\0"+source).encode("utf-8"))[:16],
            "location": location, "kind": block_kind, "source": source,
            "translation": None, "status": "PENDING",
            "ambiguities": [], "notes": [],
        })
    meta = {
        "schema_version": 1, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": kind, "source_filename": path.name, "source_sha256": checksum,
        "source_language": "zh", "target_language": "vi",
        "segment_count": len(entries), "extraction_warnings": warnings,
        "review_status": "NOT_REVIEWED", "rights_status": "UNVERIFIED",
    }
    save_segments(workspace, entries)
    save_json(workspace / "project.json", meta)
    return meta
