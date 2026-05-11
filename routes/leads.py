"""
Leads Route — view and manage leads in the CRM.

Endpoints:
  GET  /leads              — list all leads (with filters)
  GET  /leads/{id}         — get a single lead with full history
  GET  /leads/stats        — pipeline summary counts
  POST /leads/{id}/score   — manually trigger a re-score
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.lead import Lead
from models.interaction import Interaction

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/stats")
def pipeline_stats(db: Session = Depends(get_db)):
    """Quick summary of the pipeline — useful for the CRM dashboard."""
    total = db.query(func.count(Lead.id)).scalar()

    quality_counts = (
        db.query(Lead.lead_quality, func.count(Lead.id))
        .group_by(Lead.lead_quality)
        .all()
    )
    status_counts = (
        db.query(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
        .all()
    )

    # Average response time (minutes) for contacted leads
    contacted = db.query(Lead).filter(Lead.first_response_at.isnot(None)).all()
    avg_response_min = None
    if contacted:
        deltas = [
            (l.first_response_at - l.created_at).total_seconds() / 60
            for l in contacted
            if l.first_response_at and l.created_at
        ]
        avg_response_min = round(sum(deltas) / len(deltas), 1) if deltas else None

    return {
        "total_leads": total,
        "by_quality": {q: c for q, c in quality_counts},
        "by_status": {s: c for s, c in status_counts},
        "avg_first_response_minutes": avg_response_min,
    }


@router.get("/")
def list_leads(
    quality: str | None = Query(None, description="Filter by quality: hot/warm/cold/new"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List leads with optional filters. Sorted by score descending."""
    query = db.query(Lead)
    if quality:
        query = query.filter(Lead.lead_quality == quality.lower())
    if status:
        query = query.filter(Lead.status == status.lower())

    leads = query.order_by(Lead.lead_score.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": l.id,
            "name": l.first_name,
            "email": l.email,
            "company": l.company_name,
            "state": l.state,
            "type": l.lead_type,
            "score": l.lead_score,
            "quality": l.lead_quality,
            "status": l.status,
            "current_intent": l.current_intent,
            "created_at": l.created_at,
            "last_interaction_at": l.last_interaction_at,
        }
        for l in leads
    ]


class NotesRequest(BaseModel):
    notes: str

class StatusRequest(BaseModel):
    status: str
    reason: str | None = None


@router.post("/{lead_id}/priority")
def toggle_priority(lead_id: int, db: Session = Depends(get_db)):
    """
    Manually toggle human_priority flag on a lead.
    When on, ARIA will alert the team on any positive signal from this lead.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}
    lead.human_priority = not lead.human_priority
    db.commit()
    return {
        "id": lead.id,
        "human_priority": lead.human_priority,
        "message": f"Priority {'enabled 🚩' if lead.human_priority else 'cleared'} for {lead.first_name}",
    }


@router.post("/{lead_id}/notes")
def set_notes(lead_id: int, body: NotesRequest, db: Session = Depends(get_db)):
    """
    Add or replace human notes on a lead.
    Notes are shown in the alert email and in the lead detail view.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}
    lead.human_notes = body.notes.strip()
    db.commit()
    return {"id": lead.id, "human_notes": lead.human_notes}


@router.patch("/{lead_id}/status")
def override_status(lead_id: int, body: StatusRequest, db: Session = Depends(get_db)):
    """
    Manually override a lead's status. Use when a team member has context
    that ARIA doesn't — e.g. "I spoke to this person, marking as contacted."
    """
    valid = {"new", "engaged", "interested", "needs_human", "contacted",
             "demo_scheduled", "demo_done", "converted", "lost", "invalid"}
    if body.status not in valid:
        return {"error": f"Invalid status. Valid options: {sorted(valid)}"}
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}
    old_status = lead.status
    lead.status = body.status
    if body.reason and lead.human_notes:
        lead.human_notes = f"{lead.human_notes}\n[Status changed {old_status}→{body.status}: {body.reason}]"
    elif body.reason:
        lead.human_notes = f"[Status changed {old_status}→{body.status}: {body.reason}]"
    db.commit()
    return {"id": lead.id, "status": lead.status, "previous": old_status}


@router.get("/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    """Get a single lead with full interaction history."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}

    interactions = (
        db.query(Interaction)
        .filter(Interaction.lead_id == lead_id)
        .order_by(Interaction.timestamp.asc())
        .all()
    )

    return {
        "lead": {
            "id": lead.id,
            "name": lead.first_name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company_name,
            "state": lead.state,
            "type": lead.lead_type,
            "team_size": lead.team_size,
            "source": lead.source_platform,
            "score": lead.lead_score,
            "quality": lead.lead_quality,
            "status": lead.status,
            "opt_out": lead.opt_out,
            "human_priority": lead.human_priority,
            "human_notes": lead.human_notes,
            "current_software": lead.current_software,
            "chat_url": f"/chat/{lead.chat_token}" if lead.chat_token else None,
            "chat_opened_at": lead.chat_opened_at,
            "alert_sent_at": lead.alert_sent_at,
            "created_at": lead.created_at,
            "first_response_at": lead.first_response_at,
        },
        "interactions": [
            {
                "id": i.id,
                "direction": i.direction,
                "message": i.message_text,
                "intent": i.intent_label,
                "send_status": i.send_status,
                "handled_by": i.handled_by,
                "timestamp": i.timestamp,
            }
            for i in interactions
        ],
    }
