# Architecture

```
sources/ (connectors) ─► ingest ─► workspace/ ─► translate ─► audit ─► review (revise/approve) ─► export
   file, url, plugins        project.json        provider       qa.json     history[], approval     md/docx/epub/srt/html
   openalex, crossref ─► library/library.jsonl (records ↔ workspaces)
```

- **sources/**: `Connector` registry. Document connectors return source-anchored blocks plus the exact raw bytes
  (SHA-256 = source revision). Search connectors return bibliographic records. Plugins via entry points.
- **workspace**: `project.json` (provenance, checksum, warnings), `segments.jsonl` (one line per passage: id, location,
  source, translation, status, model, ambiguities, notes, history, approval), `qa.json`, `source_snapshot.html` for URLs.
  A changed source requires a new workspace, so old translations and audits are never overwritten.
- **translate**: one passage at a time with two previous passages as context and the glossary; checkpoint after each
  passage. OpenAI-compatible providers + Gemini; local endpoints need no external-transfer flag.
- **qa**: deterministic checks → issue ledger (CRITICAL/HIGH/MEDIUM/LOW) and conservative G1–G11 gate states.
- **review**: append-only revisions; approvals store a hash of the approved text and lapse if it changes.
- **export**: clean reader outputs; review status stated once in the colophon; anchors keep segment IDs.
- **library**: deduplicated records (DOI or normalized title+year) with every place they were found.
