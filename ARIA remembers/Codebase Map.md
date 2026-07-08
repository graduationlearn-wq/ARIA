---
title: Codebase Map
type: technical
tags: [codebase, files, python, fastapi]
updated: 2026-06-22
---

# Codebase Map

← [[HOME]] | See also: [[Architecture]], [[Dashboard]], [[Auth & Hierarchy]]

All files in `ARIA/aria/`. Every file's purpose in plain English.

---

## Entry points

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app. Registers all routers (incl. `auth`, `templates`). `asynccontextmanager` lifespan: `_check_production_config()` (refuses dev secret on a non-local deploy), `init_db()`, `seed_kb()`, `seed_users()` + `assign_unowned_leads()`, `seed_templates()`, starts APScheduler. Adds `SessionMiddleware` (signed cookie, `Secure` on HTTPS) |
| `config.py` | `.env` → `Settings` via Pydantic v2 `SettingsConfigDict`. Adds `session_secret` (+ `DEV_SESSION_SECRET` sentinel), `auth_provider`, `auth0_*`, and `is_local_host`/`is_https` helpers, on top of the LLM/SMTP/whatsapp/base_url fields |
| `database.py` | SQLAlchemy engine, `SessionLocal`, `Base`, `get_db()`, `init_db()`. `_run_light_migrations()` adds new columns idempotently (`leads.meet_link`, `leads.owner_id`, `interactions.sender_user_id`) — safe on an existing DB |
| `requirements.txt` | + `itsdangerous` (session cookie), `authlib` (Auth0, optional), `openpyxl` (xlsx import) on top of fastapi/uvicorn/sqlalchemy/pydantic/groq/anthropic/apscheduler. Pinned to tested versions |
| `seed_demo.py` | Standalone idempotent demo seeder — full org + ~25 leads with history. Run `python seed_demo.py`. Not part of app startup. See [[Lead Sources & Assignment]] |
| `.env.example` | Template — copy to `.env` and fill in all keys |

---

## Models (database tables)

| File | Table | Key fields |
|------|-------|-----------|
| `models/lead.py` | `leads` | …all earlier fields… + **`owner_id` (FK users — the assigned handler), `meet_link`** |
| `models/interaction.py` | `interactions` | lead_id (FK), direction, channel, message_text, intent_label, intent_confidence, handled_by (aria/human), send_status, reviewer_notes, message_type, **`sender_user_id` (FK users — who sent a human message; group-chat attribution)** |
| `models/user.py` | `users` | id, name, email (unique), password_hash (PBKDF2), role (employee/manager/admin), `manager_id` (self-FK — the reporting tree), avatar_seed, **`signature_image` (filename of the user's uploaded signature image; null = none)**, is_active, created_at |
| `models/email_template.py` | `email_templates` | **NEW.** name, stage (canonical pipeline key or null), subject, body (with `{placeholders}`), attachments (JSON filenames), is_active |
| `models/sheet_source.py` | `sheet_sources` | **NEW.** name, sheet_url, owner_user_id (FK), is_active, last_synced_at, last_status, last_imported, total_imported — a Google/OneDrive lead sheet owned by a leader |
| `models/escalation.py` | `escalations` | lead_id (FK), interaction_id (FK), triggered_at, reason, assigned_to, status |
| `models/knowledge_base.py` | `knowledge_base` | question, answer, category, active, is_placeholder, updated_at |
| `models/demo.py` | `demos` | lead_id (FK), created_at, scheduled_preference, demo_number, status |

---

## Schemas

| File | Purpose |
|------|---------|
| `schemas/lead.py` | `LeadWebhookPayload` — matches Facebook/Instagram lead ad form field names. `LeadResponse` — what the API returns |

---

## Services (the brain)

| File | Purpose |
|------|---------|
| `services/intent_classifier.py` | `classify_intent(message)` → `IntentResult(label, confidence)`. Rules-based keyword matching. 14 intent labels. `should_escalate(intent)` returns True for `bot_detection` and `escalation_request` |
| `services/lead_scorer.py` | `compute_initial_score(lead)` → (score, quality). Buckets: Profile (40) + Form Intent (30) + Engagement (30). `apply_engagement_delta()` adjusts on reply. `apply_decay()` degrades score for inactive leads |
| `services/message_builder.py` | `build_first_touch(lead)` — personalised opening email. `build_followup_1()` (24hr), `build_followup_2()` (72hr). `build_subject_line()` |
| `services/kb_lookup.py` | `search_kb(query, db)` — word-overlap scoring against KB. `get_answer_for_intent(intent_label, db)` — maps intent to KB category |
| `services/kb_seeder.py` | Seeds 25 FAQ entries into `knowledge_base` table on first startup. Called by `main.py` lifespan. Safe to call multiple times (skips if already seeded) |
| `services/llm.py` | `generate_draft(lead, intent, message, history, kb_context)` for email/approval drafts. `generate_chat_response()` for real-time chat (short, conversational). Supports Groq + Anthropic via `LLM_PROVIDER` env var. **`post_process_response()`** regex-scrubs every LLM output for hallucinated prices, date promises, guarantee language — critical compliance layer, do not bypass |
| `services/scheduler.py` | `run_followup_1()` (24hr), `run_followup_2()` (72hr), `run_7day_nudge()`, `run_reengagements()`, `run_score_decay()`. `run_all_followups()` called hourly by APScheduler in IST timezone |
| `services/chat_flow.py` | `GUIDED_STEPS` list drives 7-step qualification sequence: `uses_software → current_software → lead_type → team_size → company_name → company_website → willing_for_demo → demo_preference`. `parse_guided_answer()` extracts CRM fields and may return `_action` key: `"demo_book" | "reengage" | "escalate" | "demo_confirmed"` |
| `services/alert_mailer.py` | `send_hot_lead_alert(lead)` — structured dossier email + WhatsApp to team when `lead_score ≥ 70`, demo confirmed, or escalation triggered |
| `services/demo_mailer.py` | `send_demo_confirmation(lead, preferred_time)` — confirmation email to the *lead* after demo booked |
| `services/auth_service.py` | **NEW.** PBKDF2 `hash_password`/`verify_password`; `subtree_ids`/`resolve_scope`/`viewable_users` (hierarchy scoping); `next_owner_id(db, among)` + `assignment_pool(user)` (auto-assignment); `seed_users`/`_upgrade_demo_users`/`assign_unowned_leads`; `user_directory`; Auth0 `map_auth0_role`/`upsert_oauth_user`. See [[Auth & Hierarchy]] |
| `services/stages.py` | **NEW.** Canonical 10-stage pipeline (`STAGE_ORDER`, `STAGE_LABELS`, `FUNNEL_TRACK`, `HUMAN_STAGES`); `lead_stage(lead)` derives the display stage from internal `status` without rewiring ARIA |
| `services/template_service.py` | `{placeholder}` rendering from lead + sender (legacy `{signature}` → empty; the image is embedded inline at send time by `email_sender`); `seed_templates()` seeds 8 defaults **idempotently by name** (6 stage + client's Post-Demo & Commercial Proposal); attachment helpers. See [[Email Templates]] |
| `services/lead_importer.py` | **NEW.** Parse CSV (stdlib) + xlsx (openpyxl, lazy); flexible header aliases (incl. Meta/Facebook Lead Ads long-question headers) → canonical lead fields; strips `p:` phone prefix; `template_csv()` download. See [[Lead Sources & Assignment]] |
| `services/lead_intake.py` | **NEW.** `intake_rows(db, rows, owner_user, *, source)` — the one shared create/dedup/score/auto-assign path used by both file import and sheet sync; returns {imported, duplicates, errors, total_rows, assigned} |
| `services/sheet_sync.py` | **NEW.** `to_csv_url()` (Google → CSV export), `is_onedrive_url()`/`to_download_url()` (OneDrive/SharePoint → `download=1` xlsx), `fetch_csv()` (fetch bytes, reject HTML/private), `sync_source()` (sniff `PK` → xlsx vs CSV → intake; never raises), `run_sheet_sync()` (15-min scheduler entry, own session). See [[Lead Sources & Assignment]] |

---

## Routes

| File | Endpoints |
|------|----------|
| `routes/auth.py` | `get_current_user` dependency; `POST /auth/login`, `/auth/register`, `/auth/logout`; `GET /auth/me` (returns `signature_image` + `signature_url`); `/auth/config`; Auth0 OIDC `/auth/login` redirect + `/auth/callback`; `PATCH /auth/users/{id}` (admin role/manager editor with self-demotion/orphan/loop guards) |
| `routes/signatures.py` | **NEW.** Per-user email signature images: `POST/DELETE /signatures/me` (login) + `GET /signatures/{filename}` (**public** — recipient mail clients fetch it). Files in `signature_files/` (gitignored). See [[Email Templates]] |
| `routes/templates.py` | `/templates` CRUD, `/templates/{id}/preview` (returns `signature_set` for the compose warning), `/templates/{id}/send` (logs a human Interaction, skips approval; **From/Reply-To = logged-in sender**, a **chosen attachment subset**, and the sender's **signature image appended**), attachment upload/download/delete, `/templates/placeholders`. Login required |
| `routes/sheets.py` | **NEW.** `/sheets/` CRUD, `/sheets/{id}/sync`, `/sheets/sync-all` (dashboard refresh button). Role-scoped: admin all · team leader own · employee none. See [[Lead Sources & Assignment]] |
| `routes/webhook.py` | `POST /webhook/lead` — ingest, dedup, score, first-touch draft, **`owner_id=next_owner_id(db)`** (auto-assign). `POST /webhook/reply` — Pydantic body now; classify → escalation gate → KB → LLM draft |
| `routes/leads.py` | Router **requires login**. `GET /stats`, `/`, `/{id}` (all **scoped** to the user's subtree). Overrides: priority/notes/status/meet. `assignable-owners`, `PATCH /{id}/owner` (reassign). `GET /analytics` (stages grid + funnel + source + histogram + weekly + cohorts). **`POST /import`** + `GET /import-template` (CSV/Excel bulk import + auto-assignment) |
| `routes/approval.py` | Router requires login. queue/stats **scoped**; approve/edit/reject now **scope-checked** to the user's team |
| `routes/scheduler.py` | Router **requires login**; `test-email` is **admin-only**. run / run-* / status |
| `routes/chat.py` | `GET /chat/{token}` (inline `CHAT_HTML`), `POST /chat/{token}/message` (guided flow → LLM; alert sends wrapped). `GET /chat/{token}/history` (shows team sender first-names). `GET/POST /chat/admin/{lead_id}` — login + scope required; reply records `sender_user_id` (group chat) |
| `routes/admin.py` | KB editor + `/admin/config` (non-secret system status). Login required |
| `routes/dashboard.py` | `GET /dashboard` — legacy inline HTML (superseded by the SPA) |

---

## Dashboard SPA (`dashboard/`)

The new lead intelligence dashboard lives in `aria/dashboard/` as four separate files. Open `index.html` directly in a browser — no server needed.

| File | Purpose |
|------|---------|
| `dashboard/index.html` | Shell + all modals: login/register overlay, Team & roles, Compose + Template manager, Import, Lead detail. Cache-busted with `?v=N` (currently v14) |
| `dashboard/styles.css` | Off-white `#fafafd` bg, ambient blobs, handoff divider, co-pilot panel, bubbles (hierarchy-coloured), stage grid, login, team rows, import drop, template manager |
| `dashboard/data.js` | Sample leads/conversations — **fallback only** for `file://` preview; overwritten by the API when served |
| `dashboard/app.js` | Auth block (`checkAuth`, `doLogin`/`doRegister`, role-aware `renderViewAs`, Team & roles, `refreshIdentity`); `loadLiveData()` replaces all globals from the API; dot chart (`parseApiDate`/`localDateKey`); group-chat bubbles with attribution; templates compose/manager; import modal; stage grid + funnel |

See [[Dashboard]] for full design notes.

---

## Utils

| File | Purpose |
|------|---------|
| `utils/email_sender.py` | `send_email(to, subject, body, attachments=, from_email=, from_name=, reply_to=, signature_image_path=)`. Plain+HTML alternative → `multipart/related` (inline **CID** signature `cid:aria-signature`) → `multipart/mixed` (file attachments), nested only as needed. Visible `From:`/`Reply-To:` can be the logged-in sender while the **SMTP envelope stays the authenticated account** (SPF/auth safe). DPDP unsubscribe footer. Falls back to console print if SMTP not configured |

---

## Tests (`tests/`)

| File | What it covers |
|------|---------------|
| `tests/conftest.py` | In-memory SQLite per test, transaction rollback; `get_current_user` overridden to an admin so existing tests run authenticated |
| `tests/test_routes.py` | Webhook lead ingestion, reply loop, deduplication |
| `tests/test_leads.py` | CRM read endpoints, manual overrides |
| `tests/test_chat.py` | Guided flow, escalation, history; admin reply |
| `tests/test_scheduler.py` | Follow-up timing, score decay |
| `tests/test_services.py` | Scorer, classifier, message builder |
| `tests/test_admin.py` | KB editor / admin config |
| `tests/test_team.py` | Role + reports-to editor, register guards |
| `tests/test_templates.py` | Template CRUD, preview, send, attachments, cross-platform filename sanitization |
| `tests/test_group_chat.py` | Group-chat sender attribution + scope |
| `tests/test_hardening.py` | Scheduler auth, approval scope, production-config guard |
| `tests/test_import.py` | Import parsing, header aliases, xlsx, dedup, validation, per-role distribution |

**Run all:** `cd aria && pytest tests/`
**Current result:** 210 passed, 1 warning (library-internal, unfixable)

---

> [!warning]
> **Patching pattern:** When adding new routes, patch at the import site: `patch("routes.<module>.send_email")` — not `utils.email_sender.send_email`. Python patches where the name is used, not where it's defined.

> [!warning]
> **Stale `__pycache__`:** If you edit a `.py` file and behaviour doesn't change, delete cache dirs: `find . -name "__pycache__" -exec rm -rf {} +`
