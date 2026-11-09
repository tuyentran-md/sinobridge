# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences in equal measure (owner-confirmed): general readers of Chinese books, fiction, news and social posts, and researchers/students reading Chinese papers (e.g. CNKI exports) who need numbers and terminology preserved. Most users read Vietnamese; English is the second target for international users.

## Product Purpose

SinoBridge turns Chinese documents (EPUB, text-layer PDF, DOCX, TXT, Markdown, HTML, subtitles) into clean Vietnamese or English drafts that can be read side by side with the source and exported as EPUB, Word, bilingual HTML or text. Success: a non-technical person drops a file, presses one button and reads a usable bilingual draft within minutes.

## Positioning

Open-source, bring-your-own-model translation that is anchored to the source passage by passage: every translated segment keeps its Chinese original, so the result is a bilingual reading/checking document rather than an opaque machine dump. The full app adds Hán-Việt transliteration, term memory and numeric QA.

## Operating Context

- Public static web demo on GitHub Pages (`web/`): no backend; files are read in the browser and progress is saved in IndexedDB.
- Model connection (owner-confirmed 2026-11-09): the user's own API key is the default path, with a free Google AI Studio Gemini key recommended first; OpenAI, OpenRouter, DeepSeek and Qwen (DashScope) keys are also accepted. All five accept direct browser requests (CORS preflight checked 2026-11-09). An in-browser WebGPU model (Qwen 2.5 via WebLLM) remains the no-key fallback.
- Local Python app (`sinobridge serve`) and CLI for heavier work.

## Capabilities and Constraints

- Targets: Vietnamese, English. Interface copy currently Vietnamese.
- No server ever receives the document or the key; keys go only to the chosen provider.
- Scanned PDFs need OCR elsewhere; complex layout, tables and footnotes are not preserved.
- Outputs are drafts; no claim of professional or scientific validation.
- The owner does not want Ollama installed on their machine (it stays an option for others in the CLI).

## Brand Commitments

- Name: SinoBridge (wordmark "Sino" + "Bridge"). License MIT.
- The owner rejects designs that feel bland/monotonous or interchangeable with generic AI sites (owner-confirmed 2026-11-09).
- First screen behaves like an app: drop file, choose model, translate and read bilingual output without scrolling (owner-confirmed 2026-11-09).

## Evidence on Hand

- Synthetic sample: `examples/synthetic_zh.md`, `examples/demo_article_zh.md` (synthetic; label as such).
- No user testimonials, usage numbers or benchmarks exist; do not invent them.

## Product Principles

1. Source stays visible: every translation is shown next to its Chinese original.
2. One obvious path: file → model → translate → read/export.
3. Honest about drafts and limits; never imply professional accuracy.
4. The user's data and key stay between the user's browser and the provider they chose.
