"""Rights-respecting scholarly discovery via public bibliographic APIs.

Search returns metadata (and open-access links when the provider knows them). No full-text
harvesting, circumvention or factual validation is performed by these adapters.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ssl

def get_json(url: str) -> dict:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "HanVietBridge/0.2 (scholarly metadata)"})
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    with urlopen(req, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def openalex_abstract(inverted: dict | None) -> str | None:
    if not inverted:
        return None
    words = sorted((pos, word) for word, positions in inverted.items() for pos in positions)
    text = " ".join(w for _, w in words)
    # Chinese abstracts are tokenized by OpenAlex; drop spaces between CJK characters
    import re
    return re.sub(r"(?<=[　-鿿＀-￯]) (?=[　-鿿＀-￯])", "", text)

def search_openalex(query: str, language: str = "zh", limit: int = 10) -> list[dict]:
    params = {"search": query, "per_page": limit}
    if language == "zh":
        params["filter"] = "language:zh"
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    data = get_json("https://api.openalex.org/works?" + urlencode(params))
    out = []
    for item in data.get("results", []):
        oa = item.get("open_access") or {}
        loc = item.get("primary_location") or {}
        out.append({
            "provider": "openalex", "provider_id": item.get("id"),
            "title": item.get("title") or item.get("display_name"),
            "doi": (item.get("doi") or "").replace("https://doi.org/", "") or None,
            "year": item.get("publication_year"), "language": item.get("language"),
            "journal": (loc.get("source") or {}).get("display_name"),
            "url": item.get("id"), "is_oa": oa.get("is_oa"), "oa_url": oa.get("oa_url"),
            "abstract": openalex_abstract(item.get("abstract_inverted_index")),
            "authors": [(a.get("author") or {}).get("display_name") for a in item.get("authorships", [])],
        })
    return out

def search_crossref(query: str, language: str = "zh", limit: int = 10) -> list[dict]:
    data = get_json("https://api.crossref.org/works?" + urlencode({"query.bibliographic": query, "rows": limit}))
    out = []
    for item in data.get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0]
        if language == "zh" and item.get("language") not in ("zh", "zh-CN", "zh-TW") \
                and not any("一" <= c <= "鿿" for c in title):
            continue
        out.append({
            "provider": "crossref", "provider_id": item.get("DOI"), "title": title, "doi": item.get("DOI"),
            "year": (item.get("published", {}).get("date-parts") or [[None]])[0][0],
            "language": item.get("language"), "journal": (item.get("container-title") or [None])[0],
            "url": item.get("URL"), "is_oa": None, "oa_url": None, "abstract": None,
            "authors": [(a.get("given", "") + " " + a.get("family", "")).strip() for a in item.get("author", [])],
        })
    return out

def search(query: str, source: str = "openalex", language: str = "zh", limit: int = 10) -> dict:
    if not query.strip() or len(query) > 500:
        raise ValueError("Query must be 1-500 characters")
    if limit < 1 or limit > 50:
        raise ValueError("Limit must be between 1 and 50")
    if language not in ("zh", "all"):
        raise ValueError("Language must be zh or all")
    from .sources import search as connector_search
    items = connector_search(source, query, language, limit)
    return {"searched_utc": datetime.now(timezone.utc).isoformat(), "provider": source,
            "query": query, "language": language, "records": items, "total_returned": len(items),
            "provenance": "Provider metadata; titles and abstracts may be incomplete. Verify at publisher/original.",
            "rights": "Metadata only; do not assume article full-text redistribution rights."}
