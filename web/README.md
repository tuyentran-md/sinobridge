# SinoBridge browser demo

This is a static GitHub Pages demo. No backend and no SinoBridge account. Users bring Chinese EPUB, text-based PDF, DOCX, TXT, Markdown or HTML files.

Model connection (`src/engine.js`):
- **Bring your own key (default):** Google Gemini (free key from Google AI Studio), OpenAI, OpenRouter, DeepSeek or Qwen/DashScope. All five expose an OpenAI-compatible chat endpoint that accepts direct browser requests, so passages and the key go straight from the browser to the chosen provider. The key stays in memory unless the user ticks "Nhớ key" (then localStorage on that device).
- **Local fallback:** an open-weight Qwen2.5 model on WebGPU via WebLLM, no key, downloaded into the browser cache on first use.
- Passages are sent in numbered batches (about 2,400 Chinese characters or 12 passages per request) with 3–4 requests in flight; 429/5xx responses are retried with backoff (honouring Retry-After); a batch whose numbering comes back incomplete is redone passage by passage; 401/403 stops with a key message. The model list is read from the provider's `/models` endpoint so new model names appear without a code change.
- Progress is checkpointed per passage in IndexedDB, so a stopped or failed run resumes where it left off.

You can:
- Import a file or open the small synthetic Chinese example.
- Choose English or Vietnamese as the translation target.
- Run an open-weight model locally in a WebGPU-compatible desktop browser.
- Pause between passages, resume later, and export draft EPUB, DOCX, TXT or bilingual HTML.

Known limitations:
- Model downloads can be multiple GB and require enough GPU memory. This is not practical on every phone or older machine.
- Small browser models may translate poorly. No semantic review or scientific validity is asserted.
- Scanned PDFs need OCR separately; complex tables, page layout, figures and footnotes are not preserved.
- Browser storage can be erased by the user or browser settings; no cross-device sync.
- ChatGPT Plus/Google AI Pro subscriptions do not confer third-party API access. This demo does not support using a consumer subscription through account sign-in.
- On the free Gemini tier Google may use submitted content to improve its products; do not send sensitive documents with a free key.
- Browser-generated outputs are drafts, not professionally checked publications.
- GitHub Pages hosts only the website code; users provide the content locally.

Build and run:

    cd web
    npm ci
    npm run dev
    npm run build

GitHub Pages deployment is configured via .github/workflows/pages.yml. Vite builds with base /sinobridge/ under GitHub Actions; local dev uses base /.

Neither uploaded books nor API keys are included in this repository. The demo does not contain any external service credentials.

Browser smoke tests are in web/tests/smoke_browser.py. They intercept the Gemini endpoint locally (batching, 429 retry, key handling, wrong-key message, exports) and never download a model or call a real provider.
