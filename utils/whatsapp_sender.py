"""
WhatsApp Sender — sends messages via Meta WhatsApp Cloud API.

SETUP (one-time):
  1. Go to https://developers.facebook.com → create an App → add WhatsApp product
  2. In App Dashboard → WhatsApp → API Setup:
       • Copy "Phone Number ID"  → WHATSAPP_PHONE_NUMBER_ID in .env
       • Generate a temporary token → WHATSAPP_API_TOKEN in .env
         (for production, create a System User with a permanent token)
  3. In .env:
       WHATSAPP_API_TOKEN=EAAxxxxx...
       WHATSAPP_PHONE_NUMBER_ID=123456789012345

HOW OUTGOING MESSAGES WORK:
  • Within 24 hours of a lead replying to you → free-form text works ✅
  • Outside 24 hours OR first contact → needs a pre-approved template
  • Demo confirmations sent right after booking = within window = fine ✅

TESTING:
  Meta gives you a test sandbox with 5 registered test numbers.
  Add your own number there to test before going live.
"""

import requests
from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Core sender
# ─────────────────────────────────────────────────────────────────────────────

def send_whatsapp_message(to_number: str, message: str) -> bool:
    """
    Send a free-form WhatsApp text message.

    to_number: international format, any style — +91 98765 43210, 919876543210, etc.
    Returns True if the API accepted the message.
    """
    if not settings.whatsapp_api_token or not settings.whatsapp_phone_number_id:
        print(f"[WhatsApp] API not configured — skipping send to {to_number}")
        print(f"[WhatsApp] Add WHATSAPP_API_TOKEN + WHATSAPP_PHONE_NUMBER_ID to .env")
        print(f"[WhatsApp] Message preview: {message[:120]}")
        return False

    # Normalise number: strip everything except digits
    clean = "".join(c for c in (to_number or "") if c.isdigit())
    if not clean:
        print(f"[WhatsApp] Invalid phone number: {to_number!r} — skipping")
        return False

    url = (
        f"https://graph.facebook.com/v18.0/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": clean,
        "type": "text",
        "text": {
            "body": message,
            "preview_url": False,   # set True if message contains a link you want previewed
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        if resp.ok:
            print(f"[WhatsApp] ✓ Sent to {clean} — {len(message)} chars")
            return True
        else:
            print(f"[WhatsApp] ✗ Failed ({resp.status_code}): {resp.text[:300]}")
            return False
    except requests.exceptions.Timeout:
        print(f"[WhatsApp] Timeout sending to {clean}")
        return False
    except Exception as e:
        print(f"[WhatsApp] Error sending to {clean}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# High-level senders
# ─────────────────────────────────────────────────────────────────────────────

def send_demo_whatsapp(lead, preferred_time: str) -> bool:
    """
    Send a demo confirmation WhatsApp to the lead immediately after they book.
    Includes Google Meet link and reassurance that our team will call them.
    """
    if not lead.phone:
        print(f"[WhatsApp] No phone for lead {lead.id} ({lead.first_name}) — skipping")
        return False

    name = (lead.first_name or "there").strip()
    phone_display = lead.phone or "your registered number"
    meet_link = settings.google_meet_link

    if meet_link:
        body = (
            f"Hi {name}! 👋\n\n"
            f"Your *BeyondSure demo is confirmed!* 🎉\n\n"
            f"📅 *Time:* {preferred_time}\n"
            f"📞 *How it works:* Our team will call you directly on {phone_display} — "
            f"you don't need to do anything.\n\n"
            f"🔗 *Google Meet link (for reference):*\n{meet_link}\n\n"
            f"We'll also send this to your email. Talk soon! 😊\n"
            f"— The BeyondSure Team"
        )
    else:
        body = (
            f"Hi {name}! 👋\n\n"
            f"Your *BeyondSure demo is confirmed!* 🎉\n\n"
            f"📅 *Time:* {preferred_time}\n"
            f"📞 *How it works:* Our team will call you directly on {phone_display}.\n\n"
            f"No need to do anything — just be available when we call! 😊\n"
            f"— The BeyondSure Team"
        )

    return send_whatsapp_message(lead.phone, body)


def send_alert_whatsapp(lead, intent: str) -> bool:
    """
    Notify the BeyondSure team via WhatsApp when a hot lead comes in.
    Sent to WHATSAPP_BUSINESS_NUMBER (the team's number, not the lead's).
    """
    if not settings.whatsapp_business_number:
        print("[WhatsApp] WHATSAPP_BUSINESS_NUMBER not set — skipping team alert")
        return False

    name = lead.first_name or "Unknown"
    company = lead.company_name or "—"
    phone = lead.phone or "—"
    score = lead.lead_score or 0
    quality = (lead.lead_quality or "new").upper()
    intent_display = intent.replace("_", " ").title()

    body = (
        f"🔥 *Hot Lead Alert — BeyondSure*\n\n"
        f"👤 *Name:* {name}\n"
        f"🏢 *Company:* {company}\n"
        f"📞 *Phone:* {phone}\n"
        f"💡 *Intent:* {intent_display}\n"
        f"📊 *Score:* {score}/100 ({quality})\n\n"
        f"➡️ View chat: {settings.base_url}/chat/admin/{lead.id}"
    )

    return send_whatsapp_message(settings.whatsapp_business_number, body)
