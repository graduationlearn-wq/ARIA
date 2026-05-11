"""
Scheduler Route — manually trigger or inspect follow-up jobs.

Endpoints:
  POST /scheduler/run              — run all follow-up jobs right now
  POST /scheduler/run/followup-1   — run follow-up 1 only
  POST /scheduler/run/followup-2   — run follow-up 2 only
  GET  /scheduler/status           — next scheduled run time + job config
  POST /scheduler/test-email       — send a test email to verify SMTP config
"""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from apscheduler.schedulers.background import BackgroundScheduler

from services.scheduler import (
    run_all_followups, run_followup_1, run_followup_2,
    run_followup_7day, run_reengagements,
)
from utils.email_sender import send_email
from config import settings

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

# Reference to the shared scheduler instance (set by main.py)
_scheduler: BackgroundScheduler | None = None


def set_scheduler(s: BackgroundScheduler):
    global _scheduler
    _scheduler = s


@router.post("/run")
def trigger_all():
    """Manually run all follow-up jobs right now — useful for testing."""
    result = run_all_followups()
    return {"status": "completed", "results": result}


@router.post("/run/followup-1")
def trigger_followup_1():
    """Manually trigger follow-up 1 only."""
    result = run_followup_1()
    return {"status": "completed", "result": result}


@router.post("/run/followup-2")
def trigger_followup_2():
    """Manually trigger follow-up 2 only."""
    result = run_followup_2()
    return {"status": "completed", "result": result}


@router.post("/run/followup-7day")
def trigger_followup_7day():
    """Manually trigger the 7-day final nudge."""
    result = run_followup_7day()
    return {"status": "completed", "result": result}


@router.post("/run/reengagements")
def trigger_reengagements():
    """Manually trigger re-engagement messages for 'maybe later' leads."""
    result = run_reengagements()
    return {"status": "completed", "result": result}


class TestEmailRequest(BaseModel):
    to: str
    name: str = "Test Lead"


@router.post("/test-email")
def test_email(body: TestEmailRequest):
    """
    Send a test email to verify your SMTP / SendGrid config is working.
    Use this before connecting real leads — hit this first.
    """
    sent = send_email(
        to_address=body.to,
        subject="ARIA test email — BeyondSure",
        body=(
            f"Hi {body.name},\n\n"
            "This is a test message from ARIA — BeyondSure Lead Engine.\n\n"
            "If you're reading this, your email delivery is configured correctly.\n\n"
            "— ARIA"
        ),
    )
    if sent:
        return {"status": "sent", "to": body.to, "provider": settings.smtp_host}
    else:
        return {
            "status": "failed",
            "detail": "Check SMTP_USER and SMTP_PASSWORD in your .env file",
            "smtp_host": settings.smtp_host,
            "smtp_user": settings.smtp_user or "(not set)",
        }


@router.get("/status")
def scheduler_status():
    """Show the current scheduler config and next run time."""
    job_info = []
    if _scheduler:
        for job in _scheduler.get_jobs():
            job_info.append({
                "id": job.id,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger),
            })

    return {
        "human_approval_mode": settings.human_approval_mode,
        "followup_1_after_hours": 24,
        "followup_2_after_hours": 72,
        "scheduled_jobs": job_info,
    }
