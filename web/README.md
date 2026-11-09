# SinoBridge browser demo

This is a static GitHub Pages demo. No backend, no account and no API key are required. Users bring Chinese EPUB, text-based PDF, DOCX, TXT, Markdown or HTML files.

The page extracts text in the browser, saves per-passage translation checkpoints in IndexedDB, and uses WebLLM with a user-selected Qwen2.5 instruct model on WebGPU. Models are downloaded from their respective public model hosts into the browser cache. Text being translated is not submitted to SinoBridge servers. No translation is produced if the model cannot load.

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
- Browser-generated outputs are drafts, not professionally checked publications.
- GitHub Pages hosts only the website code; users provide the content locally.

Build and run:

    cd web
    npm ci
    npm run dev
    npm run build

GitHub Pages deployment is configured via .github/workflows/pages.yml. Vite builds with base /sinobridge/ under GitHub Actions; local dev uses base /.

Neither uploaded books nor API keys are included in this repository. The demo does not contain any external service credentials.

Browser smoke tests for the no-model workflow and export are in web/tests/smoke_browser.py; tests must not download or call a paid language model.
