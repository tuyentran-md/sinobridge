# Bundled data

| File | Content | License |
|---|---|---|
| `hanviet_chars.tsv` | Hán-Việt readings per character, ranked by evidence, conditioned on pinyin | CC BY-SA 4.0 |
| `hanviet_words.tsv` | Sino-Vietnamese words and Chinese proper names with Hán-Việt renderings | CC BY-SA 4.0 |
| `names_en.tsv` | ~19.8k Chinese proper nouns with pinyin and established English names (CC-CEDICT) | CC BY-SA 4.0 |
| `pinyin_chars.tsv` | Mandarin readings per character (Unihan kMandarin, kXHC1983) | Unicode License v3 |

Built by `scripts/build_hanviet_data.py` and `scripts/build_pinyin_data.py` from:

- **Wiktionary** via [kaikki.org](https://kaikki.org/dictionary/Vietnamese/) — CC BY-SA 4.0 (and GFDL), Wiktionary contributors.
- **CVDICT** by Phong Phan, <https://github.com/ph0ngp/CVDICT> — CC BY-SA 4.0, based on CC-CEDICT
  (CC BY-SA 4.0, MDBG).
- **CC-CEDICT**, <https://www.mdbg.net/chinese/dictionary?page=cc-cedict> — CC BY-SA 4.0, MDBG;
  CEDICT © 1997–1998 Paul Andrew Denisowski.
- **Unicode Unihan** database (kVietnamese, variants) — Unicode License v3, © Unicode, Inc.

`pinyin_chars.tsv` is distributed under the Unicode License v3 (https://www.unicode.org/license.txt). The other data files are
distributed under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/);
if you redistribute modified versions of them, keep this attribution and the same license.
The SinoBridge source code is MIT licensed.

Measured quality (held-out 10% of aligned CVDICT names, character-level only, no dictionary lookup):
88% of names fully correct, 95% of syllables correct. Known names in the bundled lexicon are looked up
directly. Always review names flagged as ambiguous.
