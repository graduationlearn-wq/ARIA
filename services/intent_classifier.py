"""
Intent Classifier — Phase 1 (rules-based keyword matching).

Returns an intent label and a confidence score (0.0–1.0).
In Phase 3 this gets replaced with an ML classifier trained on
the interactions table, but the label names stay the same.
"""

import re
from dataclasses import dataclass


@dataclass
class IntentResult:
    label: str
    confidence: float  # 0.0 – 1.0


# ── Keyword maps ──────────────────────────────────────────────────────────────
# Order matters — more specific / higher-risk intents come first.

INTENT_KEYWORDS: dict[str, list[str]] = {
    # Always escalate — check these first
    "bot_detection": [
        "are you a bot", "is this a bot", "am i talking to ai", "is this automated",
        "are you human", "talking to ai", "is this ai", "robot", "are you an ai",
    ],
    "escalation_request": [
        "talk to someone", "speak to a person", "connect me to",
        "speak to sales", "talk to your manager", "real agent", "real person",
        "want to speak to", "speak with someone", "call me back", "schedule a call with"
    ],

    # Positive signals
    "demo_request": [
        "want to see", "show me", "book demo", "schedule demo", "book a call",
        "schedule a call", "demo", "when can we meet", "set up a call",
        "let's connect", "interested in demo", "want a demo", "can i see"
    ],
    "positive_signal": [
        "sounds good", "sounds interesting", "looks good", "looks useful",
        "tell me more", "interesting", "yes", "okay", "ok", "sure", "please share",
        "send details", "would like to know more", "want to know"
    ],

    # Information queries
    "pricing_query": [
        "how much", "cost", "price", "pricing", "plans", "subscription",
        "fees", "charges", "payment", 
        "annual plan", "monthly plan", "per user", "per month"
    ],
    "feature_query": [
        "does it support", "can it do", "does it have", "what about",
        "integration", "reports", "feature", "functionality", "works with",
        "compatible", "can i track", "does it track", "what does it do",
        "how does it work", "tell me about the platform"
    ],
    "onboarding_query": [
        "how do i start", "get started", "setup", "training", "how long",
        "migrate", "import data", "onboarding", "sign up", "register",
        "how to use", "easy to use", "difficult to use"
    ],
    "greeting": [
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "namaste", "hii", "helo"
    ],

    # Objections
    "objection_cost": [
        "too expensive", "no budget", "can't afford", "costly", "cheaper",
        "budget constraint", "out of budget", "not affordable", "high price",
        "reduce price", "discount"
    ],
    "objection_timing": [
        "not now", "busy right now", "call me later", "call later", "remind me",
        "after festival", "some time later", "right now not", "currently busy",
        "will get back", "contact me later", "not the right time", "next month",
        "later i am", "busy at"
    ],
    "objection_switching": [
        "already using", "already use", "use another", "happy with current",
        "hard to switch", "team won't adopt", "currently using", "we use another",
        "have our own", "own system", "don't want to change", "switching is hard"
    ],

    # Negative / exit
    "not_interested": [
        "not interested", "remove me", "stop messaging", "don't contact",
        "no thanks", "unsubscribe", "opt out", "don't call", "please stop",
        "block", "spam"
    ],
}


def classify_intent(message: str) -> IntentResult:
    """
    Classify the intent of an incoming message.
    Returns the matched intent and a confidence score.
    Falls back to 'unclear' with confidence 0.3 if nothing matches.
    """
    text = message.lower().strip()
    text_clean = re.sub(r"[^\w\s]", " ", text)

    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            kw_clean = re.sub(r"[^\w\s]", " ", kw.lower())
            if kw_clean in text_clean:
                confidence = 1.0 if kw_clean == text_clean.strip() else 0.85
                return IntentResult(label=intent, confidence=confidence)

    return IntentResult(label="unclear", confidence=0.3)


def should_escalate(intent: IntentResult) -> bool:
    """Return True if this intent must bypass ARIA and go straight to a human."""
    return intent.label in ("bot_detection", "escalation_request")
