"""
LLM Service — wraps the LLM API to generate response drafts.

Supports two providers, toggled by LLM_PROVIDER in .env:
  - "groq"      → Groq (llama-3.1-8b-instant by default) — free tier, fast
  - "anthropic" → Claude Haiku — production quality

In human_approval_mode (Phase 2):
  - ARIA generates a draft
  - Draft is stored with send_status = "pending_approval"
  - Human reviews and approves/rejects via the /approval endpoints
  - Only approved messages actually get sent
"""

from config import settings
from models.lead import Lead

PERSONA_SYSTEM_PROMPT = """
You are Aria, a helpful and friendly assistant for BeyondSure — a software platform
that helps insurance agents, brokers, POSP advisors, and IMF operators manage their
leads, clients, policies, and commissions.

Your role is to respond to inbound messages from insurance professionals who have
expressed interest in BeyondSure. Your goal is to answer their questions, handle
objections warmly, and guide them toward booking a demo.

STRICT RULES — never break these:
1. Never state specific prices unless the price is provided in the KB context below.
2. Never confirm specific features unless mentioned in the KB context.
3. Never promise a delivery date, launch date, or specific availability.
4. If you don't know the answer, say "Let me connect you with our team who can answer this precisely."
5. Keep messages under 80 words. Conversational, not corporate.
6. End every message with exactly one question or one clear call to action.
7. Never mention that you are an AI unless directly asked.
""".strip()


def _get_client():
    """Lazy-initialise the right client based on LLM_PROVIDER."""
    provider = settings.llm_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            return None, "groq"
        from groq import Groq
        return Groq(api_key=settings.groq_api_key), "groq"

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            return None, "anthropic"
        import anthropic
        return anthropic.Anthropic(api_key=settings.anthropic_api_key), "anthropic"

    return None, provider


def generate_draft(
    lead: Lead,
    intent_label: str,
    incoming_message: str,
    conversation_history: list[dict],
    kb_context: str = "",
) -> str:
    """
    Generate a draft response for a lead's message.

    Args:
        lead: The Lead ORM object
        intent_label: Classified intent of the incoming message
        incoming_message: The raw text of the lead's message
        conversation_history: Last 3 interactions as list of {"role": ..., "content": ...}
        kb_context: Relevant KB entry text to inject into context

    Returns:
        Draft response text string.
    """
    client, provider = _get_client()

    if client is None:
        key_name = "GROQ_API_KEY" if provider == "groq" else "ANTHROPIC_API_KEY"
        return f"[LLM unavailable — {key_name} not set in .env]"

    # Build context block
    context_block = ""
    if kb_context:
        context_block = f"\n\nRELEVANT KNOWLEDGE BASE CONTEXT:\n{kb_context}\n"

    lead_context = (
        f"\n\nLEAD CONTEXT:\n"
        f"Name: {lead.first_name or 'Unknown'}\n"
        f"Type: {lead.lead_type or 'unknown'}\n"
        f"Company: {lead.company_name or 'unknown'}\n"
        f"Team size: {lead.team_size or 'unknown'}\n"
        f"Uses software: {lead.uses_software}\n"
        f"Lead quality: {lead.lead_quality}\n"
        f"Detected intent: {intent_label}\n"
    )

    system = PERSONA_SYSTEM_PROMPT + context_block + lead_context

    # Build message list — last 3 turns of history + current message
    messages = conversation_history[-6:] + [
        {"role": "user", "content": incoming_message}
    ]

    # ── Groq (OpenAI-compatible) ──────────────────────────────────────────────
    if provider == "groq":
        response = client.chat.completions.create(
            model=settings.groq_model,
            max_tokens=300,
            messages=[{"role": "system", "content": system}] + messages,
        )
        return response.choices[0].message.content.strip()

    # ── Anthropic (Claude) ────────────────────────────────────────────────────
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=system,
        messages=messages,
    )
    return response.content[0].text.strip()
