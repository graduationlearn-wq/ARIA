"""
ARIA — Adaptive Response & Intent Architecture
Main FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000

Then open:
    http://localhost:8000/docs   ← interactive API docs (try every endpoint here)
    http://localhost:8000/       ← health check
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from database import init_db, SessionLocal
from routes import webhook, leads, approval, chat, admin, auth, templates
from routes import scheduler as scheduler_route
from routes.scheduler import set_scheduler
from services.scheduler import run_all_followups
from services.kb_seeder import seed_kb
from services.auth_service import seed_users, assign_unowned_leads
from services.template_service import seed_templates

# ── Background scheduler (follow-up jobs) ────────────────────────────────────
_scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
_scheduler.add_job(
    run_all_followups,
    trigger="interval",
    hours=1,
    id="followup_jobs",
    replace_existing=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed KB + users, start scheduler.  Shutdown: stop scheduler."""
    init_db()
    seed_kb()
    # Seed the 3-level demo org and backfill ownership on any existing leads.
    _db = SessionLocal()
    try:
        seed_users(_db)
        assign_unowned_leads(_db)
        seed_templates(_db)
    finally:
        _db.close()
    _scheduler.start()
    set_scheduler(_scheduler)
    print("=" * 57)
    print("  ARIA is running.")
    print("  Dashboard:         http://localhost:8000/ui")
    print("  Docs:              http://localhost:8000/docs")
    print("  Approval queue:    http://localhost:8000/approval/queue")
    print("  Scheduler:         http://localhost:8000/scheduler/status")
    print("  Chat (example):    http://localhost:8000/chat/<token>")
    print("  KB Editor:         http://localhost:8000/admin/kb")
    print("=" * 57)
    yield
    if _scheduler.running:
        _scheduler.shutdown()


app = FastAPI(
    title="ARIA — BeyondSure Lead Engine",
    description=(
        "AI-powered lead engagement system. "
        "Receives leads → scores them → generates responses → human approves → sends."
    ),
    version="0.1.0 — Phase 2 Beta",
    lifespan=lifespan,
)

# Signed session cookie (powers login). Same-origin SPA → cookie sent automatically.
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")


# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(approval.router)
app.include_router(scheduler_route.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(templates.router)

# ── Dashboard SPA (served at /ui so it's same-origin with the API) ────────────
_dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
app.mount("/ui", StaticFiles(directory=_dashboard_dir, html=True), name="ui")


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "running",
        "system": "ARIA — BeyondSure Lead Engine",
        "phase": "2 — Assisted Generation (human approval mode)",
        "docs": "/docs",
        "scheduler": "running" if _scheduler.running else "stopped",
    }
