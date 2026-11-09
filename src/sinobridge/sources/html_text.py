"""Stdlib HTML -> ordered text blocks. Used for EPUB chapters, saved web pages and fetched URLs."""
from __future__ import annotations
from html.parser import HTMLParser
import re

BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "blockquote", "td", "th", "tr", "dd", "dt",
              "h1", "h2", "h3", "h4", "h5", "h6", "pre", "figcaption", "caption", "ul", "ol", "table", "body"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "button",
             "iframe", "template", "select", "head"}
VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}

# Elements dropped wherever they appear (by class substring): navigation boxes, edit links,
# reference markers, share/comment widgets.
SKIP_CLASSES = ("navbox", "mw-editsection", "reference", "noprint", "catlinks", "mw-jump-link",
                "metadata", "sistersitebox", "sidebar", "hatnote", "ambox")

# Known article containers, tried in order. (attribute, value-substring) or ("tag", name).
CONTAINERS = [
    ("id", "js_content"),            # WeChat Official Account articles (mp.weixin.qq.com)
    ("class", "mw-parser-output"),   # Wikipedia / MediaWiki
    ("class", "RichText"),           # Zhihu answers / columns
    ("class", "article-content"),    # many Chinese news/CMS sites
    ("class", "weibo-text"),         # Weibo mobile
    ("tag", "article"),
    ("tag", "main"),
]

class _Blocks(HTMLParser):
    def __init__(self, container=None):
        super().__init__(convert_charrefs=True)
        self.container = container
        self.inside = 0 if container else 1   # depth inside the chosen container (1 = whole page)
        self.root_tag = None
        self.skip = 0
        self.stack: list[tuple[str, bool]] = []   # (tag, opened a skip region)
        self.buf: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self.in_title = False

    def _matches(self, tag, attrs):
        if not self.container:
            return False
        key, value = self.container
        if key == "tag":
            return tag == value
        attr = dict(attrs).get(key) or ""
        return value in (attr.split() if key == "class" else [attr]) or (key == "class" and value in attr)

    def flush(self):
        text = re.sub(r"[ \t\r\f\v 　]+", " ", "".join(self.buf))
        text = "\n".join(line.strip() for line in text.split("\n")).strip()
        self.buf = []
        if text and self.inside:
            heading = any(t in HEADINGS for t, _ in self.stack[-3:])
            self.blocks.append(("heading" if heading else "paragraph", text))

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if self.container and not self.inside and self._matches(tag, attrs):
            self.flush()
            self.inside, self.root_tag, self.skip = 1, tag, 0  # the article body wins over wrappers
            self.stack.append((tag, False))
            return
        if tag in VOID:
            if tag == "br" and not self.skip:
                self.buf.append("\n")
            return
        classes = dict(attrs).get("class") or ""
        skipping = tag in SKIP_TAGS or any(c in classes for c in SKIP_CLASSES)
        if self.inside and self.root_tag and tag == self.root_tag:
            self.inside += 1
        if tag in BLOCK_TAGS and not self.skip:
            self.flush()
        if skipping:
            self.skip += 1
        self.stack.append((tag, skipping))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in VOID:
            return
        if tag in BLOCK_TAGS and not self.skip:
            self.flush()
        if any(t == tag for t, _ in self.stack):
            while self.stack:
                t, skipped = self.stack.pop()
                if skipped:
                    self.skip = max(0, self.skip - 1)
                if t == tag:
                    break
        if self.root_tag and tag == self.root_tag and self.inside:
            self.inside -= 1

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if not self.skip and self.inside:
            self.buf.append(data)

    def close(self):
        super().close()
        self.flush()

def choose_container(html: str):
    for key, value in CONTAINERS:
        if key == "tag":
            if re.search(rf"<{value}[\s>]", html, re.I):
                return (key, value)
        elif re.search(rf'{key}\s*=\s*["\'][^"\']*\b{re.escape(value)}\b', html, re.I):
            return (key, value)
    return None

def html_blocks(html: str, prefix: str = "", detect_container: bool = True):
    """Return ([(location, kind, text)], title). Locations are `<prefix>block:N` (1-based)."""
    container = choose_container(html) if detect_container else None
    parser = _Blocks(container)
    parser.feed(html)
    parser.close()
    blocks = parser.blocks
    if container and not blocks:  # container matched in an attribute string only; fall back to page
        parser = _Blocks(None)
        parser.feed(html)
        parser.close()
        blocks = parser.blocks
    title = " ".join("".join(parser.title_parts).split())
    return [(f"{prefix}block:{i}", kind, text) for i, (kind, text) in enumerate(blocks, 1)], title

def decode_html(raw: bytes, declared: str | None = None) -> str:
    """Decode bytes using the declared/meta charset; Chinese sites still use GBK/GB18030."""
    candidates = [declared] if declared else []
    meta = re.search(rb'<meta[^>]+charset=["\']?([A-Za-z0-9_\-]+)', raw[:4096], re.I)
    if meta:
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "gb18030"]
    for enc in candidates:
        try:
            enc = "gb18030" if enc and enc.lower() in ("gb2312", "gbk") else enc
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError, TypeError):
            continue
    return raw.decode("utf-8", errors="replace")
