"""
Approval Route — human review queue for ARIA-generated drafts.

This is the core of Phase 2 (assisted generation).
ARIA drafts → human sees here → approves or edits → message sent.

Endpoints:
  GET  /approval/queue           — all drafts waiting for approval
  POST /approval/{id}/approve    — approve and send a draft
  POST /approval/{id}/edit       — edit the draft text then send
  POST /approval/{id}/reject     — reject a draft (mark as rejected, no send)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.interaction import Interaction
from models.lead import Lead
from models.user import User
from utils.email_sender import send_email
from services.auth_service import resolve_scope, subtree_ids
from routes.auth import get_current_user

router = APIRouter(prefix="/approval", tags=["Approval Queue"],
                   dependencies=[Depends(get_current_user)])


class EditRequest(BaseModel):
    revised_text: str
    reviewer_notes: str | None = None


# ── GET /approval/queue ───────────────────────────────────────────────────────
@router.get("/queue")
def get_approval_queue(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Outbound drafts waiting for approval, scoped to the current user's team.
    """
    scope = resolve_scope(current, db, None)
    q = db.query(Interaction).filter(
        Interaction.direction == "outbound",
        Interaction.send_status == "pending_approval",
    )
    if scope is not None:
        q = q.join(Lead, Lead.id == Interaction.lead_id).filter(Lead.owner_id.in_(scope))
    pending = q.order_by(Interaction.timestamp.asc()).all()

    results = []
    for interaction in pending:
        lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()
        results.append({
            "draft_id": interaction.id,
            "lead_id": interaction.lead_id,
            "lead_name": lead.first_name if lead else "Unknown",
            "lead_email": lead.email if lead else None,
            "lead_quality": lead.lead_quality if lead else None,
            "lead_score": lead.lead_score if lead else 0,
            "intent_context": interaction.intent_label,
            "draft_message": interaction.message_text,
            "created_at": interaction.timestamp,
        })

    return {
        "total_pending": len(results),
        "drafts": results,
    }


# ── GET /approval/stats ───────────────────────────────────────────────────────
@router.get("/stats")
def approval_stats(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Approval-queue metrics + recent review activity, scoped to the user's team.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

    scope = resolve_scope(current, db, None)
    scoped_lead_ids = None
    if scope is not None:
        scoped_lead_ids = [
            lid for (lid,) in db.query(Lead.id).filter(Lead.owner_id.in_(scope)).all()
        ]

    def base_q():
        q = db.query(Interaction).filter(Interaction.direction == "outbound")
        if scoped_lead_ids is not None:
            q = q.filter(Interaction.lead_id.in_(scoped_lead_ids))
        return q

    pending = base_q().filter(Interaction.send_status == "pending_approval").count()
    rejected = base_q().filter(Interaction.send_status == "rejected").count()
    sent_total = base_q().filter(Interaction.send_status == "sent").count()
    approved_today = (
        base_q().filter(
            Interaction.send_status == "sent",
            Interaction.handled_by.in_(["human_approved", "human_edited", "human"]),
            Interaction.timestamp >= today_start,
        ).count()
    )

    # Recent review activity (last 10 sent/rejected outbound messages)
    recent = (
        base_q()
        .filter(
            or_(Interaction.send_status == "sent", Interaction.send_status == "rejected"),
        )
        .order_by(Interaction.timestamp.desc())
        .limit(10)
        .all()
    )

    activity = []
    for i in recent:
        lead = db.query(Lead).filter(Lead.id == i.lead_id).first()
        if i.send_status == "rejected":
            action, tone = "Rejected", "red"
        elif i.handled_by == "human_edited":
            action, tone = "Edited", "purple"
        elif i.handled_by == "human":
            action, tone = "Replied", "green"
        else:
            action, tone = "Approved", "green"
        summary = (i.message_text or "").replace("\n", " ").strip()
        activity.append({
            "action": action,
            "tone": tone,
            "lead_name": lead.first_name if lead else "Unknown",
            "summary": (summary[:52] + "…") if len(summary) > 52 else summary,
            "time": i.timestamp.strftime("%H:%M") if i.timestamp else "",
        })

    return {
        "stats": {
            "pending": pending,
            "approved_today": approved_today,
            "rejected": rejected,
            "sent_total": sent_total,
        },
        "activity": activity,
    }


# ── POST /approval/{id}/approve ───────────────────────────────────────────────
@router.post("/{interaction_id}/approve")
def approve_draft(
    interaction_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Approve a draft and send it immediately.
    """
    interaction = _get_pending_draft(interaction_id, db, current)
    lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()

    if not lead or not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    subject = _build_reply_subject(lead)
    sent = send_email(lead.email, subject, interaction.message_text)

    if sent:
        interaction.send_status = "sent"
        interaction.handled_by = "human_approved"
        if not lead.first_response_at:
            lead.first_response_at = datetime.now(timezone.utc)
            lead.status = "contacted"
        lead.last_interaction_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "sent", "draft_id": interaction_id, "to": lead.email}
    else:
        raise HTTPException(status_code=500, detail="Email send failed — check SMTP config")


# ── POST /approval/{id}/edit ──────────────────────────────────────────────────
@router.post("/{interaction_id}/edit")
def edit_and_send(
    interaction_id: int,
    body: EditRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Replace the draft text with a human-revised version, then send.
    The original ARIA draft is overwritten — reviewer_notes records what changed.
    """
    interaction = _get_pending_draft(interaction_id, db, current)
    lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()

    if not lead or not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    # Replace draft with edited version
    interaction.message_text = body.revised_text
    interaction.reviewer_notes = body.reviewer_notes
    interaction.handled_by = "human_edited"

    subject = _build_reply_subject(lead)
    sent = send_email(lead.email, subject, body.revised_text)

    if sent:
        interaction.send_status = "sent"
        if not lead.first_response_at:
            lead.first_response_at = datetime.now(timezone.utc)
            lead.status = "contacted"
        lead.last_interaction_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "sent_with_edits", "draft_id": interaction_id}
    else:
        raise HTTPException(status_code=500, detail="Email send failed — check SMTP config")


# ── POST /approval/{id}/reject ────────────────────────────────────────────────
@router.post("/{interaction_id}/reject")
def reject_draft(
    interaction_id: int,
    notes: str | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Reject a draft — it won't be sent. Lead stays in queue.
    Use this when ARIA's response was off and you'll handle it manually.
    """
    interaction = _get_pending_draft(interaction_id, db, current)
    interaction.send_status = "rejected"
    interaction.reviewer_notes = notes
    db.commit()
    return {"status": "rejected", "draft_id": interaction_id}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_pending_draft(interaction_id: int, db: Session, current: User) -> Interaction:
    interaction = db.query(Interaction).filter(
        Interaction.id == interaction_id,
        Interaction.send_status == "pending_approval",
    ).first()
    if not interaction:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or already processed"
        )
    # Scope check — a user can only act on drafts for leads in their team.
    scope = subtree_ids(current, db)
    if scope is not None:
        lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()
        if lead is None or lead.owner_id not in scope:
            raise HTTPException(status_code=403, detail="This draft is outside your team")
    return interaction


def _build_reply_subject(lead: Lead) -> str:
    name = (lead.first_name or "").strip()
    return f"Re: BeyondSure — {name}" if name else "Re: BeyondSure"
