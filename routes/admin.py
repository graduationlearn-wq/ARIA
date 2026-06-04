"""
Admin Route — internal tooling for BeyondSure operators.

Endpoints:
  GET  /admin/kb              — KB editor HTML page
  GET  /admin/kb/entries      — all KB entries as JSON
  PUT  /admin/kb/{id}         — update an entry's answer / active flag
  POST /admin/kb              — add a new entry
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.knowledge_base import KnowledgeBase
from config import settings

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Config / system status (no secrets) ─────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    """
    Non-sensitive system configuration + KB stats for the Settings page.
    Never returns API keys or SMTP passwords — only presence flags.
    """
    kb_total        = db.query(KnowledgeBase).count()
    kb_placeholders = db.query(KnowledgeBase).filter(KnowledgeBase.is_placeholder == True).count()  # noqa: E712
    kb_active       = db.query(KnowledgeBase).filter(KnowledgeBase.active == True).count()           # noqa: E712

    return {
        "aria": {
            "human_approval_mode": settings.human_approval_mode,
            "llm_provider":        settings.llm_provider,
            "base_url":            settings.base_url,
            "version":             "0.6 - Phase 2",
        },
        "channels": {
            "facebook":  {"label": "Facebook Lead Ads", "connected": False, "note": "Connect webhook in Meta Business Suite"},
            "instagram": {"label": "Instagram Lead Ads", "connected": False, "note": "Shares the Meta webhook with Facebook"},
            "email":     {"label": "Email (SMTP)", "connected": bool(settings.smtp_user and settings.smtp_password), "note": "Outbound first-touch & follow-ups"},
            "whatsapp":  {"label": "WhatsApp Cloud API", "connected": bool(settings.whatsapp_api_token and settings.whatsapp_phone_number_id), "note": "Team adds credentials when ready"},
        },
        "alerts": {
            "alert_email":      settings.alert_email or "(not set)",
            "whatsapp_number":  settings.whatsapp_business_number or "(not set)",
        },
        "knowledge_base": {
            "total":        kb_total,
            "active":       kb_active,
            "placeholders": kb_placeholders,
            "answered":     kb_total - kb_placeholders,
        },
    }


# ── Pydantic models ────────────────────────────────────────────────────────────

class KBUpdateRequest(BaseModel):
    answer: str | None = None
    active: bool | None = None


class KBCreateRequest(BaseModel):
    question: str
    answer: str
    category: str


# ── API endpoints ──────────────────────────────────────────────────────────────

@router.get("/kb/entries")
def get_kb_entries(db: Session = Depends(get_db)):
    """Return all KB entries, sorted by category then id."""
    entries = (
        db.query(KnowledgeBase)
        .order_by(KnowledgeBase.category, KnowledgeBase.id)
        .all()
    )
    return [
        {
            "id":             e.id,
            "question":       e.question,
            "answer":         e.answer,
            "category":       e.category,
            "active":         e.active,
            "is_placeholder": e.is_placeholder,
            "updated_at":     e.updated_at.isoformat() if e.updated_at else None,
        }
        for e in entries
    ]


@router.put("/kb/{entry_id}")
def update_kb_entry(
    entry_id: int,
    body: KBUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update an entry's answer and/or active flag."""
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if body.answer is not None:
        entry.answer         = body.answer.strip()
        entry.is_placeholder = False          # marking answered
    if body.active is not None:
        entry.active = body.active

    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "id":             entry.id,
        "answer":         entry.answer,
        "active":         entry.active,
        "is_placeholder": entry.is_placeholder,
        "updated_at":     entry.updated_at.isoformat(),
    }


@router.post("/kb")
def create_kb_entry(body: KBCreateRequest, db: Session = Depends(get_db)):
    """Add a new KB entry."""
    entry = KnowledgeBase(
        question=body.question.strip(),
        answer=body.answer.strip(),
        category=body.category.strip(),
        active=True,
        is_placeholder=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "question": entry.question, "category": entry.category}


# ── KB Editor HTML page ────────────────────────────────────────────────────────

@router.get("/kb", response_class=HTMLResponse)
def kb_admin_page():
    """Self-contained KB editor — no auth, internal use only."""
    return HTMLResponse(content=_KB_HTML)


# ── Inline HTML (self-contained: CSS + JS included) ───────────────────────────

_KB_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA · KB Editor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:      #fafafd;
    --card:    #ffffff;
    --border:  rgba(15,17,41,0.08);
    --ink-1:   #0f1129;
    --ink-2:   #3d4152;
    --ink-3:   #7c7f96;
    --ink-4:   #b0b3c6;
    --accent:  #6c5ce7;
    --green:   #10b981;
    --amber:   #f59e0b;
    --red:     #ef4444;
    --radius:  14px;
    --shadow:  0 0 0 1px rgba(15,17,41,0.05), 0 2px 8px rgba(15,17,41,0.06);
  }

  body {
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--ink-1);
    min-height: 100vh;
    padding-bottom: 60px;
  }

  /* ── topbar ── */
  .topbar {
    position: sticky; top: 0; z-index: 100;
    background: rgba(255,255,255,0.88);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    display: flex; align-items: center; justify-content: space-between;
    height: 60px;
  }
  .tb-left { display: flex; align-items: center; gap: 12px; }
  .tb-logo {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, #a78bfa, #6c5ce7);
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 700; font-size: 14px;
  }
  .tb-title { font-weight: 700; font-size: 16px; letter-spacing: -0.02em; }
  .tb-sub { font-size: 12px; color: var(--ink-3); margin-left: 4px; }
  .tb-right { display: flex; align-items: center; gap: 10px; }
  #progress-text { font-size: 13px; font-weight: 600; color: var(--ink-2); }
  #progress-bar-wrap {
    width: 140px; height: 6px; background: #e8e9f0; border-radius: 99px; overflow: hidden;
  }
  #progress-bar-fill {
    height: 100%; background: var(--green); border-radius: 99px;
    transition: width .4s ease;
  }
  .btn-add {
    display: flex; align-items: center; gap: 6px;
    padding: 7px 14px; border-radius: 8px; border: none; cursor: pointer;
    background: var(--accent); color: #fff;
    font: 600 13px 'Inter', sans-serif;
    transition: opacity .15s;
  }
  .btn-add:hover { opacity: .85; }

  /* ── main ── */
  main { max-width: 860px; margin: 0 auto; padding: 32px 24px; }

  /* ── add form ── */
  .add-form {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 20px 24px;
    box-shadow: var(--shadow); margin-bottom: 32px;
    display: none;
  }
  .add-form.open { display: block; }
  .add-form h3 { font-size: 14px; font-weight: 600; margin-bottom: 14px; }
  .af-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .af-full  { grid-column: 1 / -1; }
  .af-label { font-size: 11px; font-weight: 600; color: var(--ink-3); margin-bottom: 4px; display: block; }
  .af-input, .af-select, .af-ta {
    width: 100%; padding: 8px 12px; border-radius: 8px;
    border: 1px solid var(--border); background: #fff;
    font: 400 13px 'Inter', sans-serif; color: var(--ink-1);
    outline: none; transition: border-color .15s;
  }
  .af-input:focus, .af-select:focus, .af-ta:focus {
    border-color: var(--accent);
  }
  .af-ta { resize: vertical; min-height: 80px; }
  .af-actions { margin-top: 14px; display: flex; gap: 8px; }
  .btn-save-new {
    padding: 7px 16px; border-radius: 8px; border: none; cursor: pointer;
    background: var(--green); color: #fff;
    font: 600 13px 'Inter', sans-serif;
  }
  .btn-cancel {
    padding: 7px 16px; border-radius: 8px; border: 1px solid var(--border);
    background: transparent; cursor: pointer;
    font: 500 13px 'Inter', sans-serif; color: var(--ink-3);
  }

  /* ── category section ── */
  .cat-section { margin-bottom: 28px; }
  .cat-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 14px; padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }
  .cat-dot {
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0;
  }
  .cat-name {
    font-size: 13px; font-weight: 700; letter-spacing: -0.01em;
    color: var(--ink-1);
  }
  .cat-count {
    font-size: 11px; color: var(--ink-4); font-weight: 500;
    background: #f0f0f5; padding: 2px 7px; border-radius: 99px;
  }

  /* ── entry card ── */
  .entry-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px;
    box-shadow: var(--shadow); margin-bottom: 10px;
    transition: border-color .15s;
  }
  .entry-card:hover { border-color: rgba(108,92,231,0.25); }
  .entry-card.inactive { opacity: .55; }

  .entry-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
  .entry-question { font-size: 14px; font-weight: 600; line-height: 1.4; }
  .entry-badges { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

  .badge {
    font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 99px;
    letter-spacing: 0.03em; white-space: nowrap;
  }
  .badge-ph  { background: #fef3c7; color: #b45309; }
  .badge-ok  { background: #dcfce7; color: #047857; }
  .badge-off { background: #f1f1f5; color: var(--ink-3); }

  .entry-ta {
    width: 100%; padding: 10px 12px; border-radius: 8px;
    border: 1px solid var(--border); background: #fafaf8;
    font: 400 13px/1.55 'Inter', sans-serif; color: var(--ink-1);
    resize: vertical; min-height: 80px; outline: none;
    transition: border-color .15s, background .15s;
  }
  .entry-ta:focus { border-color: var(--accent); background: #fff; }

  .entry-footer {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 10px;
  }
  .entry-meta { font-size: 11px; color: var(--ink-4); }
  .entry-actions { display: flex; align-items: center; gap: 8px; }

  .toggle-wrap { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .toggle-lbl { font-size: 12px; color: var(--ink-3); user-select: none; }
  .toggle-input { width: 32px; height: 18px; cursor: pointer; }

  .btn-update {
    padding: 6px 14px; border-radius: 8px; border: none; cursor: pointer;
    background: var(--accent); color: #fff;
    font: 600 12px 'Inter', sans-serif;
    transition: opacity .15s, transform .1s;
  }
  .btn-update:hover { opacity: .85; }
  .btn-update:active { transform: scale(.97); }
  .btn-update:disabled { opacity: .45; cursor: default; }
  .btn-update.saved { background: var(--green); }

  /* ── toast ── */
  #toast {
    position: fixed; bottom: 24px; right: 24px;
    background: var(--ink-1); color: #fff;
    padding: 10px 18px; border-radius: 10px;
    font-size: 13px; font-weight: 500;
    box-shadow: 0 4px 20px rgba(0,0,0,.25);
    opacity: 0; transform: translateY(8px);
    transition: opacity .25s, transform .25s;
    pointer-events: none; z-index: 999;
  }
  #toast.show { opacity: 1; transform: translateY(0); }

  /* ── loading state ── */
  .loading { padding: 60px; text-align: center; color: var(--ink-4); font-size: 14px; }
</style>
</head>
<body>

<header class="topbar">
  <div class="tb-left">
    <div class="tb-logo">A</div>
    <span class="tb-title">KB Editor</span>
    <span class="tb-sub">BeyondSure · internal</span>
  </div>
  <div class="tb-right">
    <span id="progress-text">Loading…</span>
    <div id="progress-bar-wrap"><div id="progress-bar-fill" style="width:0%"></div></div>
    <button class="btn-add" onclick="toggleAddForm()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Add entry
    </button>
  </div>
</header>

<main>
  <!-- add form (hidden by default) -->
  <form class="add-form" id="add-form" onsubmit="submitNew(event)">
    <h3>New KB entry</h3>
    <div class="af-grid">
      <div>
        <label class="af-label">Question</label>
        <input class="af-input" id="nq" placeholder="e.g. Does BeyondSure have an API?" required>
      </div>
      <div>
        <label class="af-label">Category</label>
        <select class="af-select" id="nc" required>
          <option value="">— pick category —</option>
          <option>Pricing &amp; Plans</option>
          <option>Features</option>
          <option>Onboarding &amp; Setup</option>
          <option>Objection Handling</option>
          <option>General</option>
        </select>
      </div>
      <div class="af-full">
        <label class="af-label">Answer</label>
        <textarea class="af-ta" id="na" rows="3" placeholder="What should ARIA say?" required></textarea>
      </div>
    </div>
    <div class="af-actions">
      <button type="submit" class="btn-save-new">Save entry</button>
      <button type="button" class="btn-cancel" onclick="toggleAddForm()">Cancel</button>
    </div>
  </form>

  <div id="kb-list"><div class="loading">Loading entries…</div></div>
</main>

<div id="toast"></div>

<script>
const CAT_COLORS = {
  'Pricing & Plans':    '#f59e0b',
  'Features':           '#6c5ce7',
  'Onboarding & Setup': '#10b981',
  'Objection Handling': '#ef4444',
  'General':            '#64748b',
};

let ALL_ENTRIES = [];
let totalActive = 0;

// ── fetch and render ──────────────────────────────────────────────────────────

async function loadEntries() {
  try {
    const r = await fetch('/admin/kb/entries');
    ALL_ENTRIES = await r.json();
    renderEntries();
    updateProgress();
  } catch (e) {
    document.getElementById('kb-list').innerHTML =
      '<div class="loading">Could not load entries — is the server running?</div>';
  }
}

function renderEntries() {
  // Group by category
  const groups = {};
  ALL_ENTRIES.forEach(e => {
    const cat = e.category || 'General';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(e);
  });

  document.getElementById('kb-list').innerHTML = Object.entries(groups).map(([cat, entries]) => {
    const color = CAT_COLORS[cat] || '#94a3b8';
    return `
      <section class="cat-section">
        <div class="cat-header">
          <span class="cat-dot" style="background:${color}"></span>
          <span class="cat-name">${cat}</span>
          <span class="cat-count">${entries.length}</span>
        </div>
        ${entries.map(entryHTML).join('')}
      </section>
    `;
  }).join('');
}

function entryHTML(e) {
  const badge = e.is_placeholder
    ? '<span class="badge badge-ph">placeholder</span>'
    : '<span class="badge badge-ok">answered</span>';
  const activeBadge = !e.active ? '<span class="badge badge-off">inactive</span>' : '';
  const updatedStr = e.updated_at
    ? new Date(e.updated_at).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' })
    : '—';

  return `
    <div class="entry-card ${e.active ? '' : 'inactive'}" id="card-${e.id}">
      <div class="entry-top">
        <div class="entry-question">${escHtml(e.question)}</div>
        <div class="entry-badges">${badge}${activeBadge}</div>
      </div>
      <textarea class="entry-ta" id="ta-${e.id}" rows="4">${escHtml(e.answer)}</textarea>
      <div class="entry-footer">
        <span class="entry-meta">Updated ${updatedStr}</span>
        <div class="entry-actions">
          <label class="toggle-wrap" title="Toggle active">
            <input class="toggle-input" type="checkbox" onchange="toggleActive(${e.id}, this.checked)" ${e.active ? 'checked' : ''}>
            <span class="toggle-lbl">${e.active ? 'Active' : 'Inactive'}</span>
          </label>
          <button class="btn-update" id="btn-${e.id}" onclick="saveEntry(${e.id})">Update</button>
        </div>
      </div>
    </div>
  `;
}

// ── save ──────────────────────────────────────────────────────────────────────

async function saveEntry(id) {
  const ta  = document.getElementById('ta-' + id);
  const btn = document.getElementById('btn-' + id);
  if (!ta || !btn) return;

  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    const r = await fetch('/admin/kb/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: ta.value }),
    });
    if (!r.ok) throw new Error('Save failed');

    const updated = await r.json();
    btn.textContent = 'Saved ✓';
    btn.classList.add('saved');
    setTimeout(() => {
      btn.textContent = 'Update';
      btn.classList.remove('saved');
      btn.disabled = false;
    }, 2000);

    // Update local state
    const entry = ALL_ENTRIES.find(e => e.id === id);
    if (entry) { entry.answer = updated.answer; entry.is_placeholder = false; }
    updateProgress();
    showToast('Answer saved for: ' + (entry?.question?.slice(0, 40) || 'entry'));
  } catch (_) {
    btn.textContent = 'Error — retry';
    btn.classList.remove('saved');
    btn.disabled = false;
  }
}

async function toggleActive(id, active) {
  const card  = document.getElementById('card-' + id);
  const lbl   = card?.querySelector('.toggle-lbl');
  try {
    await fetch('/admin/kb/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active }),
    });
    if (card) card.classList.toggle('inactive', !active);
    if (lbl)  lbl.textContent = active ? 'Active' : 'Inactive';
    const entry = ALL_ENTRIES.find(e => e.id === id);
    if (entry) entry.active = active;
    updateProgress();
    showToast(active ? 'Entry activated' : 'Entry deactivated');
  } catch (_) { showToast('Could not save — check server'); }
}

// ── add new ───────────────────────────────────────────────────────────────────

function toggleAddForm() {
  document.getElementById('add-form').classList.toggle('open');
}

async function submitNew(evt) {
  evt.preventDefault();
  const q = document.getElementById('nq').value.trim();
  const c = document.getElementById('nc').value;
  const a = document.getElementById('na').value.trim();
  if (!q || !c || !a) return;

  try {
    const r = await fetch('/admin/kb', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, answer: a, category: c }),
    });
    if (!r.ok) throw new Error();
    showToast('Entry added!');
    document.getElementById('add-form').classList.remove('open');
    document.getElementById('add-form').reset();
    await loadEntries();  // refresh
  } catch (_) { showToast('Could not add entry — check server'); }
}

// ── progress ──────────────────────────────────────────────────────────────────

function updateProgress() {
  const total   = ALL_ENTRIES.length;
  const active  = ALL_ENTRIES.filter(e => e.active).length;
  const pct     = total > 0 ? Math.round((active / total) * 100) : 0;
  document.getElementById('progress-text').textContent = active + ' of ' + total + ' active';
  document.getElementById('progress-bar-fill').style.width = pct + '%';
}

// ── toast ─────────────────────────────────────────────────────────────────────

let toastTimer;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
}

// ── utils ─────────────────────────────────────────────────────────────────────

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── boot ──────────────────────────────────────────────────────────────────────

loadEntries();
</script>
</body>
</html>"""
