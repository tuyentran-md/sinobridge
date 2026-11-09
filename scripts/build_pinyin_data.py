#!/usr/bin/env python3
"""Build the bundled pinyin / English-name data in src/sinobridge/data/.

Inputs (download yourself, then pass their paths):
  Unihan (unzipped)  https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip              Unicode License v3
  CC-CEDICT          https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip  CC BY-SA 4.0

Outputs:
  pinyin_chars.tsv  char, most common Mandarin reading (tone marks), all readings     (Unihan: Unicode License)
  names_en.tsv      simplified, traditional, numbered pinyin, English name or ''        (CC-CEDICT: CC BY-SA 4.0)

names_en.tsv keeps CC-CEDICT proper nouns (capitalized pinyin). The English name is the leading run of
capitalized words of the first gloss ("Zhuge Liang (181-234), ..." -> "Zhuge Liang"; "Beijing municipality"
-> "Beijing"), following one "see X" cross-reference when needed.

Usage: python3 scripts/build_pinyin_data.py UNIHAN_DIR cedict_ts.u8
"""
from __future__ import annotations
from collections import defaultdict
import os
from pathlib import Path
import re
import sys

OUT = Path(os.getenv("PINYIN_OUT") or Path(__file__).resolve().parents[1] / "src" / "sinobridge" / "data")
CJK = re.compile(r"^[㐀-鿿豈-﫿\U00020000-\U0002ffff]+$")
NAME_WORD = re.compile(r"^[A-Z][A-Za-z'’\-āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]*$")
STOP = {"The", "A", "An", "See", "Variant", "Old", "Abbr", "Surname", "Taiwan", "Japanese", "Korean", "Chinese"}

def english_head(gloss: str) -> str:
    head = re.split(r"[(,;:/]", gloss)[0].strip()
    words = []
    for w in head.split():
        if not NAME_WORD.match(w) or (not words and w in STOP):
            break
        words.append(w)
    return " ".join(words)

def main(unihan_dir, cedict):
    readings = {}
    for line in (Path(unihan_dir) / "Unihan_Readings.txt").read_text(encoding="utf-8").splitlines():
        p = line.split("\t")
        if len(p) != 3:
            continue
        ch = chr(int(p[0][2:], 16))
        if p[1] == "kMandarin":
            readings.setdefault(ch, [None, []])[0] = p[2].split()[0]
        elif p[1] == "kXHC1983":   # modern dictionary readings (kHanyuPinyin adds archaic ones)
            for r in re.findall(r"[:,]([^\s,:]+)", p[2]):
                lst = readings.setdefault(ch, [None, []])[1]
                if r not in lst:
                    lst.append(r)
    rows = []
    for ch, (main_r, others) in sorted(readings.items()):
        if not main_r:
            continue
        alls = [main_r] + [r for r in others if r != main_r]
        rows.append(f"{ch}\t{main_r}\t{' '.join(alls)}\n")
    header = ("# Mandarin readings per character from Unicode Unihan (kMandarin, kXHC1983).\n"
              "# Unicode License v3, (c) Unicode, Inc. Columns: char, most common reading, all readings\n")
    (OUT / "pinyin_chars.tsv").write_text(header + "".join(rows), encoding="utf-8")

    entries = {}
    by_key = defaultdict(list)
    for line in Path(cedict).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\S+) (\S+) \[([^\]]+)\] /(.*)/\s*$", line)
        if not m:
            continue
        trad, simp, py, defs = m.groups()
        by_key[simp].append((trad, py, defs))
    for simp, items in by_key.items():
        for trad, py, defs in items:
            sylls = py.split()
            if not CJK.match(simp) or len(sylls) != len(simp) or not sylls[0][:1].isupper():
                continue
            gloss = defs.split("/")[0]
            name = english_head(gloss)
            ref = re.match(r"^see (?:[^|\[]+\|)?([^\[\s]+)\[", gloss)
            if not name and ref and ref.group(1) in by_key:
                name = english_head(by_key[ref.group(1)][0][2].split("/")[0])
                if ref.group(1).startswith(simp) and len(ref.group(1)) > len(simp):
                    # 四川 -> see 四川省 "Sichuan Province": the short form has no administrative suffix
                    name = re.sub(r"\s+(Province|City|County|District|Municipality|Prefecture|Town|Township|"
                                  r"Autonomous Region|Autonomous Prefecture|Autonomous County|Special Administrative Region)$",
                                  "", name)
            if simp not in entries or (name and not entries[simp][2]):
                entries[simp] = (trad, py, name)
    lines = [f"{s}\t{t}\t{py}\t{name}\n" for s, (t, py, name) in sorted(entries.items())]
    header = ("# Chinese proper nouns from CC-CEDICT (CC BY-SA 4.0, MDBG; CEDICT (C) 1997-1998 Paul Andrew Denisowski).\n"
              "# Built by scripts/build_pinyin_data.py. License of this file: CC BY-SA 4.0.\n"
              "# Columns: simplified, traditional, numbered pinyin, English name ('' if the gloss has none)\n")
    (OUT / "names_en.tsv").write_text(header + "".join(lines), encoding="utf-8")
    print(f"chars {len(rows)}; proper nouns {len(lines)}; with English name {sum(1 for l in lines if not l.endswith(chr(9)+chr(10)))}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
