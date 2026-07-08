---
title: Message Templates
type: logic
tags: [messages, templates, email, llm]
updated: 2026-06-14
---

# Message Templates

← [[HOME]] | Code: `services/message_builder.py`, `services/llm.py`

> [!note] This note = ARIA's **automated** outbound (first-touch / follow-ups, via the approval queue). For the **human-driven**, one-click templated emails with attachments (proposals, recaps, welcome), see [[Email Templates]].

## Two types of messages

| Type | Who writes it | When |
|------|--------------|------|
| First-touch | `message_builder.py` (template) | New lead arrives |
| Reply draft | LLM (Groq/Claude) | Lead sends a reply |

---

## First-touch message

Built by `build_first_touch(lead)` with conditional logic:

**Base structure:**
```
Hi [first_name],

[Opening line based on lead type]
[Software context line if uses_software = No]
[Demo offer if willing_for_demo = Yes, else soft ask]
[Pain point question if team_size is known]

[Sign-off]
```

**Conditional swaps:**

| Condition | Line used |
|-----------|----------|
| `willing_for_demo = True` | "I'd love to offer you a personalised demo — when works for you?" |
| `willing_for_demo = False/None` | "Would you be open to a quick 20-minute call?" |
| `uses_software = False` | "You mentioned you're not using any software yet — you're in the right place." |
| `lead_type = broker` | Opening mentions "brokerage" specifically |
| `team_size` is known | Closes with team-size-specific pain point question |

## Follow-ups

| Message | Timing | Key angle |
|---------|--------|-----------|
| `build_followup_1()` | 24hrs after first-touch | Gentle check-in |
| `build_followup_2()` | 72hrs after first-touch | Value-add, social proof |

> [!note] Follow-up scheduling is not yet wired up
> The functions exist in `message_builder.py` but there's no scheduler calling them yet. This is on the [[Roadmap]].

## LLM reply drafts

**Model:** `llama-3.1-8b-instant` (Groq, testing) / `claude-haiku-4-5-20251001` (production)

**System prompt rules (never break these):**
1. Never state specific prices unless in KB context
2. Never confirm specific features unless in KB context
3. Never promise delivery/launch dates
4. If unsure → "Let me connect you with our team who can answer this precisely"
5. Under 80 words
6. End with exactly one question or one CTA
7. Never say you're an AI unless directly asked

**Context injected per request:**
- Lead name, type, company, team size, uses_software, lead_quality
- Detected intent label
- Relevant KB entry (if found)
- Last 3 conversation turns (6 messages)

## Subject lines

Built by `build_subject_line(lead, message_number)`:
- Message 1: `"BeyondSure — built for [lead_type]s like you, [first_name]"`
- Replies: `"Re: BeyondSure — [first_name]"`

## Email footer

Every outbound email includes an unsubscribe footer (DPDP compliance). When a lead replies with `not_interested` intent → `opt_out = True` → no further contact.
