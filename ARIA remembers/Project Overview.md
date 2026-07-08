---
title: Project Overview
type: context
tags: [overview, beyondsure, aria, b2b]
updated: 2026-06-14
---

# Project Overview

← [[HOME]]

## The company

**BeyondSure** sells a SaaS platform to insurance professionals — agents, brokers, POSP advisors, and IMF operators. The platform helps them manage leads, clients, policies, and commissions.

> [!important] B2B, not B2C
> ARIA talks to *insurance professionals* (potential platform customers), NOT to end consumers buying insurance. This distinction matters for tone, message content, and compliance scope.

## The problem ARIA solves

BeyondSure gets leads from many channels — Facebook/Instagram ads, and a tied-up
marketing team that collects leads and sends them in (sheets, enquiry emails). Before ARIA:

- Average time from lead submission to first response: **202 days**
- Connection rate: **7%**
- Process: leads sat in a spreadsheet; a person manually assigned them to staff and followed up (or didn't)

ARIA brings first response down to **under 5 minutes** and **automates both the intake and the assignment**.

## What ARIA does

```
Lead arrives — FB/IG webhook · CSV/Excel import · (email/sheet planned)
        ↓
ARIA dedups → creates Lead record → scores it (0–100, hot/warm/cold)
        ↓
AUTO-ASSIGNS to the least-loaded employee in the right team   ← see [[Lead Sources & Assignment]]
        ↓
(webhook) builds a personalised first-touch draft
        ↓
Human reviews draft → approves / edits / rejects   (Phase 2 — [[Auth & Hierarchy]] scopes who sees what)
        ↓
Email sent to lead → lead replies → ARIA classifies intent → KB + LLM draft → approve → sent
        ↓
Lead can chat (/chat/{token}); when they want a person → escalates to the Inbox,
where the assigned employee, their team leader, and admin work it as a group chat
```

## Lead types ARIA handles

| Type | Description | Score weight |
|------|-------------|-------------|
| Broker | Licensed insurance broker | Highest |
| IMF | Insurance Marketing Firm | High |
| Agent | Individual insurance agent | Medium |
| POSP Advisor | Point of Sales Person | Lower |
| Invalid | Bad/spam entry | Heavily penalised |

## Channels

- **Lead intake (now):** FB/IG webhook · CSV/Excel import. **Planned:** email enquiries / Google Sheet sync (~15-min auto-fetch), WhatsApp.
- **Outbound (now):** Email (smtplib / Gmail SMTP) — automated drafts via the approval queue, plus one-click [[Email Templates]] and a live Inbox chat.
- **Planned:** WhatsApp via Cloud API (scaffolded; needs team credentials).

## Compliance notes

- IRDAI regulations apply (Indian insurance regulator)
- DPDP Act (India's data protection law) requires consent logging
- All leads have `consent_logged_at` timestamp in the DB
- Opt-out is respected — `opt_out = True` stops all further contact
- ARIA never claims to be human unless directly asked

## Key files outside the codebase

| File | Location |
|------|----------|
| `ARIA_Lead_Analysis.docx` | `ARIA/Architecture/` — 6-page report with 4 charts |
| `ARIA_Knowledge_Base.xlsx` | `ARIA/Architecture/` — 25 FAQ entries |
| `Sample Sheet for CRM.xlsx` | `~/Downloads/` — marketing's example lead sheet (basis for the planned Sheet sync) |
| `seed_demo.py` | `ARIA/aria/` — run to load the full demo org + leads with history |
