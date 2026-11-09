"""Rights-respecting scholarly discovery via public bibliographic APIs.

Search returns metadata only. No full-text harvesting, circumvention or factual
validation is performed by these adapters.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import ssl
from .store import save_json

def get_json(url: str) -> dict:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "HanVietBridge/0.1 (academic metadata research)"})
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except ImportError:
        pass
    with urlopen(req, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))

def search(query: str, source: str = "openalex", language: str = "zh", limit: int = 10) -> dict:
    if not query.strip() or len(query) > 500:
        raise ValueError("Query must be 1-500 characters")
    if limit < 1 or limit > 50:
        raise ValueError("Limit must be between 1 and 50")
    if language not in ("zh", "all"):
        raise ValueError("Language must be zh or all")
    if source == "openalex":
        params = {"search": query, "per_page": limit}
        if language == "zh":
            params["filter"] = "language:zh"
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        url = "https://api.openalex.org/works?" + urlencode(params)
        data = get_json(url)
        items = [{
            "provider": "openalex", "provider_id": item.get("id"),
            "title": item.get("title") or item.get("display_name"),
            "doi": item.get("doi"), "year": item.get("publication_year"),
            "language": item.get("language"), "url": item.get("id"),
            "is_oa": (item.get("open_access") or {}).get("is_oa"),
            "authors": [a.get("author",{}).get("display_name") for a in item.get("authorships",[])],
        } for item in data.get("results", [])]
    elif source == "crossref":
        params = {"query.bibliographic": query, "rows": limit}
        url = "https://api.crossref.org/works?" + urlencode(params)
        data = get_json(url)
        items = []
        for item in data.get("message",{}).get("items",[]):
            title = (item.get("title") or [""])[0]
            if language == "zh" and item.get("language") not in ("zh", "zh-CN", "zh-TW") and not any("\u4e00"<=c<="\u9fff" for c in title):
                continue
            items.append({
                "provider": "crossref", "provider_id": item.get("DOI"),
                "title": title, "doi": item.get("DOI"), "year": (item.get("published",{}).get("date-parts") or [[None]])[0][0],
                "language": item.get("language"), "url": item.get("URL"),
                "is_oa": None, "authors": [(a.get("given","")+" "+a.get("family","")).strip() for a in item.get("author",[])],
            })
    else:
        raise ValueError("Source must be openalex or crossref")
    return {"searched_utc": datetime.now(timezone.utc).isoformat(), "provider": source,
            "query": query, "language": language, "records": items, "total_returned": len(items),
            "provenance": "Provider metadata; source titles and abstracts may be incomplete. Verify at publisher/original.",
            "rights": "Metadata only; do not assume article full-text redistribution rights."}
