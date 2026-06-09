"""
User model — the team hierarchy that owns and works leads.

Three roles, three levels of visibility:
  • employee — sees only the leads they own (brought in)
  • manager  — sees their whole team's leads (the employees reporting to them)
  • admin    — sees everyone's leads and performance

`manager_id` builds the tree: an employee points at their manager, a manager
points at the admin (or null). Leads carry `owner_id` → the employee who owns them.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="employee")  # employee | manager | admin
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    avatar_seed: Mapped[str] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
