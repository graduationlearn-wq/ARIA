"""
Alert Mailer — sends a structured internal alert to the BeyondSure team
when a lead crosses the threshold for human contact.

This is NOT a customer email. It goes to the team inbox (ALERT_EMAIL in .env).

The email is a complete lead dossier — everything a salesperson needs to
pick up the phone with confidence: who they are, what they want, their score,
the conversation so far, and a recommended action.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from models.lead import Lead
from models.interaction import Interaction
from utils.email_sender import send_email
from config import settings


def _score_bar(score: int) -> str:
    """Visual score bar for the email body."""
    filled = round(score / 10)
    return "█" * filled + "░" * (10 - filled) + f"  {score}/100"


def _quality_label(lead: Lead) -> str:
    emoji = {"hot": "🔥", "warm": "🟡", "cold": "🔵", "new": "⚪"}.get(
        lead.lead_quality or "new", "⚪"
    )
    return f"{emoji} {(lead.lead_quality or 'new').upper()}"


def _build_conversation_summary(lead: Lead, db: Session) -> str:
    """Pull the last 6 chat interactions for the email summary."""
    recent = (
        db.query(Interaction)
        .filter(
            Interaction.lead_id == lead.id,
            Interaction.message_type.in_(["chat_in", "chat_out", "first_touch"]),
        )
        .order_by(Interaction.timestamp.asc())
        .limit(10)
        .all()
    )
    if not recent:
        return "(No conversation yet — lead opened the chat link)"

    lines = []
    for i in recent:
        role = "Lead" if i.direction == "inbound" else "ARIA"
        text = (i.message_text or "")[:120]
        if len(i.message_text or "") > 120:
            text += "..."
        lines.append(f"  {role}: {text}")
    return "\n".join(lines)


def _recommended_action(intent: str, lead: Lead) -> str:
    if intent == "demo_request":
        return "Call within 2 hours and confirm a demo slot. They're ready."
    if intent == "escalation_request":
        return "Call immediately — they explicitly asked for a person."
    if lead.willing_for_demo:
        return "Lead confirmed demo interest. Call to lock in a time this week."
    if lead.lead_score >= 70:
        return "Hot lead. Reach out personally — don't let this go to a follow-up."
    if lead.human_priority:
        return "Manually flagged as priority. Personal outreach recommended."
    return "Warm lead showing interest. A personal call would move this forward."


def build_alert_email_body(lead: Lead, intent: str, last_message: str, db: Session) -> tuple[str, str]:
    """
    Returns (subject, body) for the human alert email.
    """
    name = lead.first_name or "Unknown"
    company = lead.company_name or "—"
    state = lead.state or "—"
    lead_type = (lead.lead_type or "unknown").replace("_", " ").title()
    team = f"{lead.team_size} people" if lead.team_size else "—"
    phone = lead.phone or "—"
    email = lead.email or "—"
    software = lead.current_software or ("Yes" if lead.uses_software else "No (managing manually)" if lead.uses_software is False else "—")
    intent_display = intent.replace("_", " ").title()
    conversation = _build_conversation_summary(lead, db)
    action = _recommended_action(intent, lead)
    score_bar = _score_bar(lead.lead_score)
    quality = _quality_label(lead)

    subject = f"🔥 Hot lead alert — {name} (Score: {lead.lead_score}, {(lead.lead_quality or 'new').title()})"
    if intent == "escalation_request":
        subject = f"⚡ Lead requested a person — {name} (act now)"

    body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ARIA LEAD ALERT — BeyondSure
  {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHO
  Name:          {name}
  Company:       {company}
  State:         {state}
  Business type: {lead_type}
  Team size:     {team}
  Phone:         {phone}
  Email:         {email}

SCORE & QUALITY
  {score_bar}
  {quality}

WHAT TRIGGERED THIS ALERT
  Intent detected:  {intent_display}
  Their last message:
  "{last_message}"

PROFILE SIGNALS
  Currently using software:  {software}
  Open to new platform:      {'Yes' if lead.open_to_platform else 'No' if lead.open_to_platform is False else '—'}
  Agreed to demo:            {'Yes' if lead.willing_for_demo else 'No' if lead.willing_for_demo is False else 'Not asked yet'}
  Human priority flag:       {'🚩 YES' if lead.human_priority else 'No'}

CONVERSATION SO FAR
{conversation}

RECOMMENDED ACTION
  → {action}

LINKS
  View full chat:    {settings.base_url}/chat/admin/{lead.id}
  Approval queue:    {settings.base_url}/approval/queue
  Lead record:       {settings.base_url}/leads/{lead.id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This alert was sent by ARIA — BeyondSure Lead Engine.
It will not repeat for this lead unless manually reset.
""".strip()

    return subject, body


def send_human_alert(lead: Lead, intent: str, last_message: str, db: Session) -> bool:
    """
    Send the structured lead dossier to the team inbox.
    Updates lead.alert_sent_at to prevent duplicate alerts.
    Returns True if sent successfully.
    """
    if not settings.alert_email:
        print(f"[Alert] ALERT_EMAIL not set — would have alerted for lead {lead.id} ({intent})")
        return False

    subject, body = build_alert_email_body(lead, intent, last_message, db)
    sent = send_email(settings.alert_email, subject, body)

    if sent:
        lead.alert_sent_at = datetime.utcnow()
        db.commit()
        print(f"[Alert] Human alert sent for lead {lead.id} — {lead.first_name} ({intent})")
    else:
        print(f"[Alert] Failed to send alert for lead {lead.id}")

    return sent
