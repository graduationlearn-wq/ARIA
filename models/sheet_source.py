"""
SheetSource — a Google Sheet (or any published CSV URL) that ARIA polls for new
leads. Each sheet belongs to a team leader (or admin); its leads auto-assign
within that owner's team. The scheduler syncs every active source on a timer.
"""

from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class SheetSource(Base):
    __tablename__ = "sheet_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sheet_url: Mapped[str] = mapped_column(Text, nullable=False)

    # The team leader (or admin) this sheet belongs to — drives the assignment pool.
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Sync bookkeeping (shown in the dashboard).
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(200), nullable=True)
    last_imported: Mapped[int] = mapped_column(Integer, default=0)
    total_imported: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<SheetSource id={self.id} name={self.name!r} owner={self.owner_user_id}>"
