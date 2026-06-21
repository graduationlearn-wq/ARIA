"""
Sheet sync — fetch a published sheet, parse it, and create + auto-assign any
new leads. Runs on a timer (every ~15 min) and on demand.

Supported sources (all read without auth — nothing to provision at deploy time):
  - Google Sheets — fetched via its CSV export URL.
  - OneDrive / SharePoint — fetched via the share link with `download=1`, which
    returns the raw .xlsx.
The link must be shared as "anyone with the link can view" or published to web.
"""

import re

import requests

from database import SessionLocal
from models.sheet_source import SheetSource
from models.user import User
from services import lead_importer, lead_intake

_DOC_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9\-_]+)")
_GID_RE = re.compile(r"[?&#]gid=([0-9]+)")
_ONEDRIVE_HOSTS = ("1drv.ms", "onedrive.live.com", "sharepoint.com")
_FETCH_TIMEOUT = 20  # seconds


def to_csv_url(url: str) -> str:
    """
    Turn a Google Sheets share/edit URL into its CSV export URL.
    Non-Google URLs (already a CSV / published link) are returned unchanged.
    """
    url = (url or "").strip()
    m = _DOC_RE.search(url)
    if not m:
        return url
    doc_id = m.group(1)
    gid_m = _GID_RE.search(url)
    gid = gid_m.group(1) if gid_m else "0"
    return f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"


def is_onedrive_url(url: str) -> bool:
    """True for OneDrive / SharePoint share links (personal or business)."""
    return any(h in (url or "").lower() for h in _ONEDRIVE_HOSTS)


def to_download_url(url: str) -> str:
    """
    OneDrive / SharePoint share links return the raw file when `download=1` is
    set; a plain fetch returns the HTML viewer page instead.
    """
    url = (url or "").strip()
    if "download=1" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}download=1"


def _fetch_url(url: str) -> str:
    """Resolve a share link to the URL that yields machine-readable bytes."""
    url = (url or "").strip()
    return to_download_url(url) if is_onedrive_url(url) else to_csv_url(url)


def fetch_csv(url: str) -> bytes:
    """
    Fetch the sheet's raw bytes — Google CSV export or a OneDrive/SharePoint xlsx
    download. The caller sniffs the bytes to pick the CSV vs xlsx parser.
    Raises ValueError with a friendly message on failure.
    """
    target = _fetch_url(url)
    try:
        resp = requests.get(target, timeout=_FETCH_TIMEOUT, allow_redirects=True)
    except requests.RequestException as e:
        raise ValueError(f"Could not reach the sheet: {e}")
    if resp.status_code != 200:
        raise ValueError(f"Sheet returned HTTP {resp.status_code}")
    # Google/OneDrive serve an HTML login/permission page when not public.
    if "text/html" in resp.headers.get("content-type", "").lower():
        raise ValueError(
            "Sheet isn't publicly readable — share it as 'anyone with the link can view' "
            "or publish it to the web, then try again."
        )
    return resp.content


def sync_source(db, source: SheetSource) -> dict:
    """
    Sync one sheet: fetch → parse → create + auto-assign new leads (dedup skips
    rows already imported on a previous run). Records status on the source.
    Never raises — errors are captured in `last_status` so the scheduler is safe.
    """
    from datetime import datetime, timezone

    owner = db.query(User).filter(User.id == source.owner_user_id).first()
    try:
        data = fetch_csv(source.sheet_url)
        # xlsx files are ZIP archives ("PK..") — anything else is treated as CSV.
        fname = "sheet.xlsx" if data[:2] == b"PK" else "sheet.csv"
        rows = lead_importer.parse_rows(fname, data)
        summary = lead_intake.intake_rows(db, rows, owner, source="sheet")
        source.last_imported = summary["imported"]
        source.total_imported = (source.total_imported or 0) + summary["imported"]
        source.last_status = (
            f"ok — {summary['imported']} new, {summary['duplicates']} dup"
        )
    except Exception as e:  # noqa: BLE001 — record and move on, never crash the job
        summary = {"imported": 0, "duplicates": 0, "errors": [], "assigned": [], "error": str(e)}
        source.last_status = f"error: {str(e)[:180]}"

    source.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    return summary


def run_sheet_sync() -> dict:
    """Scheduler entry point — sync every active sheet source. Owns its DB session."""
    db = SessionLocal()
    try:
        sources = db.query(SheetSource).filter(SheetSource.is_active == True).all()  # noqa: E712
        results = {}
        for s in sources:
            results[s.id] = sync_source(db, s)
        if sources:
            print(f"[SheetSync] Synced {len(sources)} sheet(s).")
        return results
    finally:
        db.close()
