---
title: Dashboard
type: technical
tags: [dashboard, frontend, ui, spa]
updated: 2026-06-14
---

# Lead Intelligence Dashboard

← [[HOME]] | See also: [[Architecture]], [[Codebase Map]], [[Auth & Hierarchy]]

> The dashboard is a vanilla-JS SPA in `aria/dashboard/`, served by the API at **`/ui`** and **live on the database** — login-gated and scoped per role. `loadLiveData()` replaces all globals from the API on load + every 30s. The `data.js` sample is only a fallback for opening `index.html` as a bare `file://` with no server.

---

## Files

| File | Size | Purpose |
|------|------|---------|
| `dashboard/index.html` | ~200 lines | Shell: topbar, nav pills, 5 `<section class="view">` panels |
| `dashboard/styles.css` | ~1000 lines | All visual design — variables, layout, components |
| `dashboard/data.js` | ~400 lines | Sample data: 56 leads, 12 conversations, TEAM, OPERATING_STATUS |
| `dashboard/app.js` | ~600 lines | All interactivity: chart, co-pilot, inbox, view switcher |

---

## Views

### Overview
- KPI row (3 cards: total leads, hot leads, approval queue count)
- Dot scatter chart (custom SVG — each dot = one real lead)
- Leads table (filterable by quality tier)
- Right column:
  - Priority actions (leads needing immediate attention)
  - ARIA Co-pilot panel (see below)

### Leads
- Full lead card grid
- Each card: avatar, name, quality pill, pipeline value, owner assignment, last activity (relative time)

### Inbox
- Conversation list with filter strip: **All / ARIA / Needs team**
- Thread view: full message history with ARIA→human handoff divider
- Handoff divider: team member avatar + name + timestamp marks the exact transition point
- Bubble types: `lead` (white), `aria` (lavender), `human` (dark slate gradient)

### Leads (added since)
- Import button → CSV/Excel import modal with distribution summary
- Click any lead → detail modal: stage dropdown, **Assigned to** (reassign for managers/admin), score breakdown, "Email the lead" → compose templated email

### Approvals
- Pending drafts grid (scoped to the user's team); approve / edit / reject

### Analytics *(now built, live)*
- KPI cards, **Lead Stages** count grid (10 stages), cumulative funnel, source mix donut, score histogram, weekly trend, cohorts table, top performers

---

## Login, identity & team management

- **Login overlay** (`/ui`): email + password (local auth) or "Continue with Auth0"; "Create an account" toggle for self-service register (new users join as Employee, unassigned).
- **"Viewing as" dropdowns** (topbar) — role-aware:
  - **Admin:** two always-present dropdowns — Team Leader, then Employee (filtered to that leader's team).
  - **Team leader:** one dropdown — their own team.
  - **Employee:** none (they only see their own).
- **Team & roles** modal (admin only, avatar menu) — change anyone's role and reports-to; guarded against self-demotion, orphaning a team, and reporting loops.

See [[Auth & Hierarchy]] for the model behind this.

---

## Group chat in the Inbox

Multiple people on a lead's chain talk in one thread. Each human bubble shows the
sender's **name + role**, colour-coded by hierarchy — admin (purple), team leader
(amber), employee (green); ARIA and the lead keep their own styles. The sender is
recorded from the logged-in session, so it can't be spoofed. The lead's own chat
page shows only first names.

---

## ARIA Co-pilot Panel

Replaces the generic "Hi, how can I help?" chat widget. Shows ARIA's actual operational state:

```
ARIA Co-pilot
Watching 12 conversations · drafting 3

Needs your decision
[icon] Rajesh Sharma approved a demo — confirm time slot  [Act →]
[icon] 2 messages flagged with low confidence            [Review →]
[icon] Priya Mehta said "maybe later" — re-engage?       [Snooze →]

ARIA today
Leads qualified: 8  |  Drafts sent: 12  |  Escalations: 1
```

Each action item links to the relevant view (`switchView('approvals')`, etc.).

Data source: `OPERATING_STATUS` object in `data.js` → `renderCopilot()` in `app.js`.

---

## Dot Scatter Chart

Custom SVG, not Chart.js. Design decisions:
- Each dot = one real lead (hover shows lead name, type, quality)
- X-axis = dates (last 14 days)
- Y-axis = count (integer ticks)
- **Critical:** a single `yScale(v)` function is shared by both y-axis tick labels and dot positions. They always align.
- Focus day auto-detects as today (last day with data). The focus column gets a soft highlight and pill showing the count.
- Topmost dot on a column sits at `yScale(count)` — aligns with the count number on the y-axis.

```javascript
// The one function that rules them all
const yScale = v => PAD.t + chartH - (v / maxCount) * chartH;

// Y-axis ticks
for (let v = 0; v <= maxCount; v++) {
  const y = yScale(v);  // label at this y
}

// Dots: i-th lead (0-indexed) sits at yScale(i+1)
d.leads.forEach((lead, i) => {
  const y = yScale(i + 1);  // dot at this y
});
```

---

## ARIA → Human Handoff in Inbox

When `messages` array contains `{ from: 'human', who: 'team_key' }`, the thread renderer injects a visual divider at that point:

```
[Priya] "What's the pricing for brokers?"
[ARIA]  "Happy to explain — we have three tiers..."
[ARIA]  "Of course — Aakash will jump in here in a moment."
────────── ARIA handed off to Aakash ── 14:00 ──────────
[Aakash] "Hi Priya, Aakash here from BeyondSure..."
[Priya]  "That works for me."
[Aakash] "Confirmation sent. See you Monday!"
```

Backend mapping:
- `from: 'lead'` → `Interaction.direction = 'inbound'`
- `from: 'aria'` → `Interaction.direction = 'outbound', handled_by = 'aria'`
- `from: 'human'` → `Interaction.direction = 'outbound', handled_by = 'human'`
- Handoff point → `Escalation` row in DB

---

## Live data (done — v0.7)

`loadLiveData()` fetches and replaces the in-memory globals on load and every 30s.
Every panel reads real DB rows; the old `data.js` arrays are only a `file://` fallback.

| Panel | Live API source |
|------|-------------------|
| Overview KPIs / stats | `GET /leads/stats` (scoped, `?as=` for drill-down) |
| Leads grid + detail | `GET /leads/`, `GET /leads/{id}` |
| Inbox conversations | built from `GET /leads/`; thread via `GET /chat/admin/{id}` |
| Approvals + activity | `GET /approval/queue`, `GET /approval/stats` |
| Analytics | `GET /leads/analytics` |
| Templates | `GET /templates/` |
| Identity / team | `GET /auth/me`, `GET /leads/assignable-owners` |

A lead's `created_at` is bucketed by **local (IST) date** for the dot chart — see [[Decision Log]] (2026-06-12).

---

## Design Language

- **Background:** `#fafafd` (off-white, almost white — not saturated lavender)
- **Ambient blobs:** `filter: blur(120px)` at 10–16% opacity — barely visible, just a hint of colour
- **Cards:** `background: #fff`, `border: 1px solid rgba(15,17,41,0.06)`, multi-layer shadow
- **Topbar:** `backdrop-filter: blur(20px) saturate(180%)` glassmorphism, `rgba(255,255,255,0.75)`
- **Typography:** Inter, negative letter-spacing (`-0.02em`), tabular numerals for figures
- **Pill nav:** active pill = `background: var(--ink-1); color: #fff`
- **Human bubble:** `background: linear-gradient(135deg, #1e293b, #334155); color: #fff`
