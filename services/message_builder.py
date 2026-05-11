"""
Message Builder — constructs personalised first-touch and follow-up messages.

Rules applied (in order):
  1. If team_size is already known → skip team size question, ask pain point instead.
  2. If willing_for_demo is True → offer to book a slot directly.
  3. If uses_software is False → add "you're in the right place" line.
  4. If lead_type is "broker" → use "brokerage" instead of "team".
  5. Fallback gracefully when fields are missing.
"""

from models.lead import Lead


def _salutation(lead: Lead) -> str:
    name = (lead.first_name or "").strip().title()
    return f"Hi {name}" if name else "Hi there"


def _company_phrase(lead: Lead) -> str:
    name = (lead.company_name or "").strip()
    return f" at {name}" if name else ""


def _lead_type_word(lead: Lead) -> str:
    lt = (lead.lead_type or "unknown").lower()
    mapping = {
        "broker": "broker",
        "imf": "insurance professional",
        "agent": "agent",
        "insurance_agent": "agent",
        "posp_advisor": "advisor",
        "advisor": "advisor",
    }
    return mapping.get(lt, "insurance professional")


def build_first_touch(lead: Lead) -> str:
    """
    Build the personalised first-touch email/WhatsApp message.
    """
    greeting = _salutation(lead)
    lt_word = _lead_type_word(lead)
    company_phrase = _company_phrase(lead)
    is_broker = (lead.lead_type or "").lower() == "broker"
    team_word = "brokerage" if is_broker else "team"

    # Core intro
    intro = (
        f"{greeting},\n\n"
        f"Thanks for your interest in BeyondSure — we help insurance {lt_word}s "
        f"manage leads, clients, and commissions in one place."
    )

    # Optional "right place" line when they have no current software
    right_place = ""
    if lead.uses_software is False:
        right_place = "\nSounds like you're looking for something new — you're in the right place."

    # Closing question — depends on what we already know
    if lead.willing_for_demo is True:
        closing = (
            f"\n\nYou mentioned you're open to a quick demo — "
            f"want to pick a time this week? I can do a 15-minute walkthrough at your convenience."
        )
    elif lead.team_size is not None:
        # We already know team size, ask about pain point instead
        closing = (
            f"\n\nWhat's the biggest challenge your {team_word}{company_phrase} "
            f"faces with managing clients right now?"
        )
    else:
        # Default — ask team size (our best qualifying question)
        closing = (
            f"\n\nQuick question — how many people are currently on your {team_word}"
            f"{company_phrase}?"
        )

    return f"{intro}{right_place}{closing}"


def build_followup_1(lead: Lead) -> str:
    """
    Follow-up message sent 24 hours after first touch if no reply.
    Deliberately different from the first message — never repeat.
    """
    greeting = _salutation(lead)
    return (
        f"{greeting}, just checking in — did you get a chance to see my earlier message?\n\n"
        f"Happy to answer any questions or set up a quick 15-min demo whenever suits you."
    )


def build_followup_2(lead: Lead) -> str:
    """
    Final automated follow-up at 72 hours. After this, hand off to human call.
    """
    greeting = _salutation(lead)
    return (
        f"{greeting}, I'll keep this short — we built BeyondSure specifically for "
        f"insurance professionals managing growing teams.\n\n"
        f"If now isn't the right time, just let me know and I won't follow up. "
        f"But if you'd like a quick look, I'm happy to show you in 15 minutes.\n\n"
        f"Reply STOP anytime to unsubscribe."
    )


def build_followup_7day(lead: Lead) -> str:
    """
    Final automated nudge — 7 days after follow-up 2. Warm, no pressure.
    After this, lead goes to needs_call and human handles it.
    """
    greeting = _salutation(lead)
    return (
        f"{greeting}, one last note from us 🙏\n\n"
        f"We know you're busy running your business — that's exactly why we built BeyondSure.\n\n"
        f"If you ever want to see how it could save your {_lead_type_word(lead)} team time, "
        f"just reply and we'll set something up in 15 minutes. "
        f"Wishing you all the best until then!\n\n"
        f"Reply STOP anytime to unsubscribe."
    )


def build_reengagement(lead: Lead) -> str:
    """
    Sent when a lead said 'maybe later' in chat and their re_engage_after
    timestamp has passed (default 3 days). Picks up the conversation warmly.
    """
    greeting = _salutation(lead)
    lt_word = _lead_type_word(lead)
    return (
        f"{greeting}, just checking in 😊\n\n"
        f"You mentioned you wanted to revisit BeyondSure — many {lt_word}s "
        f"we work with feel the same way at first, and once they see it in action "
        f"they wonder why they waited.\n\n"
        f"Would you like a quick 15-minute look? No pressure at all."
    )


def build_subject_line(lead: Lead, message_number: int = 1) -> str:
    """Generate an email subject line."""
    name = (lead.first_name or "").strip().title()
    subjects = {
        1: f"Manage your insurance business better, {name}" if name else "Manage your insurance business better",
        2: "Just checking in — BeyondSure",
        3: "Last message from BeyondSure",
    }
    return subjects.get(message_number, "BeyondSure — Insurance Platform")
