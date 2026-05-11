"""
Webhook Route — receives new lead form submissions.

Two endpoints:
  POST /webhook/lead     — receives FB/IG lead ad form data
  POST /webhook/reply    — receives an inbound reply from a lead (email/WA)

Flow for new lead:
  1. Parse payload → create Lead row
  2. Score the lead
  3. Build first-touch message
  4. If human_approval_mode → save as pending draft
     Else → send immediately
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.lead import Lead
from models.interaction import Interaction
from models.escalation import Escalation
from schemas.lead import LeadWebhookPayload, LeadResponse
from services.lead_scorer import score_lead, apply_engagement_delta, score_to_quality
from services.message_builder import build_first_touch, build_subject_line
from services.intent_classifier import classify_intent, should_escalate
from services.kb_lookup import search_kb, get_answer_for_intent
from services.llm import generate_draft
from utils.email_sender import send_email
from config import settings

router = APIRouter(prefix="/webhook", tags=["Webhook"])


# ── Helper: normalise boolean strings from form ───────────────────────────────
def _parse_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    return val.strip().lower() in ("yes", "true", "1")


def _parse_lead_type(val: str | None) -> str:
    if not val:
        return "unknown"
    v = val.lower().strip()
    mapping = {
        "insurance_agent": "agent",
        "posp_advisor": "posp_advisor",
        "broker": "broker",
        "imf": "imf",
        "advisor": "advisor",
        "invalid": "invalid",
    }
    return mapping.get(v, v)


# ── POST /webhook/lead ────────────────────────────────────────────────────────
@router.post("/lead", response_model=LeadResponse)
def receive_lead(payload: LeadWebhookPayload, db: Session = Depends(get_db)):
    """
    Called by Facebook/Instagram lead ad form on every new submission.
    Creates the lead, scores it, and queues the first-touch message.
    """

    # 1. Create Lead record
    lead = Lead(
        first_name=payload.first_name,
        email=payload.email,
        phone=payload.phone,
        state=payload.state,
        company_name=payload.company_name,
        lead_type=_parse_lead_type(payload.types_of_business),
        source_platform=payload.platform or "unknown",
        uses_software=_parse_bool(payload.do_you_currently_use_any_software),
        open_to_platform=_parse_bool(
            payload.are_you_open_to_adopting_a_new_technology_platform
        ),
        willing_for_demo=_parse_bool(
            payload.would_you_be_willing_to_evaluate_a_new_tech_solution
        ),
        channel="email",
        channel_id=payload.email,
        consent_logged_at=datetime.utcnow(),
    )
    db.add(lead)
    db.flush()  # get lead.id before commit

    # 2. Score the lead
    score, quality = score_lead(lead)
    lead.lead_score = score
    lead.lead_quality = quality

    # 3. Build first-touch message
    message_body = build_first_touch(lead)
    subject = build_subject_line(lead, message_number=1)

    # 4. Create outbound interaction (draft or sent)
    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        message_text=message_body,
        message_type="first_touch",
        handled_by="aria",
        send_status="pending_approval" if settings.human_approval_mode else "approved",
    )
    db.add(interaction)

    # 5. Send immediately if not in approval mode
    if not settings.human_approval_mode and lead.email:
        sent = send_email(lead.email, subject, message_body)
        if sent:
            interaction.send_status = "sent"
            lead.first_response_at = datetime.utcnow()
            lead.status = "contacted"
            lead.last_interaction_at = datetime.utcnow()

    db.commit()
    db.refresh(lead)

    print(
        f"[Webhook] New lead: {lead.first_name} | {lead.email} | "
        f"Score: {lead.lead_score} | Quality: {lead.lead_quality} | "
        f"Draft status: {interaction.send_status}"
    )
    return lead


# ── POST /webhook/reply ───────────────────────────────────────────────────────
@router.post("/reply")
def receive_reply(lead_id: int, message: str, db: Session = Depends(get_db)):
    """
    Called when a lead replies to an email/WhatsApp message.
    Classifies intent → looks up KB → generates draft response.

    In a real integration this would be triggered by:
      - SendGrid Inbound Parse webhook (email replies)
      - Sent API webhook (WhatsApp replies)
    """

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.opt_out:
        return {"status": "skipped", "reason": "Lead has opted out"}

    # 1. Classify intent
    intent = classify_intent(message)

    # 2. Log inbound interaction
    inbound = Interaction(
        lead_id=lead.id,
        direction="inbound",
        channel="email",
        message_text=message,
        intent_label=intent.label,
        intent_confidence=intent.confidence,
        handled_by="aria",
    )
    db.add(inbound)

    # Update lead state
    lead.current_intent = intent.label
    lead.last_interaction_at = datetime.utcnow()
    new_score = apply_engagement_delta(lead.lead_score, intent.label)
    lead.lead_score = new_score
    lead.lead_quality = score_to_quality(new_score)

    # Handle opt-out
    if intent.label == "not_interested":
        lead.opt_out = True
        lead.status = "lost"
        db.commit()
        return {"status": "opted_out", "intent": intent.label}

    # 3. Check escalation gate — skip AI entirely for these intents
    if should_escalate(intent):
        escalation = Escalation(
            lead_id=lead.id,
            interaction_id=inbound.id,
            reason=intent.label,
        )
        db.add(escalation)
        lead.status = "escalated"
        lead.assigned_to = "human_queue"
        db.commit()
        print(f"[Escalation] Lead {lead.id} escalated — reason: {intent.label}")
        return {"status": "escalated", "reason": intent.label}

    # 4. KB lookup
    kb_entry = get_answer_for_intent(intent.label, db)
    kb_context = f"Q: {kb_entry.question}\nA: {kb_entry.answer}" if kb_entry else ""

    # 5. Build conversation history (last 3 exchanges)
    recent = (
        db.query(Interaction)
        .filter(Interaction.lead_id == lead.id)
        .order_by(Interaction.timestamp.desc())
        .limit(6)
        .all()
    )
    history = [
        {
            "role": "user" if i.direction == "inbound" else "assistant",
            "content": i.message_text or "",
        }
        for i in reversed(recent)
        if i.message_text
    ]

    # 6. Generate draft via LLM
    draft_text = generate_draft(
        lead=lead,
        intent_label=intent.label,
        incoming_message=message,
        conversation_history=history,
        kb_context=kb_context,
    )

    # 7. Save outbound draft
    outbound = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        message_text=draft_text,
        intent_label=intent.label,
        handled_by="aria",
        send_status="pending_approval" if settings.human_approval_mode else "approved",
    )
    db.add(outbound)

    # Send immediately if not in approval mode
    if not settings.human_approval_mode and lead.email:
        subject = f"Re: BeyondSure — {lead.first_name or 'there'}"
        sent = send_email(lead.email, subject, draft_text)
        if sent:
            outbound.send_status = "sent"

    db.commit()

    return {
        "status": "draft_created" if settings.human_approval_mode else "sent",
        "intent": intent.label,
        "confidence": intent.confidence,
        "draft_id": outbound.id,
        "draft_preview": draft_text[:120] + "..." if len(draft_text) > 120 else draft_text,
    }
