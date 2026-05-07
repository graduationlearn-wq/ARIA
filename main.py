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
from database import init_db
from routes import webhook, leads, approval

app = FastAPI(
    title="ARIA — BeyondSure Lead Engine",
    description=(
        "AI-powered lead engagement system. "
        "Receives leads → scores them → generates responses → human approves → sends."
    ),
    version="0.1.0 — Phase 2 Beta",
)


@app.on_event("startup")
def on_startup():
    """Create all DB tables on first run."""
    init_db()
    print("=" * 55)
    print("  ARIA is running.")
    print("  Docs: http://localhost:8000/docs")
    print("  Approval queue: http://localhost:8000/approval/queue")
    print("=" * 55)


# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(approval.router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "running",
        "system": "ARIA — BeyondSure Lead Engine",
        "phase": "2 — Assisted Generation (human approval mode)",
        "docs": "/docs",
    }
