# HanViet Bridge

**Source-traceable Chinese → Vietnamese translation and Chinese-language scholarly discovery.**

A reusable, open-source-ready Python CLI. Initial scope: help translate permitted documents, audit transfer errors, generate clearly labeled **drafts**, and search public scholarly metadata. The app does **not** claim professional translation, factual verification, or publishing readiness.

## Three workflows

1. **Book** — import permitted Chinese TXT/Markdown/DOCX/EPUB/PDF, translate with paragraph context and glossary, produce bilingual Markdown and draft EPUB.
2. **Academic paper** — preserve source-linked passage IDs; check numbers, DOI, citation tokens, and China-specific terms. Tables, equations, images and PDF reading order still need manual inspection.
3. **Research explorer** — search bibliographic records via [OpenAlex](https://help.openalex.org/api/) or [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), save metadata plus provenance. CNKI/Wanfang/VIP/SinoMed full-text access is **not implemented** and must honor provider rights.

All generated projects live outside Git by default (workspace/ is ignored). The repo includes no private input documents or API keys.

## Quick start

Python 3.10+. At the repository root:

    python3 -m venv .venv
    .venv/bin/pip install -e .
    hanviet ingest examples/synthetic_zh.md --workspace workspace/demo --kind paper
    hanviet status --workspace workspace/demo
    hanviet translate --workspace workspace/demo --provider gemini --model YOUR_AVAILABLE_MODEL --dry-run
    hanviet audit --workspace workspace/demo
    hanviet export --workspace workspace/demo --format md --out outputs/demo_draft.md --draft --bilingual

No model request occurs until --allow-external is supplied with a configured key. **Never send patient-identifiable or confidential manuscripts to unapproved remote models.**

Translate **one segment** through an approved provider:

    export GEMINI_API_KEY="..."
    hanviet translate --workspace workspace/demo --provider gemini --model YOUR_AVAILABLE_MODEL --max-segments 1 --allow-external

Alternatively use --provider openai with OPENAI_API_KEY and an accessible model.
Browser subscriptions and model entitlements do not automatically provide API access.
A --max-segments value of 0 means all pending segments, potentially with significant API costs.

Draft exports and mechanical QA:

    hanviet audit --workspace workspace/demo --glossary examples/glossary.sample.json
    hanviet export --workspace workspace/demo --format epub --out outputs/book_draft.epub --draft
    hanviet export --workspace workspace/demo --format docx --out outputs/paper_draft.docx --draft

DOCX export requires python-docx; PDF extraction requires PyMuPDF (pip install -e '.[pdf]').
PDF scans are not OCR'd. EPUB export is a basic reading draft, not EPUBCheck-certified or visually validated.

Bilingual review page and traceable corrections:

    hanviet export --workspace workspace/demo --format html --out outputs/review.html
    hanviet revise --workspace workspace/demo --segment SEGMENT_ID --text "Bản sửa" \
        --reviewer "Name" --reason "Wrong number 58 -> 85" --severity HIGH --issue-code NUMERIC_MISMATCH
    hanviet approve --workspace workspace/demo --segment SEGMENT_ID --reviewer "Name" --evidence "Read against source"

The HTML page is a single offline file (no server, no network). Click any Vietnamese passage to see the exact
Chinese source passage, its location, audit flags, ambiguities/notes, approval and revision history.
Revisions are append-only (previous text, reviewer, reason, severity). An approval is bound to a hash of the
approved text; if the translation changes afterwards, audit raises STALE_APPROVAL and the approval no longer counts.

Numeric QA compares values, not strings: 1.25 = 1,25 (Vietnamese decimal comma), 1,200 = 1.200, full-width digits
and simple Chinese numerals (一百二十 = 120) are matched. A changed value (5% -> 50%) is flagged HIGH.

Find Chinese-language research metadata:

    hanviet search "小儿肛门直肠畸形" --source openalex --language zh --limit 5 --out outputs/chinese_papers.json
    hanviet search "肛门直肠畸形" --source crossref --language zh --limit 5

Crossref results are filtered client-side and can be sparse. Both services can miss local Chinese-language studies.

## Output and provenance

- project.json — source checksum, type, warnings, source/target language and review/rights status.
- segments.jsonl — source, source location, stable segment ID, draft translation, model and explicit human approval.
- qa.json — issue ledger, severity, eleven gate states, and release-readiness blocked pending review.
- outputs/ — explicitly requested artifacts only, ignored by Git.

If source content changes, use a **new workspace** to preserve the old translation and audit. Model results are saved after each successful segment.

## Eleven editorial gates

G1 Chinese semantics; G2 Vietnamese fluency; G3 sentence completeness; G4 paragraph coherence; G5 style; G6 terminology; G7 science and numeric fidelity; G8 Chinese vs Vietnamese jurisdiction; G9 structural completeness; G10 full-chapter reading; G11 independent adversarial review.

**Critical caveat:** automated checks can only provide partial evidence for G6–G9. No automatic PASS is issued for semantic or scientific accuracy. Even a zero-issue audit does not authorize public release. Read [QA policy](docs/qa-policy.md).

## Security, provenance and rights

- No source books or paywalled papers distributed, only synthetic example text.
- Check ownership and translation/redistribution rights before exporting or sharing translated content. Translation does not extinguish source copyright.
- Research module fetches metadata, not bulk full text, copyrighted figures, or paywalled provider documents.
- Every paragraph retains source location and ID, but flattened figures/tables still need human comparison.
- Paid API calls require explicit opt-in. No credentials are logged or committed.
- Never use translated medical findings for clinical conclusions without independent primary-source reading.
- No automatic Git commits, pushes, deployments, releases or background tasks.

## Inspiration and attribution

Workflow inspiration: the public [How To Live Better Chinese-to-Vietnamese translation prompt](https://thuongtin.notion.site/Prompt-d-ch-How-To-Live-Better-t-ti-ng-Trung-sang-ti-ng-Vi-t-41172ac96186819dae67c730db8d7152), and [thuongtin/HowToLiveBetter](https://github.com/thuongtin/HowToLiveBetter) (upstream repo displayed CC BY 4.0 in November 2026). We adapted the general notions of fidelity, fluency, staged QA and provenance; **we do not copy the book or upstream source**. The toolkit's code is independently implemented and MIT licensed.

## Planned features (not implemented)

- Robust scientific PDF layout, table/formula OCR, cell/page provenance, JATS and RIS.
- Chapter-wide glossary consistency, in-browser editing (review page is read-only; corrections via `revise`), manual adjudication.
- Independent model reviewer and human-locked release gates.
- Publication EPUB3 (TOC, cover, layout, EPUBCheck, visual and device QA).
- Rights-respecting licensed catalog adapters for CNKI/Wanfang/VIP/SinoMed.
- Local model integration and source-cited RAG; complete research provenance and citation checks.

## Verification

    python3 -m unittest discover -s tests -v
    python3 -m compileall -q src

**Status:** v0.1 local prototype (+ review page, revision history); not yet pushed or published.
