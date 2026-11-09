# Roadmap

Status markers: ✅ done · 🔜 next · 💡 proposed

## Sources
- ✅ Files: TXT/MD, DOCX (heading styles), EPUB (spine order), PDF text layer, saved HTML, SRT/VTT subtitles
- ✅ One public URL per call with article-body detection (WeChat, Zhihu, MediaWiki, news CMS) and snapshot
- ✅ Citation exports: RIS, EndNote, NoteExpress (CNKI, Wanfang, VIP, SinoMed)
- ✅ OpenAlex (abstracts, OA links), Crossref; plugin entry point `hanviet_bridge.sources`
- 🔜 OCR for scanned PDFs/images (ocrmypdf `chi_sim`/`chi_tra`, optional PaddleOCR) with page/box locations
- 💡 RSS/Atom feeds (incl. self-hosted RSSHub for WeChat/Weibo) to follow Chinese sources over time
- 💡 Open Chinese repositories: ChinaXiv preprints, Chinese Wikipedia/Wikisource, Project Gutenberg Chinese texts
- 💡 Douyin/Bilibili: auto-caption via local Whisper when no subtitle file exists

## Translation quality
- ✅ Value-based numeric QA across zh/en/vi formats and Chinese numerals; DOI/URL/citation checks
- ✅ Append-only revisions, hash-bound approvals, offline bilingual review page
- 🔜 **Hán-Việt name transliteration**: Chinese person/place names rendered in Hán-Việt
  (毛泽东 → Mao Trạch Đông) from Unicode Unihan `kVietnamese` readings, with pinyin alternative for modern names
- 🔜 Automatic term memory: candidate terms/names extracted before translation; flag inconsistent renderings
  across chapters; reuse approved terms across projects
- 💡 Independent second-model review pass that only *flags* (never silently rewrites)
- 💡 Reading aids in the review page: pinyin + Hán-Việt on hover for any Chinese character

## Output
- ✅ EPUB3 with chapters, TOC, colophon, bilingual mode; DOCX; Markdown; SRT/VTT
- 🔜 EPUBCheck in CI; cover image; footnotes for translator notes
- 💡 Print-ready PDF via Typst/LaTeX; bilingual side-by-side PDF

## Interface
- 💡 Local web app (`hanviet serve`): edit, approve and resolve issues in the browser; same JSONL store
