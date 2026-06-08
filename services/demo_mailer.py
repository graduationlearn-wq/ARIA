"""
Demo Confirmation Mailer — sends a meeting confirmation to the lead.

Sent when a lead confirms a demo and shares their preferred call time.
Contains:
  - Google Meet link
  - Preferred time they selected
  - Clear message: "Our team will call you — no need to join the link beforehand"
  - What to expect in the demo

This is a lead-facing email (not internal like alert_mailer).
"""

from models.lead import Lead
from utils.email_sender import send_email
from config import settings  # used for base_url (chat link in footer)


def send_demo_confirmation(lead: Lead, preferred_time: str) -> bool:
    """
    Send the demo confirmation email to the lead.
    Returns True if sent successfully.
    """
    if not lead.email:
        print(f"[Demo Mailer] No email for lead {lead.id} — skipping confirmation")
        return False

    name = (lead.first_name or "there").strip()
    phone = lead.phone or "your registered number"

    subject = f"Your BeyondSure demo is confirmed! 🎉"

    body = f"""Hi {name},

Great news — your BeyondSure demo is all set! 🙌

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR DEMO DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅  Preferred time:   {preferred_time}
📞  How it works:     Our team will call you directly on {phone}

You don't need to do anything — just be available when we call!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT TO EXPECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅  Quick 15-minute walkthrough
✅  See exactly how BeyondSure works for your business
✅  Ask any questions — our team knows the product inside out
✅  No pressure, no commitment

Our team will confirm the exact time shortly.

Talk soon! 😊
The BeyondSure Team

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Questions? Reply to this email or [chat with us]({settings.base_url}/chat/{lead.chat_token}).
""".strip()

    sent = send_email(lead.email, subject, body)
    if sent:
        print(f"[Demo Mailer] Confirmation sent to {lead.email} — preferred: {preferred_time}")
    else:
        print(f"[Demo Mailer] Failed to send confirmation to {lead.email}")
    return sent
