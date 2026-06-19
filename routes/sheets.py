"""
Sheet sources — manage the Google Sheets ARIA polls for leads.

Each sheet belongs to a team leader (or admin); its leads auto-assign within
that owner's team. Admins manage any leader's sheets; team leaders manage their
own; employees have no access. See [[Lead Sources & Assignment]].
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.sheet_source import SheetSource
from models.user import User
from routes.auth import get_current_user
from services import sheet_sync

router = APIRouter(prefix="/sheets", tags=["Sheet Sync"],
                   dependencies=[Depends(get_current_user)])


class SheetUpsert(BaseModel):
    name: str
    sheet_url: str
    owner_user_id: int | None = None   # which leader's team; defaults to the caller
    is_active: bool | None = None


def _require_manager(current: User):
    if current.role == "employee":
        raise HTTPException(status_code=403, detail="Only team leaders or admins manage sheet sources")


def _resolve_owner(current: User, owner_user_id: int | None, db: Session) -> User:
    """
    Validate who a sheet belongs to. A team leader can only own their own sheets;
    an admin can assign a sheet to any leader/admin. The owner drives assignment.
    """
    if owner_user_id is None or owner_user_id == current.id:
        return current
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="You can only add sheets for your own team")
    owner = db.query(User).filter(User.id == owner_user_id, User.is_active == True).first()  # noqa: E712
    if not owner or owner.role not in ("manager", "admin"):
        raise HTTPException(status_code=400, detail="A sheet must belong to a team leader or admin")
    return owner


def _visible(current: User, db: Session):
    q = db.query(SheetSource)
    if current.role == "manager":
        q = q.filter(SheetSource.owner_user_id == current.id)
    elif current.role == "employee":
        q = q.filter(SheetSource.id == -1)  # none
    return q  # admin → all


def _public(s: SheetSource, names: dict) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "sheet_url": s.sheet_url,
        "owner_user_id": s.owner_user_id,
        "owner_name": names.get(s.owner_user_id),
        "is_active": s.is_active,
        "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
        "last_status": s.last_status,
        "last_imported": s.last_imported,
        "total_imported": s.total_imported,
    }


def _names(db: Session) -> dict:
    return {uid: nm for uid, nm in db.query(User.id, User.name).all()}


@router.get("/")
def list_sheets(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    names = _names(db)
    return {"sheets": [_public(s, names) for s in _visible(current, db).order_by(SheetSource.name).all()]}


@router.post("/")
def create_sheet(body: SheetUpsert, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    _require_manager(current)
    if not body.name.strip() or not body.sheet_url.strip():
        raise HTTPException(status_code=400, detail="Name and sheet URL are required")
    owner = _resolve_owner(current, body.owner_user_id, db)
    s = SheetSource(name=body.name.strip(), sheet_url=body.sheet_url.strip(),
                    owner_user_id=owner.id, is_active=True)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _public(s, _names(db))


def _get_owned(sheet_id: int, current: User, db: Session) -> SheetSource:
    s = db.query(SheetSource).filter(SheetSource.id == sheet_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sheet source not found")
    _require_manager(current)
    if current.role == "manager" and s.owner_user_id != current.id:
        raise HTTPException(status_code=403, detail="That sheet belongs to another team")
    return s


@router.put("/{sheet_id}")
def update_sheet(sheet_id: int, body: SheetUpsert, db: Session = Depends(get_db),
                 current: User = Depends(get_current_user)):
    s = _get_owned(sheet_id, current, db)
    if body.name.strip():
        s.name = body.name.strip()
    if body.sheet_url.strip():
        s.sheet_url = body.sheet_url.strip()
    if body.is_active is not None:
        s.is_active = body.is_active
    if body.owner_user_id is not None:
        s.owner_user_id = _resolve_owner(current, body.owner_user_id, db).id
    db.commit()
    db.refresh(s)
    return _public(s, _names(db))


@router.delete("/{sheet_id}")
def delete_sheet(sheet_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    s = _get_owned(sheet_id, current, db)
    db.delete(s)
    db.commit()
    return {"status": "deleted", "id": sheet_id}


@router.post("/sync-all")
def sync_all(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """
    Sync every active sheet the caller can see (their own, or all for admin).
    Used by the dashboard refresh button so one click pulls sheets + reloads.
    Returns quickly for users with no sheets (e.g. employees).
    """
    sources = _visible(current, db).filter(SheetSource.is_active == True).all()  # noqa: E712
    imported = 0
    for s in sources:
        res = sheet_sync.sync_source(db, s)
        imported += res.get("imported", 0)
    return {"synced": len(sources), "imported": imported}


@router.post("/{sheet_id}/sync")
def sync_now(sheet_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Fetch the sheet right now and import any new leads."""
    s = _get_owned(sheet_id, current, db)
    summary = sheet_sync.sync_source(db, s)
    return {"sheet": _public(s, _names(db)), "result": summary}
