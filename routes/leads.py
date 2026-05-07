"""
Leads Route — view and manage leads in the CRM.

Endpoints:
  GET  /leads              — list all leads (with filters)
  GET  /leads/{id}         — get a single lead with full history
  GET  /leads/stats        — pipeline summary counts
  POST /leads/{id}/score   — manually trigger a re-score
"""

from fastapi import APIRouter, Depends, Query
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
