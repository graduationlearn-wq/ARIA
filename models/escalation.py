from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    interaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("interactions.id"), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # low_trust | bot_question | high_value | complex_query | escalation_request | no_response
    reason: Mapped[str] = mapped_column(String(100), nullable=False)

    assigned_to: Mapped[str] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # open | resolved
    status: Mapped[str] = mapped_column(String(20), default="open")

    lead: Mapped["Lead"] = relationship("Lead", back_populates="escalations")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Escalation id={self.id} lead_id={self.lead_id} reason={self.reason}>"
