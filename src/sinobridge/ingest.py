"""Turn any supported source (file, URL, plugin connector) into a source-anchored workspace."""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from .sources import open_document
from .sources.files import extract_file as extract  # backwards-compatible name
from .store import sha256, save_json, save_segments, load_project

TARGETS = ("vi", "en")

def ingest(source, workspace: Path, kind: str, connector: str | None = None, target: str = "vi") -> dict:
    if kind not in ("book", "paper", "article", "subtitle"):
        raise ValueError("--kind must be book, paper, article or subtitle")
    if target not in TARGETS:
        raise ValueError("--target must be vi (Vietnamese) or en (English)")
    ref = str(source)
    workspace = workspace.expanduser().resolve()
    raw, blocks, warnings, provenance = open_document(ref, connector)
    checksum = sha256(raw)
    if (workspace / "project.json").exists():
        old = load_project(workspace)
        if old["source_sha256"] != checksum or old["kind"] != kind or old.get("target_language", "vi") != target:
            raise RuntimeError("Workspace has a different source/revision; choose a NEW workspace to protect existing translations")
        return old
    if not blocks:
        raise RuntimeError("No text blocks extracted. Check scanned document/OCR and source format.")
    if provenance.get("origin") == "url":
        # keep the exact bytes that were translated: web pages change or disappear
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "source_snapshot.html").write_bytes(raw)
        provenance["snapshot"] = "source_snapshot.html"
    entries = [{
        "id": sha256((location + "\0" + text).encode("utf-8"))[:16],
        "location": location, "kind": block_kind, "source": text,
        "translation": None, "status": "PENDING", "ambiguities": [], "notes": [],
    } for location, block_kind, text in blocks]
    name = provenance.get("filename") or provenance.get("title") or provenance.get("url") or ref
    meta = {
        "schema_version": 2, "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind": kind, "source_filename": name, "source_sha256": checksum, "provenance": provenance,
        "source_language": "zh", "target_language": target,
        "segment_count": len(entries), "extraction_warnings": warnings,
        "review_status": "NOT_REVIEWED", "rights_status": "UNVERIFIED",
    }
    save_segments(workspace, entries)
    save_json(workspace / "project.json", meta)
    return meta
