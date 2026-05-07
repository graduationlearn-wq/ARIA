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

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.interaction import Interaction
from models.lead import Lead
from utils.email_sender import send_email

router = APIRouter(prefix="/approval", tags=["Approval Queue"])


class EditRequest(BaseModel):
    revised_text: str
    reviewer_notes: str | None = None


# ── GET /approval/queue ───────────────────────────────────────────────────────
@router.get("/queue")
def get_approval_queue(db: Session = Depends(get_db)):
    """
    Returns all outbound drafts waiting for human approval.
    This is what a team member checks before messages go out.
    """
    pending = (
        db.query(Interaction)
        .filter(
            Interaction.direction == "outbound",
            Interaction.send_status == "pending_approval",
        )
        .order_by(Interaction.timestamp.asc())
        .all()
    )

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


# ── POST /approval/{id}/approve ───────────────────────────────────────────────
@router.post("/{interaction_id}/approve")
def approve_draft(interaction_id: int, db: Session = Depends(get_db)):
    """
    Approve a draft and send it immediately.
    """
    interaction = _get_pending_draft(interaction_id, db)
    lead = db.query(Lead).filter(Lead.id == interaction.lead_id).first()

    if not lead or not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")

    subject = _build_reply_subject(lead)
    sent = send_email(lead.email, subject, interaction.message_text)

    if sent:
        interaction.send_status = "sent"
        interaction.handled_by = "human_approved"
        if not lead.first_response_at:
            lead.first_response_at = datetime.utcnow()
            lead.status = "contacted"
        lead.last_interaction_at = datetime.utcnow()
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
):
    """
    Replace the draft text with a human-revised version, then send.
    The original ARIA draft is overwritten — reviewer_notes records what changed.
    """
    interaction = _get_pending_draft(interaction_id, db)
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
            lead.first_response_at = datetime.utcnow()
            lead.status = "contacted"
        lead.last_interaction_at = datetime.utcnow()
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
):
    """
    Reject a draft — it won't be sent. Lead stays in queue.
    Use this when ARIA's response was off and you'll handle it manually.
    """
    interaction = _get_pending_draft(interaction_id, db)
    interaction.send_status = "rejected"
    interaction.reviewer_notes = notes
    db.commit()
    return {"status": "rejected", "draft_id": interaction_id}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_pending_draft(interaction_id: int, db: Session) -> Interaction:
    interaction = db.query(Interaction).filter(
        Interaction.id == interaction_id,
        Interaction.send_status == "pending_approval",
    ).first()
    if not interaction:
        raise HTTPException(
            status_code=404,
            detail="Draft not found or already processed"
        )
    return interaction


def _build_reply_subject(lead: Lead) -> str:
    name = (lead.first_name or "").strip()
    return f"Re: BeyondSure — {name}" if name else "Re: BeyondSure"
