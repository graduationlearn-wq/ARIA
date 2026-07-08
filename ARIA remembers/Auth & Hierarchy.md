---
title: Auth & Hierarchy
type: technical
tags: [auth, rbac, hierarchy, users, security]
updated: 2026-06-14
---

# Auth & Hierarchy

← [[HOME]] | See also: [[Architecture]], [[Codebase Map]], [[Lead Sources & Assignment]], [[Deployment]]

> ARIA is a multi-user CRM with a 3-level org tree. Login is required for everything except the public lead-facing surfaces. Who you are decides whose leads you can see.

---

## The three roles

| Role | Internal key | Sees | Can do |
|------|-------------|------|--------|
| **Admin** | `admin` | Everyone's leads | Everything + change roles / reporting in **Team & roles** |
| **Team Leader** | `manager` | Their own team's leads (self + direct reports) | Reassign within team, approve their team's drafts |
| **Employee** | `employee` | Only their own leads | Work their leads; can't reassign to others |

The tree is a self-referential `users.manager_id`. Admin sits at the top (`manager_id = NULL`).
Note the **display name is "Team Leader"** but the internal role key is `manager` (don't rename the key — it's wired through scoping, seeds, and tests).

---

## Scoping — who sees whose leads

`services/auth_service.py`:

- `subtree_ids(user, db)` → set of user ids whose leads this user may see. **Admin → `None`** (means "everyone, no filter"). Manager → `{self} ∪ direct reports`. Employee → `{self}`.
- `resolve_scope(user, db, as_user)` → combines that with the optional "viewing as" drill-down (`?as=` query param) the dashboard sends.
- Every leads/approval/chat-admin endpoint filters `Lead.owner_id.in_(scope)` when scope isn't `None`.

The dashboard "viewing as" dropdowns are role-aware (admin: Team Leader → Employee; leader: their team; employee: none). See [[Dashboard]].

---

## Login providers (pluggable — `AUTH_PROVIDER`)

| Mode | How | Deps |
|------|-----|------|
| `local` (default) | Seeded email/password. PBKDF2-HMAC-SHA256 hashing in the stdlib (no bcrypt/passlib). Session cookie via Starlette `SessionMiddleware` + itsdangerous. | none new |
| `auth0` | Auth0 OIDC + RBAC. `GET /auth/login` → redirect, `/auth/callback` exchanges the code, role comes from a custom claim (`map_auth0_role`), `upsert_oauth_user` mirrors the identity into the local `users` tree by email. | authlib (lazy-imported) |

Chosen so local needs **zero new deploy infra** and Auth0 is a config flip — "no deploy issues" either way. The BeyondSure tech team asked for Auth0/RBAC; it's ready when they want it.

---

## Endpoints (`routes/auth.py`)

| Endpoint | Who | Purpose |
|----------|-----|---------|
| `POST /auth/login` | public | Local email/password → session |
| `POST /auth/register` | public | Self-service signup → joins as **Employee, unassigned** |
| `POST /auth/logout` | any | Clears the session |
| `GET /auth/me` | login | Current user + the people they can "view as" |
| `GET /auth/config` | public | Tells the login screen local vs auth0 |
| `GET /auth/login` · `/auth/callback` | public | Auth0 OIDC redirect flow |
| `PATCH /auth/users/{id}` | **admin** | Change a user's role / reports-to |

`get_current_user` (the dependency) reads `request.session["user_id"]` → 401 if missing/inactive.

---

## Team & roles editor guards

`PATCH /auth/users/{id}` (admin only) refuses moves that would corrupt the tree:
- **No self-demotion** — you can't change your own role.
- **No orphaned team** — a manager with reports can't be demoted to employee until their people are moved (promoting up to admin is fine).
- **No reporting loops** — walks up the chain to reject cycles; people can only report to a manager or admin; nobody reports to themselves.

---

## Seeded demo org

`seed_users()` (startup) creates 3 role-named accounts; `_upgrade_demo_users()` renames any old personal-named seeds in place. `seed_demo.py` extends this to 2 leaders + 4 employees. Accounts are role-named on purpose (the team asked not to use personal names):

| Login | Password | Role |
|-------|----------|------|
| `admin@beyondsure.in` | admin123 | Admin |
| `leader@beyondsure.in` / `leader2@beyondsure.in` | leader123 | Team Leader |
| `employee@beyondsure.in` … `employee4@beyondsure.in` | employee123 | Employee |

> [!warning] These are demo credentials. Before production: set a real `SESSION_SECRET` (the boot guard enforces it on a non-local deploy) and replace/disable the seeded logins. See [[Deployment]].

---

## Why this matters for assignment

Ownership (`lead.owner_id`) = the assigned handler, and the same hierarchy decides
the **auto-assignment pool** (`assignment_pool`). A team leader's imported leads
spread only across their team; system sources spread across everyone. Full detail in
[[Lead Sources & Assignment]].
