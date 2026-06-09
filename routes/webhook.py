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

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

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
from services.auth_service import next_owner_id
from utils.email_sender import send_email
from config import settings

router = APIRouter(prefix="/webhook", tags=["Webhook"])


# ── Helper: find duplicate lead by email or phone ────────────────────────────
def _find_duplicate(email: str | None, phone: str | None, db: Session) -> Lead | None:
    """
    Returns an existing Lead if email or phone already exists in the DB.
    Email match takes priority. Phone match is a fallback.
    Returns None if no duplicate found.
    """
    if not email and not phone:
        return None

    filters = []
    if email:
        filters.append(Lead.email == email.strip().lower())
    if phone:
        # strip spaces/dashes for comparison
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        filters.append(Lead.phone == clean_phone)

    return db.query(Lead).filter(or_(*filters)).first()


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


# ── Helper: append CTA buttons to email body ─────────────────────────────────
def _append_cta(body: str, chat_url: str, whatsapp_url: str | None) -> str:
    """
    Appends the two CTA links (chat + WhatsApp) to the email body.

    Links use [text](url) markdown — email_sender renders them as hidden
    hyperlinks in the HTML part (raw URL never shown) while keeping a
    'text: url' fallback in the plain-text part.
    """
    cta = f"\n\n──────────────────────────────\n"
    cta += f"💬  [Chat with us now (instant)]({chat_url})\n"
    if whatsapp_url:
        cta += f"📱  [Continue on WhatsApp]({whatsapp_url})\n"
    cta += "──────────────────────────────"
    return body + cta


# ── POST /webhook/lead ────────────────────────────────────────────────────────
@router.post("/lead")
def receive_lead(payload: LeadWebhookPayload, db: Session = Depends(get_db)):
    """
    Called by Facebook/Instagram lead ad form on every new submission.
    Creates the lead, scores it, and queues the first-touch message.

    Returns a LeadResponse dict plus a `duplicate` flag:
      - duplicate=False → fresh lead, first-touch queued
      - duplicate=True  → lead already exists, no new record created
    """

    # 0. Deduplication check
    existing = _find_duplicate(payload.email, payload.phone, db)
    if existing:
        existing.last_interaction_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        print(
            f"[Webhook] Duplicate lead — skipped. "
            f"Matched: {existing.first_name} | {existing.email} | {existing.phone} (id={existing.id})"
        )
        return {
            "duplicate": True,
            "id": existing.id,
            "first_name": existing.first_name,
            "email": existing.email,
            "lead_quality": existing.lead_quality,
            "lead_score": existing.lead_score,
            "status": existing.status,
            "message": "Duplicate lead — existing record updated (last_interaction_at refreshed).",
        }

    # 1. Create Lead record (normalise email to lowercase)
    lead = Lead(
        first_name=payload.first_name,
        email=payload.email.strip().lower() if payload.email else None,
        phone=payload.phone.strip().replace(" ", "").replace("-", "") if payload.phone else None,
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
        consent_logged_at=datetime.now(timezone.utc),
        owner_id=next_owner_id(db),  # round-robin to the next employee
    )
    db.add(lead)
    db.flush()  # get lead.id before commit

    # 2. Score the lead
    score, quality = score_lead(lead)
    lead.lead_score = score
    lead.lead_quality = quality

    # 3. Build first-touch message with chat link
    chat_url = f"{settings.base_url}/chat/{lead.chat_token}"
    wa_number = settings.whatsapp_business_number
    whatsapp_url = f"https://wa.me/{wa_number}?text=Hi%2C+I%27m+interested+in+BeyondSure" if wa_number else None

    message_body = build_first_touch(lead)
    message_body_with_cta = _append_cta(message_body, chat_url, whatsapp_url)
    subject = build_subject_line(lead, message_number=1)

    # 4. Create outbound interaction (draft or sent)
    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        message_text=message_body_with_cta,
        message_type="first_touch",
        handled_by="aria",
        send_status="pending_approval" if settings.human_approval_mode else "approved",
    )
    db.add(interaction)

    # 5. Send immediately if not in approval mode
    if not settings.human_approval_mode and lead.email:
        sent = send_email(lead.email, subject, message_body_with_cta)
        if sent:
            interaction.send_status = "sent"
            lead.first_response_at = datetime.now(timezone.utc)
            lead.status = "contacted"
            lead.last_interaction_at = datetime.now(timezone.utc)
            print(f"[Webhook] Chat link sent: {chat_url}")

    db.commit()
    db.refresh(lead)

    print(
        f"[Webhook] New lead: {lead.first_name} | {lead.email} | "
        f"Score: {lead.lead_score} | Quality: {lead.lead_quality} | "
        f"Draft status: {interaction.send_status}"
    )
    print(f"[Webhook] Chat link: {chat_url}")
    return {
        "duplicate": False,
        "id": lead.id,
        "first_name": lead.first_name,
        "email": lead.email,
        "lead_quality": lead.lead_quality,
        "lead_score": lead.lead_score,
        "status": lead.status,
        "message": f"Lead created. Draft queued ({interaction.send_status}).",
    }


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
    lead.last_interaction_at = datetime.now(timezone.utc)
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
