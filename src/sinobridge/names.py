"""Chinese names for English output (Hanyu Pinyin conventions) and a target-aware dispatcher.

English: CC-CEDICT proper nouns give established forms (诸葛亮 -> Zhuge Liang, 孔子 -> Confucius,
西藏 -> Tibet, 长江 -> Yangtze River). Unknown names are romanized from per-character Mandarin readings:
person = surname + given name written together (张明华 -> Zhang Minghua, 欧阳修 -> Ouyang Xiu),
place = one word with an apostrophe before a/o/e syllables (西安 -> Xi'an) plus an English
administrative noun (四川省 -> Sichuan Province). Polyphonic characters are flagged, never silently resolved.

Vietnamese: delegated to hanviet (Hán-Việt).
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

DATA = Path(__file__).resolve().parent / "data"
CJK = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0002ffff]")

COMPOUND_SURNAMES = {"欧阳", "司马", "诸葛", "上官", "东方", "皇甫", "尉迟", "公孙", "慕容", "夏侯", "令狐", "长孙",
                     "宇文", "司徒", "西门", "端木", "独孤", "南宫", "轩辕", "澹台", "太史", "申屠", "呼延", "万俟",
                     "歐陽", "司馬", "諸葛", "東方", "公孫", "長孫", "獨孤", "軒轅"}
# Readings used when the character is a surname (first character of a person name)
SURNAME_PINYIN = {"单": "shan", "單": "shan", "曾": "zeng", "乐": "yue", "樂": "yue", "区": "ou", "區": "ou",
                  "解": "xie", "仇": "qiu", "朴": "piao", "查": "zha", "盖": "ge", "蓋": "ge", "华": "hua", "華": "hua",
                  "种": "chong", "種": "chong", "繁": "po", "缪": "miao", "繆": "miao", "尉迟": "yuchi",
                  "万俟": "moqi", "长孙": "zhangsun", "長孫": "zhangsun", "覃": "qin", "翟": "zhai", "谌": "chen",
                  "柏": "bai", "秘": "bi", "员": "yun", "召": "shao", "折": "she", "黑": "he", "宁": "ning", "沈": "shen"}
SUFFIX_EN = {"省": "Province", "市": "", "县": "County", "縣": "County", "区": "District", "區": "District",
             "镇": "Town", "鎮": "Town", "乡": "Township", "鄉": "Township", "村": "Village",
             "自治区": "Autonomous Region", "自治區": "Autonomous Region", "自治州": "Autonomous Prefecture",
             "自治县": "Autonomous County", "自治縣": "Autonomous County"}

def plain(syllable: str) -> str:
    """'zhāng' / 'zhang1' / 'lu:3' -> 'zhang' / 'lü' (tone marks dropped, ü kept)."""
    s = re.sub(r"[1-5]$", "", syllable.lower()).replace("u:", "ü").replace("v", "ü")
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if ch == "̈":           # keep the diaeresis of ü
            out.append(ch)
        elif unicodedata.category(ch) != "Mn":
            out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))

@lru_cache(maxsize=1)
def char_readings() -> dict:
    table = {}
    for line in (DATA / "pinyin_chars.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        ch, main, alls = line.split("\t")
        table[ch] = (main, alls.split())
    return table

@lru_cache(maxsize=1)
def proper_nouns() -> dict:
    """{chinese: (numbered pinyin list, English name or '')} from CC-CEDICT."""
    out = {}
    for line in (DATA / "names_en.tsv").read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        simp, trad, py, name = (line.split("\t") + [""])[:4]
        item = (py.split(), name)
        out.setdefault(simp, item)
        out.setdefault(trad, item)
    return out

def join_syllables(sylls: list[str]) -> str:
    """Pinyin word: apostrophe before a/o/e-initial syllables after the first (xi'an, chang'an)."""
    word = ""
    for i, s in enumerate(sylls):
        if i and s[:1] in "aoeāáǎàōóǒòēéěè":
            word += "'"
        word += s
    return word[:1].upper() + word[1:]

def _char_pinyin(text: str, surname_first: bool):
    sylls, ambiguous, unknown = [], [], []
    for i, ch in enumerate(text):
        if surname_first and i == 0 and ch in SURNAME_PINYIN:
            sylls.append(SURNAME_PINYIN[ch])
            continue
        main, alls = char_readings().get(ch, (None, []))
        if not main:
            unknown.append(ch)
            sylls.append(ch)
            continue
        sylls.append(plain(main))
        if len({plain(r) for r in alls}) > 1:
            ambiguous.append(ch)
    return sylls, ambiguous, unknown

def english(text: str, type_: str = "person") -> dict:
    """English rendering of a Chinese name. type_: person | place | other."""
    entry = proper_nouns().get(text)
    if entry and entry[1]:
        return {"zh": text, "render": entry[1], "exact": True, "ambiguous": [], "unknown": [], "source": "cc-cedict"}
    if type_ == "place":
        for suffix in sorted(SUFFIX_EN, key=len, reverse=True):
            if text.endswith(suffix) and len(text) > len(suffix) + 1:
                inner = english(text[:-len(suffix)], "place")
                noun = SUFFIX_EN[suffix]
                inner.update(zh=text, render=f"{inner['render']} {noun}".strip(), exact=inner["exact"])
                return inner
    if entry:   # known proper noun without an English gloss: use its dictionary pinyin (handles polyphones)
        sylls, ambiguous, unknown = [plain(s) for s in entry[0]], [], []
        source = "cc-cedict-pinyin"
    else:
        sylls, ambiguous, unknown = _char_pinyin(text, surname_first=type_ == "person")
        source = "characters"
    if type_ == "person" and len(sylls) >= 2:
        cut = 2 if text[:2] in COMPOUND_SURNAMES and len(sylls) >= 3 else 1
        render = join_syllables(sylls[:cut]) + " " + join_syllables(sylls[cut:])
    else:
        render = join_syllables(sylls)
    return {"zh": text, "render": render, "exact": False, "ambiguous": ambiguous, "unknown": unknown, "source": source}

def contextual_pinyin(chunk: str) -> list[str] | None:
    """Numbered pinyin of a known proper noun (used to pick Hán-Việt readings of polyphones)."""
    entry = proper_nouns().get(chunk)
    return [s.lower() for s in entry[0]] if entry and len(entry[0]) == len(chunk) else None

# ------------------------------------------------------------------ target-aware dispatcher
TARGETS = {"vi": "Vietnamese", "en": "English"}

def render_name(text: str, type_: str, target: str) -> dict:
    """{'render', 'exact', 'ambiguous', 'unknown'} for a Chinese-origin name in the target language."""
    if target == "en":
        kind = "person" if type_ == "person" else "place" if type_ == "place" else "other"
        return english(text, kind)
    from . import hanviet
    r = hanviet.transliterate(text)
    return {"zh": text, "render": r["hanviet"], "exact": r["exact"], "ambiguous": r["ambiguous"],
            "unknown": r["unknown"], "source": "hanviet"}
