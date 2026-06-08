"""
Leads Route — view and manage leads in the CRM.

Endpoints:
  GET  /leads              — list all leads (with filters)
  GET  /leads/{id}         — get a single lead with full history
  GET  /leads/stats        — pipeline summary counts
  POST /leads/{id}/score   — manually trigger a re-score
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.lead import Lead
from models.interaction import Interaction
from services.lead_scorer import score_breakdown

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
            "phone": l.phone,
            "company": l.company_name,
            "state": l.state,
            "type": l.lead_type,
            "team_size": l.team_size,
            "source": l.source_platform,
            "score": l.lead_score,
            "quality": l.lead_quality,
            "status": l.status,
            "current_intent": l.current_intent,
            "willing_for_demo": l.willing_for_demo,
            "demo_preference": l.demo_preference,
            "human_priority": l.human_priority,
            "meet_link": l.meet_link,
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

class MeetRequest(BaseModel):
    link: str


@router.post("/{lead_id}/meet")
def set_meet_link(lead_id: int, body: MeetRequest, db: Session = Depends(get_db)):
    """
    Save (or clear) a Google Meet link for this lead so the team can rejoin
    the same meeting next time from the Inbox video-call button.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}
    link = body.link.strip()
    # Basic sanity check — only accept http(s) links, else clear
    lead.meet_link = link if link.startswith(("http://", "https://")) else None
    db.commit()
    return {"id": lead.id, "meet_link": lead.meet_link}


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


@router.get("/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """
    Aggregated analytics for the dashboard Analytics view.
    Returns funnel, source mix, score distribution, weekly trend, and cohorts.
    """
    leads = db.query(Lead).all()
    total = max(len(leads), 1)

    # ── Pipeline funnel ────────────────────────────────────────────────────────
    from collections import Counter
    status_counts = Counter(l.status or "new" for l in leads)

    contacted_n = sum(status_counts.get(s, 0) for s in ["contacted", "engaged", "needs_human"])
    demo_n      = sum(status_counts.get(s, 0) for s in ["demo_scheduled", "demo_done"])
    converted_n = status_counts.get("converted", 0)

    funnel = [
        {"stage": "New leads",  "count": total,        "pct": 100},
        {"stage": "Contacted",  "count": contacted_n,  "pct": round(contacted_n  / total * 100)},
        {"stage": "Demo",       "count": demo_n,        "pct": round(demo_n       / total * 100)},
        {"stage": "Converted",  "count": converted_n,   "pct": round(converted_n  / total * 100)},
    ]

    # ── Source mix ─────────────────────────────────────────────────────────────
    src_counts = Counter(
        ("facebook" if (l.source_platform or "").lower() in ("fb", "facebook") else
         "instagram" if (l.source_platform or "").lower() in ("ig", "instagram") else
         "other")
        for l in leads
    )
    sources = [
        {"name": "Facebook",  "count": src_counts["facebook"],  "color": "#1877f2"},
        {"name": "Instagram", "count": src_counts["instagram"], "color": "#e1306c"},
        {"name": "Other",     "count": src_counts["other"],     "color": "#94a3b8"},
    ]

    # ── Score distribution ─────────────────────────────────────────────────────
    buckets = {"0–20": 0, "21–40": 0, "41–60": 0, "61–80": 0, "81–100": 0}
    for l in leads:
        s = l.lead_score or 0
        if   s <= 20:  buckets["0–20"]   += 1
        elif s <= 40:  buckets["21–40"]  += 1
        elif s <= 60:  buckets["41–60"]  += 1
        elif s <= 80:  buckets["61–80"]  += 1
        else:          buckets["81–100"] += 1
    score_buckets = [{"b": k, "n": v} for k, v in buckets.items()]

    # ── Weekly trend (last 8 weeks) ────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    weekly_trend = []
    for i in range(7, -1, -1):
        w_start = now - timedelta(weeks=i + 1)
        w_end   = now - timedelta(weeks=i)
        label   = f"W{8 - i}"
        lead_n  = sum(
            1 for l in leads
            if l.created_at and w_start <= l.created_at.replace(tzinfo=timezone.utc) < w_end
        )
        demo_n2 = sum(
            1 for l in leads
            if l.created_at
            and w_start <= l.created_at.replace(tzinfo=timezone.utc) < w_end
            and l.willing_for_demo
        )
        weekly_trend.append({"w": label, "leads": lead_n, "demos": demo_n2})

    # ── Cohorts (same weekly buckets) ─────────────────────────────────────────
    cohorts = []
    for i, wk in enumerate(weekly_trend):
        w_start = now - timedelta(weeks=8 - i)
        w_end   = now - timedelta(weeks=7 - i)
        bucket_leads = [
            l for l in leads
            if l.created_at
            and w_start <= l.created_at.replace(tzinfo=timezone.utc) < w_end
        ]
        n = len(bucket_leads)
        contacted2  = sum(1 for l in bucket_leads if l.status not in ("new", None))
        replied     = sum(1 for l in bucket_leads if l.last_interaction_at and l.last_interaction_at != l.created_at)
        demos2      = sum(1 for l in bucket_leads if l.willing_for_demo)
        won2        = sum(1 for l in bucket_leads if l.status == "converted")
        cohorts.append({
            "week": wk["w"], "leads": n, "contacted": contacted2,
            "replied": replied, "demos": demos2, "won": won2,
        })

    return {
        "funnel":       funnel,
        "sources":      sources,
        "score_buckets": score_buckets,
        "weekly_trend": weekly_trend,
        "cohorts":      cohorts,
        "summary": {
            "total":     total,
            "hot":       sum(1 for l in leads if l.lead_quality == "hot"),
            "warm":      sum(1 for l in leads if l.lead_quality == "warm"),
            "demos":     sum(1 for l in leads if l.willing_for_demo),
            "converted": converted_n,
        },
    }


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
            # ── Identity ──────────────────────────────────────────────────────
            "id": lead.id,
            "name": lead.first_name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company_name,
            "state": lead.state,
            # ── Profile ───────────────────────────────────────────────────────
            "type": lead.lead_type,
            "team_size": lead.team_size,
            "source": lead.source_platform,
            "channel": lead.channel,
            "uses_software": lead.uses_software,
            "current_software": lead.current_software,
            "open_to_platform": lead.open_to_platform,
            "company_website": lead.company_website,
            # ── Scoring & status ──────────────────────────────────────────────
            "score": lead.lead_score,
            "quality": lead.lead_quality,
            "score_breakdown": score_breakdown(lead),
            "status": lead.status,
            "current_intent": lead.current_intent,
            # ── Demo interest ─────────────────────────────────────────────────
            "willing_for_demo": lead.willing_for_demo,
            "demo_preference": lead.demo_preference,
            "meet_link": lead.meet_link,
            # ── Compliance & overrides ────────────────────────────────────────
            "opt_out": lead.opt_out,
            "human_priority": lead.human_priority,
            "human_notes": lead.human_notes,
            # ── Chat ─────────────────────────────────────────────────────────
            "chat_url": f"/chat/{lead.chat_token}" if lead.chat_token else None,
            "chat_opened_at": lead.chat_opened_at,
            "alert_sent_at": lead.alert_sent_at,
            # ── Re-engagement ─────────────────────────────────────────────────
            "re_engage_after": lead.re_engage_after,
            # ── Timestamps ───────────────────────────────────────────────────
            "created_at": lead.created_at,
            "first_response_at": lead.first_response_at,
            "last_interaction_at": lead.last_interaction_at,
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
