"""
Tests for group-chat attribution in the inbox:
sender recorded from the session, scope-checked replies, and
name/role enrichment on every surface that serves the thread.
"""

from main import app
from models.interaction import Interaction
from models.lead import Lead
from models.user import User
from routes.auth import get_current_user


def make_org(db):
    """admin → leader → emp1, plus emp2 under the same leader."""
    admin = User(name="Admin", email="a@test.in", role="admin", password_hash="x")
    leader = User(name="Team Leader", email="l@test.in", role="manager", password_hash="x")
    emp1 = User(name="Employee One", email="e1@test.in", role="employee", password_hash="x")
    emp2 = User(name="Employee Two", email="e2@test.in", role="employee", password_hash="x")
    db.add_all([admin, leader, emp1, emp2])
    db.flush()
    leader.manager_id = admin.id
    emp1.manager_id = leader.id
    emp2.manager_id = leader.id
    db.commit()
    return admin, leader, emp1, emp2


def make_lead(db, owner_id=None):
    lead = Lead(first_name="Harsh", email="harsh@rupeeco.com",
                company_name="RupeeCo", owner_id=owner_id)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


class TestReplyAttribution:
    def test_reply_records_sender_from_session(self, client, db):
        admin, leader, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(leader)

        r = client.post(f"/chat/admin/{lead.id}/reply", json={"message": "Hello from the leader"})
        assert r.status_code == 200
        assert r.json()["sender_name"] == "Team Leader"
        assert r.json()["sender_role"] == "manager"

        row = db.query(Interaction).filter(Interaction.lead_id == lead.id).first()
        assert row.sender_user_id == leader.id
        assert row.handled_by == "human"

    def test_each_sender_is_attributed_separately(self, client, db):
        admin, leader, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)

        for user, text in [(emp1, "emp msg"), (leader, "leader msg"), (admin, "admin msg")]:
            as_user(user)
            assert client.post(f"/chat/admin/{lead.id}/reply", json={"message": text}).status_code == 200

        senders = [i.sender_user_id for i in db.query(Interaction)
                   .filter(Interaction.lead_id == lead.id).order_by(Interaction.id).all()]
        assert senders == [emp1.id, leader.id, admin.id]


class TestReplyScope:
    def test_other_employee_cannot_reply(self, client, db):
        _, _, emp1, emp2 = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(emp2)

        r = client.post(f"/chat/admin/{lead.id}/reply", json={"message": "intruding"})
        assert r.status_code == 403

    def test_chain_can_reply(self, client, db):
        admin, leader, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)

        for user in (emp1, leader, admin):
            as_user(user)
            r = client.post(f"/chat/admin/{lead.id}/reply", json={"message": "hi"})
            assert r.status_code == 200, f"{user.name} should be able to reply"

    def test_admin_view_scope_checked(self, client, db):
        _, _, emp1, emp2 = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(emp2)

        assert client.get(f"/chat/admin/{lead.id}").status_code == 403


class TestThreadEnrichment:
    def test_lead_detail_includes_sender(self, client, db):
        _, leader, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(leader)
        client.post(f"/chat/admin/{lead.id}/reply", json={"message": "attributed"})

        d = client.get(f"/leads/{lead.id}").json()
        human = [i for i in d["interactions"] if i["handled_by"] == "human"]
        assert human[0]["sender_name"] == "Team Leader"
        assert human[0]["sender_role"] == "manager"

    def test_legacy_message_without_sender_is_null(self, client, db):
        _, _, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        db.add(Interaction(lead_id=lead.id, direction="outbound", channel="chat",
                           message_text="old message", message_type="chat_out",
                           handled_by="human", send_status="sent"))
        db.commit()
        as_user(emp1)

        d = client.get(f"/leads/{lead.id}").json()
        human = [i for i in d["interactions"] if i["handled_by"] == "human"]
        assert human[0]["sender_name"] is None  # frontend falls back to neutral "Team"

    def test_admin_chat_view_includes_sender_and_role(self, client, db):
        admin, _, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(admin)
        client.post(f"/chat/admin/{lead.id}/reply", json={"message": "from admin"})

        conv = client.get(f"/chat/admin/{lead.id}").json()["conversation"]
        human = [m for m in conv if m["role"] == "human"]
        assert human[0]["sender_name"] == "Admin"
        assert human[0]["sender_role"] == "admin"


class TestLeadFacingHistory:
    def test_history_shows_first_name_only(self, client, db):
        _, leader, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        as_user(leader)
        client.post(f"/chat/admin/{lead.id}/reply", json={"message": "hello there"})

        d = client.get(f"/chat/{lead.chat_token}/history").json()
        human = [m for m in d["messages"] if m["handled_by"] == "human"]
        assert human[0]["who"] == "Team"  # first word of "Team Leader"
        # No role/email leaks to the lead-facing payload
        assert "sender_role" not in human[0]
        assert "sender_name" not in human[0]

    def test_aria_messages_have_no_who(self, client, db):
        _, _, emp1, _ = make_org(db)
        lead = make_lead(db, owner_id=emp1.id)
        db.add(Interaction(lead_id=lead.id, direction="outbound", channel="chat",
                           message_text="aria says hi", message_type="chat_out",
                           handled_by="aria", send_status="sent"))
        db.commit()

        d = client.get(f"/chat/{lead.chat_token}/history").json()
        assert d["messages"][0]["who"] is None
