"""
Tests for the /scheduler/* endpoints.

Scheduler jobs (run_followup_1 etc.) use their own SessionLocal
and are tested at the endpoint level — we verify the HTTP contract,
not the DB side-effects (those are covered by the service unit tests).
"""

from unittest.mock import patch


class TestSchedulerStatus:

    def test_status_returns_expected_keys(self, client):
        resp = client.get("/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "human_approval_mode" in data
        assert "followup_1_after_hours" in data
        assert "followup_2_after_hours" in data
        assert "scheduled_jobs" in data

    def test_status_followup_windows_correct(self, client):
        data = client.get("/scheduler/status").json()
        assert data["followup_1_after_hours"] == 24
        assert data["followup_2_after_hours"] == 72


class TestSchedulerManualTriggers:

    def _patch_jobs(self):
        """Patch all job functions so no real DB work happens."""
        return [
            patch("routes.scheduler.run_all_followups",         return_value={"ok": True}),
            patch("routes.scheduler.run_followup_1",            return_value={"queued": 0}),
            patch("routes.scheduler.run_followup_2",            return_value={"queued": 0}),
            patch("routes.scheduler.run_followup_7day",         return_value={"queued": 0}),
            patch("routes.scheduler.run_reengagements",         return_value={"queued": 0}),
            patch("routes.scheduler.run_score_decay",           return_value={"updated": 0}),
            patch("routes.scheduler.run_pending_approved_sends", return_value={"sent": 0}),
        ]

    def test_run_all_returns_completed(self, client):
        patches = self._patch_jobs()
        for p in patches:
            p.start()
        try:
            resp = client.post("/scheduler/run")
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
        finally:
            for p in patches:
                p.stop()

    def test_run_followup1_endpoint(self, client):
        with patch("routes.scheduler.run_followup_1", return_value={"queued": 0}) as m:
            resp = client.post("/scheduler/run/followup-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        m.assert_called_once()

    def test_run_score_decay_endpoint(self, client):
        with patch("routes.scheduler.run_score_decay", return_value={"updated": 0}) as m:
            resp = client.post("/scheduler/run/score-decay")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        m.assert_called_once()

    def test_run_pending_sends_endpoint(self, client):
        with patch("routes.scheduler.run_pending_approved_sends", return_value={"sent": 0}) as m:
            resp = client.post("/scheduler/run/pending-sends")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        m.assert_called_once()


class TestSchedulerTestEmail:

    def test_test_email_fails_gracefully_with_no_smtp(self, client):
        """Should return a failure dict, not crash."""
        with patch("routes.scheduler.send_email", return_value=False):
            resp = client.post(
                "/scheduler/test-email",
                json={"to": "test@example.com", "name": "Test"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_test_email_reports_sent_on_success(self, client):
        with patch("routes.scheduler.send_email", return_value=True):
            resp = client.post(
                "/scheduler/test-email",
                json={"to": "test@example.com", "name": "Test"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"
        assert resp.json()["to"] == "test@example.com"
