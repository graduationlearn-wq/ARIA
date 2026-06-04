"""
Tests for the /admin/* endpoints and the /ui/ dashboard SPA.

Covers:
  - KB editor HTML page
  - GET /admin/kb/entries
  - POST /admin/kb  (create)
  - PUT  /admin/kb/{id}  (update answer, toggle active, 404 guard)
  - GET /ui/  (dashboard SPA served as StaticFiles)

No external dependencies — uses the in-memory test DB from conftest.py.
"""

# ─────────────────────────────────────────────────────────────────────────────
# KB Editor page
# ─────────────────────────────────────────────────────────────────────────────

class TestKBAdminPage:

    def test_page_serves_html(self, client):
        resp = client.get("/admin/kb")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_page_contains_editor_ui(self, client):
        resp = client.get("/admin/kb")
        assert "KB Editor" in resp.text
        assert "BeyondSure" in resp.text


# ─────────────────────────────────────────────────────────────────────────────
# KB entries API
# ─────────────────────────────────────────────────────────────────────────────

class TestKBEntries:

    def test_get_entries_returns_list(self, client, db):
        resp = client.get("/admin/kb/entries")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_entry(self, client, db):
        resp = client.post("/admin/kb", json={
            "question": "Does BeyondSure have an API?",
            "answer": "Yes, we offer a REST API for enterprise integrations.",
            "category": "Features",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["question"] == "Does BeyondSure have an API?"
        assert data["category"] == "Features"
        assert "id" in data

    def test_created_entry_appears_in_list(self, client, db):
        client.post("/admin/kb", json={
            "question": "List visibility test?",
            "answer": "Yes.",
            "category": "General",
        })
        resp = client.get("/admin/kb/entries")
        questions = [e["question"] for e in resp.json()]
        assert "List visibility test?" in questions

    def test_update_entry_answer(self, client, db):
        create = client.post("/admin/kb", json={
            "question": "Will this be updated?",
            "answer": "Original answer.",
            "category": "General",
        })
        entry_id = create.json()["id"]

        resp = client.put(f"/admin/kb/{entry_id}", json={"answer": "Updated answer."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Updated answer."

    def test_update_answer_clears_placeholder_flag(self, client, db):
        """Saving an answer must mark the entry as no longer a placeholder."""
        from models.knowledge_base import KnowledgeBase

        # Manually insert a placeholder entry
        entry = KnowledgeBase(
            question="Placeholder Q?",
            answer="[PLACEHOLDER]",
            category="General",
            active=True,
            is_placeholder=True,
        )
        db.add(entry)
        db.flush()

        resp = client.put(f"/admin/kb/{entry.id}", json={"answer": "Real answer now."})
        assert resp.status_code == 200
        assert resp.json()["is_placeholder"] is False

    def test_update_nonexistent_entry_returns_404(self, client, db):
        resp = client.put("/admin/kb/99999", json={"answer": "test"})
        assert resp.status_code == 404

    def test_toggle_entry_inactive(self, client, db):
        create = client.post("/admin/kb", json={
            "question": "Toggle me?",
            "answer": "Some answer.",
            "category": "General",
        })
        entry_id = create.json()["id"]

        resp = client.put(f"/admin/kb/{entry_id}", json={"active": False})
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_toggle_entry_back_to_active(self, client, db):
        create = client.post("/admin/kb", json={
            "question": "Toggle back?",
            "answer": "Some answer.",
            "category": "General",
        })
        entry_id = create.json()["id"]

        client.put(f"/admin/kb/{entry_id}", json={"active": False})
        resp = client.put(f"/admin/kb/{entry_id}", json={"active": True})
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    def test_update_answer_and_active_together(self, client, db):
        create = client.post("/admin/kb", json={
            "question": "Both fields?",
            "answer": "Old answer.",
            "category": "General",
        })
        entry_id = create.json()["id"]

        resp = client.put(f"/admin/kb/{entry_id}", json={
            "answer": "New answer.",
            "active": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "New answer."
        assert data["active"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Config endpoint (Settings page)
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_config_returns_sections(self, client, db):
        resp = client.get("/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("aria", "channels", "alerts", "knowledge_base"):
            assert key in data

    def test_config_has_no_secrets(self, client, db):
        """Config must never leak API keys or SMTP passwords."""
        resp = client.get("/admin/config")
        body = resp.text.lower()
        assert "api_key" not in body
        assert "password" not in body
        assert "smtp_password" not in body

    def test_config_channels_are_booleans(self, client, db):
        resp = client.get("/admin/config")
        channels = resp.json()["channels"]
        for ch in channels.values():
            assert isinstance(ch["connected"], bool)
            assert "label" in ch and "note" in ch

    def test_config_kb_counts_present(self, client, db):
        resp = client.get("/admin/config")
        kb = resp.json()["knowledge_base"]
        for key in ("total", "active", "placeholders", "answered"):
            assert key in kb and isinstance(kb[key], int)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard SPA
# ─────────────────────────────────────────────────────────────────────────────

class TestDashboardSPA:

    def test_spa_root_serves_html(self, client):
        """/ui/ must serve index.html — confirms StaticFiles mount is wired correctly."""
        resp = client.get("/ui/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_spa_contains_aria_branding(self, client):
        resp = client.get("/ui/")
        assert "ARIA" in resp.text
