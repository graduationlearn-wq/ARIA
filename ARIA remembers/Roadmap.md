---
title: Roadmap
type: planning
tags: [roadmap, phases, planning]
updated: 2026-06-22
---

# Roadmap

← [[HOME]] | Current status: [[Build Status]] | Milestones: [[Checkpoints]]

## Phase overview

```
Phase 1  ████████████  Rules + scoring + first-touch          ✅ Done
Phase 2  ████████████  Approval + chat + dashboard + team CRM  🔄 Nearly complete (v0.11; deploy + email left)
Phase 3  ░░░░░░░░░░░░  Auto-send + ML classifier               📋 Planned
```

---

## Phase 1 — Foundation ✅

**Goal:** Get the pipeline working end-to-end with a safety net

- [x] Lead ingestion webhook (FB/IG form)
- [x] Lead scoring (3-bucket system)
- [x] Intent classification (rules-based, 14 labels)
- [x] First-touch message builder
- [x] Knowledge base structure + seeder
- [x] Human approval queue (drafts only, no auto-send)
- [x] Email delivery (SMTP)
- [x] Escalation gate (bot_detection + escalation_request)

---

## Phase 2 — Assisted Generation 🔄

**Goal:** ARIA drafts, human approves, system proves itself

- [x] Reply handling with LLM draft generation
- [x] Dual LLM provider (Groq testing / Anthropic production)
- [x] Follow-up scheduler (24hr + 72hr + 7-day) — APScheduler, hourly, IST
- [x] Score decay + re-engagement campaigns for cold leads
- [x] Lead deduplication (email+phone OR match, normalised)
- [x] Chat flow — guided 7-step qualification via `/chat/{token}`
- [x] ARIA→human handoff via Inbox (escalation creates handoff thread)
- [x] Demo booking + confirmation mailer to lead
- [x] Hot lead alert mailer to team (email + WhatsApp scaffold)
- [x] LLM compliance post-processor (scrubs prices, promises, guarantees)
- [x] Lead intelligence dashboard SPA — now wired to the live API (5 views)
- [x] Real login + 3-role hierarchy (employee / team leader / admin), local + Auth0-ready — [[Auth & Hierarchy]]
- [x] 10-stage CRM pipeline + analytics build-out
- [x] Stage-aware email templates with attachments — [[Email Templates]]
- [x] Inbox group chat with per-sender attribution
- [x] Bulk CSV/Excel import + one auto-assignment policy ("within the team") — [[Lead Sources & Assignment]]
- [x] Google + OneDrive/SharePoint sheet sync (15-min poll + refresh button, no API creds) — [[Lead Sources & Assignment]]
- [x] Email template send controls — pick attachments, uploaded signature image, sender = login email — [[Email Templates]]
- [x] Deployment hardening (full checkup → SHIP) — [[Deployment]]
- [x] Test suite — 248 tests, in-memory SQLite, 0 failures
- [ ] Chat resume + 15-day link expiry (designed — not built; token re-entry → AI recap → continue)
- [ ] Email lead ingestion (deferred — awaiting details)
- [ ] Connect FB/IG Lead Ads webhook (real leads auto-flowing in)
- [ ] Fill KB placeholders (21 answers — needs real info from team)
- [ ] Deploy to server (Railway / Render) — set real `SESSION_SECRET`, choose Auth0 vs local

**Exit criteria:** 100+ drafts reviewed, quality consistently good → move to Phase 3

---

## Phase 3 — Autonomy 📋

**Goal:** Remove human approval for standard cases, upgrade intelligence

- [ ] Auto-send low-risk intents (positive_signal, greeting, onboarding_query)
- [ ] Keep human approval for pricing_query and objection intents
- [ ] ML intent classifier trained on real `interactions` data
- [ ] WhatsApp channel live (Sent API — needs team budget approval)
- [ ] A/B message testing
- [ ] Analytics view in dashboard (funnel chart, intent distribution, avg response time)
- [ ] Confidence threshold — low confidence drafts still go to human queue

---

## Parallel track — CRM (now the core, not a side track)

The `leads` / `interactions` / `users` tables are a full multi-user CRM with a 3-role
hierarchy. The dashboard SPA is **live on the API** (auth-gated, scoped per team).
Leads enter via webhook + import today; email/sheet sync is the next channel. See
[[Auth & Hierarchy]] and [[Lead Sources & Assignment]].

---

## Sheet sync — shipped (v0.10)

ARIA polls each leader's sheet ~every 15 min (plus the dashboard refresh button), fetches new
rows, and creates + auto-assigns them through the existing policy. Works for **Google Sheets**
(published-CSV URL) and **OneDrive/SharePoint** (`download=1` → xlsx), no API credentials. See
[[Lead Sources & Assignment]]. Open question (parked): one shared sheet vs. per-leader sheets.

## Next big piece — Chat resume + link expiry (designed, not built)

The `/chat/{token}` link gets a sliding 15-day expiry; the **token** becomes a durable resume
credential. A returning lead re-enters the token (web now; WhatsApp/Facebook later), ARIA
**recaps the conversation so far via the LLM, then continues**. Channel-agnostic — one resume
path, reused by every future channel. Full security model + the corrected "the link never
actually expired" premise are in [[Decision Log]] (2026-06-22).

---

## Technology decisions still open

| Decision | Options | Status |
|----------|---------|--------|
| Lead-email intake | forwarded mailbox · inbound-parse (SendGrid/Mailgun) | **Deferred — awaiting details** |
| Sheet sync | Google published-CSV · OneDrive/SharePoint download | **Done** (both, no API creds) |
| Chat resume mechanism | sliding 15-day expiry + token re-entry + AI recap | **Designed — not built** |
| Resume second factor | token-only · token + email/phone re-confirm | Open (recommend re-confirm after expiry) |
| Auth in production | local seeded users · Auth0 OIDC+RBAC | Pluggable; decide at deploy |
| WhatsApp channel | Cloud API | Scaffolded; needs team credentials |
| Production database | PostgreSQL on Railway / Supabase | Not decided (schema is Postgres-ready) |
| Production hosting | Railway / Render / EC2 | Not decided |
| Email provider | Gmail SMTP (current) / SendGrid | Gmail works for now |
