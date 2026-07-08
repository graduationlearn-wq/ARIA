"""
Tests for per-user email signature images:
upload / replace, public serve, delete, validation, and login requirement.
"""

from io import BytesIO

from main import app
from models.user import User
from routes.auth import get_current_user

# Minimal valid-ish PNG header + filler bytes.
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def as_real_user(db, name="Rep", email="rep@bs.in"):
    """Persist a user and log in as them (the /signatures/me routes commit to it)."""
    u = User(name=name, email=email, role="employee", password_hash="x")
    db.add(u); db.commit(); db.refresh(u)
    app.dependency_overrides[get_current_user] = lambda: u
    return u


def png_upload():
    return {"file": ("sig.png", BytesIO(PNG), "image/png")}


class TestSignatureUpload:
    def test_upload_sets_serves_and_exposes(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.signatures.SIGNATURE_FILES_DIR", str(tmp_path))
        u = as_real_user(db)

        r = client.post("/signatures/me", files=png_upload())
        assert r.status_code == 200, r.text
        stored = r.json()["signature_image"]
        assert stored == f"u{u.id}.png"
        assert db.get(User, u.id).signature_image == stored
        assert (tmp_path / stored).is_file()

        # Public serve (email clients fetch this) + /auth/me exposes the URL.
        assert client.get(f"/signatures/{stored}").status_code == 200
        assert client.get("/auth/me").json()["signature_url"] == f"/signatures/{stored}"

    def test_replacing_removes_the_old_file(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.signatures.SIGNATURE_FILES_DIR", str(tmp_path))
        u = as_real_user(db)
        client.post("/signatures/me", files=png_upload())
        # Upload a jpg — the old png must be cleaned up (one signature per user).
        client.post("/signatures/me", files={"file": ("s.jpg", BytesIO(PNG), "image/jpeg")})
        assert db.get(User, u.id).signature_image == f"u{u.id}.jpg"
        assert not (tmp_path / f"u{u.id}.png").exists()

    def test_rejects_non_image(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.signatures.SIGNATURE_FILES_DIR", str(tmp_path))
        as_real_user(db)
        r = client.post("/signatures/me",
                        files={"file": ("sig.pdf", BytesIO(b"%PDF"), "application/pdf")})
        assert r.status_code == 400

    def test_delete_clears(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.signatures.SIGNATURE_FILES_DIR", str(tmp_path))
        u = as_real_user(db)
        client.post("/signatures/me", files=png_upload())
        r = client.delete("/signatures/me")
        assert r.status_code == 200
        assert db.get(User, u.id).signature_image is None
        assert not (tmp_path / f"u{u.id}.png").exists()

    def test_serve_404_when_missing(self, client, db, tmp_path, monkeypatch):
        monkeypatch.setattr("routes.signatures.SIGNATURE_FILES_DIR", str(tmp_path))
        assert client.get("/signatures/nope.png").status_code == 404

    def test_upload_requires_login(self, client, db):
        app.dependency_overrides.pop(get_current_user, None)
        r = client.post("/signatures/me", files=png_upload())
        assert r.status_code == 401


# ── Inline (CID) embedding of the signature in the actual email ───────────────

class _FakeSMTP:
    captured = {}

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def ehlo(self): pass
    def starttls(self): pass
    def login(self, *a): pass
    def sendmail(self, frm, to, msg): _FakeSMTP.captured["msg"] = msg


def _with_smtp(monkeypatch, tmp_path):
    from utils import email_sender
    monkeypatch.setattr(email_sender.settings, "smtp_user", "u@x.in")
    monkeypatch.setattr(email_sender.settings, "smtp_password", "pw")
    monkeypatch.setattr(email_sender.settings, "email_from_address", "from@x.in")
    monkeypatch.setattr(email_sender.smtplib, "SMTP", _FakeSMTP)
    return email_sender


def test_signature_embedded_inline_via_cid(tmp_path, monkeypatch):
    es = _with_smtp(monkeypatch, tmp_path)
    img = tmp_path / "sig.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)

    ok = es.send_email("lead@x.in", "Sub", "Hello", signature_image_path=str(img))
    assert ok is True
    raw = _FakeSMTP.captured["msg"]
    assert "multipart/related" in raw               # image nested with the HTML
    assert "Content-ID: <aria-signature>" in raw    # the inline image part
    assert "cid:aria-signature" in raw              # referenced from the HTML body


def test_no_cid_when_signature_file_missing(tmp_path, monkeypatch):
    es = _with_smtp(monkeypatch, tmp_path)
    ok = es.send_email("lead@x.in", "Sub", "Hello",
                       signature_image_path=str(tmp_path / "does_not_exist.png"))
    assert ok is True
    assert "cid:aria-signature" not in _FakeSMTP.captured["msg"]
