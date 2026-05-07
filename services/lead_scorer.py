"""
Lead Scorer — rules-based v1.

Scores are split into three categories (max 100 total):
  Profile score   — 40 pts  (static, set at lead creation)
  Form intent     — 30 pts  (static, set at lead creation)
  Engagement      — 30 pts  (dynamic, updated per interaction)

Quality tiers:
  Hot   → 70–100
  Warm  → 40–69
  Cold  → 10–39
  New   →  0–9  (or no interactions yet)
"""

from models.lead import Lead


# ── Profile score (max 40) ────────────────────────────────────────────────────

LEAD_TYPE_SCORES: dict[str, int] = {
    "broker": 15,
    "imf": 12,
    "agent": 8,
    "insurance_agent": 8,
    "advisor": 5,
    "posp_advisor": 5,
    "unknown": 0,
    "invalid": -40,   # disqualifies the lead
}

TEAM_SIZE_SCORES: list[tuple[int, int]] = [
    (20, 15),   # 20+ employees → 15 pts
    (10, 12),   # 10–19
    (5,  8),    # 5–9
    (2,  5),    # 2–4
    (1,  2),    # solo
]

USES_SOFTWARE_SCORES: dict[bool, int] = {
    False: 10,   # No existing software → needs a solution
    True:  5,    # Has software → harder to switch but still interested
}


def _profile_score(lead: Lead) -> int:
    # Business type
    lt = (lead.lead_type or "unknown").lower().strip()
    type_pts = LEAD_TYPE_SCORES.get(lt, 0)
    if type_pts == -40:
        return -40  # disqualified immediately

    # Team size
    size_pts = 0
    if lead.team_size is not None:
        for threshold, pts in TEAM_SIZE_SCORES:
            if lead.team_size >= threshold:
                size_pts = pts
                break

    # Software usage
    sw_pts = 0
    if lead.uses_software is not None:
        sw_pts = USES_SOFTWARE_SCORES.get(lead.uses_software, 0)

    return min(type_pts + size_pts + sw_pts, 40)


# ── Form intent score (max 30) ────────────────────────────────────────────────

def _form_intent_score(lead: Lead) -> int:
    pts = 0
    if lead.willing_for_demo is True:
        pts += 20
    if lead.open_to_platform is True:
        pts += 10
    return min(pts, 30)


# ── Engagement score delta (applied per interaction event) ───────────────────

ENGAGEMENT_DELTAS: dict[str, int] = {
    "replied_to_first_message": 10,
    "connected_on_call":        8,
    "demo_request":             15,
    "positive_signal":          8,
    "pricing_query":            5,
    "feature_query":            5,
    "onboarding_query":         5,
    "demo_attended":            12,
    "objection_cost":           -5,
    "objection_timing":         -8,
    "objection_switching":      -10,
    "no_response_3_followups":  -10,
    "demo_no_show":             -15,
    "not_interested":           -50,   # kills the lead
}

DECAY_THRESHOLDS: list[tuple[int, int]] = [
    (31, -20),
    (15, -10),
    (8,  -5),
    (0,   0),
]


# ── Main scoring functions ────────────────────────────────────────────────────

def compute_initial_score(lead: Lead) -> int:
    """
    Calculate the full score at lead creation time.
    Called once when a new lead webhook arrives.
    """
    profile = _profile_score(lead)
    if profile == -40:
        return 0  # disqualified

    intent = _form_intent_score(lead)
    return max(0, min(100, profile + intent))


def apply_engagement_delta(current_score: int, event: str) -> int:
    """
    Update score when an interaction event occurs.
    Pass the intent label (e.g. 'demo_request') or an event name.

    Usage:
        lead.lead_score = apply_engagement_delta(lead.lead_score, intent_label)
    """
    delta = ENGAGEMENT_DELTAS.get(event, 0)
    return max(0, min(100, current_score + delta))


def apply_decay(current_score: int, days_since_last_interaction: int) -> int:
    """
    Apply inactivity penalty based on days since last interaction.
    Called by a scheduled job (daily).
    """
    penalty = 0
    for threshold, p in DECAY_THRESHOLDS:
        if days_since_last_interaction >= threshold:
            penalty = p
            break
    return max(0, current_score + penalty)


def score_to_quality(score: int, is_disqualified: bool = False) -> str:
    """Map a numeric score to a quality tier label."""
    if is_disqualified:
        return "invalid"
    if score >= 70:
        return "hot"
    if score >= 40:
        return "warm"
    if score >= 10:
        return "cold"
    return "new"


def score_lead(lead: Lead) -> tuple[int, str]:
    """
    Convenience function: compute initial score + quality tier.
    Returns (score, quality).
    """
    is_invalid = (lead.lead_type or "").lower() == "invalid"
    score = 0 if is_invalid else compute_initial_score(lead)
    quality = score_to_quality(score, is_disqualified=is_invalid)
    return score, quality
