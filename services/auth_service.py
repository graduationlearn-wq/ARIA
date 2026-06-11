"""
Auth & hierarchy service.

Password hashing uses the stdlib (PBKDF2-HMAC-SHA256) — no extra packages.
Scoping turns a logged-in user into the set of owner_ids whose leads they may
see, honouring the 3-level hierarchy and an optional "viewing as" drill-down.
"""

import hashlib
import hmac
import os

from sqlalchemy.orm import Session

from models.user import User
from models.lead import Lead


# ── Password hashing (PBKDF2, stdlib) ─────────────────────────────────────────

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


# ── Hierarchy scoping ─────────────────────────────────────────────────────────

def subtree_ids(user: User, db: Session) -> set[int] | None:
    """
    The owner_ids whose leads `user` may see.
    Returns None for admin (means: everyone, no filter).
    """
    if user.role == "admin":
        return None
    if user.role == "manager":
        reports = db.query(User.id).filter(User.manager_id == user.id).all()
        return {user.id} | {r[0] for r in reports}
    return {user.id}  # employee → only their own


def resolve_scope(user: User, db: Session, as_user_id: int | None) -> set[int] | None:
    """
    Combine the user's own scope with an optional "viewing as" drill-down.
    Returns None (no filter / everyone) or a set of owner_ids to filter on.
    """
    allowed = subtree_ids(user, db)

    if not as_user_id:
        return allowed

    # Can the user even view this person? (admin: yes; others: must be in scope)
    if allowed is not None and as_user_id not in allowed:
        return allowed  # not permitted — ignore the drill-down

    target = db.query(User).filter(User.id == as_user_id).first()
    if not target:
        return allowed
    return subtree_ids(target, db)  # narrow to the target's own subtree


def viewable_users(user: User, db: Session) -> list[User]:
    """Users that should appear in this user's 'viewing as' selector."""
    if user.role == "admin":
        return db.query(User).filter(User.is_active == True).order_by(User.role, User.name).all()  # noqa: E712
    if user.role == "manager":
        ids = subtree_ids(user, db)
        return db.query(User).filter(User.id.in_(ids)).order_by(User.role, User.name).all()
    return [user]


def public_user(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "manager_id": u.manager_id,
        "avatar_seed": u.avatar_seed or u.name,
    }


# ── Round-robin lead ownership ────────────────────────────────────────────────

def next_owner_id(db: Session) -> int | None:
    """
    Pick the active employee with the fewest leads (balanced round-robin).
    Returns None if there are no employees yet (e.g. in tests).
    """
    employees = db.query(User).filter(
        User.role == "employee", User.is_active == True  # noqa: E712
    ).all()
    if not employees:
        return None
    counts = {
        e.id: db.query(Lead).filter(Lead.owner_id == e.id).count()
        for e in employees
    }
    return min(counts, key=counts.get)


# ── Seeding the demo org ──────────────────────────────────────────────────────

# Role-named accounts — the internal role key for a team leader stays "manager".
DEFAULT_USERS = [
    # name,          email,                     role,        password,      reports_to (email or None)
    ("Admin",        "admin@beyondsure.in",     "admin",     "admin123",    None),
    ("Team Leader",  "leader@beyondsure.in",    "manager",   "leader123",   "admin@beyondsure.in"),
    ("Employee",     "employee@beyondsure.in",  "employee",  "employee123", "leader@beyondsure.in"),
]

# Old seeded identities → role-named ones (one-time fix-up for existing dev DBs).
_DEMO_UPGRADES = [
    # match email,             match name,        new name,      new email,              new password
    ("admin@beyondsure.in",    "Kunal",           "Admin",       None,                   None),
    ("manager@beyondsure.in",  "Mohammad Faizan", "Team Leader", "leader@beyondsure.in", "leader123"),
    ("employee@beyondsure.in", "Rushal K",        "Employee",    None,                   None),
]


def _upgrade_demo_users(db: Session) -> None:
    """Rename previously-seeded demo users to role-based identities. Idempotent —
    only touches rows that still carry the exact old seeded name + email."""
    changed = False
    for email, old_name, new_name, new_email, new_password in _DEMO_UPGRADES:
        u = db.query(User).filter(User.email == email, User.name == old_name).first()
        if not u:
            continue
        u.name = new_name
        u.avatar_seed = new_name
        if new_email:
            u.email = new_email
        if new_password:
            u.password_hash = hash_password(new_password)
        changed = True
    if changed:
        db.commit()
        print("[Auth] Upgraded demo users to role-based identities (admin/leader/employee).")


def seed_users(db: Session) -> None:
    """Create the 3-level demo org if no users exist. Idempotent."""
    if db.query(User).count() > 0:
        _upgrade_demo_users(db)
        return

    by_email: dict[str, User] = {}
    # First pass — create everyone
    for name, email, role, password, _ in DEFAULT_USERS:
        u = User(
            name=name, email=email, role=role,
            password_hash=hash_password(password), avatar_seed=name,
        )
        db.add(u)
        by_email[email] = u
    db.flush()

    # Second pass — wire the hierarchy
    for name, email, role, password, reports_to in DEFAULT_USERS:
        if reports_to and reports_to in by_email:
            by_email[email].manager_id = by_email[reports_to].id

    db.commit()
    print("[Auth] Seeded 3 demo users (admin/leader/employee).")


def map_auth0_role(roles) -> str:
    """Map an Auth0 roles claim (list or string) to ARIA's 3 roles."""
    if isinstance(roles, str):
        roles = [roles]
    roles = [str(r).lower() for r in (roles or [])]
    if "admin" in roles:
        return "admin"
    if "manager" in roles:
        return "manager"
    return "employee"


def upsert_oauth_user(db: Session, sub: str, email: str, name: str, role: str) -> User:
    """
    Create or update the local User row that mirrors an Auth0 identity.
    Auth0 owns identity + role; ARIA owns the org tree + lead ownership, linked
    by email (stable across logins). The role always reflects the Auth0 claim.
    """
    email = (email or "").lower().strip()
    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None:
        user = User(name=name or email, email=email, password_hash="", role=role,
                    avatar_seed=name or email, is_active=True)
        db.add(user)
    else:
        user.name = name or user.name
        user.role = role  # keep ARIA's role in sync with Auth0 RBAC
        user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def assign_unowned_leads(db: Session) -> None:
    """Give any existing owner-less leads to employees round-robin (demo backfill)."""
    employees = db.query(User).filter(
        User.role == "employee", User.is_active == True  # noqa: E712
    ).all()
    if not employees:
        return
    unowned = db.query(Lead).filter(Lead.owner_id.is_(None)).all()
    for i, lead in enumerate(unowned):
        lead.owner_id = employees[i % len(employees)].id
    if unowned:
        db.commit()
