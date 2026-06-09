"""
Lead Stages — the canonical 10-stage pipeline shared with the BeyondSure CRM.

ARIA's internal `status` field stays as-is (new, engaged, interested,
needs_human, contacted, demo_scheduled, demo_done, converted, lost, invalid)
so the chat flow, inbox, and scheduler keep working. This module derives the
*display* stage from that status, so the dashboard speaks the same language as
the rest of the CRM without rewiring ARIA's internals.

ARIA auto-drives the early stages (New → Contacted → Interested → Follow-up →
Post Demo Follow-Up). The later, human-only stages (Negotiation, Post Commercial
Follow-Up, Parked, Won, Lost) are set manually from the lead detail view, which
writes the canonical key straight into `status`.
"""

from models.lead import Lead


# Grid order (matches the CRM's "Lead Stages" layout)
STAGE_ORDER = [
    "new", "contacted", "interested", "follow_up", "negotiation",
    "post_demo", "post_commercial", "parked", "won", "lost",
]

STAGE_LABELS = {
    "new":             "New Lead",
    "contacted":       "Contacted",
    "interested":      "Interested",
    "follow_up":       "Follow-up",
    "negotiation":     "Negotiation",
    "post_demo":       "Post Demo Follow-Up",
    "post_commercial": "Post Commercial Follow-Up",
    "parked":          "Parked",
    "won":             "Won",
    "lost":            "Lost",
}

# Linear conversion track for the funnel chart (Parked/Lost are off-track).
FUNNEL_TRACK = [
    "new", "contacted", "interested", "follow_up",
    "post_demo", "negotiation", "post_commercial", "won",
]

# Stages a human owns — ARIA must not auto-downgrade a lead out of these.
HUMAN_STAGES = {
    "follow_up", "post_demo", "negotiation", "post_commercial",
    "parked", "won", "lost",
}

# Internal status → canonical stage (when the status isn't already a stage key).
_STATUS_TO_STAGE = {
    "new":            "new",
    "contacted":      "contacted",
    "interested":     "interested",
    "engaged":        "interested",
    "demo_scheduled": "post_demo",
    "demo_done":      "post_demo",
    "converted":      "won",
    "invalid":        "lost",
    "lost":           "lost",
}


def lead_stage(lead: Lead) -> str:
    """Return the canonical pipeline stage for a lead."""
    status = (lead.status or "new").lower()

    # Already a canonical stage key (e.g. set manually from the detail view).
    if status in STAGE_LABELS:
        return status

    # needs_human is an attention flag, not a stage — infer the real stage.
    if status == "needs_human":
        if lead.demo_preference or lead.willing_for_demo:
            return "post_demo"
        return "follow_up"

    return _STATUS_TO_STAGE.get(status, "new")
