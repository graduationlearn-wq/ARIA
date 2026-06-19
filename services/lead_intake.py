"""
Lead intake — the shared create-and-auto-assign path for every bulk source
(file import, Google Sheet sync).

Takes raw {header: value} rows, maps them to canonical lead fields, dedups
(by email/phone against the whole DB and within the batch), scores each lead,
and auto-assigns it to the right team via the hierarchy policy. One code path so
import and sheet-sync behave identically. See [[Lead Sources & Assignment]].
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.lead import Lead
from models.user import User
from services import lead_importer
from services.lead_scorer import score_lead
from services.auth_service import assignment_pool


def intake_rows(db: Session, rows: list[dict], owner_user: User | None, *, source: str) -> dict:
    """
    Create leads from raw rows, auto-assigned within `owner_user`'s team
    (admin / system source → all employees). Returns a summary:
    {imported, duplicates, errors, total_rows, assigned:[{owner_id,owner_name,count}]}.
    """
    rows = rows[: lead_importer.MAX_ROWS]

    # Dedup sets — existing DB contacts + within-batch.
    existing_emails = {e.lower() for (e,) in db.query(Lead.email).filter(Lead.email.isnot(None)).all() if e}
    existing_phones = {p for (p,) in db.query(Lead.phone).filter(Lead.phone.isnot(None)).all() if p}
    seen_email: set[str] = set()
    seen_phone: set[str] = set()

    # Auto-distribution pool — balance across the right team, in memory.
    pool = assignment_pool(owner_user, db) if owner_user else None
    emp_q = db.query(User).filter(User.role == "employee", User.is_active == True)  # noqa: E712
    if pool is not None:
        emp_q = emp_q.filter(User.id.in_(pool))
    pool_emps = emp_q.all()
    counts = {e.id: db.query(Lead).filter(Lead.owner_id == e.id).count() for e in pool_emps}
    fallback_owner = owner_user.id if owner_user else None

    def assign_owner():
        if not counts:
            return fallback_owner
        eid = min(counts, key=counts.get)
        counts[eid] += 1
        return eid

    imported, duplicates = 0, 0
    errors: list[dict] = []
    distribution: dict[int, int] = {}

    for idx, raw in enumerate(rows, start=1):
        f = lead_importer.to_lead_fields(raw)
        name = f.get("first_name")
        email = f.get("email")
        phone = f.get("phone")

        if not name or not (email or phone):
            errors.append({"row": idx, "reason": "missing name or contact (email/phone)"})
            continue
        if email and (email in existing_emails or email in seen_email):
            duplicates += 1
            continue
        if phone and (phone in existing_phones or phone in seen_phone):
            duplicates += 1
            continue

        owner_id = assign_owner()
        lead = Lead(
            first_name=name,
            email=email,
            phone=phone,
            state=f.get("state"),
            company_name=f.get("company_name"),
            lead_type=f.get("lead_type") or "unknown",
            source_platform=f.get("source") or source,
            team_size=f.get("team_size"),
            uses_software=f.get("uses_software"),
            open_to_platform=f.get("open_to_platform"),
            willing_for_demo=f.get("willing_for_demo"),
            company_website=f.get("company_website"),
            channel="email" if email else "whatsapp",
            channel_id=email or phone,
            status="new",
            owner_id=owner_id,
            consent_logged_at=datetime.now(timezone.utc),
        )
        db.add(lead)
        db.flush()
        score, quality = score_lead(lead)
        lead.lead_score = score
        lead.lead_quality = quality

        imported += 1
        if owner_id is not None:
            distribution[owner_id] = distribution.get(owner_id, 0) + 1
        if email:
            seen_email.add(email)
        if phone:
            seen_phone.add(phone)

    db.commit()
    name_map = {uid: nm for uid, nm in db.query(User.id, User.name).all()}
    return {
        "imported": imported,
        "duplicates": duplicates,
        "errors": errors,
        "total_rows": len(rows),
        "assigned": [
            {"owner_id": oid, "owner_name": name_map.get(oid), "count": n}
            for oid, n in sorted(distribution.items(), key=lambda kv: -kv[1])
        ],
    }
