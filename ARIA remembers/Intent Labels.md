---
title: Intent Labels
type: logic
tags: [intent, classifier, nlp]
updated: 2026-05-29
---

# Intent Labels

← [[HOME]] | Code: `services/intent_classifier.py`

## How classification works

1. Lowercase + strip the message
2. Remove punctuation via regex (`[^\w\s]` → space)
3. Check each intent's keyword list in order (order matters — specific/high-risk first)
4. First match wins → returns `IntentResult(label, confidence)`
5. Exact match → confidence 1.0, partial match → 0.85
6. No match → `unclear`, confidence 0.3

## All 14 labels

### Escalation (checked first — bypass AI)

| Label | Triggers | Action |
|-------|---------|--------|
| `bot_detection` | "are you a bot", "am i talking to ai", "is this automated", "are you human", "are you an ai" | Escalate to human |
| `escalation_request` | "talk to someone", "real person", "speak to a person", "connect me to", "want to speak to", "real agent" | Escalate to human |

> [!warning] These two intents skip the LLM entirely
> `should_escalate()` returns True → creates Escalation record → lead status = "escalated"

### Positive signals

| Label | Sample triggers |
|-------|----------------|
| `demo_request` | "want to see", "book demo", "schedule a call", "set up a call", "let's connect", "want a demo" |
| `positive_signal` | "sounds good", "tell me more", "interesting", "yes", "sure", "send details" |

### Information queries

| Label | Sample triggers |
|-------|----------------|
| `pricing_query` | "how much", "cost", "price", "pricing", "plans", "subscription", "per month" |
| `feature_query` | "does it support", "integration", "reports", "how does it work", "tell me about the platform" |
| `onboarding_query` | "how do i start", "get started", "setup", "training", "migrate", "sign up" |
| `greeting` | "hi", "hello", "hey", "namaste", "good morning" |

### Objections

| Label | Sample triggers |
|-------|----------------|
| `objection_cost` | "too expensive", "no budget", "costly", "discount", "reduce price" |
| `objection_timing` | "not now", "busy right now", "call me later", "next month", "will get back" |
| `objection_switching` | "already using", "happy with current", "own system", "hard to switch" |

### Exit

| Label | Sample triggers |
|-------|----------------|
| `not_interested` | "not interested", "remove me", "stop messaging", "unsubscribe", "opt out" |

### Fallback

| Label | When |
|-------|------|
| `unclear` | No keyword matched |

## Important fixes made (don't break these)

> [!note] These were bugs we caught during testing
> - `"call me"` was in `escalation_request` — too broad, matched "call me later" which is objection_timing. **Fixed:** removed "call me", added "call me later" to objection_timing
> - `"real person"` was in `bot_detection` — moved to `escalation_request` (correct intent)
> - `"expensive"`, `"affordable"`, `"cheap"` were in `pricing_query` — removed because they're sentiment/objection words that belong only in `objection_cost`

## Phase 3 upgrade

In Phase 3, this rules-based classifier gets replaced with an ML classifier trained on the `interactions` table. The 14 label names stay the same — only the matching logic changes.
