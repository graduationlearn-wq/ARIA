---
title: Email Templates
type: technical
tags: [templates, email, attachments, outbound, signature]
updated: 2026-06-22
---

# Email Templates

← [[HOME]] | See also: [[Message Templates]], [[Codebase Map]], [[Lead Sources & Assignment]]

> One-click, stage-aware templated emails. The team picks a template, ARIA fills the `{placeholders}` from the lead + the logged-in sender, attaches the right files, and sends — no retyping in Gmail.

> [!note] Not the same as [[Message Templates]]
> `message_builder.py` builds ARIA's **automated** first-touch / follow-up copy (goes through the approval queue). **This** is a human-driven library for proposals, recaps, welcome mails, etc. — sent directly by a person.

---

## Where it came from

Reps were retyping the same emails (e.g. the BeyondSure proposal + company profile email to RupeeCo) and hand-attaching PDFs. The seeded "Proposal + Company Profile" template mirrors that exact email.

---

## How it works

- `models/email_template.py` — `EmailTemplate(name, stage, subject, body, attachments, is_active)`. `stage` is a canonical pipeline key (or null = any stage), so the right template is **suggested per lead**.
- `services/template_service.py` — `{placeholder}` rendering from the lead + sender; unknown tokens are left visible (so a typo is caught, not silently blank); `signature_image_html(sender, base_url)` builds the sender's signature `<img>`; `seed_templates()` seeds the defaults **idempotently by name** (adds any missing ones, never duplicates, never resurrects a deleted one).
- `routes/templates.py` — CRUD, `/preview` (rendered subject/body for a lead), `/send`, attachment upload/download/delete, `/placeholders`. **Login required.**
- `routes/signatures.py` — per-user signature **image** upload/delete + public serve. See the signature section below.
- `utils/email_sender.py` — sends real attachments as `multipart/mixed`; accepts `from_email` / `from_name` / `reply_to` (visible sender = logged-in member) and `signature_html` (appended to the HTML body).

**Placeholders:** `{lead_name}`, `{company_name}`, `{lead_email}`, `{lead_phone}`, `{lead_type}`, `{state}`, `{chat_link}`, `{meet_link}`, `{demo_preference}`, `{sender_name}`, `{sender_email}`, `{today}`. *(The old `{signature}` text token is retired — signatures are now uploaded images, appended automatically; any legacy `{signature}` in a body renders to nothing.)*

---

## Send-time controls (2026-06-22)

Three additions so a send matches how a rep actually works:

1. **Pick which attachments go** — the compose modal lists a template's attachments as **checkboxes** (existing files pre-ticked; a missing file is disabled). `/send` takes `attachments: [stored_file_names]` — `None` = send all (back-compat), `[]` = send none. The list is whitelisted against the template's own files (no traversal).
2. **Uploaded signature image** — each person uploads their own signature **image** (the branded block from their mail client) once, at **avatar menu → My email signature**. ARIA appends it to the bottom of every template email they send. Per-user, stored in `signature_files/` (gitignored — personal, repo is public), filename on `users.signature_image`. `routes/signatures.py`: `POST/DELETE /signatures/me` (login) + `GET /signatures/{filename}` (used by the dashboard preview). **Embedded inline via CID** at send time (2026-07-07 fix) — `/send` passes the image's file **path** to `send_email(signature_image_path=…)`, which attaches it as a `Content-ID` part (`cid:aria-signature`) inside a `multipart/related`. The image travels **inside** the email, so it renders in every client with **no dependency on a public URL or `BASE_URL`** (this is the porting-friendly form). **Non-blocking warning** in Compose if the sender hasn't uploaded one. *(Superseded the earlier plain-text/branded-template idea, then the hosted-URL form — see [[Decision Log]].)*
3. **Sender = the login email** — `/send` passes the logged-in user's email/name as the message **`From:` and `Reply-To:`**, so the lead sees (and replies to) the real person. The SMTP **envelope sender stays the authenticated account** (SPF/auth stay valid) — only the visible headers change. Deliverability of a custom From depends on the mailbox allowing send-as (fine when the team is all on one domain, e.g. a Hostinger `@beyondsure.in` mailbox); Reply-To routes replies either way.

---

## Seeded templates

8 defaults. Six stage templates (Proposal + Company Profile, Follow-up Nudge, Post-Demo Recap, Commercial Terms, Welcome Aboard, Re-engagement) **plus the client's two** (from `CRM Email Templates.docx`):

- **Post-Demo — Thank You & Next Steps** — has manual fill-in tokens (`{proposal_status}`, `{next_steps}`, `{integration_details}`, `{implementation_timeline}`) that surface in Compose as an "unknown tokens" checklist for the sender to complete before sending.
- **Commercial Proposal** — attaches `Lending_Insurance_Proposal.pdf` (upload the real PDF via Manage templates; it shows "(missing)" until then).

---

## Sending & approval

A template send is **human-initiated → it sends immediately and skips the Approvals queue** (the person clicking send *is* the approval). It's logged as a human-handled outbound `Interaction` with `sender_user_id` set, and blocked for opted-out leads / leads with no email. See [[Decision Log]] (approval queue vs templates are deliberately separate).

---

## Attachments & git

- Upload via the dashboard (Compose → Manage templates). Stored as `t{template_id}__{name}`; filenames sanitized cross-platform (treat `/` and `\` as separators, strip `..`). Download is whitelisted to the template's own files (no traversal).
- **Real company PDFs are gitignored** (`template_files/*`, keep `.gitkeep`) — the repo is public, so documents stay local and are re-uploaded per deployment. The seeded templates reference the real `BeyondSure_Company_Profile.pdf` + `Lending_Insurance_Proposal.pdf` locally.

---

## Dashboard

Open a lead → **"Email the lead" → Compose from template**: the stage-matched template is pre-selected, subject/body arrive filled, attachments shown as **tickable checkboxes**; a note says whether your signature will be added (amber warning if you haven't uploaded one); edit and Send. **Manage templates** (inside Compose) edits copy/stage, uploads attachments. **Avatar menu → My email signature** = the upload space for your signature image (preview + replace + remove). Dashboard assets are at `?v=19`.
