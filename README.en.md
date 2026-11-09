# SinoBridge

**Translate Chinese books and documents into English or Vietnamese. Compare each translated passage with its source.**

[Tiếng Việt](README.md) · **English**

**[Try the browser demo](https://tuyentran-md.github.io/sinobridge/)** · Local WebGPU translation without an API key (compatible hardware required). See [browser demo limitations](web/README.md).

SinoBridge is an open-source tool for translating Chinese documents on your computer. Add a file, choose a language and your own AI model, then download the translation. The command-line interface also supports research workflows.

| Part | What it does |
|---|---|
| **Import files** | Open EPUB, text-based PDF, Word, TXT, Markdown, HTML and subtitles. The CLI also imports public web pages and citation exports from CNKI/Wanfang/VIP/SinoMed; it does not access paid databases directly. |
| **Translate and check** | Translate into English or Vietnamese with your own model/API key, or use Ollama locally. A term memory keeps names consistent; automatic checks flag some problems with numbers and citations. |
| **Read and export** | Download EPUB, Word, Markdown, subtitles or offline bilingual HTML. Select a passage to see its Chinese source, notes and revision history. |

![Bilingual review page: click a translated sentence to see the Chinese source, QA flags, names and pinyin](docs/images/review-page-en.png)

*In the offline bilingual review page, a red border flags a number mismatch. Select a passage to see its Chinese source, terms and review notes. Hover over 北 to see its pinyin.*

## How it works

```mermaid
flowchart LR
    A["📄 Chinese source<br/>file · web page · subtitles<br/>CNKI/Wanfang citations"] --> B["Split into passages<br/>each with an ID + original location"]
    B --> C["Translate passage by passage<br/>→ English or Vietnamese<br/>with name suggestions"]
    C --> D["Automatic QA<br/>numbers · DOI · citations<br/>consistent names/terms"]
    D --> E["Human review<br/>tracked corrections · approval"]
    E --> F["📚 Publish<br/>EPUB · DOCX · Markdown<br/>subtitles · review page"]
    T[("Term memory<br/>诸葛亮 → Zhuge Liang")] -.-> C
    C -.-> T
    T -.-> D
```

Each translated passage retains a source ID and location (line, page or subtitle timestamp), so you can look up the corresponding Chinese passage.

## Get started: drag and drop

![SinoBridge desktop browser interface](docs/images/gui-en.png)

1. Install Python 3.10+ if needed. On GitHub select Code → Download ZIP and unzip the repository.
2. Double-click Start SinoBridge.command (macOS) or Start SinoBridge.bat (Windows) in the scripts folder. The first run installs the required libraries.
3. Drop in a file and choose English or Vietnamese.
4. Choose an AI provider, enter your model name and API key, or select Ollama if you have a local model. Consent before sending text to a remote provider, then click **Translate document**.
5. Download EPUB, Word, Markdown or the bilingual HTML file. Finished passages are kept if you stop mid-translation.

The interface works in English and Vietnamese. Files are stored in the .sinobridge/projects folder under your home directory. SinoBridge does not sync them. If you translate through an API, text goes to the selected provider and any fees are billed by that provider. The API key is not saved to disk.

For installation help, see [the quickstart guide](docs/quickstart-gui.md). CLI users can run the sinobridge serve --open command.

## Install (command line)

Python 3.10+.

    git clone https://github.com/tuyentran-md/sinobridge.git && cd sinobridge
    python3 -m venv .venv && . .venv/bin/activate
    pip install -e '.[all]'      # includes PDF and DOCX support

## Command-line quick start

Pick the target language when you import a document (`--target en` or `--target vi`; Vietnamese is the default):

    sinobridge sources                                       # list supported inputs
    sinobridge ingest book.epub --workspace work/book --kind book --target en
    sinobridge ingest "https://zh.wikipedia.org/wiki/汉越词" --workspace work/wiki --kind article --target en
    sinobridge ingest video.zh.srt --workspace work/video --kind subtitle --target en

Translate. The default is one passage so you can check the result first; `--max-segments 0` translates everything. Text is only sent to a
service when you pass `--allow-external`, after checking the document's rights and privacy:

    export GEMINI_API_KEY=...        # or OPENAI_API_KEY, DEEPSEEK_API_KEY, DASHSCOPE_API_KEY...
    sinobridge translate --workspace work/book --provider gemini --model <flash-model> --allow-external --dry-run
    sinobridge translate --workspace work/book --provider gemini --model <flash-model> --allow-external --max-segments 0
    sinobridge translate --workspace work/book --provider openai --model <gpt-model> --allow-external

The model is your choice: `openai`, `gemini`, `deepseek`, `qwen`, `openrouter`, `ollama`, or any OpenAI-compatible server
(`--provider openai-compatible --base-url ...`). See `.env.example`.

## Chinese names and terms

![Chinese names in English: established forms from the dictionary, otherwise Hanyu Pinyin rules](docs/images/names-en-cli.png)

- **English**: established forms come from about 17,000 CC-CEDICT proper nouns (Confucius, Tibet, Hong Kong, Yangtze River). Other names
  follow Hanyu Pinyin conventions:
  - people are written surname first, with the given name as one word (张明华 → Zhang Minghua);
  - compound surnames stay together (欧阳 → Ouyang), and surname readings are used (单 → Shan);
  - places are written as one word, with apostrophes where needed (Xi'an), plus an English administrative noun (Sichuan Province).
- **Vietnamese**: Hán-Việt readings, looked up first in a bundled lexicon of about 11,600 entries from Wiktionary and CVDICT, then built
  syllable by syllable with readings ranked by real usage and chosen by pinyin. On names held out from building the data, 88% come out
  fully correct and 95% of syllables are correct.
- Polyphonic characters (乐 lè/yuè, 重 zhòng/chóng) are flagged for review, never silently resolved.
- During translation, the model receives the known names in each passage and must list the names and terms it used. Chinese-origin names
  are normalized to the standard form for the target language. Foreign names written in Chinese characters (特朗普) keep their original
  form (Trump).
- The **term memory** (`terms.json`) holds one agreed rendering per name or term. The audit reports `TERM_INCONSISTENT` when a passage
  differs from it.

      sinobridge name 诸葛亮 张明华 --to en                       # Zhuge Liang · Zhang Minghua
      sinobridge name 四川省 西安 --to en --type place             # Sichuan Province · Xi'an
      sinobridge terms scan --workspace work/book                  # known names in the book, no model needed
      sinobridge terms set 诸葛亮 "Kongming" --type person --workspace work/book   # lock your own choice
      sinobridge terms list --workspace work/book

## Check, review, correct, approve

    sinobridge audit  --workspace work/book --glossary examples/glossary.sample.json
    sinobridge export --workspace work/book --format html --out out/review.html
    sinobridge revise --workspace work/book --segment <ID> --text "Corrected sentence" --reviewer "Lan" \
                      --reason "Number 58 -> 85" --severity HIGH
    sinobridge approve --workspace work/book --segment <ID> --reviewer "Lan" --evidence "Checked against source"

Numbers are compared by value, not by string:
- separators: 1.25 = 1,25;
- scale words: 120万 = 1.2 million = 1,2 triệu;
- month names: 2025年3月 = March 2025;
- Chinese numerals: 一百二十 = 120.

A changed value (5% → 50%) is flagged HIGH.

## Export files

    sinobridge export --workspace work/book  --format epub --out out/book.epub
    sinobridge export --workspace work/book  --format epub --bilingual --out out/book-bilingual.epub
    sinobridge export --workspace work/book  --format docx --out out/book.docx
    sinobridge export --workspace work/video --format srt  --out out/video.en.srt

<img src="docs/images/epub-bilingual.png" alt="Bilingual EPUB: translated paragraph followed by the Chinese original" width="300" align="right">

**Bilingual EPUB** (right; shown here with a Vietnamese target): each translated paragraph is followed by its Chinese original. It has
chapters and a table of contents and passes EPUBCheck. Leave out `--bilingual` for a translation-only edition.

Pages carry no "draft" banners. The review status is stated once, honestly, on the colophon page (for example "Draft translation:
120/300 passages human-reviewed"). Every passage keeps an invisible anchor to its source passage.

<br clear="right">

## Chinese research metadata

    sinobridge search "先天性巨结肠" --source openalex --limit 10 --library mylib
    sinobridge library import cnki_export.ris --library mylib      # RIS / EndNote / NoteExpress
    sinobridge library list --library mylib --query 巨结肠
    sinobridge library link --library mylib --record <ID> --workspace work/paper1
    sinobridge library export --library mylib --out refs.ris        # open in Zotero / EndNote

- OpenAlex returns abstracts and open-access links when available.
- **CNKI / Wanfang / VIP / SinoMed**: the tool never logs in or scrapes. If you have access, export the citations
  (RIS/EndNote/NoteExpress) and download the PDFs yourself, then use `library import` and `ingest`. Convert `.caj` files to PDF first.
- Social media that needs a login (Weibo, Zhihu, Xiaohongshu), or that blocks automated fetching in robots.txt (WeChat): open the page
  in your browser, use *Save Page As (HTML)*, and `ingest` the saved file.

## Principles

- **Traceability**: every passage has an ID, its location in the original and the SHA-256 of the source; fetched web pages are saved
  as a snapshot, because web content changes.
- **Limits of automatic checks**: automated checks are partial evidence. No semantic or scientific gate is ever passed automatically. See the
  [QA policy](docs/qa-policy.md).
- **Rights and privacy**: text goes to an API only with `--allow-external`; there is no paywall bypass and no bulk crawling, and
  robots.txt is honored. Translating a text does not remove the original author's copyright.
- Do not draw clinical conclusions from translated medical literature without reading the primary source.

## Writing a connector (plugin)

Any Python package can add a connector through the `sinobridge.sources` entry point, for example an institution's licensed CNKI API,
a Weibo export reader or an RSS feed. See [docs/connectors.md](docs/connectors.md).

## Roadmap, contributing, credits

[ROADMAP.md](ROADMAP.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

The workflow (fidelity, natural style, staged QA, provenance) was inspired by the
[How To Live Better translation prompt](https://thuongtin.notion.site/Prompt-d-ch-How-To-Live-Better-t-ti-ng-Trung-sang-ti-ng-Vi-t-41172ac96186819dae67c730db8d7152)
and [thuongtin/HowToLiveBetter](https://github.com/thuongtin/HowToLiveBetter) (CC BY 4.0). The code is written independently and
licensed MIT.

Bundled language data (`src/sinobridge/data/`) is built from Wiktionary (via kaikki.org), CVDICT by Phong Phan, CC-CEDICT (MDBG) and
the Unicode Unihan database. It is distributed under **CC BY-SA 4.0** (Unihan-derived files: Unicode License); see
[src/sinobridge/data/README.md](src/sinobridge/data/README.md).

The screenshots use the fictional article in `examples/demo_article_zh.md`. Regenerate them with `python3 scripts/make_readme_images.py`
(requires Playwright).

## Tests

    python3 -m unittest discover -s tests -v
