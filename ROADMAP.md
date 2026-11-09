# Roadmap

Status markers: ✅ done · 🔜 next · 💡 proposed

## Sources
- ✅ Files: TXT/MD, DOCX (heading styles), EPUB (spine order), PDF text layer, saved HTML, SRT/VTT subtitles
- ✅ One public URL per call with article-body detection (WeChat, Zhihu, MediaWiki, news CMS) and snapshot
- ✅ Citation exports: RIS, EndNote, NoteExpress (CNKI, Wanfang, VIP, SinoMed)
- ✅ OpenAlex (abstracts, OA links), Crossref; plugin entry point `sinobridge.sources`
- 🔜 OCR for scanned PDFs/images (ocrmypdf `chi_sim`/`chi_tra`, optional PaddleOCR) with page/box locations
- 💡 RSS/Atom feeds (incl. self-hosted RSSHub for WeChat/Weibo) to follow Chinese sources over time
- 💡 Open Chinese repositories: ChinaXiv preprints, Chinese Wikipedia/Wikisource, Project Gutenberg Chinese texts
- 💡 Douyin/Bilibili: auto-caption via local Whisper when no subtitle file exists

## Translation quality
- ✅ Target languages: Vietnamese and English (`--target vi|en`); prompts, name rules, QA wording,
  exports and the review page follow the target
- ✅ English names: CC-CEDICT established forms, otherwise Hanyu Pinyin rules (surname first, compound
  surnames, surname readings, apostrophes, administrative nouns); polyphones flagged
- 🔜 More targets (e.g. Indonesian, Thai) via the same LANG table; contributions welcome
- ✅ Value-based numeric QA across zh/en/vi formats and Chinese numerals; DOI/URL/citation checks
- ✅ Append-only revisions, hash-bound approvals, offline bilingual review page
- ✅ Hán-Việt transliteration of names/terms: bundled lexicon (Wiktionary + CVDICT) and evidence-ranked,
  pinyin-conditioned character readings; ambiguity flags; 88% exact on held-out names
- ✅ Term memory per project: model-detected entities, Hán-Việt for Chinese names, foreign names kept,
  locked renderings, TERM_INCONSISTENT audit
- 🔜 Share approved term memories across projects; import/export glossaries (TSV, TBX)
- 🔜 Larger name lexicon: community-reviewed list of modern Chinese public figures and places
- 💡 Independent second-model review pass that only *flags* (never silently rewrites)
- ✅ Reading aid in the review page: Hán-Việt on hover for every Chinese character
- 💡 Pinyin on hover too (needs a pinyin source bundled or fetched)

## Output
- ✅ EPUB3 with chapters, TOC, colophon, bilingual mode; DOCX; Markdown; SRT/VTT
- 🔜 EPUBCheck in CI; cover image; footnotes for translator notes
- 💡 Print-ready PDF via Typst/LaTeX; bilingual side-by-side PDF

## Interface
- 💡 Local web app (`sinobridge serve`): edit, approve and resolve issues in the browser; same JSONL store
