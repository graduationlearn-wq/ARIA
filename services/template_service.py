"""
Template service — placeholder rendering + default stage templates.

Placeholders use single curly braces, e.g. {lead_name}. Rendering substitutes
known tokens from the Lead row and the logged-in sender; unknown tokens are
left as-is so the person composing can spot and fix them before sending.
"""

import json
import re
from datetime import datetime

from sqlalchemy.orm import Session

from config import settings
from models.email_template import EmailTemplate
from models.lead import Lead
from models.user import User


_TOKEN = re.compile(r"\{([a-z_]+)\}")

# Token → (description, how it's resolved). Shown in the template editor.
PLACEHOLDERS = {
    "lead_name":       "Lead's first name (falls back to 'there')",
    "company_name":    "Lead's company (falls back to 'your company')",
    "lead_email":      "Lead's email address",
    "lead_phone":      "Lead's phone number",
    "lead_type":       "Lead type — broker / agent / IMF…",
    "state":           "Lead's state / location",
    "chat_link":       "Personalised ARIA chat link for this lead",
    "meet_link":       "Saved Google Meet link (blank if none)",
    "demo_preference": "Lead's preferred demo time (blank if none)",
    "sender_name":     "Name of the logged-in team member sending the mail",
    "sender_email":    "Email of the logged-in team member",
    "today":           "Today's date, e.g. 10 Jun 2026",
}


def signature_image_html(sender: User | None, base_url: str) -> str | None:
    """
    The <img> block for the sender's uploaded signature image, or None if they
    haven't uploaded one. Uses an absolute URL so it renders in the recipient's
    mail client. The image is served publicly by routes/signatures.py.
    """
    fn = getattr(sender, "signature_image", None) if sender else None
    if not fn:
        return None
    src = f"{(base_url or '').rstrip('/')}/signatures/{fn}"
    return (f'<img src="{src}" alt="Email signature" '
            f'style="max-width:540px;height:auto;border:0;display:block;">')


def _token_values(lead: Lead, sender: User | None) -> dict[str, str]:
    chat_link = (
        f"{settings.base_url.rstrip('/')}/chat/{lead.chat_token}"
        if lead.chat_token else ""
    )
    return {
        "lead_name":       (lead.first_name or "").strip() or "there",
        "company_name":    (lead.company_name or "").strip() or "your company",
        "lead_email":      lead.email or "",
        "lead_phone":      lead.phone or "",
        "lead_type":       lead.lead_type or "",
        "state":           lead.state or "",
        "chat_link":       chat_link,
        "meet_link":       lead.meet_link or "",
        "demo_preference": lead.demo_preference or "",
        "sender_name":     (sender.name if sender else "") or "The BeyondSure Team",
        "sender_email":    (sender.email if sender else "") or "",
        # The signature is now an uploaded image appended at send time, so the old
        # {signature} text token just resolves to nothing (kept for legacy bodies).
        "signature":       "",
        "today":           datetime.now().strftime("%d %b %Y"),
    }


def render_template(text: str, lead: Lead, sender: User | None = None) -> tuple[str, list[str]]:
    """
    Fill {placeholders} in `text` from the lead + sender.
    Returns (rendered_text, unknown_tokens) — unknown tokens stay in place.
    """
    values = _token_values(lead, sender)
    unknown: list[str] = []

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        if key in values:
            return values[key]
        unknown.append(key)
        return m.group(0)

    return _TOKEN.sub(_sub, text), unknown


def attachment_list(tpl: EmailTemplate) -> list[str]:
    """The template's attachments column parsed as a list (never raises)."""
    try:
        files = json.loads(tpl.attachments or "[]")
        return [f for f in files if isinstance(f, str)]
    except (ValueError, TypeError):
        return []


# ── Default templates (one per key pipeline stage) ────────────────────────────

# Templates end with a sign-off; the sender's uploaded signature image is
# appended automatically at send time (see routes/templates.py send_template).
_SIGNATURE = "Best Regards,"

DEFAULT_TEMPLATES = [
    {
        "name": "Post-Demo — Thank You & Next Steps",
        "stage": "post_demo",
        "subject": "Thank you for attending the BeyondSure demo",
        "body": (
            "Hi {lead_name},\n\n"
            "Thank you for taking the time to attend the BeyondSure product demonstration. "
            "It was a pleasure interacting with you and understanding your business requirements.\n\n"
            "As discussed, the next steps are:\n"
            "- Commercial proposal: {proposal_status}\n"
            "- Next steps: {next_steps}\n"
            "- Integration discussion: {integration_details}\n"
            "- Tentative implementation timeline: {implementation_timeline}\n\n"
            "Please let us know if you have any additional questions or require any further "
            "information. We'd be happy to arrange another discussion if needed.\n\n"
            "We look forward to working with you and taking the next steps together.\n\n" + _SIGNATURE
        ),
        # {proposal_status}/{next_steps}/… are filled in by the sender before sending
        # (they surface as "unknown tokens" in the compose box as a fill-in checklist).
        "attachments": [],
    },
    {
        "name": "Commercial Proposal",
        "stage": "negotiation",
        "subject": "BeyondSure commercial proposal for {company_name}",
        "body": (
            "Hi {lead_name},\n\n"
            "Thank you for your time and the opportunity to understand your requirements.\n\n"
            "Please find the commercial proposal attached for your review. The proposal "
            "includes the pricing and scope discussed during our conversations.\n\n"
            "Kindly review the proposal and let us know if you have any questions or require "
            "any clarification. We would be happy to discuss it further and address any "
            "feedback you may have.\n\n"
            "We look forward to your response and hope to move ahead with the next steps.\n\n" + _SIGNATURE
        ),
        "attachments": ["Lending_Insurance_Proposal.pdf"],
    },
    {
        "name": "Proposal + Company Profile",
        "stage": "interested",
        "subject": "BeyondSure : Proposal and Company Profile for {company_name}",
        "body": (
            "Dear {lead_name},\n\n"
            "As discussed, please find attached the BeyondSure Company Profile and the "
            "Lending Insurance Proposal for your review.\n\n"
            "The proposal outlines how BeyondSure can support {company_name} with embedded "
            "lending insurance solutions, helping enhance customer protection while "
            "creating additional value for your lending ecosystem.\n\n"
            "I would be happy to schedule a discussion to walk you through the proposal "
            "and address any questions you may have.\n\n"
            "Looking forward to your feedback.\n\n" + _SIGNATURE
        ),
        "attachments": ["BeyondSure_Company_Profile.pdf", "Lending_Insurance_Proposal.pdf"],
    },
    {
        "name": "Follow-up Nudge",
        "stage": "follow_up",
        "subject": "Following up — BeyondSure for {company_name}",
        "body": (
            "Hi {lead_name},\n\n"
            "Just checking in on my earlier note. I know things get busy, so I wanted to "
            "keep BeyondSure on your radar.\n\n"
            "If it's easier, you can ask questions any time on our chat: [start here]({chat_link})\n\n"
            "Would a quick 15-minute call this week work for you?\n\n" + _SIGNATURE
        ),
        "attachments": [],
    },
    {
        "name": "Post-Demo Recap",
        "stage": "post_demo",
        "subject": "Thank you for your time — next steps for {company_name}",
        "body": (
            "Dear {lead_name},\n\n"
            "Thank you for taking the time to see BeyondSure in action. I hope the demo "
            "gave you a clear picture of how the platform can work for {company_name}.\n\n"
            "As discussed, I'm attaching our Company Profile for your records. If any "
            "questions came up after the call, I'm happy to walk through them.\n\n"
            "Shall we set up a short follow-up to talk about commercials and rollout?\n\n" + _SIGNATURE
        ),
        "attachments": ["BeyondSure_Company_Profile.pdf"],
    },
    {
        "name": "Commercial Terms Follow-up",
        "stage": "negotiation",
        "subject": "BeyondSure — commercial proposal for {company_name}",
        "body": (
            "Dear {lead_name},\n\n"
            "Further to our discussion, please find the commercial terms we spoke about. "
            "I've kept the structure flexible so we can align it with how {company_name} "
            "prefers to work.\n\n"
            "Happy to get on a call and close out any open points — just let me know a "
            "time that suits you.\n\n" + _SIGNATURE
        ),
        "attachments": [],
    },
    {
        "name": "Welcome Aboard",
        "stage": "won",
        "subject": "Welcome to BeyondSure, {company_name}!",
        "body": (
            "Dear {lead_name},\n\n"
            "Welcome aboard! We're delighted to have {company_name} with BeyondSure.\n\n"
            "Your onboarding lead will reach out within one working day to set up your "
            "account, walk your team through the platform, and plan the rollout.\n\n"
            "If you need anything in the meantime, just reply to this email — it comes "
            "straight to me.\n\n" + _SIGNATURE
        ),
        "attachments": [],
    },
    {
        "name": "Re-engagement (Parked)",
        "stage": "parked",
        "subject": "Picking things back up, {lead_name}?",
        "body": (
            "Hi {lead_name},\n\n"
            "When we last spoke, the timing wasn't quite right — completely understood. "
            "I wanted to check in and see if things have changed at {company_name}.\n\n"
            "A lot has improved on our side since then, and I'd love to show you what's "
            "new. You can also reach us any time on chat: [start here]({chat_link})\n\n" + _SIGNATURE
        ),
        "attachments": [],
    },
]


def seed_templates(db: Session) -> None:
    """
    Add any default templates that aren't present yet, matched by name. Idempotent:
    won't duplicate, and won't resurrect a template the team deleted (delete is a
    soft is_active flip, so the row still exists by name and is skipped here).
    """
    existing = {name for (name,) in db.query(EmailTemplate.name).all()}
    added = 0
    for t in DEFAULT_TEMPLATES:
        if t["name"] in existing:
            continue
        db.add(EmailTemplate(
            name=t["name"], stage=t["stage"],
            subject=t["subject"], body=t["body"],
            attachments=json.dumps(t["attachments"]),
        ))
        added += 1
    if added:
        db.commit()
        print(f"[Templates] Seeded {added} email template(s).")
