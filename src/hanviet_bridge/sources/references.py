"""Import citation exports from Chinese databases into the research library.

CNKI, Wanfang, VIP (维普), SinoMed and most Chinese platforms let a signed-in user export selected
records as RIS, EndNote (%-tagged) or NoteExpress. Importing those files works with whatever
access the user legitimately has; nothing here logs in to, scrapes or bypasses a provider.
"""
from __future__ import annotations
from pathlib import Path
import re

RIS_MAP = {"TI": "title", "T1": "title", "AU": "authors", "A1": "authors", "PY": "year", "Y1": "year",
           "DA": "year", "JO": "journal", "JF": "journal", "T2": "journal", "DO": "doi", "UR": "url",
           "AB": "abstract", "N2": "abstract", "KW": "keywords", "LA": "language", "VL": "volume",
           "IS": "issue", "SP": "start_page", "EP": "end_page", "PB": "publisher", "SN": "issn"}
ENDNOTE_MAP = {"%T": "title", "%A": "authors", "%D": "year", "%J": "journal", "%B": "journal",
               "%R": "doi", "%U": "url", "%X": "abstract", "%K": "keywords", "%G": "language",
               "%V": "volume", "%N": "issue", "%P": "pages", "%I": "publisher", "%@": "issn"}
NOTEEXPRESS_MAP = {"Title": "title", "Author": "authors", "Year": "year", "Journal": "journal",
                   "Secondary Title": "journal", "DOI": "doi", "URL": "url", "Abstract": "abstract",
                   "Keywords": "keywords", "Language": "language", "Volume": "volume", "Issue": "issue",
                   "Pages": "pages", "Publisher": "publisher", "ISBN/ISSN": "issn"}
MULTI = {"authors", "keywords"}

def _add(rec: dict, field: str, value: str):
    value = value.strip()
    if not value:
        return
    if field in MULTI:
        parts = re.split(r"[;；]\s*", value) if field == "keywords" or ";" in value or "；" in value else [value]
        rec.setdefault(field, []).extend(p for p in parts if p)
    elif field in rec and field == "abstract":
        rec[field] += " " + value
    else:
        rec.setdefault(field, value)

def _finish(rec: dict, fmt: str, index: int) -> dict:
    if "year" in rec:
        m = re.search(r"(1[89]|20)\d{2}", rec["year"])
        rec["year"] = int(m.group(0)) if m else None
    if rec.get("doi"):
        rec["doi"] = re.sub(r"^https?://(dx\.)?doi\.org/", "", rec["doi"].strip(), flags=re.I)
    if not rec.get("language") and any("一" <= c <= "鿿" for c in rec.get("title", "")):
        rec["language"] = "zh"
    rec.update({"provider": f"import:{fmt}", "provider_id": rec.get("doi") or f"{fmt}:{index}"})
    rec.setdefault("authors", [])
    return rec

def parse_ris(text: str) -> list[dict]:
    records, rec = [], {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  -\s?(.*)$", line)
        if not m:
            continue
        tag, value = m.groups()
        if tag == "TY":
            rec = {"type": value.strip()}
        elif tag == "ER":
            if rec:
                records.append(_finish(rec, "ris", len(records) + 1))
            rec = {}
        elif tag in RIS_MAP:
            _add(rec, RIS_MAP[tag], value)
    return records

def parse_endnote(text: str) -> list[dict]:
    records = []
    for chunk in re.split(r"\n\s*\n", text):
        rec = {}
        for line in chunk.splitlines():
            m = re.match(r"^(%[A-Z0-9@])\s+(.*)$", line)
            if m and m.group(1) == "%0":
                rec["type"] = m.group(2).strip()
            elif m and m.group(1) in ENDNOTE_MAP:
                _add(rec, ENDNOTE_MAP[m.group(1)], m.group(2))
        if rec.get("title"):
            records.append(_finish(rec, "endnote", len(records) + 1))
    return records

def parse_noteexpress(text: str) -> list[dict]:
    records = []
    for chunk in re.split(r"\n\s*\n", text):
        rec = {}
        for line in chunk.splitlines():
            m = re.match(r"^\{([^}]+)\}:\s*(.*)$", line)
            if m and m.group(1) == "Reference Type":
                rec["type"] = m.group(2).strip()
            elif m and m.group(1) in NOTEEXPRESS_MAP:
                _add(rec, NOTEEXPRESS_MAP[m.group(1)], m.group(2))
        if rec.get("title"):
            records.append(_finish(rec, "noteexpress", len(records) + 1))
    return records

def import_references(path: Path) -> dict:
    text = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030"):
        try:
            text = text.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Cannot decode citation file (expected UTF-8 or GBK)")
    if re.search(r"^TY  -", text, re.M):
        fmt, records = "ris", parse_ris(text)
    elif re.search(r"^\{Reference Type\}:", text, re.M):
        fmt, records = "noteexpress", parse_noteexpress(text)
    elif re.search(r"^%[0TA] ", text, re.M):
        fmt, records = "endnote", parse_endnote(text)
    else:
        raise ValueError("Unrecognized citation format: export RIS, EndNote or NoteExpress from the database")
    if not records:
        raise ValueError(f"No records found in {fmt} file")
    return {"format": fmt, "file": path.name, "records": records,
            "rights": "Metadata exported by the user from their own database access; full texts are not included."}
