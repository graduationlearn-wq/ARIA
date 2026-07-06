"""
Per-user email signature images.

Each team member uploads their own signature (the branded block from their mail
client) once; ARIA appends it to the bottom of every email they send from a
template. Stored on disk in signature_files/ (gitignored — personal images), one
file per user, named `u{user_id}.{ext}`.

Endpoints:
  POST   /signatures/me          — upload / replace my signature image (login)
  DELETE /signatures/me          — remove my signature image (login)
  GET    /signatures/{filename}  — serve an image (PUBLIC — email clients fetch it)
"""

import os
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routes.auth import get_current_user

router = APIRouter(prefix="/signatures", tags=["Signatures"])

SIGNATURE_FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signature_files")
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_BYTES = 2 * 1024 * 1024  # 2 MB
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@router.post("/me")
async def upload_my_signature(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Use an image file ({', '.join(sorted(ALLOWED_EXTENSIONS))})",
        )
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image too large (max 2 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")

    os.makedirs(SIGNATURE_FILES_DIR, exist_ok=True)
    # Drop any previous file for this user (a different extension would orphan it).
    for e in ALLOWED_EXTENSIONS:
        old = os.path.join(SIGNATURE_FILES_DIR, f"u{current.id}{e}")
        if os.path.isfile(old):
            try:
                os.remove(old)
            except OSError:
                pass

    stored = f"u{current.id}{ext}"
    with open(os.path.join(SIGNATURE_FILES_DIR, stored), "wb") as f:
        f.write(data)

    current.signature_image = stored
    db.commit()
    return {"signature_image": stored, "url": f"/signatures/{stored}"}


@router.delete("/me")
def delete_my_signature(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fn = current.signature_image
    current.signature_image = None
    db.commit()
    if fn:
        try:
            os.remove(os.path.join(SIGNATURE_FILES_DIR, fn))
        except OSError:
            pass
    return {"signature_image": None}


@router.get("/{filename}")
def get_signature(filename: str):
    """Public — the recipient's email client fetches this to render the signature."""
    safe = _SAFE_NAME.sub("", os.path.basename(filename))
    path = os.path.join(SIGNATURE_FILES_DIR, safe)
    if not safe or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Signature not found")
    return FileResponse(path)
