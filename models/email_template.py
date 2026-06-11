"""
EmailTemplate — reusable, stage-aware outbound email templates.

Each template belongs to a pipeline stage (or none = general purpose). The
subject/body contain {placeholders} that are filled from the Lead row and the
logged-in sender at compose time. `attachments` is a JSON list of filenames
stored in the template_files/ directory and sent as real email attachments.
"""

from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Canonical pipeline stage this template is meant for (services/stages.py),
    # or NULL for a general-purpose template usable at any stage.
    stage: Mapped[str] = mapped_column(String(30), nullable=True)

    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON list of filenames (relative to template_files/) sent as attachments.
    attachments: Mapped[str] = mapped_column(Text, default="[]")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<EmailTemplate id={self.id} name={self.name!r} stage={self.stage}>"
