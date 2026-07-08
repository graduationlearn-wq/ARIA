---
title: ARIA — Master Index
type: MOC
tags: [index, moc, aria]
updated: 2026-06-22
---

# ARIA — BeyondSure Lead Engine

> AI-powered lead engagement system. Leads arrive from many channels → ARIA scores them → auto-assigns to a team member → drafts responses → human approves → sends. A real team hierarchy works the leads through a shared inbox.

## What is this vault?

This vault is the living brain of the ARIA project. Every decision, every file, every design choice is documented here. When you pick this project back up after a break — or hand it to someone else — this is where you start.

---

## 🗺️ Navigate the vault

| Note | What's inside |
|------|--------------|
| [[Project Overview]] | What ARIA does, who it's for, why we built it |
| [[Architecture]] | System layers, data flow, tech stack |
| [[Codebase Map]] | Every file explained in one place |
| [[Auth & Hierarchy]] | Login, the 3-role tree, scoping, team management |
| [[Lead Sources & Assignment]] | Every way a lead enters + how it's auto-assigned |
| [[Dashboard]] | The team dashboard — views, login, modals, live data |
| [[Email Templates]] | Stage-aware one-click templated emails with attachments |
| [[Lead Scoring]] | How leads get a score and quality rating |
| [[Intent Labels]] | All the intents ARIA can detect |
| [[Message Templates]] | First-touch and follow-up message logic |
| [[Data Insights]] | What the real BeyondSure lead data told us |
| [[Deployment]] | Production hardening + go-live checklist |
| [[Decision Log]] | Every major call we made and why |
| [[Build Status]] | What's built, what's pending, known issues |
| [[Roadmap]] | Phase 1→2→3 plan |
| [[Checkpoints]] | Named milestones with clear done-criteria (v0.1 → v1.1) |

---

## 🔢 Quick numbers

- **202 days** — average gap between lead creation and first response (before ARIA)
- **7%** — connection rate on existing leads
- **< 5 minutes** — ARIA's target first-response time
- **251** tests passing (0 failures, 1 library warning unfixable)
- **3-role hierarchy** — admin · team leader · employee
- **5** dashboard views, all live on the database: Overview · Leads · Inbox · Approvals · Analytics
- **4** lead sources: FB/IG webhook · CSV/Excel import · Google + OneDrive sheet sync (all live) · email (deferred)
- **10-stage** canonical CRM pipeline (New → … → Won / Lost)
- **25** FAQ entries in the knowledge base (4 real, 21 placeholder)

---

## 🚦 Current status

```
Phase 1 ✅  Rules-based intent classifier                  (v0.1–v0.2)
Phase 2 ✅  Human approval mode + reply loop               (v0.2)
Phase 2 ✅  Follow-up scheduler (24hr + 72hr + 7d)         (v0.3)
Phase 2 ✅  Live ready — SMTP + real lead test             (v0.4)
Phase 2 ✅  Chat flow + dedup + audit + P0 fixes           (v0.5/v0.6)
Phase 2 ✅  Dashboard SPA, now wired to live API           (v0.7)
Phase 2 ✅  Auth + 3-role hierarchy + login (local/Auth0)  (v0.8)
Phase 2 ✅  Stage-aware email templates + attachments      (v0.8)
Phase 2 ✅  Inbox group chat (per-sender attribution)      (v0.8)
Phase 2 ✅  Deployment hardening (full checkup → SHIP)     (v0.8)
Phase 2 ✅  Bulk import (CSV/Excel) + auto-assignment       (v0.9)
Phase 2 ✅  Google + OneDrive sheet sync (~15-min)          (v0.10)
Phase 2 ✅  Template send: attachments + signature + sender  (v0.11 current)
Phase 2 ⏳  Chat resume + 15-day link expiry — designed     (v0.12, not built)
Phase 2 ⏳  Email lead ingestion — deferred (awaiting details)
Phase 2 ⏳  Connect FB/IG webhook to real ads               (next)
Phase 2 ⏳  Fill KB placeholders (21 answers) — needs team  (blocker)
Phase 3 📋  ML intent classifier — planned                 (v1.1)
```

---

## 👤 Context

- **Built by:** Arnav (intern) for the **BeyondSure** team
- **Company:** BeyondSure — sells a SaaS platform to insurance agents, brokers, POSP advisors, IMF operators ("Click. Cover. Relax.")
- **How leads reach them today:** a tied-up marketing team collects leads and sends them in (forms, sheets, enquiry emails); a person used to assign them manually — ARIA now automates that
- **Stack:** FastAPI + SQLite + Anthropic/Groq + smtplib + session auth (Auth0-ready)
- **Repo:** https://github.com/graduationlearn-wq/ARIA
- **Latest pushed commit:** `4bd794e` — feat: template send controls + per-user uploaded email signatures (attachment selection · uploaded signature image · sender-as-login).
- **Demo logins (local auth):** `admin@beyondsure.in` / admin123 · `leader@beyondsure.in` / leader123 · `employee@beyondsure.in` / employee123 (run `python seed_demo.py` for the full demo org + leads)
- **Live-test data:** a real admin login + a test lead were seeded into the local `aria.db` for end-to-end email testing. The actual credentials are kept out of the repo (aria.db is gitignored).
