"""
Dashboard Route — supervisor-facing UI served directly from FastAPI.

  GET /dashboard   → beautiful real-time dashboard (no Swagger needed)

Fetches live data from the same API endpoints the system uses.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA — BeyondSure Lead Engine</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f3;color:#1a1a18;min-height:100vh}
.sidebar{position:fixed;left:0;top:0;width:210px;height:100vh;background:#fff;border-right:0.5px solid #e0dfd8;padding:1.25rem;z-index:10;display:flex;flex-direction:column}
.logo{margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:0.5px solid #e0dfd8}
.logo-title{font-size:15px;font-weight:600;color:#1a1a18}
.logo-sub{font-size:11px;color:#888780;margin-top:2px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px;color:#888780;margin-bottom:3px;transition:background 0.12s;user-select:none}
.nav-item:hover{background:#f5f5f3;color:#1a1a18}
.nav-item.active{background:#f5f5f3;color:#1a1a18;font-weight:500}
.nav-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.nav-badge{background:#F7C1C1;color:#791F1F;font-size:10px;padding:1px 6px;border-radius:10px;margin-left:auto;font-weight:500}
.sidebar-footer{margin-top:auto;padding-top:1rem;border-top:0.5px solid #e0dfd8;font-size:11px;color:#b4b2a9}
.sidebar-footer span{display:block;margin-bottom:2px}
.main{margin-left:210px;padding:1.5rem;min-height:100vh}
.page{display:none}.page.active{display:block}
.page-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.25rem}
.page-title{font-size:16px;font-weight:500;color:#1a1a18}
.page-sub{font-size:12px;color:#888780}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:1.25rem}
.kpi{background:#ebebea;border-radius:8px;padding:1rem 1.25rem}
.kpi-label{font-size:11px;color:#888780;margin-bottom:5px;text-transform:uppercase;letter-spacing:0.03em}
.kpi-value{font-size:24px;font-weight:500;color:#1a1a18;line-height:1}
.kpi-delta{font-size:11px;color:#888780;margin-top:4px}
.kpi-value.hot{color:#993C1D}.kpi-value.amber{color:#854F0B}.kpi-value.green{color:#3B6D11}
.two-col{display:grid;grid-template-columns:1.2fr 0.8fr;gap:1rem;margin-bottom:1rem}
.card{background:#fff;border:0.5px solid #e0dfd8;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem}
.card-title{font-size:13px;font-weight:500;color:#1a1a18;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}
.refresh-btn{font-size:11px;color:#888780;cursor:pointer;background:none;border:none;padding:2px 6px;border-radius:4px}
.refresh-btn:hover{background:#f5f5f3;color:#1a1a18}
.funnel-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.funnel-label{font-size:12px;color:#888780;width:85px;text-align:right;flex-shrink:0}
.funnel-wrap{flex:1;height:22px;background:#f5f5f3;border-radius:6px;overflow:hidden}
.funnel-bar{height:100%;border-radius:6px;display:flex;align-items:center;padding-left:8px;font-size:11px;font-weight:500;color:#fff;min-width:28px;transition:width 0.6s ease}
.funnel-n{font-size:12px;color:#888780;width:24px;text-align:right;flex-shrink:0}
.activity-row{display:flex;gap:10px;padding:8px 0;border-bottom:0.5px solid #e0dfd8;align-items:flex-start}
.activity-row:last-child{border-bottom:none}
.activity-time{font-size:11px;color:#b4b2a9;white-space:nowrap;width:65px;padding-top:1px;flex-shrink:0}
.activity-text{font-size:13px;color:#1a1a18;line-height:1.4}
.badge{display:inline-block;font-size:11px;font-weight:500;padding:2px 8px;border-radius:6px}
.hot{background:#FAECE7;color:#993C1D}.warm{background:#FAEEDA;color:#854F0B}.cold{background:#E6F1FB;color:#185FA5}
.intent-tag{font-size:11px;color:#888780;background:#f5f5f3;padding:2px 7px;border-radius:6px;white-space:nowrap}
.draft-card{border:0.5px solid #e0dfd8;border-radius:10px;padding:1rem 1.25rem;margin-bottom:10px;background:#fff;transition:opacity 0.3s}
.draft-card.fading{opacity:0.3}
.draft-meta-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.draft-who{display:flex;align-items:center;gap:9px}
.avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:500;flex-shrink:0}
.draft-name{font-size:14px;font-weight:500;color:#1a1a18}
.draft-info{font-size:12px;color:#888780;margin-top:1px}
.draft-body{font-size:13px;color:#5f5e5a;background:#f9f9f8;padding:10px 12px;border-radius:8px;margin-bottom:10px;line-height:1.55;border:0.5px solid #e8e7e0}
.draft-edit{width:100%;font-size:13px;padding:8px 10px;border:0.5px solid #b4b2a9;border-radius:8px;background:#fff;color:#1a1a18;resize:vertical;min-height:80px;font-family:inherit;display:none;margin-bottom:8px}
.draft-edit:focus{outline:none;border-color:#5DCAA5}
.btn-row{display:flex;gap:8px}
.btn{font-size:12px;padding:5px 12px;border-radius:8px;border:0.5px solid #b4b2a9;cursor:pointer;background:transparent;color:#1a1a18;transition:background 0.12s;font-family:inherit}
.btn:hover{background:#f5f5f3}
.btn-approve{background:#EAF3DE;border-color:#97C459;color:#3B6D11}.btn-approve:hover{background:#C0DD97}
.btn-edit{background:#f5f5f3;border-color:#b4b2a9}.btn-edit.active{background:#E6F1FB;border-color:#378ADD;color:#185FA5}
.btn-reject{background:#FCEBEB;border-color:#F09595;color:#A32D2D}.btn-reject:hover{background:#F7C1C1}
.leads-table{width:100%;border-collapse:collapse;font-size:13px}
.leads-table th{text-align:left;font-size:11px;font-weight:500;color:#888780;padding:8px 12px;border-bottom:0.5px solid #e0dfd8;white-space:nowrap}
.leads-table td{padding:10px 12px;border-bottom:0.5px solid #e0dfd8;color:#1a1a18;vertical-align:middle}
.leads-table tr:last-child td{border-bottom:none}
.leads-table tbody tr:hover td{background:#fafaf9}
.score-wrap{display:flex;align-items:center;gap:6px}
.score-bar{height:4px;border-radius:2px;background:#e0dfd8;width:50px;overflow:hidden;flex-shrink:0}
.score-fill{height:100%;border-radius:2px}
.status-dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:5px;flex-shrink:0}
.empty-state{text-align:center;padding:3rem;color:#888780;font-size:14px;background:#fafaf9;border-radius:10px;border:0.5px dashed #e0dfd8}
.filter-row{display:flex;gap:8px;align-items:center}
select,input{font-family:inherit;font-size:12px;padding:6px 10px;border:0.5px solid #b4b2a9;border-radius:8px;background:#fff;color:#1a1a18}
select:focus,input:focus{outline:none;border-color:#5DCAA5}
.toast{position:fixed;bottom:20px;right:20px;background:#1a1a18;color:#fff;border-radius:8px;padding:10px 16px;font-size:13px;display:none;z-index:100;opacity:0;transition:opacity 0.2s}
.toast.show{display:block;opacity:1}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #e0dfd8;border-top-color:#1a1a18;border-radius:50%;animation:spin 0.6s linear infinite;vertical-align:middle;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
.stat-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:0.5px solid #e0dfd8;font-size:13px}
.stat-row:last-child{border-bottom:none}
.stat-label{color:#888780}.stat-value{font-weight:500;color:#1a1a18}
</style>
</head>
<body>

<div class="sidebar">
  <div class="logo">
    <div class="logo-title">ARIA</div>
    <div class="logo-sub">BeyondSure Lead Engine</div>
  </div>
  <div class="nav-item active" onclick="nav('dashboard',this)">
    <div class="nav-dot" style="background:#5DCAA5"></div>Dashboard
  </div>
  <div class="nav-item" onclick="nav('approval',this)">
    <div class="nav-dot" style="background:#EF9F27"></div>Approval Queue
    <span class="nav-badge" id="nav-badge" style="display:none">0</span>
  </div>
  <div class="nav-item" onclick="nav('leads',this)">
    <div class="nav-dot" style="background:#378ADD"></div>All Leads
  </div>
  <div class="nav-item" onclick="nav('stats',this)">
    <div class="nav-dot" style="background:#D4537E"></div>Pipeline Stats
  </div>
  <div class="sidebar-footer">
    <span id="footer-date"></span>
    <span id="footer-mode" style="color:#EF9F27"></span>
  </div>
</div>

<div class="main">

  <!-- DASHBOARD -->
  <div class="page active" id="page-dashboard">
    <div class="page-header">
      <div class="page-title">Overview</div>
      <div class="page-sub" id="dash-updated"></div>
    </div>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Total Leads</div><div class="kpi-value" id="k-total">—</div><div class="kpi-delta">all time</div></div>
      <div class="kpi"><div class="kpi-label">Hot Leads</div><div class="kpi-value hot" id="k-hot">—</div><div class="kpi-delta">score ≥ 65</div></div>
      <div class="kpi"><div class="kpi-label">Pending Approval</div><div class="kpi-value amber" id="k-pending">—</div><div class="kpi-delta">drafts waiting</div></div>
      <div class="kpi"><div class="kpi-label">Avg First Response</div><div class="kpi-value green" id="k-response">—</div><div class="kpi-delta" id="k-response-sub">vs 202 days before</div></div>
    </div>
    <div class="two-col">
      <div class="card">
        <div class="card-title">Pipeline funnel <button class="refresh-btn" onclick="loadDashboard()">↻ refresh</button></div>
        <div id="funnel-container"><div style="color:#888780;font-size:13px">Loading...</div></div>
      </div>
      <div class="card">
        <div class="card-title">By quality</div>
        <div id="quality-breakdown"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Recent interactions</div>
      <div id="recent-activity"><div style="color:#888780;font-size:13px">Loading...</div></div>
    </div>
  </div>

  <!-- APPROVAL QUEUE -->
  <div class="page" id="page-approval">
    <div class="page-header">
      <div class="page-title">Approval Queue</div>
      <div class="page-sub" id="queue-sub"></div>
    </div>
    <div id="approval-list"></div>
    <div class="empty-state" id="queue-empty" style="display:none">All caught up — no drafts waiting for review.</div>
  </div>

  <!-- ALL LEADS -->
  <div class="page" id="page-leads">
    <div class="page-header">
      <div class="page-title">All Leads</div>
      <div class="filter-row">
        <select id="filter-q" onchange="loadLeads()">
          <option value="">All quality</option>
          <option value="hot">Hot</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </select>
        <select id="filter-s" onchange="loadLeads()">
          <option value="">All status</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="escalated">Escalated</option>
          <option value="needs_call">Needs call</option>
          <option value="lost">Lost</option>
        </select>
      </div>
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <table class="leads-table">
        <thead><tr>
          <th>Name</th><th>Type</th><th>State</th><th>Score</th>
          <th>Quality</th><th>Intent</th><th>Status</th><th>Created</th>
        </tr></thead>
        <tbody id="leads-tbody"><tr><td colspan="8" style="padding:1.5rem;color:#888780;text-align:center">Loading...</td></tr></tbody>
      </table>
    </div>
  </div>

  <!-- PIPELINE STATS -->
  <div class="page" id="page-stats">
    <div class="page-header">
      <div class="page-title">Pipeline Stats</div>
      <button class="refresh-btn" onclick="loadStats()" style="font-size:13px;border:0.5px solid #e0dfd8;padding:5px 12px;border-radius:8px;background:#fff;cursor:pointer">↻ Refresh</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
      <div class="card">
        <div class="card-title">Leads by quality</div>
        <div id="stats-quality"></div>
      </div>
      <div class="card">
        <div class="card-title">Leads by status</div>
        <div id="stats-status"></div>
      </div>
    </div>
    <div class="card" style="max-width:400px">
      <div class="card-title">Response time</div>
      <div id="stats-response"></div>
    </div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
const BASE = '';

async function api(path, method='GET', body=null) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(BASE + path, opts);
  return r.json();
}

function nav(id, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  el.classList.add('active');
  if (id === 'dashboard') loadDashboard();
  if (id === 'approval') loadApproval();
  if (id === 'leads') loadLeads();
  if (id === 'stats') loadStats();
}

function toast(msg, dur=2500) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

function timeAgo(iso) {
  const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  if (s < 86400) return Math.floor(s/3600) + 'h ago';
  return Math.floor(s/86400) + 'd ago';
}

function scoreColor(s) {
  return s >= 65 ? '#D85A30' : s >= 40 ? '#EF9F27' : '#378ADD';
}

function statusColor(s) {
  const m = {new:'#5DCAA5',contacted:'#378ADD',escalated:'#D85A30',needs_call:'#EF9F27',lost:'#b4b2a9',converted:'#639922'};
  return m[s] || '#b4b2a9';
}

function initials(name) {
  return (name || '?').split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase();
}

function avatarColors(quality) {
  return {hot:['#FAECE7','#993C1D'],warm:['#FAEEDA','#854F0B'],cold:['#E6F1FB','#185FA5']}[quality] || ['#E1F5EE','#0F6E56'];
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  document.getElementById('dash-updated').textContent = 'Updated ' + new Date().toLocaleTimeString('en-IN');
  try {
    const [stats, queue] = await Promise.all([
      api('/leads/stats'),
      api('/approval/queue'),
    ]);

    document.getElementById('k-total').textContent = stats.total_leads ?? 0;
    document.getElementById('k-hot').textContent = stats.by_quality?.hot ?? 0;
    const pending = queue.total_pending ?? 0;
    document.getElementById('k-pending').textContent = pending;
    updateNavBadge(pending);

    const avg = stats.avg_first_response_minutes;
    if (avg !== null && avg !== undefined) {
      document.getElementById('k-response').textContent = avg < 60 ? avg + ' min' : (avg/60).toFixed(1) + ' hr';
    } else {
      document.getElementById('k-response').textContent = '—';
    }

    // Funnel
    const byStatus = stats.by_status || {};
    const funnelData = [
      {label:'Total', n: stats.total_leads||0, color:'#378ADD'},
      {label:'Contacted', n: byStatus.contacted||0, color:'#5DCAA5'},
      {label:'Escalated', n: byStatus.escalated||0, color:'#EF9F27'},
      {label:'Needs call', n: byStatus.needs_call||0, color:'#D85A30'},
      {label:'Converted', n: byStatus.converted||0, color:'#639922'},
    ];
    const maxN = funnelData[0].n || 1;
    document.getElementById('funnel-container').innerHTML = funnelData.map(f => `
      <div class="funnel-row">
        <div class="funnel-label">${f.label}</div>
        <div class="funnel-wrap">
          <div class="funnel-bar" style="width:${Math.max(4,Math.round(f.n/maxN*100))}%;background:${f.color}">${f.n > 0 ? f.n : ''}</div>
        </div>
        <div class="funnel-n">${f.n}</div>
      </div>`).join('');

    // Quality breakdown
    const bq = stats.by_quality || {};
    const total = stats.total_leads || 1;
    const qColors = {hot:'#D85A30',warm:'#EF9F27',cold:'#378ADD',new:'#5DCAA5'};
    document.getElementById('quality-breakdown').innerHTML = ['hot','warm','cold'].map(q => {
      const n = bq[q] || 0;
      const pct = Math.round(n / total * 100);
      return `<div class="funnel-row">
        <div class="funnel-label">${q.charAt(0).toUpperCase()+q.slice(1)}</div>
        <div class="funnel-wrap"><div class="funnel-bar" style="width:${Math.max(2,pct)}%;background:${qColors[q]}">${n > 0 ? n : ''}</div></div>
        <div class="funnel-n">${n}</div>
      </div>`;
    }).join('');

    // Recent from queue drafts
    const recent = (queue.drafts || []).slice(0,5);
    if (recent.length === 0) {
      document.getElementById('recent-activity').innerHTML = '<div style="color:#888780;font-size:13px;padding:8px 0">No recent activity yet.</div>';
    } else {
      document.getElementById('recent-activity').innerHTML = recent.map(d => `
        <div class="activity-row">
          <div class="activity-time">${timeAgo(d.created_at)}</div>
          <div class="activity-text">Draft ready for <strong>${d.lead_name}</strong> — intent: <span class="intent-tag">${(d.intent_context||'').replace(/_/g,' ')}</span> <span class="badge ${d.lead_quality||''}">${d.lead_quality||''}</span></div>
        </div>`).join('');
    }
  } catch(e) {
    console.error(e);
  }
}

// ── Approval Queue ────────────────────────────────────────────────────────────
async function loadApproval() {
  const data = await api('/approval/queue');
  const drafts = data.drafts || [];
  document.getElementById('queue-sub').textContent = drafts.length + ' draft' + (drafts.length !== 1 ? 's' : '') + ' waiting';
  updateNavBadge(drafts.length);

  const empty = document.getElementById('queue-empty');
  const list = document.getElementById('approval-list');

  if (drafts.length === 0) { list.innerHTML = ''; empty.style.display = ''; return; }
  empty.style.display = 'none';

  list.innerHTML = drafts.map(d => {
    const [abg, afg] = avatarColors(d.lead_quality);
    return `
    <div class="draft-card" id="dc-${d.draft_id}">
      <div class="draft-meta-row">
        <div class="draft-who">
          <div class="avatar" style="background:${abg};color:${afg}">${initials(d.lead_name)}</div>
          <div>
            <div class="draft-name">${d.lead_name}</div>
            <div class="draft-info">Score ${d.lead_score||0} · <span class="intent-tag">${(d.intent_context||'').replace(/_/g,' ')}</span></div>
          </div>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <span class="badge ${d.lead_quality||''}">${d.lead_quality||''}</span>
          <span style="font-size:11px;color:#b4b2a9">${timeAgo(d.created_at)}</span>
        </div>
      </div>
      <div class="draft-body" id="db-${d.draft_id}">${d.draft_message || ''}</div>
      <textarea class="draft-edit" id="de-${d.draft_id}">${d.draft_message || ''}</textarea>
      <div class="btn-row">
        <button class="btn btn-approve" onclick="approve(${d.draft_id})">Approve &amp; send</button>
        <button class="btn btn-edit" id="be-${d.draft_id}" onclick="toggleEdit(${d.draft_id})">Edit</button>
        <button class="btn btn-reject" onclick="reject(${d.draft_id})">Reject</button>
      </div>
    </div>`;
  }).join('');
}

function toggleEdit(id) {
  const ea = document.getElementById('de-'+id);
  const btn = document.getElementById('be-'+id);
  const db = document.getElementById('db-'+id);
  const open = ea.style.display !== 'block';
  ea.style.display = open ? 'block' : 'none';
  db.style.display = open ? 'none' : 'block';
  btn.classList.toggle('active', open);
  btn.textContent = open ? 'Cancel' : 'Edit';
}

async function approve(id) {
  const card = document.getElementById('dc-'+id);
  card.classList.add('fading');
  const ea = document.getElementById('de-'+id);
  const isEdited = ea.style.display === 'block';

  if (isEdited) {
    await api(`/approval/${id}/edit`, 'POST', {revised_text: ea.value, reviewer_notes: 'Edited via dashboard'});
    toast('Edited draft sent');
  } else {
    await api(`/approval/${id}/approve`, 'POST');
    toast('Draft approved — email sent');
  }
  setTimeout(() => { card.remove(); checkQueueEmpty(); updateNavBadge(); }, 400);
}

async function reject(id) {
  const card = document.getElementById('dc-'+id);
  card.classList.add('fading');
  await api(`/approval/${id}/reject`, 'POST');
  toast('Draft rejected');
  setTimeout(() => { card.remove(); checkQueueEmpty(); updateNavBadge(); }, 400);
}

function checkQueueEmpty() {
  const list = document.getElementById('approval-list');
  if (!list.querySelector('.draft-card')) {
    document.getElementById('queue-empty').style.display = '';
    document.getElementById('queue-sub').textContent = '0 drafts waiting';
  }
}

// ── Leads ─────────────────────────────────────────────────────────────────────
async function loadLeads() {
  const q = document.getElementById('filter-q').value;
  const s = document.getElementById('filter-s').value;
  let url = '/leads/?limit=100';
  if (q) url += '&quality=' + q;
  if (s) url += '&status=' + s;
  const leads = await api(url);
  const tbody = document.getElementById('leads-tbody');
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:#888780;text-align:center">No leads found.</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map(l => `
    <tr>
      <td style="font-weight:500">${l.name || '—'}</td>
      <td style="color:#888780">${l.type || '—'}</td>
      <td style="color:#888780">${l.state || '—'}</td>
      <td><div class="score-wrap">
        <div class="score-bar"><div class="score-fill" style="width:${l.score}%;background:${scoreColor(l.score)}"></div></div>
        <span style="font-size:12px">${l.score}</span>
      </div></td>
      <td><span class="badge ${l.quality||''}">${l.quality||'—'}</span></td>
      <td><span class="intent-tag">${(l.current_intent||'—').replace(/_/g,' ')}</span></td>
      <td><span class="status-dot" style="background:${statusColor(l.status)}"></span>${l.status||'—'}</td>
      <td style="color:#888780;font-size:12px">${l.created_at ? new Date(l.created_at).toLocaleDateString('en-IN') : '—'}</td>
    </tr>`).join('');
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  const stats = await api('/leads/stats');
  const bq = stats.by_quality || {};
  const bs = stats.by_status || {};

  document.getElementById('stats-quality').innerHTML = Object.entries(bq).map(([k,v]) => `
    <div class="stat-row"><span class="stat-label">${k}</span><span class="stat-value">${v}</span></div>`).join('') || '<div style="color:#888780;font-size:13px">No data yet.</div>';

  document.getElementById('stats-status').innerHTML = Object.entries(bs).map(([k,v]) => `
    <div class="stat-row"><span class="stat-label">${k.replace(/_/g,' ')}</span><span class="stat-value">${v}</span></div>`).join('') || '<div style="color:#888780;font-size:13px">No data yet.</div>';

  const avg = stats.avg_first_response_minutes;
  document.getElementById('stats-response').innerHTML = `
    <div class="stat-row"><span class="stat-label">Avg first response</span><span class="stat-value">${avg !== null && avg !== undefined ? (avg < 60 ? avg + ' min' : (avg/60).toFixed(1) + ' hrs') : 'No data yet'}</span></div>
    <div class="stat-row"><span class="stat-label">Before ARIA</span><span class="stat-value" style="color:#993C1D">202 days</span></div>
    <div class="stat-row"><span class="stat-label">Total leads</span><span class="stat-value">${stats.total_leads}</span></div>`;
}

async function updateNavBadge(n) {
  if (n === undefined) {
    const data = await api('/approval/queue');
    n = data.total_pending || 0;
  }
  const badge = document.getElementById('nav-badge');
  badge.textContent = n;
  badge.style.display = n > 0 ? '' : 'none';
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.getElementById('footer-date').textContent = new Date().toLocaleDateString('en-IN', {weekday:'short',day:'numeric',month:'short',year:'numeric'});

fetch('/').then(r=>r.json()).then(d => {
  document.getElementById('footer-mode').textContent = d.scheduler === 'running' ? '● Scheduler running' : '○ Scheduler stopped';
});

loadDashboard();
updateNavBadge();
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Live supervisor-facing dashboard — real data from the API."""
    return HTMLResponse(content=DASHBOARD_HTML)
