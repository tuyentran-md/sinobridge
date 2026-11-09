# SinoBridge in the browser

A static GitHub Pages application for Chinese-to-Vietnamese/English book and document translation. There is no hosted SinoBridge translation backend or shared service account. Each reader supplies their own file and model access.

## Read, translate, stop and resume

1. Import an EPUB, text-based PDF, DOCX, TXT, Markdown or HTML file, or open the synthetic sample.
2. Choose Vietnamese or English and a model connection below. Click **Bắt đầu dịch**.
3. Read **Bản dịch**, **Song ngữ** or **Bản gốc**. Only 200 passages are rendered at once; Previous/Next and a page-number field navigate the book. These are reading pages, not original PDF page numbers.
4. **Dừng** stops the browser run. Completed batches are committed before the next batch starts. Choose the saved title in the library and click **Dịch tiếp** to skip already translated passages.
5. Click the SinoBridge logo or **Trang chủ** to return home without deleting the library. Home stays home after reload; choose a saved title explicitly to reopen it. Returning home during translation does not cancel the run.
6. Download draft EPUB, DOCX, TXT or bilingual HTML, including partial translations. Untranslated passages retain their Chinese text with a marker. Exported reading files are not restorable checkpoints.

## What it adds to pasting text into a chat

The app splits and queues passages, preserves source order, pairs originals with translations, saves completed work and assembles downloadable files. It does not provide its own translation model or guarantee better translations than the same model in chat.

`src/engine.js` sends numbered batches of roughly 2,400 source characters or at most 12 passages, with two preceding source passages as short context. It does not send or remember the whole book in one model context. Incomplete numbered answers trigger retries for missing passages. The browser version does not include the CLI's terminology memory, numeric/citation QA or human-review history.

## Model connections

- **Own API key (public default):** Gemini, OpenAI, OpenRouter, DeepSeek or Qwen/DashScope. Requests go directly from the browser to the selected provider; the key remains in memory unless **Nhớ key** is checked. Model lists are fetched from the provider. API requests use 3–4 workers with backoff for 429/5xx and stop on invalid credentials or exhausted retries.
- **Own signed-in account:** start the local SinoBridge app and select Google/Antigravity (`agy`) or ChatGPT/Codex. The page connects to `127.0.0.1` on that user's computer; the local app invokes their signed-in CLI. Usage counts against their own account, not the site owner's. The account bridge uses two workers. It does not turn a subscription into an API key or expose account credentials to GitHub Pages. CLI errors stop the run and leave committed checkpoints available to resume.
- **Browser GPU:** an open-weight Qwen2.5 model via WebLLM, one passage at a time. It needs WebGPU, a large first download and sufficient GPU memory; quality is usually lower than cloud models.

For account access, install and sign in to `agy` or Codex once, then run the launcher in `scripts/`. The default app port is 8765. If occupied, run `sinobridge serve --port 8767` and enter **8767** in **Cổng app**. Keep the app running. Chrome/Edge may require local-network permission; Safari may block this connection. The server binds only to loopback, checks Host and Origin, and accepts the official web origin plus its own local origin (additional development origins require explicit configuration).

## Checkpoints and storage

IndexedDB holds the original document once, lightweight library summaries, and translation records keyed by project and passage. Each completed batch commits its new translations and library count in one transaction, without rewriting the entire book. The saved count/time is shown only after that transaction completes. A storage error stops further work and reports the problem; it is not silently marked as saved.

Existing version-1 browser projects are migrated without deleting their originals or translations. The library loads summaries; full text and checkpoints are loaded only when a title is opened.

Keep the tab open while translating. Closing it, shutting down the computer or losing the current request stops the browser run; the interrupted batch may need to be sent again. An account CLI may finish an already running request after the browser stops. Resume in the same browser profile and site origin. Checkpoints are not cloud backups: clearing site data, private browsing or moving computers can lose them. Download reading copies periodically.

## Long-book limits

- Maximum file size: **32 MiB**; extracted text: **8,000,000 JavaScript string code units**; PDF: **900 pages**.
- These are import limits, not a tested guarantee for every book/device. The active document is still held in browser memory, and exports assemble the document in memory. Split very large books into chapters or volumes.
- PDF scans need separate OCR. Tables, illustrations, page layout and footnotes are not faithfully preserved.
- Try a chapter first to assess terminology, cost/quota and speed. There is no unconditional completion-time or cost estimate before enough passages have completed.
- Long-range terminology consistency and scientific accuracy require human review. All exports are machine-translation drafts.
- Free-tier provider data-use policies and quotas still apply. GitHub Pages hosts the application code, not uploaded books or credentials.

## Development and verification

    cd web
    npm ci
    npm run dev
    npm run build

GitHub Actions builds with base `/sinobridge/` and deploys `web/dist`; local development uses `/`. Browser smoke and long-book regression tests use synthetic text and mock providers, never real credentials or model quota:

    python3 web/tests/smoke_browser.py
    python3 web/tests/long_book_browser.py
