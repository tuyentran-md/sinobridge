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
from . import hanviet, terms as term_memory

EXPORTS = {"md": exporters.markdown, "docx": exporters.docx, "epub": exporters.epub,
           "srt": exporters.subtitles, "vtt": exporters.subtitles}

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sinobridge", description="Source-traceable Chinese -> English/Vietnamese reading, translation and research")
    sub = p.add_subparsers(dest="command", required=True)

    sv = sub.add_parser("serve", help="Local drag-and-drop web interface (no cloud account)")
    sv.add_argument("--open", action="store_true", help="Open default browser")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--data-dir", type=Path)

    sub.add_parser("sources", help="List source connectors (built-in and plugins)")

    i = sub.add_parser("ingest", help="Import a file or URL into a source-linked workspace")
    i.add_argument("source", help="File path (txt/md/docx/epub/pdf/html/srt/vtt) or http(s) URL")
    i.add_argument("--workspace", required=True, type=Path)
    i.add_argument("--kind", default="book", choices=["book", "paper", "article", "subtitle"])
    i.add_argument("--connector", help="Force a specific document connector (see 'sinobridge sources')")
    i.add_argument("--target", default="vi", choices=["vi", "en"], help="Target language: vi (Vietnamese) or en (English)")

    t = sub.add_parser("translate", help="Model translation (external services need --allow-external)")
    t.add_argument("--workspace", required=True, type=Path)
    t.add_argument("--provider", required=True, choices=list(PROVIDERS))
    t.add_argument("--model", default="", help="Model name; for chatgpt/google accounts omit it to use the account default")
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

    nm = sub.add_parser("name", help="Render Chinese names: --to vi (Hán-Việt) or --to en (pinyin / English form)")
    nm.add_argument("text", nargs="+")
    nm.add_argument("--to", default="vi", choices=["vi", "en"])
    nm.add_argument("--type", default="person", choices=["person", "place", "other"])

    h = sub.add_parser("hanviet", help="Hán-Việt for Chinese names/terms (诸葛亮 -> Gia Cát Lượng)")
    h.add_argument("text", nargs="+")
    h.add_argument("--lower", action="store_true", help="Do not capitalize (terms rather than names)")

    tm = sub.add_parser("terms", help="Project term memory: names/terms with one agreed rendering")
    tms = tm.add_subparsers(dest="action", required=True)
    tl = tms.add_parser("list")
    tl.add_argument("--status", choices=["auto", "locked"])
    tset = tms.add_parser("set", help="Lock a rendering (enforced in translation and audit)")
    tset.add_argument("zh")
    tset.add_argument("render", help="Agreed rendering in the workspace's target language")
    tset.add_argument("--type", default="term", choices=["person", "place", "org", "dynasty", "work", "era", "term"])
    tset.add_argument("--note")
    trm = tms.add_parser("remove")
    trm.add_argument("zh")
    tsc = tms.add_parser("scan", help="Find known Chinese names in the source and suggest Hán-Việt (no model)")
    for sp in (tl, tset, trm, tsc):
        sp.add_argument("--workspace", required=True, type=Path)

    dt = sub.add_parser("data", help="Optional data: fetch the full CVDICT dictionary (CC BY-SA 4.0)")
    dt.add_argument("action", choices=["fetch", "info"])

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
        return ingest(args.source, args.workspace, args.kind, args.connector, args.target)
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
        summary = exporters.review_summary(load_segments(args.workspace),
                                           exporters.lang_of(load_project(args.workspace)))
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
    if c == "name":
        from .names import render_name
        out = [render_name(t, args.type, args.to) for t in args.text]
        return out[0] if len(out) == 1 else out
    if c == "hanviet":
        results = [hanviet.transliterate(t, capitalize=not args.lower) for t in args.text]
        for r in results:
            glosses = hanviet.dictionary_glosses(r["zh"]) if hanviet.dictionary() else []
            if glosses:
                r["meanings"] = glosses
        return results[0] if len(results) == 1 else results
    if c == "terms":
        if args.action == "list":
            return {zh: t for zh, t in term_memory.load(args.workspace).items()
                    if not args.status or t.get("status") == args.status}
        if args.action == "set":
            return term_memory.set_term(args.workspace, args.zh, args.render, args.type, args.note)
        if args.action == "remove":
            return term_memory.remove_term(args.workspace, args.zh)
        if args.action == "scan":
            found = {}
            target = load_project(args.workspace).get("target_language", "vi")
            for seg in load_segments(args.workspace):
                for zh, r in term_memory.name_hints(seg["source"], target).items():
                    found.setdefault(zh, {"render": r, "first_segment": seg["id"], "count": 0})["count"] += 1
            return dict(sorted(found.items(), key=lambda kv: -kv[1]["count"]))
    if c == "data":
        if args.action == "fetch":
            return hanviet.fetch_dictionary()
        return {"bundled": [str(hanviet.DATA), str(hanviet.WORDS)], "cvdict_cache": str(hanviet.cache_dir() / "CVDICT.u8"),
                "cvdict_present": bool(hanviet.dictionary()),
                "licenses": "Bundled data CC BY-SA 4.0 (Wiktionary, CVDICT) + Unicode Unihan; code MIT"}
    if c == "status":
        meta, segs = load_project(args.workspace), load_segments(args.workspace)
        count = lambda st: sum(s["status"] == st for s in segs)
        return {"source": meta["source_filename"], "source_sha256": meta["source_sha256"],
                "connector": (meta.get("provenance") or {}).get("connector"), "segments": len(segs),
                "pending": count("PENDING"), "draft": count("DRAFT"), "revised": count("REVISED"),
                "approved": count("APPROVED"), "target_language": meta.get("target_language", "vi"),
                "review": exporters.review_summary(segs, exporters.lang_of(meta))["status_line"],
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
        if args.command == "serve":
            from .webapp import main as serve_main
            options = ["--port", str(args.port)]
            if args.open:
                options.append("--open")
            if args.data_dir:
                options += ["--data-dir", str(args.data_dir)]
            return serve_main(options)
        print(json.dumps(run(args), indent=2, ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, FileNotFoundError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
