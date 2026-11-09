"""Command-line entry point. No paid API calls, crawling or publication by default."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .store import load_project, load_segments, save_json, save_text
from .ingest import ingest
from .translate import translate, PROVIDERS
from .qa import audit
from .explore import search
from .review import approve, revise, review_html
from . import export as exporters
from . import library as lib
from .sources import registry
from .sources.references import import_references

EXPORTS = {"md": exporters.markdown, "docx": exporters.docx, "epub": exporters.epub,
           "srt": exporters.subtitles, "vtt": exporters.subtitles}

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hanviet", description="Source-traceable Chinese -> Vietnamese reading, translation and research")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="List source connectors (built-in and plugins)")

    i = sub.add_parser("ingest", help="Import a file or URL into a source-linked workspace")
    i.add_argument("source", help="File path (txt/md/docx/epub/pdf/html/srt/vtt) or http(s) URL")
    i.add_argument("--workspace", required=True, type=Path)
    i.add_argument("--kind", default="book", choices=["book", "paper", "article", "subtitle"])
    i.add_argument("--connector", help="Force a specific document connector (see 'hanviet sources')")

    t = sub.add_parser("translate", help="Model translation (external services need --allow-external)")
    t.add_argument("--workspace", required=True, type=Path)
    t.add_argument("--provider", required=True, choices=list(PROVIDERS))
    t.add_argument("--model", required=True)
    t.add_argument("--base-url", help="Override endpoint (required for openai-compatible)")
    t.add_argument("--max-segments", type=int, default=1, help="0 = all pending segments")
    t.add_argument("--allow-external", action="store_true", help="Permit sending text to a remote API")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--glossary", type=Path)

    q = sub.add_parser("audit", help="Automated QA ledger (never replaces human review)")
    q.add_argument("--workspace", required=True, type=Path)
    q.add_argument("--glossary", type=Path)

    e = sub.add_parser("export", help="Reader output: md, docx, epub, srt/vtt, or html review page")
    e.add_argument("--workspace", required=True, type=Path)
    e.add_argument("--format", choices=list(EXPORTS) + ["html"], default="md")
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--bilingual", action="store_true", help="Chinese source under each Vietnamese passage")
    e.add_argument("--trace", action="store_true", help="Markdown: add segment ID/location comments")

    x = sub.add_parser("search", help="Search scholarly metadata (no full text)")
    x.add_argument("query")
    x.add_argument("--source", default="openalex")
    x.add_argument("--language", choices=["zh", "all"], default="zh")
    x.add_argument("--limit", type=int, default=10)
    x.add_argument("--out", type=Path, help="Save results with provenance as JSON")
    x.add_argument("--library", type=Path, help="Also add results to this research library")

    L = sub.add_parser("library", help="Research library: import citation exports, list, link, export RIS")
    Ls = L.add_subparsers(dest="action", required=True)
    li = Ls.add_parser("import", help="Import RIS / EndNote / NoteExpress exported from CNKI, Wanfang, VIP, SinoMed...")
    li.add_argument("file", type=Path)
    ll = Ls.add_parser("list")
    ll.add_argument("--query")
    lk = Ls.add_parser("link", help="Link a library record to a translation workspace")
    lk.add_argument("--record", required=True)
    lk.add_argument("--workspace", required=True, type=Path)
    lx = Ls.add_parser("export", help="Export records as RIS (Zotero/EndNote/Mendeley)")
    lx.add_argument("--out", type=Path, required=True)
    lx.add_argument("--query")
    for sp in (li, ll, lk, lx):
        sp.add_argument("--library", type=Path, default=Path("library"))

    s = sub.add_parser("status", help="Show project coverage and review state")
    s.add_argument("--workspace", required=True, type=Path)

    a = sub.add_parser("approve", help="Record a human review of one segment (bound to its current text)")
    a.add_argument("--workspace", required=True, type=Path)
    a.add_argument("--segment", required=True)
    a.add_argument("--reviewer", required=True)
    a.add_argument("--evidence", required=True)

    r = sub.add_parser("revise", help="Correct a translation; keeps previous text, reviewer, reason, severity")
    r.add_argument("--workspace", required=True, type=Path)
    r.add_argument("--segment", required=True)
    r.add_argument("--text", required=True)
    r.add_argument("--reviewer", required=True)
    r.add_argument("--reason", required=True)
    r.add_argument("--severity", choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    r.add_argument("--issue-code")
    return p

def run(args) -> object:
    c = args.command
    if c == "sources":
        return [{"name": k.name, "kind": k.kind, "access": k.access, "description": k.description,
                 "origin": k.origin, **({"notes": k.notes} if k.notes else {})} for k in registry().values()]
    if c == "ingest":
        return ingest(args.source, args.workspace, args.kind, args.connector)
    if c == "translate":
        return translate(args.workspace, args.provider, args.model, allow_external=args.allow_external,
                         dry_run=args.dry_run, limit=args.max_segments, glossary_path=args.glossary,
                         base_url=args.base_url)
    if c == "audit":
        return {k: v for k, v in audit(args.workspace, args.glossary).items() if k != "issues"}
    if c == "export":
        if args.format == "html":
            return {"file": str(review_html(args.workspace, args.out).resolve()), "kind": "review page"}
        out = EXPORTS[args.format](args.workspace, args.out, args.bilingual, args.trace)
        summary = exporters.review_summary(load_segments(args.workspace))
        return {"file": str(out.resolve()), "review": summary["status_line"]}
    if c == "search":
        result = search(args.query, args.source, args.language, args.limit)
        if args.out:
            save_json(args.out, result)
        if args.library:
            result["library"] = lib.add(args.library, result["records"],
                                        {"provider": args.source, "query": args.query})
        return result
    if c == "library":
        if args.action == "import":
            data = import_references(args.file)
            return lib.add(args.library, data["records"], {"file": data["file"], "format": data["format"]})
        if args.action == "list":
            return [{"id": r["id"], "year": r.get("year"), "title": r.get("title"), "doi": r.get("doi"),
                     "oa_url": r.get("oa_url"), "workspaces": r.get("workspaces")}
                    for r in lib.find(args.library, args.query)]
        if args.action == "link":
            return lib.link(args.library, args.record, args.workspace)
        if args.action == "export":
            records = lib.find(args.library, args.query)
            save_text(args.out, lib.to_ris(records))
            return {"file": str(args.out.resolve()), "records": len(records)}
    if c == "status":
        meta, segs = load_project(args.workspace), load_segments(args.workspace)
        count = lambda st: sum(s["status"] == st for s in segs)
        return {"source": meta["source_filename"], "source_sha256": meta["source_sha256"],
                "connector": (meta.get("provenance") or {}).get("connector"), "segments": len(segs),
                "pending": count("PENDING"), "draft": count("DRAFT"), "revised": count("REVISED"),
                "approved": count("APPROVED"), "review": exporters.review_summary(segs)["status_line"],
                "rights_status": meta["rights_status"], "warnings": meta.get("extraction_warnings", [])}
    if c == "approve":
        return approve(args.workspace, args.segment, args.reviewer, args.evidence)
    if c == "revise":
        return revise(args.workspace, args.segment, args.text, args.reviewer, args.reason,
                      args.severity, args.issue_code)
    raise RuntimeError("Unknown command")

def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(run(args), indent=2, ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, FileNotFoundError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
