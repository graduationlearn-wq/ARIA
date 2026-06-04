"""
Tests for the /chat/* endpoints.

LLM calls, email sends, and WhatsApp sends are all mocked so
tests run offline with no external dependencies.
Fixtures come from conftest.py.
"""

from unittest.mock import patch

from models.lead import Lead

# Payload used to create the test lead before each chat test
_LEAD_PAYLOAD = {
    "first_name": "Ananya",
    "email": "ananya@chattest.in",
    "phone": "9111111111",
    "state": "Delhi",
    "company_name": "Ananya Insurance",
    "types_of_business": "agent",
    "platform": "fb",
}

def _make_patches() -> list:
    """
    Create a fresh list of patchers for each test.
    Must be called per-test — patcher objects are NOT reusable after stop().
    """
    return [
        patch("routes.chat.send_human_alert",       return_value=True),
        patch("routes.chat.send_alert_whatsapp",    return_value=True),
        patch("routes.chat.send_demo_confirmation", return_value=True),
        patch("routes.chat.send_demo_whatsapp",     return_value=True),
        patch("routes.chat.generate_chat_response", return_value="Test LLM response."),
        patch("routes.webhook.send_email",          return_value=True),
    ]


def _start_patches() -> list:
    """Start all outbound-call patches and return the patcher list for later stopping."""
    patches = _make_patches()
    for p in patches:
        p.start()
    return patches   # return patchers (not mocks) so _stop_patches can call p.stop()


def _stop_patches(patches: list) -> None:
    for p in patches:
        p.stop()


def _create_lead_and_get_token(client, db) -> tuple[int, str]:
    """Create a lead via webhook and return (lead_id, chat_token)."""
    with patch("routes.webhook.send_email", return_value=True), \
         patch("config.settings.human_approval_mode", True):
        resp = client.post("/webhook/lead", json=_LEAD_PAYLOAD)
    lead_id = resp.json()["id"]
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    return lead_id, lead.chat_token


# ─────────────────────────────────────────────────────────────────────────────

class TestChatPage:

    def test_valid_token_returns_html(self, client, db):
        _, token = _create_lead_and_get_token(client, db)
        resp = client.get(f"/chat/{token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "BeyondSure" in resp.text

    def test_invalid_token_returns_404(self, client):
        resp = client.get("/chat/totally-fake-token-xyz")
        assert resp.status_code == 404


class TestChatHistory:

    def test_welcome_message_on_first_visit(self, client, db):
        _, token = _create_lead_and_get_token(client, db)
        resp = client.get(f"/chat/{token}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "welcome" in data
        assert data["welcome"]["message"] != ""
        assert len(data["welcome"]["options"]) > 0

    def test_chat_opened_at_set_on_first_visit(self, client, db):
        lead_id, token = _create_lead_and_get_token(client, db)
        client.get(f"/chat/{token}/history")
        db.expire_all()
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        assert lead.chat_opened_at is not None

    def test_invalid_token_returns_error(self, client):
        resp = client.get("/chat/invalid-token/history")
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_history_returned_after_messages(self, client, db):
        mocks = _start_patches()
        try:
            _, token = _create_lead_and_get_token(client, db)
            client.post(f"/chat/{token}/message", json={"message": "Hi there"})
            resp = client.get(f"/chat/{token}/history")
            data = resp.json()
            assert "messages" in data
            assert len(data["messages"]) >= 1
        finally:
            _stop_patches(mocks)


class TestChatMessage:

    def test_invalid_token_returns_404(self, client):
        resp = client.post("/chat/bad-token/message", json={"message": "Hello"})
        assert resp.status_code == 404

    def test_empty_message_returns_400(self, client, db):
        """Whitespace-only message is caught by the route handler → 400."""
        _, token = _create_lead_and_get_token(client, db)
        resp = client.post(f"/chat/{token}/message", json={"message": "   "})
        assert resp.status_code == 400

    def test_message_exceeds_max_length_returns_422(self, client, db):
        """Messages over 2000 chars are rejected by Pydantic before hitting the LLM."""
        _, token = _create_lead_and_get_token(client, db)
        resp = client.post(f"/chat/{token}/message", json={"message": "A" * 2001})
        assert resp.status_code == 422

    def test_exact_max_length_accepted(self, client, db):
        """A message of exactly 2000 chars must be accepted (boundary check)."""
        mocks = _start_patches()
        try:
            _, token = _create_lead_and_get_token(client, db)
            resp = client.post(f"/chat/{token}/message", json={"message": "B" * 2000})
            assert resp.status_code == 200
        finally:
            _stop_patches(mocks)

    def test_guided_flow_responds_to_first_message(self, client, db):
        mocks = _start_patches()
        try:
            _, token = _create_lead_and_get_token(client, db)
            resp = client.post(f"/chat/{token}/message", json={"message": "Let's go!"})
            assert resp.status_code == 200
            data = resp.json()
            assert "message" in data
            assert data["escalated"] is False
            assert len(data["message"]) > 0
        finally:
            _stop_patches(mocks)

    def test_not_interested_sets_opt_out(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            client.post(f"/chat/{token}/message", json={"message": "not interested, stop messaging"})
            db.expire_all()
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            assert lead.opt_out is True
            assert lead.status == "lost"
        finally:
            _stop_patches(mocks)

    def test_opt_out_lead_gets_blocked_response(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            # Opt out first
            client.post(f"/chat/{token}/message", json={"message": "not interested"})
            # Try messaging again
            resp = client.post(f"/chat/{token}/message", json={"message": "actually wait"})
            assert resp.status_code == 200
            assert "unsubscribed" in resp.json()["message"].lower()
        finally:
            _stop_patches(mocks)

    def test_escalation_request_creates_escalation_row(self, client, db):
        from models.escalation import Escalation
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            resp = client.post(
                f"/chat/{token}/message",
                json={"message": "I want to speak to a real person"},
            )
            assert resp.status_code == 200
            assert resp.json()["escalated"] is True
            # Escalation row must exist in DB
            escalation = db.query(Escalation).filter(Escalation.lead_id == lead_id).first()
            assert escalation is not None
        finally:
            _stop_patches(mocks)

    def test_uses_software_answer_updates_lead(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            # Answer the first guided step: uses_software
            client.post(f"/chat/{token}/message", json={"message": "No, managing manually"})
            db.expire_all()
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            assert lead.uses_software is False
        finally:
            _stop_patches(mocks)

    def test_unclear_first_asks_clarifying_question(self, client, db):
        mocks = _start_patches()
        try:
            _, token = _create_lead_and_get_token(client, db)
            resp = client.post(
                f"/chat/{token}/message",
                json={"message": "xkzqwerty gibberish 999"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["escalated"] is False
            # Should ask a clarifying question, not escalate immediately
            assert len(data["message"]) > 0
        finally:
            _stop_patches(mocks)


class TestHumanReply:
    """Tests for POST /chat/admin/{lead_id}/reply — team member sends into chat thread."""

    def test_human_reply_creates_interaction(self, client, db):
        from models.interaction import Interaction
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            resp = client.post(
                f"/chat/admin/{lead_id}/reply",
                json={"message": "Hi, this is Kunal from BeyondSure. How can I help?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["lead_name"] is not None
            assert "message" in data
            assert "timestamp" in data

            # Verify the interaction row was created as human outbound
            interaction = (
                db.query(Interaction)
                .filter(
                    Interaction.lead_id == lead_id,
                    Interaction.handled_by == "human",
                    Interaction.direction == "outbound",
                )
                .first()
            )
            assert interaction is not None
            assert interaction.message_text == "Hi, this is Kunal from BeyondSure. How can I help?"
        finally:
            _stop_patches(mocks)

    def test_human_reply_appears_in_chat_history(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            # Open chat first (sets chat_opened_at)
            client.get(f"/chat/{token}/history")
            # Team member sends a reply
            client.post(f"/chat/admin/{lead_id}/reply", json={"message": "Team reply here."})
            # History should now include the human message
            resp = client.get(f"/chat/{token}/history")
            data = resp.json()
            human_msgs = [m for m in data.get("messages", []) if m.get("handled_by") == "human"]
            assert len(human_msgs) >= 1
            assert human_msgs[-1]["text"] == "Team reply here."
        finally:
            _stop_patches(mocks)

    def test_human_reply_404_for_unknown_lead(self, client, db):
        resp = client.post("/chat/admin/99999/reply", json={"message": "Hello"})
        assert resp.status_code == 404

    def test_human_reply_too_long_returns_422(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, _ = _create_lead_and_get_token(client, db)
            resp = client.post(f"/chat/admin/{lead_id}/reply", json={"message": "X" * 2001})
            assert resp.status_code == 422
        finally:
            _stop_patches(mocks)


class TestChatAdminView:

    def test_admin_view_returns_conversation(self, client, db):
        mocks = _start_patches()
        try:
            lead_id, token = _create_lead_and_get_token(client, db)
            client.post(f"/chat/{token}/message", json={"message": "Hello"})
            resp = client.get(f"/chat/admin/{lead_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert "lead" in data
            assert "conversation" in data
            assert data["lead"]["id"] == lead_id
        finally:
            _stop_patches(mocks)

    def test_admin_view_404_for_unknown_lead(self, client):
        resp = client.get("/chat/admin/99999")
        assert resp.status_code == 404
