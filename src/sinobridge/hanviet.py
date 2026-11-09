"""Hán-Việt transliteration of Chinese names and terms.

Two layers:

1. A bundled per-character table (data/hanviet_chars.tsv, CC BY-SA 4.0) with readings ranked by how
   often they occur in real Hán-Việt renderings of proper names, conditioned on Mandarin pinyin.
2. Optional: the full CVDICT dictionary (``sinobridge data fetch``) for exact names/terms
   (诸葛亮 -> Gia Cát Lượng, 重庆 -> Trùng Khánh) and contextual pinyin for polyphonic characters.

Output is a suggestion with alternatives and an explicit ambiguity list, never a silent guess.
"""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
import os
from pathlib import Path
import re
import unicodedata

DATA = Path(__file__).resolve().parent / "data" / "hanviet_chars.tsv"
CVDICT_URL = "https://raw.githubusercontent.com/ph0ngp/CVDICT/master/CVDICT.u8"
TONES = {"̀", "́", "̃", "̉", "̣"}
CJK = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0002ffff]")

def tone_key(word: str) -> str:
    """Key insensitive to tone-mark placement (hoà == hòa) and case."""
    decomposed = unicodedata.normalize("NFD", word.lower())
    tone = "".join(c for c in decomposed if c in TONES)
    base = unicodedata.normalize("NFC", "".join(c for c in decomposed if c not in TONES))
    if len(base) > 1 and base.endswith("y") and (base[-2] not in "aăâeêioôơuư" or base.endswith("quy")):
        base = base[:-1] + "i"   # lý == lí, quý == quí, mỹ == mĩ (old/new spelling)
    return base + tone

def norm_text(text: str) -> str:
    """Word-by-word tone_key, for 'does this rendering occur in that sentence' checks."""
    return " " + " ".join(tone_key(w) for w in re.findall(r"\w+", text)) + " "

def contains(haystack: str, needle: str) -> bool:
    return norm_text(needle) in norm_text(haystack)

def cache_dir() -> Path:
    root = os.getenv("SINOBRIDGE_CACHE") or os.path.join(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache", "sinobridge")
    return Path(root)

@lru_cache(maxsize=1)
def char_table() -> dict:
    table = defaultdict(list)   # char -> [(pinyin, reading, count)]
    for line in DATA.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        ch, py, reading, count, _src = line.split("\t")
        table[ch].append((py, reading, int(count)))
    return dict(table)

def readings(ch: str, pinyin: str | None = None) -> list[tuple[str, float]]:
    """Ranked (reading, share) for one character; pinyin (e.g. 'xing2') narrows polyphones."""
    rows = char_table().get(ch, [])
    if pinyin:
        exact = [r for r in rows if r[0] == pinyin.lower()]
        rows = exact or rows
    totals = defaultdict(int)
    canon = {}
    for _py, reading, count in rows:
        k = tone_key(reading)
        totals[k] += count
        canon.setdefault(k, reading)
    if not totals:
        return []
    weight = sum(totals.values())
    if weight == 0:   # Unihan-only characters: keep listed order, equal shares
        return [(canon[k], 1 / len(canon)) for k in canon]
    return sorted(((canon[k], n / weight) for k, n in totals.items()), key=lambda x: -x[1])

# ------------------------------------------------------------------ word/name lexicon (bundled)
WORDS = DATA.parent / "hanviet_words.tsv"

@lru_cache(maxsize=1)
def lexicon() -> dict:
    """{chinese (simplified and traditional): (vietnamese, kind)} from Wiktionary + CVDICT."""
    out = {}
    for line in WORDS.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        simp, trad, vi, kind, _src = line.split("\t")
        out.setdefault(simp, (vi, kind))
        out.setdefault(trad, (vi, kind))
    return out

# ------------------------------------------------------------------ optional full CVDICT
@lru_cache(maxsize=1)
def dictionary() -> dict:
    """{simplified or traditional: [(pinyin syllables, glosses)]} if CVDICT has been fetched."""
    path = cache_dir() / "CVDICT.u8"
    entries = defaultdict(list)
    if not path.is_file():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\S+) (\S+) \[([^\]]+)\] /(.*)/\s*$", line)
        if m:
            trad, simp, py, defs = m.groups()
            item = (py.split(), [d for d in defs.split("/") if d])
            entries[simp].append(item)
            if trad != simp:
                entries[trad].append(item)
    return dict(entries)

def fetch_dictionary() -> dict:
    from urllib.request import Request, urlopen
    target = cache_dir() / "CVDICT.u8"
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(CVDICT_URL, headers={"User-Agent": "SinoBridge/0.2"}), timeout=120) as r:
        data = r.read()
    if b"CVDICT" not in data[:2000]:
        raise RuntimeError("Downloaded file does not look like CVDICT")
    target.write_bytes(data)
    dictionary.cache_clear()
    return {"file": str(target), "bytes": len(data), "license": "CC BY-SA 4.0 (Phong Phan, CVDICT; based on CC-CEDICT)"}

def dictionary_glosses(text: str, limit: int = 3) -> list[str]:
    """Vietnamese meanings from CVDICT (needs `sinobridge data fetch`)."""
    return [g for _py, glosses in dictionary().get(text, []) for g in glosses][:limit]

def _pinyin(chunk: str):
    hit = dictionary().get(chunk)
    if not hit:
        from .names import contextual_pinyin
        return contextual_pinyin(chunk)
    proper = [h for h in hit if h[0] and h[0][0][:1].isupper()]
    py = (proper or hit)[0][0]
    return [p.lower() for p in py] if len(py) == len(chunk) else None

def _segment(text: str, use_lexicon: bool = True):
    """Greedy longest match; yields (chunk, lexicon entry or None, pinyin or None)."""
    from .names import proper_nouns
    lex, d, pn = lexicon() if use_lexicon else {}, dictionary(), proper_nouns()
    i = 0
    while i < len(text):
        if not CJK.match(text[i]):
            j = i
            while j < len(text) and not CJK.match(text[j]):
                j += 1
            yield text[i:j], None, None
            i = j
            continue
        for size in range(min(8, len(text) - i), 0, -1):
            chunk = text[i:i + size]
            if size == 1 or chunk in lex or chunk in d or chunk in pn:
                yield chunk, lex.get(chunk) if size > 1 else None, _pinyin(chunk)
                i += size
                break

# ------------------------------------------------------------------ public API
def _cap(words: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in words.split())

# Administrative/geographic suffixes that Vietnamese puts in front as a common noun.
SUFFIX_FRONT = {"省": "tỉnh", "市": "thành phố", "县": "huyện", "縣": "huyện", "区": "quận", "區": "quận",
                "镇": "trấn", "鎮": "trấn", "乡": "hương", "鄉": "hương", "村": "thôn", "江": "sông", "河": "sông",
                "山": "núi", "岛": "đảo", "島": "đảo", "湖": "hồ", "湾": "vịnh", "灣": "vịnh"}
KEEP_SUFFIX = {"江", "河", "山", "湖", "岛", "島"}   # often part of the proper name itself (长江 = Trường Giang)

def transliterate(text: str, capitalize: bool = True, use_lexicon: bool = True) -> dict:
    """See _transliterate; additionally renders 四川省 as 'tỉnh Tứ Xuyên'."""
    if (len(text) > 2 and text[-1] in SUFFIX_FRONT and text[-1] not in KEEP_SUFFIX
            and not (use_lexicon and text in lexicon())):
        inner = _transliterate(text[:-1], capitalize, use_lexicon)
        inner["hanviet"] = f"{SUFFIX_FRONT[text[-1]]} {inner['hanviet']}"
        inner["zh"] = text
        inner["pieces"].append({"zh": text[-1], "hanviet": SUFFIX_FRONT[text[-1]], "from": "suffix"})
        return inner
    return _transliterate(text, capitalize, use_lexicon)

def _transliterate(text: str, capitalize: bool = True, use_lexicon: bool = True) -> dict:
    """Hán-Việt for a name/term: dictionary words first, then character readings ranked by evidence.

    Returns the rendering, the pieces it came from, and what a human should check
    (characters with competing readings, characters without any known reading).
    """
    out, pieces, ambiguous, unknown = [], [], [], []
    for chunk, entry, py in _segment(text, use_lexicon):
        if not CJK.match(chunk[0]):
            out.append(chunk.strip())
            continue
        if entry:
            vi, kind = entry
            out.append(vi if kind == "name" else (_cap(vi) if capitalize else vi))
            pieces.append({"zh": chunk, "hanviet": vi, "from": kind})
            continue
        for k, ch in enumerate(chunk):
            cands = readings(ch, py[k] if py else None)
            if not cands:
                unknown.append(ch)
                out.append(ch)
                pieces.append({"zh": ch, "hanviet": None, "from": "unknown"})
                continue
            best, share = cands[0]
            out.append(best.capitalize() if capitalize else best)
            pieces.append({"zh": ch, "hanviet": best, "from": "char", "pinyin": py[k] if py else None,
                           "alternatives": [r for r, _ in cands[1:4]]})
            if len(cands) > 1 and share < 0.75:
                ambiguous.append(ch)
    rendered = re.sub(r"\s+", " ", " ".join(x for x in out if x)).strip()
    return {"zh": text, "hanviet": rendered, "pieces": pieces, "ambiguous": ambiguous, "unknown": unknown,
            "exact": len(pieces) == 1 and pieces[0]["from"] in ("name", "word")}

def char_hints(text: str) -> dict:
    """{char: 'reading1/reading2'} for every CJK character in text (for reading aids)."""
    hints = {}
    for ch in set(CJK.findall(text)):
        cands = readings(ch)
        if cands:
            hints[ch] = "/".join(r for r, _ in cands[:3])
    return hints
