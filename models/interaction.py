from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # inbound (lead wrote) | outbound (ARIA/human wrote)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)

    # whatsapp | email | call
    channel: Mapped[str] = mapped_column(String(20), default="email")

    message_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Intent classification (filled for inbound messages)
    intent_label: Mapped[str] = mapped_column(String(100), nullable=True)
    intent_confidence: Mapped[float] = mapped_column(Float, nullable=True)

    # aria | human
    handled_by: Mapped[str] = mapped_column(String(20), default="aria")

    # For outbound messages in human_approval_mode:
    # pending_approval | approved | sent | rejected
    send_status: Mapped[str] = mapped_column(String(30), nullable=True)

    # Quality score for outbound ARIA messages (0.0 – 1.0)
    trust_score: Mapped[float] = mapped_column(Float, nullable=True)

    # Seconds between last inbound and this outbound (response time tracking)
    response_time_sec: Mapped[int] = mapped_column(Integer, nullable=True)

    # Notes from human reviewer (used during approval)
    reviewer_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # first_touch | followup_1 | followup_2 | reply_draft
    # Tracks which step in the outbound sequence this message is
    message_type: Mapped[str] = mapped_column(String(30), nullable=True)

    # ── Relationship ──────────────────────────────────────────────────────────
    lead: Mapped["Lead"] = relationship("Lead", back_populates="interactions")  # noqa: F821

    def __repr__(self) -> str:
        return (f"<Interaction id={self.id} lead_id={self.lead_id} "
                f"direction={self.direction} intent={self.intent_label}>")
