"""Source connectors: where Chinese material comes from.

Two connector kinds share one registry:

* document connectors turn a reference (file path, URL, ...) into source-anchored text blocks;
* search connectors return bibliographic records for the research library.

Third-party packages can add connectors (e.g. an institution's licensed CNKI/Wanfang API,
a Weibo export reader) without changing this repository, via the entry-point group
``hanviet_bridge.sources``. See docs/connectors.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable
from .files import extract_file, EXTRACTORS
from . import web

@dataclass
class Connector:
    name: str
    kind: str                      # "document" | "search"
    description: str
    access: str = "public"         # "public" | "user-provided" | "licensed"
    handles: Callable[[str], bool] | None = None   # document connectors: can this ref be opened?
    open: Callable[[str], tuple] | None = None      # ref -> (raw bytes, blocks, warnings, provenance)
    search: Callable[..., list] | None = None       # (query, language, limit) -> records
    origin: str = "builtin"
    notes: list[str] = field(default_factory=list)

def _open_file(ref: str):
    path = Path(ref).expanduser().resolve()
    blocks, warnings = extract_file(path)
    return path.read_bytes(), blocks, warnings, {"origin": "file", "filename": path.name}

def _is_file(ref: str) -> bool:
    return not ref.startswith(("http://", "https://")) and Path(ref).expanduser().suffix.lower() in EXTRACTORS

def _is_url(ref: str) -> bool:
    return ref.startswith(("http://", "https://"))

def _builtin() -> list[Connector]:
    from ..explore import search_openalex, search_crossref
    return [
        Connector("file", "document",
                  "Local TXT/Markdown, DOCX, EPUB, PDF (text layer), saved HTML pages, SRT/VTT subtitles",
                  "user-provided", _is_file, _open_file,
                  notes=["CNKI/Wanfang/VIP: download the PDF with your own access, then ingest it",
                         "Login-only social pages (Weibo, Xiaohongshu, Zhihu): save page as HTML from your browser",
                         "Bilibili/Douyin/YouTube videos: download the Chinese subtitle file (.srt/.vtt)"]),
        Connector("url", "document",
                  "One public web page per call: WeChat Official Account articles, Zhihu columns, news, blogs",
                  "public", _is_url, web.extract_url,
                  notes=["robots.txt honored; no crawling, login, cookies or anti-bot circumvention"]),
        Connector("openalex", "search", "OpenAlex scholarly metadata (language:zh filter, OA links)",
                  "public", search=search_openalex),
        Connector("crossref", "search", "Crossref DOI metadata (client-side Chinese filter; sparse)",
                  "public", search=search_crossref),
    ]

def _plugins() -> list[Connector]:
    found = []
    try:
        eps = entry_points(group="hanviet_bridge.sources")
    except TypeError:  # Python < 3.10 API
        eps = entry_points().get("hanviet_bridge.sources", [])
    for ep in eps:
        try:
            obj = ep.load()
            items = obj() if callable(obj) and not isinstance(obj, Connector) else obj
            for c in (items if isinstance(items, (list, tuple)) else [items]):
                if isinstance(c, Connector):
                    c.origin = f"plugin:{ep.value}"
                    found.append(c)
        except Exception as exc:  # a broken plugin must not break the core tool
            found.append(Connector(ep.name, "broken", f"Failed to load plugin: {exc}", origin=f"plugin:{ep.value}"))
    return found

def registry() -> dict[str, Connector]:
    out = {}
    for c in _builtin() + _plugins():
        out.setdefault(c.name, c)
    return out

def open_document(ref: str, connector: str | None = None):
    reg = registry()
    if connector:
        c = reg.get(connector)
        if not c or c.kind != "document":
            raise ValueError(f"No document connector named {connector!r}")
    else:
        c = next((c for c in reg.values() if c.kind == "document" and c.handles and c.handles(ref)), None)
        if c is None:
            raise ValueError(f"No connector can open {ref!r}. Run 'hanviet sources' to list supported inputs.")
    raw, blocks, warnings, provenance = c.open(ref)
    provenance = {**provenance, "connector": c.name}
    return raw, blocks, warnings, provenance

def search(source: str, query: str, language: str = "zh", limit: int = 10) -> list[dict]:
    c = registry().get(source)
    if not c or c.kind != "search":
        raise ValueError(f"No search connector named {source!r}")
    return c.search(query, language, limit)
