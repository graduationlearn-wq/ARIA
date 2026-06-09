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
/** Approval stats + recent activity from /approval/stats */
let APPROVAL = { stats: {}, activity: [] };

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
/* ══════════════════════ AUTH & HIERARCHY ══════════════════════ */
let CURRENT_USER = null;          // logged-in user {id,name,email,role,...}
let VIEWABLE = [];                // users this user can drill into
let VIEW_AS = null;               // user_id being viewed, or null = own scope
let ASSIGNABLE_OWNERS = [];       // employees this user can reassign leads to

const roleLabel = r => r === 'admin' ? 'Admin' : r === 'manager' ? 'Manager' : 'Employee';
const asParam = () => VIEW_AS ? `?as=${VIEW_AS}` : '';

async function checkAuth() {
  try {
    const r = await fetch('/auth/me');
    if (!r.ok) return false;
    const d = await r.json();
    CURRENT_USER = d.user; VIEWABLE = d.viewable || [];
    return true;
  } catch { return false; }
}

async function doLogin(email, password) {
  const r = await fetch('/auth/login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail || 'Invalid email or password');
  }
  const d = await r.json();
  CURRENT_USER = d.user; VIEWABLE = d.viewable || [];
}

async function loadAssignableOwners() {
  ASSIGNABLE_OWNERS = [];
  if (!CURRENT_USER || CURRENT_USER.role === 'employee') return;
  try { const r = await fetch('/leads/assignable-owners'); if (r.ok) ASSIGNABLE_OWNERS = await r.json(); } catch {}
}

function renderIdentity() {
  if (!CURRENT_USER) return;
  const av = avatarUrl(CURRENT_USER.avatar_seed || CURRENT_USER.name);
  if ($('me-avatar'))         $('me-avatar').src = av;
  if ($('avatar-menu-img'))   $('avatar-menu-img').src = av;
  if ($('avatar-menu-name'))  $('avatar-menu-name').textContent = CURRENT_USER.name;
  if ($('avatar-menu-role'))  $('avatar-menu-role').textContent = `${roleLabel(CURRENT_USER.role)} · ${CURRENT_USER.email}`;
  renderViewAs();
}

function renderViewAs() {
  const host = $('viewas');
  if (!host) return;
  if (!CURRENT_USER || CURRENT_USER.role === 'employee') { host.innerHTML = ''; return; }
  const allLabel = CURRENT_USER.role === 'admin' ? 'Everyone' : 'My team';
  const opts = [`<option value="">${allLabel}</option>`].concat(
    VIEWABLE.filter(u => u.id !== CURRENT_USER.id).map(u =>
      `<option value="${u.id}" ${String(VIEW_AS) === String(u.id) ? 'selected' : ''}>${esc(u.name)} · ${roleLabel(u.role)}</option>`)
  );
  host.innerHTML = `<select id="viewas-select" class="viewas-select" title="Whose pipeline to view">${opts.join('')}</select>`;
  $('viewas-select').addEventListener('change', async e => {
    VIEW_AS = e.target.value || null;
    await loadLiveData();
    renderAll();
  });
}

function showLogin(msg) {
  const o = $('login-overlay'); if (o) o.hidden = false;
  const e = $('login-error'); if (e) { e.hidden = !msg; if (msg) e.textContent = msg; }
}
function hideLogin() { const o = $('login-overlay'); if (o) o.hidden = true; }

async function loadAuthConfig() {
  try { const r = await fetch('/auth/config'); if (r.ok) return (await r.json()).provider || 'local'; } catch {}
  return 'local';
}

function applyLoginMode(provider) {
  const local = $('login-local'), a0 = $('login-auth0'), sub = $('login-sub');
  if (provider === 'auth0') {
    if (local) local.hidden = true;
    if (a0) { a0.hidden = false; a0.onclick = () => { window.location.href = '/auth/login'; }; }
    if (sub) sub.textContent = 'Sign in with your BeyondSure (Auth0) account.';
  } else {
    if (local) local.hidden = false;
    if (a0) a0.hidden = true;
  }
}

function wireLogin() {
  const f = $('login-form'); if (!f) return;
  f.addEventListener('submit', async ev => {
    ev.preventDefault();
    const email = ($('login-email').value || '').trim();
    const password = $('login-password').value || '';
    const btn = $('login-submit'); const orig = btn.textContent;
    btn.disabled = true; btn.textContent = 'Signing in…';
    try {
      await doLogin(email, password);
      hideLogin();
      await bootDashboard();
    } catch (err) {
      showLogin(err.message || 'Invalid email or password');
    } finally { btn.disabled = false; btn.textContent = orig; }
  });
}

/** Render identity + load data once the user is authenticated. */
async function bootDashboard() {
  renderIdentity();
  await loadAssignableOwners();
  const fe = CONVERSATIONS.findIndex(c => c.escalated);
  if (fe >= 0) activeConv = fe;
  renderAll();
  await Promise.all([loadLiveData(), loadConfig()]);
  const le = CONVERSATIONS.findIndex(c => c.escalated);
  activeConv = le >= 0 ? le : 0;
  renderAll();
}

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
    meet_link: l.meet_link || null,
    demo_preference: l.demo_preference || null,
    email: l.email || '',
    stage: l.stage || 'new',
    owner_id: l.owner_id || null,
    owner_name: l.owner_name || null,
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
    const asQ = VIEW_AS ? `?as=${VIEW_AS}` : '';
    const [statsRes, leadsRes, queueRes] = await Promise.all([
      fetch(`/leads/stats${asQ}`),
      fetch(`/leads/?limit=200${VIEW_AS ? `&as=${VIEW_AS}` : ''}`),
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

    // Fetch approval stats + recent activity
    try {
      const sRes = await fetch('/approval/stats');
      if (sRes.ok) APPROVAL = await sRes.json();
    } catch (_) { /* keep last known */ }

    // Fetch analytics for the Analytics view
    try {
      const aRes = await fetch(`/leads/analytics${VIEW_AS ? `?as=${VIEW_AS}` : ''}`);
      if (aRes.ok) {
        const a = await aRes.json();
        ANALYTICS.funnel       = a.funnel.map(s => ({ stage: s.stage, count: s.count, pct: s.pct }));
        ANALYTICS.stages       = (a.stages || []).map(s => ({ key: s.key, label: s.label, count: s.count }));
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
      renderDrafts(); renderActivity(); renderKPIs(); renderCopilot(); renderOverviewTable(); renderLeadsQuick();
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

    // Enrich the conversation's lead with detail fields for the header tools
    if (lead) {
      c.lead.phone = lead.phone;
      c.lead.email = lead.email;
      c.lead.human_priority = lead.human_priority;
      c.lead.score = lead.score;
      c.lead.quality = lead.quality;
    }

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
  video:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m23 7-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>`,
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
function newThisWeek() {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 7);
  return LEADS.filter(l => l.created_at && new Date(l.created_at) >= cutoff).length;
}

function renderKPIs() {
  const total = LEADS.length;
  const demos = LEADS.filter(l => l.willing_for_demo
    || ['demo_scheduled','demo_done','converted'].includes(l.status)).length;
  animate($('kpi-leads'), total);
  animate($('kpi-demos'), demos);

  // Hot pipeline value (sum of estimated pipeline across hot leads)
  const hotLeads    = LEADS.filter(l => l.quality === 'hot');
  const hotPipeline = hotLeads.reduce((s, l) => s + (l.pipeline || 0), 0);
  if ($('kpi-pipeline'))     $('kpi-pipeline').textContent     = hotPipeline ? fmtMoney(hotPipeline) : '₹0';
  if ($('kpi-pipeline-sub')) $('kpi-pipeline-sub').textContent = `${hotLeads.length} hot lead${hotLeads.length !== 1 ? 's' : ''}`;

  // "New this week" chip on the Leads card
  const wk = newThisWeek();
  const chip = $('kpi-leads-chip');
  if (chip) { chip.hidden = wk === 0; chip.textContent = `+${wk} this wk`; }
  if ($('kpi-leads-sub')) $('kpi-leads-sub').textContent = `${total} total in pipeline`;
  if ($('kpi-demos-sub')) $('kpi-demos-sub').textContent = 'demo-ready leads';
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
    .sort(SORTERS[leadsSort])
    .slice(0, 8);

  $('leads-body').innerHTML = rows.map(l => `
    <tr>
      <td>
        <div class="client-cell">
          <div class="client-avatar"><img src="${l.avatar}" alt="">${pfPip(l.channel)}</div>
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
let chartMode = 'day';   // 'day' | 'week' | 'month'

/** Bucket leads into time columns for the current chart mode */
function buildChartBuckets(mode) {
  const now = new Date();
  const buckets = [];
  const inDay = (l, key) => l.created_at === key;

  if (mode === 'week') {
    for (let i = 11; i >= 0; i--) {
      const end = new Date(now); end.setDate(now.getDate() - i * 7); end.setHours(23,59,59,999);
      const start = new Date(end); start.setDate(end.getDate() - 6); start.setHours(0,0,0,0);
      const leads = LEADS.filter(l => { const d = new Date(l.created_at); return d >= start && d <= end; })
        .sort((a, b) => b.score - a.score);
      buckets.push({ leads, label: `${MONTHS[start.getMonth()]} ${start.getDate()}`, isLast: i === 0 });
    }
  } else if (mode === 'month') {
    for (let i = 5; i >= 0; i--) {
      const dt = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const leads = LEADS.filter(l => {
        const d = new Date(l.created_at);
        return d.getFullYear() === dt.getFullYear() && d.getMonth() === dt.getMonth();
      }).sort((a, b) => b.score - a.score);
      buckets.push({ leads, label: MONTHS[dt.getMonth()], isLast: i === 0 });
    }
  } else { // day — last 28 days
    for (let i = 27; i >= 0; i--) {
      const dt = new Date(now); dt.setDate(now.getDate() - i);
      const key = dt.toISOString().split('T')[0];
      const leads = LEADS.filter(l => inDay(l, key)).sort((a, b) => b.score - a.score);
      buckets.push({ leads, label: `${MONTHS[dt.getMonth()]} ${dt.getDate()}`, isLast: i === 0 });
    }
  }
  return buckets;
}

function renderDotChart() {
  const host = $('dot-chart');
  const W = host.clientWidth || 600;
  const H = 240;
  const PAD = { t: 30, r: 12, b: 28, l: 28 };
  const chartW = W - PAD.l - PAD.r;
  const chartH = H - PAD.t - PAD.b;

  // Build time buckets for the current chart mode (day / week / month)
  const days = buildChartBuckets(chartMode);

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

  // X-axis labels — adaptive density: ~7 evenly-spaced labels max, always show
  // the last one, and skip any that would collide with it. Prevents overlap in
  // every mode (28 days / 12 weeks / 6 months).
  const lastWord = { day: 'Today', week: 'This wk', month: 'This mo' }[chartMode];
  const lastIdx  = days.length - 1;
  const step     = Math.max(1, Math.ceil(days.length / 7));
  days.forEach((d, idx) => {
    const isLast = idx === lastIdx;
    if (!isLast && (idx % step !== 0 || lastIdx - idx < step)) return;
    const x = PAD.l + idx * slot + slot / 2;
    const cls = idx === focusIdx ? 'dc-x-lbl active' : 'dc-x-lbl';
    const text = isLast ? lastWord : d.label;
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

/* Shared lead sort (used by both the Leads grid and the Overview table) */
let leadsSort = 'score';
const SORTERS = {
  score:  (a, b) => b.score - a.score,
  newest: (a, b) => (b.created_at || '').localeCompare(a.created_at || ''),
  name:   (a, b) => (a.name || '').localeCompare(b.name || ''),
};
const SORT_ORDER = ['score', 'newest', 'name'];
const SORT_LABEL = { score: 'highest score', newest: 'newest first', name: 'name A–Z' };

function cycleLeadSort() {
  const i = SORT_ORDER.indexOf(leadsSort);
  leadsSort = SORT_ORDER[(i + 1) % SORT_ORDER.length];
  renderLeadGrid();
  renderOverviewTable();
  toast(`Sorted by ${SORT_LABEL[leadsSort]}`);
}

/* Platform glyphs — identical to the channel badges beside the ARIA logo (top-left). */
const PF_GLYPH = {
  fb: 'f',
  ig: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="3.5"/><circle cx="17.5" cy="6.5" r="1" fill="#fff"/></svg>',
  wa: '<svg viewBox="0 0 24 24" fill="#fff"><path d="M12 2a10 10 0 0 0-8.5 15.2L2 22l4.9-1.3A10 10 0 1 0 12 2zm5.4 14.1c-.2.6-1.3 1.2-1.8 1.3-.5.1-1 .1-1.7-.1-.4-.1-.9-.3-1.6-.6-2.8-1.2-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9 0-1.3.7-2 1-2.3.2-.2.5-.3.7-.3h.5c.2 0 .5-.1.7.5l1 2.3c.1.2.1.4 0 .6l-.3.4-.4.5c-.1.1-.3.3-.1.6.2.4 1 1.6 2.1 2.6 1.4 1.2 2.6 1.6 2.9 1.8.4.2.6.1.8-.1l.9-1.1c.2-.3.5-.2.8-.1l2.2 1c.3.2.5.2.6.4 0 .2 0 1-.2 1.5z"/></svg>',
};
function pfKey(channel) {
  const c = (channel || '').toLowerCase();
  return (c === 'ig' || c === 'instagram') ? 'ig'
       : (c === 'wa' || c === 'whatsapp')  ? 'wa' : 'fb';
}
/** Inline platform badge (colored circle + white glyph), matching the top-left icons. */
function pfBadge(channel, extraClass = '') {
  const k = pfKey(channel);
  return `<span class="pf-badge pf-${k} ${extraClass}">${PF_GLYPH[k]}</span>`;
}
/** Corner pip on an avatar — same platform glyph, pip-sized. */
function pfPip(channel) {
  const k = pfKey(channel);
  return `<span class="pf-mini ${k}">${PF_GLYPH[k]}</span>`;
}

function renderLeadGrid() {
  const cards = LEADS
    .filter(l => !leadsQ || l.quality === leadsQ)
    .sort(SORTERS[leadsSort])
    .slice(0, 18);

  if (!cards.length) {
    $('lead-grid').innerHTML = `
      <div style="grid-column:1/-1;padding:48px;text-align:center;color:var(--ink-4);font-size:13px">
        ${leadsQ ? `No ${leadsQ} leads right now.` : 'No leads yet. New leads from Facebook/Instagram will appear here.'}
      </div>`;
    return;
  }

  $('lead-grid').innerHTML = cards.map(l => {
    const ownerPill = l.owner_name
      ? `<div class="lc-owner" title="Owner: ${esc(l.owner_name)}"><div class="lc-owner-av"><img src="${avatarUrl(l.owner_name)}" alt=""></div>${esc(l.owner_name)}</div>`
      : `<div class="lc-owner" style="color:var(--ink-4)" title="Unassigned">· unassigned</div>`;
    return `
      <div class="lead-card" data-lead-id="${l.id}" role="button" tabindex="0" title="View ${esc(l.name)}'s details">
        <span class="lc-quality-dot lc-q-${l.quality}"></span>
        ${ownerPill}
        <div class="lc-avatar">
          <img src="${l.avatar}" alt="">
          ${pfPip(l.channel)}
        </div>
        <div class="lc-name">${esc(l.name)}</div>
        <div class="lc-role">${esc(l.role)} · ${esc(l.company)}</div>
        <div class="lc-grid">
          <div class="lc-stat">
            <span class="lc-stat-lbl">From</span>
            <span class="lc-stat-val">${pfBadge(l.channel, 'pf-badge--xs')}${l.channel === 'instagram' ? 'Instagram' : 'Facebook'}</span>
          </div>
          <div class="lc-stat">
            <span class="lc-stat-lbl">Score</span>
            <span class="lc-stat-val">${l.score}</span>
          </div>
          <div class="lc-stat">
            <span class="lc-stat-lbl">Sector</span>
            <span class="lc-stat-val">${TYPE_LBL[l.lead_type] || l.lead_type}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');

  $$('#lead-grid .lead-card').forEach(el => {
    el.addEventListener('click', () => openLeadDetail(+el.dataset.leadId));
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLeadDetail(+el.dataset.leadId); }
    });
  });
}

/* ══════════════════════ LEAD DETAIL ══════════════════════ */
async function openLeadDetail(id) {
  const overlay = $('leaddetail-overlay');
  const body    = $('leaddetail-body');
  if (!overlay || !body) return;
  body.innerHTML = `<p class="modal-sub">Loading…</p>`;
  overlay.hidden = false;
  try {
    const res  = await fetch(`/leads/${id}`);
    const data = await res.json();
    if (data.error) { body.innerHTML = `<p class="modal-sub">${esc(data.error)}</p>`; return; }
    renderLeadDetail(data);
  } catch (_) {
    body.innerHTML = `<p class="modal-sub">Couldn't load this lead. Is the server running?</p>`;
  }
}

function closeLeadDetail() { const o = $('leaddetail-overlay'); if (o) o.hidden = true; }

function renderLeadDetail(data) {
  const l = data.lead || {};
  const src = (l.source || '').toLowerCase();
  const srcName = (src === 'ig' || src === 'instagram') ? 'Instagram'
                : (src === 'fb' || src === 'facebook') ? 'Facebook'
                : (l.source || 'Unknown');
  const dotCh = srcName === 'Instagram' ? 'instagram' : 'facebook';
  const fmtDT = iso => iso ? new Date(iso).toLocaleString('en-IN', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
  const yn = v => v === true ? 'Yes' : v === false ? 'No' : '—';
  const row = (k, v) => `<div class="ld-row"><span class="ld-k">${k}</span><span class="ld-v">${v}</span></div>`;

  // Owner section — reassignable for managers/admin, read-only otherwise.
  const canAssign = CURRENT_USER && CURRENT_USER.role !== 'employee' && ASSIGNABLE_OWNERS.length;
  const ownerSectionHtml = canAssign
    ? `<div class="ld-section">
         <div class="ld-section-title">Owner</div>
         <select class="ld-stage-select" id="ld-owner">
           ${ASSIGNABLE_OWNERS.map(o => `<option value="${o.id}" ${l.owner_id === o.id ? 'selected' : ''}>${esc(o.name)}</option>`).join('')}
         </select>
         <div class="ld-score-note">The employee who owns this lead. Reassign to balance the team.</div>
       </div>`
    : (l.owner_name
        ? `<div class="ld-section"><div class="ld-section-title">Owner</div>${row('Brought by', esc(l.owner_name))}</div>`
        : '');

  const bd = l.score_breakdown || {};
  const bar = (label, val, max, tint) => {
    const pct  = Math.max(0, Math.min(100, Math.round((Math.max(0, val) / max) * 100)));
    const sign = val < 0 ? '−' : '';
    return `<div class="ld-bar-row">
      <span class="ld-bar-lbl">${label}</span>
      <span class="ld-bar-track"><span class="ld-bar-fill" style="width:${pct}%;background:${tint}"></span></span>
      <span class="ld-bar-val">${sign}${Math.abs(val)}<small>/${max}</small></span>
    </div>`;
  };

  const interactions = data.interactions || [];
  const lastMsgs = interactions.slice(-4).map(i => {
    const who  = i.direction === 'inbound' ? 'Lead' : (i.handled_by === 'human' ? 'Team' : 'ARIA');
    const full = i.message || '';
    return `<div class="ld-msg"><b>${who}:</b> ${esc(full.replace(/\n+/g,' ').slice(0,90))}${full.length>90?'…':''}</div>`;
  }).join('') || `<div class="ld-msg" style="color:var(--ink-4)">No messages yet — the first-touch email is queued for approval.</div>`;

  $('leaddetail-body').innerHTML = `
    <div class="ld-head">
      <div class="ld-name">${esc(l.name || 'Unknown')}</div>
      <span class="ld-badge ld-q-${l.quality}">${esc(l.quality || '')} · ${l.score ?? 0}</span>
    </div>
    <div class="ld-sub">${esc(l.type || '—')} · ${esc(l.company || '—')}</div>

    <div class="ld-section">
      <div class="ld-section-title">Pipeline stage</div>
      <select class="ld-stage-select" id="ld-stage">
        ${STAGES.map(([k, lbl]) => `<option value="${k}" ${l.stage === k ? 'selected' : ''}>${lbl}</option>`).join('')}
      </select>
      <div class="ld-score-note">ARIA sets the early stages automatically. Move it forward (Negotiation → Won) as your team progresses the deal.</div>
    </div>

    ${ownerSectionHtml}

    <div class="ld-section">
      <div class="ld-section-title">Where they came from</div>
      ${row('Source', `${pfBadge(dotCh, 'pf-badge--xs')} ${esc(srcName)} lead ad`)}
      ${row('Location', esc(l.state || '—'))}
      ${row('Arrived', fmtDT(l.created_at))}
    </div>

    <div class="ld-section">
      <div class="ld-section-title">Contact</div>
      ${row('Email', esc(l.email || '—'))}
      ${row('Phone', esc(l.phone || '—'))}
    </div>

    <div class="ld-section">
      <div class="ld-section-title">Profile</div>
      ${row('Team size', l.team_size ?? '—')}
      ${row('Uses software', yn(l.uses_software) + (l.current_software ? ` (${esc(l.current_software)})` : ''))}
      ${row('Open to new platform', yn(l.open_to_platform))}
      ${row('Website', esc(l.company_website || '—'))}
      ${row('Wants demo', yn(l.willing_for_demo) + (l.demo_preference ? ` — ${esc(l.demo_preference)}` : ''))}
    </div>

    <div class="ld-section">
      <div class="ld-section-title">Why this score?</div>
      ${bar('Profile · type, team, software', bd.profile ?? 0, bd.profile_max ?? 40, '#6c5ce7')}
      ${bar('Form intent · from the ad form', bd.form_intent ?? 0, bd.form_intent_max ?? 30, '#00b894')}
      ${bar('Engagement · from chat', bd.engagement ?? 0, bd.engagement_max ?? 30, '#fdcb6e')}
      <div class="ld-score-note">Profile &amp; form intent come straight from the lead's ad-form answers (so a lead has a score before any email or chat). Engagement moves as they interact.</div>
    </div>

    <div class="ld-section">
      <div class="ld-section-title">Recent activity</div>
      ${lastMsgs}
    </div>
  `;

  const sel = $('ld-stage');
  if (sel) sel.addEventListener('change', () => setLeadStage(l.id, sel.value, l.name || 'Lead'));

  const osel = $('ld-owner');
  if (osel) osel.addEventListener('change', () => reassignOwner(l.id, +osel.value));
}

async function reassignOwner(id, ownerId) {
  try {
    const r = await fetch(`/leads/${id}/owner`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ owner_id: ownerId }),
    });
    if (!r.ok) throw new Error();
    const d = await r.json();
    const L = LEADS.find(x => x.id === id);
    if (L) { L.owner_id = d.owner_id; L.owner_name = d.owner_name; }
    toast(`Reassigned to ${d.owner_name}`);
    await loadLiveData();
    renderAll();
  } catch { toast('Could not reassign this lead', true); }
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
let convFilter = 'all';       // 'all' | 'aria' | 'team'
let convPlatform = 'all';     // 'all' | 'facebook' | 'instagram'

function filteredConvs() {
  let list = CONVERSATIONS;
  if (convFilter === 'aria') list = list.filter(c => !c.escalated);
  else if (convFilter === 'team') list = list.filter(c => c.escalated);
  if (convPlatform !== 'all') list = list.filter(c => c.lead.channel === convPlatform);
  return list;
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
          ${pfPip(c.lead.channel)}
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

  // Platform dropdown — real menu (All / Facebook / Instagram)
  $('conv-platform-btn')?.addEventListener('click', e => {
    e.stopPropagation();
    togglePopover('conv-platform-menu');
  });
  $$('#conv-platform-menu .menu-item').forEach(mi => {
    mi.addEventListener('click', () => {
      convPlatform = mi.dataset.plat;
      $('conv-platform-btn').childNodes[0].nodeValue = mi.textContent + ' ';
      closeAllPopovers();
      renderConvList();
    });
  });
}

/** Toggle a lead's human-priority flag via the API (used from the Inbox header) */
async function togglePriority(c) {
  try {
    const r = await fetch(`/leads/${c.lead_id}/priority`, { method: 'POST' });
    if (!r.ok) throw new Error();
    const d = await r.json();
    c.lead.human_priority = d.human_priority;
    renderConvThread();
    toast(d.message || (d.human_priority ? 'Flagged as priority' : 'Priority cleared'));
  } catch { toast('Could not update priority', true); }
}

/** Next weekday (skips Sat/Sun), used as the default suggested slot. */
function nextBusinessDay() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
  return d;
}

/** Google Calendar "create event" link, pre-filled with the lead + their preferred time. */
function buildCalendarUrl(c) {
  const pad = n => String(n).padStart(2, '0');
  const day = nextBusinessDay();
  const ymd = `${day.getFullYear()}${pad(day.getMonth() + 1)}${pad(day.getDate())}`;
  const dates = `${ymd}T110000/${ymd}T113000`;  // default 11:00–11:30 IST; team adjusts
  const pref = c.lead.demo_preference;
  const details =
    `Product demo for ${c.lead.name}.` +
    (pref ? `\n\nLead's preferred time: ${pref} — adjust the slot to match.` : '') +
    `\n\nClick "Add Google Meet video conferencing", then send the invite.`;
  const p = new URLSearchParams({
    action: 'TEMPLATE',
    text:   `BeyondSure Demo — ${c.lead.name}`,
    dates,
    ctz:    'Asia/Kolkata',
    details,
  });
  if (c.lead.email) p.set('add', c.lead.email);  // invites the lead
  return 'https://calendar.google.com/calendar/render?' + p.toString();
}

async function startMeet(c) {
  // Already scheduled → rejoin the saved Meet directly.
  if (c.lead.meet_link) { window.open(c.lead.meet_link, '_blank', 'noopener'); return; }

  // Not scheduled yet → open a pre-filled Google Calendar invite (lead + their
  // preferred time). The team sets the slot, adds Google Meet, and sends it.
  window.open(buildCalendarUrl(c), '_blank', 'noopener');
  const link = prompt(
    `A Google Calendar invite opened, pre-filled for ${c.lead.name}` +
    (c.lead.demo_preference ? ` (prefers: ${c.lead.demo_preference})` : '') + `.\n\n` +
    `Set the time, click "Add Google Meet", and send it — then paste the Meet ` +
    `link here to save it for rejoining (leave blank to skip):`
  );
  if (!link) return;
  const url = link.trim();
  if (!/^https?:\/\//.test(url)) { toast("That doesn't look like a link — not saved", true); return; }
  try {
    const r = await fetch(`/leads/${c.lead_id}/meet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ link: url }),
    });
    if (!r.ok) throw new Error();
    const d = await r.json();
    c.lead.meet_link = d.meet_link;
    const L = LEADS.find(x => x.id === c.lead_id); if (L) L.meet_link = d.meet_link;  // keep master copy in sync
    renderConvThread();
    toast(`Meeting saved for ${c.lead.name}`);
  } catch { toast('Could not save the meeting link', true); }
}

function renderConvThread() {
  const c = CONVERSATIONS[activeConv];
  if (!c) return;

  const phone = c.lead.phone;
  const starred = !!c.lead.human_priority;
  $('conv-head').innerHTML = `
    <div class="ch-avatar"><img src="${c.lead.avatar}" alt=""></div>
    <div>
      <div class="ch-name">${esc(c.lead.name)}</div>
      <div class="ch-meta">${esc(c.lead.city)} · Local time ${new Date().toLocaleTimeString('en-IN',{hour:'numeric',minute:'2-digit'})}</div>
    </div>
    <div class="ch-tools">
      <button class="icon-btn sm" id="ch-call" title="${phone ? 'Call ' + esc(phone) : 'No phone on file'}" ${phone ? '' : 'disabled'}>${ICONS.phone}</button>
      <button class="icon-btn sm ${c.lead.meet_link ? 'has-meet' : ''}" id="ch-meet" title="${c.lead.meet_link ? 'Join scheduled Google Meet' : 'Schedule a Google Meet'}">${ICONS.video}</button>
      <button class="icon-btn sm ${starred ? 'starred' : ''}" id="ch-star" title="${starred ? 'Priority — click to clear' : 'Flag as priority'}">${ICONS.star}</button>
    </div>
  `;
  if (phone) $('ch-call')?.addEventListener('click', () => { window.location.href = 'tel:' + phone; });
  $('ch-meet')?.addEventListener('click', () => startMeet(c));
  $('ch-star')?.addEventListener('click', () => togglePriority(c));

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
let draftFilter = '';   // '' | 'pricing' | 'demo' | 'objection'

function renderApprovalStats() {
  const s = APPROVAL.stats || {};
  if ($('ap-pending'))  $('ap-pending').textContent  = s.pending ?? PENDING_DRAFTS.length;
  if ($('ap-approved')) $('ap-approved').textContent = s.approved_today ?? 0;
  if ($('ap-rejected')) $('ap-rejected').textContent = s.rejected ?? 0;
  if ($('ap-sent'))     $('ap-sent').textContent     = s.sent_total ?? 0;
}

function renderActivity() {
  const host = $('activity-list');
  if (!host) return;
  const acts = APPROVAL.activity || [];
  const TONE = { green: 'ad-green', purple: 'ad-purple', red: 'ad-red' };
  if (!acts.length) {
    host.innerHTML = `<li style="padding:24px;text-align:center;color:var(--ink-4);font-size:13px;list-style:none">No activity yet — approve a draft to see it here.</li>`;
    return;
  }
  host.innerHTML = acts.map(a => `
    <li>
      <span class="act-dot ${TONE[a.tone] || 'ad-green'}"></span>
      <div>
        <div class="act-title">${esc(a.action)}</div>
        <div class="act-desc">${esc(a.summary || '')} <span style="color:var(--ink-4)">· ${esc(a.lead_name)}</span></div>
      </div>
      <span class="act-time">${esc(a.time)}</span>
    </li>`).join('');
}

function renderDrafts() {
  renderApprovalStats();

  const filtered = draftFilter
    ? PENDING_DRAFTS.filter(d => (d.intent || '').includes(draftFilter))
    : PENDING_DRAFTS;

  if (!filtered.length) {
    const msg = PENDING_DRAFTS.length
      ? `No ${draftFilter} drafts right now.`
      : 'No drafts waiting for review';
    $('draft-list').innerHTML = `
      <div style="padding:48px;text-align:center;color:var(--ink-4)">
        <div style="font-size:32px;margin-bottom:8px">✓</div>
        <div style="font-weight:600;color:var(--ink-2)">All clear</div>
        <div style="font-size:13px;margin-top:4px">${msg}</div>
      </div>`;
    return;
  }

  $('draft-list').innerHTML = filtered.map(d => {
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

/* ── Wire Approvals controls ── */
function wireApprovals() {
  $$('#draft-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      $$('#draft-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      draftFilter = tab.dataset.intent || '';
      renderDrafts();
    });
  });

  $('review-hot-btn')?.addEventListener('click', () => {
    // Sort pending drafts by the lead's score (hottest first)
    PENDING_DRAFTS.sort((a, b) => (b._lead_score || 0) - (a._lead_score || 0));
    draftFilter = '';
    $$('#draft-tabs .tab').forEach((t, i) => t.classList.toggle('active', i === 0));
    switchView('approvals');
    renderDrafts();
    toast('Drafts sorted — hottest leads first');
  });
}

/* ── Overview chart controls + CSV export ── */
function exportLeadsCSV() {
  if (!LEADS.length) { toast('No leads to export', true); return; }
  const cols = ['id', 'name', 'company', 'city', 'lead_type', 'quality', 'score', 'status', 'handle'];
  const head = ['ID', 'Name', 'Company', 'State', 'Type', 'Quality', 'Score', 'Status', 'Email'];
  const q = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const rows = LEADS.map(l => cols.map(c => q(l[c])).join(','));
  const csv = [head.join(','), ...rows].join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aria-leads-${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  toast(`Exported ${LEADS.length} lead${LEADS.length !== 1 ? 's' : ''} to CSV`);
}

function wireOverviewChart() {
  $$('#chart-controls .seg-btn').forEach(b => b.addEventListener('click', () => {
    $$('#chart-controls .seg-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    chartMode = b.dataset.mode;
    renderDotChart();
  }));
  $('chart-export-btn')?.addEventListener('click', exportLeadsCSV);
  $('run-analysis-btn')?.addEventListener('click', () => switchView('analytics'));
}

/* ══════════════════════ ANALYTICS VIEW ══════════════════════ */
function renderAnaKpis() {
  const total = LEADS.length;
  const denom = total || 1;
  const pipeline = LEADS.reduce((s, l) => s + (l.pipeline || 0), 0);
  const hot   = LEADS.filter(l => l.quality === 'hot').length;
  const demo  = LEADS.filter(l => l.willing_for_demo).length;
  const avg   = Math.round(LEADS.reduce((s, l) => s + (l.score || 0), 0) / denom);
  if ($('ana-pipeline')) $('ana-pipeline').textContent = pipeline ? fmtMoney(pipeline) : '₹0';
  if ($('ana-hotpct'))   $('ana-hotpct').textContent   = `${Math.round(hot / denom * 100)}%`;
  if ($('ana-demopct'))  $('ana-demopct').textContent  = `${Math.round(demo / denom * 100)}%`;
  if ($('ana-avgscore')) $('ana-avgscore').textContent = total ? avg : '—';
}

function renderInsights() {
  const host = $('insight-list');
  if (!host) return;
  const total = LEADS.length;
  const TONES = [
    { bg: '#fef3c7', fg: '#b45309', icon: ICONS.flame },
    { bg: '#dcfce7', fg: '#16a34a', icon: ICONS.check },
    { bg: '#ede9fe', fg: '#6d28d9', icon: ICONS.inbox },
    { bg: '#fce7f3', fg: '#be185d', icon: ICONS.sparkle },
  ];

  if (!total) {
    host.innerHTML = `<li style="padding:24px;text-align:center;color:var(--ink-4);font-size:13px;list-style:none">Insights appear once leads arrive.</li>`;
    if ($('insight-count')) $('insight-count').textContent = '0';
    return;
  }

  const ins = [];
  const fb = LEADS.filter(l => l.channel === 'facebook').length;
  const ig = LEADS.filter(l => l.channel === 'instagram').length;
  if (fb || ig) {
    const top = fb >= ig ? 'Facebook' : 'Instagram';
    ins.push({ title: `${top} brings most of your leads`, sub: `${fb} from Facebook · ${ig} from Instagram` });
  }
  const hot = LEADS.filter(l => l.quality === 'hot').length;
  ins.push({
    title: `${Math.round(hot / total * 100)}% of your leads are hot`,
    sub: hot ? `${hot} ready for priority outreach` : 'Qualify warm leads to grow this',
  });
  if (PENDING_DRAFTS.length) ins.push({
    title: `${PENDING_DRAFTS.length} draft${PENDING_DRAFTS.length > 1 ? 's' : ''} awaiting approval`,
    sub: 'Clear the queue to keep response time low',
  });
  const demo = LEADS.filter(l => l.willing_for_demo).length;
  if (demo) ins.push({ title: `${demo} lead${demo > 1 ? 's' : ''} want a demo`, sub: 'Confirm time slots to move them forward' });

  const shown = ins.slice(0, 4);
  if ($('insight-count')) $('insight-count').textContent = `${shown.length} live`;
  host.innerHTML = shown.map((it, i) => {
    const t = TONES[i % TONES.length];
    return `<li>
      <div class="ins-icon" style="background:${t.bg};color:${t.fg}">${t.icon}</div>
      <div><div class="ins-title">${esc(it.title)}</div><div class="ins-sub">${esc(it.sub)}</div></div>
    </li>`;
  }).join('');
}

/* ══════════════════════ LEAD STAGES ══════════════════════ */
const STAGES = [
  ['new', 'New Lead'], ['contacted', 'Contacted'], ['interested', 'Interested'],
  ['follow_up', 'Follow-up'], ['negotiation', 'Negotiation'], ['post_demo', 'Post Demo Follow-Up'],
  ['post_commercial', 'Post Commercial Follow-Up'], ['parked', 'Parked'], ['won', 'Won'], ['lost', 'Lost'],
];
const STAGE_LBL = Object.fromEntries(STAGES);
const STAGE_TINT = {
  new:'#eef2ff', contacted:'#e0e7ff', interested:'#ede9fe', follow_up:'#fef9c3',
  negotiation:'#ffe4e6', post_demo:'#dbeafe', post_commercial:'#dcfce7',
  parked:'#f1f5f9', won:'#d1fae5', lost:'#fee2e2',
};
const STAGE_FG = {
  new:'#4338ca', contacted:'#4338ca', interested:'#6d28d9', follow_up:'#a16207',
  negotiation:'#be123c', post_demo:'#1d4ed8', post_commercial:'#15803d',
  parked:'#475569', won:'#047857', lost:'#b91c1c',
};

function renderStages() {
  const host = $('lead-stages');
  if (!host) return;
  const stages = (ANALYTICS.stages && ANALYTICS.stages.length) ? ANALYTICS.stages : [];
  host.innerHTML = stages.map(s => `
    <div class="stage-card">
      <span class="stage-chip" style="background:${STAGE_TINT[s.key] || '#f1f5f9'};color:${STAGE_FG[s.key] || '#475569'}">${esc(s.label)}</span>
      <span class="stage-num">${s.count}</span>
      <span class="stage-sub">leads</span>
    </div>`).join('');
}

async function setLeadStage(id, stage, name) {
  try {
    const r = await fetch(`/leads/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: stage }),
    });
    if (!r.ok) throw new Error();
    const L = LEADS.find(x => x.id === id); if (L) L.stage = stage;
    const c = CONVERSATIONS.find(x => x.lead_id === id); if (c && c.lead) c.lead.stage = stage;
    toast(`${name} → ${STAGE_LBL[stage] || stage}`);
    // refresh stage counts + grids from the server
    await loadLiveData();
    renderAll();
  } catch { toast('Could not update stage', true); }
}

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
  if ($('avatar-menu-img'))  $('avatar-menu-img').src = ME.avatar;
  if ($('avatar-menu-name')) $('avatar-menu-name').textContent = ME.name;
  if ($('avatar-menu-role')) $('avatar-menu-role').textContent = ME.email || 'BeyondSure team';
}

/* ══════════════════════ PHASE 1: TOPBAR ══════════════════════ */

let CONFIG = null;          // cached /admin/config
let notifsRead = false;     // whether the user dismissed the notification dot

/** Fetch non-sensitive backend config (once, cached) */
async function loadConfig() {
  if (window.location.protocol === 'file:') return null;
  try {
    const r = await fetch('/admin/config');
    if (r.ok) CONFIG = await r.json();
  } catch (_) {}
  return CONFIG;
}

/* ── Generic popover open/close ── */
function closeAllPopovers(except) {
  ['notif-panel', 'avatar-menu', 'channel-popover', 'conv-platform-menu'].forEach(id => {
    if (id !== except) { const el = $(id); if (el) el.hidden = true; }
  });
}
function togglePopover(id) {
  const el = $(id);
  if (!el) return;
  const willOpen = el.hidden;
  closeAllPopovers(willOpen ? id : null);
  el.hidden = !willOpen;
}

/* ── Notifications ── */
function buildNotifications() {
  const items = [];
  const escalated = LEADS.filter(l => l.status === 'escalated' || l.status === 'needs_human');
  const hot       = LEADS.filter(l => l.quality === 'hot');
  const demos     = LEADS.filter(l => l.willing_for_demo
    && !['converted','demo_done'].includes(l.status));

  escalated.forEach(l => items.push({
    icon: '🙋', bg: '#fce7f3',
    title: `${l.name} asked to talk to your team`,
    meta: 'Open the conversation in Inbox',
    action: () => openConversationByLead(l.id),
  }));
  hot.forEach(l => items.push({
    icon: '🔥', bg: '#fef3c7',
    title: `${l.name} is hot — score ${l.score}`,
    meta: `${TYPE_LBL[l.lead_type] || l.lead_type} · ${l.company}`,
    action: () => openConversationByLead(l.id),
  }));
  if (PENDING_DRAFTS.length) items.push({
    icon: '📝', bg: '#ede9fe',
    title: `${PENDING_DRAFTS.length} draft${PENDING_DRAFTS.length > 1 ? 's' : ''} awaiting approval`,
    meta: 'Review before they go out',
    action: () => switchView('approvals'),
  });
  demos.forEach(l => items.push({
    icon: '📅', bg: '#dcfce7',
    title: `${l.name} wants a demo`,
    meta: 'Confirm a time slot',
    action: () => openConversationByLead(l.id),
  }));
  return items;
}

function renderNotifications() {
  const items = buildNotifications();
  const list = $('notif-list');
  const dot  = $('notif-dot');
  if (dot) dot.hidden = !(items.length && !notifsRead);

  if (!list) return;
  if (!items.length) {
    list.innerHTML = `<li class="notif-empty">You're all caught up 🎉<br>No actions need your attention.</li>`;
    return;
  }
  list.innerHTML = items.map((it, i) => `
    <li class="notif-item" data-ni="${i}">
      <div class="notif-ico" style="background:${it.bg}">${it.icon}</div>
      <div class="notif-body">
        <div class="notif-title">${esc(it.title)}</div>
        <div class="notif-meta">${esc(it.meta)}</div>
      </div>
    </li>`).join('');
  $$('#notif-list .notif-item').forEach(el => {
    el.addEventListener('click', () => {
      items[+el.dataset.ni].action();
      closeAllPopovers();
    });
  });
}

/* ── Channels popover ── */
function renderChannelPopover() {
  const host = $('channel-list');
  if (!host || !CONFIG) return;
  const ch = CONFIG.channels;
  const order = ['facebook', 'instagram', 'whatsapp', 'email'];
  host.innerHTML = order.map(k => {
    const c = ch[k]; if (!c) return '';
    const on = c.connected;
    return `<div class="chan-row">
      <span class="chan-dot ${on ? 'on' : 'off'}"></span>
      <span class="chan-name">${esc(c.label)}</span>
      <span class="chan-status ${on ? 'on' : 'off'}">${on ? 'Connected' : 'Not set'}</span>
    </div>`;
  }).join('');
}

/* ── Global lead search ── */
function openSearch() {
  const ov = $('search-overlay');
  if (!ov) return;
  ov.hidden = false;
  const inp = $('search-input');
  inp.value = '';
  renderSearchResults('');
  setTimeout(() => inp.focus(), 30);
}
function closeSearch() { const ov = $('search-overlay'); if (ov) ov.hidden = true; }

function renderSearchResults(q) {
  const host = $('search-results');
  if (!host) return;
  const query = q.trim().toLowerCase();
  let matches = LEADS;
  if (query) {
    matches = LEADS.filter(l =>
      (l.name || '').toLowerCase().includes(query) ||
      (l.company || '').toLowerCase().includes(query) ||
      (l.handle || '').toLowerCase().includes(query));
  }
  matches = matches.slice(0, 8);

  if (!matches.length) {
    host.innerHTML = `<li class="search-empty">${query ? 'No leads match.' : 'Start typing to search your leads.'}</li>`;
    return;
  }
  host.innerHTML = matches.map(l => `
    <li class="search-result" data-lead="${l.id}">
      <img src="${l.avatar}" alt="">
      <div class="sr-body">
        <div class="sr-name">${esc(l.name)}</div>
        <div class="sr-meta">${esc(l.company)} · ${TYPE_LBL[l.lead_type] || l.lead_type} · ${esc(l.city)}</div>
      </div>
      <span class="sr-score" style="background:${Q_COLOR[l.quality]}22;color:${Q_COLOR[l.quality]}">${l.score}</span>
    </li>`).join('');
  $$('#search-results .search-result').forEach(el => {
    el.addEventListener('click', () => {
      openConversationByLead(+el.dataset.lead);
      closeSearch();
    });
  });
}

/** Jump to a lead's conversation in the Inbox */
function openConversationByLead(leadId) {
  switchView('inbox');
  const idx = CONVERSATIONS.findIndex(c => c.lead_id === leadId);
  if (idx >= 0) {
    activeConv = idx;
    renderConvList();
    renderConvThread();
  }
}

/* ── Wire all topbar controls ── */
function wireTopbar() {
  $('notif-btn')?.addEventListener('click', e => {
    e.stopPropagation();
    notifsRead = true;
    renderNotifications();
    togglePopover('notif-panel');
  });
  $('notif-clear')?.addEventListener('click', e => {
    e.stopPropagation();
    notifsRead = true;
    renderNotifications();
  });
  $('avatar-btn')?.addEventListener('click', e => { e.stopPropagation(); togglePopover('avatar-menu'); });
  $('channel-add-btn')?.addEventListener('click', e => {
    e.stopPropagation();
    renderChannelPopover();
    togglePopover('channel-popover');
  });
  $('channel-settings-link')?.addEventListener('click', () => { closeAllPopovers(); openSettings('channels'); });

  // Avatar menu actions
  $$('#avatar-menu .menu-item').forEach(mi => {
    mi.addEventListener('click', () => {
      const a = mi.dataset.action;
      closeAllPopovers();
      if (a === 'settings') openSettings('knowledge');
      else if (a === 'kb')  window.open('/admin/kb', '_blank');
      else if (a === 'docs') openSettings('docs');
      else if (a === 'signout') { fetch('/auth/logout', { method: 'POST' }).finally(() => location.reload()); }
    });
  });

  // Settings button
  $('settings-btn')?.addEventListener('click', () => openSettings('knowledge'));

  // Search
  $('search-btn')?.addEventListener('click', openSearch);
  $('search-input')?.addEventListener('input', e => renderSearchResults(e.target.value));
  $('search-overlay')?.addEventListener('click', e => { if (e.target.id === 'search-overlay') closeSearch(); });

  // Global keyboard: Ctrl/Cmd+K opens search, Esc closes overlays
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openSearch(); }
    if (e.key === 'Escape') { closeSearch(); closeAllPopovers(); closeAddLead(); }
  });

  // Click-away closes popovers
  document.addEventListener('click', e => {
    if (!e.target.closest('.popover-anchor')) closeAllPopovers();
  });

  // Settings sub-nav tabs
  $$('#settings-nav .set-tab').forEach(tab => {
    tab.addEventListener('click', () => showSettingsSection(tab.dataset.sec));
  });
}

/* ══════════════════════ SETTINGS PAGE ══════════════════════ */
function openSettings(section) {
  switchView('settings');
  if (section) showSettingsSection(section);
  renderSettings();
}

function showSettingsSection(sec) {
  $$('#settings-nav .set-tab').forEach(t => t.classList.toggle('active', t.dataset.sec === sec));
  $$('.set-section').forEach(s => s.classList.toggle('active', s.id === `set-${sec}`));
}

async function renderSettings() {
  if (!CONFIG) await loadConfig();

  // Knowledge Base
  if (CONFIG?.knowledge_base) {
    const kb = CONFIG.knowledge_base;
    const stats = $('kb-stats');
    if (stats) stats.innerHTML = [
      ['Total', kb.total], ['Answered', kb.answered],
      ['Placeholders', kb.placeholders], ['Active', kb.active],
    ].map(([l, v]) => `<div class="kb-stat"><div class="kb-stat-val">${v}</div><div class="kb-stat-lbl">${l}</div></div>`).join('');
    const pct = kb.total ? Math.round((kb.answered / kb.total) * 100) : 0;
    if ($('kb-progress-fill')) $('kb-progress-fill').style.width = pct + '%';
    if ($('kb-progress-lbl'))  $('kb-progress-lbl').textContent = `${pct}% answered · ${kb.placeholders} placeholder${kb.placeholders !== 1 ? 's' : ''} left`;
  }

  // Channels
  if (CONFIG?.channels) {
    const ICO = {
      facebook:  { bg: '#1877f2', t: 'f' },
      instagram: { bg: 'linear-gradient(135deg,#f09433,#dc2743,#bc1888)', t: '◉' },
      whatsapp:  { bg: '#25d366', t: '✆' },
      email:     { bg: '#6c5ce7', t: '✉' },
    };
    $('channel-grid').innerHTML = ['facebook','instagram','whatsapp','email'].map(k => {
      const c = CONFIG.channels[k]; if (!c) return '';
      const ic = ICO[k];
      return `<div class="chan-card">
        <div class="chan-card-ico" style="background:${ic.bg}">${ic.t}</div>
        <div class="chan-card-body">
          <div class="chan-card-name">${esc(c.label)}</div>
          <div class="chan-card-note">${esc(c.note)}</div>
        </div>
        <span class="chan-pill ${c.connected ? 'on' : 'off'}">${c.connected ? 'Connected' : 'Pending'}</span>
      </div>`;
    }).join('');
  }

  // ARIA behaviour
  if (CONFIG?.aria) {
    const a = CONFIG.aria;
    const rows = [
      ['Human approval mode', 'Every message waits for a team member to approve before sending.',
        a.human_approval_mode ? `<span class="pill-on">ON</span>` : `<span class="pill-off">OFF</span>`],
      ['LLM provider', 'Which model drafts replies and chat responses.', a.llm_provider],
      ['Base URL', 'Used to build chat links in outbound emails.', a.base_url],
      ['Alert email', 'Where hot-lead dossiers are sent.', CONFIG.alerts.alert_email],
      ['WhatsApp alert number', 'Team number for internal hot-lead pings.', CONFIG.alerts.whatsapp_number],
    ];
    $('behavior-list').innerHTML = rows.map(([n, d, v]) => `
      <div class="behavior-row">
        <div class="behavior-info"><div class="behavior-name">${n}</div><div class="behavior-desc">${d}</div></div>
        <div class="behavior-val">${v}</div>
      </div>`).join('');
  }

  // Team
  const tg = $('team-grid');
  if (tg && typeof TEAM === 'object') {
    tg.innerHTML = Object.values(TEAM).map(m => `
      <div class="team-card">
        <img src="${m.avatar}" alt="">
        <div><div class="team-card-name">${esc(m.name)}</div><div class="team-card-role">${esc(m.role)}</div></div>
      </div>`).join('');
  }

  // Docs
  const dg = $('docs-grid');
  if (dg) dg.innerHTML = [
    ['How leads are scored', 'Profile (40) + form intent (30) + engagement (30) = 0–100. Hot ≥70, Warm 40–69, Cold 10–39.'],
    ['The approval queue', 'ARIA drafts every message. Nothing reaches a lead until a team member approves it in the Approvals tab.'],
    ['Chat → human handoff', 'When a lead asks for a person, the chat escalates and the full thread appears in Inbox for you to take over.'],
    ['Follow-ups', 'ARIA auto-nudges quiet leads at 24h, 72h and 7 days, then re-engages "maybe later" leads — all via the approval queue.'],
    ['Knowledge Base', 'ARIA only quotes facts from the KB. Keep pricing and feature answers current in the KB Editor.'],
    ['Compliance scrub', 'Every AI reply is filtered for invented prices, date promises and guarantees before it is shown to you.'],
  ].map(([h, p]) => `<div class="doc-card"><h3>${h}</h3><p>${p}</p></div>`).join('');

  // System
  const sl = $('system-list');
  if (sl && CONFIG?.aria) {
    let sched = '—';
    try { const r = await fetch('/scheduler/status'); if (r.ok) { const s = await r.json(); sched = s.running || s.status ? 'Running' : 'Stopped'; } } catch (_) {}
    const rows = [
      ['Backend', 'running', 'Live'],
      ['Scheduler', 'Follow-up jobs (hourly, IST)', sched],
      ['Version', 'ARIA build', CONFIG.aria.version],
      ['Total leads', 'In the database', String(LEADS.length)],
      ['Pending approvals', 'Drafts awaiting review', String(PENDING_DRAFTS.length)],
    ];
    sl.innerHTML = rows.map(([n, d, v]) => `
      <div class="system-row">
        <div class="behavior-info"><div class="system-name">${n}</div><div class="behavior-desc">${d}</div></div>
        <div class="system-val">${v}</div>
      </div>`).join('');
  }
}

/* ══════════════════════ PHASE 3a: LEADS ACTIONS ══════════════════════ */

let toastTimer = null;
/** Show a transient toast message at the bottom of the screen */
function toast(msg, bad = false) {
  const t = $('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast' + (bad ? ' toast-bad' : '');
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

/* ── Add Lead modal ── */
function openAddLead() {
  const ov = $('addlead-overlay');
  if (!ov) return;
  $('addlead-form').reset();
  $('addlead-error').hidden = true;
  ov.hidden = false;
  setTimeout(() => $('addlead-form').querySelector('input')?.focus(), 30);
}
function closeAddLead() { const ov = $('addlead-overlay'); if (ov) ov.hidden = true; }

async function submitAddLead(e) {
  e.preventDefault();
  const form = $('addlead-form');
  const btn  = $('addlead-submit');
  const err  = $('addlead-error');
  const payload = Object.fromEntries(new FormData(form).entries());

  if (!payload.first_name?.trim() || !payload.email?.trim()) {
    err.textContent = 'Name and email are required.';
    err.hidden = false;
    return;
  }

  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = 'Adding…';
  err.hidden = true;

  try {
    const r = await fetch('/webhook/lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Failed to add lead');

    closeAddLead();
    await loadLiveData();
    leadsQ = ''; overviewQ = '';
    renderAll();
    if (data.duplicate) {
      toast(`${data.first_name || 'Lead'} already exists — record updated`);
    } else {
      toast(`${data.first_name || 'Lead'} added · ${data.lead_quality} (${data.lead_score}) · draft queued`);
    }
  } catch (ex) {
    err.textContent = ex.message || 'Something went wrong.';
    err.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

/* ── Live quick-action cards (Leads aside) ── */
function renderLeadsQuick() {
  const host = $('leads-quick');
  if (!host) return;
  const pending = PENDING_DRAFTS.length;
  const warm    = LEADS.filter(l => l.quality === 'warm').length;
  const team    = LEADS.filter(l => l.status === 'escalated' || l.status === 'needs_human').length;

  const actions = [];
  if (pending) actions.push({
    icon: ICONS.inbox, bg: '#ede9fe', fg: '#6d28d9',
    label: `Review ${pending} pending draft${pending > 1 ? 's' : ''}`,
    sub: 'Approve before they go out', goto: 'approvals',
  });
  if (team) actions.push({
    icon: ICONS.handoff, bg: '#fce7f3', fg: '#be185d',
    label: `${team} conversation${team > 1 ? 's' : ''} need the team`,
    sub: 'Pick up where ARIA left off', goto: 'inbox',
  });
  actions.push({
    icon: ICONS.flame, bg: '#fef3c7', fg: '#b45309',
    label: warm ? `Follow up ${warm} warm lead${warm > 1 ? 's' : ''}` : 'Add your next lead',
    sub: warm ? 'Nudge them toward a demo' : 'Grow the pipeline',
    action: warm ? () => { switchView('leads'); setLeadsTab('warm'); } : openAddLead,
  });

  host.innerHTML = actions.map((a, i) => `
    <button class="qa-real" data-qi="${i}">
      <span class="qa-icon" style="background:${a.bg};color:${a.fg}">${a.icon}</span>
      <span><span class="qa-label">${esc(a.label)}</span><span class="qa-sub">${esc(a.sub)}</span></span>
    </button>`).join('');
  $$('#leads-quick .qa-real').forEach(el => {
    el.addEventListener('click', () => {
      const a = actions[+el.dataset.qi];
      if (a.action) a.action();
      else if (a.goto) switchView(a.goto);
    });
  });
}

/** Programmatically activate a Leads quality tab */
function setLeadsTab(q) {
  leadsQ = q;
  $$('#leads-view-tabs .tab').forEach(t => t.classList.toggle('active', t.dataset.q === q));
  renderLeadGrid();
}

/* ── Wire Leads-view + Overview controls ── */
function wireLeadsView() {
  $('add-lead-btn')?.addEventListener('click', openAddLead);
  $('addlead-close')?.addEventListener('click', closeAddLead);
  $('addlead-cancel')?.addEventListener('click', closeAddLead);
  $('addlead-form')?.addEventListener('submit', submitAddLead);
  $('addlead-overlay')?.addEventListener('click', e => { if (e.target.id === 'addlead-overlay') closeAddLead(); });

  $('leaddetail-close')?.addEventListener('click', closeLeadDetail);
  $('leaddetail-overlay')?.addEventListener('click', e => { if (e.target.id === 'leaddetail-overlay') closeLeadDetail(); });

  $('ov-search-btn')?.addEventListener('click', openSearch);
  $('leads-search-btn')?.addEventListener('click', openSearch);
  $('ov-sort-btn')?.addEventListener('click', cycleLeadSort);
  $('leads-sort-btn')?.addEventListener('click', cycleLeadSort);

  $('priority-see-all')?.addEventListener('click', e => { e.preventDefault(); switchView('approvals'); });
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
  renderLeadsQuick();
  renderSourceMix();
  renderConvList();
  renderConvThread();
  renderDrafts();
  renderActivity();
  renderAnaKpis();
  renderInsights();
  renderStages();
  renderFunnel();
  renderSourceChart();
  renderHistogram();
  renderWeekly();
  renderCohorts();
  renderTopPerformers();
  renderNotifications();
}

/* ══════════════════════ BOOT ══════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  wireNav();
  wireTopbar();
  wireOverviewTabs();
  wireLeadsTabs();
  wireLeadsView();
  wireApprovals();
  wireOverviewChart();
  wireConvFilters();
  wireLogin();

  const isServed = window.location.protocol !== 'file:';

  // ── Auth gate (only when served by the API) ──
  if (isServed) {
    const ok = await checkAuth();
    if (!ok) {
      applyLoginMode(await loadAuthConfig());  // local form vs Auth0 button
      showLogin();
      return;                                  // wait for login → bootDashboard()
    }
    await bootDashboard();
  } else {
    // file:// sample mode — no server, keep the placeholder identity
    renderMe();
    const firstEscalated = CONVERSATIONS.findIndex(c => c.escalated);
    if (firstEscalated >= 0) activeConv = firstEscalated;
    renderAll();
  }

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
    renderActivity();
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
