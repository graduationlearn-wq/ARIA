---
title: Checkpoints
type: milestones
tags: [checkpoints, milestones, versions]
updated: 2026-06-22
---

# Checkpoints

← [[HOME]] | See also: [[Roadmap]], [[Build Status]]

> A checkpoint is a named, demonstrable state of the system. Each one has clear "done" criteria — not just code written, but working and tested.

---

## ✅ v0.1 — Skeleton (done)

**What it proved:** The architecture holds. All layers connect.

- [x] FastAPI server starts, all routes register
- [x] Lead model + DB tables create on first run
- [x] `POST /webhook/lead` creates a lead record
- [x] Lead scorer returns a score and quality label
- [x] First-touch message builds correctly for different lead types
- [x] Approval queue shows pending drafts
- [x] Email sender prints to console (SMTP not yet connected)

---

## ✅ v0.2 — Intent + Reply Loop (done)

**What it proved:** ARIA can handle a reply, not just a new lead.

- [x] `POST /webhook/reply` classifies intent correctly
- [x] Escalation gate works (bot_detection, escalation_request bypass LLM)
- [x] LLM generates a context-aware draft (Groq working)
- [x] KB lookup injects relevant FAQ context into prompt
- [x] Opt-out (`not_interested`) sets `opt_out = True`, stops future messages
- [x] All 14 intent labels tested and verified

---

## ✅ v0.3 — Follow-up Sequence (done)

**What it proved:** Leads that go quiet don't fall off the radar.

- [x] `message_type` field on Interaction tracks sequence position
- [x] APScheduler runs every hour in background (IST timezone)
- [x] Follow-up 1 queued 24hrs after first-touch if no reply
- [x] Follow-up 2 queued 72hrs after follow-up 1 if still no reply
- [x] After follow-up 2, lead status → `needs_call`
- [x] `POST /scheduler/run` manual trigger available in Swagger
- [x] No double-queuing — scheduler skips if follow-up already exists

---

## ✅ v0.4 — Live Ready (done — 2026-05-08)

**What it proved:** Real leads, real emails, real test.

- [x] SMTP connected and verified
- [x] Test email delivered
- [x] Real lead pushed through `POST /webhook/lead`
- [x] Draft appeared in approval queue
- [x] Draft approved → email landed in inbox
- [x] Live dashboard at `http://localhost:8000/dashboard` working

---

## ✅ v0.5 / v0.6 — Chat Flow + Dashboard + Hardening (done — 2026-05-29)

**What it proved:** ARIA can qualify leads via a live chat interface, the team has a real dashboard, and the codebase is clean.

- [x] Lead deduplication (email+phone OR match, normalised)
- [x] Chat flow: `GET /chat/{token}` serves inline HTML chat page to lead
- [x] Guided 7-step qualification sequence (`uses_software` → … → `demo_preference`)
- [x] CRM fields update in real-time as lead answers
- [x] Score recomputes on each profile-field update
- [x] Escalation path: lead asks for human → `Escalation` row created → team alerted
- [x] `post_process_response()` compliance scrub on all LLM output
- [x] 7-day nudge + re-engagement + score decay added to scheduler
- [x] Demo model + demo confirmation mailer
- [x] Alert mailer: team dossier email + WhatsApp on hot lead / demo confirmed / escalation
- [x] Test suite: 109 tests passing, in-memory SQLite isolation
- [x] All `datetime.utcnow()` → `datetime.now(timezone.utc)` (83 warnings eliminated)
- [x] `main.py` lifespan fix (`asynccontextmanager` replaces deprecated `on_event`)
- [x] `config.py` Pydantic v2 fix (`SettingsConfigDict` replaces deprecated `class Config`)
- [x] Lead intelligence dashboard SPA: 4 views (Overview · Leads · Inbox · Approvals)
- [x] ARIA→human handoff visible in Inbox with divider + team member thread
- [x] Architecture audit (`Architecture/ARIA_ARCHITECTURE_AUDIT.md`)
- [ ] KB placeholders filled — still pending team input (21 answers)

---

## ✅ v0.7 — Dashboard Connected (done — 2026-06-08)

**What it proved:** The dashboard shows real data, not a mockup.

- [x] `aria/dashboard/` wired to the live API — every view reads the DB via `loadLiveData()`
- [x] Analytics view built out (KPIs, stage grid, funnel, source mix, score histogram, weekly, cohorts)
- [x] Sample `data.js` reduced to a `file://` preview fallback
- [ ] FB/IG Lead Ads webhook connected to real ads — *still pending*
- [ ] Server deployed — *still pending*

---

## ✅ v0.8 — Team, Templates, Group Chat, Hardening (done — 2026-06-12)

**What it proved:** ARIA is a real multi-user CRM the team can log into and trust to deploy.

- [x] Real login + 3-role hierarchy (employee / team leader / admin), local + Auth0-ready — [[Auth & Hierarchy]]
- [x] Self-service register; admin "Team & roles" editor (role + reports-to, with loop/orphan guards)
- [x] Per-team scoping on every endpoint; role-aware "viewing as" dropdowns
- [x] 10-stage canonical pipeline derived from internal status — [[Lead Sources & Assignment]]
- [x] Stage-aware email templates with `{placeholders}` + real attachments — [[Email Templates]]
- [x] Inbox group chat — multiple roles in one thread, per-sender attribution from the session
- [x] Full-checkup audit → fixed all blockers (session-secret guard, scheduler auth, Secure cookie, approval scope, alert wrappers, dep pinning) — [[Deployment]]
- [x] Cross-platform filename sanitization; overview dot chart fixed to local (IST) dates
- [x] `seed_demo.py` — full demo org + leads with history
- [x] Tests: 109 → ~206

---

## ✅ v0.9 — Bulk Import + Auto-Assignment (done — 2026-06-14)

**What it proved:** Leads from any channel land on the right person automatically.

- [x] CSV + Excel import (`/leads/import`) with flexible headers, dedup, validation, template download
- [x] One auto-assignment policy for every source — "within the team" balanced round-robin
- [x] Import reframed from "owned by uploader" → auto-distributed; UI wording "Assigned to"
- [x] 210 tests passing
- [x] Importer aligned to the real Meta/Facebook Lead Ads export shape

---

## ✅ v0.10 — Sheet Sync (done — 2026-06-22)

**What it proved:** Marketing's lead sheets flow into ARIA on a timer, from Google *or* OneDrive, with no API setup.

- [x] `models/sheet_source.py` + `routes/sheets.py` (CRUD, `/{id}/sync`, `/sync-all`, role-scoped)
- [x] `services/sheet_sync.py` — Google published-CSV URL + OneDrive/SharePoint `download=1` xlsx; `PK`-header sniff selects the parser
- [x] `services/lead_intake.py` — one shared create/dedup/score/auto-assign path for file import + sheet sync
- [x] 15-min scheduler job `run_sheet_sync()` + dashboard refresh button (`/sheets/sync-all`, disabled while running)
- [x] Verified live against a real OneDrive `1drv.ms` link (9 rows, fields mapped); 232 tests passing
- [ ] Commit the OneDrive support (currently local) + decide one-shared-sheet vs per-leader

---

## ✅ v0.11 — Email Template Send Controls (done — 2026-06-22)

**What it proved:** A rep can send a template email their way — chosen attachments, their own uploaded signature, from their own address.

- [x] Send-time **attachment selection** — compose checkboxes; `/send` takes `attachments:[names]` (None=all, []=none), whitelisted to the template's files
- [x] **Uploaded signature image** — each user uploads their signature at avatar menu → My email signature; appended to sent emails. `routes/signatures.py`; `users.signature_image` column; `signature_files/` (gitignored); non-blocking Compose warning if none
- [x] **Sender = login email** — `From:`/`Reply-To:` = logged-in user; SMTP envelope stays the authenticated account
- [x] Client's 2 real templates seeded (Post-Demo, Commercial Proposal); seeding idempotent by name
- [x] 248 tests passing; dashboard `?v=19`
- [x] Live-test admin + lead seeded into local aria.db (credentials kept local, not in the repo)
- [ ] Upload the real proposal PDF to the Commercial Proposal template (via Manage templates)

---

## 📋 v0.12 — Chat Resume (designed, not built)

**What it will prove:** A lead who closed the chat (or whose 15-day link expired) can come back, get an AI recap, and continue.

**Planned:**
- [ ] Sliding 15-day expiry on the chat session (enforced on page load *and* message POST)
- [ ] `POST /chat/resume` — token (+ optional email/phone re-confirm), rate-limited, token off the URL
- [ ] LLM recap of the conversation so far → reactivate session → continue
- [ ] `Referrer-Policy: no-referrer`, masked token logging; channel-agnostic so WhatsApp/FB reuse it later

---

## 📋 v1.0 — Phase 2 Complete

**What it will prove:** The team trusts ARIA enough to use it daily.

**Done when:**
- [ ] 100+ drafts reviewed and sent through the approval queue
- [ ] Draft quality consistently rated "good" or "edited slightly" by reviewers
- [ ] Average first-response time confirmed < 10 minutes
- [ ] Zero incidents of ARIA sending something embarrassing or wrong
- [ ] Supervisor sign-off

**This is the exit criteria for Phase 2 → unlocks Phase 3 (auto-send)**

---

## 📋 v1.1 — Phase 3 Begins

**What it will prove:** ARIA can act autonomously for standard cases.

**Done when:**
- [ ] Low-risk intents auto-send without human approval (greeting, positive_signal, onboarding_query)
- [ ] High-risk intents still go to approval queue (pricing_query, objections)
- [ ] Confidence threshold: uncertain drafts go to queue regardless of intent
- [ ] ML classifier trained on real `interactions` data

---

## How to use this file

- When starting a new session: check which checkpoint is current
- When completing a task: tick the relevant box and update `updated:` in frontmatter
- When something blocks a checkpoint: add it to that checkpoint's items
- When a checkpoint is fully done: move it to ✅ and note the date
