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
    verify_password, viewable_users, public_user, resolve_scope,
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
    return {
        "user": public_user(current),
        "viewable": [public_user(u) for u in viewable_users(current, db)],
    }
