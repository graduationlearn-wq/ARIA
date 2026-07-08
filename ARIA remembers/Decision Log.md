---
title: Decision Log
type: decisions
tags: [decisions, reasoning, architecture]
updated: 2026-06-14
---

# Decision Log

← [[HOME]]

Every major decision, what we chose, and why. Newest decisions at the top.

---

## 2026-07-07 — Two checkup fixes: signature via CID; failed sends surfaced

**Context:** A `/full-checkup` before handing the features to the CRM developer. Only the two feature-level issues that would carry a real bug into the port were fixed (auth/webhook/rate-limit findings dropped — the CRM owns that infrastructure).

**Fix 1 — signature embedded inline via CID (was a hosted `BASE_URL` `<img>`):** `send_email` now takes `signature_image_path` and attaches the image as a `Content-ID` part (`cid:aria-signature`) inside a `multipart/related`, instead of `<img src="{BASE_URL}/signatures/…">`. **Why:** the hosted form silently fails to render if `BASE_URL` isn't public or the mail client blocks external images — the #1 thing that would break on port. CID puts the image *inside* the email, so it renders everywhere and the ported code only needs the file on disk (no public route, no absolute URL). Removed `signature_image_html()`; the dashboard preview still uses `GET /signatures/{filename}`.

**Fix 3 — failed sends made visible:** genuine send failures now record `send_status="failed"` (scheduler auto-send + the pending-approved retry, which previously stayed silently `"approved"`), and `/approval/stats` returns a `failed` count and lists "Send failed" items (red) in its activity feed — so a lead who never received their email is no longer invisible. Template-send failures were already stored as `"failed"` but shown nowhere; now they surface too.

**Not fixed (CRM owns them):** default-admin seeding, webhook signature verification, rate limiting, object-level authz on `/leads/{id}` mutations, SSRF on sheet URLs. Recorded in the checkup report for the CRM developer.

---

## 2026-06-22 — Signature = an uploaded image, appended on send (not text)

**Decision:** Each team member **uploads their own signature image** (the branded block from their mail client) at avatar menu → My email signature; ARIA appends it to the bottom of every template email they send. Stored per-user in `signature_files/` (gitignored), filename on `users.signature_image`. `routes/signatures.py`: `POST/DELETE /signatures/me` (login) + `GET /signatures/{filename}` (public, so the recipient's mail client can fetch it). Appended as a raw `<img>` in the email HTML (`signature_html`), served from `BASE_URL`. Compose shows a **non-blocking warning** if the sender hasn't uploaded one — never blocks the send.
**Why (supersedes the earlier same-day plan):** I first built a plain-text `{signature}` token, then a branded HTML template with per-user fields. The user's actual example was a rich branded block (logo, colours, title, links) that differs per person — trying to template that is fragile. Letting each person upload their finished signature image is simpler, exactly matches "signature of the person who logs in", and needs no logo extraction or field-by-field modelling. The old `{signature}` text token now resolves to empty for legacy bodies.
**Trade-off:** an image signature isn't clickable, and hosted (`BASE_URL`) images can be blocked by a mail client until "load images" — acceptable for 1:1 sales mail; renders in prod with a real domain.

---

## 2026-06-22 — Template send: pick attachments, sender = login email

**Decision:** Two additions to the human-driven [[Email Templates]] feature:
- **Attachment selection** — `/send` accepts `attachments:[stored_names]` (None = all, [] = none), whitelisted to the template's own files; the compose modal renders them as checkboxes.
- **Sender identity** — the message `From:` and `Reply-To:` carry the logged-in team member's email/name; the SMTP **envelope sender stays the authenticated account** so SPF/auth stay valid.
**Why:** The client asked to send from a template with chosen attachments, from the sender's own address. Keeping the envelope authenticated is the safe way to show a per-user From without breaking delivery.
**Deploy caveat:** a custom visible From only *delivers as-is* when the mailbox allows send-as (fine when the team shares one domain, e.g. a Hostinger `@beyondsure.in` mailbox). Otherwise strict providers may rewrite From — Reply-To still routes replies to the sender.

---

## 2026-06-22 — Default templates seed idempotently by name (+ the client's two)

**Decision:** `seed_templates()` now adds any default template that isn't already present **matched by name**, instead of only seeding when the table is empty. Added the client's two real templates (from `CRM Email Templates.docx`): **Post-Demo — Thank You & Next Steps** and **Commercial Proposal**.
**Why:** The two client templates had to appear even in an existing DB that already held the earlier six. By-name matching also means it never duplicates and never resurrects a template the team deleted (delete is a soft `is_active` flip — the row still exists by name and is skipped). The Post-Demo template intentionally keeps manual fill-in tokens (`{proposal_status}` …) that surface as an "unknown tokens" checklist in Compose.

---

## 2026-06-22 — Chat resume: disposable link, durable token, AI recap *(PROPOSED — not built)*

**Decision (design, awaiting build):** The `/chat/{token}` link becomes **disposable** — a sliding 15-day expiry (every message resets the clock; only *dormant* sessions die). The **token** is the durable resume credential: a returning lead presents it on any channel, ARIA **summarizes the conversation so far, then continues**. The resume logic is **channel-agnostic** — built for web first; future WhatsApp/Facebook buttons call the same path with no rework.
**Why:** From a lead's perspective an always-live link is undesirable; but the chat shouldn't be *lost* either. The conversation already persists server-side under the token (`/chat/{token}/history` rehydrates it; the token never expired before today), so the real gap is only "lead lost the email." A token-resume + recap closes it.
**Corrected premise:** the chat link does *not* currently expire and reopening it already restores full history — so "the chat is lost" wasn't true. Also, ARIA's WhatsApp wiring today is **outbound alerts only**; real two-way lead chat on WhatsApp is a separate, heavier build (Business API inbound), deferred.
**Security model:** token stays unguessable (`uuid4`); on manual resume take it via **POST, not the URL** (keeps it out of logs/history/referrers); `Referrer-Policy: no-referrer` on the chat page; **rate-limit** resume attempts; optional **email/phone re-confirm** after expiry (defense-in-depth if a token leaks); enforce expiry on **both** the page load and the message POST; the recap is the lead's own data only and still runs through the compliance scrub.

---

## 2026-06-22 — Sheet sync with zero API credentials (Google CSV + OneDrive download)

**Decision:** Sync marketing lead sheets by fetching a **public link**, not via any Google/Microsoft API. Google Sheets → the `/export?format=csv` URL; OneDrive/SharePoint → the share link with `download=1` (returns the raw `.xlsx`). The fetcher sniffs the `PK` magic-header to route xlsx → openpyxl vs. text → CSV. One shared `lead_intake.intake_rows()` then dedups/scores/auto-assigns, so re-running a sync needs no "seen rows" marker.
**Why:** "No deploy issues" — no service account, OAuth, or secret to provision; the only requirement is the sheet being shared "anyone with the link can view." OneDrive was added because the test sheet was a personal OneDrive file, not a Google Sheet; a raw fetch of a `1drv.ms` link returns the HTML viewer page (hence the earlier "isn't publicly readable" error), and `download=1` is what yields the actual file.
**Trade-off:** a OneDrive `?e=…` share token changes if the sheet is re-shared, so Google's published-CSV URL is more stable for an unattended poll. *(OneDrive support is local/uncommitted as of this entry.)*

---

## 2026-06-22 — Approval queue and email templates are NOT redundant

**Decision (clarification, no code change):** Keep both. The **approval queue** gates *AI-authored* outbound (first-touch + scheduled follow-ups) — reactive, the human is the checkpoint. **Email templates** are *human-authored, human-initiated* sends (proposal, company profile, demo follow-up) that bypass the queue because the person clicking send *is* the approval. The only overlap is the shared "edit before send" affordance; the trigger, authorship, and reusability differ.
**Why:** Flagged as possibly duplicate. They sit at opposite ends of the same pipe. Natural future seam (not built): a "save this approved draft as a template" button to connect them rather than merge them. (Reaffirms the 2026-06-10 decision below.)

---

## 2026-06-14 — One automated assignment policy for every lead source

**Decision:** Leads are no longer "owned by whoever brought them." They flow into a pool and are auto-assigned on arrival to the least-loaded employee, via a single policy used by every ingestion path (webhook, import, future email/sheet).
**Why:** The meeting reframed reality — a marketing team collects leads centrally and a person *distributes* them to employees. Ownership means "who handles it," not "who sourced it." Automating that distribution is the whole point.
**Scope ("within the team"):** `assignment_pool(user)` decides the candidate set — system sources (webhook/email) and admin → all employees; a team leader's import → their own team; an employee's import → themselves. `next_owner_id(db, among=…)` then picks the least-loaded employee in that set (balanced by current lead count, not blind rotation).
**Rule:** every new lead source plugs into this same policy. Don't reintroduce "owned by the uploader."

---

## 2026-06-14 — Bulk import does NOT create first-touch drafts

**Decision:** Imported leads are created as `new` and scored, but no first-touch draft is queued (unlike webhook leads).
**Why:** A bulk contact list could be hundreds of rows — auto-queuing a draft each would flood the Approvals queue and fire a message per row. Import = "load the list"; the assigned employee chooses when to engage.

---

## 2026-06-14 — Lead import via CSV + Excel, openpyxl lazy-imported

**Decision:** `/leads/import` parses CSV with the stdlib and `.xlsx` with openpyxl, which is imported lazily inside the xlsx path.
**Why:** CSV must work on any deployment with zero extra deps; Excel support shouldn't be a hard dependency that breaks a CSV-only install. Lazy import means a missing openpyxl only affects xlsx uploads, with a clear error.

---

## 2026-06-13 — Email ingestion deferred (pending real-world details)

**Decision:** Build the parser/endpoint for email-sourced leads *later*, once the team clarifies how the marketing emails actually arrive (forwarded mailbox? inbound-parse service? a Google Sheet the marketing team updates, refreshed ~every 15 min?).
**Why:** Too many unknowns to commit a design. The auto-assignment policy is already source-agnostic, so email/sheet will plug straight in when the mechanism is known.

---

## 2026-06-12 — Plot dashboard dates by local (IST) calendar, not UTC

**Decision:** The overview dot chart buckets leads by the viewer's local date. `parseApiDate()` treats naive backend timestamps as UTC, `localDateKey()` formats the local day.
**Why:** Timestamps are stored UTC. A lead created late-evening UTC is "tomorrow" in IST, so it was plotting a day early. Both the lead key and the column key now use local dates so they agree with what the user sees.

---

## 2026-06-12 — Sanitize upload filenames without os.path.basename

**Decision:** Template-attachment filenames are sanitized with pure string ops (treat both `/` and `\` as separators, strip leading dots, collapse `..`).
**Why:** `os.path.basename` only splits on the host OS separator — a Windows-style `..\..\x.pdf` kept its `..` on the Linux CI runner. Pure string handling behaves identically everywhere. (Storage was already safe via the `t{id}__` prefix + download whitelist.)

---

## 2026-06-12 — Deployment hardening: fail fast on insecure config

**Decision:** From the full-checkup audit (NO-SHIP → SHIP): refuse to boot a non-local deployment that still uses the dev `SESSION_SECRET`; mark the session cookie `Secure` on HTTPS; require login on `/scheduler/*` (test-email is admin-only); scope-check approval approve/edit/reject; wrap escalation alert sends so an SMTP/WhatsApp outage can't 500 the lead chat; pin dependencies.
**Why:** The dev default session secret is public in the repo — deploying with it lets anyone forge an admin cookie. `/scheduler/test-email` was an open email relay. These were the real blockers; everything else was already sound.

---

## 2026-06-11 — Inbox is a group chat, sender taken from the session

**Decision:** Any of the lead's chain (owning employee, their team leader, admin) can talk in one thread. Each human message records `sender_user_id` from the logged-in session — never from the client. Bubbles show the sender's name + role, colour-coded by hierarchy.
**Why:** Multiple people handle a lead; the thread must show *who* said what. Taking the sender from the session (not a client field) makes it unforgeable. Scope-checked: only the lead's chain can post. The lead sees only first names — never roles or emails.

---

## 2026-06-10 — Human-composed sends skip the approval queue

**Decision:** Template emails and inbox/group-chat messages send immediately; only ARIA-drafted outbound (first-touch, replies, scheduled follow-ups) go through Approvals.
**Why:** When a person composes and clicks send, they *are* the approval. The queue exists to gate the AI, not to gate humans.

---

## 2026-06-10 — Stage-aware email template library (separate from message_builder)

**Decision:** A new `EmailTemplate` model + `/templates` CRUD/preview/send, with `{placeholders}` filled from the lead + logged-in sender and real file attachments. Templates are keyed to pipeline stages so the right one is suggested per lead.
**Why:** Reps were retyping the same proposal/follow-up emails in Gmail and hand-attaching PDFs. This mirrors their real workflow (the RupeeCo proposal email) as one-click. Distinct from `message_builder.py`, which builds ARIA's automated first-touch/follow-ups. Real attachment files stay out of git (uploaded via the dashboard).

---

## 2026-06-09 — 10-stage canonical pipeline layered over internal status

**Decision:** `services/stages.py` derives a canonical 10-stage CRM pipeline (New → Contacted → Interested → Follow-up → Negotiation → Post Demo → Post Commercial → Parked → Won → Lost) from the lead's internal `status`, without rewiring ARIA's internals.
**Why:** A coworker's CRM uses 8+ stages; analytics only had 4. Layering display-stages over the existing status preserved the working chat/inbox/scheduler (and all tests) while speaking the team's language. Later stages are set manually from the lead detail; ARIA drives the early ones.

---

## 2026-06-08 — Real session auth + 3-role hierarchy (local now, Auth0 at deploy)

**Decision:** Replaced the fake "viewing as" dropdowns with real login. `AUTH_PROVIDER=local` uses seeded email/password (PBKDF2, stdlib — no bcrypt); `AUTH_PROVIDER=auth0` enables Auth0 OIDC + RBAC via lazily-imported authlib. Three roles — employee / team leader (internal role key `manager`) / admin — in a self-referential `manager_id` tree. Scoping (`subtree_ids`) decides who sees whose leads.
**Why:** The team wanted real logins for the 3 levels, and the BeyondSure tech team recommended Auth0/RBAC. Making auth pluggable means local mode needs zero new deploy infra, and Auth0 is a config flip — "no deploy issues" either way.
**Naming:** accounts are role-named (`admin@`/`leader@`/`employee@beyondsure.in`), not personal names — per the team's request.

---

## 2026-06-08 — Dashboard wired to the live API (no more sample data)

**Decision:** Every dashboard panel (leads, approvals, activity, analytics, inbox, notifications, co-pilot, priority) now reads the database via `loadLiveData()`. `data.js` sample content is only a fallback for `file://` preview with no server.
**Why:** The dashboard was display-only sample data; the team needs to see real leads. All render functions read globals that `loadLiveData()` replaces from the API on a 30s refresh.

---

## 2026-05-29 — Multi-file dashboard SPA, not Chart.js single HTML

**Decision:** Dashboard lives in `aria/dashboard/` as 4 separate files (`index.html`, `styles.css`, `data.js`, `app.js`)
**Why:** Maintainable at scale. Logic, data, and styles in separate files. No build step — opens directly in browser.
**Design language:** LoopAI-inspired — off-white `#fafafd` background, 1px hairline card borders, multi-layer shadows, glassmorphic topbar, Inter font with tabular numerals. Deliberately not "typical AI dashboard" look.
**Chart:** Custom SVG dot/scatter chart (not Chart.js). Each dot = one real lead. Single shared `yScale(v)` function ensures y-axis labels and dot positions always align.

---

## 2026-05-29 — ARIA Co-pilot panel replaces chat widget

**Decision:** Right sidebar panel shows ARIA's operational status, not a consumer-style "Hi, how can I help?" chat
**Why:** This is a team CRM dashboard, not a consumer product. The panel shows: how many conversations ARIA is watching/drafting, what decisions need human input, and ARIA's daily stats. Maps directly to backend concepts (approval queue, escalation rows, scheduler jobs).

---

## 2026-05-29 — Inbox shows full ARIA→human conversation thread

**Decision:** When a lead escalates, the Inbox view shows the full conversation with a visual handoff divider
**Why:** Team members need context. Seeing what ARIA said before them prevents "I already answered that" moments. The handoff divider (team member avatar + timestamp) makes the transition point unambiguous.

---

## 2026-05-29 — asynccontextmanager lifespan over deprecated @app.on_event

**Decision:** `main.py` uses `@asynccontextmanager async def lifespan(app)` pattern
**Why:** FastAPI deprecated `@app.on_event("startup")` / `@app.on_event("shutdown")` in 0.93. The `lifespan` context manager is the official replacement. Eliminated deprecation warnings.

---

## 2026-05-29 — Pydantic v2 SettingsConfigDict

**Decision:** `config.py` uses `model_config = SettingsConfigDict(env_file=".env")` instead of inner `class Config`
**Why:** Pydantic v2 deprecated the inner `class Config` pattern. `SettingsConfigDict` is the v2 replacement and eliminates the warning.

---

## 2026-05-27 — LLM post-processor as compliance firewall

**Decision:** Every LLM response goes through `post_process_response()` before reaching a lead
**Why:** LLMs hallucinate specific prices, date promises ("we'll call you tomorrow"), and guarantee language ("you'll definitely get results"). In insurance B2B sales, these could be legally or reputationally damaging. The regex scrub is a hard safety layer — it runs regardless of which LLM provider is active.
**Rule:** Never bypass this. If the scrub is removing useful content, fix the prompt, not the scrub.

---

## 2026-05-27 — Chat token for secure per-lead chat links

**Decision:** Each lead gets a unique `chat_token` (UUID) stored in the `leads` table. Chat links are `{BASE_URL}/chat/{token}`
**Why:** Tokens are unguessable. A lead can only access their own chat. No auth system needed — the token IS the auth. Tokens are included in the first-touch email.

---

## 2026-05-27 — Inline HTML/CSS/JS for chat UI (no frontend build)

**Decision:** The entire chat UI is a string constant `CHAT_HTML` inside `routes/chat.py`. No separate frontend project, no build step, no static file serving.
**Why:** KISS. The chat page is a single screen with one interaction pattern. A full frontend project would add complexity (npm, webpack, deployment coupling) for no benefit at this stage.
**Trade-off:** Editing HTML inside a Python string is annoying. Acceptable for now — if the chat UI grows, extract to a Jinja2 template.

---

## 2026-05-27 — _action key in parse_guided_answer()

**Decision:** `parse_guided_answer()` can return `{"_action": "demo_book" | "reengage" | "escalate" | "demo_confirmed"}` alongside field updates
**Why:** The guided flow sometimes triggers side effects (book demo, create escalation, re-engage) beyond just updating a CRM field. The `_action` key lets the chat route pop the action and branch before applying DB updates. Clean separation: flow logic knows what happened, route logic decides what to do about it.

---

## 2026-05-20 — Score recomputation vs delta distinction

**Decision:** Profile field updates → full `compute_initial_score()` recalculation + re-add engagement delta. Non-profile events → only `apply_engagement_delta()`.
**Why:** Profile fields (lead_type, team_size, uses_software, open_to_platform) change the base score fundamentally. Just applying a delta would compound incorrectly. Engagement events (demo_request, objection) are incremental by nature — full recompute would lose prior engagement history.
**Rule:** Do not break this distinction. The two scoring paths exist for a reason.

---

## 2026-05-07 — Use Groq for testing, Anthropic for production

**Decision:** Support both LLM providers via `LLM_PROVIDER` env variable
**Why:** Groq is free-tier with fast inference (good for dev/testing). Anthropic Claude Haiku is better quality for production. Single toggle, no code change.
**Trade-off:** Groq's Llama models are slightly less consistent than Claude for short persuasive messages.

---

## 2026-05-07 — Human approval mode ON by default

**Decision:** `HUMAN_APPROVAL_MODE=true` is the default
**Why:** Phase 2 — we never auto-send without a human seeing the draft first. Builds trust before going fully autonomous.
**When to change:** After reviewing 100+ approved drafts and confirming quality is consistently good.

---

## 2026-05-07 — SQLite for dev, Postgres-ready schema

**Decision:** Use SQLite locally, but schema is written for Postgres
**Why:** SQLite needs zero setup for development. Just change `DATABASE_URL` in `.env` to switch.

---

## 2026-05-07 — Email first, WhatsApp later

**Decision:** Phase 2 uses email only
**Why:** Email requires no third-party API cost. Sent API (WhatsApp) costs ₹0.015/contact — needs team approval.
**Status:** WhatsApp integration scaffolded (`alert_mailer.py` calls it). Credentials to be added by the team.

---

## 2026-05-07 — Rules-based classifier for Phase 1

**Decision:** Start with keyword matching, not ML
**Why:** No labelled training data yet. Rules-based is explainable, debuggable, fast to iterate. The `interactions` table will accumulate real data for Phase 3 ML training.
**Risk:** Lower accuracy on varied phrasing. Mitigated by synonym coverage in keyword lists.

---

## 2026-05-07 — Escalation skips LLM entirely

**Decision:** `bot_detection` and `escalation_request` bypass AI generation
**Why:** If someone suspects a bot or asks for a human, sending an AI response would be dishonest and damage trust.
**Implementation:** `should_escalate()` check in `webhook.py` and `chat.py` before any LLM call.

---

## 2026-05-07 — B2B framing (agents/brokers), not B2C (insurance buyers)

**Decision:** ARIA talks to insurance *professionals*, not end consumers
**Why:** BeyondSure sells software to agents, not insurance policies to customers. Simpler compliance, no consumer protection framing needed.
