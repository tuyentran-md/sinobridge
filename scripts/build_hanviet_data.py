#!/usr/bin/env python3
"""Build the bundled Hán-Việt data in src/sinobridge/data/ from open sources.

Inputs (download yourself, then pass their paths):
  Unihan.zip (unzipped)   https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip        Unicode License v3
  Wiktionary (kaikki.org) https://kaikki.org/dictionary/Vietnamese/kaikki.org-dictionary-Vietnamese.jsonl
                                                                                           CC BY-SA 4.0 / GFDL
  CVDICT.u8               https://github.com/ph0ngp/CVDICT                                CC BY-SA 4.0

Outputs (CC BY-SA 4.0):
  hanviet_chars.tsv   char, pinyin ('' = any), reading, evidence count, source
  hanviet_words.tsv   chinese (simplified), chinese (traditional), vietnamese, kind (name|word), source

Method
  1. Valid Hán-Việt readings per character come from Wiktionary ("han-viet-reading", which excludes
     Nôm readings); Unihan kVietnamese (mixed Hán-Việt/Nôm) only fills characters Wiktionary lacks.
  2. Evidence counts come from aligned pairs: Wiktionary "Sino-Vietnamese word from 北京" entries and
     CVDICT proper nouns whose gloss is a syllable-by-syllable rendering (validated against step 1).
     CVDICT pairs carry Mandarin pinyin, so polyphones are ranked per reading (行 xing2 hành / hang2 hàng).

Usage: python3 scripts/build_hanviet_data.py UNIHAN_DIR KAIKKI_VI.jsonl CVDICT.u8
"""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sinobridge.hanviet import tone_key  # noqa: E402

import os
OUT = Path(os.getenv("HANVIET_OUT") or Path(__file__).resolve().parents[1] / "src" / "sinobridge" / "data")
HOLDOUT = bool(os.getenv("HANVIET_HOLDOUT"))
HELD: list = []
VI_WORD = re.compile(r"^[A-Za-zÀ-ỹĐđ]+$")
CJK = re.compile(r"^[㐀-鿿豈-﫿\U00020000-\U0002ffff]+$")
# Chinese suffix -> Vietnamese generic noun placed in FRONT ("鸭绿江" -> "sông Áp Lục")
PREFIXES = {"县": "huyện", "縣": "huyện", "市": "thành phố", "省": "tỉnh", "区": "quận", "區": "quận",
            "江": "sông", "河": "sông", "山": "núi", "岛": "đảo", "島": "đảo", "湖": "hồ", "镇": "trấn",
            "鎮": "trấn", "湾": "vịnh", "灣": "vịnh"}

def load_unihan(folder: Path):
    viet, to_simp, to_trad = {}, defaultdict(list), defaultdict(list)
    for line in (folder / "Unihan_Readings.txt").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[1] == "kVietnamese":
            viet[chr(int(p[0][2:], 16))] = p[2].split()
    for line in (folder / "Unihan_Variants.txt").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[1] in ("kSimplifiedVariant", "kTraditionalVariant"):
            a = chr(int(p[0][2:], 16))
            targets = [chr(int(cp[2:].split("<")[0], 16)) for cp in p[2].split()]
            (to_simp if p[1] == "kSimplifiedVariant" else to_trad)[a].extend(t for t in targets if t != a)
    return viet, to_simp, to_trad

def load_wiktionary(path: Path):
    readings, words, mixed = defaultdict(list), [], defaultdict(list)
    for line in path.open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("pos") == "character":
            for sense in d.get("senses", []) + [d]:
                for rel in sense.get("related", []) or []:
                    if "han-viet-reading" in rel.get("tags", []) and rel["word"] not in readings[d["word"]]:
                        readings[d["word"]].append(rel["word"].lower())
            for f in d.get("forms") or []:   # older entries: Hán-Việt and Nôm readings mixed
                if "Hán-Nôm" in f.get("tags", []) and VI_WORD.match(f["form"]):
                    mixed[d["word"]].append(f["form"].lower())
            continue
        for t in d.get("etymology_templates") or []:
            if t.get("name") == "etymid" and CJK.match(t.get("args", {}).get("2", "")):
                han, vi = t["args"]["2"], d["word"]
                if len(vi.split()) == len(han) and all(VI_WORD.match(w) for w in vi.split()):
                    words.append((han, vi, "name" if d.get("pos") == "name" else "word"))
                break
    return readings, mixed, list(dict.fromkeys(words))

def main(unihan_dir, kaikki, cvdict):
    viet, to_simp, to_trad = load_unihan(Path(unihan_dir))
    wk_read, wk_mixed, wk_words = load_wiktionary(Path(kaikki))
    for ch, rs in viet.items():   # Unihan + Wiktionary Hán-Nôm forms = mixed inventory
        wk_mixed[ch] = list(dict.fromkeys(wk_mixed.get(ch, []) + rs))

    def valid(ch):
        """(readings, source) with simplified/traditional variants merged."""
        for table, src in ((wk_read, "wiktionary"), (wk_mixed, "mixed")):
            out = list(table.get(ch, []))
            for v in to_trad.get(ch, []) + to_simp.get(ch, []):
                out += [r for r in table.get(v, []) if r not in out]
            if out:
                return out, src
        return [], None

    def simplify(text):
        return "".join((to_simp.get(c) or [c])[0] for c in text)

    evidence = defaultdict(Counter)          # (char, pinyin) -> Counter(reading)
    lexicon = {}                             # simplified -> (traditional, vietnamese, kind, source)

    def learn(chars, vi_words, pinyin=None):
        for k, (c, w) in enumerate(zip(chars, vi_words)):
            evidence[(c, pinyin[k] if pinyin else "")][w.lower()] += 1

    def aligned(chars, vi_words):
        """Accept only renderings that are syllable-by-syllable Hán-Việt."""
        hits = checkable = 0
        for c, w in zip(chars, vi_words):
            rs, _ = valid(c)
            if rs:
                checkable += 1
                hits += tone_key(w) in {tone_key(r) for r in rs}
        return hits > 0 and hits >= checkable - (1 if len(chars) >= 3 else 0) and hits * 2 >= len(chars)

    for han, vi, kind in wk_words:
        words = vi.split()
        if aligned(han, words):
            learn(han, words)
            simp = simplify(han)
            if simp != han:
                learn(simp, words)
            lexicon.setdefault(simp, (han, vi, kind, "wiktionary"))

    names = 0
    for line in Path(cvdict).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\S+) (\S+) \[([^\]]+)\] /(.*)/\s*$", line)
        if not m:
            continue
        trad, simp, py, defs = m.groups()
        sylls = [s.lower() for s in py.split()]
        if not sylls or not py[0].isupper() or not CJK.match(simp) or len(sylls) != len(simp):
            continue
        head = re.split(r"[(,;（:]", defs.split("/")[0])[0].strip()
        full_simp, full_head = simp, head
        if len(simp) > 2 and simp[-1] in PREFIXES and head.lower().startswith(PREFIXES[simp[-1]] + " "):
            head = head[len(PREFIXES[simp[-1]]) + 1:]
            trad, simp, sylls = trad[:-1], simp[:-1], sylls[:-1]
        words = head.split()
        if len(words) != len(simp) or not all(VI_WORD.match(w) for w in words) or not aligned(simp, words):
            continue
        names += 1
        if HOLDOUT and names % 10 == 0:        # evaluation mode: keep every 10th name unseen
            HELD.append((full_simp, full_head))
            continue
        learn(simp, words, sylls)
        if trad != simp and len(trad) == len(simp):
            learn(trad, words, sylls)
        lexicon.setdefault(full_simp, (trad if full_simp == simp else trad + full_simp[-1], full_head, "name", "cvdict"))

    hv_syllables = {tone_key(r) for rs in wk_read.values() for r in rs}
    rows = []
    chars = set(wk_read) | set(wk_mixed) | {c for c, _ in evidence}
    chars |= {v for c in list(chars) for v in to_simp.get(c, []) + to_trad.get(c, [])}
    chars |= {c for c, _ in evidence}
    for ch in sorted(chars):
        rs, src = valid(ch)
        if not rs:
            # no inventory at all (rare characters): trust aligned names whose other characters validated
            learned = Counter()
            for (c, py), counter in evidence.items():
                if c == ch:
                    learned.update(counter)
            rows += [(ch, "", w, n, "evidence-only") for w, n in learned.most_common() if VI_WORD.match(w)]
            continue
        keys = {tone_key(r): r for r in rs}
        any_counts = Counter()
        for (c, py), counter in evidence.items():
            if c != ch:
                continue
            per_py = Counter()
            for w, n in counter.items():
                k = tone_key(w)
                if k in keys:            # only readings confirmed as Hán-Việt
                    per_py[k] += n
                    any_counts[k] += n
            if py:
                rows += [(ch, py, keys[k], n, "evidence") for k, n in per_py.most_common()]
        listed = [k for k in keys]
        # without evidence, a syllable that is a confirmed Hán-Việt reading somewhere beats a Nôm-only one
        ranked = sorted(listed, key=lambda k: (-any_counts[k], k not in hv_syllables, listed.index(k)))
        rows += [(ch, "", keys[k], any_counts[k], src) for k in ranked]
    header = ("# Hán-Việt readings per character. Built by scripts/build_hanviet_data.py from Wiktionary\n"
              "# (CC BY-SA 4.0), CVDICT by Phong Phan (CC BY-SA 4.0, based on CC-CEDICT) and Unicode Unihan.\n"
              "# License of this file: CC BY-SA 4.0. Columns: char, pinyin ('' = any), reading, evidence, source\n")
    (OUT / "hanviet_chars.tsv").write_text(header + "".join("\t".join(map(str, r)) + "\n" for r in rows), encoding="utf-8")
    lex_header = ("# Sino-Vietnamese words and Chinese proper names with Hán-Việt renderings. Built by\n"
                  "# scripts/build_hanviet_data.py from Wiktionary and CVDICT (both CC BY-SA 4.0). License: CC BY-SA 4.0.\n"
                  "# Columns: simplified, traditional, vietnamese, kind, source\n")
    lex = sorted((s, *v) for s, v in lexicon.items())
    (OUT / "hanviet_words.tsv").write_text(lex_header + "".join("\t".join(r) + "\n" for r in lex), encoding="utf-8")
    if HOLDOUT:
        (OUT / "holdout.tsv").write_text("".join(f"{a}\t{b}\n" for a, b in HELD), encoding="utf-8")
    print(f"wiktionary chars {len(wk_read)}, words {len(wk_words)}; cvdict names aligned {names}; "
          f"char rows {len(rows)}; lexicon {len(lex)}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
