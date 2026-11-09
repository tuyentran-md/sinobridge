# Bundled data

| File | Content | License |
|---|---|---|
| `hanviet_chars.tsv` | Hán-Việt readings per character, ranked by evidence, conditioned on pinyin | CC BY-SA 4.0 |
| `hanviet_words.tsv` | Sino-Vietnamese words and Chinese proper names with Hán-Việt renderings | CC BY-SA 4.0 |

Built by `scripts/build_hanviet_data.py` from:

- **Wiktionary** via [kaikki.org](https://kaikki.org/dictionary/Vietnamese/) — CC BY-SA 4.0 (and GFDL), Wiktionary contributors.
- **CVDICT** by Phong Phan, <https://github.com/ph0ngp/CVDICT> — CC BY-SA 4.0, based on CC-CEDICT
  (CC BY-SA 4.0, MDBG).
- **Unicode Unihan** database (kVietnamese, variants) — Unicode License v3, © Unicode, Inc.

These data files are distributed under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/);
if you redistribute modified versions of them, keep this attribution and the same license.
The SinoBridge source code is MIT licensed.

Measured quality (held-out 10% of aligned CVDICT names, character-level only, no dictionary lookup):
88% of names fully correct, 95% of syllables correct. Known names in the bundled lexicon are looked up
directly. Always review names flagged as ambiguous.
