"""
Leads Route — view and manage leads in the CRM.

Endpoints:
  GET  /leads              — list all leads (with filters)
  GET  /leads/{id}         — get a single lead with full history
  GET  /leads/stats        — pipeline summary counts
  POST /leads/{id}/score   — manually trigger a re-score
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.lead import Lead
from models.interaction import Interaction
from models.user import User
from services.lead_scorer import score_breakdown
from services.stages import (
    STAGE_ORDER, STAGE_LABELS, FUNNEL_TRACK, lead_stage,
)
from services.auth_service import resolve_scope, subtree_ids, user_directory
from routes.auth import get_current_user

# Every leads endpoint requires a logged-in user.
router = APIRouter(prefix="/leads", tags=["Leads"], dependencies=[Depends(get_current_user)])


def _owner_names(db: Session) -> dict[int, str]:
    """Map user_id → name for cheap owner lookups in responses."""
    return {uid: name for uid, name in db.query(User.id, User.name).all()}


@router.get("/stats")
def pipeline_stats(
    as_user: int | None = Query(None, alias="as"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Quick summary of the pipeline — scoped to what the current user may see."""
    scope = resolve_scope(current, db, as_user)

    def scoped(q):
        return q.filter(Lead.owner_id.in_(scope)) if scope is not None else q

    total = scoped(db.query(func.count(Lead.id))).scalar()

    quality_counts = (
        scoped(db.query(Lead.lead_quality, func.count(Lead.id)))
        .group_by(Lead.lead_quality)
        .all()
    )
    status_counts = (
        scoped(db.query(Lead.status, func.count(Lead.id)))
        .group_by(Lead.status)
        .all()
    )

    # Average response time (minutes) for contacted leads
    contacted = scoped(db.query(Lead).filter(Lead.first_response_at.isnot(None))).all()
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
    as_user: int | None = Query(None, alias="as"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """List leads (scoped to the current user), sorted by score descending."""
    query = db.query(Lead)
    scope = resolve_scope(current, db, as_user)
    if scope is not None:
        query = query.filter(Lead.owner_id.in_(scope))
    if quality:
        query = query.filter(Lead.lead_quality == quality.lower())
    if status:
        query = query.filter(Lead.status == status.lower())

    leads = query.order_by(Lead.lead_score.desc()).offset(offset).limit(limit).all()
    names = _owner_names(db)

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
            "stage": lead_stage(l),
            "owner_id": l.owner_id,
            "owner_name": names.get(l.owner_id),
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

class OwnerRequest(BaseModel):
    owner_id: int


@router.get("/assignable-owners")
def assignable_owners(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Employees the current user can assign leads to (admin: all; manager: their team)."""
    if current.role == "employee":
        return []
    scope = subtree_ids(current, db)  # None for admin
    q = db.query(User).filter(User.role == "employee", User.is_active == True)  # noqa: E712
    if scope is not None:
        q = q.filter(User.id.in_(scope))
    return [{"id": u.id, "name": u.name} for u in q.order_by(User.name).all()]


@router.patch("/{lead_id}/owner")
def reassign_owner(
    lead_id: int, body: OwnerRequest,
    db: Session = Depends(get_db), current: User = Depends(get_current_user),
):
    """Reassign a lead to an employee. Managers/admin only, within their scope."""
    if current.role == "employee":
        raise HTTPException(status_code=403, detail="Employees cannot reassign leads")
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    scope = subtree_ids(current, db)
    target = db.query(User).filter(User.id == body.owner_id, User.role == "employee").first()
    if not target or (scope is not None and target.id not in scope):
        raise HTTPException(status_code=400, detail="Invalid owner")
    lead.owner_id = target.id
    db.commit()
    return {"id": lead.id, "owner_id": lead.owner_id, "owner_name": target.name}


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
             "demo_scheduled", "demo_done", "converted", "lost", "invalid",
             # canonical pipeline stages (set from the lead detail view)
             "follow_up", "post_demo", "negotiation", "post_commercial",
             "parked", "won"}
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
def get_analytics(
    as_user: int | None = Query(None, alias="as"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Aggregated analytics for the dashboard Analytics view (scoped to the user).
    Returns lead stages, funnel, source mix, score distribution, trend, cohorts.
    """
    q = db.query(Lead)
    scope = resolve_scope(current, db, as_user)
    if scope is not None:
        q = q.filter(Lead.owner_id.in_(scope))
    leads = q.all()
    total = max(len(leads), 1)

    # ── Canonical lead stages (the 10-stage CRM pipeline) ──────────────────────
    from collections import Counter
    stage_of = {l.id: lead_stage(l) for l in leads}
    stage_counts = Counter(stage_of.values())
    stages = [
        {"key": k, "label": STAGE_LABELS[k], "count": stage_counts.get(k, 0)}
        for k in STAGE_ORDER
    ]

    # ── Pipeline funnel — cumulative over the linear track ──────────────────────
    # Parked/Lost are off-track, so they're excluded from the funnel (shown in the
    # stage grid instead). Each bar = leads currently at-or-beyond that stage.
    track_idx = {k: i for i, k in enumerate(FUNNEL_TRACK)}
    on_track = [s for s in stage_of.values() if s in track_idx]
    on_track_total = max(len(on_track), 1)
    funnel = []
    for i, k in enumerate(FUNNEL_TRACK):
        cnt = sum(1 for s in on_track if track_idx[s] >= i)
        funnel.append({
            "stage": STAGE_LABELS[k],
            "count": cnt,
            "pct": round(cnt / on_track_total * 100),
        })

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
        "stages":       stages,
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
            "converted": stage_counts.get("won", 0),
        },
    }


@router.get("/{lead_id}")
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Get a single lead with full interaction history (scope-checked)."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}

    # Visibility check — non-admins can only open leads inside their scope.
    scope = subtree_ids(current, db)
    if scope is not None and lead.owner_id not in scope:
        raise HTTPException(status_code=403, detail="Not allowed to view this lead")

    names = _owner_names(db)
    directory = user_directory(db)

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
            "stage": lead_stage(lead),
            "owner_id": lead.owner_id,
            "owner_name": names.get(lead.owner_id),
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
                "sender_name": directory.get(i.sender_user_id, {}).get("name") if i.sender_user_id else None,
                "sender_role": directory.get(i.sender_user_id, {}).get("role") if i.sender_user_id else None,
                "timestamp": i.timestamp,
            }
            for i in interactions
        ],
    }
