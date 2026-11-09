"""Evidence-based deterministic checks; never pretend these prove semantic correctness."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import re
import unicodedata
from pathlib import Path
from .store import load_project, load_segments, save_json
from .review import approval_is_current

NUMBERS = re.compile(r"(?<![0-9A-Za-z])(?:\d+(?:[.,]\d+)*)(?:\s?%)?")
DOIS = re.compile(r"10\.\d{4,9}/[^\s<>\"'\]\[，；]+", re.IGNORECASE)
URLS = re.compile(r"https?://[^\s<>\]\[\)\(]+", re.IGNORECASE)
CITATIONS = re.compile(r"\[\d+(?:\s*[-,–]\s*\d+)*\]")
CHINESE_TERMS = ("中华人民共和国", "中国", "中国大陆", "人民法院", "医保", "国家卫健委")

ZH_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
ZH_UNITS = {"十": 10, "百": 100, "千": 1000}
ZH_BIG = {"万": 10_000, "亿": 100_000_000}
ZH_NUMERAL = re.compile(r"[零〇一二两三四五六七八九十百千万亿]+")  # soft: may satisfy, never reported

def capture(regex, txt):
    return Counter(m.group(0).rstrip(".,;。；") for m in regex.finditer(txt))

def zh_numeral_value(token: str) -> int | None:
    """Parse simple Chinese numerals (e.g. 一百二十 -> 120). Returns None if unsure."""
    total = section = digit = 0
    seen = False
    for ch in token:
        if ch in ZH_DIGITS:
            digit, seen = ZH_DIGITS[ch], True
        elif ch in ZH_UNITS:
            section += (digit or 1) * ZH_UNITS[ch]
            digit, seen = 0, True
        elif ch in ZH_BIG:
            total += (section + digit) * ZH_BIG[ch]
            section = digit = 0
        else:
            return None
    return total + section + digit if seen else None

def number_candidates(token: str) -> frozenset:
    """All plausible numeric values of a token under zh/en/vi separators.

    "1,25" (vi) and "1.25" (zh/en) both yield 1.25; "1.200"/"1,200" yield {1.2, 1200}.
    Ambiguity is resolved by intersection with the other language, never by guessing.
    """
    pct = token.rstrip().endswith("%")
    core = token.replace("%", "").strip()
    seps = set(re.findall(r"[.,]", core))
    cands = set()
    def add(text):
        try:
            cands.add(float(text))
        except ValueError:
            pass
    if not seps:
        add(core)
    else:
        for dec in (".", ","):
            other = "," if dec == "." else "."
            if core.count(dec) <= 1:
                integer, _, frac = core.partition(dec)
                groups = integer.split(other)
                if len(groups) == 1 or all(len(g) == 3 for g in groups[1:]):
                    add("".join(groups) + ("." + frac if frac else ""))
        # pure thousands grouping with a single separator type, e.g. 1.200.000
        for sep in seps:
            groups = core.split(sep)
            if len(seps) == 1 and len(groups) > 1 and all(len(g) == 3 for g in groups[1:]):
                add("".join(groups))
    return frozenset((v, pct) for v in cands)

# "120万" == "1.2 million" == "1,2 triệu": scale words after a number
MULTIPLIERS = {"万": 1e4, "萬": 1e4, "亿": 1e8, "億": 1e8, "千": 1e3, "百万": 1e6, "百萬": 1e6, "千万": 1e7, "千萬": 1e7,
               "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "k": 1e3, "m": 1e6, "bn": 1e9,
               "nghìn": 1e3, "ngàn": 1e3, "vạn": 1e4, "triệu": 1e6, "tỷ": 1e9, "tỉ": 1e9, "nghìn tỷ": 1e12}
MULTIPLIER = re.compile(r"\s?(" + "|".join(sorted(map(re.escape, MULTIPLIERS), key=len, reverse=True)) + r")(?![A-Za-zÀ-ỹ])",
                        re.IGNORECASE)

MONTHS = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|"
                    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b\.?")   # capitalized only: "may" is a verb
MONTH_NUM = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

def numeric_tokens(text: str) -> list[tuple[str, frozenset, bool]]:
    """(token, candidate values, soft). Chinese-numeral tokens are `soft`: they can satisfy
    a counterpart (一百二十 ~ 120) but are never reported alone, because words such as
    万一 or 一一 are not quantities."""
    text = unicodedata.normalize("NFKC", text)
    out = []
    for m in NUMBERS.finditer(text):
        token = m.group(0).rstrip(".,;。；")
        cands = number_candidates(token)
        unit = MULTIPLIER.match(text, m.end())
        if unit and "%" not in token:
            factor = MULTIPLIERS[unit.group(1).lower()]
            # keep the bare value too (a translator may write "120 vạn"); add the scaled value
            cands = cands | frozenset((round(v * factor, 4), pct) for v, pct in cands)
            token += unit.group(1)
        out.append((token, cands, False))
    for m in MONTHS.finditer(text):   # "March 2025" for 2025年3月: soft, never reported alone
        out.append((m.group(0), frozenset({(float(MONTH_NUM[m.group(0).lower()[:3]]), False)}), True))
    for m in ZH_NUMERAL.finditer(text):
        value = zh_numeral_value(m.group(0))
        if value is not None:
            out.append((m.group(0), frozenset({(float(value), False)}), True))
    return out

def unmatched_numbers(left: str, right: str) -> list[str]:
    """Tokens in `left` whose value has no counterpart in `right` (multiset matching)."""
    pool = [c for _, c, _ in numeric_tokens(right)]
    missing = []
    for token, cands, soft in sorted(numeric_tokens(left), key=lambda t: t[2]):
        hit = next((j for j, other in enumerate(pool) if cands & other), None)
        if hit is not None:
            pool.pop(hit)
        elif not soft:
            missing.append(token)
    return missing

def make_issue(segment: dict, code: str, severity: str, detail: str) -> dict:
    return {"segment_id": segment["id"], "location": segment["location"],
            "code": code, "severity": severity, "detail": detail, "status": "OPEN"}

CHINA_WORDS = {"vi": ("trung quốc", "đại lục", "trung hoa"),
               "en": ("china", "chinese", "prc", "mainland", "people's republic")}

def check_segment(seg: dict, glossary: dict | None = None, lang: str = "vi") -> list[dict]:
    if not seg.get("translation"):
        return [make_issue(seg, "MISSING_TRANSLATION", "HIGH", "No translated passage")]
    original, target = seg["source"], seg["translation"]
    issues = []
    missing_num, added_num = unmatched_numbers(original, target), unmatched_numbers(target, original)
    if missing_num:
        issues.append(make_issue(seg, "NUMERIC_MISMATCH", "HIGH", f"Source numbers without matching value in target: {missing_num}"))
    if added_num:
        issues.append(make_issue(seg, "ADDED_NUMERIC_MISMATCH", "HIGH", f"Target numbers without matching value in source: {added_num}"))
    for name, pattern in [("DOI_MISMATCH", DOIS),
                          ("URL_MISMATCH", URLS), ("CITATION_MISMATCH", CITATIONS)]:
        missing = capture(pattern, original) - capture(pattern, target)
        if missing:
            issues.append(make_issue(seg, name, "HIGH", f"Source tokens absent in target: {dict(missing)}"))
        added = capture(pattern, target) - capture(pattern, original)
        if added:
            issues.append(make_issue(seg, "ADDED_"+name, "HIGH", f"Target tokens absent in source: {dict(added)}"))
    if any(term in original for term in CHINESE_TERMS) and not any(t in target.lower() for t in CHINA_WORDS.get(lang, CHINA_WORDS["vi"])):
        issues.append(make_issue(seg, "JURISDICTION_CONTEXT", "MEDIUM",
                                 "China-specific terms detected; manually verify the jurisdiction is explicit in the translation"))
    for zh, vi in (glossary or {}).items():
        if zh in original and vi.lower() not in target.lower():
            issues.append(make_issue(seg, "GLOSSARY_MISMATCH", "MEDIUM", f"{zh} -> {vi}"))
    if seg.get("ambiguities"):
        issues.append(make_issue(seg, "MODEL_AMBIGUITY", "HIGH",
                                 "Translator marked ambiguities: " + "; ".join(seg["ambiguities"])))
    if seg["status"] == "APPROVED" and not approval_is_current(seg):
        issues.append(make_issue(seg, "STALE_APPROVAL", "HIGH", "Translation changed after approval; re-review required"))
    if seg["kind"] == "table":
        issues.append(make_issue(seg, "TABLE_MANUAL_QA", "MEDIUM", "Verify cell ordering, denominators and table structure"))
    return issues

def check_terms(seg: dict, memory: dict) -> list[dict]:
    """Every remembered name/term in the source must keep its agreed rendering."""
    from . import terms as term_memory
    from .hanviet import contains
    if not seg.get("translation"):
        return []
    issues = []
    for zh, t in term_memory.in_text(memory, seg["source"]).items():
        vi = term_memory.rendering(t)
        if vi and not contains(seg["translation"], vi):
            locked = t.get("status") == "locked"
            issues.append(make_issue(seg, "TERM_INCONSISTENT", "HIGH" if locked else "MEDIUM",
                                     f"{zh} -> expected '{vi}' ({t.get('type', 'term')}, {t.get('status')})"))
    return issues

def audit(workspace: Path, glossary_path: Path | None = None) -> dict:
    from . import terms as term_memory
    proj = load_project(workspace)
    segs = load_segments(workspace)
    glossary = {}
    if glossary_path:
        import json
        glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
    memory = term_memory.load(workspace)
    target = proj.get("target_language", "vi")
    issues = [issue for s in segs for issue in check_segment(s, glossary, target) + check_terms(s, memory)]
    missing = sum(not s.get("translation") for s in segs)
    critical_high = sum(issue["severity"] in ("CRITICAL", "HIGH") for issue in issues)
    reviewed = sum(approval_is_current(s) for s in segs)
    gates = {f"G{i}": {"status": "PENDING_HUMAN_REVIEW"} for i in range(1,12)}
    gates["G6"] = {"status": "CHECKED_PARTIAL", "basis": "Glossary and term-memory rendering checks (string level)"}
    gates["G7"] = {"status": "CHECKED_PARTIAL", "basis": "Numeric/DOI/citation string checks; not scientific fact verification"}
    gates["G8"] = {"status": "CHECKED_PARTIAL", "basis": "Jurisdiction keyword heuristic; manual review required"}
    gates["G9"] = {"status": "FAIL" if missing else "CHECKED_PARTIAL",
                   "basis": "Source-to-translation segment coverage, not formatting/layout integrity"}
    out = {
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": proj["source_sha256"], "segment_count": len(segs),
        "translated_drafts_or_better": len(segs)-missing, "approved_segments": reviewed,
        "missing_translations": missing, "unresolved_high_or_critical": critical_high,
        "gates": gates, "issues": issues,
        "release_readiness": "BLOCKED" if missing or critical_high or reviewed != len(segs) else "PENDING_HUMAN_GATES",
        "disclaimer": "No LLM translation or automated check is equivalent to investigator/editor approval."
    }
    save_json(workspace / "qa.json", out)
    return out
