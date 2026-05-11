"""
Follow-up Scheduler — queues follow-up messages for leads that haven't replied.

Sequence:
  First-touch sent
      └─ No reply after 24 hrs → Follow-up 1
              └─ No reply after 72 hrs → Follow-up 2
                      └─ Still no reply → hand off to human (status = needs_call)

Rules:
  - Never follow up on opted-out leads
  - Never follow up on escalated / lost / converted leads
  - Never send a follow-up if the lead has replied (any inbound interaction exists)
  - Don't double-queue: skip if a follow-up draft already exists in pending_approval
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from database import SessionLocal
from models.interaction import Interaction
from models.lead import Lead
from services.message_builder import (
    build_followup_1, build_followup_2, build_followup_7day,
    build_reengagement, build_subject_line,
)
from services.lead_scorer import apply_decay, score_to_quality
from config import settings
from utils.email_sender import send_email


# ── Tuneable windows ──────────────────────────────────────────────────────────
FOLLOWUP_1_AFTER_HOURS  = 24
FOLLOWUP_2_AFTER_HOURS  = 72    # measured from when followup_1 was queued
FOLLOWUP_7DAY_AFTER_DAYS = 7    # measured from when followup_2 was queued


# ── Internal helpers ──────────────────────────────────────────────────────────

def _has_inbound(lead_id: int, db: Session) -> bool:
    """Return True if the lead has replied at least once."""
    return db.query(Interaction).filter(
        Interaction.lead_id == lead_id,
        Interaction.direction == "inbound",
    ).first() is not None


def _has_message_type(lead_id: int, message_type: str, db: Session) -> bool:
    """Return True if a follow-up of this type has already been queued or sent."""
    return db.query(Interaction).filter(
        Interaction.lead_id == lead_id,
        Interaction.message_type == message_type,
    ).first() is not None


def _queue_or_send(lead: Lead, message_text: str, message_type: str,
                   message_number: int, db: Session) -> str:
    """
    Create an outbound interaction.
    If human_approval_mode → pending_approval (goes to approval queue).
    Else → send immediately.
    """
    subject = build_subject_line(lead, message_number)

    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        message_text=message_text,
        message_type=message_type,
        handled_by="aria",
        send_status="pending_approval" if settings.human_approval_mode else "approved",
    )
    db.add(interaction)

    if not settings.human_approval_mode and lead.email:
        sent = send_email(lead.email, subject, message_text)
        if sent:
            interaction.send_status = "sent"
            lead.last_interaction_at = datetime.utcnow()

    db.commit()
    return interaction.send_status


# ── Public job functions ──────────────────────────────────────────────────────

def run_followup_1() -> dict:
    """
    Queue follow-up 1 for leads where:
      - First-touch was sent > 24 hrs ago
      - No inbound reply yet
      - No followup_1 already exists
    """
    db: Session = SessionLocal()
    cutoff = datetime.utcnow() - timedelta(hours=FOLLOWUP_1_AFTER_HOURS)
    queued = 0
    skipped = 0

    try:
        # Leads where we sent a first-touch and they haven't replied
        candidates = db.query(Lead).filter(
            Lead.opt_out.is_(False) | Lead.opt_out.is_(None),
            Lead.status.notin_(["escalated", "lost", "converted"]),
            Lead.first_response_at.isnot(None),
            Lead.first_response_at <= cutoff,
        ).all()

        for lead in candidates:
            if _has_inbound(lead.id, db):
                skipped += 1
                continue
            if _has_message_type(lead.id, "followup_1", db):
                skipped += 1
                continue

            message = build_followup_1(lead)
            status = _queue_or_send(lead, message, "followup_1", 2, db)
            queued += 1
            print(f"[Scheduler] Follow-up 1 → Lead {lead.id} ({lead.first_name}) | {status}")

    finally:
        db.close()

    return {"job": "followup_1", "queued": queued, "skipped": skipped}


def run_followup_2() -> dict:
    """
    Queue follow-up 2 for leads where:
      - Follow-up 1 was queued > 72 hrs ago
      - No inbound reply yet
      - No followup_2 already exists
    """
    db: Session = SessionLocal()
    cutoff = datetime.utcnow() - timedelta(hours=FOLLOWUP_2_AFTER_HOURS)
    queued = 0
    skipped = 0

    try:
        candidates = db.query(Lead).filter(
            Lead.opt_out.is_(False) | Lead.opt_out.is_(None),
            Lead.status.notin_(["escalated", "lost", "converted"]),
        ).all()

        for lead in candidates:
            if _has_inbound(lead.id, db):
                skipped += 1
                continue
            if _has_message_type(lead.id, "followup_2", db):
                skipped += 1
                continue

            # Find the followup_1 interaction for this lead
            fu1 = db.query(Interaction).filter(
                Interaction.lead_id == lead.id,
                Interaction.message_type == "followup_1",
            ).first()

            if not fu1:
                skipped += 1
                continue

            if fu1.timestamp > cutoff:
                skipped += 1  # too soon — followup_1 < 72 hrs old
                continue

            message = build_followup_2(lead)
            status = _queue_or_send(lead, message, "followup_2", 3, db)

            # After followup_2, mark lead as needing a human call
            lead.status = "needs_call"
            db.commit()

            queued += 1
            print(f"[Scheduler] Follow-up 2 → Lead {lead.id} ({lead.first_name}) | {status}")

    finally:
        db.close()

    return {"job": "followup_2", "queued": queued, "skipped": skipped}


def run_followup_7day() -> dict:
    """
    Queue a final 7-day nudge for leads where:
      - Follow-up 2 was sent > 7 days ago
      - No inbound reply yet
      - No followup_7day already exists
    After this, lead status → needs_call (human must reach out personally).
    """
    db: Session = SessionLocal()
    cutoff = datetime.utcnow() - timedelta(days=FOLLOWUP_7DAY_AFTER_DAYS)
    queued = 0
    skipped = 0

    try:
        candidates = db.query(Lead).filter(
            Lead.opt_out.is_(False) | Lead.opt_out.is_(None),
            Lead.status.notin_(["escalated", "lost", "converted", "contacted"]),
        ).all()

        for lead in candidates:
            if _has_inbound(lead.id, db):
                skipped += 1
                continue
            if _has_message_type(lead.id, "followup_7day", db):
                skipped += 1
                continue

            fu2 = db.query(Interaction).filter(
                Interaction.lead_id == lead.id,
                Interaction.message_type == "followup_2",
            ).first()

            if not fu2 or fu2.timestamp > cutoff:
                skipped += 1
                continue

            message = build_followup_7day(lead)
            status = _queue_or_send(lead, message, "followup_7day", 4, db)
            lead.status = "needs_call"
            db.commit()

            queued += 1
            print(f"[Scheduler] 7-day nudge → Lead {lead.id} ({lead.first_name}) | {status}")

    finally:
        db.close()

    return {"job": "followup_7day", "queued": queued, "skipped": skipped}


def run_reengagements() -> dict:
    """
    Re-engage leads who said 'maybe later' in chat.
    Fires when lead.re_engage_after <= now and lead hasn't replied or opted out.
    Resumes the conversation by sending the re-engagement message.
    """
    db: Session = SessionLocal()
    now = datetime.utcnow()
    queued = 0
    skipped = 0

    try:
        candidates = db.query(Lead).filter(
            Lead.re_engage_after.isnot(None),
            Lead.re_engage_after <= now,
            Lead.opt_out.is_(False) | Lead.opt_out.is_(None),
            Lead.status.notin_(["lost", "converted", "contacted", "needs_human"]),
        ).all()

        for lead in candidates:
            if _has_inbound(lead.id, db):
                # They came back on their own — clear the re-engage timer
                lead.re_engage_after = None
                db.commit()
                skipped += 1
                continue

            if _has_message_type(lead.id, "reengagement", db):
                skipped += 1
                continue

            message = build_reengagement(lead)
            status = _queue_or_send(lead, message, "reengagement", 2, db)

            # Clear the timer so we don't re-send
            lead.re_engage_after = None
            db.commit()

            queued += 1
            print(f"[Scheduler] Re-engagement → Lead {lead.id} ({lead.first_name}) | {status}")

    finally:
        db.close()

    return {"job": "reengagements", "queued": queued, "skipped": skipped}




def run_score_decay() -> dict:
    """
    Apply inactivity score decay to all active leads.
    Called by run_all_followups() every hour.
    Penalises leads: 31+ days = -20pts, 15-30 days = -10pts, 8-14 days = -5pts.
    """
    db: Session = SessionLocal()
    now = datetime.utcnow()
    updated = 0
    skipped = 0

    try:
        candidates = db.query(Lead).filter(
            Lead.opt_out.is_(False) | Lead.opt_out.is_(None),
            Lead.status.notin_(["lost", "converted"]),
            Lead.last_interaction_at.isnot(None),
        ).all()

        for lead in candidates:
            days_silent = (now - lead.last_interaction_at).days
            if days_silent < 8:
                skipped += 1
                continue

            old_score = lead.lead_score or 0
            new_score = apply_decay(old_score, days_silent)
            if new_score == old_score:
                skipped += 1
                continue

            lead.lead_score = new_score
            lead.lead_quality = score_to_quality(new_score)
            updated += 1
            print(
                f"[Scheduler] Decay Lead {lead.id} ({lead.first_name}): "
                f"{old_score} -> {new_score} ({days_silent} days silent)"
            )

        db.commit()

    finally:
        db.close()

    return {"job": "score_decay", "updated": updated, "skipped": skipped}


def run_all_followups() -> dict:
    """Run all follow-up, re-engagement, and decay jobs. Called by APScheduler every hour."""
    print(f"[Scheduler] Running follow-up jobs at {datetime.utcnow().isoformat()}")
    r1 = run_followup_1()
    r2 = run_followup_2()
    r3 = run_followup_7day()
    r4 = run_reengagements()
    r5 = run_score_decay()
    return {
        "followup_1": r1,
        "followup_2": r2,
        "followup_7day": r3,
        "reengagements": r4,
        "score_decay": r5,
    }
