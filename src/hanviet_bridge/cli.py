"""Command-line entry point. No paid API calls or public releases by default."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .store import load_project, load_segments, save_json, save_segments
from .ingest import ingest
from .translate import translate
from .qa import audit
from .explore import search
from . import export as exporters
from .review import approve, revise, review_html

def main(argv=None):
    p = argparse.ArgumentParser(prog="hanviet", description="Source-linked Chinese->Vietnamese translation and research metadata")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("ingest", help="Extract a document into a source-linked project")
    i.add_argument("source", type=Path)
    i.add_argument("--workspace", required=True, type=Path)
    i.add_argument("--kind", required=True, choices=["book", "paper"])
    t = sub.add_parser("translate", help="AI translation (explicit paid/external opt-in)")
    t.add_argument("--workspace", required=True, type=Path)
    t.add_argument("--provider", required=True, choices=["openai", "gemini"])
    t.add_argument("--model", required=True)
    t.add_argument("--max-segments", type=int, default=1)
    t.add_argument("--allow-external", action="store_true")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--glossary", type=Path)
    q = sub.add_parser("audit", help="Automated QA (never replaces semantic/human review)")
    q.add_argument("--workspace", required=True, type=Path)
    q.add_argument("--glossary", type=Path)
    e = sub.add_parser("export", help="Produce INTERNAL DRAFT only")
    e.add_argument("--workspace", required=True, type=Path)
    e.add_argument("--format", choices=["md", "epub", "docx", "html"], default="md",
                   help="html = offline bilingual review page (click Vietnamese -> Chinese source, issues, history)")
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--draft", action="store_true", help="Explicitly acknowledge unreviewed draft output")
    e.add_argument("--bilingual", action="store_true")
    x = sub.add_parser("search", help="Retrieve scholarly metadata, not full text")
    x.add_argument("query")
    x.add_argument("--source", choices=["openalex", "crossref"], default="openalex")
    x.add_argument("--language", choices=["zh", "all"], default="zh")
    x.add_argument("--limit", type=int, default=10)
    x.add_argument("--out", type=Path, help="Save retrieved metadata with provenance")
    s = sub.add_parser("status", help="Show honest current project coverage")
    s.add_argument("--workspace", required=True, type=Path)
    a = sub.add_parser("approve", help="Record a human-reviewed segment decision")
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
    args = p.parse_args(argv)
    try:
        if args.command == "ingest":
            result = ingest(args.source, args.workspace, args.kind)
        elif args.command == "translate":
            result = translate(args.workspace, args.provider, args.model, allow_external=args.allow_external,
                               dry_run=args.dry_run, limit=args.max_segments, glossary_path=args.glossary)
        elif args.command == "audit":
            result = audit(args.workspace, args.glossary)
            result = {key:value for key,value in result.items() if key != "issues"}
        elif args.command == "export":
            if args.format == "html":
                result = {"file": str(review_html(args.workspace, args.out).resolve()), "status": "DRAFT_REVIEW_PAGE"}
            else:
                fn = {"md": exporters.markdown, "docx": exporters.docx, "epub": exporters.epub}[args.format]
                result = {"file": str(fn(args.workspace, args.out, args.bilingual, args.draft).resolve()), "status": "DRAFT"}
        elif args.command == "search":
            result = search(args.query, args.source, args.language, args.limit)
            if args.out:
                save_json(args.out, result)
        elif args.command == "status":
            meta, segs = load_project(args.workspace), load_segments(args.workspace)
            result = {"source": meta["source_filename"], "source_sha256": meta["source_sha256"],
                      "segments": len(segs), "pending": sum(s["status"]=="PENDING" for s in segs),
                      "draft": sum(s["status"]=="DRAFT" for s in segs),
                      "revised": sum(s["status"]=="REVISED" for s in segs),
                      "approved": sum(s["status"]=="APPROVED" for s in segs),
                      "review_status": meta["review_status"], "rights_status": meta["rights_status"]}
        elif args.command == "approve":
            result = approve(args.workspace, args.segment, args.reviewer, args.evidence)
        elif args.command == "revise":
            result = revise(args.workspace, args.segment, args.text, args.reviewer, args.reason,
                            args.severity, args.issue_code)
        else:
            raise RuntimeError("Unknown command")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, FileNotFoundError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
