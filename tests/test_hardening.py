"""
Tests for the deployment-hardening fixes from the full checkup:
  - scheduler endpoints require login (test-email is admin-only)
  - approval actions enforce team scope
  - the production-config guard refuses insecure defaults on a real deploy
"""

from unittest.mock import patch

import pytest

from config import settings, DEV_SESSION_SECRET
from main import _check_production_config
from models.interaction import Interaction
from models.lead import Lead
from models.user import User
from routes.auth import get_current_user
from main import app


# ── Org + draft helpers ───────────────────────────────────────────────────────

def make_org(db):
    admin = User(name="Admin", email="a@test.in", role="admin", password_hash="x")
    leader = User(name="Leader", email="l@test.in", role="manager", password_hash="x")
    emp1 = User(name="Emp One", email="e1@test.in", role="employee", password_hash="x")
    emp2 = User(name="Emp Two", email="e2@test.in", role="employee", password_hash="x")
    db.add_all([admin, leader, emp1, emp2])
    db.flush()
    leader.manager_id = admin.id
    emp1.manager_id = leader.id
    emp2.manager_id = leader.id
    db.commit()
    return admin, leader, emp1, emp2


def make_draft(db, owner_id):
    lead = Lead(first_name="Harsh", email="harsh@rupeeco.com", owner_id=owner_id)
    db.add(lead)
    db.flush()
    draft = Interaction(lead_id=lead.id, direction="outbound", channel="email",
                        message_text="draft body", handled_by="aria",
                        send_status="pending_approval")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return lead, draft


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


# ── Scheduler auth ────────────────────────────────────────────────────────────

class TestSchedulerAuth:
    def test_status_requires_login(self, client, db):
        # Drop the conftest admin override → real get_current_user runs → 401.
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/scheduler/status").status_code == 401

    def test_status_ok_when_logged_in(self, client, db):
        # conftest default override = admin
        assert client.get("/scheduler/status").status_code == 200

    def test_test_email_is_admin_only(self, client, db):
        _, _, emp1, _ = make_org(db)
        as_user(emp1)
        r = client.post("/scheduler/test-email", json={"to": "x@example.com"})
        assert r.status_code == 403

    def test_test_email_allows_admin(self, client, db):
        # Admin passes the role gate; send_email is patched so no real SMTP.
        with patch("routes.scheduler.send_email", return_value=True):
            r = client.post("/scheduler/test-email", json={"to": "x@example.com"})
        assert r.status_code == 200


# ── Approval scope ────────────────────────────────────────────────────────────

class TestApprovalScope:
    def test_other_team_employee_cannot_approve(self, client, db):
        _, _, emp1, emp2 = make_org(db)
        _, draft = make_draft(db, owner_id=emp1.id)
        as_user(emp2)
        r = client.post(f"/approval/{draft.id}/approve")
        assert r.status_code == 403

    def test_other_team_employee_cannot_reject(self, client, db):
        _, _, emp1, emp2 = make_org(db)
        _, draft = make_draft(db, owner_id=emp1.id)
        as_user(emp2)
        r = client.post(f"/approval/{draft.id}/reject")
        assert r.status_code == 403

    def test_owner_can_approve(self, client, db):
        _, _, emp1, _ = make_org(db)
        _, draft = make_draft(db, owner_id=emp1.id)
        as_user(emp1)
        with patch("routes.approval.send_email", return_value=True):
            r = client.post(f"/approval/{draft.id}/approve")
        assert r.status_code == 200

    def test_admin_can_reject_any(self, client, db):
        admin, _, emp1, _ = make_org(db)
        _, draft = make_draft(db, owner_id=emp1.id)
        as_user(admin)
        r = client.post(f"/approval/{draft.id}/reject")
        assert r.status_code == 200


# ── Production config guard ───────────────────────────────────────────────────

class TestProductionGuard:
    def test_rejects_dev_secret_on_real_deploy(self, monkeypatch):
        monkeypatch.setattr(settings, "base_url", "https://app.beyondsure.in")
        monkeypatch.setattr(settings, "auth_provider", "local")
        monkeypatch.setattr(settings, "session_secret", DEV_SESSION_SECRET)
        with pytest.raises(RuntimeError, match="SESSION_SECRET"):
            _check_production_config()

    def test_allows_dev_secret_on_localhost(self, monkeypatch):
        monkeypatch.setattr(settings, "base_url", "http://localhost:8000")
        monkeypatch.setattr(settings, "session_secret", DEV_SESSION_SECRET)
        _check_production_config()  # must not raise

    def test_allows_real_secret_on_real_deploy(self, monkeypatch):
        monkeypatch.setattr(settings, "base_url", "https://app.beyondsure.in")
        monkeypatch.setattr(settings, "auth_provider", "local")
        monkeypatch.setattr(settings, "session_secret", "a-real-long-random-secret")
        _check_production_config()  # must not raise
