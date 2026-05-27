"""
Tests for the /leads/* endpoints.

Covers: list, detail, stats, and manual override routes.
Fixtures come from conftest.py.
"""

from unittest.mock import patch

BROKER_PAYLOAD = {
    "first_name": "Ravi",
    "email": "ravi@leadtest.in",
    "phone": "9000000001",
    "state": "Gujarat",
    "company_name": "Ravi Brokers",
    "types_of_business": "broker",
    "are_you_open_to_adopting_a_new_technology_platform": "yes",
    "do_you_currently_use_any_software": "no",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "yes",
    "platform": "fb",
}

IMF_PAYLOAD = {
    "first_name": "Sunita",
    "email": "sunita@imftest.in",
    "phone": "9000000002",
    "state": "Rajasthan",
    "types_of_business": "imf",
    "are_you_open_to_adopting_a_new_technology_platform": "no",
    "do_you_currently_use_any_software": "yes",
    "would_you_be_willing_to_evaluate_a_new_tech_solution": "no",
    "platform": "ig",
}


def _post_lead(client, payload=None):
    """Helper: create a lead via webhook and return the response JSON."""
    with patch("routes.webhook.send_email", return_value=True), \
         patch("config.settings.human_approval_mode", True):
        return client.post("/webhook/lead", json=payload or BROKER_PAYLOAD).json()


# ─────────────────────────────────────────────────────────────────────────────

class TestLeadsList:

    def test_empty_list_initially(self, client):
        resp = client.get("/leads/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_lead_after_creation(self, client):
        _post_lead(client)
        leads = client.get("/leads/").json()
        assert len(leads) == 1
        assert leads[0]["name"] == "Ravi"

    def test_list_includes_new_fields(self, client):
        _post_lead(client)
        lead = client.get("/leads/").json()[0]
        # Fields added in the enrich pass
        assert "phone" in lead
        assert "team_size" in lead
        assert "willing_for_demo" in lead
        assert "human_priority" in lead

    def test_filter_by_quality(self, client):
        _post_lead(client)
        # Broker + demo + open = warm/hot — filtering for "cold" should return 0
        resp = client.get("/leads/?quality=cold")
        assert resp.status_code == 200
        leads = resp.json()
        assert all(l["quality"] == "cold" for l in leads)

    def test_filter_by_status(self, client):
        _post_lead(client)
        resp = client.get("/leads/?status=new")
        assert resp.status_code == 200
        leads = resp.json()
        assert all(l["status"] == "new" for l in leads)

    def test_limit_is_respected(self, client):
        _post_lead(client)
        _post_lead(client, IMF_PAYLOAD)
        resp = client.get("/leads/?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_sorted_by_score_descending(self, client):
        _post_lead(client)           # broker — high score
        _post_lead(client, IMF_PAYLOAD)  # IMF no demo — lower score
        leads = client.get("/leads/").json()
        scores = [l["score"] for l in leads]
        assert scores == sorted(scores, reverse=True)


class TestLeadDetail:

    def test_returns_full_lead(self, client):
        created = _post_lead(client)
        lead_id = created["id"]
        resp = client.get(f"/leads/{lead_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "lead" in data
        assert "interactions" in data

    def test_returns_all_chat_flow_fields(self, client):
        created = _post_lead(client)
        lead = client.get(f"/leads/{created['id']}").json()["lead"]
        for field in [
            "uses_software", "open_to_platform", "willing_for_demo",
            "demo_preference", "company_website", "re_engage_after",
            "current_intent", "last_interaction_at", "channel",
        ]:
            assert field in lead, f"Missing field: {field}"

    def test_nonexistent_lead_returns_error(self, client):
        resp = client.get("/leads/9999")
        assert resp.status_code == 200  # returns {"error": "..."}, not 404
        assert "error" in resp.json()

    def test_interactions_list_is_present(self, client):
        created = _post_lead(client)
        detail = client.get(f"/leads/{created['id']}").json()
        assert isinstance(detail["interactions"], list)
        # At least the first-touch interaction should exist
        assert len(detail["interactions"]) >= 1


class TestLeadStats:

    def test_stats_on_empty_db(self, client):
        resp = client.get("/leads/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_leads"] == 0
        assert data["avg_first_response_minutes"] is None

    def test_stats_count_correct_after_creation(self, client):
        _post_lead(client)
        _post_lead(client, IMF_PAYLOAD)
        data = client.get("/leads/stats").json()
        assert data["total_leads"] == 2
        assert "by_quality" in data
        assert "by_status" in data


class TestLeadManualOverrides:

    def test_toggle_priority_on(self, client):
        created = _post_lead(client)
        resp = client.post(f"/leads/{created['id']}/priority")
        assert resp.status_code == 200
        assert resp.json()["human_priority"] is True

    def test_toggle_priority_off(self, client):
        created = _post_lead(client)
        client.post(f"/leads/{created['id']}/priority")   # turn on
        resp = client.post(f"/leads/{created['id']}/priority")  # turn off
        assert resp.json()["human_priority"] is False

    def test_set_notes(self, client):
        created = _post_lead(client)
        resp = client.post(
            f"/leads/{created['id']}/notes",
            json={"notes": "Spoke to him — very interested in broker plan"},
        )
        assert resp.status_code == 200
        assert resp.json()["human_notes"] == "Spoke to him — very interested in broker plan"

    def test_override_status_valid(self, client):
        created = _post_lead(client)
        resp = client.patch(
            f"/leads/{created['id']}/status",
            json={"status": "converted", "reason": "Signed up directly"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "converted"

    def test_override_status_invalid_value(self, client):
        created = _post_lead(client)
        resp = client.patch(
            f"/leads/{created['id']}/status",
            json={"status": "flying_spaghetti_monster"},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()
