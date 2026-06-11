"""
Tests for PATCH /auth/users/{id} — the admin's team & roles editor.
The org tree drives lead visibility, so the guards matter:
no self-demotion, no orphaned teams, no reporting loops.
"""

from main import app
from models.user import User
from routes.auth import get_current_user


def make_org(db):
    """Boss(admin) → Mgr(manager) → Emp(employee). Boss is created first so its
    id matches the conftest current-user id (1) — used by the self-change test."""
    boss = User(name="Boss", email="boss@test", role="admin", password_hash="x")
    mgr = User(name="Mgr", email="mgr@test", role="manager", password_hash="x")
    emp = User(name="Emp", email="emp@test", role="employee", password_hash="x")
    db.add_all([boss, mgr, emp])
    db.flush()
    mgr.manager_id = boss.id
    emp.manager_id = mgr.id
    db.commit()
    return boss, mgr, emp


class TestRoleChanges:
    def test_promote_employee_to_manager(self, client, db):
        _, _, emp = make_org(db)
        r = client.patch(f"/auth/users/{emp.id}", json={"role": "manager"})
        assert r.status_code == 200
        assert r.json()["role"] == "manager"

    def test_cannot_change_own_role(self, client, db):
        boss, _, _ = make_org(db)
        assert boss.id == 1  # same id as the conftest current user
        r = client.patch(f"/auth/users/{boss.id}", json={"role": "employee"})
        assert r.status_code == 400

    def test_cannot_demote_manager_with_reports(self, client, db):
        boss, mgr, emp = make_org(db)
        r = client.patch(f"/auth/users/{mgr.id}", json={"role": "employee"})
        assert r.status_code == 400
        assert "team member" in r.json()["detail"]

        # Move the report away, then demotion goes through.
        r = client.patch(f"/auth/users/{emp.id}", json={"manager_id": boss.id})
        assert r.status_code == 200
        r = client.patch(f"/auth/users/{mgr.id}", json={"role": "employee"})
        assert r.status_code == 200

    def test_promote_to_admin_clears_manager(self, client, db):
        _, mgr, _ = make_org(db)
        # mgr has no reports? It has emp — promote emp instead via a fresh user.
        r = client.patch(f"/auth/users/{mgr.id}", json={"role": "admin"})
        # mgr still has a report (emp) but is moving UP, not down — allowed.
        assert r.status_code == 200
        assert r.json()["manager_id"] is None

    def test_unknown_role_rejected(self, client, db):
        _, _, emp = make_org(db)
        r = client.patch(f"/auth/users/{emp.id}", json={"role": "ceo"})
        assert r.status_code == 400


class TestManagerChanges:
    def test_reassign_reports_to(self, client, db):
        boss, _, emp = make_org(db)
        r = client.patch(f"/auth/users/{emp.id}", json={"manager_id": boss.id})
        assert r.status_code == 200
        assert r.json()["manager_id"] == boss.id

    def test_cannot_report_to_self(self, client, db):
        _, mgr, _ = make_org(db)
        r = client.patch(f"/auth/users/{mgr.id}", json={"manager_id": mgr.id})
        assert r.status_code == 400

    def test_cannot_report_to_employee(self, client, db):
        _, mgr, emp = make_org(db)
        r = client.patch(f"/auth/users/{mgr.id}", json={"manager_id": emp.id})
        assert r.status_code == 400

    def test_reporting_loop_blocked(self, client, db):
        boss, mgr, _ = make_org(db)
        m2 = User(name="Mgr2", email="mgr2@test", role="manager",
                  password_hash="x", manager_id=mgr.id)
        db.add(m2)
        db.commit()
        db.refresh(m2)

        # mgr → m2 while m2 → mgr would be a loop.
        r = client.patch(f"/auth/users/{mgr.id}", json={"manager_id": m2.id})
        assert r.status_code == 400
        assert "loop" in r.json()["detail"]


class TestPermissions:
    def test_non_admin_forbidden(self, client, db):
        _, mgr, emp = make_org(db)
        app.dependency_overrides[get_current_user] = lambda: mgr
        r = client.patch(f"/auth/users/{emp.id}", json={"role": "manager"})
        assert r.status_code == 403

    def test_missing_user_404(self, client, db):
        make_org(db)
        r = client.patch("/auth/users/9999", json={"role": "manager"})
        assert r.status_code == 404


class TestRegister:
    def test_register_creates_employee(self, client, db):
        r = client.post("/auth/register", json={
            "name": "New Person", "email": "new@beyondsure.in", "password": "secret1",
        })
        assert r.status_code == 200
        u = r.json()["user"]
        assert u["role"] == "employee"
        assert u["manager_id"] is None  # admin assigns the team later

        created = db.query(User).filter(User.email == "new@beyondsure.in").first()
        assert created is not None
        assert created.role == "employee"

    def test_register_rejects_duplicate_email(self, client):
        payload = {"name": "First", "email": "dup@test.in", "password": "secret1"}
        assert client.post("/auth/register", json=payload).status_code == 200

        r = client.post("/auth/register", json={**payload, "name": "Imposter"})
        assert r.status_code == 400
        assert "already registered" in r.json()["detail"]

    def test_register_rejects_short_password(self, client):
        r = client.post("/auth/register", json={
            "name": "X", "email": "x@test.in", "password": "abc",
        })
        assert r.status_code == 400

    def test_register_rejects_bad_email(self, client):
        r = client.post("/auth/register", json={
            "name": "X", "email": "not-an-email", "password": "secret1",
        })
        assert r.status_code == 400

    def test_register_blocked_in_auth0_mode(self, client, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "auth_provider", "auth0")
        r = client.post("/auth/register", json={
            "name": "X", "email": "x@test.in", "password": "secret1",
        })
        assert r.status_code == 400
