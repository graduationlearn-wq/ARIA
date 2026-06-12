"""
Email Templates — stage-aware, one-click outbound emails.

The team picks a template (suggested by the lead's pipeline stage), ARIA fills
{placeholders} from the lead record + logged-in sender, attaches the template's
files (company profile, proposal PDFs…), and sends — no retyping in Gmail.

Endpoints (all require login):
  GET    /templates/                          — list active templates (?stage= filter)
  POST   /templates/                          — create a template
  PUT    /templates/{id}                      — update name/stage/subject/body
  DELETE /templates/{id}                      — deactivate (soft delete)
  GET    /templates/placeholders              — supported {tokens} for the editor
  GET    /templates/{id}/preview?lead_id=     — rendered subject/body for a lead
  POST   /templates/{id}/send                 — send to the lead (logs an Interaction)
  POST   /templates/{id}/attachments          — upload an attachment file
  GET    /templates/{id}/attachments/{name}   — download an attachment
  DELETE /templates/{id}/attachments/{name}   — detach (and remove if template-owned)
"""

import json
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.email_template import EmailTemplate
from models.interaction import Interaction
from models.lead import Lead
from models.user import User
from routes.auth import get_current_user
from services.auth_service import subtree_ids
from services.stages import STAGE_LABELS, lead_stage
from services.template_service import (
    PLACEHOLDERS, attachment_list, render_template,
)
from utils.email_sender import send_email

router = APIRouter(prefix="/templates", tags=["Email Templates"],
                   dependencies=[Depends(get_current_user)])

# Attachment storage — sibling of this package: aria/template_files/
TEMPLATE_FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "template_files")

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
                      ".png", ".jpg", ".jpeg", ".csv", ".txt"}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")
_UPLOAD_PREFIX = re.compile(r"^t\d+__")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_template(template_id: int, db: Session) -> EmailTemplate:
    tpl = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id, EmailTemplate.is_active == True  # noqa: E712
    ).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


def _get_scoped_lead(lead_id: int, db: Session, current: User) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    scope = subtree_ids(current, db)
    if scope is not None and lead.owner_id not in scope:
        raise HTTPException(status_code=403, detail="Not allowed to email this lead")
    return lead


def _attachment_info(tpl: EmailTemplate) -> list[dict]:
    """Attachments with display names + whether the file actually exists on disk."""
    out = []
    for name in attachment_list(tpl):
        out.append({
            "file": name,
            "display": _UPLOAD_PREFIX.sub("", name),
            "exists": os.path.isfile(os.path.join(TEMPLATE_FILES_DIR, name)),
        })
    return out


def _template_json(tpl: EmailTemplate) -> dict:
    return {
        "id": tpl.id,
        "name": tpl.name,
        "stage": tpl.stage,
        "stage_label": STAGE_LABELS.get(tpl.stage) if tpl.stage else None,
        "subject": tpl.subject,
        "body": tpl.body,
        "attachments": _attachment_info(tpl),
    }


def _sanitize_filename(raw: str) -> str:
    """basename + character whitelist; rejects empty/dot-only results."""
    name = os.path.basename(raw or "").strip()
    name = _SAFE_NAME.sub("_", name)
    if not name or name.strip("._ ") == "":
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


# ── Models ────────────────────────────────────────────────────────────────────

class TemplateUpsert(BaseModel):
    name: str
    stage: str | None = None
    subject: str
    body: str


class SendRequest(BaseModel):
    lead_id: int
    subject: str | None = None   # edited override; falls back to rendered template
    body: str | None = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("/")
def list_templates(stage: str | None = None, db: Session = Depends(get_db)):
    q = db.query(EmailTemplate).filter(EmailTemplate.is_active == True)  # noqa: E712
    if stage:
        q = q.filter(EmailTemplate.stage == stage)
    templates = q.order_by(EmailTemplate.name).all()
    return {"templates": [_template_json(t) for t in templates]}


@router.get("/placeholders")
def list_placeholders():
    """The {tokens} the editor can use, with what each one resolves to."""
    return {"placeholders": PLACEHOLDERS}


@router.post("/")
def create_template(body: TemplateUpsert, db: Session = Depends(get_db)):
    if body.stage and body.stage not in STAGE_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{body.stage}'")
    if not body.name.strip() or not body.subject.strip() or not body.body.strip():
        raise HTTPException(status_code=400, detail="Name, subject and body are required")
    tpl = EmailTemplate(name=body.name.strip(), stage=body.stage or None,
                        subject=body.subject.strip(), body=body.body)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return _template_json(tpl)


@router.put("/{template_id}")
def update_template(template_id: int, body: TemplateUpsert, db: Session = Depends(get_db)):
    if body.stage and body.stage not in STAGE_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{body.stage}'")
    if not body.name.strip() or not body.subject.strip() or not body.body.strip():
        raise HTTPException(status_code=400, detail="Name, subject and body are required")
    tpl = _get_template(template_id, db)
    tpl.name = body.name.strip()
    tpl.stage = body.stage or None
    tpl.subject = body.subject.strip()
    tpl.body = body.body
    db.commit()
    db.refresh(tpl)
    return _template_json(tpl)


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    tpl = _get_template(template_id, db)
    tpl.is_active = False
    db.commit()
    return {"status": "deleted", "id": template_id}


# ── Preview & send ────────────────────────────────────────────────────────────

@router.get("/{template_id}/preview")
def preview_template(
    template_id: int,
    lead_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Subject/body rendered for one lead — what the email will actually say."""
    tpl = _get_template(template_id, db)
    lead = _get_scoped_lead(lead_id, db, current)

    subject, unknown_s = render_template(tpl.subject, lead, current)
    body, unknown_b = render_template(tpl.body, lead, current)

    return {
        "template_id": tpl.id,
        "lead_id": lead.id,
        "to": lead.email,
        "subject": subject,
        "body": body,
        "attachments": _attachment_info(tpl),
        "unknown_tokens": sorted(set(unknown_s + unknown_b)),
        "lead_stage": lead_stage(lead),
    }


@router.post("/{template_id}/send")
def send_template(
    template_id: int,
    req: SendRequest,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """
    Send the (possibly edited) rendered email to the lead, with the template's
    attachments. Human-initiated, so it sends immediately — no approval queue —
    and is logged as a human-handled outbound Interaction.
    """
    tpl = _get_template(template_id, db)
    lead = _get_scoped_lead(req.lead_id, db, current)
    if not lead.email:
        raise HTTPException(status_code=400, detail="This lead has no email address")
    if lead.opt_out:
        raise HTTPException(status_code=400, detail="This lead has opted out of emails")

    subject = (req.subject or "").strip() or render_template(tpl.subject, lead, current)[0]
    body = req.body if (req.body or "").strip() else render_template(tpl.body, lead, current)[0]

    paths = [
        os.path.join(TEMPLATE_FILES_DIR, name)
        for name in attachment_list(tpl)
        if os.path.isfile(os.path.join(TEMPLATE_FILES_DIR, name))
    ]

    sent = send_email(lead.email, subject, body, attachments=paths)

    interaction = Interaction(
        lead_id=lead.id,
        direction="outbound",
        channel="email",
        message_text=f"[{subject}]\n\n{body}",
        handled_by="human",
        sender_user_id=current.id,
        send_status="sent" if sent else "failed",
        message_type="template",
    )
    db.add(interaction)
    lead.last_interaction_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "status": "sent" if sent else "failed",
        "detail": None if sent else "SMTP not configured or send failed — check server logs",
        "to": lead.email,
        "subject": subject,
        "attachments_sent": [os.path.basename(p) for p in paths],
    }


# ── Attachments ───────────────────────────────────────────────────────────────

@router.post("/{template_id}/attachments")
async def upload_attachment(
    template_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    tpl = _get_template(template_id, db)

    name = _sanitize_filename(file.filename)
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext or '(none)'}' not allowed. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    data = await file.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")

    os.makedirs(TEMPLATE_FILES_DIR, exist_ok=True)
    stored = f"t{tpl.id}__{name}"
    with open(os.path.join(TEMPLATE_FILES_DIR, stored), "wb") as f:
        f.write(data)

    files = attachment_list(tpl)
    if stored not in files:
        files.append(stored)
    tpl.attachments = json.dumps(files)
    db.commit()
    db.refresh(tpl)
    return _template_json(tpl)


@router.get("/{template_id}/attachments/{name}")
def download_attachment(template_id: int, name: str, db: Session = Depends(get_db)):
    tpl = _get_template(template_id, db)
    # Only files listed on this template may be fetched — blocks path traversal.
    if name not in attachment_list(tpl):
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = os.path.join(TEMPLATE_FILES_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(path, filename=_UPLOAD_PREFIX.sub("", name))


@router.delete("/{template_id}/attachments/{name}")
def remove_attachment(template_id: int, name: str, db: Session = Depends(get_db)):
    tpl = _get_template(template_id, db)
    files = attachment_list(tpl)
    if name not in files:
        raise HTTPException(status_code=404, detail="Attachment not found")
    tpl.attachments = json.dumps([f for f in files if f != name])
    db.commit()

    # Delete from disk only if this template owns the upload (t{id}__ prefix);
    # shared seeded files (company profile etc.) stay for other templates.
    if name.startswith(f"t{tpl.id}__"):
        try:
            os.remove(os.path.join(TEMPLATE_FILES_DIR, name))
        except OSError:
            pass
    db.refresh(tpl)
    return _template_json(tpl)
