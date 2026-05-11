"""
ARIA — Adaptive Response & Intent Architecture
Main FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000

Then open:
    http://localhost:8000/docs   ← interactive API docs (try every endpoint here)
    http://localhost:8000/       ← health check
"""

from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from database import init_db
from routes import webhook, leads, approval
from routes import scheduler as scheduler_route
from routes.scheduler import set_scheduler
from services.scheduler import run_all_followups

app = FastAPI(
    title="ARIA — BeyondSure Lead Engine",
    description=(
        "AI-powered lead engagement system. "
        "Receives leads → scores them → generates responses → human approves → sends."
    ),
    version="0.1.0 — Phase 2 Beta",
)

# ── Background scheduler (follow-up jobs) ────────────────────────────────────
_scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
_scheduler.add_job(
    run_all_followups,
    trigger="interval",
    hours=1,
    id="followup_jobs",
    replace_existing=True,
)


@app.on_event("startup")
def on_startup():
    """Create all DB tables on first run, then start the background scheduler."""
    init_db()
    _scheduler.start()
    set_scheduler(_scheduler)
    print("=" * 55)
    print("  ARIA is running.")
    print("  Docs:           http://localhost:8000/docs")
    print("  Approval queue: http://localhost:8000/approval/queue")
    print("  Scheduler:      http://localhost:8000/scheduler/status")
    print("=" * 55)


@app.on_event("shutdown")
def on_shutdown():
    """Gracefully stop the scheduler on server shutdown."""
    if _scheduler.running:
        _scheduler.shutdown()


# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(approval.router)
app.include_router(scheduler_route.router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "running",
        "system": "ARIA — BeyondSure Lead Engine",
        "phase": "2 — Assisted Generation (human approval mode)",
        "docs": "/docs",
        "scheduler": "running" if _scheduler.running else "stopped",
    }
