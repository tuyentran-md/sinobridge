"""Per-project term memory: names and terms with one agreed rendering in the target language.

terms.json maps Chinese -> {render, type, origin, status, source, first_segment, count}
("vi" is accepted as the rendering key of older Vietnamese workspaces).

* status "locked": set by a person (`sinobridge terms set`), always enforced.
* status "auto": first rendering seen (Hán-Việt or pinyin/established English form for Chinese names,
  the model's choice for terms); enforced afterwards so chapter 12 says what chapter 1 said.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from .store import save_json
from . import hanviet, names

NAME_TYPES = {"person", "place", "org", "dynasty", "work", "era"}

def path(workspace: Path) -> Path:
    return workspace / "terms.json"

def rendering(entry: dict) -> str | None:
    return entry.get("render") or entry.get("vi")

def load(workspace: Path) -> dict:
    p = path(workspace)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

def save(workspace: Path, terms: dict) -> None:
    save_json(path(workspace), dict(sorted(terms.items(), key=lambda kv: (-len(kv[0]), kv[0]))))

def set_term(workspace: Path, zh: str, render: str, type_: str = "term", note: str | None = None) -> dict:
    terms = load(workspace)
    entry = terms.get(zh, {})
    entry.pop("vi", None)
    entry.update({"render": render, "type": type_, "status": "locked", "source": "user",
                  "updated_utc": datetime.now(timezone.utc).isoformat()})
    if note:
        entry["note"] = note
    terms[zh] = entry
    save(workspace, terms)
    return {zh: entry}

def remove_term(workspace: Path, zh: str) -> dict:
    terms = load(workspace)
    if zh not in terms:
        raise RuntimeError(f"{zh} is not in the term memory")
    removed = terms.pop(zh)
    save(workspace, terms)
    return {"removed": zh, "was": removed}

def in_text(terms: dict, text: str) -> dict:
    """Terms occurring in text; a longer term hides the shorter ones inside it (诸葛亮 hides 葛)."""
    found, covered = {}, [False] * len(text)
    for zh in sorted(terms, key=len, reverse=True):
        start = text.find(zh)
        while start != -1:
            if not any(covered[start:start + len(zh)]):
                found[zh] = terms[zh]
                for i in range(start, start + len(zh)):
                    covered[i] = True
            start = text.find(zh, start + 1)
    return found

def name_hints(text: str, target: str = "vi") -> dict:
    """Known Chinese proper names in text with their rendering in the target language."""
    hints = {}
    if target == "en":
        pn = names.proper_nouns()
        i = 0
        while i < len(text):
            for size in range(min(8, len(text) - i), 1, -1):
                chunk = text[i:i + size]
                if chunk in pn and pn[chunk][1]:
                    hints[chunk] = pn[chunk][1]
                    i += size - 1
                    break
            i += 1
        return hints
    for chunk, entry, _py in hanviet._segment(text):
        if entry and entry[1] == "name" and len(chunk) >= 2:
            hints[chunk] = entry[0]
    return hints

def plausible_hanviet(zh: str, vi: str) -> bool:
    """True if vi reads zh syllable by syllable with known Hán-Việt readings (any of them)."""
    words = vi.split()
    if len(words) != len(zh):
        return False
    return all(hanviet.tone_key(w) in {hanviet.tone_key(r) for r, _ in hanviet.readings(c)} for c, w in zip(zh, words))

def suggested_rendering(entity: dict, target: str = "vi") -> str | None:
    """Standard rendering for Chinese-origin names; None for foreign names and ordinary terms.

    A dictionary rendering wins. Otherwise, for Vietnamese, if the model chose another valid Hán-Việt
    reading of the same characters (it saw the context: 乐山 Lạc Sơn), the model's choice is kept;
    for English, a model rendering that differs only in spacing/case/apostrophes is kept.
    """
    if entity.get("type") not in NAME_TYPES or entity.get("origin", "chinese") != "chinese":
        return None
    result = names.render_name(entity["zh"], entity.get("type"), target)
    model = (entity.get("render") or entity.get("vi") or "").strip()
    if result["exact"] or not model:
        return result["render"]
    if target == "vi" and plausible_hanviet(entity["zh"], model):
        return model
    if target == "en" and model.replace("'", "").replace(" ", "").lower() == \
            result["render"].replace("'", "").replace(" ", "").lower():
        return model
    return result["render"]

def record(workspace: Path, segment_id: str, entities: list[dict], target: str = "vi") -> list[dict]:
    """Add model-detected entities to memory. Returns notes where the model's rendering differs."""
    terms = load(workspace)
    notes = []
    for e in entities:
        zh = (e.get("zh") or "").strip()
        if not zh or len(zh) > 30:
            continue
        standard = suggested_rendering(e, target)
        model = (e.get("render") or e.get("vi") or "").strip()
        if zh in terms:
            terms[zh]["count"] = terms[zh].get("count", 1) + 1
            continue
        terms[zh] = {"render": standard or model, "type": e.get("type", "term"), "origin": e.get("origin", "chinese"),
                     "status": "auto", "source": ("hanviet" if target == "vi" else "pinyin") if standard else "model",
                     "first_segment": segment_id, "count": 1}
        if standard and model and hanviet.norm_text(standard) != hanviet.norm_text(model):
            terms[zh]["model_rendering"] = model
            notes.append({"zh": zh, "model": model, "standard": standard})
    save(workspace, terms)
    return notes
