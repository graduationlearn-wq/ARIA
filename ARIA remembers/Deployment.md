---
title: Deployment
type: technical
tags: [deployment, security, hardening, production]
updated: 2026-06-22
---

# Deployment

← [[HOME]] | See also: [[Auth & Hierarchy]], [[Architecture]], [[Build Status]]

> A full-checkup audit (2026-06-12) took ARIA from **NO-SHIP → SHIP**. This note records what was hardened and what's left before going live.

---

## Hardening done (the audit blockers)

| Fix | Where | Why it mattered |
|-----|-------|-----------------|
| **Boot guard on dev secret** | `config.DEV_SESSION_SECRET`, `main._check_production_config()` | The dev `SESSION_SECRET` is public in the repo — deploying with it lets anyone forge an admin cookie. App now **refuses to start** on a non-local `BASE_URL` if the secret is still the default. |
| **Secure session cookie** | `main.py` `SessionMiddleware(https_only=settings.is_https)` | Cookie marked `Secure` on HTTPS so it's never sent over plain HTTP. |
| **Scheduler auth** | `routes/scheduler.py` | `/scheduler/*` now requires login; `test-email` is admin-only — it was an open email relay (anyone could send mail from our domain). |
| **Approval scope** | `routes/approval.py` | approve/edit/reject now scope-checked to the user's team (was login-only). |
| **Alert sends wrapped** | `routes/chat.py` `_alert_team`/`_confirm_demo_to_lead` | An SMTP/WhatsApp outage can no longer 500 the lead-facing chat. |
| **Dependencies pinned** | `requirements.txt` | Reproducible installs. |
| **Cross-platform filenames** | `routes/templates.py` | Upload sanitization no longer depends on the host OS separator (fixed a Linux-CI failure). |

Result: 210 tests pass; the public-by-design surfaces (`/webhook/*`, `/chat/{token}*`, login/register) are intentionally open, everything else is auth-gated.

---

## Before going live — checklist

- [ ] Set a strong `SESSION_SECRET` in prod `.env` (`python -c "import secrets; print(secrets.token_hex(32))"`). The boot guard enforces this on a non-local `BASE_URL`.
- [ ] Set `BASE_URL` to the real `https://…` host (drives the Secure cookie + chat links).
- [ ] Decide auth: keep `local` (replace/disable seeded logins) **or** set `AUTH_PROVIDER=auth0` + the `AUTH0_*` keys.
- [ ] Move `print()` operational logging to the `logging` module.
- [ ] Add Meta webhook **signature verification** on `/webhook/lead` before exposing it publicly.
- [ ] Decide DB: SQLite is fine for the demo; switch `DATABASE_URL` to Postgres for real concurrency (schema is Postgres-ready).
- [ ] Re-upload template attachment PDFs (gitignored — not in the repo), incl. the real proposal PDF on the Commercial Proposal template.
- [ ] **Email sender (per-user From):** template sends set `From:`/`Reply-To:` to the logged-in user. For that address to *deliver as-is*, the SMTP mailbox must allow send-as — cleanest when the whole team is on one domain (e.g. a Hostinger `@beyondsure.in` mailbox that authenticates and is allowed to send for its users). Otherwise strict providers rewrite From; Reply-To still routes replies. Confirm this when wiring the real SMTP creds.
- [ ] **Signature images:** each user re-uploads their signature (avatar menu → My email signature) — `signature_files/` is gitignored, so it's empty on a fresh deploy. Images are served from `BASE_URL/signatures/…`, so `BASE_URL` must be publicly reachable for them to render in recipients' inboxes.
- [ ] If using Auth0: do a quick login test against the tenant before going live.

---

## Verify-after-deploy smoke test

1. `GET /` → 200, `scheduler: running`.
2. `GET /leads/` without a cookie → **401**.
3. `GET /scheduler/status` without a cookie → **401** (confirms the scheduler-auth fix shipped).
4. Log in as admin → see all leads; as employee → only their own.
5. Confirm the `session` cookie shows `Secure` + `HttpOnly` in dev-tools.
6. Send one template email to yourself → arrives with attachments.
7. Open a chat link, escalate, reply from the Inbox → lead sees the team message with the sender's first name.

---

## Idempotent migrations

`database._run_light_migrations()` adds new columns with guarded `ALTER TABLE` (currently `leads.meet_link`, `leads.owner_id`, `interactions.sender_user_id`, `users.signature_image`). Deploying onto an existing DB just works — additive and re-runnable. Keep a pre-deploy DB snapshot anyway; rollback = redeploy the previous commit (older code ignores the new nullable columns).
