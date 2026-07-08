---
title: Build Status
type: status
tags: [status, progress, todo]
updated: 2026-06-22
---

# Build Status

← [[HOME]] | See also: [[Roadmap]], [[Checkpoints]]

> Update this note whenever something is completed or discovered.
> Current checkpoint: **v0.11 — done** (email template send-time controls). Latest pushed commit `4bd794e` — template send controls + per-user uploaded signatures. Two `/full-checkup` fixes since (signature now embedded inline via CID; failed sends surfaced in approval stats) are **local — not yet committed**. **251 tests passing.**
> Next: chat resume + 15-day link expiry (designed — not built, see [[Roadmap]] / [[Decision Log]]); email lead ingestion (deferred); FB/IG webhook; deploy.

---

## ✅ Done

### Backend core (`aria/`)
- [x] `main.py` — FastAPI app, startup banner, `asynccontextmanager` lifespan (not deprecated `on_event`)
- [x] `config.py` — `.env` loading via Pydantic v2 `SettingsConfigDict` (not deprecated `class Config`)
- [x] `database.py` — SQLAlchemy + SQLite setup
- [x] `models/lead.py` — Lead ORM, extended with chat_token, human_priority, human_notes, current_software, alert_sent_at, chat_opened_at, re_engage_after
- [x] `models/interaction.py` — every inbound/outbound message
- [x] `models/escalation.py` — created when lead asks for human
- [x] `models/knowledge_base.py` — FAQ Q&A store
- [x] `models/demo.py` — demo bookings (scheduled_preference, demo_number, status)
- [x] `schemas/lead.py` — Pydantic webhook payload + response

### Services
- [x] `services/intent_classifier.py` — 14 intents, rules-based, tested
- [x] `services/lead_scorer.py` — 3-bucket scoring (profile 40 + form_intent 30 + engagement 30), score decay, re-engagement
- [x] `services/message_builder.py` — first-touch + follow-up 1/2 templates
- [x] `services/kb_lookup.py` — word-overlap KB search
- [x] `services/kb_seeder.py` — seeds database with 25 FAQ entries on startup
- [x] `services/llm.py` — Groq + Anthropic dual provider, post-processor scrubs LLM output (prices, date promises, guarantee language)
- [x] `services/scheduler.py` — follow-up 1 (24hr), follow-up 2 (72hr), 7-day nudge, re-engagement, score decay; APScheduler runs hourly in IST timezone
- [x] `services/chat_flow.py` — guided 7-step qualification sequence, CRM field extraction, `parse_guided_answer()` with `_action` key for branching
- [x] `services/alert_mailer.py` — structured hot-lead dossier email to team (triggers at score ≥ 70, demo confirmed, or escalation)
- [x] `services/demo_mailer.py` — confirmation email sent to lead when demo is booked; includes Google Meet link + what to expect

### Routes
- [x] `routes/webhook.py` — lead ingestion, deduplication (email+phone OR match, normalised), reply handling
- [x] `routes/leads.py` — CRM read endpoints + manual overrides (priority flag, notes, status)
- [x] `routes/approval.py` — human review queue (approve / edit / reject)
- [x] `routes/scheduler.py` — manual trigger + status endpoints
- [x] `routes/chat.py` — inline chat page (HTML/CSS/JS string constant), message handler, history endpoint, admin view, guided flow + open LLM pipeline
- [x] `routes/dashboard.py` — serves legacy inline dashboard HTML at `GET /dashboard`

### Dashboard SPA (`aria/dashboard/`)
- [x] `dashboard/index.html` — 5-view shell (Overview · Leads · Inbox · Approvals · Analytics placeholder)
- [x] `dashboard/styles.css` — ~1000 lines: off-white `#fafafd` bg, glassmorphic topbar, ambient blobs, multi-layer card shadows, handoff divider, co-pilot panel
- [x] `dashboard/data.js` — 56 sample leads, 12 conversations (3 with ARIA→human handoff), TEAM registry, OPERATING_STATUS
- [x] `dashboard/app.js` — dot scatter chart (shared yScale), co-pilot panel, conv thread renderer, handoff divider injection, filter chips, view switcher

### Utilities & config
- [x] `utils/email_sender.py` — SMTP email with DPDP footer; falls back to console print in dev
- [x] `.env.example` — complete template with comments for all required keys
- [x] `requirements.txt` — all production dependencies
- [x] `requirements-dev.txt` — pytest, httpx, coverage (dev-only)
- [x] `pytest.ini` / `setup.cfg` — pytest config, coverage settings

### Auth, hierarchy & CRM ownership (v0.8) — see [[Auth & Hierarchy]]
- [x] `models/user.py` — User (employee / manager / admin), self-referential `manager_id` tree
- [x] `services/auth_service.py` — PBKDF2 password hashing (stdlib), `subtree_ids`/`resolve_scope`, `next_owner_id(among)`, `assignment_pool`, seed/upgrade demo org, Auth0 role mapping
- [x] `routes/auth.py` — login/logout/register, `get_current_user` dep, Auth0 OIDC flow, `PATCH /auth/users/{id}` (admin role/manager editor with loop/orphan guards)
- [x] Leads have `owner_id`; every dashboard/approval endpoint scoped to the user's subtree
- [x] Login screen + self-service register; admin "Team & roles" editor; role-aware "viewing as" dropdowns (admin: team-leader + employee; leader: their team; employee: none)
- [x] Pluggable provider — `AUTH_PROVIDER=local` (default, no new deps) or `auth0` (lazy authlib)

### Pipeline stages (v0.8) — see [[Lead Sources & Assignment]]
- [x] `services/stages.py` — 10-stage canonical CRM pipeline derived from internal `status`
- [x] Analytics: stage-count grid + cumulative funnel; lead detail has a stage dropdown

### Email templates (v0.8) — see [[Email Templates]]
- [x] `models/email_template.py`, `services/template_service.py`, `routes/templates.py`
- [x] CRUD + `{placeholder}` preview/send, real file attachments, 6 seeded stage templates
- [x] `utils/email_sender.py` extended for attachments (multipart/mixed)
- [x] Compose modal + template manager in the dashboard; sends skip the approval queue (human is the approval)

### Inbox group chat (v0.8)
- [x] `interactions.sender_user_id` records who sent each human message (idempotent migration)
- [x] Sender taken from the session (unforgeable); name + role shown, colour-coded by hierarchy
- [x] Scope-checked: only the lead's chain (owner → leader → admin) can post; lead sees first names only

### Bulk import + auto-assignment (v0.9) — see [[Lead Sources & Assignment]]
- [x] `services/lead_importer.py` — CSV (stdlib) + xlsx (openpyxl, lazy), flexible header aliases, dedup, validation
- [x] `POST /leads/import` + `/leads/import-template`; dashboard Import modal with distribution summary
- [x] One auto-assignment policy across all sources (webhook + import); "within the team" round-robin
- [x] Importer aligned to the real Meta/Facebook Lead Ads export (long question headers → `uses_software`/`open_to_platform`/`willing_for_demo`, `types_of_business` → lead_type, `p:` phone prefix stripped)

### Google + OneDrive sheet sync (v0.10) — see [[Lead Sources & Assignment]]
- [x] `models/sheet_source.py`, `routes/sheets.py` (CRUD + `/{id}/sync` + `/sync-all`, role-scoped), `services/sheet_sync.py`
- [x] `services/lead_intake.py` — shared create/dedup/score/auto-assign used by both file import and sheet sync
- [x] Google Sheets via published-CSV export URL; **OneDrive/SharePoint via `download=1` → xlsx** (host auto-detected, `PK`-header sniff picks the parser) — no API credentials needed *(committed `6f8ec6b`)*
- [x] 15-min scheduler job `run_sheet_sync()` + dashboard refresh button (`/sheets/sync-all`, disabled while running)
- [x] Verified live against a real OneDrive `1drv.ms` link (9 rows parsed, fields mapped)

### Email template send-time controls (v0.11) — see [[Email Templates]] *(committed `4bd794e`)*
- [x] **Pick attachments at send** — compose modal checkboxes; `/send` takes `attachments:[names]` (None=all, []=none), whitelisted to the template's files
- [x] **Uploaded signature image** — each user uploads their signature at avatar menu → My email signature; appended to the email HTML on send. `routes/signatures.py` (`POST/DELETE /signatures/me` + public `GET /signatures/{fn}`); `users.signature_image` column (idempotent migration); files in `signature_files/` (gitignored); `signature_image_html()` builds the `<img>`; **non-blocking warning** in Compose if none uploaded
- [x] **Sender = login email** — `/send` sets `From:`/`Reply-To:` to the logged-in user; SMTP envelope stays the authenticated account
- [x] The client's 2 templates seeded (Post-Demo, Commercial Proposal); seeding now idempotent **by name**
- [x] Dashboard `?v=19`; +16 tests (attachments, signature upload/serve/delete, sender identity, seed-by-name) → `tests/test_signatures.py` added

### Deployment hardening (v0.8) — see [[Deployment]]
- [x] Boot guard refuses dev `SESSION_SECRET` on a non-local deploy; cookie `Secure` on HTTPS
- [x] `/scheduler/*` requires login (test-email admin-only); approval actions scope-checked
- [x] Escalation alert sends wrapped (outage can't 500 the lead chat); dependencies pinned

### Demo data
- [x] `seed_demo.py` — idempotent demo org + ~25 leads WITH full history (drafts, chat threads, escalations, demos); `@demoleads.in` marker so re-runs are clean

### Tests (`aria/tests/`)
- [x] `tests/conftest.py` — in-memory SQLite, per-test rollback, `get_current_user` overridden to admin
- [x] `test_routes.py`, `test_leads.py`, `test_chat.py`, `test_scheduler.py`, `test_services.py`, `test_admin.py` (earlier suites)
- [x] `test_team.py` — role/manager editor + register guards
- [x] `test_templates.py` — template CRUD, preview, send, attachments, cross-platform filename sanitization
- [x] `test_group_chat.py` — sender attribution + scope
- [x] `test_hardening.py` — scheduler auth, approval scope, production-config guard
- [x] `test_import.py` — parsing, header aliases, xlsx, dedup, validation, per-role distribution, Meta-export columns
- [x] `test_sheets.py` — URL normalize (Google + OneDrive), CRUD/permissions, sync + dedup, xlsx-bytes sniff, sync-all scope
- [x] `test_templates.py` — signature-on-send + preview flag, sender identity on send, send-time attachment selection, seed-by-name
- [x] `test_signatures.py` — signature image upload/replace/serve/delete, non-image reject, login required
- [x] **248 tests passing, 1 warning** (pydantic-settings v2.2 internal warning — unfixable without upstream release)

### Code hygiene
- [x] All `datetime.utcnow()` → `datetime.now(timezone.utc)` across 6 files (83 deprecation warnings eliminated)
- [x] `main.py` lifespan — `@app.on_event` → `asynccontextmanager` (FastAPI 0.111 deprecation fix)
- [x] `config.py` — `class Config` inner class → `SettingsConfigDict` (Pydantic v2 deprecation fix)

### Research & documents (outside `aria/`)
- [x] `ARIA_Lead_Analysis.docx` — 6-page report, 4 charts, key findings
- [x] `ARIA_Knowledge_Base.xlsx` — 25 FAQ entries, summary sheet
- [x] `Architecture/ARIA_ARCHITECTURE_AUDIT.md` — P0/P1/P2 issue audit

---

## ⏳ Pending

### Must do before real use
- [ ] Fill in 21 KB placeholder answers — needs real pricing/features info from team
- [ ] Connect Facebook/Instagram Lead Ads webhook (real leads auto-flowing in)
- [ ] Email / Google-Sheet lead ingestion — **deferred**, awaiting details on how marketing actually sends leads (forwarded mailbox vs inbound-parse vs a sheet refreshed ~15 min). The auto-assignment policy is source-agnostic, so it plugs straight in.
- [ ] Deploy to server (Railway / Render) — set a real `SESSION_SECRET` (boot guard enforces this); decide Auth0 vs local
- [ ] Get a real end-to-end test against live ad leads

### Should do soon
- [ ] **Chat resume + 15-day link expiry** — *designed, not built.* Sliding 15-day expiry on the chat session; durable token re-entry → AI recap of the conversation so far → continue. Channel-agnostic (web now; WhatsApp/FB buttons reuse the same resume later). Security: token via POST not URL, `Referrer-Policy: no-referrer`, rate-limited resume, optional email/phone re-confirm, expiry enforced on page **and** message endpoints. See [[Decision Log]] / [[Roadmap]].
- [ ] Upload the real proposal PDF to the Commercial Proposal template (via Manage templates — shows "(missing)" until then)
- [ ] Error logging via the `logging` module (failed SMTP / LLM timeouts — currently `print()` in some paths)
- [ ] Meta webhook signature verification on `/webhook/lead`
- [ ] Backend timezone seam in weekly/cohort analytics (still aggregates in UTC weeks)

### Nice to have
- [ ] WhatsApp channel via Cloud API (scaffolded; needs team credentials)
- [ ] A/B message testing framework
- [ ] Consolidate `routes/dashboard.py` legacy inline HTML (superseded by the SPA)

---

## ✅ Recently resolved (were open)

| Was | Now |
|-----|-----|
| Dashboard used sample `data.js` | **Live** — every panel reads the API via `loadLiveData()`; sample data is only a `file://` fallback |
| No bulk lead import | **Done** — CSV/Excel import with auto-assignment |
| Google Sheet sync "planned" | **Done** — Google + OneDrive/SharePoint, 15-min poll + refresh button, no API creds |
| OneDrive link rejected as "not public" | **Fixed** — host detected, `download=1` → xlsx, `PK`-sniff parser routing |
| Analytics view was a placeholder | **Built** — KPIs, stage grid, funnel, source mix, score histogram, weekly, cohorts |
| Leads "owned by whoever brought them" | **Reframed** — auto-assigned on arrival; ownership = who handles it |
| Open email relay on `/scheduler/test-email` | **Closed** — login + admin required |
| Forgeable session (public dev secret) | **Closed** — boot guard + `Secure` cookie |

---

## 🐛 Known issues / watch out for

| Issue | Status | Fix |
|-------|--------|-----|
| 21 KB answers are placeholders | Open | LLM falls back to "Let me connect you with our team" |
| `routes/dashboard.py` legacy inline HTML | Open | Superseded by the SPA — consolidate/remove when convenient |
| Operational logging via `print()` | Open | Move to `logging` module before production |
| Weekly/cohort analytics use UTC weeks | Open | Daily dot chart is fixed (local date); weekly/cohort backend still UTC |
| Stale `__pycache__` | Mitigated | Delete cache dirs if edited files aren't being picked up |
| 1 test warning (pydantic-settings v2.2) | Unfixable | Internal library warning, not our code |

> [!note] PowerShell + git commit messages
> Multi-line commit messages with inner double-quotes break the PowerShell here-string when piped to git. Keep commit-message bodies quote-free (this bit us twice).
