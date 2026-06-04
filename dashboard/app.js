/* ══════════════════════════════════════════════════════════════════
   ARIA dashboard · 5-view application
   ══════════════════════════════════════════════════════════════════ */

/* ─── tiny helpers ─── */
const $  = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

/** Escape user-supplied strings before inserting into innerHTML (XSS prevention) */
const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

/** Live summary stats from /leads/stats (populated by loadLiveData) */
let LIVE_STATS = {};

/* ══════════════════════════════════════════════════════════════════
   LIVE DATA LAYER
   When served from FastAPI (/ui) → same-origin fetches, no CORS needed.
   When opened as file:// (no server) → silently falls back to data.js samples.
   ══════════════════════════════════════════════════════════════════ */

/** Generate a Dicebear avatar URL from any name */
function avatarUrl(name) {
  const seed = encodeURIComponent((name || 'unknown').trim());
  return `https://api.dicebear.com/7.x/notionists/svg?seed=${seed}&backgroundColor=d8b4fe,a78bfa,c4b5fd,ddd6fe,ede9fe`;
}

/** Convert /leads/ API item → dashboard LEAD format */
function mapApiLead(l) {
  const dateStr = l.created_at ? l.created_at.split('T')[0] : new Date().toISOString().split('T')[0];
  const t = l.type || 'agent';
  const src = (l.source || '').toLowerCase();
  const channel = (src === 'ig' || src === 'instagram') ? 'instagram' : 'facebook';
  return {
    id: l.id,
    name: l.name || 'Unknown',
    company: l.company || '—',
    city: l.state || '—',
    state: l.state || '',
    handle: l.email || '',
    role: t.charAt(0).toUpperCase() + t.slice(1),
    lead_type: t,
    channel,   // derived from real source_platform (fb/ig)
    score: l.score || 0,
    quality: l.quality || 'new',
    status: l.status || 'new',
    created_at: dateStr,
    avatar: avatarUrl(l.name),
    pipeline: Math.max(50000, (l.team_size || 3) * 18000),
    owner: null,
    last_activity_min: l.last_interaction_at
      ? Math.max(1, Math.floor((Date.now() - new Date(l.last_interaction_at)) / 60000))
      : null,
    uses_software: l.uses_software,
    team_size: l.team_size,
    willing_for_demo: l.willing_for_demo,
    current_intent: l.current_intent,
    chat_url: l.chat_url,
    human_priority: l.human_priority,
  };
}

/** Convert /approval/queue item → dashboard PENDING_DRAFTS format */
function mapApiDraft(d) {
  // Trim the CTA block (the ──── divider + chat/WhatsApp links) for a clean preview
  let body = d.draft_message || '';
  const dividerMatch = body.search(/[─—-]{6,}/);
  if (dividerMatch > 0) body = body.slice(0, dividerMatch).trim();

  const lines = body.split('\n').map(s => s.trim()).filter(Boolean);
  return {
    id:         d.draft_id,
    lead_id:    d.lead_id,
    intent:     d.intent_context || 'first_touch',
    subject:    lines[0] || `Message for ${d.lead_name}`,
    body:       lines.slice(1).join('\n') || body,
    created_at: d.created_at || new Date().toISOString(),
    // keep original API fields so renderDrafts() can fall back if lead not in LEADS
    _lead_name:    d.lead_name,
    _lead_email:   d.lead_email,
    _lead_quality: d.lead_quality,
    _lead_score:   d.lead_score,
  };
}

/** Update the live/sample indicator chip in the topbar */
function setLiveIndicator(live, count) {
  const pill = $('live-pill');
  if (!pill) return;
  if (live) {
    pill.textContent = `● Live · ${count} lead${count !== 1 ? 's' : ''}`;
    pill.style.cssText = 'background:#dcfce7;color:#047857;border-color:#bbf7d0';
  } else {
    pill.textContent = '○ Sample data';
    pill.style.cssText = 'background:#fef3c7;color:#b45309;border-color:#fde68a';
  }
}

/**
 * Fetch live data from FastAPI and replace global arrays in-place.
 * All existing render functions keep working — they still read from LEADS, PENDING_DRAFTS, etc.
 */
async function loadLiveData() {
  const isServed = window.location.protocol !== 'file:';
  if (!isServed) { setLiveIndicator(false, null); return; }

  try {
    const [statsRes, leadsRes, queueRes] = await Promise.all([
      fetch('/leads/stats'),
      fetch('/leads/?limit=200'),
      fetch('/approval/queue'),
    ]);
    if (!statsRes.ok || !leadsRes.ok || !queueRes.ok) throw new Error('API error');

    const stats    = await statsRes.json();
    const apiLeads = await leadsRes.json();
    const apiQueue = await queueRes.json();

    // /approval/queue returns { total_pending, drafts: [...] } — extract the array
    const queueDrafts = Array.isArray(apiQueue) ? apiQueue : (apiQueue.drafts || []);

    // Replace sample data in-place (all render fns keep their references)
    LEADS.length = 0;
    apiLeads.map(mapApiLead).forEach(l => LEADS.push(l));

    PENDING_DRAFTS.length = 0;
    queueDrafts.map(mapApiDraft).forEach(d => PENDING_DRAFTS.push(d));

    // Capture summary stats for mini-cards
    LIVE_STATS = {
      avgResponseMin: stats.avg_first_response_minutes,
      byQuality: stats.by_quality || {},
    };

    // Update co-pilot with real operational numbers
    OPERATING_STATUS.monitoring = LEADS.length;
    OPERATING_STATUS.drafting   = PENDING_DRAFTS.length;
    const hot  = (stats.by_quality || {}).hot  || 0;
    OPERATING_STATUS.today = [
      { val: LEADS.length,          lbl: 'Total leads' },
      { val: hot,                   lbl: 'Hot' },
      { val: PENDING_DRAFTS.length, lbl: 'Pending approvals' },
    ];

    // Fetch analytics for the Analytics view
    try {
      const aRes = await fetch('/leads/analytics');
      if (aRes.ok) {
        const a = await aRes.json();
        ANALYTICS.funnel       = a.funnel.map(s => ({ stage: s.stage, count: s.count, pct: s.pct }));
        ANALYTICS.sources      = a.sources;
        ANALYTICS.scoreBuckets = a.score_buckets.map(b => ({ b: b.b, n: b.n }));
        ANALYTICS.weeklyTrend  = a.weekly_trend.map(w => ({ w: w.w, leads: w.leads, demos: w.demos }));
        ANALYTICS.cohorts      = a.cohorts.map(c => ({
          week: c.week, leads: c.leads, contacted: c.contacted,
          replied: c.replied, demos: c.demos, won: c.won,
        }));
      }
    } catch (_) { /* analytics unavailable — sample data stays */ }

    // Derive Priority items from live leads (no extra endpoint needed)
    const hotLeads       = LEADS.filter(l => l.quality === 'hot');
    const escalatedLeads = LEADS.filter(l => l.status === 'escalated' || l.status === 'needs_human');
    const demoLeads      = LEADS.filter(l => l.willing_for_demo && l.quality !== 'converted');
    const livePriority   = [];

    if (hotLeads.length)
      livePriority.push({
        icon: 'flame', tone: 'rose',
        title: `${hotLeads.length} hot lead${hotLeads.length > 1 ? 's' : ''} ready`,
        meta: 'Score 70+ — contact today',
        desc: hotLeads.slice(0, 2).map(l => esc(l.name)).join(', ') + (hotLeads.length > 2 ? ` +${hotLeads.length - 2} more` : ''),
        progress: `${hotLeads.length} of ${LEADS.length}`,
      });

    if (escalatedLeads.length)
      livePriority.push({
        icon: 'handoff', tone: 'warm',
        title: `${escalatedLeads.length} lead${escalatedLeads.length > 1 ? 's' : ''} need team`,
        meta: 'Human escalation requested',
        desc: escalatedLeads.slice(0, 2).map(l => esc(l.name)).join(', '),
        progress: '',
      });

    if (PENDING_DRAFTS.length)
      livePriority.push({
        icon: 'inbox', tone: 'violet',
        title: `${PENDING_DRAFTS.length} draft${PENDING_DRAFTS.length > 1 ? 's' : ''} pending review`,
        meta: 'Approval queue — review before sending',
        desc: 'Click Approvals to review',
        progress: '',
      });

    if (!livePriority.length)
      livePriority.push({
        icon: 'check', tone: 'mint',
        title: 'All clear',
        meta: 'No urgent actions right now',
        desc: 'ARIA is handling everything',
        progress: '',
      });

    if (livePriority.length) PRIORITY_ITEMS.splice(0, PRIORITY_ITEMS.length, ...livePriority.slice(0, 3));

    // Derive Co-pilot decisions from live data
    const liveDecisions = [];
    if (demoLeads.length)
      liveDecisions.push({
        icon: 'check', tone: 'mint',
        title: `${demoLeads.length} lead${demoLeads.length > 1 ? 's' : ''} want a demo`,
        meta: 'Follow up to confirm time slot',
        cta: 'Act', goto: 'leads',
      });
    if (PENDING_DRAFTS.length)
      liveDecisions.push({
        icon: 'inbox', tone: 'violet',
        title: `${PENDING_DRAFTS.length} draft${PENDING_DRAFTS.length > 1 ? 's' : ''} waiting`,
        meta: 'Review before they go out',
        cta: 'Review', goto: 'approvals',
      });
    if (escalatedLeads.length)
      liveDecisions.push({
        icon: 'handoff', tone: 'rose',
        title: `${escalatedLeads.length} need${escalatedLeads.length > 1 ? '' : 's'} human`,
        meta: 'Asked to speak to the team',
        cta: 'Handle', goto: 'inbox',
      });

    if (liveDecisions.length)
      OPERATING_STATUS.decisions = liveDecisions;
    else
      OPERATING_STATUS.decisions = [{
        icon: 'sparkle', tone: 'mint',
        title: 'Nothing urgent',
        meta: 'ARIA is running smoothly',
        cta: 'View', goto: 'overview',
      }];

    // Build Inbox conversations from every lead — in a CRM each lead is a thread.
    // Sort most-recently-active first (leads with no activity sink to the bottom).
    const convLeads = [...LEADS]
      .sort((a, b) => (a.last_activity_min ?? 1e9) - (b.last_activity_min ?? 1e9))
      .slice(0, 25);

    // Always rebuild live (never keep sample conversations when served from the server)
    CONVERSATIONS.length = 0;
    convLeads.forEach(l => CONVERSATIONS.push({
      lead_id: l.id,
      unread:  0,
      last_at: l.last_activity_min !== null ? relTime(l.last_activity_min) : 'new',
      escalated: l.status === 'escalated' || l.status === 'needs_human',
      handoff_at: null,
      handed_to:  null,
      preview: l.current_intent
        ? l.current_intent.replace(/_/g, ' ')
        : `${l.quality} · score ${l.score}`,
      lead: {
        id:      l.id,
        name:    l.name,
        city:    l.city,
        channel: l.channel,
        avatar:  l.avatar,
      },
      messages: null,   // lazy-loaded on first click
    }));

    setLiveIndicator(true, LEADS.length);
  } catch (_) {
    // Server not running or network issue — silently use sample data
    setLiveIndicator(false, null);
  }
}

/** Approve a draft via the API, then refresh */
async function approveDraft(draftId, btn) {
  btn.disabled = true;
  btn.innerHTML = `${ICONS.clock} Sending…`;
  try {
    const r = await fetch(`/approval/${draftId}/approve`, { method: 'POST' });
    if (r.ok) {
      await loadLiveData();
      renderDrafts(); renderKPIs(); renderCopilot(); renderOverviewTable();
    } else {
      btn.disabled = false;
      btn.innerHTML = `${ICONS.checkSm} Approve &amp; send`;
    }
  } catch { btn.disabled = false; }
}

/** Reject a draft via the API, then refresh */
async function rejectDraft(draftId, btn) {
  btn.disabled = true;
  try {
    await fetch(`/approval/${draftId}/reject`, { method: 'POST' });
    await loadLiveData();
    renderDrafts(); renderKPIs(); renderCopilot(); renderOverviewTable();
  } catch { btn.disabled = false; }
}

/* ── Inbox helpers ─────────────────────────────────────────────────────────── */

/** Format minutes-ago into a short relative string */
function relTime(minutes) {
  if (!minutes || minutes < 1) return 'now';
  if (minutes < 60)   return `${minutes}m`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h`;
  return `${Math.floor(minutes / 1440)}d`;
}

/**
 * Fetch a lead's full interaction history from the API and populate c.messages.
 * Called lazily when the user first opens a conversation.
 */
async function loadConvMessages(convIdx) {
  const c = CONVERSATIONS[convIdx];
  if (!c || c.messages !== null) return;

  try {
    const r = await fetch(`/leads/${c.lead_id}`);
    if (!r.ok) { c.messages = []; return; }
    const { lead, interactions } = await r.json();

    c.messages = interactions.map(i => {
      const t = i.timestamp
        ? new Date(i.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
        : '—';

      if (i.direction === 'inbound') {
        return { from: 'lead', text: i.message, t };
      }
      if (i.handled_by === 'human') {
        return { from: 'human', who: 'kunal', text: i.message, t };
      }
      // ARIA outbound — store badge separately so text can be safely escaped
      const badge = i.send_status === 'pending_approval'
        ? '<span class="msg-status pending">pending approval</span>'
        : i.send_status === 'rejected'
          ? '<span class="msg-status rejected">rejected</span>'
          : '';
      return { from: 'aria', text: i.message, badge, t };
    });

    // Detect first human handoff
    const firstHuman = interactions.find(
      i => i.handled_by === 'human' && i.direction === 'outbound'
    );
    if (firstHuman) {
      c.escalated = true;
      c.handoff_at = new Date(firstHuman.timestamp)
        .toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      c.handed_to = 'kunal';
    }
  } catch (_) { c.messages = []; }
}
const fmtDate = iso => {
  const [, m, d] = iso.split('-');
  return `${parseInt(d)} ${MONTHS[parseInt(m)-1]}`;
};
const fmtMoney = v => v >= 1e7 ? `₹${(v/1e7).toFixed(1)}Cr` : v >= 1e5 ? `₹${(v/1e5).toFixed(1)}L` : `₹${(v/1e3).toFixed(0)}k`;

/* ─── quality colours (one source of truth) ─── */
const Q_COLOR = { hot:'#6c5ce7', warm:'#34d399', cold:'#fbbf24', new:'#a78bfa' };

/* ═════════ icons (SVG strings) ═════════ */
const ICONS = {
  inbox:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>`,
  handoff: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  clock:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  flame:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
  check:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
  call:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`,
  sparkle: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/></svg>`,
  chevron: `<svg class="pri-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>`,
  more:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/></svg>`,
  phone:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`,
  star:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  edit:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  x:       `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>`,
  checkSm: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
};
const PRI_TONE = {
  warm:   { bg:'#fef3c7', fg:'#b45309' },
  mint:   { bg:'#dcfce7', fg:'#047857' },
  rose:   { bg:'#fce7f3', fg:'#be185d' },
  violet: { bg:'#ede9fe', fg:'#6d28d9' },
};

const TYPE_LBL = { broker:'Broker', IMF:'IMF', agent:'Agent', corporate:'Corp.', posp:'POSP' };
const PF_BG = { facebook:'#1877f2', instagram:'linear-gradient(135deg,#f09433,#dc2743,#bc1888)' };

/* ══════════════════════ VIEW SWITCHING ══════════════════════ */
function switchView(name) {
  $$('.view').forEach(v => v.classList.remove('active'));
  $(`view-${name}`).classList.add('active');
  $$('#navpills .pill').forEach(p => p.classList.toggle('active', p.dataset.view === name));
}
function wireNav() {
  $$('#navpills .pill').forEach(p => p.addEventListener('click', () => switchView(p.dataset.view)));
}

/* ══════════════════════ OVERVIEW : KPI counters ══════════════════════ */
function renderKPIs() {
  const total = LEADS.length;
  const demos = LEADS.filter(l => ['demo_scheduled','demo_done','converted'].includes(l.status)).length;
  animate($('kpi-leads'), total);
  animate($('kpi-demos'), demos);
}
function animate(el, target, ms = 900) {
  if (!el) return;
  const t0 = performance.now();
  (function step(now) {
    const p = Math.min((now - t0) / ms, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(target * ease);
    if (p < 1) requestAnimationFrame(step);
  })(t0);
}

/* ══════════════════════ OVERVIEW : Priority ══════════════════════ */
function renderPriority() {
  $('priority-list').innerHTML = PRIORITY_ITEMS.map(it => {
    const t = PRI_TONE[it.tone];
    return `<li class="priority-item">
      <div class="pri-icon" style="background:${t.bg};color:${t.fg}">${ICONS[it.icon]}</div>
      <div class="pri-body">
        <div class="pri-row">
          <span class="pri-title">${it.title}</span>
          <span class="pri-meta">${it.meta}</span>
          <span class="pri-progress">${it.progress}</span>
        </div>
        <div class="pri-desc">${it.desc}</div>
      </div>
      ${ICONS.chevron}
    </li>`;
  }).join('');
}

/* ══════════════════════ OVERVIEW : ARIA Co-pilot ══════════════════════ */
const CP_TONE = {
  mint:   { bg:'#dcfce7', fg:'#047857' },
  rose:   { bg:'#fce7f3', fg:'#be185d' },
  violet: { bg:'#ede9fe', fg:'#6d28d9' },
  warm:   { bg:'#fef3c7', fg:'#b45309' },
};

function renderCopilot() {
  $('cp-monitor').textContent  = OPERATING_STATUS.monitoring;
  $('cp-drafting').textContent = OPERATING_STATUS.drafting;

  $('cp-actions').innerHTML = OPERATING_STATUS.decisions.map((d, i) => {
    const tone = CP_TONE[d.tone];
    return `<li class="cp-action" data-goto="${d.goto}">
      <div class="cp-ico" style="background:${tone.bg};color:${tone.fg}">${ICONS[d.icon]}</div>
      <div class="cp-body">
        <div class="cp-a-title">${d.title}</div>
        <div class="cp-a-meta">${d.meta}</div>
      </div>
      <button class="cp-a-cta">${d.cta} ›</button>
    </li>`;
  }).join('');

  // clicking either the row or its CTA navigates to the relevant view
  $$('#cp-actions .cp-action').forEach(el => {
    el.addEventListener('click', () => switchView(el.dataset.goto));
  });

  $('cp-stats').innerHTML = OPERATING_STATUS.today.map(s =>
    `<div class="cp-stat"><div class="cp-stat-val">${s.val}</div><div class="cp-stat-lbl">${s.lbl}</div></div>`
  ).join('');
}

/* ══════════════════════ OVERVIEW : Leads table ══════════════════════ */
let overviewQ = '';
function renderOverviewTable() {
  const rows = LEADS
    .filter(l => !overviewQ || l.quality === overviewQ)
    .sort((a,b) => b.score - a.score)
    .slice(0, 8);

  $('leads-body').innerHTML = rows.map(l => `
    <tr>
      <td>
        <div class="client-cell">
          <div class="client-avatar"><img src="${l.avatar}" alt=""><span class="pf-mini ${l.channel === 'facebook' ? 'fb':'ig'}"></span></div>
          <div><div class="client-name">${esc(l.name)}</div><div class="client-handle">${esc(l.handle)}</div></div>
        </div>
      </td>
      <td>
        <div class="lead-cell">
          <div class="lead-co">${esc(l.company)}</div>
          <div class="lead-meta"><span class="type-tag">${TYPE_LBL[l.lead_type]||l.lead_type}</span><span>${esc(l.city)}</span></div>
        </div>
      </td>
      <td><span style="color:var(--ink-3);font-size:12px">${fmtDate(l.created_at)}</span></td>
      <td><div class="score-row"><div class="score-track"><div class="score-fill" style="width:${l.score}%"></div></div><span class="score-num">${l.score}</span></div></td>
      <td><span class="status st-${l.status}">${l.status.replace(/_/g,' ')}</span></td>
      <td><button class="row-more">${ICONS.more}</button></td>
    </tr>
  `).join('');

  $('c-all').textContent  = LEADS.length;
  $('c-hot').textContent  = LEADS.filter(l => l.quality === 'hot').length;
  $('c-warm').textContent = LEADS.filter(l => l.quality === 'warm').length;
}
function wireOverviewTabs() {
  $$('#lead-tabs .tab').forEach(t => t.addEventListener('click', () => {
    $$('#lead-tabs .tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    overviewQ = t.dataset.q;
    renderOverviewTable();
  }));
}

/* ══════════════════════ OVERVIEW : DOT CHART (with tooltips) ══════════════════════ */
let chartLayout = null;  // saved layout for tooltip positioning

function renderDotChart() {
  const host = $('dot-chart');
  const W = host.clientWidth || 600;
  const H = 240;
  const PAD = { t: 30, r: 12, b: 28, l: 28 };
  const chartW = W - PAD.l - PAD.r;
  const chartH = H - PAD.t - PAD.b;

  // group leads by day — last 28 days from today (dynamic, not hardcoded to May)
  const todayDt = new Date();
  const days = [];
  for (let i = 27; i >= 0; i--) {
    const dt = new Date(todayDt);
    dt.setDate(todayDt.getDate() - i);
    const key = dt.toISOString().split('T')[0];
    const mo  = MONTHS[dt.getMonth()];
    const day = dt.getDate();
    const todays = LEADS.filter(l => l.created_at === key)
      .sort((a, b) => b.score - a.score);
    days.push({ date: key, day, month: mo, leads: todays });
  }

  // Focus: today (last day in range). If it has zero leads, fall back to most recent active day.
  let focusIdx = days.length - 1;
  if (!days[focusIdx].leads.length) {
    for (let i = days.length - 1; i >= 0; i--) {
      if (days[i].leads.length) { focusIdx = i; break; }
    }
  }

  const maxCount = Math.max(4, ...days.map(d => d.leads.length));
  const slot = chartW / days.length;
  const dotR = 4.5;

  // ONE y-scale used by both ticks AND dots — guarantees alignment.
  const yScale = v => PAD.t + chartH - (v / maxCount) * chartH;

  let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">`;

  // Y axis: one tick per integer (0..maxCount). Now labels mean exactly "n leads".
  for (let v = 0; v <= maxCount; v++) {
    const y = yScale(v);
    svg += `<line class="dc-grid" x1="${PAD.l}" y1="${y}" x2="${W - PAD.r}" y2="${y}"/>`;
    svg += `<text class="dc-y-lbl" x="${PAD.l - 6}" y="${y + 3}" text-anchor="end">${v}</text>`;
  }

  // focus highlight rail
  const fx = PAD.l + focusIdx * slot + slot / 2;
  svg += `<rect class="dc-highlight" x="${fx - 16}" y="${PAD.t - 4}" width="32" height="${chartH + 8}"/>`;

  // forecast tail (projected to next 7 days)
  const forecast = [];
  for (let i = Math.max(0, days.length - 8); i < days.length; i++) {
    const proj = Math.min(days[i].leads.length * 1.18, maxCount);
    forecast.push(`${PAD.l + i * slot + slot / 2},${yScale(proj)}`);
  }
  if (forecast.length > 1) svg += `<polyline class="dc-tail" points="${forecast.join(' ')}"/>`;

  // Dots: the (i+1)th lead in the stack sits exactly at y = yScale(i+1).
  // So a column of 2 dots has its top dot touching the "2" gridline.
  days.forEach((d, idx) => {
    const x = PAD.l + idx * slot + slot / 2;
    d.leads.forEach((lead, i) => {
      const y = yScale(i + 1);
      svg += `<circle class="dc-dot" cx="${x}" cy="${y}" r="${dotR}" fill="${Q_COLOR[lead.quality]}" opacity="0.95" data-lead-id="${lead.id}"/>`;
    });
  });

  // Focus pill — sits just above the top dot of the focus day.
  const n = days[focusIdx].leads.length;
  const pillY = n > 0 ? yScale(n) - 28 : PAD.t - 22;
  svg += `<g transform="translate(${fx - 26}, ${pillY})">
    <rect class="dc-pill-bg" x="0" y="0" width="52" height="20"/>
    <text class="dc-pill" x="26" y="13.5" text-anchor="middle">${n} lead${n !== 1 ? 's' : ''}</text>
  </g>`;

  // X-axis labels: a handful evenly + focus day labeled "Today" if it's May 28.
  const labelIdx = new Set([0, 6, 13, focusIdx, 20]);
  days.forEach((d, idx) => {
    if (!labelIdx.has(idx)) return;
    const x = PAD.l + idx * slot + slot / 2;
    const cls = idx === focusIdx ? 'dc-x-lbl active' : 'dc-x-lbl';
    const text = idx === days.length - 1 ? 'Today' : `${d.month} ${d.day}`;
    svg += `<text class="${cls}" x="${x}" y="${H - 8}" text-anchor="middle">${text}</text>`;
  });

  svg += `</svg>`;
  const tt = $('dc-tooltip');
  host.innerHTML = svg;
  host.appendChild(tt);
  chartLayout = { W, H };
  wireDotHover(host);
}

function wireDotHover(host) {
  const tt = $('dc-tooltip');
  host.addEventListener('mouseover', e => {
    if (e.target.tagName !== 'circle' || !e.target.dataset.leadId) return;
    const lead = LEADS.find(l => l.id == e.target.dataset.leadId);
    if (!lead) return;
    const dotBox = e.target.getBoundingClientRect();
    const hostBox = host.getBoundingClientRect();
    const left = dotBox.left + dotBox.width/2 - hostBox.left;
    const top  = dotBox.top - hostBox.top;
    tt.innerHTML = `
      <div class="dc-tt-head">
        <div class="dc-tt-avatar"><img src="${lead.avatar}" alt=""></div>
        <div>
          <div class="dc-tt-name">${esc(lead.name)}</div>
          <div class="dc-tt-co">${esc(lead.company)} · ${esc(lead.city)}</div>
        </div>
      </div>
      <div class="dc-tt-meta">
        <span class="dc-tt-q" style="background:${Q_COLOR[lead.quality]}"></span>
        Score ${lead.score} · ${lead.status.replace(/_/g,' ')}
      </div>`;
    tt.style.left = left + 'px';
    tt.style.top = top + 'px';
    tt.classList.add('show');
  });
  host.addEventListener('mouseout', e => {
    if (e.target.tagName === 'circle') $('dc-tooltip').classList.remove('show');
  });
}

/* ══════════════════════ LEADS VIEW ══════════════════════ */
let leadsQ = '';

function pfDotStyle(channel) {
  return channel === 'facebook' ? 'background:#1877f2' : 'background:linear-gradient(135deg,#f09433,#dc2743,#bc1888)';
}

function renderLeadGrid() {
  const cards = LEADS
    .filter(l => !leadsQ || l.quality === leadsQ)
    .sort((a, b) => b.score - a.score)
    .slice(0, 18);

  if (!cards.length) {
    $('lead-grid').innerHTML = `
      <div style="grid-column:1/-1;padding:48px;text-align:center;color:var(--ink-4);font-size:13px">
        ${leadsQ ? `No ${leadsQ} leads right now.` : 'No leads yet. New leads from Facebook/Instagram will appear here.'}
      </div>`;
    return;
  }

  $('lead-grid').innerHTML = cards.map(l => {
    const owner = l.owner ? TEAM[l.owner] : null;
    const ownerPill = owner
      ? `<div class="lc-owner" title="Owner: ${owner.name}"><div class="lc-owner-av"><img src="${owner.avatar}" alt=""></div>${owner.name}</div>`
      : `<div class="lc-owner" style="color:var(--ink-4)" title="Unassigned">· unassigned</div>`;
    return `
      <div class="lead-card">
        <span class="lc-quality-dot lc-q-${l.quality}"></span>
        ${ownerPill}
        <div class="lc-avatar">
          <img src="${l.avatar}" alt="">
          <span class="pf-mini" style="${pfDotStyle(l.channel)}"></span>
        </div>
        <div class="lc-name">${esc(l.name)}</div>
        <div class="lc-role">${esc(l.role)} · ${esc(l.company)}</div>
        <div class="lc-grid">
          <div class="lc-stat">
            <span class="lc-stat-lbl">From</span>
            <span class="lc-channel" style="${pfDotStyle(l.channel)}"></span>
          </div>
          <div class="lc-stat">
            <span class="lc-stat-lbl">Sector</span>
            <span class="lc-stat-val">${TYPE_LBL[l.lead_type] || l.lead_type}</span>
          </div>
          <div class="lc-stat">
            <span class="lc-stat-lbl">Value</span>
            <span class="lc-stat-val">${fmtMoney(l.pipeline)}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderSourceMix() {
  const fb = LEADS.filter(l => l.channel === 'facebook').length;
  const ig = LEADS.filter(l => l.channel === 'instagram').length;
  $('source-mix').innerHTML = `
    <div class="sm-bucket" style="--sm-tint:#dbeafe">
      <span class="sm-num">${fb}</span><span class="sm-lbl">Facebook</span>
    </div>
    <div class="sm-bucket" style="--sm-tint:#fce7f3">
      <span class="sm-num">${ig}</span><span class="sm-lbl">Instagram</span>
    </div>
    <div class="sm-bucket" style="--sm-tint:#dcfce7">
      <span class="sm-num">0</span><span class="sm-lbl">Web direct</span>
    </div>
  `;
}

function wireLeadsTabs() {
  $$('#leads-view-tabs .tab').forEach(t => t.addEventListener('click', () => {
    $$('#leads-view-tabs .tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    leadsQ = t.dataset.q;
    renderLeadGrid();
  }));
}

/* ══════════════════════ INBOX COMPOSER ══════════════════════ */

/**
 * Enable or disable the Inbox message composer depending on whether
 * the active conversation has been escalated to the team.
 * Only escalated conversations allow team replies.
 */
function wireInboxComposer(c) {
  const form    = document.getElementById('conv-input-form');
  const input   = document.getElementById('inbox-reply-input');
  const sendBtn = document.getElementById('inbox-send-btn');
  const foot    = document.getElementById('conv-foot');
  if (!form || !input || !sendBtn) return;

  if (c && c.escalated) {
    input.disabled   = false;
    sendBtn.disabled = false;
    input.placeholder = `Reply to ${esc(c.lead.name)}…`;
    if (foot) foot.textContent = 'You are replying as a team member. Lead sees this in real-time.';

    // Replace any previous handler (fresh wire each render)
    const handler = (e) => {
      e.preventDefault();
      sendHumanReply(c, input, sendBtn);
    };
    form.onsubmit = handler;
  } else {
    input.disabled    = true;
    sendBtn.disabled  = true;
    input.placeholder = 'ARIA is handling this conversation';
    if (foot) foot.textContent = 'ARIA is managing this conversation.';
    form.onsubmit = e => e.preventDefault();
  }
}

/** Send a human reply from the Inbox to the lead's chat thread. */
async function sendHumanReply(c, input, sendBtn) {
  const msg = input.value.trim();
  if (!msg) return;

  input.disabled   = true;
  sendBtn.disabled = true;
  const original   = sendBtn.innerHTML;
  sendBtn.innerHTML = ICONS.clock;

  try {
    const r = await fetch(`/chat/admin/${c.lead_id}/reply`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message: msg }),
    });

    if (r.ok) {
      const data = await r.json();
      input.value = '';

      // Optimistically append to the conversation thread
      if (c.messages) {
        c.messages.push({
          from: 'human',
          who:  'kunal',
          text: data.message,
          t:    new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        });
        renderConvThread();   // re-renders thread + re-wires composer
        return;               // early return — composer is re-wired inside renderConvThread
      }
    }
  } catch (_) {}

  // Restore on error
  sendBtn.innerHTML = original;
  input.disabled    = false;
  sendBtn.disabled  = false;
  input.focus();
}

/* ══════════════════════ INBOX VIEW ══════════════════════ */
let activeConv = 0;
let convFilter = 'all';   // 'all' | 'aria' | 'team'

function filteredConvs() {
  if (convFilter === 'aria') return CONVERSATIONS.filter(c => !c.escalated);
  if (convFilter === 'team') return CONVERSATIONS.filter(c => c.escalated);
  return CONVERSATIONS;
}

function renderConvList() {
  // counts (always show against full list, not filtered)
  $('cf-all').textContent  = CONVERSATIONS.length;
  $('cf-aria').textContent = CONVERSATIONS.filter(c => !c.escalated).length;
  $('cf-team').textContent = CONVERSATIONS.filter(c =>  c.escalated).length;

  const list = filteredConvs();

  if (!list.length) {
    $('conv-list').innerHTML = `
      <li style="padding:40px 20px;text-align:center;color:var(--ink-4);font-size:13px;list-style:none">
        ${convFilter === 'team' ? 'No conversations need the team yet.'
          : convFilter === 'aria' ? 'No active ARIA conversations.'
          : 'No conversations yet. Leads appear here once they arrive.'}
      </li>`;
    return;
  }

  $('conv-list').innerHTML = list.map((c) => {
    const idx = CONVERSATIONS.indexOf(c);   // preserve global index for click
    const teamFlag = c.escalated
      ? `<span class="cli-flag">${ICONS.handoff} Needs team</span>`
      : '';
    return `
      <li class="conv-list-item ${idx === activeConv ? 'active' : ''}" data-i="${idx}">
        <div class="cli-avatar">
          <img src="${c.lead.avatar}" alt="">
          <span class="pf-mini ${c.lead.channel === 'facebook' ? 'fb':'ig'}"></span>
        </div>
        <div class="cli-body">
          <div class="cli-row">
            <span class="cli-name">${esc(c.lead.name)}</span>
            <span class="cli-time">${c.last_at}</span>
          </div>
          <div class="cli-preview">${esc(c.preview)}</div>
          ${teamFlag}
        </div>
        ${c.unread ? `<div class="cli-unread">${c.unread}</div>` : ''}
      </li>
    `;
  }).join('');

  $$('#conv-list .conv-list-item').forEach(li => {
    li.addEventListener('click', () => {
      activeConv = parseInt(li.dataset.i);
      renderConvList();
      renderConvThread();
    });
  });
}

function wireConvFilters() {
  $$('#conv-filters .conv-fchip').forEach(b => {
    b.addEventListener('click', () => {
      $$('#conv-filters .conv-fchip').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      convFilter = b.dataset.f;
      renderConvList();
    });
  });
}

function renderConvThread() {
  const c = CONVERSATIONS[activeConv];
  if (!c) return;

  $('conv-head').innerHTML = `
    <div class="ch-avatar"><img src="${c.lead.avatar}" alt=""></div>
    <div>
      <div class="ch-name">${esc(c.lead.name)}</div>
      <div class="ch-meta">${esc(c.lead.city)} · Local time ${new Date().toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit'})}</div>
    </div>
    <div class="ch-tools">
      <button class="icon-btn sm" title="Call">${ICONS.phone}</button>
      <button class="icon-btn sm" title="Save">${ICONS.star}</button>
      <button class="icon-btn sm">${ICONS.more}</button>
    </div>
  `;

  // Lazy-load messages when this conversation hasn't been opened yet
  if (c.messages === null) {
    $('conv-thread').innerHTML = `
      <div style="padding:40px;text-align:center;color:var(--ink-4);font-size:13px">
        Loading conversation…
      </div>`;
    wireInboxComposer(null);   // disable composer while loading
    loadConvMessages(activeConv).then(() => {
      // Only re-render if the user is still on this conversation
      if (CONVERSATIONS[activeConv] === c) renderConvThread();
    });
    return;
  }

  if (c.messages.length === 0) {
    $('conv-thread').innerHTML = `
      <div style="padding:40px;text-align:center;color:var(--ink-4);font-size:13px">
        No messages yet — ARIA's first-touch draft is in the approval queue.
      </div>`;
    return;
  }

  // Wire composer now that messages are loaded
  wireInboxComposer(c);

  // Walk messages — inject a handoff divider the first time we see a human sender.
  // Preserves full lead↔ARIA history so the teammate picks up with context.
  const FALLBACK_TM = { name: 'Team', role: 'BeyondSure', avatar: avatarUrl('BeyondSure Team') };

  let dividerInjected = false;
  $('conv-thread').innerHTML = c.messages.map(m => {
    let divider = '';
    if (m.from === 'human' && !dividerInjected) {
      dividerInjected = true;
      const tm = TEAM[c.handed_to] || TEAM[m.who] || FALLBACK_TM;
      divider = `
        <div class="handoff-divider">
          <div class="ho-line"></div>
          <div class="handoff-pill">
            <div class="ho-avatar"><img src="${tm.avatar}" alt=""></div>
            <span>ARIA handed off to <b>${tm.name}</b></span>
            <span class="ho-time">· ${c.handoff_at || 'now'}</span>
          </div>
          <div class="ho-line"></div>
        </div>
      `;
    }
    return divider + renderBubble(m);
  }).join('');
}

function renderBubble(m) {
  if (m.from === 'human') {
    const tm = TEAM[m.who] || { name: 'Team', role: 'BeyondSure', avatar: avatarUrl('BeyondSure') };
    return `
      <div class="bubble-row human">
        <div class="bubble-who"><div class="bubble-who-avatar"><img src="${tm.avatar}" alt=""></div>${esc(tm.name)} · ${esc(tm.role)}</div>
        <div class="bubble human">${esc(m.text)}</div>
        <div class="bubble-time">${m.t}</div>
      </div>
    `;
  }
  const cls = m.from === 'lead' ? 'lead' : 'aria';
  // badge is a trusted HTML span (our own code); text is user/LLM-supplied → escape it
  const badge = m.badge ? ' ' + m.badge : '';
  return `
    <div class="bubble-row ${cls}">
      <div class="bubble ${cls}">${esc(m.text)}${badge}</div>
      <div class="bubble-time">${m.t}</div>
    </div>
  `;
}

/* ══════════════════════ APPROVALS VIEW ══════════════════════ */
function renderDrafts() {
  $('ap-pending').textContent = PENDING_DRAFTS.length;

  if (!PENDING_DRAFTS.length) {
    $('draft-list').innerHTML = `
      <div style="padding:48px;text-align:center;color:var(--ink-4)">
        <div style="font-size:32px;margin-bottom:8px">✓</div>
        <div style="font-weight:600;color:var(--ink-2)">All clear</div>
        <div style="font-size:13px;margin-top:4px">No drafts waiting for review</div>
      </div>`;
    return;
  }

  $('draft-list').innerHTML = PENDING_DRAFTS.map(d => {
    // Prefer live LEADS lookup; fall back to API fields stored in draft
    const lead = LEADS.find(l => l.id === d.lead_id) || {
      avatar: avatarUrl(d._lead_name || 'Unknown'),
      name: d._lead_name || 'Unknown',
      company: d._lead_email || '—',
      city: '—',
      status: 'active',
      quality: d._lead_quality || 'new',
    };
    const time = d.created_at ? d.created_at.split('T')[1]?.slice(0, 5) : '—';
    return `
      <div class="draft" data-draft-id="${d.id}">
        <div class="draft-lead">
          <div class="client-avatar"><img src="${lead.avatar}" alt=""></div>
          <div>
            <div class="draft-lead-name">${esc(lead.name)}</div>
            <div class="draft-lead-co">${esc(lead.company)} · ${esc(lead.city)}</div>
          </div>
        </div>
        <div class="draft-body">
          <div class="draft-meta">
            <span class="intent-tag">${d.intent.replace(/_/g, ' ')}</span>
            <span class="draft-time">Drafted at ${time}</span>
            <span class="status st-${lead.status}">${lead.status.replace(/_/g,' ')}</span>
          </div>
          <div class="draft-subject">${esc(d.subject)}</div>
          <div class="draft-text">${esc(d.body)}</div>
        </div>
        <div class="draft-actions">
          <button class="btn btn-approve" data-did="${d.id}">${ICONS.checkSm} Approve &amp; send</button>
          <button class="btn btn-edit">${ICONS.edit} Edit</button>
          <button class="btn btn-reject" data-did="${d.id}">${ICONS.x} Reject</button>
        </div>
      </div>
    `;
  }).join('');

  // Wire approve / reject buttons to the live API
  $$('#draft-list .btn-approve').forEach(btn => {
    btn.addEventListener('click', () => approveDraft(btn.dataset.did, btn));
  });
  $$('#draft-list .btn-reject').forEach(btn => {
    btn.addEventListener('click', () => rejectDraft(btn.dataset.did, btn));
  });
}

/* ══════════════════════ ANALYTICS VIEW ══════════════════════ */
function renderFunnel() {
  $('funnel').innerHTML = ANALYTICS.funnel.map(s => `
    <div class="funnel-row">
      <span class="funnel-stage">${s.stage}</span>
      <div class="funnel-track"><div class="funnel-fill" style="width:${s.pct}%"><span class="fpct">${s.pct}%</span></div></div>
      <span class="funnel-count">${s.count}</span>
    </div>
  `).join('');
}

function renderSourceChart() {
  const total = ANALYTICS.sources.reduce((a, s) => a + s.count, 0);
  const C = 130, R = 52, SW = 18;
  const circ = 2 * Math.PI * R;
  let offset = 0;
  const segments = ANALYTICS.sources.map(s => {
    const frac = s.count / total;
    const dash = frac * circ;
    const seg = `<circle cx="${C/2}" cy="${C/2}" r="${R}" fill="none" stroke="${s.color}" stroke-width="${SW}" stroke-dasharray="${dash} ${circ}" stroke-dashoffset="${-offset}" transform="rotate(-90 ${C/2} ${C/2})"/>`;
    offset += dash;
    return seg;
  }).join('');

  $('src-chart').innerHTML = `
    <div class="donut-wrap">
      <svg viewBox="0 0 ${C} ${C}" width="${C}" height="${C}">${segments}</svg>
      <div class="donut-center"><div><div class="donut-num">${total}</div><div class="donut-lbl">Leads</div></div></div>
    </div>
    <div class="src-legend">
      ${ANALYTICS.sources.map(s => `
        <div class="src-row">
          <span class="src-sw" style="background:${s.color}"></span>
          <span class="src-name">${s.name}</span>
          <span class="src-count">${s.count}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderHistogram() {
  const max = Math.max(...ANALYTICS.scoreBuckets.map(b => b.n));
  $('histogram').innerHTML = ANALYTICS.scoreBuckets.map(b => {
    const h = (b.n / max) * 110;
    return `<div class="hg-bar">
      <div class="hg-track" style="height:${h}px"><span class="hg-n">${b.n}</span></div>
      <span class="hg-lbl">${b.b}</span>
    </div>`;
  }).join('');
}

function renderWeekly() {
  const maxL = Math.max(...ANALYTICS.weeklyTrend.map(w => w.leads));
  $('weekly').innerHTML = ANALYTICS.weeklyTrend.map(w => `
    <div class="weekly-row">
      <span class="weekly-lbl">${w.w}</span>
      <div class="weekly-bars">
        <div class="wb1" style="height:${(w.leads/maxL)*28}px"></div>
        <div class="wb2" style="height:${(w.demos/maxL)*28}px"></div>
      </div>
      <span class="weekly-nums"><b>${w.leads}</b> · ${w.demos}</span>
    </div>
  `).join('');
}

function renderCohorts() {
  $('cohort-body').innerHTML = ANALYTICS.cohorts.map(c => {
    const conv = c.leads ? ((c.won / c.leads) * 100).toFixed(1) : '0.0';
    return `<tr>
      <td><b>${c.week}</b></td>
      <td>${c.leads}</td>
      <td>${c.contacted}</td>
      <td>${c.replied}</td>
      <td>${c.demos}</td>
      <td>${c.won}</td>
      <td><b>${conv}%</b></td>
    </tr>`;
  }).join('');
}

function renderTopPerformers() {
  const top = [...LEADS].sort((a,b) => b.score - a.score).slice(0, 5);
  const rankCls = ['gold', 'silver', 'bronze'];
  $('top-list').innerHTML = top.map((l, i) => `
    <li class="top-row">
      <div class="top-rank ${rankCls[i] || ''}">${i + 1}</div>
      <div class="client-avatar"><img src="${l.avatar}" alt=""></div>
      <span class="top-name">${esc(l.name)}</span>
      <span class="top-score">${l.score}</span>
    </li>
  `).join('');
}

/* ══════════════════════ OVERVIEW : Mini cards + Leads sub ══════════════════════ */
function renderMiniCards() {
  // Response time
  const resp = $('mini-resp');
  if (resp) {
    const m = LIVE_STATS.avgResponseMin;
    resp.textContent = (m === null || m === undefined) ? 'no data' : `${Math.round(m)} min`;
  }

  // Conversion: demos booked vs hot leads
  const demos = LEADS.filter(l => l.willing_for_demo
    || ['demo_scheduled','demo_done','converted'].includes(l.status)).length;
  const hot   = LEADS.filter(l => l.quality === 'hot').length;
  const pct   = LEADS.length ? Math.round((demos / LEADS.length) * 100) : 0;

  if ($('mini-demos')) $('mini-demos').textContent = demos;
  if ($('mini-hot'))   $('mini-hot').textContent   = hot;
  if ($('mini-conv-fill'))   $('mini-conv-fill').style.width  = pct + '%';
  if ($('mini-conv-marker')) $('mini-conv-marker').style.left = pct + '%';
}

function renderLeadsSub() {
  const el = $('leads-card-sub');
  if (!el) return;
  const q = LIVE_STATS.byQuality || {};
  const total = LEADS.length;
  el.textContent = total
    ? `${total} total · ${q.hot||0} hot, ${q.warm||0} warm, ${q.cold||0} cold, ${q.new||0} fresh`
    : 'No leads yet';
}

/* ══════════════════════ ME AVATAR ══════════════════════ */
function renderMe() {
  const img = $('me-avatar');
  if (img) img.src = ME.avatar;
}

/* ══════════════════════ RE-RENDER ALL ══════════════════════ */
function renderAll() {
  renderKPIs();
  renderPriority();
  renderCopilot();
  renderMiniCards();
  renderOverviewTable();
  renderDotChart();
  renderLeadGrid();
  renderLeadsSub();
  renderSourceMix();
  renderConvList();
  renderConvThread();
  renderDrafts();
  renderFunnel();
  renderSourceChart();
  renderHistogram();
  renderWeekly();
  renderCohorts();
  renderTopPerformers();
}

/* ══════════════════════ BOOT ══════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  renderMe();
  wireNav();
  wireOverviewTabs();
  wireLeadsTabs();

  // Inbox — default to first escalated thread (shows ARIA→human handoff)
  const firstEscalated = CONVERSATIONS.findIndex(c => c.escalated);
  if (firstEscalated >= 0) activeConv = firstEscalated;
  wireConvFilters();

  // 1. Render immediately with sample data (instant visual — no blank flash)
  renderAll();

  // 2. Load live data from the API, then re-render with real numbers
  await loadLiveData();
  // Live data rebuilt CONVERSATIONS — re-select a valid thread (prefer escalated)
  const liveEscalated = CONVERSATIONS.findIndex(c => c.escalated);
  activeConv = liveEscalated >= 0 ? liveEscalated : 0;
  renderAll();

  // Refresh button
  const refreshBtn = $('refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.style.opacity = '0.4';
      refreshBtn.style.pointerEvents = 'none';
      await loadLiveData();
      renderAll();
      refreshBtn.style.opacity = '';
      refreshBtn.style.pointerEvents = '';
    });
  }

  // Re-render chart on resize
  let rt;
  window.addEventListener('resize', () => {
    clearTimeout(rt);
    rt = setTimeout(renderDotChart, 150);
  });

  // Auto-refresh live data every 30 s. Re-renders the non-disruptive views
  // (skips renderConvThread so a team member mid-reply isn't interrupted).
  setInterval(async () => {
    await loadLiveData();
    renderDrafts();
    renderKPIs();
    renderCopilot();
    renderMiniCards();
    renderOverviewTable();
    renderDotChart();
    renderLeadGrid();
    renderLeadsSub();
    renderConvList();
    renderFunnel();
    renderSourceChart();
    renderHistogram();
    renderWeekly();
    renderCohorts();
    renderTopPerformers();
  }, 30_000);
});
