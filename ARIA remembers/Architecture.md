---
title: Architecture
type: technical
tags: [architecture, system-design, fastapi, backend]
updated: 2026-06-22
---

# Architecture

← [[HOME]] | See also: [[Codebase Map]], [[Auth & Hierarchy]], [[Lead Sources & Assignment]]

## Full system pipeline

```
┌─────────────────────────────────────────────┐
│  INGESTION LAYER  (source-agnostic)         │
│  FB/IG Lead Form  → POST /webhook/lead       │
│  CSV / Excel file → POST /leads/import       │
│  Google/OneDrive  → /sheets/* + 15-min job   │
│  Email enquiries  → (deferred)               │
│  Lead deduplication (email+phone OR match)  │
│  Email reply      → POST /webhook/reply      │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  AUTO-ASSIGNMENT  (one policy, all sources) │
│  assignment_pool(user) → candidate team     │
│  next_owner_id(among)  → least-loaded emp.  │
│  lead.owner_id set on arrival               │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  CORE BRAIN                                 │
│  Intent Classifier  (rules → Phase 3 ML)   │
│  Lead Scorer        (profile+form+engage)   │
│  KB Lookup          (FAQ word-overlap)      │
│  Score Decay        (penalise inactivity)   │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  CHAT LAYER  (new in v0.5/v0.6)             │
│  GET /chat/{token}  — inline HTML chat UI   │
│  POST /chat/{token}/message                 │
│  Guided 7-step qualification flow           │
│  → CRM field extraction (lead_type, team…)  │
│  Open LLM pipeline after guided flow done   │
│  post_process_response() — compliance scrub │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  GENERATION LAYER                           │
│  Message Builder    (first-touch templates) │
│  LLM Service        (Groq / Claude)         │
│  post_process_response() — compliance scrub │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  TRUST MONITOR  (Phase 2)                   │
│  Human Approval Queue                       │
│  Approve / Edit / Reject                    │
│  All scheduler jobs also queue here         │
└──────────────────┬──────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  DISPATCH                                   │
│  Email Sender (smtplib)                     │
│  Alert Mailer — team dossier on hot leads   │
│  Demo Mailer  — confirmation to lead        │
│  WhatsApp (Sent API) — Phase 3              │
└─────────────────────────────────────────────┘

         ↕ all layers read/write
┌─────────────────────────────────────────────┐
│  DATABASE  (SQLite dev → Postgres prod)     │
│  leads · interactions · escalations         │
│  knowledge_base · demos                     │
└─────────────────────────────────────────────┘

         ↕ separate from main pipeline
┌─────────────────────────────────────────────┐
│  BACKGROUND SCHEDULER  (APScheduler, IST)   │
│  Every hour: followup_1, followup_2,        │
│  7day_nudge, reengagements, score_decay     │
│  Every 15 min: run_sheet_sync (Google/OD)   │
└─────────────────────────────────────────────┘

         ↕ team-facing UI (login-gated, scoped per role)
┌─────────────────────────────────────────────┐
│  DASHBOARD SPA  (aria/dashboard/)           │
│  Overview · Leads · Inbox · Approvals ·      │
│  Analytics  — all LIVE on the API           │
│  Login / register · Team & roles ·          │
│  Compose templates · Import · Sheets ·       │
│  Group chat · Refresh (syncs sheets)         │
└─────────────────────────────────────────────┘

         ↕ identity & access (see [[Auth & Hierarchy]])
┌─────────────────────────────────────────────┐
│  AUTH + HIERARCHY                           │
│  Session cookie (itsdangerous) — local      │
│  or Auth0 OIDC+RBAC (AUTH_PROVIDER)         │
│  users tree: admin → team leader → employee │
│  subtree_ids() scopes who sees whose leads  │
└─────────────────────────────────────────────┘
```

---

## Escalation path

```
Intent = bot_detection OR escalation_request
         ↓
Skip LLM entirely
         ↓
Create Escalation row + set lead.status = "escalated"
         ↓
Alert team (email + WhatsApp via alert_mailer)
         ↓
Lead appears in Inbox with ARIA→human handoff divider
         ↓
Human takes over in-thread
```

---

## Chat → Inbox handoff

```
Lead clicks /chat/{token} link in email
         ↓
Guided 7-step qualification flow (chat_flow.py)
         ↓
Open LLM pipeline (intent → KB → llm.py)
         ↓
Lead says "can I speak to someone?" (escalation_request intent)
         ↓
ARIA: "Of course — [team member] will jump in here in a moment."
         ↓
Escalation row created → appears in Inbox view of dashboard
         ↓
Team member continues the same conversation thread in Inbox
```

---

## Tech stack

| Layer | Technology | Why chosen |
|-------|-----------|------------|
| API framework | FastAPI 0.111 | Fast, auto-generates Swagger docs |
| Server | Uvicorn 0.29 | ASGI, works with FastAPI |
| ORM | SQLAlchemy 2.0 | Postgres-ready, clean models |
| Database (dev) | SQLite | Zero setup, file-based |
| Database (prod) | PostgreSQL | Scale, concurrent writes |
| Validation | Pydantic v2 | Type-safe request parsing |
| Config | pydantic-settings v2 (`SettingsConfigDict`) | .env file management |
| LLM (testing) | Groq API — `llama-3.1-8b-instant` | Free tier, very fast |
| LLM (production) | Anthropic — `claude-haiku-4-5-20251001` | Quality, speed |
| Scheduler | APScheduler | Background jobs, IST timezone |
| Email | smtplib (built-in) | No extra dependency; attachments via multipart/mixed |
| Dashboard | Vanilla HTML/CSS/JS SPA | No build step; live on the API, auth-gated |
| Session auth | Starlette SessionMiddleware + itsdangerous | Signed cookie, `Secure` on HTTPS |
| Auth (prod option) | Auth0 OIDC + RBAC via authlib (lazy) | Pluggable; `AUTH_PROVIDER=auth0` |
| Password hashing | PBKDF2-HMAC-SHA256 (stdlib) | No bcrypt/passlib dependency |
| Excel import | openpyxl (lazy) | CSV needs no deps; xlsx optional |

---

## LLM provider switching

```env
LLM_PROVIDER=groq        # for testing (free)
LLM_PROVIDER=anthropic   # for production
```

No code change required — `services/llm.py` handles both.

---

## Human approval mode

```env
HUMAN_APPROVAL_MODE=true    # Phase 2: all drafts need approval
HUMAN_APPROVAL_MODE=false   # Phase 3: auto-send
```

All paths respect this flag: webhook handler, chat route, all scheduler jobs.

---

## API endpoints (current)

| Method | Endpoint | Purpose |
|--------|----------|---------|
**Public (no auth — by design):** `/webhook/*`, `/chat/{token}*`, `/auth/login`, `/auth/register`, `/auth/config`, the `/ui` SPA shell. Everything else needs a logged-in session.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/webhook/lead` | New lead from FB/IG; dedup, score, first-touch draft, auto-assign |
| POST | `/webhook/reply` | Lead's email reply (Pydantic body) |
| POST | `/leads/import` | Bulk CSV/Excel import + auto-assignment *(login)* |
| GET | `/leads/import-template` | Download a sample import CSV *(login)* |
| GET | `/leads/`, `/leads/stats`, `/leads/{id}` | Lead list / stats / detail — scoped *(login)* |
| GET | `/leads/analytics` | Stage grid, funnel, source, histogram, weekly, cohorts *(login)* |
| GET/PATCH | `/leads/assignable-owners`, `/leads/{id}/owner` | Reassign a lead *(login)* |
| GET/POST | `/approval/queue`, `/approval/{id}/approve\|edit\|reject` | Review queue — scoped *(login)* |
| GET/POST | `/templates/*` | Template CRUD, preview, send, attachments *(login)* |
| POST/GET | `/auth/login`, `/auth/register`, `/auth/logout`, `/auth/me`, `/auth/config` | Auth |
| GET | `/auth/login`, `/auth/callback` | Auth0 OIDC redirect flow |
| PATCH | `/auth/users/{id}` | Admin: change role / reports-to *(admin)* |
| GET/POST | `/chat/{token}`, `/chat/{token}/message\|history` | Lead-facing chat |
| GET/POST | `/chat/admin/{lead_id}`, `/chat/admin/{lead_id}/reply` | Inbox thread + group-chat reply — scoped *(login)* |
| POST/GET | `/scheduler/run*`, `/scheduler/status`, `/scheduler/test-email` | Jobs *(login; test-email admin)* |
| GET | `/admin/kb*`, `/admin/config` | KB editor + system status *(login)* |
| GET | `/dashboard` | Legacy inline dashboard |
| GET | `/`, `/docs` | Health check · Swagger UI |

---

## Running locally

```bash
cd ARIA/aria
pip install -r requirements.txt
cp .env.example .env
# fill in GROQ_API_KEY at minimum
uvicorn main:app --reload --port 8000
# open http://localhost:8000/docs
```

Dashboard SPA: open `aria/dashboard/index.html` directly in a browser.
