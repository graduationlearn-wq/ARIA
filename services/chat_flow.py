"""
Chat Flow Service — guided qualification flow matching the WhatsApp automation design.

Flow order (mirrors the designed WhatsApp flow):
  1. Uses software?  (YES/NO — branches here)
     └─ YES → Which software? (open text)
     └─ NO  → Affirming response, continue
  2. Business type   (Agent / IMF / Broker / POSP / Advisor / Others)
  3. Team size       (free number input)
  4. Company name    (if not already captured from form)
  5. Website         (open text, with "I need one" option)
  6. Demo interest   (Yes book / Maybe later / Just exploring / Talk to expert)
     └─ Yes        → Calendar link + schedule
     └─ Maybe/Exploring → Set re_engage_after (scheduler picks up in 3 days)
     └─ Talk to expert → Escalate immediately

Every answer writes back to the Lead CRM record in real time.
The chat is a qualification engine. Every message either updates a field or updates a score.
"""

import re
from models.lead import Lead


# ─────────────────────────────────────────────────────────────────────────────
# Guided flow steps
# ─────────────────────────────────────────────────────────────────────────────
# Each step has:
#   field      — the Lead column this step is trying to fill
#   check      — lambda(lead) → True means this step still needs answering
#   message    — the question ARIA asks (or message_fn for dynamic text)
#   options    — quick-reply buttons (empty list = text input only)
#   affirm     — optional short affirmation shown BEFORE the question
#   affirm_fn  — dynamic affirm based on lead state (overrides affirm)

GUIDED_STEPS = [
    # ── Step 1: Software usage ─────────────────────────────────────────────
    {
        "field": "uses_software",
        "check": lambda lead: lead.uses_software is None,
        "message": (
            "Quick question to get you the right info 👇\n"
            "Are you currently using any software to manage your leads or client data?"
        ),
        "options": ["Yes, I use something", "No, managing manually"],
    },

    # ── Step 1b: Which software (only if YES) ─────────────────────────────
    {
        "field": "current_software",
        "check": lambda lead: lead.uses_software is True and not lead.current_software,
        "affirm": "Got it 👍",
        "message": (
            "What are you currently using?\n"
            "(CRM, Lead Management, Excel, Insur-tech SaaS or something else?)"
        ),
        "options": [],  # free text — they type the name
    },

    # ── Step 2: Business type ──────────────────────────────────────────────
    {
        "field": "lead_type",
        "check": lambda lead: lead.lead_type in (None, "unknown"),
        # Affirm differs: NO software branch gets encouragement, YES branch gets none
        "affirm_fn": lambda lead: (
            "That's actually perfect timing! 😊\n"
            "Most of our clients started the same way—and now save hours every week."
            if lead.uses_software is False else None
        ),
        "message": "Can I ask: what type of business are you?",
        "options": ["Agent", "IMF", "Broker", "POSP", "Advisor", "Others"],
    },

    # ── Step 3: Team size ──────────────────────────────────────────────────
    {
        "field": "team_size",
        "check": lambda lead: lead.team_size is None,
        "affirm": "Great! 🙌",
        "message_fn": lambda lead: (
            f"To understand your setup better:\n"
            f"How many people are in your "
            f"{'brokerage' if (lead.lead_type or '') == 'broker' else 'team'}?\n"
            f"(Just reply with a number eg: 1, 2, 5)"
        ),
        "options": [],  # free text — matches the WhatsApp design intent
    },

    # ── Step 4: Company name (only if not captured from form) ─────────────
    {
        "field": "company_name",
        "check": lambda lead: not (lead.company_name or "").strip(),
        "affirm": "Thanks! 🙏",
        "message": (
            "A couple of quick details so we can personalise things for you:\n\n"
            "What's your company name?"
        ),
        "options": [],
    },

    # ── Step 5: Website ────────────────────────────────────────────────────
    {
        "field": "company_website",
        "check": lambda lead: not lead.company_website,
        "message": (
            "And your website?\n"
            "(If you don't have one yet, just say so — "
            "we can help with that too 😊)"
        ),
        "options": ["I don't have one yet", "I need a website"],
    },

    # ── Step 6: Demo interest ──────────────────────────────────────────────
    # Special branching handled in chat route via _action key.
    {
        "field": "willing_for_demo",
        "check": lambda lead: lead.willing_for_demo is None,
        "message": "Would you like to quickly see how BeyondSure works? 👀",
        "options": [
            "Yes, book a demo 📅",
            "Maybe later",
            "Just exploring",
            "Talk to an expert 📞",
        ],
    },

    # ── Step 7: Preferred call time (only after demo confirmed) ───────────
    {
        "field": "demo_preference",
        "check": lambda lead: lead.willing_for_demo is True and not lead.demo_preference,
        "message": (
            "When works best for a quick call? ☎️\n\n"
            "Our team will call you directly — you don't need to do anything, "
            "just be available at your number."
        ),
        "options": [
            "This week — mornings",
            "This week — evenings",
            "Next week",
            "Flexible — anytime",
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Welcome message
# ─────────────────────────────────────────────────────────────────────────────

def get_welcome_message(lead: Lead) -> dict:
    """First message ARIA sends when a lead opens the chat link for the first time."""
    name = (lead.first_name or "").strip()
    greeting = f"Hi {name}! 👋" if name else "Hi! 👋"

    body = (
        f"{greeting} Thanks for your interest in BeyondSure!\n\n"
        f"We help insurance businesses manage leads, policies & commissions "
        f"all in one place—so you can save time and grow faster 🚀\n\n"
        f"I'm ARIA, your BeyondSure assistant. I'll ask a few quick questions "
        f"to understand your setup — takes about 2 minutes."
    )
    return {
        "message": body,
        "options": ["Let's go! 👍", "I have a specific question"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Flow helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_next_guided_step(lead: Lead) -> dict | None:
    """
    Returns the next unanswered guided step, or None if the flow is complete.
    The returned dict includes an optional affirm message prefix.
    """
    for step in GUIDED_STEPS:
        if step["check"](lead):
            msg_fn = step.get("message_fn")
            base_message = msg_fn(lead) if msg_fn else step["message"]

            # Dynamic affirm takes priority over static
            affirm = None
            if "affirm_fn" in step:
                affirm = step["affirm_fn"](lead)
            elif "affirm" in step:
                affirm = step["affirm"]

            full_message = f"{affirm}\n\n{base_message}" if affirm else base_message

            return {
                "field":   step["field"],
                "message": full_message,
                "options": step.get("options", []),
            }
    return None


def parse_guided_answer(field: str, answer: str, lead: Lead) -> dict:
    """
    Parse the lead's answer for a given field.
    Returns a dict of {column: value} to write to the Lead record.
    May also include a special "_action" key for routing logic in the chat handler:
      _action = "demo_book"    → show calendar link
      _action = "reengage"     → set re_engage_after, send warm farewell
      _action = "escalate"     → trigger human alert immediately
    Returns {} if the answer is ambiguous and nothing should be written.
    """
    ans = answer.lower().strip()

    if field == "uses_software":
        if "yes" in ans or "use" in ans or "using" in ans:
            return {"uses_software": True}
        if "no" in ans or "manual" in ans or "not" in ans:
            return {"uses_software": False}
        return {}

    elif field == "current_software":
        # Store whatever they typed as the software name
        sw = extract_software_name(answer) or answer.strip().title()
        return {"current_software": sw[:200]}

    elif field == "lead_type":
        mapping = {
            "agent":   "agent",
            "imf":     "imf",
            "broker":  "broker",
            "posp":    "posp_advisor",
            "advisor": "advisor",
            "others":  "advisor",   # fallback; human_notes will flag for review
            "other":   "advisor",
        }
        for k, v in mapping.items():
            if k in ans:
                updates = {"lead_type": v}
                if "other" in ans:
                    # Flag for human review — we don't know their exact type
                    updates["human_notes"] = (
                        (lead.human_notes or "") +
                        "\n[Lead selected 'Others' for business type — needs manual review]"
                    ).strip()
                return updates
        return {}

    elif field == "team_size":
        # Exact number from free text
        nums = re.findall(r"\d+", ans)
        if nums:
            return {"team_size": int(nums[0])}
        # Fallback word matching
        if "just me" in ans or "solo" in ans or "only me" in ans:
            return {"team_size": 1}
        return {}

    elif field == "company_name":
        name = answer.strip()
        if name and len(name) > 1:
            return {"company_name": name[:200]}
        return {}

    elif field == "company_website":
        low = answer.lower().strip()
        if "don't have" in low or "dont have" in low or "no website" in low:
            return {"company_website": "none"}
        if "need a website" in low or "need one" in low:
            return {"company_website": "needs_website"}
        # Store whatever URL they typed
        url = answer.strip()
        if url:
            return {"company_website": url[:300]}
        return {}

    elif field == "willing_for_demo":
        if "yes" in ans or "book" in ans or "demo" in ans or "📅" in ans:
            return {"willing_for_demo": True, "_action": "demo_book"}
        if "maybe" in ans or "later" in ans or "exploring" in ans:
            return {"_action": "reengage"}
        if "talk" in ans or "expert" in ans or "call" in ans or "📞" in ans:
            return {"_action": "escalate"}
        return {}

    elif field == "demo_preference":
        # Store whatever they said as the preference — no strict parsing needed
        pref = answer.strip()
        if pref:
            return {"demo_preference": pref[:200], "_action": "demo_confirmed"}
        return {}

    return {}


def extract_software_name(message: str) -> str | None:
    """Try to identify a known software name from free text."""
    known = [
        "turtlemint", "policyboss", "crmnext", "salesforce", "zoho",
        "leadsquared", "freshsales", "hubspot", "excel", "google sheets",
        "posist", "insurancedekho", "coverfox", "renewbuy", "polifyx",
        "whatsapp", "telegram", "spreadsheet",
    ]
    lower = message.lower()
    for sw in known:
        if sw in lower:
            return sw.title()
    # Pattern: "I use X" or "using X"
    match = re.search(r"(?:use|using)\s+([A-Z][A-Za-z0-9]+)", message)
    if match:
        return match.group(1)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Post-flow helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_flow_complete_message(lead: Lead, calendar_url: str = "") -> dict:
    """
    Message + options shown when the full guided flow is complete
    and willing_for_demo was confirmed.
    """
    name = (lead.first_name or "").strip()
    suffix = f", {name}" if name else ""

    if calendar_url:
        msg = (
            f"Awesome{suffix}! 🙌\n\n"
            f"Here's a quick link to book your demo at your convenience:\n"
            f"{calendar_url}\n\n"
            f"Or I can help schedule it for you — what time works best this week?"
        )
        options = ["This week works", "Next week is better", "Send me info first"]
    else:
        msg = (
            f"Awesome{suffix}! 🙌\n\n"
            f"I've noted your interest in a demo. Our team will reach out shortly "
            f"to confirm a time. In the meantime, feel free to ask anything!"
        )
        options = ["Tell me about pricing", "What features does it have?", "How long is the demo?"]

    return {"message": msg, "options": options}


def get_reengage_message(lead: Lead) -> dict:
    """
    Warm farewell when lead says 'Maybe later' or 'Just exploring'.
    Sets up re-engagement — scheduler will nudge them in 3 days.
    """
    name = (lead.first_name or "").strip()
    msg = (
        f"No worries at all 😊\n\n"
        f"Just so you know — many insurance teams switch when they're ready to grow faster ⏳\n\n"
        f"I'll check back in a few days. Feel free to message anytime, "
        f"{'and have a great day ' + name + '!' if name else 'take care!'}"
    )
    return {"message": msg, "options": []}


# ─────────────────────────────────────────────────────────────────────────────
# Alert threshold
# ─────────────────────────────────────────────────────────────────────────────

ALERT_INTENTS = {"demo_request", "escalation_request"}
ALERT_SCORE_THRESHOLD = 70


def should_alert_human(lead: Lead, intent: str) -> bool:
    """
    True if the system should fire a human alert for this lead.
    Only fires once per lead (alert_sent_at blocks repeat).
    """
    if lead.alert_sent_at:
        return False
    if intent in ALERT_INTENTS:
        return True
    if lead.willing_for_demo and lead.lead_score >= ALERT_SCORE_THRESHOLD:
        return True
    if lead.human_priority and intent in ("positive_signal", "pricing_query", "feature_query"):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Contextual quick-reply options for open chat
# ─────────────────────────────────────────────────────────────────────────────

INTENT_OPTIONS: dict[str, list[str]] = {
    "pricing_query":       ["Tell me more", "I'd like a demo 📅", "Talk to someone"],
    "feature_query":       ["Tell me more", "Book a demo", "Other question"],
    "demo_request":        ["Yes, this week", "Schedule next week", "Just exploring"],
    "positive_signal":     ["I'd like a demo 📅", "Tell me more", "Talk to your team"],
    "objection_cost":      ["Tell me about ROI", "Are there flexible plans?", "Talk to the team"],
    "objection_timing":    ["Remind me next month", "Send me info", "Let's talk now"],
    "objection_switching": ["How easy is migration?", "What makes you different?", "Talk to someone"],
    "onboarding_query":    ["How long does setup take?", "Do you offer training?", "See a demo"],
    "greeting":            ["Tell me about BeyondSure", "I want a demo 📅", "Ask about pricing"],
}


def get_contextual_options(intent: str) -> list[str]:
    return INTENT_OPTIONS.get(intent, [])
