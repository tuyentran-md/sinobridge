"""Fetch ONE public web page (WeChat article, Zhihu column, news, blog) and keep a snapshot.

Rules: one explicit URL per call, no crawling, robots.txt honored, no login/cookie reuse, no
anti-bot or paywall circumvention. For pages that need login, save the page from your own browser
(File > Save Page As > HTML) and ingest that file; you remain responsible for usage rights.
"""
from __future__ import annotations
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
import ssl
from .html_text import html_blocks, decode_html

USER_AGENT = "SinoBridge/0.2 (open-source translation toolkit; single-page fetch)"
MAX_BYTES = 8 * 1024 * 1024

def _context():
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return ctx

def robots_allows(url: str) -> bool | None:
    """True/False from robots.txt; None if robots.txt could not be read (treated as allowed)."""
    parts = urlparse(url)
    robots = RobotFileParser()
    try:
        req = Request(f"{parts.scheme}://{parts.netloc}/robots.txt", headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15, context=_context()) as r:
            robots.parse(r.read(512 * 1024).decode("utf-8", errors="replace").splitlines())
    except Exception:
        return None
    return robots.can_fetch(USER_AGENT, url)

def fetch(url: str) -> tuple[bytes, str | None, str]:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("URL must start with http:// or https://")
    if robots_allows(url) is False:
        raise RuntimeError(f"{parts.netloc} robots.txt disallows automated fetching of this page. "
                           "Open it in your browser, save as HTML, then ingest the saved file.")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(req, timeout=30, context=_context()) as r:
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise RuntimeError("Page larger than 8 MB; save it locally and ingest the file instead")
        return raw, r.headers.get_content_charset(), r.geturl()

def extract_url(url: str):
    raw, charset, final_url = fetch(url)
    blocks, title = html_blocks(decode_html(raw, charset))
    warnings = ["Fetched web page: verify that the article body (not comments/ads/menus) was captured",
                "Social/news content keeps its author's copyright; translate for private study or with permission"]
    if title:
        warnings.append(f"Page title: {title}")
    if len(blocks) < 2:
        warnings.append("Very little text extracted: the page may need login or render with JavaScript. "
                        "Save it from your browser and ingest the HTML file.")
    provenance = {"origin": "url", "url": url, "final_url": final_url, "title": title or None}
    return raw, blocks, warnings, provenance
