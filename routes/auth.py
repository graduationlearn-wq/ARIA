"""
Auth routes — login / logout / who-am-I, plus the get_current_user dependency
used to protect and scope the internal dashboard endpoints.

Public endpoints (no auth): /webhook/*, /chat/*, /auth/login, the /ui static SPA.
Everything else expects a logged-in user via the signed session cookie.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import User
from services.auth_service import (
    hash_password, verify_password, viewable_users, public_user, resolve_scope,
    map_auth0_role, upsert_oauth_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Auth0 OIDC client (lazy — authlib only loaded when auth_provider="auth0") ──

_oauth = None


def _auth0_client():
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth  # lazy import
        oauth = OAuth()
        oauth.register(
            name="auth0",
            client_id=settings.auth0_client_id,
            client_secret=settings.auth0_client_secret,
            server_metadata_url=f"https://{settings.auth0_domain}/.well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email"},
        )
        _oauth = oauth
    return _oauth.auth0


# ── Dependency: current logged-in user ────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == uid).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ── Models ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class UserUpdate(BaseModel):
    role: str | None = None
    manager_id: int | None = None


VALID_ROLES = {"employee", "manager", "admin"}
MIN_PASSWORD_LENGTH = 6


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config")
def auth_config():
    """Public — lets the login screen render the right UI (local form vs Auth0)."""
    return {"provider": settings.auth_provider}


@router.post("/login")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """Local email/password login. (Auth0 mode uses the GET redirect flow.)"""
    if settings.auth_provider == "auth0":
        raise HTTPException(status_code=400, detail="This deployment uses Auth0 — use Sign in with Auth0")
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    request.session["user_id"] = user.id
    return {"user": public_user(user), "viewable": [public_user(u) for u in viewable_users(user, db)]}


@router.post("/register")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Self-service signup (local auth only). New people join as Employee with no
    team yet — the admin assigns their role and team leader in Team & roles.
    """
    if settings.auth_provider == "auth0":
        raise HTTPException(status_code=400, detail="Accounts are managed in Auth0 — ask your admin for an invite")

    name = body.name.strip()
    email = body.email.lower().strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="That email is already registered — sign in instead")

    user = User(name=name, email=email, role="employee",
                password_hash=hash_password(body.password), avatar_seed=name)
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    return {"user": public_user(user), "viewable": [public_user(u) for u in viewable_users(user, db)]}


# ── Auth0 OIDC redirect flow ──────────────────────────────────────────────────

@router.get("/login")
async def login_redirect(request: Request):
    """Auth0 mode: kick off the OIDC redirect. Local mode: just go to the app."""
    if settings.auth_provider != "auth0":
        return RedirectResponse(url="/ui/")
    client = _auth0_client()
    redirect_uri = settings.base_url.rstrip("/") + "/auth/callback"
    kwargs = {}
    if settings.auth0_audience:
        kwargs["audience"] = settings.auth0_audience
    return await client.authorize_redirect(request, redirect_uri, **kwargs)


@router.get("/callback")
async def auth0_callback(request: Request, db: Session = Depends(get_db)):
    """Auth0 redirects here with the code; exchange it, upsert the user, log in."""
    client = _auth0_client()
    token = await client.authorize_access_token(request)
    info = token.get("userinfo") or await client.userinfo(token=token)
    role = map_auth0_role(info.get(settings.auth0_roles_claim, []))
    user = upsert_oauth_user(
        db, sub=info.get("sub"), email=info.get("email"),
        name=info.get("name") or info.get("email"), role=role,
    )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/ui/")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    resp = {"status": "logged_out"}
    if settings.auth_provider == "auth0" and settings.auth0_domain:
        # Optional: clear the Auth0 SSO session too.
        resp["auth0_logout"] = (
            f"https://{settings.auth0_domain}/v2/logout"
            f"?client_id={settings.auth0_client_id}"
            f"&returnTo={settings.base_url.rstrip('/')}/ui/"
        )
    return resp


@router.get("/me")
def me(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current user + the people they can drill into (for the 'viewing as' selector)."""
    fn = current.signature_image
    return {
        "user": public_user(current),
        "viewable": [public_user(u) for u in viewable_users(current, db)],
        "signature_image": fn or None,                       # uploaded signature filename
        "signature_url": f"/signatures/{fn}" if fn else None,  # to preview it
    }


# ── Team management (admin only) ──────────────────────────────────────────────

@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change a team member's role or who they report to. Admin only.
    The org tree drives what everyone sees, so this is guarded carefully:
    no self-demotion, no orphaning a manager's team, no reporting loops.
    """
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Only an admin can change roles")

    target = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    fields = body.model_fields_set

    if "role" in fields and body.role and body.role != target.role:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Unknown role '{body.role}'")
        if target.id == current.id:
            raise HTTPException(status_code=400, detail="You can't change your own role")
        # Demoting to employee would orphan their team; moving up (admin) is fine.
        if target.role == "manager" and body.role == "employee":
            reports = db.query(User).filter(
                User.manager_id == target.id, User.is_active == True  # noqa: E712
            ).count()
            if reports:
                raise HTTPException(
                    status_code=400,
                    detail=f"{target.name} still has {reports} team member(s) — move them to another team leader first",
                )
        target.role = body.role
        if body.role == "admin":
            target.manager_id = None  # admins sit at the top of the tree

    if "manager_id" in fields and target.role != "admin":
        mid = body.manager_id
        if mid is None:
            target.manager_id = None
        else:
            if mid == target.id:
                raise HTTPException(status_code=400, detail="Someone can't report to themselves")
            boss = db.query(User).filter(User.id == mid, User.is_active == True).first()  # noqa: E712
            if not boss:
                raise HTTPException(status_code=404, detail="Manager not found")
            if boss.role not in ("manager", "admin"):
                raise HTTPException(status_code=400, detail="People can only report to a team leader or an admin")
            # Walk up from the new boss — if we reach the target, it's a loop.
            seen = {target.id}
            node = boss
            while node:
                if node.id in seen:
                    raise HTTPException(status_code=400, detail="That would create a reporting loop")
                seen.add(node.id)
                node = (db.query(User).filter(User.id == node.manager_id).first()
                        if node.manager_id else None)
            target.manager_id = mid

    db.commit()
    db.refresh(target)
    return public_user(target)
