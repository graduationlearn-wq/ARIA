---
title: Lead Sources & Assignment
type: technical
tags: [leads, ingestion, import, assignment, pipeline, sheets]
updated: 2026-06-22
---

# Lead Sources & Assignment

← [[HOME]] | See also: [[Architecture]], [[Auth & Hierarchy]], [[Lead Scoring]]

> Leads enter from several channels into one pool. Whatever the source, ARIA dedups, scores, and **auto-assigns** the lead to a team member on arrival. Ownership = who handles it, not who sourced it.

---

## The model shift (2026-06-14)

ARIA originally treated a lead as *owned by whoever brought it* (webhook round-robin; imports belonged to the uploader). A meeting reframed reality: a marketing team collects leads centrally and a person used to **distribute** them to employees. So:

- Ownership now means **"who's assigned to handle it."**
- There is **one assignment policy**, applied at every entry point.
- "Brought by" wording became **"Assigned to"** across the UI.

---

## Sources

| Source | Endpoint / mechanism | Status | First-touch draft? |
|--------|----------------------|--------|--------------------|
| FB/IG Lead Ads | `POST /webhook/lead` | live (test payloads; real ad webhook pending) | yes (queued to Approvals) |
| CSV / Excel file | `POST /leads/import` (+ `/import-template`) | **live** | **no** (bulk list — don't flood the queue) |
| Google / OneDrive sheet | `/sheets/*` + 15-min scheduler job | **live** | **no** (bulk source) |
| Email enquiries | parser + endpoint | **deferred** — awaiting details | TBD |

All sources share dedup (email+phone OR match, normalised) and `score_lead()`, and route through the same `lead_intake.intake_rows()` → auto-assignment.

---

## Bulk import (`services/lead_importer.py`)

- **CSV** parsed with the stdlib; **`.xlsx`** with openpyxl, **lazy-imported** inside the xlsx path (so CSV works with zero extra deps; xlsx-only installs get a clear message).
- **Flexible headers** — matched case/space/underscore-insensitively against alias sets: e.g. `Name`/`Full Name`, `Phone`/`Mobile`, `Company`/`Organisation`, `Type`, `Source`, `Team Size`, `Wants Demo`, `Website`. Unknown columns ignored.
- **Validation** per row (needs a name + email or phone); bad rows reported with row number + reason.
- **Dedup** against the whole DB and within the file.
- `template_csv()` powers the "Download template" link.

UI: **Import** button on the Leads view → modal with file picker, template link, and an imported / duplicate / skipped + distribution summary.

---

## Auto-assignment policy ("within the team")

Two functions in `services/auth_service.py`:

- **`assignment_pool(user, db)`** → the candidate employee set, by source/role:
  - system sources (webhook / future email-sheet) or **admin** → `None` = **all** active employees
  - **team leader** import → **their own team**
  - **employee** import → **themselves**
- **`next_owner_id(db, among=…)`** → the **least-loaded** employee in that set (balanced by current lead count — not blind rotation), `lead.owner_id` set on arrival.

Import distributes in-memory across the pool (preload counts once, then balance), so a 30-row file spreads evenly. Verified live: admin's import of 8 balanced across all employees; a team leader's import of 6 stayed inside their team.

> [!note] Rule
> Every new lead source must route through this same policy. Don't reintroduce "owned by the uploader."

---

## The 10-stage pipeline (`services/stages.py`)

A canonical display pipeline derived from the lead's internal `status` — added so ARIA speaks the same language as the coworker's CRM without rewiring internals:

```
New → Contacted → Interested → Follow-up → Negotiation →
Post Demo Follow-Up → Post Commercial Follow-Up → Parked → Won → Lost
```

- `lead_stage(lead)` maps internal status → canonical stage (e.g. `needs_human` → Post Demo if a demo exists, else Follow-up; `converted` → Won; `invalid` → Lost).
- ARIA auto-drives the early stages; the later/human stages are set from the lead-detail **stage dropdown**.
- Analytics renders a **stage-count grid** + a **cumulative funnel** (Parked/Lost are off-track) + source mix + score histogram + weekly + cohorts.

---

## Sheet sync — live (`services/sheet_sync.py`, `routes/sheets.py`)

Marketing maintains lead sheets (sample: `Sample Sheet for CRM.xlsx` — the Meta/Facebook Lead Ads export). ARIA now syncs them with **no API credentials** — the sheet just has to be shared "anyone with the link can view".

- **Model** `models/sheet_source.py` — `name`, `sheet_url`, `owner_user_id`, `is_active`, plus `last_synced_at` / `last_status` / `last_imported` / `total_imported` status fields.
- **CRUD + sync** `routes/sheets.py` — `/sheets/` CRUD, `/{id}/sync`, `/sync-all`. Scoped: admin all · team leader own · employee none. A leader owns their own sheet; admin can assign one to a leader.
- **Two source types, auto-detected by URL:**
  - **Google Sheets** → `to_csv_url()` rewrites the edit/share URL to its `/export?format=csv` link.
  - **OneDrive / SharePoint** (`1drv.ms`, `onedrive.live.com`, `sharepoint.com`) → `to_download_url()` appends `download=1`, which returns the raw `.xlsx` (a plain fetch returns the HTML viewer page). *(2026-06-22)*
  - `fetch_csv()` fetches the bytes; `sync_source()` **sniffs the `PK` header** → routes `.xlsx` to openpyxl, everything else to the CSV parser.
- **Shared intake** — fetched rows go through `services/lead_intake.intake_rows()`, the same create/dedup/score/auto-assign path the file import uses. Dedup across the whole DB means re-running a sync only creates genuinely new rows (no "seen rows" marker needed).
- **Two triggers:** the 15-min scheduler job `run_sheet_sync()` (own DB session, never raises — errors land in `last_status`), and the dashboard's top-right **refresh** button (`/sheets/sync-all`, disabled while running so it can't be spammed).

> [!note] OneDrive is a bearer link
> `download=1` works only while the share is public; the `?e=…` token in a OneDrive URL changes if the sheet is re-shared. Google's published-CSV URL is the more stable choice for an unattended poll.

**Open question (parked):** one shared marketing sheet vs. each leader owning their own — current design assumes per-leader sheets.
