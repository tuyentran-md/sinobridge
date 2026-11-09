"""Per-project term memory: names and terms with one agreed Vietnamese rendering.

terms.json maps Chinese -> {vi, type, origin, status, source, first_segment, count}.

* status "locked": set by a person (`sinobridge terms set`), always enforced.
* status "auto": first rendering seen (Hán-Việt for Chinese names, the model's choice for terms);
  enforced afterwards so chapter 12 says what chapter 1 said, until a person changes it.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
from .store import save_json
from . import hanviet

NAME_TYPES = {"person", "place", "org", "dynasty", "work", "era"}

def path(workspace: Path) -> Path:
    return workspace / "terms.json"

def load(workspace: Path) -> dict:
    p = path(workspace)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

def save(workspace: Path, terms: dict) -> None:
    save_json(path(workspace), dict(sorted(terms.items(), key=lambda kv: (-len(kv[0]), kv[0]))))

def set_term(workspace: Path, zh: str, vi: str, type_: str = "term", note: str | None = None) -> dict:
    terms = load(workspace)
    entry = terms.get(zh, {})
    entry.update({"vi": vi, "type": type_, "status": "locked", "source": "user",
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

def name_hints(text: str) -> dict:
    """Known Chinese proper names in text (bundled lexicon), with their Hán-Việt rendering."""
    hints = {}
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

def suggested_rendering(entity: dict) -> str | None:
    """Hán-Việt for Chinese-origin names; None for foreign names and ordinary terms.

    A dictionary rendering wins. Otherwise, if the model chose another valid reading of the same
    characters (it saw the context: 乐山 Lạc Sơn, not Nhạc Sơn), the model's choice is kept.
    """
    if entity.get("type") not in NAME_TYPES or entity.get("origin", "chinese") != "chinese":
        return None
    result = hanviet.transliterate(entity["zh"])
    model_vi = (entity.get("vi") or "").strip()
    if not result["exact"] and model_vi and plausible_hanviet(entity["zh"], model_vi):
        return model_vi
    return result["hanviet"]

def record(workspace: Path, segment_id: str, entities: list[dict]) -> list[dict]:
    """Add model-detected entities to memory. Returns notes about renderings that differ from memory."""
    terms = load(workspace)
    notes = []
    for e in entities:
        zh = (e.get("zh") or "").strip()
        if not zh or len(zh) > 30:
            continue
        hv = suggested_rendering(e)
        vi = (e.get("vi") or "").strip()
        if zh in terms:
            terms[zh]["count"] = terms[zh].get("count", 1) + 1
            continue
        terms[zh] = {"vi": hv or vi, "type": e.get("type", "term"), "origin": e.get("origin", "chinese"),
                     "status": "auto", "source": "hanviet" if hv else "model", "first_segment": segment_id,
                     "count": 1}
        if hv and vi and hanviet.norm_text(hv) != hanviet.norm_text(vi):
            terms[zh]["model_rendering"] = vi
            notes.append({"zh": zh, "model": vi, "hanviet": hv})
    save(workspace, terms)
    return notes
