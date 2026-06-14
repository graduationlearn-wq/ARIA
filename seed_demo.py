"""
seed_demo.py — load a rich demo org + dummy leads WITH full interaction history,
so every dashboard tab (Leads, Inbox, Approvals, Analytics, Notifications) is
populated from the database — not display-only placeholders.

Builds:
  Admin
   ├── Team Leader 1 ──> Employee 1, Employee 2
   └── Team Leader 2 ──> Employee 3, Employee 4
  …plus ~24 dummy leads spread across the four employees, each with a realistic
  history: first-touch drafts awaiting approval, lead↔ARIA chat threads, team
  replies (group chat, attributed to the owner/leader), escalations, and demos.

Why a standalone script (not app startup): the auto-seed only fires on an empty
database, so it would never touch an existing one. This is an explicit,
idempotent demo tool you run when you want to populate or refresh demo data.

Idempotent + safe to re-run:
  • Users are upserted by email — existing admin/leader/employee logins keep
    working (passwords below); extra leaders/employees are added.
  • Demo leads use the @demoleads.in marker. Each run clears the previous demo
    batch (and its interactions/escalations/demos) and regenerates it. Your REAL
    leads (any other email domain) are never touched.

Run from the aria/ directory:
    python seed_demo.py
"""

import random
from datetime import datetime, timedelta, timezone

from database import SessionLocal, init_db
from models.user import User
from models.lead import Lead
from models.interaction import Interaction
from models.escalation import Escalation
from models.demo import Demo
from services.auth_service import hash_password
from services.lead_scorer import score_lead, apply_engagement_delta, score_to_quality

DEMO_DOMAIN = "demoleads.in"   # marker so demo leads can be cleanly re-seeded

# ── The demo org tree ─────────────────────────────────────────────────────────
# name,            email,                     role,       password,      reports_to
ORG = [
    ("Admin",          "admin@beyondsure.in",     "admin",    "admin123",    None),
    ("Team Leader 1",  "leader@beyondsure.in",    "manager",  "leader123",   "admin@beyondsure.in"),
    ("Team Leader 2",  "leader2@beyondsure.in",   "manager",  "leader123",   "admin@beyondsure.in"),
    ("Employee 1",     "employee@beyondsure.in",  "employee", "employee123", "leader@beyondsure.in"),
    ("Employee 2",     "employee2@beyondsure.in", "employee", "employee123", "leader@beyondsure.in"),
    ("Employee 3",     "employee3@beyondsure.in", "employee", "employee123", "leader2@beyondsure.in"),
    ("Employee 4",     "employee4@beyondsure.in", "employee", "employee123", "leader2@beyondsure.in"),
]

# ── Dummy-lead content pools ──────────────────────────────────────────────────
FIRST_NAMES = [
    "Rahul", "Sneha", "Amit", "Pooja", "Karan", "Divya", "Rohit", "Meera",
    "Ankit", "Nisha", "Suresh", "Kavya", "Vivek", "Anjali", "Manish", "Ritu",
    "Deepak", "Shreya", "Gaurav", "Tanvi", "Harish", "Neha", "Sanjay", "Isha",
]
COMPANIES = [
    "Shield Insurance Brokers", "TrustCover Advisory", "SafeNest Insure",
    "Prime Risk Partners", "Aegis Financial", "Bharat Assure", "NovaCover",
    "Sterling Insurance", "Guardian Brokers", "Apex Risk Solutions",
    "Lumin Insure", "Verdant Advisory", "Crest Insurance", "Anchor Cover",
]
STATES = [
    "Maharashtra", "Karnataka", "Delhi", "Gujarat", "Tamil Nadu",
    "Telangana", "Rajasthan", "West Bengal", "Punjab", "Kerala",
]
LEAD_TYPES = ["broker", "imf", "agent", "posp_advisor", "advisor"]
SOURCES = ["fb", "ig"]

# Each entry = the lead's pipeline state. 'needs_human' shows as escalated in the
# Inbox; the rest are canonical 10-stage keys. (status, wants_demo)
STAGE_MIX = [
    ("new", False), ("new", False), ("contacted", False), ("contacted", True),
    ("interested", True), ("interested", True), ("follow_up", True),
    ("needs_human", True), ("needs_human", False), ("post_demo", True),
    ("negotiation", True), ("post_commercial", True), ("won", True),
    ("parked", False), ("lost", False),
]

INBOUND_MSGS = {
    "pricing_query":   ["What does it cost for my team?", "Can you share pricing details?"],
    "feature_query":   ["Does it handle commission tracking?", "Can it manage renewals and policies?"],
    "demo_request":    ["Can I see a quick demo?", "I'd like to see how it works."],
    "objection_cost":  ["Sounds a bit expensive for us.", "Not sure it fits our budget right now."],
    "positive_signal": ["This looks really useful!", "Yes, that's exactly what we need."],
}
ARIA_REPLIES = {
    "pricing_query":   "Pricing scales with your team size — I'll have our team share exact numbers. Want a quick call?",
    "feature_query":   "Yes — BeyondSure tracks policies, renewals and commissions in one place. Shall I show you?",
    "demo_request":    "Absolutely! What time works best for a short walkthrough this week?",
    "objection_cost":  "Totally understand — most teams save more than the cost in saved hours. Can I show you how?",
    "positive_signal": "Great to hear! Would you like to see it in action on a quick call?",
}
TEAM_REPLIES = [
    "Hi {name}, this is {sender} from BeyondSure — happy to walk you through it personally.",
    "Thanks {name}! I can set up a quick call. Does this week work for you?",
    "Great questions, {name}. Let me put together a short demo tailored to your team.",
    "Appreciate the patience, {name} — sharing the proposal now, let me know your thoughts.",
]
DEMO_SLOTS = ["This week, afternoons", "Tomorrow 4 PM", "Friday morning", "Next Monday, 11 AM", "Flexible — you pick"]


def upsert_org(db):
    """Create or update the demo org users. Returns {email: User}."""
    by_email = {}
    for name, email, role, password, _ in ORG:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            u = User(name=name, email=email, role=role,
                     password_hash=hash_password(password), avatar_seed=name,
                     is_active=True)
            db.add(u)
        else:
            u.name = name
            u.role = role
            u.avatar_seed = name
            u.is_active = True
            u.password_hash = hash_password(password)  # keep demo passwords known
        by_email[email] = u
    db.flush()
    for name, email, role, password, reports_to in ORG:
        by_email[email].manager_id = by_email[reports_to].id if reports_to else None
    db.commit()
    return by_email


def clear_demo_leads(db):
    """Remove the previous demo-lead batch (and its child rows). Real leads stay."""
    leads = db.query(Lead).filter(Lead.email.like(f"%@{DEMO_DOMAIN}")).all()
    ids = [l.id for l in leads]
    if ids:
        db.query(Interaction).filter(Interaction.lead_id.in_(ids)).delete(synchronize_session=False)
        db.query(Escalation).filter(Escalation.lead_id.in_(ids)).delete(synchronize_session=False)
        db.query(Demo).filter(Demo.lead_id.in_(ids)).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
    return len(ids)


def make_lead(owner_id, idx):
    name = random.choice(FIRST_NAMES)
    status, wants_demo = random.choice(STAGE_MIX)
    team_size = random.choice([1, 3, 6, 12, 25, 40])
    days_ago = random.choices(range(0, 12), weights=[6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1])[0]
    created = datetime.now(timezone.utc) - timedelta(
        days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59)
    )
    phone = "9" + "".join(random.choice("0123456789") for _ in range(9))

    lead = Lead(
        first_name=name,
        email=f"{name.lower()}{idx}@{DEMO_DOMAIN}",
        phone=phone,
        state=random.choice(STATES),
        company_name=random.choice(COMPANIES),
        lead_type=random.choice(LEAD_TYPES),
        source_platform=random.choice(SOURCES),
        team_size=team_size,
        uses_software=random.choice([True, False]),
        open_to_platform=random.choice([True, True, False]),
        willing_for_demo=wants_demo,
        channel=random.choice(["email", "email", "whatsapp"]),
        channel_id=phone,
        status=status,
        owner_id=owner_id,
        created_at=created,
        last_interaction_at=created + timedelta(hours=random.randint(1, 30)),
    )

    # Stage-specific profile fields
    if status in ("post_demo", "negotiation", "post_commercial", "won", "needs_human") and wants_demo:
        lead.demo_preference = random.choice(DEMO_SLOTS)
    if status == "won":
        lead.converted_at = lead.last_interaction_at
    if status == "parked":
        lead.re_engage_after = datetime.now(timezone.utc) + timedelta(days=random.randint(2, 10))
    if status == "lost":
        lead.opt_out = True
    if status in ("needs_human",):
        lead.assigned_to = "human_queue"

    # Realistic score: profile + form, plus engagement for advanced stages.
    score, _ = score_lead(lead)
    if status in ("post_demo", "negotiation", "post_commercial", "won"):
        for _ in range(random.randint(1, 3)):
            score = apply_engagement_delta(score, "demo_request")
    elif status in ("interested", "follow_up", "needs_human"):
        score = apply_engagement_delta(score, "positive_signal")
    lead.lead_score = max(0, min(100, score))
    lead.lead_quality = score_to_quality(lead.lead_score)
    return lead


def _msg(lead, direction, text, t, *, handled_by="aria", mtype=None,
         intent=None, status=None, sender_id=None):
    return Interaction(
        lead_id=lead.id, direction=direction, channel="chat",
        message_text=text, message_type=mtype, intent_label=intent,
        handled_by=handled_by, send_status=status, sender_user_id=sender_id,
        timestamp=t,
    )


ARIA_MANAGED = ("new", "contacted", "interested", "follow_up")


def seed_history(db, lead, owner, leader):
    """
    Give a lead a realistic interaction trail so every tab has live content.
    Returns True if a pending-approval draft was created (for the Approvals queue).
    """
    t = lead.created_at + timedelta(minutes=5)
    step = lambda mins=0: timedelta(minutes=mins or random.randint(20, 600))
    rows = []
    pending = False
    status = lead.status

    # 1. First touch — every lead gets one outbound. 'new' leads keep theirs
    #    PENDING (populates the Approvals queue); the rest were already sent.
    first_touch = (
        f"Hi {lead.first_name}, thanks for your interest in BeyondSure! "
        "We help insurance teams manage leads, policies and commissions in one place. "
        "Happy to show you around — when works for a quick chat?"
    )
    if status == "new":
        intent = random.choice(["pricing_query", "feature_query", "demo_request", "objection_cost"])
        rows.append(_msg(lead, "outbound", first_touch, t, handled_by="aria",
                         mtype="first_touch", intent=intent, status="pending_approval"))
        db.add_all(rows)
        return True

    rows.append(_msg(lead, "outbound", first_touch, t, handled_by="human_approved",
                     mtype="first_touch", status="sent"))
    t += step()

    # 2. Lead replies and ARIA answers (chat thread). For ARIA-managed stages the
    #    LAST reply is sometimes left as a pending draft → populates Approvals with
    #    varied intents (pricing / demo / objection) so the filter tabs have content.
    n_exchanges = 1 if status == "contacted" else random.randint(1, 3)
    leave_pending = status in ARIA_MANAGED and random.random() < 0.5
    for i in range(n_exchanges):
        intent = random.choice(list(INBOUND_MSGS.keys()))
        rows.append(_msg(lead, "inbound", random.choice(INBOUND_MSGS[intent]), t,
                         handled_by="lead", mtype="chat_in", intent=intent))
        t += step(8)
        is_last = (i == n_exchanges - 1)
        if is_last and leave_pending:
            rows.append(_msg(lead, "outbound", ARIA_REPLIES[intent], t,
                             handled_by="aria", mtype="reply_draft", intent=intent,
                             status="pending_approval"))
            pending = True
        else:
            rows.append(_msg(lead, "outbound", ARIA_REPLIES[intent], t,
                             handled_by="aria", mtype="chat_out", intent=intent, status="sent"))
        t += step()

    # 3. Escalated / advanced stages → the team takes over (group chat).
    human_stages = ("needs_human", "follow_up", "post_demo", "negotiation", "post_commercial", "won", "parked")
    if status in human_stages:
        # The owning employee replies (attributed).
        rows.append(_msg(lead, "outbound",
                         random.choice(TEAM_REPLIES).format(name=lead.first_name, sender=owner.name.split()[0]),
                         t, handled_by="human", mtype="chat_out", status="sent", sender_id=owner.id))
        t += step()
        # On hotter deals the team leader chimes in too — shows hierarchy in one thread.
        if status in ("negotiation", "post_commercial", "won") and leader:
            rows.append(_msg(lead, "outbound",
                             f"Hi {lead.first_name}, {leader.name.split()[0]} here (team lead). "
                             "Glad to support — let's get this across the line.",
                             t, handled_by="human", mtype="chat_out", status="sent", sender_id=leader.id))
            t += step()

    db.add_all(rows)

    # 4. Escalation row for leads that asked for a human.
    if status == "needs_human":
        first_inbound = next((r for r in rows if r.direction == "inbound"), None)
        db.flush()  # ensure ids for interaction_id link
        db.add(Escalation(
            lead_id=lead.id,
            interaction_id=first_inbound.id if first_inbound else None,
            reason="escalation_request",
            assigned_to="human_queue",
        ))

    # 5. Demo row for booked/advanced leads.
    if status in ("post_demo", "negotiation", "post_commercial", "won"):
        db.add(Demo(
            lead_id=lead.id,
            scheduled_preference=lead.demo_preference or random.choice(DEMO_SLOTS),
            status="completed" if status in ("post_commercial", "won") else "scheduled",
            demo_number=1,
            booked_via="aria_chat",
        ))
    return pending


def seed_leads(db, employees, leader_of):
    """Give each employee a varied handful of demo leads, each with history."""
    counter = 1
    per_employee = {}
    pending_total = 0
    for emp in employees:
        n = random.randint(5, 8)
        for _ in range(n):
            lead = make_lead(emp.id, counter)
            db.add(lead)
            db.flush()  # get lead.id for the interactions
            if seed_history(db, lead, emp, leader_of.get(emp.id)):
                pending_total += 1
            counter += 1
        per_employee[emp.name] = n
    db.commit()
    return per_employee, pending_total


def main():
    init_db()  # ensure tables + light migrations
    db = SessionLocal()
    try:
        by_email = upsert_org(db)
        removed = clear_demo_leads(db)
        employees = [u for u in by_email.values() if u.role == "employee"]
        # Map each employee → their team leader (User) for group-chat attribution.
        users_by_id = {u.id: u for u in by_email.values()}
        leader_of = {e.id: users_by_id.get(e.manager_id) for e in employees}

        per_emp, pending = seed_leads(db, employees, leader_of)

        print("=" * 56)
        print("  Demo data seeded (full working prototype)")
        print("=" * 56)
        print(f"  Cleared {removed} old demo lead(s); created "
              f"{sum(per_emp.values())} new across {len(employees)} employees.")
        print(f"  ~{pending} first-touch drafts are waiting in the Approvals queue.")
        print("-" * 56)
        admin = next(u for u in by_email.values() if u.role == "admin")
        print(f"  {admin.name}  ({admin.email})")
        for leader in [u for u in by_email.values() if u.role == "manager"]:
            print(f"    {leader.name}  ({leader.email})")
            for emp in employees:
                if emp.manager_id == leader.id:
                    n = db.query(Lead).filter(Lead.owner_id == emp.id).count()
                    print(f"      {emp.name}  ({emp.email})  — {n} leads")
        print("-" * 56)
        print("  Logins (all): admin123 / leader123 / employee123")
        print("=" * 56)
    finally:
        db.close()


if __name__ == "__main__":
    main()
