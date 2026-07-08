---
title: Lead Scoring
type: logic
tags: [scoring, leads, algorithm]
updated: 2026-06-14
---

# Lead Scoring

← [[HOME]] | Code: `services/lead_scorer.py` | See also: [[Lead Sources & Assignment]]

> [!note] Every lead is scored on arrival from **any** source (webhook, import). `score_breakdown(lead)` exposes the three buckets to the dashboard's "Why this score?" panel. `score_lead(lead)` returns `(score, quality)`.

## Score range

- **0–100** integer
- **Hot:** ≥ 65
- **Warm:** 40–64
- **Cold:** < 40

## Three scoring buckets

### 1. Profile score (max ~40 pts)

Based on who the lead is:

| Lead type | Points |
|-----------|--------|
| Broker | 15 |
| IMF | 12 |
| Agent | 8 |
| POSP Advisor | 5 |
| Unknown | 0 |
| Invalid | −40 |

| Team size | Points |
|-----------|--------|
| 20+ | 15 |
| 10–19 | 12 |
| 5–9 | 8 |
| 2–4 | 5 |
| Solo | 2 |
| Unknown | 0 |

### 2. Form intent score (max 30 pts)

Based on how they answered the lead form:

| Signal | Points |
|--------|--------|
| willing_for_demo = Yes | +15 |
| open_to_platform = Yes | +10 |
| uses_software = No | +5 (not locked in elsewhere) |

### 3. Engagement delta (applied on reply)

Score adjusts each time the lead interacts:

| Intent | Delta |
|--------|-------|
| demo_request | +15 |
| positive_signal | +8 |
| pricing_query | +5 |
| feature_query | +5 |
| onboarding_query | +3 |
| greeting | +2 |
| unclear | 0 |
| objection_cost | −5 |
| objection_timing | −3 |
| objection_switching | −8 |
| not_interested | −50 |
| escalation_request | 0 |
| bot_detection | 0 |

## Score decay

Inactive leads lose points over time:
- **30 days no interaction:** −10 pts
- **60 days no interaction:** −20 pts
- **90+ days:** −30 pts

## Example calculation

Rajesh Sharma — broker, team of 12, willing for demo, open to platform, currently uses no software:

```
Profile:   broker(15) + team 10-19(12) = 27
Form:      willing_for_demo(15) + open_to_platform(10) + no_software(5) = 30
Total:     57 → Warm

After reply with demo_request intent:
57 + 15 = 72 → Hot
```

## Quality labels map to actions

| Quality | Handling |
|---------|---------|
| Hot | Priority in approval queue, faster follow-up cadence |
| Warm | Standard queue |
| Cold | Deprioritised, longer follow-up gap |
| (opt_out) | No further contact, status = lost |
