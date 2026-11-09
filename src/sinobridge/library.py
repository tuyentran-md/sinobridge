"""Research library: one JSONL file of deduplicated records, each traceable to where it came from
(search query or citation export) and, once ingested, to the translation workspace."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from .store import save_text, sha256

def _norm_title(title: str | None) -> str:
    return re.sub(r"[\W_]+", "", (title or "").lower())

def record_key(rec: dict) -> str:
    if rec.get("doi"):
        return "doi:" + rec["doi"].lower()
    return "t:" + sha256((_norm_title(rec.get("title")) + str(rec.get("year") or "")).encode())[:16]

def load(library: Path) -> list[dict]:
    path = library / "library.jsonl"
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

def save(library: Path, records: list[dict]) -> None:
    save_text(library / "library.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))

def add(library: Path, records: list[dict], how: dict) -> dict:
    """Merge records; existing entries gain missing fields and a new provenance entry."""
    lib = load(library)
    index = {r["key"]: r for r in lib}
    added = merged = 0
    stamp = {**how, "utc": datetime.now(timezone.utc).isoformat()}
    for rec in records:
        key = record_key(rec)
        clean = {k: v for k, v in rec.items() if v not in (None, "", [])}
        if key in index:
            cur = index[key]
            for k, v in clean.items():
                cur.setdefault(k, v)
            cur["found_via"].append(stamp)
            merged += 1
        else:
            entry = {"key": key, "id": sha256(key.encode())[:10], **clean, "found_via": [stamp], "workspaces": []}
            lib.append(entry)
            index[key] = entry
            added += 1
    save(library, lib)
    return {"library": str(library), "added": added, "merged_duplicates": merged, "total": len(lib)}

def link(library: Path, record_id: str, workspace: Path) -> dict:
    lib = load(library)
    rec = next((r for r in lib if r["id"] == record_id), None)
    if rec is None:
        raise RuntimeError(f"Record {record_id} not in library")
    ws = str(workspace.expanduser().resolve())
    if ws not in rec["workspaces"]:
        rec["workspaces"].append(ws)
    save(library, lib)
    return {"record": record_id, "title": rec.get("title"), "workspaces": rec["workspaces"]}

def find(library: Path, query: str | None = None) -> list[dict]:
    lib = load(library)
    if not query:
        return lib
    q = query.lower()
    return [r for r in lib if q in " ".join(str(r.get(k) or "") for k in ("title", "abstract", "journal", "doi")).lower()
            or any(q in (a or "").lower() for a in r.get("authors", []) + r.get("keywords", []))]

def to_ris(records: list[dict]) -> str:
    """RIS for Zotero / EndNote / Mendeley."""
    out = []
    for r in records:
        lines = ["TY  - " + ("JOUR" if r.get("journal") else "GEN"), f"TI  - {r.get('title') or ''}"]
        lines += [f"AU  - {a}" for a in r.get("authors", []) if a]
        for tag, key in (("PY", "year"), ("JO", "journal"), ("DO", "doi"), ("UR", "oa_url"),
                         ("AB", "abstract"), ("LA", "language"), ("VL", "volume"), ("IS", "issue")):
            if r.get(key):
                lines.append(f"{tag}  - {r[key]}")
        lines += [f"KW  - {k}" for k in r.get("keywords", [])]
        lines.append(f"N1  - sinobridge library id {r['id']}; found via " +
                     ", ".join(f.get('provider') or f.get('file') or '?' for f in r["found_via"]))
        out.append("\n".join(lines) + "\nER  - \n")
    return "\n".join(out)
