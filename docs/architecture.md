# Architecture

Ingest → immutable source-anchored segments and checksum.
Translate → limited context window + optional glossary + one opted-in model, checkpoint per segment.
QA → deterministic checks, 4-severity issue ledger, conservative G1–G11 states.
Explorer → metadata-only scholarly provider adapters with dated query provenance.
Export → clearly labeled internal reading drafts in Markdown, DOCX and minimal EPUB3.

Extension points: ingest.extract (JATS, OCR, rich PDF); translate.call_model (offline models); qa.check_segment (scientific semantic review); explore.search (licensed sources and import); export (Pandoc, EPUBCheck, visual testing).

Translation copyright, model privacy consent and publication rights are separate approval gates.
