"""Human review: traceable revisions, approvals bound to exact text, bilingual review page."""
from __future__ import annotations
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from .store import load_project, load_segments, save_segments, save_text, sha256

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def text_hash(text: str | None) -> str | None:
    return sha256(text.encode("utf-8"))[:16] if text else None

def find_segment(segs: list[dict], segment_id: str) -> dict:
    matches = [s for s in segs if s["id"] == segment_id]
    if len(matches) != 1:
        raise RuntimeError(f"Segment {segment_id} not found")
    return matches[0]

def revise(workspace: Path, segment_id: str, new_text: str, reviewer: str, reason: str,
           severity: str | None = None, issue_code: str | None = None) -> dict:
    """Replace a translation, keeping the previous text, who, why and severity (append-only)."""
    if not new_text.strip() or not reviewer.strip() or not reason.strip():
        raise ValueError("Revision needs non-empty text, reviewer and reason")
    if severity and severity.upper() not in SEVERITIES:
        raise ValueError(f"Severity must be one of {SEVERITIES}")
    segs = load_segments(workspace)
    seg = find_segment(segs, segment_id)
    entry = {"utc": now(), "reviewer": reviewer, "reason": reason,
             "severity": severity.upper() if severity else None, "issue_code": issue_code,
             "previous": seg.get("translation"), "previous_status": seg["status"]}
    seg.setdefault("history", []).append(entry)
    seg["translation"] = new_text.strip()
    seg["status"] = "REVISED"
    seg.pop("approval", None)  # any approval referred to the old text
    save_segments(workspace, segs)
    return {"segment": segment_id, "status": "REVISED", "revisions": len(seg["history"])}

def approve(workspace: Path, segment_id: str, reviewer: str, evidence: str) -> dict:
    segs = load_segments(workspace)
    seg = find_segment(segs, segment_id)
    if not seg.get("translation"):
        raise RuntimeError("Segment has no translation")
    seg["status"] = "APPROVED"
    seg["approval"] = {"reviewer": reviewer, "evidence": evidence, "utc": now(),
                       "translation_hash": text_hash(seg["translation"])}
    save_segments(workspace, segs)
    return {"segment": segment_id, "status": "APPROVED", "reviewer": reviewer}

def approval_is_current(seg: dict) -> bool:
    appr = seg.get("approval") or {}
    return seg["status"] == "APPROVED" and appr.get("translation_hash") == text_hash(seg.get("translation"))

UI = {
    "vi": {"title": "Song ngữ: ", "draft": "Bản dịch cần đối chiếu với bản gốc", "only": "chỉ đoạn có cảnh báo",
           "showzh": "hiện cả tiếng Trung", "missing": "chưa dịch", "noaudit": "chưa kiểm tra tự động",
           "pick": "Chọn một đoạn để xem bản gốc tiếng Trung, các cảnh báo và lịch sử sửa.",
           "source": "Nguồn tiếng Trung", "hover": "Rê chuột lên chữ Hán để xem âm Hán Việt.", "location": "vị trí",
           "status": "trạng thái", "issues": "Cảnh báo tự động", "noflags": "Không có cảnh báo tự động cho đoạn này.",
           "terms": "Tên riêng / thuật ngữ", "locked": "đã khoá", "auto": "tự động", "model": "mô hình",
           "notes": "Chỗ cần xem lại / ghi chú", "approval": "Duyệt", "notapproved": "chưa duyệt",
           "stale": "Bản dịch đã sửa. Cần duyệt lại.", "history": "Lịch sử sửa"},
    "en": {"title": "Bilingual: ", "draft": "Check this translation against the source", "only": "only passages with flags",
           "showzh": "show Chinese text", "missing": "untranslated", "noaudit": "automatic checks not run",
           "pick": "Select a passage to see its Chinese source, flags and edit history.",
           "source": "Chinese source", "hover": "Hover over a character to see its pinyin.", "location": "location",
           "status": "status", "issues": "QA flags", "noflags": "No automatic flags for this passage.",
           "terms": "Names / terms", "locked": "locked", "auto": "auto", "model": "model",
           "notes": "Questions / notes", "approval": "Approval", "notapproved": "not approved",
           "stale": "Translation edited after approval. Review again.", "history": "Revision history"},
}

PAGE = """<!DOCTYPE html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--line:#d8d8d8;--muted:#666;--sel:#fff6d6;--hi:#b42318;--med:#b54708;--low:#475467}
*{box-sizing:border-box}body{margin:0;font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1d1d1d}
header{padding:.6rem 1rem;border-bottom:1px solid var(--line);display:flex;gap:1rem;flex-wrap:wrap;align-items:baseline}
header b{font-size:1.05rem}.tag{font-size:.8rem;color:var(--muted)}.draft{color:var(--hi);font-weight:600}
main{display:grid;grid-template-columns:minmax(0,3fr) minmax(280px,2fr);height:calc(100vh - 3.2rem)}
#text{overflow:auto;padding:1rem 1.5rem}#side{overflow:auto;border-left:1px solid var(--line);padding:1rem;background:#fafafa}
.seg{padding:.35rem .5rem;margin:0 -.5rem .4rem;border-radius:4px;cursor:pointer;border-left:3px solid transparent}
.seg:hover{background:#f3f3f3}.seg.sel{background:var(--sel)}
.seg.h{font-weight:700;font-size:1.15rem;margin-top:1rem}.seg.missing{color:var(--muted);font-style:italic}
.seg.sev-CRITICAL,.seg.sev-HIGH{border-left-color:var(--hi)}.seg.sev-MEDIUM{border-left-color:var(--med)}.seg.sev-LOW{border-left-color:var(--low)}
.zh{font-family:"PingFang SC","Noto Serif CJK SC","Songti SC",serif;font-size:1.1rem;white-space:pre-wrap;background:#fff;border:1px solid var(--line);padding:.6rem;border-radius:4px}
h3{font-size:.85rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:1.1rem 0 .3rem}
.issue{border-left:3px solid var(--low);padding:.2rem .5rem;margin:.3rem 0;background:#fff;font-size:.9rem}
.issue.CRITICAL,.issue.HIGH{border-color:var(--hi)}.issue.MEDIUM{border-color:var(--med)}
.rev{font-size:.88rem;border-top:1px dashed var(--line);padding:.4rem 0}.rev del{color:var(--muted)}
code{font-size:.85em}.hv{cursor:help;border-bottom:1px dotted #bbb;position:relative}.hv:hover{background:#e8f0ff}
.hv:hover::after{content:attr(data-hv);position:absolute;left:-.2rem;bottom:125%;white-space:nowrap;
background:#1d2939;color:#fff;font:600 .8rem/1.2 system-ui,sans-serif;padding:.25rem .45rem;border-radius:4px;z-index:5}.filters label{font-size:.85rem;margin-right:.6rem}
@media (max-width:800px){main{grid-template-columns:1fr;height:auto}#side{border-left:0;border-top:1px solid var(--line)}}
</style></head><body>
<header><b>__TITLE__</b><span class="draft">__U_draft__</span>
<span class="tag">source SHA256 __SHA__ · audit __AUDIT__</span>
<span class="filters"><label><input type="checkbox" id="onlyIssues"> __U_only__</label>
<label><input type="checkbox" id="showZh"> __U_showzh__</label></span></header>
<main><div id="text"></div><aside id="side"><p class="tag">__U_pick__</p></aside></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const U=D.ui;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const rank={CRITICAL:0,HIGH:1,MEDIUM:2,LOW:3};
const zhHints=t=>[...t].map(c=>D.hints[c]?`<span class="hv" data-hv="${esc(D.hints[c])}">${esc(c)}</span>`:esc(c)).join('');
const worst=s=>(D.issues[s.id]||[]).map(i=>i.severity).sort((a,b)=>rank[a]-rank[b])[0];
function render(){
  const only=document.getElementById('onlyIssues').checked, zh=document.getElementById('showZh').checked;
  document.getElementById('text').innerHTML=D.segments.filter(s=>!only||worst(s)).map(s=>{
    const w=worst(s), cls=['seg',s.kind==='heading'?'h':'',s.translation?'':'missing',w?'sev-'+w:''].join(' ');
    const strip=t=>s.kind==='heading'?String(t).replace(/^\\s*#+\\s*/,''):t;
    const body=s.translation?esc(strip(s.translation)):'['+U.missing+'] '+esc(strip(s.source));
    return `<div class="${cls}" data-id="${s.id}" id="seg-${s.id}">${body}${zh&&s.translation?`<div class="zh" style="margin-top:.3rem;font-size:.95rem">${esc(s.source)}</div>`:''}</div>`}).join('');
}
function show(id){
  const s=D.segments.find(x=>x.id===id); if(!s) return;
  document.querySelectorAll('.seg.sel').forEach(e=>e.classList.remove('sel'));
  const el=document.getElementById('seg-'+id); if(el) el.classList.add('sel');
  const iss=D.issues[id]||[], hist=s.history||[];
  const terms=Object.entries(D.terms).filter(([zh])=>s.source.includes(zh));
  const appr=s.approval?`${esc(s.approval.reviewer)} · ${esc(s.approval.utc)} · ${esc(s.approval.evidence)}${s.approval_current?'':' <b style="color:var(--hi)">('+U.stale+')</b>'}`:U.notapproved;
  document.getElementById('side').innerHTML=`
  <h3>${U.source}</h3><div class="zh">${zhHints(s.source)}</div><p class="tag">${U.hover}</p>
  <p class="tag">ID <code>${esc(s.id)}</code> · ${U.location} <code>${esc(s.location)}</code> · ${esc(s.kind)} · ${U.status} <b>${esc(s.status)}</b>${s.model?` · model ${esc(s.model.provider)}/${esc(s.model.name)}`:''}</p>
  <h3>${U.issues} (${iss.length})</h3>${iss.length?iss.map(i=>`<div class="issue ${esc(i.severity)}"><b>${esc(i.severity)}</b> ${esc(i.code)}<br>${esc(i.detail)}</div>`).join(''):'<p class="tag">'+U.noflags+'</p>'}
  <h3>${U.terms} (${terms.length})</h3>${terms.length?terms.map(([zh,t])=>`<div class="issue ${t.status==='locked'?'':'LOW'}"><b>${esc(zh)}</b> → ${esc(t.render||t.vi||'?')} <span class="tag">${esc(t.type||'')} · ${t.status==='locked'?U.locked:U.auto}${t.model_rendering?' · '+U.model+': '+esc(t.model_rendering):''}</span></div>`).join(''):'<p class="tag">—</p>'}
  <h3>${U.notes}</h3>${[...(s.ambiguities||[]).map(a=>'⚠ '+esc(a)),...(s.notes||[]).map(esc)].map(x=>`<div>${x}</div>`).join('')||'<p class="tag">—</p>'}
  <h3>${U.approval}</h3><p>${appr}</p>
  <h3>${U.history} (${hist.length})</h3>${hist.slice().reverse().map(h=>`<div class="rev">${esc(h.utc)} · <b>${esc(h.reviewer)}</b>${h.severity?' · '+esc(h.severity):''}${h.issue_code?' · '+esc(h.issue_code):''}<br>${esc(h.reason)}<br><del>${esc(h.previous)}</del></div>`).join('')||'<p class="tag">—</p>'}`;
  history.replaceState(null,'','#'+id);
}
document.getElementById('text').addEventListener('click',e=>{const t=e.target.closest('.seg'); if(t) show(t.dataset.id)});
document.getElementById('onlyIssues').onchange=render; document.getElementById('showZh').onchange=render;
render(); if(location.hash) show(location.hash.slice(1));
</script></body></html>"""

def review_html(workspace: Path, outfile: Path) -> Path:
    """Self-contained offline bilingual review page (no network, no server)."""
    project, segs = load_project(workspace), load_segments(workspace)
    qa_path = workspace / "qa.json"
    lang = project.get("target_language", "vi") if project.get("target_language") in UI else "vi"
    ui = UI[lang]
    issues, audited = {}, ui["noaudit"]
    if qa_path.is_file():
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
        if qa.get("source_sha256") == project["source_sha256"]:
            audited = qa.get("audited_utc", "?")
            for issue in qa.get("issues", []):
                issues.setdefault(issue["segment_id"], []).append(issue)
    from . import terms as term_memory
    source_text = "".join(s["source"] for s in segs)
    if lang == "en":
        from .names import char_readings
        hints = {c: " / ".join(dict.fromkeys(char_readings()[c][1][:3] or [char_readings()[c][0]]))
                 for c in set(source_text) if c in char_readings()}
    else:
        from .hanviet import char_hints
        hints = char_hints(source_text)
    data = {"segments": [{**s, "approval_current": approval_is_current(s)} for s in segs], "issues": issues,
            "terms": term_memory.load(workspace), "hints": hints, "ui": ui}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = ui["title"] + Path(project["source_filename"]).stem
    page = PAGE
    for key in ("draft", "only", "showzh", "pick"):
        page = page.replace(f"__U_{key}__", escape(ui[key]))
    page = (page.replace("__TITLE__", escape(title)).replace("__SHA__", project["source_sha256"][:12])
                .replace("__AUDIT__", escape(audited)).replace("__LANG__", lang).replace("__DATA__", payload))
    save_text(outfile, page)
    return outfile
