"""
Tests for /webhook and /approval routes.

Uses an in-memory SQLite DB per test session and patches send_email so no
real SMTP calls are made.  human_approval_mode is forced True so every
first-touch message lands in the queue rather than being sent.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app

# ── Test DB setup ─────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Fresh DB transaction rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Reusable payloads ─────────────────────────────────────────────────────────

BROKER_PAYLOAD = {
    "first_name": "Rajesh",
    "email": "rajesh@brokerhouse.in",
    "phone": "9876543210",
    "state": "Maharashtra",
    "company_name": "Mehta Brokers",
    "types_of_business": "broker",
    "are_you_open_to_adopting_a_new_technology_platform": "yes",
    "do_you_currently_use_any_software": "no",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "yes",
    "platform": "fb",
}

AGENT_PAYLOAD = {
    "first_name": "Priya",
    "email": "priya@agents.in",
    "phone": "9123456780",
    "state": "Karnataka",
    "types_of_business": "insurance_agent",
    "are_you_open_to_adopting_a_new_technology_platform": "no",
    "do_you_currently_use_any_software": "yes",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "no",
    "platform": "ig",
}

INVALID_PAYLOAD = {
    "first_name": "Bot",
    "email": "spam@test.com",
    "types_of_business": "invalid",
    "platform": "fb",
}


# ── /webhook/lead ─────────────────────────────────────────────────────────────

class TestWebhookLead:

    def test_creates_lead_and_returns_response(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json=BROKER_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert data["first_name"] == "Rajesh"
        assert data["email"] == "rajesh@brokerhouse.in"
        assert data["id"] >= 1

    def test_broker_scores_warm_or_hot(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json=BROKER_PAYLOAD)

        data = resp.json()
        # broker + demo willing + open to platform = 15+20+10 = 45 → warm
        assert data["lead_quality"] in ("warm", "hot")
        assert data["lead_score"] >= 40

    def test_agent_scores_lower_than_broker(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            broker_resp = client.post("/webhook/lead", json=BROKER_PAYLOAD)
            agent_resp = client.post("/webhook/lead", json=AGENT_PAYLOAD)

        assert agent_resp.status_code == 200
        assert agent_resp.json()["lead_score"] < broker_resp.json()["lead_score"]

    def test_invalid_lead_type_scores_zero(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json=INVALID_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert data["lead_score"] == 0
        assert data["lead_quality"] == "invalid"

    def test_status_is_new_when_approval_mode_on(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json=BROKER_PAYLOAD)

        assert resp.json()["status"] == "new"

    def test_email_not_sent_when_approval_mode_on(self, client):
        with patch("routes.webhook.send_email", return_value=True) as mock_send, \
             patch("config.settings.human_approval_mode", True):
            client.post("/webhook/lead", json=BROKER_PAYLOAD)

        mock_send.assert_not_called()

    def test_status_is_contacted_when_approval_mode_off(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", False):
            resp = client.post("/webhook/lead", json=BROKER_PAYLOAD)

        assert resp.json()["status"] == "contacted"

    def test_minimal_payload_accepted(self, client):
        """Only first_name and email — all other fields optional."""
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json={
                "first_name": "Anon",
                "email": "anon@example.com",
            })

        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Anon"

    def test_empty_payload_accepted(self, client):
        """All fields are optional — empty body should not 422."""
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            resp = client.post("/webhook/lead", json={})

        assert resp.status_code == 200


# ── /approval/queue ───────────────────────────────────────────────────────────

class TestApprovalQueue:

    def _post_lead(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            return client.post("/webhook/lead", json=BROKER_PAYLOAD).json()

    def test_queue_empty_initially(self, client):
        resp = client.get("/approval/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pending"] == 0
        assert data["drafts"] == []

    def test_queue_contains_draft_after_lead_created(self, client):
        self._post_lead(client)
        resp = client.get("/approval/queue")
        data = resp.json()
        assert data["total_pending"] == 1
        draft = data["drafts"][0]
        assert draft["lead_name"] == "Rajesh"
        assert draft["lead_email"] == "rajesh@brokerhouse.in"
        assert draft["draft_message"] is not None
        assert draft["draft_id"] >= 1

    def test_queue_draft_has_lead_quality(self, client):
        self._post_lead(client)
        draft = client.get("/approval/queue").json()["drafts"][0]
        assert draft["lead_quality"] in ("cold", "warm", "hot", "new")
        assert isinstance(draft["lead_score"], int)


# ── /approval/{id}/approve ────────────────────────────────────────────────────

class TestApprovalApprove:

    def _create_draft(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            client.post("/webhook/lead", json=BROKER_PAYLOAD)
        return client.get("/approval/queue").json()["drafts"][0]["draft_id"]

    def test_approve_sends_email_and_returns_sent(self, client):
        draft_id = self._create_draft(client)
        with patch("routes.approval.send_email", return_value=True) as mock_send:
            resp = client.post(f"/approval/{draft_id}/approve")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["draft_id"] == draft_id
        assert data["to"] == "rajesh@brokerhouse.in"
        mock_send.assert_called_once()

    def test_approve_removes_draft_from_queue(self, client):
        draft_id = self._create_draft(client)
        with patch("routes.approval.send_email", return_value=True):
            client.post(f"/approval/{draft_id}/approve")

        queue = client.get("/approval/queue").json()
        assert queue["total_pending"] == 0

    def test_approve_nonexistent_draft_returns_404(self, client):
        resp = client.post("/approval/9999/approve")
        assert resp.status_code == 404

    def test_approve_already_processed_draft_returns_404(self, client):
        draft_id = self._create_draft(client)
        with patch("routes.approval.send_email", return_value=True):
            client.post(f"/approval/{draft_id}/approve")
        # second approval attempt
        resp = client.post(f"/approval/{draft_id}/approve")
        assert resp.status_code == 404

    def test_approve_returns_500_on_smtp_failure(self, client):
        draft_id = self._create_draft(client)
        with patch("routes.approval.send_email", return_value=False):
            resp = client.post(f"/approval/{draft_id}/approve")
        assert resp.status_code == 500


# ── /approval/{id}/edit ───────────────────────────────────────────────────────

class TestApprovalEdit:

    def _create_draft(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            client.post("/webhook/lead", json=BROKER_PAYLOAD)
        return client.get("/approval/queue").json()["drafts"][0]["draft_id"]

    def test_edit_sends_revised_text(self, client):
        draft_id = self._create_draft(client)
        revised = "Hi Rajesh, let's schedule a quick 15-min call this week!"
        with patch("routes.approval.send_email", return_value=True) as mock_send:
            resp = client.post(f"/approval/{draft_id}/edit", json={
                "revised_text": revised,
                "reviewer_notes": "Made it shorter",
            })

        assert resp.status_code == 200
        assert resp.json()["status"] == "sent_with_edits"
        call_args = mock_send.call_args
        assert revised in call_args[0]  # positional arg 2 (body)

    def test_edit_removes_draft_from_queue(self, client):
        draft_id = self._create_draft(client)
        with patch("routes.approval.send_email", return_value=True):
            client.post(f"/approval/{draft_id}/edit", json={"revised_text": "Updated."})

        assert client.get("/approval/queue").json()["total_pending"] == 0

    def test_edit_nonexistent_draft_returns_404(self, client):
        resp = client.post("/approval/9999/edit", json={"revised_text": "Hello"})
        assert resp.status_code == 404

    def test_edit_missing_revised_text_returns_422(self, client):
        draft_id = self._create_draft(client)
        resp = client.post(f"/approval/{draft_id}/edit", json={})
        assert resp.status_code == 422


# ── /approval/{id}/reject ─────────────────────────────────────────────────────

class TestApprovalReject:

    def _create_draft(self, client):
        with patch("routes.webhook.send_email", return_value=True), \
             patch("config.settings.human_approval_mode", True):
            client.post("/webhook/lead", json=BROKER_PAYLOAD)
        return client.get("/approval/queue").json()["drafts"][0]["draft_id"]

    def test_reject_returns_rejected_status(self, client):
        draft_id = self._create_draft(client)
        resp = client.post(f"/approval/{draft_id}/reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert data["draft_id"] == draft_id

    def test_reject_removes_draft_from_queue(self, client):
        draft_id = self._create_draft(client)
        client.post(f"/approval/{draft_id}/reject")
        assert client.get("/approval/queue").json()["total_pending"] == 0

    def test_reject_with_notes(self, client):
        draft_id = self._create_draft(client)
        resp = client.post(
            f"/approval/{draft_id}/reject",
            params={"notes": "Tone was off"},
        )
        assert resp.status_code == 200

    def test_reject_nonexistent_draft_returns_404(self, client):
        resp = client.post("/approval/9999/reject")
        assert resp.status_code == 404

    def test_reject_twice_returns_404(self, client):
        draft_id = self._create_draft(client)
        client.post(f"/approval/{draft_id}/reject")
        resp = client.post(f"/approval/{draft_id}/reject")
        assert resp.status_code == 404
