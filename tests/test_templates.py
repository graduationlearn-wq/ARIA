"""
Tests for the stage-aware email template system:
rendering, CRUD, preview, send (with Interaction logging), and attachments.
"""

from io import BytesIO
from unittest.mock import patch

from models.email_template import EmailTemplate
from models.interaction import Interaction
from models.lead import Lead
from services.template_service import (
    DEFAULT_TEMPLATES, render_template, seed_templates,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_lead(db, **overrides):
    fields = dict(first_name="Harsh", email="harsh@rupeeco.com",
                  company_name="RupeeCo", lead_type="broker", status="engaged")
    fields.update(overrides)
    lead = Lead(**fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def make_template(client, **overrides):
    payload = {
        "name": "Proposal",
        "stage": "interested",
        "subject": "BeyondSure proposal for {company_name}",
        "body": "Dear {lead_name},\n\nPlease find attached.\n\nRegards,\n{sender_name}",
    }
    payload.update(overrides)
    r = client.post("/templates/", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ── Rendering ─────────────────────────────────────────────────────────────────

class TestRendering:
    def test_fills_lead_and_company(self, db):
        lead = make_lead(db)
        text, unknown = render_template("Dear {lead_name} of {company_name},", lead)

        assert text == "Dear Harsh of RupeeCo,"
        assert unknown == []

    def test_fallbacks_when_lead_fields_missing(self, db):
        lead = make_lead(db, first_name=None, company_name=None)
        text, _ = render_template("Hi {lead_name} at {company_name}", lead)

        assert text == "Hi there at your company"

    def test_unknown_tokens_are_kept_and_reported(self, db):
        lead = make_lead(db)
        text, unknown = render_template("Hello {lead_name} {made_up_token}", lead)

        assert "{made_up_token}" in text
        assert unknown == ["made_up_token"]

    def test_seed_templates_is_idempotent(self, db):
        seed_templates(db)
        seed_templates(db)

        assert db.query(EmailTemplate).count() == len(DEFAULT_TEMPLATES)


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestTemplateCrud:
    def test_create_and_list(self, client):
        created = make_template(client, name="My Proposal")

        r = client.get("/templates/")
        names = [t["name"] for t in r.json()["templates"]]
        assert "My Proposal" in names
        assert created["stage_label"] == "Interested"

    def test_create_rejects_unknown_stage(self, client):
        r = client.post("/templates/", json={
            "name": "X", "stage": "galaxy", "subject": "s", "body": "b",
        })
        assert r.status_code == 400

    def test_update_changes_fields(self, client):
        tpl = make_template(client)
        r = client.put(f"/templates/{tpl['id']}", json={
            "name": "Renamed", "stage": "won", "subject": "New subject", "body": "New body",
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"
        assert r.json()["stage"] == "won"

    def test_delete_hides_from_list(self, client):
        tpl = make_template(client, name="Doomed")
        r = client.delete(f"/templates/{tpl['id']}")
        assert r.status_code == 200

        names = [t["name"] for t in client.get("/templates/").json()["templates"]]
        assert "Doomed" not in names

    def test_stage_filter(self, client):
        make_template(client, name="WonTpl", stage="won")
        make_template(client, name="IntTpl", stage="interested")

        names = [t["name"] for t in client.get("/templates/?stage=won").json()["templates"]]
        assert "WonTpl" in names
        assert "IntTpl" not in names


# ── Preview ───────────────────────────────────────────────────────────────────

class TestPreview:
    def test_preview_renders_for_lead(self, client, db):
        lead = make_lead(db)
        tpl = make_template(client)

        r = client.get(f"/templates/{tpl['id']}/preview?lead_id={lead.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["to"] == "harsh@rupeeco.com"
        assert data["subject"] == "BeyondSure proposal for RupeeCo"
        assert "Dear Harsh," in data["body"]
        assert "Test Admin" in data["body"]  # sender from logged-in user

    def test_preview_missing_lead_404(self, client):
        tpl = make_template(client)
        r = client.get(f"/templates/{tpl['id']}/preview?lead_id=99999")
        assert r.status_code == 404


# ── Send ──────────────────────────────────────────────────────────────────────

class TestSend:
    def test_send_renders_and_logs_interaction(self, client, db):
        lead = make_lead(db)
        tpl = make_template(client)

        with patch("routes.templates.send_email", return_value=True) as mock_send:
            r = client.post(f"/templates/{tpl['id']}/send", json={"lead_id": lead.id})

        assert r.status_code == 200
        assert r.json()["status"] == "sent"
        args, kwargs = mock_send.call_args
        assert args[0] == "harsh@rupeeco.com"
        assert args[1] == "BeyondSure proposal for RupeeCo"
        assert "Dear Harsh," in args[2]

        interaction = db.query(Interaction).filter(Interaction.lead_id == lead.id).first()
        assert interaction is not None
        assert interaction.handled_by == "human"
        assert interaction.send_status == "sent"
        assert interaction.message_type == "template"

    def test_send_uses_edited_overrides(self, client, db):
        lead = make_lead(db)
        tpl = make_template(client)

        with patch("routes.templates.send_email", return_value=True) as mock_send:
            r = client.post(f"/templates/{tpl['id']}/send", json={
                "lead_id": lead.id,
                "subject": "Edited subject",
                "body": "Edited body",
            })

        assert r.status_code == 200
        args, _ = mock_send.call_args
        assert args[1] == "Edited subject"
        assert args[2] == "Edited body"

    def test_send_fails_without_email(self, client, db):
        lead = make_lead(db, email=None)
        tpl = make_template(client)

        r = client.post(f"/templates/{tpl['id']}/send", json={"lead_id": lead.id})
        assert r.status_code == 400

    def test_send_blocked_for_opted_out_lead(self, client, db):
        lead = make_lead(db, opt_out=True)
        tpl = make_template(client)

        r = client.post(f"/templates/{tpl['id']}/send", json={"lead_id": lead.id})
        assert r.status_code == 400

    def test_failed_smtp_logged_as_failed(self, client, db):
        lead = make_lead(db)
        tpl = make_template(client)

        with patch("routes.templates.send_email", return_value=False):
            r = client.post(f"/templates/{tpl['id']}/send", json={"lead_id": lead.id})

        assert r.status_code == 200
        assert r.json()["status"] == "failed"
        interaction = db.query(Interaction).filter(Interaction.lead_id == lead.id).first()
        assert interaction.send_status == "failed"


# ── Attachments ───────────────────────────────────────────────────────────────

class TestAttachments:
    def test_upload_attach_send_and_remove(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.templates.TEMPLATE_FILES_DIR", str(tmp_path))
        lead = make_lead(db)
        tpl = make_template(client)

        # Upload
        r = client.post(
            f"/templates/{tpl['id']}/attachments",
            files={"file": ("Profile.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
        assert r.status_code == 200, r.text
        files = r.json()["attachments"]
        assert files[0]["display"] == "Profile.pdf"
        assert files[0]["exists"] is True
        stored = files[0]["file"]
        assert stored.startswith(f"t{tpl['id']}__")

        # Send includes the attachment path
        with patch("routes.templates.send_email", return_value=True) as mock_send:
            client.post(f"/templates/{tpl['id']}/send", json={"lead_id": lead.id})
        _, kwargs = mock_send.call_args
        assert len(kwargs["attachments"]) == 1
        assert kwargs["attachments"][0].endswith(stored)

        # Download works for listed file only
        assert client.get(f"/templates/{tpl['id']}/attachments/{stored}").status_code == 200
        assert client.get(f"/templates/{tpl['id']}/attachments/evil.pdf").status_code == 404

        # Remove detaches and deletes the uploaded file
        r = client.delete(f"/templates/{tpl['id']}/attachments/{stored}")
        assert r.status_code == 200
        assert r.json()["attachments"] == []
        assert not (tmp_path / stored).exists()

    def test_upload_rejects_disallowed_extension(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.templates.TEMPLATE_FILES_DIR", str(tmp_path))
        tpl = make_template(client)

        r = client.post(
            f"/templates/{tpl['id']}/attachments",
            files={"file": ("malware.exe", BytesIO(b"MZ"), "application/octet-stream")},
        )
        assert r.status_code == 400

    def test_upload_sanitizes_traversal_filename(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.templates.TEMPLATE_FILES_DIR", str(tmp_path))
        tpl = make_template(client)

        r = client.post(
            f"/templates/{tpl['id']}/attachments",
            files={"file": ("..\\..\\sneaky.pdf", BytesIO(b"%PDF"), "application/pdf")},
        )
        assert r.status_code == 200
        stored = r.json()["attachments"][0]["file"]
        assert ".." not in stored
        assert "/" not in stored and "\\" not in stored
