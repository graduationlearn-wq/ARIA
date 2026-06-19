"""
Tests for Google Sheet lead sync:
URL normalization, CRUD + permissions, and the sync path (fetch patched) —
new rows create + auto-assign within the owner's team, re-sync dedups.
"""

from unittest.mock import patch

import pytest

from main import app
from models.lead import Lead
from models.sheet_source import SheetSource
from models.user import User
from routes.auth import get_current_user
from services import sheet_sync

CSV = (
    "Name,Email,Phone,Company,Type,Team Size,Wants Demo\n"
    "Mitesh Chotai,mitesh@kedaar.in,8591713250,Kedaar Capital,agent,4,yes\n"
    "Asha Rao,asha@nova.in,9000000022,Nova,broker,15,no\n"
)


def make_org(db):
    admin = User(name="Admin", email="a@test.in", role="admin", password_hash="x")
    leader = User(name="Leader", email="l@test.in", role="manager", password_hash="x")
    db.add_all([admin, leader]); db.flush()
    leader.manager_id = admin.id
    e1 = User(name="E1", email="e1@test.in", role="employee", password_hash="x", manager_id=leader.id)
    e2 = User(name="E2", email="e2@test.in", role="employee", password_hash="x", manager_id=leader.id)
    db.add_all([e1, e2]); db.commit()
    return admin, leader, e1, e2


def as_user(u):
    app.dependency_overrides[get_current_user] = lambda: u


# ── URL normalization ─────────────────────────────────────────────────────────

class TestUrlNormalize:
    def test_edit_url_to_csv(self):
        u = "https://docs.google.com/spreadsheets/d/ABC123/edit#gid=456"
        assert sheet_sync.to_csv_url(u) == "https://docs.google.com/spreadsheets/d/ABC123/export?format=csv&gid=456"

    def test_url_without_gid_defaults_zero(self):
        u = "https://docs.google.com/spreadsheets/d/ABC123/edit"
        assert sheet_sync.to_csv_url(u).endswith("export?format=csv&gid=0")

    def test_non_google_url_passthrough(self):
        u = "http://localhost:9000/leads.csv"
        assert sheet_sync.to_csv_url(u) == u


# ── CRUD + permissions ────────────────────────────────────────────────────────

class TestSheetCrud:
    def test_leader_creates_own_sheet(self, client, db):
        _, leader, _, _ = make_org(db)
        as_user(leader)
        r = client.post("/sheets/", json={"name": "My Sheet", "sheet_url": "http://x/leads.csv"})
        assert r.status_code == 200
        assert r.json()["owner_user_id"] == leader.id

    def test_employee_cannot_manage(self, client, db):
        _, _, e1, _ = make_org(db)
        as_user(e1)
        assert client.post("/sheets/", json={"name": "X", "sheet_url": "http://x"}).status_code == 403
        assert client.get("/sheets/").json()["sheets"] == []

    def test_leader_cannot_own_for_another(self, client, db):
        admin, leader, _, _ = make_org(db)
        as_user(leader)
        r = client.post("/sheets/", json={"name": "X", "sheet_url": "http://x", "owner_user_id": admin.id})
        assert r.status_code == 403

    def test_admin_assigns_to_leader(self, client, db):
        admin, leader, _, _ = make_org(db)
        as_user(admin)
        r = client.post("/sheets/", json={"name": "S", "sheet_url": "http://x", "owner_user_id": leader.id})
        assert r.status_code == 200 and r.json()["owner_user_id"] == leader.id

    def test_leader_sees_only_own_sheets(self, client, db):
        admin, leader, _, _ = make_org(db)
        db.add(SheetSource(name="admin-sheet", sheet_url="http://x", owner_user_id=admin.id))
        db.add(SheetSource(name="leader-sheet", sheet_url="http://y", owner_user_id=leader.id))
        db.commit()
        as_user(leader)
        names = {s["name"] for s in client.get("/sheets/").json()["sheets"]}
        assert names == {"leader-sheet"}


# ── Sync (fetch patched) ──────────────────────────────────────────────────────

class TestSync:
    def test_sync_creates_and_assigns_within_team(self, client, db):
        _, leader, e1, e2 = make_org(db)
        as_user(leader)
        sid = client.post("/sheets/", json={"name": "S", "sheet_url": "http://x/leads.csv"}).json()["id"]

        with patch("services.sheet_sync.fetch_csv", return_value=CSV.encode()):
            r = client.post(f"/sheets/{sid}/sync")
        assert r.status_code == 200
        assert r.json()["result"]["imported"] == 2

        leads = db.query(Lead).all()
        assert len(leads) == 2
        # Auto-assigned to the leader's own employees, nobody else.
        assert {l.owner_id for l in leads}.issubset({e1.id, e2.id})
        assert all(l.source_platform == "sheet" and l.status == "new" for l in leads)

    def test_resync_dedups(self, client, db):
        _, leader, _, _ = make_org(db)
        as_user(leader)
        sid = client.post("/sheets/", json={"name": "S", "sheet_url": "http://x/leads.csv"}).json()["id"]
        with patch("services.sheet_sync.fetch_csv", return_value=CSV.encode()):
            client.post(f"/sheets/{sid}/sync")
            r2 = client.post(f"/sheets/{sid}/sync")  # same rows again
        assert r2.json()["result"]["imported"] == 0
        assert r2.json()["result"]["duplicates"] == 2
        assert db.query(Lead).count() == 2

    def test_private_sheet_records_error_not_crash(self, client, db):
        _, leader, _, _ = make_org(db)
        as_user(leader)
        sid = client.post("/sheets/", json={"name": "S", "sheet_url": "http://x"}).json()["id"]
        with patch("services.sheet_sync.fetch_csv", side_effect=ValueError("not public")):
            r = client.post(f"/sheets/{sid}/sync")
        assert r.status_code == 200
        assert "not public" in r.json()["result"]["error"]
        assert db.get(SheetSource, sid).last_status.startswith("error")

    def test_run_sheet_sync_job(self, db):
        # The scheduler entry point syncs all active sheets via its own session.
        _, leader, _, _ = make_org(db)
        db.add(SheetSource(name="S", sheet_url="http://x/leads.csv", owner_user_id=leader.id))
        db.commit()
        with patch("services.sheet_sync.fetch_csv", return_value=CSV.encode()), \
             patch("services.sheet_sync.SessionLocal", return_value=db):
            results = sheet_sync.run_sheet_sync()
        assert any(v["imported"] == 2 for v in results.values())


class TestSyncAll:
    def test_sync_all_pulls_visible_sheets(self, client, db):
        _, leader, _, _ = make_org(db)
        as_user(leader)
        client.post("/sheets/", json={"name": "S", "sheet_url": "http://x/leads.csv"})
        with patch("services.sheet_sync.fetch_csv", return_value=CSV.encode()):
            r = client.post("/sheets/sync-all")
        assert r.status_code == 200
        assert r.json()["synced"] == 1
        assert r.json()["imported"] == 2

    def test_sync_all_empty_for_employee(self, client, db):
        _, _, e1, _ = make_org(db)
        as_user(e1)
        r = client.post("/sheets/sync-all")
        assert r.status_code == 200
        assert r.json() == {"synced": 0, "imported": 0}


class TestRequiresAuth:
    def test_sheets_requires_login(self, client, db):
        app.dependency_overrides.pop(get_current_user, None)
        assert client.get("/sheets/").status_code == 401
